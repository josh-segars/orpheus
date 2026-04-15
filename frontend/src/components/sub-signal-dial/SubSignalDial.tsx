import { useMemo } from 'react'
import { bandForNormalizedScore } from '../signal-meter'
import type { SignalBand } from '../../types/scoring'
import './SubSignalDial.css'

export interface SubSignalDialProps {
  /**
   * Score on a 0–10 scale. Values below 1 are clamped to 1 (needle at
   * minimum tick); values above 10 are clamped to 10. For a dimension's
   * normalized_score (0–1), multiply by 10 before passing in.
   */
  score: number
  /**
   * Optional explicit band label. If omitted, derived from score via
   * `bandForNormalizedScore(score / 10)`.
   */
  band?: SignalBand
  /** Display size in px for the dial box. Default 64. */
  size?: number
  /** Extra className for the root. */
  className?: string
  /** Optional aria-label; defaults to a descriptive sentence. */
  ariaLabel?: string
}

/**
 * Sub-signal dial — speedometer-style gauge.
 *
 * Geometry:
 * - 270° sweep from 225° (bottom-left, ~7:30 clock) clockwise through 0°
 *   (top) to 135° (bottom-right, ~4:30 clock).
 * - 10 ticks at 30° intervals marking scores 1–10.
 * - Needle is a dark triangular notch on the gold dial, rotated to the
 *   current score angle. At score=7.2, the notch lands around 1:40 clock.
 *
 * The "dial" metaphor is chosen over a filling meter because the product
 * principle is that these dimensions are adjustable — "dial in" your signal.
 */
export function SubSignalDial({
  score,
  band,
  size = 64,
  className,
  ariaLabel,
}: SubSignalDialProps) {
  const clamped = Math.max(1, Math.min(10, score))
  const activeBand = band ?? bandForNormalizedScore(clamped / 10)

  const ticks = useMemo(() => buildTicks(), [])
  const needleAngle = scoreToAngle(clamped)

  const rootClass = ['ssd-root', className].filter(Boolean).join(' ')

  return (
    <div
      className={rootClass}
      role="meter"
      aria-valuemin={1}
      aria-valuemax={10}
      aria-valuenow={clamped}
      aria-valuetext={`${activeBand}`}
      aria-label={ariaLabel ?? 'Sub-signal strength'}
    >
      <svg
        className="ssd-svg"
        width={size}
        height={size}
        viewBox="0 0 64 64"
        aria-hidden="true"
      >
        {/* Tick ring — sits outside the dial */}
        {ticks.map((t, i) => (
          <line
            key={i}
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            stroke="var(--ssd-tick)"
            strokeWidth={1}
            strokeLinecap="round"
          />
        ))}

        {/* Dial — solid gold disk */}
        <circle cx={CX} cy={CY} r={R_DIAL} fill="var(--ssd-dial)" />

        {/* Needle — thin rectangular hand from center to the disk edge,
            painted in the card's background color so it reads as a slot
            cut through the dial. Rotated to the score angle. */}
        <rect
          x={CX - NEEDLE_WIDTH / 2}
          y={CY - R_DIAL}
          width={NEEDLE_WIDTH}
          height={R_DIAL}
          fill="var(--ssd-needle)"
          transform={`rotate(${needleAngle} ${CX} ${CY})`}
        />
      </svg>

      <div className="ssd-label">{activeBand}</div>
    </div>
  )
}

// ── Geometry ────────────────────────────────────────────────

// Fixed viewBox: 0 0 64 64
const CX = 32
const CY = 32
const R_DIAL = 20          // solid gold disk radius
const R_TICK_INNER = 24    // inner end of each tick (just outside dial)
const R_TICK_OUTER = 30    // outer end of each tick
const NEEDLE_WIDTH = 3     // px — thickness of the rectangular hand
const START_ANGLE = 225    // 7:30 clock position
const SWEEP = 270          // bottom-left → top → bottom-right
const TICK_COUNT = 10
const TICK_STEP = SWEEP / (TICK_COUNT - 1) // 30° between ticks

/** Clock-angle degrees → (x, y) on a circle of given radius, centered at (CX, CY).
 *  0° = top, 90° = right, 180° = bottom, 270° = left. */
function polar(angleDeg: number, r: number) {
  const rad = (angleDeg * Math.PI) / 180
  return {
    x: CX + r * Math.sin(rad),
    y: CY - r * Math.cos(rad),
  }
}

function buildTicks() {
  const out: { x1: number; y1: number; x2: number; y2: number }[] = []
  for (let i = 0; i < TICK_COUNT; i++) {
    const angle = START_ANGLE + i * TICK_STEP
    const inner = polar(angle, R_TICK_INNER)
    const outer = polar(angle, R_TICK_OUTER)
    out.push({ x1: inner.x, y1: inner.y, x2: outer.x, y2: outer.y })
  }
  return out
}

function scoreToAngle(score: number) {
  return START_ANGLE + ((score - 1) / (TICK_COUNT - 1)) * SWEEP
}

