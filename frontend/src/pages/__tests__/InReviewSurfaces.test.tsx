/**
 * ORPHEUS-120 — the "advisor is reviewing" client surfaces.
 *
 * A complete advisory job whose report the advisor hasn't released yet
 * comes back with `result: null` + `in_review: true`. Both report pages
 * must render the distinct In Review surface — not Analysis-in-Progress
 * (the pipeline is done) and not the report (the payload is gated).
 *
 * Uses the ORPHEUS-47 convention: vi.mock the data hooks, render inside
 * MemoryRouter. useJob is mocked with a mutable holder so each test can
 * vary the job shape.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Job } from '../../types/job'
import { CheatSheetPage } from '../CheatSheetPage'
import { SignalScorePage } from '../SignalScorePage'

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

function inReviewJob(): Job {
  return {
    id: 'job-in-review-1',
    state: 'complete',
    created_at: '2026-08-11T12:00:00+00:00',
    updated_at: null,
    client_id: 'client-1',
    result: null,
    error: null,
    in_review: true,
  }
}

function renderAt(path: string, element: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/jobs/:jobId" element={element} />
        <Route path="/jobs/:jobId/cheat-sheet" element={element} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ORPHEUS-120 in-review surfaces', () => {
  it('SignalScorePage renders the In Review surface, not Analysis-in-Progress', () => {
    mockJob = inReviewJob()
    renderAt('/jobs/job-in-review-1', <SignalScorePage />)

    expect(
      screen.getByText(/your advisor is reviewing your report/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/in review/i)).toBeInTheDocument()
    expect(
      screen.queryByText(/still being prepared/i),
    ).not.toBeInTheDocument()
  })

  it('SignalScorePage keeps Analysis-in-Progress for a running job', () => {
    mockJob = { ...inReviewJob(), state: 'running', in_review: false }
    renderAt('/jobs/job-in-review-1', <SignalScorePage />)

    expect(
      screen.getByText(/still being prepared/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/your advisor is reviewing/i),
    ).not.toBeInTheDocument()
  })

  it('CheatSheetPage renders the In Review surface for a gated job', () => {
    mockJob = inReviewJob()
    renderAt('/jobs/job-in-review-1/cheat-sheet', <CheatSheetPage />)

    expect(
      screen.getByText(/your advisor is reviewing your report/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/still being prepared/i),
    ).not.toBeInTheDocument()
  })
})
