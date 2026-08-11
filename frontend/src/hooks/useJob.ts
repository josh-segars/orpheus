import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/apiClient'
import type { Job } from '../types/job'

/**
 * Fetch a job by id. Auto-polls while the job is still pending/running
 * so the Analysis-in-Progress screen can transition to the Signal Score
 * screen without a manual refresh.
 *
 * ORPHEUS-120: also polls (gently) while a complete advisory job is in
 * review, so the client sees the report appear when the advisor releases
 * it — a publish is an admin action, not a worker race, so 15s is plenty.
 */
export function useJob(jobId: string | undefined) {
  return useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: ({ signal }) => apiGet<Job>(`/jobs/${jobId}`, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const job = query.state.data
      if (job?.state === 'pending' || job?.state === 'running') return 3_000
      if (job?.state === 'complete' && job.in_review) return 15_000
      return false
    },
  })
}
