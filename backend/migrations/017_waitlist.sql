-- 017_waitlist.sql  (ORPHEUS-8)
--
-- Marketing-site waitlist capture. The www marketing landing page (served by
-- the same Vite frontend, hostname-routed — apex/www render the landing page,
-- app.* renders the portal) collects emails from prospects while the product
-- is invitation-only closed beta. Stored here so the existing browser-side
-- anon Supabase client can write directly, with no new backend endpoint.
--
-- Security posture: the browser holds the anon key, so the RLS policy allows
-- INSERT for the `anon` (and `authenticated`) role only. There is NO select /
-- update / delete policy, so the table is write-only from the client — a
-- visitor can add their email but can never read the list back. Reads are
-- service-role only (Supabase dashboard / backend), which bypasses RLS.
--
-- Duplicate emails: a UNIQUE index on lower(email) collapses repeats. The
-- frontend treats the resulting 23505 as success ("you're on the list").

create table if not exists public.waitlist (
    id          uuid primary key default gen_random_uuid(),
    email       text not null,
    source      text,                       -- e.g. 'www-landing'
    user_agent  text,
    created_at  timestamptz not null default now()
);

create unique index if not exists waitlist_email_unique
    on public.waitlist (lower(email));

alter table public.waitlist enable row level security;

-- Anonymous visitors (and any authenticated user) may add themselves. The
-- WITH CHECK gates the row shape with a light email sanity check; there is
-- deliberately no USING clause for other verbs, so anon cannot read, update,
-- or delete.
drop policy if exists waitlist_insert_anon on public.waitlist;
create policy waitlist_insert_anon
    on public.waitlist
    for insert
    to anon, authenticated
    with check (
        email is not null
        and char_length(email) between 3 and 320
        and position('@' in email) > 1
    );

comment on table public.waitlist is
    'ORPHEUS-8: closed-beta waitlist emails captured by the www marketing landing page. Anon-insert-only via RLS; reads are service-role only.';
