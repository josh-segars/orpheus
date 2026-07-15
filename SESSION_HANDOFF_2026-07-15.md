# Session Handoff — 2026-07-15

Replaces `SESSION_HANDOFF_2026-07-13.md` — its threads are resolved or carried below:

- **ORPHEUS-93 / 97 / 86 (frontend half) / 105 / 106** — all shipped and documented; their Vercel + Railway redeploys are still the pending manual step (carried).
- **ORPHEUS-8 go-live** — the "migrations 017/018 not applied to cloud" caveat was **stale**: this session verified both are applied (ladder shows 2026-07-02, harmless idempotent re-apply 2026-07-08) and the table shape matches the migration files exactly (8 columns, RLS + anon-INSERT-only policy, unique index, 0 rows). Remaining go-live steps are the Vercel domain + registrar DNS wiring only. Carried, reduced.
- **ORPHEUS-108** — still Backlog (high), blocked on Andrew's file-size/time-to-failure data. Carried.
- **ORPHEUS-107** — still Backlog (low), wants Tim privacy check. Carried.
- **ORPHEUS-90 Decision Log paste** — still owed. Carried.
- **Untracked-by-intent files** — unchanged (see "State of the repo").

This session was a single-ticket session: shipped and closed **ORPHEUS-104** (waitlist admin view), and cleared the stale 017/018 caveat en route.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-104 | Waitlist admin view: surface `public.waitlist` in /admin | ✅ **Done (this session, `cd6eb94`).** Live once Railway backend redeploys. |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | 🔄 In Progress. Frontend half shipped 07-13 (`4edf25f`); stays open until it deploys + validates. Backend half = 108. |
| ORPHEUS-108 | Large multipart uploads die at the edge | ⏳ Backlog (high). Blocked on Andrew's file-size/time-to-failure data. |
| ORPHEUS-102 | Live validation of the gate trio (88/100/101) | ⏳ Backlog (medium). Unblocked; fold in the ORPHEUS-97 model-key spot-check. |
| ORPHEUS-93 / 97 / 105 / 106 | (resend messaging / config_snapshot model / UI polish / LIMITED DATA proportionality) | ✅ Done, deploys pending (same Vercel + Railway redeploys). |
| ORPHEUS-99 | Atomic "Publish report" admin action | ⏳ Backlog (low). |
| ORPHEUS-94 | Email-mismatch reads as an error | ⏳ Backlog (low). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |
| ORPHEUS-107 | Persist LinkedIn avatar past OIDC picture-URL expiry | ⏳ Backlog (low). Wants Tim privacy check. |
| ORPHEUS-96 | Andrew question: forward-facing CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew's call). |

---

## What this session did

### ORPHEUS-104 — waitlist admin view — commit `cd6eb94`, closed

Shape locked with Josh up front: **section below the existing AdminPage panes** (not a tab/toggle — no nav state on a stopgap page), **header stats included** (signup count + beta_access / live_workshop breakdown, computed client-side from the fetched rows).

- **Backend** — `GET /admin/waitlist` in `backend/routers/admin.py` (`AdminWaitlistEntry` / `ListAdminWaitlistResponse` models), gated by the existing `get_current_admin`. Single round trip, newest-first. The service-role client is *required*, not just conventional: `public.waitlist` is anon-INSERT-only with no select policy (migration 017), so RLS bypass is the only read path. Nullable-tolerant for migration-017-era email-only rows (names → None, NULL interests → []).
- **Frontend** — `useAdminWaitlist` hook in `useAdmin.ts` (admin-allowlist gated like the other admin hooks, keyed `['admin', 'waitlist']`) + `WaitlistSection` / `WaitlistTable` in `AdminPage.tsx` with interest display labels (`beta_access` → "Beta access"; unknown values pass through verbatim since the column is extensible without migration) and a "No signups yet" empty state. Two small CSS additions (`.admin-waitlist-stats`, `.admin-chip-interest`).
- **Tests** — +3 pytest in `test_admin.py` (happy path incl. single-round-trip assertion, 017-era row tolerance, empty table); +2 vitest in `AdminPage.test.tsx` (rows + stats + labels + email-only fallback; empty state). The `vi.mock('../../hooks/useAdmin')` factory gained the `useAdminWaitlist` entry — remember it's a whole-module mock, so any new hook AdminPage consumes must be added there.

Files touched: `backend/routers/admin.py`, `backend/tests/test_admin.py`, `frontend/src/hooks/useAdmin.ts`, `frontend/src/pages/AdminPage.tsx`, `frontend/src/pages/AdminPage.css`, `frontend/src/pages/__tests__/AdminPage.test.tsx`.

### Cloud finding — migrations 017/018 were already applied

Asked to apply them for ORPHEUS-104's dependency, the preflight found them already in the cloud ladder (`017_waitlist` + `018_waitlist_fields` at 2026-07-02, re-applied 2026-07-08 — both idempotent, duplicate harmless). Verified live: all 8 columns, `rls_enabled=true`, only policy `waitlist_insert_anon`, `waitlist_email_unique` index present, **0 rows** (consistent with the marketing page not being live on the apex yet). PRODUCT_CONTEXT's Build Status row corrected. Nothing was applied this session — read-only verification only.

---

## Pending — your manual steps

1. **Push** — this session's commits with the command below (also covers the 07-13 part-3 commits if they haven't gone yet).
2. **Vercel redeploy** — picks up ORPHEUS-104's admin waitlist section + the carried 07-13 bundle (86 frontend half, 93 inline resend confirm, 105 UI batch).
3. **Railway backend + worker redeploy** (carried) — backend now also serves `GET /admin/waitlist`; worker redeploy still owed for the ORPHEUS-97 model key + 106 banner clear. Watch the auto-deploy quirk (check the Deployments tab took the new commit).
4. **ORPHEUS-8 go-live, remaining** — Vercel Domains: add `orpheussocial.com` + `www.`; update registrar DNS off the GoDaddy placeholder; confirm SSL + the `isMarketingHost()` branch live; test a waitlist submit end-to-end (migrations are ready — the submit should now succeed, and the new /admin section will show it).
5. **Decision Log paste (ORPHEUS-90)** — still owed. Drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`.
6. **ORPHEUS-108 data** — Andrew's fresh ZIP (+ XLSX) size and DevTools time-to-failure, when convenient.

---

## Recommended pickup for next session

1. **ORPHEUS-102** (live validation of the gate trio) — needs a real Basic archive for the reject path; fold in the ORPHEUS-97 model-key spot-check and the first live `GET /admin/waitlist` check on the same pass.
2. **ORPHEUS-8 go-live finish** — domain/DNS is manual (yours), but a session can verify the hostname branch + waitlist submit end-to-end right after, and the new /admin section closes the loop on seeing the row.
3. **ORPHEUS-108** — once the file-size/time-to-failure data exists; streaming-to-Storage is the likely primary fix.

---

## Caveats / things that will bite

1. **Nothing from 07-13 or today is validated in prod yet** — the Vercel + Railway redeploys are the gate. `GET /admin/waitlist` 404s in prod until the backend redeploy.
2. **ORPHEUS-86 doesn't fix the actual upload failure** — a high-activity client with a large archive still can't submit; ORPHEUS-108 is the real fix.
3. **The waitlist has 0 rows** — the /admin section will show its empty state until the marketing page is live on the apex (ORPHEUS-8 DNS step).
4. **AdminPage test mock is whole-module** — `vi.mock('../../hooks/useAdmin')` must list every hook AdminPage imports; a future hook addition without a mock entry breaks all seven cases with an unhelpful "not a function".
5. **Sandbox quirks unchanged** — no `pip install` / pytest (runs on Josh's terminal); no SSH push; `.git/*.lock` needs the `mv`-workaround before each commit; `tmp_obj` unlink warnings cosmetic; origin-comparison unreliable from the sandbox, so the push command below is the safe catch-all.
6. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, the local `.claude/` cache, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now (end of session)

One code commit `cd6eb94` (ORPHEUS-104) + the wrap commit (this handoff, CLAUDE.md + PRODUCT_CONTEXT.md refresh, 07-13 handoff retired). Backend pytest **375 green** (372 → 375, Josh's terminal), frontend vitest **74 green** (72 → 74), `tsc -b` clean. Working tree otherwise clean except the intentionally-untracked files in caveat 6.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry (drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). ORPHEUS-85 still owes its entry when it ships.
