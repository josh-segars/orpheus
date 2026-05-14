import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiPostJson } from '../lib/apiClient'
import { ADVISOR_CLIENTS_QUERY_KEY } from './useAdvisorClients'

/**
 * Body of POST /advisor/self-report (ORPHEUS-39).
 *
 * `display_name` is optional. The frontend passes the LinkedIn
 * `user_metadata.name` from the Supabase session when present; the
 * backend falls back to the email local-part otherwise.
 */
export interface SelfReportRequest {
  display_name?: string | null
}

/**
 * Response from POST /advisor/self-report.
 *
 * `created=true` indicates a fresh INSERT, `created=false` indicates
 * an idempotent hit — a self-clients row already existed. The UI
 * uses this to decide whether to announce "Your self-report row is
 * ready" vs silently navigate (the row was already there, the
 * advisor probably double-clicked).
 */
export interface SelfReportResponse {
  client_id: string
  created: boolean
}

/**
 * React Query mutation for POST /advisor/self-report (ORPHEUS-39).
 *
 * Two cache invalidations on success:
 *
 *   1. `['advisor', 'clients']` — the new clients row needs to appear
 *      in the advisor's list immediately.
 *
 *   2. `['session']` — the advisor now also holds the client role,
 *      so `useSessionRoles` should refetch. This is what unlocks the
 *      "My report" tab in PortalNav (the dual-role toggle).
 *
 * Optimistic update is intentionally skipped — we don't have the
 * canonical client_id until the server responds, and a stub row in
 * the list would race with the "redirect to /jobs/:id" outcome the
 * caller actually wants on first creation.
 */
export function useSelfReport() {
  const queryClient = useQueryClient()

  return useMutation<SelfReportResponse, ApiError, SelfReportRequest>({
    mutationFn: (body) =>
      apiPostJson<SelfReportResponse>('/advisor/self-report', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADVISOR_CLIENTS_QUERY_KEY })
      void queryClient.invalidateQueries({ queryKey: ['session'] })
    },
  })
}

/**
 * Best-effort error-message extractor for the self-report mutation.
 * 403 (non-advisor) and 500 (INSERT failed) are the only realistic
 * error shapes; the rest fall back to a generic message.
 */
export function extractSelfReportErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === 'object') {
    const detail = (error.body as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail) {
      return detail
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return 'We couldn’t set up your self-report. Please try again.'
}
