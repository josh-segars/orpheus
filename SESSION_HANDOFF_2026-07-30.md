# Session Handoff — 2026-07-30

Short session, one ticket. Replaces `SESSION_HANDOFF_2026-07-27.md`, retired in this commit — most of what it described is closed or has moved into CLAUDE.md "Decisions Made":

- **ORPHEUS-122 (new): landing copy revision shipped** (`da591f2`). Andrew's 2026-07-27 copy doc applied to both landing surfaces.
- **The 07-27 handoff's top recommendation is half-done and it didn't know it.** ORPHEUS-117 → 112 → 113 shipped code the same evening the wrap was written, in a session that left no handoff. All three are correctly In Progress; the shared acceptance test hasn't been run. Details below — **this is the most important thing on this page.**
- **Carried unchanged from 07-27:** ORPHEUS-119's live-verification remainder, ORPHEUS-120, ORPHEUS-114/115/116, ORPHEUS-111, the ORPHEUS-90 Decision Log paste, ORPHEUS-107, the Andrew comms items, untracked-by-intent files.

---

## The 112/113/117 state, since it isn't what the last handoff implies

The 07-27 wrap discovered ORPHEUS-112–117 during the wrap itself and wrote them up as the recommended-but-unstarted next batch. Between that wrap and this session, four commits landed:

| Commit | Ticket | What it did |
|---|---|---|
| `274aa97` | ORPHEUS-117 | Label the measured signal instead of leaking raw units |
| `2ac7bc8` | ORPHEUS-112 | Divide impressions by posts, not by days |
| `c308e40` | ORPHEUS-113 | Compute milestone values instead of generating them |
| `c2df921` | 112/113/117 | In-place report regeneration script |

**All three tickets are still In Progress in Plane, and that is correct** — the code is in, but the batch's shared acceptance test (regenerate `b902bd06`; assert no "875", no raw internal units, no milestone below its own baseline) has not been run. `c2df921` exists precisely to run it.

**So the next session's pickup is running the acceptance test, not re-implementing the batch.** Read the four commits before touching any of it.

Worth knowing about `c2df921` because its safety properties change the regeneration calculus: it re-runs stages 3 and 4 only, against the job's already-stored `ingested_data`, and overwrites that job's `scores` and `narratives` rows — so a corrected report *replaces* the wrong one instead of appearing beside it as a second job. Stages 1 and 2 are deliberately skipped (parsing is unchanged by this batch and the stored Dim 1 / Dim 4 rubric sub-dim scores are reused), so the composite is guaranteed identical and no rubric calls are spent. It is dry-run by default, snapshots the existing rows before any write with a `--restore` that puts them back verbatim, asserts the composite is unchanged and aborts if it moved, and runs verification **before** the write so a bad generation leaves the delivered report untouched.

That resolves the 07-27 handoff's "a re-run mints a new job, so a client would see two reports" objection. What it does **not** resolve is *which* delivered reports to correct — every report with impressions carries the bad value, not just Andrew's. Still open.

Also still open, and possibly Andrew's rather than an implementation detail: ORPHEUS-112's metric-definition caveat. The numerator spans all live content while the denominator is posts-published-in-window, so 2,853 is an approximation with a client-facing label attached.

---

## ORPHEUS-122 — landing copy revision (`da591f2`)

Andrew's revised copy (Google Doc, 2026-07-27 revision) applied to `frontend/src/pages/LandingPage.tsx` and `orpheus-landing-v1.html`.

**The doc's vocabulary rules are load bearing and now live in the LandingPage docstring** so a future edit doesn't quietly undo them: *diagnostic* = the mode of analysis, *assessment* = the offering you run, *report* = the document you receive; "action plan" names the function and "quick reference card" the presentation; the product is referred to by name, never as "we"; zero em dashes.

Beyond the straight text swaps:

- **Pricing became Access.** `id="pricing"` → `id="access"` (nothing linked it); cards are Beta Assessment (Available now) and Live Cohorts (Pre-release). The `landing-pricing-*` class names stay — renaming them churns both stylesheets for no behavioral gain.
- **Interest labels renamed, stored values deliberately not.** The form and the `/admin` waitlist section read "Beta Assessment" / "Live Cohorts"; rows still persist `beta_access` / `live_workshop`. Same display-map split as `SUB_DIM_DISPLAY_NAMES`. Renaming the persisted strings would orphan every waitlist row written before this pass. A LandingPage test now pins that the access card and the interest checkbox say the same thing, so the label and the offering name can't drift apart.
- **`.landing-fineprint` is gone.** It held the dropped expectations paragraph and had no remaining users; replaced by `.landing-founders` for the new founder-credibility block rather than left behind as dead CSS.

**Three of the copy doc's four open items resolved [Josh, 2026-07-30]:** headline takes the doc's new wording in the built design's title case ("Your Presence Speaks / Make It Sing"); step 3 is "Your Action Plan" for parallelism with "Your Report"; the "outcomes will vary" expectations paragraph is **dropped** rather than deferred to Tim.

Verification: `tsc -b` clean, frontend vitest **79 green** (unchanged count — four assertions naming old copy were retargeted, not added to). The two files were diffed against the doc section by section, which caught a missing terminal period on the How It Works header and a "you have earned" where the doc has "you've earned".

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-122 | Landing page copy pass (2026-07-27 revision) | ✅ Done |
| ORPHEUS-117 / 112 / 113 | Raw units / impressions denominator / invented milestones | 🔄 **In Progress — code shipped, acceptance test not yet run** |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — cause established; awaiting live verification + monitoring |
| ORPHEUS-120 | Advisory draft gate doesn't hold on the read path | ⏳ Backlog (high) — dependency of 114 |
| ORPHEUS-114 / 115 | Reconciliation gate + unit registry / prose mislabels | ⏳ Backlog (high / medium) — 114 pairs with 120; 115 needs 114's registry |
| ORPHEUS-116 | "What Travels" reach-driver evidence layer | ⏳ Backlog (medium) — largest scope, gated on Andrew |
| ORPHEUS-111 | 50 MB cap vs 150 MB advisory vs 200 MB copy | ⏳ Backlog (medium) |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | (publish action / email-mismatch / invite-advisor / self-serve signup / avatar) | ⏳ Backlog, unchanged |
| ORPHEUS-96 follow-up | CTA as sub-dim 1B criterion | ⏳ Deferred (framework, Andrew) |

Baselines: backend pytest **391 green** (unverified this session — no backend changes), frontend vitest **79 green**.

---

## Pending — your manual steps

1. **Push.** Two commits: `da591f2` (ORPHEUS-122) and this wrap.
2. **Read the landing page live** before it matters to anyone — the copy was verified against the doc textually, not visually. `/site` on localhost, or Live Server on `orpheus-landing-v1.html`. The founder block is the only new layout, and it's centered above the form.
3. **Decision Log paste (ORPHEUS-90)** — still owed (`outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md` from the 06-24 session). Carried since 06-24; consider whether it's actually going to happen.
4. **Delete the duplicate ORPHEUS-118 comment** if it's still there (carried from 07-27; Plane's MCP has no delete-comment tool).
5. **Andrew comms, carried:** (a) Nicole's report is the first real-client exercise of the ORPHEUS-63 score-0 posture, worth his read-through; (b) Jenn hasn't retried since the MIME fix; (c) Jodie needs an onboarding nudge, not a fix; (d) ORPHEUS-120's open question — should the feedback ask wait for advisory publication at all? **New:** (e) the copy doc's fourth open item, below.

---

## The one open question from ORPHEUS-122

**The report hero announces "composite score N of 100" to screen readers.** It's sr-only text inside the hero `<h1>`, added under ORPHEUS-51 as the accessibility fallback for a band indicator that is otherwise color-and-label only. So it isn't visually client-visible — but it *is* read aloud on the client's own report, which sits against the bands-not-numbers principle and against "not vanity metrics" in the site copy. Andrew flagged it in the copy doc.

Left untouched on purpose: the obvious fix (drop the number) makes the accessibility story worse, and a band-only announcement was already considered and rejected when 51 shipped. This wants a decision, not a silent edit. Recorded on ORPHEUS-122 rather than filed as its own ticket — file one if the answer is "change it."

---

## Recommended pickup for next session

1. **Run the 112/113/117 acceptance test** via `c2df921` against `b902bd06`. That's the shortest path to closing three high-priority tickets whose code is already in. Then decide regeneration scope for the other affected reports.
2. **ORPHEUS-120 + ORPHEUS-114 together**, per the 07-27 cross-link — design the publish boundary once. 120 is small alone (filter `status` for client callers in `_build_result_payload`, plus an "advisor is reviewing this" surface) but shouldn't land twice.
3. **ORPHEUS-115** after 114 — depends on the label registry.
4. **ORPHEUS-119's remainder** rides the next real first-time completion under an `is_individual = true` advisor. No action until then.
5. **ORPHEUS-116** last: largest scope, medium priority, gated on Andrew for format granularity.
6. Then ORPHEUS-111, ORPHEUS-107, ORPHEUS-94, ORPHEUS-99.

---

## Caveats / things that will bite

1. **Two consecutive sessions have now shipped code without a handoff** (07-22 filing, 07-27 evening batch). Both were invisible to the canon until a later session went looking. The 07-27 wrap already made this caveat #6 and it recurred four hours later. Running the full Plane list at session start is what catches it — this session did, which is the only reason the 112/113/117 state is written down here.
2. **`python-multipart` is still in `requirements.txt` unused**, deliberately, comment-flagged. Fold the removal into the next backend commit; don't give it a dedicated deploy.
3. **Resend's dashboard still lists the provider as GoDaddy.** The zone is Vercel's. **Do not use Resend's Auto configure button.**
4. **Email outages are invisible from inside the product.** Both send paths swallow `EmailSendError` by design. The last one ran ~10 days undetected. Monitoring scope is folded into ORPHEUS-119.
5. **A returning or advisory client completing a report is NOT an ORPHEUS-119 verification event** — the send fires only on a client's *first* completion and only under an `is_individual = true` advisor.
6. **The part-1-partial sub-question is open** (on ORPHEUS-110): if LinkedIn's 10-minute partial download carries the Complete fingerprint files, a part-1 upload would pass as zero-activity. Needs a real part-1 sample.
7. **Abandoned staging uploads still aren't swept** — Jenn's orphaned `analytics.xlsx` from 07-17 sits in `{client}/staging/`. Harmless at current volume.
8. **The prototype's `<title>` reads "Orpheus Social — Tune your professional signal"** — an em dash and a tagline that appears nowhere in the copy doc. Out of scope for ORPHEUS-122, left alone. Worth a look if the copy rules are meant to cover page titles.
9. **Sandbox quirks unchanged** — no pip/pytest (Josh's terminal); no SSH push, and `git fetch` fails too, so the origin comparison at session start is against a stale ref; `.git/*.lock` needs the `mv` workaround before each commit, and `.git/index.lock` sometimes needs a second explicit `mv` after a failed commit; no DNS resolver (use the DoH snippet in `CREDENTIALS.md`); `rm` inside the mount needs delete permission granted for the folder first.
10. **Untracked-by-intent files** — do not `git add`: `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `create_beta_survey_form.gs`, both `rubric_consistency_results_*.json`, `.claude/`, `outputs/`, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`.

---

## State of the repo right now

One code commit this session (`da591f2`, unpushed) plus this wrap commit. `c2df921` and the three commits before it were pushed by Josh at the start of this session. Working tree otherwise clean except the intentionally-untracked files in caveat 10.

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
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk` (Andrew's revision source for ORPHEUS-122)
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry. ORPHEUS-85 still owes its entry when it ships.
