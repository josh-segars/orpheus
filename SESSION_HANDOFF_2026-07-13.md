# Session Handoff — 2026-07-13

Replaces `SESSION_HANDOFF_2026-07-10.md` — its threads are resolved or carried below:

- **ORPHEUS-105** (UI polish) — shipped 2026-07-10 (`a4a8fa8`/`567b40f`/`cdc1e9e`); documented in CLAUDE.md. Still needs the push + Vercel redeploy to appear in prod (see "Pending — your manual steps"). Carried.
- **ORPHEUS-107** (persist avatar) — still Backlog/low; unchanged. Wants a Tim privacy check first.
- **ORPHEUS-106 deploy** — Railway backend + worker redeploy still pending to clear the on-report banner for any non-Andrew affected row. Carried.
- **ORPHEUS-8 go-live** (migrations 017/018 + Vercel domain/DNS) — still pending, unchanged. Carried.
- **ORPHEUS-90 Decision Log paste** — still owed. Carried.
- **Untracked-by-intent files** — unchanged; still untracked (see "State of the repo").

This session was a single-ticket session: shipped the frontend half of **ORPHEUS-86** (upload-failure UX) and split the backend/diagnosis half out as **ORPHEUS-108**.

**Part 2 (same day):** shipped and closed **ORPHEUS-97** (persist scoring model into `config_snapshot`, commit `2656ee3`); backend pytest confirmed **370 green** (367 → 370). All session commits **pushed** — the part-1 "Push" step is done.

**Part 3 (same day):** shipped and closed **ORPHEUS-93** (resend-invitation messaging, commit `ef55ff7`); backend pytest confirmed **372 green** (370 → 372), frontend vitest **72 green** (69 → 72). Part-3 commits (ef55ff7 + this wrap) need a push.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-86 | Upload UI: catch network-level fetch failures with actionable guidance | 🔄 **In Progress.** Frontend half shipped this session (`4edf25f`). Stays open until it deploys + validates; backend half split to 108. |
| ORPHEUS-108 | Large multipart uploads die at the edge — confirm mechanism + stream to Storage | ⏳ **Backlog (high; filed this session).** Parented to 86. Blocked on Andrew's file-size/time-to-failure data. |
| ORPHEUS-105 | UI polish batch | ✅ Done (2026-07-10). Deploy still pending. |
| ORPHEUS-107 | Persist LinkedIn avatar past OIDC picture-URL expiry | ⏳ Backlog (low). Wants Tim privacy check. |
| ORPHEUS-106 | LIMITED DATA chip on immaterial parse_failure | ✅ Done. Deploy still pending. |
| ORPHEUS-104 | Waitlist admin view: surface `public.waitlist` in /admin | ⏳ Backlog (medium). |
| ORPHEUS-102 | Live validation of the gate trio (88/100/101) | ⏳ Backlog (medium). Unblocked (103 deployed). |
| ORPHEUS-99 | Atomic "Publish report" admin action | ⏳ Backlog (low). |
| ORPHEUS-93 | Resend invalidates prior link | ✅ **Done (part 3, `ef55ff7`).** Deploy pending (rides the same Vercel + Railway redeploys). |
| ORPHEUS-94 | Email-mismatch reads as an error | ⏳ Backlog (low). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |
| ORPHEUS-97 | Persist scoring model into config_snapshot | ✅ **Done (part 2, `2656ee3`).** Worker redeploy pending for the model key to appear on new jobs. |
| ORPHEUS-96 | Andrew question: forward-facing CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew's call). |

---

## What this session did

### ORPHEUS-86 — upload-failure UX, frontend half — commit `4edf25f`

Scoped (with Josh, up front) to the mechanism-independent half. The backend/diagnosis half was split to ORPHEUS-108 because it's blocked on data we don't have (Andrew's fresh ZIP/XLSX size, time-to-failure) and there's no Railway MCP connected to inspect edge limits.

Three pieces, frontend-only:

1. **`apiClient` NetworkError.** New `NetworkError` type + a `safeFetch()` helper that wraps all four fetch calls (`apiGet` / `apiPostJson` / `apiPatchJson` / `apiPostMultipart`). A rejected `fetch()` — transport-level death (connection dropped, DNS, CORS, upload body killed mid-transfer, the "Failed to fetch" symptom) — is normalized to `NetworkError`; a deliberate `AbortError` (React Query unmount, etc.) passes through unchanged so cancellations aren't misclassified as failures.

2. **Actionable copy in GroundworkPage.** New `resolveSubmitError()` maps `NetworkError` → connection/large-archive guidance ("we couldn't reach the server… your Complete archive only needs its data files, the photos/videos aren't used… re-download a smaller export"), `ApiError` → FastAPI `{detail}` (the Basic/stale/parse gate rejections), else generic. The submit-error note now reads as an issue (`--issue`, `role=alert`) instead of muted grey text.

3. **Warn-don't-block size guardrail** [Josh, 2026-07-13]. A non-blocking advisory (`.groundwork-completion-warning`) renders when the selected archive exceeds `LARGE_ARCHIVE_WARN_BYTES` (~150 MB) — Complete exports only need their CSVs; media isn't used in scoring. Chosen over a hard client cap because the real edge limit is unconfirmed and a legitimately large archive should stay submittable.

No prototype backport — the Groundwork prototype (`orpheus-groundwork-v1.html`) is JS-free with a disabled button, so there's no submit behavior to mirror.

Files touched: `frontend/src/lib/apiClient.ts`, `frontend/src/pages/GroundworkPage.tsx`, `frontend/src/pages/GroundworkPage.css`, + new tests `frontend/src/pages/__tests__/GroundworkPage.test.tsx` and `frontend/src/lib/__tests__/apiClient.test.ts`.

### ORPHEUS-97 — persist scoring model into config_snapshot (part 2) — commit `2656ee3`, closed

`build_config_snapshot` (`backend/scoring/config.py`) now always writes a `model` key: defaults to the effective pipeline model (`backend.agents.DEFAULT_MODEL`, which resolves the `ANTHROPIC_MODEL` env override at import time), with an optional explicit `model=` param for experiments. Worker call site unchanged — picks it up automatically. No migration, no backfill (pre-existing rows stay null; 2026-06-12 deploy = the known Sonnet-4/4.6 boundary). +3 pytest cases (`TestConfigSnapshotModel`); backend pytest **370 green** on Josh's terminal. Closed in Plane. First post-worker-redeploy job should show `"model": "claude-sonnet-4-6"` in its snapshot — fold that spot-check into the next fresh-job validation.

### ORPHEUS-93 — resend-invitation messaging (part 3) — commit `ef55ff7`, closed

Live-beta finding (Monika, Ashley): resend rotates `invitation_token`, so every previously-emailed link 401s the moment the new email sends — recipients holding the original email read it as "expired." Rotation stays (correct for security); this ships the messaging around it, all three pieces from the ticket:

1. **Resend email copy** — `format_invitation_email` gains `is_resend: bool = False`; the resend variant adds "This email replaces any invitation we sent you earlier — only the link below will work now" to both bodies. Threaded through `send_invitation_email`; `resend_invitation` passes `is_resend=True`. First-send copy unchanged.
2. **Softened accept-invitation 401** — token-miss detail now leads with the replaced-by-a-newer-invitation likelihood + recovery path (check inbox for the newest email / ask the advisor for a fresh invite). Frontend surfaces `detail` verbatim — no frontend change for this piece. Still doesn't distinguish "never existed" from "rotated away" (leak-resistance unchanged).
3. **Advisor-side inline confirmation** [Josh, 2026-07-13: inline confirm over static note or copy-only] — ClientsPage Resend click arms an inline "replaces the earlier invitation" Confirm/Cancel state (`.advisor-row-confirm`); the mutation fires only on Confirm.

Tests: +2 template cases, `is_resend=True` pinned in the resend happy path, +3 ClientsPage confirm-flow cases (one pre-existing matcher anchored — "Resend invitation" collided with `/send invitation/i`). No prototype backport (resend/accept flows are React-only). Sibling ORPHEUS-94 untouched.

Files touched: `backend/email/templates.py`, `backend/email/resend_client.py`, `backend/routers/clients.py`, `backend/tests/test_email_templates.py`, `backend/tests/test_resend_invitation.py`, `frontend/src/pages/advisor/ClientsPage.{tsx,css}`, `frontend/src/pages/advisor/__tests__/ClientsPage.test.tsx`.

### ORPHEUS-108 — filed (Backlog, high, parented to 86)

The underlying edge-death fix. Carries forward the ORPHEUS-86 symptom, the missing-data checklist (Andrew's fresh ZIP/XLSX size, time-to-failure on the failed request, control retry with older files), and the fix directions (stream the upload to Supabase Storage instead of buffering whole-body in RAM; check whether Railway exposes an edge body-size/timeout knob; hard client cap once the real limit is known). Beta impact high — the ORPHEUS-86 UX makes the failure graceful but doesn't let a high-activity client through.

---

## Pending — your manual steps

1. **Push** — part-3 commits (`ef55ff7` + the part-3 wrap) with the command below. (Parts 1–2 already pushed.)
2. ~~**`pytest backend/`**~~ — **done in part 3: 372 green** (covers the ORPHEUS-93 +2). Frontend vitest **72 green**; `tsc -b` clean.
3. **ORPHEUS-86 deploy + validate** — Vercel picks up the pushed bundle (redeploy manually if it didn't auto-fire). Validate: submitting with the network cut (or throttled to death) shows the connection guidance, not "Failed to fetch"; a >150 MB archive shows the advisory but still submits. Covers ORPHEUS-105's UI batch and ORPHEUS-93's inline resend confirm in the same bundle.
4. **Railway backend + worker redeploy** (carried; now also covers 97 + 93) — picks up `1a6298a` (ORPHEUS-106 banner clear), `2656ee3` (config_snapshot model key on new jobs), and `ef55ff7` (resend email variant + softened 401). Remember the auto-deploy quirk: check the Deployments tab actually took the new commit.
5. **ORPHEUS-8 go-live** (carried, not code): apply migrations **017 + 018** to cloud Supabase; add `orpheussocial.com` + `www.` in Vercel → Domains and update registrar DNS off the GoDaddy placeholder; confirm SSL + the `isMarketingHost()` branch live; test a waitlist submit end-to-end. (Waitlist submit fails until 017/018 are applied.)
6. **Decision Log paste (ORPHEUS-90)** — still owed. Drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`.
7. **ORPHEUS-108 data** — when convenient, grab Andrew's fresh ZIP (+ XLSX) size and the DevTools time-to-failure so 108 can pick a fix.

---

## Recommended pickup for next session

1. **ORPHEUS-104** (waitlist admin view) — pairs naturally with the ORPHEUS-8 go-live; small, self-contained `/admin` addition.
2. **ORPHEUS-108** (edge-death fix) — only once you have the file-size/time-to-failure data; the streaming-to-Storage change is the likely primary fix.
3. **ORPHEUS-102** (live validation of the gate trio) — needs a real Basic archive for the reject path; fold in the ORPHEUS-97 model-key spot-check on the same fresh job.

---

## Caveats / things that will bite

1. **ORPHEUS-86 + 105 are pushed but not validated in prod.** (Part 2 update — the push happened.) Prod shows the new bundle once Vercel redeploys; the ORPHEUS-97 model key only appears on jobs scored after the *worker* redeploys.
2. **ORPHEUS-86 doesn't fix the actual upload failure** — a high-activity client with a large archive still can't submit; the fix just tells them why and suggests a smaller export. The real fix is ORPHEUS-108.
3. **ORPHEUS-106 banner** still needs the backend/worker redeploy to clear on any non-Andrew affected row.
4. **ORPHEUS-8 migrations 017 + 018 still NOT applied to cloud.** Waitlist submit fails until applied.
5. **Sandbox quirks unchanged** — no `pip install` / no pytest (PyPI blocked; `tsc -b` + vitest run fine); no SSH push; `.git/*.lock` needs the `mv`-workaround before each commit; `tmp_obj` unlink warnings are cosmetic; the git-fetch/`origin/main..HEAD` comparison is unreliable from the sandbox (SSH egress blocked), so the push command below is the safe catch-all.
6. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, the local `.claude/` cache, and (new today, from a parallel session) `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now (end of session)

Part 1: one code commit `4edf25f` (ORPHEUS-86, frontend half) + its wrap `41b56e6`. Part 2: one code commit `2656ee3` (ORPHEUS-97) + its wrap `47c06cd`. Part 3: one code commit `ef55ff7` (ORPHEUS-93) + the part-3 wrap (this handoff updated in place + CLAUDE.md/PRODUCT_CONTEXT.md entries). Parts 1–2 are **pushed**; the part-3 commits are not. Working tree otherwise clean except the intentionally-untracked files in caveat 6 (plus three new intentionally-untracked drafts from a parallel session today: `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`).

Suggested push (covers `ef55ff7` + the part-3 wrap commit):

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry (drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). ORPHEUS-85 still owes its entry when it ships.
