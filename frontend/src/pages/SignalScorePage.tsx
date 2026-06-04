import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useJob } from '../hooks/useJob'
import type {
  DimensionScore,
  SignalBand,
  SubDimensionScore,
} from '../types/scoring'
import wavesDissonant from '../assets/wave-1-dissonant.png'
import wavesUntuned from '../assets/wave-2-untuned.png'
import wavesTuning from '../assets/wave-3-tuning.png'
import wavesTuned from '../assets/wave-4-tuned.png'
import wavesResonant from '../assets/wave-5-resonant.png'
import './SignalScorePage.css'

/**
 * Signal Score report screen — v2 4-dimension architecture, ORPHEUS-50
 * redesign. Per the approved Figma, the composite display is the band
 * label only (no needle, no number) on top of a full-bleed waveform
 * hero. Each dimension renders as a card showing a 5-pill band row,
 * the dimension narrative, and an expandable sub-dimension list with
 * 5-pip rating rows. Sub-dimension narrative payload comes from
 * SubDimensionScore.{summary, best_practices, improvements} (filled
 * by ORPHEUS-21 when it ships).
 */
export function SignalScorePage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { data: job, isLoading, error } = useJob(jobId)

  if (isLoading) {
    return (
      <main className="main-interior">
        <div className="page-status">Loading your Signal Score&hellip;</div>
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
            Your Signal Score is still being prepared
          </h2>
          <p className="section-intro">
            This page will refresh automatically when the analysis is complete.
          </p>
        </div>
      </main>
    )
  }

  const { scoring, narratives } = job.result
  const { composite, band, dimensions } = scoring.scored_dimensions

  return (
    <main className="main-interior signal-main">
      {/* Score hero — contained inside main-interior. Band-keyed waveform
          is a billboard that overflows the column horizontally and bleeds
          vertically into the dimensions area below. Composite score
          number is sr-only; the band label is the only visible composite
          display per the "clients see bands" product principle. */}
      <section className="score-hero" aria-labelledby="score-hero-band">
        <img
          src={bandToWaveform(band)}
          alt=""
          className="score-hero-waves"
          aria-hidden="true"
        />
        <div className="score-hero-content">
          <div className="score-hero-eyebrow">Your Composition</div>
          <h1 className="score-hero-band" id="score-hero-band">
            {band}
            <span className="sr-only">
              {' '}&mdash; composite score {Math.round(composite)} of 100
            </span>
          </h1>
        </div>
      </section>

      {/* Dimensions */}
      <div className="section-header signal-section-header">
        <div className="section-eyebrow">Dimensions</div>
        <h2 className="section-title">Your Signal Composition</h2>
      </div>

      <div className="dimensions-grid">
        {dimensions.map((dim) => (
          <DimensionCard
            key={dim.name}
            dimension={dim}
            narrative={narratives.dimension_narratives[dim.name]}
          />
        ))}
      </div>

      {/* Actions */}
      <div className="actions">
        <Link to="/" className="btn-secondary">
          &larr; Return to Groundwork
        </Link>
        <div className="actions-group">
          <Link to={`/jobs/${job.id}/cheat-sheet`} className="btn-secondary">
            View Cheat Sheet
          </Link>
          <Link to={`/jobs/${job.id}/forward-brief`} className="btn-primary">
            View My Forward Brief &rarr;
          </Link>
        </div>
      </div>
    </main>
  )
}

// --- Pieces ---------------------------------------------------------------

interface DimensionCardProps {
  dimension: DimensionScore
  narrative: string | undefined
}

function DimensionCard({ dimension, narrative }: DimensionCardProps) {
  // Per-dimension band is now server-authoritative (ORPHEUS-22). Previously
  // derived client-side from normalized_score × 100 via dimensionBand(); that
  // helper is gone — the backend computes it in scoring/engine.py against
  // the same composite SIGNAL_BANDS thresholds.
  const dimBand = dimension.band
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (name: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })

  return (
    <div className="dimension-card">
      <div className="dim-header">
        <div className="dim-name">{dimension.name}</div>
        <BandPillRow
          activeBand={dimBand}
          dimensionName={dimension.name}
          score={dimension.normalized_score}
        />
      </div>
      {narrative && <p className="dim-narrative">{narrative}</p>}
      {dimension.sub_dimensions.length > 0 && (
        <>
          <div className="dim-divider" />
          <div className="sub-dim-list">
            {dimension.sub_dimensions.map((sub) => (
              <SubDimRow
                key={sub.name}
                sub={sub}
                expanded={expanded.has(sub.name)}
                onToggle={() => toggle(sub.name)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

interface BandPillRowProps {
  activeBand: SignalBand
  dimensionName: string
  /** Dimension's normalized 0-1 score; surfaced to assistive tech alongside the band label. */
  score: number
}

function BandPillRow({ activeBand, dimensionName, score }: BandPillRowProps) {
  const numericScore = Math.round(score * 100)
  return (
    <div
      className="band-pills"
      role="group"
      aria-label={`${dimensionName} band: ${activeBand} — score ${numericScore} of 100`}
    >
      {BAND_ORDER.map((b) => (
        <span
          key={b}
          className={`band-pill${b === activeBand ? ' band-pill-active' : ''}`}
          aria-current={b === activeBand ? 'true' : undefined}
        >
          {b}
        </span>
      ))}
    </div>
  )
}

interface SubDimRowProps {
  sub: SubDimensionScore
  expanded: boolean
  onToggle: () => void
}

function SubDimRow({ sub, expanded, onToggle }: SubDimRowProps) {
  const filledPips = pipCount(sub)
  const hasDetail = isExpandable(sub)

  const row = (
    <div className="sub-dim-row-content">
      <span className="sub-dim-name">{subDimDisplayName(sub.name)}</span>
      <PipRow filled={filledPips} />
    </div>
  )

  if (!hasDetail) {
    return <div className="sub-dim sub-dim-static">{row}</div>
  }

  return (
    <div className={`sub-dim sub-dim-expandable${expanded ? ' is-expanded' : ''}`}>
      <button
        type="button"
        className="sub-dim-trigger"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        {row}
      </button>
      {expanded && (
        <div className="sub-dim-detail">
          {sub.summary && <DetailSection label="Summary" prose={sub.summary} />}
          {sub.best_practices && (
            <DetailSection label="Best Practices" prose={sub.best_practices} />
          )}
          {sub.improvements && sub.improvements.length > 0 && (
            <DetailSection label="Improvements" bullets={sub.improvements} />
          )}
        </div>
      )}
    </div>
  )
}

function PipRow({ filled }: { filled: number }) {
  return (
    <div className="pip-row" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className={`pip pip-${i}${i <= filled ? ' pip-filled' : ''}`}
        />
      ))}
    </div>
  )
}

function DetailSection({
  label,
  prose,
  bullets,
}: {
  label: string
  prose?: string
  bullets?: string[]
}) {
  return (
    <div className="detail-section">
      <div className="detail-section-label">{label}</div>
      {prose && <p className="detail-section-prose">{prose}</p>}
      {bullets && (
        <ul className="detail-section-list">
          {bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

// --- Helpers --------------------------------------------------------------

const BAND_ORDER: readonly SignalBand[] = [
  'Dissonant',
  'Untuned',
  'Tuning',
  'Tuned',
  'Resonant',
] as const

/**
 * Client-facing display names for a handful of sub-dimensions whose internal
 * (rubric / scoring engine / config) names read as engineering-y. The internal
 * names stay canonical everywhere upstream — backend models, narrative agent
 * input, narrative agent output, tests — and this map only swaps the visible
 * label at the leaf-row render. ORPHEUS-21 decision (Andrew + Josh, 2026-06-03):
 * rename selectively rather than rewriting the source-of-truth identifiers.
 *
 * The eight sub-dims not listed here (Headline Clarity, About Section
 * Coherence, Profile Completeness, Identity Clarity, Recency, Continuity,
 * Posting Presence, Topic Consistency) render with their internal names as-is.
 */
const SUB_DIM_DISPLAY_NAMES: Record<string, string> = {
  'Experience Description Quality': 'Experience Narrative',
  'History Depth': 'Engagement History',
  'Outbound Engagement Presence': 'Engagement Volume',
  'Engagement Quality Score': 'Substantive Engagement',
  'Profile-Content Coherence': 'Profile-Content Match',
}

function subDimDisplayName(internalName: string): string {
  return SUB_DIM_DISPLAY_NAMES[internalName] ?? internalName
}

/**
 * Band-keyed waveform assets. Five distinct visuals, one per tuner band —
 * the band IS the hero image, not just a label over a shared backdrop.
 *
 * Source files live in the repo-root assets/images/ alongside the HTML
 * prototype assets; the frontend mirror in src/assets/ exists so Vite's
 * default fs.allow accepts the import (same workaround that was applied
 * to waves.jpg in ORPHEUS-50). Replacing a band's visual is a two-step
 * file swap (repo-root + mirror) with no code change.
 */
const WAVES_BY_BAND: Record<SignalBand, string> = {
  Dissonant: wavesDissonant,
  Untuned: wavesUntuned,
  Tuning: wavesTuning,
  Tuned: wavesTuned,
  Resonant: wavesResonant,
}

function bandToWaveform(band: SignalBand): string {
  return WAVES_BY_BAND[band]
}

/**
 * Number of filled pips (0–5) for a sub-dimension. Rubric scores are 1–5,
 * quantitative scores 0–5; both clamp into [0, 5] so the same 5-pip row
 * pattern works regardless of method.
 */
function pipCount(sub: SubDimensionScore): number {
  return Math.min(5, Math.max(0, Math.round(sub.score)))
}

function isExpandable(sub: SubDimensionScore) {
  return Boolean(
    sub.summary ||
      sub.best_practices ||
      (sub.improvements && sub.improvements.length > 0),
  )
}
