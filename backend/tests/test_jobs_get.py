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


# --------------------------------------------------------------------------- #
# Complete-job payload assembly — ORPHEUS-59 regression
# --------------------------------------------------------------------------- #
#
# Background: the first cloud e2e (2026-06-02) crashed because
# `_build_result_payload` was written against a schema that never landed.
# Three independent mismatches stacked:
#
#   * narratives.content → narratives.generated_text (+ edited_text)
#   * scores.scored_dimensions → scores.dimensions (already-serialized
#     ScoredDimensions JSONB)
#   * cheat_sheet section is never produced by the narrative agent;
#     the handler had been short-circuiting to None on every complete
#     job because of that
#
# These tests pin the wire-shape contract so the next migration touching
# either table doesn't silently re-break complete-job rendering.


def _score_row(*, job_id: str) -> dict[str, Any]:
    """Minimal scores row in the shape the worker writes today.

    `dimensions` is the JSONB-serialized ScoredDimensions; the handler
    forwards it verbatim under the `scored_dimensions` wire key.
    """
    return {
        "id": "score-uuid",
        "job_id": job_id,
        "total_score": 58.0,
        "band": "Tuning",
        "dimensions": {
            "composite": 58.0,
            "band": "Tuning",
            "dimensions": [
                {
                    "name": "Profile Signal Clarity",
                    "weight": 0.35,
                    "confidence": "CONFIRMED",
                    "normalized_score": 0.72,
                    "contribution": 25.2,
                    "band": "Tuned",
                    "sub_dimensions": [],
                    "completeness_floor_applied": False,
                },
            ],
        },
        "forward_brief_data": {
            "quantitative": {"follower_count": 1247},
            "qualitative_flags": {},
        },
        "scored_at": "2026-06-02T00:00:00+00:00",
    }


def _narrative_row(
    *, section: str, generated_text: str, edited_text: str | None = None
) -> dict[str, Any]:
    return {
        "section": section,
        "generated_text": generated_text,
        "edited_text": edited_text,
    }


@pytest.mark.asyncio
async def test_complete_job_assembles_payload():
    """ORPHEUS-59: a complete job returns a fully-shaped `result` payload.

    Covers the wire contract end to end: `scored_dimensions` populated
    from `scores.dimensions`, `dimension_narratives` keyed by section
    name from `generated_text`, `forward_brief` from its row, and
    `cheat_sheet` serialized as null (the agent doesn't emit it yet).
    """
    fake = FakeSupabase(
        responses=[
            # jobs query — status=complete fires the payload assembly
            {
                "data": [
                    _job_row(
                        job_id=JOB_1_ID,
                        client_id=CLIENT_1_ID,
                        status_value="complete",
                    )
                ]
            },
            # scores query
            {"data": [_score_row(job_id=JOB_1_ID)]},
            # narratives query — 4 dim sections + forward_brief, no
            # cheat_sheet (matches the agent's actual output)
            {
                "data": [
                    _narrative_row(
                        section="Profile Signal Clarity",
                        generated_text="Profile narrative.",
                    ),
                    _narrative_row(
                        section="Behavioral Signal Strength",
                        generated_text="Strength narrative.",
                    ),
                    _narrative_row(
                        section="Behavioral Signal Quality",
                        generated_text="Quality narrative.",
                    ),
                    _narrative_row(
                        section="Profile-Behavior Alignment",
                        generated_text="Alignment narrative.",
                    ),
                    _narrative_row(
                        section="forward_brief",
                        generated_text="Forward brief body.",
                    ),
                ]
            },
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.get_job(
            job_id=JOB_1_ID,
            roles=_client_roles(CLIENT_1_ID),
        )

    assert result.state == "complete"
    assert result.result is not None
    # Wire-key contract: handler forwards `scores.dimensions` under
    # `scored_dimensions` for backward compat with the frontend type.
    scoring = result.result["scoring"]
    assert scoring["scored_dimensions"]["composite"] == 58.0
    assert scoring["scored_dimensions"]["band"] == "Tuning"
    assert scoring["forward_brief_data"]["quantitative"]["follower_count"] == 1247
    # Narratives: four dimension entries + forward_brief, no cheat_sheet.
    narr = result.result["narratives"]
    assert set(narr["dimension_narratives"].keys()) == {
        "Profile Signal Clarity",
        "Behavioral Signal Strength",
        "Behavioral Signal Quality",
        "Profile-Behavior Alignment",
    }
    assert narr["forward_brief"] == "Forward brief body."
    assert narr["cheat_sheet"] is None
    assert fake.tables_queried == ["jobs", "scores", "narratives"]


@pytest.mark.asyncio
async def test_complete_job_edited_text_wins_over_generated():
    """ORPHEUS-31 + ORPHEUS-59: admin edits surface to the client.

    When `narratives.edited_text` is a non-empty string, the handler
    uses it instead of `generated_text` — admin saves a typo fix or a
    full rewrite from /admin and the next polling tick sees it.
    """
    fake = FakeSupabase(
        responses=[
            {
                "data": [
                    _job_row(
                        job_id=JOB_1_ID,
                        client_id=CLIENT_1_ID,
                        status_value="complete",
                    )
                ]
            },
            {"data": [_score_row(job_id=JOB_1_ID)]},
            {
                "data": [
                    _narrative_row(
                        section="Profile Signal Clarity",
                        generated_text="Generator output.",
                        edited_text="Andrew's hand-tuned version.",
                    ),
                    _narrative_row(
                        section="forward_brief",
                        generated_text="Generated brief.",
                        edited_text="   ",  # whitespace-only doesn't win
                    ),
                ]
            },
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.get_job(
            job_id=JOB_1_ID,
            roles=_client_roles(CLIENT_1_ID),
        )

    assert result.result is not None
    narr = result.result["narratives"]
    # Non-empty edited_text wins.
    assert (
        narr["dimension_narratives"]["Profile Signal Clarity"]
        == "Andrew's hand-tuned version."
    )
    # Whitespace-only edited_text falls through to generated_text.
    assert narr["forward_brief"] == "Generated brief."


@pytest.mark.asyncio
async def test_complete_job_with_missing_scores_returns_no_result():
    """`scores` row missing → `result` is null on the wire, not 500.

    The job row says status=complete but the scores row hasn't been
    written yet (or was deleted). The handler short-circuits to None
    rather than raising — the polling AnalysisPage stays on the
    in-progress screen until the data arrives.
    """
    fake = FakeSupabase(
        responses=[
            {
                "data": [
                    _job_row(
                        job_id=JOB_1_ID,
                        client_id=CLIENT_1_ID,
                        status_value="complete",
                    )
                ]
            },
            # scores query returns nothing
            {"data": []},
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.get_job(
            job_id=JOB_1_ID,
            roles=_client_roles(CLIENT_1_ID),
        )

    assert result.state == "complete"
    assert result.result is None
    # Narratives query was not made — scores miss short-circuits early.
    assert fake.tables_queried == ["jobs", "scores"]


@pytest.mark.asyncio
async def test_complete_job_with_missing_forward_brief_returns_no_result():
    """Missing forward_brief narrative → `result` is null.

    Dimension narratives without the forward_brief is an incomplete
    state — the frontend's Forward Brief page would 500 on a null
    body. Surface null `result` so the polling stays open until the
    full set lands.
    """
    fake = FakeSupabase(
        responses=[
            {
                "data": [
                    _job_row(
                        job_id=JOB_1_ID,
                        client_id=CLIENT_1_ID,
                        status_value="complete",
                    )
                ]
            },
            {"data": [_score_row(job_id=JOB_1_ID)]},
            {
                "data": [
                    _narrative_row(
                        section="Profile Signal Clarity",
                        generated_text="Profile narrative.",
                    ),
                    # no forward_brief row
                ]
            },
        ]
    )

    with _patch_supabase(fake):
        result = await jobs_router.get_job(
            job_id=JOB_1_ID,
            roles=_client_roles(CLIENT_1_ID),
        )

    assert result.state == "complete"
    assert result.result is None
