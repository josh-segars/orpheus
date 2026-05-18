"""Unit tests for backend/routers/clients.py — POST /clients/{id}/resend-invitation.

The advisor-facing recovery path: rotate a client's invitation token
and re-send the email. The 502 case is slightly subtle — the token
has already been rotated by the time Resend rejects the send, so the
old email link is dead regardless. Tests pin that the rotation
happened even when the network step fails.

Same direct-handler-invocation + FakeSupabase pattern as the other
test files in this chain.
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
from backend.email.resend_client import EmailSendError
from backend.routers import clients as clients_router


ADVISOR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_ADVISOR_ID = "ffffffff-0000-0000-0000-000000000000"
CLIENT_ID = "99999999-aaaa-bbbb-cccc-dddddddddddd"
CLIENT_EMAIL = "client@example.com"
ADVISOR_USER_ID = "user-advisor-uuid"
ADVISOR_EMAIL = "andrew@ess3.ai"
ORIGINAL_TOKEN = "11111111-2222-2222-2222-222222222222"


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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _advisor_roles() -> SessionRoles:
    return SessionRoles(
        user_id=ADVISOR_USER_ID,
        email=ADVISOR_EMAIL,
        access_token="test-token",
        advisor_id=ADVISOR_ID,
        client_id=None,
    )


def _client_roles() -> SessionRoles:
    """A user with a clients row but no advisors row."""
    return SessionRoles(
        user_id="user-client-uuid",
        email="client-user@example.com",
        access_token="test-token",
        advisor_id=None,
        client_id="some-client-id",
    )


def _row(*, invitation_status: str = "pending") -> dict[str, Any]:
    return {
        "id": CLIENT_ID,
        "advisor_id": ADVISOR_ID,
        "user_id": None,
        "display_name": "Test Client",
        "email": CLIENT_EMAIL,
        "invitation_token": ORIGINAL_TOKEN,
        "invitation_expires_at": (
            datetime.now(timezone.utc) + timedelta(days=14)
        ).isoformat(),
        "invitation_status": invitation_status,
        "status": "active",
        "created_at": "2026-05-13T00:00:00+00:00",
    }


class _Chain:
    """Chain mock supporting select / eq / limit / update / execute."""

    def __init__(self, parent: "FakeSupabase", table_name: str) -> None:
        self._parent = parent
        self._table = table_name

    def select(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "_Chain":
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
        return SimpleNamespace(**response)


class FakeSupabase:
    """Ordered-response fake for the resend-invitation flow.

    Handler call order on the happy path:
      1. SELECT clients by (id, advisor_id)
      2. SELECT advisors.practice_name by id
      3. UPDATE clients by id

    Tests configure the responses queue accordingly; UPDATE payloads
    are captured for shape assertions.
    """

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.captured_updates: list[dict[str, Any]] = []

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)


def _patch_supabase(fake: FakeSupabase):
    return patch.object(clients_router, "get_service_client", return_value=fake)


def _patch_send_email(*, side_effect: Any = None, return_value: str = "msg_test"):
    if side_effect is not None:
        return patch.object(
            clients_router,
            "send_invitation_email",
            side_effect=side_effect,
        )
    return patch.object(
        clients_router,
        "send_invitation_email",
        return_value=return_value,
    )


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_resend_happy_path_rotates_token_and_sends_email():
    """Advisor calls resend on a pending row. Token rotates, email sends, 200 returned."""
    fake = FakeSupabase(
        responses=[
            {"data": [_row()]},                           # SELECT clients
            {"data": [{"practice_name": "Segars Advisory"}]},  # advisor lookup
            {"data": [{"id": CLIENT_ID}]},                 # UPDATE result
        ]
    )

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        response = await clients_router.resend_invitation(
            client_id=CLIENT_ID,
            roles=_advisor_roles(),
        )

    assert response.client_id == CLIENT_ID

    # UPDATE rotated the token + expiry, reset status to pending.
    assert len(fake.captured_updates) == 1
    update_payload = fake.captured_updates[0]["payload"]
    assert update_payload["invitation_status"] == "pending"
    assert update_payload["invitation_token"]  # uuid4 string, non-empty
    assert update_payload["invitation_token"] != ORIGINAL_TOKEN  # actually rotated
    assert update_payload["invitation_expires_at"]

    # Email sent with the NEW token in the invite URL.
    fake_send.assert_called_once()
    call_kwargs = fake_send.call_args.kwargs
    assert call_kwargs["to_email"] == CLIENT_EMAIL
    assert call_kwargs["advisor_name"] == "Segars Advisory"
    assert update_payload["invitation_token"] in call_kwargs["invite_url"]
    # Old token explicitly NOT in the new URL.
    assert ORIGINAL_TOKEN not in call_kwargs["invite_url"]


# --------------------------------------------------------------------------- #
# 403 — role gating
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_resend_rejects_client_only_caller():
    """A user with a clients row but no advisors row gets 403."""
    fake = FakeSupabase(responses=[])  # should never be hit

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        with pytest.raises(HTTPException) as exc:
            await clients_router.resend_invitation(
                client_id=CLIENT_ID,
                roles=_client_roles(),
            )

    assert exc.value.status_code == 403
    fake_send.assert_not_called()
    assert fake.captured_updates == []


# --------------------------------------------------------------------------- #
# 404 — client not found / belongs to another advisor
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_resend_404_when_client_belongs_to_other_advisor():
    """SELECT filtered on (id, advisor_id) returns empty → 404.

    The handler doesn't distinguish "wrong advisor" from "no such id"
    in the response — same 404 for both, preventing existence leak
    across advisors.
    """
    # The mock returns empty because the SELECT filter doesn't match —
    # we don't need to simulate the filter logic, just the result.
    fake = FakeSupabase(responses=[{"data": []}])

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        with pytest.raises(HTTPException) as exc:
            await clients_router.resend_invitation(
                client_id=CLIENT_ID,
                roles=_advisor_roles(),
            )

    assert exc.value.status_code == 404
    fake_send.assert_not_called()
    assert fake.captured_updates == []


@pytest.mark.asyncio
async def test_resend_404_when_client_id_unknown():
    """A nonexistent client_id also returns 404."""
    fake = FakeSupabase(responses=[{"data": []}])

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        with pytest.raises(HTTPException) as exc:
            await clients_router.resend_invitation(
                client_id="00000000-0000-0000-0000-000000000000",
                roles=_advisor_roles(),
            )

    assert exc.value.status_code == 404
    fake_send.assert_not_called()


# --------------------------------------------------------------------------- #
# 409 — already accepted
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_resend_409_when_invitation_already_accepted():
    """SELECT returns a row with invitation_status='accepted' → 409.

    Resending would orphan the accepted state. Different flow needed
    for revoke + reinvite (not in beta scope).
    """
    fake = FakeSupabase(
        responses=[
            {"data": [_row(invitation_status="accepted")]},
        ]
    )

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        with pytest.raises(HTTPException) as exc:
            await clients_router.resend_invitation(
                client_id=CLIENT_ID,
                roles=_advisor_roles(),
            )

    assert exc.value.status_code == 409
    assert "accepted" in exc.value.detail.lower()
    fake_send.assert_not_called()
    assert fake.captured_updates == []


# --------------------------------------------------------------------------- #
# 502 — Resend rejects but token was already rotated
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_resend_502_rotates_token_before_send_fails():
    """Resend rejects the send. The token was already rotated, so the
    OLD email link is now dead regardless. The 502 detail tells the
    advisor the refresh worked but the send didn't.

    This is a subtle invariant: the token rotation must commit
    BEFORE the network call. If we sent first and rotated after, a
    transient Resend failure would leave the old token live and the
    new one absent — confusing state on retry.
    """
    fake = FakeSupabase(
        responses=[
            {"data": [_row()]},
            {"data": [{"practice_name": "Segars Advisory"}]},
            {"data": [{"id": CLIENT_ID}]},
        ]
    )

    with _patch_supabase(fake), _patch_send_email(
        side_effect=EmailSendError("Resend rejected: 500 Internal Error"),
    ):
        with pytest.raises(HTTPException) as exc:
            await clients_router.resend_invitation(
                client_id=CLIENT_ID,
                roles=_advisor_roles(),
            )

    assert exc.value.status_code == 502
    # The detail must communicate the token-was-rotated fact so the
    # advisor knows retrying is safe.
    assert "refreshed" in exc.value.detail.lower() or "rotated" in exc.value.detail.lower()

    # And the UPDATE genuinely happened — the new token is in place.
    assert len(fake.captured_updates) == 1
    new_token = fake.captured_updates[0]["payload"]["invitation_token"]
    assert new_token
    assert new_token != ORIGINAL_TOKEN
