import { useQuery, useQueryClient } from '@tanstack/react-query'

import { apiGet, ApiError } from '../lib/apiClient'
import { useSession } from '../lib/auth'
import { useSessionRoles } from './useSessionRoles'

/**
 * One row in the advisor's client list (GET /clients).
 *
 * Shape mirrors `ClientListItem` in backend/routers/clients.py.
 * `is_self` lets the UI suppress the "Run my own report" button and
 * decorate the row with a "You" affordance without a second round
 * trip against /session.
 *
 * `latest_job` is null when no job has ever been kicked off for this
 * client; otherwise it's the most recent regardless of state.
 */
export interface AdvisorClient {
  id: string
  display_name: string
  email: string
  invitation_status: 'pending' | 'accepted' | 'expired'
  is_self: boolean
  latest_job: {
    id: string
    status: 'pending' | 'running' | 'complete' | 'failed'
    // ORPHEUS-88: completed on incomplete/degraded data — chip the roster row.
    data_limited?: boolean
  } | null
}

/**
 * Body of GET /clients.
 */
export interface AdvisorClientsResponse {
  clients: AdvisorClient[]
}

/**
 * React Query hook against GET /clients (ORPHEUS-39).
 *
 * Caching strategy:
 *
 *   - `enabled` gates on (a) authenticated Supabase session AND (b)
 *     `roles.is_advisor()` resolved via `/session`. Before either is
 *     true the query is dormant — non-advisors never hit /clients
 *     and the 403 doesn't get rendered as a misleading "error" state.
 *
 *   - No `staleTime` override; default 0 means the list refetches on
 *     window focus and on every mount. That's intentional: invitation
 *     state changes server-side (acceptance via /accept-invitation,
 *     jobs progressing) and the admin page is exactly where the
 *     advisor wants the freshest view.
 *
 *   - `retry: false`. A 401/403 here means an auth-shape problem, not
 *     a transient failure; retrying won't help and would silently
 *     burn requests.
 *
 * The cache key `['advisor', 'clients']` is invalidated by the
 * invite / resend / self-report mutation hooks below, so a successful
 * mutation surfaces in the list without a manual refetch.
 */
export function useAdvisorClients() {
  const { status } = useSession()
  const rolesQuery = useSessionRoles()
  const isAdvisor = Boolean(rolesQuery.data?.advisor_id)

  return useQuery<AdvisorClientsResponse, ApiError>({
    queryKey: ['advisor', 'clients'],
    queryFn: () => apiGet<AdvisorClientsResponse>('/clients'),
    enabled: status === 'authenticated' && isAdvisor,
    retry: false,
  })
}

/**
 * Cache key for the list query. Exported so mutation hooks below
 * stay in sync with the query hook without stringly-typed
 * duplication.
 */
export const ADVISOR_CLIENTS_QUERY_KEY = ['advisor', 'clients'] as const

/**
 * Helper for mutation hooks: read the current list cache.
 *
 * Used for optimistic updates (see useInviteClient) so the new row
 * appears immediately and rolls back on failure. Returns undefined
 * if the list hasn't been fetched yet — in which case the mutation
 * skips the optimistic path entirely.
 */
export function readAdvisorClientsCache(queryClient: ReturnType<typeof useQueryClient>) {
  return queryClient.getQueryData<AdvisorClientsResponse>(ADVISOR_CLIENTS_QUERY_KEY)
}
