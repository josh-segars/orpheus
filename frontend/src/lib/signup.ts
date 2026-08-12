/**
 * Self-serve sign-up flow constants and helpers (ORPHEUS-85).
 *
 * The beta access code has to survive the LinkedIn OAuth round trip
 * between /signup (which collects it and kicks off OAuth) and
 * /signup/callback (which retrieves it and calls POST /signup/complete).
 * Exactly the invitation token's problem, solved the same way
 * (ORPHEUS-92): the code rides the OAuth `redirectTo` URL as a query
 * param — the source of truth, because in-app browsers return from the
 * OAuth hop in a fresh browsing context where sessionStorage is gone —
 * with sessionStorage retained as a same-context fallback.
 *
 * Unlike the invitation token, losing the code is recoverable in-place:
 * the callback page re-prompts for it (the user is already
 * authenticated, so no OAuth re-run is needed). And a leaked code is
 * lower-stakes than a leaked token — it's a shared value that gates row
 * creation behind an authenticated session, not a single-use credential
 * linked to a specific person. We still strip it from the address bar
 * once captured.
 */

export const PENDING_SIGNUP_CODE_KEY = 'orpheus.pendingSignupCode'

/** Query-string key carrying the code through the OAuth redirect. */
export const SIGNUP_CODE_QUERY_KEY = 'signup_code'

/**
 * Read the beta access code from the current URL's query string, if
 * present. Primary source — survives cross-context OAuth redirects
 * that drop sessionStorage (ORPHEUS-92's lesson).
 */
export function readSignupCodeFromUrl(
  search: string = window.location.search,
): string | null {
  const value = new URLSearchParams(search).get(SIGNUP_CODE_QUERY_KEY)
  return value && value.length > 0 ? value : null
}

export function readPendingSignupCode(): string | null {
  try {
    return sessionStorage.getItem(PENDING_SIGNUP_CODE_KEY)
  } catch {
    // Private mode / disabled storage — the URL carrier is primary, and
    // the callback page re-prompts if both sources come up empty.
    return null
  }
}

export function writePendingSignupCode(code: string): void {
  try {
    sessionStorage.setItem(PENDING_SIGNUP_CODE_KEY, code)
  } catch {
    // Same trade-off as consent.ts: URL is the primary carrier.
  }
}

export function clearPendingSignupCode(): void {
  try {
    sessionStorage.removeItem(PENDING_SIGNUP_CODE_KEY)
  } catch {
    // Nothing useful to do.
  }
}
