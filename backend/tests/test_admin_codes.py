"""Unit tests for the /admin/codes endpoints (ORPHEUS-129).

Direct handler invocation with a fake supabase client — same pattern
as test_signup.py / test_admin.py's router layer. The get_current_admin
dependency itself is covered in test_admin.py; here the handlers
receive a pre-built SessionRoles.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.routers import admin as admin_router


ADMIN_EMAIL = "josh@ess3.ai"
CODE_ID = "cccccccc-dddd-eeee-ffff-000000000000"
GROUP_ADVISOR_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


_REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.local",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "RESEND_API_KEY": "test-resend-key",
    "APP_BASE_URL": "https://app.test.local",
    "ADMIN_EMAILS": ADMIN_EMAIL,
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

def _admin_roles() -> SessionRoles:
    return SessionRoles(
        user_id="admin-user-uuid",
        email=ADMIN_EMAIL,
        access_token="test-token",
        advisor_id=None,
        client_id=None,
    )


def _code_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": CODE_ID,
        "code": "ORPH-AAAA-BBBB",
        "label": "Closed beta",
        "advisor_id": None,
        "expires_at": None,
        "max_uses": None,
        "disabled_at": None,
        "created_by": ADMIN_EMAIL,
        "created_at": "2026-08-12T00:00:00+00:00",
    }
    row.update(overrides)
    return row


class _Chain:
    def __init__(self, parent: "FakeSupabase", table_name: str) -> None:
        self._parent = parent
        self._table = table_name

    def select(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def in_(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def insert(self, payload: dict[str, Any]) -> "_Chain":
        self._parent.captured_inserts.append(
            {"table": self._table, "payload": payload}
        )
        return self

    def update(self, payload: dict[str, Any]) -> "_Chain":
        self._parent.captured_updates.append(
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
        return SimpleNamespace(**{"count": None, **response})


class FakeSupabase:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.captured_inserts: list[dict[str, Any]] = []
        self.captured_updates: list[dict[str, Any]] = []

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)


def _patch_supabase(fake: FakeSupabase):
    return patch.object(admin_router, "get_service_client", return_value=fake)


# --------------------------------------------------------------------------- #
# Code generation
# --------------------------------------------------------------------------- #

def test_generate_code_shape_and_alphabet():
    """ORPH-XXXX-XXXX from the unambiguous alphabet — no lookalikes."""
    for _ in range(50):
        code = admin_router._generate_code()
        prefix, a, b = code.split("-")
        assert prefix == "ORPH"
        assert len(a) == len(b) == 4
        for ch in a + b:
            assert ch in admin_router._CODE_ALPHABET
            assert ch not in "ILO01"


# --------------------------------------------------------------------------- #
# GET /admin/codes
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_codes_with_redemption_counts_and_advisor_labels():
    """Codes come back newest-first with counts bucketed from the
    redemptions table and practice names resolved for routing codes."""
    other_code_id = "dddddddd-eeee-ffff-0000-111111111111"
    fake = FakeSupabase(
        responses=[
            {"data": [
                _code_row(),
                _code_row(
                    id=other_code_id,
                    code="ACME2027",
                    label="Acme cohort",
                    advisor_id=GROUP_ADVISOR_ID,
                ),
            ]},                                                # codes
            {"data": [
                {"code_id": CODE_ID},
                {"code_id": CODE_ID},
                {"code_id": other_code_id},
            ]},                                                # redemptions
            {"data": [
                {"id": GROUP_ADVISOR_ID, "practice_name": "Acme Advisory"},
            ]},                                                # advisors
        ]
    )

    with _patch_supabase(fake):
        response = await admin_router.list_admin_codes(_admin=_admin_roles())

    assert len(response.codes) == 2
    by_id = {c.id: c for c in response.codes}
    assert by_id[CODE_ID].redemption_count == 2
    assert by_id[CODE_ID].advisor_practice_name is None
    assert by_id[other_code_id].redemption_count == 1
    assert by_id[other_code_id].advisor_practice_name == "Acme Advisory"


@pytest.mark.asyncio
async def test_list_codes_empty_table_short_circuits():
    fake = FakeSupabase(responses=[{"data": []}])

    with _patch_supabase(fake):
        response = await admin_router.list_admin_codes(_admin=_admin_roles())

    assert response.codes == []
    # Only the codes query ran — no redemptions / advisors round trips.
    assert fake.responses == []


# --------------------------------------------------------------------------- #
# POST /admin/codes
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_create_code_generates_when_no_vanity_supplied():
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row(code="ORPH-WXYZ-2345", label="Closed beta")]},
        ]
    )

    with _patch_supabase(fake):
        response = await admin_router.create_admin_code(
            request=admin_router.CreateAdminCodeRequest(label="Closed beta"),
            admin=_admin_roles(),
        )

    assert response.redemption_count == 0
    payload = fake.captured_inserts[0]["payload"]
    assert fake.captured_inserts[0]["table"] == "signup_codes"
    # A generated code was minted (shape pinned separately).
    assert payload["code"].startswith("ORPH-")
    assert payload["label"] == "Closed beta"
    assert payload["created_by"] == ADMIN_EMAIL
    assert payload["advisor_id"] is None


@pytest.mark.asyncio
async def test_create_code_accepts_vanity_value():
    fake = FakeSupabase(
        responses=[
            {"data": [_code_row(code="ACME2027")]},
        ]
    )

    with _patch_supabase(fake):
        await admin_router.create_admin_code(
            request=admin_router.CreateAdminCodeRequest(
                label="Acme cohort",
                code="  ACME2027  ",   # validator strips
            ),
            admin=_admin_roles(),
        )

    assert fake.captured_inserts[0]["payload"]["code"] == "ACME2027"


@pytest.mark.asyncio
async def test_create_code_probes_routing_advisor():
    """advisor_id supplied → existence probe; 400 when it misses."""
    fake = FakeSupabase(responses=[{"data": []}])  # advisor probe misses

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await admin_router.create_admin_code(
                request=admin_router.CreateAdminCodeRequest(
                    label="Acme cohort",
                    advisor_id=GROUP_ADVISOR_ID,
                ),
                admin=_admin_roles(),
            )

    assert exc.value.status_code == 400
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_create_code_duplicate_returns_409():
    class FakeUniqueViolation(Exception):
        code = "23505"

    fake = FakeSupabase(
        responses=[
            {"raise": FakeUniqueViolation(
                'duplicate key value violates unique constraint '
                '"signup_codes_code_unique"'
            )},
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await admin_router.create_admin_code(
                request=admin_router.CreateAdminCodeRequest(
                    label="Duplicate",
                    code="ACME2027",
                ),
                admin=_admin_roles(),
            )

    assert exc.value.status_code == 409


def test_create_code_request_rejects_whitespace_vanity():
    with pytest.raises(ValueError):
        admin_router.CreateAdminCodeRequest(label="x", code="has space")


def test_create_code_request_rejects_bad_expires_at():
    with pytest.raises(ValueError):
        admin_router.CreateAdminCodeRequest(label="x", expires_at="not-a-date")


# --------------------------------------------------------------------------- #
# PATCH /admin/codes/{id}
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_disable_code_sets_disabled_at():
    fake = FakeSupabase(
        responses=[
            {"data": [{"id": CODE_ID}]},                            # lookup
            {"data": [_code_row(disabled_at="2026-08-12T16:00:00+00:00")]},
            {"data": [], "count": 3},                               # redemptions
        ]
    )

    with _patch_supabase(fake):
        response = await admin_router.update_admin_code(
            code_id=CODE_ID,
            request=admin_router.UpdateAdminCodeRequest(disabled=True),
            admin=_admin_roles(),
        )

    assert response.disabled_at is not None
    assert response.redemption_count == 3
    update_payload = fake.captured_updates[0]["payload"]
    assert update_payload["disabled_at"] is not None


@pytest.mark.asyncio
async def test_enable_code_clears_disabled_at():
    fake = FakeSupabase(
        responses=[
            {"data": [{"id": CODE_ID}]},
            {"data": [_code_row(disabled_at=None)]},
            {"data": [], "count": 0},
        ]
    )

    with _patch_supabase(fake):
        response = await admin_router.update_admin_code(
            code_id=CODE_ID,
            request=admin_router.UpdateAdminCodeRequest(disabled=False),
            admin=_admin_roles(),
        )

    assert response.disabled_at is None
    assert fake.captured_updates[0]["payload"] == {"disabled_at": None}


@pytest.mark.asyncio
async def test_patch_unknown_code_returns_404():
    fake = FakeSupabase(responses=[{"data": []}])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await admin_router.update_admin_code(
                code_id="no-such-id",
                request=admin_router.UpdateAdminCodeRequest(disabled=True),
                admin=_admin_roles(),
            )

    assert exc.value.status_code == 404
    assert fake.captured_updates == []


# --------------------------------------------------------------------------- #
# GET /admin/codes/{id}/redemptions — per-code roster (ORPHEUS-129)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_roster_returns_members_with_latest_job():
    """Redemptions resolve to client name/email + latest job, preserving
    the newest-first redemption order."""
    fake = FakeSupabase(
        responses=[
            {"data": [{"id": CODE_ID}]},                       # code probe
            {"data": [
                {"client_id": "client-b", "redeemed_at": "2026-08-12T10:00:00+00:00"},
                {"client_id": "client-a", "redeemed_at": "2026-08-11T09:00:00+00:00"},
            ]},                                                # redemptions
            {"data": [
                {"id": "client-a", "display_name": "Ann A", "email": "ann@example.com"},
                {"id": "client-b", "display_name": "Bob B", "email": "bob@example.com"},
            ]},                                                # clients
            {"data": [
                {"id": "job-b1", "client_id": "client-b", "status": "complete",
                 "created_at": "2026-08-12T11:00:00+00:00", "data_limited": False},
                {"id": "job-b0", "client_id": "client-b", "status": "failed",
                 "created_at": "2026-08-12T10:30:00+00:00", "data_limited": False},
            ]},                                                # jobs desc
        ]
    )

    with _patch_supabase(fake):
        response = await admin_router.list_admin_code_redemptions(
            code_id=CODE_ID,
            _admin=_admin_roles(),
        )

    assert [r.display_name for r in response.redemptions] == ["Bob B", "Ann A"]
    bob, ann = response.redemptions
    # Latest job per client: first hit in the desc-ordered jobs query.
    assert bob.latest_job is not None
    assert bob.latest_job.id == "job-b1"
    assert bob.latest_job.status == "complete"
    # No jobs yet → roster still shows the member, coverage gap visible.
    assert ann.latest_job is None
    assert ann.email == "ann@example.com"


@pytest.mark.asyncio
async def test_roster_unknown_code_returns_404():
    fake = FakeSupabase(responses=[{"data": []}])  # code probe misses

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await admin_router.list_admin_code_redemptions(
                code_id="no-such-code",
                _admin=_admin_roles(),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_roster_empty_code_short_circuits():
    """Zero redemptions → empty roster, no clients/jobs round trips."""
    fake = FakeSupabase(
        responses=[
            {"data": [{"id": CODE_ID}]},   # code probe
            {"data": []},                  # redemptions empty
        ]
    )

    with _patch_supabase(fake):
        response = await admin_router.list_admin_code_redemptions(
            code_id=CODE_ID,
            _admin=_admin_roles(),
        )

    assert response.redemptions == []
    assert fake.responses == []  # nothing else was fetched


@pytest.mark.asyncio
async def test_roster_skips_redemption_with_missing_client():
    """A redemption whose clients row vanished (deletion race) is
    skipped, not a 500 — CASCADE removes the redemption on the next
    fetch anyway."""
    fake = FakeSupabase(
        responses=[
            {"data": [{"id": CODE_ID}]},
            {"data": [
                {"client_id": "client-gone", "redeemed_at": "2026-08-12T10:00:00+00:00"},
                {"client_id": "client-a", "redeemed_at": "2026-08-11T09:00:00+00:00"},
            ]},
            {"data": [
                {"id": "client-a", "display_name": "Ann A", "email": "ann@example.com"},
            ]},                            # client-gone missing
            {"data": []},                  # no jobs
        ]
    )

    with _patch_supabase(fake):
        response = await admin_router.list_admin_code_redemptions(
            code_id=CODE_ID,
            _admin=_admin_roles(),
        )

    assert [r.client_id for r in response.redemptions] == ["client-a"]
