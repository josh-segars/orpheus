import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { signInWithLinkedIn, useSession } from '../lib/auth'
import './LoginPage.css'

/**
 * /login — single-purpose page that kicks off the LinkedIn OIDC flow.
 *
 * Renders no PortalLayout; the user is unauthenticated and the wordmark + a
 * single primary action are all they need. Errors returned from the OAuth
 * round trip arrive via the URL hash fragment (#error=...&error_description=...)
 * — typically because LinkedIn returned an unverified email and the
 * on_auth_user_created trigger refused to create the clients row.
 */
export function LoginPage() {
  const { status } = useSession()
  const location = useLocation()
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

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
    setErrorMessage(null)
    setSubmitting(true)
    try {
      await signInWithLinkedIn(`${window.location.origin}/`)
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
        <p className="login-blurb">
          Orpheus uses your LinkedIn account to authenticate you. We never post on your
          behalf, and your LinkedIn data is shared only as part of your existing engagement
          with Andrew.
        </p>

        {errorMessage && (
          <div className="login-error" role="alert">
            <div className="login-error-label">We could not sign you in</div>
            <div className="login-error-body">{errorMessage}</div>
          </div>
        )}

        <button
          type="button"
          className="login-button"
          onClick={handleClick}
          disabled={submitting || status === 'loading'}
        >
          {submitting ? 'Redirecting to LinkedIn…' : 'Continue with LinkedIn'}
        </button>

        <p className="login-fineprint">
          By continuing you agree to Orpheus’s confidentiality and data-handling
          terms (provided separately by Andrew).
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
