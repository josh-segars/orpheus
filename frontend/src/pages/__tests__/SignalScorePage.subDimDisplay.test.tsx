/**
 * SignalScorePage sub-dim display-name remap — ORPHEUS-21.
 *
 * Five canonical sub-dim names get a client-facing display swap on
 * the leaf row; eight others pass through unchanged. This file mocks
 * useJob with a hand-rolled fixture that uses canonical names for each
 * of the five rename targets, plus one passthrough name, so the swap
 * is exercised end-to-end via the rendered DOM rather than via an
 * exported pure function. Internal names stay canonical everywhere
 * upstream; the map exists only at the leaf-row label.
 *
 * Lives in a separate file from SignalScorePage.test.tsx because that
 * suite mocks useJob with the design-playground demoJob fixture (which
 * uses aspirational labels that don't match the rename map). vitest's
 * module-level vi.mock pattern doesn't compose cleanly per-test, so
 * a separate file is the path with least magic.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import { SignalScorePage } from '../SignalScorePage'
import type { Job } from '../../types/job'

// --------------------------------------------------------------------------- //
// Module mocks — same asset stub strategy as SignalScorePage.test.tsx
// --------------------------------------------------------------------------- //

vi.mock('../../assets/wave-1-dissonant.png', () => ({ default: 'wave-1-stub' }))
vi.mock('../../assets/wave-2-untuned.png', () => ({ default: 'wave-2-stub' }))
vi.mock('../../assets/wave-3-tuning.png', () => ({ default: 'wave-3-stub' }))
vi.mock('../../assets/wave-4-tuned.png', () => ({ default: 'wave-4-stub' }))
vi.mock('../../assets/wave-5-resonant.png', () => ({ default: 'wave-5-stub' }))

const fixtureJob: Job = {
  id: 'remap',
  state: 'complete',
  created_at: '2026-06-03T00:00:00Z',
  updated_at: '2026-06-03T00:00:01Z',
  client_id: 'remap-client',
  error: null,
  result: {
    scoring: {
      scored_dimensions: {
        composite: 50.0,
        band: 'Tuning',
        dimensions: [
          {
            name: 'Profile Signal Clarity',
            weight: 0.35,
            confidence: 'CONFIRMED',
            normalized_score: 0.60,
            contribution: 21.0,
            band: 'Tuning',
            completeness_floor_applied: false,
            sub_dimensions: [
              // Renamed: Experience Description Quality → Experience Narrative
              {
                name: 'Experience Description Quality',
                score: 3,
                scale: '1-5',
                method: 'rubric',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary: 'Experience summary.',
                best_practices: 'Experience standard.',
                improvements: ['Experience action.'],
              },
              // Passthrough: Headline Clarity stays as-is
              {
                name: 'Headline Clarity',
                score: 3,
                scale: '1-5',
                method: 'rubric',
                confidence: 'CONFIRMED',
                raw_value: null,
                summary: 'Headline summary.',
                best_practices: 'Headline standard.',
                improvements: ['Headline action.'],
              },
            ],
          },
          {
            name: 'Behavioral Signal Strength',
            weight: 0.30,
            confidence: 'CONFIRMED',
            normalized_score: 0.55,
            contribution: 16.5,
            band: 'Tuning',
            completeness_floor_applied: false,
            sub_dimensions: [
              // Renamed: History Depth → Engagement History
              {
                name: 'History Depth',
                score: 4,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: 320,
                summary: 'History summary.',
                improvements: ['History action.'],
              },
            ],
          },
          {
            name: 'Behavioral Signal Quality',
            weight: 0.20,
            confidence: 'CONFIRMED',
            normalized_score: 0.50,
            contribution: 10.0,
            band: 'Tuning',
            completeness_floor_applied: false,
            sub_dimensions: [
              // Renamed: Outbound Engagement Presence → Engagement Volume
              {
                name: 'Outbound Engagement Presence',
                score: 3,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: 200,
                summary: 'Outbound summary.',
                best_practices: 'Outbound standard.',
                improvements: ['Outbound action.'],
              },
              // Renamed: Engagement Quality Score → Substantive Engagement
              {
                name: 'Engagement Quality Score',
                score: 3,
                scale: '0-5',
                method: 'quantitative',
                confidence: 'CONFIRMED',
                raw_value: 90,
                summary: 'Quality summary.',
                best_practices: 'Quality standard.',
                improvements: ['Quality action.'],
              },
            ],
          },
          {
            name: 'Profile-Behavior Alignment',
            weight: 0.15,
            confidence: 'INFERRED',
            normalized_score: 0.50,
            contribution: 7.5,
            band: 'Tuning',
            completeness_floor_applied: false,
            sub_dimensions: [
              // Renamed: Profile-Content Coherence → Profile-Content Match
              {
                name: 'Profile-Content Coherence',
                score: 3,
                scale: '1-5',
                method: 'rubric',
                confidence: 'INFERRED',
                raw_value: null,
                summary: 'Coherence summary.',
                best_practices: 'Coherence standard.',
                improvements: ['Coherence action.'],
              },
            ],
          },
        ],
      },
      forward_brief_data: {
        quantitative: {
          follower_count: null,
          follower_growth_rate: null,
          unique_members_reached: null,
          avg_impressions_per_post: null,
          avg_engagement_rate: null,
          top_post_impressions: null,
          audience_seniority: null,
          audience_industries: null,
          audience_geography: null,
          top_organizations: null,
          avg_comment_length_words: null,
          longest_posting_gap_weeks: null,
          zero_post_week_pct: null,
        },
        qualitative_flags: {
          viewer_actor_affinity: { concentrated: false, top_targets: [] },
          visual_professionalism: { photo_present: true },
          engagement_invitation: {
            services_present: false,
            contact_visible: false,
            cta_in_about: false,
          },
        },
      },
    },
    narratives: {
      dimension_narratives: {
        'Profile Signal Clarity': 'Dim narrative.',
        'Behavioral Signal Strength': 'Dim narrative.',
        'Behavioral Signal Quality': 'Dim narrative.',
        'Profile-Behavior Alignment': 'Dim narrative.',
      },
      forward_brief: 'Forward brief.',
      cheat_sheet: null,
    },
  },
}

vi.mock('../../hooks/useJob', () => ({
  useJob: () => ({ data: fixtureJob, isLoading: false, error: null }),
}))

// ORPHEUS-71: stub the hero subject-resolution hooks (see SignalScorePage).
vi.mock('../../hooks/useSessionRoles', () => ({
  useSessionRoles: () => ({ data: undefined }),
}))
vi.mock('../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: () => ({ data: undefined }),
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/jobs/remap']}>
      <Routes>
        <Route path="/jobs/:jobId" element={<SignalScorePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// --------------------------------------------------------------------------- //
// Assertions
// --------------------------------------------------------------------------- //

describe('SignalScorePage sub-dimension display-name remap', () => {
  it('renders the five renamed sub-dims with their client-facing labels', () => {
    renderPage()
    expect(screen.getByText('Experience Narrative')).toBeInTheDocument()
    expect(screen.getByText('Engagement History')).toBeInTheDocument()
    expect(screen.getByText('Engagement Volume')).toBeInTheDocument()
    expect(screen.getByText('Substantive Engagement')).toBeInTheDocument()
    expect(screen.getByText('Profile-Content Match')).toBeInTheDocument()
  })

  it('does not render the internal names for the five renamed sub-dims', () => {
    renderPage()
    // The internal names must NOT appear in any rendered text — they are
    // backend-only identifiers. If they leak through, the display map's
    // ?? sub.name fallback fired by accident.
    expect(screen.queryByText('Experience Description Quality')).not.toBeInTheDocument()
    expect(screen.queryByText('History Depth')).not.toBeInTheDocument()
    expect(screen.queryByText('Outbound Engagement Presence')).not.toBeInTheDocument()
    expect(screen.queryByText('Engagement Quality Score')).not.toBeInTheDocument()
    expect(screen.queryByText('Profile-Content Coherence')).not.toBeInTheDocument()
  })

  it('leaves sub-dims that are not in the rename map unchanged', () => {
    renderPage()
    // Headline Clarity is the passthrough fixture entry — internal name
    // and display name are the same.
    expect(screen.getByText('Headline Clarity')).toBeInTheDocument()
  })
})
