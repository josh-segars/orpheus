import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { EmailMismatchConfirmation } from '../components/EmailMismatchConfirmation'
import {
  extractAcceptInvitationErrorMessage,
  useAcceptInvitation,
} from '../hooks/useAcceptInvitation'
import { signOut, useSession } from '../lib/auth'
import {
  clearPendingInvitationToken,
  readPendingInvitationToken,
} from '../lib/invitation'

/**
 * /invite/callback — the post-OAuth landing page in the invitation flow
 * (ORPHEUS-38).
 *
 * The user reaches this URL after LinkedIn OAuth completes. They ARE
 * authenticated (a Supabase session exists) but may not yet have a
 * clients row — that's the linkage step we're about to perform. The
 * page sits OUTSIDE ProtectedRoute because ProtectedRoute, post-
 * commit-10, gates on session roles via GET /session; an
 * authenticated-but-not-yet-invited user would bounce to
 * /not-invited before we got to accept the invitation.
 *
 * State machine (rendered cards):
 *
 *   ┌────────────────────────┬────────────────────────────────────┐
 *   │ Trigger                │ UI                                  │
 *   ├────────────────────────┼────────────────────────────────────┤
 *   │ session loading        │ "Finalizing your invitation…"      │
 *   │ no token               │ Error: re-click the email link     │
 *   │ unauthenticated        │ Error: OAuth didn't complete       │
 *   │ mutation pending       │ "Finalizing your invitation…"      │
 *   │ mutation success +     │ <Navigate to="/"/> (with cleanup)  │
 *   │   no mismatch          │                                    │
 *   │ mutation success +     │ EmailMismatchConfirmation          │
 *   │   requires_confirmation│                                    │
 *   │ mutation error         │ Error: backend detail + Sign out   │
 *   └────────────────────────┴────────────────────────────────────┘
 *
 * The token is read once at mount-time via useState's initializer.
 * Subsequent re-renders use the captured value so the mutation
 * remains addressable even after a successful clear.
 */
export function InviteCallbackPage() {
  const navigate = useNavigate()
  const { status: sessionStatus } = useSession()
  const acceptMutation = useAcceptInvitation()
  const [token] = useState<string | null>(() => readPendingInvitationToken())
  // Tracks whether we've already kicked off the initial accept call,
  // so we don't double-fire when react re-renders this component
  // before the first call's state propagates.
  const [hasInitialized, setHasInitialized] = useState(false)

  // Fire the first accept call once the Supabase session is ready
  // and we have a token. The mutation idempotency on the backend
  // would handle a duplicate call, but locking this here keeps
  // logs cleaner.
  useEffect(() => {
    if (hasInitialized) return
    if (sessionStatus !== 'authenticated') return
    if (!token) return
    setHasInitialized(true)
    acceptMutation.mutate({ token })
  }, [hasInitialized, sessionStatus, token, acceptMutation])

  // Success path: clear the stashed token once we have a non-mismatch
  // success response. The cleanup happens in an effect so we don't
  // mutate sessionStorage during render.
  const isSuccess =
    acceptMutation.isSuccess &&
    acceptMutation.data !== undefined &&
    !acceptMutation.data.requires_confirmation

  useEffect(() => {
    if (isSuccess) {
      clearPendingInvitationToken()
    }
  }, [isSuccess])

  // ── Error rendering helpers ──────────────────────────────────────

  if (!token) {
    return (
      <ErrorCard
        title="Invitation link incomplete"
        message="We could not find an invitation token. Please re-click the link in your invitation email and try again."
        primaryAction={{
          label: 'Go to sign in',
          onClick: () => navigate('/login', { replace: true }),
        }}
      />
    )
  }

  if (sessionStatus === 'unauthenticated') {
    return (
      <ErrorCard
        title="Sign-in didn't complete"
        message="LinkedIn didn't return a valid sign-in. Please re-click the link in your invitation email."
        primaryAction={{
          label: 'Go to sign in',
          onClick: () => navigate('/login', { replace: true }),
        }}
      />
    )
  }

  // ── Loading ─────────────────────────────────────────────────────

  if (
    sessionStatus === 'loading' ||
    acceptMutation.isPending ||
    !hasInitialized
  ) {
    return <LoadingCard />
  }

  // ── Mismatch confirmation ───────────────────────────────────────

  if (
    acceptMutation.data?.requires_confirmation &&
    acceptMutation.data.invitation_email &&
    acceptMutation.data.linkedin_email
  ) {
    return (
      <EmailMismatchConfirmation
        invitationEmail={acceptMutation.data.invitation_email}
        linkedinEmail={acceptMutation.data.linkedin_email}
        isConfirming={acceptMutation.isPending}
        onContinue={() => acceptMutation.mutate({ token, confirmed: true })}
        onCancel={async () => {
          clearPendingInvitationToken()
          try {
            await signOut()
          } catch {
            // signOut errors aren't user-actionable from this page;
            // the navigate below still routes them out.
          }
          navigate('/login', { replace: true })
        }}
      />
    )
  }

  // ── Error ───────────────────────────────────────────────────────

  if (acceptMutation.isError) {
    const message = extractAcceptInvitationErrorMessage(acceptMutation.error)
    return (
      <ErrorCard
        title="We could not finalize your invitation"
        message={message}
        primaryAction={{
          label: 'Sign out and try again',
          onClick: async () => {
            clearPendingInvitationToken()
            try {
              await signOut()
            } catch {
              // best-effort
            }
            navigate('/login', { replace: true })
          },
        }}
      />
    )
  }

  // ── Success: redirect to the portal root, which routes the user
  // to Welcome / Groundwork / Analysis / Score per SmartIndexRedirect.
  if (isSuccess) {
    return <Navigate to="/" replace />
  }

  // Catch-all (shouldn't reach in practice).
  return <LoadingCard />
}

// --------------------------------------------------------------------- //
// Internal cards
// --------------------------------------------------------------------- //

function LoadingCard() {
  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>
        <h1 className="login-title">Finalizing your invitation…</h1>
        <p className="login-blurb">
          We're linking your LinkedIn account to your client profile.
          This should only take a moment.
        </p>
      </div>
    </main>
  )
}

interface ErrorCardProps {
  title: string
  message: string
  primaryAction: { label: string; onClick: () => void | Promise<void> }
}

function ErrorCard({ title, message, primaryAction }: ErrorCardProps) {
  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>
        <h1 className="login-title">{title}</h1>
        <div className="login-error" role="alert">
          <div className="login-error-body">{message}</div>
        </div>
        <button
          type="button"
          className="login-button"
          onClick={() => {
            void primaryAction.onClick()
          }}
        >
          {primaryAction.label}
        </button>
      </div>
    </main>
  )
}
