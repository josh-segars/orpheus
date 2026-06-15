import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiPostMultipart } from '../lib/apiClient'
import { supabase } from '../lib/supabase'
import type { Job } from '../types/job'

interface CreateJobArgs {
  archive: File
  analytics: File
}

/**
 * Submit the LinkedIn ZIP + XLSX to POST /jobs and return the freshly-
 * created pending Job. The Groundwork page calls this when the client
 * clicks "My Groundwork is Complete" — on success it navigates to the
 * Analysis-in-Progress screen, which polls GET /jobs/{id}.
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
      const form = new FormData()
      form.append('archive', archive, archive.name)
      form.append('analytics', analytics, analytics.name)

      const { data } = await supabase.auth.getUser()
      const meta = data.user?.user_metadata
      const hasProfilePhoto = Boolean(meta?.picture ?? meta?.avatar_url)
      form.append('has_profile_photo', String(hasProfilePhoto))

      return apiPostMultipart<Job>('/jobs', form)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groundwork-progress'] })
    },
  })
}
