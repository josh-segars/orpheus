import { useState } from 'react'
import { useParams } from 'react-router-dom'

import {
  InAppBrowserNotice,
  useInAppBrowserGuard,
} from '../components/InAppBrowserNotice'
import { signInWithLinkedIn } from '../lib/auth'
import {
  CURRENT_PRIVACY_VERSION,
  CURRENT_TERMS_VERSION,
  PRIVACY_PATH,
  TERMS_PATH,
  withAcceptanceParams,
  writePendingTermsAcceptance,
} from '../lib/consent'
import {
  INVITATION_TOKEN_QUERY_KEY,
  writePendingInvitationToken,
} from '../lib/invitation'
import './LoginPage.css'

/**
 * /invite/:token — the public landing page reached by clicking the
 * email link.
 *
 * ORPHEUS-132 changed what this page is. It used to be side effects
 * only: stash the token, call signInWithOAuth from an effect, and show
 * a transient "Redirecting to LinkedIn…" card that the browser
 * navigated away from within a tick. That made invitation the one
 * account-creating entry point with no consent gate — an invited client
 * could sign up, upload an archive and read a report having never been
 * shown the Terms of Service or the Privacy Policy. Since invitation is
 * how the entire advisory roster is onboarded, the covered paths
 * (/login, /signup) were the minority ones.
 *
 * So the redirect is now user-initiated, behind the same unticked-by-
 * default checkbox those two pages use. The cost is one extra click on
 * a link the recipient expected to be instant; the return is an
 * affirmative act we can actually point at. A pre-ticked box would keep
 * the click and lose the point of having it.
 *
 * The acceptance rides the OAuth `redirectTo` query string alongside the
 * invitation token — see lib/consent.ts for why the URL beats
 * sessionStorage as the carrier, and lib/invitation.ts for the same
 * lesson learned the hard way on the token (ORPHEUS-92). Nothing
 * downstream needed changing: captureTermsAcceptanceFromUrl runs at
 * module load on whatever route the hop returns to and strips only its
 * own params, and TermsAcceptanceRecorder sits outside <Routes> so it
 * fires on /invite/callback while the caller still has no clients row.
 *
 * Public route — sits outside ProtectedRoute. The user is by definition
 * not authenticated yet (or, if they are, the OAuth flow effectively
 * refreshes their session against LinkedIn and they still land on
 * /invite/callback for invitation acceptance).
 *
 * LoginPage.css is imported explicitly rather than inherited: this page
 * has always used its .login-* scaffold, but only ever received it
 * transitively through InAppBrowserNotice. That was luck, and it now
 * has to carry the .login-consent rules too.
 */
export function InviteLandingPage() {
  const { token } = useParams<{ token: string }>()
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [showAcceptPrompt, setShowAcceptPrompt] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const { blocked, allowAnyway } = useInAppBrowserGuard()

  // ORPHEUS-130: inside an app's built-in browser the LinkedIn hop
  // cannot complete — the host app intercepts its own domain and drops
  // the user on a feed with no error and no way back. This page is the
  // one most often opened that way, straight out of a DM or an email.
  //
  // Note for anyone maintaining this: the `isBlocked` primitive the
  // previous version derived for an effect dependency array is gone
  // along with the effect. `blocked` is a fresh object every render, so
  // if an effect ever returns here, derive the primitive again rather
  // than putting `blocked` in the deps.
  if (blocked) {
    return <InAppBrowserNotice info={blocked} onContinueAnyway={allowAnyway} />
  }

  // react-router shouldn't be able to match this route without a :token
  // segment, but a friendly card beats a blank screen if some future
  // routing change drops the param.
  const missingToken = !token

  const handleContinue = async () => {
    if (!token) return
    // Belt to the disabled button's braces: if the box somehow isn't
    // ticked, say why rather than failing silently.
    if (!accepted) {
      setShowAcceptPrompt(true)
      return
    }
    setErrorMessage(null)
    setSubmitting(true)

    // Same-context fallbacks. The redirect URL below is the primary
    // carrier for both values, because in-app and email browsers hand
    // the OAuth hop to a fresh browsing context where sessionStorage is
    // gone (ORPHEUS-92).
    writePendingInvitationToken(token)
    writePendingTermsAcceptance({
      termsVersion: CURRENT_TERMS_VERSION,
      privacyVersion: CURRENT_PRIVACY_VERSION,
    })

    const callbackUrl = withAcceptanceParams(
      new URL(`${window.location.origin}/invite/callback`),
    )
    callbackUrl.searchParams.set(INVITATION_TOKEN_QUERY_KEY, token)

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

  if (missingToken) {
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
            <div className="login-error-body">
              This invitation link is missing its token.
            </div>
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

        <h1 className="login-title">Accept your invitation</h1>
        <p className="login-blurb">
          You've been invited to Orpheus. We use your LinkedIn account to
          verify who you are; how we collect, use, and protect your data is
          described in the documents below.
        </p>

        {errorMessage && (
          <div className="login-error" role="alert">
            <div className="login-error-label">
              We could not start the sign-in flow
            </div>
            <div className="login-error-body">{errorMessage}</div>
          </div>
        )}

        <div className="login-consent">
          <label className="login-consent-row" htmlFor="invite-accept-terms">
            <input
              id="invite-accept-terms"
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
          onClick={() => void handleContinue()}
          disabled={!accepted || submitting}
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
