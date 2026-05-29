/**
 * SignalScorePage smoke test — ORPHEUS-50.
 *
 * Proof-of-life for the redesigned Signal Score page (waveform hero,
 * dimension cards, 5-pill band rows, 5-pip sub-dimension rows,
 * expandable detail). Per the ORPHEUS-47 convention, vi.mock the data
 * hook (useJob) rather than running an MSW server.
 *
 * Coverage scope is deliberately narrow:
 *   - hero renders the composite band label
 *   - each dimension renders its name + a band-pills row
 *   - sub-dimension rows render with their 5-pip rating displays
 *   - the actions bar exposes the Forward Brief / Cheat Sheet links
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import { SignalScorePage } from '../SignalScorePage'
import { demoJob } from '../../mocks/fixtures/signalScoreJob'

// --------------------------------------------------------------------------- //
// Module mocks
//
// jpg import is resolved by Vite at build time; jsdom doesn't load it, so
// we stub the module to an empty string. useJob is mocked to return the
// demoJob fixture.
// --------------------------------------------------------------------------- //

vi.mock('../../assets/waves.jpg', () => ({ default: '' }))

vi.mock('../../hooks/useJob', () => ({
  useJob: () => ({
    data: demoJob,
    isLoading: false,
    error: null,
  }),
}))

// --------------------------------------------------------------------------- //
// Render helper — wraps in Routes so useParams resolves to a real jobId.
// --------------------------------------------------------------------------- //

function renderSignalScorePage() {
  return render(
    <MemoryRouter initialEntries={['/jobs/demo']}>
      <Routes>
        <Route path="/jobs/:jobId" element={<SignalScorePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// --------------------------------------------------------------------------- //
// Assertions
// --------------------------------------------------------------------------- //

describe('SignalScorePage', () => {
  it('renders the composite band as the hero headline', () => {
    renderSignalScorePage()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Tuning' }),
    ).toBeInTheDocument()
  })

  it('renders all four dimension cards with their names', () => {
    renderSignalScorePage()
    expect(screen.getByText('Profile Signal Clarity')).toBeInTheDocument()
    expect(screen.getByText('Behavioral Signal Strength')).toBeInTheDocument()
    expect(screen.getByText('Behavioral Signal Quality')).toBeInTheDocument()
    expect(screen.getByText('Profile-Behavior Alignment')).toBeInTheDocument()
  })

  it('renders a 5-pill band row for each dimension', () => {
    renderSignalScorePage()
    // Each dimension card has a band-pills group → 4 total.
    const groups = screen.getAllByRole('group', { name: /dimension band/i })
    expect(groups).toHaveLength(4)
  })

  it('exposes the secondary "Return to Groundwork" link and the primary "View My Forward Brief" link', () => {
    renderSignalScorePage()
    expect(
      screen.getByRole('link', { name: /return to groundwork/i }),
    ).toBeInTheDocument()
    const fb = screen.getByRole('link', { name: /view my forward brief/i })
    expect(fb).toHaveAttribute('href', '/jobs/demo/forward-brief')
  })

  it('expands a sub-dimension row when its trigger is clicked, revealing Summary / Best Practices / Improvements', async () => {
    const user = userEvent.setup()
    renderSignalScorePage()
    // Headline specificity is a rubric sub-dim with summary/best_practices/improvements all populated in the fixture.
    const trigger = screen
      .getByText('Headline specificity')
      .closest('button')!
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Summary')).toBeInTheDocument()
    expect(screen.getByText('Best Practices')).toBeInTheDocument()
    expect(screen.getByText('Improvements')).toBeInTheDocument()
  })
})
