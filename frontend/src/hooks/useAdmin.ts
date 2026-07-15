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

import { ApiError, apiGet, apiPatchJson } from '../lib/apiClient'
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
