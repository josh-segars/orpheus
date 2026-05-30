/**
 * SignalScorePage smoke test — ORPHEUS-50 + ORPHEUS-51.
 *
 * Proof-of-life for the Signal Score page after the ORPHEUS-51 hero
 * restructure. Per the ORPHEUS-47 convention, vi.mock the data hook
 * (useJob) rather than running an MSW server.
 *
 * Coverage scope:
 *   - hero renders the composite band label as the h1
 *   - the composite numeric score is sr-only inside the hero (a11y)
 *   - hero img uses the band-keyed waveform asset (band → asset mapping)
 *   - each dimension renders its name + a band-pills row with a
 *     dimension-aware aria-label (sr-only fallback for color-only band)
 *   - sub-dimension rows render with their 5-pip rating displays and
 *     expand to reveal Summary / Best Practices / Improvements
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
// The five band-keyed waveform JPGs are resolved by Vite at build time;
// jsdom doesn't load them, so each mock returns a unique stub string. That
// way the rendered <img src> can be asserted against the band-to-asset
// mapping. useJob is mocked to return the demoJob fixture.
// --------------------------------------------------------------------------- //

vi.mock('../../assets/wave-1-dissonant.png', () => ({ default: 'wave-1-dissonant-stub' }))
vi.mock('../../assets/wave-2-untuned.png', () => ({ default: 'wave-2-untuned-stub' }))
vi.mock('../../assets/wave-3-tuning.png', () => ({ default: 'wave-3-tuning-stub' }))
vi.mock('../../assets/wave-4-tuned.png', () => ({ default: 'wave-4-tuned-stub' }))
vi.mock('../../assets/wave-5-resonant.png', () => ({ default: 'wave-5-resonant-stub' }))

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
    // The h1's accessible name now combines the visible band label with
    // the sr-only composite-score string; match the visible substring.
    expect(
      screen.getByRole('heading', { level: 1, name: /Tuning/i }),
    ).toBeInTheDocument()
  })

  it('exposes the composite numeric score as sr-only text inside the hero heading (ORPHEUS-51)', () => {
    renderSignalScorePage()
    // demoJob.scoring.scored_dimensions.composite is 58.
    expect(
      screen.getByText(/composite score 58 of 100/i),
    ).toBeInTheDocument()
  })

  it('uses the band-keyed waveform asset for the hero (ORPHEUS-51)', () => {
    renderSignalScorePage()
    // demoJob.scoring.scored_dimensions.band is 'Tuning' → the Tuning
    // asset should resolve via bandToWaveform().
    const img = document.querySelector('.score-hero-waves') as HTMLImageElement | null
    expect(img).not.toBeNull()
    expect(img!.src).toContain('wave-3-tuning-stub')
  })

  it('renders all four dimension cards with their names', () => {
    renderSignalScorePage()
    expect(screen.getByText('Profile Signal Clarity')).toBeInTheDocument()
    expect(screen.getByText('Behavioral Signal Strength')).toBeInTheDocument()
    expect(screen.getByText('Behavioral Signal Quality')).toBeInTheDocument()
    expect(screen.getByText('Profile-Behavior Alignment')).toBeInTheDocument()
  })

  it('renders a 5-pill band row per dimension with a score-aware aria-label (ORPHEUS-51)', () => {
    renderSignalScorePage()
    // Each dimension card's band-pills group has aria-label of the form
    // "<DimName> band: <Band> — score <N> of 100"; match the shape
    // rather than any specific dimension name.
    const groups = screen.getAllByRole('group', {
      name: /band: .* score \d+ of 100/i,
    })
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
    // Headline specificity is a rubric sub-dim with summary / best_practices /
    // improvements all populated in the fixture.
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
