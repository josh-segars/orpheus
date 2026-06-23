import type { SignalBand } from '../../types/scoring'

/**
 * Band ranges per PRODUCT_CONTEXT.md § "Signal strength bands".
 * - `min`/`max` are inclusive score boundaries (0–100).
 * - `width` is the % of the 0–100 scale the band occupies.
 * - `midpoint` is where a centered label would sit.
 *
 * PROVISIONAL — breakpoints recalibrate at 50–100 profiles.
 */
export interface BandRange {
  band: SignalBand
  min: number
  max: number
  width: number
  midpoint: number
}

// Widths are segment widths between the visual boundary ticks
// (0/25/45/65/80/100), summing to exactly 100. Each band occupies the
// range from its preceding boundary to its trailing boundary.
export const BANDS: BandRange[] = [
  { band: 'Dissonant', min: 0,  max: 24,  width: 25, midpoint: 12.5 },
  { band: 'Untuned',   min: 25, max: 44,  width: 20, midpoint: 35   },
  { band: 'Tuning',    min: 45, max: 64,  width: 20, midpoint: 55   },
  { band: 'Tuned',     min: 65, max: 79,  width: 15, midpoint: 72.5 },
  { band: 'Resonant',  min: 80, max: 100, width: 20, midpoint: 90   },
]

/** Numeric boundaries that get labeled under major ticks. */
export const BAND_BOUNDARIES = [0, 25, 45, 65, 80, 100] as const

/**
 * Return the band a given score falls into.
 *
 * Bands are matched as half-open lower bounds (ORPHEUS-95): a score belongs to
 * the highest band whose `min` it meets or exceeds. The inclusive `min`/`max`
 * integer ranges leave one-unit gaps between consecutive bands — (24, 25),
 * (44, 45), (64, 65), (79, 80) — and a fractional score landing in a gap
 * (e.g. 79.13) would previously match no band and fall through to 'Dissonant'.
 * Lower-bound matching closes the gaps while preserving the documented integer
 * thresholds exactly. Mirrors backend `assign_band`.
 */
export function bandForScore(score: number): SignalBand {
  const clamped = Math.max(0, Math.min(100, score))
  for (let i = BANDS.length - 1; i >= 0; i--) {
    if (clamped >= BANDS[i].min) return BANDS[i].band
  }
  return 'Dissonant'
}

/**
 * Classify a dimension's normalized score (0–1) into a band using the same
 * thresholds as the composite. Input 0.72 → 72 → 'Tuned'.
 * Dimensions don't have their own band thresholds in the Pydantic models;
 * this is a UI-layer classification for display only.
 */
export function bandForNormalizedScore(normalizedScore: number): SignalBand {
  return bandForScore(normalizedScore * 100)
}
