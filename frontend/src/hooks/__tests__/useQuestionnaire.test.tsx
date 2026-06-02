/**
 * useUpsertQuestionnaire — ORPHEUS-57 regression coverage.
 *
 * The bug shipped 2026-06-01: the mutationFn was using
 * `session.user.id` (auth.users.id) as `client_id`, but the schema
 * FKs `questionnaire_responses.client_id → clients(id)` and RLS keys
 * on `clients.id`. The fix routes through `useSessionRoles()` so the
 * upsert writes the row id the backend recognises.
 *
 * Coverage:
 *   1. Happy path — upsert payload's `client_id` comes from
 *      `useSessionRoles().data.client_id`, NOT `session.user.id`.
 *   2. Defensive guard — null `client_id` raises a clear error
 *      before any Supabase call.
 *
 * Per the ORPHEUS-47 convention, we vi.mock the data dependencies
 * (useSessionRoles, supabase) rather than running an MSW server.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { type ReactNode } from 'react'

import { useUpsertQuestionnaire } from '../useQuestionnaire'
import { useSessionRoles } from '../useSessionRoles'

// --------------------------------------------------------------------------- //
// Module mocks
// --------------------------------------------------------------------------- //

vi.mock('../useSessionRoles', () => ({
  useSessionRoles: vi.fn(),
}))

// Mock the supabase singleton at the import site. The upsert chain
// ends in a single() call that returns { data, error }; that's the
// only shape the hook reads.
const upsertSingleMock = vi.fn()
const upsertSelectMock = vi.fn(() => ({ single: upsertSingleMock }))
const upsertChainMock = vi.fn(
  (_payload: Record<string, unknown>, _options?: Record<string, unknown>) => ({
    select: upsertSelectMock,
  }),
)
const fromMock = vi.fn((_table: string) => ({ upsert: upsertChainMock }))

vi.mock('../../lib/supabase', () => ({
  supabase: {
    from: (table: string) => fromMock(table),
  },
}))

// --------------------------------------------------------------------------- //
// Render harness
// --------------------------------------------------------------------------- //

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
  return { Wrapper, queryClient }
}

// --------------------------------------------------------------------------- //
// Tests
// --------------------------------------------------------------------------- //

describe('useUpsertQuestionnaire (ORPHEUS-57)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    upsertSingleMock.mockResolvedValue({
      data: {
        client_id: 'clients-row-uuid',
        answers: { q9: 'hi' },
        created_at: '2026-06-02T00:00:00Z',
        updated_at: '2026-06-02T00:00:00Z',
      },
      error: null,
    })
  })

  it('writes clients.id from useSessionRoles, not auth.users.id', async () => {
    // The whole point of the regression: these two values diverged
    // under ORPHEUS-36's schema split. The hook MUST use the clients.id
    // value (from /session) rather than the auth.users.id (from the
    // Supabase session).
    vi.mocked(useSessionRoles).mockReturnValue({
      data: {
        user_id: 'auth-users-uuid-DO-NOT-USE',
        email: 'c@example.com',
        advisor_id: null,
        client_id: 'clients-row-uuid',
      },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSessionRoles>)

    const { Wrapper } = makeWrapper()
    const { result } = renderHook(() => useUpsertQuestionnaire(), {
      wrapper: Wrapper,
    })

    await act(async () => {
      await result.current.mutateAsync({ answers: { q9: 'hi' } })
    })

    await waitFor(() => expect(upsertChainMock).toHaveBeenCalledTimes(1))
    const firstCall = upsertChainMock.mock.calls[0]
    expect(firstCall).toBeDefined()
    const payload = firstCall![0] as {
      client_id: string
      answers: Record<string, unknown>
    }
    expect(payload.client_id).toBe('clients-row-uuid')
    expect(payload.client_id).not.toBe('auth-users-uuid-DO-NOT-USE')
    expect(payload.answers).toEqual({ q9: 'hi' })
    expect(fromMock).toHaveBeenCalledWith('questionnaire_responses')
  })

  it('throws a clear error when client_id is null (advisor-only / pre-link)', async () => {
    vi.mocked(useSessionRoles).mockReturnValue({
      data: {
        user_id: 'auth-users-uuid',
        email: 'a@example.com',
        advisor_id: 'advisor-1',
        client_id: null,
      },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSessionRoles>)

    const { Wrapper } = makeWrapper()
    const { result } = renderHook(() => useUpsertQuestionnaire(), {
      wrapper: Wrapper,
    })

    await expect(
      result.current.mutateAsync({ answers: { q9: 'hi' } }),
    ).rejects.toThrow(/no client_id resolved/i)

    // Critically — we must NOT have called supabase at all. Writing
    // `null` (or any non-clients.id value) would have RLS-rejected
    // silently, which is the whole bug.
    expect(fromMock).not.toHaveBeenCalled()
  })
})
