-- Migration 005: Add quality_report JSONB column to ingested_data
-- Stores structured data quality findings from the ingestion stage.
-- Advisors see this report; narrative generation uses it to acknowledge
-- data limitations in the Forward Brief.
-- Applied to Supabase: pending

ALTER TABLE public.ingested_data
ADD COLUMN quality_report jsonb;

COMMENT ON COLUMN public.ingested_data.quality_report IS 'Structured data quality report (DataQualityReport model). Contains severity-tagged issues, file inventory, row counts, and date range from ingestion.';
