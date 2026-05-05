"""Jobs API — the endpoint the frontend's `useJob` hook polls.

Contract mirrors frontend/src/types/job.ts: a `Job` with id, state, timestamps,
optional `result` (ScoringStageOutput + Narratives), and optional `error`.

This router ships in ORPHEUS-27. RLS is still disabled at this phase, so
authorization is currently enforced only by the `get_current_client`
dependency matching the token's `sub` against a `public.clients` row, plus
the `.eq("client_id", current.client_id)` filter below. Once ORPHEUS-29
enables RLS, the user-scoped Supabase client in `backend/db.user_scoped_supabase`
adds a second, database-level enforcement layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import CurrentClient, get_current_client
from backend.db import user_scoped_supabase
from backend.models.job import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    current: CurrentClient = Depends(get_current_client),
) -> Job:
    """Fetch a single job by id. Caller must own it.

    Returns 404 for either "no such job" or "job belongs to someone else" —
    we don't leak the existence of another client's jobs.
    """
    supabase = user_scoped_supabase(current.access_token)

    result = (
        supabase.table("jobs")
        .select("*")
        .eq("id", job_id)
        .eq("client_id", current.client_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id!r} not found.",
        )

    row = result.data[0]

    # The frontend's JobResultPayload lives in two columns: the scoring engine
    # output and the narratives. Join them here into the `result` dict the
    # React client expects. When either is missing (state != complete), we
    # pass `None`.
    payload = _build_result_payload(supabase, job_id)

    return Job(
        id=str(row["id"]),
        state=row["status"],  # db column is `status`; frontend type is `state`
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
        client_id=row.get("client_id"),
        result=payload,
        error=row.get("error_message"),
    )


def _build_result_payload(supabase, job_id: str) -> dict | None:
    """Join scoring + narratives rows into the JobResultPayload dict.

    Returns None if either half is missing (i.e. job not yet complete).
    """
    scores = (
        supabase.table("scores")
        .select("*")
        .eq("job_id", job_id)
        .limit(1)
        .execute()
    )
    if not scores.data:
        return None

    narratives_rows = (
        supabase.table("narratives")
        .select("section,content")
        .eq("job_id", job_id)
        .execute()
    )
    if not narratives_rows.data:
        return None

    score_row = scores.data[0]
    dimension_narratives: dict[str, str] = {}
    forward_brief: str | None = None
    cheat_sheet: dict | None = None

    for n in narratives_rows.data:
        section = n["section"]
        content = n["content"]
        if section == "forward_brief":
            forward_brief = content if isinstance(content, str) else None
        elif section == "cheat_sheet":
            cheat_sheet = content if isinstance(content, dict) else None
        else:
            dimension_narratives[section] = (
                content if isinstance(content, str) else ""
            )

    if forward_brief is None or cheat_sheet is None:
        return None

    return {
        "scoring": {
            "scored_dimensions": score_row.get("scored_dimensions"),
            "forward_brief_data": score_row.get("forward_brief_data"),
        },
        "narratives": {
            "dimension_narratives": dimension_narratives,
            "forward_brief": forward_brief,
            "cheat_sheet": cheat_sheet,
        },
    }
