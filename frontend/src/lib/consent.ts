/**
 * Consent constants and the OAuth-round-trip carrier (ORPHEUS-126).
 *
 * Two separate consents, captured in two separate places:
 *
 *   1. Terms of Service + Privacy Policy — a checkbox on /login that gates
 *      "Continue with LinkedIn". Account-level and version-scoped.
 *   2. LinkedIn upload processing — a checkbox on the Groundwork submit
 *      step. Per-submission; lives on the jobs row.
 *
 * This module owns (1)'s hard part. The affirmative act happens *before*
 * authentication, so there is no user id to attach it to at the moment it
 * happens — the intent has to survive the LinkedIn OIDC round trip and be
 * recorded on the way back.
 *
 * The carrier is the OAuth `redirectTo` query string, with sessionStorage as
 * a same-context fallback. This is the shape ORPHEUS-92 arrived at for the
 * invitation token after sessionStorage alone lost it for real beta users:
 * email and LinkedIn in-app browsers frequently hand the OAuth hop to the
 * system browser and return in a *fresh* browsing context where anything
 * stashed in sessionStorage is gone. Supabase's redirect allow-list uses a
 * `/**` wildcard, which covers the query string.
 *
 * `captureFromUrl` is called at module-load time from main.tsx, before React
 * renders. That timing is deliberate and load-bearing: the post-login landing
 * route is `/`, whose SmartIndexRedirect immediately <Navigate>s away and
 * discards the query string. Reading it from inside a component effect races
 * that redirect; reading it before the first render cannot.
 *
 * Unlike the invitation token, a leaked value here is inert — it says only
 * "somebody ticked a box against version X", carries no identity, and grants
 * nothing. We still strip it from the URL after capture so a refresh or a
 * shared link can't replay it, and so the address bar stays clean.
 */

/**
 * Effective date of the currently-published Terms of Service (/terms).
 *
 * OPEN ITEM FOR ORPHEUS-125: 125 owns publishing the documents and setting
 * their real effective date in place of the drafts' `[publication date]`
 * placeholder. These two constants, backend/consent_versions.py, and the
 * documents themselves must all carry the same date — the backend refuses a
 * version string it doesn't recognise, so drift fails closed (nobody can
 * sign in or submit) rather than recording consent against a document
 * version that never existed.
 */
export const CURRENT_TERMS_VERSION = '2026-08-11'

/** Effective date of the currently-published Privacy Policy (/privacy). */
export const CURRENT_PRIVACY_VERSION = '2026-08-11'

/** Published document routes. Created by ORPHEUS-125; 404 until it lands. */
export const TERMS_PATH = '/terms'
export const PRIVACY_PATH = '/privacy'

const PENDING_ACCEPTANCE_KEY = 'orpheus.pendingTermsAcceptance'

/** Query-string keys carrying the acceptance through the OAuth redirect. */
export const TERMS_VERSION_QUERY_KEY = 'terms_v'
export const PRIVACY_VERSION_QUERY_KEY = 'privacy_v'

export interface PendingTermsAcceptance {
  termsVersion: string
  privacyVersion: string
}

/**
 * Build the post-OAuth landing URL, carrying the accepted versions.
 * Called by LoginPage when the user ticks the box and continues.
 */
export function buildAcceptanceRedirectUrl(
  origin: string = window.location.origin,
): string {
  const url = new URL(`${origin}/`)
  url.searchParams.set(TERMS_VERSION_QUERY_KEY, CURRENT_TERMS_VERSION)
  url.searchParams.set(PRIVACY_VERSION_QUERY_KEY, CURRENT_PRIVACY_VERSION)
  return url.toString()
}

export function readPendingTermsAcceptance(): PendingTermsAcceptance | null {
  try {
    const raw = sessionStorage.getItem(PENDING_ACCEPTANCE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<PendingTermsAcceptance>
    if (!parsed.termsVersion || !parsed.privacyVersion) return null
    return {
      termsVersion: parsed.termsVersion,
      privacyVersion: parsed.privacyVersion,
    }
  } catch {
    // Private mode, disabled storage, or a corrupt value. Treat as absent —
    // the worst case is that an acceptance goes unrecorded, which we would
    // rather have than a thrown error on the sign-in path.
    return null
  }
}

export function writePendingTermsAcceptance(
  acceptance: PendingTermsAcceptance,
): void {
  try {
    sessionStorage.setItem(PENDING_ACCEPTANCE_KEY, JSON.stringify(acceptance))
  } catch {
    // Same trade-off: the URL carrier is the primary path anyway.
  }
}

export function clearPendingTermsAcceptance(): void {
  try {
    sessionStorage.removeItem(PENDING_ACCEPTANCE_KEY)
  } catch {
    // Nothing useful to do.
  }
}

/**
 * Read an acceptance out of the current URL, stash it, and strip it from the
 * address bar. Idempotent and safe to call when no acceptance is present.
 *
 * Called from main.tsx at module load — see the note at the top of this file
 * for why it cannot wait for a component effect.
 *
 * Returns the captured acceptance, or null when the URL carried none.
 */
export function captureTermsAcceptanceFromUrl(): PendingTermsAcceptance | null {
  let search: string
  try {
    search = window.location.search
  } catch {
    return null
  }
  if (!search) return null

  const params = new URLSearchParams(search)
  const termsVersion = params.get(TERMS_VERSION_QUERY_KEY)
  const privacyVersion = params.get(PRIVACY_VERSION_QUERY_KEY)
  if (!termsVersion || !privacyVersion) return null

  const acceptance: PendingTermsAcceptance = { termsVersion, privacyVersion }
  writePendingTermsAcceptance(acceptance)

  // Strip only our own params, preserving anything else on the URL (the
  // invitation flow's ?token= lands on a different route, but a future
  // param shouldn't be collateral damage).
  try {
    params.delete(TERMS_VERSION_QUERY_KEY)
    params.delete(PRIVACY_VERSION_QUERY_KEY)
    const remaining = params.toString()
    const cleaned =
      window.location.pathname + (remaining ? `?${remaining}` : '')
    window.history.replaceState(null, '', cleaned)
  } catch {
    // Leaving the params in the bar is cosmetic; the capture already
    // succeeded, and the recorder clears sessionStorage once it posts.
  }

  return acceptance
}
