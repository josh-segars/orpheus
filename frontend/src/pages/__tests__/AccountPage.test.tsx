/**
 * AccountPage Danger Zone tests — ORPHEUS-124.
 *
 * Per the ORPHEUS-47 convention, the data hooks are vi.mocked rather
 * than running an MSW server. Coverage:
 *
 *   - typed confirmation gates the destructive button: disabled until
 *     the exact phrase is typed, then fires the mutation
 *   - blocked advisor (non-self roster rows) sees the reason inline and
 *     no delete control
 *   - dual-role advisor whose only roster row is is_self is NOT blocked
 *   - post-success: signOut runs and the router lands on /login with
 *     accountDeleted state
 *   - mutation failure renders the backend's detail and stays on page
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'

import { AccountPage } from '../AccountPage'
import { ApiError } from '../../lib/apiClient'

// Mutable hook returns — reassigned per test, reset in beforeEach.
let mockSessionRoles: {
  data: { user_id: string; advisor_id: string | null; client_id: string | null } | undefined
} = { data: undefined }
let mockAdvisorClients: {
  data: { clients: { id: string; display_name: string; is_self: boolean }[] } | undefined
} = { data: undefined }

const mutateAsync = vi.fn()
let mockIsPending = false

const signOutMock = vi.fn()

vi.mock('../../hooks/useSessionRoles', () => ({
  useSessionRoles: () => mockSessionRoles,
}))
vi.mock('../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: () => mockAdvisorClients,
}))
vi.mock('../../hooks/useDeleteAccount', () => ({
  useDeleteAccount: () => ({
    mutateAsync,
    get isPending() {
      return mockIsPending
    },
  }),
}))
vi.mock('../../lib/auth', () => ({
  signOut: (...args: unknown[]) => signOutMock(...args),
}))

function LoginProbe() {
  const location = useLocation()
  return (
    <div data-testid="login-probe">
      {location.state?.accountDeleted ? 'deleted-state' : 'no-state'}
    </div>
  )
}

function renderAccountPage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/account']}>
        <Routes>
          <Route path="/account" element={<AccountPage />} />
          <Route path="/login" element={<LoginProbe />} />
          <Route path="/" element={<div>home</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockSessionRoles = {
    data: { user_id: 'user-1', advisor_id: null, client_id: 'client-1' },
  }
  mockAdvisorClients = { data: undefined }
  mockIsPending = false
  mutateAsync.mockReset()
  signOutMock.mockReset()
  signOutMock.mockResolvedValue(undefined)
})

describe('AccountPage Danger Zone (ORPHEUS-124)', () => {
  it('gates the destructive button behind the typed confirmation', async () => {
    const user = userEvent.setup()
    mutateAsync.mockResolvedValue({ deleted: true })
    renderAccountPage()

    // Arm the confirm state.
    await user.click(screen.getByRole('button', { name: /delete my account/i }))

    const confirmButton = screen.getByRole('button', {
      name: /permanently delete/i,
    })
    expect(confirmButton).toBeDisabled()

    const input = screen.getByLabelText(/type DELETE to confirm/i)
    await user.type(input, 'delete')
    expect(confirmButton).toBeDisabled() // case matters

    await user.clear(input)
    await user.type(input, 'DELETE')
    expect(confirmButton).toBeEnabled()

    await user.click(confirmButton)
    expect(mutateAsync).toHaveBeenCalledTimes(1)
  })

  it('shows the blocked explanation instead of the control for an advisor with clients', () => {
    mockSessionRoles = {
      data: { user_id: 'user-1', advisor_id: 'adv-1', client_id: 'client-1' },
    }
    mockAdvisorClients = {
      data: {
        clients: [
          { id: 'client-1', display_name: 'Me', is_self: true },
          { id: 'client-2', display_name: 'Someone Else', is_self: false },
        ],
      },
    }
    renderAccountPage()

    expect(
      screen.getByText(/roster still has 1 client\b/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /delete my account/i }),
    ).not.toBeInTheDocument()
  })

  it('does not block a dual-role advisor whose only roster row is is_self', () => {
    mockSessionRoles = {
      data: { user_id: 'user-1', advisor_id: 'adv-1', client_id: 'client-1' },
    }
    mockAdvisorClients = {
      data: {
        clients: [{ id: 'client-1', display_name: 'Me', is_self: true }],
      },
    }
    renderAccountPage()

    expect(
      screen.getByRole('button', { name: /delete my account/i }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/roster still has/i)).not.toBeInTheDocument()
  })

  it('signs out and lands on /login with accountDeleted state on success', async () => {
    const user = userEvent.setup()
    mutateAsync.mockResolvedValue({ deleted: true })
    renderAccountPage()

    await user.click(screen.getByRole('button', { name: /delete my account/i }))
    await user.type(screen.getByLabelText(/type DELETE to confirm/i), 'DELETE')
    await user.click(screen.getByRole('button', { name: /permanently delete/i }))

    await waitFor(() => {
      expect(screen.getByTestId('login-probe')).toHaveTextContent(
        'deleted-state',
      )
    })
    expect(signOutMock).toHaveBeenCalledTimes(1)
  })

  it('still navigates when signOut rejects (session already dead server-side)', async () => {
    const user = userEvent.setup()
    mutateAsync.mockResolvedValue({ deleted: true })
    signOutMock.mockRejectedValue(new Error('session gone'))
    renderAccountPage()

    await user.click(screen.getByRole('button', { name: /delete my account/i }))
    await user.type(screen.getByLabelText(/type DELETE to confirm/i), 'DELETE')
    await user.click(screen.getByRole('button', { name: /permanently delete/i }))

    await waitFor(() => {
      expect(screen.getByTestId('login-probe')).toHaveTextContent(
        'deleted-state',
      )
    })
  })

  it('renders the backend detail and stays on the page when the delete fails', async () => {
    const user = userEvent.setup()
    mutateAsync.mockRejectedValue(
      new ApiError('DELETE /account failed: 409', 409, {
        detail: 'Your advisor roster still has 2 clients.',
      }),
    )
    renderAccountPage()

    await user.click(screen.getByRole('button', { name: /delete my account/i }))
    await user.type(screen.getByLabelText(/type DELETE to confirm/i), 'DELETE')
    await user.click(screen.getByRole('button', { name: /permanently delete/i }))

    expect(
      await screen.findByText(/roster still has 2 clients/i),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('login-probe')).not.toBeInTheDocument()
    expect(signOutMock).not.toHaveBeenCalled()
  })
})
