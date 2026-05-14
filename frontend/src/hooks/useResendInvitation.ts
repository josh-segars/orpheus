import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiPostJson } from '../lib/apiClient'
import { ADVISOR_CLIENTS_QUERY_KEY } from './useAdvisorClients'

/**
 * Response from POST /clients/{id}/resend-invitation. Returns the same
 * client_id — the row's PK is unchanged, just its invitation_token /
 * invitation_expires_at are rotated and `invitation_status` is reset
 * to 'pending'.
 */
export interface ResendInvitationResponse {
  client_id: string
}

/**
 * React Query mutation for POST /clients/{id}/resend-invitation
 * (ORPHEUS-38 / ORPHEUS-39).
 *
 * No optimistic update here — there's no visible row-level change
 * the UI needs to render before the server confirms. The backend
 * rotates the token + resets status to 'pending' on success; status
 * was probably already 'pending' or 'expired', so a flash of "now
 * pending again" isn't worth the optimistic-rollback complexity.
 *
 * onSuccess invalidates the list cache so a status change from
 * 'expired' → 'pending' surfaces; that's the only user-visible
 * difference and it's worth a refetch.
 */
export function useResendInvitation() {
  const queryClient = useQueryClient()

  return useMutation<ResendInvitationResponse, ApiError, string>({
    mutationFn: (clientId) =>
      apiPostJson<ResendInvitationResponse>(
        `/clients/${clientId}/resend-invitation`,
        // POST with an empty body — the backend reads everything it
        // needs from the URL + auth context.
        {},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADVISOR_CLIENTS_QUERY_KEY })
    },
  })
}

/**
 * Best-effort error-message extractor for the resend mutation. The
 * 409 case (client already accepted) carries the most actionable
 * detail; 502 (email failed but token rotated) is similar. Defaults
 * to a generic message otherwise.
 */
export function extractResendErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === 'object') {
    const detail = (error.body as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail) {
      return detail
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return 'We couldn’t resend the invitation. Please try again.'
}
