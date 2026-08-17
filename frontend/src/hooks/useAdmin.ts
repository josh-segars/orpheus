/**
 * React Query hooks for the /admin stopgap surface (ORPHEUS-31).
 *
 * All four hooks gate on Supabase session + admin allowlist membership
 * (resolved client-side from `VITE_ADMIN_EMAILS`). The allowlist is NOT
 * a security boundary — the backend enforces it via the
 * `get_current_admin` dependency. The client-side check exists so the
 * admin UI doesn't fire a request that's guaranteed to 403.
 *
 * Mirrors the response shapes from backend/routers/admin.py exactly;
 * keep both sides in sync when the schema evolves.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import { ApiError, apiGet, apiPatchJson, apiPostJson } from '../lib/apiClient'
import { useSession } from '../lib/auth'

// --------------------------------------------------------------------------- //
// Allowlist resolution
//
// `VITE_ADMIN_EMAILS` is a comma-separated string baked into the Vite
// bundle at build time. It exists solely as a UX gate so non-admins
// don't hit /admin endpoints and see misleading 403s; the backend
// enforces the real allowlist via env-var ADMIN_EMAILS.
// --------------------------------------------------------------------------- //

const ADMIN_EMAIL_SET: Set<string> = (() => {
  const raw = (import.meta.env.VITE_ADMIN_EMAILS as string | undefined) ?? ''
  return new Set(
    raw
      .split(',')
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
  )
})()

export function isAdminEmail(email: string | null | undefined): boolean {
  if (!email) return false
  return ADMIN_EMAIL_SET.has(email.trim().toLowerCase())
}

// --------------------------------------------------------------------------- //
// Response types — mirror backend/routers/admin.py
// --------------------------------------------------------------------------- //

export interface AdminAdvisorSummary {
  id: string
  practice_name: string | null
  email: string | null
}

export interface AdminJobSummary {
  id: string
  status: string
  created_at: string | null
  data_limited?: boolean // ORPHEUS-88
}

export interface AdminClient {
  id: string
  display_name: string
  email: string
  invitation_status: string
  created_at: string | null
  user_id: string | null
  advisor: AdminAdvisorSummary | null
  latest_job: AdminJobSummary | null
}

export interface AdminClientsResponse {
  clients: AdminClient[]
}

export interface AdminNarrativeMeta {
  id: string
  section: string
  status: string
  has_edited_text: boolean
  published_at: string | null
  generated_at: string | null
}

export interface AdminJob {
  id: string
  client_id: string
  client_display_name: string | null
  client_email: string | null
  status: string
  version_label: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  data_limited?: boolean // ORPHEUS-88
  // ORPHEUS-131: the narrative shipped with prose-number-gate violations
  // still in it (final-attempt degrade, or the `log` kill switch). Optional —
  // pre-migration-023 rows carry neither field.
  prose_gate_degraded?: boolean
  prose_gate_violations?: string | null
  narratives: AdminNarrativeMeta[]
}

export interface AdminJobsResponse {
  jobs: AdminJob[]
}

export interface AdminNarrative {
  id: string
  job_id: string
  section: string
  generated_text: string
  edited_text: string | null
  status: string
  published_at: string | null
  generated_at: string | null
}

export interface UpdateAdminNarrativeRequest {
  edited_text?: string | null
  status?: 'draft' | 'published'
}

// ORPHEUS-104 — mirrors AdminWaitlistEntry in backend/routers/admin.py
export interface AdminWaitlistEntry {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  interests: string[]
  source: string | null
  created_at: string | null
}

export interface AdminWaitlistResponse {
  entries: AdminWaitlistEntry[]
}

// --------------------------------------------------------------------------- //
// Query keys — centralised so mutation hooks invalidate the right caches
// --------------------------------------------------------------------------- //

export const ADMIN_CLIENTS_QUERY_KEY = ['admin', 'clients'] as const

export const adminJobsQueryKey = (clientId: string | null) =>
  ['admin', 'jobs', clientId ?? 'all'] as const

export const adminNarrativeQueryKey = (narrativeId: string) =>
  ['admin', 'narratives', narrativeId] as const

export const ADMIN_WAITLIST_QUERY_KEY = ['admin', 'waitlist'] as const

// --------------------------------------------------------------------------- //
// Hooks
// --------------------------------------------------------------------------- //

function useEnabled() {
  // Gate every admin query on (a) authenticated Supabase session and
  // (b) signed-in email present in VITE_ADMIN_EMAILS. The allowlist
  // check is duplicated server-side; doing it here means the UI never
  // surfaces a confusing 403 to non-admin users who navigate to /admin
  // directly (they get bounced by AdminRoute before this fires).
  const { session, status } = useSession()
  const email = session?.user?.email ?? null
  return status === 'authenticated' && isAdminEmail(email)
}

export function useAdminClients() {
  const enabled = useEnabled()
  return useQuery<AdminClientsResponse, ApiError>({
    queryKey: ADMIN_CLIENTS_QUERY_KEY,
    queryFn: () => apiGet<AdminClientsResponse>('/admin/clients'),
    enabled,
    retry: false,
  })
}

export function useAdminJobs(clientId: string | null = null) {
  const enabled = useEnabled()
  return useQuery<AdminJobsResponse, ApiError>({
    queryKey: adminJobsQueryKey(clientId),
    queryFn: () =>
      apiGet<AdminJobsResponse>(
        clientId
          ? `/admin/jobs?client_id=${encodeURIComponent(clientId)}`
          : '/admin/jobs',
      ),
    enabled,
    retry: false,
  })
}

export function useAdminNarrative(narrativeId: string | null) {
  const enabled = useEnabled() && Boolean(narrativeId)
  return useQuery<AdminNarrative, ApiError>({
    queryKey: narrativeId
      ? adminNarrativeQueryKey(narrativeId)
      : ['admin', 'narratives', '__none__'],
    queryFn: () =>
      apiGet<AdminNarrative>(`/admin/narratives/${narrativeId}`),
    enabled,
    retry: false,
  })
}

/**
 * Read-only view of `public.waitlist` via `GET /admin/waitlist`
 * (ORPHEUS-104). The table is write-only from the browser (anon
 * INSERT-only RLS), so this admin endpoint is the only in-app read
 * surface for marketing-page signups.
 */
export function useAdminWaitlist() {
  const enabled = useEnabled()
  return useQuery<AdminWaitlistResponse, ApiError>({
    queryKey: ADMIN_WAITLIST_QUERY_KEY,
    queryFn: () => apiGet<AdminWaitlistResponse>('/admin/waitlist'),
    enabled,
    retry: false,
  })
}

/**
 * Mutation against `PATCH /admin/narratives/{id}`.
 *
 * On success, invalidates the narrative's own cache so the editor
 * sees the persisted row, plus the admin/jobs cache so the section's
 * `has_edited_text` / `status` chips in the jobs list refresh. We
 * don't try optimistic updates here — narrative text is the thing the
 * admin wants to see persist correctly; a flash of stale data on save
 * is preferable to silently dropping a typo correction on rollback.
 */
export function useUpdateAdminNarrative() {
  const queryClient = useQueryClient()
  return useMutation<
    AdminNarrative,
    ApiError,
    { narrativeId: string; body: UpdateAdminNarrativeRequest }
  >({
    mutationFn: ({ narrativeId, body }) =>
      apiPatchJson<AdminNarrative>(`/admin/narratives/${narrativeId}`, body),
    onSuccess: (data) => {
      queryClient.setQueryData(adminNarrativeQueryKey(data.id), data)
      // Invalidate every admin/jobs variant — clientId-filter cache
      // keys are derived, so target the prefix.
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'jobs'],
      })
    },
  })
}

/**
 * Best-effort detail extractor for ApiError bodies. Mirrors the helper
 * in useInviteClient — FastAPI HTTPException serialises as
 * `{detail: "..."}` and validation errors as `{detail: [{loc, msg, type}, ...]}`.
 */
export function extractAdminErrorMessage(error: unknown): string {
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
  return 'Something went wrong. Please try again.'
}

// --------------------------------------------------------------------------- //
// Sign-up access codes (ORPHEUS-129)
// --------------------------------------------------------------------------- //

// Mirrors AdminSignupCode in backend/routers/admin.py.
export interface AdminSignupCode {
  id: string
  code: string
  label: string
  advisor_id: string | null
  advisor_practice_name: string | null
  expires_at: string | null
  max_uses: number | null
  disabled_at: string | null
  created_by: string | null
  created_at: string | null
  redemption_count: number
}

export interface AdminCodesResponse {
  codes: AdminSignupCode[]
}

export interface CreateAdminCodeRequest {
  label: string
  code?: string | null
  advisor_id?: string | null
  expires_at?: string | null
  max_uses?: number | null
}

export const ADMIN_CODES_QUERY_KEY = ['admin', 'codes'] as const

export function useAdminCodes() {
  const enabled = useEnabled()
  return useQuery<AdminCodesResponse, ApiError>({
    queryKey: ADMIN_CODES_QUERY_KEY,
    queryFn: () => apiGet<AdminCodesResponse>('/admin/codes'),
    enabled,
    retry: false,
  })
}

/**
 * Mutation against `POST /admin/codes`. On success, invalidates the
 * codes list so the new row (with its generated code value) appears —
 * the response also carries the full row, so callers can surface the
 * minted code immediately without waiting for the refetch.
 */
export function useCreateAdminCode() {
  const queryClient = useQueryClient()
  return useMutation<AdminSignupCode, ApiError, CreateAdminCodeRequest>({
    mutationFn: (body) => apiPostJson<AdminSignupCode>('/admin/codes', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADMIN_CODES_QUERY_KEY })
    },
  })
}

/**
 * Mutation against `PATCH /admin/codes/{id}` — the disable/enable
 * kill switch. Same invalidate-don't-optimistically-update posture as
 * the narrative editor: a disabled code failing to disable must not
 * look disabled.
 */
export function useUpdateAdminCode() {
  const queryClient = useQueryClient()
  return useMutation<
    AdminSignupCode,
    ApiError,
    { codeId: string; disabled: boolean }
  >({
    mutationFn: ({ codeId, disabled }) =>
      apiPatchJson<AdminSignupCode>(`/admin/codes/${codeId}`, { disabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADMIN_CODES_QUERY_KEY })
    },
  })
}

// Mirrors AdminCodeRedemption in backend/routers/admin.py — the
// proto-cohort roster row (see the B2B Cohort Assessment scoping doc:
// redemptions are enrollment provenance; `cohort_members` backfills
// from these when the cohort layer lands).
export interface AdminCodeRedemption {
  client_id: string
  display_name: string
  email: string
  redeemed_at: string | null
  latest_job: AdminJobSummary | null
}

export interface AdminCodeRedemptionsResponse {
  redemptions: AdminCodeRedemption[]
}

export function adminCodeRedemptionsQueryKey(codeId: string | null) {
  return ['admin', 'codes', codeId, 'redemptions'] as const
}

/**
 * Roster for one code — fetched on demand when the admin expands the
 * code's row (same load-on-select posture as useAdminNarrative), so
 * the codes list stays one cheap query.
 */
export function useAdminCodeRedemptions(codeId: string | null) {
  const enabled = useEnabled() && Boolean(codeId)
  return useQuery<AdminCodeRedemptionsResponse, ApiError>({
    queryKey: adminCodeRedemptionsQueryKey(codeId),
    queryFn: () =>
      apiGet<AdminCodeRedemptionsResponse>(
        `/admin/codes/${codeId}/redemptions`,
      ),
    enabled,
    retry: false,
  })
}
