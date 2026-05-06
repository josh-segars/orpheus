import { Link, useNavigate } from 'react-router-dom'
import { useGroundworkProgress } from '../hooks/useGroundworkProgress'
import './GroundworkPage.css'

/**
 * Groundwork Checklist — the hub the client returns to between every
 * questionnaire section and LinkedIn upload step. Ported from
 * orpheus-groundwork-v1.html.
 *
 * Per-item completion state is read from useGroundworkProgress(). Until
 * ORPHEUS-16 (LinkedIn uploads) and ORPHEUS-18 (questionnaire_responses)
 * land, every item renders as incomplete and the "My Groundwork is
 * Complete" CTA stays disabled — matching the prototype's empty state.
 */
export function GroundworkPage() {
  const { data, isLoading } = useGroundworkProgress()
  const navigate = useNavigate()

  // Render the checklist with empty progress while we wait for the first
  // round-trip. The prototype is a fully static page, so this is fine — no
  // skeleton needed beyond a tiny placeholder.
  const progress = data ?? null

  const handleComplete = () => {
    if (!progress?.allComplete) return
    if (progress.latestPendingJobId) {
      navigate(`/jobs/${progress.latestPendingJobId}/analysis`)
    } else {
      // ORPHEUS-16 will create the job inside the LinkedIn upload flow, so
      // by the time the checklist is fully complete the latest job should
      // already exist. This fallback exists so the button isn't a dead end
      // if state lags briefly.
      navigate('/analysis')
    }
  }

  return (
    <main className="groundwork-main">
      <div className="groundwork-page-header">
        <h1 className="groundwork-page-title">Groundwork Checklist</h1>
        <p className="groundwork-page-intro">
          Everything here forms the foundation of your diagnostic. Work
          through each item at your own pace and return as often as needed.
          Your progress is saved. We have placed the LinkedIn data requests
          first, as one step requires up to 24 hours for LinkedIn to prepare
          your files. Starting there now means the rest can happen while you
          wait. Your Signal Score analysis begins as soon as all items are
          complete.
        </p>
      </div>

      <div className="groundwork-checklist">
        <div className="groundwork-checklist-group">
          <div className="groundwork-group-label">LinkedIn Data</div>
          <ChecklistItem
            to="/linkedin/step1"
            title="Request Your Data Archive"
            badge="Up to 24 hours"
            complete={progress?.linkedInArchive ?? false}
          />
          <ChecklistItem
            to="/linkedin/step2"
            title="Export Your Analytics"
            complete={progress?.linkedInAnalytics ?? false}
          />
        </div>

        <div className="groundwork-checklist-group">
          <div className="groundwork-group-label">Questionnaire</div>
          <ChecklistItem
            to="/questionnaire/s1"
            title="Professional Identity"
            complete={progress?.questionnaireS1 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s2"
            title="Career Stage & Context"
            complete={progress?.questionnaireS2 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s3"
            title="Target Audiences"
            complete={progress?.questionnaireS3 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s4"
            title="Goals"
            complete={progress?.questionnaireS4 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s5"
            title="Current LinkedIn Relationship"
            complete={progress?.questionnaireS5 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s6"
            title="Voice & Style"
            complete={progress?.questionnaireS6 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s7"
            title="Practical Parameters"
            complete={progress?.questionnaireS7 ?? false}
          />
        </div>
      </div>

      <div className="groundwork-completion-row">
        {/*
          The prototype renders an `<a>`. We render a `<button>` because the
          target depends on whether a job already exists for this client, so
          we need to compute the destination at click time. Disabled state
          is reflected by the absence of the `.active` modifier — the
          prototype's `:not(.active)` selector keeps the cursor as
          not-allowed and opacity at 0.35.
        */}
        <button
          type="button"
          className={
            progress?.allComplete
              ? 'groundwork-btn-complete active'
              : 'groundwork-btn-complete'
          }
          onClick={handleComplete}
          disabled={!progress?.allComplete || isLoading}
        >
          My Groundwork is Complete
        </button>
        <span className="groundwork-completion-note">
          Available once all items above are complete.
        </span>
      </div>
    </main>
  )
}

interface ChecklistItemProps {
  to: string
  title: string
  badge?: string
  complete: boolean
}

function ChecklistItem({ to, title, badge, complete }: ChecklistItemProps) {
  return (
    <Link
      to={to}
      className={
        complete
          ? 'groundwork-checklist-item complete'
          : 'groundwork-checklist-item'
      }
    >
      <div className="groundwork-check-indicator">
        <span className="groundwork-check-mark">&#10003;</span>
      </div>
      <div className="groundwork-item-content">
        <div className="groundwork-item-title-row">
          <span className="groundwork-item-title">{title}</span>
          {badge && <span className="groundwork-item-badge">{badge}</span>}
        </div>
      </div>
      <div className="groundwork-item-arrow">&#8250;</div>
    </Link>
  )
}
