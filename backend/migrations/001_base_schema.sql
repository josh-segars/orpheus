-- Migration 001: Base schema (snapshot of prod public schema). Refs ORPHEUS-35.
--
-- =====================================================================
-- READ THIS BEFORE TOUCHING ANYTHING
-- =====================================================================
--
-- This file is a faithful dump of the current production public schema
-- (project ref: yqxuddkixzjruxtdjxpr) captured 2026-05-11. It exists so
-- new local-dev databases can be spun up to match prod without needing
-- access to the prod project — the gap that blocked ORPHEUS-20's
-- end-to-end verification.
--
-- The schema here represents the *legacy* design that pre-dates the
-- LinkedIn-auth architecture decided in ORPHEUS-23 (2026-04-21). The
-- conceptual model in this file is the advisor-managed-clients design:
--
--   - `advisors` rows represent advisor accounts.
--   - `clients` rows are subjects of analysis, linked to an advisor and
--     (optionally) to a Supabase auth.users row for portal access.
--   - RLS policies use SECURITY DEFINER helpers (`get_advisor_id`,
--     `get_client_id`) and dual `_as_advisor` / `_as_client` policies
--     per table.
--
-- The current code in this repo (post-ORPHEUS-23) targets a different
-- design — LinkedIn-1:1 self-serve, simpler auth.uid() RLS, etc. — which
-- is the design migrations 007 / 008 / 009 / 010 were written for. Those
-- migrations assume a fresh DB; against the schema in this file most of
-- them are no-ops (CREATE TABLE IF NOT EXISTS guards) or worse, partial
-- conflicts. They are kept in the repo as historical record but should
-- NOT be applied on top of this file in a fresh setup.
--
-- A fresh local-dev setup is:
--     supabase db reset
--     # then apply, in order:
--     #   001_base_schema.sql                  — this file
--     #   011_questionnaire_align_to_spec.sql  — ORPHEUS-33 questionnaire reshape
--     #   012_clients_invitation_columns.sql   — ORPHEUS-36 invitation_token columns
--
-- Migrations 003-006 are domain-additive (v2 scoring columns, narratives
-- column rename, quality_report column, claim_next_job RPC) and ARE
-- already applied in prod — their effects are baked into the schema
-- below. Re-running them on a DB that has this file applied would be
-- partially a no-op and partially redundant; safest to skip.
--
-- Migration 012 (added 2026-05-13, after this file was captured) layers
-- the `invitation_token` + `invitation_expires_at` columns onto
-- public.clients. Idempotent — safe to re-apply, safe in any order
-- after 001.
--
-- See ORPHEUS-35 for the broader story.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Custom types (enums)
--
-- CREATE TYPE has no IF NOT EXISTS clause even in Postgres 17, so wrap each
-- in a DO block. Idempotent.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'client_status') THEN
        CREATE TYPE public.client_status AS ENUM ('active', 'inactive', 'migrated');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invitation_status') THEN
        CREATE TYPE public.invitation_status AS ENUM ('pending', 'accepted', 'expired');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
        CREATE TYPE public.job_status AS ENUM ('pending', 'running', 'complete', 'failed');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'narrative_status') THEN
        CREATE TYPE public.narrative_status AS ENUM ('draft', 'published');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'report_type') THEN
        CREATE TYPE public.report_type AS ENUM ('advisory', 'self_serve');
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- public.advisors
-- One row per advisor or self-serve individual.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.advisors (
    id              uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid         NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    is_individual   boolean      NOT NULL DEFAULT false,
    practice_name   text,
    logo_url        text,
    color_primary   text,
    color_accent    text,
    custom_domain   text,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    narrative_config jsonb
);

COMMENT ON TABLE  public.advisors                   IS 'One row per advisor or self-serve individual. Self-serve users have is_individual = true.';
COMMENT ON COLUMN public.advisors.narrative_config  IS 'Advisor-level narrative generation config (voice, recommendation_style, system_mechanics, practice_focus, custom_instructions). Null = use platform defaults.';

-- ---------------------------------------------------------------------------
-- public.clients
-- Subject of analysis. Linked to an advisor; optionally linked to a
-- Supabase auth user.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.clients (
    id                 uuid                NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    advisor_id         uuid                NOT NULL REFERENCES public.advisors(id) ON DELETE CASCADE,
    user_id            uuid                REFERENCES auth.users(id) ON DELETE SET NULL,
    display_name       text                NOT NULL,
    email              text                NOT NULL,
    invitation_status  public.invitation_status NOT NULL DEFAULT 'pending',
    status             public.client_status     NOT NULL DEFAULT 'active',
    created_at         timestamptz         NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.clients IS 'Subject being analyzed. Advisory clients are invited by email; self-serve users have one client record pointing to themselves.';

CREATE INDEX IF NOT EXISTS idx_clients_advisor_id ON public.clients (advisor_id);
CREATE INDEX IF NOT EXISTS idx_clients_user_id    ON public.clients (user_id) WHERE (user_id IS NOT NULL);

-- ---------------------------------------------------------------------------
-- public.jobs
-- Analysis pipeline runs.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.jobs (
    id                uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id         uuid              NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    status            public.job_status NOT NULL DEFAULT 'pending',
    version_label     text,
    config_snapshot   jsonb,
    attempt_count     integer           NOT NULL DEFAULT 0,
    error_message     text,
    created_at        timestamptz       NOT NULL DEFAULT now(),
    started_at        timestamptz,
    completed_at      timestamptz
);

COMMENT ON TABLE public.jobs IS 'Analysis pipeline runs. Each job produces ingested_data, scores, narratives, and a report.';

CREATE INDEX IF NOT EXISTS idx_jobs_client_id ON public.jobs (client_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status    ON public.jobs (status) WHERE (status = ANY (ARRAY['pending'::public.job_status, 'running'::public.job_status]));

-- ---------------------------------------------------------------------------
-- public.ingested_data
-- Parsed LinkedIn ZIP + Analytics XLSX as structured JSONB.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.ingested_data (
    id              uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          uuid         NOT NULL UNIQUE REFERENCES public.jobs(id) ON DELETE CASCADE,
    zip_data        jsonb,
    xlsx_data       jsonb,
    ingested_at     timestamptz  NOT NULL DEFAULT now(),
    quality_report  jsonb
);

COMMENT ON TABLE  public.ingested_data                IS 'Parsed LinkedIn ZIP and XLSX data as structured JSONB. Intermediate state between raw files and scoring.';
COMMENT ON COLUMN public.ingested_data.quality_report IS 'Structured data quality report (DataQualityReport model). Contains severity-tagged issues, file inventory, row counts, and date range from ingestion.';

-- ---------------------------------------------------------------------------
-- public.scores
-- Signal Score v2 results — both dimension scores and Forward Brief data.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.scores (
    id                  uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              uuid         NOT NULL UNIQUE REFERENCES public.jobs(id) ON DELETE CASCADE,
    total_score         numeric      NOT NULL,
    dimensions          jsonb        NOT NULL,
    scored_at           timestamptz  NOT NULL DEFAULT now(),
    band                text         CHECK (band IS NULL OR band = ANY (ARRAY['Weak', 'Emerging', 'Moderate', 'Strong', 'Exceptional'])),
    forward_brief_data  jsonb
);

COMMENT ON TABLE  public.scores                    IS 'Signal Score v2 results. dimensions JSONB contains 4 dimension scores; forward_brief_data JSONB contains Reach/Resonance/Authority data and qualitative flags.';
COMMENT ON COLUMN public.scores.band               IS 'Client-facing signal strength band: Weak/Emerging/Moderate/Strong/Exceptional';
COMMENT ON COLUMN public.scores.forward_brief_data IS 'Structured data for Forward Brief: quantitative fields + qualitative flags (JSONB)';

-- ---------------------------------------------------------------------------
-- public.narratives
-- AI-generated narratives per section. Section is a dimension name or
-- "forward_brief". The UNIQUE INDEX retains its legacy name
-- (`narratives_job_id_dimension_key`) from before migration 004 renamed
-- the `dimension` column to `section`.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.narratives (
    id              uuid                    PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          uuid                    NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    section         text                    NOT NULL,
    generated_text  text                    NOT NULL,
    edited_text     text,
    status          public.narrative_status NOT NULL DEFAULT 'draft',
    published_at    timestamptz,
    generated_at    timestamptz             NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.narratives         IS 'AI-generated narratives per section. Section is a dimension name or "forward_brief". Advisory flow uses draft→published; self-serve auto-publishes.';
COMMENT ON COLUMN public.narratives.section IS 'Section identifier: dimension name (e.g. "Profile Signal Clarity") or "forward_brief"';

CREATE INDEX        IF NOT EXISTS idx_narratives_job_id           ON public.narratives (job_id);
CREATE UNIQUE INDEX IF NOT EXISTS narratives_job_id_dimension_key ON public.narratives (job_id, section);

-- ---------------------------------------------------------------------------
-- public.reports
-- Published Signal Score + Forward Brief. Branding snapshotted at
-- generation time.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.reports (
    id                 uuid               PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id             uuid               NOT NULL UNIQUE REFERENCES public.jobs(id) ON DELETE CASCADE,
    client_id          uuid               NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    report_type        public.report_type NOT NULL,
    branding_snapshot  jsonb              NOT NULL DEFAULT '{}'::jsonb,
    forward_brief      jsonb,
    published_at       timestamptz        DEFAULT now()
);

COMMENT ON TABLE public.reports IS 'Published Signal Score + Forward Brief. Branding is snapshotted at generation time for historical accuracy.';

CREATE INDEX IF NOT EXISTS idx_reports_client_id ON public.reports (client_id);

-- ---------------------------------------------------------------------------
-- public.questionnaire_responses
-- One row per client. Note: this is the legacy shape (id PK, client_id
-- UNIQUE, responses column, schema_version, completed_at). Migration 011
-- aligns this table to the ORPHEUS-33 spec.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.questionnaire_responses (
    id              uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid         NOT NULL UNIQUE REFERENCES public.clients(id) ON DELETE CASCADE,
    responses       jsonb        NOT NULL DEFAULT '{}'::jsonb,
    schema_version  text         NOT NULL DEFAULT '1.0',
    completed_at    timestamptz,
    updated_at      timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.questionnaire_responses IS 'Questionnaire answers stored as JSONB. One row per client, updated incrementally.';

-- ---------------------------------------------------------------------------
-- Helper functions used by RLS policies.
--
-- SECURITY DEFINER + `SET search_path TO ''` so the resolver runs with
-- the function owner's privileges and an empty search path (defence in
-- depth against schema-hijack attacks).
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_advisor_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $$
    SELECT id FROM public.advisors WHERE user_id = auth.uid()
$$;

CREATE OR REPLACE FUNCTION public.get_client_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $$
    SELECT id FROM public.clients WHERE user_id = auth.uid()
$$;

-- ---------------------------------------------------------------------------
-- claim_next_job RPC — used by the worker to atomically claim a pending
-- job with FOR UPDATE SKIP LOCKED. Originally introduced by migration
-- 006; included here as part of the base snapshot.
-- ---------------------------------------------------------------------------

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

    claimed_job.status := 'running';
    claimed_job.started_at := now();
    RETURN NEXT claimed_job;
END;
$$;

-- ---------------------------------------------------------------------------
-- RLS — enable + policies
--
-- Prod uses dual `_as_advisor` / `_as_client` policies per table, plus
-- the SECURITY DEFINER helpers above. This is a more sophisticated
-- design than migration 008's simpler auth.uid() check; the two won't
-- compose cleanly.
-- ---------------------------------------------------------------------------

ALTER TABLE public.advisors                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clients                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingested_data           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scores                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.narratives              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questionnaire_responses ENABLE ROW LEVEL SECURITY;

-- advisors
DROP POLICY IF EXISTS advisors_select_own ON public.advisors;
CREATE POLICY advisors_select_own ON public.advisors
    FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS advisors_update_own ON public.advisors;
CREATE POLICY advisors_update_own ON public.advisors
    FOR UPDATE USING (user_id = auth.uid());

-- clients
DROP POLICY IF EXISTS clients_select_as_advisor ON public.clients;
CREATE POLICY clients_select_as_advisor ON public.clients
    FOR SELECT USING (advisor_id = public.get_advisor_id());

DROP POLICY IF EXISTS clients_select_as_client ON public.clients;
CREATE POLICY clients_select_as_client ON public.clients
    FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS clients_insert_as_advisor ON public.clients;
CREATE POLICY clients_insert_as_advisor ON public.clients
    FOR INSERT WITH CHECK (advisor_id = public.get_advisor_id());

DROP POLICY IF EXISTS clients_update_as_advisor ON public.clients;
CREATE POLICY clients_update_as_advisor ON public.clients
    FOR UPDATE USING (advisor_id = public.get_advisor_id());

DROP POLICY IF EXISTS clients_delete_as_advisor ON public.clients;
CREATE POLICY clients_delete_as_advisor ON public.clients
    FOR DELETE USING (advisor_id = public.get_advisor_id());

-- jobs
DROP POLICY IF EXISTS jobs_select_as_advisor ON public.jobs;
CREATE POLICY jobs_select_as_advisor ON public.jobs
    FOR SELECT USING (
        client_id IN (SELECT id FROM public.clients WHERE advisor_id = public.get_advisor_id())
    );

DROP POLICY IF EXISTS jobs_select_as_client ON public.jobs;
CREATE POLICY jobs_select_as_client ON public.jobs
    FOR SELECT USING (client_id = public.get_client_id());

DROP POLICY IF EXISTS jobs_insert_as_advisor ON public.jobs;
CREATE POLICY jobs_insert_as_advisor ON public.jobs
    FOR INSERT WITH CHECK (
        client_id IN (SELECT id FROM public.clients WHERE advisor_id = public.get_advisor_id())
    );

DROP POLICY IF EXISTS jobs_insert_as_client ON public.jobs;
CREATE POLICY jobs_insert_as_client ON public.jobs
    FOR INSERT WITH CHECK (client_id = public.get_client_id());

-- ingested_data
DROP POLICY IF EXISTS ingested_data_select_as_advisor ON public.ingested_data;
CREATE POLICY ingested_data_select_as_advisor ON public.ingested_data
    FOR SELECT USING (
        job_id IN (
            SELECT j.id FROM public.jobs j
            JOIN public.clients c ON c.id = j.client_id
            WHERE c.advisor_id = public.get_advisor_id()
        )
    );

DROP POLICY IF EXISTS ingested_data_select_as_client ON public.ingested_data;
CREATE POLICY ingested_data_select_as_client ON public.ingested_data
    FOR SELECT USING (
        job_id IN (SELECT id FROM public.jobs WHERE client_id = public.get_client_id())
    );

-- scores
DROP POLICY IF EXISTS scores_select_as_advisor ON public.scores;
CREATE POLICY scores_select_as_advisor ON public.scores
    FOR SELECT USING (
        job_id IN (
            SELECT j.id FROM public.jobs j
            JOIN public.clients c ON c.id = j.client_id
            WHERE c.advisor_id = public.get_advisor_id()
        )
    );

DROP POLICY IF EXISTS scores_select_as_client ON public.scores;
CREATE POLICY scores_select_as_client ON public.scores
    FOR SELECT USING (
        job_id IN (SELECT id FROM public.jobs WHERE client_id = public.get_client_id())
    );

-- narratives
DROP POLICY IF EXISTS narratives_select_as_advisor ON public.narratives;
CREATE POLICY narratives_select_as_advisor ON public.narratives
    FOR SELECT USING (
        job_id IN (
            SELECT j.id FROM public.jobs j
            JOIN public.clients c ON c.id = j.client_id
            WHERE c.advisor_id = public.get_advisor_id()
        )
    );

DROP POLICY IF EXISTS narratives_select_as_client ON public.narratives;
CREATE POLICY narratives_select_as_client ON public.narratives
    FOR SELECT USING (
        status = 'published' AND
        job_id IN (SELECT id FROM public.jobs WHERE client_id = public.get_client_id())
    );

DROP POLICY IF EXISTS narratives_update_as_advisor ON public.narratives;
CREATE POLICY narratives_update_as_advisor ON public.narratives
    FOR UPDATE USING (
        job_id IN (
            SELECT j.id FROM public.jobs j
            JOIN public.clients c ON c.id = j.client_id
            WHERE c.advisor_id = public.get_advisor_id()
        )
    );

-- reports
DROP POLICY IF EXISTS reports_select_as_advisor ON public.reports;
CREATE POLICY reports_select_as_advisor ON public.reports
    FOR SELECT USING (
        client_id IN (SELECT id FROM public.clients WHERE advisor_id = public.get_advisor_id())
    );

DROP POLICY IF EXISTS reports_select_as_client ON public.reports;
CREATE POLICY reports_select_as_client ON public.reports
    FOR SELECT USING (client_id = public.get_client_id());

-- questionnaire_responses
DROP POLICY IF EXISTS qr_select_as_advisor ON public.questionnaire_responses;
CREATE POLICY qr_select_as_advisor ON public.questionnaire_responses
    FOR SELECT USING (
        client_id IN (SELECT id FROM public.clients WHERE advisor_id = public.get_advisor_id())
    );

DROP POLICY IF EXISTS qr_select_as_client ON public.questionnaire_responses;
CREATE POLICY qr_select_as_client ON public.questionnaire_responses
    FOR SELECT USING (client_id = public.get_client_id());

DROP POLICY IF EXISTS qr_insert_as_advisor ON public.questionnaire_responses;
CREATE POLICY qr_insert_as_advisor ON public.questionnaire_responses
    FOR INSERT WITH CHECK (
        client_id IN (SELECT id FROM public.clients WHERE advisor_id = public.get_advisor_id())
    );

DROP POLICY IF EXISTS qr_insert_as_client ON public.questionnaire_responses;
CREATE POLICY qr_insert_as_client ON public.questionnaire_responses
    FOR INSERT WITH CHECK (client_id = public.get_client_id());

DROP POLICY IF EXISTS qr_update_as_advisor ON public.questionnaire_responses;
CREATE POLICY qr_update_as_advisor ON public.questionnaire_responses
    FOR UPDATE USING (
        client_id IN (SELECT id FROM public.clients WHERE advisor_id = public.get_advisor_id())
    );

DROP POLICY IF EXISTS qr_update_as_client ON public.questionnaire_responses;
CREATE POLICY qr_update_as_client ON public.questionnaire_responses
    FOR UPDATE USING (client_id = public.get_client_id());

COMMIT;
