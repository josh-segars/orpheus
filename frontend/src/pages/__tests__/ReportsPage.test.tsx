/**
 * ReportsPage (ORPHEUS-81) — the client's multi-report landing surface.
 *
 * Coverage scope:
 *   - One row per job: complete rows link to the report and show the
 *     band chip; in-flight rows link to the Analysis screen; failed
 *     rows render statically with no link.
 *   - "Run a New Report" links to /groundwork when no job is in
 *     flight, and is replaced by the in-progress note when one is.
 *   - Empty state points at the Groundwork Checklist.
 *
 * Uses the ORPHEUS-47 convention: vi.mock the data hook, render inside
 * MemoryRouter.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { useJobs } from '../../hooks/useJobs'
import type { JobSummary } from '../../types/job'
import { ReportsPage } from '../ReportsPage'

vi.mock('../../hooks/useJobs')

const COMPLETE_JOB: JobSummary = {
  id: 'job-complete-1',
  state: 'complete',
  created_at: '2026-06-01T12:00:00+00:00',
  band: 'Tuned',
}

const RUNNING_JOB: JobSummary = {
  id: 'job-running-1',
  state: 'running',
  created_at: '2026-06-12T12:00:00+00:00',
  band: null,
}

const FAILED_JOB: JobSummary = {
  id: 'job-failed-1',
  state: 'failed',
  created_at: '2026-05-20T12:00:00+00:00',
  band: null,
}

function mockJobs(jobs: JobSummary[]) {
  vi.mocked(useJobs).mockReturnValue({
    data: jobs,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useJobs>)
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ReportsPage />
    </MemoryRouter>,
  )
}

describe('ReportsPage', () => {
  it('renders a linked row per job: complete → report with band chip, in-flight → analysis, failed → static', () => {
    mockJobs([RUNNING_JOB, COMPLETE_JOB, FAILED_JOB])
    renderPage()

    const completeRow = screen.getByRole('link', { name: /view report/i })
    expect(completeRow).toHaveAttribute('href', '/jobs/job-complete-1')
    expect(screen.getByText('Tuned')).toBeInTheDocument()

    const inFlightRow = screen.getByRole('link', { name: /view progress/i })
    expect(inFlightRow).toHaveAttribute('href', '/jobs/job-running-1/analysis')

    // Failed row renders, but not as a link.
    expect(screen.getByText(/did not complete/i)).toBeInTheDocument()
    const links = screen.getAllByRole('link')
    expect(
      links.some((l) => l.getAttribute('href') === '/jobs/job-failed-1'),
    ).toBe(false)
  })

  it('shows "Run a New Report" → /groundwork when no job is in flight', () => {
    mockJobs([COMPLETE_JOB, FAILED_JOB])
    renderPage()

    const run = screen.getByRole('link', { name: /run a new report/i })
    expect(run).toHaveAttribute('href', '/groundwork')
    expect(
      screen.queryByText(/a report is in progress/i),
    ).not.toBeInTheDocument()
  })

  it('replaces the run button with the in-progress note while a job is in flight (frontend half of the ORPHEUS-81 run guard)', () => {
    mockJobs([RUNNING_JOB, COMPLETE_JOB])
    renderPage()

    expect(
      screen.queryByRole('link', { name: /run a new report/i }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/a report is in progress/i)).toBeInTheDocument()
  })

  it('renders the empty state with a Groundwork link when the client has no jobs', () => {
    mockJobs([])
    renderPage()

    expect(
      screen.getByText(/haven’t run a report yet/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /groundwork checklist/i }),
    ).toHaveAttribute('href', '/groundwork')
  })
})
