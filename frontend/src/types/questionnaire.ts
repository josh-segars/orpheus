/**
 * Frontend types for the simplified 9-question intake questionnaire
 * (ORPHEUS-33). Mirrors the JSONB shape persisted in
 * public.questionnaire_responses after migration 010.
 *
 * Shape decisions (locked in
 * Spec_Simplified_Intake_Questionnaire_2026-05-11.md):
 *
 *   - Flat key/value map keyed by question id. Q1 and Q2 are multi-select
 *     (string arrays of canonical option labels in display order, not
 *     selection order). Q3..Q8 are single-select strings. Q9 is free text.
 *
 *   - The canonical option string "Other" appears in q1/q2 arrays and in
 *     q3/q4 values whenever the user picked Other. The free-text content
 *     lives in the parallel `qN_other` field. Q5..Q9 do not have Other.
 *
 *   - Q8's "All of the above" is stored as the literal string "All of the
 *     above" — narrative generation reasons about that explicit choice
 *     rather than fanning it back out into four constituents.
 *
 *   - All fields are optional here because the form persists drafts as
 *     answers accumulate. The completion check below derives a single
 *     `questionnaireComplete` boolean at read time — the spec removed the
 *     persisted section_completion column to make answers the single
 *     source of truth.
 */

/**
 * The canonical "Other" option label. Used wherever an answer needs to be
 * compared against the Other option (predicate, form rendering).
 */
export const OTHER_OPTION = 'Other'

/**
 * Draft answer shape. The form mutates this incrementally as the user
 * fills it in; everything is optional at this layer.
 */
export interface QuestionnaireAnswers {
  /** Q1 — current situation (multi-select with Other). */
  q1?: string[]
  q1_other?: string
  /** Q2 — actively pursuing (multi-select with Other). */
  q2?: string[]
  q2_other?: string
  /** Q3 — what's driving interest now (single-select with Other). */
  q3?: string
  q3_other?: string
  /** Q4 — current LinkedIn approach (single-select with Other). */
  q4?: string
  q4_other?: string
  /** Q5 — comfort with current presence (single-select, no Other). */
  q5?: string
  /** Q6 — familiarity with how LinkedIn works (single-select, no Other). */
  q6?: string
  /** Q7 — understanding of online-presence impact (single-select, no Other). */
  q7?: string
  /** Q8 — 12-month success picture (single-select, no Other; literal "All of the above" allowed). */
  q8?: string
  /** Q9 — anything else (free text, required, "Nothing to add" acceptable). */
  q9?: string
}

export interface QuestionnaireResponse {
  client_id: string
  answers: QuestionnaireAnswers
  created_at: string
  updated_at: string
}

/**
 * Read-time completion check. The questionnaire is complete iff:
 *
 *   - q1 and q2 each have ≥1 selection
 *   - q3..q8 are populated (non-empty strings)
 *   - q9 is non-empty after trim
 *   - When "Other" is selected on q1..q4, the corresponding qN_other text
 *     is non-empty after trim (the spec rejects "selected Other but typed
 *     nothing" as an incomplete answer)
 *
 * Returns a boolean. The Groundwork checklist's questionnaire row uses
 * this; no persisted flag is involved.
 */
export function isQuestionnaireComplete(answers: QuestionnaireAnswers): boolean {
  // Q1 — at least one selection; Other requires text.
  const q1 = answers.q1 ?? []
  if (q1.length === 0) return false
  if (q1.includes(OTHER_OPTION) && !(answers.q1_other ?? '').trim()) return false

  // Q2 — at least one selection; Other requires text.
  const q2 = answers.q2 ?? []
  if (q2.length === 0) return false
  if (q2.includes(OTHER_OPTION) && !(answers.q2_other ?? '').trim()) return false

  // Q3 — single value; Other requires text.
  const q3 = answers.q3 ?? ''
  if (!q3) return false
  if (q3 === OTHER_OPTION && !(answers.q3_other ?? '').trim()) return false

  // Q4 — single value; Other requires text.
  const q4 = answers.q4 ?? ''
  if (!q4) return false
  if (q4 === OTHER_OPTION && !(answers.q4_other ?? '').trim()) return false

  // Q5..Q8 — single value, no Other variants.
  if (!(answers.q5 ?? '')) return false
  if (!(answers.q6 ?? '')) return false
  if (!(answers.q7 ?? '')) return false
  if (!(answers.q8 ?? '')) return false

  // Q9 — free text, must be non-empty after trim. "Nothing to add" or
  // "N/A" both satisfy this.
  if (!(answers.q9 ?? '').trim()) return false

  return true
}
