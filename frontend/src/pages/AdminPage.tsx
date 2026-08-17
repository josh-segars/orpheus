/**
 * /admin — email-allowlisted stopgap surface (ORPHEUS-31).
 *
 * Two-pane workflow:
 *
 *   * Left: clients table (every clients row across all advisors,
 *     with owning advisor + latest-job chips). Selecting a row
 *     filters the right pane to that client's jobs.
 *
 *   * Right: jobs for the selected client (or "all jobs" when nothing
 *     is selected). Each job exposes its narratives as a
 *     section picker; selecting a narrative opens the inline editor
 *     in the bottom panel.
 *
 * Route gate: `AdminRoute` in App.tsx redirects non-admins to / so a
 * non-allowlisted client doesn't see the page chrome at all. The
 * backend re-enforces the same allowlist via `get_current_admin`.
 *
 * Intentionally lo-fi visual treatment — this is a stopgap until the
 * separate advisor-auth decision lands. Shared design tokens are
 * still used so the page doesn't look out-of-place next to the rest
 * of the portal.
 */
import { FormEvent, Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  AdminClient,
  AdminJob,
  AdminNarrativeMeta,
  AdminSignupCode,
  AdminWaitlistEntry,
  extractAdminErrorMessage,
  useAdminClients,
  useAdminCodeRedemptions,
  useAdminCodes,
  useAdminJobs,
  useAdminNarrative,
  useAdminWaitlist,
  useCreateAdminCode,
  useUpdateAdminCode,
  useUpdateAdminNarrative,
} from '../hooks/useAdmin'
import './AdminPage.css'

export function AdminPage() {
  const clientsQuery = useAdminClients()
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [selectedNarrativeId, setSelectedNarrativeId] = useState<string | null>(
    null,
  )
  const jobsQuery = useAdminJobs(selectedClientId)

  return (
    <main className="admin-main">
      <header className="admin-header">
        <h1 className="admin-title">Admin console</h1>
        <p className="admin-intro">
          God-mode view of every client and job in the system. Stopgap
          surface — narrative edits write straight to <code>public.narratives</code>;
          there is no draft state beyond what you save.
        </p>
      </header>

      <section className="admin-section">
        <h2 className="admin-section-title">Clients</h2>
        <ClientsTable
          isLoading={clientsQuery.isLoading}
          isError={clientsQuery.isError}
          errorMessage={
            clientsQuery.isError
              ? extractAdminErrorMessage(clientsQuery.error)
              : null
          }
          clients={clientsQuery.data?.clients ?? []}
          selectedClientId={selectedClientId}
          onSelect={(id) => {
            setSelectedClientId(id)
            setSelectedNarrativeId(null)
          }}
        />
      </section>

      <section className="admin-section">
        <h2 className="admin-section-title">
          {selectedClientId ? 'Jobs (filtered)' : 'Jobs (all)'}
          {selectedClientId && (
            <button
              type="button"
              className="admin-clear-filter-btn"
              onClick={() => {
                setSelectedClientId(null)
                setSelectedNarrativeId(null)
              }}
            >
              Clear filter
            </button>
          )}
        </h2>
        <JobsTable
          isLoading={jobsQuery.isLoading}
          isError={jobsQuery.isError}
          errorMessage={
            jobsQuery.isError ? extractAdminErrorMessage(jobsQuery.error) : null
          }
          jobs={jobsQuery.data?.jobs ?? []}
          selectedNarrativeId={selectedNarrativeId}
          onSelectNarrative={setSelectedNarrativeId}
        />
      </section>

      {selectedNarrativeId && (
        <section className="admin-section">
          <h2 className="admin-section-title">Narrative editor</h2>
          <NarrativeEditor
            narrativeId={selectedNarrativeId}
            onClose={() => setSelectedNarrativeId(null)}
          />
        </section>
      )}

      <CodesSection />

      <WaitlistSection />
    </main>
  )
}

// --------------------------------------------------------------------------- //
// Sign-up codes (ORPHEUS-129) — generate / list / disable access codes
// --------------------------------------------------------------------------- //

function CodesSection() {
  const codesQuery = useAdminCodes()
  const createMutation = useCreateAdminCode()
  const updateMutation = useUpdateAdminCode()

  const [label, setLabel] = useState('')
  const [vanityCode, setVanityCode] = useState('')
  const [advisorId, setAdvisorId] = useState('')
  const [maxUses, setMaxUses] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  // The most recently minted code, surfaced prominently so the admin
  // can copy it without hunting the table.
  const [mintedCode, setMintedCode] = useState<AdminSignupCode | null>(null)

  const codes = codesQuery.data?.codes ?? []

  const handleCreate = (event: FormEvent) => {
    event.preventDefault()
    setFormError(null)
    const trimmedLabel = label.trim()
    if (!trimmedLabel) {
      setFormError('A label is required — what is this code for?')
      return
    }
    const parsedMaxUses = maxUses.trim() ? Number(maxUses.trim()) : null
    if (parsedMaxUses !== null && (!Number.isInteger(parsedMaxUses) || parsedMaxUses <= 0)) {
      setFormError('Max uses must be a positive whole number (or blank for unlimited).')
      return
    }
    createMutation.mutate(
      {
        label: trimmedLabel,
        code: vanityCode.trim() || null,
        advisor_id: advisorId.trim() || null,
        // <input type="date"> yields YYYY-MM-DD, a valid ISO 8601 date —
        // the backend stores it as midnight UTC on that day.
        expires_at: expiresAt.trim() || null,
        max_uses: parsedMaxUses,
      },
      {
        onSuccess: (created) => {
          setMintedCode(created)
          setLabel('')
          setVanityCode('')
          setAdvisorId('')
          setMaxUses('')
          setExpiresAt('')
        },
        onError: (err) => {
          setFormError(extractAdminErrorMessage(err))
        },
      },
    )
  }

  return (
    <section className="admin-section">
      <h2 className="admin-section-title">
        Sign-up codes
        {!codesQuery.isLoading && !codesQuery.isError && (
          <span className="admin-waitlist-stats">
            {codes.length} code{codes.length === 1 ? '' : 's'}
            {' · '}
            {codes.reduce((sum, c) => sum + c.redemption_count, 0)} redemptions
          </span>
        )}
      </h2>

      <form className="admin-codes-form" onSubmit={handleCreate}>
        <input
          type="text"
          className="admin-codes-input"
          placeholder="Label (required) — e.g. Closed beta"
          aria-label="Code label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <input
          type="text"
          className="admin-codes-input"
          placeholder="Vanity code (blank = generate)"
          aria-label="Vanity code"
          value={vanityCode}
          onChange={(e) => setVanityCode(e.target.value)}
        />
        <input
          type="text"
          className="admin-codes-input"
          placeholder="Routing advisor id (blank = house)"
          aria-label="Routing advisor id"
          value={advisorId}
          onChange={(e) => setAdvisorId(e.target.value)}
        />
        <input
          type="text"
          className="admin-codes-input admin-codes-input-narrow"
          placeholder="Max uses"
          aria-label="Max uses"
          value={maxUses}
          onChange={(e) => setMaxUses(e.target.value)}
        />
        <input
          type="date"
          className="admin-codes-input admin-codes-input-narrow"
          aria-label="Expires on"
          title="Expires on (blank = never)"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
        />
        <button
          type="submit"
          className="admin-codes-create"
          disabled={createMutation.isPending}
        >
          {createMutation.isPending ? 'Creating…' : 'Create code'}
        </button>
      </form>

      {formError && (
        <div className="admin-status admin-status-error" role="alert">
          {formError}
        </div>
      )}

      {mintedCode && (
        <div className="admin-codes-minted" role="status">
          Created <strong>{mintedCode.label}</strong>:{' '}
          <code className="admin-codes-value">{mintedCode.code}</code> — share
          it as{' '}
          <code className="admin-codes-value">
            /signup?code={encodeURIComponent(mintedCode.code)}
          </code>
        </div>
      )}

      <CodesTable
        isLoading={codesQuery.isLoading}
        isError={codesQuery.isError}
        errorMessage={
          codesQuery.isError
            ? extractAdminErrorMessage(codesQuery.error)
            : null
        }
        codes={codes}
        onToggle={(code) =>
          updateMutation.mutate({
            codeId: code.id,
            disabled: code.disabled_at === null,
          })
        }
        togglePending={updateMutation.isPending}
      />
    </section>
  )
}

interface CodesTableProps {
  isLoading: boolean
  isError: boolean
  errorMessage: string | null
  codes: AdminSignupCode[]
  onToggle: (code: AdminSignupCode) => void
  togglePending: boolean
}

function CodesTable({
  isLoading,
  isError,
  errorMessage,
  codes,
  onToggle,
  togglePending,
}: CodesTableProps) {
  // Per-code roster expansion (ORPHEUS-129). One roster open at a time —
  // the question is "who's behind THIS code", not a cross-code compare.
  const [expandedCodeId, setExpandedCodeId] = useState<string | null>(null)
  if (isLoading) {
    return <div className="admin-status">Loading codes…</div>
  }
  if (isError) {
    return (
      <div className="admin-status admin-status-error" role="alert">
        {errorMessage ?? 'Failed to load codes.'}
      </div>
    )
  }
  if (codes.length === 0) {
    return (
      <div className="admin-status">
        No codes yet. Create one above to open the self-serve sign-up
        funnel — without an active code, /signup rejects everyone.
      </div>
    )
  }

  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>Code</th>
          <th>Label</th>
          <th>Routing</th>
          <th>Redemptions</th>
          <th>Expires</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {codes.map((code) => {
          const disabled = code.disabled_at !== null
          const expanded = expandedCodeId === code.id
          return (
            <Fragment key={code.id}>
              <tr>
                <td>
                  <code className="admin-codes-value">{code.code}</code>
                </td>
                <td>{code.label}</td>
                <td>
                  {code.advisor_id
                    ? code.advisor_practice_name ?? code.advisor_id
                    : 'House'}
                </td>
                <td>
                  {/* The count doubles as the roster toggle — "who's
                      behind this number" is the natural click. */}
                  <button
                    type="button"
                    className="admin-roster-toggle"
                    aria-expanded={expanded}
                    onClick={() =>
                      setExpandedCodeId(expanded ? null : code.id)
                    }
                  >
                    {code.redemption_count}
                    {code.max_uses !== null ? ` / ${code.max_uses}` : ''}
                    {' '}
                    {expanded ? '▾' : '▸'}
                  </button>
                </td>
                <td>{code.expires_at ? code.expires_at.slice(0, 10) : '—'}</td>
                <td>{disabled ? 'Disabled' : 'Active'}</td>
                <td>
                  <button
                    type="button"
                    className="admin-codes-toggle"
                    disabled={togglePending}
                    onClick={() => onToggle(code)}
                  >
                    {disabled ? 'Enable' : 'Disable'}
                  </button>
                </td>
              </tr>
              {expanded && (
                <tr className="admin-roster-row">
                  <td colSpan={7}>
                    <CodeRoster codeId={code.id} />
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}

/**
 * The per-code roster (ORPHEUS-129) — every client who signed up
 * through the code, with sign-up date and latest-report status. This
 * is the proto-cohort view: when the B2B cohort layer lands (see the
 * Cohort Assessment scoping doc), `cohort_members` backfills from
 * exactly these redemption rows, and this table grows into the
 * roster heat-map.
 */
function CodeRoster({ codeId }: { codeId: string }) {
  const rosterQuery = useAdminCodeRedemptions(codeId)

  if (rosterQuery.isLoading) {
    return <div className="admin-status">Loading roster…</div>
  }
  if (rosterQuery.isError) {
    return (
      <div className="admin-status admin-status-error" role="alert">
        {extractAdminErrorMessage(rosterQuery.error)}
      </div>
    )
  }
  const redemptions = rosterQuery.data?.redemptions ?? []
  if (redemptions.length === 0) {
    return (
      <div className="admin-status">
        No sign-ups through this code yet.
      </div>
    )
  }

  return (
    <table className="admin-table admin-roster-table">
      <thead>
        <tr>
          <th>Member</th>
          <th>Email</th>
          <th>Signed up</th>
          <th>Latest report</th>
        </tr>
      </thead>
      <tbody>
        {redemptions.map((member) => (
          <tr key={member.client_id}>
            <td>{member.display_name}</td>
            <td>{member.email}</td>
            <td>
              {member.redeemed_at ? member.redeemed_at.slice(0, 10) : '—'}
            </td>
            <td>
              {member.latest_job
                ? `${member.latest_job.status}${
                    member.latest_job.data_limited ? ' · limited data' : ''
                  }`
                : 'none yet'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// --------------------------------------------------------------------------- //
// Waitlist (ORPHEUS-104) — read-only view of public.waitlist
// --------------------------------------------------------------------------- //

function WaitlistSection() {
  const waitlistQuery = useAdminWaitlist()
  const entries = waitlistQuery.data?.entries ?? []

  const betaCount = entries.filter((e) =>
    e.interests.includes('beta_access'),
  ).length
  const workshopCount = entries.filter((e) =>
    e.interests.includes('live_workshop'),
  ).length

  return (
    <section className="admin-section">
      <h2 className="admin-section-title">
        Waitlist
        {!waitlistQuery.isLoading && !waitlistQuery.isError && (
          <span className="admin-waitlist-stats">
            {entries.length} signup{entries.length === 1 ? '' : 's'}
            {' · '}
            {betaCount} beta assessment
            {' · '}
            {workshopCount} live cohorts
          </span>
        )}
      </h2>
      <WaitlistTable
        isLoading={waitlistQuery.isLoading}
        isError={waitlistQuery.isError}
        errorMessage={
          waitlistQuery.isError
            ? extractAdminErrorMessage(waitlistQuery.error)
            : null
        }
        entries={entries}
      />
    </section>
  )
}

interface WaitlistTableProps {
  isLoading: boolean
  isError: boolean
  errorMessage: string | null
  entries: AdminWaitlistEntry[]
}

function WaitlistTable({
  isLoading,
  isError,
  errorMessage,
  entries,
}: WaitlistTableProps) {
  if (isLoading) {
    return <div className="admin-status">Loading waitlist…</div>
  }
  if (isError) {
    return (
      <div className="admin-status admin-status-error" role="alert">
        {errorMessage ?? 'Failed to load waitlist.'}
      </div>
    )
  }
  if (entries.length === 0) {
    return (
      <div className="admin-status">
        No signups yet. Express-interest submissions from the marketing
        page will appear here.
      </div>
    )
  }

  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Interests</th>
          <th>Source</th>
          <th>Signed up</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id} className="admin-row">
            <td>{formatWaitlistName(entry)}</td>
            <td>{entry.email}</td>
            <td>
              {entry.interests.length === 0 ? (
                <span className="admin-cell-secondary">—</span>
              ) : (
                entry.interests.map((interest) => (
                  <span
                    key={interest}
                    className="admin-chip admin-chip-interest"
                  >
                    {WAITLIST_INTEREST_LABELS[interest] ?? interest}
                  </span>
                ))
              )}
            </td>
            <td className="admin-cell-secondary">{entry.source ?? '—'}</td>
            <td className="admin-cell-secondary">
              {formatDateOnly(entry.created_at)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// Display labels for the migration-018 interests values. Unknown values
// (the column is extensible without migration) fall through verbatim. The
// labels track the landing page copy while the stored values stay canonical,
// so these two renamed in the 2026-07-27 pass and the values did not.
const WAITLIST_INTEREST_LABELS: Record<string, string> = {
  beta_access: 'Beta assessment',
  live_workshop: 'Live cohorts',
}

function formatWaitlistName(entry: AdminWaitlistEntry): string {
  const name = [entry.first_name, entry.last_name]
    .filter(Boolean)
    .join(' ')
    .trim()
  return name || '—'
}

// --------------------------------------------------------------------------- //
// Clients table
// --------------------------------------------------------------------------- //

interface ClientsTableProps {
  isLoading: boolean
  isError: boolean
  errorMessage: string | null
  clients: AdminClient[]
  selectedClientId: string | null
  onSelect: (id: string) => void
}

function ClientsTable({
  isLoading,
  isError,
  errorMessage,
  clients,
  selectedClientId,
  onSelect,
}: ClientsTableProps) {
  if (isLoading) {
    return <div className="admin-status">Loading clients…</div>
  }
  if (isError) {
    return (
      <div className="admin-status admin-status-error" role="alert">
        {errorMessage ?? 'Failed to load clients.'}
      </div>
    )
  }
  if (clients.length === 0) {
    return (
      <div className="admin-status">
        No clients yet. The first invitation accepted from
        /advisor/clients will appear here.
      </div>
    )
  }

  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Advisor</th>
          <th>Invitation</th>
          <th>Latest job</th>
          <th>Joined</th>
          <th aria-label="Actions" />
        </tr>
      </thead>
      <tbody>
        {clients.map((client) => (
          <tr
            key={client.id}
            className={
              client.id === selectedClientId
                ? 'admin-row admin-row-selected'
                : 'admin-row'
            }
          >
            <td>{client.display_name}</td>
            <td>{client.email}</td>
            <td>
              {client.advisor
                ? client.advisor.practice_name ??
                  client.advisor.email ??
                  client.advisor.id
                : '—'}
            </td>
            <td>
              <span
                className={`admin-chip admin-chip-${client.invitation_status}`}
              >
                {client.invitation_status}
              </span>
            </td>
            <td>
              {client.latest_job ? (
                <>
                  <span
                    className={`admin-chip admin-chip-job-${client.latest_job.status}`}
                  >
                    {client.latest_job.status}
                  </span>
                  {client.latest_job.data_limited && (
                    <span
                      className="admin-chip admin-chip-limited"
                      title="Completed on incomplete data (ORPHEUS-88)"
                    >
                      limited data
                    </span>
                  )}
                </>
              ) : (
                <span className="admin-chip admin-chip-job-none">none</span>
              )}
            </td>
            <td className="admin-cell-secondary">
              {formatDateOnly(client.created_at)}
            </td>
            <td className="admin-actions-cell">
              <button
                type="button"
                className="admin-row-btn"
                onClick={() => onSelect(client.id)}
              >
                {client.id === selectedClientId ? 'Selected' : 'View jobs'}
              </button>
              {client.latest_job?.status === 'complete' && (
                <Link
                  to={`/jobs/${client.latest_job.id}`}
                  className="admin-row-btn admin-row-btn-secondary"
                >
                  Open report
                </Link>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// --------------------------------------------------------------------------- //
// Jobs table — with nested narrative-picker chips
// --------------------------------------------------------------------------- //

interface JobsTableProps {
  isLoading: boolean
  isError: boolean
  errorMessage: string | null
  jobs: AdminJob[]
  selectedNarrativeId: string | null
  onSelectNarrative: (id: string) => void
}

function JobsTable({
  isLoading,
  isError,
  errorMessage,
  jobs,
  selectedNarrativeId,
  onSelectNarrative,
}: JobsTableProps) {
  if (isLoading) {
    return <div className="admin-status">Loading jobs…</div>
  }
  if (isError) {
    return (
      <div className="admin-status admin-status-error" role="alert">
        {errorMessage ?? 'Failed to load jobs.'}
      </div>
    )
  }
  if (jobs.length === 0) {
    return <div className="admin-status">No jobs.</div>
  }

  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>Job id</th>
          <th>Client</th>
          <th>Status</th>
          <th>Created</th>
          <th>Completed</th>
          <th>Narratives</th>
        </tr>
      </thead>
      <tbody>
        {jobs.map((job) => (
          <tr key={job.id} className="admin-row">
            <td>
              <code className="admin-code">{shortenId(job.id)}</code>
            </td>
            <td>{job.client_display_name ?? '—'}</td>
            <td>
              <span className={`admin-chip admin-chip-job-${job.status}`}>
                {job.status}
              </span>
              {job.data_limited && (
                <span
                  className="admin-chip admin-chip-limited"
                  title="Completed on incomplete data (ORPHEUS-88)"
                >
                  limited data
                </span>
              )}
              {job.prose_gate_degraded && (
                <span
                  className="admin-chip admin-chip-degraded"
                  title={
                    job.prose_gate_violations
                      ? `Unverified figures in client-facing prose ` +
                        `(ORPHEUS-131): ${job.prose_gate_violations}`
                      : 'Served with unverified figures in client-facing ' +
                        'prose (ORPHEUS-131)'
                  }
                >
                  unverified figures
                </span>
              )}
              {job.error_message && (
                <span
                  className="admin-job-error"
                  title={job.error_message}
                >
                  {job.error_message.slice(0, 64)}
                </span>
              )}
            </td>
            <td className="admin-cell-secondary">
              {formatDateOnly(job.created_at)}
            </td>
            <td className="admin-cell-secondary">
              {formatDateOnly(job.completed_at)}
            </td>
            <td className="admin-narrative-cell">
              {job.narratives.length === 0 ? (
                <span className="admin-cell-secondary">—</span>
              ) : (
                <NarrativePicker
                  narratives={job.narratives}
                  selectedNarrativeId={selectedNarrativeId}
                  onSelect={onSelectNarrative}
                />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

interface NarrativePickerProps {
  narratives: AdminNarrativeMeta[]
  selectedNarrativeId: string | null
  onSelect: (id: string) => void
}

function NarrativePicker({
  narratives,
  selectedNarrativeId,
  onSelect,
}: NarrativePickerProps) {
  return (
    <div className="admin-narrative-chips">
      {narratives.map((n) => (
        <button
          key={n.id}
          type="button"
          className={
            n.id === selectedNarrativeId
              ? 'admin-narrative-chip admin-narrative-chip-selected'
              : 'admin-narrative-chip'
          }
          onClick={() => onSelect(n.id)}
          title={`Section: ${n.section}\nStatus: ${n.status}${n.has_edited_text ? '\nEdited' : ''}`}
        >
          {n.section}
          {n.has_edited_text && (
            <span className="admin-narrative-chip-edited">•</span>
          )}
        </button>
      ))}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Inline narrative editor
// --------------------------------------------------------------------------- //

interface NarrativeEditorProps {
  narrativeId: string
  onClose: () => void
}

function NarrativeEditor({ narrativeId, onClose }: NarrativeEditorProps) {
  const narrativeQuery = useAdminNarrative(narrativeId)
  const updateMutation = useUpdateAdminNarrative()
  const [editedText, setEditedText] = useState<string>('')
  const [statusValue, setStatusValue] = useState<'draft' | 'published'>('draft')
  const [banner, setBanner] = useState<
    { kind: 'success' | 'error'; message: string } | null
  >(null)

  // Sync form-local state from the loaded narrative. React Query memo-
  // stabilises `narrativeQuery.data`, so this only fires when the row
  // actually changes (new narrativeId, or a successful PATCH's
  // setQueryData). Resetting the banner on the same edge clears stale
  // success / error messages when the admin clicks to a different
  // section.
  useEffect(() => {
    const data = narrativeQuery.data
    if (!data) return
    setEditedText(data.edited_text ?? data.generated_text ?? '')
    setStatusValue(data.status === 'published' ? 'published' : 'draft')
    setBanner(null)
  }, [narrativeQuery.data])

  if (narrativeQuery.isLoading) {
    return <div className="admin-status">Loading narrative…</div>
  }
  if (narrativeQuery.isError) {
    return (
      <div className="admin-status admin-status-error" role="alert">
        {extractAdminErrorMessage(narrativeQuery.error)}
      </div>
    )
  }
  if (!narrativeQuery.data) {
    return null
  }

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBanner(null)
    try {
      await updateMutation.mutateAsync({
        narrativeId,
        body: {
          edited_text: editedText,
          status: statusValue,
        },
      })
      setBanner({ kind: 'success', message: 'Narrative saved.' })
    } catch (err) {
      setBanner({ kind: 'error', message: extractAdminErrorMessage(err) })
    }
  }

  return (
    <form className="admin-editor" onSubmit={handleSave}>
      <header className="admin-editor-header">
        <div>
          <div className="admin-editor-section">
            {narrativeQuery.data.section}
          </div>
          <div className="admin-cell-secondary admin-editor-meta">
            Job <code className="admin-code">{shortenId(narrativeQuery.data.job_id)}</code>
            {' · '}
            generated {formatDateOnly(narrativeQuery.data.generated_at)}
          </div>
        </div>
        <button
          type="button"
          className="admin-editor-close"
          onClick={onClose}
          aria-label="Close editor"
        >
          ×
        </button>
      </header>

      {banner && (
        <div
          className={
            banner.kind === 'success'
              ? 'admin-editor-banner admin-editor-banner-success'
              : 'admin-editor-banner admin-editor-banner-error'
          }
          role={banner.kind === 'error' ? 'alert' : 'status'}
        >
          {banner.message}
        </div>
      )}

      <label className="admin-editor-field">
        <span className="admin-editor-label">Generated (read-only)</span>
        <textarea
          className="admin-editor-textarea admin-editor-textarea-readonly"
          value={narrativeQuery.data.generated_text}
          readOnly
          rows={6}
        />
      </label>

      <label className="admin-editor-field">
        <span className="admin-editor-label">Edited text</span>
        <textarea
          className="admin-editor-textarea"
          value={editedText}
          onChange={(e) => setEditedText(e.target.value)}
          rows={10}
        />
      </label>

      <div className="admin-editor-row">
        <label className="admin-editor-status-field">
          <span className="admin-editor-label">Status</span>
          <select
            className="admin-editor-select"
            value={statusValue}
            onChange={(e) =>
              setStatusValue(e.target.value === 'published' ? 'published' : 'draft')
            }
          >
            <option value="draft">draft</option>
            <option value="published">published</option>
          </select>
        </label>
        <button
          type="submit"
          className="admin-editor-save"
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? 'Saving…' : 'Save narrative'}
        </button>
      </div>
    </form>
  )
}

// --------------------------------------------------------------------------- //
// Small formatting helpers
// --------------------------------------------------------------------------- //

function formatDateOnly(iso: string | null | undefined): string {
  if (!iso) return '—'
  // Render YYYY-MM-DD — the admin surface is dense; a full timestamp
  // is noise on most cells. The job-error tooltip carries the full
  // text when needed.
  return iso.slice(0, 10)
}

function shortenId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id
}
