"""Jobs API — the endpoint the frontend's `useJob` hook polls plus the
multipart POST /jobs that the LinkedIn upload flow submits to (ORPHEUS-16).

Contract mirrors frontend/src/types/job.ts: a `Job` with id, state, timestamps,
optional `result` (ScoringStageOutput + Narratives), and optional `error`.

The GET path uses `user_scoped_supabase` so RLS (migration 008) enforces
ownership at the database. The POST path uses the service-role client
because `ingested_data` only has SELECT RLS for clients — INSERTs are
server-only — and we want a single client throughout the multi-table write
so partial failures are easier to reason about.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.auth import CurrentClient, get_current_client
from backend.db import get_service_client, user_scoped_supabase
from backend.ingestion.xlsx_parser import parse_xlsx
from backend.ingestion.zip_parser import parse_zip
from backend.models.job import Job

logger = logging.getLogger("orpheus.jobs")

router = APIRouter(prefix="/jobs", tags=["jobs"])


# Storage configuration. Mirrors the path convention the worker reads from
# (backend/workers/processor.py): `uploads/{client_id}/{job_id}/archive.zip`
# and `analytics.xlsx`. Keep these strings in sync with the worker.
_STORAGE_BUCKET = "uploads"
_ARCHIVE_FILENAME = "archive.zip"
_ANALYTICS_FILENAME = "analytics.xlsx"

# Reasonable upper bounds. The LinkedIn complete archive is typically
# 5–50 MB; the analytics XLSX is well under 1 MB. We don't want to OOM the
# Railway dyno on a hostile upload. Tune these in config.py if real-world
# archives push past them.
_MAX_ARCHIVE_BYTES = 200 * 1024 * 1024  # 200 MB
_MAX_ANALYTICS_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("", response_model=Job, status_code=status.HTTP_201_CREATED)
async def create_job(
    archive: Annotated[UploadFile, File(description="LinkedIn complete data archive (ZIP).")],
    analytics: Annotated[UploadFile, File(description="LinkedIn Analytics export (XLSX).")],
    current: CurrentClient = Depends(get_current_client),
) -> Job:
    """Create a new analysis job from a client's uploaded LinkedIn data.

    Pipeline at request time:

      1. Read both uploads into memory (size-capped).
      2. Parse the ZIP and the XLSX inline so we surface bad uploads as
         400s rather than letting the worker fail later.
      3. Insert a `pending` job row to mint a job_id.
      4. Upload the raw bytes to Supabase Storage at the path the worker
         reads from. The worker will re-parse from there — this gives us
         a durable copy independent of whatever the request handler did.
      5. Persist the parsed JSONB + quality report into ingested_data so
         the worker's stage_ingestion can short-circuit if it ever wants
         to (today it always re-parses; that's an idempotent upsert).

    Returns the freshly-created Job (state=pending, no result yet). The
    frontend redirects to the Analysis-in-Progress screen which polls
    GET /jobs/{id} for completion.
    """

    # ── 1. Read & validate uploads ─────────────────────────────────────

    archive_bytes = await _read_upload(archive, _MAX_ARCHIVE_BYTES, "archive")
    analytics_bytes = await _read_upload(
        analytics, _MAX_ANALYTICS_BYTES, "analytics"
    )

    # ── 2. Parse inline so bad uploads fail fast ───────────────────────

    try:
        zip_data, quality_report = parse_zip(archive_bytes)
    except Exception as exc:
        # parse_zip raises BadZipFile / FileNotFoundError / KeyError on
        # malformed inputs. Surface a stable 400 to the client.
        logger.warning(
            "ZIP parse failed for client %s: %s", current.client_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "We couldn't read your LinkedIn archive. Please make sure "
                "you uploaded the unmodified ZIP from "
                "Settings → Data privacy → Download larger data archive."
            ),
        ) from exc

    try:
        xlsx_data = parse_xlsx(analytics_bytes)
    except Exception as exc:
        logger.warning(
            "XLSX parse failed for client %s: %s", current.client_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "We couldn't read your LinkedIn analytics export. Please "
                "make sure you uploaded the XLSX exactly as LinkedIn "
                "delivered it from the Analytics → Export flow."
            ),
        ) from exc

    # ── 3. Mint the job row ────────────────────────────────────────────

    supabase = get_service_client()

    job_insert = (
        supabase.table("jobs")
        .insert(
            {
                "client_id": current.client_id,
                "status": "pending",
            }
        )
        .execute()
    )
    if not job_insert.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job row.",
        )
    job_row = job_insert.data[0]
    job_id = str(job_row["id"])

    logger.info(
        "Created pending job %s for client %s", job_id, current.client_id
    )

    # ── 4. Upload raw bytes to Supabase Storage ────────────────────────

    archive_path = (
        f"{current.client_id}/{job_id}/{_ARCHIVE_FILENAME}"
    )
    analytics_path = (
        f"{current.client_id}/{job_id}/{_ANALYTICS_FILENAME}"
    )
    try:
        supabase.storage.from_(_STORAGE_BUCKET).upload(
            archive_path,
            archive_bytes,
            {"content-type": "application/zip", "upsert": "true"},
        )
        supabase.storage.from_(_STORAGE_BUCKET).upload(
            analytics_path,
            analytics_bytes,
            {
                "content-type": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                "upsert": "true",
            },
        )
    except Exception as exc:
        # Storage write failed after the job row exists. Mark the job
        # failed so the orphan is visible in the dashboard rather than
        # leaving the client polling forever.
        logger.exception(
            "Storage upload failed for job %s: %s", job_id, exc
        )
        supabase.table("jobs").update(
            {
                "status": "failed",
                "error_message": "Storage upload failed; please retry.",
            }
        ).eq("id", job_id).execute()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "We couldn't save your files. This is usually transient — "
                "please try again in a moment."
            ),
        ) from exc

    # ── 5. Persist parsed data + quality report ────────────────────────

    try:
        supabase.table("ingested_data").upsert(
            {
                "job_id": job_id,
                "zip_data": zip_data.model_dump(),
                "xlsx_data": xlsx_data.model_dump(),
                "quality_report": quality_report.model_dump(),
                "ingested_at": datetime.utcnow().isoformat(),
            },
            on_conflict="job_id",
        ).execute()
    except Exception as exc:
        # If ingested_data insert fails (e.g. table missing on a partial
        # local-dev schema), the worker's stage_ingestion will re-parse
        # from storage on its first run, so the job can still complete.
        # We log loudly but don't fail the request — the user has
        # successfully submitted and will see real progress on the
        # Analysis screen.
        logger.exception(
            "Persisting ingested_data for job %s failed (worker will "
            "re-parse from storage): %s",
            job_id,
            exc,
        )

    return Job(
        id=job_id,
        state=job_row["status"],
        created_at=job_row["created_at"],
        updated_at=job_row.get("updated_at"),
        client_id=job_row.get("client_id"),
        result=None,
        error=None,
    )


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

    # The frontend's JobResultPayload lives in two tables: scores and
    # narratives. Only fetch them once the worker has finished writing —
    # for pending/running/failed jobs, those rows don't exist yet, and
    # querying them is both wasteful and (on a partial dev schema) fatal.
    # The AnalysisPage polls this endpoint every 3s; a cheap pending
    # response keeps that quiet.
    payload = (
        _build_result_payload(supabase, job_id)
        if row["status"] == "complete"
        else None
    )

    return Job(
        id=str(row["id"]),
        state=row["status"],  # db column is `status`; frontend type is `state`
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
        client_id=row.get("client_id"),
        result=payload,
        error=row.get("error_message"),
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _read_upload(
    upload: UploadFile, max_bytes: int, label: str
) -> bytes:
    """Read an UploadFile into memory with a size cap.

    Streams the file in chunks so a hostile request can't exhaust memory
    before we notice — we abort with a 413 once max_bytes is crossed.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)  # 1 MB at a time
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Your {label} upload exceeds the "
                    f"{max_bytes // (1024 * 1024)} MB limit. "
                    "Please contact support if you have a larger archive."
                ),
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The {label} upload is empty.",
        )
    return b"".join(chunks)


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
