/**
 * useCreateJob — ORPHEUS-108 browser-direct upload flow.
 *
 * The hook no longer POSTs a multipart body through the backend (large
 * archives died mid-transfer at the Railway edge). It must instead:
 *   1. mint signed Storage upload targets via POST /jobs/upload-urls,
 *   2. upload both files browser → Supabase Storage,
 *   3. submit POST /jobs/from-uploads with the upload_id + the original
 *      archive filename (which feeds the ORPHEUS-101 filename gate).
 *
 * apiClient is partially mocked (apiPostJson only) so the real
 * NetworkError class flows through for instanceof checks — the same
 * class GroundworkPage branches on for its connection guidance.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NetworkError } from '../../lib/apiClient'
import { useCreateJob } from '../useCreateJob'

const apiPostJson = vi.hoisted(() => vi.fn())
const uploadToSignedUrl = vi.hoisted(() => vi.fn())

vi.mock('../../lib/apiClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/apiClient')>()
  return { ...actual, apiPostJson }
})

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getUser: vi.fn().mockResolvedValue({
        data: { user: { user_metadata: { picture: 'https://p.example/x' } } },
      }),
    },
    storage: {
      from: vi.fn(() => ({ uploadToSignedUrl })),
    },
  },
}))

const TARGETS = {
  upload_id: '22222222-2222-2222-2222-222222222222',
  archive: { path: 'c1/staging/u1/archive.zip', token: 'tok-a' },
  analytics: { path: 'c1/staging/u1/analytics.xlsx', token: 'tok-x' },
}

const JOB = { id: 'job-1', state: 'pending' }

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

function files() {
  return {
    archive: new File(['zip-bytes'], 'Complete_LinkedInDataExport_07-14-2026.zip'),
    analytics: new File(['xlsx-bytes'], 'Content_2026.xlsx'),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useCreateJob (ORPHEUS-108 direct upload)', () => {
  it('mints upload URLs, uploads both files to Storage, then submits from-uploads', async () => {
    apiPostJson
      .mockResolvedValueOnce(TARGETS) // POST /jobs/upload-urls
      .mockResolvedValueOnce(JOB) // POST /jobs/from-uploads
    uploadToSignedUrl.mockResolvedValue({ data: {}, error: null })

    const { result } = renderHook(() => useCreateJob(), { wrapper })
    result.current.mutate(files())

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiPostJson).toHaveBeenNthCalledWith(1, '/jobs/upload-urls', {})
    // Both files went browser → Storage with the minted path + token.
    expect(uploadToSignedUrl).toHaveBeenCalledTimes(2)
    expect(uploadToSignedUrl).toHaveBeenCalledWith(
      TARGETS.archive.path,
      TARGETS.archive.token,
      expect.any(File),
      expect.objectContaining({ contentType: 'application/zip' }),
    )
    // The submit carries the upload_id, the ORIGINAL archive filename
    // (staged objects are always archive.zip), and the OIDC photo flag.
    expect(apiPostJson).toHaveBeenNthCalledWith(2, '/jobs/from-uploads', {
      upload_id: TARGETS.upload_id,
      archive_filename: 'Complete_LinkedInDataExport_07-14-2026.zip',
      has_profile_photo: true,
    })
    expect(result.current.data).toEqual(JOB)
  })

  it('surfaces a failed Storage upload as a NetworkError and never submits', async () => {
    apiPostJson.mockResolvedValueOnce(TARGETS)
    uploadToSignedUrl
      .mockResolvedValueOnce({ data: null, error: { message: 'dropped' } })
      .mockResolvedValueOnce({ data: {}, error: null })

    const { result } = renderHook(() => useCreateJob(), { wrapper })
    result.current.mutate(files())

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toBeInstanceOf(NetworkError)
    // POST /jobs/from-uploads was never called — only the upload-urls mint.
    expect(apiPostJson).toHaveBeenCalledTimes(1)
  })
})
