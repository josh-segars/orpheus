import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import {
  isQuestionnaireComplete,
  type QuestionnaireAnswers,
} from '../types/questionnaire'

/**
 * Per-item completion state for the Groundwork checklist. After ORPHEUS-33
 * the checklist is three rows: the intake questionnaire and the two
 * LinkedIn data items. Questionnaire completion is derived at read time
 * from the answers JSONB (migration 010 dropped the persisted
 * section_completion column).
 *
 * Sources:
 *   - questionnaireComplete is `isQuestionnaireComplete(answers)` — all 9
 *     required keys populated, with non-empty qN_other text when the user
 *     selected Other on q1..q4.
 *   - LinkedIn upload flags come from the in-memory File state held in
 *     LinkedInUploadContext. This hook returns `false` for both; the
 *     Groundwork page overrides locally before computing the gate.
 *   - latestPendingJobId / latestCompleteJobId surface the most recent
 *     job, used by the smart index redirect in App.tsx.
 */
export interface GroundworkProgress {
  // LinkedIn data uploads — overridden locally by GroundworkPage from
  // LinkedInUploadContext (in-memory File state, lost on hard refresh).
  linkedInArchive: boolean
  linkedInAnalytics: boolean
  // Questionnaire — derived from questionnaire_responses.answers.
  questionnaireComplete: boolean
  // Derived: every item above true → enable "My Groundwork is Complete".
  allComplete: boolean
  // Latest in-flight job, if any.
  latestPendingJobId: string | null
  latestCompleteJobId: string | null
  // True when ANY job row exists regardless of status (ORPHEUS-81) —
  // drives the smart redirect to the reports list. Distinct from the
  // two ids above: a client whose latest job failed but who has older
  // complete reports must still land on the list.
  hasAnyJob: boolean
}

interface JobRow {
  id: string
  status: 'pending' | 'running' | 'complete' | 'failed'
  created_at: string
}

interface QuestionnaireRow {
  answers: QuestionnaireAnswers | null
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
      // Fire both reads in parallel — they're independent. RLS filters
      // each to the current client's rows, so we don't need an explicit
      // `.eq('client_id',...)` filter; auth.uid() does it at the row
      // level.
      //
      // allSettled keeps the page rendering when one read fails (e.g.
      // migrations 009/010 not yet applied on this database). A failed
      // questionnaire read is treated as "no answers".
      const [jobsResult, questionnaireResult] = await Promise.allSettled([
        supabase
          .from('jobs')
          .select('id,status,created_at')
          .order('created_at', { ascending: false })
          .limit(1),
        supabase
          .from('questionnaire_responses')
          .select('answers')
          .limit(1)
          .maybeSingle(),
      ])

      // Jobs is the more critical read — it drives the smart redirect.
      // Bail hard on errors here so the caller can show its error state.
      if (jobsResult.status === 'rejected') throw jobsResult.reason
      if (jobsResult.value.error) throw jobsResult.value.error

      const latest = (jobsResult.value.data?.[0] as JobRow | undefined) ?? null
      const hasAnyJob = latest !== null
      const latestPendingJobId =
        latest && (latest.status === 'pending' || latest.status === 'running')
          ? latest.id
          : null
      const latestCompleteJobId =
        latest && latest.status === 'complete' ? latest.id : null

      // Treat a missing/erroring questionnaire row as "no answers". This
      // lets Groundwork render before the client has saved anything.
      const answers: QuestionnaireAnswers =
        questionnaireResult.status === 'fulfilled' &&
        !questionnaireResult.value.error
          ? ((questionnaireResult.value.data as QuestionnaireRow | null)
              ?.answers ?? {})
          : {}

      const questionnaireComplete = isQuestionnaireComplete(answers)

      // LinkedIn upload flags are tracked client-side in
      // LinkedInUploadContext (in-memory File objects) rather than on the
      // server, so this hook can't determine them. GroundworkPage
      // overrides these locally before computing `allComplete`. We
      // surface `false` here so any other consumer treats LinkedIn items
      // as incomplete by default.
      const linkedInArchive = false
      const linkedInAnalytics = false

      // The hook-level `allComplete` matches the conservative read:
      // GroundworkPage recomputes against the in-memory upload state
      // before enabling the submit CTA.
      const allComplete =
        linkedInArchive && linkedInAnalytics && questionnaireComplete

      return {
        linkedInArchive,
        linkedInAnalytics,
        questionnaireComplete,
        allComplete,
        latestPendingJobId,
        latestCompleteJobId,
        hasAnyJob,
      }
    },
    staleTime: 5_000,
  })
}
