"""Unit tests for backend/routers/clients.py — GET /clients (ORPHEUS-39).

Direct handler-invocation pattern, same as test_clients_invite.py: we
build a `SessionRoles`, monkey-patch `get_service_client`, then call
the route function. FastAPI's dependency injection is bypassed for
unit-level isolation.

Coverage:
  - Happy path: rows ordered by created_at desc, latest_job populated
    from the bucketed jobs query.
  - is_self flag: the row whose user_id matches the advisor's
    user_id is flagged.
  - Empty list: no clients → empty response, no second query needed.
  - 403 client-only caller.
  - 403 neither-role caller (handler-side defense in depth).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.routers import clients as clients_router


ADVISOR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ADVISOR_USER_ID = "user-advisor-uuid"
ADVISOR_EMAIL = "andrew@segarsadvisory.com"
CLIENT_A_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_B_ID = "22222222-2222-2222-2222-222222222222"
CLIENT_SELF_ID = "33333333-3333-3333-3333-333333333333"
JOB_A1_ID = "aaaa1111-0000-0000-0000-000000000000"
JOB_A2_ID = "aaaa2222-0000-0000-0000-000000000000"
JOB_B1_ID = "bbbb1111-0000-0000-0000-000000000000"


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


def _roles(*, advisor_id: str | None, client_id: str | None) -> SessionRoles:
    return SessionRoles(
        user_id=ADVISOR_USER_ID,
        email=ADVISOR_EMAIL,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


# --------------------------------------------------------------------------- #
# Pluggable supabase chain
# --------------------------------------------------------------------------- #

class _Chain:
    """Records call shape, returns the next queued response on execute().

    GET /clients uses .select(...).eq(...).order(...).execute() on
    clients, then .select(...).in_(...).order(...).execute() on jobs —
    we support both shapes without distinguishing.
    """

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

    def execute(self) -> SimpleNamespace:
        if self._parent.responses:
            response = self._parent.responses.pop(0)
        else:
            response = {"data": []}
        return SimpleNamespace(**response)


class FakeSupabase:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.tables_queried: list[str] = []

    def table(self, name: str) -> _Chain:
        self.tables_queried.append(name)
        return _Chain(self, name)


def _patch_supabase(fake: FakeSupabase):
    return patch.object(clients_router, "get_service_client", return_value=fake)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_clients_happy_path_with_jobs():
    """Advisor with two clients, two jobs on client A, one on B.

    The most recent job per client should win — the first hit in the
    desc-ordered jobs query.
    """
    fake = FakeSupabase(
        responses=[
            # clients query
            {
                "data": [
                    {
                        "id": CLIENT_A_ID,
                        "display_name": "Client A",
                        "email": "a@example.com",
                        "invitation_status": "accepted",
                        "user_id": "user-a-uuid",
                        "created_at": "2026-05-01T00:00:00+00:00",
                    },
                    {
                        "id": CLIENT_B_ID,
                        "display_name": "Client B",
                        "email": "b@example.com",
                        "invitation_status": "pending",
                        "user_id": None,
                        "created_at": "2026-04-15T00:00:00+00:00",
                    },
                ]
            },
            # jobs query — desc order, first hit per client wins
            {
                "data": [
                    {
                        "id": JOB_A2_ID,
                        "client_id": CLIENT_A_ID,
                        "status": "complete",
                        "created_at": "2026-05-10T00:00:00+00:00",
                    },
                    {
                        "id": JOB_A1_ID,
                        "client_id": CLIENT_A_ID,
                        "status": "failed",
                        "created_at": "2026-05-01T00:00:00+00:00",
                    },
                    {
                        "id": JOB_B1_ID,
                        "client_id": CLIENT_B_ID,
                        "status": "pending",
                        "created_at": "2026-05-05T00:00:00+00:00",
                    },
                ]
            },
        ]
    )

    with _patch_supabase(fake):
        response = await clients_router.list_clients(
            roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
        )

    assert len(response.clients) == 2
    a, b = response.clients

    assert a.id == CLIENT_A_ID
    assert a.display_name == "Client A"
    assert a.email == "a@example.com"
    assert a.invitation_status == "accepted"
    assert a.is_self is False  # advisor user_id != client A user_id
    assert a.latest_job is not None
    assert a.latest_job.id == JOB_A2_ID  # most recent of A's two jobs
    assert a.latest_job.status == "complete"

    assert b.id == CLIENT_B_ID
    assert b.invitation_status == "pending"
    assert b.is_self is False
    assert b.latest_job is not None
    assert b.latest_job.id == JOB_B1_ID
    assert b.latest_job.status == "pending"

    # Two queries: clients first, then jobs.
    assert fake.tables_queried == ["clients", "jobs"]


@pytest.mark.asyncio
async def test_list_clients_flags_self_clients_row():
    """The row whose user_id matches the advisor's user_id is `is_self=True`."""
    fake = FakeSupabase(
        responses=[
            {
                "data": [
                    {
                        "id": CLIENT_SELF_ID,
                        "display_name": "Andrew (self)",
                        "email": ADVISOR_EMAIL,
                        "invitation_status": "accepted",
                        "user_id": ADVISOR_USER_ID,  # matches roles.user_id
                        "created_at": "2026-05-12T00:00:00+00:00",
                    },
                    {
                        "id": CLIENT_A_ID,
                        "display_name": "Client A",
                        "email": "a@example.com",
                        "invitation_status": "accepted",
                        "user_id": "user-a-uuid",
                        "created_at": "2026-05-01T00:00:00+00:00",
                    },
                ]
            },
            {"data": []},  # no jobs yet
        ]
    )

    with _patch_supabase(fake):
        response = await clients_router.list_clients(
            roles=_roles(advisor_id=ADVISOR_ID, client_id=CLIENT_SELF_ID),
        )

    self_row, other_row = response.clients
    assert self_row.is_self is True
    assert other_row.is_self is False
    # No jobs at all — both rows carry latest_job=None.
    assert self_row.latest_job is None
    assert other_row.latest_job is None


@pytest.mark.asyncio
async def test_list_clients_empty_skips_jobs_query():
    """Empty client list short-circuits the jobs query entirely."""
    fake = FakeSupabase(responses=[{"data": []}])

    with _patch_supabase(fake):
        response = await clients_router.list_clients(
            roles=_roles(advisor_id=ADVISOR_ID, client_id=None),
        )

    assert response.clients == []
    # Only one query — no point asking the jobs table about nothing.
    assert fake.tables_queried == ["clients"]


# --------------------------------------------------------------------------- #
# 403 — role gating
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_clients_rejects_client_only_caller():
    """A client without an advisor role gets 403."""
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await clients_router.list_clients(
                roles=_roles(advisor_id=None, client_id="some-client-id"),
            )

    assert exc.value.status_code == 403
    assert "advisor" in exc.value.detail.lower()
    assert fake.tables_queried == []


@pytest.mark.asyncio
async def test_list_clients_rejects_neither_role_caller():
    """Defense-in-depth: handler 403s even if upstream dep was bypassed."""
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await clients_router.list_clients(
                roles=_roles(advisor_id=None, client_id=None),
            )

    assert exc.value.status_code == 403
    assert fake.tables_queried == []
