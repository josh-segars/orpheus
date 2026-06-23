import { describe, expect, it } from 'vitest'
import { bandForScore, bandForNormalizedScore } from '../bands'

describe('bandForScore', () => {
  it('maps integer values at each band lower bound', () => {
    expect(bandForScore(0)).toBe('Dissonant')
    expect(bandForScore(24)).toBe('Dissonant')
    expect(bandForScore(25)).toBe('Untuned')
    expect(bandForScore(44)).toBe('Untuned')
    expect(bandForScore(45)).toBe('Tuning')
    expect(bandForScore(64)).toBe('Tuning')
    expect(bandForScore(65)).toBe('Tuned')
    expect(bandForScore(79)).toBe('Tuned')
    expect(bandForScore(80)).toBe('Resonant')
    expect(bandForScore(100)).toBe('Resonant')
  })

  // ORPHEUS-95 regression: fractional composites in the one-unit gaps between
  // the inclusive integer ranges must map to the band below, not fall through
  // to the 'Dissonant' fallback.
  it('maps fractional values in the inter-band gaps to the band below', () => {
    expect(bandForScore(24.5)).toBe('Dissonant')
    expect(bandForScore(44.5)).toBe('Untuned')
    expect(bandForScore(64.5)).toBe('Tuning')
    expect(bandForScore(79.5)).toBe('Tuned')
    expect(bandForScore(79.13)).toBe('Tuned') // the live bug (Andrew, 2026-06-23)
  })

  it('clamps out-of-range scores', () => {
    expect(bandForScore(120)).toBe('Resonant')
    expect(bandForScore(-5)).toBe('Dissonant')
  })
})

describe('bandForNormalizedScore', () => {
  it('scales 0–1 to 0–100 before classifying', () => {
    expect(bandForNormalizedScore(0.72)).toBe('Tuned')
    expect(bandForNormalizedScore(0.7913)).toBe('Tuned')
    expect(bandForNormalizedScore(0.8)).toBe('Resonant')
  })
})
