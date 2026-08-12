import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  PENDING_SIGNUP_CODE_KEY,
  readSignupCodeFromUrl,
} from '../../lib/signup'

// ── Module mocks (ORPHEUS-47 convention: mock the data/lib hooks) ──────

const signInWithLinkedInMock = vi.fn((_redirectTo?: string) => Promise.resolve())
const signOutMock = vi.fn(() => Promise.resolve())
const useSessionMock = vi.fn(() => ({
  session: null as unknown,
  status: 'unauthenticated' as 'loading' | 'authenticated' | 'unauthenticated',
}))

vi.mock('../../lib/auth', () => ({
  signInWithLinkedIn: (redirectTo?: string) => signInWithLinkedInMock(redirectTo),
  signOut: () => signOutMock(),
  useSession: () => useSessionMock(),
}))

const completeMutateMock = vi.fn()
const completeMutationState = {
  mutate: completeMutateMock,
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
  return {
    ...actual,
    useCompleteSignup: () => completeMutationState,
  }
})

const apiPostJsonMock = vi.fn(() => Promise.resolve({}))
vi.mock('../../lib/apiClient', async () => {
  const actual = await vi.importActual<typeof import('../../lib/apiClient')>(
    '../../lib/apiClient',
  )
  return {
    ...actual,
    apiPostJson: (...args: unknown[]) => apiPostJsonMock(...(args as [])),
  }
})

// Imported AFTER the mocks so the components pick up the mocked modules.
import { SignupCallbackPage } from '../SignupCallbackPage'
import { SignupPage } from '../SignupPage'

beforeEach(() => {
  useSessionMock.mockReturnValue({ session: null, status: 'unauthenticated' })
  completeMutationState.isPending = false
  completeMutationState.isSuccess = false
  completeMutationState.isError = false
  completeMutationState.data = undefined
  completeMutationState.error = undefined
  sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})

afterEach(() => {
  vi.clearAllMocks()
})

// ── Helper ─────────────────────────────────────────────────────────────

describe('readSignupCodeFromUrl', () => {
  it('returns the code from the query string', () => {
    expect(readSignupCodeFromUrl('?signup_code=beta123')).toBe('beta123')
  })

  it('returns null when the param is absent', () => {
    expect(readSignupCodeFromUrl('?foo=bar')).toBeNull()
  })

  it('returns null when the param is empty', () => {
    expect(readSignupCodeFromUrl('?signup_code=')).toBeNull()
  })
})

// ── Sign-up page: code + consent ride the OAuth redirectTo URL ──────────

describe('SignupPage (unauthenticated)', () => {
  function renderPage() {
    return render(
      <MemoryRouter initialEntries={['/signup']}>
        <SignupPage />
      </MemoryRouter>,
    )
  }

  function fillAndSubmit(code = 'beta123') {
    fireEvent.change(screen.getByLabelText(/beta access code/i), {
      target: { value: code },
    })
    fireEvent.click(screen.getByLabelText(/i agree to the/i))
    fireEvent.click(
      screen.getByRole('button', { name: /continue with linkedin/i }),
    )
  }

  it('passes the code and consent versions through the OAuth redirect URL', () => {
    renderPage()
    fillAndSubmit('beta123')

    expect(signInWithLinkedInMock).toHaveBeenCalledTimes(1)
    const redirectTo = signInWithLinkedInMock.mock.calls[0][0] as string
    expect(redirectTo).toContain('/signup/callback')
    expect(redirectTo).toContain('signup_code=beta123')
    // ORPHEUS-126: the acceptance rides the same URL.
    expect(redirectTo).toContain('terms_v=')
    expect(redirectTo).toContain('privacy_v=')
  })

  it('still stashes the code in sessionStorage as a fallback', () => {
    renderPage()
    fillAndSubmit('beta123')

    expect(sessionStorage.getItem(PENDING_SIGNUP_CODE_KEY)).toBe('beta123')
  })

  it('prefills the code from a shareable /signup?code= link (ORPHEUS-129)', () => {
    window.history.replaceState({}, '', '/signup?code=ACME2027')
    renderPage()

    expect(screen.getByLabelText(/beta access code/i)).toHaveValue('ACME2027')

    // Consent + submit still required — the prefill only saves typing.
    fireEvent.click(screen.getByLabelText(/i agree to the/i))
    fireEvent.click(
      screen.getByRole('button', { name: /continue with linkedin/i }),
    )
    const redirectTo = signInWithLinkedInMock.mock.calls[0][0] as string
    expect(redirectTo).toContain('signup_code=ACME2027')
  })

  it('does not start OAuth without a code', () => {
    renderPage()
    fireEvent.click(screen.getByLabelText(/i agree to the/i))
    fireEvent.click(
      screen.getByRole('button', { name: /continue with linkedin/i }),
    )

    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
    expect(
      screen.getByText(/please enter your beta access code/i),
    ).toBeInTheDocument()
  })

  it('does not start OAuth without the consent box ticked', () => {
    renderPage()
    fireEvent.change(screen.getByLabelText(/beta access code/i), {
      target: { value: 'beta123' },
    })
    fireEvent.click(
      screen.getByRole('button', { name: /continue with linkedin/i }),
    )

    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
    expect(
      screen.getByText(/please agree to the terms of service/i),
    ).toBeInTheDocument()
  })
})

// ── Sign-up page: already-authenticated branch (from /not-invited) ──────

describe('SignupPage (authenticated)', () => {
  it('completes in place without an OAuth re-run', () => {
    useSessionMock.mockReturnValue({
      session: {
        user: { user_metadata: { name: 'Pat Doe' } },
      } as unknown,
      status: 'authenticated',
    })

    render(
      <MemoryRouter initialEntries={['/signup']}>
        <SignupPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/beta access code/i), {
      target: { value: 'beta123' },
    })
    fireEvent.click(screen.getByLabelText(/i agree to the/i))
    fireEvent.click(screen.getByRole('button', { name: /complete sign-up/i }))

    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
    expect(completeMutateMock).toHaveBeenCalledTimes(1)
    expect(completeMutateMock.mock.calls[0][0]).toEqual({
      beta_code: 'beta123',
      display_name: 'Pat Doe',
    })
  })
})

// ── Callback page: code resolves from the URL even when sessionStorage
//    was dropped by a cross-context redirect (the ORPHEUS-92 pattern) ────

describe('SignupCallbackPage', () => {
  it('completes using the URL code when sessionStorage is empty', () => {
    useSessionMock.mockReturnValue({
      session: { user: { user_metadata: { name: 'Pat Doe' } } } as unknown,
      status: 'authenticated',
    })
    window.history.replaceState({}, '', '/signup/callback?signup_code=urlcode')
    expect(sessionStorage.getItem(PENDING_SIGNUP_CODE_KEY)).toBeNull()

    render(
      <MemoryRouter>
        <SignupCallbackPage />
      </MemoryRouter>,
    )

    expect(completeMutateMock).toHaveBeenCalledWith({
      beta_code: 'urlcode',
      display_name: 'Pat Doe',
    })
  })

  it('strips the code from the address bar once captured', () => {
    useSessionMock.mockReturnValue({
      session: { user: {} } as unknown,
      status: 'authenticated',
    })
    window.history.replaceState({}, '', '/signup/callback?signup_code=urlcode')

    render(
      <MemoryRouter>
        <SignupCallbackPage />
      </MemoryRouter>,
    )

    expect(window.location.search).not.toContain('signup_code=')
    // Capture still succeeded despite the URL being cleaned.
    expect(completeMutateMock).toHaveBeenCalledWith({
      beta_code: 'urlcode',
      display_name: null,
    })
  })

  it('re-prompts for the code instead of dead-ending when none arrived', () => {
    useSessionMock.mockReturnValue({
      session: { user: {} } as unknown,
      status: 'authenticated',
    })
    // No code in URL, nothing in sessionStorage.

    render(
      <MemoryRouter>
        <SignupCallbackPage />
      </MemoryRouter>,
    )

    expect(completeMutateMock).not.toHaveBeenCalled()
    expect(
      screen.getByRole('heading', { name: /enter your access code/i }),
    ).toBeInTheDocument()

    // Entering a code and submitting fires the mutation — no OAuth re-run.
    fireEvent.change(screen.getByLabelText(/beta access code/i), {
      target: { value: 'typed-code' },
    })
    fireEvent.click(screen.getByRole('button', { name: /complete sign-up/i }))
    expect(completeMutateMock).toHaveBeenCalledWith({
      beta_code: 'typed-code',
      display_name: null,
    })
    expect(signInWithLinkedInMock).not.toHaveBeenCalled()
  })

  it('shows the OAuth-didn\'t-complete card when unauthenticated', () => {
    useSessionMock.mockReturnValue({
      session: null,
      status: 'unauthenticated',
    })
    window.history.replaceState({}, '', '/signup/callback?signup_code=urlcode')

    render(
      <MemoryRouter>
        <SignupCallbackPage />
      </MemoryRouter>,
    )

    expect(completeMutateMock).not.toHaveBeenCalled()
    expect(
      screen.getByRole('heading', { name: /sign-in didn't complete/i }),
    ).toBeInTheDocument()
  })
})
