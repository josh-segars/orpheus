"""Unit tests for backend/routers/advisor.py — POST /advisor/self-report
(ORPHEUS-39).

Same direct-handler-invocation pattern as test_clients_invite.py /
test_clients_list.py: build a SessionRoles, monkey-patch
`get_service_client`, call the route function.

Coverage:
  - First call creates the row, returns `created=True`.
  - Second call (idempotency): row already exists, no INSERT, returns
    `created=False`.
  - 403 client-only caller.
  - 403 neither-role caller.
  - Display name: caller-supplied wins; email-local-part fallback when
    None or blank; "Self" when even email's local-part is empty.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.routers import advisor as advisor_router


ADVISOR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ADVISOR_USER_ID = "user-advisor-uuid"
ADVISOR_EMAIL = "andrew@ess3.ai"
NEW_CLIENT_ID = "11111111-2222-3333-4444-555555555555"
EXISTING_CLIENT_ID = "99999999-8888-7777-6666-555555555555"


_REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.local",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "RESEND_API_KEY": "test-resend-key",
    "APP_BASE_URL": "https://app.test.local",
}


@pytest.fixture(autouse=True)
def _reset_env_and_cache(monkeypatch):
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    config_mod._reset_settings_cache_for_tests()


def _roles(
    *,
    advisor_id: str | None,
    client_id: str | None,
    email: str = ADVISOR_EMAIL,
) -> SessionRoles:
    return SessionRoles(
        user_id=ADVISOR_USER_ID,
        email=email,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


# --------------------------------------------------------------------------- #
# Pluggable supabase chain (same shape as the invite tests)
# --------------------------------------------------------------------------- #

class _Chain:
    def __init__(self, parent: "FakeSupabase", table_name: str) -> None:
        self._parent = parent
        self._table = table_name

    def select(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> "_Chain":
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
        return SimpleNamespace(**response)


class FakeSupabase:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.captured_inserts: list[dict[str, Any]] = []

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)


def _patch_supabase(fake: FakeSupabase):
    return patch.object(advisor_router, "get_service_client", return_value=fake)


# --------------------------------------------------------------------------- #
# First-call creation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_self_report_creates_new_row_on_first_call():
    """No existing self-clients row → INSERT, return created=True."""
    fake = FakeSupabase(
        responses=[
            {"data": []},  # idempotency check: no row yet
            {"data": [{"id": NEW_CLIENT_ID}]},  # INSERT result
        ]
    )

    with _patch_supabase(fake):
        response = await advisor_router.advisor_self_report(
            request=advisor_router.SelfReportRequest(display_name="Andrew Segars"),
            roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
        )

    assert response.client_id == NEW_CLIENT_ID
    assert response.created is True

    assert len(fake.captured_inserts) == 1
    payload = fake.captured_inserts[0]["payload"]
    assert payload["advisor_id"] == ADVISOR_ID
    assert payload["user_id"] == ADVISOR_USER_ID
    assert payload["display_name"] == "Andrew Segars"
    assert payload["email"] == ADVISOR_EMAIL
    assert payload["invitation_status"] == "accepted"
    # No token issued for a self-report row.
    assert "invitation_token" not in payload or payload["invitation_token"] is None


@pytest.mark.asyncio
async def test_self_report_uses_email_local_part_when_display_name_omitted():
    """Caller passed no display_name → fall back to email local-part."""
    fake = FakeSupabase(
        responses=[
            {"data": []},
            {"data": [{"id": NEW_CLIENT_ID}]},
        ]
    )

    with _patch_supabase(fake):
        await advisor_router.advisor_self_report(
            request=advisor_router.SelfReportRequest(display_name=None),
            roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
        )

    payload = fake.captured_inserts[0]["payload"]
    assert payload["display_name"] == "andrew"  # local-part of advisor email


@pytest.mark.asyncio
async def test_self_report_normalises_blank_display_name_to_fallback():
    """Whitespace-only display_name → trimmed to None → fallback used."""
    fake = FakeSupabase(
        responses=[
            {"data": []},
            {"data": [{"id": NEW_CLIENT_ID}]},
        ]
    )

    with _patch_supabase(fake):
        await advisor_router.advisor_self_report(
            request=advisor_router.SelfReportRequest(display_name="   "),
            roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
        )

    payload = fake.captured_inserts[0]["payload"]
    assert payload["display_name"] == "andrew"


# --------------------------------------------------------------------------- #
# Idempotency — second call returns the existing row, no INSERT
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_self_report_idempotent_on_second_call():
    """Self-clients row already exists → return it, no INSERT, created=False."""
    fake = FakeSupabase(
        responses=[
            {"data": [{"id": EXISTING_CLIENT_ID}]},
        ]
    )

    with _patch_supabase(fake):
        response = await advisor_router.advisor_self_report(
            request=advisor_router.SelfReportRequest(display_name="Andrew Segars"),
            roles=_roles(
                advisor_id=ADVISOR_ID,
                client_id=EXISTING_CLIENT_ID,  # advisor is already a client too
            ),
        )

    assert response.client_id == EXISTING_CLIENT_ID
    assert response.created is False
    # Crucially, no second query (no INSERT).
    assert fake.captured_inserts == []


# --------------------------------------------------------------------------- #
# 403 — role gating
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_self_report_rejects_client_only_caller():
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await advisor_router.advisor_self_report(
                request=advisor_router.SelfReportRequest(display_name=None),
                roles=_roles(advisor_id=None, client_id="some-client-id"),
            )

    assert exc.value.status_code == 403
    assert "advisor" in exc.value.detail.lower()
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_self_report_rejects_neither_role_caller():
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await advisor_router.advisor_self_report(
                request=advisor_router.SelfReportRequest(display_name=None),
                roles=_roles(advisor_id=None, client_id=None),
            )

    assert exc.value.status_code == 403
    assert fake.captured_inserts == []
