/**
 * useDeleteAccount — mutation against DELETE /account (ORPHEUS-124).
 *
 * Deliberately a *pure* mutation: the post-success teardown (local
 * sign-out, cache clear, redirect to /login) lives in the AccountPage
 * handler, not here. Two reasons:
 *
 *   1. Order matters and is page-specific — the explicit
 *      `navigate('/login', { state: { accountDeleted: true } })` must
 *      run in the same handler as the sign-out so the confirmation
 *      notice's location state isn't lost to ProtectedRoute's own
 *      session-null redirect racing it.
 *   2. `signOut()` can reject after a successful deletion (the server
 *      side of the session is already gone), and that failure must not
 *      mark the mutation itself as errored — the account IS deleted.
 *
 * Errors surface as `ApiError` (409 roster guard, 502 partial-failure
 * messages — both carry a user-renderable `body.detail`) or
 * `NetworkError` (transport death).
 */

import { useMutation } from '@tanstack/react-query'

import { apiDelete } from '../lib/apiClient'

export interface DeleteAccountResponse {
  deleted: boolean
}

export function useDeleteAccount() {
  return useMutation<DeleteAccountResponse | undefined, Error>({
    mutationFn: () => apiDelete<DeleteAccountResponse>('/account'),
  })
}
