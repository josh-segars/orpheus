-- Migration 004: Rename narratives.dimension → section
-- In v2, narratives can be keyed to a dimension name OR "forward_brief"
-- Applied to Supabase 2026-04-08

ALTER TABLE public.narratives
RENAME COLUMN dimension TO section;

COMMENT ON TABLE public.narratives IS 'AI-generated narratives per section. Section is a dimension name or "forward_brief". Advisory flow uses draft→published; self-serve auto-publishes.';
COMMENT ON COLUMN public.narratives.section IS 'Section identifier: dimension name (e.g. "Profile Signal Clarity") or "forward_brief"';
