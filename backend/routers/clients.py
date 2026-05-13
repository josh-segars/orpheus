"""Clients API — advisor-managed invitation flow (ORPHEUS-38).

This file will grow across commits #4–#6 of the ORPHEUS-38 chain:

  Commit #4 (this commit): POST /clients/invite — advisor issues an
    invitation. Creates a pending `clients` row + sends the email.

  Commit #5: POST /accept-invitation — token holder accepts. NOT in
    this router (different prefix, different auth dependency).

  Commit #6: POST /clients/{id}/resend-invitation — advisor rotates
    the token and re-sends the email.

The "/clients" prefix means all routes here are
`POST /clients/<something>`. The accept endpoint is intentionally
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

from backend.auth import SessionRoles, get_current_session_roles
from backend.config import get_settings
from backend.db import get_service_client
from backend.email.resend_client import EmailSendError, send_invitation_email

logger = logging.getLogger("orpheus.clients")

router = APIRouter(prefix="/clients", tags=["clients"])


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


# --------------------------------------------------------------------------- #
# Endpoint
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
