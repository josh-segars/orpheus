-- Migration 012: add invitation_token + invitation_expires_at columns to public.clients.
-- Refs ORPHEUS-36.
--
-- =====================================================================
-- WHAT THIS DOES
-- =====================================================================
--
-- First DB-side step toward the advisor-invitation flow described in
-- Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md. Adds the two
-- columns the backend needs to back the invitation lifecycle:
--
--   - invitation_token       uuid          — single-use opaque token; NULL
--                                            after acceptance or revocation.
--   - invitation_expires_at  timestamptz   — soft expiry, enforced in the
--                                            backend (not as a column check).
--
-- Plus a partial UNIQUE index on `invitation_token` so:
--   - two active invitations can never collide on the same token, but
--   - many accepted clients can simultaneously have NULL tokens.
--
-- =====================================================================
-- ASSUMED STARTING STATE
-- =====================================================================
--
-- Runs on top of 001_base_schema.sql (prod) or any later state that
-- still has public.clients in its prod shape. Defensive against re-runs:
-- every change uses IF NOT EXISTS so the migration is idempotent.
--
-- Does NOT compose with migration 007 — 007 creates a different `clients`
-- shape (LinkedIn 1:1, id = auth.users.id) that doesn't have advisor_id
-- or invitation_status. See the historical-record header on 007 for the
-- drift story.
--
-- =====================================================================
-- DATA IMPACT
-- =====================================================================
--
-- Pure column additions on a table with 1 prod row at the time of
-- authoring. New columns are nullable with no default, so existing rows
-- pick up NULL and nothing else changes.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Add the two invitation columns. IF NOT EXISTS makes this idempotent.
-- ---------------------------------------------------------------------------

ALTER TABLE public.clients
    ADD COLUMN IF NOT EXISTS invitation_token       uuid,
    ADD COLUMN IF NOT EXISTS invitation_expires_at  timestamptz;

COMMENT ON COLUMN public.clients.invitation_token IS
    'Single-use opaque invitation token (uuid). NULL after the invitee accepts the invite or the advisor revokes/re-issues it. Partial UNIQUE index prevents collisions on active invitations.';

COMMENT ON COLUMN public.clients.invitation_expires_at IS
    'Soft expiry timestamp for invitation_token. Enforced by the backend at /accept-invitation time, not as a column check constraint, so an advisor can extend or shorten an expiry without a migration.';

-- ---------------------------------------------------------------------------
-- 2. Partial UNIQUE index on invitation_token. Partial so accepted clients
--    with NULL tokens don't collide.
-- ---------------------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_invitation_token
    ON public.clients (invitation_token)
    WHERE invitation_token IS NOT NULL;

COMMIT;
