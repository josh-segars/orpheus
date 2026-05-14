import { FormEvent, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useSession } from '../../lib/auth'
import {
  AdvisorClient,
  useAdvisorClients,
} from '../../hooks/useAdvisorClients'
import {
  extractInviteErrorMessage,
  useInviteClient,
} from '../../hooks/useInviteClient'
import {
  extractResendErrorMessage,
  useResendInvitation,
} from '../../hooks/useResendInvitation'
import {
  extractSelfReportErrorMessage,
  useSelfReport,
} from '../../hooks/useSelfReport'
import './ClientsPage.css'

/**
 * /advisor/clients — the advisor's admin console for managing their
 * client roster (ORPHEUS-39).
 *
 * Three logical regions on a single page (decision locked in
 * Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md):
 *
 *   1. Header — page title + "Run my own report" button. Per the
 *      ticket's implementer-choice resolution, the self-report
 *      affordance is a top-of-page button rather than a row in the
 *      list. Clearer empty-state behaviour, simpler list rendering.
 *
 *   2. Invite form — two fields (display name + email), inline
 *      (not modal), posts to POST /clients/invite. Optimistic update
 *      inserts the pending row immediately; mutation hook rolls back
 *      on failure and invalidates the list on settle.
 *
 *   3. Client list — table-like layout per row, with invitation
 *      chip, latest-job chip, and per-row actions. Empty state
 *      replaces the list with a brief explainer when zero clients
 *      exist yet.
 *
 * Route protection: see App.tsx — wrapped by AdvisorRoute which
 * redirects non-advisors to /. ProtectedRoute (the upstream gate)
 * has already established that the caller has at least one of
 * is_advisor / is_client.
 */
export function ClientsPage() {
  const { session } = useSession()
  const navigate = useNavigate()
  const clientsQuery = useAdvisorClients()
  const inviteMutation = useInviteClient()
  const selfReportMutation = useSelfReport()

  // Banner state — invite/self-report results bubble up here. Cleared
  // when the advisor takes a new action or dismisses.
  const [banner, setBanner] = useState<
    { kind: 'success' | 'error'; message: string } | null
  >(null)

  // Form-local state. Two-field controlled form, no react-hook-form
  // for two inputs.
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')

  const clients = clientsQuery.data?.clients ?? []
  const hasSelfRow = useMemo(
    () => clients.some((c) => c.is_self),
    [clients],
  )

  // LinkedIn `name` claim from the Supabase session — used as the
  // default display name for the self-report row. The backend falls
  // back to the email local-part if we pass null.
  const linkedInName = (() => {
    const meta = session?.user?.user_metadata as
      | { name?: string; given_name?: string; family_name?: string }
      | undefined
    if (meta?.name && meta.name.trim()) return meta.name.trim()
    const composed = [meta?.given_name, meta?.family_name]
      .filter((v): v is string => Boolean(v && v.trim()))
      .join(' ')
    return composed || null
  })()

  const handleInviteSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBanner(null)
    const trimmedName = displayName.trim()
    const trimmedEmail = email.trim()
    if (!trimmedName || !trimmedEmail) {
      setBanner({
        kind: 'error',
        message: 'Please enter both a name and an email address.',
      })
      return
    }
    try {
      await inviteMutation.mutateAsync({
        display_name: trimmedName,
        email: trimmedEmail,
      })
      setBanner({
        kind: 'success',
        message: `Invitation sent to ${trimmedEmail}.`,
      })
      setDisplayName('')
      setEmail('')
    } catch (err) {
      setBanner({
        kind: 'error',
        message: extractInviteErrorMessage(err),
      })
    }
  }

  const handleSelfReport = async () => {
    setBanner(null)
    try {
      const result = await selfReportMutation.mutateAsync({
        display_name: linkedInName,
      })
      if (result.created) {
        setBanner({
          kind: 'success',
          message: 'Your self-report is ready. Heading to Groundwork.',
        })
      }
      // Navigate to / — SmartIndexRedirect routes to /welcome or
      // /groundwork depending on whether the advisor has dismissed
      // the welcome screen. On idempotent hits (created=false) we
      // still navigate; the user clicked the button, they want to
      // land in their own portal.
      navigate('/')
    } catch (err) {
      setBanner({
        kind: 'error',
        message: extractSelfReportErrorMessage(err),
      })
    }
  }

  return (
    <main className="advisor-clients-main">
      <header className="advisor-clients-header">
        <div className="advisor-clients-header-text">
          <h1 className="advisor-clients-title">Manage clients</h1>
          <p className="advisor-clients-intro">
            Invite clients, track their invitation status, and open
            their reports as jobs complete. Each invitation expires
            after 14 days; use Resend to issue a fresh link.
          </p>
        </div>
        {!hasSelfRow && (
          <button
            type="button"
            className="advisor-clients-self-report-btn"
            onClick={handleSelfReport}
            disabled={selfReportMutation.isPending}
          >
            {selfReportMutation.isPending
              ? 'Setting up…'
              : 'Run my own report'}
          </button>
        )}
      </header>

      {banner && (
        <div
          className={
            banner.kind === 'success'
              ? 'advisor-banner advisor-banner-success'
              : 'advisor-banner advisor-banner-error'
          }
          role={banner.kind === 'error' ? 'alert' : 'status'}
        >
          <span className="advisor-banner-text">{banner.message}</span>
          <button
            type="button"
            className="advisor-banner-dismiss"
            aria-label="Dismiss"
            onClick={() => setBanner(null)}
          >
            &times;
          </button>
        </div>
      )}

      <section className="advisor-invite-section">
        <h2 className="advisor-section-title">Invite a client</h2>
        <form
          className="advisor-invite-form"
          onSubmit={handleInviteSubmit}
          noValidate
        >
          <label className="advisor-invite-field">
            <span className="advisor-invite-label">Name</span>
            <input
              type="text"
              className="advisor-invite-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Jane Doe"
              maxLength={200}
              disabled={inviteMutation.isPending}
            />
          </label>
          <label className="advisor-invite-field">
            <span className="advisor-invite-label">Email</span>
            <input
              type="email"
              className="advisor-invite-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@example.com"
              maxLength={320}
              disabled={inviteMutation.isPending}
            />
          </label>
          <button
            type="submit"
            className="advisor-invite-submit"
            disabled={inviteMutation.isPending}
          >
            {inviteMutation.isPending ? 'Sending…' : 'Send invitation'}
          </button>
        </form>
      </section>

      {/*
        List section is suppressed entirely when there are zero
        clients — per ORPHEUS-39 spec ("no list shown" in the empty
        state). The page header's intro paragraph + the invite form
        above carry the empty-state message; surfacing a separate
        "Your clients" header with an empty card underneath would
        add visual noise without telling the user anything they
        don't already know.

        Loading and error states still render — those aren't the
        empty state, they're transient states that should be visible.
      */}
      {(clientsQuery.isLoading ||
        clientsQuery.isError ||
        clients.length > 0) && (
        <section className="advisor-list-section">
          <h2 className="advisor-section-title">Your clients</h2>
          <ClientListBody
            isLoading={clientsQuery.isLoading}
            isError={clientsQuery.isError}
            clients={clients}
          />
        </section>
      )}
    </main>
  )
}

// --------------------------------------------------------------------------- //
// List body — loading / error / populated
//
// The pure-empty case (no clients at all) is handled one level up by
// suppressing the whole section. This component only renders when at
// least one of {loading, error, populated} applies.
// --------------------------------------------------------------------------- //

interface ClientListBodyProps {
  isLoading: boolean
  isError: boolean
  clients: AdvisorClient[]
}

function ClientListBody({ isLoading, isError, clients }: ClientListBodyProps) {
  if (isLoading) {
    return (
      <div className="advisor-list-status">Loading your clients…</div>
    )
  }
  if (isError) {
    return (
      <div className="advisor-list-status advisor-list-status-error">
        We couldn’t load your client list. Refresh the page to try again.
      </div>
    )
  }

  return (
    <ul className="advisor-client-list" role="list">
      {clients.map((client) => (
        <ClientRow key={client.id} client={client} />
      ))}
    </ul>
  )
}

// --------------------------------------------------------------------------- //
// Per-row rendering
// --------------------------------------------------------------------------- //

interface ClientRowProps {
  client: AdvisorClient
}

function ClientRow({ client }: ClientRowProps) {
  const resendMutation = useResendInvitation()
  const [resendError, setResendError] = useState<string | null>(null)

  const handleResend = async () => {
    setResendError(null)
    try {
      await resendMutation.mutateAsync(client.id)
    } catch (err) {
      setResendError(extractResendErrorMessage(err))
    }
  }

  // Optimistic placeholder rows carry a tombstone id starting with
  // `optimistic-` (see useInviteClient). Hide action buttons on
  // those until the server confirms — they have no real id yet.
  const isOptimistic = client.id.startsWith('optimistic-')

  return (
    <li className="advisor-client-row">
      <div className="advisor-client-identity">
        <div className="advisor-client-name">
          {client.display_name}
          {client.is_self && (
            <span className="advisor-client-self-badge">You</span>
          )}
        </div>
        <div className="advisor-client-email">{client.email}</div>
      </div>

      <div className="advisor-client-status">
        <InvitationChip status={client.invitation_status} />
        <JobChip latest={client.latest_job} />
      </div>

      <div className="advisor-client-actions">
        {/*
         * "View report" is shown only for the advisor's own self-report
         * row right now. The GET /jobs/{id} endpoint requires
         * is_client(); an advisor-only session viewing a separate
         * client's job 403s. Advisor visibility into client jobs is its
         * own follow-up ticket.
         */}
        {client.is_self &&
          client.latest_job &&
          client.latest_job.status === 'complete' && (
            <Link
              to={`/jobs/${client.latest_job.id}`}
              className="advisor-row-action advisor-row-action-primary"
            >
              View report
            </Link>
          )}

        {!client.is_self &&
          !isOptimistic &&
          (client.invitation_status === 'pending' ||
            client.invitation_status === 'expired') && (
            <button
              type="button"
              className="advisor-row-action"
              onClick={handleResend}
              disabled={resendMutation.isPending}
            >
              {resendMutation.isPending ? 'Resending…' : 'Resend invitation'}
            </button>
          )}
      </div>

      {resendError && (
        <div className="advisor-row-error" role="alert">
          {resendError}
        </div>
      )}
    </li>
  )
}

interface InvitationChipProps {
  status: AdvisorClient['invitation_status']
}

function InvitationChip({ status }: InvitationChipProps) {
  const label =
    status === 'pending'
      ? 'Pending'
      : status === 'accepted'
        ? 'Accepted'
        : 'Expired'
  return (
    <span
      className={`advisor-chip advisor-chip-invitation advisor-chip-${status}`}
    >
      {label}
    </span>
  )
}

interface JobChipProps {
  latest: AdvisorClient['latest_job']
}

function JobChip({ latest }: JobChipProps) {
  if (!latest) {
    return (
      <span className="advisor-chip advisor-chip-job advisor-chip-job-none">
        No job yet
      </span>
    )
  }
  const label =
    latest.status === 'pending'
      ? 'Job pending'
      : latest.status === 'running'
        ? 'Analysing'
        : latest.status === 'complete'
          ? 'Report ready'
          : 'Job failed'
  return (
    <span
      className={`advisor-chip advisor-chip-job advisor-chip-job-${latest.status}`}
    >
      {label}
    </span>
  )
}
