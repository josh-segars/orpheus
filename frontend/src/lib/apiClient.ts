/**
 * Thin fetch wrapper. In dev (with VITE_API_BASE_URL pointed at the local
 * FastAPI on http://localhost:8000), requests hit the real backend. MSW is
 * still installed for offline frontend playgrounds, but its handlers register
 * paths only — same-origin matches — so they don't intercept cross-origin
 * calls to the backend.
 *
 * Every authenticated request carries `Authorization: Bearer <access_token>`
 * pulled from the current Supabase session. The backend's
 * get_current_session_roles dependency (backend/auth.py) verifies the token
 * against Supabase JWKS and resolves the user's advisor/client role(s).
 */

import { supabase } from './supabase'

/**
 * Resolve `VITE_API_BASE_URL` at module-eval time. Fails fast (matches
 * the `supabase.ts` posture for `VITE_SUPABASE_*`) if the env var is
 * missing or, post-ORPHEUS-54, if it's set to a scheme-less host. A
 * value like `orpheus-production-5082.up.railway.app` (no
 * `https://`) is interpreted by the browser as a relative path off
 * the current origin, so requests like `apiGet('/session')` land on
 * the SPA index.html with 304s and `useSessionRoles` reads HTML
 * instead of JSON. Catching this at boot beats debugging a
 * `/not-invited` bounce in prod.
 */
const baseUrl = (() => {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (!raw || !raw.trim()) {
    throw new Error(
      'Missing API base URL. Set VITE_API_BASE_URL in your frontend env ' +
        '(e.g. http://localhost:8000 for local, https://<your-host> for ' +
        'deployed). See frontend/.env.local.example.',
    )
  }
  const trimmed = raw.trim()
  if (!/^https?:\/\//i.test(trimmed)) {
    throw new Error(
      `Invalid VITE_API_BASE_URL: ${JSON.stringify(trimmed)}. It must ` +
        'include a scheme (http:// or https://). A scheme-less host is ' +
        'treated as a relative path by the browser, which silently routes ' +
        'API calls into the SPA index.html.',
    )
  }
  return trimmed.replace(/\/$/, '')
})()

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * A transport-level failure — the request never produced an HTTP response.
 * `fetch()` rejects with a `TypeError` (surfaced to users as the opaque
 * "Failed to fetch") when the connection is refused/dropped, DNS fails,
 * CORS blocks it, or a large upload body dies mid-transfer at the edge
 * (the ORPHEUS-86 symptom). Distinct from `ApiError`, which always carries
 * a real HTTP status and (usually) a `{detail}` body the UI can render.
 * Callers branch on `instanceof NetworkError` to show connection-oriented
 * guidance instead of leaking the raw browser message.
 */
export class NetworkError extends Error {
  constructor(
    message: string,
    public readonly cause?: unknown,
  ) {
    super(message)
    this.name = 'NetworkError'
  }
}

/**
 * A deterministic rejection from Supabase Storage (HTTP 4xx) during the
 * ORPHEUS-108 browser-direct upload — wrong MIME type, size cap, or a
 * bad/expired signed-URL token. Unlike `NetworkError`, retrying the same
 * file cannot succeed, so callers must NOT show connection-oriented
 * guidance (ORPHEUS-109: Windows ZIP MIME rejections wore the
 * connection/large-archive copy and triaged as a network mystery).
 * `reason` carries the storage service's own message for display so the
 * next such failure is self-identifying. Lives here (not in useCreateJob)
 * because apiClient is the error-taxonomy home GroundworkPage already
 * branches on, even though Storage uploads don't travel through the
 * fetch wrappers below.
 */
export class UploadRejectedError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly reason: string,
  ) {
    super(message)
    this.name = 'UploadRejectedError'
  }
}

/**
 * `fetch()` with transport failures normalized to `NetworkError`. A
 * deliberate `AbortController` cancellation (React Query unmount, etc.)
 * still surfaces as the original `AbortError` so callers can treat it as
 * a cancellation rather than a failure.
 */
async function safeFetch(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err
    }
    throw new NetworkError(
      'The request could not reach the server.',
      err,
    )
  }
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(await authHeaders()),
  }

  const res = await safeFetch(url, { method: 'GET', headers, signal })
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      // body wasn't JSON — fine, leave null
    }
    throw new ApiError(`GET ${path} failed: ${res.status}`, res.status, body)
  }
  return (await res.json()) as T
}

/**
 * POST a JSON body. Used by the invitation flow (ORPHEUS-38) and any
 * future endpoint where the request shape isn't multipart.
 *
 * Pairs with the backend's Pydantic-validated request models — the
 * shape mismatch case surfaces as a 422 with FastAPI's standard
 * `{detail: [{loc, msg, type}, ...]}` body, which the ApiError carries
 * through to callers.
 */
export async function apiPostJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(await authHeaders()),
  }

  const res = await safeFetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    let responseBody: unknown = null
    try {
      responseBody = await res.json()
    } catch {
      // body wasn't JSON — fine, leave null
    }
    throw new ApiError(
      `POST ${path} failed: ${res.status}`,
      res.status,
      responseBody,
    )
  }
  return (await res.json()) as T
}

/**
 * PATCH a JSON body. Used by the admin surface (ORPHEUS-31) to update
 * narrative rows; pairs with backend `UpdateAdminNarrativeRequest`-style
 * partial models where `model_dump(exclude_unset=True)` matters server-side.
 *
 * Same error shape as `apiPostJson` — non-2xx throws an `ApiError`
 * carrying the parsed body so callers can extract `body.detail`.
 */
export async function apiPatchJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(await authHeaders()),
  }

  const res = await safeFetch(url, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    let responseBody: unknown = null
    try {
      responseBody = await res.json()
    } catch {
      // body wasn't JSON — fine, leave null
    }
    throw new ApiError(
      `PATCH ${path} failed: ${res.status}`,
      res.status,
      responseBody,
    )
  }
  return (await res.json()) as T
}

/**
 * POST a multipart/form-data body. Used by the LinkedIn upload flow
 * (ORPHEUS-16) to submit the ZIP archive + XLSX analytics to /jobs.
 *
 * We deliberately don't set a Content-Type header — the browser's fetch
 * implementation generates one with the correct multipart boundary when
 * the body is a FormData instance.
 */
export async function apiPostMultipart<T>(
  path: string,
  formData: FormData,
  signal?: AbortSignal,
): Promise<T> {
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(await authHeaders()),
  }

  const res = await safeFetch(url, {
    method: 'POST',
    headers,
    body: formData,
    signal,
  })
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      // body wasn't JSON — fine, leave null
    }
    throw new ApiError(`POST ${path} failed: ${res.status}`, res.status, body)
  }
  return (await res.json()) as T
}
