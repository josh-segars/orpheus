/**
 * apiClient transport-failure handling — ORPHEUS-86.
 *
 * safeFetch() normalizes a rejected fetch() (transport-level death —
 * connection dropped, DNS, CORS, upload body killed mid-transfer) into a
 * typed NetworkError so callers can branch on it and show actionable
 * guidance instead of the opaque "Failed to fetch". A deliberate
 * AbortController cancellation still surfaces as the original AbortError,
 * and a real non-2xx HTTP response still throws ApiError as before.
 */
import { apiDelete, apiGet, ApiError, NetworkError } from '../apiClient'

describe('apiClient transport failures (ORPHEUS-86)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('wraps a rejected fetch (TypeError) as NetworkError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    )
    await expect(apiGet('/session')).rejects.toBeInstanceOf(NetworkError)
  })

  it('passes an AbortError through unchanged (cancellation, not failure)', async () => {
    const abort = new DOMException('aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(apiGet('/session')).rejects.toBe(abort)
  })

  it('still throws ApiError on a non-2xx HTTP response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'forbidden' }),
      } as Response),
    )
    await expect(apiGet('/session')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('apiDelete (ORPHEUS-124)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('carries the response body through an ApiError on non-2xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: 'roster is non-empty' }),
      } as Response),
    )
    await expect(apiDelete('/account')).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      body: { detail: 'roster is non-empty' },
    })
  })

  it('returns undefined on a 204 and JSON otherwise', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 204 } as Response),
    )
    await expect(apiDelete('/account')).resolves.toBeUndefined()

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ deleted: true }),
      } as Response),
    )
    await expect(apiDelete('/account')).resolves.toEqual({ deleted: true })
  })
})
