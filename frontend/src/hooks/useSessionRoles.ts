import { useQuery } from '@tanstack/react-query'

import { apiGet, ApiError } from '../lib/apiClient'
import { useSession } from '../lib/auth'

/**
 * Backend-shaped session role tuple, returned by GET /session
 * (backend/routers/session.py).
 *
 * `advisor_id` and `client_id` are both optional and independently
 * orthogonal: either, both, or neither may be set. The "neither"
 * case is the canonical "authenticated but not invited" signal that
 * ProtectedRoute uses to route users to /not-invited.
 */
export interface SessionRoles {
  user_id: string
  email: string
  advisor_id: string | null
  client_id: string | null
}

/**
 * Fetch the caller's session roles from the backend.
 *
 * Caching strategy:
 *
 *   - `enabled` gates the query on the Supabase session being
 *     authenticated. Before sign-in the query is dormant; nothing
 *     gets fetched. After sign-out, useSession in lib/auth.ts
 *     clears the QueryClient, so the next mount starts fresh.
 *
 *   - `staleTime: Infinity` because roles don't change during a
 *     session. Supabase auto-refreshes the JWT every hour but the
 *     /session response is invariant under that refresh. We do
 *     invalidate the cache manually on key state changes:
 *     `useAcceptInvitation`'s onSuccess invalidates ['session']
 *     so the freshly-linked clients row is observed.
 *
 *   - `retry: false`. A 401 from /session means something
 *     authentication-shaped is wrong (token signature, audience,
 *     issuer) — retrying won't help, and the user should be
 *     bounced to /not-invited (where they can sign out).
 */
export function useSessionRoles() {
  const { status } = useSession()

  return useQuery<SessionRoles, ApiError>({
    queryKey: ['session'],
    queryFn: () => apiGet<SessionRoles>('/session'),
    enabled: status === 'authenticated',
    staleTime: Infinity,
    retry: false,
  })
}
