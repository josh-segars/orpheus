"""Unit tests for backend/routers/clients.py — POST /accept-invitation.

This endpoint has the trickiest state machine in ORPHEUS-38: it must
distinguish four token states (unknown, expired, accepted, pending),
two role permutations on accepted tokens (same user vs different),
and the email-mismatch soft-confirmation flow. Each is pinned by a
dedicated test below.

Same direct-handler-invocation pattern as test_clients_invite.py.
The FakeSupabase is extended to support UPDATE chains too.
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
from backend.routers import clients as clients_router


TOKEN = "11112222-3333-4444-5555-666677778888"
CLIENT_ID = "99999999-aaaa-bbbb-cccc-dddddddddddd"
INVITATION_EMAIL = "invited@example.com"
LINKEDIN_EMAIL = "invited@example.com"  # default match case
MISMATCH_LINKEDIN_EMAIL = "personal@example.com"
USER_ID = "user-a-uuid"
OTHER_USER_ID = "user-b-uuid"


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

def _roles(
    *,
    user_id: str = USER_ID,
    email: str = LINKEDIN_EMAIL,
    advisor_id: str | None = None,
    client_id: str | None = None,
) -> SessionRoles:
    """Build a SessionRoles for the accept-invitation caller.

    Defaults match the "freshly-signed-in invitee, no business row yet"
    case — both role fields None. Tests can override for the replay
    scenarios where the caller may already hold a clients row.
    """
    return SessionRoles(
        user_id=user_id,
        email=email,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


def _row(
    *,
    invitation_status: str = "pending",
    user_id: str | None = None,
    email: str = INVITATION_EMAIL,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a clients row matching what supabase-py returns from SELECT *."""
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=14)
    return {
        "id": CLIENT_ID,
        "advisor_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "user_id": user_id,
        "display_name": "Test Client",
        "email": email,
        "invitation_token": TOKEN,
        "invitation_expires_at": expires_at.isoformat(),
        "invitation_status": invitation_status,
        "status": "active",
        "created_at": "2026-05-13T00:00:00+00:00",
    }


class _Chain:
    """Supabase chain stand-in supporting select / eq / limit / update / execute."""

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
    """Configurable fake for the accept-invitation flow.

    Handler calls in order:
      1. SELECT clients by token  (always)
      2. UPDATE clients by id     (only on actual accept)

    Tests provide the responses in order. UPDATE payloads are
    captured for assertion.
    """

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.captured_updates: list[dict[str, Any]] = []

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)


def _patch_supabase(fake: FakeSupabase):
    return patch.object(clients_router, "get_service_client", return_value=fake)


# --------------------------------------------------------------------------- #
# Happy path — emails match
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_accept_happy_path_no_mismatch():
    """Pending row, emails match → UPDATE proceeds, 200 returned."""
    fake = FakeSupabase(
        responses=[
            {"data": [_row()]},                       # SELECT by token
            {"data": [{"id": CLIENT_ID}]},            # UPDATE returns the row
        ]
    )

    with _patch_supabase(fake):
        response = await clients_router.accept_invitation(
            request=clients_router.AcceptInvitationRequest(token=TOKEN),
            roles=_roles(),
        )

    assert response.client_id == CLIENT_ID
    assert response.requires_confirmation is False
    assert response.invitation_email is None
    assert response.linkedin_email is None

    # UPDATE was issued with the canonical accept payload.
    assert len(fake.captured_updates) == 1
    update_payload = fake.captured_updates[0]["payload"]
    assert update_payload["user_id"] == USER_ID
    assert update_payload["invitation_status"] == "accepted"


# --------------------------------------------------------------------------- #
# Email mismatch — soft confirmation
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_accept_mismatch_returns_requires_confirmation():
    """Invitation email differs from LinkedIn email, confirmed=False
    → 200 with requires_confirmation, NO update."""
    fake = FakeSupabase(
        responses=[
            {"data": [_row(email=INVITATION_EMAIL)]},
        ]
    )

    with _patch_supabase(fake):
        response = await clients_router.accept_invitation(
            request=clients_router.AcceptInvitationRequest(
                token=TOKEN,
                confirmed=False,
            ),
            roles=_roles(email=MISMATCH_LINKEDIN_EMAIL),
        )

    assert response.client_id == CLIENT_ID
    assert response.requires_confirmation is True
    assert response.invitation_email == INVITATION_EMAIL
    assert response.linkedin_email == MISMATCH_LINKEDIN_EMAIL

    # Critically: NO update happened. Row stays pending until the
    # user confirms via a second request with confirmed=True.
    assert fake.captured_updates == []


@pytest.mark.asyncio
async def test_accept_mismatch_with_confirmed_accepts():
    """Same mismatch as above, but confirmed=True → UPDATE proceeds."""
    fake = FakeSupabase(
        responses=[
            {"data": [_row(email=INVITATION_EMAIL)]},
            {"data": [{"id": CLIENT_ID}]},
        ]
    )

    with _patch_supabase(fake):
        response = await clients_router.accept_invitation(
            request=clients_router.AcceptInvitationRequest(
                token=TOKEN,
                confirmed=True,
            ),
            roles=_roles(email=MISMATCH_LINKEDIN_EMAIL),
        )

    assert response.client_id == CLIENT_ID
    assert response.requires_confirmation is False
    assert len(fake.captured_updates) == 1
    assert fake.captured_updates[0]["payload"]["user_id"] == USER_ID


# --------------------------------------------------------------------------- #
# Expiry
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_accept_expired_token_returns_401():
    """Pending row with invitation_expires_at in the past → 401 with 'expired'."""
    past = datetime.now(timezone.utc) - timedelta(days=1)
    fake = FakeSupabase(
        responses=[
            {"data": [_row(expires_at=past)]},
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await clients_router.accept_invitation(
                request=clients_router.AcceptInvitationRequest(token=TOKEN),
                roles=_roles(),
            )

    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()
    assert fake.captured_updates == []


# --------------------------------------------------------------------------- #
# Unknown token
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_accept_unknown_token_returns_401():
    """Token not found in DB → 401 'not found or no longer valid'."""
    fake = FakeSupabase(responses=[{"data": []}])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await clients_router.accept_invitation(
                request=clients_router.AcceptInvitationRequest(token=TOKEN),
                roles=_roles(),
            )

    assert exc.value.status_code == 401
    # We don't differentiate "never existed" from "rotated away" in the
    # detail — frontend renders the same not-found state either way.
    assert "not found" in exc.value.detail.lower() or "valid" in exc.value.detail.lower()
    assert fake.captured_updates == []


# --------------------------------------------------------------------------- #
# Replay scenarios — already-accepted rows
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_accept_replay_by_same_user_is_idempotent():
    """Already-accepted row, same user_id → 200 with existing client_id, NO update.

    This is the "user clicks the email link again from a second device
    or a few weeks later" case. Without idempotency, returning users
    would see a confusing 401 instead of just landing in the portal.
    """
    fake = FakeSupabase(
        responses=[
            {"data": [_row(invitation_status="accepted", user_id=USER_ID)]},
        ]
    )

    with _patch_supabase(fake):
        response = await clients_router.accept_invitation(
            request=clients_router.AcceptInvitationRequest(token=TOKEN),
            roles=_roles(user_id=USER_ID),
        )

    assert response.client_id == CLIENT_ID
    assert response.requires_confirmation is False
    # Critically: the row was NOT re-UPDATEd. Idempotent replay is a
    # read-only operation.
    assert fake.captured_updates == []


@pytest.mark.asyncio
async def test_accept_replay_by_different_user_returns_401():
    """Already-accepted row, different user_id → 401.

    A token that's been burned by one user can't be re-claimed by
    another. Protects against the case where the original invitee
    forwards the email and someone else tries to use the link.
    """
    fake = FakeSupabase(
        responses=[
            {"data": [_row(invitation_status="accepted", user_id=USER_ID)]},
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await clients_router.accept_invitation(
                request=clients_router.AcceptInvitationRequest(token=TOKEN),
                roles=_roles(user_id=OTHER_USER_ID),
            )

    assert exc.value.status_code == 401
    assert "already" in exc.value.detail.lower()
    assert fake.captured_updates == []
