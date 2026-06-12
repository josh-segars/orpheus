import { Link } from 'react-router-dom'
import { useJobs } from '../hooks/useJobs'
import type { JobSummary } from '../types/job'
import './ReportsPage.css'

/**
 * Reports list — the client's landing surface once they have at least
 * one report (ORPHEUS-81). One row per job, newest first: run date,
 * composite band chip (complete) or status (in flight / failed), and a
 * link into the report or the Analysis-in-Progress screen.
 *
 * "Run a New Report" re-enters the Groundwork flow. Each run needs
 * fresh LinkedIn uploads (data-retention: ingested data is deleted
 * after processing); questionnaire answers carry forward as editable
 * defaults, so that checklist item arrives already complete. The
 * button hides while a job is in flight — the backend enforces the
 * same single-in-flight-run guard with a 409 (POST /jobs).
 */
export function ReportsPage() {
  const { data: jobs, isLoading, isError } = useJobs()

  if (isLoading) {
    return (
      <main className="main-interior">
        <div className="page-status">Loading your reports&hellip;</div>
      </main>
    )
  }

  if (isError || !jobs) {
    return (
      <main className="main-interior">
        <div className="page-status">
          We couldn&rsquo;t load your reports. Please try again.
        </div>
      </main>
    )
  }

  const hasInFlight = jobs.some(
    (j) => j.state === 'pending' || j.state === 'running',
  )

  return (
    <main className="main-interior">
      <div className="section-header reports-header">
        <div>
          <div className="section-eyebrow">Reports</div>
          <h2 className="section-title">My Reports</h2>
        </div>
        {hasInFlight ? (
          <span className="reports-in-flight-note">
            A report is in progress
          </span>
        ) : (
          <Link to="/groundwork" className="btn-primary">
            Run a New Report
          </Link>
        )}
      </div>

      {jobs.length === 0 ? (
        <p className="section-intro">
          You haven&rsquo;t run a report yet. Head to your{' '}
          <Link to="/groundwork">Groundwork Checklist</Link> to get started.
        </p>
      ) : (
        <div className="reports-list">
          {jobs.map((job) => (
            <ReportRow key={job.id} job={job} />
          ))}
        </div>
      )}
    </main>
  )
}

function ReportRow({ job }: { job: JobSummary }) {
  const date = formatRunDate(job.created_at)

  if (job.state === 'complete') {
    return (
      <Link to={`/jobs/${job.id}`} className="report-row report-row-link">
        <span className="report-row-date">{date}</span>
        {job.band && (
          <span className={`report-band-chip ${bandChipClass(job.band)}`}>
            {job.band}
          </span>
        )}
        <span className="report-row-action">View report &rsaquo;</span>
      </Link>
    )
  }

  if (job.state === 'pending' || job.state === 'running') {
    return (
      <Link
        to={`/jobs/${job.id}/analysis`}
        className="report-row report-row-link"
      >
        <span className="report-row-date">{date}</span>
        <span className="report-status-chip report-status-in-progress">
          In progress
        </span>
        <span className="report-row-action">View progress &rsaquo;</span>
      </Link>
    )
  }

  // failed
  return (
    <div className="report-row">
      <span className="report-row-date">{date}</span>
      <span className="report-status-chip report-status-failed">
        Did not complete
      </span>
      <span className="report-row-note">
        You can run a new report from your Groundwork Checklist.
      </span>
    </div>
  )
}

function formatRunDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Band chip color class — same spectrum mapping as the report page's
 * band pills (ORPHEUS-70): Dissonant→pip-1 … Resonant→pip-5.
 */
const BAND_CHIP_CLASSES: Record<string, string> = {
  Dissonant: 'report-band-1',
  Untuned: 'report-band-2',
  Tuning: 'report-band-3',
  Tuned: 'report-band-4',
  Resonant: 'report-band-5',
}

function bandChipClass(band: string): string {
  return BAND_CHIP_CLASSES[band] ?? ''
}
