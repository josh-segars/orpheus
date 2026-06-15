-- 015_jobs_oidc_photo.sql  (ORPHEUS-89)
--
-- Source the Forward Brief profile-photo presence signal from the client's
-- LinkedIn OIDC `picture` claim instead of (only) the ZIP rich-media
-- heuristic. The boolean is captured in the client's own session at
-- submission time (POST /jobs) and persisted here; the picture URL itself
-- is never stored.
--
-- NULL means "no OIDC signal captured" — the scoring engine falls back to
-- the rich-media heuristic (any "profile photo" event in Rich_Media.csv).
-- This covers older jobs and any future advisor-run path where the client's
-- own session isn't the submitter. When non-NULL, the OIDC value wins.
--
-- The worker picks this up for free: claim_next_job (migration 006) returns
-- SETOF public.jobs via SELECT *, so the new column flows into the claimed
-- job dict without an RPC change.

ALTER TABLE public.jobs
    ADD COLUMN IF NOT EXISTS oidc_photo_present boolean;

COMMENT ON COLUMN public.jobs.oidc_photo_present IS
    'Profile-photo presence from the client''s LinkedIn OIDC picture claim, captured at submission. NULL = no OIDC signal; scoring falls back to the ZIP rich-media heuristic. When non-NULL, OIDC wins.';
