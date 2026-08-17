-- 023_jobs_prose_gate_degraded.sql  (ORPHEUS-131)
--
-- Marker for a report the prose-number gate (ORPHEUS-121) let through with
-- violations still standing.
--
-- Before this, the gate was all-or-nothing: `block` mode raised on every
-- attempt that quoted an unwhitelisted figure, and because
-- `generate_narratives` retries up to 3 times INSIDE a worker loop that
-- itself retries the pipeline up to 3 times, a persistently-rejecting
-- generation burned up to nine 8192-token calls and could land the job
-- `failed` on prose alone — client data entirely fine. Job b03ca0f5
-- (2026-08-13) spent two of its three worker attempts this way and took six
-- minutes against a normal one.
--
-- ORPHEUS-131 degrades instead of failing: the gate still rejects and retries
-- the non-final attempts (where it does nearly all of its work), and the final
-- attempt serves the narrative with the violation logged and recorded here.
-- The `log` kill-switch mode records the same way — it is a global override,
-- so without a per-job marker every report served during an incident would
-- hide its unverified figures.
--
-- Two columns, matching the ORPHEUS-88 `data_limited` shape (cheap boolean for
-- list/roster chips) but with the detail alongside it rather than in a JSONB:
-- there is no per-job prose-gate document to read the violations back out of,
-- and "which figure is unverified" is the only question an admin will ask on
-- seeing the chip.
--
--   prose_gate_degraded    — boolean chip source for /admin/jobs.
--   prose_gate_violations  — describe_violations() summary, e.g.
--                            "section:Behavioral Signal Strength: '2,394';
--                             cheat_sheet.priorities[0]: '318'".
--
-- Written by the worker on every completion (run_pipeline, alongside
-- data_limited), unconditionally rather than only-when-true, so an
-- ORPHEUS-81 re-run that comes back clean clears a previous degradation
-- instead of leaving a stale flag.
--
-- Defaults to false / NULL. NO BACK-FILL: the gate shipped 2026-08-14
-- (ORPHEUS-121) and nothing recorded which historical reports would have
-- tripped it. Re-deriving it would mean re-running the gate against stored
-- narratives, which is a real analysis, not a migration — and every
-- pre-gate report predates the whitelist it would be judged against. Same
-- posture as 016 and ORPHEUS-97: untrustworthy history stays at the default.
--
-- claim_next_job (migration 006) returns SELECT *, so both columns flow into
-- the claimed job dict harmlessly.

ALTER TABLE public.jobs
    ADD COLUMN IF NOT EXISTS prose_gate_degraded boolean NOT NULL DEFAULT false;

ALTER TABLE public.jobs
    ADD COLUMN IF NOT EXISTS prose_gate_violations text;

COMMENT ON COLUMN public.jobs.prose_gate_degraded IS
    'ORPHEUS-131: true when this report''s narrative was served with prose-number-gate violations still standing — the final block-mode generation attempt degraded rather than failing the job, or PROSE_NUMBER_GATE was in log mode. Set by the worker at completion; cleared by a clean re-run. No back-fill (the gate postdates every earlier report).';

COMMENT ON COLUMN public.jobs.prose_gate_violations IS
    'ORPHEUS-131: describe_violations() summary of the unwhitelisted figures served in this report (where: token pairs). NULL when prose_gate_degraded is false. The review surface for /admin — an admin can fix the figure via narratives.edited_text.';
