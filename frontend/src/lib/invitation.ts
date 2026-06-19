/**
 * Shared invitation-flow constants and helpers (ORPHEUS-38, ORPHEUS-92).
 *
 * The invitation token has to survive the LinkedIn OAuth round trip
 * between /invite/:token (which kicks it off) and /invite/callback
 * (which retrieves it and calls POST /accept-invitation).
 *
 * As of ORPHEUS-92 the token rides the OAuth `redirectTo` URL as a
 * `?token=` query param, with sessionStorage retained as a fallback.
 * The URL is the source of truth because sessionStorage is per
 * browsing context: email and LinkedIn in-app browsers frequently hand
 * the OAuth hop off to the system browser or the LinkedIn app and
 * return to a *fresh* context where the stashed value is gone. That
 * dropped-token case was surfacing to real beta users as the callback's
 * "Invitation link incomplete" card, which they read as an expired
 * link. The URL survives the cross-context redirect; sessionStorage
 * stays as belt-and-suspenders for same-context flows.
 *
 * Tradeoff accepted: the token now appears in the address bar / history
 * on the callback page. The callback strips it from the URL via
 * history.replaceState once captured, and the token is single-use after
 * acceptance (status flips to 'accepted', blocking reuse by any other
 * user) and time-boxed by invitation_expires_at — so the residual
 * exposure window is small.
 */

export const PENDING_INVITATION_TOKEN_KEY = 'pendingInvitationToken'

/** Query-string key used to carry the token through the OAuth redirect. */
export const INVITATION_TOKEN_QUERY_KEY = 'token'

/**
 * Read the invitation token from the current URL's query string, if
 * present. This is the primary source post-ORPHEUS-92 because it
 * survives cross-context OAuth redirects that drop sessionStorage.
 */
export function readInvitationTokenFromUrl(
  search: string = window.location.search,
): string | null {
  const value = new URLSearchParams(search).get(INVITATION_TOKEN_QUERY_KEY)
  return value && value.length > 0 ? value : null
}

export function readPendingInvitationToken(): string | null {
  return sessionStorage.getItem(PENDING_INVITATION_TOKEN_KEY)
}

export function writePendingInvitationToken(token: string): void {
  sessionStorage.setItem(PENDING_INVITATION_TOKEN_KEY, token)
}

export function clearPendingInvitationToken(): void {
  sessionStorage.removeItem(PENDING_INVITATION_TOKEN_KEY)
}
