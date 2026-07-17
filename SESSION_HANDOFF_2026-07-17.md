# Session Handoff — 2026-07-17

Replaces `SESSION_HANDOFF_2026-07-15.md` — no code shipped this session (ops only), but its deploy-state threads moved materially:

- **The carried Vercel + Railway redeploys are DONE.** Found already satisfied at session start: both Railway services and Vercel production were already running the 07-15 handoff commit (`1befd68`), so the 07-13/07-15 bundle (ORPHEUS-86 frontend half, 93, 97, 104, 105, 106, 108) has been live in prod since ~07-15. All three services were then redeployed *again* today with the new survey URL (see below), so this is doubly moot.
- **ORPHEUS-108 / 86 / 102 live validation** — still owed, but genuinely unblocked now that deploys are confirmed live. Carried.
- **ORPHEUS-8 go-live** — Vercel domain + registrar DNS wiring still the only remaining step. Carried.
- **ORPHEUS-90 Decision Log paste** — still owed. Carried.
- **ORPHEUS-107** (avatar persistence, wants Tim privacy check) — still Backlog. Carried.
- **Supabase file-size limit check** (07-15 pending step 4) — still owed. Carried.
- **Untracked-by-intent files** — unchanged.

---

## What this session did — beta survey URL rotation (no ticket, ops only)

The closed-beta feedback Google Form URL changed. New canonical URL (the `?usp=publish-editor` copy-tracker param was trimmed):

```
https://docs.google.com/forms/d/e/1FAIpQLSdsqHIJJ_f3wF0vW9A45OgWRbllG-_YRIo09eZXfgS-sSxGvw/viewform
```

Updated in all three places the URL lives (it's env-only — nothing in the repo tracks it):

1. **Railway** — `BETA_SURVEY_URL` is a **shared project variable** referenced by both services as `${{shared.BETA_SURVEY_URL}}` (one edit covers backend + worker; this wasn't documented anywhere before — now noted in CLAUDE.md's deploy-platform section). Edited via Project Settings → Shared Variables; both services redeployed and came back Online.
2. **Vercel** — `VITE_BETA_SURVEY_URL` exists as **two separate entries** (Production and Preview, not one combined row); both updated, production redeployed (fresh build, no cache).
3. **Local** — `frontend/.env.local` (untracked).

**Verified live:** the nav "Tell Us What You Think" link on `app.orpheussocial.com` carries the new href.

Side effect worth knowing: today's Railway redeploy also delivered the worker redeploy that 07-15 listed as owed (ORPHEUS-97 config_snapshot model key, ORPHEUS-106 banner clear) — the worker is now definitely on current code.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-108 | Large multipart uploads die at the edge | 🔄 In Progress — code live in prod since 07-15; needs live validation (a real submission, ideally Andrew's large archive), then legacy multipart removal + close. |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | 🔄 In Progress — closes with 108's live validation. |
| ORPHEUS-102 | Live validation of the gate trio (88/100/101) | ⏳ Backlog (medium). Fold in the ORPHEUS-97 model-key spot-check + first live `GET /admin/waitlist`. |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | (publish action / email-mismatch / invite-advisor / self-serve signup / avatar) | ⏳ Backlog, unchanged. |
| ORPHEUS-96 | Andrew question: forward-facing CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew's call). |

---

## Pending — your manual steps

1. **Push** — the wrap commit only. Command below.
2. **Supabase file-size limit check** — dashboard → Storage settings: confirm the global upload limit accommodates real Complete archives (binds the browser-direct path).
3. **ORPHEUS-8 go-live, remaining** — Vercel Domains: add `orpheussocial.com` + `www.`; registrar DNS off the GoDaddy placeholder; confirm SSL + the `isMarketingHost()` branch; test a waitlist submit e2e.
4. **Decision Log paste (ORPHEUS-90)** — still owed. Drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`.

---

## Recommended pickup for next session

1. **ORPHEUS-108 live validation** — everything is deployed; just needs a real submission through the new flow. Success closes 86, unlocks legacy-multipart removal, then close 108.
2. **ORPHEUS-102** — gate-trio validation (needs a real Basic archive for the reject path) + ORPHEUS-97 model-key spot-check + live `GET /admin/waitlist`.
3. **ORPHEUS-8 go-live finish** — after your DNS step, a session can verify the hostname branch + waitlist submit.

---

## Caveats / things that will bite

1. **The legacy multipart POST /jobs is still live** — remove it (and `_read_upload`) once 108 validates; `_apply_submission_gates` makes it a clean deletion.
2. **Abandoned staging uploads aren't swept** — follow-up only if the bucket accumulates.
3. **TUS resumable upload is the escalation path** if very large files still fail browser→Storage.
4. **Old emailed survey links** — any already-sent report-ready email carries the old form URL; if the old form is closed/unpublished, those links dead-end. Only matters if recipients click stale emails.
5. **Sandbox quirks unchanged** — no `pip install` / pytest (Josh's terminal); no SSH push; `.git/*.lock` needs the `mv`-workaround before each commit.
6. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, the local `.claude/` cache, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`. (Note: `Survey_Closed_Beta_Feedback_2026-06-08.md` + the .gs generator describe the *old* form — stale but harmless; refresh only if the survey content itself changed.)

---

## State of the repo right now

No code commits this session. This wrap commit (handoff swap + CLAUDE.md note) is the only unpushed commit. Test baselines unchanged from 07-15: backend pytest **387 green**, frontend vitest **76 green**. Working tree otherwise clean except the intentionally-untracked files in caveat 6.

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
