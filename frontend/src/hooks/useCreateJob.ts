import { useMutation, useQueryClient } from '@tanstack/react-query'
import { NetworkError, UploadRejectedError, apiPostJson } from '../lib/apiClient'
import { supabase } from '../lib/supabase'
import type { Job } from '../types/job'

const ZIP_MIME = 'application/zip'
const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * Rebuild the picked File with a canonical MIME type before upload
 * (ORPHEUS-109). supabase-js `uploadToSignedUrl` sends the File itself
 * via multipart and Storage honors the browser/OS-reported type — the
 * `contentType` option does not apply on that path. Windows registers
 * `.zip` as `application/x-zip-compressed`, which 400'd against the
 * bucket allowlist (InvalidMimeType) for every Windows client.
 * Normalizing here makes OS MIME-registry quirks structurally
 * irrelevant. Name and lastModified are preserved — the ORPHEUS-101
 * filename gate reads `archive.name` downstream.
 */
function withCanonicalMime(file: File, type: string): File {
  if (file.type === type) return file
  return new File([file], file.name, { type, lastModified: file.lastModified })
}

/**
 * Classify a failed Storage upload (ORPHEUS-109). A Storage 4xx (MIME,
 * size cap, bad/expired token) is deterministic — retrying the identical
 * file cannot succeed — so it becomes an UploadRejectedError carrying the
 * service's own message. Anything without a numeric 4xx status (transport
 * death, 5xx) stays the ORPHEUS-86 NetworkError so GroundworkPage's
 * connection/large-archive guidance applies.
 */
function toUploadError(which: 'archive' | 'analytics', error: object): Error {
  const { status, message } = error as { status?: unknown; message?: unknown }
  if (typeof status === 'number' && status >= 400 && status < 500) {
    return new UploadRejectedError(
      `Your ${which} upload was rejected by storage.`,
      status,
      typeof message === 'string' && message ? message : 'no detail provided',
    )
  }
  return new NetworkError(`Your ${which} upload did not complete.`, error)
}

interface CreateJobArgs {
  archive: File
  analytics: File
}

interface UploadTarget {
  path: string
  token: string
}

interface CreateUploadUrlsResponse {
  upload_id: string
  archive: UploadTarget
  analytics: UploadTarget
}

/**
 * Submit the LinkedIn ZIP + XLSX and return the freshly-created pending
 * Job. The Groundwork page calls this when the client clicks "My
 * Groundwork is Complete" — on success it navigates to the
 * Analysis-in-Progress screen, which polls GET /jobs/{id}.
 *
 * ORPHEUS-108: the files no longer travel through the backend as a
 * multipart body — large archives were observed dying mid-transfer at the
 * Railway edge (the ORPHEUS-86 "Failed to fetch" symptom). Instead:
 *
 *   1. POST /jobs/upload-urls mints signed Supabase Storage upload URLs
 *      (and runs the concurrent-run guard before anything is transferred);
 *   2. both files upload browser → Storage directly, bypassing the
 *      Railway edge entirely;
 *   3. POST /jobs/from-uploads (small JSON body) runs the submission
 *      gates server-side against the staged bytes and mints the job.
 *
 * A failed direct upload surfaces as a NetworkError so GroundworkPage's
 * existing connection/large-archive guidance (ORPHEUS-86) applies —
 * unless Storage answered with a 4xx, which is deterministic and
 * surfaces as UploadRejectedError instead (ORPHEUS-109).
 *
 * On success we invalidate the groundwork-progress query so the smart
 * index redirect picks up the new pending job on the next render.
 *
 * We also capture whether the client's LinkedIn OIDC session carries a
 * profile picture (ORPHEUS-89). This is the one moment the OIDC claim is
 * available — in the client's own authenticated session — and it's a more
 * reliable photo-presence signal than the ZIP rich-media heuristic the
 * backend otherwise falls back to. Only the boolean is sent; the picture
 * URL is ephemeral and never persisted.
 */
export function useCreateJob() {
  const queryClient = useQueryClient()

  return useMutation<Job, Error, CreateJobArgs>({
    mutationFn: async ({ archive, analytics }) => {
      const targets = await apiPostJson<CreateUploadUrlsResponse>(
        '/jobs/upload-urls',
        {},
      )

      const bucket = supabase.storage.from('uploads')
      const [archiveResult, analyticsResult] = await Promise.all([
        bucket.uploadToSignedUrl(
          targets.archive.path,
          targets.archive.token,
          withCanonicalMime(archive, ZIP_MIME),
          { contentType: ZIP_MIME },
        ),
        bucket.uploadToSignedUrl(
          targets.analytics.path,
          targets.analytics.token,
          withCanonicalMime(analytics, XLSX_MIME),
          { contentType: XLSX_MIME },
        ),
      ])
      if (archiveResult.error) {
        throw toUploadError('archive', archiveResult.error)
      }
      if (analyticsResult.error) {
        throw toUploadError('analytics', analyticsResult.error)
      }

      const { data } = await supabase.auth.getUser()
      const meta = data.user?.user_metadata
      const hasProfilePhoto = Boolean(meta?.picture ?? meta?.avatar_url)

      return apiPostJson<Job>('/jobs/from-uploads', {
        upload_id: targets.upload_id,
        // The staged object is always named archive.zip; the original
        // browser filename carries the Basic/Complete flag + export date
        // for the ORPHEUS-101 filename gate.
        archive_filename: archive.name,
        has_profile_photo: hasProfilePhoto,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groundwork-progress'] })
    },
  })
}
