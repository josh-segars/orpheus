"""Jobs API — the endpoint the frontend's `useJob` hook polls plus the
multipart POST /jobs that the LinkedIn upload flow submits to (ORPHEUS-16).

Contract mirrors frontend/src/types/job.ts: a `Job` with id, state, timestamps,
optional `result` (ScoringStageOutput + Narratives), and optional `error`.

Both paths use the service-role Supabase client. The POST path uses it
because `ingested_data` only has SELECT RLS for clients — INSERTs are
server-only — and we want a single client throughout the multi-table write
so partial failures are easier to reason about. The GET path used to lean
on `user_scoped_supabase` for RLS-backed ownership checks; ORPHEUS-46
moved it to service-role + an explicit `allowed_client_ids` check so the
same handler can serve both clients viewing their own jobs and advisors
viewing the jobs of clients they manage. The leak-resistance contract is
preserved by the handler (404 for any case the caller can't see),
matching the pattern already used by `GET /clients`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.auth import SessionRoles, get_current_session_roles
from backend.db import get_service_client
from backend.ingestion.xlsx_parser import parse_xlsx
from backend.ingestion.zip_parser import parse_zip
from backend.models.job import Job, JobSummary

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
    roles: SessionRoles = Depends(get_current_session_roles),
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

    Requires the client role — advisors hitting this endpoint without an
    accompanying clients row get a 403, not silent acceptance into a
    job they couldn't see afterward.
    """

    if not roles.is_client():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submitting a diagnostic requires a client profile.",
        )
    client_id = roles.client_id
    assert client_id is not None  # narrowed by is_client() guard above

    # ── 0. Concurrent-run guard (ORPHEUS-81) ───────────────────────────
    # One in-flight pipeline per client. Checked before the uploads are
    # even read so the reject is cheap. The frontend hides the "Run a
    # new report" entry point while a job is in flight; this is the
    # authoritative backstop for direct submissions.

    supabase = get_service_client()
    if _has_active_job(supabase, client_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You already have a report in progress. Please wait for "
                "it to finish before starting a new one."
            ),
        )

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
            "ZIP parse failed for client %s: %s", client_id, exc
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
            "XLSX parse failed for client %s: %s", client_id, exc
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

    job_insert = (
        supabase.table("jobs")
        .insert(
            {
                "client_id": client_id,
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
        "Created pending job %s for client %s", job_id, client_id
    )

    # ── 4. Upload raw bytes to Supabase Storage ────────────────────────

    archive_path = (
        f"{client_id}/{job_id}/{_ARCHIVE_FILENAME}"
    )
    analytics_path = (
        f"{client_id}/{job_id}/{_ANALYTICS_FILENAME}"
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


@router.get("", response_model=list[JobSummary])
async def list_jobs(
    roles: SessionRoles = Depends(get_current_session_roles),
) -> list[JobSummary]:
    """List the caller's own jobs, newest first (ORPHEUS-81).

    Backs the client's reports list page. Client role required — the
    advisor surface keeps its `latest_job` chip on `GET /clients` for
    v1 (per-client report history is a separate follow-up), so there's
    no advisor branch here. Dual-role callers (Andrew) get their own
    client row's jobs, same as any client.

    Two queries: the caller's jobs, then a bucketed scores read
    (`job_id, band`) for the complete ones so each list row can show
    its composite band without dragging the full result payload over
    the wire. Mirrors the bucketing pattern in `GET /clients`.
    """
    if not roles.is_client():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewing reports requires a client profile.",
        )
    client_id = roles.client_id
    assert client_id is not None  # narrowed by is_client() guard above

    supabase = get_service_client()

    # NB: column list must match the live schema — jobs has created_at /
    # started_at / completed_at, NOT updated_at. Selecting a nonexistent
    # column makes PostgREST 400 and the handler 500 (ORPHEUS-59/61
    # anti-pattern; bitten again on this endpoint's first deploy).
    jobs_result = (
        supabase.table("jobs")
        .select("id,status,created_at")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = jobs_result.data or []
    if not rows:
        return []

    complete_ids = [
        str(r["id"]) for r in rows if r.get("status") == "complete"
    ]
    band_by_job: dict[str, str] = {}
    if complete_ids:
        scores_result = (
            supabase.table("scores")
            .select("job_id,band")
            .in_("job_id", complete_ids)
            .execute()
        )
        for s in scores_result.data or []:
            if s.get("band"):
                band_by_job[str(s["job_id"])] = s["band"]

    return [
        JobSummary(
            id=str(r["id"]),
            state=r["status"],
            created_at=r["created_at"],
            band=band_by_job.get(str(r["id"])),
        )
        for r in rows
    ]


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    roles: SessionRoles = Depends(get_current_session_roles),
) -> Job:
    """Fetch a single job by id. Caller must own it via either role.

    Returns 404 for any case the caller can't see — "no such job", "job
    belongs to a client that isn't yours", or "advisor doesn't manage
    that client". We don't leak the existence of jobs the caller can't
    see (matches the leak-resistance contract on `GET /clients`).

    Role gate accepts either:
      * is_client() — the original client-viewing-own-report path. Job
        must belong to `roles.client_id`.
      * is_advisor() — ORPHEUS-46. Job must belong to a client the
        advisor manages (`clients.advisor_id == roles.advisor_id`).

    Dual-role callers (an advisor who is also their own client, e.g.
    Andrew) see the union of both predicates. The advisor's self-clients
    row appears among their managed clients, so the union is idempotent
    for the "view own self-report" case.

    Uses the service-role Supabase client and an explicit
    `allowed_client_ids` filter rather than `user_scoped_supabase`,
    matching the pattern in `GET /clients`. The handler enforces
    ownership directly; RLS is not relied upon here.
    """
    if not (roles.is_client() or roles.is_advisor()):
        # Unreachable under `get_current_session_roles` (which 401s the
        # neither-role case) but defends against a future code path
        # that swaps in `get_verified_session` here.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewing a diagnostic requires a client or advisor profile.",
        )

    supabase = get_service_client()

    # Compute the set of client_ids whose jobs this caller is allowed
    # to see. Service-role lookup because RLS on `clients` keys on
    # auth.uid() and we want the advisor's roster regardless of the
    # session token's RLS context.
    allowed_client_ids: set[str] = set()
    if roles.is_client():
        assert roles.client_id is not None  # narrowed by is_client()
        allowed_client_ids.add(roles.client_id)
    if roles.is_advisor():
        advisor_clients = (
            supabase.table("clients")
            .select("id")
            .eq("advisor_id", roles.advisor_id)
            .execute()
        )
        for client_row in advisor_clients.data or []:
            allowed_client_ids.add(str(client_row["id"]))

    if not allowed_client_ids:
        # Advisor with zero managed clients (and no client role of
        # their own). The job, if it exists, definitionally doesn't
        # belong to them — 404 not 403 to match the leak-resistance
        # contract.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id!r} not found.",
        )

    result = (
        supabase.table("jobs")
        .select("*")
        .eq("id", job_id)
        .in_("client_id", list(allowed_client_ids))
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


def _has_active_job(supabase, client_id: str) -> bool:
    """True when the client has a job in a non-terminal state.

    The concurrent-run guard on POST /jobs (ORPHEUS-81): one in-flight
    pipeline per client. `pending` and `running` are the non-terminal
    states; `complete` and `failed` don't block a new run (failed jobs
    are retried by submitting fresh — the worker's own 3× retry happens
    within the `running` state).
    """
    result = (
        supabase.table("jobs")
        .select("id")
        .eq("client_id", client_id)
        .in_("status", ["pending", "running"])
        .limit(1)
        .execute()
    )
    return bool(result.data)


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

    Returns None when the worker hasn't finished writing either half —
    no scores row, or no narratives at all. ORPHEUS-68 retired the
    standalone forward_brief narrative: new jobs don't write the row,
    and the wire payload no longer carries a `forward_brief` key. Rows
    with section='forward_brief' on the three preserved pre-68 demo
    jobs are tolerated and ignored. The per-dimension `summary` field
    (the always-visible card teaser) rides `scores.dimensions` JSONB
    and surfaces through `scored_dimensions` automatically — null on
    pre-68 jobs, which the frontend renders via graceful fallback.

    ORPHEUS-59 reconciled three mismatches between this reader and
    what the worker actually persists:

      * `narratives.content` was renamed to `generated_text` (plus
        `edited_text` for the admin-edit override path; ORPHEUS-31).
        We read both and prefer a non-empty `edited_text` so admin
        edits surface to the client without a worker re-run.
      * `scores.scored_dimensions` is `scores.dimensions` on the
        wire — the worker writes the serialized ScoredDimensions
        JSONB directly into that column.
      * `cheat_sheet` was added to the agent's output in ORPHEUS-60
        (this handler change shipped alongside). When the worker
        persists a `section='cheat_sheet'` row, its `generated_text`
        is the JSON-encoded `CheatSheetContent`; we deserialize on
        read. Legacy jobs that predate ORPHEUS-60 have no such row
        and the wire serializes `cheat_sheet: null` — CheatSheetPage's
        existing null-state branch renders the not-ready surface.
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
        .select("section,generated_text,edited_text")
        .eq("job_id", job_id)
        .execute()
    )
    if not narratives_rows.data:
        return None

    score_row = scores.data[0]
    dimension_narratives: dict[str, str] = {}
    cheat_sheet: dict | None = None

    for n in narratives_rows.data:
        section = n["section"]
        # `edited_text` wins when the admin has saved a non-empty
        # override; otherwise fall through to the generator's output.
        edited = n.get("edited_text")
        generated = n.get("generated_text")
        if isinstance(edited, str) and edited.strip():
            text = edited
        elif isinstance(generated, str):
            text = generated
        else:
            text = ""

        if section == "forward_brief":
            # ORPHEUS-68: the standalone Forward Brief is retired. The three
            # preserved pre-68 demo jobs still have this row — ignore it
            # rather than surface or 500.
            continue
        elif section == "cheat_sheet":
            # ORPHEUS-60: deserialize the JSON-encoded CheatSheetContent
            # back into a dict for the wire. Malformed JSON falls back to
            # None rather than 500ing the whole job — the frontend's
            # null-state surface is the graceful path here. Admin edits
            # of cheat_sheet via /admin (which would land plain text in
            # `edited_text`) currently fail this parse and degrade to
            # the legacy null path; structured editing is a future
            # follow-up if it becomes a need.
            try:
                parsed = json.loads(text) if text else None
            except (ValueError, TypeError):
                logger.warning(
                    "Job %s cheat_sheet row failed JSON parse; "
                    "serializing null on the wire.",
                    job_id,
                )
                parsed = None
            if isinstance(parsed, dict):
                cheat_sheet = parsed
        else:
            dimension_narratives[section] = text

    if not dimension_narratives:
        return None

    return {
        "scoring": {
            "scored_dimensions": score_row.get("dimensions"),
            "forward_brief_data": score_row.get("forward_brief_data"),
        },
        "narratives": {
            "dimension_narratives": dimension_narratives,
            "cheat_sheet": cheat_sheet,
        },
    }
