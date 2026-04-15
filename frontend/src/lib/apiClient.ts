/**
 * Thin fetch wrapper. In dev, MSW intercepts requests at the same origin,
 * so the base URL defaults to ''. In production we'll point at the
 * Railway-hosted FastAPI service via VITE_API_BASE_URL.
 */

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

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
  const res = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      // ignore
    }
    throw new ApiError(`GET ${path} failed: ${res.status}`, res.status, body)
  }
  return (await res.json()) as T
}
