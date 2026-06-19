import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

// ── Landing page: token rides the OAuth redirectTo URL (ORPHEUS-92) ─────

describe('InviteLandingPage', () => {
  it('passes the token through the OAuth redirect URL', () => {
    render(
      <MemoryRouter initialEntries={['/invite/abc123']}>
        <Routes>
          <Route path="/invite/:token" element={<InviteLandingPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(signInWithLinkedInMock).toHaveBeenCalledTimes(1)
    const redirectTo = signInWithLinkedInMock.mock.calls[0][0] as string
    expect(redirectTo).toContain('/invite/callback')
    expect(redirectTo).toContain('token=abc123')
  })

  it('still stashes the token in sessionStorage as a fallback', () => {
    render(
      <MemoryRouter initialEntries={['/invite/abc123']}>
        <Routes>
          <Route path="/invite/:token" element={<InviteLandingPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(sessionStorage.getItem(PENDING_INVITATION_TOKEN_KEY)).toBe('abc123')
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
