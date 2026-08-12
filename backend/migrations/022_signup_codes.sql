-- 022_signup_codes.sql  (ORPHEUS-129, expands the ORPHEUS-85 gate)
--
-- =====================================================================
-- WHAT THIS DOES
-- =====================================================================
--
-- Turns the self-serve sign-up gate from a single shared env value
-- (BETA_ACCESS_CODE — retired before it was ever set in Railway) into
-- a durable code system:
--
--   - public.signup_codes      — admin-generated access codes. Each
--                                carries a label (what it's for), an
--                                optional advisor routing override (the
--                                group/business case), optional expiry
--                                and max-uses limits, and a disable
--                                timestamp for per-code kill switches.
--   - public.code_redemptions  — one row per client created through a
--                                code. This IS the attribution record
--                                ("which cohort did this client come
--                                from") and the source of use counts —
--                                there is deliberately NO use_count
--                                counter column to keep in sync;
--                                counts are derived by counting
--                                redemptions.
--
-- RLS posture: enabled on both tables with NO policies — service-role
-- only, same shape as public.waitlist (migration 017). The anon and
-- authenticated roles can neither read nor write; the backend is the
-- sole path in (POST /signup/complete validates + redeems, /admin/codes
-- manages).
--
-- =====================================================================
-- ASSUMED STARTING STATE
-- =====================================================================
--
-- Runs on top of 001_base_schema.sql + 014 (clients_user_id_unique).
-- References public.advisors and public.clients. Idempotent: IF NOT
-- EXISTS guards throughout.
--
-- =====================================================================
-- DATA IMPACT
-- =====================================================================
--
-- Pure table additions; no existing rows touched. Seeding the first
-- code (the closed-beta code) happens operationally via /admin/codes
-- or a one-off INSERT — not in this migration, because the code value
-- is a secret and migrations are committed to source.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. public.signup_codes
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.signup_codes (
    id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    code         text         NOT NULL,
    label        text         NOT NULL,
    -- Routing override for group/business codes: clients created with
    -- this code land under this advisor instead of HOUSE_ADVISOR_ID.
    -- SET NULL on advisor delete = the code silently falls back to the
    -- house advisor rather than breaking sign-up.
    advisor_id   uuid         REFERENCES public.advisors(id) ON DELETE SET NULL,
    expires_at   timestamptz,
    max_uses     integer      CHECK (max_uses IS NULL OR max_uses > 0),
    disabled_at  timestamptz,
    created_by   text,
    created_at   timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.signup_codes             IS 'Admin-generated sign-up access codes (ORPHEUS-129). Validated by POST /signup/complete; managed via /admin/codes. Service-role only (RLS enabled, no policies).';
COMMENT ON COLUMN public.signup_codes.code        IS 'The code users enter on /signup. Unique case-insensitively (lower(code) index). Stored plaintext deliberately — codes are distribution secrets admins must read back to hand out, not passwords.';
COMMENT ON COLUMN public.signup_codes.label       IS 'Admin-facing purpose label, e.g. "Closed beta" or "Acme Co cohort — spring 2027".';
COMMENT ON COLUMN public.signup_codes.advisor_id  IS 'Optional routing override: clients signing up with this code land under this advisor instead of the HOUSE_ADVISOR_ID default. NULL = house advisor.';
COMMENT ON COLUMN public.signup_codes.max_uses    IS 'Optional redemption cap. NULL = unlimited. Enforced check-then-insert (non-atomic; over-redemption by 1 possible under concurrency — accepted at beta scale, see ORPHEUS-129).';
COMMENT ON COLUMN public.signup_codes.disabled_at IS 'Per-code kill switch. Non-NULL = code rejected at /signup/complete regardless of expiry/uses.';
COMMENT ON COLUMN public.signup_codes.created_by  IS 'Email of the admin who created the code (from the get_current_admin JWT). Text, not an FK — admin identity is an env allowlist, not a table.';

-- Case-insensitive uniqueness: "ACME2027" and "acme2027" are the same
-- code. Lookups normalize with lower() on both sides.
CREATE UNIQUE INDEX IF NOT EXISTS signup_codes_code_unique
    ON public.signup_codes (lower(code));

ALTER TABLE public.signup_codes ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 2. public.code_redemptions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.code_redemptions (
    id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    code_id      uuid         NOT NULL REFERENCES public.signup_codes(id) ON DELETE CASCADE,
    -- CASCADE with the client: if the client is deleted (ORPHEUS-124
    -- account deletion), their attribution row goes too — a redemption
    -- of a deleted account is personal data with no remaining purpose.
    client_id    uuid         NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    redeemed_at  timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.code_redemptions           IS 'One row per client created through a signup code (ORPHEUS-129). Attribution record + the source of per-code use counts (counted, not countered). Service-role only.';
COMMENT ON COLUMN public.code_redemptions.client_id IS 'The clients row minted by this redemption. A client is created exactly once, so at most one redemption exists per client (unique index).';

-- One redemption per client — a clients row is minted exactly once.
CREATE UNIQUE INDEX IF NOT EXISTS code_redemptions_client_unique
    ON public.code_redemptions (client_id);

CREATE INDEX IF NOT EXISTS idx_code_redemptions_code_id
    ON public.code_redemptions (code_id);

ALTER TABLE public.code_redemptions ENABLE ROW LEVEL SECURITY;

COMMIT;
