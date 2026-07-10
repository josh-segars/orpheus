import { Link, useNavigate } from 'react-router-dom'
import { UploadArea } from '../../components/uploads/UploadArea'
import { MaterialIcon } from '../../components/icons/MaterialIcon'
import { useLinkedInUpload } from '../../contexts/LinkedInUploadContext'

/**
 * LinkedIn Data — Step 2 of 2: Export Your Analytics.
 * Ported from orpheus-linkedin-step2.html.
 *
 * The user picks the LinkedIn analytics XLSX via the upload zone; the File
 * is held in the LinkedInUploadContext (in-memory) until "My Groundwork is
 * Complete" triggers the multipart POST /jobs from the Groundwork page.
 */
export function LinkedInStep2Page() {
  const { analytics, setAnalytics } = useLinkedInUpload()
  const navigate = useNavigate()

  const goToGroundwork = () => navigate('/groundwork')

  return (
    <main className="main-interior">
      <Link to="/groundwork" className="back-link">
        <MaterialIcon name="chevron_left" size={18} className="back-arrow" /> Groundwork Checklist
      </Link>

      <div className="section-header">
        <span className="section-eyebrow">LinkedIn Data &middot; Step 2 of 2</span>
        <h1 className="section-title">Export Your Analytics</h1>
        <p className="section-intro">
          LinkedIn makes a structured analytics export available that
          captures your post reach, audience demographics, follower data,
          and engagement history. This export takes only a moment to
          generate and downloads immediately.
        </p>
      </div>

      <div className="info-notice">
        <div className="info-notice-text">
          <span className="info-notice-label">Finding this page</span>
          <p className="info-notice-body">
            The analytics export is accessed through the{' '}
            <strong>Post impressions</strong> link in the left column of
            your LinkedIn feed. If you do not see it, you can navigate
            directly:{' '}
            <a
              href="https://www.linkedin.com/analytics/creator/content/"
              target="_blank"
              rel="noreferrer"
            >
              linkedin.com/analytics/creator/content
            </a>
          </p>
        </div>
      </div>

      <div className="steps">
        <Step
          n={1}
          title="Go to your LinkedIn feed"
          body={
            <>
              From any LinkedIn page, click <strong>Home</strong> in the top
              navigation to return to your feed.
            </>
          }
        />
        <Step
          n={2}
          title="Select Post impressions"
          body={
            <>
              In the left column of your feed, locate and click{' '}
              <strong>Post impressions</strong>. This opens the LinkedIn
              Analytics page for your content.
            </>
          }
        />
        <Step
          n={3}
          title="Set the date range to Past 365 days"
          body={
            <>
              Near the top of the analytics view, click the date range
              dropdown. Select <strong>Past 365 days</strong>, then click{' '}
              <strong>Show results</strong>.
            </>
          }
          note="Using a consistent date range ensures your diagnostic reflects a full year of activity rather than a narrow recent window."
        />
        <Step
          n={4}
          title="Export the file"
          body={
            <>
              Click the <strong>Export</strong> button in the upper right
              corner of the page. The file will download immediately as an
              Excel spreadsheet.
            </>
          }
        />
        <Step
          n={5}
          title="Upload your file below"
          body="Upload the Excel file as downloaded. The filename will reflect your name and the date of the export."
        />
      </div>

      <UploadArea
        label="Upload your analytics export"
        primary="Drop your file here or browse"
        secondary="Upload the Excel file exactly as LinkedIn delivered it"
        fileTypeLabel="XLSX file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file={analytics}
        onFileChange={setAnalytics}
      />

      <div className="actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={goToGroundwork}
        >
          Save My Progress
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={goToGroundwork}
          disabled={!analytics}
        >
          This Step is Complete
        </button>
      </div>
    </main>
  )
}

interface StepProps {
  n: number
  title: string
  body: React.ReactNode
  note?: string
}

function Step({ n, title, body, note }: StepProps) {
  return (
    <div className="step">
      <div className="step-number">{n}</div>
      <div className="step-content">
        <p className="step-title">{title}</p>
        <p className="step-body">{body}</p>
        {note && <p className="step-note">{note}</p>}
      </div>
    </div>
  )
}
