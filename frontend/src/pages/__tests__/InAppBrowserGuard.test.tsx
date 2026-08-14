/**
 * In-app browser guard across all three sign-in doors — ORPHEUS-130.
 *
 * The regression being pinned: a tester opens a link from a LinkedIn DM,
 * we hand off to LinkedIn OAuth, the LinkedIn app intercepts its own
 * domain and drops them on their feed. Four attempts, zero /callback
 * hits, no account (live, 2026-08-13).
 *
 * The sharpest case was /invite/:token, whose entire job used to be an
 * unattended redirect — the assertion that signInWithLinkedIn is NOT
 * called there is the one that would have prevented the reported
 * experience. ORPHEUS-132 has since put a consent gate in front of that
 * hop, so the page no longer redirects on its own; the guard still has
 * to suppress the whole card, and the escape hatch still has to hand
 * back a working invitation.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearOverride } from '../../lib/inAppBrowser'

// ── Module mocks (ORPHEUS-47 convention) ───────────────────────────────

const signInWithLinkedInMock = vi.fn((_redirectTo?: string) => Promise.resolve())
const useSessionMock = vi.fn(() => ({
  session: null as unknown,
  status: 'unauthenticated' as 'loading' | 'authenticated' | 'unauthenticated',
}))

vi.mock('../../lib/auth', () => ({
  signInWithLinkedIn: (redirectTo?: string) => signInWithLinkedInMock(redirectTo),
  signOut: () => Promise.resolve(),
  useSession: () => useSessionMock(),
}))

const completeMutationState = {
  mutate: vi.fn(),
  isPending: false,
  isSuccess: false,
  isError: false,
  data: undefined as unknown,
  error: undefined as unknown,
}

vi.mock('../../hooks/useCompleteSignup', async () => {
  const actual = await vi.importActual<
    typeof import('../../hooks/useCompleteSignup')
  >('../../hooks/useCompleteSignup')
  return { ...actual, useCompleteSignup: () => completeMutationState }
})

vi.mock('../../lib/apiClient', async () => {
  const actual = await vi.importActual<typeof import('../../lib/apiClient')>(
    '../../lib/apiClient',
  )
  return { ...actual, apiPostJson: () => Promise.resolve({}) }
})

// Imported AFTER the mocks so the components pick up the mocked modules.
import { InviteLandingPage } from '../InviteLandingPage'
import { LoginPage } from '../LoginPage'
import { SignupPage } from '../SignupPage'

// ── User agents ────────────────────────────────────────────────────────

const LINKEDIN_IOS =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [LinkedInApp]'
const SAFARI_IOS =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'

const realUserAgent = Object.getOwnPropertyDescriptor(
  window.navigator,
  'userAgent',
)

function setUserAgent(ua: string) {
  Object.defineProperty(window.navigator, 'userAgent', {
    value: ua,
    configurable: true,
  })
}

function renderInvite() {
  return render(
    <MemoryRouter initialEntries={['/invite/tok-abc123']}>
      <Routes>
        <Route path="/invite/:token" element={<InviteLandingPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const guardHeading = () =>
  screen.queryByRole('heading', { name: /open this page in your browser/i })

/** Clear the ORPHEUS-132 consent gate and press the button. */
function acceptAndContinue() {
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(
    screen.getByRole('button', { name: /continue with linkedin/i }),
  )
}

beforeEach(() => {
  signInWithLinkedInMock.mockClear()
  clearOverride()
  sessionStorage.clear()
})

afterEach(() => {
  vi.clearAllMocks()
  clearOverride()
  if (realUserAgent) {
    Object.defineProperty(window.navigator, 'userAgent', realUserAgent)
  }
})

// ── Blocked ────────────────────────────────────────────────────────────

describe('inside a LinkedIn in-app browser', () => {
  beforeEach(() => setUserAgent(LINKEDIN_IOS))

  it('replaces the sign-in action on /login', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    expect(guardHeading()).toBeInTheDocument()
    // Names the host app specifically — a generic "your browser" would
    // leave the user guessing which window they're actually in.
    expect(screen.getByText(/inside LinkedIn/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /continue with linkedin/i }),
    ).not.toBeInTheDocument()
  })

  it('replaces the sign-up action on /signup', () => {
    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    )

    expect(guardHeading()).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /continue with linkedin/i }),
    ).not.toBeInTheDocument()
  })

  it('replaces the whole invitation card on /invite/:token', () => {
    renderInvite()

    // The whole point: no handoff into a hop that cannot complete.
    // Without this the user is dropped on their feed with no error and
    // nothing to go back to. Post-ORPHEUS-132 the guard must also take
    // the consent gate off the screen — offering someone a ToS checkbox
    // in front of a sign-in that cannot succeed is worse than useless.
    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
    expect(guardHeading()).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('names the iOS gesture rather than a generic instruction', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/Open in Safari/i)).toBeInTheDocument()
  })
})

// ── Escape hatch ───────────────────────────────────────────────────────

describe('the escape hatch', () => {
  beforeEach(() => setUserAgent(LINKEDIN_IOS))

  it('restores the normal sign-in action on /login', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /continue here anyway/i }))

    expect(guardHeading()).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue with linkedin/i }),
    ).toBeInTheDocument()
  })

  it('restores the invitation consent gate on /invite/:token, token intact', async () => {
    renderInvite()

    fireEvent.click(screen.getByRole('button', { name: /continue here anyway/i }))

    // Taking the hatch returns the user to the normal flow — which is
    // now the consent gate, not an immediate redirect. The token has to
    // survive both hops.
    expect(guardHeading()).not.toBeInTheDocument()
    acceptAndContinue()

    await waitFor(() => {
      expect(signInWithLinkedInMock).toHaveBeenCalledTimes(1)
    })
    expect(signInWithLinkedInMock.mock.calls[0][0]).toContain('token=tok-abc123')
  })
})

// ── Copy link ──────────────────────────────────────────────────────────

describe('copy link', () => {
  beforeEach(() => setUserAgent(LINKEDIN_IOS))

  it('copies the current URL so an invitation token survives the hop', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    Object.defineProperty(window.navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /copy link/i }))

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(window.location.href)
    })
    expect(
      await screen.findByRole('button', { name: /link copied/i }),
    ).toBeInTheDocument()
  })
})

// ── Not blocked ────────────────────────────────────────────────────────

describe('inside a real browser', () => {
  beforeEach(() => setUserAgent(SAFARI_IOS))

  it('leaves /login alone', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    expect(guardHeading()).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue with linkedin/i }),
    ).toBeInTheDocument()
  })

  it('leaves /signup alone', () => {
    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    )

    expect(guardHeading()).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue with linkedin/i }),
    ).toBeInTheDocument()
  })

  it('shows /invite/:token its consent gate rather than the guard', async () => {
    renderInvite()

    expect(guardHeading()).not.toBeInTheDocument()
    // Not blocked, but no longer automatic either (ORPHEUS-132).
    expect(signInWithLinkedInMock).not.toHaveBeenCalled()

    acceptAndContinue()
    await waitFor(() => {
      expect(signInWithLinkedInMock).toHaveBeenCalledTimes(1)
    })
  })
})
