import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { MaterialIcon } from '../components/icons/MaterialIcon'
import { useLinkedInUpload } from '../contexts/LinkedInUploadContext'
import { useCreateJob } from '../hooks/useCreateJob'
import { useGroundworkProgress } from '../hooks/useGroundworkProgress'
import { ApiError, NetworkError, UploadRejectedError } from '../lib/apiClient'
import './GroundworkPage.css'

// Soft advisory threshold for the archive (ORPHEUS-86). A LinkedIn "Complete"
// export is typically 5–50 MB; the behavioral CSVs the parsers need are tiny.
// Rich media (images/video) is what bloats large archives, and none of it is
// used in scoring. Past this size the multipart upload is at elevated risk of
// dying mid-transfer at the edge before the server-side 200 MB cap can return
// a friendly error, so we warn — but don't block, since the real edge limit
// is unconfirmed and a legitimately large archive should still be submittable.
const LARGE_ARCHIVE_WARN_BYTES = 150 * 1024 * 1024 // 150 MB

// Fallback shown when the network drops the upload before any HTTP response.
const NETWORK_ERROR_MESSAGE =
  'We couldn’t reach the server, so your upload didn’t go through. This can ' +
  'happen with very large archives or an unstable connection. Your LinkedIn ' +
  '“Complete” archive only needs its data files — the photos and videos ' +
  'inside it aren’t used in your analysis — so re-downloading a smaller ' +
  'export can help. Please check your connection and try again.'

function formatMegabytes(bytes: number): string {
  return `${Math.round(bytes / (1024 * 1024))} MB`
}

const GENERIC_SUBMIT_ERROR = 'We couldn’t submit your data. Please try again.'

/**
 * Map a submit failure to client-facing copy. An UploadRejectedError is a
 * deterministic Storage 4xx (MIME/size/token — ORPHEUS-109) and surfaces
 * the service's own reason, never connection guidance; a NetworkError is a
 * transport-level death (the ORPHEUS-86 case) and gets connection-oriented
 * guidance; an ApiError carries FastAPI's `{detail}` for HTTPExceptions
 * (Basic-archive/stale/parse rejections etc.); anything else is generic.
 */
function resolveSubmitError(err: unknown): string {
  if (err instanceof UploadRejectedError) {
    return (
      `${err.message} The storage service said: “${err.reason}”. This ` +
      'isn’t a connection problem, so retrying the same file won’t help. ' +
      'If the message mentions the file’s type or size, re-downloading a ' +
      'fresh LinkedIn export usually resolves it — otherwise, please share ' +
      'this message with us so we can help.'
    )
  }
  if (err instanceof NetworkError) {
    return NETWORK_ERROR_MESSAGE
  }
  if (err instanceof ApiError && typeof err.body === 'object' && err.body) {
    return (err.body as { detail?: string }).detail ?? GENERIC_SUBMIT_ERROR
  }
  return GENERIC_SUBMIT_ERROR
}

/**
 * Groundwork Checklist — the hub the client returns to between the intake
 * questionnaire and each LinkedIn upload step. Ported from
 * orpheus-groundwork-v1.html.
 *
 * Per-item completion sources:
 *   - LinkedIn data items reflect the in-memory file state held in
 *     LinkedInUploadContext (ORPHEUS-16). Picked files survive route
 *     navigation but not a hard refresh.
 *   - Questionnaire completion is derived at read time from
 *     questionnaire_responses.answers (ORPHEUS-33, migration 010).
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

  // Soft, non-blocking warning for an unusually large archive (ORPHEUS-86).
  const largeArchive = !!archive && archive.size > LARGE_ARCHIVE_WARN_BYTES

  // Derived "all complete" using the live LinkedIn flags. Questionnaire
  // completion is a single derived boolean (see useGroundworkProgress).
  const allComplete =
    linkedInArchive && linkedInAnalytics && !!data?.questionnaireComplete

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
      setSubmitError(resolveSubmitError(err))
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
          wait. Your analysis begins as soon as all items are
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
            to="/questionnaire"
            title="Intake Questionnaire"
            complete={data?.questionnaireComplete ?? false}
          />
        </div>
      </div>

      <div className="groundwork-completion-row">
        {largeArchive && (
          <p className="groundwork-completion-warning" role="status">
            Your data archive is large ({formatMegabytes(archive!.size)}). A
            LinkedIn “Complete” export only needs its data files — the photos
            and videos inside it aren’t used in your analysis. You can still
            submit as-is, but if the upload fails, re-downloading a smaller
            export usually fixes it.
          </p>
        )}
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
        <span
          className={
            submitError
              ? 'groundwork-completion-note error'
              : 'groundwork-completion-note'
          }
          role={submitError ? 'alert' : undefined}
        >
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
        <MaterialIcon name="check" size={14} className="groundwork-check-mark" />
      </div>
      <div className="groundwork-item-content">
        <div className="groundwork-item-title-row">
          <span className="groundwork-item-title">{title}</span>
          {badge && <span className="groundwork-item-badge">{badge}</span>}
        </div>
      </div>
      <MaterialIcon name="chevron_right" size={20} className="groundwork-item-arrow" />
    </Link>
  )
}
