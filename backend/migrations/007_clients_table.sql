-- Migration 007: public.clients table + on_auth_user_created trigger + FK on jobs
--
-- Implements the data model from Decision: LinkedIn Auth (2026-04-21) — ORPHEUS-23.
-- This migration creates the app-owned clients table, a trigger that populates
-- rows on first LinkedIn sign-in (enforcing the email-verified gate), and a
-- foreign key from jobs.client_id -> clients.id.
--
-- RLS is intentionally NOT enabled in this migration — that ships in 008 once
-- the backend user-scoped Supabase client is wired up. This keeps the incremental
-- rollout reviewable and revertable per the Migration Plan section of ORPHEUS-23.
--
-- Run against Supabase: Dashboard → SQL Editor → paste and run.
-- Or via Supabase CLI: `supabase db push` from the repo root.
--
-- Prerequisites:
--   - Supabase Auth schema is present (auth.users exists). Always true on
--     Supabase projects; this migration will fail fast if somehow absent.
--   - public.jobs exists with a client_id column (it does — predates the
--     known migrations). The FK is added at the bottom of this file.

BEGIN;

-- ---------------------------------------------------------------------------
-- public.clients
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.clients (
    id                       uuid         PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    linkedin_sub             text         NOT NULL,
    display_name             text         NOT NULL,
    given_name               text,
    family_name              text,
    profile_picture_url      text,
    locale                   text,
    groundwork_completed_at  timestamptz,
    created_at               timestamptz  NOT NULL DEFAULT now(),
    updated_at               timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.clients                       IS 'App-owned client profile. Keyed 1:1 on auth.users.id. Seeded from LinkedIn OIDC on first login.';
COMMENT ON COLUMN public.clients.linkedin_sub          IS 'LinkedIn member URN (OIDC sub claim). Stable across email changes.';
COMMENT ON COLUMN public.clients.display_name          IS 'Advisor-editable display name. Seeded from OIDC name on first login.';
COMMENT ON COLUMN public.clients.profile_picture_url   IS 'Advisor-editable picture. Seeded from OIDC picture on first login.';
COMMENT ON COLUMN public.clients.groundwork_completed_at IS 'Set when the client finishes the Groundwork Checklist. Used to route the portal landing screen.';

-- Unique index on linkedin_sub — same LinkedIn member should never map to two clients rows.
CREATE UNIQUE INDEX IF NOT EXISTS clients_linkedin_sub_unique ON public.clients (linkedin_sub);

-- updated_at auto-touch on UPDATE.
CREATE OR REPLACE FUNCTION public.clients_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS clients_set_updated_at ON public.clients;
CREATE TRIGGER clients_set_updated_at
    BEFORE UPDATE ON public.clients
    FOR EACH ROW
    EXECUTE FUNCTION public.clients_set_updated_at();

-- ---------------------------------------------------------------------------
-- on_auth_user_created trigger
--
-- Fires after a new auth.users row is inserted. Two responsibilities:
--
--   1. Enforce the email-verified gate. If email_confirmed_at IS NULL, raise
--      an exception that aborts the whole insert transaction (Supabase will
--      have already issued the user id, but the row is rolled back). Clients
--      can never reach a state where a verified auth.users row has no
--      clients row.
--
--   2. Populate public.clients from raw_user_meta_data / raw_app_meta_data.
--      Uses ON CONFLICT DO NOTHING so this is idempotent (Supabase can
--      re-trigger on some provider link scenarios).
--
-- LinkedIn OIDC provides the following keys in raw_user_meta_data:
--   name, given_name, family_name, picture, locale, email, email_verified
-- and in raw_app_meta_data:
--   provider = 'linkedin_oidc', providers = ['linkedin_oidc']
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    provider text;
BEGIN
    provider := COALESCE(NEW.raw_app_meta_data->>'provider', '');

    -- Only handle LinkedIn sign-ins. Other providers (if ever added) will
    -- need their own branch. Email/password sign-ups (if ever enabled)
    -- would also land here and should be explicitly rejected.
    IF provider <> 'linkedin_oidc' THEN
        RAISE EXCEPTION
            'Unsupported auth provider: %. Only linkedin_oidc is enabled.',
            provider
            USING ERRCODE = 'raise_exception';
    END IF;

    -- Email verification gate. Supabase populates email_confirmed_at from
    -- LinkedIn's email_verified claim. If the claim was false, this column
    -- stays NULL, and we refuse to create a clients row.
    IF NEW.email_confirmed_at IS NULL THEN
        RAISE EXCEPTION
            'LinkedIn returned email_verified=false for sub=%. Sign-in refused.',
            COALESCE(NEW.raw_user_meta_data->>'sub', '(unknown)')
            USING ERRCODE = 'raise_exception',
                  HINT = 'The user must verify their email address on LinkedIn before signing in.';
    END IF;

    INSERT INTO public.clients (
        id,
        linkedin_sub,
        display_name,
        given_name,
        family_name,
        profile_picture_url,
        locale
    )
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'sub', NEW.id::text),
        COALESCE(
            NULLIF(NEW.raw_user_meta_data->>'name', ''),
            NULLIF(CONCAT_WS(' ',
                NEW.raw_user_meta_data->>'given_name',
                NEW.raw_user_meta_data->>'family_name'
            ), ''),
            split_part(NEW.email, '@', 1)
        ),
        NEW.raw_user_meta_data->>'given_name',
        NEW.raw_user_meta_data->>'family_name',
        NEW.raw_user_meta_data->>'picture',
        NEW.raw_user_meta_data->>'locale'
    )
    ON CONFLICT (id) DO NOTHING;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.handle_new_auth_user IS
    'AFTER INSERT trigger on auth.users. Enforces the LinkedIn email-verified gate and populates public.clients from the OIDC claims on raw_user_meta_data. Raising here aborts the auth.users insert, so unverified sign-ins leave no orphan rows.';

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_auth_user();

-- ---------------------------------------------------------------------------
-- FK on public.jobs.client_id
--
-- The jobs table predates the known migrations, so client_id already exists.
-- We only add the FK if it isn't already present. A defensive type check is
-- included: if client_id is not uuid, the migration fails with a clear error
-- so Josh can decide on a cast path rather than getting a cryptic FK failure.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    col_type text;
BEGIN
    SELECT data_type
      INTO col_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name   = 'jobs'
       AND column_name  = 'client_id';

    IF col_type IS NULL THEN
        RAISE EXCEPTION 'Expected column public.jobs.client_id to exist';
    END IF;

    IF col_type <> 'uuid' THEN
        RAISE EXCEPTION
            'public.jobs.client_id is type % — expected uuid. Add an explicit ALTER TABLE ... TYPE uuid USING client_id::uuid; to this migration before the FK step.',
            col_type;
    END IF;
END
$$;

-- Add the FK if missing. Using a named constraint so re-runs are idempotent.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.table_constraints
         WHERE constraint_schema = 'public'
           AND table_name        = 'jobs'
           AND constraint_name   = 'jobs_client_id_fkey'
    ) THEN
        ALTER TABLE public.jobs
            ADD CONSTRAINT jobs_client_id_fkey
            FOREIGN KEY (client_id)
            REFERENCES public.clients(id)
            ON DELETE CASCADE;
    END IF;
END
$$;

COMMENT ON COLUMN public.jobs.client_id IS 'Owner of this job. FK to public.clients(id); cascades on account deletion (Decision: LinkedIn Auth, ORPHEUS-23).';

COMMIT;
