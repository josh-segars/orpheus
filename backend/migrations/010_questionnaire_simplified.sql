-- Migration 010: simplified 9-question intake questionnaire (ORPHEUS-33).
--
-- Replaces the 23-question, 7-section questionnaire shipped under ORPHEUS-18
-- (migration 009) with a 9-question intake. See
-- Spec_Simplified_Intake_Questionnaire_2026-05-11.md for the full rationale
-- and the verbatim question text.
--
-- Two structural changes:
--
--   1. TRUNCATE public.questionnaire_responses
--      The new `answers` JSONB shape is incompatible with the old one
--      (different keys, different value types). Pre-launch there is no prod
--      data to preserve. If a future migration of this kind ships AFTER
--      real client answers exist, this step must be replaced with a real
--      shape-translation: read each row, project old keys onto new keys
--      where they map, and rewrite.
--
--   2. DROP COLUMN section_completion
--      Section-level completion no longer makes sense with a single-page
--      questionnaire. The frontend now derives a single
--      `questionnaireComplete` boolean at read time by checking that all 9
--      required keys are populated in `answers`. Single source of truth,
--      no persisted flag to keep in sync with the answer set.
--
-- RLS policies on public.questionnaire_responses remain unchanged — see
-- migration 009. The trigger that touches updated_at on UPDATE remains
-- unchanged. The `answers` column itself is preserved (same column, same
-- jsonb type, same NOT NULL DEFAULT '{}').
--
-- Idempotent: TRUNCATE is unconditional but harmless on an empty table;
-- DROP COLUMN uses IF EXISTS so re-running after section_completion is
-- already gone is a no-op. The COMMENT update is unconditional.

BEGIN;

-- Wipe pre-existing answers (incompatible shape).
TRUNCATE TABLE public.questionnaire_responses;

-- Drop the section_completion column — completion is now derived from
-- answers content (see frontend src/types/questionnaire.ts:isQuestionnaireComplete).
ALTER TABLE public.questionnaire_responses
    DROP COLUMN IF EXISTS section_completion;

-- Refresh the answers column comment so the documented shape matches the
-- new questionnaire. The old comment listed q1..q23 specifically.
COMMENT ON COLUMN public.questionnaire_responses.answers IS
    'Flat map matching frontend QuestionnaireAnswers: { q1: string[], q1_other: string, q2: string[], q2_other: string, q3..q4: string, q3_other / q4_other: string, q5..q9: string }. See Spec_Simplified_Intake_Questionnaire_2026-05-11.md for canonical option strings.';

-- Refresh the table comment to drop the stale section_completion mention.
COMMENT ON TABLE public.questionnaire_responses IS
    'Per-client questionnaire answers for the 9-question intake (ORPHEUS-33). One row per client; upserted on save. Completion is derived from answers content, not persisted.';

COMMIT;
