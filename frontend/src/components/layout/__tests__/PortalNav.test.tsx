/**
 * PortalNav smoke test — ORPHEUS-52.
 *
 * Covers the three name-source branches of the new "Prepared for /
 * [Name]" identity cluster, plus a logout-click regression. Per the
 * ORPHEUS-47 convention, vi.mock the data hooks rather than running an
 * MSW server.
 *
 * Coverage scope:
 *   - Pure client viewing their own report renders the LinkedIn `name`
 *     from the session.
 *   - Advisor viewing a client's job renders the matched client row's
 *     `display_name` (from the GET /clients roster).
 *   - Dual-role advisor on their own self-report renders the advisor's
 *     own LinkedIn `name` — the matched roster row carries `is_self:
 *     true`, which short-circuits the lookup back to the session user.
 *   - Clicking the logout icon button invokes `signOut`.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { PortalNav } from '../PortalNav'
import { signOut } from '../../../lib/auth'
import { useJob } from '../../../hooks/useJob'
import { useAdvisorClients } from '../../../hooks/useAdvisorClients'
import { useSessionRoles } from '../../../hooks/useSessionRoles'
import type { AdvisorClient } from '../../../hooks/useAdvisorClients'

// --------------------------------------------------------------------------- //
// Module mocks
//
// vi.mock is hoisted, so it runs before PortalNav's transitive imports
// resolve. Mocking '../../../lib/auth' in particular short-circuits the
// import of '../../../lib/supabase', which would otherwise demand
// VITE_SUPABASE_* at module-load time.
//
// Each hook is exported as a vi.fn() so individual tests can stub a
// per-case return value via vi.mocked(hook).mockReturnValue(...). The
// useSession mock provides the LinkedIn metadata used by the
// "Prepared for" cluster's session-user-name fallback path.
// --------------------------------------------------------------------------- //

vi.mock('../../../lib/auth', () => ({
  useSession: () => ({
    session: {
      user: {
        email: 'andrew@example.com',
        user_metadata: { name: 'Andrew Segars' },
      },
    },
    status: 'authenticated',
  }),
  signOut: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../../hooks/useSessionRoles', () => ({
  useSessionRoles: vi.fn(),
}))

vi.mock('../../../hooks/useJob', () => ({
  useJob: vi.fn(),
}))

vi.mock('../../../hooks/useAdvisorClients', () => ({
  useAdvisorClients: vi.fn(),
}))

// --------------------------------------------------------------------------- //
// Render helper — drops PortalNav inside a Routes tree so useParams
// resolves `:jobId` on /jobs/* routes the way the live app does.
// --------------------------------------------------------------------------- //

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/jobs/:jobId" element={<PortalNav />} />
        <Route path="/jobs/:jobId/analysis" element={<PortalNav />} />
        <Route path="*" element={<PortalNav />} />
      </Routes>
    </MemoryRouter>,
  )
}

// Fixture constructors — keep each test's intent obvious at the call
// site rather than burying the role/job state in a shared block.

function rolesClientOnly() {
  return { data: { user_id: 'u-client', email: 'c@x', advisor_id: null, client_id: 'client-self' } }
}
function rolesAdvisorOnly() {
  return { data: { user_id: 'u-adv', email: 'a@x', advisor_id: 'advisor-1', client_id: null } }
}
function rolesDualRole() {
  return {
    data: {
      user_id: 'u-andrew',
      email: 'andrew@example.com',
      advisor_id: 'advisor-1',
      client_id: 'client-andrew-self',
    },
  }
}

function jobWithClient(clientId: string) {
  return {
    data: { id: 'job-1', state: 'complete', client_id: clientId },
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useJob>
}

function clientsRoster(rows: AdvisorClient[]) {
  return {
    data: { clients: rows },
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useAdvisorClients>
}

// --------------------------------------------------------------------------- //
// Tests
// --------------------------------------------------------------------------- //

describe('PortalNav identity cluster (ORPHEUS-52)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the signed-in client’s own LinkedIn name when they view their own report', () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesClientOnly() as ReturnType<typeof useSessionRoles>)
    vi.mocked(useJob).mockReturnValue(jobWithClient('client-self'))
    // Pure clients never trigger the advisor roster fetch; the hook is
    // gated on isAdvisor internally. Return an empty/disabled shape.
    vi.mocked(useAdvisorClients).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAdvisorClients>)

    renderAt('/jobs/job-1')

    expect(screen.getByText('Prepared for')).toBeInTheDocument()
    expect(screen.getByText('Andrew Segars')).toBeInTheDocument()
  })

  it("renders the client's display_name when an advisor views that client's job", () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesAdvisorOnly() as ReturnType<typeof useSessionRoles>)
    vi.mocked(useJob).mockReturnValue(jobWithClient('client-jane'))
    vi.mocked(useAdvisorClients).mockReturnValue(
      clientsRoster([
        {
          id: 'client-jane',
          display_name: 'Jane Doe',
          email: 'jane@example.com',
          invitation_status: 'accepted',
          is_self: false,
          latest_job: { id: 'job-1', status: 'complete' },
        },
      ]),
    )

    renderAt('/jobs/job-1')

    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    // The session user's own name must NOT leak into the cluster on
    // this surface — the report subject is the client, not the
    // signed-in advisor.
    expect(screen.queryByText('Andrew Segars')).not.toBeInTheDocument()
  })

  it("renders the advisor's own name when a dual-role advisor views their own self-report", () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesDualRole() as ReturnType<typeof useSessionRoles>)
    vi.mocked(useJob).mockReturnValue(jobWithClient('client-andrew-self'))
    // The advisor's roster includes their own self-clients row with
    // `is_self: true`; that's what tells PortalNav to fall back to the
    // session display name instead of the roster's display_name (which
    // could be a free-text advisor label rather than the LinkedIn name).
    vi.mocked(useAdvisorClients).mockReturnValue(
      clientsRoster([
        {
          id: 'client-andrew-self',
          display_name: 'Andrew (self)',
          email: 'andrew@example.com',
          invitation_status: 'accepted',
          is_self: true,
          latest_job: { id: 'job-1', status: 'complete' },
        },
      ]),
    )

    renderAt('/jobs/job-1')

    expect(screen.getByText('Andrew Segars')).toBeInTheDocument()
    // The free-text advisor label for the self-row must NOT win over
    // the LinkedIn-sourced display name.
    expect(screen.queryByText('Andrew (self)')).not.toBeInTheDocument()
  })

  // ORPHEUS-56: advisor-only users navigating off /advisor/clients (e.g.
  // to /admin) need a clickable Link, not a decorative span — the
  // pre-fix markup left them stuck typing the URL by hand.
  it('renders a clickable Manage clients link for advisor-only users off /advisor/clients', () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesAdvisorOnly() as ReturnType<typeof useSessionRoles>)
    vi.mocked(useJob).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useJob>)
    vi.mocked(useAdvisorClients).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAdvisorClients>)

    renderAt('/admin')

    const link = screen.getByRole('link', { name: /manage clients/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/advisor/clients')
  })

  it('hides the Manage clients pill for advisor-only users on /advisor/clients itself', () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesAdvisorOnly() as ReturnType<typeof useSessionRoles>)
    vi.mocked(useJob).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useJob>)
    vi.mocked(useAdvisorClients).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAdvisorClients>)

    renderAt('/advisor/clients')

    // The Manage clients pill is suppressed on its own page — the user
    // is already there, no nav target needed.
    expect(
      screen.queryByRole('link', { name: /manage clients/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/^manage clients$/i)).not.toBeInTheDocument()
  })

  it('invokes signOut when the logout icon button is clicked', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesClientOnly() as ReturnType<typeof useSessionRoles>)
    vi.mocked(useJob).mockReturnValue(jobWithClient('client-self'))
    vi.mocked(useAdvisorClients).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAdvisorClients>)

    const user = userEvent.setup()
    renderAt('/jobs/job-1')

    await user.click(screen.getByRole('button', { name: /sign out/i }))
    expect(signOut).toHaveBeenCalledTimes(1)
  })
})
