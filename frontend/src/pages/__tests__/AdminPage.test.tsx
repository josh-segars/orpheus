/**
 * AdminPage smoke + interaction tests — ORPHEUS-31.
 *
 * Same harness as ClientsPage.test.tsx — vi.mock the data hooks
 * rather than running an MSW server. Coverage:
 *
 *   1. Renders the clients table with rows from useAdminClients.
 *   2. Renders the unfiltered jobs table by default.
 *   3. Selecting a client filters the jobs pane (header changes,
 *      Clear filter shows up).
 *   4. Clicking a narrative chip opens the narrative editor and
 *      shows the loaded text.
 *   5. Saving the editor calls the update mutation with the form
 *      values.
 *
 * The narrative editor's success/error banners are intentionally
 * not asserted here — that's reaching into mutation state shape,
 * and the underlying hook is covered separately. Smoke-coverage
 * the click-through; deep state-machine coverage can land per-
 * feature.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import type {
  AdminClient,
  AdminJob,
  AdminNarrative,
} from '../../hooks/useAdmin'
import { AdminPage } from '../AdminPage'

// --------------------------------------------------------------------------- //
// Module mocks
//
// `vi.mock(... factory)` runs before the test body, so the inline
// fixture references must be defined inside the factory (or the imports
// happen before the values exist). We expose mutable refs that test
// cases can update before render.
// --------------------------------------------------------------------------- //

const mockClientsRef: { data: AdminClient[]; isLoading: boolean; isError: boolean } = {
  data: [],
  isLoading: false,
  isError: false,
}
const mockJobsArgRef: { clientId: string | null } = { clientId: null }
const mockJobsRef: { data: AdminJob[]; isLoading: boolean; isError: boolean } = {
  data: [],
  isLoading: false,
  isError: false,
}
const mockNarrativeRef: {
  data: AdminNarrative | null
  isLoading: boolean
  isError: boolean
} = {
  data: null,
  isLoading: false,
  isError: false,
}
const mockMutateAsync = vi.fn()

vi.mock('../../lib/auth', () => ({
  useSession: () => ({
    session: { user: { email: 'admin@example.com', user_metadata: {} } },
    status: 'authenticated',
  }),
}))

vi.mock('../../hooks/useAdmin', () => ({
  isAdminEmail: () => true,
  extractAdminErrorMessage: () => 'admin error',
  useAdminClients: () => ({
    data: { clients: mockClientsRef.data },
    isLoading: mockClientsRef.isLoading,
    isError: mockClientsRef.isError,
  }),
  useAdminJobs: (clientId: string | null) => {
    mockJobsArgRef.clientId = clientId
    return {
      data: { jobs: mockJobsRef.data },
      isLoading: mockJobsRef.isLoading,
      isError: mockJobsRef.isError,
    }
  },
  useAdminNarrative: (_narrativeId: string | null) => ({
    data: mockNarrativeRef.data,
    isLoading: mockNarrativeRef.isLoading,
    isError: mockNarrativeRef.isError,
  }),
  useUpdateAdminNarrative: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
}))

// --------------------------------------------------------------------------- //
// Fixtures + render helper
// --------------------------------------------------------------------------- //

const mockClients: AdminClient[] = [
  {
    id: 'client-uuid-a',
    display_name: 'Client A',
    email: 'a@example.com',
    invitation_status: 'accepted',
    created_at: '2026-05-10T00:00:00+00:00',
    user_id: 'user-a',
    advisor: {
      id: 'advisor-uuid-1',
      practice_name: "Andrew's Practice",
      email: 'andrew@ess3.ai',
    },
    latest_job: { id: 'job-uuid-1', status: 'complete', created_at: null },
  },
  {
    id: 'client-uuid-b',
    display_name: 'Client B',
    email: 'b@example.com',
    invitation_status: 'pending',
    created_at: '2026-05-05T00:00:00+00:00',
    user_id: null,
    advisor: {
      id: 'advisor-uuid-2',
      practice_name: null,
      email: 'advisor-b@example.com',
    },
    latest_job: null,
  },
]

const mockJobs: AdminJob[] = [
  {
    id: 'job-uuid-1',
    client_id: 'client-uuid-a',
    client_display_name: 'Client A',
    client_email: 'a@example.com',
    status: 'complete',
    version_label: 'v2',
    created_at: '2026-05-12T00:00:00+00:00',
    started_at: null,
    completed_at: '2026-05-12T00:01:00+00:00',
    error_message: null,
    narratives: [
      {
        id: 'narr-uuid-1',
        section: 'Profile Signal Clarity',
        status: 'draft',
        has_edited_text: false,
        published_at: null,
        generated_at: '2026-05-12T00:00:30+00:00',
      },
    ],
  },
]

function resetMocks() {
  mockClientsRef.data = mockClients
  mockClientsRef.isLoading = false
  mockClientsRef.isError = false
  mockJobsRef.data = mockJobs
  mockJobsRef.isLoading = false
  mockJobsRef.isError = false
  mockJobsArgRef.clientId = null
  mockNarrativeRef.data = null
  mockNarrativeRef.isLoading = false
  mockNarrativeRef.isError = false
  mockMutateAsync.mockReset()
  mockMutateAsync.mockResolvedValue({})
}

function renderAdmin() {
  return render(
    <MemoryRouter>
      <AdminPage />
    </MemoryRouter>,
  )
}

// --------------------------------------------------------------------------- //
// Tests
// --------------------------------------------------------------------------- //

describe('AdminPage', () => {
  beforeEach(() => {
    resetMocks()
  })

  it('renders the clients table with rows from useAdminClients', () => {
    renderAdmin()
    // "Client A" appears in both the clients table (display_name) and
    // the jobs table (client_display_name); assert >= 1 occurrence
    // rather than a unique getByText.
    expect(screen.getAllByText('Client A').length).toBeGreaterThan(0)
    expect(screen.getByText('Client B')).toBeInTheDocument()
    expect(screen.getByText("Andrew's Practice")).toBeInTheDocument()
  })

  it('renders the jobs table unfiltered by default', () => {
    renderAdmin()
    expect(
      screen.getByRole('heading', { level: 2, name: /jobs \(all\)/i }),
    ).toBeInTheDocument()
    // Job row is visible (matches the section name from the fixture).
    expect(screen.getByText('Profile Signal Clarity')).toBeInTheDocument()
  })

  it('filters the jobs pane to the selected client', async () => {
    const user = userEvent.setup()
    renderAdmin()
    const viewJobsButton = screen.getAllByRole('button', { name: /view jobs/i })[0]
    await user.click(viewJobsButton)
    expect(
      screen.getByRole('heading', { level: 2, name: /jobs \(filtered\)/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /clear filter/i }),
    ).toBeInTheDocument()
    expect(mockJobsArgRef.clientId).toBe('client-uuid-a')
  })

  it('opens the narrative editor with loaded text when a chip is clicked', async () => {
    mockNarrativeRef.data = {
      id: 'narr-uuid-1',
      job_id: 'job-uuid-1',
      section: 'Profile Signal Clarity',
      generated_text: 'Generated paragraph from the agent.',
      edited_text: 'Hand-polished version.',
      status: 'draft',
      published_at: null,
      generated_at: '2026-05-12T00:00:30+00:00',
    }
    const user = userEvent.setup()
    renderAdmin()
    await user.click(
      screen.getByRole('button', { name: /profile signal clarity/i }),
    )
    expect(
      screen.getByRole('heading', { level: 2, name: /narrative editor/i }),
    ).toBeInTheDocument()
    // Edited-text textarea is pre-populated.
    expect(
      screen.getByDisplayValue('Hand-polished version.'),
    ).toBeInTheDocument()
    // Generated text shows up read-only.
    expect(
      screen.getByDisplayValue('Generated paragraph from the agent.'),
    ).toBeInTheDocument()
  })

  it('calls the update mutation when the editor saves', async () => {
    mockNarrativeRef.data = {
      id: 'narr-uuid-1',
      job_id: 'job-uuid-1',
      section: 'Profile Signal Clarity',
      generated_text: 'Generated.',
      edited_text: 'Original edit.',
      status: 'draft',
      published_at: null,
      generated_at: '2026-05-12T00:00:30+00:00',
    }
    const user = userEvent.setup()
    renderAdmin()
    await user.click(
      screen.getByRole('button', { name: /profile signal clarity/i }),
    )
    await user.click(
      screen.getByRole('button', { name: /save narrative/i }),
    )
    expect(mockMutateAsync).toHaveBeenCalledWith({
      narrativeId: 'narr-uuid-1',
      body: { edited_text: 'Original edit.', status: 'draft' },
    })
  })
})
