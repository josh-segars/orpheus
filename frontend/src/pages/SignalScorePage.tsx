import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAdvisorClients } from '../hooks/useAdvisorClients'
import { useJob } from '../hooks/useJob'
import { useSessionRoles } from '../hooks/useSessionRoles'
import type {
  DimensionScore,
  ForwardBriefData,
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
 * redesign + ORPHEUS-69 Forward Brief consolidation. The composite
 * display is the band label only (no needle, no number) on top of a
 * band-keyed waveform hero. Each dimension renders as a card showing a
 * 5-pill band row, the always-visible 1–2 sentence dimension summary
 * (ORPHEUS-68), a read more / read less toggle revealing the combined
 * messaging paragraph (the reaxised narrative: interpretation +
 * forward-looking guidance), and an expandable sub-dimension list with
 * 5-pip rating rows (ORPHEUS-21).
 *
 * The structured metrics block at the bottom renders forward_brief_data
 * in two sections — "Audience & Reach" (quantitative stat grid +
 * audience breakdowns) and "Profile Signals" (boolean flag checklist).
 * The standalone Forward Brief page is retired (ORPHEUS-69); flow is
 * Signal Score → Cheat Sheet.
 *
 * Graceful fallback for pre-ORPHEUS-68 jobs (the three preserved cloud
 * demos): dimensions without a `summary` render the narrative directly
 * with no toggle, matching the pre-69 card shape.
 */
export function SignalScorePage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { data: job, isLoading, error } = useJob(jobId)

  // Report-subject resolution (ORPHEUS-71). The nav identity cluster now
  // always shows the signed-in user's own name, so the report subject
  // ("whose Composition is this?") surfaces in the hero instead. An
  // advisor viewing a client's report sees "[Client]'s Composition";
  // everyone else (client on their own report, dual-role advisor on
  // their self-report) sees "Your Composition". Hooks are called
  // unconditionally per rules-of-hooks; the advisor roster query gates
  // internally on the advisor role.
  const sessionRolesQuery = useSessionRoles()
  const advisorClientsQuery = useAdvisorClients()

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

  // Advisor viewing a client who isn't themselves → name the subject.
  const isAdvisor = Boolean(sessionRolesQuery.data?.advisor_id)
  const matchedClient =
    isAdvisor && job.client_id
      ? advisorClientsQuery.data?.clients.find((c) => c.id === job.client_id)
      : undefined
  const subjectName =
    matchedClient && !matchedClient.is_self ? matchedClient.display_name : null
  const heroEyebrow = subjectName
    ? `${subjectName}'s Composition`
    : 'Your Composition'

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
          <div className="score-hero-eyebrow">{heroEyebrow}</div>
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

      {/* Structured metrics block (ORPHEUS-69) — the quantitative half of
          the retired Forward Brief, rendered as data instead of prose. */}
      {scoring.forward_brief_data && (
        <MetricsBlock data={scoring.forward_brief_data} />
      )}

      {/* Actions — flow is Signal Score → Cheat Sheet (ORPHEUS-69). */}
      <div className="actions">
        <Link to="/" className="btn-secondary">
          &larr; Return to Groundwork
        </Link>
        <Link to={`/jobs/${job.id}/cheat-sheet`} className="btn-primary">
          View Cheat Sheet &rarr;
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
  // Per-dimension band is now server-authoritative (ORPHEUS-22). Previously
  // derived client-side from normalized_score × 100 via dimensionBand(); that
  // helper is gone — the backend computes it in scoring/engine.py against
  // the same composite SIGNAL_BANDS thresholds.
  const dimBand = dimension.band
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  // ORPHEUS-69: read more / read less toggle for the combined messaging
  // paragraph. Collapsed by default; only rendered when the dimension
  // carries a summary (post-ORPHEUS-68 jobs). Pre-68 jobs fall back to
  // the always-visible narrative with no toggle.
  const [narrativeOpen, setNarrativeOpen] = useState(false)

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

  const summary = dimension.summary ?? null

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
      {summary ? (
        <>
          <p className="dim-summary">{summary}</p>
          {narrative && (
            <>
              {narrativeOpen && <p className="dim-narrative">{narrative}</p>}
              <button
                type="button"
                className="dim-read-more"
                onClick={() => setNarrativeOpen((open) => !open)}
                aria-expanded={narrativeOpen}
              >
                {narrativeOpen ? 'Read less' : 'Read more'}
              </button>
            </>
          )}
        </>
      ) : (
        // Graceful fallback for pre-ORPHEUS-68 jobs: no summary on the
        // wire, so render the narrative directly (pre-69 card shape).
        narrative && <p className="dim-narrative">{narrative}</p>
      )}
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

// --- Metrics block (ORPHEUS-69) --------------------------------------------

/**
 * Structured rendering of forward_brief_data at the bottom of the page —
 * the quantitative half of the retired Forward Brief. Two sections
 * (layout locked with Josh, 2026-06-10):
 *
 *   1. "Audience & Reach" — stat-card grid for the numeric metrics,
 *      followed by compact audience-breakdown lists (seniority /
 *      industries / geographies / organizations).
 *   2. "Profile Signals" — the qualitative boolean flags as a
 *      check / cross row list.
 *
 * Every stat renders only when its value is non-null (the parsers emit
 * null for anything the export didn't carry), and each section hides
 * entirely when it has nothing to show.
 */
function MetricsBlock({ data }: { data: ForwardBriefData }) {
  const q = data.quantitative
  const flags = data.qualitative_flags

  const stats: { label: string; value: string }[] = []
  if (q.follower_count != null)
    stats.push({ label: 'Followers', value: formatCount(q.follower_count) })
  if (q.follower_growth_rate != null)
    stats.push({
      label: 'New followers / week',
      value: formatDecimal(q.follower_growth_rate),
    })
  if (q.unique_members_reached != null)
    stats.push({
      label: 'Members reached',
      value: formatCount(q.unique_members_reached),
    })
  if (q.avg_impressions_per_post != null)
    stats.push({
      label: 'Avg impressions / post',
      value: formatCount(Math.round(q.avg_impressions_per_post)),
    })
  if (q.avg_engagement_rate != null)
    stats.push({
      label: 'Engagement rate',
      value: formatPercent(q.avg_engagement_rate),
    })
  if (q.top_post_impressions != null)
    stats.push({
      label: 'Top post impressions',
      value: formatCount(q.top_post_impressions),
    })
  if (q.avg_comment_length_words != null)
    stats.push({
      label: 'Avg comment length',
      value: `${formatDecimal(q.avg_comment_length_words)} words`,
    })
  if (q.longest_posting_gap_weeks != null)
    stats.push({
      label: 'Longest posting gap',
      value: `${q.longest_posting_gap_weeks} wk`,
    })
  if (q.zero_post_week_pct != null)
    stats.push({
      label: 'Zero-post weeks',
      value: formatPercent(q.zero_post_week_pct),
    })

  const seniority = q.audience_seniority
    ? Object.entries(q.audience_seniority)
        .sort((a, b) => b[1] - a[1])
        .map(([name, pct]) => ({ name, pct }))
    : []
  const breakdowns: { label: string; segments: { name: string; pct: number }[] }[] = []
  if (seniority.length > 0)
    breakdowns.push({ label: 'Audience seniority', segments: seniority })
  if (q.audience_industries && q.audience_industries.length > 0)
    breakdowns.push({
      label: 'Top industries',
      segments: q.audience_industries.slice(0, 5),
    })
  if (q.audience_geography && q.audience_geography.length > 0)
    breakdowns.push({
      label: 'Top geographies',
      segments: q.audience_geography.slice(0, 5),
    })

  const signals: { label: string; on: boolean }[] = [
    {
      label: 'Profile photo present',
      on: flags.visual_professionalism.photo_present,
    },
    {
      label: 'Call to action in About',
      on: flags.engagement_invitation.cta_in_about,
    },
    {
      label: 'Services section listed',
      on: flags.engagement_invitation.services_present,
    },
    {
      label: 'Contact info visible',
      on: flags.engagement_invitation.contact_visible,
    },
    {
      label: 'Engagement spread across your network',
      on: !flags.viewer_actor_affinity.concentrated,
    },
  ]

  const hasReach = stats.length > 0 || breakdowns.length > 0

  return (
    <section className="metrics-block" aria-label="Your numbers at a glance">
      <div className="section-header signal-section-header">
        <div className="section-eyebrow">The Data</div>
        <h2 className="section-title">Your Numbers at a Glance</h2>
      </div>

      {hasReach && (
        <div className="metrics-section">
          <div className="metrics-section-label">Audience &amp; Reach</div>
          {stats.length > 0 && (
            <div className="metrics-stat-grid">
              {stats.map((s) => (
                <div key={s.label} className="metrics-stat">
                  <div className="metrics-stat-value">{s.value}</div>
                  <div className="metrics-stat-label">{s.label}</div>
                </div>
              ))}
            </div>
          )}
          {breakdowns.length > 0 && (
            <div className="metrics-breakdowns">
              {breakdowns.map((b) => (
                <div key={b.label} className="metrics-breakdown">
                  <div className="metrics-breakdown-label">{b.label}</div>
                  <ul className="metrics-breakdown-list">
                    {b.segments.map((seg) => (
                      <li key={seg.name} className="metrics-breakdown-item">
                        <span className="metrics-breakdown-name">{seg.name}</span>
                        <span className="metrics-breakdown-pct">
                          {formatPercent(seg.pct)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {q.top_organizations && q.top_organizations.length > 0 && (
                <div className="metrics-breakdown">
                  <div className="metrics-breakdown-label">
                    Top follower organizations
                  </div>
                  <p className="metrics-breakdown-prose">
                    {q.top_organizations.slice(0, 10).join(', ')}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="metrics-section">
        <div className="metrics-section-label">Profile Signals</div>
        <ul className="metrics-signal-list">
          {signals.map((s) => (
            <li
              key={s.label}
              className={`metrics-signal${s.on ? ' metrics-signal-on' : ''}`}
            >
              <span className="metrics-signal-mark" aria-hidden="true">
                {s.on ? '✓' : '✕'}
              </span>
              <span className="metrics-signal-label">{s.label}</span>
              <span className="sr-only">{s.on ? ' — yes' : ' — no'}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function formatCount(n: number): string {
  return n.toLocaleString('en-US')
}

function formatDecimal(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

function formatPercent(p: number): string {
  const pct = p * 100
  return `${pct < 10 && !Number.isInteger(pct) ? pct.toFixed(1) : Math.round(pct)}%`
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
