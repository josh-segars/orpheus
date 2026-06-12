import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/apiClient'
import type { JobSummary } from '../types/job'

/**
 * Fetch the signed-in client's full jobs list (GET /jobs, ORPHEUS-81).
 * Backs the reports list page. Polls while any job is in flight so the
 * list row transitions from "In progress" to its band without a manual
 * refresh — same posture as useJob's per-job polling, at a gentler
 * cadence since the AnalysisPage owns the fast poll.
 */
export function useJobs() {
  return useQuery<JobSummary[]>({
    queryKey: ['jobs'],
    queryFn: ({ signal }) => apiGet<JobSummary[]>('/jobs', signal),
    refetchInterval: (query) => {
      const rows = query.state.data
      const hasInFlight = rows?.some(
        (j) => j.state === 'pending' || j.state === 'running',
      )
      return hasInFlight ? 5_000 : false
    },
  })
}
