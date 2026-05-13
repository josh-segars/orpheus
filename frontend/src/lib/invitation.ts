/**
 * Shared invitation-flow constants and helpers (ORPHEUS-38).
 *
 * The invitation token is briefly stashed in sessionStorage between
 * /invite/:token (which kicks off the LinkedIn OAuth round trip) and
 * /invite/callback (which retrieves it and calls POST /accept-invitation).
 *
 * Why sessionStorage rather than the URL? Two reasons:
 *   1. The OAuth redirect_to lands on a static path (/invite/callback) so
 *      Supabase's allow-list configuration stays simple. Passing the token
 *      back through the URL would require either a wildcard redirect or
 *      per-token configuration.
 *   2. We don't want the token re-appearing in the browser history or
 *      referer headers after acceptance.
 *
 * Limitation worth knowing about: sessionStorage is per-tab. If a user
 * opens the email link in one tab and LinkedIn redirects into a fresh
 * tab (rare but possible), the token won't survive. The manual e2e
 * exercises the normal path; if the rare case bites a real user, the
 * recovery is to re-click the email link in the same tab.
 */

export const PENDING_INVITATION_TOKEN_KEY = 'pendingInvitationToken'

export function readPendingInvitationToken(): string | null {
  return sessionStorage.getItem(PENDING_INVITATION_TOKEN_KEY)
}

export function writePendingInvitationToken(token: string): void {
  sessionStorage.setItem(PENDING_INVITATION_TOKEN_KEY, token)
}

export function clearPendingInvitationToken(): void {
  sessionStorage.removeItem(PENDING_INVITATION_TOKEN_KEY)
}
