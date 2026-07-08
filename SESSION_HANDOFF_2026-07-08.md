# Session Handoff — 2026-07-08

Replaces `SESSION_HANDOFF_2026-07-01.md` — its threads are resolved or carried below:

- **ORPHEUS-102** (live validation of the gate trio) — still open (Backlog); unchanged this session. Carried under "Recommended pickup."
- **ORPHEUS-90 Decision Log paste** — still owed; carried under "Pending — your manual steps."
- **Untracked-by-intent files** — unchanged; still untracked (see "State of the repo").
- **The gate trio (ORPHEUS-88/100/101)** — a bug it exposed (ORPHEUS-103) is fixed this session; see below.
- **ORPHEUS-8 (apex/marketing)** — the 07-01 handoff listed it as genuinely open pending a product call. That call was made (marketing landing page), the code was found already-built-but-uncommitted in the working tree, and it shipped + closed this session.

This session started from a bug report — Complete LinkedIn uploads failing — traced it to a regression the July 1 gate trio exposed (**ORPHEUS-103**), fixed it, and then wrapped the leftover uncommitted work from prior undocumented sessions: the **ORPHEUS-8** marketing-site + waitlist feature, plus documenting the orphan follow-up commit `610df1a`.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-103 | Missing-file detection rejects Complete archives with member-ID-suffixed CSVs | ✅ **Done this session.** Commit `0135b91`. |
| ORPHEUS-8 | Custom domain / marketing site + waitlist | ✅ **Done this session.** Commit `b701196`. Manual deploy steps remain (below). |
| ORPHEUS-102 | Live validation of the gate trio (88/100/101) | ⏳ Backlog (medium). Needs a fresh export + a real Basic archive. **ORPHEUS-103 must be deployed first** or the freshly-suffixed export will be wrongly rejected. |
| ORPHEUS-99 | Atomic "Publish report" admin action | ⏳ Backlog (low). |
| ORPHEUS-93 / 94 | Resend invalidates prior link / email-mismatch reads as error | ⏳ Backlog (medium / low). |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |
| ORPHEUS-97 | Persist scoring model into config_snapshot | ⏳ Backlog (medium). |
| ORPHEUS-96 | Andrew question: forward-facing CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew's call). |

---

## What this session did

### ORPHEUS-103 — suffix-tolerant missing-file detection — commit `0135b91`

**The bug you reported.** Complete LinkedIn downloads were failing at upload. Root cause: ORPHEUS-87 (2026-06-12) taught the ZIP *read* path (`_read_csv_from_zip`) to tolerate the modern `_<memberid>` filename suffix (`Shares_181682616.csv`), but the *missing-file detection* in `parse_zip` still did an exact-name compare (`found_lower = {basename.lower()}; if "shares.csv" not in found_lower`). So a modern Complete export parsed its behavioral data fine yet was flagged with a CRITICAL MISSING_FILE for Shares.csv (plus warnings for Comments/Reactions).

This was a **latent, benign** spurious flag — until **ORPHEUS-88** (2026-07-01) turned a CRITICAL+MISSING_FILE into a *hard upload block* at POST /jobs gate 2b. From that deploy on, any genuine Complete archive with the modern suffixed filenames was rejected at upload with the "this looks like a Basic archive" 422. The two fixes stacked into a regression.

**Fix.** Extracted the suffix-tolerant match into shared `_csv_name_matches` / `_csv_present` helpers (single source of truth so the read path and the detection path can't drift apart again — that drift is exactly what caused this) and routed all four missing-file checks (Profile/Shares/Comments/Reactions) through `_csv_present`. A genuinely missing Shares.csv (real Basic archive) still flags and still blocks — proven by test.

**Tests.** +3 cases in `backend/tests/test_zip_parser.py`: a suffixed Complete archive produces zero missing-file criticals and `has_blocking_issue is False`; suffixed vs. classic naming agree; a no-Shares archive still flags + blocks. Reproduced in-session against the exact live shape (`Shares_181682616.csv`) before/after.

### ORPHEUS-8 — marketing landing page + waitlist — commit `b701196`

Found already built but uncommitted in the working tree (prior undocumented session). Verified clean (tsc + vitest 60 green), committed, and closed per your call.

- `App.tsx` gains an `isMarketingHost()` branch (new `frontend/src/lib/host.ts`) — on www/apex it renders a separate route tree (public `LandingPage` at `/`, no auth/portal shell); `app.*` keeps the portal; a `/site` path previews the landing page on localhost without spoofing a hostname.
- Waitlist capture (`useWaitlist.ts`) writes browser-direct via the anon Supabase client — no new backend endpoint. Migration **017** creates a write-only `public.waitlist` (anon INSERT-only RLS, no select/update/delete; unique index on `lower(email)`, client treats 23505 as success). Migration **018** adds `first_name` / `last_name` / `interests text[]`.
- HTML prototype `orpheus-landing-v1.html`; assets `animation-screen.jpg` + `signal-report.png` (repo + frontend mirror).

### Documented orphan commit `610df1a`

A 2026-07-01 same-day follow-up to the gate trio (switched the gate rejections to `HTTP_422_UNPROCESSABLE_CONTENT` to silence a Starlette deprecation, `backend/routers/jobs.py`) that landed after the 07-01 handoff and was never documented. Now captured in CLAUDE.md. Code is fine and already on `origin/main`.

### Docs (this wrap commit)

CLAUDE.md: "Active phase" tail extended (103 + 8 + the `610df1a` follow-up); two new "Decisions Made" entries (103, 8). PRODUCT_CONTEXT.md: Frontend build-status row (vitest 54 → 60 + landing page), migration ladder gains 017/018 (flagged not-yet-applied-to-cloud), the Complete-archive ingestion note records the ORPHEUS-103 suffix-tolerant detection fix.

---

## Pending — your manual steps

1. **Push** (see below) — three local-only commits this session: `0135b91` (ORPHEUS-103), `b701196` (ORPHEUS-8), and this wrap commit.
2. **`pytest backend/`** on your terminal to confirm the count (sandbox can't — PyPI blocked). ORPHEUS-103 adds +3 to test_zip_parser; baseline was ~349 after the gate trio → expect ~352.
3. **ORPHEUS-103 deploy** — Railway backend + worker redeploy to pick up `0135b91` (watch the auto-deploy quirk). This unblocks real Complete uploads; do it before ORPHEUS-102.
4. **ORPHEUS-8 go-live** (not code): apply migrations **017 + 018** to cloud Supabase; add `orpheussocial.com` + `www.` in Vercel → Domains and update registrar DNS off the GoDaddy "Launching Soon" placeholder; confirm SSL + that the `isMarketingHost()` branch resolves live (www/apex → landing, `app.` → portal). Test a waitlist submission end-to-end (a row lands, and the client genuinely can't read the list back).
5. **Decision Log paste (ORPHEUS-90)** — still owed. The 4.6-acceptance entry is drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`; paste into the Shared Canon Decision Log when convenient.

---

## Recommended pickup for next session

1. **ORPHEUS-102** (live validation of the gate trio) — now genuinely unblocked once ORPHEUS-103 deploys: a freshly-downloaded (suffixed) Complete export will pass instead of being wrongly rejected. Still needs a real Basic archive for the reject path + folds in Brandon's Complete re-export.
2. **ORPHEUS-8 live smoke** — after DNS/Vercel wiring, confirm the marketing host + waitlist end-to-end (part of step 4 above; worth a ticket-less verification pass).
3. **ORPHEUS-93 / 94** (invite-flow polish, batchable) or **ORPHEUS-86** (upload transport-failure UX).
4. **ORPHEUS-97** (persist scoring model in config_snapshot) — small, self-contained.

---

## Caveats / things that will bite

1. **ORPHEUS-103 is code-only until deployed.** Complete uploads keep failing in prod until Railway backend + worker redeploy `0135b91`. This is the single highest-value deploy right now.
2. **ORPHEUS-102 depends on 103 being live.** If you validate the gate trio against a fresh export before 103 deploys, the suffixed filenames will trip the very bug 103 fixes — you'll get a false "Basic archive" rejection on a valid Complete archive.
3. **Migrations 017 + 018 are committed but NOT applied to cloud.** The waitlist feature will 404/500 on submit until they're applied. No backfill needed (new tables).
4. **Backend pytest unconfirmed from sandbox** (PyPI blocked). ORPHEUS-103 `py_compile` clean; +3 cases. Frontend vitest **60 green**, tsc clean (both run in sandbox).
5. **`.git/*.lock` sandbox quirk bit again** — the `mv`-workaround was needed before each commit; `tmp_obj` unlink warnings are cosmetic. No SSH push from sandbox.
6. **Untracked-by-intent files unchanged** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, and the local `.claude/` cache.
7. **ORPHEUS-8 scope grew past its title.** The ticket read "Configure custom domain on Vercel" but the shipped work is a full marketing page + waitlist; the DNS/Vercel domain config itself is still a manual step (step 4). Closed anyway per Josh's call — the manual steps are captured here so they aren't lost with the ticket.

---

## State of the repo right now (end of session)

Three local-only commits: `0135b91` (ORPHEUS-103 + tests), `b701196` (ORPHEUS-8 feature), and the wrap commit (this handoff + CLAUDE.md + PRODUCT_CONTEXT, retiring `SESSION_HANDOFF_2026-07-01.md`). Working tree otherwise clean except the intentionally-untracked files in caveat 6.

Suggested push (covers all three commits):

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry (drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). ORPHEUS-85 still owes its entry when it ships.
