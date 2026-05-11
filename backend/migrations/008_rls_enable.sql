-- =====================================================================
-- HISTORICAL — DO NOT RUN AGAINST PROD OR ON TOP OF 001_base_schema.sql.
-- =====================================================================
-- This migration designs simpler `auth.uid()`-direct RLS policies that
-- assume the migration-007 clients model (id = auth.users.id). Prod
-- (and 001_base_schema.sql) instead uses dual `_as_advisor` /
-- `_as_client` policies with SECURITY DEFINER helpers
-- (get_advisor_id, get_client_id) — a more sophisticated design that
-- accounts for the advisor-managed-invite flow.
--
-- Running this on top of 001 would re-enable RLS (no-op; already on)
-- and then add policies that may conflict with the prod design. The
-- result is a confused policy set rather than a clean override.
--
-- Kept for historical record. See ORPHEUS-35 for the broader drift.
-- =====================================================================
--
-- Migration 008: enable Row Level Security across the Orpheus app schema.
--
-- Implements the access-control boundary from Decision: LinkedIn Auth
-- (ORPHEUS-23). Until this migration the only ownership check on
-- client-facing routes was the .eq('client_id', current.client_id) filter
-- in backend/routers/jobs.py. After this migration the database itself
-- enforces ownership via auth.uid().
--
-- IMPORTANT: deploy together with a backend that uses
-- backend.db.user_scoped_supabase() for client-facing requests. Worker
-- and admin routes continue to use the service-role client which
-- bypasses RLS by design.
--
-- Defensive shape: clients and jobs are applied unconditionally because
-- both definitely exist (clients from migration 007, jobs from the
-- production setup or local baseline). The narrative / scoring / ingestion
-- tables (ingested_data, scores, narratives) live in production but may
-- not exist on a partial local-dev schema, so each is wrapped in a
-- table-existence check and emits a NOTICE on skip. The same migration
-- file therefore runs cleanly against both environments.
--
-- Idempotent: DROP POLICY IF EXISTS before each CREATE means re-running
-- this migration is harmless (e.g. after a `supabase db reset`).

BEGIN;

-- ---------------------------------------------------------------------------
-- public.clients
-- ---------------------------------------------------------------------------

ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clients_select_own ON public.clients;
CREATE POLICY clients_select_own
    ON public.clients
    FOR SELECT
    TO authenticated
    USING (id = auth.uid());

DROP POLICY IF EXISTS clients_update_own ON public.clients;
CREATE POLICY clients_update_own
    ON public.clients
    FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- No client INSERT policy: rows are inserted only by the
-- on_auth_user_created trigger (SECURITY DEFINER, runs as table owner,
-- bypasses RLS) or by service-role admin operations.
--
-- No client DELETE policy: account deletion cascades from auth.users
-- via FK; we don't want clients deleting their public.clients row
-- without also deleting the auth identity.

COMMENT ON TABLE public.clients IS 'App-owned client profile. RLS: clients can SELECT/UPDATE their own row only. INSERT via trigger, DELETE via cascade only.';

-- ---------------------------------------------------------------------------
-- public.jobs
-- ---------------------------------------------------------------------------

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS jobs_select_own ON public.jobs;
CREATE POLICY jobs_select_own
    ON public.jobs
    FOR SELECT
    TO authenticated
    USING (client_id = auth.uid());

DROP POLICY IF EXISTS jobs_insert_own ON public.jobs;
CREATE POLICY jobs_insert_own
    ON public.jobs
    FOR INSERT
    TO authenticated
    WITH CHECK (client_id = auth.uid());

-- No client UPDATE / DELETE policies: job state transitions
-- (pending → running → complete / failed) are server-owned and run
-- via the worker (service-role).

COMMENT ON TABLE public.jobs IS 'Analysis jobs. RLS: clients can SELECT their own; INSERT only with client_id = auth.uid(). State transitions handled server-side via service role.';

-- ---------------------------------------------------------------------------
-- public.ingested_data — read-only for clients, gated by job ownership.
-- Skipped if the table is not present (partial local-dev schema).
-- ---------------------------------------------------------------------------

DO $rls$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_tables
         WHERE schemaname = 'public'
           AND tablename  = 'ingested_data'
    ) THEN
        EXECUTE 'ALTER TABLE public.ingested_data ENABLE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS ingested_data_select_via_jobs ON public.ingested_data';
        EXECUTE $policy$
            CREATE POLICY ingested_data_select_via_jobs
                ON public.ingested_data
                FOR SELECT
                TO authenticated
                USING (
                    EXISTS (
                        SELECT 1
                          FROM public.jobs j
                         WHERE j.id        = public.ingested_data.job_id
                           AND j.client_id = auth.uid()
                    )
                )
        $policy$;
        RAISE NOTICE 'RLS enabled on public.ingested_data';
    ELSE
        RAISE NOTICE 'Skipping public.ingested_data — table not present in this database';
    END IF;
END
$rls$;

-- ---------------------------------------------------------------------------
-- public.scores — same pattern.
-- ---------------------------------------------------------------------------

DO $rls$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_tables
         WHERE schemaname = 'public'
           AND tablename  = 'scores'
    ) THEN
        EXECUTE 'ALTER TABLE public.scores ENABLE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS scores_select_via_jobs ON public.scores';
        EXECUTE $policy$
            CREATE POLICY scores_select_via_jobs
                ON public.scores
                FOR SELECT
                TO authenticated
                USING (
                    EXISTS (
                        SELECT 1
                          FROM public.jobs j
                         WHERE j.id        = public.scores.job_id
                           AND j.client_id = auth.uid()
                    )
                )
        $policy$;
        RAISE NOTICE 'RLS enabled on public.scores';
    ELSE
        RAISE NOTICE 'Skipping public.scores — table not present in this database';
    END IF;
END
$rls$;

-- ---------------------------------------------------------------------------
-- public.narratives — same pattern.
-- ---------------------------------------------------------------------------

DO $rls$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_tables
         WHERE schemaname = 'public'
           AND tablename  = 'narratives'
    ) THEN
        EXECUTE 'ALTER TABLE public.narratives ENABLE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS narratives_select_via_jobs ON public.narratives';
        EXECUTE $policy$
            CREATE POLICY narratives_select_via_jobs
                ON public.narratives
                FOR SELECT
                TO authenticated
                USING (
                    EXISTS (
                        SELECT 1
                          FROM public.jobs j
                         WHERE j.id        = public.narratives.job_id
                           AND j.client_id = auth.uid()
                    )
                )
        $policy$;
        RAISE NOTICE 'RLS enabled on public.narratives';
    ELSE
        RAISE NOTICE 'Skipping public.narratives — table not present in this database';
    END IF;
END
$rls$;

COMMIT;
