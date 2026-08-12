import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'

import { signInWithLinkedIn, useSession } from '../lib/auth'
import {
  CURRENT_PRIVACY_VERSION,
  CURRENT_TERMS_VERSION,
  PRIVACY_PATH,
  TERMS_PATH,
  buildAcceptanceRedirectUrl,
  writePendingTermsAcceptance,
} from '../lib/consent'
import './LoginPage.css'

/**
 * /login — single-purpose page that kicks off the LinkedIn OIDC flow.
 *
 * Renders no PortalLayout; the user is unauthenticated and the wordmark + a
 * single primary action are all they need. Errors returned from the OAuth
 * round trip arrive via the URL hash fragment (#error=...&error_description=...)
 * — typically because LinkedIn returned an unverified email and the
 * on_auth_user_created trigger refused to create the clients row.
 *
 * ORPHEUS-126: signing in requires ticking the ToS + Privacy Policy
 * checkbox, which replaces the old "provided separately by Andrew" fine
 * print. The box is unticked by default (a pre-ticked box is not a clear
 * affirmative act) and gates the sign-in button. Because the affirmative act
 * happens here — pre-authentication — the accepted versions ride the OAuth
 * `redirectTo` query string and are recorded on the way back by
 * TermsAcceptanceRecorder. See lib/consent.ts for why the URL rather than
 * sessionStorage is the primary carrier (ORPHEUS-92's lesson).
 *
 * The document links open in a new tab on purpose: a same-tab navigation
 * from here would unmount this page and lose the ticked state, so reading
 * the terms would silently cost the user their checkbox.
 */
export function LoginPage() {
  const { status } = useSession()
  const location = useLocation()
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [showAcceptPrompt, setShowAcceptPrompt] = useState(false)

  // Set by AccountPage's post-deletion redirect (ORPHEUS-124). Router
  // state rather than a query param so a shared/bookmarked URL can't
  // replay the notice.
  const accountDeleted = Boolean(
    (location.state as { accountDeleted?: boolean } | null)?.accountDeleted,
  )

  // Pull error info out of the URL hash on first render. Supabase populates
  // both ?error and #error depending on how the upstream provider replies;
  // we look in both places.
  useEffect(() => {
    const message = parseAuthError(location.hash, location.search)
    if (message) {
      setErrorMessage(message)
      // Clean the URL so a refresh doesn't replay the error banner.
      window.history.replaceState(null, '', location.pathname)
    }
  }, [location.hash, location.search, location.pathname])

  // If we're already signed in, jump straight to the portal.
  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  const handleClick = async () => {
    // Belt to the disabled button's braces: if the box somehow isn't
    // ticked, say why rather than failing silently.
    if (!accepted) {
      setShowAcceptPrompt(true)
      return
    }
    setErrorMessage(null)
    setSubmitting(true)

    // Same-context fallback; the redirect URL below is the primary carrier
    // because in-app browsers return in a fresh context (ORPHEUS-92).
    writePendingTermsAcceptance({
      termsVersion: CURRENT_TERMS_VERSION,
      privacyVersion: CURRENT_PRIVACY_VERSION,
    })

    try {
      await signInWithLinkedIn(buildAcceptanceRedirectUrl())
      // signInWithOAuth navigates the browser away; nothing more to do.
    } catch (err) {
      setSubmitting(false)
      setErrorMessage(
        err instanceof Error ? err.message : 'Could not start the LinkedIn sign-in flow.',
      )
    }
  }

  return (
    <main className="login-shell">
      <div className="login-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>

        <h1 className="login-title">Sign in to your portal</h1>
        {/* ORPHEUS-125: the last advisory-era sentence ("…your existing
            engagement with Andrew") retired — the product is self-serve
            and the documents linked below now say what actually happens
            to the data. */}
        <p className="login-blurb">
          Orpheus uses your LinkedIn account to authenticate you. How we
          collect, use, and protect your data is described in the documents
          below.
        </p>

        {accountDeleted && (
          <div className="login-notice" role="status">
            <div className="login-notice-label">Account deleted</div>
            <div className="login-notice-body">
              Your account and its data have been deleted. Thanks for
              trying Orpheus Social.
            </div>
          </div>
        )}

        {errorMessage && (
          <div className="login-error" role="alert">
            <div className="login-error-label">We could not sign you in</div>
            <div className="login-error-body">{errorMessage}</div>
          </div>
        )}

        {/* ORPHEUS-85/129: self-serve sign-up is the primary acquisition
            path during the beta, so it gets a first-class panel above the
            sign-in machinery rather than a fine-print crosslink
            [Josh, 2026-08-12]. Same visual family as .login-notice —
            accent-toned, good news, not a caution. */}
        <div className="login-signup-panel">
          <div className="login-signup-label">New to Orpheus?</div>
          <div className="login-signup-body">
            The beta is open — if you have an access code, you can create
            your account in about a minute.
          </div>
          <Link to="/signup" className="login-signup-button">
            Sign up with an access code
          </Link>
        </div>

        <div className="login-consent">
          <label className="login-consent-row" htmlFor="login-accept-terms">
            <input
              id="login-accept-terms"
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
          onClick={handleClick}
          disabled={!accepted || submitting || status === 'loading'}
        >
          {submitting ? 'Redirecting to LinkedIn…' : 'Continue with LinkedIn'}
        </button>

        <p className="login-fineprint">
          Orpheus uses your LinkedIn account only to verify who you are. We
          never post on your behalf.
        </p>
      </div>
    </main>
  )
}

/**
 * Parse Supabase's OAuth error envelope from the URL.
 *
 * Format examples:
 *   #error=server_error&error_description=Database+error...
 *   ?error=access_denied&error_description=The+user+cancelled
 *
 * Special-case the verification-gate path: our `on_auth_user_created`
 * trigger raises with the literal phrase "email_verified=false" when LinkedIn
 * reports an unverified address. Translate that into a friendlier message
 * the executive on the other side can act on.
 */
function parseAuthError(hash: string, search: string): string | null {
  const fromHash = hash.startsWith('#') ? hash.slice(1) : hash
  const fromSearch = search.startsWith('?') ? search.slice(1) : search
  const params = new URLSearchParams(fromHash || fromSearch)
  const errorCode = params.get('error') ?? params.get('error_code')
  const description = params.get('error_description')

  if (!errorCode && !description) {
    return null
  }

  const decoded = description ? description.replace(/\+/g, ' ') : ''

  if (decoded.toLowerCase().includes('email_verified=false')) {
    return (
      'LinkedIn reported your email address as unverified. Please verify your ' +
      'email on LinkedIn (Settings → Sign in & security → Email addresses) and ' +
      'try again.'
    )
  }

  if (errorCode === 'access_denied') {
    return 'Sign-in was cancelled before LinkedIn returned a response. Please try again.'
  }

  return decoded || `Sign-in failed (${errorCode ?? 'unknown error'}).`
}
