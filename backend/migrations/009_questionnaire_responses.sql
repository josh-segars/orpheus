-- =====================================================================
-- HISTORICAL — DO NOT RUN AGAINST PROD OR ON TOP OF 001_base_schema.sql.
-- =====================================================================
-- This migration creates `public.questionnaire_responses` with a
-- different shape than the one already in prod:
--
--   This migration         vs.   Prod (in 001_base_schema.sql)
--   ------------------------     ----------------------------------
--   client_id PRIMARY KEY        id PK + client_id UNIQUE
--   answers jsonb                responses jsonb
--   section_completion jsonb     (absent)
--   created_at                   (absent)
--                                schema_version, completed_at
--
-- CREATE TABLE IF NOT EXISTS means this is a silent no-op against any
-- DB that already has 001 applied. The trigger / RLS policy creation
-- portions still attempt to run and may add a redundant
-- questionnaire_responses_set_updated_at trigger plus policies named
-- questionnaire_responses_(select|insert|update)_own that don't match
-- prod's `qr_*_as_(advisor|client)` design.
--
-- Migration 011_questionnaire_align_to_spec.sql is the correct path on
-- top of 001 — it reshapes the existing table to the spec shape rather
-- than trying to create it from scratch.
-- =====================================================================
--
-- Migration 009: public.questionnaire_responses table for ORPHEUS-18.
--
-- Stores per-client questionnaire answers (Q1–Q23 across 7 sections) plus
-- per-section completion flags. One row per client; the row is created on
-- first save by the React app via upsert. The narrative-generation worker
-- reads from this table when assembling the prompt context.
--
-- Shape decisions:
--
--   - `answers jsonb` is a flat key/value map. Keys are 'q1'..'q23' plus
--     '<qN>_other' for the two radio-with-other questions (q5, q22). Values
--     are strings, string[] (q12), or numbers (q16). The discriminator is
--     question id, not a tagged union — keeps reads/writes trivial in the
--     React form code and the Python prompt assembly.
--
--   - `section_completion jsonb` is { s1: bool, ... s7: bool }. Drives the
--     Groundwork checklist's per-section badges and the "My Groundwork is
--     Complete" CTA's enable state.
--
--   - One row per client (not per section, not per question). Keeps autosave
--     to a single upsert and avoids a join in the worker prompt assembly.
--     If we ever want answer history, we can add a `questionnaire_response_history`
--     audit table without changing this shape.
--
-- RLS: enabled in this same migration. Policies key on auth.uid() and grant
-- read/write only on the client's own row, mirroring migration 008. The
-- worker continues to read via service-role (RLS-bypassing) when generating
-- narratives.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS, DROP POLICY IF EXISTS before
-- CREATE, DROP TRIGGER IF EXISTS before CREATE.

BEGIN;

-- ---------------------------------------------------------------------------
-- public.questionnaire_responses
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.questionnaire_responses (
    client_id          uuid         PRIMARY KEY REFERENCES public.clients(id) ON DELETE CASCADE,
    answers            jsonb        NOT NULL DEFAULT '{}'::jsonb,
    section_completion jsonb        NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz  NOT NULL DEFAULT now(),
    updated_at         timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.questionnaire_responses                    IS 'Per-client questionnaire draft + completion. One row per client; upserted on save.';
COMMENT ON COLUMN public.questionnaire_responses.answers            IS 'Flat map: { q1: string, ..., q12: string[], q16: number, q5_other: string, q22_other: string }.';
COMMENT ON COLUMN public.questionnaire_responses.section_completion IS 'Flags driving the Groundwork checklist: { s1: bool, ..., s7: bool }. Set when the client clicks "This Section is Complete".';

-- updated_at auto-touch on UPDATE (mirrors the pattern in migration 007).
CREATE OR REPLACE FUNCTION public.questionnaire_responses_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS questionnaire_responses_set_updated_at ON public.questionnaire_responses;
CREATE TRIGGER questionnaire_responses_set_updated_at
    BEFORE UPDATE ON public.questionnaire_responses
    FOR EACH ROW
    EXECUTE FUNCTION public.questionnaire_responses_set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
--
-- Mirrors migration 008's pattern: SELECT/INSERT/UPDATE policies keyed on
-- auth.uid(). DELETE is intentionally not granted — clients keep their
-- answers as long as their account exists; account deletion cascades via
-- the FK on clients(id).
-- ---------------------------------------------------------------------------

ALTER TABLE public.questionnaire_responses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS questionnaire_responses_select_own ON public.questionnaire_responses;
CREATE POLICY questionnaire_responses_select_own
    ON public.questionnaire_responses
    FOR SELECT
    TO authenticated
    USING (client_id = auth.uid());

DROP POLICY IF EXISTS questionnaire_responses_insert_own ON public.questionnaire_responses;
CREATE POLICY questionnaire_responses_insert_own
    ON public.questionnaire_responses
    FOR INSERT
    TO authenticated
    WITH CHECK (client_id = auth.uid());

DROP POLICY IF EXISTS questionnaire_responses_update_own ON public.questionnaire_responses;
CREATE POLICY questionnaire_responses_update_own
    ON public.questionnaire_responses
    FOR UPDATE
    TO authenticated
    USING (client_id = auth.uid())
    WITH CHECK (client_id = auth.uid());

COMMIT;
