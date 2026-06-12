-- 014_clients_user_id_unique.sql  (ORPHEUS-83)
--
-- Enforce the documented invariant from
-- Decision_Self_Serve_And_Advisor_Invite_2026-05-11: one auth.users row
-- owns AT MOST one clients row. Without this index, a second invitation
-- acceptance by an already-linked user created a duplicate clients row
-- (observed live 2026-06-12: Andrew's user held two rows under Josh's
-- advisor, making get_current_session_roles' clients lookup
-- nondeterministic; data repaired in-session, this is the structural
-- guard).
--
-- Partial index: pending invitations have user_id IS NULL and there can
-- be any number of them, so the uniqueness constraint applies only to
-- linked rows.
--
-- Pre-apply check (must return zero rows, or the CREATE will fail):
--
--   SELECT user_id, count(*) FROM public.clients
--   WHERE user_id IS NOT NULL
--   GROUP BY user_id HAVING count(*) > 1;
--
-- The accept-invitation handler also pre-checks (409) so users get a
-- clear message instead of a unique-violation 500; this index is the
-- backstop for races and any future write path.

CREATE UNIQUE INDEX IF NOT EXISTS clients_user_id_unique
    ON public.clients (user_id)
    WHERE user_id IS NOT NULL;
