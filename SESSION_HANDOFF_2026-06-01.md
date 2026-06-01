# Session Handoff — 2026-06-01

Retires `SESSION_HANDOFF_2026-05-31_part2.md`. Its recommended pickup options were ORPHEUS-21 (still blocked on Andrew's Forward Brief revisions), ORPHEUS-45 (still no concrete use case), and a handful of carry-forwards. This session shipped **ORPHEUS-25** (cloud Supabase + prod LinkedIn OIDC) and back-applied migration 013 to cloud as a carry-forward fix; the other open threads remain in the same state.

Unusual session shape: ops/config only, no code commits. Single Plane ticket closed; one handoff commit covers the doc refresh.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-25 | Cloud Supabase + prod LinkedIn provider configuration | ✅ Done. No code commits — entirely external configuration. Carry-forward: migration 013 applied to cloud Supabase in the same session. |
| ORPHEUS-31 | `/admin` stopgap (email-allowlisted) | ✅ Done last session (`fa380c9`). |
| ORPHEUS-43 | Pin Railway build command in source | ✅ Done two sessions ago. |
| ORPHEUS-22 | Server-side per-dimension band classification | ✅ Done three sessions ago. |
| ORPHEUS-52 | PortalNav identity cluster | ✅ Done four sessions ago. |
| ORPHEUS-51 | Signal Score hero restructure + per-band waveforms | ✅ Done five sessions ago. |
| ORPHEUS-21 | Backend: Extend SubDimensionScore with narrative fields | ⏸ Hold pending Andrew's Forward Brief revisions. Unchanged. |
| ORPHEUS-44 | Live e2e walk-through of invite + advisor flow | 🟢 **UNBLOCKED** (ORPHEUS-25 was the gate). Now the obvious top pickup. |
| ORPHEUS-45 | Advisor admin UI: 'Edit' action on client list rows | ⏳ Forward-Brief-safe. UX. Unchanged. |
| ORPHEUS-48 | Multi-tenant branding | ⏸ Deferred. Unchanged. |
| ORPHEUS-40 / 41 / 42 | Stripe, disconnect, account mgmt | ⏸ Beta-deferred. Unchanged. |

No other tickets touched this session.

---

## What this session shipped

### ORPHEUS-25 — Cloud Supabase + prod LinkedIn OIDC wiring (no code commits)

Ticket was filed 2026-04-21 as Phase 2 of the LinkedIn Auth rollout (ORPHEUS-23) and had been the standing gate on ORPHEUS-44 (live e2e). Acceptance criteria explicitly configuration-only — no code change required.

**LinkedIn Developer app (production).** New app created at https://www.linkedin.com/developers/apps, distinct from the local dev app from ORPHEUS-24. **Sign In with LinkedIn using OpenID Connect** product enabled (auto-approved). Authorized redirect URL: `https://yqxuddkixzjruxtdjxpr.supabase.co/auth/v1/callback`. OAuth 2.0 scopes (`openid`, `profile`, `email`) auto-added by the OIDC product.

**Cloud Supabase (`yqxuddkixzjruxtdjxpr`, project URL `https://yqxuddkixzjruxtdjxpr.supabase.co`).**

- Authentication → Providers → **LinkedIn (OIDC) enabled**, Client ID + Client Secret pasted from the LinkedIn app. Note: LinkedIn's Auth tab labels these as "Client ID" / "Primary Client Secret" in some views and "API Key" / "API Secret Key" in others — they're the same values, just different vocabulary.
- Authentication → URL Configuration: **Site URL** = `https://app.orpheussocial.com`. **Redirect URLs** allowlist contains `https://app.orpheussocial.com/**` so OAuth callbacks land on any sub-route. Default Vercel `*.vercel.app` URL is **not** in the redirect allowlist — if a future deploy ever needs to test against the raw Vercel preview URL, add it explicitly.
- Authentication → Email: **Confirm email OFF** (already was — LinkedIn OIDC's `email_verified` claim is the trust signal, not a Supabase double-opt-in).

**Env propagation.** Anon key uses the **legacy `eyJhbG...` JWT format**, not the newer `sb_publishable_*` key — matches the backend's JWKS-verification path in `backend/auth.py`; switching to publishable keys would require a separate refactor. Vercel got the four `VITE_*` vars (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` pointed at the Railway backend, `VITE_ADMIN_EMAILS`) and a redeploy was triggered so the new bundle picked up the values. Railway (both backend and worker services) got `SUPABASE_ANON_KEY` confirmed/added and `ADMIN_EMAILS` added fresh (new requirement since ORPHEUS-31 shipped 2026-05-31). Pre-existing `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `APP_BASE_URL` / `FRONTEND_ORIGINS` / `ANTHROPIC_API_KEY` / `RESEND_API_KEY` already pointed at this project from prior deploy work.

**Carry-forward fix in the same session: migration 013 applied to cloud.** The handoff caveat from 2026-05-29 (ORPHEUS-49 band rename) listed migration `013_band_rename` as not-yet-applied to prod. Resolved in-session:

1. Audited the cloud migration ladder via the Supabase MCP. Cloud had 5 entries: `initial_schema`, `rls_policies`, `v2_scoring_columns`, `rename_narratives_dimension_to_section`, `clients_invitation_columns`. Repo has 12 active migrations (001 + 003 + 004 + 005 + 006 + 008 + 011 + 012 + 013; 007 + 009 + 010 historical).
2. The apparent gaps (005 quality_report, 006 claim_next_job RPC, 011 questionnaire_align_to_spec) turned out to be folded into the `initial_schema` snapshot rather than missing — verified by direct schema inspection: `ingested_data.quality_report` present, `claim_next_job` RPC function present in `information_schema.routines`, `questionnaire_responses` table shape matches the ORPHEUS-33 simplified spec (`client_id` / `answers` JSONB / `updated_at`).
3. Confirmed `scores_band_check` was still on the pre-rename labels (`Weak/Emerging/Moderate/Strong/Exceptional`), `scores` table had 0 rows.
4. Applied migration 013 via the Supabase MCP. Drops the old `scores_band_check` CHECK, runs the CASE update (no-op on empty rows), re-adds the CHECK with `Dissonant/Untuned/Tuning/Tuned/Resonant`, updates the column comment.
5. Post-apply verification: `pg_get_constraintdef('scores_band_check')` returns `CHECK (band IS NULL OR band IN ('Dissonant', 'Untuned', 'Tuning', 'Tuned', 'Resonant'))`. ✅

**Verification.**

- Pre-013 schema audit: all 8 `public.*` tables present, RLS enabled, 0 rows across the board.
- Post-013: constraint swap confirmed via direct query.
- LinkedIn OAuth kickoff verified live: `https://app.orpheussocial.com/login` → "Sign in with LinkedIn" button → consent screen renders with the prod LinkedIn app name (not the local dev app). Did not push through to full callback — that's the e2e walk under ORPHEUS-44.

**Scope decisions locked.**

- Site URL = the production custom domain (`app.orpheussocial.com`), not the `*.vercel.app` URL. DNS already pointed at Vercel before this session.
- Anon key uses the legacy JWT format; switching to `sb_publishable_*` keys is a separate refactor.

**Files touched.** None — entirely external configuration. Migration 013 source was already in repo at `backend/migrations/013_band_rename.sql`.

### New tickets filed

None this session.

---

## Recommended pickup for next session

**ORPHEUS-44 (live e2e walk-through of invite + advisor flow)** — newly unblocked by ORPHEUS-25. The right "first day in production" smoke. Suggested test plan:

1. From the `/admin` surface (Andrew or Josh signed in via the `ADMIN_EMAILS` allowlist), confirm the cloud DB is empty and the admin shell loads.
2. Run an advisor invite end-to-end:
   - Sign in as an advisor (the same advisor user can run both halves of the flow if needed).
   - From `/advisor/clients`, invite a test client email.
   - Confirm the Resend email lands; click the invite link.
   - Complete LinkedIn OAuth from the invite landing page.
   - Confirm the `clients` row is linked (`user_id` populated, `invitation_status = accepted`) and the post-acceptance redirect lands the client on Welcome/Groundwork.
3. Walk a full client journey: groundwork → questionnaire → LinkedIn ZIP + XLSX upload → analysis → Signal Score → Forward Brief.
4. Switch back to advisor view; confirm the "View report" uncloak (ORPHEUS-46) surfaces the complete job.
5. Edit a narrative from `/admin` (ORPHEUS-31); confirm the edit persists across reload.
6. Note any rough edges; file follow-up tickets.

ORPHEUS-44 is intentionally a manual e2e — it's the surface that catches the "this works in isolation but the wiring between systems has a quirk" class of issue.

**Alternative pickups (unchanged from 2026-05-31_part2):**

- **ORPHEUS-21 (sub-dim narrative fields)** if Andrew's Forward Brief revisions have landed. Same rationale as prior handoffs.
- **ORPHEUS-45 (Edit action on client rows).** Concrete-but-small advisor UX win.
- **Loading-flicker polish on the PortalNav cluster** (carry-forward).
- **"Prepared for [own name]" on `/advisor/clients` + `/admin`** (carry-forward).
- **CONVENTIONS.md update for same-day handoffs** (carry-forward from 2026-05-30_part3).
- **`frontend/src/assets/waves.jpg` cleanup** (carry-forward from 2026-05-30_part2).
- **AdminRoute tightening** (carry-forward from 2026-05-31_part2).
- **Anon-key format migration to `sb_publishable_*`** (new). Currently the codebase JWKS-verifies the legacy JWT anon key. Supabase's newer publishable-key format would require an `auth.py` refactor. Trivially low-urgency; the legacy format isn't going away soon.

---

## Caveats / things that will bite

1. **ORPHEUS-44 is now the load-bearing next ticket.** Until it runs, "the production stack works" is still a hypothesis. ORPHEUS-25 only verified OAuth kickoff to the LinkedIn consent screen — not the consent → callback → row-creation chain. Plan to run it before any new client / advisor onboards for real.
2. **`ADMIN_EMAILS` / `VITE_ADMIN_EMAILS` are now populated in cloud env.** Drift between Vercel and Railway lists = either the route is shown to a user who 403s on every request (Vercel ahead of Railway) or the route is hidden from a user who could call it directly (Railway ahead of Vercel). Worth a one-line sanity check on both sides whenever the admin list changes.
3. **Anon key is the legacy JWT format.** The publishable-key format Supabase introduced isn't supported by the current `backend/auth.py` JWKS path. If a Supabase dashboard hint nudges toward "rotate to a publishable key", that's a code change, not a one-click swap.
4. **Site URL is `app.orpheussocial.com`, NOT the `*.vercel.app` URL.** OAuth redirects from a `*.vercel.app` preview deploy will fail with "redirect URL mismatch". If a preview-environment test is ever needed, add the preview origin to the Supabase Redirect URLs allowlist explicitly.
5. **Migration 013 is now applied to cloud.** Replaces handoff caveat #11 from 2026-05-31_part2. The fresh-DB recipe is now `001 + 011 + 012 + 013` (updated in `PRODUCT_CONTEXT.md` Build Status).
6. **Sandbox proxy blocks `*.supabase.co`.** When verifying cloud Supabase via raw HTTP from the sandbox, requests hit a 403 from the proxy's allowlist filter (`X-Proxy-Error: blocked-by-allowlist`). The Supabase MCP path works fine; only direct `curl`/`web_fetch` against the project URL is blocked. Verification of the live Supabase auth settings endpoint needs Josh's terminal or browser.
7. **Sandbox can't run pytest** (PyPI blocked) — carry-forward. No backend tests added this session, so the ~180-green baseline from ORPHEUS-31 still stands without re-verification.
8. **`.git/*.lock` workaround still needed before each commit** — same pattern as every prior session.
9. **Compliance drafts at repo root remain intentionally untracked** — Privacy Policy / TOS / DPA drafts. Don't `git add` them. As of this commit they sit alongside `Signal_Score_Dimensions_Reference_2026-05-20.md` (also intentionally untracked).
10. **Andrew's Forward Brief revisions are still pending** — holds ORPHEUS-21. Once they land, ORPHEUS-31's narrative editor naturally extends.

---

## State of the repo right now (end of session)

After the handoff commit this skill produces:

```
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (<handoff-sha> Session handoff: 2026-06-01. Retire 2026-05-31_part2.)

Untracked (intentionally — all in .gitignore):
  LinkedIn_BD_DPA_Review_2026-05-07.md
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
  Signal_Score_Dimensions_Reference_2026-05-20.md
```

`SESSION_HANDOFF_2026-05-31_part2.md` is retired in this commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Latest Decision Log entries:** 2026-05-29 Signal Score redesign + dark mode (ORPHEUS-50); 2026-05-29 band rename (ORPHEUS-49); 2026-05-20 ownership clarification + canon adoption. (No new Decision Log entry drafted this session — ORPHEUS-25 is execution against the LinkedIn Auth architecture already documented in ORPHEUS-23 / `Decision_LinkedIn_Auth_2026-04-21.md`, not a new cross-stakeholder decision.)
