import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiGet, apiPostJson } from '../lib/apiClient'
import type { SessionRoles } from './useSessionRoles'

/**
 * Request body for POST /accept-invitation (ORPHEUS-38).
 *
 * `confirmed` defaults to false. The frontend sends `true` only after
 * the user has explicitly OK'd the soft-confirmation card surfaced when
 * the invitation email differs from their LinkedIn email.
 */
export interface AcceptInvitationRequest {
  token: string
  confirmed?: boolean
}

/**
 * Response from POST /accept-invitation.
 *
 * `requires_confirmation=true` means the invitation email differs from
 * the LinkedIn email; the frontend should render the mismatch
 * confirmation UI with `invitation_email` and `linkedin_email` shown.
 * In all other cases both email fields are `null` and the response
 * carries `client_id` for the successfully-linked row.
 */
export interface AcceptInvitationResponse {
  client_id: string
  requires_confirmation: boolean
  invitation_email: string | null
  linkedin_email: string | null
}

/**
 * React Query mutation wrapping POST /accept-invitation.
 *
 * The hook is used by InviteCallbackPage in two passes:
 *   1. First call on mount with just `{token}` — the backend may
 *      return either `requires_confirmation=true` (mismatch) or
 *      `requires_confirmation=false` (accepted).
 *   2. If the first response was mismatch, the page re-invokes
 *      mutate with `{token, confirmed: true}` once the user
 *      confirms.
 *
 * Both calls share the same mutation instance so the UI's pending
 * state is consistent across both passes.
 */
export function useAcceptInvitation() {
  const queryClient = useQueryClient()
  return useMutation<
    AcceptInvitationResponse,
    ApiError,
    AcceptInvitationRequest
  >({
    mutationFn: ({ token, confirmed }) =>
      apiPostJson<AcceptInvitationResponse>('/accept-invitation', {
        token,
        confirmed: confirmed ?? false,
      }),
    onSuccess: async (data) => {
      // Once acceptance commits server-side, the user has a real
      // clients row that the ProtectedRoute / NotInvitedPage logic
      // gates on. Skip the refresh in the mismatch case — nothing
      // changed server-side yet, the row is still pending until the
      // user confirms with `{confirmed: true}`.
      if (data.requires_confirmation) return

      // ORPHEUS-58: AWAIT the session refresh before the mutation
      // resolves. `invalidateQueries` alone is racy because
      // `useSessionRoles` is unmounted on the public /invite/callback
      // route — invalidation marks the cache stale but can't trigger
      // a refetch with no observer. ProtectedRoute mounts a beat
      // later (after `<Navigate to="/" />` fires) and, with
      // `staleTime: Infinity` on `useSessionRoles`, would read the
      // pre-acceptance neither-role snapshot from the cache and
      // bounce the user to /not-invited before the refetch lands.
      //
      // `fetchQuery` writes fresh data into the cache regardless of
      // mount state and resolves only when the response is in.
      // Because onSuccess is awaited, the mutation's `isSuccess`
      // doesn't flip until the cache is primed, so the InviteCallback
      // page's `<Navigate to="/" />` only fires once ProtectedRoute
      // is guaranteed to read the fresh roles.
      try {
        await queryClient.fetchQuery<SessionRoles, ApiError>({
          queryKey: ['session'],
          queryFn: () => apiGet<SessionRoles>('/session'),
          staleTime: 0,
        })
      } catch {
        // If the /session call itself fails here, ProtectedRoute
        // will re-fetch on mount and surface the error through its
        // own error path. Don't block the mutation success on it.
      }
      // Keep the invalidation too so any other consumer (e.g. a hook
      // mounted later in the same render cycle) sees stale-flagged
      // data and refetches as expected.
      void queryClient.invalidateQueries({ queryKey: ['session'] })
    },
  })
}

/**
 * Best-effort extraction of a user-readable message from an ApiError
 * or other thrown value. Used by the callback page's error UI.
 *
 * FastAPI's HTTPException serializes as `{detail: "..."}`. Validation
 * errors serialize as `{detail: [{loc, msg, type}, ...]}` — we
 * collapse the list to its first `msg` rather than try to render the
 * full structure to a portal-facing user.
 */
export function extractAcceptInvitationErrorMessage(error: unknown): string {
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
  return 'We could not finalize your invitation. Please try again.'
}
