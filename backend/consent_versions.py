"""Published policy versions (ORPHEUS-126).

Single backend source of truth for which Terms of Service / Privacy Policy
version a consent record refers to. The frontend mirror lives in
frontend/src/lib/consent.ts and the two MUST agree — the backend rejects a
submission whose declared version it doesn't recognise, so a drifting pair
fails closed (nobody can submit) rather than silently recording consent
against a document that never existed.

OPEN ITEM FOR ORPHEUS-125: these strings are the *effective dates* of the
published documents. ORPHEUS-125 owns publishing /terms and /privacy and
setting their real effective date in place of the drafts' `[publication
date]` placeholder. If 125 publishes under a different date than the values
below, update all three places (here, the frontend mirror, and the documents)
in the same commit — otherwise consent rows point at a version no user could
have read.
"""

from __future__ import annotations

# Effective date of the currently-published Terms of Service (/terms).
CURRENT_TERMS_VERSION = "2026-08-11"

# Effective date of the currently-published Privacy Policy (/privacy).
CURRENT_PRIVACY_VERSION = "2026-08-11"

# Versions we still accept a consent declaration for. Only the current pair
# today; when ORPHEUS-125's s19 change-notice flow bumps a version, the
# 30-day notice window is the period during which both the outgoing and
# incoming versions are legitimately in play, so the outgoing one stays here
# until the new text takes effect.
ACCEPTED_TERMS_VERSIONS = frozenset({CURRENT_TERMS_VERSION})
ACCEPTED_PRIVACY_VERSIONS = frozenset({CURRENT_PRIVACY_VERSION})
