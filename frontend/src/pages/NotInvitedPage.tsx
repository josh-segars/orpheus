import { useNavigate } from 'react-router-dom'

import { signOut } from '../lib/auth'
import './NotInvitedPage.css'

/**
 * /not-invited — the page ProtectedRoute redirects authenticated users
 * to when GET /session returns no role (advisor_id null AND client_id
 * null) or errors out.
 *
 * Two real-world causes that bring users here:
 *
 *   1. Expired invitation. The user clicked an old email link, signed
 *      in successfully against LinkedIn, but the backend's
 *      /accept-invitation rejected the expired token. They sit
 *      authenticated-but-not-linked until they get a fresh
 *      invitation from their advisor.
 *
 *   2. LinkedIn account mismatch they declined. The user was invited
 *      under one address but signed in to LinkedIn with another and
 *      declined the soft-confirmation card. The auth.users row
 *      exists but no clients row references it.
 *
 * Both cases are recovered by signing out + starting over (either
 * with the same LinkedIn account once their advisor re-issues, or
 * with a different LinkedIn account next time).
 *
 * Sits outside ProtectedRoute. The user IS authenticated when
 * reaching this page — ProtectedRoute literally sent them here —
 * so the sign-out button has a real session to terminate.
 */
export function NotInvitedPage() {
  const navigate = useNavigate()

  const handleSignOut = async () => {
    try {
      await signOut()
    } catch {
      // signOut errors aren't actionable from this UI; the
      // navigate still routes them out of the broken state.
    }
    navigate('/login', { replace: true })
  }

  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>

        <h1 className="login-title">We couldn't find your invitation</h1>
        <p className="login-blurb">
          You're signed in to LinkedIn, but Orpheus doesn't have an
          active profile linked to this account. This usually means
          one of two things:
        </p>

        <ul className="not-invited-causes">
          <li>
            Your invitation expired before you accepted it. Ask your
            advisor to send a fresh link.
          </li>
          <li>
            You signed in with a different LinkedIn account than the
            one you were invited under.
          </li>
        </ul>

        <button
          type="button"
          className="login-button"
          onClick={() => {
            void handleSignOut()
          }}
        >
          Sign out
        </button>

        <p className="login-fineprint">
          If you believe this is a mistake, please contact your advisor.
        </p>
      </div>
    </main>
  )
}
