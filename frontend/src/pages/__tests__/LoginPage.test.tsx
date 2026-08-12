/**
 * LoginPage ToS + Privacy consent gate — ORPHEUS-126.
 *
 * Privacy Policy s6 rested the uploads on consent that was never collected;
 * Route A (Josh, 2026-08-11) collects it for real. Two things matter here and
 * both are pinned below: the box starts unticked and gates sign-in (a
 * pre-ticked box is not a clear affirmative act under Art. 4(11)), and the
 * accepted versions ride the OAuth redirect URL so the acceptance survives
 * the round trip — the ORPHEUS-92 failure mode.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const signInWithLinkedInMock = vi.fn((_redirectTo?: string) => Promise.resolve())
const useSessionMock = vi.fn(() => ({
  status: 'unauthenticated' as const,
  session: null,
}))

vi.mock('../../lib/auth', () => ({
  signInWithLinkedIn: (redirectTo?: string) => signInWithLinkedInMock(redirectTo),
  signOut: () => Promise.resolve(),
  useSession: () => useSessionMock(),
}))

// Imported after the mock so the component picks it up.
import { LoginPage } from '../LoginPage'
import {
  CURRENT_PRIVACY_VERSION,
  CURRENT_TERMS_VERSION,
  readPendingTermsAcceptance,
} from '../../lib/consent'

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

const checkbox = () =>
  screen.getByRole('checkbox', { name: /terms of service/i })
const signInButton = () =>
  screen.getByRole('button', { name: /continue with linkedin/i })

beforeEach(() => {
  signInWithLinkedInMock.mockClear()
  sessionStorage.clear()
})

afterEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe('LoginPage consent gate (ORPHEUS-126)', () => {
  it('starts unticked — consent is never pre-given', () => {
    renderPage()
    expect(checkbox()).not.toBeChecked()
  })

  it('disables sign-in until the box is ticked', () => {
    renderPage()
    expect(signInButton()).toBeDisabled()
    fireEvent.click(checkbox())
    expect(signInButton()).toBeEnabled()
  })

  it('does not start the OAuth flow while unticked', () => {
    renderPage()
    fireEvent.click(signInButton())
    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
  })

  it('carries both accepted versions on the OAuth redirect URL', () => {
    renderPage()
    fireEvent.click(checkbox())
    fireEvent.click(signInButton())

    expect(signInWithLinkedInMock).toHaveBeenCalledTimes(1)
    const redirectTo = signInWithLinkedInMock.mock.calls[0][0] as string
    const url = new URL(redirectTo)
    expect(url.searchParams.get('terms_v')).toBe(CURRENT_TERMS_VERSION)
    expect(url.searchParams.get('privacy_v')).toBe(CURRENT_PRIVACY_VERSION)
  })

  it('also stashes the acceptance in sessionStorage as the same-context fallback', () => {
    renderPage()
    fireEvent.click(checkbox())
    fireEvent.click(signInButton())

    expect(readPendingTermsAcceptance()).toEqual({
      termsVersion: CURRENT_TERMS_VERSION,
      privacyVersion: CURRENT_PRIVACY_VERSION,
    })
  })

  it('links both documents, and opens them in a new tab so the tick survives', () => {
    renderPage()
    const terms = screen.getByRole('link', { name: /terms of service/i })
    const privacy = screen.getByRole('link', { name: /privacy policy/i })
    expect(terms).toHaveAttribute('href', '/terms')
    expect(privacy).toHaveAttribute('href', '/privacy')
    // A same-tab navigation would unmount the page and silently discard the
    // checkbox — reading the terms must not cost the user their consent.
    expect(terms).toHaveAttribute('target', '_blank')
    expect(privacy).toHaveAttribute('target', '_blank')
  })

  it('no longer claims the terms are provided separately by Andrew', () => {
    renderPage()
    expect(screen.queryByText(/provided separately/i)).toBeNull()
  })
})

// ── Self-serve sign-up panel (ORPHEUS-85/129) ───────────────────────────

describe('LoginPage sign-up panel (ORPHEUS-85/129)', () => {
  it('renders the sign-up panel with a first-class link to /signup', () => {
    renderPage()
    expect(screen.getByText(/new to orpheus\?/i)).toBeInTheDocument()
    const signup = screen.getByRole('link', {
      name: /sign up with an access code/i,
    })
    expect(signup).toHaveAttribute('href', '/signup')
  })

  it('keeps sign-in as the only button — sign-up is a link, not a competing submit', () => {
    renderPage()
    // Exactly one button on the card (Continue with LinkedIn); the
    // sign-up action is an anchor so it can't be confused with the
    // consent-gated submit.
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })
})
