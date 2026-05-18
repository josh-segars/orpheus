"""Unit tests for backend/routers/jobs.py — GET /jobs/{job_id} role gate.

Direct handler-invocation pattern, same as test_clients_list.py: we
build a `SessionRoles`, monkey-patch `get_service_client`, then call
the route function. FastAPI's dependency injection is bypassed for
unit-level isolation.

ORPHEUS-46 relaxed the role gate from is_client()-only to
"is_client() OR is_advisor() AND advisor-owns-client". Coverage:

  - (a) Advisor viewing their own client's job → 200.
  - (b) Advisor viewing another advisor's client's job → 404 (no leak).
  - (c) Advisor with no managed clients → 404 (short-circuit before
        the jobs query).
  - (d) Client viewing own job → 200 (regression on the original path).
  - (e) Client viewing another client's job → 404 (regression).

We deliberately use non-"complete" job statuses for all five cases so
`_build_result_payload` doesn't fire — the ticket is about the role
gate, not the payload assembly which has been stable for months.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.routers import jobs as jobs_router


# --------------------------------------------------------------------------- #
# Fixtures / constants
# --------------------------------------------------------------------------- #

ADVISOR_1_ID = "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa"
ADVISOR_2_ID = "aaaaaaaa-2222-2222-2222-aaaaaaaaaaaa"
ADVISOR_USER_ID = "user-advisor-uuid"
ADVISOR_EMAIL = "andrew@ess3.ai"

CLIENT_1_ID = "11111111-1111-1111-1111-111111111111"  # owned by ADVISOR_1
CLIENT_2_ID = "22222222-2222-2222-2222-222222222222"  # owned by ADVISOR_2

JOB_1_ID = "job-1111-1111-1111-111111111111"  # belongs to CLIENT_1
JOB_2_ID = "job-2222-2222-2222-222222222222"  # belongs to CLIENT_2


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


def _advisor_roles(advisor_id: str) -> SessionRoles:
    return SessionRoles(
        user_id=ADVISOR_USER_ID,
        email=ADVISOR_EMAIL,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=None,
    )


def _client_roles(client_id: str) -> SessionRoles:
    return SessionRoles(
        user_id="user-client-uuid",
        email="client@example.com",
        access_token="test-token",
        advisor_id=None,
        client_id=client_id,
    )


# --------------------------------------------------------------------------- #
# Pluggable supabase chain — same shape as test_clients_list.py
# --------------------------------------------------------------------------- #

class _Chain:
    """Returns the next queued response on execute(); records table accesses
    on the parent FakeSupabase.

    GET /jobs/{id} uses two chains: clients (.select.eq.execute) and jobs
    (.select.eq.in_.limit.execute). Both shapes accepted by the same chain.
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
    return patch.object(jobs_router, "get_service_client", return_value=fake)


def _job_row(*, job_id: str, client_id: str, status_value: str = "running") -> dict[str, Any]:
    return {
        "id": job_id,
        "client_id": client_id,
        "status": status_value,
        "created_at": "2026-05-15T00:00:00+00:00",
        "updated_at": "2026-05-15T00:00:01+00:00",
        "error_message": None,
    }


# --------------------------------------------------------------------------- #
# Advisor path — ORPHEUS-46 happy and unhappy
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_advisor_can_view_own_client_job():
    """ORPHEUS-46 (a): advisor opens a job for a client they manage → 200.

    Two queries fire: clients (to expand the advisor's roster) and
    jobs (filtered on the resulting client_id set).
    """
    fake = FakeSupabase(
        responses=[
            # clients query — advisor manages CLIENT_1
            {"data": [{"id": CLIENT_1_ID}]},
            # jobs query — JOB_1 belongs to CLIENT_1
            {"data": [_job_row(job_id=JOB_1_ID, client_id=CLIENT_1_ID)]},
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.get_job(
            job_id=JOB_1_ID,
            roles=_advisor_roles(ADVISOR_1_ID),
        )

    assert result.id == JOB_1_ID
    assert result.state == "running"
    assert result.client_id == CLIENT_1_ID
    assert result.result is None  # not "complete" → no payload assembly
    assert fake.tables_queried == ["clients", "jobs"]


@pytest.mark.asyncio
async def test_advisor_cannot_view_other_advisors_client_job():
    """ORPHEUS-46 (b): advisor opens a job for someone else's client → 404.

    The .in_("client_id", [...]) filter on the jobs query excludes the
    other-advisor's client_id, so the jobs response is empty even though
    the job exists in the database. We must return 404 — not 403 — so we
    don't leak that the job exists.
    """
    fake = FakeSupabase(
        responses=[
            # clients query — advisor manages CLIENT_1 only (not CLIENT_2)
            {"data": [{"id": CLIENT_1_ID}]},
            # jobs query — filtered by .in_(["CLIENT_1"]), so JOB_2 (belonging
            # to CLIENT_2) doesn't come back
            {"data": []},
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await jobs_router.get_job(
                job_id=JOB_2_ID,
                roles=_advisor_roles(ADVISOR_1_ID),
            )

    assert exc.value.status_code == 404
    assert JOB_2_ID in exc.value.detail
    assert fake.tables_queried == ["clients", "jobs"]


@pytest.mark.asyncio
async def test_advisor_with_no_clients_gets_404():
    """ORPHEUS-46 (c): advisor with no clients short-circuits to 404.

    The handler skips the jobs query entirely when allowed_client_ids is
    empty — no point asking the jobs table about an empty filter, and
    the answer is the same (404) regardless of whether the job exists.
    """
    fake = FakeSupabase(
        responses=[
            # clients query — no rows
            {"data": []},
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await jobs_router.get_job(
                job_id=JOB_1_ID,
                roles=_advisor_roles(ADVISOR_1_ID),
            )

    assert exc.value.status_code == 404
    # Only the clients query fired — the short-circuit kicked in before
    # we touched the jobs table.
    assert fake.tables_queried == ["clients"]


# --------------------------------------------------------------------------- #
# Client path — regression on the original behavior
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_client_can_view_own_job():
    """ORPHEUS-46 (d): the original client path still works.

    Client-only callers don't expand the clients table — `allowed_client_ids`
    is just `{roles.client_id}`. Only one query fires: jobs.
    """
    fake = FakeSupabase(
        responses=[
            # jobs query only
            {"data": [_job_row(job_id=JOB_1_ID, client_id=CLIENT_1_ID)]},
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.get_job(
            job_id=JOB_1_ID,
            roles=_client_roles(CLIENT_1_ID),
        )

    assert result.id == JOB_1_ID
    assert result.client_id == CLIENT_1_ID
    # No clients-table expansion for a client-only caller.
    assert fake.tables_queried == ["jobs"]


@pytest.mark.asyncio
async def test_client_cannot_view_other_clients_job():
    """ORPHEUS-46 (e): client viewing another client's job → 404.

    The .in_("client_id", [own_client_id]) filter excludes the other
    client's jobs at the query level — empty response, 404 to the
    caller, no leak.
    """
    fake = FakeSupabase(
        responses=[
            # jobs query — JOB_2 belongs to CLIENT_2, filtered out
            {"data": []},
        ]
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await jobs_router.get_job(
                job_id=JOB_2_ID,
                roles=_client_roles(CLIENT_1_ID),
            )

    assert exc.value.status_code == 404
    assert fake.tables_queried == ["jobs"]
