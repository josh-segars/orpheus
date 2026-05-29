-- Migration 013: Rename Signal Score bands to tuner metaphor
-- Maps:
--   Weak        -> Dissonant
--   Emerging    -> Untuned
--   Moderate    -> Tuning
--   Strong      -> Tuned
--   Exceptional -> Resonant
--
-- Pure relabel. Numeric composite thresholds (0-24, 25-44, 45-64, 65-79,
-- 80-100) are unchanged. Underlying scoring math is unchanged.
--
-- Per ORPHEUS-49. See Decision Log canon entry 2026-05-29.
--
-- Run against Supabase: Dashboard -> SQL Editor -> paste and run
-- Or via Supabase CLI: supabase db push

BEGIN;

-- Drop the existing band CHECK constraint. The constraint is named
-- `scores_band_check` (from migration 003); Postgres also auto-names the
-- inline CHECK from migration 001's CREATE TABLE the same way, so the
-- DROP IF EXISTS handles both fresh-from-001 and prod-via-003 environments.
ALTER TABLE public.scores DROP CONSTRAINT IF EXISTS scores_band_check;

-- Migrate any existing band values to the new labels. Safe to run on an
-- empty table; the WHERE band IS NOT NULL guard preserves NULLs.
UPDATE public.scores
SET band = CASE band
    WHEN 'Weak'        THEN 'Dissonant'
    WHEN 'Emerging'    THEN 'Untuned'
    WHEN 'Moderate'    THEN 'Tuning'
    WHEN 'Strong'      THEN 'Tuned'
    WHEN 'Exceptional' THEN 'Resonant'
    ELSE band  -- leave already-renamed rows alone (idempotency)
END
WHERE band IS NOT NULL;

-- Re-add the CHECK constraint with the tuner-metaphor labels.
ALTER TABLE public.scores
ADD CONSTRAINT scores_band_check
CHECK (band IS NULL OR band IN ('Dissonant', 'Untuned', 'Tuning', 'Tuned', 'Resonant'));

-- Update the column comment to reflect the new labels.
COMMENT ON COLUMN public.scores.band IS 'Client-facing signal strength band (tuner metaphor): Dissonant/Untuned/Tuning/Tuned/Resonant';

COMMIT;
