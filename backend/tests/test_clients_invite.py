"""Unit tests for backend/routers/clients.py — POST /clients/invite.

Direct handler-invocation pattern, same as test_auth.py: we construct
a `SessionRoles` instance, monkey-patch `get_service_client` and
`send_invitation_email`, then call the route function. FastAPI's
dependency injection is bypassed for unit-level isolation; full-stack
integration is covered by the manual e2e at commit #11.

Coverage (commit #4 of ORPHEUS-38):
  - Happy path: advisor invites, INSERT shape verified, email sent,
    response carries the new client_id.
  - 403 client-only: caller has clients role but no advisors row.
  - 403 no-roles: caller's handler-side guard fires even if the
    upstream dependency was bypassed (defense in depth).
  - 409 duplicate: an existing (advisor_id, email) row exists.
  - 502 Resend failure: row persists, response tells the advisor to
    resend.
"""

from __future__ import annotations

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
CLIENT_ID = "99999999-8888-7777-6666-555555555555"
NEW_CLIENT_ID = "11111111-2222-3333-4444-555555555555"
ADVISOR_USER_ID = "user-advisor-uuid"
ADVISOR_EMAIL = "andrew@ess3.ai"
INVITE_EMAIL = "client@example.com"


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
    """Settings boot-validates on every call; reset the cache per test."""
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    config_mod._reset_settings_cache_for_tests()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _roles(*, advisor_id: str | None, client_id: str | None) -> SessionRoles:
    """Build a SessionRoles matching the desired role permutation."""
    return SessionRoles(
        user_id=ADVISOR_USER_ID,
        email=ADVISOR_EMAIL,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


class _Chain:
    """Pluggable supabase query chain.

    Operations recorded: `select`, `eq`, `limit`, `insert`. On
    `execute()`, the FakeSupabase pops the next pre-configured
    response off its queue and returns it as `SimpleNamespace(data=...)`.

    INSERT payloads are captured on the parent so tests can assert on
    what we wrote.
    """

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
    """Ordered-response stand-in for a supabase-py service client.

    Pass `responses=[{data: [...]}, ...]` in the order the handler
    issues queries. The handler's call order is:

      1. advisors lookup (practice_name)
      2. clients duplicate pre-check
      3. clients INSERT

    Tests that short-circuit earlier (e.g. the 403 cases) won't pop
    any responses; tests that 409 only pop the first two.

    Inserts are captured on `captured_inserts` so tests can verify
    the row shape without depending on the execute response.
    """

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.captured_inserts: list[dict[str, Any]] = []

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
async def test_invite_happy_path():
    """Advisor invites a new email. Returns 201 + the new client_id."""
    fake = FakeSupabase(
        responses=[
            {"data": [{"practice_name": "Segars Advisory"}]},  # advisor lookup
            {"data": []},                                       # dup check: clean
            {"data": [{"id": NEW_CLIENT_ID}]},                  # INSERT result
        ]
    )

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        response = await clients_router.invite_client(
            request=clients_router.InviteClientRequest(
                display_name="Test Client",
                email="  Client@Example.com  ",  # whitespace + mixed case
            ),
            roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
        )

    assert response.client_id == NEW_CLIENT_ID

    # Exactly one INSERT was issued, on the clients table, with the
    # normalized email + a pending status + a generated token.
    assert len(fake.captured_inserts) == 1
    insert = fake.captured_inserts[0]
    assert insert["table"] == "clients"
    payload = insert["payload"]
    assert payload["advisor_id"] == ADVISOR_ID
    assert payload["display_name"] == "Test Client"
    assert payload["email"] == INVITE_EMAIL  # lowercased, trimmed
    assert payload["invitation_status"] == "pending"
    assert payload["user_id"] is None
    assert payload["invitation_token"]  # uuid4 string, non-empty
    assert payload["invitation_expires_at"]  # iso timestamp

    # Email called once with the normalized address and the practice
    # name from the advisors lookup (not the JWT email fallback).
    fake_send.assert_called_once()
    call_kwargs = fake_send.call_args.kwargs
    assert call_kwargs["to_email"] == INVITE_EMAIL
    assert call_kwargs["advisor_name"] == "Segars Advisory"
    assert call_kwargs["invite_url"].startswith("https://app.test.local/invite/")
    assert payload["invitation_token"] in call_kwargs["invite_url"]


@pytest.mark.asyncio
async def test_invite_falls_back_to_advisor_email_when_no_practice_name():
    """When `practice_name` is null/empty, use the advisor's JWT email."""
    fake = FakeSupabase(
        responses=[
            {"data": [{"practice_name": None}]},  # no practice_name set
            {"data": []},
            {"data": [{"id": NEW_CLIENT_ID}]},
        ]
    )

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        await clients_router.invite_client(
            request=clients_router.InviteClientRequest(
                display_name="Test Client",
                email=INVITE_EMAIL,
            ),
            roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
        )

    fake_send.assert_called_once()
    assert fake_send.call_args.kwargs["advisor_name"] == ADVISOR_EMAIL


# --------------------------------------------------------------------------- #
# 403 — role gating
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_invite_rejects_client_only_caller():
    """A user with a clients row but no advisors row gets 403."""
    fake = FakeSupabase(responses=[])  # should never be hit

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        with pytest.raises(HTTPException) as exc:
            await clients_router.invite_client(
                request=clients_router.InviteClientRequest(
                    display_name="Test Client",
                    email=INVITE_EMAIL,
                ),
                roles=_roles(advisor_id=None, client_id=CLIENT_ID),
            )

    assert exc.value.status_code == 403
    assert "advisor" in exc.value.detail.lower()
    fake_send.assert_not_called()
    assert fake.captured_inserts == []


@pytest.mark.asyncio
async def test_invite_rejects_neither_role_caller():
    """Handler-side defense in depth: 403 even if neither role is set.

    In production, get_current_session_roles raises 401 before this
    handler runs. The handler's own `is_advisor()` guard is a safety
    net in case the dependency is bypassed (tests, future refactor,
    or an upstream auth change).
    """
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        with pytest.raises(HTTPException) as exc:
            await clients_router.invite_client(
                request=clients_router.InviteClientRequest(
                    display_name="Test Client",
                    email=INVITE_EMAIL,
                ),
                roles=_roles(advisor_id=None, client_id=None),
            )

    assert exc.value.status_code == 403
    fake_send.assert_not_called()


# --------------------------------------------------------------------------- #
# 409 — duplicate (advisor_id, email)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_invite_409_when_email_already_invited_by_same_advisor():
    """The pre-check finds an existing row, so we 409 without INSERTing.

    Catches advisors retrying the form after a successful send (e.g.
    confused by the success state in the UI) without producing a
    second ghost row in the table.
    """
    fake = FakeSupabase(
        responses=[
            {"data": [{"practice_name": "Segars Advisory"}]},  # advisor lookup
            {"data": [{"id": "existing-client-id"}]},          # dup hit
        ]
    )

    with _patch_supabase(fake), _patch_send_email() as fake_send:
        with pytest.raises(HTTPException) as exc:
            await clients_router.invite_client(
                request=clients_router.InviteClientRequest(
                    display_name="Test Client",
                    email=INVITE_EMAIL,
                ),
                roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
            )

    assert exc.value.status_code == 409
    assert fake.captured_inserts == []
    fake_send.assert_not_called()


# --------------------------------------------------------------------------- #
# 502 — Resend failure
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_invite_502_when_resend_fails_but_keeps_clients_row():
    """If Resend rejects the send, the row persists and we surface 502.

    The detail must mention that the row was kept, so the UI can
    direct the advisor to the resend endpoint instead of asking them
    to re-enter the form.
    """
    fake = FakeSupabase(
        responses=[
            {"data": [{"practice_name": "Segars Advisory"}]},
            {"data": []},
            {"data": [{"id": NEW_CLIENT_ID}]},
        ]
    )

    with _patch_supabase(fake), _patch_send_email(
        side_effect=EmailSendError("Resend rejected: 422 Invalid `to`"),
    ):
        with pytest.raises(HTTPException) as exc:
            await clients_router.invite_client(
                request=clients_router.InviteClientRequest(
                    display_name="Test Client",
                    email=INVITE_EMAIL,
                ),
                roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
            )

    assert exc.value.status_code == 502
    assert "resend" in exc.value.detail.lower()
    # The INSERT happened — the row exists.
    assert len(fake.captured_inserts) == 1
    assert fake.captured_inserts[0]["payload"]["email"] == INVITE_EMAIL
