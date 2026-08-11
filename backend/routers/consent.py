"""Consent API (ORPHEUS-126).

POST /consent/terms records that the caller accepted the Terms of Service +
Privacy Policy. The affirmative act happens on /login, before the LinkedIn
OIDC hop — but there is no authenticated identity to attach it to until the
round trip completes, so the frontend carries the intent across the redirect
(see frontend/src/lib/consent.ts) and posts it here on first authenticated
render.

Why this endpoint uses `get_verified_session` rather than the default
`get_current_session_roles`: a brand-new self-serve user can arrive here
before their clients row exists, and an advisor-invited user posts this from
/login's redirect *before* /accept-invitation has run. Both are neither-role
at that instant, and the strict dependency would 401 them as "not invited" —
losing the very consent record we need. Same reasoning ORPHEUS-124's
DELETE /account applies to its own retry path.

Writes go through the service-role client. The table's RLS grants the user
SELECT on their own rows and no INSERT at all, deliberately: a consent record
the subject could write themselves is not evidence of anything.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.auth import SessionRoles, get_verified_session
from backend.consent_versions import (
    ACCEPTED_PRIVACY_VERSIONS,
    ACCEPTED_TERMS_VERSIONS,
)
from backend.db import get_service_client

logger = logging.getLogger("orpheus.consent")

router = APIRouter(prefix="/consent", tags=["consent"])


class RecordTermsAcceptanceRequest(BaseModel):
    terms_version: str
    privacy_version: str


class RecordTermsAcceptanceResponse(BaseModel):
    recorded: bool
    """True when this call created the row; False when an identical
    acceptance already existed. Both are success — the endpoint is
    idempotent because the frontend may retry it across a refresh."""

    terms_version: str
    privacy_version: str


@router.post(
    "/terms",
    response_model=RecordTermsAcceptanceResponse,
    status_code=status.HTTP_200_OK,
)
async def record_terms_acceptance(
    body: RecordTermsAcceptanceRequest,
    roles: Annotated[SessionRoles, Depends(get_verified_session)],
) -> RecordTermsAcceptanceResponse:
    """Record the caller's acceptance of the ToS + Privacy Policy.

    Rejects a version pair we don't publish. That matters more than it
    looks: accepting an arbitrary string would let a stale cached bundle
    record consent against a document version that never existed, and the
    row would be indistinguishable from a real one afterwards.
    """
    if body.terms_version not in ACCEPTED_TERMS_VERSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unrecognised terms version. Please reload the page and "
                "sign in again."
            ),
        )
    if body.privacy_version not in ACCEPTED_PRIVACY_VERSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unrecognised privacy policy version. Please reload the "
                "page and sign in again."
            ),
        )

    supabase = get_service_client()

    # Idempotency is enforced by idx_terms_acceptances_user_versions, but
    # check first so the common re-post path doesn't rely on catching a
    # driver-specific unique-violation error shape.
    existing = (
        supabase.table("terms_acceptances")
        .select("id")
        .eq("user_id", roles.user_id)
        .eq("terms_version", body.terms_version)
        .eq("privacy_version", body.privacy_version)
        .limit(1)
        .execute()
    )
    if existing.data:
        return RecordTermsAcceptanceResponse(
            recorded=False,
            terms_version=body.terms_version,
            privacy_version=body.privacy_version,
        )

    try:
        supabase.table("terms_acceptances").insert(
            {
                "user_id": roles.user_id,
                "terms_version": body.terms_version,
                "privacy_version": body.privacy_version,
            }
        ).execute()
    except Exception as exc:
        # A concurrent duplicate (two tabs finishing the OAuth hop at once)
        # trips the unique index. That is the desired end state, not a
        # failure, so treat it as already-recorded rather than 500ing at a
        # user who did everything right.
        if _is_unique_violation(exc):
            logger.info(
                "Duplicate terms acceptance for user %s (%s/%s) — treating "
                "as recorded",
                roles.user_id,
                body.terms_version,
                body.privacy_version,
            )
            return RecordTermsAcceptanceResponse(
                recorded=False,
                terms_version=body.terms_version,
                privacy_version=body.privacy_version,
            )
        logger.exception(
            "Failed to record terms acceptance for user %s: %s",
            roles.user_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "We couldn't record your agreement. This is usually "
                "transient — please try again in a moment."
            ),
        ) from exc

    logger.info(
        "Recorded terms acceptance for user %s (terms %s, privacy %s)",
        roles.user_id,
        body.terms_version,
        body.privacy_version,
    )
    return RecordTermsAcceptanceResponse(
        recorded=True,
        terms_version=body.terms_version,
        privacy_version=body.privacy_version,
    )


def _is_unique_violation(exc: Exception) -> bool:
    """Best-effort detection of a Postgres 23505 surfaced by supabase-py.

    The client wraps PostgREST errors rather than raising psycopg
    exceptions, so there is no exception class to catch — the code lands in
    the message or in a `code` attribute depending on version. Matching on
    both is deliberately loose; a false negative only costs us a 502 on a
    genuine duplicate, which the frontend retries harmlessly.
    """
    code = getattr(exc, "code", None)
    if code == "23505":
        return True
    text = str(exc)
    return "23505" in text or "duplicate key value" in text.lower()
