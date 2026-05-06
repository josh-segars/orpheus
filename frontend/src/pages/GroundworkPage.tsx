import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useLinkedInUpload } from '../contexts/LinkedInUploadContext'
import { useCreateJob } from '../hooks/useCreateJob'
import { useGroundworkProgress } from '../hooks/useGroundworkProgress'
import { ApiError } from '../lib/apiClient'
import './GroundworkPage.css'

/**
 * Groundwork Checklist — the hub the client returns to between every
 * questionnaire section and LinkedIn upload step. Ported from
 * orpheus-groundwork-v1.html.
 *
 * Per-item completion sources:
 *   - LinkedIn data items reflect the in-memory file state held in
 *     LinkedInUploadContext (ORPHEUS-16). Picked files survive route
 *     navigation but not a hard refresh.
 *   - Questionnaire sections reflect questionnaire_responses.section_completion
 *     (ORPHEUS-18, migration 009).
 *   - Latest pending/complete job is read from the jobs table.
 *
 * "My Groundwork is Complete" submits the multipart POST /jobs with both
 * files; on success we navigate to /jobs/:id/analysis (ORPHEUS-20). If the
 * client already has a pending job (re-clicking the button), we route them
 * straight to the existing analysis page without resubmitting.
 */
export function GroundworkPage() {
  const { data, isLoading } = useGroundworkProgress()
  const { archive, analytics, clear: clearUploads } = useLinkedInUpload()
  const createJob = useCreateJob()
  const navigate = useNavigate()
  const [submitError, setSubmitError] = useState<string | null>(null)

  // LinkedIn flags come from the in-memory upload context — overrides the
  // stub `false` values from useGroundworkProgress.
  const linkedInArchive = !!archive
  const linkedInAnalytics = !!analytics

  // Derived "all complete" using the live LinkedIn flags. Questionnaire
  // flags continue to come from the server-side row.
  const allComplete =
    linkedInArchive &&
    linkedInAnalytics &&
    !!data?.questionnaireS1 &&
    !!data?.questionnaireS2 &&
    !!data?.questionnaireS3 &&
    !!data?.questionnaireS4 &&
    !!data?.questionnaireS5 &&
    !!data?.questionnaireS6 &&
    !!data?.questionnaireS7

  const handleComplete = async () => {
    setSubmitError(null)

    // If we already have a pending job (e.g. user double-clicked or refreshed
    // between submit and navigation), just send them to its analysis page.
    if (data?.latestPendingJobId) {
      navigate(`/jobs/${data.latestPendingJobId}/analysis`)
      return
    }

    if (!archive || !analytics) {
      setSubmitError(
        'Please re-upload your LinkedIn files. The browser may have cleared them after a refresh.',
      )
      return
    }

    try {
      const job = await createJob.mutateAsync({ archive, analytics })
      // Drop the in-memory blobs once the server has them — they're no
      // longer needed and we don't want to keep them resident.
      clearUploads()
      navigate(`/jobs/${job.id}/analysis`)
    } catch (err) {
      const message =
        err instanceof ApiError && typeof err.body === 'object' && err.body
          ? // FastAPI returns { detail: "..." } for HTTPExceptions.
            ((err.body as { detail?: string }).detail ??
              'We couldn’t submit your data. Please try again.')
          : err instanceof Error
            ? err.message
            : 'We couldn’t submit your data. Please try again.'
      setSubmitError(message)
    }
  }

  const buttonDisabled =
    !allComplete || isLoading || createJob.isPending
  const buttonLabel = createJob.isPending
    ? 'Submitting…'
    : 'My Groundwork is Complete'

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
            complete={linkedInArchive}
          />
          <ChecklistItem
            to="/linkedin/step2"
            title="Export Your Analytics"
            complete={linkedInAnalytics}
          />
        </div>

        <div className="groundwork-checklist-group">
          <div className="groundwork-group-label">Questionnaire</div>
          <ChecklistItem
            to="/questionnaire/s1"
            title="Professional Identity"
            complete={data?.questionnaireS1 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s2"
            title="Career Stage & Context"
            complete={data?.questionnaireS2 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s3"
            title="Target Audiences"
            complete={data?.questionnaireS3 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s4"
            title="Goals"
            complete={data?.questionnaireS4 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s5"
            title="Current LinkedIn Relationship"
            complete={data?.questionnaireS5 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s6"
            title="Voice & Style"
            complete={data?.questionnaireS6 ?? false}
          />
          <ChecklistItem
            to="/questionnaire/s7"
            title="Practical Parameters"
            complete={data?.questionnaireS7 ?? false}
          />
        </div>
      </div>

      <div className="groundwork-completion-row">
        <button
          type="button"
          className={
            allComplete
              ? 'groundwork-btn-complete active'
              : 'groundwork-btn-complete'
          }
          onClick={handleComplete}
          disabled={buttonDisabled}
        >
          {buttonLabel}
        </button>
        <span className="groundwork-completion-note">
          {submitError
            ? submitError
            : 'Available once all items above are complete.'}
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
