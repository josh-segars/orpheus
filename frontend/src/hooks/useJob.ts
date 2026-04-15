import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/apiClient'
import type { Job } from '../types/job'

/**
 * Fetch a job by id. Auto-polls while the job is still pending/running
 * so the Analysis-in-Progress screen can transition to the Signal Score
 * screen without a manual refresh.
 */
export function useJob(jobId: string | undefined) {
  return useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: ({ signal }) => apiGet<Job>(`/jobs/${jobId}`, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const state = query.state.data?.state
      return state === 'pending' || state === 'running' ? 3_000 : false
    },
  })
}
