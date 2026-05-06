import { type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'

interface SectionLayoutProps {
  /** Section ordinal — drives the eyebrow text. */
  sectionNumber: 1 | 2 | 3 | 4 | 5 | 6 | 7
  /** Section title — drives the page heading and document title. */
  title: string
  /** Section intro paragraph. */
  intro: string
  /** Question elements as children. */
  children: ReactNode
  /** Save without marking the section complete. Should resolve once the
   *  underlying upsert lands. */
  onSave: () => Promise<void>
  /** Save and mark the section complete. Should resolve once the underlying
   *  upsert lands so navigation isn't racy. */
  onComplete: () => Promise<void>
  /** Reflects an in-flight save — disables both action buttons so users
   *  don't fire a second mutation before the first lands. */
  isSaving: boolean
}

/**
 * Shared chrome for every questionnaire section page. Mirrors the
 * `<main class="main-interior">` structure used in
 * orpheus-questionnaire-s1..s7.html: back link, section header, questions
 * slot, and the actions row at the bottom.
 *
 * Both action buttons trigger persistence then navigate to /groundwork.
 * Persistence is awaited so the cache reflects the final state before the
 * Groundwork page reads it.
 */
export function SectionLayout({
  sectionNumber,
  title,
  intro,
  children,
  onSave,
  onComplete,
  isSaving,
}: SectionLayoutProps) {
  const navigate = useNavigate()

  const handleSave = async () => {
    await onSave()
    navigate('/groundwork')
  }

  const handleComplete = async () => {
    await onComplete()
    navigate('/groundwork')
  }

  return (
    <main className="main-interior">
      <Link to="/groundwork" className="back-link">
        <span className="back-arrow">&#8249;</span> Groundwork Checklist
      </Link>

      <div className="section-header">
        <span className="section-eyebrow">
          Questionnaire &middot; Section {sectionNumber} of 7
        </span>
        <h1 className="section-title">{title}</h1>
        <p className="section-intro">{intro}</p>
      </div>

      <div className="questions">{children}</div>

      <div className="actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={handleSave}
          disabled={isSaving}
        >
          Save My Answers
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={handleComplete}
          disabled={isSaving}
        >
          This Section is Complete
        </button>
      </div>
    </main>
  )
}
