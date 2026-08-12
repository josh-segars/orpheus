"""Self-serve sign-up API (ORPHEUS-85, gate expanded by ORPHEUS-129).

POST /signup/complete — the post-OAuth linkage step for clients who
arrive WITHOUT an invitation. Revises the [2026-05-11] "beta is
invitation-only (no /signup)" decision from
Decision_Self_Serve_And_Advisor_Invite: beta clients can now sign up
ahead of Stripe (ORPHEUS-40), gated by an access code.

Ownership model (locked by Josh, 2026-06-12): house advisor by
default. Self-serve sign-ups are auto-assigned to the advisor row
named by the HOUSE_ADVISOR_ID env (see backend/config.py) —
`clients.advisor_id` stays NOT NULL, advisor-less clients were
rejected as an option. ORPHEUS-129 adds the group/business exception:
a signup code can carry its own `advisor_id`, and clients created
through that code land under that advisor instead (e.g. a business
cohort under the business's advisor row).

Gate (ORPHEUS-129, decided [Josh, 2026-08-12] before first deploy —
the interim single BETA_ACCESS_CODE env never shipped): codes are rows
in `public.signup_codes` (migration 022), admin-generated via
/admin/codes, each with optional expiry, max-uses, and a per-code
disable switch. Every successful sign-up records a
`public.code_redemptions` row — the attribution record ("which cohort
did this client come from") and the source of use counts.

Relationship to /accept-invitation (backend/routers/clients.py):

  * Same auth posture — `get_verified_session`, because the caller is
    freshly authenticated and their clients row doesn't exist yet;
    the sign-up completion IS the row-creation step.
  * Same ORPHEUS-83 invariant — one auth user owns at most one clients
    row. Here it makes the endpoint idempotent get-or-create: a caller
    who already holds a linked row (invited OR self-serve) gets that
    row back with `created=false`, never a second one. Migration 014's
    partial unique index on clients.user_id backstops races.

Fail-closed posture: when HOUSE_ADVISOR_ID is unset the endpoint 503s
(there is no default advisor to assign to), and with no active rows in
signup_codes every code 403s. Self-serve sign-up is a feature you turn
ON, not one you forget off.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth import SessionRoles, get_verified_session
from backend.config import get_settings
from backend.db import get_service_client

logger = logging.getLogger("orpheus.signup")

router = APIRouter(tags=["signup"])


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #

class SignupCompleteRequest(BaseModel):
    """Body for POST /signup/complete.

    `beta_code` is the access code the user entered on /signup; it
    rides the OAuth redirect URL (same ORPHEUS-92 carrier pattern as
    the invitation token) and is validated here, server-side, against
    `public.signup_codes`.

    `display_name` is the user's name as reported by LinkedIn OIDC
    (`user_metadata.name` on the Supabase session). Optional because
    metadata shape isn't guaranteed; the backend falls back to the
    email local-part rather than failing sign-up over a display label.
    """

    beta_code: str = Field(..., min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)


class SignupCompleteResponse(BaseModel):
    """Response from POST /signup/complete.

    `created=False` marks the idempotent path — the caller already had
    a linked clients row (from a prior sign-up OR an accepted
    invitation) and got it back unchanged. The frontend treats both
    values identically (navigate to the portal); the flag exists for
    logging/debugging clarity.
    """

    client_id: str
    created: bool


# --------------------------------------------------------------------------- #
# Code lookup / validation helpers
# --------------------------------------------------------------------------- #

def _escape_ilike(value: str) -> str:
    """Escape PostgREST ilike wildcards so a code is matched literally.

    Lookup uses `ilike` with no added wildcards as a case-insensitive
    equality (matching migration 022's unique-on-lower(code) semantics),
    but a vanity code containing `%` or `_` would otherwise turn into a
    pattern. Generated codes never contain either; this guards vanity
    input.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _find_active_code(supabase: Any, submitted: str) -> dict[str, Any] | None:
    """Return the signup_codes row for `submitted` if it is redeemable.

    None means "reject with the generic 403" — unknown code, disabled,
    expired, or fully redeemed. The caller doesn't learn which, and
    neither does the user (no enumeration help; the beta-scale
    recovery for a confused legitimate user is asking whoever gave
    them the code).

    Validation order: existence → disabled → expiry → max-uses. The
    max-uses check counts `code_redemptions` rows (there is no counter
    column to drift) and is check-then-insert rather than atomic —
    over-redemption by 1 under concurrency is accepted at beta scale
    (documented on migration 022 and ORPHEUS-129).
    """
    lookup = (
        supabase.table("signup_codes")
        .select("*")
        .ilike("code", _escape_ilike(submitted))
        .limit(1)
        .execute()
    )
    if not lookup.data:
        return None
    row = lookup.data[0]

    if row.get("disabled_at") is not None:
        logger.info("Signup code %s rejected: disabled", row.get("id"))
        return None

    expires_at_str = row.get("expires_at")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
        except ValueError:
            # Malformed timestamp — fail closed on this code, loudly.
            logger.error(
                "Malformed expires_at on signup code %s: %r",
                row.get("id"),
                expires_at_str,
            )
            return None
        if expires_at < datetime.now(timezone.utc):
            logger.info("Signup code %s rejected: expired", row.get("id"))
            return None

    max_uses = row.get("max_uses")
    if max_uses is not None:
        count_result = (
            supabase.table("code_redemptions")
            .select("id", count="exact")
            .eq("code_id", row["id"])
            .execute()
        )
        redeemed = count_result.count or 0
        if redeemed >= max_uses:
            logger.info(
                "Signup code %s rejected: fully redeemed (%d/%d)",
                row.get("id"),
                redeemed,
                max_uses,
            )
            return None

    return row


# --------------------------------------------------------------------------- #
# POST /signup/complete
# --------------------------------------------------------------------------- #

@router.post("/signup/complete", response_model=SignupCompleteResponse)
async def complete_signup(
    request: SignupCompleteRequest,
    roles: Annotated[SessionRoles, Depends(get_verified_session)],
) -> SignupCompleteResponse:
    """Create (or return) the caller's clients row via a signup code.

    Decision tree:

      1. Feature gate: 503 unless `house_advisor_id` is configured —
         there is no default advisor to assign to without it, even
         when a code carries its own routing (the code's advisor may
         have been deleted, falling back to house). Fail-closed.
      2. Idempotency (ORPHEUS-83): if the caller already holds a linked
         clients row, return it with `created=False` — BEFORE the code
         check, so a disabled/expired code can't lock an already-linked
         user out of their own portal. The only information this path
         reveals is the caller's own client_id, which GET /session
         exposes anyway.
      3. Code check: 403 unless the submitted code matches an active
         `signup_codes` row (exists, not disabled, not expired, under
         max_uses). Case-insensitive, stripped. The frontend re-prompts
         for the code without re-running OAuth.
      4. Advisor resolution: the code's `advisor_id` override when set
         (group/business routing, ORPHEUS-129), else HOUSE_ADVISOR_ID.
         Existence probe → 503 on a dangling reference. Configuration
         error — surfacing it as an explicit 503 with a log line beats
         the FK-violation 500 the INSERT would otherwise produce.
      5. INSERT the clients row: resolved advisor, user_id = caller,
         email from the JWT (normalized), display name from the request
         with email-local-part fallback, invitation_status = 'accepted'
         (the row is born linked; there is no pending state to move
         through), no invitation token.
      6. Record the redemption (attribution + use counting). Best-effort:
         the client exists at this point, and unwinding a created
         account over a bookkeeping row would punish the user for our
         error — a failed insert logs loudly instead.
      7. Race backstop: a 23505 unique violation from migration 014's
         index (two concurrent completions, or a concurrent invitation
         acceptance) re-SELECTs by user_id and returns the winner's row
         with `created=False` — and records no redemption (the winning
         request recorded its own).

    Caveat for future writers: rows created here have
    `invitation_token IS NULL` — any future flow that assumes every
    clients row was minted by /clients/invite (e.g. a resend sweep)
    must tolerate that.
    """
    settings = get_settings()

    # ── 1. Feature gate — fail closed ───────────────────────────────────
    if not settings.house_advisor_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Self-serve sign-up is not enabled. Ask your advisor "
                "for an invitation instead."
            ),
        )

    supabase = get_service_client()

    # ── 2. Idempotent replay — caller already linked (ORPHEUS-83) ──────
    if roles.client_id is not None:
        logger.info(
            "Signup replay: user %s already linked to client %s",
            roles.user_id,
            roles.client_id,
        )
        return SignupCompleteResponse(client_id=roles.client_id, created=False)

    # ── 3. Access code (signup_codes table, ORPHEUS-129) ────────────────
    code_row = _find_active_code(supabase, request.beta_code.strip())
    if code_row is None:
        # Deliberately one generic detail for unknown / disabled /
        # expired / fully-redeemed — no enumeration help.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "That access code isn't valid or is no longer active. "
                "Check the code you were given and try again."
            ),
        )

    # ── 4. Advisor resolution — code override, else house ───────────────
    advisor_id = code_row.get("advisor_id") or settings.house_advisor_id
    advisor_lookup = (
        supabase.table("advisors")
        .select("id")
        .eq("id", advisor_id)
        .limit(1)
        .execute()
    )
    if not advisor_lookup.data:
        logger.error(
            "Signup advisor %s (code %s, house %s) has no advisors row — "
            "self-serve sign-up is misconfigured",
            advisor_id,
            code_row.get("id"),
            settings.house_advisor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Self-serve sign-up is misconfigured on this deployment. "
                "Please contact support."
            ),
        )

    # ── 5. INSERT the linked clients row ────────────────────────────────
    email = (roles.email or "").strip().lower()
    display_name = (request.display_name or "").strip()
    if not display_name:
        # LinkedIn metadata didn't arrive (or the frontend didn't send
        # it). The email local-part is a serviceable label the client
        # can read as themselves; advisors can rename later.
        display_name = email.split("@", 1)[0] or email

    try:
        insert_result = (
            supabase.table("clients")
            .insert(
                {
                    "advisor_id": advisor_id,
                    "user_id": roles.user_id,
                    "display_name": display_name,
                    "email": email,
                    # Born linked: there is no pending→accepted lifecycle
                    # for a self-serve row, and no token to accept with.
                    "invitation_status": "accepted",
                    "invitation_token": None,
                    "invitation_expires_at": None,
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 — narrowed by the 23505 check
        code = getattr(exc, "code", None)
        if code == "23505" or "23505" in str(exc):
            # ── 7. Race backstop (migration 014) ────────────────────────
            # Someone else linked this user between the roles lookup and
            # our INSERT — a double-submit, or a concurrent invitation
            # acceptance. The winner's row is the caller's row; fetch
            # and return it idempotently. No redemption recorded — the
            # winning request recorded its own (if it came through a
            # code at all).
            refetch = (
                supabase.table("clients")
                .select("id")
                .eq("user_id", roles.user_id)
                .limit(1)
                .execute()
            )
            if refetch.data:
                existing_id = str(refetch.data[0]["id"])
                logger.info(
                    "Signup race resolved: user %s already linked to "
                    "client %s",
                    roles.user_id,
                    existing_id,
                )
                return SignupCompleteResponse(
                    client_id=existing_id,
                    created=False,
                )
            # Unique violation but no row on refetch — shouldn't happen;
            # surface as a 500 rather than pretending success.
            logger.error(
                "23505 on signup insert for user %s but no clients row "
                "found on refetch",
                roles.user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete sign-up.",
            ) from exc
        raise

    if not insert_result.data:
        logger.error(
            "Failed to insert self-serve clients row for user %s "
            "(empty result.data)",
            roles.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete sign-up.",
        )

    client_id = str(insert_result.data[0]["id"])

    # ── 6. Record the redemption (attribution; best-effort) ─────────────
    try:
        (
            supabase.table("code_redemptions")
            .insert({"code_id": code_row["id"], "client_id": client_id})
            .execute()
        )
    except Exception:  # noqa: BLE001 — bookkeeping must not undo the account
        logger.exception(
            "Failed to record redemption of code %s by client %s — "
            "attribution lost, recover manually if it matters",
            code_row.get("id"),
            client_id,
        )

    logger.info(
        "Self-serve sign-up: user=%s client=%s advisor=%s code=%s (%s)",
        roles.user_id,
        client_id,
        advisor_id,
        code_row.get("id"),
        code_row.get("label"),
    )
    return SignupCompleteResponse(client_id=client_id, created=True)
