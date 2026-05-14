"""Advisor API — endpoints scoped to the advisor's own admin actions
that don't fit under the /clients prefix.

Today this is just one endpoint: POST /advisor/self-report (ORPHEUS-39).
It exists so an advisor can lazily provision their own `clients` row
without going through the invitation flow (no email, no token, no
acceptance step). The advisor IS the subject.

The route lives here rather than in `clients.py` because:

  * The caller is an advisor acting on their own behalf — semantically
    closer to /admin than to /clients.
  * Adding it under /clients would force the URL into either
    /clients/self-report (ambiguous with /clients/{id}/...) or
    /clients/me (overloaded with "me-as-client").

`get_current_session_roles` is enough — the advisor must already have
their `advisors` row to call this endpoint, so the neither-role case
is rejected upstream with the typed 401.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.auth import SessionRoles, get_current_session_roles
from backend.db import get_service_client

logger = logging.getLogger("orpheus.advisor")

router = APIRouter(prefix="/advisor", tags=["advisor"])


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #

class SelfReportRequest(BaseModel):
    """Body for POST /advisor/self-report.

    `display_name` is optional. The frontend passes the LinkedIn
    `user_metadata.name` from the Supabase session when it has one;
    we fall back to the email local-part otherwise so a clients row
    always has a non-empty display_name (NOT NULL in the schema).
    """

    display_name: str | None = Field(default=None, max_length=200)

    @field_validator("display_name")
    @classmethod
    def _trim_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class SelfReportResponse(BaseModel):
    """Response from POST /advisor/self-report.

    `created=True` indicates a new row was inserted; `created=False`
    indicates the call was idempotent — a self-clients row already
    existed and we returned its id. Lets the UI tell the difference
    between "first run" (e.g. announce-it-with-a-toast) and "second
    click" (silently navigate).
    """

    client_id: str
    created: bool


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #

@router.post("/self-report", response_model=SelfReportResponse)
async def advisor_self_report(
    request: SelfReportRequest,
    roles: Annotated[SessionRoles, Depends(get_current_session_roles)],
) -> SelfReportResponse:
    """Get-or-create the advisor's self-clients row.

    Idempotent by design: the second call from the same advisor returns
    the same client_id with `created=False`, so the UI's "Run my own
    report" button can be safely re-clicked without producing a second
    row.

    Decision tree:

      1. Reject non-advisor callers with 403.
      2. SELECT for the existing self-clients row keyed on
         (advisor_id = roles.advisor_id, user_id = roles.user_id).
         If present, return it with `created=False`.
      3. Compute the display_name: caller-supplied (preferred) →
         email local-part fallback.
      4. INSERT a new clients row:
           advisor_id        = self
           user_id           = self
           display_name      = computed above
           email             = roles.email
           invitation_status = 'accepted'
           invitation_token  = NULL (already accepted)
         Return the new id with `created=True`.

    Returns 200 (not 201) in both branches. The "created" boolean
    carries the new-vs-existing distinction; status code stays stable
    so the frontend's mutation hook can use a single onSuccess path.

    The clients row created here is functionally identical to one
    that went through the invite/accept flow — the worker, scoring
    engine, and report routes don't distinguish self-report from
    invited-client. Andrew using his own portal looks the same to
    the pipeline as any other client.
    """
    if not roles.is_advisor():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Running a self-report requires an advisor profile.",
        )
    advisor_id = roles.advisor_id
    assert advisor_id is not None  # narrowed by is_advisor() guard above
    user_id = roles.user_id

    supabase = get_service_client()

    # ── Idempotency check ──────────────────────────────────────────────

    existing = (
        supabase.table("clients")
        .select("id")
        .eq("advisor_id", advisor_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        existing_id = str(existing.data[0]["id"])
        logger.info(
            "Self-report idempotent hit: advisor=%s client=%s",
            advisor_id,
            existing_id,
        )
        return SelfReportResponse(client_id=existing_id, created=False)

    # ── Compute display_name ────────────────────────────────────────────

    display_name = request.display_name
    if not display_name:
        # Email local-part is a sensible last-resort — guaranteed
        # non-empty under the JWT-claim validation in auth.py (every
        # token has an email claim or we'd never have gotten here).
        email_local = (roles.email or "").split("@", 1)[0].strip()
        display_name = email_local or "Self"

    # ── INSERT the self-clients row ─────────────────────────────────────

    insert_result = (
        supabase.table("clients")
        .insert(
            {
                "advisor_id": advisor_id,
                "user_id": user_id,
                "display_name": display_name,
                "email": roles.email,
                "invitation_status": "accepted",
                # invitation_token + invitation_expires_at stay NULL —
                # the row is born accepted, no token ever issued.
            }
        )
        .execute()
    )
    if not insert_result.data:
        logger.error(
            "Failed to insert self-clients row for advisor %s (empty result.data)",
            advisor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create self-report client row.",
        )

    new_id = str(insert_result.data[0]["id"])
    logger.info(
        "Self-report created: advisor=%s client=%s",
        advisor_id,
        new_id,
    )
    return SelfReportResponse(client_id=new_id, created=True)
