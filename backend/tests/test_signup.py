"""Unit tests for backend/routers/signup.py — POST /signup/complete
(ORPHEUS-85; gate expanded onto the signup_codes table by ORPHEUS-129).

Same direct-handler-invocation pattern as test_accept_invitation.py.
The FakeSupabase supports select + insert chains, per-call `count`
responses (for the max_uses redemption count), and can raise from
`execute()` to simulate migration 014's unique-violation race.

The decision tree under test:

  1. feature gate (503 when HOUSE_ADVISOR_ID unset)
  2. idempotent replay for already-linked callers — BEFORE the code
     check, so a disabled/expired code can't lock a returning client out
  3. code validation against signup_codes (403 on unknown / disabled /
     expired / fully-redeemed — one generic detail for all four)
  4. advisor resolution: code advisor_id override, else house; 503 on
     a dangling advisor reference
  5. INSERT under the resolved advisor, born 'accepted', token NULL
  6. redemption recorded best-effort (failure logs, never unwinds)
  7. 23505 race backstop refetches by user_id (no redemption recorded)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.routers import signup as signup_router


HOUSE_ADVISOR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
GROUP_ADVISOR_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
CODE_ID = "cccccccc-dddd-eeee-ffff-000000000000"
BETA_CODE = "ORPH-BETA-2026"
USER_ID = "user-a-uuid"
EMAIL = "newclient@example.com"
NEW_CLIENT_ID = "99999999-aaaa-bbbb-cccc-dddddddddddd"
EXISTING_CLIENT_ID = "11111111-2222-3333-4444-555555555555"


_REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.local",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "RESEND_API_KEY": "test-resend-key",
    "APP_BASE_URL": "https://app.test.local",
    # ORPHEUS-85 feature gate — on by default for these tests; the
    # disabled case deletes it explicitly.
    "HOUSE_ADVISOR_ID": HOUSE_ADVISOR_ID,
}


@pytest.fixture(autouse=True)
def _reset_env_and_cache(monkeypatch):
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    config_mod._reset_settings_cache_for_tests()
    yield
    config_mod._reset_settings_cache_for_tests()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _roles(
    *,
    user_id: str = USER_ID,
    email: str = EMAIL,
    advisor_id: str | None = None,
    client_id: str | None = None,
) -> SessionRoles:
    """Freshly-signed-up caller by default — both role fields None."""
    return SessionRoles(
        user_id=user_id,
        email=email,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


def _request(
    *,
    beta_code: str = BETA_CODE,
    display_name: str | None = "New Client",
) -> signup_router.SignupCompleteRequest:
    return signup_router.SignupCompleteRequest(
        beta_code=beta_code,
        display_name=display_name,
    )


def _code_row(
    *,
    advisor_id: str | None = None,
    expires_at: datetime | None = None,
    max_uses: int | None = None,
    disabled_at: str | None = None,
) -> dict[str, Any]:
    """A signup_codes row as supabase-py returns it from SELECT *."""
    return {
        "id": CODE_ID,
        "code": BETA_CODE,
        "label": "Closed beta",
        "advisor_id": advisor_id,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "max_uses": max_uses,
        "disabled_at": disabled_at,
        "created_by": "josh@ess3.ai",
        "created_at": "2026-08-12T00:00:00+00:00",
    }


class _Chain:
    """Supabase chain stand-in: select / eq / ilike / limit / insert / execute."""

    def __init__(self, parent: "FakeSupabase", table_name: str) -> None:
        self._parent = parent
        self._table = table_name

    def select(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def ilike(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def insert(self, payload: dict[str, Any]) -> "_Chain":
        self._parent.captured_inserts.append(
            {"table": self._table, "payload": payload}
        )
        return self

    def execute(self) -> SimpleNamespace:
        if self._parent.responses:
            response = self._parent.responses.pop(0)
        else:
            response = {"data": []}
        if "raise" in response:
            raise response["raise"]
        # `count` defaults to None (only redemption-count queries set it).
        return SimpleNamespace(**{"count": None, **response})


class FakeSupabase:
    """Configurable fake for the signup flow.

    Handler calls in order (full happy path, code without max_uses):
      1. SELECT signup_codes by code (ilike)
      2. SELECT advisors by id          (resolution probe)
      3. INSERT clients                 (row creation)
      4. INSERT code_redemptions        (attribution)
    A code WITH max_uses adds a redemption-count SELECT between 1 and 2.
    """

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.captured_inserts: list[dict[str, Any]] = []

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)

    def inserts_for(self, table: str) -> list[dict[str, Any]]:
        return [
            entry["payload"]
            for entry in self.captured_inserts
            if entry["table"] == table
        ]


def _patch_supabase(fake: FakeSupabase):
    return patch.object(signup_router, "get_service_client", return_value=fake)


# --------------------------------------------------------------------------- #
# Feature gate — fail closed
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_signup_disabled_without_house_advisor(monkeypatch):
    """HOUSE_ADVISOR_ID unset → 503, no DB traffic."""
    monkeypatch.delenv("HOUSE_ADVISOR_ID", raising=False)
    config_mod._reset_settings_cache_for_tests()

    fake = FakeSupabase(responses=[])
    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(),
                roles=_roles(),
            )

    assert exc.value.status_code == 503
    assert "not enabled" in exc.value.detail.lower()
    assert fake.captured_inserts == []


# --------------------------------------------------------------------------- #
# Idempotent replay — already-linked caller
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_signup_already_linked_caller_is_idempotent():
    """Caller with an existing clients row gets it back, created=False,
    no INSERT and no code lookup. This is the ORPHEUS-83 invariant."""
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(),
            roles=_roles(client_id=EXISTING_CLIENT_ID),
        )

    assert response.client_id == EXISTING_CLIENT_ID
    assert response.created is False
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_signup_replay_wins_over_dead_code():
    """Already-linked caller with a code that would be rejected still
    gets their row back. Pins the check ordering: replay runs before the
    code check so a disabled/expired code can't lock a returning client
    out of the portal they already belong to."""
    # No responses queued — the replay path must not touch the DB.
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(beta_code="long-since-disabled-code"),
            roles=_roles(client_id=EXISTING_CLIENT_ID),
        )

    assert response.client_id == EXISTING_CLIENT_ID
    assert response.created is False


# --------------------------------------------------------------------------- #
# Code validation — signup_codes table (ORPHEUS-129)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_signup_unknown_code_returns_403():
    fake = FakeSupabase(responses=[{"data": []}])  # code lookup misses

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(beta_code="no-such-code"),
                roles=_roles(),
            )

    assert exc.value.status_code == 403
    assert "code" in exc.value.detail.lower()
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_signup_disabled_code_returns_403():
    """disabled_at set → same generic 403 as unknown (no enumeration)."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row(disabled_at="2026-08-01T00:00:00+00:00")]},
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(),
                roles=_roles(),
            )

    assert exc.value.status_code == 403
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_signup_expired_code_returns_403():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    fake = FakeSupabase(responses=[{"data": [_code_row(expires_at=past)]}])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(),
                roles=_roles(),
            )

    assert exc.value.status_code == 403
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_signup_fully_redeemed_code_returns_403():
    """max_uses reached (counted from code_redemptions) → 403."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row(max_uses=25)]},   # code lookup
            {"data": [], "count": 25},            # redemption count == cap
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(),
                roles=_roles(),
            )

    assert exc.value.status_code == 403
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_signup_code_under_max_uses_passes():
    """max_uses set but not reached → sign-up proceeds and the
    redemption is recorded."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row(max_uses=25)]},       # code lookup
            {"data": [], "count": 24},                # one seat left
            {"data": [{"id": HOUSE_ADVISOR_ID}]},     # advisor probe
            {"data": [{"id": NEW_CLIENT_ID}]},        # INSERT clients
            {"data": [{"id": "redemption-uuid"}]},    # INSERT redemption
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(),
            roles=_roles(),
        )

    assert response.created is True
    redemptions = fake.inserts_for("code_redemptions")
    assert redemptions == [{"code_id": CODE_ID, "client_id": NEW_CLIENT_ID}]


@pytest.mark.asyncio
async def test_signup_code_is_stripped_before_lookup():
    """Leading/trailing whitespace on the submitted code is forgiven —
    the classic copy-paste-from-email artifact. Pinned via the ilike
    argument the handler passes."""
    captured_patterns: list[str] = []

    class _SpyChain(_Chain):
        def ilike(self, _column: str, pattern: str) -> "_Chain":  # type: ignore[override]
            captured_patterns.append(pattern)
            return self

    class _SpyFake(FakeSupabase):
        def table(self, name: str) -> _Chain:
            return _SpyChain(self, name)

    fake = _SpyFake(
        responses=[
            {"data": [_code_row()]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"data": [{"id": NEW_CLIENT_ID}]},
            {"data": [{"id": "redemption-uuid"}]},
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(beta_code=f"  {BETA_CODE}  "),
            roles=_roles(),
        )

    assert response.created is True
    assert captured_patterns == [BETA_CODE]


def test_escape_ilike_neutralizes_wildcards():
    """A vanity code containing % or _ must match literally, not as a
    pattern — pins the escaping helper directly."""
    assert signup_router._escape_ilike("A%B_C") == "A\\%B\\_C"
    assert signup_router._escape_ilike("plain") == "plain"
    assert signup_router._escape_ilike("back\\slash") == "back\\\\slash"


# --------------------------------------------------------------------------- #
# Advisor resolution — house default vs. code override (ORPHEUS-129)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_signup_defaults_to_house_advisor():
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row(advisor_id=None)]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"data": [{"id": NEW_CLIENT_ID}]},
            {"data": [{"id": "redemption-uuid"}]},
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(),
            roles=_roles(),
        )

    assert response.created is True
    clients_payload = fake.inserts_for("clients")[0]
    assert clients_payload["advisor_id"] == HOUSE_ADVISOR_ID


@pytest.mark.asyncio
async def test_signup_group_code_routes_to_its_advisor():
    """A code carrying advisor_id overrides the house default — the
    group/business routing case."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row(advisor_id=GROUP_ADVISOR_ID)]},
            {"data": [{"id": GROUP_ADVISOR_ID}]},     # probe hits the GROUP row
            {"data": [{"id": NEW_CLIENT_ID}]},
            {"data": [{"id": "redemption-uuid"}]},
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(),
            roles=_roles(),
        )

    assert response.created is True
    clients_payload = fake.inserts_for("clients")[0]
    assert clients_payload["advisor_id"] == GROUP_ADVISOR_ID


@pytest.mark.asyncio
async def test_signup_missing_resolved_advisor_returns_503():
    """Resolved advisor (house or override) has no advisors row →
    explicit 503, not a downstream FK-violation 500."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},
            {"data": []},                              # advisor probe misses
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(),
                roles=_roles(),
            )

    assert exc.value.status_code == 503
    assert "misconfigured" in exc.value.detail.lower()
    assert fake.captured_inserts == []


# --------------------------------------------------------------------------- #
# Happy path — row creation + redemption
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_signup_happy_path_creates_row_and_redemption():
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"data": [{"id": NEW_CLIENT_ID}]},
            {"data": [{"id": "redemption-uuid"}]},
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(display_name="New Client"),
            roles=_roles(email="NewClient@Example.com"),
        )

    assert response.client_id == NEW_CLIENT_ID
    assert response.created is True

    clients_payload = fake.inserts_for("clients")[0]
    assert clients_payload["advisor_id"] == HOUSE_ADVISOR_ID
    assert clients_payload["user_id"] == USER_ID
    assert clients_payload["display_name"] == "New Client"
    # Email normalized the same way the invite flow normalizes.
    assert clients_payload["email"] == "newclient@example.com"
    # Born linked: accepted status, no token lifecycle.
    assert clients_payload["invitation_status"] == "accepted"
    assert clients_payload["invitation_token"] is None
    assert clients_payload["invitation_expires_at"] is None

    # Attribution recorded.
    assert fake.inserts_for("code_redemptions") == [
        {"code_id": CODE_ID, "client_id": NEW_CLIENT_ID}
    ]


@pytest.mark.asyncio
async def test_signup_display_name_falls_back_to_email_local_part():
    """No display_name from LinkedIn metadata → email local-part, not a
    blank label (clients.display_name is NOT NULL)."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"data": [{"id": NEW_CLIENT_ID}]},
            {"data": [{"id": "redemption-uuid"}]},
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(display_name=None),
            roles=_roles(email="pat.doe@example.com"),
        )

    assert response.created is True
    assert fake.inserts_for("clients")[0]["display_name"] == "pat.doe"


@pytest.mark.asyncio
async def test_signup_advisor_caller_without_client_row_can_sign_up():
    """An advisor with no clients row of their own may self-serve sign
    up as a client (dual-role support — same posture as
    /accept-invitation, which only guards client_id)."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"data": [{"id": NEW_CLIENT_ID}]},
            {"data": [{"id": "redemption-uuid"}]},
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(),
            roles=_roles(advisor_id="some-advisor-uuid"),
        )

    assert response.client_id == NEW_CLIENT_ID
    assert response.created is True


@pytest.mark.asyncio
async def test_signup_redemption_failure_does_not_unwind_account():
    """A failed code_redemptions INSERT logs and continues — the client
    exists; bookkeeping must not punish the user (best-effort posture,
    same family as the report-ready email sends)."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"data": [{"id": NEW_CLIENT_ID}]},
            {"raise": RuntimeError("redemption insert blew up")},
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(),
            roles=_roles(),
        )

    assert response.client_id == NEW_CLIENT_ID
    assert response.created is True


# --------------------------------------------------------------------------- #
# Race backstop — migration 014 unique violation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_signup_unique_violation_refetches_and_returns_existing():
    """23505 on clients INSERT (concurrent completion or invitation
    acceptance linked this user first) → refetch by user_id →
    created=False, and NO redemption recorded (the winner recorded its
    own)."""

    class FakeUniqueViolation(Exception):
        code = "23505"

    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},                        # code lookup
            {"data": [{"id": HOUSE_ADVISOR_ID}]},           # advisor probe
            {"raise": FakeUniqueViolation(                  # clients INSERT blows up
                'duplicate key value violates unique constraint '
                '"clients_user_id_unique"'
            )},
            {"data": [{"id": EXISTING_CLIENT_ID}]},         # refetch by user_id
        ]
    )

    with _patch_supabase(fake):
        response = await signup_router.complete_signup(
            request=_request(),
            roles=_roles(),
        )

    assert response.client_id == EXISTING_CLIENT_ID
    assert response.created is False
    assert fake.inserts_for("code_redemptions") == []


@pytest.mark.asyncio
async def test_signup_unique_violation_with_empty_refetch_returns_500():
    """23505 but the refetch finds nothing — surface a 500 rather than
    pretending success. Shouldn't happen; pinned so it stays loud."""

    class FakeUniqueViolation(Exception):
        code = "23505"

    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"raise": FakeUniqueViolation("23505")},
            {"data": []},                                    # refetch misses
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(),
                roles=_roles(),
            )

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_signup_empty_insert_result_returns_500():
    """Defensive: clients INSERT succeeded but returned no data → 500."""
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row()]},
            {"data": [{"id": HOUSE_ADVISOR_ID}]},
            {"data": []},                                    # empty INSERT result
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await signup_router.complete_signup(
                request=_request(),
                roles=_roles(),
            )

    assert exc.value.status_code == 500
