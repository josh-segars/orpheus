/**
 * CheatSheetPage subtitle test — ORPHEUS-74.
 *
 * Regression coverage for the "prepared for C7af460c 19fa 4145 …" bug:
 * the old formatClientName(job.client_id) helper title-cased real client
 * UUIDs into junk. The page now resolves the report subject the way the
 * Signal Score hero does post-ORPHEUS-71 (useSessionRoles +
 * useAdvisorClients roster lookup). Per the ORPHEUS-47 convention, the
 * data hooks are vi.mocked rather than running an MSW server.
 *
 * Coverage scope:
 *   - self-view (no advisor role): no "prepared for" clause, and no
 *     title-cased UUID fragments leak into the subtitle
 *   - advisor viewing a non-self client: "prepared for [display_name]"
 *     from the roster
 *   - dual-role advisor on their own self-report (is_self): no clause
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import { CheatSheetPage } from '../CheatSheetPage'
import { demoJob } from '../../mocks/fixtures/signalScoreJob'

// Real-shaped UUID standing in for the cloud client id that surfaced the
// bug during ORPHEUS-73 live validation.
const CLIENT_UUID = 'c7af460c-19fa-4145-ac95-990c4ec731d1'

const uuidJob = { ...demoJob, client_id: CLIENT_UUID }

// Mutable hook returns — reassigned per test, reset in beforeEach.
let mockSessionRoles: { data: { advisor_id: string | null } | undefined } = {
  data: undefined,
}
let mockAdvisorClients: {
  data:
    | { clients: { id: string; display_name: string; is_self: boolean }[] }
    | undefined
} = { data: undefined }

vi.mock('../../hooks/useJob', () => ({
  useJob: () => ({ data: uuidJob, isLoading: false, error: null }),
}))
vi.mock('../../hooks/useSessionRoles', () => ({
  useSessionRoles: () => mockSessionRoles,
}))
vi.mock('../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: () => mockAdvisorClients,
}))

function renderCheatSheetPage() {
  return render(
    <MemoryRouter initialEntries={[`/jobs/${uuidJob.id}/cheat-sheet`]}>
      <Routes>
        <Route path="/jobs/:jobId/cheat-sheet" element={<CheatSheetPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CheatSheetPage subtitle (ORPHEUS-74)', () => {
  beforeEach(() => {
    mockSessionRoles = { data: undefined }
    mockAdvisorClients = { data: undefined }
  })

  it('renders no "prepared for" clause on a self-view, and never title-cases the client UUID', () => {
    renderCheatSheetPage()
    expect(screen.getByText(/priorities and weekly rhythm/i)).toBeInTheDocument()
    expect(screen.queryByText(/prepared for/i)).not.toBeInTheDocument()
    // The old formatClientName output for this UUID started "C7af460c".
    expect(screen.queryByText(/C7af460c/)).not.toBeInTheDocument()
  })

  it('shows the roster display_name when an advisor views a non-self client report', () => {
    mockSessionRoles = { data: { advisor_id: 'advisor-1' } }
    mockAdvisorClients = {
      data: {
        clients: [
          { id: CLIENT_UUID, display_name: 'Andrew Segars', is_self: false },
        ],
      },
    }
    renderCheatSheetPage()
    expect(
      screen.getByText(/prepared for Andrew Segars/),
    ).toBeInTheDocument()
  })

  it('drops the clause for a dual-role advisor viewing their own self-report (is_self)', () => {
    mockSessionRoles = { data: { advisor_id: 'advisor-1' } }
    mockAdvisorClients = {
      data: {
        clients: [
          { id: CLIENT_UUID, display_name: 'Andrew (self)', is_self: true },
        ],
      },
    }
    renderCheatSheetPage()
    expect(screen.queryByText(/prepared for/i)).not.toBeInTheDocument()
  })
})
