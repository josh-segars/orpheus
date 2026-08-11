-- 021: ORPHEUS-120 — one-time publish of pre-gate advisory reports.
--
-- Context: until ORPHEUS-120, GET /jobs/{id} never filtered narratives on
-- status, so every client on an advisory roster has been reading their
-- "draft" report since pipeline completion (13 clients, since 2026-06-16).
-- The read-path gate this migration accompanies would retroactively hide
-- those reports. Publishing them matches lived reality: nothing changes
-- for anyone, and the gate applies cleanly to all future advisory jobs.
--
-- Decision [Josh, 2026-08-11]: raw SQL backfill, no emails. The ORPHEUS-98
-- report-ready/feedback-ask email trigger lives exclusively in the admin
-- PATCH handler (_maybe_send_report_ready_on_publish), so this backfill
-- cannot send email. The 13 feedback asks stay unsent by design (Andrew
-- can nudge manually); stamping published_at also suppresses any future
-- automated send for these reports (already-announced dedup).
--
-- Run order: apply to production BEFORE deploying the gate. Backfill-first
-- is behavior-equivalent to the status quo (those clients already see
-- those reports); gate-first would briefly vanish 13 reports.

-- 1. Publish every remaining draft narrative on a complete job.
UPDATE public.narratives n
SET status = 'published',
    published_at = COALESCE(n.published_at, now())
FROM public.jobs j
WHERE n.job_id = j.id
  AND j.status = 'complete'
  AND n.status = 'draft';

-- 2. Stamp the report-level publication marker the read gate keys on.
UPDATE public.reports r
SET published_at = now()
FROM public.jobs j
WHERE r.job_id = j.id
  AND j.status = 'complete'
  AND r.report_type = 'advisory'
  AND r.published_at IS NULL;

-- Verification (both must return 0):
--
--   SELECT count(*) FROM public.narratives n
--   JOIN public.jobs j ON j.id = n.job_id
--   WHERE j.status = 'complete' AND n.status = 'draft';
--
--   SELECT count(*) FROM public.reports r
--   JOIN public.jobs j ON j.id = r.job_id
--   WHERE j.status = 'complete'
--     AND r.report_type = 'advisory'
--     AND r.published_at IS NULL;
