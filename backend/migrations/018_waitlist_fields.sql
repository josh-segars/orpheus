-- 018_waitlist_fields.sql  (ORPHEUS-8)
--
-- Expand the marketing waitlist capture (migration 017) from email-only to a
-- short "express interest" form: first name, last name, and which offering(s)
-- the prospect is interested in.
--
-- interests is a text[] rather than two booleans so the set of offerings can
-- grow without another migration. Current values: 'beta_access',
-- 'live_workshop'. Empty array is allowed at the DB level; the frontend
-- requires at least one selection.
--
-- The migration-017 RLS insert policy checks only the email shape, so the new
-- columns are covered by the existing anon-insert grant with no policy change.
-- Names are validated client-side; keeping the DB check minimal avoids
-- rejecting an otherwise-good lead over a formatting quibble.

alter table public.waitlist
    add column if not exists first_name text,
    add column if not exists last_name  text,
    add column if not exists interests  text[] not null default '{}';

comment on column public.waitlist.interests is
    'ORPHEUS-8: offerings the prospect expressed interest in. Values: beta_access, live_workshop. Extensible without migration.';
