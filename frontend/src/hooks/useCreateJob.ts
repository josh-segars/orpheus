import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiPostMultipart } from '../lib/apiClient'
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
 */
export function useCreateJob() {
  const queryClient = useQueryClient()

  return useMutation<Job, Error, CreateJobArgs>({
    mutationFn: async ({ archive, analytics }) => {
      const form = new FormData()
      form.append('archive', archive, archive.name)
      form.append('analytics', analytics, analytics.name)
      return apiPostMultipart<Job>('/jobs', form)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groundwork-progress'] })
    },
  })
}
