"""Unit tests for ORPHEUS-81 — GET /jobs (reports list) and the
concurrent-run guard on POST /jobs.

Direct handler-invocation pattern, same as test_jobs_get.py: build a
`SessionRoles`, monkey-patch `get_service_client`, call the route
function (or helper). FastAPI's dependency injection is bypassed for
unit-level isolation.

Coverage:

  list_jobs:
    - (a) Client with mixed-status jobs → rows newest-first with band
          joined onto complete jobs only.
    - (b) Client with no jobs → empty list, scores query skipped.
    - (c) Advisor-only caller → 403 (the advisor surface keeps the
          latest_job chip on GET /clients; no advisor branch here).
    - (d) Complete job with a missing scores row → band null, no crash.

  _has_active_job (the POST /jobs guard):
    - (e) Pending job present → True.
    - (f) Only terminal-status jobs → False (the .in_ filter excludes
          them server-side; an empty response is the signal).
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

CLIENT_ID = "11111111-1111-1111-1111-111111111111"
ADVISOR_ID = "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa"

JOB_COMPLETE_ID = "job-1111-1111-1111-111111111111"
JOB_RUNNING_ID = "job-2222-2222-2222-222222222222"
JOB_FAILED_ID = "job-3333-3333-3333-333333333333"


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


def _client_roles() -> SessionRoles:
    return SessionRoles(
        user_id="user-client-uuid",
        email="client@example.com",
        access_token="test-token",
        advisor_id=None,
        client_id=CLIENT_ID,
    )


def _advisor_only_roles() -> SessionRoles:
    return SessionRoles(
        user_id="user-advisor-uuid",
        email="andrew@ess3.ai",
        access_token="test-token",
        advisor_id=ADVISOR_ID,
        client_id=None,
    )


# --------------------------------------------------------------------------- #
# Pluggable supabase chain — same shape as test_jobs_get.py
# --------------------------------------------------------------------------- #

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


def _job_row(*, job_id: str, status_value: str) -> dict[str, Any]:
    return {
        "id": job_id,
        "status": status_value,
        "created_at": "2026-06-12T00:00:00+00:00",
        "updated_at": "2026-06-12T00:00:01+00:00",
    }


# --------------------------------------------------------------------------- #
# GET /jobs — list_jobs
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_list_jobs_joins_band_onto_complete_rows():
    """(a) Mixed-status list: band lands on the complete row only."""
    fake = FakeSupabase(
        responses=[
            # jobs query — newest first (running, then complete, then failed)
            {
                "data": [
                    _job_row(job_id=JOB_RUNNING_ID, status_value="running"),
                    _job_row(job_id=JOB_COMPLETE_ID, status_value="complete"),
                    _job_row(job_id=JOB_FAILED_ID, status_value="failed"),
                ]
            },
            # scores query — bucketed on the complete ids only
            {"data": [{"job_id": JOB_COMPLETE_ID, "band": "Tuned"}]},
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.list_jobs(roles=_client_roles())

    assert [r.id for r in result] == [
        JOB_RUNNING_ID,
        JOB_COMPLETE_ID,
        JOB_FAILED_ID,
    ]
    assert [r.band for r in result] == [None, "Tuned", None]
    assert [r.state for r in result] == ["running", "complete", "failed"]
    assert fake.tables_queried == ["jobs", "scores"]


@pytest.mark.asyncio
async def test_list_jobs_empty_skips_scores_query():
    """(b) No jobs → empty list, and the scores table is never queried."""
    fake = FakeSupabase(responses=[{"data": []}])

    with _patch_supabase(fake):
        result = await jobs_router.list_jobs(roles=_client_roles())

    assert result == []
    assert fake.tables_queried == ["jobs"]


@pytest.mark.asyncio
async def test_list_jobs_rejects_advisor_only_caller():
    """(c) Advisor-only session → 403; no queries fire."""
    fake = FakeSupabase(responses=[])

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await jobs_router.list_jobs(roles=_advisor_only_roles())

    assert exc.value.status_code == 403
    assert fake.tables_queried == []


@pytest.mark.asyncio
async def test_list_jobs_tolerates_missing_scores_row():
    """(d) Complete job without a scores row → band null, no crash."""
    fake = FakeSupabase(
        responses=[
            {"data": [_job_row(job_id=JOB_COMPLETE_ID, status_value="complete")]},
            {"data": []},  # scores query comes back empty
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.list_jobs(roles=_client_roles())

    assert len(result) == 1
    assert result[0].band is None
    assert result[0].state == "complete"


# --------------------------------------------------------------------------- #
# POST /jobs — concurrent-run guard helper
# --------------------------------------------------------------------------- #

def test_has_active_job_true_when_pending_exists():
    """(e) A pending/running row comes back → guard fires."""
    fake = FakeSupabase(
        responses=[{"data": [{"id": JOB_RUNNING_ID}]}]
    )
    assert jobs_router._has_active_job(fake, CLIENT_ID) is True
    assert fake.tables_queried == ["jobs"]


def test_has_active_job_false_when_only_terminal_jobs():
    """(f) The .in_(["pending","running"]) filter excludes terminal rows
    server-side, so an empty response means no active job."""
    fake = FakeSupabase(responses=[{"data": []}])
    assert jobs_router._has_active_job(fake, CLIENT_ID) is False
