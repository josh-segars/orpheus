import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

import { MaterialIcon } from '../components/icons/MaterialIcon'
import { useAdvisorClients } from '../hooks/useAdvisorClients'
import { useDeleteAccount } from '../hooks/useDeleteAccount'
import { useSessionRoles } from '../hooks/useSessionRoles'
import { signOut } from '../lib/auth'
import { ApiError, NetworkError } from '../lib/apiClient'
import './AccountPage.css'

/**
 * /account — account management (ORPHEUS-71 → ORPHEUS-42 / ORPHEUS-124).
 *
 * The full account-management surface (profile, subscription,
 * disconnect) is still ORPHEUS-42, beta-deferred. What ships now is the
 * Danger Zone: self-service account deletion (ORPHEUS-124), the ToS
 * §13.2 / Privacy Policy §12.1 promise and a LinkedIn API §4.4
 * obligation.
 *
 * Confirmation is an inline *typed* confirmation ("DELETE"), following
 * the app's no-browser-dialog posture (ORPHEUS-93's Resend pattern) —
 * no window.confirm.
 *
 * Advisors with a non-empty roster (any client row that isn't their own
 * is_self row) see the blocked explanation instead of the delete
 * control — the backend enforces the same guard with a 409, so this is
 * UX honesty rather than security.
 *
 * Post-success ordering matters: mutateAsync → best-effort signOut
 * (the server-side session may already be dead once the auth user is
 * gone — a rejection here must not resurrect an error state) → cache
 * clear → explicit navigate to /login carrying `state.accountDeleted`,
 * so the login screen can confirm the deletion before ProtectedRoute's
 * own session-null redirect (which carries no state) would have landed
 * there anyway.
 */

const CONFIRM_PHRASE = 'DELETE'

function resolveDeleteError(err: unknown): string {
  if (err instanceof NetworkError) {
    return (
      'We couldn’t reach the server, so nothing was deleted. Please ' +
      'check your connection and try again.'
    )
  }
  if (err instanceof ApiError && typeof err.body === 'object' && err.body) {
    const detail = (err.body as { detail?: string }).detail
    if (detail) {
      return detail
    }
  }
  return 'Something went wrong and your account was not deleted. Please try again.'
}

export function AccountPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const rolesQuery = useSessionRoles()
  const advisorClients = useAdvisorClients()
  const deleteAccount = useDeleteAccount()

  const [confirming, setConfirming] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const isAdvisor = Boolean(rolesQuery.data?.advisor_id)
  // A roster row blocks deletion unless it's the advisor's own is_self
  // row. `is_self` is computed server-side against auth.uid(), so it is
  // exactly the "user_id == caller" test the backend guard applies.
  const blockingClients = isAdvisor
    ? (advisorClients.data?.clients ?? []).filter((c) => !c.is_self)
    : []
  const blocked = isAdvisor && blockingClients.length > 0

  const handleConfirmDelete = async () => {
    setDeleteError(null)
    try {
      await deleteAccount.mutateAsync()
    } catch (err) {
      setDeleteError(resolveDeleteError(err))
      return
    }
    try {
      await signOut()
    } catch {
      // The auth user is already gone server-side; local session state
      // is cleared by the cache clear + navigation below either way.
    }
    queryClient.clear()
    navigate('/login', { replace: true, state: { accountDeleted: true } })
  }

  return (
    <main className="main-interior">
      <div className="section-header">
        <div className="section-eyebrow">Account</div>
        <h2 className="section-title">Manage your account</h2>
        <p className="section-intro">
          Profile and data management tools are still being built during
          the beta &mdash; for anything you need in the meantime, contact
          us at contact@orpheussocial.com. Deleting your account is
          available below.
        </p>
      </div>

      <section className="danger-zone" aria-labelledby="danger-zone-title">
        <h3 className="danger-zone-title" id="danger-zone-title">
          Delete my account
        </h3>
        {blocked ? (
          <p className="danger-zone-body">
            Your advisor roster still has {blockingClients.length}{' '}
            {blockingClients.length === 1 ? 'client' : 'clients'}. Deleting
            your account would destroy their reports too, so it&rsquo;s
            blocked while your roster is non-empty. Contact us at
            contact@orpheussocial.com to arrange a transfer or roster
            cleanup first.
          </p>
        ) : (
          <>
            <p className="danger-zone-body">
              This permanently deletes your account and everything
              attached to it: your reports, your questionnaire answers,
              and your uploaded LinkedIn files. It cannot be undone.
            </p>

            {!confirming && (
              <button
                type="button"
                className="danger-zone-button"
                onClick={() => {
                  setConfirming(true)
                  setConfirmText('')
                  setDeleteError(null)
                }}
              >
                Delete my account
              </button>
            )}

            {confirming && (
              <div className="danger-zone-confirm">
                <label
                  className="danger-zone-confirm-label"
                  htmlFor="delete-confirm-input"
                >
                  Type {CONFIRM_PHRASE} to confirm
                </label>
                <input
                  id="delete-confirm-input"
                  className="danger-zone-confirm-input"
                  type="text"
                  autoComplete="off"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                />
                <div className="danger-zone-confirm-actions">
                  <button
                    type="button"
                    className="danger-zone-button"
                    disabled={
                      confirmText !== CONFIRM_PHRASE ||
                      deleteAccount.isPending
                    }
                    onClick={handleConfirmDelete}
                  >
                    {deleteAccount.isPending
                      ? 'Deleting…'
                      : 'Permanently delete'}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={deleteAccount.isPending}
                    onClick={() => {
                      setConfirming(false)
                      setConfirmText('')
                      setDeleteError(null)
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {deleteError && (
              <div className="danger-zone-error" role="alert">
                {deleteError}
              </div>
            )}
          </>
        )}
      </section>

      <div className="actions">
        <Link to="/" className="btn-secondary">
          <MaterialIcon name="arrow_back" size={16} /> Back to my portal
        </Link>
      </div>
    </main>
  )
}
