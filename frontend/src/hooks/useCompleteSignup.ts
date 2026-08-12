import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Session } from '@supabase/supabase-js'

import { ApiError, apiGet, apiPostJson } from '../lib/apiClient'
import type { SessionRoles } from './useSessionRoles'

/**
 * Request body for POST /signup/complete (ORPHEUS-85).
 *
 * `display_name` is best-effort from LinkedIn OIDC metadata — the
 * backend falls back to the email local-part when it's absent, so
 * callers should pass null rather than inventing a value.
 */
export interface CompleteSignupRequest {
  beta_code: string
  display_name: string | null
}

/**
 * Response from POST /signup/complete.
 *
 * `created=false` is the idempotent path — the caller already had a
 * linked clients row (prior sign-up or accepted invitation) and got it
 * back. The UI treats both values identically.
 */
export interface CompleteSignupResponse {
  client_id: string
  created: boolean
}

/**
 * Best-effort display name from the Supabase session's LinkedIn OIDC
 * metadata. LinkedIn provides `name` (and `given_name`/`family_name`)
 * in user_metadata; shape isn't guaranteed, so every read is defensive
 * and the fallback is null — the backend derives a label server-side.
 */
export function displayNameFromSession(session: Session | null): string | null {
  const metadata = session?.user?.user_metadata as
    | Record<string, unknown>
    | undefined
  if (!metadata) return null

  const name = metadata.name
  if (typeof name === 'string' && name.trim()) return name.trim()

  const given = typeof metadata.given_name === 'string' ? metadata.given_name : ''
  const family =
    typeof metadata.family_name === 'string' ? metadata.family_name : ''
  const joined = `${given} ${family}`.trim()
  return joined || null
}

/**
 * React Query mutation wrapping POST /signup/complete.
 *
 * Used by SignupCallbackPage (post-OAuth auto-fire) and by SignupPage's
 * already-authenticated branch (a /not-invited user clicking "sign
 * up"). On a wrong-code 403 the caller re-prompts and re-invokes with
 * the corrected code — same mutation instance, no OAuth re-run.
 *
 * The onSuccess session-priming mirrors useAcceptInvitation exactly
 * (ORPHEUS-58): `useSessionRoles` has no observer mounted on the public
 * signup routes, so `invalidateQueries` alone can't refetch — the
 * navigate to "/" would race ProtectedRoute into reading the stale
 * neither-role snapshot and bouncing the brand-new client to
 * /not-invited. `fetchQuery` writes fresh roles into the cache before
 * the mutation resolves.
 */
export function useCompleteSignup() {
  const queryClient = useQueryClient()
  return useMutation<CompleteSignupResponse, ApiError, CompleteSignupRequest>({
    mutationFn: ({ beta_code, display_name }) =>
      apiPostJson<CompleteSignupResponse>('/signup/complete', {
        beta_code,
        display_name,
      }),
    onSuccess: async () => {
      try {
        await queryClient.fetchQuery<SessionRoles, ApiError>({
          queryKey: ['session'],
          queryFn: () => apiGet<SessionRoles>('/session'),
          staleTime: 0,
        })
      } catch {
        // If /session fails here, ProtectedRoute refetches on mount and
        // surfaces the error through its own path. Don't block success.
      }
      void queryClient.invalidateQueries({ queryKey: ['session'] })
    },
  })
}

/**
 * Best-effort extraction of a user-readable message from an ApiError.
 * Same collapse rules as the invitation flow's extractor: FastAPI's
 * HTTPException serializes as `{detail: "..."}`; validation errors as
 * `{detail: [{loc, msg, type}, ...]}`.
 */
export function extractSignupErrorMessage(error: unknown): string {
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
  return 'We could not complete your sign-up. Please try again.'
}

/** True when the error is the wrong-beta-code 403 — the recoverable case. */
export function isWrongCodeError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403
}
