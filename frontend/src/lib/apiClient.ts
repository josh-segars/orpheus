/**
 * Thin fetch wrapper. In dev (with VITE_API_BASE_URL pointed at the local
 * FastAPI on http://localhost:8000), requests hit the real backend. MSW is
 * still installed for offline frontend playgrounds, but its handlers register
 * paths only — same-origin matches — so they don't intercept cross-origin
 * calls to the backend.
 *
 * Every authenticated request carries `Authorization: Bearer <access_token>`
 * pulled from the current Supabase session. The backend's get_current_client
 * dependency (backend/auth.py) verifies the token against Supabase JWKS.
 */

import { supabase } from './supabase'

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

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

  const res = await fetch(url, { method: 'GET', headers, signal })
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
