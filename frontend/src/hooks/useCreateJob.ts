import { useMutation, useQueryClient } from '@tanstack/react-query'
import { NetworkError, apiPostJson } from '../lib/apiClient'
import { supabase } from '../lib/supabase'
import type { Job } from '../types/job'

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
 * existing connection/large-archive guidance (ORPHEUS-86) applies
 * unchanged.
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
          archive,
          { contentType: 'application/zip' },
        ),
        bucket.uploadToSignedUrl(
          targets.analytics.path,
          targets.analytics.token,
          analytics,
          {
            contentType:
              'application/vnd.openxmlformats-officedocument.' +
              'spreadsheetml.sheet',
          },
        ),
      ])
      if (archiveResult.error) {
        throw new NetworkError(
          'Your archive upload did not complete.',
          archiveResult.error,
        )
      }
      if (analyticsResult.error) {
        throw new NetworkError(
          'Your analytics upload did not complete.',
          analyticsResult.error,
        )
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
