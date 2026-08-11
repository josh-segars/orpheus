/**
 * ORPHEUS-114 (f) — the "How this score is computed" methodology block.
 *
 * Renders dimension weights + the signal-band ladder from the payload's
 * methodology facts. The negative sweep extends ORPHEUS-128: the block
 * must contain only generic scale facts — never the client's composite or
 * per-dimension contributions (the fixture's 58.0 / 25.2 / 16.5 / 12.2 /
 * 10.8 must not appear inside it).
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { SignalScorePage } from '../SignalScorePage'
import { demoJob } from '../../mocks/fixtures/signalScoreJob'
import type { Job, Methodology } from '../../types/job'

vi.mock('../../assets/wave-1-dissonant.png', () => ({ default: 'wave-1-stub' }))
vi.mock('../../assets/wave-2-untuned.png', () => ({ default: 'wave-2-stub' }))
vi.mock('../../assets/wave-3-tuning.png', () => ({ default: 'wave-3-stub' }))
vi.mock('../../assets/wave-4-tuned.png', () => ({ default: 'wave-4-stub' }))
vi.mock('../../assets/wave-5-resonant.png', () => ({ default: 'wave-5-stub' }))

let mockJob: Job

vi.mock('../../hooks/useJob', () => ({
  useJob: () => ({ data: mockJob, isLoading: false, error: null }),
}))
vi.mock('../../hooks/useSessionRoles', () => ({
  useSessionRoles: () => ({ data: undefined }),
}))
vi.mock('../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: () => ({ data: undefined }),
}))

const METHODOLOGY: Methodology = {
  dimension_weights: {
    'Profile Signal Clarity': 0.35,
    'Behavioral Signal Strength': 0.3,
    'Behavioral Signal Quality': 0.2,
    'Profile-Behavior Alignment': 0.15,
  },
  bands: [
    { name: 'Dissonant', min: 0 },
    { name: 'Untuned', min: 25 },
    { name: 'Tuning', min: 45 },
    { name: 'Tuned', min: 65 },
    { name: 'Resonant', min: 80 },
  ],
  formula: 'weighted_normalized_sum',
  snapshot: true,
}

function jobWithMethodology(): Job {
  return {
    ...(demoJob as Job),
    result: {
      ...(demoJob as Job).result!,
      methodology: METHODOLOGY,
    },
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/jobs/demo']}>
      <Routes>
        <Route path="/jobs/:jobId" element={<SignalScorePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SignalScorePage methodology block (ORPHEUS-114 f)', () => {
  it('renders the four dimension weights and the five-band ladder', () => {
    mockJob = jobWithMethodology()
    renderPage()

    const block = screen.getByRole('region', {
      name: /how this score is computed/i,
    })
    expect(block).toBeInTheDocument()
    // Weights render as percentages against display names (ORPHEUS-78 map).
    expect(block).toHaveTextContent('Profile Clarity')
    expect(block).toHaveTextContent('35%')
    expect(block).toHaveTextContent('30%')
    expect(block).toHaveTextContent('20%')
    expect(block).toHaveTextContent('15%')
    // Band ladder with half-open ranges, top band open-ended.
    expect(block).toHaveTextContent('0–24')
    expect(block).toHaveTextContent('25–44')
    expect(block).toHaveTextContent('45–64')
    expect(block).toHaveTextContent('65–79')
    expect(block).toHaveTextContent('80+')
  })

  it('contains no client-specific numbers (ORPHEUS-128 negative sweep)', () => {
    mockJob = jobWithMethodology()
    renderPage()

    const block = screen.getByRole('region', {
      name: /how this score is computed/i,
    })
    // The fixture's composite and per-dimension contributions must not
    // leak into the methodology block in any modality.
    for (const clientNumber of ['58.0', '25.2', '16.5', '12.2', '10.8']) {
      expect(block).not.toHaveTextContent(clientNumber)
    }
    expect(block.querySelectorAll('.sr-only')).toHaveLength(0)
    expect(block.querySelectorAll('[aria-hidden]')).toHaveLength(0)
  })

  it('renders nothing when the payload has no methodology', () => {
    const job = jobWithMethodology()
    delete job.result!.methodology
    mockJob = job
    renderPage()

    expect(
      screen.queryByRole('region', { name: /how this score is computed/i }),
    ).not.toBeInTheDocument()
  })
})
