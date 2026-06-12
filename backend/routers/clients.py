"""Clients API — advisor-managed invitation flow (ORPHEUS-38, ORPHEUS-39).

This file grew across the ORPHEUS-38 + ORPHEUS-39 chain:

  ORPHEUS-38 commit #4: POST /clients/invite — advisor issues an
    invitation. Creates a pending `clients` row + sends the email.

  ORPHEUS-38 commit #5: POST /accept-invitation — token holder
    accepts. NOT in this router (different prefix, different auth
    dependency).

  ORPHEUS-38 commit #6: POST /clients/{id}/resend-invitation —
    advisor rotates the token and re-sends the email.

  ORPHEUS-39: GET /clients — list this advisor's clients, with each
    row's most-recent job's id+status. Backs the new
    /advisor/clients admin page.

The "/clients" prefix means all routes here are
`<METHOD> /clients[/<something>]`. The accept endpoint is intentionally
outside this prefix because its caller has no clients row yet — the
acceptance IS the linkage step.

Auth posture: every endpoint in this router depends on
`get_current_session_roles` (raises 401 on neither-role) and gates
itself on `roles.is_advisor()` with a 403 when missing. Routes that
need to serve neither-role users use `get_verified_session` instead
and don't live here.

Email handling: addresses are normalized via `.strip().lower()` before
both the duplicate-check and the INSERT. The invitation_status enum
expects 'pending' / 'accepted' / 'expired' (defined in migration 001).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.auth import (
    SessionRoles,
    get_current_session_roles,
    get_verified_session,
)
from backend.config import get_settings
from backend.db import get_service_client
from backend.email.resend_client import EmailSendError, send_invitation_email

logger = logging.getLogger("orpheus.clients")

# Two routers in this module:
#   * `router` with prefix="/clients" hosts the advisor-owned routes
#     (POST /clients/invite, POST /clients/{id}/resend-invitation).
#   * `accept_router` has no prefix and hosts POST /accept-invitation —
#     it sits outside the clients namespace because the caller has no
#     clients row yet (the acceptance IS the linkage step). Both are
#     registered separately in backend.main.
router = APIRouter(prefix="/clients", tags=["clients"])
accept_router = APIRouter(tags=["clients"])


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #

class InviteClientRequest(BaseModel):
    """Body for POST /clients/invite.

    `display_name` is the advisor's free-text label for the client —
    used in the admin UI list view. `email` is where the invitation
    link is sent; we normalize via `.strip().lower()` before any
    storage or comparison so trailing-space typos and case quirks
    don't surface as ghost rows or duplicate-but-not-quite failures.
    """

    display_name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=320)

    @field_validator("display_name")
    @classmethod
    def _trim_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("display_name must not be blank")
        return trimmed

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        # Lightweight check — we'd rather rely on Resend's delivery
        # feedback than a strict regex. But an `@` and a `.` after it
        # rules out obviously-malformed inputs.
        normalized = value.strip().lower()
        at = normalized.find("@")
        if at < 1 or "." not in normalized[at + 1:]:
            raise ValueError(f"email does not look valid: {value!r}")
        return normalized


class InviteClientResponse(BaseModel):
    """Response from POST /clients/invite — just the new clients.id."""

    client_id: str


class JobSummary(BaseModel):
    """A single client's most-recent job — id + state — for the list view.

    Compact shape because the admin list doesn't need the full Job
    payload (no result, no error). The frontend renders a status chip
    from `status` and links to `/jobs/{id}` on accepted-with-job rows.
    """

    id: str
    status: str


class ClientListItem(BaseModel):
    """One row in the advisor's client list response.

    `is_self=True` flags the advisor's self-clients row (where
    `clients.user_id == advisors.user_id` for this advisor). Lets the
    UI suppress the "Run my own report" button and render the row
    with a "You" affordance without an extra round trip.

    `latest_job` is null when this client has never had a job kicked
    off; otherwise it's the most recent (created_at desc) regardless
    of state — pending, running, complete, or failed.
    """

    id: str
    display_name: str
    email: str
    invitation_status: str
    is_self: bool
    latest_job: JobSummary | None


class ListClientsResponse(BaseModel):
    """Body of GET /clients."""

    clients: list[ClientListItem]


# --------------------------------------------------------------------------- #
# GET /clients — admin list view (ORPHEUS-39)
# --------------------------------------------------------------------------- #

@router.get("", response_model=ListClientsResponse)
async def list_clients(
    roles: Annotated[SessionRoles, Depends(get_current_session_roles)],
) -> ListClientsResponse:
    """List every `clients` row owned by the calling advisor.

    Two round trips:

      1. SELECT id, display_name, email, invitation_status, user_id
         FROM clients WHERE advisor_id = roles.advisor_id
         ORDER BY created_at DESC.

      2. SELECT id, client_id, status FROM jobs
         WHERE client_id IN (<step 1 ids>) ORDER BY created_at DESC.
         Bucket in Python — first hit per client_id wins.

    A two-query approach beats an N+1-per-client lookup at any list
    size and beats a JOIN at small list sizes (no DISTINCT ON gymnastics
    against supabase-py's chainable builder). It does pull every job
    for every client into memory; the worst case for a single advisor
    is hundreds of rows, well below anything that hurts the dyno.

    Service-role client because the admin endpoint is the system-of-
    record view; advisors see all their own clients regardless of
    user RLS context. The handler-side `is_advisor()` guard plus
    the `advisor_id = roles.advisor_id` filter on the clients query
    enforces ownership.

    Sort order: newest-first by created_at — matches what an advisor
    cares about (new invitations, recent activity).
    """
    if not roles.is_advisor():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Listing clients requires an advisor profile.",
        )
    advisor_id = roles.advisor_id
    assert advisor_id is not None  # narrowed by is_advisor() guard above

    supabase = get_service_client()

    # ── 1. Pull the clients rows ────────────────────────────────────────

    clients_result = (
        supabase.table("clients")
        .select("id, display_name, email, invitation_status, user_id, created_at")
        .eq("advisor_id", advisor_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = clients_result.data or []

    # ── 2. Pull jobs for those clients (single query, bucket in Python) ─

    latest_by_client: dict[str, dict] = {}
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
            # First hit wins — query is ordered desc, so this is most recent.
            if cid not in latest_by_client:
                latest_by_client[cid] = job

    # ── 3. Assemble the response ────────────────────────────────────────

    items: list[ClientListItem] = []
    for row in rows:
        row_id = str(row["id"])
        latest = latest_by_client.get(row_id)
        items.append(
            ClientListItem(
                id=row_id,
                display_name=row["display_name"],
                email=row["email"],
                invitation_status=row["invitation_status"],
                is_self=(row.get("user_id") == roles.user_id),
                latest_job=(
                    JobSummary(id=str(latest["id"]), status=latest["status"])
                    if latest is not None
                    else None
                ),
            )
        )

    return ListClientsResponse(clients=items)


# --------------------------------------------------------------------------- #
# POST /clients/invite — issue a new invitation (ORPHEUS-38)
# --------------------------------------------------------------------------- #

@router.post(
    "/invite",
    response_model=InviteClientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_client(
    request: InviteClientRequest,
    roles: Annotated[SessionRoles, Depends(get_current_session_roles)],
) -> InviteClientResponse:
    """Create a pending `clients` row and email the invitation link.

    Flow:

      1. Reject non-advisor callers with 403. (The 401 case never
         reaches here — `get_current_session_roles` raises before
         this handler runs.)
      2. Look up the advisor's display-name. Prefer `practice_name`
         from the advisors row; fall back to the advisor's own email
         from the JWT.
      3. 409 pre-check: refuse to create a second `clients` row for
         the same (advisor_id, lowercased email). Prevents ghost rows
         from an advisor retrying the form.
      4. Mint a fresh `invitation_token` (uuid4) and an
         `invitation_expires_at` = now + N days (N from settings).
      5. INSERT the new row with `invitation_status='pending'` and
         `user_id=NULL`.
      6. Send the email via Resend. If the send fails, the row
         persists — the advisor can recover via the resend endpoint
         (commit #6). The 502 detail tells them so.

    Returns the new client_id. Status 201 because we minted a resource.
    """

    if not roles.is_advisor():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inviting clients requires an advisor profile.",
        )
    advisor_id = roles.advisor_id
    assert advisor_id is not None  # narrowed by is_advisor() guard above

    settings = get_settings()
    supabase = get_service_client()

    email = request.email  # already normalized by the validator
    display_name = request.display_name  # already trimmed

    # ── Advisor display-name lookup ────────────────────────────────────

    advisor_lookup = (
        supabase.table("advisors")
        .select("practice_name")
        .eq("id", advisor_id)
        .limit(1)
        .execute()
    )
    advisor_display_name = roles.email  # fallback
    if advisor_lookup.data:
        practice_name = advisor_lookup.data[0].get("practice_name")
        if isinstance(practice_name, str) and practice_name.strip():
            advisor_display_name = practice_name.strip()

    # ── 409 duplicate check ─────────────────────────────────────────────

    duplicate = (
        supabase.table("clients")
        .select("id")
        .eq("advisor_id", advisor_id)
        .eq("email", email)
        .limit(1)
        .execute()
    )
    if duplicate.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You've already invited this email address. Use the "
                "resend-invitation endpoint to issue a fresh token."
            ),
        )

    # ── INSERT the pending clients row ──────────────────────────────────

    token = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.invitation_expiry_days
    )

    insert_result = (
        supabase.table("clients")
        .insert(
            {
                "advisor_id": advisor_id,
                "display_name": display_name,
                "email": email,
                "invitation_token": token,
                "invitation_expires_at": expires_at.isoformat(),
                "invitation_status": "pending",
                "user_id": None,
            }
        )
        .execute()
    )
    if not insert_result.data:
        logger.error(
            "Failed to insert clients row for advisor %s, email %s "
            "(empty result.data)",
            advisor_id,
            email,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create client row.",
        )
    client_id = str(insert_result.data[0]["id"])

    # ── Send the invitation email ───────────────────────────────────────

    invite_url = f"{settings.app_base_url}/invite/{token}"

    try:
        send_invitation_email(
            to_email=email,
            advisor_name=advisor_display_name,
            invite_url=invite_url,
        )
    except EmailSendError as exc:
        # The clients row exists. We intentionally do NOT roll it back —
        # the advisor can hit the resend endpoint to rotate the token
        # and try again. Surface a clear 502 so the UI can tell them.
        logger.exception(
            "Resend send failed for new client %s (advisor %s): %s",
            client_id,
            advisor_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Failed to send the invitation email. The client record "
                "was created, so you can retry via the resend "
                "endpoint without re-entering the details."
            ),
        ) from exc

    logger.info(
        "Issued invitation: advisor=%s client=%s email=%s",
        advisor_id,
        client_id,
        email,
    )

    return InviteClientResponse(client_id=client_id)


# --------------------------------------------------------------------------- #
# POST /accept-invitation
# --------------------------------------------------------------------------- #

class AcceptInvitationRequest(BaseModel):
    """Body for POST /accept-invitation.

    The token comes from the email link the client clicked. `confirmed`
    is the soft-confirmation flag the frontend sends after the user
    OKs an email-mismatch warning (i.e. their invitation went to one
    address but they're signed in to LinkedIn with another).
    """

    token: str = Field(..., min_length=1)
    confirmed: bool = False


class AcceptInvitationResponse(BaseModel):
    """Response from POST /accept-invitation.

    `requires_confirmation=True` indicates the invitation email differs
    from the LinkedIn email; `invitation_email` + `linkedin_email` are
    populated so the frontend can render the confirmation card. The
    response is 200 either way — mismatch is a soft state, not an
    error.
    """

    client_id: str
    requires_confirmation: bool
    invitation_email: str | None = None
    linkedin_email: str | None = None


@accept_router.post(
    "/accept-invitation",
    response_model=AcceptInvitationResponse,
)
async def accept_invitation(
    request: AcceptInvitationRequest,
    roles: Annotated[SessionRoles, Depends(get_verified_session)],
) -> AcceptInvitationResponse:
    """Accept an invitation: link the clients row to the caller's auth user.

    Depends on `get_verified_session` rather than the default
    `get_current_session_roles` because the caller's clients row
    hasn't been linked yet — this endpoint IS the linkage step.

    Decision tree:

      1. SELECT by token. 401 if no row.
      2. If `invitation_status == 'accepted'`: replay case.
           - `clients.user_id == roles.user_id`: idempotent 200 with
             the existing client_id. The token is intentionally
             preserved through acceptance (see implementation note
             below) so the same user clicking an old email link lands
             cleanly.
           - Otherwise: 401. A different user trying to claim a token
             already burned by someone else.
      3. Check expiry (only for non-accepted statuses): 401 if past.
      3b. ORPHEUS-83: if the caller already holds a linked clients row
          (roles.client_id is not None), 409. One auth user owns at
          most one clients row — accepting a second invitation must
          surface a clear state, not silently link a duplicate. This
          check runs BEFORE the email-mismatch card so users aren't
          asked to confirm an acceptance that can never complete.
          Migration 014's partial unique index on clients.user_id is
          the DB-level backstop.
      4. Compute case-insensitive email mismatch.
           - Mismatch + `confirmed=False`: 200 with
             `requires_confirmation=True` and both emails populated so
             the frontend can render the confirmation card. NO update.
           - Match or `confirmed=True`: proceed to UPDATE.
      5. UPDATE: set `user_id` and flip `invitation_status` to
         'accepted'. Return 200 with `client_id`.

    Implementation note (deviation from spec): the spec's UPDATE clause
    says to null `invitation_token` and `invitation_expires_at` on
    acceptance, but its replay-by-same-user case can't work that way —
    the row would no longer be reachable via the token. We preserve
    both fields and only flip status. The partial unique index on
    `invitation_token WHERE invitation_token IS NOT NULL` still
    enforces uniqueness for newly-issued invitations, and resend-
    invitation (commit #6) refuses to overwrite accepted rows, so
    accepted tokens never get reused.
    """
    supabase = get_service_client()

    lookup = (
        supabase.table("clients")
        .select("*")
        .eq("invitation_token", request.token)
        .limit(1)
        .execute()
    )
    if not lookup.data:
        # Either the token never existed, or it's been rotated away by
        # a resend-invitation. We don't distinguish — both surface to
        # the frontend as the same "invitation not found" state.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invitation not found or no longer valid.",
        )

    row = lookup.data[0]
    row_id = str(row["id"])
    invitation_status_value = row.get("invitation_status")

    # ── Replay of already-accepted invitation ───────────────────────────
    if invitation_status_value == "accepted":
        if row.get("user_id") == roles.user_id:
            # Same user clicking an old email link. Treat as a no-op
            # success rather than confusing them with a 401.
            return AcceptInvitationResponse(
                client_id=row_id,
                requires_confirmation=False,
            )
        # Different user trying to claim a token that's already been
        # burned. Refuse without leaking which user owns it now.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This invitation has already been accepted.",
        )

    # ── Expiry check (only applies to non-accepted rows) ────────────────
    expires_at_str = row.get("invitation_expires_at")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
        except ValueError as exc:
            logger.exception(
                "Malformed invitation_expires_at for client %s: %r",
                row_id,
                expires_at_str,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invitation timestamp is malformed.",
            ) from exc
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This invitation has expired. Ask your advisor to resend.",
            )

    # ── Already-linked caller check (ORPHEUS-83) ────────────────────────
    # Pending rows always have user_id NULL, so reaching this point with
    # roles.client_id set means the caller's linked row is a DIFFERENT
    # row than the one this token points at. Refuse rather than create
    # a duplicate; migration 014's unique index backstops races.
    if roles.client_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Your account is already linked to a client profile, and "
                "each account can hold only one. Ask the advisor who sent "
                "this invitation to contact support if you need to move "
                "your profile."
            ),
        )

    # ── Email mismatch check ────────────────────────────────────────────
    invitation_email_raw = row.get("email") or ""
    invitation_email_norm = invitation_email_raw.strip().lower()
    linkedin_email_norm = (roles.email or "").strip().lower()
    is_mismatch = invitation_email_norm != linkedin_email_norm

    if is_mismatch and not request.confirmed:
        # Soft confirmation: hand both emails back so the frontend can
        # render the "you were invited as X but signed in as Y, OK?"
        # card. No UPDATE; the row stays pending until the user
        # confirms.
        return AcceptInvitationResponse(
            client_id=row_id,
            requires_confirmation=True,
            invitation_email=invitation_email_raw,
            linkedin_email=roles.email,
        )

    # ── Accept: UPDATE the row ──────────────────────────────────────────
    try:
        update_result = (
            supabase.table("clients")
            .update(
                {
                    "user_id": roles.user_id,
                    "invitation_status": "accepted",
                    # Token + expires_at intentionally preserved; see
                    # implementation note in the docstring.
                }
            )
            .eq("id", row_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 — narrowed by the 23505 check
        # Race backstop (ORPHEUS-83): two concurrent acceptances by the
        # same user can both pass the pre-check above; migration 014's
        # partial unique index rejects the second UPDATE with a 23505
        # unique violation. Surface the same 409 as the pre-check
        # instead of an unhandled 500. Anything else re-raises.
        code = getattr(exc, "code", None)
        if code == "23505" or "23505" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Your account is already linked to a client profile, "
                    "and each account can hold only one."
                ),
            ) from exc
        raise
    if not update_result.data:
        logger.error(
            "Failed to update clients row %s on accept (empty result.data)",
            row_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept invitation.",
        )

    logger.info(
        "Accepted invitation: client=%s user=%s mismatch=%s",
        row_id,
        roles.user_id,
        is_mismatch,
    )

    return AcceptInvitationResponse(
        client_id=row_id,
        requires_confirmation=False,
    )


# --------------------------------------------------------------------------- #
# POST /clients/{client_id}/resend-invitation
# --------------------------------------------------------------------------- #

@router.post(
    "/{client_id}/resend-invitation",
    response_model=InviteClientResponse,
)
async def resend_invitation(
    client_id: str,
    roles: Annotated[SessionRoles, Depends(get_current_session_roles)],
) -> InviteClientResponse:
    """Rotate a client's invitation token + expiry and re-send the email.

    Lets the advisor recover from any reason an invitation didn't
    land: expired before the client clicked, lost in inbox triage,
    sent to a typo'd address that the advisor has since updated, etc.

    Flow:

      1. 403 if not roles.is_advisor().
      2. SELECT the clients row filtered on BOTH id and
         advisor_id = roles.advisor_id. Returning 404 for "wrong
         advisor" alongside "no such client" prevents leaking the
         existence of other advisors' clients.
      3. 409 if invitation_status == 'accepted'. Resending would
         orphan the accepted state — the advisor needs a separate
         revoke-and-reinvite flow for that (not in beta scope).
         Status 'expired' or 'pending' both resend cleanly.
      4. Look up the advisor's display-name for the email body
         (same fallback chain as /clients/invite).
      5. Generate fresh uuid4 token + new expiry. UPDATE the clients
         row with the new values and reset status to 'pending'.
      6. Send the new email via Resend. If Resend rejects, 502 — but
         the token has ALREADY been rotated, so the old email link
         is dead. The 502 detail tells the advisor the token has
         been refreshed (i.e. retrying the endpoint will not reuse
         the same token, but will work assuming Resend recovers).

    Returns the same client_id (the row's PK isn't rotated, just its
    invitation fields).
    """
    if not roles.is_advisor():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resending invitations requires an advisor profile.",
        )
    advisor_id = roles.advisor_id
    assert advisor_id is not None  # narrowed by is_advisor() guard above

    settings = get_settings()
    supabase = get_service_client()

    # ── SELECT the clients row ─────────────────────────────────────────

    lookup = (
        supabase.table("clients")
        .select("*")
        .eq("id", client_id)
        .eq("advisor_id", advisor_id)
        .limit(1)
        .execute()
    )
    if not lookup.data:
        # Either no such client or it belongs to another advisor.
        # We don't differentiate — see docstring.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found.",
        )
    row = lookup.data[0]

    if row.get("invitation_status") == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This client has already accepted their invitation. "
                "Resending would invalidate the accepted state — if you "
                "need to re-invite, contact support to revoke and "
                "reissue."
            ),
        )

    client_email = row.get("email")
    if not client_email:
        # Defensive: a clients row without an email shouldn't exist
        # under migration 001's NOT NULL constraint, but if it did
        # we'd want a clear failure rather than a confusing email send.
        logger.error("Clients row %s has no email; cannot resend", client_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Client row is missing an email address.",
        )

    # ── Advisor display-name lookup (same fallback chain as /invite) ───

    advisor_lookup = (
        supabase.table("advisors")
        .select("practice_name")
        .eq("id", advisor_id)
        .limit(1)
        .execute()
    )
    advisor_display_name = roles.email
    if advisor_lookup.data:
        practice_name = advisor_lookup.data[0].get("practice_name")
        if isinstance(practice_name, str) and practice_name.strip():
            advisor_display_name = practice_name.strip()

    # ── Rotate token + expiry, reset status ────────────────────────────

    new_token = str(uuid4())
    new_expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.invitation_expiry_days
    )

    update_result = (
        supabase.table("clients")
        .update(
            {
                "invitation_token": new_token,
                "invitation_expires_at": new_expires_at.isoformat(),
                "invitation_status": "pending",
            }
        )
        .eq("id", client_id)
        .execute()
    )
    if not update_result.data:
        logger.error(
            "Failed to rotate token on client %s (empty update result)",
            client_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh the invitation.",
        )

    # ── Send the new email ─────────────────────────────────────────────

    invite_url = f"{settings.app_base_url}/invite/{new_token}"

    try:
        send_invitation_email(
            to_email=client_email,
            advisor_name=advisor_display_name,
            invite_url=invite_url,
        )
    except EmailSendError as exc:
        # Token has already been rotated. The OLD email link is now
        # dead regardless. Surface a 502 telling the advisor the
        # token refresh worked but the send didn't — they can try
        # again, which will rotate the token AGAIN (idempotent from
        # the advisor's perspective).
        logger.exception(
            "Resend send failed for client %s (advisor %s): %s",
            client_id,
            advisor_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Failed to send the new invitation email. The "
                "invitation token has been refreshed, so you can "
                "safely retry."
            ),
        ) from exc

    logger.info(
        "Resent invitation: advisor=%s client=%s email=%s",
        advisor_id,
        client_id,
        client_email,
    )

    return InviteClientResponse(client_id=client_id)
