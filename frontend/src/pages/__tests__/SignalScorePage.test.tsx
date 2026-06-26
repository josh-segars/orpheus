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
 *   - dimension cards show the always-visible summary with a read more /
 *     read less toggle for the combined narrative (ORPHEUS-69)
 *   - the metrics block renders forward_brief_data stats + profile
 *     signals (ORPHEUS-69)
 *   - the actions bar exposes the Cheat Sheet link; the Forward Brief
 *     surface is retired (ORPHEUS-69)
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

// ORPHEUS-71: SignalScorePage now resolves the report subject for the
// hero eyebrow via useSessionRoles + useAdvisorClients. Stub both so
// they don't hit React Query without a provider; data:undefined yields
// the "Your Composition" (self-view) default.
vi.mock('../../hooks/useSessionRoles', () => ({
  useSessionRoles: () => ({ data: undefined }),
}))
vi.mock('../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: () => ({ data: undefined }),
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

  it('renders all four dimension cards with their shortened display names (ORPHEUS-78)', () => {
    renderSignalScorePage()
    // Client-facing display names; internal names stay canonical upstream.
    expect(screen.getByText('Profile Clarity')).toBeInTheDocument()
    expect(screen.getByText('Signal Strength')).toBeInTheDocument()
    expect(screen.getByText('Signal Quality')).toBeInTheDocument()
    expect(screen.getByText('Alignment')).toBeInTheDocument()
    // The internal names must not leak to the card headers.
    expect(
      screen.queryByText('Profile Signal Clarity'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('Behavioral Signal Strength'),
    ).not.toBeInTheDocument()
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

  it('renders the server-provided band per dimension (ORPHEUS-22)', () => {
    // The client no longer derives the band from normalized_score; it reads
    // dimension.band from the API payload. Assert the rendered aria-label
    // for each dimension card uses the fixture's `band` value verbatim,
    // not a re-derivation from normalized_score.
    renderSignalScorePage()
    // ORPHEUS-78: the aria-label carries the client-facing display name,
    // not the internal dimension name.
    const displayNames: Record<string, string> = {
      'Profile Signal Clarity': 'Profile Clarity',
      'Behavioral Signal Strength': 'Signal Strength',
      'Behavioral Signal Quality': 'Signal Quality',
      'Profile-Behavior Alignment': 'Alignment',
    }
    for (const dim of demoJob.result!.scoring.scored_dimensions.dimensions) {
      const numeric = Math.round(dim.normalized_score * 100)
      const expected = new RegExp(
        `^${displayNames[dim.name] ?? dim.name} band: ${dim.band} — score ${numeric} of 100$`,
      )
      expect(
        screen.getByRole('group', { name: expected }),
      ).toBeInTheDocument()
    }
  })

  it('exposes the secondary "View My Reports" link (ORPHEUS-81) and primary "View My Quick Reference Card" link (ORPHEUS-78); the Forward Brief link is retired (ORPHEUS-69)', () => {
    renderSignalScorePage()
    // ORPHEUS-81: the secondary action targets the reports list, not
    // Groundwork — multi-report flow.
    const reports = screen.getByRole('link', { name: /view my reports/i })
    expect(reports).toHaveAttribute('href', '/reports')
    // ORPHEUS-76/78: user-facing copy says "View My Quick Reference Card";
    // the route and code identifiers keep the cheat-sheet name.
    const cs = screen.getByRole('link', {
      name: /view my quick reference card/i,
    })
    expect(cs).toHaveAttribute('href', '/jobs/demo/cheat-sheet')
    expect(
      screen.queryByRole('link', { name: /forward brief/i }),
    ).not.toBeInTheDocument()
  })

  it('shows the always-visible dimension summary and reveals the combined narrative behind a read more toggle (ORPHEUS-69)', async () => {
    const user = userEvent.setup()
    renderSignalScorePage()
    // The summary teaser is visible without interaction…
    expect(
      screen.getByText(/two recommendations is low for your stage/i),
    ).toBeInTheDocument()
    // …while the combined narrative is collapsed by default.
    const narrativeSnippet = /reads as substantive and credible/i
    expect(screen.queryByText(narrativeSnippet)).not.toBeInTheDocument()

    const toggles = screen.getAllByRole('button', { name: /read more/i })
    expect(toggles).toHaveLength(4) // one per dimension card
    await user.click(toggles[0])
    expect(screen.getByText(narrativeSnippet)).toBeInTheDocument()
    // Toggle flips to "Read less" and collapses on second click.
    const readLess = screen.getByRole('button', { name: /read less/i })
    await user.click(readLess)
    expect(screen.queryByText(narrativeSnippet)).not.toBeInTheDocument()
  })

  it('renders the metrics block with quantitative stats and profile signal flags (ORPHEUS-69)', () => {
    renderSignalScorePage()
    expect(
      screen.getByRole('heading', { name: /your numbers at a glance/i }),
    ).toBeInTheDocument()
    // Quantitative stat from forward_brief_data.quantitative.
    expect(screen.getByText('Followers')).toBeInTheDocument()
    expect(screen.getByText('1,247')).toBeInTheDocument()
    // Audience breakdown list.
    expect(screen.getByText('Management Consulting')).toBeInTheDocument()
    // Boolean flags render as the Profile Signals checklist.
    expect(screen.getByText('Profile Signals')).toBeInTheDocument()
    expect(screen.getByText('Profile photo present')).toBeInTheDocument()
    expect(
      screen.getByText('Engagement spread across your network'),
    ).toBeInTheDocument()
    // ORPHEUS-96: the brittle engagement_invitation rows (CTA / services /
    // contact) are no longer surfaced — they misfire on normal profiles and
    // would contradict the now-text-grounded narrative.
    expect(screen.queryByText('Call to action in About')).not.toBeInTheDocument()
    expect(screen.queryByText('Services section listed')).not.toBeInTheDocument()
    expect(screen.queryByText('Contact info visible')).not.toBeInTheDocument()
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
