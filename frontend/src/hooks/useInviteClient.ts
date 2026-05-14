import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiPostJson } from '../lib/apiClient'
import {
  ADVISOR_CLIENTS_QUERY_KEY,
  AdvisorClient,
  AdvisorClientsResponse,
} from './useAdvisorClients'

/**
 * Body of POST /clients/invite. Matches `InviteClientRequest` in
 * backend/routers/clients.py. The backend trims + lowercases both
 * fields server-side; we don't need to pre-normalise here.
 */
export interface InviteClientRequest {
  display_name: string
  email: string
}

/**
 * Response from POST /clients/invite — just the new clients.id.
 */
export interface InviteClientResponse {
  client_id: string
}

/**
 * React Query mutation for POST /clients/invite (ORPHEUS-38 / ORPHEUS-39).
 *
 * Optimistic update strategy:
 *
 *   - onMutate snapshots the current list, splices a pending placeholder
 *     row to the top (the backend orders desc by created_at, so newest
 *     wins). The placeholder uses a tombstone id (`optimistic-<random>`)
 *     so the UI knows not to wire action buttons to it before the
 *     server confirms.
 *   - onError restores the snapshot — if invite failed, the pending row
 *     disappears.
 *   - onSettled invalidates the list query so the next read is the real
 *     server state. Catches the success case (real id from response
 *     replaces the placeholder) and any partial state from a 502 (row
 *     persisted, email failed — the user can hit resend).
 *
 * The 502 case is worth calling out: the backend deliberately keeps the
 * clients row on email-send failure so the advisor can retry via the
 * resend endpoint. onError would normally roll back; onSettled's
 * invalidate pulls in the real row regardless, so a 502 leaves the
 * advisor seeing the persisted pending row + a banner directing them
 * to resend.
 */
export function useInviteClient() {
  const queryClient = useQueryClient()

  return useMutation<
    InviteClientResponse,
    ApiError,
    InviteClientRequest,
    { previousList: AdvisorClientsResponse | undefined }
  >({
    mutationFn: (body) => apiPostJson<InviteClientResponse>('/clients/invite', body),

    onMutate: async (variables) => {
      // Cancel any in-flight list refetch so it doesn't clobber the
      // optimistic insert before the server responds.
      await queryClient.cancelQueries({ queryKey: ADVISOR_CLIENTS_QUERY_KEY })

      const previousList = queryClient.getQueryData<AdvisorClientsResponse>(
        ADVISOR_CLIENTS_QUERY_KEY,
      )

      if (previousList) {
        const placeholder: AdvisorClient = {
          id: `optimistic-${Math.random().toString(36).slice(2)}`,
          display_name: variables.display_name,
          email: variables.email,
          invitation_status: 'pending',
          is_self: false,
          latest_job: null,
        }
        queryClient.setQueryData<AdvisorClientsResponse>(
          ADVISOR_CLIENTS_QUERY_KEY,
          { clients: [placeholder, ...previousList.clients] },
        )
      }

      return { previousList }
    },

    onError: (_err, _variables, context) => {
      if (context?.previousList) {
        queryClient.setQueryData(ADVISOR_CLIENTS_QUERY_KEY, context.previousList)
      }
    },

    onSettled: () => {
      // Whether success or failure, refetch so the cache reflects
      // actual server state (the real row id, the real created_at,
      // any partial state from a 502).
      void queryClient.invalidateQueries({ queryKey: ADVISOR_CLIENTS_QUERY_KEY })
    },
  })
}

/**
 * Best-effort user-facing error message extractor. Mirrors
 * `extractAcceptInvitationErrorMessage` in useAcceptInvitation.ts —
 * FastAPI HTTPException serializes as `{detail: "..."}` and
 * validation errors as `{detail: [{loc, msg, type}, ...]}`.
 *
 * The 409 case (duplicate email) and 502 case (email failed but row
 * exists) carry the most actionable detail; the rest fall back to a
 * generic message rather than render PyJWT internals.
 */
export function extractInviteErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === 'object') {
    const detail = (error.body as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail) {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown }
      if (typeof first.msg === 'string' && first.msg) {
        return first.msg
      }
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return 'We couldn’t send the invitation. Please try again.'
}
