import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import {
  displayNameFromSession,
  extractSignupErrorMessage,
  isWrongCodeError,
  useCompleteSignup,
} from '../hooks/useCompleteSignup'
import { signOut, useSession } from '../lib/auth'
import {
  clearPendingSignupCode,
  readPendingSignupCode,
  readSignupCodeFromUrl,
  SIGNUP_CODE_QUERY_KEY,
} from '../lib/signup'
import './LoginPage.css'
import './SignupPage.css'

/**
 * /signup/callback — the post-OAuth landing page in the self-serve
 * sign-up flow (ORPHEUS-85). Mirrors InviteCallbackPage's structure:
 * the user IS authenticated (a Supabase session exists) but has no
 * clients row yet — POST /signup/complete is the row-creation step,
 * which is why this page sits OUTSIDE ProtectedRoute (the neither-role
 * state would bounce to /not-invited before we could complete).
 *
 * State machine (rendered cards):
 *
 *   ┌────────────────────────┬────────────────────────────────────┐
 *   │ Trigger                │ UI                                  │
 *   ├────────────────────────┼────────────────────────────────────┤
 *   │ session loading        │ "Finalizing your sign-up…"         │
 *   │ unauthenticated        │ Error: OAuth didn't complete       │
 *   │ no code / wrong code   │ Code re-prompt card (no OAuth      │
 *   │   (403)                │   re-run — session persists)       │
 *   │ mutation pending       │ "Finalizing your sign-up…"         │
 *   │ mutation success       │ <Navigate to="/"/> (with cleanup)  │
 *   │ other mutation error   │ Error: backend detail + Sign out   │
 *   └────────────────────────┴────────────────────────────────────┘
 *
 * The code resolves URL-first (survives cross-context OAuth redirects,
 * ORPHEUS-92) with the sessionStorage stash as fallback, then is
 * stripped from the address bar. Unlike the invitation token, a
 * missing code is NOT a dead end: the user is already authenticated,
 * so we just ask for it again inline.
 */
export function SignupCallbackPage() {
  const navigate = useNavigate()
  const { session, status: sessionStatus } = useSession()
  const completeMutation = useCompleteSignup()
  // Captured once at mount so the value stays addressable after we
  // strip it from the URL below.
  const [initialCode] = useState<string | null>(
    () => readSignupCodeFromUrl() ?? readPendingSignupCode(),
  )
  // The re-prompt card's input. Seeded empty — it only renders after
  // the initial code was missing or rejected, and echoing a rejected
  // code back invites resubmitting the same typo.
  const [retryCode, setRetryCode] = useState('')

  // Strip the code from the address bar once captured, preserving the
  // hash — Supabase's implicit flow returns session tokens in the
  // fragment and parses them after this effect runs (the 2026-08-11
  // sign-in outage mechanism).
  useEffect(() => {
    if (typeof window === 'undefined') return
    const url = new URL(window.location.href)
    if (url.searchParams.has(SIGNUP_CODE_QUERY_KEY)) {
      url.searchParams.delete(SIGNUP_CODE_QUERY_KEY)
      window.history.replaceState(
        window.history.state,
        '',
        `${url.pathname}${url.search}${url.hash}`,
      )
    }
  }, [])

  const [hasInitialized, setHasInitialized] = useState(false)

  // Fire the first completion attempt once the session is ready and we
  // have a code. A missing code skips straight to the re-prompt card.
  useEffect(() => {
    if (hasInitialized) return
    if (sessionStatus !== 'authenticated') return
    if (!initialCode) return
    setHasInitialized(true)
    completeMutation.mutate({
      beta_code: initialCode,
      display_name: displayNameFromSession(session),
    })
  }, [hasInitialized, sessionStatus, initialCode, session, completeMutation])

  const isSuccess = completeMutation.isSuccess

  useEffect(() => {
    if (isSuccess) {
      clearPendingSignupCode()
    }
  }, [isSuccess])

  // ── Unauthenticated: OAuth didn't complete ──────────────────────────
  if (sessionStatus === 'unauthenticated') {
    return (
      <ErrorCard
        title="Sign-in didn't complete"
        message="LinkedIn didn't return a valid sign-in. Please start again from the sign-up page."
        primaryAction={{
          label: 'Back to sign-up',
          onClick: () => navigate('/signup', { replace: true }),
        }}
      />
    )
  }

  // ── Loading ─────────────────────────────────────────────────────────
  if (
    sessionStatus === 'loading' ||
    completeMutation.isPending ||
    (!hasInitialized && initialCode !== null)
  ) {
    return <LoadingCard />
  }

  // ── Success: enter the portal ───────────────────────────────────────
  if (isSuccess) {
    return <Navigate to="/" replace />
  }

  // ── Recoverable: no code arrived, or the code was rejected (403) ────
  // The user is authenticated, so re-prompting inline avoids an OAuth
  // re-run entirely.
  const wrongCode = completeMutation.isError && isWrongCodeError(completeMutation.error)
  if (initialCode === null || wrongCode) {
    return (
      <main className="login-shell">
        <div className="login-card">
          <div className="login-wordmark">
            <span className="wordmark-orpheus">Orpheus</span>
            <span className="wordmark-social">Social</span>
          </div>
          <h1 className="login-title">Enter your access code</h1>
          <p className="login-blurb">
            You're signed in — we just need your beta access code to
            finish setting up your account.
          </p>
          {wrongCode && (
            <div className="login-error" role="alert">
              <div className="login-error-label">
                That code didn't work
              </div>
              <div className="login-error-body">
                {extractSignupErrorMessage(completeMutation.error)}
              </div>
            </div>
          )}
          <div className="signup-code-field">
            <label className="signup-code-label" htmlFor="signup-retry-code">
              Beta access code
            </label>
            <input
              id="signup-retry-code"
              type="text"
              className="signup-code-input"
              placeholder="Enter your access code"
              value={retryCode}
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              onChange={(event) => setRetryCode(event.target.value)}
            />
          </div>
          <button
            type="button"
            className="login-button"
            disabled={!retryCode.trim() || completeMutation.isPending}
            onClick={() =>
              completeMutation.mutate({
                beta_code: retryCode.trim(),
                display_name: displayNameFromSession(session),
              })
            }
          >
            Complete sign-up
          </button>
          <p className="login-fineprint">
            Don't have a code? Sign-ups are limited during the beta —
            contact the person who pointed you at Orpheus.
          </p>
        </div>
      </main>
    )
  }

  // ── Unrecoverable error ─────────────────────────────────────────────
  if (completeMutation.isError) {
    return (
      <ErrorCard
        title="We could not complete your sign-up"
        message={extractSignupErrorMessage(completeMutation.error)}
        primaryAction={{
          label: 'Sign out and try again',
          onClick: async () => {
            clearPendingSignupCode()
            try {
              await signOut()
            } catch {
              // best-effort
            }
            navigate('/signup', { replace: true })
          },
        }}
      />
    )
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
        <h1 className="login-title">Finalizing your sign-up…</h1>
        <p className="login-blurb">
          We're setting up your Orpheus profile. This should only take a
          moment.
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
