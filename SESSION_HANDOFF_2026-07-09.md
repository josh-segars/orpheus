# Session Handoff — 2026-07-09

Replaces `SESSION_HANDOFF_2026-07-08.md` — its threads are resolved or carried below:

- **ORPHEUS-103** (suffix-tolerant missing-file detection) — shipped last session (`0135b91`). Andrew's July 8 report ran clean with suffixed CSVs and zero missing-file criticals, which confirms 103 is **deployed and working** in prod. Closed.
- **ORPHEUS-8** (marketing landing + waitlist) — shipped last session (`b701196`). Its manual go-live ops (migrations 017/018 to cloud, Vercel domain + DNS) are **still pending**; carried under "Pending — your manual steps."
- **ORPHEUS-90 Decision Log paste** — still owed; carried below.
- **Untracked-by-intent files** — unchanged; still untracked (see "State of the repo").

This session started from a bug report — Andrew's report showing a red `LIMITED DATA` "error icon" that was assumed fixed by ORPHEUS-103. It was a *different* mechanism (an over-sensitive quality-gate rule), diagnosed against live cloud data, fixed (**ORPHEUS-106**), and the one affected stored row corrected.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-106 | LIMITED DATA chip fires on immaterial parse_failure | ✅ **Done this session.** Commit `1a6298a`. Deploy pending. |
| ORPHEUS-105 | UI polish: error clipping, Profile Signals icons, feedback CTA anim, broken avatar | ⏳ Backlog (created 2026-07-09; not started). |
| ORPHEUS-104 | Waitlist admin view: surface `public.waitlist` in /admin | ⏳ Backlog (medium). |
| ORPHEUS-102 | Live validation of the gate trio (88/100/101) | ⏳ Backlog (medium). 103 is deployed, so now genuinely unblocked. |
| ORPHEUS-99 | Atomic "Publish report" admin action | ⏳ Backlog (low). |
| ORPHEUS-93 / 94 | Resend invalidates prior link / email-mismatch reads as error | ⏳ Backlog (medium / low). |
| ORPHEUS-86 | Upload UI: catch network-level fetch failures | ⏳ Backlog (medium). |
| ORPHEUS-84 / 85 | Admin invite-advisor / self-serve client sign-up | ⏳ Backlog (medium). |
| ORPHEUS-97 | Persist scoring model into config_snapshot | ⏳ Backlog (medium). |
| ORPHEUS-96 | Andrew question: forward-facing CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew's call). |

---

## What this session did

### ORPHEUS-106 — proportional parse_failure data-limitation — commit `1a6298a`

**The bug.** Andrew's July 8 report (job `8e1f1e81`) showed a red `LIMITED DATA` chip on the reports list plus a client-facing banner. We'd assumed ORPHEUS-103 fixed it — but 103 addresses Complete-archive *rejection*, a different mechanism. His archive parsed perfectly: 336 shares / 2,306 comments / 9,417 reactions, zero missing-file criticals.

**Root cause.** The report's only data-limiting issue was a *warning*-level `parse_failure`: "66 comment(s) have unparseable dates and will be excluded from scoring" — **66 of 2,306 = 2.9%**, the benign LinkedIn date-format tail first noted in ORPHEUS-87. ORPHEUS-88's `is_data_limited` counted *any* `parse_failure` warning as data-limiting regardless of magnitude, so a negligible drop branded the whole report. His July 8 job was the **only row system-wide** with `data_limited=true` (June 26 and earlier predate the ORPHEUS-88 gate — migration 016, no backfill — so they show nothing).

**Fix.** `QualityIssue` gains an optional `total_rows`; `backend/ingestion/zip_parser.py` stamps it (`len(share_rows)` / `len(comment_rows)` / `len(reaction_rows)`) at the three unparseable-date sites. `DataQualityReport.data_limitation_issues()` (`backend/models/quality.py`) now counts a `parse_failure` only when `rows_affected / total_rows > PARSE_FAILURE_MATERIAL_FRACTION` (0.10). The WARNING is still recorded in the stored report / admin view (audit trail preserved) — it just no longer trips the client banner/chip below the threshold. A magnitude-unassessable issue (no counts, e.g. legacy stored reports) stays conservative = data-limiting, so ORPHEUS-88's blocking behavior is unchanged.

**Tests.** +3 cases in `backend/tests/test_quality.py`: 66/2,306 → not data-limited (Andrew's exact shape); 800/2,000 → still data-limited; no-totals → conservative fallback stays data-limited. The pre-existing parse_failure test (no `total_rows`) still passes via the fallback.

**Live data correction (cloud).** Job `8e1f1e81`: `jobs.data_limited` → false (the chip cleared immediately — it reads the denormalized flag), and the stored `quality_report` parse_failure back-patched with `total_rows: 2306` so the on-report banner (recomputed live from `is_data_limited` in `GET /jobs/{id}`) also clears once the backend redeploys. Guarded UPDATE, only the one affected row.

---

## Pending — your manual steps

1. **Push** — one local-only commit this session: `1a6298a` (ORPHEUS-106). Command below. (If the three 2026-07-08 commits somehow weren't pushed, this sweeps them too — though the clean-parse of Andrew's July 8 report indicates 103/8 already deployed.)
2. **`pytest backend/`** — you already confirmed green this session (+3 in `test_quality.py`). No further action unless you want a fresh count for the record.
3. **ORPHEUS-106 deploy** — Railway backend + worker redeploy to pick up `1a6298a`. The reports-list chip is already gone (denormalized flag); the on-report **banner** clears only after the backend redeploys.
4. **ORPHEUS-8 go-live** (unchanged from 2026-07-08, not code): apply migrations **017 + 018** to cloud Supabase; add `orpheussocial.com` + `www.` in Vercel → Domains and update registrar DNS off the GoDaddy placeholder; confirm SSL + the `isMarketingHost()` branch resolves live; test a waitlist submission end-to-end.
5. **Decision Log paste (ORPHEUS-90)** — still owed. Drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`; paste into the Shared Canon Decision Log when convenient.

---

## Recommended pickup for next session

1. **ORPHEUS-105** (UI polish batch) — self-contained frontend/CSS: error-message clipping behind the waveform hero, Profile Signals check/cross → Material icons, feedback-CTA animation, and the broken LinkedIn avatar (`onError` → initials fallback). All visible on the report/chrome; batchable.
2. **ORPHEUS-102** (live validation of the gate trio) — now genuinely unblocked (103 is deployed). Needs a real Basic archive for the reject path + folds in Brandon's Complete re-export.
3. **ORPHEUS-104** (waitlist admin view) — pairs naturally with the ORPHEUS-8 go-live.
4. **ORPHEUS-97** (persist scoring model in config_snapshot) — small, self-contained.

---

## Caveats / things that will bite

1. **ORPHEUS-106 is code-only until deployed.** Andrew's chip already cleared via the data correction, but any *other* report with a >0 unparseable-date tail keeps computing `data_limited` under the old rule until Railway backend + worker redeploy `1a6298a`. (In practice Andrew's was the only affected row.)
2. **The banner vs. chip split.** The reports-list/roster/admin **chip** reads the denormalized `jobs.data_limited` (corrected in data now). The on-report **banner** recomputes live from the stored `quality_report`; it needs both the code deploy *and* the `total_rows` back-patch (done for `8e1f1e81`) to clear. Pre-deploy, expect the banner to still show on Andrew's report while the chip is gone — resolves on redeploy.
3. **ORPHEUS-8 migrations 017 + 018 still NOT applied to cloud.** Waitlist submit will fail until applied. No backfill needed.
4. **Backend pytest confirmed green on Josh's terminal this session** (+3). Sandbox still can't run pytest (PyPI blocked) — `py_compile` clean only.
5. **`.git/*.lock` sandbox quirk bit again** — `mv`-workaround used before commit; `tmp_obj` unlink warnings are cosmetic. No SSH push from sandbox.
6. **Untracked-by-intent files unchanged** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, and the local `.claude/` cache.

---

## State of the repo right now (end of session)

One local-only commit this session: `1a6298a` (ORPHEUS-106 + tests). This wrap commit adds the new handoff + CLAUDE.md + PRODUCT_CONTEXT updates and retires `SESSION_HANDOFF_2026-07-08.md`. Working tree otherwise clean except the intentionally-untracked files in caveat 6.

Suggested push (covers both commits):

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry (drafted at `outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). ORPHEUS-85 still owes its entry when it ships.
