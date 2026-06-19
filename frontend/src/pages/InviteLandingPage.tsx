import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { signInWithLinkedIn } from '../lib/auth'
import {
  INVITATION_TOKEN_QUERY_KEY,
  writePendingInvitationToken,
} from '../lib/invitation'

/**
 * /invite/:token — the public landing page reached by clicking the
 * email link.
 *
 * Side effects only: stash the token in sessionStorage so the
 * post-OAuth /invite/callback page can find it, then kick off the
 * LinkedIn OIDC round trip. The page never renders anything more than
 * a transient "Redirecting to LinkedIn…" notice because
 * supabase.auth.signInWithOAuth navigates the browser away within a
 * tick of being called.
 *
 * Public route — sits outside ProtectedRoute. The user is by
 * definition not authenticated yet (or, if they are, the OAuth flow
 * effectively refreshes their session against LinkedIn and they
 * still land on /invite/callback for invitation acceptance).
 *
 * The "no token" path renders an error state because react-router
 * shouldn't be able to reach this component without a :token segment,
 * but we'd rather show a friendly card than a blank screen if some
 * future routing change drops the param.
 */
export function InviteLandingPage() {
  const { token } = useParams<{ token: string }>()
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setErrorMessage('This invitation link is missing its token.')
      return
    }

    // Belt-and-suspenders for same-context flows; the URL param below
    // is the primary carrier post-ORPHEUS-92.
    writePendingInvitationToken(token)

    // Carry the token through the OAuth round trip on the redirect URL
    // so it survives cross-context redirects (in-app / mobile browsers)
    // that drop sessionStorage. Supabase's redirect allow-list uses a
    // `/**` wildcard, which covers the query string. (ORPHEUS-92)
    const callbackUrl = new URL(`${window.location.origin}/invite/callback`)
    callbackUrl.searchParams.set(INVITATION_TOKEN_QUERY_KEY, token)

    // No await — the redirect IS the success path. Errors bubble up
    // via the .catch below if Supabase can't initiate the OAuth flow.
    signInWithLinkedIn(callbackUrl.toString()).catch(
      (err: unknown) => {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : 'Could not start the LinkedIn sign-in flow.',
        )
      },
    )
  }, [token])

  if (errorMessage) {
    return (
      <main className="login-shell">
        <div className="login-card">
          <div className="login-wordmark">
            <span className="wordmark-orpheus">Orpheus</span>
            <span className="wordmark-social">Social</span>
          </div>
          <h1 className="login-title">Invitation problem</h1>
          <div className="login-error" role="alert">
            <div className="login-error-label">
              We could not start the sign-in flow
            </div>
            <div className="login-error-body">{errorMessage}</div>
          </div>
          <p className="login-fineprint">
            Please try the email link again, or ask your advisor to resend the
            invitation.
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>
        <h1 className="login-title">Redirecting to LinkedIn…</h1>
        <p className="login-blurb">
          We're sending you to LinkedIn to verify your identity. You'll come
          right back to Orpheus once you're signed in.
        </p>
      </div>
    </main>
  )
}
