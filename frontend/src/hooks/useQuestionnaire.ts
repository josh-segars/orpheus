import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { supabase } from '../lib/supabase'
import { useSessionRoles } from './useSessionRoles'
import type {
  QuestionnaireAnswers,
  QuestionnaireResponse,
} from '../types/questionnaire'

const QUERY_KEY = ['questionnaire-response'] as const

const EMPTY: QuestionnaireResponse = {
  client_id: '',
  answers: {},
  // The `as` casts let us share an immutable empty object across consumers
  // without having to fabricate timestamps the UI never reads.
  created_at: '',
  updated_at: '',
}

/**
 * Read the current client's questionnaire response row from Supabase.
 *
 * RLS scopes the SELECT to the signed-in client's own row (migration 009 +
 * 010). Returns the EMPTY shape if no row exists yet — the first save will
 * INSERT via the upsert path in `useUpsertQuestionnaire`.
 */
export function useQuestionnaireResponse() {
  return useQuery<QuestionnaireResponse>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const { data, error } = await supabase
        .from('questionnaire_responses')
        .select('*')
        .limit(1)
        .maybeSingle()

      if (error) throw error
      if (!data) return EMPTY
      return data as QuestionnaireResponse
    },
    staleTime: 5_000,
  })
}

interface UpsertArgs {
  /** New answers to merge into the existing answers map. */
  answers: QuestionnaireAnswers
}

/**
 * Upsert the current client's questionnaire response. We merge incoming
 * fields into the cached row before writing so partial saves don't blow
 * away unrelated answers.
 *
 * The caller passes only the fields that changed; this hook computes the
 * post-merge JSONB shape.
 *
 * client_id source (ORPHEUS-57): we need `clients.id`, NOT `auth.users.id`.
 * Those values diverged when ORPHEUS-36's schema split made the clients
 * table a separate identity linked to auth.users via `clients.user_id`.
 * The schema FKs `questionnaire_responses.client_id → clients(id)` and the
 * RLS policy `qr_insert_as_client` checks `client_id = get_client_id()`
 * (which returns `clients.id`). Writing `auth.users.id` here meant RLS
 * rejected the upsert silently — PostgREST returned empty data, the UI
 * saw "answers don't save," no error surfaced anywhere. Reading from
 * `useSessionRoles()` ensures we use the row id the backend gives us
 * via GET /session.
 */
export function useUpsertQuestionnaire() {
  const queryClient = useQueryClient()
  const sessionRolesQuery = useSessionRoles()
  const clientId = sessionRolesQuery.data?.client_id ?? null

  return useMutation({
    mutationFn: async ({ answers }: UpsertArgs) => {
      // Defensive guard: an advisor-only user reaching this code path
      // shouldn't be possible via the UI (the questionnaire route is
      // gated behind ProtectedRoute + a client portal nav), but if it
      // ever happens, fail loudly instead of writing a row that RLS
      // will reject silently.
      if (!clientId) {
        throw new Error(
          'Cannot save questionnaire: no client_id resolved for this session.',
        )
      }

      // Read-modify-write: merge into whatever's currently in the cache.
      // The cache is the source of truth between mutations because we
      // optimistically write back into it after each successful upsert.
      const current =
        queryClient.getQueryData<QuestionnaireResponse>(QUERY_KEY) ?? EMPTY

      const mergedAnswers: QuestionnaireAnswers = {
        ...current.answers,
        ...answers,
      }

      const { data, error } = await supabase
        .from('questionnaire_responses')
        .upsert(
          {
            client_id: clientId,
            answers: mergedAnswers,
          },
          { onConflict: 'client_id' },
        )
        .select('*')
        .single()

      if (error) throw error
      return data as QuestionnaireResponse
    },
    onSuccess: (row) => {
      queryClient.setQueryData<QuestionnaireResponse>(QUERY_KEY, row)
      // Groundwork progress derives questionnaireComplete from answers, so
      // any save invalidates that row's completion flag.
      queryClient.invalidateQueries({ queryKey: ['groundwork-progress'] })
    },
  })
}

/**
 * Working-copy state container with debounced autosave for the single-page
 * questionnaire (ORPHEUS-33).
 *
 * Components call this once at the top of `QuestionnairePage`, get back a
 * controlled `answers` object plus a setter, and don't have to think about
 * persistence — changes flush to Supabase 700ms after the last edit. A
 * manual `flush()` is exposed for the "Save My Answers" /
 * "This Section is Complete" buttons that need to wait until the write
 * lands before navigating.
 */
export function useQuestionnaireDraft() {
  const { data: row, isLoading } = useQuestionnaireResponse()
  const upsert = useUpsertQuestionnaire()

  // The form's working copy. Initialised from the latest server snapshot
  // and re-synced when the snapshot changes. We avoid clobbering the
  // user's in-flight edits by only re-initialising once.
  const [draft, setDraft] = useState<QuestionnaireAnswers>(row?.answers ?? {})
  const initialised = useRef(false)

  useEffect(() => {
    if (initialised.current) return
    if (row && row.answers) {
      setDraft(row.answers)
      initialised.current = true
    }
  }, [row])

  // Debounced autosave. We snapshot the latest pending payload in a ref so
  // the timeout always saves the freshest values, not a closed-over stale
  // copy.
  const pendingRef = useRef<QuestionnaireAnswers | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scheduleSave = (next: QuestionnaireAnswers) => {
    pendingRef.current = next
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      const payload = pendingRef.current
      pendingRef.current = null
      timerRef.current = null
      if (payload) {
        upsert.mutate({ answers: payload })
      }
    }, 700)
  }

  const updateAnswer = <K extends keyof QuestionnaireAnswers>(
    key: K,
    value: QuestionnaireAnswers[K],
  ) => {
    setDraft((prev) => {
      const next = { ...prev, [key]: value }
      scheduleSave(next)
      return next
    })
  }

  /**
   * Force any pending debounced save to flush immediately. Returns a
   * promise that resolves when the write completes — callers should await
   * before navigating away so the row reflects the final state.
   */
  const flush = async (): Promise<void> => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const answersPayload = pendingRef.current
    pendingRef.current = null

    if (!answersPayload) return

    await upsert.mutateAsync({ answers: answersPayload })
  }

  return {
    answers: draft,
    updateAnswer,
    flush,
    isLoading,
    isSaving: upsert.isPending,
    saveError: upsert.error,
  }
}
