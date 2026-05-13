import './EmailMismatchConfirmation.css'

/**
 * Soft confirmation surfaced by InviteCallbackPage when the invitation
 * email differs from the LinkedIn email the user signed in with. The
 * mismatch is usually benign (work email vs personal LinkedIn) so we
 * ask rather than block (ORPHEUS-38 decision).
 *
 * Presentational only. The page wires Continue (re-call accept with
 * `confirmed: true`) and Cancel (sign-out + route to /login).
 */
export interface EmailMismatchConfirmationProps {
  invitationEmail: string
  linkedinEmail: string
  onContinue: () => void
  onCancel: () => void
  /** Disable buttons + show a "Confirming…" label on Continue. */
  isConfirming?: boolean
}

export function EmailMismatchConfirmation({
  invitationEmail,
  linkedinEmail,
  onContinue,
  onCancel,
  isConfirming = false,
}: EmailMismatchConfirmationProps) {
  return (
    <main className="login-shell">
      <div className="login-card mismatch-card">
        <div className="login-wordmark">
          <span className="wordmark-orpheus">Orpheus</span>
          <span className="wordmark-social">Social</span>
        </div>

        <h1 className="login-title">Confirm your invitation</h1>
        <p className="login-blurb">
          Your invitation went to one email address, but you signed in
          with another. This is usually fine — a work email gets the
          invite while LinkedIn is connected to a personal one — but
          please confirm before continuing.
        </p>

        <dl className="mismatch-grid">
          <div className="mismatch-row">
            <dt className="mismatch-label">Invitation sent to</dt>
            <dd className="mismatch-value">{invitationEmail}</dd>
          </div>
          <div className="mismatch-row">
            <dt className="mismatch-label">Signed in as</dt>
            <dd className="mismatch-value">{linkedinEmail}</dd>
          </div>
        </dl>

        <div className="mismatch-actions">
          <button
            type="button"
            className="login-button"
            onClick={onContinue}
            disabled={isConfirming}
          >
            {isConfirming ? 'Confirming…' : 'Continue'}
          </button>
          <button
            type="button"
            className="login-button mismatch-cancel"
            onClick={onCancel}
            disabled={isConfirming}
          >
            Sign out and try another account
          </button>
        </div>
      </div>
    </main>
  )
}
