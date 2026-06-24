"""Admin API — email-allowlisted stopgap surface (ORPHEUS-31).

The endpoints here are deliberately minimal and supersedeable. They
exist so an admin (Andrew, Josh, Tim — whoever appears in
`ADMIN_EMAILS`) can inspect any client's data and tweak narrative
text before the proper advisor surface in /advisor/clients catches
up to whatever the practice actually needs.

Three routes:

  * `GET /admin/clients` — every `clients` row in the system, joined
    with its owning advisor's display info and its single most-recent
    job. Distinct from `GET /clients` (advisor-scoped to the caller's
    own clients via `advisor_id`); this surface is god-mode.

  * `GET /admin/jobs` — every `jobs` row, optional `?client_id=` filter
    to narrow to one client. Each job carries enough narrative
    metadata to drive the editor's section picker without a second
    round trip.

  * `GET /admin/narratives/{narrative_id}` — full text of one
    narrative row (generated + edited).
  * `PATCH /admin/narratives/{narrative_id}` — update `edited_text`
    and / or `status` on a narrative row.

Every endpoint depends on `get_current_admin` (backend/auth.py) and
uses the service-role Supabase client (RLS bypassed intentionally —
the whole point of the admin surface is to see across tenants).

Will be superseded by the separate advisor-auth decision; the
codebase pattern lets that future work replace `/admin` entirely
without orphaned helpers (no shared dependency surface beyond the
generic auth + db modules).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.auth import SessionRoles, get_current_admin
from backend.config import get_settings
from backend.db import get_service_client
from backend.email.resend_client import (
    EmailSendError,
    send_report_ready_email,
)

logger = logging.getLogger("orpheus.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


# --------------------------------------------------------------------------- #
# Shared response models
# --------------------------------------------------------------------------- #

class AdminAdvisorSummary(BaseModel):
    """Just enough advisor identity to label a clients row in the list view.

    `practice_name` falls back to None when the advisor row has no
    practice_name set; the UI then shows the advisor email as a label.
    """

    id: str
    practice_name: str | None
    email: str | None


class AdminJobSummary(BaseModel):
    """One job's id + status, used in the clients list."""

    id: str
    status: str
    created_at: str | None


class AdminClient(BaseModel):
    """One row of `GET /admin/clients`.

    `advisor` is the owning advisor's summary; `latest_job` is null when
    the client has never had a job kicked off.
    """

    id: str
    display_name: str
    email: str
    invitation_status: str
    created_at: str | None
    user_id: str | None
    advisor: AdminAdvisorSummary | None
    latest_job: AdminJobSummary | None


class ListAdminClientsResponse(BaseModel):
    """Body of `GET /admin/clients`."""

    clients: list[AdminClient]


class AdminNarrativeMeta(BaseModel):
    """Compact narrative description nested under a job in the jobs list.

    Carries enough for the editor's section picker (which sections
    exist, what state they're in, whether an edit has been saved)
    without paying for the full text on the list response.
    """

    id: str
    section: str
    status: str
    has_edited_text: bool
    published_at: str | None
    generated_at: str | None


class AdminJob(BaseModel):
    """One row of `GET /admin/jobs`."""

    id: str
    client_id: str
    client_display_name: str | None
    client_email: str | None
    status: str
    version_label: str | None
    created_at: str | None
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    narratives: list[AdminNarrativeMeta]


class ListAdminJobsResponse(BaseModel):
    """Body of `GET /admin/jobs`."""

    jobs: list[AdminJob]


class AdminNarrative(BaseModel):
    """Body of `GET /admin/narratives/{id}` and `PATCH /admin/narratives/{id}`.

    Full narrative payload — generated text alongside the editable
    fields. `edited_text` and `status` are the only fields the PATCH
    handler accepts.
    """

    id: str
    job_id: str
    section: str
    generated_text: str
    edited_text: str | None
    status: str
    published_at: str | None
    generated_at: str | None


class UpdateAdminNarrativeRequest(BaseModel):
    """Body for `PATCH /admin/narratives/{id}`.

    Both fields are optional so the editor can save either independently
    (typo fix without re-publishing, status flip without text change).
    Pydantic's default `model_dump(exclude_unset=True)` lets the handler
    distinguish "field omitted" from "field set to None" — the former
    is a no-op, the latter explicitly clears `edited_text`.
    """

    edited_text: str | None = Field(default=None, max_length=200_000)
    status: str | None = Field(default=None)


# --------------------------------------------------------------------------- #
# GET /admin/clients — list every client row across all advisors
# --------------------------------------------------------------------------- #

@router.get("/clients", response_model=ListAdminClientsResponse)
async def list_admin_clients(
    _admin: Annotated[SessionRoles, Depends(get_current_admin)],
) -> ListAdminClientsResponse:
    """Return every clients row in the system, with advisor + latest-job info.

    Three round trips — same shape as `GET /clients` plus an advisors
    lookup:

      1. SELECT all clients ordered by created_at desc.
      2. SELECT all jobs whose client_id is in the step-1 set, ordered
         desc. Bucket in Python; first hit per client_id is the most
         recent.
      3. SELECT advisor rows whose id is in the unique-advisor set
         from step 1, build a dict by id.

    Service-role throughout — RLS bypassed intentionally; the route is
    gated upstream by `get_current_admin`'s email-allowlist check.

    No pagination yet: at beta scale ("Andrew + a handful of
    early-access clients") returning everything in one shot is the
    right call. If the client count crosses ~500 we'll want to layer
    in a `limit` / `offset` or keyset pagination, but that's a follow-
    up beyond ORPHEUS-31's stopgap scope.
    """
    supabase = get_service_client()

    # ── 1. Pull all clients rows ───────────────────────────────────────

    clients_result = (
        supabase.table("clients")
        .select(
            "id, display_name, email, invitation_status, "
            "advisor_id, user_id, created_at"
        )
        .order("created_at", desc=True)
        .execute()
    )
    rows = clients_result.data or []

    # ── 2. Bucket the most-recent job per client_id ────────────────────

    latest_by_client: dict[str, dict[str, Any]] = {}
    if rows:
        client_ids = [str(r["id"]) for r in rows]
        jobs_result = (
            supabase.table("jobs")
            .select("id, client_id, status, created_at")
            .in_("client_id", client_ids)
            .order("created_at", desc=True)
            .execute()
        )
        for job in jobs_result.data or []:
            cid = str(job["client_id"])
            if cid not in latest_by_client:
                latest_by_client[cid] = job

    # ── 3. Resolve owning advisors ─────────────────────────────────────

    advisor_ids = sorted(
        {str(r["advisor_id"]) for r in rows if r.get("advisor_id")}
    )
    advisor_by_id: dict[str, dict[str, Any]] = {}
    if advisor_ids:
        advisors_result = (
            supabase.table("advisors")
            .select("id, user_id, practice_name")
            .in_("id", advisor_ids)
            .execute()
        )
        for adv in advisors_result.data or []:
            advisor_by_id[str(adv["id"])] = adv

    # ── 3a. Resolve advisor emails from auth.users ─────────────────────
    # `public.advisors` doesn't carry email — identity lives on
    # `auth.users` (set by the LinkedIn OIDC provider on signup). The
    # admin label-fallback path documented on AdminAdvisorSummary
    # requires this join. List-all is fine at beta scale (~5-50
    # advisors); revisit if we ever cross a few hundred. Best-effort:
    # if the admin API isn't usable for any reason we degrade to
    # email=None and let practice_name carry the label.
    advisor_email_by_user_id = _resolve_advisor_emails(
        supabase, list(advisor_by_id.values())
    )

    # ── 4. Assemble the response ───────────────────────────────────────

    items: list[AdminClient] = []
    for row in rows:
        row_id = str(row["id"])
        advisor_id = (
            str(row["advisor_id"]) if row.get("advisor_id") else None
        )
        adv_row = advisor_by_id.get(advisor_id) if advisor_id else None
        adv_email: str | None = None
        if adv_row and adv_row.get("user_id"):
            adv_email = advisor_email_by_user_id.get(
                str(adv_row["user_id"])
            )
        latest = latest_by_client.get(row_id)
        items.append(
            AdminClient(
                id=row_id,
                display_name=row["display_name"],
                email=row["email"],
                invitation_status=row["invitation_status"],
                created_at=_iso_or_none(row.get("created_at")),
                user_id=(
                    str(row["user_id"]) if row.get("user_id") else None
                ),
                advisor=(
                    AdminAdvisorSummary(
                        id=str(adv_row["id"]),
                        practice_name=adv_row.get("practice_name"),
                        email=adv_email,
                    )
                    if adv_row is not None
                    else None
                ),
                latest_job=(
                    AdminJobSummary(
                        id=str(latest["id"]),
                        status=latest["status"],
                        created_at=_iso_or_none(latest.get("created_at")),
                    )
                    if latest is not None
                    else None
                ),
            )
        )

    return ListAdminClientsResponse(clients=items)


# --------------------------------------------------------------------------- #
# GET /admin/jobs — every job row, with narrative metadata nested
# --------------------------------------------------------------------------- #

@router.get("/jobs", response_model=ListAdminJobsResponse)
async def list_admin_jobs(
    _admin: Annotated[SessionRoles, Depends(get_current_admin)],
    client_id: Annotated[
        str | None,
        Query(description="Optional client_id filter — return only this client's jobs."),
    ] = None,
) -> ListAdminJobsResponse:
    """Return jobs across the system, optionally filtered to one client.

    Three round trips:

      1. SELECT jobs (optionally filtered by `client_id`) ordered by
         created_at desc.
      2. SELECT clients in the step-1 client_id set, dict by id, so
         the response can label each job with the client display name
         + email without an N+1.
      3. SELECT narratives whose job_id is in the step-1 set; group
         by job_id in Python.

    The narratives query pulls metadata only (no `generated_text`,
    no `edited_text`) so the response payload stays small. Editor
    loads the full text via `GET /admin/narratives/{id}` on demand.

    `has_edited_text` is True when the row's `edited_text` is non-NULL
    and non-empty after strip — gives the UI a fast "edited" badge
    without shipping the entire text just to check.
    """
    supabase = get_service_client()

    # ── 1. Pull jobs (optional client_id filter) ───────────────────────

    jobs_query = supabase.table("jobs").select(
        "id, client_id, status, version_label, created_at, "
        "started_at, completed_at, error_message"
    )
    if client_id:
        jobs_query = jobs_query.eq("client_id", client_id)
    jobs_result = jobs_query.order("created_at", desc=True).execute()
    job_rows = jobs_result.data or []

    if not job_rows:
        return ListAdminJobsResponse(jobs=[])

    job_ids = [str(j["id"]) for j in job_rows]
    client_ids = sorted({str(j["client_id"]) for j in job_rows})

    # ── 2. Pull owning client identity (for label fields) ──────────────

    client_by_id: dict[str, dict[str, Any]] = {}
    if client_ids:
        clients_result = (
            supabase.table("clients")
            .select("id, display_name, email")
            .in_("id", client_ids)
            .execute()
        )
        for c in clients_result.data or []:
            client_by_id[str(c["id"])] = c

    # ── 3. Pull narrative metadata for those jobs ──────────────────────

    narratives_by_job: dict[str, list[AdminNarrativeMeta]] = {}
    narratives_result = (
        supabase.table("narratives")
        .select(
            "id, job_id, section, status, edited_text, "
            "published_at, generated_at"
        )
        .in_("job_id", job_ids)
        .order("generated_at", desc=False)
        .execute()
    )
    for n in narratives_result.data or []:
        jid = str(n["job_id"])
        edited = n.get("edited_text")
        meta = AdminNarrativeMeta(
            id=str(n["id"]),
            section=n["section"],
            status=n.get("status") or "draft",
            has_edited_text=bool(
                isinstance(edited, str) and edited.strip()
            ),
            published_at=_iso_or_none(n.get("published_at")),
            generated_at=_iso_or_none(n.get("generated_at")),
        )
        narratives_by_job.setdefault(jid, []).append(meta)

    # ── 4. Assemble response ───────────────────────────────────────────

    items: list[AdminJob] = []
    for j in job_rows:
        jid = str(j["id"])
        cid = str(j["client_id"])
        c_row = client_by_id.get(cid)
        items.append(
            AdminJob(
                id=jid,
                client_id=cid,
                client_display_name=(
                    c_row.get("display_name") if c_row else None
                ),
                client_email=c_row.get("email") if c_row else None,
                status=j["status"],
                version_label=j.get("version_label"),
                created_at=_iso_or_none(j.get("created_at")),
                started_at=_iso_or_none(j.get("started_at")),
                completed_at=_iso_or_none(j.get("completed_at")),
                error_message=j.get("error_message"),
                narratives=narratives_by_job.get(jid, []),
            )
        )

    return ListAdminJobsResponse(jobs=items)


# --------------------------------------------------------------------------- #
# GET /admin/narratives/{id} — full text of one narrative row
# --------------------------------------------------------------------------- #

@router.get("/narratives/{narrative_id}", response_model=AdminNarrative)
async def get_admin_narrative(
    narrative_id: str,
    _admin: Annotated[SessionRoles, Depends(get_current_admin)],
) -> AdminNarrative:
    """Read a single narrative row by PK.

    Returns the full generated + edited text so the editor can
    populate its textareas. 404 when the row doesn't exist (admin
    surface; no caller-scoping to dodge around).
    """
    supabase = get_service_client()

    result = (
        supabase.table("narratives")
        .select("*")
        .eq("id", narrative_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Narrative {narrative_id!r} not found.",
        )

    return _narrative_from_row(result.data[0])


# --------------------------------------------------------------------------- #
# PATCH /admin/narratives/{id} — update edited_text and / or status
# --------------------------------------------------------------------------- #

@router.patch("/narratives/{narrative_id}", response_model=AdminNarrative)
async def update_admin_narrative(
    narrative_id: str,
    request: UpdateAdminNarrativeRequest,
    _admin: Annotated[SessionRoles, Depends(get_current_admin)],
) -> AdminNarrative:
    """Update a narrative's `edited_text` and / or `status`.

    Body fields are independently optional. The handler distinguishes
    "field omitted" (leave the column alone) from "field set to null"
    (explicitly clear `edited_text`) via Pydantic's `exclude_unset`.

    `status` is validated against the `narrative_status` enum
    ('draft' / 'published') in code rather than relying on a DB-level
    constraint violation to surface — clearer error message.

    Empty bodies (no fields set) return the existing row unchanged
    rather than 400. The editor's save-on-blur flow can fire a PATCH
    with nothing changed if the user clicked away without editing;
    no-oping is friendlier than the alternative.
    """
    supabase = get_service_client()

    update_fields: dict[str, Any] = request.model_dump(exclude_unset=True)

    if "status" in update_fields:
        new_status = update_fields["status"]
        if new_status not in ("draft", "published"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid status. Must be 'draft' or 'published'."
                ),
            )

    # Existence check — same 404 path as GET so the admin can't update
    # a phantom row and get back a confusing empty response.
    existing = (
        supabase.table("narratives")
        .select("id")
        .eq("id", narrative_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Narrative {narrative_id!r} not found.",
        )

    # No-op if nothing to update — return the current row.
    if not update_fields:
        current = (
            supabase.table("narratives")
            .select("*")
            .eq("id", narrative_id)
            .limit(1)
            .execute()
        )
        return _narrative_from_row(current.data[0])

    update_result = (
        supabase.table("narratives")
        .update(update_fields)
        .eq("id", narrative_id)
        .execute()
    )
    if not update_result.data:
        logger.error(
            "Failed to update narrative %s (empty result.data)",
            narrative_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update narrative.",
        )

    logger.info(
        "Admin narrative update: id=%s fields=%s",
        narrative_id,
        sorted(update_fields.keys()),
    )

    # ORPHEUS-98: when a status flip publishes the *last* draft narrative
    # for a job, the report just became viewable by the client — fire the
    # report-ready email. Best-effort; never affects the PATCH response.
    if update_fields.get("status") == "published":
        _maybe_send_report_ready_on_publish(
            supabase, update_result.data[0]
        )

    return _narrative_from_row(update_result.data[0])


# --------------------------------------------------------------------------- #
# Report-ready email on advisory publication (ORPHEUS-98)
# --------------------------------------------------------------------------- #

def _maybe_send_report_ready_on_publish(supabase, narrative_row: dict[str, Any]) -> None:
    """Send the report-ready email when an advisory report becomes viewable.

    The only publish mechanism today is per-narrative status flips through
    this admin editor, so "the report is ready" is the moment the *last*
    draft narrative for the job flips to published. We detect that by
    checking that no `draft` narratives remain for the job.

    Idempotency + "first report only" both ride `reports.published_at`:

      * It's NULL for advisory reports until we set it here, so a NULL
        value means "not yet announced" — we set it and send.
      * It's already set by the worker for self-serve reports (whose
        narratives are never draft), so this path no-ops for them — no
        double-send with the worker's completion email.
      * A returning client whose earlier report already has a non-NULL
        published_at still gets THIS report's published_at stamped, but
        the email is suppressed — the feedback ask is once per client.

    Never raises: any failure is logged and swallowed. The publish itself
    has already succeeded and is the caller's actual job.
    """
    job_id = narrative_row.get("job_id")
    if not job_id:
        return

    try:
        # Are any drafts left for this job? If so, the report isn't fully
        # published — wait for the last one.
        remaining_drafts = (
            supabase.table("narratives")
            .select("id", count="exact")
            .eq("job_id", job_id)
            .eq("status", "draft")
            .execute()
        )
        draft_count = getattr(remaining_drafts, "count", None)
        if draft_count is None:
            draft_count = len(remaining_drafts.data or [])
        if draft_count > 0:
            return

        # Find the report row for this job.
        report_result = (
            supabase.table("reports")
            .select("client_id, published_at")
            .eq("job_id", job_id)
            .limit(1)
            .execute()
        )
        if not report_result.data:
            logger.warning(
                "[%s] Report-ready email skipped — no reports row", job_id
            )
            return
        report = report_result.data[0]

        # Dedup: already announced → nothing to do.
        if report.get("published_at"):
            return

        client_id = report["client_id"]

        # Is this the client's first report to reach published? Look for any
        # OTHER report of theirs already stamped.
        prior = (
            supabase.table("reports")
            .select("job_id, published_at")
            .eq("client_id", client_id)
            .not_.is_("published_at", "null")
            .limit(1)
            .execute()
        )
        is_first_published = not prior.data

        now = datetime.utcnow().isoformat()

        # Stamp published_at regardless, so re-saves don't re-trigger.
        supabase.table("reports").update(
            {"published_at": now}
        ).eq("job_id", job_id).execute()

        if not is_first_published:
            logger.info(
                "[%s] Report-ready email suppressed — not the client's "
                "first published report (published_at stamped)",
                job_id,
            )
            return

        # Resolve recipient from the clients row.
        client_result = (
            supabase.table("clients")
            .select("email, display_name")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )
        if not client_result.data:
            logger.warning(
                "[%s] Report-ready email skipped — clients row %s missing",
                job_id,
                client_id,
            )
            return
        client_row = client_result.data[0]

        to_email = client_row.get("email")
        if not to_email:
            logger.warning(
                "[%s] Report-ready email skipped — no email on clients row",
                job_id,
            )
            return
        client_name = client_row.get("display_name") or to_email.split("@")[0]

        settings = get_settings()
        app_base_url = settings.app_base_url.rstrip("/")
        report_url = f"{app_base_url}/reports"
        survey_url = settings.beta_survey_url or None

        message_id = send_report_ready_email(
            to_email=to_email,
            client_name=client_name,
            report_url=report_url,
            survey_url=survey_url,
        )
        logger.info(
            "[%s] Report-ready email sent to %s (resend id=%s, survey=%s)",
            job_id,
            to_email,
            message_id,
            "yes" if survey_url else "no",
        )
    except EmailSendError as e:
        logger.warning("[%s] Report-ready email send failed: %s", job_id, e)
    except Exception as e:  # noqa: BLE001 — must never break the publish
        logger.warning(
            "[%s] Report-ready email skipped on unexpected error: %s",
            job_id,
            e,
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _iso_or_none(value: Any) -> str | None:
    """Return the value as a string when truthy, else None.

    Supabase already serializes timestamptz columns as ISO strings;
    this is just a safe pass-through that copes with NULL rows
    (None on read) without raising on `.isoformat()` of None.
    """
    if value is None:
        return None
    return str(value)


def _resolve_advisor_emails(
    supabase, advisor_rows: list[dict[str, Any]]
) -> dict[str, str]:
    """Build a `user_id -> email` map for the given advisor rows.

    `public.advisors` doesn't store email — the identity lives on
    `auth.users`, populated by the LinkedIn OIDC provider on first
    sign-in. We use the service-role auth admin API to list users and
    filter to the user_ids we actually need.

    Returns `{}` if no lookup is needed or if the admin API isn't
    usable (older supabase-py, transient network failure, etc.). The
    email field on AdminAdvisorSummary is a UI label fallback, not
    essential data — degrading to None is fine.

    The shape of `supabase.auth.admin.list_users()` varies across
    supabase-py versions (some return a list directly; some wrap in a
    `ListUsersResponse` with a `.users` field; either way each user
    exposes `id` and `email`). We handle both.
    """
    wanted_user_ids = {
        str(adv["user_id"])
        for adv in advisor_rows
        if adv.get("user_id")
    }
    if not wanted_user_ids:
        return {}

    try:
        users_response = supabase.auth.admin.list_users()
    except Exception:
        logger.exception("auth.admin.list_users failed; advisor emails will be None")
        return {}

    users_iter = (
        users_response
        if isinstance(users_response, list)
        else getattr(users_response, "users", None) or []
    )

    email_by_user_id: dict[str, str] = {}
    for user in users_iter:
        uid = getattr(user, "id", None)
        email = getattr(user, "email", None)
        if uid is None and isinstance(user, dict):
            uid = user.get("id")
            email = user.get("email")
        if uid and email and str(uid) in wanted_user_ids:
            email_by_user_id[str(uid)] = email
    return email_by_user_id


def _narrative_from_row(row: dict[str, Any]) -> AdminNarrative:
    """Build the AdminNarrative response from a raw `narratives` row.

    Centralizes the column-to-field mapping so the GET and PATCH
    handlers don't drift apart. `generated_text` is required by the
    schema (NOT NULL); if a row ever surfaces with it missing we
    default to empty string rather than 500 the admin out — the
    editor can show "[missing]" and the admin can investigate.
    """
    return AdminNarrative(
        id=str(row["id"]),
        job_id=str(row["job_id"]),
        section=row["section"],
        generated_text=row.get("generated_text") or "",
        edited_text=row.get("edited_text"),
        status=row.get("status") or "draft",
        published_at=_iso_or_none(row.get("published_at")),
        generated_at=_iso_or_none(row.get("generated_at")),
    )
