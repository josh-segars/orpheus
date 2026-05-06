import { Link, useNavigate } from 'react-router-dom'
import { UploadArea } from '../../components/uploads/UploadArea'
import { useLinkedInUpload } from '../../contexts/LinkedInUploadContext'

/**
 * LinkedIn Data — Step 1 of 2: Request Your Data Archive.
 * Ported from orpheus-linkedin-step1.html.
 *
 * The user picks the LinkedIn ZIP via the upload zone; the File is held in
 * the LinkedInUploadContext (in-memory) until "My Groundwork is Complete"
 * triggers the multipart POST /jobs from the Groundwork page. Both action
 * buttons return to the checklist; "This Step is Complete" doesn't differ
 * from "Save My Progress" yet because per-step gating only depends on
 * whether a file is selected.
 */
export function LinkedInStep1Page() {
  const { archive, setArchive } = useLinkedInUpload()
  const navigate = useNavigate()

  const goToGroundwork = () => navigate('/groundwork')

  return (
    <main className="main-interior">
      <Link to="/groundwork" className="back-link">
        <span className="back-arrow">&#8249;</span> Groundwork Checklist
      </Link>

      <div className="section-header">
        <span className="section-eyebrow">LinkedIn Data &middot; Step 1 of 2</span>
        <h1 className="section-title">Request Your Data Archive</h1>
        <p className="section-intro">
          LinkedIn can export a comprehensive archive of your professional
          data including your profile, work history, connections, skills, and
          recommendations. This file forms the primary data input for your
          diagnostic and takes up to 24 hours for LinkedIn to prepare.
        </p>
      </div>

      <div className="info-notice">
        <div className="info-notice-text">
          <span className="info-notice-label">Plan ahead</span>
          <p className="info-notice-body">
            LinkedIn may take up to 24 hours to prepare your file. We
            recommend completing this step first so the rest of your
            Groundwork can happen while you wait.
          </p>
        </div>
      </div>

      <div className="steps">
        <Step
          n={1}
          title="Open Settings & Privacy"
          body={
            <>
              From any LinkedIn page, click your profile photo or the{' '}
              <strong>Me</strong> icon at the top of the screen. Select{' '}
              <strong>Settings &amp; Privacy</strong> from the dropdown menu.
            </>
          }
        />
        <Step
          n={2}
          title="Navigate to Download your data"
          body={
            <>
              In the left sidebar, select <strong>Data privacy</strong>. Then
              choose <strong>Download your data</strong> from the options
              that appear.
            </>
          }
        />
        <Step
          n={3}
          title="Select the full archive"
          body={
            <>
              Choose <strong>Download larger data archive</strong> — the
              first option. This includes your connections, profile,
              recommendations, and the full history LinkedIn holds on your
              account.
            </>
          }
        />
        <Step
          n={4}
          title="Request the archive"
          body={
            <>
              Click <strong>Request archive</strong>. The page will update to
              confirm your request and display a timestamp. You will receive
              an email from LinkedIn when your file is ready.
            </>
          }
          note="You can close this page while you wait. There is no need to leave it open."
        />
        <Step
          n={5}
          title="Return and download when ready"
          body={
            <>
              Once you receive LinkedIn&rsquo;s email notification, return to
              the same <strong>Download your data</strong> page. You will
              see a <strong>Download archive</strong> button listing the
              files included. Click it to save the ZIP file to your
              computer.
            </>
          }
        />
        <Step
          n={6}
          title="Upload your file below"
          body="Upload the ZIP file as downloaded. There is no need to extract or modify its contents."
        />
      </div>

      <UploadArea
        label="Upload your data archive"
        primary="Drop your file here or browse"
        secondary="Upload the ZIP file exactly as LinkedIn delivered it"
        fileTypeLabel="ZIP file"
        accept=".zip,application/zip,application/x-zip-compressed"
        file={archive}
        onFileChange={setArchive}
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
          disabled={!archive}
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
