import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { SectionCompletion } from '../types/questionnaire'

/**
 * Per-item completion state for the Groundwork checklist. The shape mirrors
 * the prototype's checklist sections (LinkedIn data + 7 questionnaire
 * sections). The hook returns booleans for each item plus a derived
 * `allComplete` flag that drives the "My Groundwork is Complete" CTA.
 *
 * Sources:
 *   - Questionnaire flags come from `questionnaire_responses.section_completion`
 *     (migration 009, populated by ORPHEUS-18's section pages).
 *   - LinkedIn upload flags come from the most recent `jobs` row's
 *     uploaded_zip / uploaded_xlsx columns (wired in ORPHEUS-16). Until
 *     that ships, both flags read `false`.
 *   - latestPendingJobId / latestCompleteJobId surface the most recent job,
 *     used by the smart index redirect in App.tsx.
 */
export interface GroundworkProgress {
  // LinkedIn data uploads — wired in ORPHEUS-16.
  linkedInArchive: boolean
  linkedInAnalytics: boolean
  // Questionnaire — driven by questionnaire_responses.section_completion.
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

interface JobRow {
  id: string
  status: 'pending' | 'running' | 'complete' | 'failed'
  created_at: string
}

interface QuestionnaireRow {
  section_completion: SectionCompletion | null
}

/**
 * Subscribe to the client's groundwork completion state. Backed by two
 * lightweight Supabase reads (jobs + questionnaire_responses) — RLS scopes
 * each to the signed-in client. React Query caches across consumers so the
 * same data is shared between the index redirect and the Groundwork
 * checklist without duplicate network calls.
 */
export function useGroundworkProgress() {
  return useQuery<GroundworkProgress>({
    queryKey: ['groundwork-progress'],
    queryFn: async () => {
      // Fire both reads in parallel — they're independent. RLS filters each
      // to the current client's rows, so we don't need a `.eq('client_id',...)`
      // filter; auth.uid() does it at the row level.
      //
      // We use allSettled so a failure on the questionnaire side (e.g.
      // migration 009 hasn't been applied yet on this database) doesn't
      // bring down the Groundwork page or smart-index redirect. A failed
      // questionnaire read is treated as "no completion flags".
      const [jobsResult, questionnaireResult] = await Promise.allSettled([
        supabase
          .from('jobs')
          .select('id,status,created_at')
          .order('created_at', { ascending: false })
          .limit(1),
        supabase
          .from('questionnaire_responses')
          .select('section_completion')
          .limit(1)
          .maybeSingle(),
      ])

      // Jobs is the more critical read — it drives the smart redirect. Bail
      // hard on errors here so the caller can show its error state.
      if (jobsResult.status === 'rejected') throw jobsResult.reason
      if (jobsResult.value.error) throw jobsResult.value.error

      const latest = (jobsResult.value.data?.[0] as JobRow | undefined) ?? null
      const latestPendingJobId =
        latest && (latest.status === 'pending' || latest.status === 'running')
          ? latest.id
          : null
      const latestCompleteJobId =
        latest && latest.status === 'complete' ? latest.id : null

      // Treat a missing/erroring questionnaire row as "no flags set". This
      // lets the Groundwork page render meaningfully even before the
      // migration ships and before the client has saved anything.
      const sections: SectionCompletion =
        questionnaireResult.status === 'fulfilled' &&
        !questionnaireResult.value.error
          ? ((questionnaireResult.value.data as QuestionnaireRow | null)
              ?.section_completion ?? {})
          : {}

      const questionnaireS1 = sections.s1 === true
      const questionnaireS2 = sections.s2 === true
      const questionnaireS3 = sections.s3 === true
      const questionnaireS4 = sections.s4 === true
      const questionnaireS5 = sections.s5 === true
      const questionnaireS6 = sections.s6 === true
      const questionnaireS7 = sections.s7 === true

      // LinkedIn upload flags are tracked client-side in
      // LinkedInUploadContext (in-memory File objects) rather than on the
      // server, so this hook can't determine them. GroundworkPage
      // overrides these locally before computing `allComplete`. We
      // surface `false` here so any other consumer treats LinkedIn items
      // as incomplete by default.
      const linkedInArchive = false
      const linkedInAnalytics = false

      // The hook-level `allComplete` matches the conservative read: it's
      // only true when every signal we can see server-side is true.
      // GroundworkPage recomputes this against the in-memory upload state
      // before enabling the submit CTA.
      const allComplete =
        linkedInArchive &&
        linkedInAnalytics &&
        questionnaireS1 &&
        questionnaireS2 &&
        questionnaireS3 &&
        questionnaireS4 &&
        questionnaireS5 &&
        questionnaireS6 &&
        questionnaireS7

      return {
        linkedInArchive,
        linkedInAnalytics,
        questionnaireS1,
        questionnaireS2,
        questionnaireS3,
        questionnaireS4,
        questionnaireS5,
        questionnaireS6,
        questionnaireS7,
        allComplete,
        latestPendingJobId,
        latestCompleteJobId,
      }
    },
    // Cheap query, but cache for a few seconds so navigating between
    // Welcome/Groundwork doesn't refetch on every transition.
    staleTime: 5_000,
  })
}
