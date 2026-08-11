/**
 * TermsAcceptanceRecorder — ORPHEUS-126.
 *
 * The other end of the /login checkbox. The acceptance is captured off the
 * post-OAuth URL before React renders (main.tsx → captureTermsAcceptanceFromUrl)
 * and posted here once a session exists. Art. 7(1) demandability rests on this
 * post landing, so the retry posture is pinned: a failure keeps the pending
 * value so the next authenticated render tries again, and it never blocks the
 * user, who has already done the affirmative act.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiPostJson = vi.fn()
vi.mock('../../lib/apiClient', () => ({
  apiPostJson: (path: string, body: unknown) => apiPostJson(path, body),
}))

let sessionStatus: 'loading' | 'authenticated' | 'unauthenticated' =
  'authenticated'
vi.mock('../../lib/auth', () => ({
  useSession: () => ({ status: sessionStatus, session: null }),
}))

import { TermsAcceptanceRecorder } from '../useRecordTermsAcceptance'
import {
  readPendingTermsAcceptance,
  writePendingTermsAcceptance,
} from '../../lib/consent'

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

function renderRecorder() {
  return render(<TermsAcceptanceRecorder />, { wrapper })
}

const PENDING = { termsVersion: '2026-08-11', privacyVersion: '2026-08-11' }

beforeEach(() => {
  apiPostJson.mockReset()
  sessionStorage.clear()
  sessionStatus = 'authenticated'
})

afterEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe('TermsAcceptanceRecorder (ORPHEUS-126)', () => {
  it('posts the pending acceptance once a session exists', async () => {
    apiPostJson.mockResolvedValue({
      recorded: true,
      terms_version: '2026-08-11',
      privacy_version: '2026-08-11',
    })
    writePendingTermsAcceptance(PENDING)

    renderRecorder()

    await waitFor(() =>
      expect(apiPostJson).toHaveBeenCalledWith('/consent/terms', {
        terms_version: '2026-08-11',
        privacy_version: '2026-08-11',
      }),
    )
  })

  it('clears the pending value once recorded', async () => {
    apiPostJson.mockResolvedValue({
      recorded: true,
      terms_version: '2026-08-11',
      privacy_version: '2026-08-11',
    })
    writePendingTermsAcceptance(PENDING)

    renderRecorder()

    await waitFor(() => expect(readPendingTermsAcceptance()).toBeNull())
  })

  it('treats an already-recorded response as done and stops carrying it', async () => {
    apiPostJson.mockResolvedValue({
      recorded: false,
      terms_version: '2026-08-11',
      privacy_version: '2026-08-11',
    })
    writePendingTermsAcceptance(PENDING)

    renderRecorder()

    await waitFor(() => expect(readPendingTermsAcceptance()).toBeNull())
  })

  it('KEEPS the pending value when the post fails, so a later render retries', async () => {
    apiPostJson.mockRejectedValue(new Error('502'))
    writePendingTermsAcceptance(PENDING)

    renderRecorder()

    await waitFor(() => expect(apiPostJson).toHaveBeenCalled())
    // The whole Art. 7(1) record depends on this eventually landing — a
    // failed post must not silently discard the user's acceptance.
    expect(readPendingTermsAcceptance()).toEqual(PENDING)
  })

  it('does not post when there is nothing pending', async () => {
    renderRecorder()
    await Promise.resolve()
    expect(apiPostJson).not.toHaveBeenCalled()
  })

  it('waits for authentication — never posts on an unauthenticated render', async () => {
    sessionStatus = 'unauthenticated'
    writePendingTermsAcceptance(PENDING)

    renderRecorder()
    await Promise.resolve()

    expect(apiPostJson).not.toHaveBeenCalled()
    expect(readPendingTermsAcceptance()).toEqual(PENDING)
  })

  it('posts only once even if the tree re-renders', async () => {
    apiPostJson.mockResolvedValue({
      recorded: true,
      terms_version: '2026-08-11',
      privacy_version: '2026-08-11',
    })
    writePendingTermsAcceptance(PENDING)

    const { rerender } = renderRecorder()
    await waitFor(() => expect(apiPostJson).toHaveBeenCalledTimes(1))
    rerender(<TermsAcceptanceRecorder />)
    await Promise.resolve()

    expect(apiPostJson).toHaveBeenCalledTimes(1)
  })
})
