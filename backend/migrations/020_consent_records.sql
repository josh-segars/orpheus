-- 020_consent_records.sql  (ORPHEUS-126)
--
-- Two consent records, for the two distinct things a user agrees to.
--
-- 1. public.terms_acceptances — account-level acceptance of the Terms of
--    Service + Privacy Policy, captured by the checkbox on /login before
--    the LinkedIn OIDC hop (Route A, Josh 2026-08-11).
-- 2. public.jobs.upload_consent_at / upload_consent_version — per-upload
--    consent for processing the LinkedIn Data Archive + Analytics Export,
--    captured by the checkbox on the Groundwork submit step.
--
-- Why two, and why separate tables: the ToS/Privacy acceptance is a
-- property of the *account* and is version-scoped (ToS section 19 commits us
-- to 30 days' notice before material changes take effect, so "what did it
-- say when they agreed" has to stay answerable). Upload consent is a
-- property of the *submission* — Art. 6(1)(a) for the archive and Art.
-- 9(2)(a) for whatever incidental special-category content the user
-- authored inside it — and a user may run several reports over time, each
-- of which is its own act of consent. Folding both onto one row would make
-- one of them a lie.
--
-- Art. 7(1) requires us to be able to DEMONSTRATE consent was given, which
-- is the entire reason these are durable rows and not a client-side flag.
--
-- terms_acceptances.user_id is ON DELETE CASCADE against auth.users, so
-- ORPHEUS-124's account deletion removes the acceptance record along with
-- the account. That is deliberate: once the account and its data are gone
-- there is no processing left for the record to justify, and keeping it
-- would itself be personal data retained without a basis (storage
-- limitation). ORPHEUS-124's teardown deletes the auth user last, so the
-- cascade fires at the very end of a successful run.
--
-- NO BACK-FILL (deliberate, Josh 2026-08-11: "new accounts only"). The 14
-- existing accounts get no synthesized acceptance row — a back-filled
-- consent record is a fabricated one, and Art. 7(1) evidence that we
-- invented is worse than an honest gap. They acquire a real row the next
-- time they sign in through /login and tick the box.

-- ---------------------------------------------------------------------------
-- public.terms_acceptances
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.terms_acceptances (
    id               uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id          uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    terms_version    text        NOT NULL,
    privacy_version  text        NOT NULL,
    accepted_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.terms_acceptances IS
    'ORPHEUS-126: account-level acceptance of the Terms of Service + Privacy Policy, recorded from the /login checkbox after the OIDC round trip completes. One row per (user, terms version, privacy version) — a version bump under ToS s19 produces a new row rather than overwriting the old one, so the historical record survives. Deliberately no back-fill for pre-2026-08-11 accounts.';

COMMENT ON COLUMN public.terms_acceptances.terms_version IS
    'Effective date of the Terms of Service the user accepted, as published at /terms. Must match POLICY_VERSIONS in frontend/src/lib/consent.ts and backend/consent_versions.py.';

COMMENT ON COLUMN public.terms_acceptances.privacy_version IS
    'Effective date of the Privacy Policy the user accepted, as published at /privacy.';

-- One row per user per version pair. Re-signing in on an unchanged version
-- is idempotent (the recorder swallows the conflict); bumping either
-- version admits a new row.
CREATE UNIQUE INDEX IF NOT EXISTS idx_terms_acceptances_user_versions
    ON public.terms_acceptances (user_id, terms_version, privacy_version);

CREATE INDEX IF NOT EXISTS idx_terms_acceptances_user_id
    ON public.terms_acceptances (user_id);

-- RLS: a user may read their own acceptance history (so a future DSR/access
-- response under ORPHEUS-127 can be served without service-role), but never
-- write it. All writes go through the service-role client in
-- backend/routers/consent.py — a self-attested consent row the client could
-- INSERT at will would be worthless as Art. 7(1) evidence.
ALTER TABLE public.terms_acceptances ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS terms_acceptances_select_own ON public.terms_acceptances;
CREATE POLICY terms_acceptances_select_own
    ON public.terms_acceptances
    FOR SELECT
    USING (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- public.jobs — per-upload consent
-- ---------------------------------------------------------------------------

ALTER TABLE public.jobs
    ADD COLUMN IF NOT EXISTS upload_consent_at      timestamptz,
    ADD COLUMN IF NOT EXISTS upload_consent_version text;

COMMENT ON COLUMN public.jobs.upload_consent_at IS
    'ORPHEUS-126: server-stamped time at which the client affirmed the upload consent for THIS submission (Art. 6(1)(a) for the archive, Art. 9(2)(a) for incidental user-authored special-category content). Set by POST /jobs/from-uploads, which refuses to mint a job without it. NULL on pre-ORPHEUS-126 jobs — no back-fill, since those submissions genuinely had no consent recorded.';

COMMENT ON COLUMN public.jobs.upload_consent_version IS
    'Privacy Policy version whose s6 / s13 the consent copy reflected at submit time.';

-- claim_next_job (migration 006) returns SELECT *, so both columns flow into
-- the worker's claimed-job dict harmlessly; the worker reads neither.
