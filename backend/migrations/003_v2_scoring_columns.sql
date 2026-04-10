-- Migration 003: Add v2 scoring columns to scores table
-- Adds band (signal strength label) and forward_brief_data (JSONB)
-- Part of the v2 architecture transition (April 2026)
--
-- Run against Supabase: Dashboard → SQL Editor → paste and run
-- Or via Supabase CLI: supabase db push

-- Add band column for signal strength label
ALTER TABLE public.scores
ADD COLUMN IF NOT EXISTS band text;

-- Add forward_brief_data for Forward Brief structured output
ALTER TABLE public.scores
ADD COLUMN IF NOT EXISTS forward_brief_data jsonb;

-- Add check constraint for valid band values
ALTER TABLE public.scores
ADD CONSTRAINT scores_band_check
CHECK (band IS NULL OR band IN ('Weak', 'Emerging', 'Moderate', 'Strong', 'Exceptional'));

-- Comment for documentation
COMMENT ON COLUMN public.scores.band IS 'Client-facing signal strength band: Weak/Emerging/Moderate/Strong/Exceptional';
COMMENT ON COLUMN public.scores.forward_brief_data IS 'Structured data for Forward Brief: quantitative fields + qualitative flags (JSONB)';
