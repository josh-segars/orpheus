/**
 * ClientsPage smoke test — ORPHEUS-47.
 *
 * Proof-of-life for the vitest + RTL toolchain and a regression for
 * the ORPHEUS-46 "View report" uncloak. Per the locked scope decisions
 * for ORPHEUS-47 (see Plane comment): vi.mock the data hooks rather
 * than running an MSW node server, and keep this test minimal — header,
 * invite form, View report visibility on a non-self complete row.
 *
 * Future ClientsPage tests (banner state machine, optimistic invite
 * insert, resend flow, empty-state suppression) should land per-feature
 * rather than ballooning this file.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { ClientsPage } from '../ClientsPage'
import type { AdvisorClient } from '../../../hooks/useAdvisorClients'

// --------------------------------------------------------------------------- //
// Module mocks
//
// vi.mock is hoisted by vitest to the top of the file, so it runs before
// ClientsPage's transitive imports resolve. Mocking '../../../lib/auth'
// in particular short-circuits the import of '../../../lib/supabase',
// which would otherwise demand VITE_SUPABASE_* at module-load time.
// --------------------------------------------------------------------------- //

vi.mock('../../../lib/auth', () => ({
  useSession: () => ({
    session: { user: { user_metadata: { name: 'Andrew Segars' } } },
    status: 'authenticated',
  }),
}))

vi.mock('../../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: () => ({
    data: { clients: mockClients },
    isLoading: false,
    isError: false,
  }),
}))

vi.mock('../../../hooks/useInviteClient', () => ({
  useInviteClient: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  extractInviteErrorMessage: (_err: unknown) => 'invite error',
}))

// Shared spy so the resend confirm-flow tests (ORPHEUS-93) can assert
// whether/when the mutation actually fired. vi.hoisted lifts it above
// the hoisted vi.mock factory.
const resendMutateAsync = vi.hoisted(() => vi.fn())

vi.mock('../../../hooks/useResendInvitation', () => ({
  useResendInvitation: () => ({
    mutateAsync: resendMutateAsync,
    isPending: false,
  }),
  extractResendErrorMessage: (_err: unknown) => 'resend error',
}))

vi.mock('../../../hooks/useSelfReport', () => ({
  useSelfReport: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  extractSelfReportErrorMessage: (_err: unknown) => 'self-report error',
}))

// --------------------------------------------------------------------------- //
// Fixture data
//
// One row that exercises the ORPHEUS-46 uncloak: a non-self client with
// a complete latest job. If the `client.is_self &&` guard ever returns
// to the View report Link, this assertion is what catches it.
// --------------------------------------------------------------------------- //

const mockClients: AdvisorClient[] = [
  {
    id: 'client-uuid-1',
    display_name: 'Jane Doe',
    email: 'jane@example.com',
    invitation_status: 'accepted',
    is_self: false,
    latest_job: { id: 'job-uuid-1', status: 'complete' },
  },
  // Pending row — exercises the Resend button + the ORPHEUS-93 inline
  // confirmation (Resend rotates the token, killing the earlier link).
  {
    id: 'client-uuid-2',
    display_name: 'Monika Gorzelanska',
    email: 'monika@example.com',
    invitation_status: 'pending',
    is_self: false,
    latest_job: null,
  },
]

// --------------------------------------------------------------------------- //
// Render helper
// --------------------------------------------------------------------------- //

function renderClientsPage() {
  return render(
    <MemoryRouter>
      <ClientsPage />
    </MemoryRouter>,
  )
}

// --------------------------------------------------------------------------- //
// Assertions
// --------------------------------------------------------------------------- //

describe('ClientsPage', () => {
  it('renders the page header', () => {
    renderClientsPage()
    expect(
      screen.getByRole('heading', { level: 1, name: /manage clients/i }),
    ).toBeInTheDocument()
  })

  it('renders the invite form with name + email fields and a submit button', () => {
    renderClientsPage()
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(
      // Anchored: /send invitation/i would also match the pending row's
      // "Resend invitation" button.
      screen.getByRole('button', { name: /^send invitation$/i }),
    ).toBeInTheDocument()
  })

  it('surfaces View report on a non-self client row whose latest job is complete (ORPHEUS-46 regression)', () => {
    renderClientsPage()
    const link = screen.getByRole('link', { name: /view report/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/jobs/job-uuid-1')
  })
})

describe('ClientsPage resend confirmation (ORPHEUS-93)', () => {
  beforeEach(() => {
    resendMutateAsync.mockReset()
    resendMutateAsync.mockResolvedValue({ client_id: 'client-uuid-2' })
  })

  it('arms an inline confirmation on Resend click without firing the mutation', async () => {
    const user = userEvent.setup()
    renderClientsPage()

    await user.click(screen.getByRole('button', { name: /resend invitation/i }))

    expect(resendMutateAsync).not.toHaveBeenCalled()
    expect(
      screen.getByText(/replaces the earlier invitation/i),
    ).toBeInTheDocument()
    // The original Resend button hides while confirming.
    expect(
      screen.queryByRole('button', { name: /resend invitation/i }),
    ).not.toBeInTheDocument()
  })

  it('fires the mutation only on Confirm resend', async () => {
    const user = userEvent.setup()
    renderClientsPage()

    await user.click(screen.getByRole('button', { name: /resend invitation/i }))
    await user.click(screen.getByRole('button', { name: /confirm resend/i }))

    expect(resendMutateAsync).toHaveBeenCalledTimes(1)
    expect(resendMutateAsync).toHaveBeenCalledWith('client-uuid-2')
  })

  it('Cancel dismisses the confirmation and restores the Resend button', async () => {
    const user = userEvent.setup()
    renderClientsPage()

    await user.click(screen.getByRole('button', { name: /resend invitation/i }))
    await user.click(screen.getByRole('button', { name: /^cancel$/i }))

    expect(resendMutateAsync).not.toHaveBeenCalled()
    expect(
      screen.queryByText(/replaces the earlier invitation/i),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /resend invitation/i }),
    ).toBeInTheDocument()
  })
})
