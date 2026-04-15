import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useJob } from '../hooks/useJob'
import { SignalMeter } from '../components/signal-meter'
import { SubSignalDial } from '../components/sub-signal-dial'
import type { DimensionScore, SubDimensionScore } from '../types/scoring'
import './SignalScorePage.css'

/**
 * Signal Score report screen — v2 4-dimension architecture.
 * Ported from orpheus-signal-score.html and adapted to the data shape
 * produced by backend/scoring/engine.py + backend/agents/narrative.py.
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
        <div className="page-status">We couldn&rsquo;t load this report. Please try again.</div>
      </main>
    )
  }

  if (job.state !== 'complete' || !job.result) {
    return (
      <main className="main-interior">
        <div className="section-header">
          <div className="section-eyebrow">Analysis in Progress</div>
          <h2 className="section-title">Your Signal Score is still being prepared</h2>
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
    <main className="main-interior">
      {/* Score section — band name as the hero, meter as the scale.
          The composite numeric score is advisor-only; clients see only the band. */}
      <section className="score-section">
        <div className="score-section-title">
          <div className="score-section-eyebrow">Your Signal Score</div>
          <h1 className="score-section-band">{band}</h1>
        </div>
        <SignalMeter score={composite} band={band} />
      </section>

      {/* Dimensions */}
      <div className="section-header">
        <div className="section-eyebrow">Dimensions</div>
        <h2 className="section-title">How Your Signal Breaks Down</h2>
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

      {/* Interpretation — served by the forward_brief Markdown on the backend,
         but we surface a short static framing here (as in the prototype) and
         link through to the full Forward Brief view. */}
      <div className="section-header">
        <div className="section-eyebrow">Interpretation</div>
        <h2 className="section-title">Reading Your Score</h2>
      </div>

      <InterpretationProse composite={composite} band={band} />

      {/* Actions */}
      <div className="actions">
        <Link to="/" className="btn-secondary">
          &larr; Return to Groundwork
        </Link>
        <Link to={`/jobs/${job.id}/forward-brief`} className="btn-primary">
          View My Forward Brief &rarr;
        </Link>
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
  // Convert backend 0–1 normalized score to the 1–10 display scale the
  // dial expects. (The dial clamps internally.)
  const dialScore = dimension.normalized_score * 10

  // Track which sub-dimensions are expanded. Users can have any number open
  // simultaneously; an "Expand / Collapse all" toggle sits above the list.
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const expandableSubs = dimension.sub_dimensions.filter(isExpandable)
  const hasExpandable = expandableSubs.length > 0
  const allExpanded =
    hasExpandable && expandableSubs.every((s) => expanded.has(s.name))

  const toggleOne = (name: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })

  const toggleAll = () =>
    setExpanded(
      allExpanded ? new Set() : new Set(expandableSubs.map((s) => s.name)),
    )

  return (
    <div className="dimension-card">
      <div className="dimension-upper">
        <div className="dimension-text">
          <div className="dimension-name">{dimension.name}</div>
          {narrative && <div className="dimension-narrative">{narrative}</div>}
        </div>
        <div className="dimension-gauge">
          <SubSignalDial
            score={dialScore}
            ariaLabel={`${dimension.name} strength`}
          />
        </div>
      </div>
      {dimension.sub_dimensions.length > 0 && (
        <div className="dimension-indicators">
          {hasExpandable && (
            <div className="indicator-list-header">
              <button
                type="button"
                className="indicator-expand-all"
                onClick={toggleAll}
                aria-pressed={allExpanded}
                aria-label={allExpanded ? 'Collapse all' : 'Expand all'}
              >
                <span>{allExpanded ? 'Collapse all' : 'Expand all'}</span>
                <span className="material-symbols-outlined" aria-hidden="true">
                  {allExpanded ? 'unfold_less' : 'unfold_more'}
                </span>
              </button>
            </div>
          )}
          {dimension.sub_dimensions.map((sub) => (
            <SubDimensionIndicator
              key={sub.name}
              sub={sub}
              expanded={expanded.has(sub.name)}
              onToggle={() => toggleOne(sub.name)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface SubDimensionIndicatorProps {
  sub: SubDimensionScore
  expanded: boolean
  onToggle: () => void
}

function SubDimensionIndicator({
  sub,
  expanded,
  onToggle,
}: SubDimensionIndicatorProps) {
  const tone = indicatorTone(sub)
  const value = formatSubDimensionValue(sub)

  const iconName = toneIconName(tone)

  // Sub-dimensions without narrative content render as a plain one-liner.
  // An empty chevron slot is preserved so columns still align with the
  // expandable rows above/below.
  if (!isExpandable(sub)) {
    return (
      <div className={`indicator indicator-${tone}`}>
        <span className="indicator-chevron-slot" aria-hidden="true" />
        <span className="indicator-label">{sub.name}</span>
        <span className="indicator-value">
          {value}
          <span
            className="material-symbols-outlined indicator-tone-icon"
            aria-hidden="true"
          >
            {iconName}
          </span>
        </span>
      </div>
    )
  }

  return (
    <div className={`indicator indicator-expandable indicator-${tone}${expanded ? ' is-expanded' : ''}`}>
      <button
        type="button"
        className="indicator-summary"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span
          className="material-symbols-outlined indicator-chevron"
          aria-hidden="true"
        >
          chevron_right
        </span>
        <span className="indicator-label">{sub.name}</span>
        <span className="indicator-value">
          {value}
          <span
            className="material-symbols-outlined indicator-tone-icon"
            aria-hidden="true"
          >
            {iconName}
          </span>
        </span>
      </button>
      {expanded && (
        <div className="indicator-detail">
          {sub.summary && (
            <SubDimensionSection label="Summary" prose={sub.summary} />
          )}
          {sub.best_practices && (
            <SubDimensionSection
              label="Best Practices"
              prose={sub.best_practices}
            />
          )}
          {sub.improvements && sub.improvements.length > 0 && (
            <SubDimensionSection
              label="Improvements"
              bullets={sub.improvements}
            />
          )}
        </div>
      )}
    </div>
  )
}

/** Material Symbols icon name for the trailing tone indicator. */
function toneIconName(tone: 'strength' | 'watch' | 'gap'): string {
  switch (tone) {
    case 'strength':
      return 'check_circle'
    case 'watch':
      return 'emergency_home'
    case 'gap':
      return 'dangerous'
  }
}

function SubDimensionSection({
  label,
  prose,
  bullets,
}: {
  label: string
  prose?: string
  bullets?: string[]
}) {
  return (
    <div className="indicator-section">
      <div className="indicator-section-label">{label}</div>
      {prose && <p className="indicator-section-prose">{prose}</p>}
      {bullets && (
        <ul className="indicator-section-list">
          {bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function isExpandable(sub: SubDimensionScore) {
  return Boolean(
    sub.summary ||
      sub.best_practices ||
      (sub.improvements && sub.improvements.length > 0),
  )
}

interface InterpretationProseProps {
  composite: number
  band: string
}

function InterpretationProse({ composite, band }: InterpretationProseProps) {
  return (
    <div className="interpretation-prose">
      <p className="interpretation-paragraph">
        A Signal Score above 80 indicates a presence that is actively building
        authority in the right spaces. Below 60 suggests fundamental gaps that,
        if left unaddressed, are working against your professional goals. Your
        score of {composite.toFixed(1)} places you in the{' '}
        <strong>{band.toLowerCase()}</strong> range — your presence exists and
        does some work, but it is not yet operating at the level your
        experience and credentials warrant.
      </p>
      <p className="interpretation-paragraph">
        Your Forward Brief translates this diagnostic into a sequenced plan.
        The recommendations are ordered by leverage: addressing them in
        sequence will produce the fastest compound improvement to your overall
        Signal Score.
      </p>
    </div>
  )
}

// --- Helpers --------------------------------------------------------------

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

/**
 * Map a sub-dimension score onto one of three visual tones used by the
 * indicator list. Rubric and quantitative scores are on different scales,
 * so we normalize first.
 */
function indicatorTone(sub: SubDimensionScore): 'strength' | 'watch' | 'gap' {
  const [minStr, maxStr] = sub.scale.split('-')
  const min = Number(minStr)
  const max = Number(maxStr)
  if (!Number.isFinite(min) || !Number.isFinite(max) || max === min) {
    return 'watch'
  }
  const normalized = (sub.score - min) / (max - min)
  if (normalized >= 0.75) return 'strength'
  if (normalized <= 0.35) return 'gap'
  return 'watch'
}

function formatSubDimensionValue(sub: SubDimensionScore): string {
  // Quantitative sub-dimensions have a raw_value that's more informative
  // to the client than the band score.
  if (sub.raw_value != null) {
    return formatRaw(sub.raw_value)
  }
  return `${sub.score} / ${sub.scale.split('-')[1]}`
}

function formatRaw(value: number): string {
  if (Number.isInteger(value)) return value.toLocaleString()
  if (value > 0 && value < 1) return `${(value * 100).toFixed(0)}%`
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}
