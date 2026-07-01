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
import { FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  AdminClient,
  AdminJob,
  AdminNarrativeMeta,
  extractAdminErrorMessage,
  useAdminClients,
  useAdminJobs,
  useAdminNarrative,
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
    </main>
  )
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
