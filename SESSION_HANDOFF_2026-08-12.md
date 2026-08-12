# Session Handoff — 2026-08-12

Replaces `SESSION_HANDOFF_2026-08-11.md` — all the threads it described are closed in code, moved into CLAUDE.md "Decisions Made", or carried below:

- **The standing top code recommendation shipped.** The ORPHEUS-120 + 114 + 121 cluster (unchanged at the top of the board since 08-05) landed as four commits in one session (worked 08-11 evening, wrapped 08-12): the advisory draft gate is enforced on the read path, a metric source/unit registry owns every client-facing label, six reconciliation identities block persistence, a prose-number gate rejects fabricated figures, and the report page explains its own methodology. All three tickets sit **In Progress awaiting live-validation events** (progress comments on each say exactly what closes them) — per the 117/112/113 precedent, they close on live evidence, not on ship.
- **The migration-021 backfill ran against production BEFORE the deploy** (155 draft narratives, 31 advisory reports, **14** clients — one more than the ticket's 13; verification selects all zero). Backfill-first was deliberate: behavior-equivalent to the leak clients already lived with, where gate-first would have vanished their reports.
- **The 08-11 GDPR/compliance threads carried unchanged:** ORPHEUS-126's per-upload consent leg and ORPHEUS-119's first-time-completion email are still event-gated; Karen's re-invite, Tim's §11 confirmation list, the ORPHEUS-90 Decision Log paste, the `_to_delete/` cleanup, and the Andrew comms items all carry verbatim (see Pending below).
- **Deploy + push done in-session:** all four commits pushed by Josh, Railway (backend + worker) and Vercel redeployed and confirmed, and the reconciliation acceptance ran green against Andrew's production data.

---

## ORPHEUS-120 — advisory draft gate enforced (shipped `c283ddb`, In Progress pending live acceptance)

`GET /jobs/{id}` nulls the **entire** result payload — scoring half included, so the composite band, dim bands, sub-dim pips, and metrics block are withheld along with the narratives — for a client viewing a complete advisory job whose `reports.published_at IS NULL`. The gate signal is deliberately job-level publication state, NOT per-narrative status counting: publication happens via per-narrative flips in /admin, and a half-published report stays fully hidden until the last flip stamps `published_at` — which is also when `_maybe_send_report_ready_on_publish` fires, so the visibility boundary and the email boundary coincide by construction. Advisors keep seeing drafts (`advisor_client_ids` tracked separately from the ownership union); dual-role callers resolve advisor-first (Andrew on his own is_self row); a missing reports row fails OPEN — though a live probe found zero complete jobs without one. `GET /jobs` marks unpublished-advisory rows `in_review` and withholds the band chip, closing the list-side leak (the band + a live "View report" link leaked independently of the payload).

Frontend: `in_review` on both wire types; "Your advisor is reviewing your report" surfaces on the report + Quick Reference Card pages (a third branch above Analysis-in-Progress — the pipeline is done, so the old copy would lie); a non-link "In review" row on `/reports` (accent-toned chip — good news in progress, not a caution); `useJob`/`useJobs` polling widened (in_review → 15s) so the release appears without a reload. AnalysisPage's auto-navigate lands on the in-review surface, which is correct. Prototype backported (`orpheus-reports-v1.html` in-review row).

**Backfill (migration 021, applied to cloud as `orpheus120_publish_backfill` 2026-08-12 UTC, pre-deploy):** raw SQL — the ORPHEUS-98 email trigger lives only in the admin PATCH handler, so the backfill cannot send. Decision [Josh, 2026-08-11]: the 14 clients' feedback asks stay unsent (stamping `published_at` suppresses the already-announced dedup permanently; Andrew nudges manually). Data-only migration; a fresh DB doesn't need it.

**Closes on:** Andrew's first real review-then-release through /admin — client sees "In review"/no band until the final flip, then report + band appear and the ORPHEUS-98 email fires for a first-time client. The ticket's open trigger-timing question resolves itself: with the gate enforced, publication is a genuine readiness moment, so the current trigger is right.

---

## ORPHEUS-114 (a–f) — registry + reconciliation gate (shipped `7dcface` + `872c051`, In Progress pending first worker-run job)

**(a)+(b)** `backend/scoring/registry.py` is the golden-source map: every client-facing metric carries its owning file/sheet + derivation, unit, **explicit denominator** (bug C — "17.5/week" and "875/day" can no longer sit as peers), window, and display precision. Both labelling layers render from it: ORPHEUS-117's `QUANTITATIVE_METRIC_LABELS` is a thin adapter over `registry.SUB_DIM_METRICS`, and `_format_forward_brief_data` dropped its hand-written f-strings for registry iteration.

**(c)** Operands persist on `ForwardBriefQuantitative`: `post_count`, `total_impressions`, `total_engagements`, `net_new_followers`, `followers_weeks_observed`, and `discovery_impressions` — the DISCOVERY sheet's own total, parsed since day one and **read for the first time** as a free cross-check. `backend/scoring/reconciliation.py` runs six identities (impressions/post × posts ≈ total; rate × weeks ≈ net new; engagement rate recomputed exactly; members_reached **range check, never sum-of-dailies**; DISCOVERY vs ENGAGEMENT within 1%; top post ≤ total), each skipped when operands are None so partial-XLSX jobs never fail on data they never had. `stage_scoring` raises BEFORE the scores upsert; deterministic input → all 3 worker retries fail → job lands `failed` with every failed identity in `error_message`. `regenerate_report.verify()` runs the same identities. Bug-A regression pinned: 875.4 × 112 vs 319,511 misses by ~221k; the corrected 2,852.8 passes at |Δ|=2.6 within tol 5.6.

**(d)** Coverage facts on `ForwardBriefData.coverage`: the top-50 per-post analytics cap made explicit (`len(top_posts)` vs posts-in-window was computed nowhere), and per-file date exclusions **including empty-Date rows the CSV parsers had been dropping uncounted** (`ZipData.raw_behavioral_row_counts` records raw totals at parse time). Rendered as a labelled DATA COVERAGE prompt block so "72 unparseable comment dates"-class prose traces to an input line.

**(e)** Resolved by verification, not construction: no ID-decoded dates exist anywhere in the codebase (a comment's Link URN is the *target post's* — decoding would be wrong anyway); documented in the registry docstring. The triplicated date-format list consolidated into `backend/scoring/dates.py` so "unparseable" means the same thing to the exclusion counts as to scoring.

**(f)** [Josh, 2026-08-11: methodology block, not wire-only] — "How This Score Is Computed" on the report page: the four dimension weights + the five-band ladder with threshold ranges, rendered from the job's own `config_snapshot` (live-config fallback marked `snapshot:false`). Deliberately excludes the client's composite/contributions so ORPHEUS-128's leak can't reopen through the methodology door — pinned by a negative sweep (no fixture composite/contribution strings, no sr-only, no aria-hidden inside the block). Rides the payload, so gated in-review viewers never receive it. Prototype backported.

**Acceptance already run against production data:** recomputing job `0007607e` (Andrew) with the shipped engine reproduced every golden fixture exactly (112 / 319,511 / 8,655 / +913 / 2,852.8 / 2.71% / 17.5 / 67,063 / 18,479) and all six identities passed — DISCOVERY vs ENGAGEMENT at Δ=0. Coverage: top 50 of 112, 341 shares in archive, 70 of 2,437 comments date-excluded.

**Closes on:** the next worker-run job logging the identities green with operands + coverage in its stored `forward_brief_data`.

---

## ORPHEUS-121 — prose-number gate (shipped `d8b7876`, In Progress pending first real generation)

`backend/agents/prose_numbers.py`: every numeric token in client-facing prose (sections, summaries, sub-dim slots, cheat sheet) must match a whitelisted value — the registry metrics in all display variants (comma-grouped / rounded / percentage forms), coverage counts, registered sub-dim raw values, computed milestone targets — or a structural allowance (years, integers ≤12, a fixed duration set incl. 90/365/50, range halves tokenize individually). Word numbers never tokenize, so "three to five posts a week" is structurally immune. **Deliberately NOT whitelisted:** the composite, contributions, normalized scores (the agent quoting the composite *should* reject, per ORPHEUS-128) and band thresholds.

On violation, `generate_narratives` rejects and retries **with the offending tokens appended to the user message** — an identical-prompt retry is near-worthless against a confidently-invented number. Kill switch `PROSE_NUMBER_GATE` env ∈ {block (default), log, off}, resolved at call time, because a deterministic false positive would otherwise fail every job with no recourse short of a deploy; rejected tokens are always audit-logged. Regression pins the 301ba109 fabrications: "2,394 total comments" and "331 posts" both reject against inputs carrying 2,437/72 and 341/112.

**Closes on:** the next real narrative generation — worker logs show a clean pass or a self-corrected retry, and no false-positive job failure. If a false positive DOES fail a job: set `PROSE_NUMBER_GATE=log` on the worker service (no deploy needed), diagnose from the logged tokens, widen the whitelist in code.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-120 | Advisory draft gate on the read path | 🔄 In Progress — shipped + deployed + backfilled; closes on Andrew's first real publish |
| ORPHEUS-114 | Reconciliation gate + metric registry (a–f) | 🔄 In Progress — shipped + deployed, acceptance green on prod data; closes on first worker-run job |
| ORPHEUS-121 | Prose-number fabrication gate | 🔄 In Progress — shipped + deployed; closes on first real generation |
| ORPHEUS-126 | Route A consent capture | 🔄 In Progress — per-upload leg closes on the next real submission |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — awaiting a first-time completion under `is_individual = true` |
| ORPHEUS-115 | Prose mislabels (bug D) | ⏳ Backlog (medium) — **unblocked**: the 114 registry's canonical labels are its substrate |
| ORPHEUS-116 | "What Travels" evidence layer | ⏳ Backlog — gated on Andrew for format granularity |
| ORPHEUS-111 | Upload size caps misaligned | ⏳ Backlog (medium) |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | unchanged | ⏳ Backlog |

Baselines: backend pytest **526 green** (460 → 526), frontend vitest **132 green** (124 → 132), `tsc -b` + vite production build clean. **Measured** — cloud Cowork session with working pip/pytest/npm; Josh's terminal should match.

---

## Pending — manual steps

1. **Watch for the three live-validation events** (each closes its ticket with the conventional comment): Andrew's first review-then-release (120), the next worker-run job's green reconciliation logs + stored operands (114), the next real generation through the prose gate (121). A single new real submission followed by Andrew publishing it would close all three at once — worth engineering if a beta client is ready.
2. **ORPHEUS-126's closing evidence** — same event as above: verify `upload_consent_at`/`upload_consent_version` on the new jobs row.
3. **Re-invite Karen** from the test roster when she wants a fresh report (carried).
4. **Delete the surplus ORPHEUS-123 Plane comments** (dashboard job; keep `6a6c67ce`) (carried).
5. **Tim's confirmation list for Privacy Policy §11 and §7/§9 claims** (carried verbatim from 08-11: MFA, admin-access logging, documented incident response, Anthropic commercial agreement, 90-day backup window, DPA/SCC close-out).
6. **ORPHEUS-90 Decision Log paste** — carried since 06-24; decide whether it will ever happen.
7. **Empty `_to_delete/`** at repo root (carried).
8. **Andrew comms, carried:** (a) Nicole's report is the first real exercise of the ORPHEUS-63 score-0 posture; (b) Jenn hasn't retried since the MIME fix; (c) Jodie needs an onboarding nudge; (d) ~~ORPHEUS-120 trigger-timing question~~ — resolved by the gate (publication is now a genuine readiness moment); (e) growth factors + the ORPHEUS-112 metric-definition caveat; **(f) new:** the 14 backfilled clients' feedback asks are permanently unsent — if Andrew wants those clients surveyed, it's a manual nudge; **(g) new:** the reconciliation tolerances and the registry's golden-source descriptions are framework-adjacent and open to his review.

---

## Recommended pickup for next session

1. **ORPHEUS-115** (prose mislabels) — now unblocked and cheap: the registry's canonical labels exist, and the prose-number gate provides the enforcement pattern (the mislabel class needs label-adjacency checking rather than token whitelisting, or a prompt constraint citing `registry.format_metric_line` language). Medium priority but it completes the trust-gap trio from Andrew's handover.
2. **ORPHEUS-111** (upload size caps) — small, self-contained, long-carried.
3. If any live-validation event fired between sessions, close the ticket(s) first with the conventional comment — the progress comments on each ticket state the exact evidence required.

---

## Caveats / things that will bite

1. **`reports.published_at` is now load-bearing on the read path.** Any future writer of narratives or reports rows must maintain it: an advisory report is client-invisible until it's stamped. `regenerate_report._write_rows` already preserves per-section publish state; a new writer that forgets writes an invisible report. The worker stamps self-serve at completion; the admin last-flip trigger stamps advisory.
2. **A reconciliation failure fails the job — by design.** The worker retries 3× (deterministic → all fail), then `status='failed'` with every failed identity in `error_message`. That message is the diagnosis; don't re-run blindly. The identities skip when operands are None, so partial-XLSX jobs are safe.
3. **`PROSE_NUMBER_GATE` is the prose gate's operational valve** — env on the worker service, resolved at call time: `block` (default) / `log` / `off`. A false positive fails jobs deterministically; the recovery is `log` mode (no deploy), then widen the whitelist in code. Rejected tokens always log regardless of mode.
4. **The jobs-router FIFO test queues now include a `reports` read** between jobs and scores for complete-status client-path tests (and `_Chain` records filter args). Any new query in `get_job` inserts a positional slot — every payload test needs its queue updated, same as this session did.
5. **Pre-114 stored rows lack operands and coverage and are never retro-checked** — all new model fields are Optional, and the gate runs only on fresh scoring output. Old reports keep their stored figures as history (the ORPHEUS-112 regeneration posture, unchanged).
6. **Module-load URL rewrites must preserve `location.hash`** (carried verbatim — the caveat-1 sign-in outage mechanism, `d076e7f`).
7. **The document effective date is load-bearing in three places** (carried verbatim — legal md + `consent.ts` + `consent_versions.py` move together).
8. **Committed ≠ applied for migrations** (carried) — 021 is applied (2026-08-12, `orpheus120_publish_backfill`); the ladder and live schema agree today.
9. **Cross-session work may arrive without its tests run** (carried); **cloud Cowork sessions can run both suites** (carried — this session measured 526/132); the on-device sandbox limitations (no pip, no SSH push, `git fetch` fails, unlink quirks) still apply.
10. **Device-bridge file transfer can't unlink; stale `.git/index.lock` files recur** (carried — `mv` aside before every stage/commit).
11. **Legal/public pages must use the canonical `nav / main-interior / footer` column; react-router preserves scroll** (carried verbatim).
12. **Untracked-by-intent set unchanged** from 08-11: `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json`, `_to_delete/` (all gitignored). `git check-ignore -v <path>` before trusting any new root file.
13. **Plane MCP double-escape quirk** (raw HTML to `add_issue_comment`; check `comment_html`) — held correct across four comments this session; unchanged.
14. **Never pin `opsz`; never rename the faces back to "Source ..."** (carried verbatim).
15. **A clean run does not prove a stochastic prose bug is fixed** (carried) — which is exactly why 121 gates in code; **verify the deploy before asking anyone to re-run; growth factors are PROVISIONAL** (carried).
16. **`python-multipart` is STILL in `requirements.txt` unused** — carried again; this session's backend commits deliberately didn't touch deps. Fold the removal into the next backend commit, for real this time.
17. **Email-path items carried:** outages invisible from inside the product; a returning/advisory client completing is NOT an ORPHEUS-119 verification event; the ORPHEUS-110 part-1-partial sub-question needs a real sample; do not use Resend's Auto configure button.

---

## State of the repo right now

Five commits this session (four code + this wrap), on top of 08-11 part 3's `b6dbb52`:

- **`c283ddb`** — ORPHEUS-120: enforce the advisory draft gate on the read path
- **`7dcface`** — ORPHEUS-114 (a–e): metric registry, operand persistence, reconciliation gate
- **`d8b7876`** — ORPHEUS-121: reject narrative prose that quotes numbers absent from its input
- **`872c051`** — ORPHEUS-114 (f): client-facing methodology block on the report page
- *(this wrap commit)* — session handoff 2026-08-12, doc refreshes, retire the 08-11 handoff

The four code commits are **pushed**; the wrap commit is the only thing left to push after this file lands.

**Prod config beyond source:** the four DNS records in the Vercel zone (unchanged); migrations 020 + 021 applied to the cloud DB via the Supabase MCP — the migrations folder and the live schema agree today. Railway backend + worker and Vercel all redeployed on the four code commits, confirmed 2026-08-12.

New backend modules this session: `backend/scoring/registry.py`, `backend/scoring/reconciliation.py`, `backend/scoring/dates.py`, `backend/agents/prose_numbers.py`, `backend/tests/test_reconciliation.py`, `backend/migrations/021_orpheus120_publish_backfill.sql`.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk`
- **Privacy Policy drafting Doc:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting Doc:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — drafting surfaces only; **the canonical published text is the repo markdown** at `frontend/src/content/legal/`.
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry. ORPHEUS-85 still owes its entry when it ships.
