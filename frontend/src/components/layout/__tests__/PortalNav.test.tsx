/**
 * PortalNav account-dropdown tests — ORPHEUS-71.
 *
 * Supersedes the ORPHEUS-52 identity-cluster tests. The nav now always
 * shows the signed-in user's OWN name under a "Logged in as" eyebrow
 * (the report-subject name moved to the Signal Score hero), and the
 * cluster is the trigger for an account dropdown. Per the ORPHEUS-47
 * convention, vi.mock the data hooks rather than running an MSW server.
 *
 * Coverage scope:
 *   - Eyebrow + own name render from the session metadata.
 *   - Menu is closed by default; clicking the trigger opens it.
 *   - Role-conditional items: client-only (View My Reports, no View
 *     Clients/Admin), advisor-only (View Clients, no View My Reports),
 *     dual-role (both), admin email (Admin entry).
 *   - Escape closes the menu.
 *   - Clicking Log Out invokes signOut.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { PortalNav } from '../PortalNav'
import { signOut } from '../../../lib/auth'
import { useSessionRoles } from '../../../hooks/useSessionRoles'
import { isAdminEmail } from '../../../hooks/useAdmin'

// --------------------------------------------------------------------------- //
// Module mocks
//
// Mocking '../../../lib/auth' short-circuits the import of
// '../../../lib/supabase', which would otherwise demand VITE_SUPABASE_*
// at module-load time. The useSession mock supplies the LinkedIn name
// used by the "Logged in as" cluster. isAdminEmail is mocked so the
// admin-entry branch is controllable without touching VITE_ADMIN_EMAILS.
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

vi.mock('../../../hooks/useAdmin', () => ({
  isAdminEmail: vi.fn(() => false),
}))

function renderNav() {
  return render(
    <MemoryRouter>
      <PortalNav />
    </MemoryRouter>,
  )
}

function rolesClientOnly() {
  return { data: { user_id: 'u-client', email: 'c@x', advisor_id: null, client_id: 'client-self' } }
}
function rolesAdvisorOnly() {
  return { data: { user_id: 'u-adv', email: 'a@x', advisor_id: 'advisor-1', client_id: null } }
}
function rolesDualRole() {
  return {
    data: { user_id: 'u-andrew', email: 'andrew@example.com', advisor_id: 'advisor-1', client_id: 'client-andrew-self' },
  }
}

// --------------------------------------------------------------------------- //
// Tests
// --------------------------------------------------------------------------- //

describe('PortalNav account dropdown (ORPHEUS-71)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(isAdminEmail).mockReturnValue(false)
  })

  it('renders the "Logged in as" eyebrow and the signed-in user’s own name', () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesClientOnly() as ReturnType<typeof useSessionRoles>)
    renderNav()

    expect(screen.getByText('Logged in as')).toBeInTheDocument()
    expect(screen.getByText('Andrew Segars')).toBeInTheDocument()
  })

  it('keeps the menu closed until the trigger is clicked', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesClientOnly() as ReturnType<typeof useSessionRoles>)
    const user = userEvent.setup()
    renderNav()

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /account menu/i }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
  })

  it('shows client items (View My Reports) and hides advisor/admin items for a client-only user', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesClientOnly() as ReturnType<typeof useSessionRoles>)
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /account menu/i }))

    expect(screen.getByRole('menuitem', { name: /view my reports/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /manage my account/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /log out/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /view clients/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /^admin$/i })).not.toBeInTheDocument()
  })

  it('shows View Clients and hides View My Reports for an advisor-only user', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesAdvisorOnly() as ReturnType<typeof useSessionRoles>)
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /account menu/i }))

    expect(screen.getByRole('menuitem', { name: /view clients/i })).toHaveAttribute(
      'href',
      '/advisor/clients',
    )
    expect(screen.queryByRole('menuitem', { name: /view my reports/i })).not.toBeInTheDocument()
  })

  it('shows both View My Reports and View Clients for a dual-role user', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesDualRole() as ReturnType<typeof useSessionRoles>)
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /account menu/i }))

    expect(screen.getByRole('menuitem', { name: /view my reports/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /view clients/i })).toBeInTheDocument()
  })

  it('shows an Admin entry to /admin for an admin-allowlisted email', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesAdvisorOnly() as ReturnType<typeof useSessionRoles>)
    vi.mocked(isAdminEmail).mockReturnValue(true)
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /account menu/i }))

    expect(screen.getByRole('menuitem', { name: /^admin$/i })).toHaveAttribute('href', '/admin')
  })

  it('closes the menu on Escape', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesClientOnly() as ReturnType<typeof useSessionRoles>)
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /account menu/i }))
    expect(screen.getByRole('menu')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('invokes signOut when Log Out is clicked', async () => {
    vi.mocked(useSessionRoles).mockReturnValue(rolesClientOnly() as ReturnType<typeof useSessionRoles>)
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /account menu/i }))
    await user.click(screen.getByRole('menuitem', { name: /log out/i }))

    expect(signOut).toHaveBeenCalledTimes(1)
  })
})
