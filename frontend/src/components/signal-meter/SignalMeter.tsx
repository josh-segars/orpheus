import { useMemo } from 'react'
import { BAND_BOUNDARIES, BANDS, bandForScore } from './bands'
import type { SignalBand } from '../../types/scoring'
import './SignalMeter.css'

export interface SignalMeterProps {
  /** 0–100 score. Clamped in range. */
  score: number
  /** Defaults to the band derived from `score`. Lets the advisor view override for demos. */
  band?: SignalBand
  /** Show the band-boundary numbers (0 / 25 / 45 / 65 / 80 / 100) above the scale. */
  showBoundaryNumbers?: boolean
  /** Extra className for the root (harness uses it to lock width). */
  className?: string
  /** Optional aria-label; defaults to a descriptive sentence. */
  ariaLabel?: string
}

/**
 * Horizontal signal-strength meter.
 *
 * Positioning: everything is expressed in percentages of the meter's inset
 * scale, so the component adapts to any container without breakpoints. The
 * only media-responsive behavior is label density — on narrow containers
 * (< 520px), inactive band labels collapse so the active band stays
 * legible (handled in CSS via a container query on `.sm-root`).
 *
 * Ticks are rendered in SVG with `preserveAspectRatio="none"` and
 * `vectorEffect="non-scaling-stroke"` so the scale stretches cleanly while
 * strokes stay crisp 1px lines.
 */
export function SignalMeter({
  score,
  band,
  showBoundaryNumbers = true,
  className,
  ariaLabel,
}: SignalMeterProps) {
  const clamped = Math.max(0, Math.min(100, score))
  const activeBand = band ?? bandForScore(clamped)

  const ticks = useMemo(() => buildTicks(), [])

  const rootClass = ['sm-root', className].filter(Boolean).join(' ')

  return (
    <div
      className={rootClass}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clamped}
      aria-valuetext={`${activeBand} signal strength`}
      aria-label={ariaLabel ?? 'Signal Score'}
    >
      <div className="sm-meter">
        {/* Boundary numbers (0 / 25 / 45 / 65 / 80 / 100). Share the same
            --sm-inset as the scale below so each number aligns with its
            major tick. */}
        {showBoundaryNumbers && (
          <div className="sm-boundary-numbers" aria-hidden="true">
            {BAND_BOUNDARIES.map((n) => (
              <span
                key={n}
                style={{ left: `${n}%` }}
                data-interior={n !== 0 && n !== 100 ? 'true' : undefined}
              >
                {n}
              </span>
            ))}
          </div>
        )}

        {/* Inset scale: tick field + reticle */}
        <div className="sm-scale">
          <svg
            className="sm-ticks"
            viewBox="0 0 1000 60"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {ticks.map((t) => (
              <line
                key={t.x}
                x1={t.x}
                x2={t.x}
                y1={t.y1}
                y2={t.y2}
                stroke={t.color}
                strokeWidth={t.width}
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
          <div
            className="sm-reticle"
            style={{ left: `${clamped}%` }}
            aria-hidden="true"
          />
        </div>

        {/* Band labels — active band emphasized (gold, larger); inactive
            bands rendered muted. On narrow containers the inactive labels
            collapse entirely via the container query in CSS. */}
        <div className="sm-band-labels">
          {BANDS.map((b) => (
            <span
              key={b.band}
              className="sm-band-label"
              style={{ left: `${b.midpoint}%` }}
              aria-current={b.band === activeBand}
            >
              {b.band}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Tick field ──────────────────────────────────────────────

interface Tick {
  x: number // 0–1000 in viewBox units
  y1: number
  y2: number
  color: string
  width: number
}

function buildTicks(): Tick[] {
  const ticks: Tick[] = []
  const boundarySet = new Set<number>(BAND_BOUNDARIES as unknown as number[])

  // 101 ticks at score 0..100. Boundary ticks (0/25/45/65/80/100) are
  // tallest and brightest; every 5th score is a "major" tick (mid height);
  // the rest are minor ticks (short, dim).
  for (let i = 0; i <= 100; i++) {
    const x = (i / 100) * 1000
    const isBoundary = boundarySet.has(i)
    const isMajor = !isBoundary && i % 5 === 0

    let y1: number, y2: number, color: string, width: number
    if (isBoundary) {
      y1 = 10
      y2 = 50
      color = 'rgba(249, 246, 240, 0.95)'
      width = 1.5
    } else if (isMajor) {
      y1 = 16
      y2 = 44
      color = 'rgba(249, 246, 240, 0.6)'
      width = 1
    } else {
      y1 = 22
      y2 = 38
      color = 'rgba(249, 246, 240, 0.35)'
      width = 1
    }
    ticks.push({ x, y1, y2, color, width })
  }
  return ticks
}
