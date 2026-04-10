-- Migration 006: claim_next_job RPC function
-- Optimistic locking for the job queue worker. Uses FOR UPDATE SKIP LOCKED
-- so multiple workers can poll without claiming the same job.
--
-- Called via: supabase.rpc("claim_next_job")
-- Returns: single job row (or empty set if no pending jobs)
-- Applied to Supabase: pending

CREATE OR REPLACE FUNCTION public.claim_next_job()
RETURNS SETOF public.jobs
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    claimed_job public.jobs;
BEGIN
    SELECT *
    INTO claimed_job
    FROM public.jobs
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE public.jobs
    SET status = 'running',
        started_at = now()
    WHERE id = claimed_job.id;

    -- Return the row with updated status
    claimed_job.status := 'running';
    claimed_job.started_at := now();
    RETURN NEXT claimed_job;
END;
$$;

COMMENT ON FUNCTION public.claim_next_job IS 'Atomically claims the oldest pending job using FOR UPDATE SKIP LOCKED. Sets status to running and records started_at. Returns the claimed job row, or empty set if none available.';
