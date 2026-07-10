# Session Handoff — 2026-07-10

Replaces `SESSION_HANDOFF_2026-07-09.md` — its threads are resolved or carried below:

- **ORPHEUS-106** (proportional parse_failure) — shipped last session (`1a6298a`), documented in CLAUDE.md "Decisions Made." Still needs the Railway backend + worker redeploy to clear the on-report banner for any *other* affected row (Andrew's chip already cleared via the live data correction). Carried under "Pending — your manual steps."
- **ORPHEUS-8 go-live** (migrations 017/018 + Vercel domain/DNS) — still pending, unchanged. Carried below.
- **ORPHEUS-90 Decision Log paste** — still owed. Carried below.
- **Untracked-by-intent files** — unchanged; still untracked (see "State of the repo").

This session was a UI-polish session: shipped **ORPHEUS-105** (three commits), then diagnosed the broken-avatar root cause against live cloud `auth.users` and filed **ORPHEUS-107** for the durable fix.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-105 | UI polish: error clipping, Material icons, feedback CTA, avatar fallback | ✅ **Done this session.** Commits `a4a8fa8` / `567b40f` / `cdc1e9e`. |
| ORPHEUS-107 | Persist LinkedIn avatar so it survives the OIDC picture-URL expiry | ⏳ Backlog (low; filed this session). |
| ORPHEUS-106 | LIMITED DATA chip on immaterial parse_failure | ✅ Done (last session). Deploy still pending. |
| ORPHEUS-104 | Waitlist admin view: surface `public.waitlist` in /admin | ⏳ Backlog (medium). |
| ORPHEUS-102 | Live validation of the gate trio (88/100/101) | ⏳ Backlog (medium). Unblocked (103 deployed). |
| ORPHEUS-99 | Atomic "Publish report" admin action | ⏳ Backlog (low). |
| ORPHEUS-93 / 94 | Resend invalidates prior link / email-mismatch reads as error | ⏳ Backlog (medium / low). |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |
| ORPHEUS-97 | Persist scoring model into config_snapshot | ⏳ Backlog (medium). |
| ORPHEUS-96 | Andrew question: forward-facing CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew's call). |

---

## What this session did

### ORPHEUS-105 — UI polish batch — commits `a4a8fa8`, `567b40f`, `cdc1e9e`

Four items from the ticket plus two in-session refinements. Frontend/CSS only; backend untouched.

1. **Error clipping behind the waveform hero.** `.quality-banner` now gets `position:relative; z-index:2` so it paints above the `.score-hero` waveform. The hero forms a `z-index:0` stacking context and its billboard image bleeds ~100px down over the following content, which is what clipped the data-limited/error copy. Fix is scoped to the banner (the only element rendered in the bleed zone); the load-error `.page-status` path renders without a hero, so it was never affected. (`SignalScorePage.css` + `orpheus-signal-score.html`.)

2. **Material iconography everywhere.** New shared `frontend/src/components/icons/MaterialIcon.tsx` — a path-map + `size` prop, renders `currentColor`, always carries a base `.material-icon` class (`vertical-align:middle`, inert inside flex parents). Every text-glyph icon was converted: Profile Signals ✓/✕ → `check`/`close`, back-link chevrons (Step1/Step2/Questionnaire), the Groundwork row chevron + completion check, the report action-button arrows, the Cheat Sheet / Account back arrows, and the questionnaire checkbox check. The pre-existing sub-dim caret was refactored onto the component too, for one system. **Scope call (Josh, in-session):** "all text-only iconography" was read to include the *form-control* checkbox check, not just standalone affordance icons — trivially reversible if that's too broad. Prototype backported across all affected pages.

3. **Banner left border.** Dropped `border-left-width:4px` so all four sides of `.quality-banner` are the uniform 1px.

4. **Broken avatar → initials fallback.** `PortalNav` `<img>` gets an `onError` handler that flips to the initials chip, plus a `useEffect` reset when the picture URL changes. +2 vitest cases (photo renders when a `picture` claim is present; `onError` → initials). Root cause of the breakage is a separate follow-up — see ORPHEUS-107 below.

5. **Feedback CTA.** Relabelled "Closed Beta Feedback" → "Tell Us What You Think" (nav + all 9 prototype pages). The static pill now runs a left→right accent **wave**: a `::before` gradient band sweeps across in ~1.1s then holds off-screen for the rest of the cycle (once per ~4.5s), paused on hover/focus and disabled under `prefers-reduced-motion`. This is the tuned version — the first pass (`a4a8fa8`) filled 55% of a 2s cycle at 0.16 alpha, which Josh flagged as reading continuous + too faint, so `cdc1e9e` slowed the cadence and widened/brightened the band (0.45 alpha). CSS-only in the shared `orpheus-styles.css`, so React + prototype share it.

### ORPHEUS-107 — filed (Backlog, low)

The broken avatar was root-caused (not a code bug): the LinkedIn OIDC `picture` claim is a **signed, time-limited** `media.licdn.com` URL. Supabase captures it only at OAuth sign-in and never refreshes it on token refresh, so the stored URL freezes at the user's last `last_sign_in_at` and eventually expires. Verified against live cloud `auth.users` (2026-07-10): the `e=` expiries fall on weekly Thursday-UTC boundaries and track each user's last sign-in — the Jul-2 and Jul-9 cohorts are already expired (Josh's own URL: `e=1782950400` = 2026-07-02, expired 8 days before the report), everyone else expires on a rolling Thursday. The ORPHEUS-105 `onError` fallback covers the beta; ORPHEUS-107 is the durable fix (persist the photo bytes ourselves at sign-in and serve from a stable URL). Flagged a privacy check with Tim before shipping (we'd be storing a copy of the profile photo).

---

## Pending — your manual steps

1. **Push** — three local commits this session: `a4a8fa8`, `567b40f`, `cdc1e9e` (all ORPHEUS-105), plus this wrap commit. Command below. (The ORPHEUS-105 avatar fallback only takes effect in prod once these deploy — pre-deploy, prod still shows the broken image.)
2. **`pytest backend/`** — not needed this session (frontend-only, backend untouched). Frontend vitest confirmed **62 green** in the sandbox.
3. **ORPHEUS-106 deploy** (carried from 2026-07-09) — Railway backend + worker redeploy to pick up `1a6298a`. Andrew's chip already cleared via the data correction; the on-report banner clears on redeploy for any other affected row.
4. **ORPHEUS-8 go-live** (carried, not code): apply migrations **017 + 018** to cloud Supabase; add `orpheussocial.com` + `www.` in Vercel → Domains and update registrar DNS off the GoDaddy placeholder; confirm SSL + the `isMarketingHost()` branch live; test a waitlist submit end-to-end. (Waitlist submit fails until 017/018 are applied.)
5. **Decision Log paste (ORPHEUS-90)** — still owed. Drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`; paste into the Shared Canon Decision Log when convenient.

---

## Recommended pickup for next session

1. **ORPHEUS-104** (waitlist admin view) — pairs naturally with the ORPHEUS-8 go-live; small, self-contained `/admin` addition.
2. **ORPHEUS-102** (live validation of the gate trio) — needs a real Basic archive for the reject path + folds in Brandon's Complete re-export.
3. **ORPHEUS-97** (persist scoring model in config_snapshot) — small, self-contained.
4. **ORPHEUS-107** (persist avatar) — only if durable avatars matter for beta; the initials fallback already covers it, and it wants a Tim privacy check first.

---

## Caveats / things that will bite

1. **ORPHEUS-105 is unpushed/undeployed.** The avatar fallback, error-clipping fix, Material icons, and wave animation are all in local commits only. Prod won't show any of it until the push + Vercel redeploy.
2. **Avatar photos will keep expiring** until ORPHEUS-107 ships. The fallback makes that graceful (initials, not a broken icon), but expect most users' photos to be absent over time — that's expected, not a regression.
3. **ORPHEUS-106 banner** still needs the backend/worker redeploy to clear on any non-Andrew affected row (chip already reads the corrected denormalized flag).
4. **ORPHEUS-8 migrations 017 + 018 still NOT applied to cloud.** Waitlist submit fails until applied.
5. **Sandbox quirks unchanged** — no `pip install` / no pytest (PyPI blocked; `tsc -b` + vitest run fine); no SSH push; `.git/*.lock` needs the `mv`-workaround before each commit; `tmp_obj` unlink warnings are cosmetic.
6. **Untracked-by-intent files unchanged** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, and the local `.claude/` cache.

---

## State of the repo right now (end of session)

Three local commits this session, all ORPHEUS-105: `a4a8fa8`, `567b40f`, `cdc1e9e`. This wrap commit adds the new handoff + the CLAUDE.md updates (Active-phase tail + a Decisions Made entry) and retires `SESSION_HANDOFF_2026-07-09.md`. Working tree otherwise clean except the intentionally-untracked files in caveat 6.

Suggested push (covers all session commits + the wrap):

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry (drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). ORPHEUS-85 still owes its entry when it ships.
