"""Unit tests for backend/routers/admin.py + get_current_admin (ORPHEUS-31).

Two layers of coverage:

  1. `get_current_admin` dependency in backend/auth.py — same JWT
     verification path the other dependencies use, plus the email
     allowlist check.

  2. The four router endpoints — direct handler invocation with
     fake supabase clients (same pattern as test_clients_list.py
     and test_clients_invite.py).

`_resolve_session`'s JWT path is already exhaustively covered by
test_auth.py; we only re-test the allowlist branches here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from backend import auth as auth_mod
from backend import config as config_mod
from backend.auth import SessionRoles
from backend.routers import admin as admin_router


# --------------------------------------------------------------------------- #
# Shared constants
# --------------------------------------------------------------------------- #

SUPABASE_URL = "https://test.supabase.local"
AUDIENCE = "authenticated"
ISSUER = f"{SUPABASE_URL}/auth/v1"
KID = "test-kid-1"
SUB = "11111111-2222-3333-4444-555555555555"

ADMIN_EMAIL = "andrew@ess3.ai"
NON_ADMIN_EMAIL = "stranger@example.com"
MIXED_CASE_ADMIN_EMAIL = "Andrew@Ess3.Ai"

ADMIN_USER_ID = "user-admin-uuid"
ADVISOR_A_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ADVISOR_B_ID = "ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb"
CLIENT_A_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_B_ID = "22222222-2222-2222-2222-222222222222"
JOB_A1_ID = "aaaa1111-0000-0000-0000-000000000000"
JOB_A2_ID = "aaaa2222-0000-0000-0000-000000000000"
JOB_B1_ID = "bbbb1111-0000-0000-0000-000000000000"
NARR_1_ID = "narr1111-0000-0000-0000-000000000000"
NARR_2_ID = "narr2222-0000-0000-0000-000000000000"


_REQUIRED_ENV = {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "SUPABASE_JWT_AUDIENCE": AUDIENCE,
    "RESEND_API_KEY": "test-resend-key",
    "APP_BASE_URL": "https://app.test.local",
}


# --------------------------------------------------------------------------- #
# Fixtures — shared JWT + env handling
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(autouse=True)
def _reset_env_and_cache(monkeypatch, rsa_keypair):
    """Reset env + the JWKS / settings caches for every test."""
    _, public_key = rsa_keypair
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    # Default: a non-empty allowlist with the admin email. Individual
    # tests can monkeypatch this to override.
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN_EMAIL)
    config_mod._reset_settings_cache_for_tests()
    auth_mod._reset_jwks_cache_for_tests()
    # Pre-populate the JWKS cache so the verification path doesn't try
    # to hit the network.
    auth_mod._jwks_cache._keys = {KID: public_key}
    auth_mod._jwks_cache._fetched_at = time.time()


def _pem(private_key) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _sign_admin_token(private_key, email: str = ADMIN_EMAIL) -> str:
    """Mint a JWT for the given email with otherwise-valid claims."""
    now = int(time.time())
    claims = {
        "sub": SUB,
        "email": email,
        "aud": AUDIENCE,
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(claims, _pem(private_key), algorithm="RS256", headers={"kid": KID})


# --------------------------------------------------------------------------- #
# FakeSupabase / FakeTable — same shape as test_auth.py and test_clients_list.py
# --------------------------------------------------------------------------- #

@dataclass
class FakeResult:
    data: list[dict] | None


class FakeTable:
    """Per-table mock supporting select / eq / in_ / order / limit / update."""

    def __init__(self, queue: list[FakeResult]) -> None:
        self._queue = queue
        self._last_update_payload: dict[str, Any] | None = None

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def in_(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def update(self, payload: dict[str, Any]):
        # Capture the update body so tests can assert what got written.
        self._last_update_payload = dict(payload)
        return self

    def execute(self) -> FakeResult:
        if self._queue:
            return self._queue.pop(0)
        return FakeResult(data=[])


class FakeSupabase:
    """Per-table queue. Pass a dict of table_name -> list of FakeResult.

    Each `.execute()` consumes one entry from that table's queue.
    """

    def __init__(self, queues: dict[str, list[FakeResult]]) -> None:
        self._tables: dict[str, FakeTable] = {
            name: FakeTable(list(q)) for name, q in queues.items()
        }
        self.tables_queried: list[str] = []

    def table(self, name: str) -> FakeTable:
        self.tables_queried.append(name)
        if name not in self._tables:
            # Default: empty queue so unexpected accesses don't blow up
            # with a KeyError on dict access. Tests still assert
            # tables_queried explicitly to catch unintended fan-out.
            self._tables[name] = FakeTable([])
        return self._tables[name]


def _admin_roles(email: str = ADMIN_EMAIL) -> SessionRoles:
    """Build a SessionRoles for a hypothetical admin caller.

    The router endpoints don't actually consume the email or role
    fields (the admin check happens upstream in `get_current_admin`),
    but we populate them so the tests can swap in handler-level mocks
    without surprises.
    """
    return SessionRoles(
        user_id=ADMIN_USER_ID,
        email=email,
        access_token="test-token",
        advisor_id=ADVISOR_A_ID,
        client_id=None,
    )


def _patch_supabase(fake: FakeSupabase):
    return patch.object(
        admin_router, "get_service_client", return_value=fake
    )


# --------------------------------------------------------------------------- #
# get_current_admin — JWT + allowlist permutations
# --------------------------------------------------------------------------- #

class _FakeAdminAuthService:
    """For testing get_current_admin: stand-in for the service client used
    inside `_resolve_session`. Returns no rows for either table — the
    admin can be neither-role and still pass the allowlist gate."""

    def table(self, _name: str):
        return _FakeAuthTable()


class _FakeAuthTable:
    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


def _patch_auth_service():
    return patch.object(
        auth_mod, "get_service_client", return_value=_FakeAdminAuthService()
    )


@pytest.mark.asyncio
async def test_admin_allowlist_accepts_listed_email(rsa_keypair):
    """Admin email present in ADMIN_EMAILS → returns SessionRoles, no 403."""
    private_key, _ = rsa_keypair
    token = _sign_admin_token(private_key)

    with _patch_auth_service():
        roles = await auth_mod.get_current_admin(f"Bearer {token}")

    assert roles.user_id == SUB
    assert roles.email == ADMIN_EMAIL
    # No advisor or client row was returned by the stand-in service
    # client; that's the "admin can be neither-role" case.
    assert roles.advisor_id is None
    assert roles.client_id is None


@pytest.mark.asyncio
async def test_admin_allowlist_is_case_insensitive(rsa_keypair, monkeypatch):
    """Allowlist comparison lowercases both sides — mixed-case OK."""
    private_key, _ = rsa_keypair
    # Mixed-case env entry should still match the mixed-case JWT email.
    monkeypatch.setenv("ADMIN_EMAILS", "Andrew@Ess3.Ai,Other@Example.com")
    config_mod._reset_settings_cache_for_tests()

    token = _sign_admin_token(private_key, email=MIXED_CASE_ADMIN_EMAIL)

    with _patch_auth_service():
        roles = await auth_mod.get_current_admin(f"Bearer {token}")

    # The JWT email is preserved verbatim — the lowercase comparison
    # only applies to the membership check.
    assert roles.email == MIXED_CASE_ADMIN_EMAIL


@pytest.mark.asyncio
async def test_admin_allowlist_rejects_non_admin_email(rsa_keypair):
    """Email not in ADMIN_EMAILS → 403 with 'not authorized' detail."""
    private_key, _ = rsa_keypair
    token = _sign_admin_token(private_key, email=NON_ADMIN_EMAIL)

    with _patch_auth_service():
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_admin(f"Bearer {token}")

    assert exc.value.status_code == 403
    assert "not authorized" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_admin_allowlist_rejects_empty_allowlist(rsa_keypair, monkeypatch):
    """Empty ADMIN_EMAILS → 403 with 'allowlist is empty' detail.

    No one is admin when the env var is unset; we surface that
    explicitly rather than letting the membership check fall through
    to a misleading generic 403.
    """
    private_key, _ = rsa_keypair
    monkeypatch.setenv("ADMIN_EMAILS", "")
    config_mod._reset_settings_cache_for_tests()

    token = _sign_admin_token(private_key)

    with _patch_auth_service():
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_admin(f"Bearer {token}")

    assert exc.value.status_code == 403
    assert "allowlist is empty" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_admin_allowlist_still_401s_on_bad_token():
    """Missing Authorization header → 401, not 403.

    Confirms `get_current_admin` doesn't short-circuit the JWT
    verification path (token problems should look like token
    problems, not like authorization problems).
    """
    with pytest.raises(HTTPException) as exc:
        await auth_mod.get_current_admin(None)
    assert exc.value.status_code == 401


# --------------------------------------------------------------------------- #
# GET /admin/clients — list every client across all advisors
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_admin_clients_returns_all_clients_with_advisor_and_job():
    """All-clients god-mode: rows from multiple advisors, latest job per row."""
    fake = FakeSupabase(
        queues={
            "clients": [
                FakeResult(
                    data=[
                        {
                            "id": CLIENT_A_ID,
                            "display_name": "Client A",
                            "email": "a@example.com",
                            "invitation_status": "accepted",
                            "advisor_id": ADVISOR_A_ID,
                            "user_id": "user-a-uuid",
                            "created_at": "2026-05-10T00:00:00+00:00",
                        },
                        {
                            "id": CLIENT_B_ID,
                            "display_name": "Client B",
                            "email": "b@example.com",
                            "invitation_status": "pending",
                            "advisor_id": ADVISOR_B_ID,
                            "user_id": None,
                            "created_at": "2026-05-01T00:00:00+00:00",
                        },
                    ]
                )
            ],
            "jobs": [
                FakeResult(
                    data=[
                        {
                            "id": JOB_A2_ID,
                            "client_id": CLIENT_A_ID,
                            "status": "complete",
                            "created_at": "2026-05-12T00:00:00+00:00",
                        },
                        {
                            "id": JOB_A1_ID,
                            "client_id": CLIENT_A_ID,
                            "status": "failed",
                            "created_at": "2026-05-08T00:00:00+00:00",
                        },
                    ]
                )
            ],
            "advisors": [
                FakeResult(
                    data=[
                        {
                            "id": ADVISOR_A_ID,
                            "user_id": "user-advisor-a-uuid",
                            "practice_name": "Andrew's Practice",
                        },
                        {
                            "id": ADVISOR_B_ID,
                            "user_id": "user-advisor-b-uuid",
                            "practice_name": None,
                        },
                    ]
                )
            ],
        }
    )

    # Stub the auth.users email lookup — ORPHEUS-59 follow-up. The
    # handler reads advisor emails from auth.users (not public.advisors)
    # via admin_router._resolve_advisor_emails; patching the helper
    # avoids needing a FakeSupabase auth.admin surface.
    with _patch_supabase(fake), patch.object(
        admin_router,
        "_resolve_advisor_emails",
        return_value={
            "user-advisor-a-uuid": ADMIN_EMAIL,
            "user-advisor-b-uuid": "advisor-b@example.com",
        },
    ):
        response = await admin_router.list_admin_clients(_admin=_admin_roles())

    assert len(response.clients) == 2
    a, b = response.clients

    assert a.id == CLIENT_A_ID
    assert a.advisor is not None
    assert a.advisor.practice_name == "Andrew's Practice"
    assert a.latest_job is not None
    # Most recent of A's two jobs.
    assert a.latest_job.id == JOB_A2_ID
    assert a.latest_job.status == "complete"

    assert b.id == CLIENT_B_ID
    assert b.advisor is not None
    assert b.advisor.practice_name is None
    assert b.advisor.email == "advisor-b@example.com"
    assert b.latest_job is None

    assert fake.tables_queried == ["clients", "jobs", "advisors"]


@pytest.mark.asyncio
async def test_list_admin_clients_empty_skips_jobs_and_advisors_queries():
    """Empty clients table → only one query."""
    fake = FakeSupabase(queues={"clients": [FakeResult(data=[])]})

    with _patch_supabase(fake):
        response = await admin_router.list_admin_clients(_admin=_admin_roles())

    assert response.clients == []
    assert fake.tables_queried == ["clients"]


# --------------------------------------------------------------------------- #
# _resolve_advisor_emails — auth.users join used by /admin/clients
# --------------------------------------------------------------------------- #


@dataclass
class _FakeAuthUser:
    """Stand-in for supabase-py's User model (the relevant attrs only)."""

    id: str
    email: str


class _FakeAuthAdmin:
    """Mock for `supabase.auth.admin` — exposes `list_users()`."""

    def __init__(self, users: list[Any] | Any) -> None:
        self._users = users

    def list_users(self):
        return self._users


class _FakeAuthClient:
    def __init__(self, admin: _FakeAuthAdmin) -> None:
        self.admin = admin


class _FakeSupabaseWithAuth:
    """Minimal supabase stand-in carrying just `.auth.admin.list_users()`."""

    def __init__(self, users: list[Any] | Any) -> None:
        self.auth = _FakeAuthClient(_FakeAuthAdmin(users))


def test_resolve_advisor_emails_filters_to_wanted_user_ids():
    """The helper returns only the user_ids that were passed in.

    list_users() returns every auth user in the project — filtering
    to the advisor user_ids we actually care about happens client-
    side so the caller can ignore the rest.
    """
    fake = _FakeSupabaseWithAuth(
        users=[
            _FakeAuthUser(id="user-advisor-a-uuid", email="andrew@example.com"),
            _FakeAuthUser(id="user-advisor-b-uuid", email="advisor-b@example.com"),
            _FakeAuthUser(id="some-other-user-uuid", email="noise@example.com"),
        ]
    )
    advisor_rows = [
        {"id": ADVISOR_A_ID, "user_id": "user-advisor-a-uuid"},
        {"id": ADVISOR_B_ID, "user_id": "user-advisor-b-uuid"},
    ]

    result = admin_router._resolve_advisor_emails(fake, advisor_rows)

    assert result == {
        "user-advisor-a-uuid": "andrew@example.com",
        "user-advisor-b-uuid": "advisor-b@example.com",
    }


def test_resolve_advisor_emails_handles_listusersresponse_shape():
    """supabase-py wraps the user list in ListUsersResponse on some versions.

    The helper handles both: bare list and an object with `.users`.
    """
    wrapped = SimpleNamespace(
        users=[
            _FakeAuthUser(id="user-advisor-a-uuid", email="andrew@example.com"),
        ]
    )
    fake = _FakeSupabaseWithAuth(users=wrapped)
    advisor_rows = [{"id": ADVISOR_A_ID, "user_id": "user-advisor-a-uuid"}]

    result = admin_router._resolve_advisor_emails(fake, advisor_rows)

    assert result == {"user-advisor-a-uuid": "andrew@example.com"}


def test_resolve_advisor_emails_returns_empty_when_no_user_ids():
    """No advisor rows / no user_ids → no auth call needed.

    Skipping the auth.admin call when the input is empty keeps the
    happy path quiet for the (rare) all-clients-have-no-advisor case.
    """

    class _NoOpAuth:
        """Will raise if list_users is called."""

        @property
        def auth(self):
            raise AssertionError("list_users should not be called")

    advisor_rows: list[dict[str, Any]] = []
    result = admin_router._resolve_advisor_emails(_NoOpAuth(), advisor_rows)
    assert result == {}


def test_resolve_advisor_emails_degrades_to_empty_on_exception():
    """Auth admin API failure is not fatal — email is a UI label fallback.

    Practice_name is the primary identifier; missing email just means
    advisors without a practice_name show their id instead.
    """

    class _FailingAuthClient:
        class _Admin:
            def list_users(self):
                raise RuntimeError("boom")

        admin = _Admin()

    class _FailingSupabase:
        auth = _FailingAuthClient()

    advisor_rows = [{"id": ADVISOR_A_ID, "user_id": "user-advisor-a-uuid"}]
    result = admin_router._resolve_advisor_emails(_FailingSupabase(), advisor_rows)
    assert result == {}


# --------------------------------------------------------------------------- #
# GET /admin/jobs — list every job, narrative metadata nested
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_admin_jobs_unfiltered_with_narratives():
    """No client_id filter: every job returned, narratives grouped by job."""
    fake = FakeSupabase(
        queues={
            "jobs": [
                FakeResult(
                    data=[
                        {
                            "id": JOB_A2_ID,
                            "client_id": CLIENT_A_ID,
                            "status": "complete",
                            "version_label": "v2",
                            "created_at": "2026-05-12T00:00:00+00:00",
                            "started_at": "2026-05-12T00:00:10+00:00",
                            "completed_at": "2026-05-12T00:00:30+00:00",
                            "error_message": None,
                        },
                        {
                            "id": JOB_B1_ID,
                            "client_id": CLIENT_B_ID,
                            "status": "failed",
                            "version_label": "v2",
                            "created_at": "2026-05-10T00:00:00+00:00",
                            "started_at": None,
                            "completed_at": None,
                            "error_message": "ZIP parse failed",
                        },
                    ]
                )
            ],
            "clients": [
                FakeResult(
                    data=[
                        {
                            "id": CLIENT_A_ID,
                            "display_name": "Client A",
                            "email": "a@example.com",
                        },
                        {
                            "id": CLIENT_B_ID,
                            "display_name": "Client B",
                            "email": "b@example.com",
                        },
                    ]
                )
            ],
            "narratives": [
                FakeResult(
                    data=[
                        {
                            "id": NARR_1_ID,
                            "job_id": JOB_A2_ID,
                            "section": "Profile Signal Clarity",
                            "status": "draft",
                            "edited_text": "  ",  # whitespace-only counts as not-edited
                            "published_at": None,
                            "generated_at": "2026-05-12T00:00:30+00:00",
                        },
                        {
                            "id": NARR_2_ID,
                            "job_id": JOB_A2_ID,
                            "section": "forward_brief",
                            "status": "published",
                            "edited_text": "Polished prose.",
                            "published_at": "2026-05-13T00:00:00+00:00",
                            "generated_at": "2026-05-12T00:00:30+00:00",
                        },
                    ]
                )
            ],
        }
    )

    with _patch_supabase(fake):
        response = await admin_router.list_admin_jobs(
            _admin=_admin_roles(), client_id=None
        )

    assert len(response.jobs) == 2
    job_a, job_b = response.jobs

    assert job_a.id == JOB_A2_ID
    assert job_a.client_display_name == "Client A"
    assert job_a.error_message is None
    assert len(job_a.narratives) == 2
    # has_edited_text differentiates the whitespace-only edit from the real one.
    by_id = {n.id: n for n in job_a.narratives}
    assert by_id[NARR_1_ID].has_edited_text is False
    assert by_id[NARR_2_ID].has_edited_text is True
    assert by_id[NARR_2_ID].status == "published"

    assert job_b.id == JOB_B1_ID
    assert job_b.error_message == "ZIP parse failed"
    assert job_b.narratives == []  # no narratives for this job

    assert fake.tables_queried == ["jobs", "clients", "narratives"]


@pytest.mark.asyncio
async def test_list_admin_jobs_with_client_filter():
    """`?client_id=` filter narrows to one client's jobs."""
    fake = FakeSupabase(
        queues={
            "jobs": [
                FakeResult(
                    data=[
                        {
                            "id": JOB_A2_ID,
                            "client_id": CLIENT_A_ID,
                            "status": "complete",
                            "version_label": None,
                            "created_at": "2026-05-12T00:00:00+00:00",
                            "started_at": None,
                            "completed_at": None,
                            "error_message": None,
                        }
                    ]
                )
            ],
            "clients": [
                FakeResult(
                    data=[
                        {
                            "id": CLIENT_A_ID,
                            "display_name": "Client A",
                            "email": "a@example.com",
                        }
                    ]
                )
            ],
            "narratives": [FakeResult(data=[])],
        }
    )

    with _patch_supabase(fake):
        response = await admin_router.list_admin_jobs(
            _admin=_admin_roles(), client_id=CLIENT_A_ID
        )

    assert len(response.jobs) == 1
    assert response.jobs[0].client_id == CLIENT_A_ID


@pytest.mark.asyncio
async def test_list_admin_jobs_empty_skips_followup_queries():
    """Empty jobs table → no clients or narratives lookups."""
    fake = FakeSupabase(queues={"jobs": [FakeResult(data=[])]})

    with _patch_supabase(fake):
        response = await admin_router.list_admin_jobs(
            _admin=_admin_roles(), client_id=None
        )

    assert response.jobs == []
    assert fake.tables_queried == ["jobs"]


# --------------------------------------------------------------------------- #
# GET /admin/narratives/{id}
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_admin_narrative_returns_full_row():
    fake = FakeSupabase(
        queues={
            "narratives": [
                FakeResult(
                    data=[
                        {
                            "id": NARR_1_ID,
                            "job_id": JOB_A2_ID,
                            "section": "Profile Signal Clarity",
                            "generated_text": "AI-generated narrative.",
                            "edited_text": "Hand-polished version.",
                            "status": "draft",
                            "published_at": None,
                            "generated_at": "2026-05-12T00:00:30+00:00",
                        }
                    ]
                )
            ]
        }
    )

    with _patch_supabase(fake):
        response = await admin_router.get_admin_narrative(
            narrative_id=NARR_1_ID, _admin=_admin_roles()
        )

    assert response.id == NARR_1_ID
    assert response.generated_text == "AI-generated narrative."
    assert response.edited_text == "Hand-polished version."
    assert response.status == "draft"


@pytest.mark.asyncio
async def test_get_admin_narrative_404_when_missing():
    fake = FakeSupabase(queues={"narratives": [FakeResult(data=[])]})

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await admin_router.get_admin_narrative(
                narrative_id=NARR_1_ID, _admin=_admin_roles()
            )

    assert exc.value.status_code == 404


# --------------------------------------------------------------------------- #
# PATCH /admin/narratives/{id}
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_patch_admin_narrative_updates_edited_text():
    fake = FakeSupabase(
        queues={
            "narratives": [
                # Existence check
                FakeResult(data=[{"id": NARR_1_ID}]),
                # Update result
                FakeResult(
                    data=[
                        {
                            "id": NARR_1_ID,
                            "job_id": JOB_A2_ID,
                            "section": "Profile Signal Clarity",
                            "generated_text": "Original generated.",
                            "edited_text": "Polished prose.",
                            "status": "draft",
                            "published_at": None,
                            "generated_at": "2026-05-12T00:00:30+00:00",
                        }
                    ]
                ),
            ]
        }
    )
    body = admin_router.UpdateAdminNarrativeRequest(edited_text="Polished prose.")

    with _patch_supabase(fake):
        response = await admin_router.update_admin_narrative(
            narrative_id=NARR_1_ID,
            request=body,
            _admin=_admin_roles(),
        )

    assert response.edited_text == "Polished prose."
    # Confirm the update payload carried `edited_text` (and only `edited_text`).
    assert fake._tables["narratives"]._last_update_payload == {
        "edited_text": "Polished prose."
    }


@pytest.mark.asyncio
async def test_patch_admin_narrative_publishes_status():
    fake = FakeSupabase(
        queues={
            "narratives": [
                FakeResult(data=[{"id": NARR_1_ID}]),
                FakeResult(
                    data=[
                        {
                            "id": NARR_1_ID,
                            "job_id": JOB_A2_ID,
                            "section": "Profile Signal Clarity",
                            "generated_text": "Original.",
                            "edited_text": None,
                            "status": "published",
                            "published_at": "2026-05-31T12:00:00+00:00",
                            "generated_at": "2026-05-12T00:00:30+00:00",
                        }
                    ]
                ),
            ]
        }
    )
    body = admin_router.UpdateAdminNarrativeRequest(status="published")

    with _patch_supabase(fake):
        response = await admin_router.update_admin_narrative(
            narrative_id=NARR_1_ID,
            request=body,
            _admin=_admin_roles(),
        )

    assert response.status == "published"
    assert fake._tables["narratives"]._last_update_payload == {
        "status": "published"
    }


@pytest.mark.asyncio
async def test_patch_admin_narrative_rejects_invalid_status():
    fake = FakeSupabase(queues={"narratives": [FakeResult(data=[{"id": NARR_1_ID}])]})
    body = admin_router.UpdateAdminNarrativeRequest(status="archived")

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await admin_router.update_admin_narrative(
                narrative_id=NARR_1_ID,
                request=body,
                _admin=_admin_roles(),
            )

    assert exc.value.status_code == 400
    assert "draft" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_patch_admin_narrative_404_when_missing():
    fake = FakeSupabase(queues={"narratives": [FakeResult(data=[])]})
    body = admin_router.UpdateAdminNarrativeRequest(edited_text="anything")

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await admin_router.update_admin_narrative(
                narrative_id=NARR_1_ID,
                request=body,
                _admin=_admin_roles(),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_admin_narrative_empty_body_is_noop():
    """Empty body → return current row, no UPDATE call.

    The editor's save-on-blur path can fire with nothing changed;
    no-oping is friendlier than 400-ing on it.
    """
    fake = FakeSupabase(
        queues={
            "narratives": [
                # Existence check
                FakeResult(data=[{"id": NARR_1_ID}]),
                # Current-row fetch (no-op path)
                FakeResult(
                    data=[
                        {
                            "id": NARR_1_ID,
                            "job_id": JOB_A2_ID,
                            "section": "Profile Signal Clarity",
                            "generated_text": "Original.",
                            "edited_text": None,
                            "status": "draft",
                            "published_at": None,
                            "generated_at": "2026-05-12T00:00:30+00:00",
                        }
                    ]
                ),
            ]
        }
    )
    body = admin_router.UpdateAdminNarrativeRequest()

    with _patch_supabase(fake):
        response = await admin_router.update_admin_narrative(
            narrative_id=NARR_1_ID,
            request=body,
            _admin=_admin_roles(),
        )

    assert response.id == NARR_1_ID
    # No `update(...)` was called.
    assert fake._tables["narratives"]._last_update_payload is None
