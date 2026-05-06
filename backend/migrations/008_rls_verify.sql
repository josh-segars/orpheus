-- Verification companion to migration 008 (RLS enable). Not a migration —
-- this script is meant to be pasted into Studio's SQL Editor (or piped
-- through psql) to confirm row-level isolation works end-to-end.
--
-- Implements the AC from ORPHEUS-29: "two seeded clients — each can read
-- their own job, gets 0 rows when trying to read the other's."
--
-- Wraps everything in a transaction that ROLLBACKs at the end, so it
-- leaves no trace in your database.
--
-- HOW TO READ THE OUTPUT
--   Each labelled SELECT below should return the count shown in the
--   comment. If any count differs, RLS is not behaving as expected and
--   the migration's policies need investigation.
--
-- BEFORE RUNNING
--   Replace every occurrence of the placeholder Josh UUID with whatever
--   UID Studio shows for your account in Authentication → Users.
--
--   Search-and-replace:
--       fcdc897f-3728-4f3c-9a26-fda848722c48   ← change to your UID
--
--   The synthetic test-user UID below is already a fixed value with no
--   collision potential, so leave that alone.
--
-- PREREQUISITES
--   - Migration 008 has been applied.
--   - Your own LinkedIn-signed-in row exists in auth.users / clients.

BEGIN;

-- ---------------------------------------------------------------------------
-- Setup
-- ---------------------------------------------------------------------------

-- Insert the synthetic second user. The on_auth_user_created trigger from
-- migration 007 will create the matching public.clients row.
INSERT INTO auth.users (
    id, aud, role, email,
    email_confirmed_at, last_sign_in_at,
    raw_user_meta_data, raw_app_meta_data,
    is_super_admin, created_at, updated_at,
    instance_id
) VALUES (
    '00000000-aaaa-bbbb-cccc-000000000099',
    'authenticated', 'authenticated',
    'rls-test@example.invalid',
    now(), now(),
    jsonb_build_object(
        'name',        'RLS Test User',
        'given_name',  'RLS',
        'family_name', 'Test',
        'sub',         'urn:test:rls-test-user',
        'picture',     null
    ),
    jsonb_build_object(
        'provider',  'linkedin_oidc',
        'providers', jsonb_build_array('linkedin_oidc')
    ),
    false,
    now(), now(),
    '00000000-0000-0000-0000-000000000000'
);

-- One job per client. Both inserts run as the postgres role here, which
-- bypasses RLS — the WITH CHECK policy on jobs only kicks in for the
-- authenticated role, exercised below.
INSERT INTO public.jobs (client_id, status) VALUES
    ('fcdc897f-3728-4f3c-9a26-fda848722c48'::uuid, 'pending'),  -- Josh
    ('00000000-aaaa-bbbb-cccc-000000000099'::uuid, 'pending');  -- RLS Test User

-- ---------------------------------------------------------------------------
-- Impersonation tests
-- ---------------------------------------------------------------------------

-- Switch out of postgres (which bypasses RLS) into the authenticated role
-- (which respects RLS) for the rest of this transaction.
SET LOCAL role = 'authenticated';

-- ─── AS JOSH ─────────────────────────────────────────────────────────────
SET LOCAL request.jwt.claims TO '{"sub": "fcdc897f-3728-4f3c-9a26-fda848722c48", "role": "authenticated", "aud": "authenticated"}';

SELECT 'josh_total_visible_jobs' AS check_name, count(*)::text AS value
  FROM public.jobs;
-- Expected: >= 1 (your existing jobs plus the one we just inserted)

SELECT 'josh_can_see_test_user_job' AS check_name, count(*)::text AS value
  FROM public.jobs
 WHERE client_id = '00000000-aaaa-bbbb-cccc-000000000099';
-- Expected: 0   <— cross-tenant isolation check

SELECT 'josh_can_read_test_user_clients_row' AS check_name, count(*)::text AS value
  FROM public.clients
 WHERE id = '00000000-aaaa-bbbb-cccc-000000000099';
-- Expected: 0

-- ─── AS RLS TEST USER ────────────────────────────────────────────────────
SET LOCAL request.jwt.claims TO '{"sub": "00000000-aaaa-bbbb-cccc-000000000099", "role": "authenticated", "aud": "authenticated"}';

SELECT 'test_user_total_visible_jobs' AS check_name, count(*)::text AS value
  FROM public.jobs;
-- Expected: 1   (only the test user's own job)

SELECT 'test_user_can_see_josh_job' AS check_name, count(*)::text AS value
  FROM public.jobs
 WHERE client_id = 'fcdc897f-3728-4f3c-9a26-fda848722c48';
-- Expected: 0   <— cross-tenant check the other direction

SELECT 'test_user_can_read_josh_clients_row' AS check_name, count(*)::text AS value
  FROM public.clients
 WHERE id = 'fcdc897f-3728-4f3c-9a26-fda848722c48';
-- Expected: 0

-- ─── AS NOBODY (no JWT claims set) ───────────────────────────────────────
SET LOCAL request.jwt.claims TO '';

SELECT 'anon_total_visible_jobs' AS check_name, count(*)::text AS value
  FROM public.jobs;
-- Expected: 0

-- ---------------------------------------------------------------------------
-- Always rollback so the synthetic user + jobs leave no trace.
-- ---------------------------------------------------------------------------

ROLLBACK;
