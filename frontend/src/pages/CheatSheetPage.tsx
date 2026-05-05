import { Link, useParams } from 'react-router-dom'
import { useJob } from '../hooks/useJob'
import type { CheatSheetPriority } from '../types/scoring'
import './CheatSheetPage.css'

/**
 * Cheat Sheet — printable one-page reference derived from the Forward
 * Brief. Content is delivered as `narratives.cheat_sheet` (structured,
 * not markdown). Print styles collapse the page to a single Letter
 * portrait sheet; see the `@media print` rules in CheatSheetPage.css.
 */
export function CheatSheetPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { data: job, isLoading, error } = useJob(jobId)

  if (isLoading) {
    return (
      <main className="main-interior">
        <div className="page-status">Loading your Cheat Sheet&hellip;</div>
      </main>
    )
  }

  if (error || !job) {
    return (
      <main className="main-interior">
        <div className="page-status">
          We couldn&rsquo;t load this report. Please try again.
        </div>
      </main>
    )
  }

  if (job.state !== 'complete' || !job.result) {
    return (
      <main className="main-interior">
        <div className="section-header">
          <div className="section-eyebrow">Analysis in Progress</div>
          <h2 className="section-title">
            Your Cheat Sheet is still being prepared
          </h2>
          <p className="section-intro">
            This page will refresh automatically when the analysis is complete.
          </p>
        </div>
      </main>
    )
  }

  const clientName = job.client_id ? formatClientName(job.client_id) : null
  const { cheat_sheet } = job.result.narratives

  return (
    <main className="main-interior">
      {/* Screen-only helper row (hidden on print) */}
      <div className="print-helper">
        <div className="print-helper-text">
          A one-page reference card drawn from your Forward Brief. Print with{' '}
          <kbd>⌘</kbd> <kbd>P</kbd> (Mac) or <kbd>Ctrl</kbd> <kbd>P</kbd>{' '}
          (Windows) — the layout is optimized for Letter portrait.
        </div>
        <button
          type="button"
          className="btn-secondary print-helper-button"
          onClick={() => window.print()}
        >
          Print
        </button>
      </div>

      {/* The "document" — what the printed page shows. */}
      <div className="cheat-doc">
        <header className="cheat-header">
          <div className="cheat-eyebrow">Cheat Sheet</div>
          <h1 className="cheat-title">Your Signal, at a Glance</h1>
          <div className="cheat-subtitle">
            Priorities and weekly rhythm
            {clientName ? ` — prepared for ${clientName}` : ''}
          </div>
        </header>

        <div className="cheat-section-label">The Priorities</div>
        <div className="cheat-priorities">
          {cheat_sheet.priorities.map((p, i) => (
            <PriorityCard key={i} priority={p} index={i + 1} />
          ))}
        </div>

        <div className="cheat-section-label">Your Weekly Rhythm</div>
        <div className="rhythm-grid">
          {cheat_sheet.rhythm.map((section, i) => (
            <div
              key={i}
              className={`rhythm-block${
                cheat_sheet.rhythm.length % 2 === 1 &&
                i === cheat_sheet.rhythm.length - 1
                  ? ' rhythm-block-full'
                  : ''
              }`}
            >
              <div className="rhythm-label">{section.cadence}</div>
              <ul className="rhythm-list">
                {section.items.map((item, j) => (
                  <li key={j} className="rhythm-item">
                    <span className="rhythm-check" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {cheat_sheet.milestones.length > 0 && (
          <>
            <div className="milestones-eyebrow">90-Day Milestones</div>
            <div className="milestones">
              {cheat_sheet.milestones.map((m, i) => (
                <div key={i} className="milestone">
                  <div className="milestone-value">{m.value}</div>
                  <div className="milestone-label">{m.label}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Screen-only action bar (hidden on print) */}
      <div className="actions cheat-actions">
        <Link to={`/jobs/${job.id}`} className="btn-secondary">
          &larr; Return to Signal Score
        </Link>
        <Link
          to={`/jobs/${job.id}/forward-brief`}
          className="btn-primary"
        >
          View Forward Brief &rarr;
        </Link>
      </div>
    </main>
  )
}

// --- Pieces ---------------------------------------------------------------

interface PriorityCardProps {
  priority: CheatSheetPriority
  index: number
}

function PriorityCard({ priority, index }: PriorityCardProps) {
  return (
    <div className="cheat-priority">
      <div className="cheat-priority-number">{index}</div>
      <div className="cheat-priority-body">
        <div className="cheat-priority-title">{priority.title}</div>
        <div className="cheat-priority-action">
          {renderBold(priority.action)}
        </div>
      </div>
    </div>
  )
}

/**
 * Minimal inline renderer — lets the backend put a bolded milestone at
 * the end of an action ("**Target: 2 in 30 days.**") without needing a
 * full markdown parser on this page.
 */
function renderBold(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = []
  const re = /\*\*(.+?)\*\*/g
  let last = 0
  let match: RegExpExecArray | null
  let key = 0

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) out.push(text.slice(last, match.index))
    out.push(<strong key={key++}>{match[1]}</strong>)
    last = re.lastIndex
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

/** Turn "jane-doe" into "Jane Doe". Defensive against odd ids. */
function formatClientName(clientId: string): string {
  return clientId
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}
