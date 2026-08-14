import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  CURRENT_PRIVACY_VERSION,
  CURRENT_TERMS_VERSION,
  readPendingTermsAcceptance,
} from '../../lib/consent'
import {
  PENDING_INVITATION_TOKEN_KEY,
  readInvitationTokenFromUrl,
} from '../../lib/invitation'

// ── Module mocks (ORPHEUS-47 convention: mock the data/lib hooks) ──────

const signInWithLinkedInMock = vi.fn((_redirectTo?: string) => Promise.resolve())
const signOutMock = vi.fn(() => Promise.resolve())
const useSessionMock = vi.fn(() => ({ status: 'authenticated' as const }))

vi.mock('../../lib/auth', () => ({
  signInWithLinkedIn: (redirectTo?: string) => signInWithLinkedInMock(redirectTo),
  signOut: () => signOutMock(),
  useSession: () => useSessionMock(),
}))

const acceptMutateMock = vi.fn()
const acceptMutationState = {
  mutate: acceptMutateMock,
  isPending: false,
  isSuccess: false,
  isError: false,
  data: undefined as unknown,
  error: undefined as unknown,
}

vi.mock('../../hooks/useAcceptInvitation', () => ({
  useAcceptInvitation: () => acceptMutationState,
  extractAcceptInvitationErrorMessage: () => 'error',
}))

// Imported AFTER the mocks so the components pick up the mocked modules.
import { InviteCallbackPage } from '../InviteCallbackPage'
import { InviteLandingPage } from '../InviteLandingPage'

beforeEach(() => {
  signInWithLinkedInMock.mockClear()
  acceptMutateMock.mockClear()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})

afterEach(() => {
  vi.clearAllMocks()
})

// ── Helper ─────────────────────────────────────────────────────────────

describe('readInvitationTokenFromUrl', () => {
  it('returns the token from the query string', () => {
    expect(readInvitationTokenFromUrl('?token=abc123')).toBe('abc123')
  })

  it('returns null when the param is absent', () => {
    expect(readInvitationTokenFromUrl('?foo=bar')).toBeNull()
  })

  it('returns null when the param is empty', () => {
    expect(readInvitationTokenFromUrl('?token=')).toBeNull()
  })
})

// ── Landing page: the consent gate (ORPHEUS-132), and the token still
//    riding the OAuth redirectTo URL (ORPHEUS-92) ──────────────────────

function renderLanding(entry = '/invite/abc123') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/invite/:token" element={<InviteLandingPage />} />
        <Route path="/invite" element={<InviteLandingPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

/** Tick the ToS box and press the button — the user-initiated hop. */
async function acceptAndContinue() {
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(
    screen.getByRole('button', { name: /continue with linkedin/i }),
  )
  await waitFor(() => {
    expect(signInWithLinkedInMock).toHaveBeenCalledTimes(1)
  })
}

describe('InviteLandingPage', () => {
  // The load-bearing one. Before ORPHEUS-132 this page redirected from an
  // effect on mount, which is precisely how invited clients reached a
  // report having never been shown the ToS or the Privacy Policy.
  it('does not start the OAuth hop until the box is ticked', () => {
    renderLanding()

    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
    const button = screen.getByRole('button', {
      name: /continue with linkedin/i,
    })
    expect(button).toBeDisabled()

    // Clicking through the disabled button changes nothing.
    fireEvent.click(button)
    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
  })

  it('offers the box unticked — a pre-ticked one is not an affirmative act', () => {
    renderLanding()
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })

  it('links both documents so the act is informed', () => {
    renderLanding()
    expect(
      screen.getByRole('link', { name: /terms of service/i }),
    ).toHaveAttribute('href', '/terms')
    expect(
      screen.getByRole('link', { name: /privacy policy/i }),
    ).toHaveAttribute('href', '/privacy')
  })

  it('passes the token through the OAuth redirect URL', async () => {
    renderLanding()
    await acceptAndContinue()

    const redirectTo = signInWithLinkedInMock.mock.calls[0][0] as string
    expect(redirectTo).toContain('/invite/callback')
    expect(redirectTo).toContain('token=abc123')
  })

  it('carries both accepted versions alongside the token', async () => {
    renderLanding()
    await acceptAndContinue()

    const redirectTo = new URL(signInWithLinkedInMock.mock.calls[0][0] as string)
    // Both must survive together: the token alone leaves consent
    // unrecorded, the versions alone leave the invitation unacceptable.
    expect(redirectTo.searchParams.get('token')).toBe('abc123')
    expect(redirectTo.searchParams.get('terms_v')).toBe(CURRENT_TERMS_VERSION)
    expect(redirectTo.searchParams.get('privacy_v')).toBe(
      CURRENT_PRIVACY_VERSION,
    )
  })

  it('still stashes the token in sessionStorage as a fallback', async () => {
    renderLanding()
    await acceptAndContinue()

    expect(sessionStorage.getItem(PENDING_INVITATION_TOKEN_KEY)).toBe('abc123')
  })

  it('stashes the acceptance in sessionStorage as a fallback too', async () => {
    renderLanding()
    await acceptAndContinue()

    expect(readPendingTermsAcceptance()).toEqual({
      termsVersion: CURRENT_TERMS_VERSION,
      privacyVersion: CURRENT_PRIVACY_VERSION,
    })
  })

  it('renders the error card, and no consent gate, when the token is missing', () => {
    renderLanding('/invite')

    expect(screen.getByText(/missing its token/i)).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
  })
})

// ── Callback page: token resolves from the URL even when sessionStorage
//    was dropped by a cross-context redirect (the ORPHEUS-92 regression) ─

describe('InviteCallbackPage', () => {
  it('accepts using the URL token when sessionStorage is empty', () => {
    // Simulate the cross-context redirect: token only in the URL, nothing
    // in sessionStorage.
    window.history.replaceState({}, '', '/invite/callback?token=urltok')
    expect(sessionStorage.getItem(PENDING_INVITATION_TOKEN_KEY)).toBeNull()

    render(
      <MemoryRouter>
        <InviteCallbackPage />
      </MemoryRouter>,
    )

    expect(acceptMutateMock).toHaveBeenCalledWith({ token: 'urltok' })
  })

  it('strips the token from the address bar once captured', () => {
    window.history.replaceState({}, '', '/invite/callback?token=urltok')

    render(
      <MemoryRouter>
        <InviteCallbackPage />
      </MemoryRouter>,
    )

    expect(window.location.search).not.toContain('token=')
    // Capture still succeeded despite the URL being cleaned.
    expect(acceptMutateMock).toHaveBeenCalledWith({ token: 'urltok' })
  })
})
