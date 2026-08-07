"""Account API — self-service account deletion (ORPHEUS-124).

One endpoint: DELETE /account. Lets a signed-in user delete their own
account and every piece of personal data the system holds for them,
without emailing us. Closes the ToS §13.2 / Privacy Policy §12.1
promise of in-portal deletion, and the LinkedIn API §4.4 obligation.

## Why this is an ordered operation, not one auth delete

The FK graph makes a bare `auth.admin.delete_user()` wrong in both
directions (see ORPHEUS-124 and the corrected CLAUDE.md entry):

  * `clients.user_id` is ON DELETE **SET NULL** (001_base_schema.sql:127)
    — deleting the auth user would *orphan* the clients row and every
    downstream jobs/ingested_data/scores/narratives/questionnaire/
    reports row. The data would survive, unlinked. The exact opposite
    of what the policy promises.
  * `advisors.user_id` is ON DELETE **CASCADE** (:104) and
    `clients.advisor_id` is ON DELETE **CASCADE** (:126) — deleting an
    advisor's auth user would destroy every client on their roster and
    all of their reports. 13 real people on Andrew's roster today.

So the handler deletes in an explicit order, most-recoverable-last:

  1. Advisor-roster guard — an advisor with clients other than their
     own `is_self` row gets a 409 and nothing is touched
     [Josh, 2026-08-06: option (a), block until the roster is empty].
  2. Storage sweep — every object under `{client_id}/` in the uploads
     bucket (job paths *and* abandoned `staging/` prefixes). Storage is
     referenced by no FK, so nothing else would ever remove it. A
     failure here aborts with 502 and the account is left fully intact.
  3. The `clients` row, deleted explicitly — its ON DELETE CASCADE FKs
     then take jobs, ingested_data, scores, narratives,
     questionnaire_responses, and reports with it.
  4. The `advisors` row, if the caller has one (roster is empty or
     self-only by the guard, so this cascade is safe).
  5. Waitlist sweep — best-effort removal of `public.waitlist` rows
     matching the account email (case-insensitive). The table has no
     FK to auth.users; a failure here logs but does not abort
     [Josh, 2026-08-06: sweep yes, best-effort].
  6. `auth.admin.delete_user()` **last** — a failure anywhere earlier
     leaves a recoverable, signed-in account rather than an orphaned
     data set.

## Why `get_verified_session`, not `get_current_session_roles`

The ticket's partial-failure requirement ("safe to re-run") forces it:
if steps 1-5 succeed and step 6 fails, the user's business rows are
gone — on retry they resolve as *neither-role*, and the default
dependency would 401 them as "not invited", stranding the auth user
forever. `get_verified_session` keeps the retry path open, and also
covers the legitimate GDPR case of a signed-up-but-never-invited user
deleting their bare auth account. Deletion is inherently self-scoped
(everything keys off the verified JWT), so relaxing the role gate
grants access to nothing but the caller's own teardown.

Immediate hard delete, no grace period [Josh, 2026-08-06] — satisfies
the Privacy Policy §10 window trivially and adds no soft-deleted state
to reason about during beta.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.auth import SessionRoles, get_verified_session
from backend.db import get_service_client

logger = logging.getLogger("orpheus.account")

router = APIRouter(prefix="/account", tags=["account"])

# Same bucket the upload flow writes (jobs.py). Defined locally rather
# than imported from jobs.py so this module doesn't depend on a private
# name in another router.
_STORAGE_BUCKET = "uploads"

# Storage folder nesting under a client prefix is at most
# {client_id}/staging/{upload_id}/<file> — three levels. Cap the walk a
# level deeper so a surprise never recurses unbounded.
_MAX_WALK_DEPTH = 4


class DeleteAccountResponse(BaseModel):
    """Response for DELETE /account."""

    deleted: bool = True


# --------------------------------------------------------------------------- #
# Storage walk
# --------------------------------------------------------------------------- #

def _collect_storage_paths(storage, prefix: str, depth: int = 0) -> list[str]:
    """Recursively collect every object path under `prefix`.

    Supabase Storage's list API is per-prefix and non-recursive: folders
    come back as entries with no object `id` and no `metadata`, files
    carry both. Client folders hold a handful of jobs during beta, well
    under the API's default page size — pagination is a follow-up if a
    client folder ever accumulates 100+ entries.

    Raises on listing failure — the caller must treat "couldn't
    enumerate" as "couldn't delete" and abort, otherwise objects the
    policy promises to remove would silently survive.
    """
    paths: list[str] = []
    entries = storage.list(prefix) or []
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not name:
            continue
        full = f"{prefix}/{name}"
        is_file = bool(entry.get("id")) or bool(entry.get("metadata"))
        if is_file:
            paths.append(full)
        elif depth < _MAX_WALK_DEPTH:
            paths.extend(_collect_storage_paths(storage, full, depth + 1))
    return paths


def _sweep_client_storage(supabase, client_id: str) -> None:
    """Remove every uploads object under `{client_id}/`.

    Raises HTTPException(502) on any failure, *before* any database row
    has been touched — the account stays intact and the user retries.
    """
    storage = supabase.storage.from_(_STORAGE_BUCKET)
    try:
        paths = _collect_storage_paths(storage, client_id)
        if paths:
            storage.remove(paths)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Storage sweep failed for client %s: %s", client_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "We couldn't remove your uploaded files, so nothing has "
                "been deleted. Please try again in a moment; if this "
                "keeps happening, contact us at contact@orpheussocial.com."
            ),
        ) from exc


def _sweep_waitlist(supabase, email: str) -> None:
    """Best-effort removal of waitlist rows matching the account email.

    `public.waitlist` stores email with submitted casing (the unique
    index is on lower(email)), and PostgREST has no lower() filter — so
    select-with-ilike would need pattern escaping to be exact. Instead:
    pull candidate ids with a case-insensitive match done in Python,
    then delete by id. Failures log and continue: the account deletion
    itself matters more than a marketing-list row, and the DSR runbook
    (ORPHEUS-127) covers manual cleanup.
    """
    try:
        result = supabase.table("waitlist").select("id,email").execute()
        rows = result.data or []
        target = email.strip().lower()
        ids = [
            row["id"]
            for row in rows
            if isinstance(row.get("email"), str)
            and row["email"].strip().lower() == target
        ]
        if ids:
            supabase.table("waitlist").delete().in_("id", ids).execute()
            logger.info(
                "Swept %d waitlist row(s) for deleted account", len(ids)
            )
    except Exception as exc:
        logger.warning("Waitlist sweep failed (non-fatal): %s", exc)


# --------------------------------------------------------------------------- #
# DELETE /account
# --------------------------------------------------------------------------- #

@router.delete("", response_model=DeleteAccountResponse)
async def delete_account(
    roles: SessionRoles = Depends(get_verified_session),
) -> DeleteAccountResponse:
    """Delete the caller's account and all associated personal data."""
    supabase = get_service_client()

    # ── 1. Advisor-roster guard ────────────────────────────────────────
    # An advisor whose roster contains anyone but themselves cannot
    # delete: the advisors-row cascade would destroy other people's
    # reports. Their own is_self row (user_id == caller) doesn't block.
    if roles.is_advisor():
        roster = (
            supabase.table("clients")
            .select("id,user_id")
            .eq("advisor_id", roles.advisor_id)
            .execute()
        )
        others = [
            row
            for row in (roster.data or [])
            if row.get("user_id") != roles.user_id
        ]
        if others:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Your advisor roster still has {len(others)} "
                    f"client{'s' if len(others) != 1 else ''}. Deleting "
                    "your account would destroy their reports too, so "
                    "it's blocked while the roster is non-empty. Contact "
                    "us at contact@orpheussocial.com to arrange a "
                    "transfer or roster cleanup first."
                ),
            )

    # ── 2. Storage sweep (aborts on failure; nothing touched yet) ─────
    if roles.is_client():
        _sweep_client_storage(supabase, str(roles.client_id))

    # ── 3 + 4. Business rows, clients first ───────────────────────────
    # Explicit deletes — never rely on the auth-user FK behavior (SET
    # NULL would orphan; the advisor cascade is handled safely here
    # because the guard has already run).
    try:
        if roles.is_client():
            supabase.table("clients").delete().eq(
                "id", roles.client_id
            ).execute()
        if roles.is_advisor():
            supabase.table("advisors").delete().eq(
                "id", roles.advisor_id
            ).execute()
    except Exception as exc:
        logger.exception(
            "Business-row deletion failed for user %s: %s",
            roles.user_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Something went wrong while deleting your data. Your "
                "account is still active — please try again, or contact "
                "us at contact@orpheussocial.com."
            ),
        ) from exc

    # ── 5. Waitlist sweep (best-effort) ────────────────────────────────
    _sweep_waitlist(supabase, roles.email)

    # ── 6. Auth user, last ─────────────────────────────────────────────
    # By here the personal data is gone; if this step fails the caller
    # retries as a neither-role session (which get_verified_session
    # allows — see module docstring) and only this step re-runs.
    try:
        supabase.auth.admin.delete_user(roles.user_id)
    except Exception as exc:
        logger.exception(
            "Auth-user deletion failed for %s: %s", roles.user_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Your data has been removed, but the sign-in account "
                "itself couldn't be deleted. Please try the delete "
                "action once more to finish, or contact us at "
                "contact@orpheussocial.com."
            ),
        ) from exc

    logger.info(
        "Account deleted: user %s (client=%s, advisor=%s)",
        roles.user_id,
        roles.client_id,
        roles.advisor_id,
    )
    return DeleteAccountResponse()
