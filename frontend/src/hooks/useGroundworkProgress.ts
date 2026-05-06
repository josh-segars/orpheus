import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'

/**
 * Per-item completion state for the Groundwork checklist. The shape mirrors
 * the prototype's checklist sections (LinkedIn data + 7 questionnaire
 * sections). The hook returns booleans for each item plus a derived
 * `allComplete` flag that drives the "My Groundwork is Complete" CTA.
 *
 * Currently this reads only the most recent `jobs` row for the signed-in
 * client. Per-item flags for the questionnaire sections and the LinkedIn
 * upload steps will be filled in by ORPHEUS-18 (questionnaire_responses
 * table) and ORPHEUS-16 (jobs.uploaded_zip / uploaded_xlsx). Until then,
 * everything except the "any work in progress" signal returns `false` so
 * the page renders the empty checklist faithfully.
 */
export interface GroundworkProgress {
  // LinkedIn data uploads — wired in ORPHEUS-16.
  linkedInArchive: boolean
  linkedInAnalytics: boolean
  // Questionnaire — wired in ORPHEUS-18 against questionnaire_responses.
  questionnaireS1: boolean
  questionnaireS2: boolean
  questionnaireS3: boolean
  questionnaireS4: boolean
  questionnaireS5: boolean
  questionnaireS6: boolean
  questionnaireS7: boolean
  // Derived: every item above true → enable "My Groundwork is Complete".
  allComplete: boolean
  // Latest in-flight job, if any. Set when an upload has been submitted —
  // index/Groundwork redirect logic uses it to send the client to the
  // Analysis-in-Progress screen instead of looping back to Groundwork.
  latestPendingJobId: string | null
  latestCompleteJobId: string | null
}

const EMPTY: GroundworkProgress = {
  linkedInArchive: false,
  linkedInAnalytics: false,
  questionnaireS1: false,
  questionnaireS2: false,
  questionnaireS3: false,
  questionnaireS4: false,
  questionnaireS5: false,
  questionnaireS6: false,
  questionnaireS7: false,
  allComplete: false,
  latestPendingJobId: null,
  latestCompleteJobId: null,
}

interface JobRow {
  id: string
  status: 'pending' | 'running' | 'complete' | 'failed'
  created_at: string
}

/**
 * Subscribe to the client's groundwork completion state. Backed by a
 * lightweight Supabase read — RLS scopes the query to the signed-in
 * client's own rows automatically. React Query caches across consumers so
 * the same data is shared between the index redirect and the Groundwork
 * checklist without duplicate network calls.
 */
export function useGroundworkProgress() {
  return useQuery<GroundworkProgress>({
    queryKey: ['groundwork-progress'],
    queryFn: async () => {
      // RLS filters to the current client's rows (migration 008). We only
      // need the most recent job to know whether anything is in flight or
      // already complete.
      const { data, error } = await supabase
        .from('jobs')
        .select('id,status,created_at')
        .order('created_at', { ascending: false })
        .limit(1)

      if (error) throw error

      const latest = (data?.[0] as JobRow | undefined) ?? null
      const latestPendingJobId =
        latest && (latest.status === 'pending' || latest.status === 'running')
          ? latest.id
          : null
      const latestCompleteJobId =
        latest && latest.status === 'complete' ? latest.id : null

      return {
        ...EMPTY,
        latestPendingJobId,
        latestCompleteJobId,
      }
    },
    // Cheap query, but cache for a few seconds so navigating between
    // Welcome/Groundwork doesn't refetch on every transition.
    staleTime: 5_000,
  })
}
