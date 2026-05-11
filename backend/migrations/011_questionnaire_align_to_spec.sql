-- Migration 011: align public.questionnaire_responses to ORPHEUS-33 spec.
-- Refs ORPHEUS-33, ORPHEUS-35.
--
-- =====================================================================
-- WHAT THIS DOES
-- =====================================================================
--
-- Reshapes the questionnaire_responses table to match the shape the
-- frontend (useQuestionnaire) and backend (worker, narrative agent)
-- already expect:
--
--   - Rename `responses` → `answers`
--   - Drop the surrogate `id` PK; promote `client_id` to PRIMARY KEY
--   - Drop the legacy `schema_version` and `completed_at` columns
--     (completion is derived at read time from `answers` content per
--     ORPHEUS-33 locked decision #5)
--   - TRUNCATE first — the old `responses` JSONB shape (23-question,
--     7-section) is incompatible with the new 9-question intake shape
--     (Spec_Simplified_Intake_Questionnaire_2026-05-11.md)
--
-- The supporting `qr_*_as_advisor` / `qr_*_as_client` RLS policies key
-- on `client_id`, not on `responses` / `id` / `schema_version` /
-- `completed_at`, so they survive this migration unchanged.
--
-- =====================================================================
-- ASSUMED STARTING STATE
-- =====================================================================
--
-- This migration is written to run on top of 001_base_schema.sql (which
-- snapshots prod's legacy schema). It is defensive against being run on
-- a DB that already happens to have the post-spec shape — every
-- structural change is guarded so a re-run is a no-op.
--
-- It is NOT designed to compose with migrations 009 / 010 in this repo
-- (those target a different starting shape and won't run cleanly on top
-- of 001 anyway — see the header comments on 007–010 for the broader
-- drift story).
--
-- =====================================================================
-- DATA WIPE
-- =====================================================================
--
-- Pre-launch, no real client answers exist. Andrew's pressure-test row
-- has the legacy `responses` JSONB shape (q1..q23 across 7 sections),
-- which the new narrative prompt + frontend can't read. Wiping is
-- consistent with the ORPHEUS-33 spec's "Pre-launch, no prod data to
-- preserve" posture.
--
-- If real client data ever exists when this kind of migration ships,
-- the TRUNCATE step must be replaced with a real shape translation
-- (read each row, project old keys onto new keys where they map).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Wipe (legacy shape is incompatible with new shape).
-- ---------------------------------------------------------------------------

TRUNCATE TABLE public.questionnaire_responses;

-- ---------------------------------------------------------------------------
-- 2. Drop columns the new design doesn't use. Guarded with IF EXISTS so
--    a re-run on an already-aligned schema is a no-op.
-- ---------------------------------------------------------------------------

ALTER TABLE public.questionnaire_responses
    DROP COLUMN IF EXISTS schema_version,
    DROP COLUMN IF EXISTS completed_at;

-- ---------------------------------------------------------------------------
-- 3. Rename `responses` → `answers`. ALTER TABLE ... RENAME COLUMN has
--    no IF EXISTS clause even in PG 17, so detect first.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'questionnaire_responses'
          AND column_name  = 'responses'
    ) THEN
        ALTER TABLE public.questionnaire_responses
            RENAME COLUMN responses TO answers;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 4. Promote client_id to PRIMARY KEY; drop the surrogate `id`.
--
--    Current state (prod / post-001):
--        PK = (id), UNIQUE (client_id), id default gen_random_uuid()
--    Target state (ORPHEUS-33 spec):
--        PK = (client_id), no `id` column
--
--    The DO block here detects which world we're in and only touches
--    what needs touching.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    has_id_column boolean;
    pk_columns    text;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'questionnaire_responses'
          AND column_name  = 'id'
    )
    INTO has_id_column;

    SELECT string_agg(a.attname, ',' ORDER BY array_position(c.conkey, a.attnum))
    FROM pg_constraint c
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
    WHERE c.conrelid = 'public.questionnaire_responses'::regclass
      AND c.contype = 'p'
    INTO pk_columns;

    -- If we're already on (client_id) PK and `id` is gone, nothing to do.
    IF pk_columns = 'client_id' AND NOT has_id_column THEN
        RETURN;
    END IF;

    -- Drop existing PK if it's not already on client_id.
    IF pk_columns IS NOT NULL AND pk_columns <> 'client_id' THEN
        ALTER TABLE public.questionnaire_responses
            DROP CONSTRAINT questionnaire_responses_pkey;
    END IF;

    -- The UNIQUE on client_id is a separate constraint — drop it so we
    -- can promote client_id to PK without a redundant unique index.
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.questionnaire_responses'::regclass
          AND conname  = 'questionnaire_responses_client_id_key'
    ) THEN
        ALTER TABLE public.questionnaire_responses
            DROP CONSTRAINT questionnaire_responses_client_id_key;
    END IF;

    -- Drop the surrogate `id` column if still present.
    IF has_id_column THEN
        ALTER TABLE public.questionnaire_responses
            DROP COLUMN id;
    END IF;

    -- Promote client_id to PK (idempotent — only runs if PK isn't already
    -- (client_id), which we covered above).
    ALTER TABLE public.questionnaire_responses
        ADD CONSTRAINT questionnaire_responses_pkey PRIMARY KEY (client_id);
END $$;

-- ---------------------------------------------------------------------------
-- 5. Refresh table + column comments so docs match the new shape.
-- ---------------------------------------------------------------------------

COMMENT ON TABLE public.questionnaire_responses IS
    'Per-client questionnaire answers for the 9-question intake (ORPHEUS-33). One row per client; upserted on save. Completion is derived from answers content, not persisted.';

COMMENT ON COLUMN public.questionnaire_responses.answers IS
    'Flat map matching frontend QuestionnaireAnswers: { q1: string[], q1_other: string, q2: string[], q2_other: string, q3..q4: string, q3_other / q4_other: string, q5..q9: string }. See Spec_Simplified_Intake_Questionnaire_2026-05-11.md for canonical option strings.';

COMMIT;
