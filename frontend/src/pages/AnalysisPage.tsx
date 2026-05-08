import { useEffect } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useJob } from '../hooks/useJob'
import './AnalysisPage.css'

/**
 * Analysis-in-Progress holding screen. Ported from orpheus-analysis.html.
 *
 * `useJob` auto-polls every 3s while the job's state is `pending` or
 * `running`. When the worker flips the job to `complete`, this page
 * navigates to the Signal Score (`/jobs/:jobId`) using `replace` so the
 * back button doesn't return the client to a stale polling page. On
 * `failed`, we surface the worker's error message and route the client
 * back to Groundwork to retry.
 *
 * Entry points to this route:
 *   - SmartIndexRedirect (App.tsx) when a pending/running job exists
 *   - GroundworkPage's submit handler on POST /jobs success
 *   - GroundworkPage's "already-pending" early return
 */
export function AnalysisPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { data: job, isLoading, error } = useJob(jobId)
  const navigate = useNavigate()

  // Auto-redirect to the Signal Score once the pipeline completes. Done
  // in an effect (not during render) so React Router gets a clean
  // commit before navigation. `replace` avoids a stale entry in history.
  useEffect(() => {
    if (job?.state === 'complete' && jobId) {
      navigate(`/jobs/${jobId}`, { replace: true })
    }
  }, [job?.state, jobId, navigate])

  // Defensive: SmartIndexRedirect and the Groundwork submit always
  // include a jobId, but a hand-crafted URL could miss it. Send those
  // back to the hub rather than rendering an empty polling page.
  if (!jobId) {
    return <Navigate to="/groundwork" replace />
  }

  if (isLoading) {
    return (
      <main className="main-interior">
        <div className="page-status">Loading your analysis status&hellip;</div>
      </main>
    )
  }

  if (error || !job) {
    return (
      <main className="main-interior">
        <div className="page-status">
          We couldn&rsquo;t check your analysis status. Please try again.
        </div>
        <div className="centered-button">
          <Link to="/groundwork" className="btn-secondary">
            Return to Groundwork
          </Link>
        </div>
      </main>
    )
  }

  if (job.state === 'failed') {
    return (
      <main className="main-interior">
        <div className="section-header">
          <div className="section-eyebrow">Analysis</div>
          <h1 className="section-title">Something went wrong with your analysis</h1>
        </div>
        <p className="section-intro">
          We weren&rsquo;t able to process your materials.
          {job.error ? (
            <>
              {' '}The system reported: <em>{job.error}</em>
            </>
          ) : (
            ' Please return to the Groundwork Checklist and try again.'
          )}
        </p>
        <div className="centered-button">
          <Link to="/groundwork" className="btn-secondary">
            Return to Groundwork
          </Link>
        </div>
      </main>
    )
  }

  if (job.state === 'complete') {
    // The effect above is mid-redirect — render a quiet placeholder so
    // we don't flash "Analysis in progress" copy for a frame.
    return (
      <main className="main-interior">
        <div className="page-status">
          Your analysis is complete &mdash; taking you to your Signal Score&hellip;
        </div>
      </main>
    )
  }

  // Default: state === 'pending' | 'running'. Faithful port of
  // orpheus-analysis.html. The status dots are decorative — the
  // section-title and -intro carry the meaning for screen readers.
  return (
    <main className="main-interior">
      <div className="section-header">
        <div className="section-eyebrow">Analysis</div>
        <h1 className="section-title">Your Analysis is Underway</h1>
      </div>

      <p className="section-intro">
        Your Groundwork is complete. Andrew is now reviewing your materials
        and preparing your Signal Score diagnostic. You will receive a
        message directly when your results are ready &mdash; typically
        within 48 hours.
      </p>

      <div className="analysis-status">
        <div className="status-dots" aria-hidden="true">
          <div className="status-dot"></div>
          <div className="status-dot"></div>
          <div className="status-dot"></div>
        </div>
        <div className="status-label">Analysis in progress</div>
      </div>

      <div className="info-notice">
        <div className="info-notice-text">
          <span className="info-notice-label">While You Wait</span>
          <div className="info-notice-body">
            If anything comes to mind that you&rsquo;d like to add to your
            questionnaire responses &mdash; a clarification, an example,
            something you forgot to mention &mdash; you can return to any
            section via the Groundwork Checklist and update your answers
            before the analysis is finalized.
          </div>
        </div>
      </div>

      <div className="centered-button">
        <Link to="/groundwork" className="btn-secondary">
          Return to Groundwork
        </Link>
      </div>
    </main>
  )
}
