import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  displayNameFromSession,
  extractSignupErrorMessage,
  useCompleteSignup,
} from '../hooks/useCompleteSignup'
import { apiPostJson } from '../lib/apiClient'
import {
  InAppBrowserNotice,
  useInAppBrowserGuard,
} from '../components/InAppBrowserNotice'
import { signInWithLinkedIn, useSession } from '../lib/auth'
import {
  CURRENT_PRIVACY_VERSION,
  CURRENT_TERMS_VERSION,
  PRIVACY_PATH,
  TERMS_PATH,
  TERMS_VERSION_QUERY_KEY,
  PRIVACY_VERSION_QUERY_KEY,
  writePendingTermsAcceptance,
} from '../lib/consent'
import {
  SIGNUP_CODE_QUERY_KEY,
  writePendingSignupCode,
} from '../lib/signup'
import './LoginPage.css'
import './SignupPage.css'

/**
 * /signup — public self-serve sign-up for beta (ORPHEUS-85).
 *
 * Revises the [2026-05-11] invitation-only decision: clients can now
 * create their own account, gated by a shared beta access code and
 * auto-assigned to the house advisor server-side.
 *
 * Two branches, one page:
 *
 *   * Unauthenticated (the normal case — a prospect arriving from a
 *     link): collect the access code + the ToS/Privacy acceptance,
 *     then kick off LinkedIn OIDC. Both the code and the accepted
 *     versions ride the OAuth `redirectTo` URL (the ORPHEUS-92
 *     carrier pattern; sessionStorage is the same-context fallback)
 *     and land on /signup/callback, which calls POST /signup/complete.
 *
 *   * Already authenticated (a neither-role user who bounced to
 *     /not-invited and clicked "sign up", or an expired-invitation
 *     holder): no OAuth needed — collect the code + acceptance and
 *     call POST /signup/complete directly, then enter the portal.
 *     The acceptance is posted straight to /consent/terms on success
 *     because TermsAcceptanceRecorder's once-per-mount effect has
 *     already run by the time this branch writes anything.
 *
 * The code is deliberately NOT validated pre-OAuth: there is no
 * unauthenticated validation endpoint (nothing to brute-force), and a
 * wrong code is recoverable post-OAuth — /signup/callback re-prompts
 * inline without re-running OAuth.
 *
 * An existing client who lands here by mistake is safe either way:
 * POST /signup/complete is an idempotent get-or-create (they get their
 * own row back, never a duplicate — ORPHEUS-83), and the crosslink
 * offers the sign-in path explicitly.
 */
export function SignupPage() {
  const { session, status } = useSession()
  const navigate = useNavigate()
  const completeMutation = useCompleteSignup()
  // Shareable-link prefill (ORPHEUS-129): /signup?code=ACME2027 seeds
  // the input so a business cohort gets one link instead of a link
  // plus a code to retype. Read once at mount; the user can still
  // edit or replace it.
  const [code, setCode] = useState(
    () => new URLSearchParams(window.location.search).get('code') ?? '',
  )
  const [accepted, setAccepted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [showAcceptPrompt, setShowAcceptPrompt] = useState(false)
  const [showCodePrompt, setShowCodePrompt] = useState(false)
  const { blocked, allowAnyway } = useInAppBrowserGuard()

  const isAuthenticated = status === 'authenticated'

  const validateForm = (): boolean => {
    let ok = true
    if (!code.trim()) {
      setShowCodePrompt(true)
      ok = false
    }
    if (!accepted) {
      setShowAcceptPrompt(true)
      ok = false
    }
    return ok
  }

  // ── Unauthenticated: kick off OAuth with the code on the URL ────────
  const handleContinueWithLinkedIn = async () => {
    if (!validateForm()) return
    setErrorMessage(null)
    setSubmitting(true)

    const trimmedCode = code.trim()

    // Same-context fallbacks; the redirect URL below is the primary
    // carrier because in-app browsers return in a fresh context
    // (ORPHEUS-92).
    writePendingSignupCode(trimmedCode)
    writePendingTermsAcceptance({
      termsVersion: CURRENT_TERMS_VERSION,
      privacyVersion: CURRENT_PRIVACY_VERSION,
    })

    const callbackUrl = new URL(`${window.location.origin}/signup/callback`)
    callbackUrl.searchParams.set(SIGNUP_CODE_QUERY_KEY, trimmedCode)
    callbackUrl.searchParams.set(TERMS_VERSION_QUERY_KEY, CURRENT_TERMS_VERSION)
    callbackUrl.searchParams.set(
      PRIVACY_VERSION_QUERY_KEY,
      CURRENT_PRIVACY_VERSION,
    )

    try {
      await signInWithLinkedIn(callbackUrl.toString())
      // signInWithOAuth navigates the browser away; nothing more to do.
    } catch (err) {
      setSubmitting(false)
      setErrorMessage(
        err instanceof Error
          ? err.message
          : 'Could not start the LinkedIn sign-in flow.',
      )
    }
  }

  // ── Authenticated: complete in place, no OAuth round trip ───────────
  const handleCompleteSignup = () => {
    if (!validateForm()) return
    setErrorMessage(null)
    completeMutation.mutate(
      {
        beta_code: code.trim(),
        display_name: displayNameFromSession(session),
      },
      {
        onSuccess: () => {
          // Record the acceptance the user just gave. Fire-and-forget,
          // matching TermsAcceptanceRecorder's non-blocking posture —
          // the backend endpoint is idempotent and a transient failure
          // must not hold the portal hostage.
          void apiPostJson('/consent/terms', {
            terms_version: CURRENT_TERMS_VERSION,
            privacy_version: CURRENT_PRIVACY_VERSION,
          }).catch(() => undefined)
          navigate('/', { replace: true })
        },
        onError: (err) => {
          setErrorMessage(extractSignupErrorMessage(err))
        },
      },
    )
  }

  const busy =
    submitting || completeMutation.isPending || status === 'loading'

  // ORPHEUS-130 — see LoginPage. The already-authenticated branch
  // below completes in place with no OAuth round trip and would
  // survive an in-app browser, but a prospect arriving here from a
  // shared /signup?code= link is the common case and cannot.
  if (blocked) {
    return <InAppBrowserNotice info={blocked} onContinueAnyway={allowAnyway} />
  }

  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>

        <h1 className="login-title">Sign up for the beta</h1>
        <p className="login-blurb">
          Orpheus is in closed beta — you'll need an access code to sign
          up. We use your LinkedIn account to verify who you are; how we
          collect, use, and protect your data is described in the
          documents below.
        </p>

        {errorMessage && (
          <div className="login-error" role="alert">
            <div className="login-error-label">We could not sign you up</div>
            <div className="login-error-body">{errorMessage}</div>
          </div>
        )}

        <div className="signup-code-field">
          <label className="signup-code-label" htmlFor="signup-beta-code">
            Beta access code
          </label>
          <input
            id="signup-beta-code"
            type="text"
            className="signup-code-input"
            placeholder="Enter your access code"
            value={code}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            onChange={(event) => {
              setCode(event.target.value)
              if (event.target.value.trim()) setShowCodePrompt(false)
            }}
          />
          {showCodePrompt && (
            <p className="login-consent-prompt" role="alert">
              Please enter your beta access code to continue.
            </p>
          )}
        </div>

        <div className="login-consent">
          <label className="login-consent-row" htmlFor="signup-accept-terms">
            <input
              id="signup-accept-terms"
              type="checkbox"
              className="login-consent-checkbox"
              checked={accepted}
              onChange={(event) => {
                setAccepted(event.target.checked)
                if (event.target.checked) setShowAcceptPrompt(false)
              }}
            />
            <span className="login-consent-label">
              I agree to the{' '}
              <a href={TERMS_PATH} target="_blank" rel="noopener noreferrer">
                Terms of Service
              </a>{' '}
              and the{' '}
              <a href={PRIVACY_PATH} target="_blank" rel="noopener noreferrer">
                Privacy Policy
              </a>
              .
            </span>
          </label>
          {showAcceptPrompt && (
            <p className="login-consent-prompt" role="alert">
              Please agree to the Terms of Service and Privacy Policy to
              continue.
            </p>
          )}
        </div>

        <button
          type="button"
          className="login-button"
          onClick={() => {
            if (isAuthenticated) {
              handleCompleteSignup()
            } else {
              void handleContinueWithLinkedIn()
            }
          }}
          disabled={busy}
        >
          {isAuthenticated
            ? completeMutation.isPending
              ? 'Completing sign-up…'
              : 'Complete sign-up'
            : submitting
              ? 'Redirecting to LinkedIn…'
              : 'Continue with LinkedIn'}
        </button>

        <p className="login-fineprint">
          Orpheus uses your LinkedIn account only to verify who you are. We
          never post on your behalf.
        </p>

        <p className="signup-crosslink">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </main>
  )
}
