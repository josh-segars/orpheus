# Session Handoff — 2026-07-21

Replaces `SESSION_HANDOFF_2026-07-17.md` — its headline threads all closed:

- **ORPHEUS-108 / 86 / 102 live validation: DONE** (2026-07-20 session). 86 + 102 closed; 108's sole remainder is deleting the legacy multipart shim.
- **Supabase file-size limit check: DONE** — the uploads bucket caps at **50 MB** (free-tier ceiling), below the 150 MB advisory and 200 MB copy; reconciliation filed as **ORPHEUS-111**.
- **Carried unchanged:** ORPHEUS-8 go-live (Vercel domain/DNS), ORPHEUS-90 Decision Log paste, ORPHEUS-107 (avatar persistence), untracked-by-intent files.

Note: this handoff also covers the **undocumented 2026-07-20 evening session** that shipped ORPHEUS-109 (`6a85b91`) and pushed both code commits — it left no handoff of its own.

---

## What these sessions did (2026-07-20 → 07-21)

### Combined live validation (closed ORPHEUS-86 + ORPHEUS-102)

Josh drove the browser, Claude verified DB/log-side. Browser-direct happy path proven organically — Andrew's submission `b902bd06` (staging→move object timestamps are the new flow's signature, pipeline clean, `config_snapshot->>'model'` populated = ORPHEUS-97 ✓). Gate trio proven with synthetic archives built in-session: Basic filename, renamed-Basic content backstop, stale date — all 422 with correct copy, zero job rows minted, staging cleaned after each reject. `data_limited` surfaces credited to the ORPHEUS-106 live false positive (declined to manufacture a degraded job in prod). First live `GET /admin/waitlist` ✓ (0-row empty state renders).

### Beta upload-failure triage — three real clients, two root causes

1. **Windows ZIP MIME (Deborah Boyd, Jenn Kellogg).** Windows registers `.zip` as `application/x-zip-compressed`; supabase-js sends the File's OS-reported MIME (the hook's `contentType` option loses on the FormData path); the uploads bucket allowlist rejected it → `InvalidMimeType` 400 on **every Windows ZIP upload**, wearing the misleading connection copy. Root-caused via storage logs (Logs Explorer now uses the unified-logs dialect — `from logs where source = 'storage_logs'`; the old BigQuery-style `unnest` queries backend-error). **Hotfixed in prod** (allowlist SQL, [Josh, 2026-07-20]) then hardened under **ORPHEUS-109** (`6a85b91`): `useCreateJob` rebuilds both files with canonical MIME (name + lastModified preserved for the filename gate), new `UploadRejectedError` surfaces Storage's own reason, migration 019 pins bucket allowlist + 50 MB limit in source (applied to cloud, idempotent).
2. **Zero-activity Complete exports (Nicole Persun — confirmed never-posts).** LinkedIn omits empty per-activity CSVs entirely, so her genuine Complete export has no Shares.csv/Comments.csv and gate 2b misread it as a renamed Basic archive — a permanent dead-end with misleading copy. **ORPHEUS-110** (`a02d5fb`): Complete-fingerprint check in `parse_zip` (≥2 of Ad_Targeting / Inferences_about_you / SearchQueries / Logins / Ads Clicked / Security Challenges, suffix-tolerant; Rich_Media deliberately excluded) reclassifies absent behavioral CSVs as EMPTY_DATA — non-blocking per ORPHEUS-88, still data-limiting. Profile.csv absence still blocks; renamed Basic still rejected.

**Live proof, same day:** Deborah submitted clean 18:24 UTC (`014dd517`); Nicole 19:46 UTC (`a8a47ff8`, `data_limited=true`, full narrative set). Both fixes validated on the exact clients who were blocked. **Jodie Uhl** checked too: no failure — she stalled pre-upload (zero questionnaire rows, last activity 07-14); just needs a nudge.

### Plane

Closed: **86, 102** (07-20), **109, 110** (07-21, after live proof + pytest). Filed: **109, 110, 111**. Still In Progress: **108** (shim removal only). The 07-17 handoff's "102 = Backlog" line was stale (Plane had it In Progress since 07-01) — moot now.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-86 | Upload UI network-failure guidance | ✅ Done (validated live by Deborah's error rendering) |
| ORPHEUS-102 | Gate trio live validation | ✅ Done (+ 97 model key + waitlist folded in) |
| ORPHEUS-109 | Windows ZIP MIME hardening | ✅ Done (`6a85b91`; Deborah's clean retry is the proof) |
| ORPHEUS-110 | Zero-activity Complete exports pass gate 2b | ✅ Done (`a02d5fb`; Nicole's report is the proof) |
| ORPHEUS-108 | Browser-direct upload | 🔄 In Progress — **only** the legacy multipart `POST /jobs` + `_read_upload` deletion remains (`_apply_submission_gates` makes it a clean cut). |
| ORPHEUS-111 | 50 MB cap vs 150 MB advisory vs 200 MB copy | ⏳ Backlog (medium). No observed archive near 50 MB yet (Andrew 1.8 MB, Deborah ~495 KB). |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | (publish action / email-mismatch / invite-advisor / self-serve signup / avatar) | ⏳ Backlog, unchanged. |
| ORPHEUS-96 follow-up | CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew). |

Test baselines: backend pytest **392 green**, frontend vitest **79 green**, `tsc -b` clean.

---

## Pending — your manual steps

1. **Push** — the wrap commit only (`a02d5fb` + `6a85b91` are already on origin). Command below.
2. **Andrew comms:** (a) **Nicole's report is live to her** — narratives auto-published at pipeline completion, and it's the first real-client exercise of the ORPHEUS-63 score-0 posture (mostly-zero behavioral sub-dims + data-limited banner). If he hasn't read it via his roster uncloak, sooner is better. (b) Jenn hasn't retried — she's unblocked since the MIME fix, tell her to try again. (c) Jodie needs an onboarding nudge, not a fix.
3. **ORPHEUS-8 go-live, remaining** — Vercel Domains + registrar DNS off the GoDaddy placeholder; then verify `isMarketingHost()` + a waitlist submit e2e.
4. **Decision Log paste (ORPHEUS-90)** — still owed (`outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md` from the 06-24 session).

---

## Recommended pickup for next session

1. **Legacy multipart removal** — delete `POST /jobs` multipart + `_read_upload`, drop the pytest cases that exercise it, close ORPHEUS-108. Small, satisfying, fully unblocked.
2. **ORPHEUS-111** — pick the real cap (50 MB is the free-tier ceiling; no observed archive is close) and align advisory + 413 copy + docs.
3. Then the backlog: ORPHEUS-107 (avatar), ORPHEUS-94, ORPHEUS-99.

---

## Caveats / things that will bite

1. **Nicole's narratives auto-published at completion** — if the intent was that advisory reports gate on admin publish (ORPHEUS-98's model), that gate did not hold for her job. Check whether her flow counted as self-serve-style publication or whether the draft gate needs enforcement. Also verify whether her report-ready email went out and with which survey URL.
2. **The part-1-partial sub-question is open** (noted on ORPHEUS-110): if LinkedIn's 10-minute partial download carries the fingerprint files, a part-1 upload would pass as zero-activity. Get a real part-1 sample before leaning harder on the fingerprint set.
3. **Abandoned staging uploads still aren't swept** — Jenn's orphaned `analytics.xlsx` from 07-17 sits in `{client}/staging/`. Harmless at current volume.
4. **Supabase Logs Explorer changed dialect** (unified logs): `from logs where source = 'storage_logs'`, not the old per-collection tables — the old `unnest` examples backend-error. `log_attributes` carries `error.raw` / `error.message` for storage 4xxs.
5. **Sandbox quirks unchanged** — no pip/pytest (Josh's terminal); no SSH push; `.git/*.lock` needs the `mv` workaround before each commit.
6. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, `.claude/`, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now

Code commits `a02d5fb` (ORPHEUS-110) + `6a85b91` (ORPHEUS-109) are pushed. This wrap commit (handoff swap + CLAUDE.md/PRODUCT_CONTEXT.md refresh) is the only unpushed commit. Working tree otherwise clean except the intentionally-untracked files in caveat 6. Prod config beyond source: none remaining — the 07-20 bucket-allowlist hotfix is now captured by migration 019.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry. ORPHEUS-85 still owes its entry when it ships.
