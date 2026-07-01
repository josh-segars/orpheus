/**
 * SignalScorePage data-limited banner — ORPHEUS-88.
 *
 * The report page renders a "based on limited data" banner above the
 * dimensions when the job result carries `quality.data_limited`. The
 * specific quality messages are listed for the client. When the flag is
 * absent/false (a healthy report, or any pre-88 job whose payload has no
 * quality block) the banner is not rendered.
 *
 * Per the ORPHEUS-47 convention we vi.mock the data hook; a hoisted
 * mutable ref lets the two cases swap the job the hook returns.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { SignalScorePage } from '../SignalScorePage'
import { demoJob } from '../../mocks/fixtures/signalScoreJob'
import type { Job } from '../../types/job'

vi.mock('../../assets/wave-1-dissonant.png', () => ({ default: 'w1' }))
vi.mock('../../assets/wave-2-untuned.png', () => ({ default: 'w2' }))
vi.mock('../../assets/wave-3-tuning.png', () => ({ default: 'w3' }))
vi.mock('../../assets/wave-4-tuned.png', () => ({ default: 'w4' }))
vi.mock('../../assets/wave-5-resonant.png', () => ({ default: 'w5' }))

const { jobRef } = vi.hoisted(() => ({ jobRef: { current: null as Job | null } }))

vi.mock('../../hooks/useJob', () => ({
  useJob: () => ({ data: jobRef.current, isLoading: false, error: null }),
}))
vi.mock('../../hooks/useSessionRoles', () => ({
  useSessionRoles: () => ({ data: undefined }),
}))
vi.mock('../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: () => ({ data: undefined }),
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/jobs/demo']}>
      <Routes>
        <Route path="/jobs/:jobId" element={<SignalScorePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const NOTICE =
  'No behavioral data found (zero posts, comments, and reactions) — ' +
  'Dimensions 2, 3, and 4 cannot be scored meaningfully'

describe('SignalScorePage data-limited banner (ORPHEUS-88)', () => {
  it('renders the banner with notices when the report is data-limited', () => {
    jobRef.current = {
      ...demoJob,
      result: {
        ...demoJob.result!,
        quality: { data_limited: true, notices: [NOTICE] },
      },
    }
    renderPage()

    expect(
      screen.getByText(/this report is based on limited data/i),
    ).toBeInTheDocument()
    expect(screen.getByText(NOTICE)).toBeInTheDocument()
    // The banner is a labelled note region.
    expect(
      screen.getByRole('note', { name: /data limitations/i }),
    ).toBeInTheDocument()
  })

  it('omits the banner for a healthy report (no quality block)', () => {
    jobRef.current = demoJob // fixture has no `quality` field
    renderPage()

    expect(
      screen.queryByText(/this report is based on limited data/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('note', { name: /data limitations/i })).toBeNull()
  })
})
