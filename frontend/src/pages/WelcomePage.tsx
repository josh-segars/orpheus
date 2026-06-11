import { Link } from 'react-router-dom'
import { useSession } from '../lib/auth'
import { markWelcomeSeen } from '../lib/welcomeFlag'
import './WelcomePage.css'

interface LinkedInUserMetadata {
  name?: string
  given_name?: string
}

/**
 * Welcome page — first screen the client lands on after sign-in, before
 * they've started Groundwork. Ported from orpheus-welcome-v6.html.
 *
 * The "Get Started" link writes a localStorage flag so the smart index
 * redirect (see App.tsx) skips Welcome on subsequent visits and routes the
 * client straight to Groundwork. The flag is intentionally per-device — it
 * only suppresses the welcome card, never any actual progress.
 */
export function WelcomePage() {
  const { session } = useSession()

  const meta = (session?.user?.user_metadata ?? {}) as LinkedInUserMetadata
  const firstName = pickFirstName(meta, session?.user?.email ?? '')

  return (
    <main className="welcome-main">
      <div className="welcome-hero">
        <span className="welcome-hero-line-1">Experience speaks.</span>
        <span className="welcome-hero-line-2">Make yours sing.</span>
      </div>

      <div className="welcome-cards-row">
        <div className="welcome-card-dark">
          <p className="welcome-card-dark-body">
            Welcome, {firstName}.
            <br />
            <br />
            You are about to lay the groundwork for a clear picture of how your
            professional presence is interpreted, resulting in a specific plan
            to ensure it reflects the credibility you&rsquo;ve earned.
            <br />
            <br />
            Take your time, and begin whenever you are ready.
          </p>
          <Link
            to="/groundwork"
            className="welcome-btn-start"
            onClick={markWelcomeSeen}
          >
            Get Started
          </Link>
        </div>

        <div className="welcome-cards-right">
          <div className="welcome-card-step">
            <div className="welcome-card-step-title">Groundwork</div>
            <p className="welcome-card-step-body">
              Submit a short questionnaire and data from your LinkedIn profile,
              allowing time for all materials to be ready before your
              diagnostic begins.
            </p>
          </div>
          <div className="welcome-card-step">
            <div className="welcome-card-step-title">Report</div>
            <p className="welcome-card-step-body">
              Your <em>report</em> measures how your professional presence
              is being interpreted across 4 dimensions, giving you a precise
              picture of where you stand and where you can strengthen your
              signal.
            </p>
          </div>
          <div className="welcome-card-step">
            <div className="welcome-card-step-title">Forward Brief</div>
            <p className="welcome-card-step-body">
              Your <em>Forward Brief</em> translates your report into a
              prioritized plan with specific steps to ensure your professional
              presence reflects the credibility you&rsquo;ve earned.
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}

function pickFirstName(meta: LinkedInUserMetadata, email: string): string {
  if (meta.given_name && meta.given_name.trim()) return meta.given_name.trim()
  if (meta.name && meta.name.trim()) {
    return meta.name.trim().split(/\s+/)[0] ?? meta.name.trim()
  }
  if (email) return email.split('@')[0]
  return 'there'
}
