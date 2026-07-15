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
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.auth import SessionRoles, get_current_session_roles
from backend.db import get_service_client
from backend.ingestion.xlsx_parser import latest_analytics_date, parse_xlsx
from backend.ingestion.zip_parser import parse_archive_filename, parse_zip
from backend.models.job import Job, JobSummary
from backend.models.quality import DataQualityReport

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

# ORPHEUS-100: reject an upload whose analytics data ends more than this many
# days before today — the client is re-uploading a stale export and the
# report would be built on an old snapshot. LinkedIn analytics refreshes
# continuously, so a fresh export ends within a day of today.
_STALE_ARCHIVE_DAYS = 14


@router.post("", response_model=Job, status_code=status.HTTP_201_CREATED)
async def create_job(
    archive: Annotated[UploadFile, File(description="LinkedIn complete data archive (ZIP).")],
    analytics: Annotated[UploadFile, File(description="LinkedIn Analytics export (XLSX).")],
    has_profile_photo: Annotated[
        bool | None,
        Form(
            description=(
                "Whether the client's LinkedIn OIDC session carries a "
                "profile picture claim (ORPHEUS-89). Captured client-side "
                "at submission; overrides the ZIP rich-media photo "
                "heuristic. Omitted/None falls back to the heuristic."
            ),
        ),
    ] = None,
    roles: SessionRoles = Depends(get_current_session_roles),
) -> Job:
    """Create a new analysis job from a client's uploaded LinkedIn data.

    LEGACY PATH (ORPHEUS-108): the frontend now uploads browser-direct to
    Storage and submits via POST /jobs/upload-urls + /jobs/from-uploads,
    keeping large bodies off the Railway edge (where they were observed
    dying mid-transfer). This multipart handler stays only so a stale
    frontend bundle keeps working across the deploy window — remove it
    once the new flow validates live.

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

    # ── 2. Parse + gates (shared with POST /jobs/from-uploads) ─────────

    zip_data, quality_report, xlsx_data = _apply_submission_gates(
        client_id, archive_bytes, analytics_bytes, archive.filename
    )

    # ── 3. Mint the job row ────────────────────────────────────────────

    job_insert = (
        supabase.table("jobs")
        .insert(
            {
                "client_id": client_id,
                "status": "pending",
                # ORPHEUS-89: OIDC photo-presence signal captured at
                # submission. None = no signal; worker falls back to the
                # ZIP rich-media heuristic at scoring time.
                "oidc_photo_present": has_profile_photo,
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

    _persist_ingested_data(
        supabase, job_id, zip_data, xlsx_data, quality_report
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


# --------------------------------------------------------------------------- #
# Browser-direct upload flow (ORPHEUS-108)
# --------------------------------------------------------------------------- #
#
# The legacy multipart POST /jobs above routes the whole archive body through
# the Railway edge, where large uploads were observed dying mid-transfer
# before the handler ever ran (no POST line in the logs after a passing
# OPTIONS preflight; ORPHEUS-86). The fix is to keep the large body off the
# Railway edge entirely:
#
#   1. POST /jobs/upload-urls mints signed Supabase Storage upload URLs for a
#      staging path. Signed URLs mean no storage RLS migration — the backend
#      keeps sole authority over paths, and the token only permits a PUT to
#      the exact object it was minted for.
#   2. The browser uploads both files directly to Supabase Storage.
#   3. POST /jobs/from-uploads downloads the staged bytes server-side
#      (Railway ↔ Supabase, no edge), runs the same three gates, mints the
#      job row, and MOVES the objects to the {client_id}/{job_id}/ path the
#      worker already reads from — the worker is untouched.
#
# The multipart handler stays temporarily so a stale frontend bundle keeps
# working across the deploy window (the Railway auto-deploy quirk makes a
# hard cutover risky); remove it once the new flow validates live.


class UploadTarget(BaseModel):
    """One signed Supabase Storage upload slot: object path + upload token."""

    path: str
    token: str


class CreateUploadUrlsResponse(BaseModel):
    upload_id: str
    archive: UploadTarget
    analytics: UploadTarget


class CreateJobFromUploadsRequest(BaseModel):
    upload_id: str
    # Original browser-side filename of the archive. Feeds the ORPHEUS-101
    # filename gate (Basic_ prefix + export-date stamp), which the storage
    # object path can't carry — staged objects are always named archive.zip.
    archive_filename: str | None = None
    # ORPHEUS-89 OIDC photo-presence signal, same semantics as the
    # multipart form field.
    has_profile_photo: bool | None = None


@router.post(
    "/upload-urls",
    response_model=CreateUploadUrlsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_urls(
    roles: SessionRoles = Depends(get_current_session_roles),
) -> CreateUploadUrlsResponse:
    """Mint signed Storage upload URLs for a browser-direct submission.

    Runs the role gate and the concurrent-run guard up front so a client
    with a job already in flight is rejected before uploading anything —
    the whole point of this flow is not to waste a large transfer.
    """
    if not roles.is_client():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submitting a diagnostic requires a client profile.",
        )
    client_id = roles.client_id
    assert client_id is not None

    supabase = get_service_client()
    if _has_active_job(supabase, client_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You already have a report in progress. Please wait for "
                "it to finish before starting a new one."
            ),
        )

    upload_id = str(uuid.uuid4())
    prefix = _staging_prefix(client_id, upload_id)
    storage = supabase.storage.from_(_STORAGE_BUCKET)
    try:
        archive_signed = storage.create_signed_upload_url(
            f"{prefix}/{_ARCHIVE_FILENAME}"
        )
        analytics_signed = storage.create_signed_upload_url(
            f"{prefix}/{_ANALYTICS_FILENAME}"
        )
    except Exception as exc:
        logger.exception(
            "Signed upload URL mint failed for client %s: %s", client_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "We couldn't prepare your upload. This is usually "
                "transient — please try again in a moment."
            ),
        ) from exc

    logger.info(
        "Minted staging upload %s for client %s", upload_id, client_id
    )
    return CreateUploadUrlsResponse(
        upload_id=upload_id,
        archive=UploadTarget(
            path=archive_signed["path"], token=archive_signed["token"]
        ),
        analytics=UploadTarget(
            path=analytics_signed["path"], token=analytics_signed["token"]
        ),
    )


@router.post(
    "/from-uploads", response_model=Job, status_code=status.HTTP_201_CREATED
)
async def create_job_from_uploads(
    body: CreateJobFromUploadsRequest,
    roles: SessionRoles = Depends(get_current_session_roles),
) -> Job:
    """Create a job from files already staged in Storage by the browser.

    Mirrors the legacy multipart handler's pipeline — same gates, same job
    row, same worker path convention — but the request body is a small JSON
    document instead of the multi-hundred-MB multipart body, so the Railway
    edge never sees the archive.
    """
    if not roles.is_client():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submitting a diagnostic requires a client profile.",
        )
    client_id = roles.client_id
    assert client_id is not None

    # upload_id must be the UUID we minted — it's interpolated into storage
    # paths, so anything else is a path-traversal attempt.
    try:
        uuid.UUID(body.upload_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload id.",
        )

    supabase = get_service_client()
    if _has_active_job(supabase, client_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You already have a report in progress. Please wait for "
                "it to finish before starting a new one."
            ),
        )

    storage = supabase.storage.from_(_STORAGE_BUCKET)
    prefix = _staging_prefix(client_id, body.upload_id)

    # ── 1. Stat + size-check the staged objects ────────────────────────
    # The signed URL can't enforce a size cap, so re-check here before
    # pulling anything into memory. Missing objects mean the browser's
    # direct upload didn't finish.

    sizes = _stat_staged_objects(storage, prefix)
    for filename, max_bytes, label in (
        (_ARCHIVE_FILENAME, _MAX_ARCHIVE_BYTES, "archive"),
        (_ANALYTICS_FILENAME, _MAX_ANALYTICS_BYTES, "analytics"),
    ):
        if filename not in sizes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Your {label} upload didn't finish. Please try "
                    "submitting again."
                ),
            )
        size = sizes[filename]
        if size is not None and size > max_bytes:
            _remove_staged(storage, prefix)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Your {label} upload exceeds the "
                    f"{max_bytes // (1024 * 1024)} MB limit. "
                    "Please contact support if you have a larger archive."
                ),
            )

    # ── 2. Download server-side + run the gates ────────────────────────

    try:
        archive_bytes = storage.download(f"{prefix}/{_ARCHIVE_FILENAME}")
        analytics_bytes = storage.download(f"{prefix}/{_ANALYTICS_FILENAME}")
    except Exception as exc:
        logger.exception(
            "Staged download failed for client %s upload %s: %s",
            client_id,
            body.upload_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "We couldn't read your uploaded files. This is usually "
                "transient — please try again in a moment."
            ),
        ) from exc

    try:
        zip_data, quality_report, xlsx_data = _apply_submission_gates(
            client_id, archive_bytes, analytics_bytes, body.archive_filename
        )
    except HTTPException:
        # A rejected submission shouldn't leave a large orphan in staging.
        _remove_staged(storage, prefix)
        raise

    # ── 3. Mint the job row ────────────────────────────────────────────

    job_insert = (
        supabase.table("jobs")
        .insert(
            {
                "client_id": client_id,
                "status": "pending",
                "oidc_photo_present": body.has_profile_photo,
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
        "Created pending job %s for client %s (from upload %s)",
        job_id,
        client_id,
        body.upload_id,
    )

    # ── 4. Move staged objects to the worker's path ────────────────────

    try:
        storage.move(
            f"{prefix}/{_ARCHIVE_FILENAME}",
            f"{client_id}/{job_id}/{_ARCHIVE_FILENAME}",
        )
        storage.move(
            f"{prefix}/{_ANALYTICS_FILENAME}",
            f"{client_id}/{job_id}/{_ANALYTICS_FILENAME}",
        )
    except Exception as exc:
        logger.exception(
            "Storage move failed for job %s: %s", job_id, exc
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

    _persist_ingested_data(
        supabase, job_id, zip_data, xlsx_data, quality_report
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
        .select("id,status,created_at,data_limited")
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
            data_limited=bool(r.get("data_limited")),
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


def _apply_submission_gates(
    client_id: str,
    archive_bytes: bytes,
    analytics_bytes: bytes,
    archive_filename: str | None,
):
    """Parse both uploads and run the three submission gates.

    Shared by the legacy multipart POST /jobs and the browser-direct
    POST /jobs/from-uploads (ORPHEUS-108) so the two entry points can
    never drift on what constitutes an acceptable submission. Raises
    HTTPException (400/422) on rejection; returns
    ``(zip_data, quality_report, xlsx_data)`` on success.

    Gates, in order:
      * inline parse — malformed ZIP/XLSX → 400 (fail fast, don't let the
        worker discover it later);
      * 2a filename (ORPHEUS-101) — a ``Basic_`` archive filename rejects
        immediately; the filename's date is the primary recency signal;
      * 2b quality (ORPHEUS-88) — CRITICAL+MISSING_FILE blocks (Basic or
        corrupt archive); an EMPTY_DATA critical from a genuinely inactive
        member passes through as a valid low-signal report;
      * 2c freshness (ORPHEUS-100) — export older than
        ``_STALE_ARCHIVE_DAYS`` rejects, filename date first, analytics
        XLSX date as fallback (the ZIP's activity dates would
        false-positive on inactive members; ORPHEUS-91).
    """
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

    # ── 2a. Filename signals (ORPHEUS-101) ─────────────────────────────

    archive_type, filename_date = parse_archive_filename(archive_filename)

    basic_archive_detail = (
        "This looks like LinkedIn's Basic data export — it leaves out your "
        "posts, comments, and reactions, which we need to measure your "
        "activity. Please request the Complete archive instead: "
        "Settings → Data privacy → Get a copy of your data → "
        "“Download larger data archive” (the option that can take up to 24 "
        "hours). Upload that ZIP once it arrives."
    )

    if archive_type == "basic":
        logger.info(
            "Rejected job for client %s at filename gate: Basic archive "
            "(%s)",
            client_id,
            archive_filename,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=basic_archive_detail,
        )

    # ── 2b. Quality gate (ORPHEUS-88) ──────────────────────────────────

    if quality_report.has_blocking_issue:
        blocking_sources = {i.source for i in quality_report.blocking_issues()}
        if "Shares.csv" in blocking_sources:
            detail = basic_archive_detail
        else:
            detail = (
                "Your archive is missing core profile data, so we can't "
                "score it. Please re-download the Complete archive from "
                "Settings → Data privacy → Get a copy of your data "
                "→ “Download larger data archive” and upload "
                "the unmodified ZIP."
            )
        logger.info(
            "Rejected job for client %s at quality gate: %s",
            client_id,
            quality_report.summary(),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        )

    # ── 2c. Freshness gate (ORPHEUS-100 + ORPHEUS-101) ─────────────────

    export_date = filename_date or latest_analytics_date(xlsx_data)
    if export_date is not None:
        age_days = (datetime.now(timezone.utc).date() - export_date).days
        if age_days > _STALE_ARCHIVE_DAYS:
            logger.info(
                "Rejected job for client %s at freshness gate: analytics "
                "ends %s (%d days old)",
                client_id,
                export_date.isoformat(),
                age_days,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "This export looks out of date — its most recent data is "
                    f"from {export_date.strftime('%B %-d, %Y')}, more than two "
                    "weeks ago. Please download fresh copies of both files "
                    "from LinkedIn and upload those so your report reflects "
                    "your current activity."
                ),
            )

    return zip_data, quality_report, xlsx_data


def _staging_prefix(client_id: str, upload_id: str) -> str:
    """Storage prefix for a browser-direct staging upload (ORPHEUS-108).

    Lives under the client's own folder but in a `staging/` segment so it
    can never collide with a `{client_id}/{job_id}/` worker path (job ids
    are UUIDs, never the literal "staging").
    """
    return f"{client_id}/staging/{upload_id}"


def _stat_staged_objects(storage, prefix: str) -> dict[str, int | None]:
    """Map staged object basename → size in bytes (None if unreported).

    Uses the storage list API on the staging prefix. Any listing failure
    returns {} — the caller treats missing entries as "upload didn't
    finish", which is the right user-facing message for that case too.
    """
    try:
        entries = storage.list(prefix) or []
    except Exception as exc:
        logger.warning(
            "Staged-object listing failed for %s: %s", prefix, exc
        )
        return {}
    sizes: dict[str, int | None] = {}
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not name:
            continue
        metadata = entry.get("metadata") or {}
        size = metadata.get("size") if isinstance(metadata, dict) else None
        sizes[name] = size if isinstance(size, int) else None
    return sizes


def _remove_staged(storage, prefix: str) -> None:
    """Best-effort cleanup of a staging upload after a rejection.

    Never raises — the rejection response matters more than the orphan.
    Abandoned staging uploads (browser uploaded, /from-uploads never
    called) are not cleaned here; a periodic sweep is a follow-up if the
    bucket ever accumulates enough to matter.
    """
    try:
        storage.remove(
            [
                f"{prefix}/{_ARCHIVE_FILENAME}",
                f"{prefix}/{_ANALYTICS_FILENAME}",
            ]
        )
    except Exception as exc:
        logger.warning(
            "Staged-object cleanup failed for %s: %s", prefix, exc
        )


def _persist_ingested_data(
    supabase, job_id: str, zip_data, xlsx_data, quality_report
) -> None:
    """Upsert the parsed JSONB + quality report into ingested_data.

    Best-effort: if the insert fails (e.g. table missing on a partial
    local-dev schema), the worker's stage_ingestion re-parses from storage
    on its first run, so the job can still complete. We log loudly but
    don't fail the request — the user has successfully submitted and will
    see real progress on the Analysis screen.
    """
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
        logger.exception(
            "Persisting ingested_data for job %s failed (worker will "
            "re-parse from storage): %s",
            job_id,
            exc,
        )


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
        # ORPHEUS-88: data-limited notice for the client report banner.
        # Read from the stored quality_report on this single-job path (one
        # extra read is fine here; the list/roster surfaces use the cheap
        # denormalized jobs.data_limited flag instead). Absent/unparseable
        # → data_limited: false with no notices (graceful, never 500s).
        "quality": _build_quality_summary(supabase, job_id),
    }


def _build_quality_summary(supabase, job_id: str) -> dict:
    """Summarize a completed job's data-quality report for the client banner.

    Returns `{data_limited: bool, notices: list[str]}`. Reads the stored
    ingested_data.quality_report JSONB and reuses the DataQualityReport
    classification helpers so the banner and the denormalized
    jobs.data_limited flag can never disagree on the definition. Any
    failure (missing row, unparseable JSONB) degrades to not-limited —
    the report still renders; we just don't show the banner.
    """
    default = {"data_limited": False, "notices": []}
    try:
        row = (
            supabase.table("ingested_data")
            .select("quality_report")
            .eq("job_id", job_id)
            .limit(1)
            .execute()
        )
        if not row.data:
            return default
        raw = row.data[0].get("quality_report")
        if not raw:
            return default
        report = DataQualityReport.model_validate(raw)
        return {
            "data_limited": report.is_data_limited,
            "notices": report.data_limitation_notices(),
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Job %s quality_report summary failed (%s); "
            "serving no banner.",
            job_id,
            exc,
        )
        return default
