# Session Handoff — 2026-08-03

The metric-accuracy batch is closed. Replaces `SESSION_HANDOFF_2026-07-30.md`, retired in this commit:

- **ORPHEUS-117 + 112 + 113 all closed** on the live acceptance test the 07-30 handoff named as the top pickup. Evidence is job `0007607e`.
- **`861d581`** — a post-closure amendment to 113's mechanism, from Andrew's live review.
- **ORPHEUS-121 filed (high)** — the residue of that review: the agent states aggregate counts matching no input value at all.
- **Two of Andrew's label findings landed on ORPHEUS-114** as registry scope, and **one of them needs pushback** rather than implementing as asked. Detail below.
- **Carried unchanged:** ORPHEUS-119's live-verification remainder, ORPHEUS-120, ORPHEUS-114/115/116, ORPHEUS-111, the ORPHEUS-90 Decision Log paste, ORPHEUS-107, the Andrew comms items, the ORPHEUS-122 sr-only score question, untracked-by-intent files.

---

## What closed, and what the evidence actually was

Job **`0007607e-e817-44b0-8a25-1a95cf97086e`** (Andrew's profile, same dataset as `b902bd06`, worker on `18d6356`):

| Check | Result |
|---|---|
| ORPHEUS-112 denominator | `2,852.8` — old code would have written 875.4 from the same inputs |
| ORPHEUS-113 milestones | `2.7` posts/wk · `3,550` impressions/post · `3,550` followers · `3.1%` engagement; no digit in any label |
| ORPHEUS-117 raw units | 0 hits |
| Stale/fabricated (`875`, `331`, `2,394`) | 0 hits |
| Composite | 82.25 / Resonant — **unchanged**, confirming the batch never touches a scored input |

The ORPHEUS-113 values had been written into the ticket comment from the code *before* the pipeline ever ran with them, and the live run reproduced them exactly — determinism confirmed against prediction, not just across runs.

**Regeneration scope resolved [Josh]:** only Andrew's report was corrected. Of the 40 stored jobs carrying the bad impressions figure, 24 are correctable (1.08×–75×, mean 8.95×) and 16 would go null — 9 pre-ORPHEUS-88 Basic archives with no `Shares.csv` at all (one was reporting *14,489 impressions per post* for a member with no parsed posts), 7 genuinely dormant members with posts in the archive but none in the window. The rest keep the old figure as history; `c2df921` is the tool if that changes.

---

## The methodological finding — read this before trusting any future clean run

Andrew's 2026-07-27 accuracy review declared bugs B, D and the raw units **fixed**. They weren't. That review ran against job `301ba109`, which executed on pre-fix code (the four commits were unpushed at the time). What he saw was the agent not reproducing three stochastic behaviours on one run.

The split is the useful part:

- **Deterministic bugs survived** — the computed denominator gives the same wrong answer every time, so bug A and its dependent C were still present, which is what he correctly reported.
- **Stochastic prose bugs "resolved"** — the model simply chose differently. `301ba109` shows **zero raw-unit hits on pre-fix code**, and its milestone set dropped the impressions target while emitting `"4,000+" / "Followers (from current 3,212)"` instead: bug B wearing a different metric.

**So a clean run is not evidence for the prose class of bug.** This is the entire case for why 117 and 113 fix in code rather than by prompt instruction — an unlabeled `raw_value` never reaches the prompt, and milestone values are computed with digit-banned labels, so both are unrepresentable rather than merely unlikely. It's recorded in 117's closing comment and CLAUDE.md too, because the next person reading "acceptance met" can't otherwise tell a structural pass from a lucky one.

---

## `861d581` — the followers amendment, and why the invariant was wrong

Andrew flagged the followers milestone (3,550) as inconsistent with the report's own 17.5/week growth rate, which projects to ~3,440. He diagnosed it as the impressions target bleeding into the followers field.

**Not bleeding** — 2,852.8 × 1.25 and 3,212 × 1.10 independently both round to 3,550 on the nearest-50 step. A coincidence, and one that had already been flagged as cosmetic when 113 closed.

**But the check underneath his diagnosis found a real gap.** A flat multiplier on an absolute baseline can land *below* the client's unaided trajectory: 3,000 followers at 50/week reach ~3,650 in 90 days, while 3,000 × 1.10 = 3,300 — a milestone asking them to do worse than nothing. That is ORPHEUS-113's own bug one level up, and its `target > baseline` guarantee cannot see it, because 3,300 does exceed 3,000.

Followers now projects the measured weekly rate across `MILESTONE_HORIZON_WEEKS` and stretches it by `FOLLOWER_TREND_STRETCH`, making the guarantee `target > unaided projection` — enforced structurally the same way, with rounding that would pull the target back onto the projection bumping a step clear. Swept 8 baselines × 8 rates, no failures. Falls back to the flat multiplier when no growth rate was measured, since there is then no trend to contradict. Followers is the only milestone with a printed trend alongside it, so the other three are unchanged. On Andrew's data 3,550 → **3,500**, which also dissolves the collision he spotted.

**Generalizable:** "target exceeds baseline" is the wrong invariant whenever the report prints a rate for the same metric. Noted on ORPHEUS-114 as a milestone-vs-metric reconciliation identity.

---

## ORPHEUS-121 (new, high) — fabricated aggregates

Reconciling every figure in `301ba109`'s two behavioral narratives against stored data:

| In the report | Actual | |
|---|---|---|
| "6,204 recorded comment actions" | 1,815 comments + 4,389 reactions | real value, **wrong label** — fixed by 117 |
| "2,394 total comments" | 2,437 parsed / 2,365 usable / 1,815 in-window | **matches nothing** |
| "331 posts in the archive" | 341 | **matches nothing** (Andrew didn't catch this one) |
| 2.2 posts/wk · 3,212 followers · 17.5/wk · 18,479 top post · July 18 | all correct | ✅ |

**The pattern is the actionable part:** every number supplied to the agent as an explicitly labelled input is correct; every number it derived or recalled from surrounding context is garbled. So this is fabrication, not ORPHEUS-115's mislabeling — and ORPHEUS-96 already shipped a grounding constraint that didn't catch it, which is why the fix is a check rather than more prompt language.

Fix folded into **ORPHEUS-114**: extract every numeric token from generated prose and require each to match a whitelisted measured value within tolerance, rejecting and retrying otherwise. The golden-source map and unit registry 114 already builds *are* the whitelist, so building it separately would mean two copies of the canonical value list. Watch for legitimate non-metric numbers (years, ordinals, "90 days", "top 50").

---

## Andrew's two label findings — one needs pushback

Both are on ORPHEUS-114 as (b) registry work, because in each case the fix is the **prompt label at source**, not a correction applied to prose afterwards.

1. **"Average engagement rate ... across posts" is an aggregate.** `avg_engagement_rate` computes `total_engagements / total_impressions`; the prompt hands the agent `Avg engagement rate: 2.7%`, so the prose is faithful to a misleading label. Fix the prompt line to "Overall engagement rate (total engagements ÷ total impressions)". Renaming the field touches the wire contract and frontend, so that's separable. Andrew called it no-urgency.

2. **The active-weeks relabel he asked for would introduce an error.** He observed the 42-of-52 figure described three ways and asked for all three aligned to "zero-post weeks" per the golden fixtures. But these are **two different metrics**:
   - **Continuity** (a scored sub-dim): weeks with **3+ posts or comments**, 42 of 52 → 80.8%. The narrative's phrasing is accurate to `DIM2_CONTINUITY_ACTIVE_THRESHOLD = 3`.
   - **`zero_post_week_pct`**: weeks with **no posts**, shares only → 19% → 81%.

   They look like one metric only because they nearly coincide on his data. A client who comments heavily in weeks they don't post would separate them sharply. Correct fix: two distinct accurate labels, and correct only the cheat sheet's "zero-activity weeks", which is genuinely wrong since "activity" implies comments. **Don't implement this one as filed.**

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-117 / 112 / 113 | Raw units / impressions denominator / invented milestones | ✅ **Done** — live acceptance on `0007607e` |
| ORPHEUS-121 | Narrative agent fabricates aggregate counts in prose | ⏳ Backlog (high) — **new**; fix folded into 114 |
| ORPHEUS-114 | Reconciliation gate + metric source/unit registry | ⏳ Backlog (high) — now carries prose-number reconciliation + Andrew's two label findings + the milestone-vs-metric identity |
| ORPHEUS-120 | Advisory draft gate doesn't hold on the read path | ⏳ Backlog (high) — dependency of 114 |
| ORPHEUS-115 | Prose mislabels | ⏳ Backlog (medium) — needs 114's registry |
| ORPHEUS-116 | "What Travels" reach-driver evidence layer | ⏳ Backlog (medium) — largest scope, gated on Andrew |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — awaiting a first-time completion under an `is_individual = true` advisor |
| ORPHEUS-111 | 50 MB cap vs 150 MB advisory vs 200 MB copy | ⏳ Backlog (medium) |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | (publish action / email-mismatch / invite-advisor / self-serve signup / avatar) | ⏳ Backlog, unchanged |
| ORPHEUS-96 follow-up | CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew) |

Baselines: backend pytest **434 green**, frontend vitest **79 green** (untouched this session).

---

## Pending — your manual steps

1. **Push.** This wrap commit only; `861d581` and everything before it are already pushed.
2. **Andrew's live report `0007607e` carries the pre-`861d581` followers milestone** (3,550, not 3,500). Everything else on it is current. `c2df921` corrects it in place without adding a fourth report to his list — and would sweep the impressions figure on `b902bd06` / `301ba109` at the same time if you want his history consistent.
3. **Decision Log paste (ORPHEUS-90)** — still owed (`outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`). Carried since 06-24; worth deciding whether it's actually going to happen.
4. **Delete the duplicate ORPHEUS-117 comment** — the first closing comment posted double-escaped (same Plane MCP quirk as ORPHEUS-118 on 07-27); the correct repost sits directly below it. Also the ORPHEUS-118 duplicate if it's still there.
5. **Andrew comms, carried:** (a) Nicole's report is the first real-client exercise of the ORPHEUS-63 score-0 posture; (b) Jenn hasn't retried since the MIME fix; (c) Jodie needs an onboarding nudge; (d) ORPHEUS-120's open question — should the feedback ask wait for advisory publication at all? (e) the ORPHEUS-122 sr-only composite-score question. **New:** (f) the growth factors and the ORPHEUS-112 metric-definition caveat, both framework-adjacent and his to rule on.

---

## Recommended pickup for next session

1. **ORPHEUS-120 + ORPHEUS-114 together**, per the standing cross-link — design the publish boundary once. 120 is small alone (filter `status` for client callers in `_build_result_payload`, plus an "advisor is reviewing this" surface) but shouldn't land twice, and 114's reconciliation identities are the regression net.
2. **ORPHEUS-121 rides 114** — it's the prose half of the same gate, and `QUANTITATIVE_METRIC_LABELS` is already the first five entries of 114's unit registry, so promote and extend rather than start fresh.
3. **ORPHEUS-115** after 114 — depends on the label registry. Andrew's two label findings are recorded on 114, one with the pushback above.
4. **ORPHEUS-119's remainder** rides the next real first-time completion. No action until then.
5. **ORPHEUS-116** last: largest scope, medium priority, gated on Andrew.
6. Then ORPHEUS-111, ORPHEUS-107, ORPHEUS-94, ORPHEUS-99.

---

## Caveats / things that will bite

1. **A clean run does not prove a stochastic prose bug is fixed.** The single most expensive lesson of this batch — it cost a false all-clear from Andrew and nearly cost regression tests pinned to three live bugs. When validating narrative behaviour, check the deterministic fingerprint (`avg_impressions_per_post`, milestone label digits), not the absence of a phrasing.
2. **Verify the deploy before asking anyone to re-run.** `301ba109` was generated on pre-fix code because the commits were unpushed, and nothing in the data said so until the fingerprint was checked. Railway's auto-deploy is intermittent; the **worker** is the service that matters for pipeline output.
3. **Growth factors are PROVISIONAL and framework-adjacent.** `MILESTONE_GROWTH_FACTORS`, `MILESTONE_HORIZON_WEEKS`, `FOLLOWER_TREND_STRETCH` are all target-setting judgments — Andrew's to tune, not ours to quietly change.
4. **`python-multipart` is still in `requirements.txt` unused**, deliberately, comment-flagged. Fold the removal into the next backend commit; don't give it a dedicated deploy.
5. **Resend's dashboard still lists the provider as GoDaddy.** The zone is Vercel's. **Do not use Resend's Auto configure button.**
6. **Email outages are invisible from inside the product.** Both send paths swallow `EmailSendError` by design; the last one ran ~10 days undetected. Monitoring scope is folded into ORPHEUS-119.
7. **A returning or advisory client completing a report is NOT an ORPHEUS-119 verification event.**
8. **The part-1-partial sub-question is open** (on ORPHEUS-110): if LinkedIn's 10-minute partial download carries the Complete fingerprint files, a part-1 upload would pass as zero-activity. Needs a real part-1 sample.
9. **Abandoned staging uploads still aren't swept** — Jenn's orphaned `analytics.xlsx` from 07-17 sits in `{client}/staging/`. Harmless at current volume.
10. **Sandbox quirks unchanged** — no pip/pytest (Josh's terminal); no SSH push, and `git fetch` fails too, so the origin comparison at session start is against a stale ref (note it updates when Josh pushes from his own terminal, since the mount *is* his working repo); `.git/*.lock` needs the `mv` workaround before each commit; no DNS resolver (use the DoH snippet in `CREDENTIALS.md`); `rm` inside the mount needs delete permission granted first. **New:** `mcp__plane__create_issue` truncates long `description_html` and fails JSON parsing — keep new-ticket descriptions compact and put the detail in a follow-up comment.
11. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, `.claude/`, `outputs/`, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now

One code commit this session (`861d581`, already pushed) plus this wrap commit. Working tree otherwise clean except the intentionally-untracked files in caveat 11 — `outputs/` now also holds a superseded draft reply to Andrew, written before Josh went live with him.

**Prod config beyond source:** the four DNS records in the Vercel zone remain the only live state not captured in the repo — which is why the `CREDENTIALS.md` record table exists.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk`
- **Andrew's accuracy review (2026-07-27, job `301ba109`):** `160KdpyALqd94Wt36DvDFkh9FYR1sn_673lzw6NMCfvc`
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry. ORPHEUS-85 still owes its entry when it ships.
