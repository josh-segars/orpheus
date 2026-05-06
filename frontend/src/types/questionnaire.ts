/**
 * Frontend types for the questionnaire — mirror the JSONB shape persisted
 * in public.questionnaire_responses (migration 009).
 *
 * The form deliberately uses a flat answer map (q1, q2, ..., q23 with
 * q5_other / q22_other for the two radio-with-other questions). Keeping the
 * shape flat lets the worker's prompt-assembly code in
 * backend/agents/narrative.py read each answer with a single key lookup
 * instead of walking a tagged union.
 */

export type SectionId = 's1' | 's2' | 's3' | 's4' | 's5' | 's6' | 's7'

export const SECTION_IDS: readonly SectionId[] = [
  's1',
  's2',
  's3',
  's4',
  's5',
  's6',
  's7',
] as const

/**
 * Per-question answer values. Each question id maps to one of three
 * primitives (string, string[], number). Optional because all answers are
 * draftable — clients can leave any field empty.
 */
export interface QuestionnaireAnswers {
  q1?: string
  q2?: string
  q3?: string
  q4?: string
  q5?: string
  q5_other?: string
  q6?: string
  q7?: string
  q8?: string
  q9?: string
  q10?: string
  q11?: string
  q12?: string[]
  q13?: string
  q14?: string
  q15?: string
  q16?: number
  q17?: string
  q18?: string
  q19?: string
  q20?: string
  q21?: string
  q22?: string
  q22_other?: string
  q23?: string
}

export type SectionCompletion = Partial<Record<SectionId, boolean>>

export interface QuestionnaireResponse {
  client_id: string
  answers: QuestionnaireAnswers
  section_completion: SectionCompletion
  created_at: string
  updated_at: string
}
