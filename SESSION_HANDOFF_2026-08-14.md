# Session Handoff — 2026-08-14

Replaces `SESSION_HANDOFF_2026-08-13.md` — everything it described carries forward or closed as follows:

- **Its Pending item 1 is done.** The wrap commit `ff4aee9` was pushed; `origin/main` and `HEAD` both sit there, working tree clean. Nothing from 08-13 is unpushed.
- **Its live-validation watch resolved — but through Andrew, not through a self-serve client.** The 08-13 handoff framed the remaining event as "one self-serve client who uploads and completes." What actually arrived was **Andrew re-running his own report on 2026-08-13**, and that single job closed **three** of the six In Progress tickets: ORPHEUS-114, ORPHEUS-121 and ORPHEUS-126. The handoff's framing was too narrow — it tied all four remaining tickets to the self-serve path when only ORPHEUS-119 actually requires it.
- **This session wrote no code.** It is a verification-and-Plane session: read the job's stored rows, verify each ticket's closing condition against them, close what fired, and file what the verification surfaced. The only commit is this wrap.
- **Two new tickets: ORPHEUS-131 and ORPHEUS-132.** 132 is the one to read first — closing ORPHEUS-126 required reading its own "still owed before close" list, and item 1 was still unfixed.
- ORPHEUS-119 / 120 / 130 stay In Progress; each was checked and each genuinely did not fire. Reasons recorded on the tickets so a future session does not re-derive them.
- Karen's re-invite, Tim's §11 list, the ORPHEUS-90 and ORPHEUS-85 Decision Log pastes, the surplus ORPHEUS-123 comments, `_to_delete/`, and the Andrew comms items all carry unchanged (see Pending).

---

## The artifact everything closed on

**Job `b03ca0f5-8904-4bf0-99ab-13677f53a74d`** — client `c7af460c` (Andrew Segars), created 2026-08-13 16:32:09 UTC, scored 16:44:44, complete 16:50:40. Composite **82.38 / Resonant**, `config_snapshot.model = claude-sonnet-4-6`, `data_limited = false`, `attempt_count = 3`.

It is the first job created after the whole metric-trust cluster deployed, so it exercises all of it at once.

---

## ORPHEUS-114 — closed 2026-08-14 (reconciliation gate + registry)

**The evidence that mattered is structural, not a log line.** `stage_scoring` raises `ReconciliationError` *before* the scores upsert, so a persisted `scores` row **is** the green result. Railway logs were never needed — which is worth generalizing: when a gate raises before a write, the row's existence is the proof.

All six identities re-verified independently from the stored row:

| identity | check | result |
|---|---|---|
| impressions/post × posts | 2,820.2 × 125 = 352,525 vs 352,526 | Δ 1 |
| DISCOVERY vs ENGAGEMENT | 352,526 vs 352,526 | **Δ 0** |
| engagement rate | 9,232 / 352,526 = 0.02619 vs 0.0262 | ok |
| follower growth | 972 / 52.14 = 18.64 vs 18.6 | ok |
| members reached | 74,746 within total impressions | range check, never summed |
| post count | 125 = `coverage.posts_in_window` | ok |

**Operands persisted (2.2a/b):** `post_count` 125, `total_impressions` 352,526, `total_engagements` 9,232, `net_new_followers` 972, `followers_weeks_observed` 52.14, `discovery_impressions` 352,526.

**Coverage persisted (2.2d):** `posts_in_window` 125, `top_posts_covered` **50** (the cap is biting — per-post reach covers 40% of the window), shares 354/0/0, comments 2,611/103/2, reactions 9,946/0/0.

**Two things re-confirmed in passing:** ORPHEUS-112 on fresh data (2,820.2, where the retired days denominator would have written ~966), and the ORPHEUS-106 proportional threshold (103/2,611 = 3.9%, under 10%, so `data_limited` correctly false).

---

## ORPHEUS-121 — closed 2026-08-14 [Josh] (prose-number gate)

**The gate blocked a real fabrication.** From `jobs.error_message`, the rejected tokens were: `Profile Signal Clarity: '400'`, `Behavioral Signal Quality: '2,549'` and `'53'`, `Experience Description Quality.summary: '400'`, `Profile Completeness.summary: '13'`, `Profile Completeness.improvements[1]: '80'`.

**`2,549` is the ticket's exact class and its provenance is worth keeping.** It matches nothing. Its two nearest real neighbours are `coverage.comments.total_rows` **2,611** and the Engagement Quality Score raw index **2,555.25** — and that second one is *suppressed* by ORPHEUS-117 as a unitless internal index, so it is absent from the prompt **and** from the whitelist. The agent minted a plausible-magnitude comment count from nothing at all. Same signature as `301ba109`'s "2,394 total comments". Without the gate it would have shipped.

**The delivered prose is clean** — every figure traces to an input: 6,740 / 1,249 / 46 / 2.4 (sub-dim raws), 6,615 (Dim 3), 74,746 / 352,526 / 2,820 / 19,375 / 18.6 / 3,246 / 29.1 / 2.6% / 12% (registry metrics), 105 (combined-exclusion variant), 52 and 2 (structural).

**Calibration note, deliberately not acted on.** Only `2,549` and `53` are fabricated aggregates. `400`, `80` and `13` read as unobservable *guidance* constants ("over 400 characters", an 80-character headline) — ORPHEUS-96's unobservable-claim class wearing a number. Rejecting them is defensible but means the gate does double duty. If a future run rejects **only** on that shape, widen `_STRUCTURAL_ALLOWANCES`. **Do not raise `_SMALL_INT_MAX` past 12** to catch `13` — that admits fabricated small counts.

---

## ORPHEUS-126 — closed 2026-08-14 (Route A consent capture)

`upload_consent_at = 2026-08-13 16:32:09.518814+00`, `upload_consent_version = 2026-08-11`. It is the only job in the table carrying a consent stamp and the only job created since migration 020, so it is the first submission through the gated path rather than a sampled one. The stamp precedes the job row by **133 ms** — consent recorded first, job minted second, the enforced ordering visible in data.

**The sharper confirmation is an absence.** Andrew has **no `terms_acceptances` row** — the table holds two, Josh (08-11) and Adam Tousley (08-12), both post-dating the login checkbox. His session predates it and there was deliberately no backfill. So the per-upload leg fired cleanly on an account that has never passed the account-level gate: exactly the case the two-records design has to tolerate, and the one a single combined record would have broken.

**Closed with a carve-out, stated on the ticket.** Its 08-11 comment listed five items owed before close; four are satisfied. The fifth is now ORPHEUS-132.

---

## ORPHEUS-132 — filed (high). Read this one.

**Invited clients never accept the ToS or Privacy Policy.** Re-verified 2026-08-14: `InviteLandingPage.tsx` contains no consent reference at all, only `LoginPage` and `SignupPage` call `buildAcceptanceRedirectUrl()`, and `backend/routers/clients.py` (which owns `/accept-invitation`) records nothing. An invited client creates an account, uploads an archive and receives a report having never been shown either document.

**That is how Andrew's entire roster was onboarded.** `/signup` is the newer, much smaller channel — and it is the only one covered. The gap is currently theoretical only because no invited client has signed up since 2026-08-11; the path is uncovered, not merely untested.

Three options, as framed on ORPHEUS-126 in August: surface the checkbox on the invite landing page (recommended — ORPHEUS-130 already broke that page's headlessness, so the objection that made it awkward no longer holds), carry acceptance in the invitation email, or accept the gap with a Decision Log entry. **Whether an unrecorded ToS acceptance is tolerable is Tim's call**, not a code decision.

---

## ORPHEUS-131 — filed (high). The prose gate's cost.

`attempt_count = 3`. Two of the worker's three pipeline attempts went to gate rejections; the job passed on **attempt 3 of 3**. Wall clock 16:44:37 → 16:50:40, six minutes against a normal ~1.

The nesting is the problem: `generate_narratives` retries 3× internally and the worker retries the pipeline 3×, so a persistently-rejecting generation burns up to **nine** 8192-token calls before the job lands `failed`. One more unlucky generation and a client watches their report fail over prose, on data that was never wrong.

Proposed fix: **degrade to `log` mode on the final generation attempt** rather than failing, with a persisted marker so a degraded report is visible in `/admin`. The gate still rejects the first two attempts, which is where it did all its work here. Secondary: clear `jobs.error_message` on `complete`, and skip re-running deterministic stages 2–3 on a narrative-only failure.

Open question on the ticket: whether a degraded report auto-publishes or parks. Advisory parks anyway under ORPHEUS-120, so this only bites the self-serve house-advisor path — which is also the path with nobody watching.

---

## The three that did not advance (checked, not assumed)

**ORPHEUS-119** — suppressed twice over, either alone sufficient: Andrew's advisor row `351f9deb` has `is_individual = false`, so `_maybe_send_report_ready_email` correctly declines at completion; and `reports.published_at IS NULL`, so the admin path has not fired. A third suppression would apply even if published — he is a returning client, so `_is_first_complete_job` is false. **The verification event is unchanged and narrow:** a first-time completion under an `is_individual = true` advisor, i.e. a self-serve client under house advisor `6b9922b9`. Adam Tousley is the only such account and has submitted nothing.

**ORPHEUS-120** — the gate is **armed on a real job for the first time**: `report_type = advisory`, `published_at IS NULL`, all five narratives `draft`. Every other complete advisory report carries `published_at = 2026-08-12 14:30:14` from the migration-021 backfill, so until now the gate had only been exercised against rows it published itself. What this does *not* establish: Andrew is dual-role on his own `is_self` row, so `viewer_is_advisor_of_job` is true and he reads the draft normally — the hold is invisible to him. **Cheapest close: he publishes this very job from `/admin`.** That exercises the release side without waiting on a roster client, though it won't fire the email (returning client). The publish half and the email half can close separately.

**ORPHEUS-130** — **no `auth.users` row for Tarita exists.** The newest account is still Adam Tousley (08-12 19:02). The acceptance event has not fired. `0aca889` is on `origin/main` so Vercel should have built, but **the deploy was not confirmed** — the project is not visible under the `orpheus-social` team via the Vercel API, so it needs a dashboard check before sending her the link.

---

## One ORPHEUS-115 datapoint

The delivered prose says twice: *"105 comments were excluded from the underlying analysis due to unparseable dates."* Coverage reads `unparseable 103, empty 2`. So **105 is right as a total and wrong as an unparseable-date count** — the label attributes all of it to one cause.

The number gate cannot catch this by design: ORPHEUS-114 deliberately whitelists `unparseable + empty` as a legitimate combined-exclusion variant, so 105 passes, correctly. It is the clean demonstration that the two tickets are non-overlapping — **121 guards provenance, 115 guards meaning.** Fix shape unchanged: render the two exclusion reasons as separately labelled counts in the DATA COVERAGE prompt block, source-side, as with ORPHEUS-117.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-114 | Reconciliation gate + registry | ✅ **Done 2026-08-14** |
| ORPHEUS-121 | Prose-number gate | ✅ **Done 2026-08-14** |
| ORPHEUS-126 | Route A consent capture | ✅ **Done 2026-08-14** — account-level gap carved to 132 |
| ORPHEUS-131 | Prose-gate rejections eat the retry budget | 🆕 Backlog, high |
| ORPHEUS-132 | Invited clients never accept the ToS | 🆕 Backlog, high — **Tim's decision** |
| ORPHEUS-120 | Advisory draft gate | 🔄 In Progress — gate armed on a real job; closes on a real review-then-release |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — needs a house-advisor client's *first* completion |
| ORPHEUS-130 | In-app browser guard | 🔄 In Progress — deploy unconfirmed; Tarita has no auth row |
| ORPHEUS-115 / 111 / 116 / 99 / 94 / 84 / 107 | unchanged | ⏳ Backlog |

Baselines unchanged and unmeasured this session (no code): backend pytest **558 green**, frontend vitest **186 green**.

---

## Pending — manual steps

1. **Confirm the Vercel build for `0aca889`** via the dashboard — the API can't see the project under the `orpheus-social` team. This blocks item 2.
2. **Re-run Tarita once the deploy is confirmed:** `https://app.orpheussocial.com/signup?code=ORPH-Z32A-K7VA`. She is a `/signup` user with no clients row; the invite path is not hers. Her completing sign-up closes ORPHEUS-130.
3. **Route ORPHEUS-132 to Tim.** It is a lawful-basis question, not an implementation one, and it affects every client on Andrew's roster.
4. **Andrew can close ORPHEUS-120's publish half himself** by publishing job `b03ca0f5` from `/admin` — no roster client needed.
5. **Two other beta testers may still be stuck in the in-app-browser trap** (carried). Worth a direct nudge once the deploy is confirmed, plus the open ops question of whether beta invitations should travel by email rather than LinkedIn DM.
6. **ORPHEUS-85's Decision Log entry is overdue** (revises the 2026-05-11 invitation-only decision; draft language in the ticket comments), alongside the long-carried ORPHEUS-90 4.6-acceptance paste.
7. **The live-validation watch, restated:** ORPHEUS-119 is now the *only* ticket needing a self-serve client who uploads and completes. 121 / 114 / 126 are spent. Pushing a recruited beta user through `/signup` **and an upload** remains the highest-leverage validation action.
8. **Re-invite Karen** from the test roster when she wants a fresh report (carried).
9. **Delete the surplus ORPHEUS-123 Plane comments** (dashboard job; keep `6a6c67ce`) (carried).
10. **Tim's confirmation list for Privacy Policy §11 and §7/§9 claims** (carried verbatim).
11. **Empty `_to_delete/`** at repo root, including `orpheus_snapshot_085.tar.gz` (~12 MB) (carried).
12. **Andrew comms, carried:** (a) Nicole / ORPHEUS-63 score-0 posture; (b) Jenn MIME retry; (c) Jodie onboarding nudge; (d) growth factors + ORPHEUS-112 caveat; (e) the 14 backfilled clients' feedback asks permanently unsent; (f) reconciliation tolerances + registry descriptions open to his review — **now with live green identities to review against**; (g) self-serve sign-up exists and those clients are NOT on his roster; (h) whether he wants a recruited beta user pushed through `/signup` — still the highest-leverage action, and now known to require a completed *report*.

---

## Recommended pickup for next session

1. **ORPHEUS-131** — small, self-contained, and it removes a live failure mode (a report that dies on prose after nine generations). The `error_message`-on-complete cleanup rides along for free.
2. **ORPHEUS-115** (prose mislabels) — unchanged top code recommendation across four handoffs, and it now has a concrete live example (the 105 / 103+2 label). The 114 registry is its substrate; the 121 gate is its enforcement pattern.
3. **ORPHEUS-111** (upload size caps: 50 MB Storage vs 150 MB advisory vs 200 MB copy) — small, long-carried.

ORPHEUS-132 is higher-stakes than any of these but is blocked on Tim, so it is not a code pickup.

---

## Caveats / things that will bite

1. **Prefer structural evidence to log evidence.** If a gate raises before a write, the row existing is the proof — no Railway log needed. Timestamp *gaps* work the same way (consent 133 ms before the job row is the enforced ordering, visible in data). This is how ORPHEUS-114 and 126 were closed from the database alone.
2. **A backfilled row proves nothing about the gate that backfilled it.** Most complete advisory reports carry `published_at = 2026-08-12 14:30:14` from migration 021. Only a row created *after* the gate shipped and still NULL demonstrates the hold. Always check whether the evidence predates the mechanism.
3. **Check whether the actor's own role hides the behavior.** Andrew is dual-role, so `viewer_is_advisor_of_job` is true on his `is_self` row and ORPHEUS-120's client-facing hold cannot be exercised by him. Ask who a gate applies to before treating a run as a test of it.
4. **`jobs.error_message` persists on successful jobs.** `b03ca0f5` is `complete` and still carries its attempt-2 traceback. Read `attempt_count` alongside it — a passing job at `attempt_count = 3` is itself a finding. (ORPHEUS-131 proposes clearing it.)
5. **Read a closing ticket's own "still owed before close" list before closing it.** ORPHEUS-126 listed five; the fifth was a real unfixed design gap that closing would have buried. Carve it out as its own ticket and say so in a comment.
6. **`jobs` has no `updated_at` and no `attempts`** — the columns are `created_at` / `started_at` / `completed_at` and `attempt_count`. `scores` has `total_score`, not `composite`. Both cost a round trip this session.
7. **The Vercel MCP cannot see the project.** `list_projects` under team `team_fSVe9C792czg1Kz6T5johM1z` returns empty and there is no `.vercel/project.json` in the repo. Deploy confirmation is a dashboard job until that is sorted.
8. **Plane comment posts can 502 through Cloudflare.** One did this session; the retry was safe (verified no duplicate via `get_issue_comments`). Check before re-posting, but don't assume the first attempt landed.
9. **Plane MCP double-escape quirk** (carried — held correct across seven comments this session: pre-escape the HTML entities in `comment_html`). Note `create_issue`'s `description_html` does **not** double-escape — pass plain HTML there.
10. **`list_project_issues` truncates** (carried) — it exceeded the tool cap again at 130 issues. Dump to file and filter with `jq`/python rather than pulling raw.
11. **Do not put `blocked` from `useInAppBrowserGuard` in a dependency array** (carried) — fresh object every render; `InviteLandingPage` derives the primitive `isBlocked` for exactly that reason.
12. **The in-app detection is a UA heuristic and always will be** (carried) — the test suite's negative half is the load-bearing part. Adding a pattern is one line; loosening one hard-blocks Safari.
13. **A wrap is not a stop signal** (carried) — if work continues after the ritual, amend the handoff or write a part-2.
14. **Closing events fire while nobody is looking** (carried, and validated again) — ORPHEUS-114/121/126's evidence sat in production for a day. When a ticket's closing condition is a *user action*, check the database at session start.
15. **Sandbox limits** (carried): no `pip install`, so backend pytest runs from Josh's terminal; SSH egress is blocked, so `git fetch`/`push` can't run here — `refs/remotes/origin/main` is still readable and is how this session established the tree was fully pushed; `.git/*.lock` needs `mv` aside before each commit; `npm run build` needs a scratch `--outDir`.
16. **Self-serve clients rows have `invitation_token IS NULL`** and `invitation_status='accepted'` from birth (carried).
17. **`signup_codes` + `code_redemptions` are service-role only**; `max_uses` is check-then-insert, not atomic; the house auth user `e68769d8` is load-bearing and deliberately unclaimable (carried).
18. **Module-load URL rewrites must preserve `location.hash`** (carried). **The document effective date is load-bearing in three places** (carried). **Committed ≠ applied for migrations** (carried; 021 and 022 both applied).
19. **A reconciliation failure fails the job by design; `PROSE_NUMBER_GATE` is the prose gate's valve** (carried) — and ORPHEUS-131 exists because that valve is all-or-nothing and needs a deploy.
20. **Untracked-by-intent set unchanged:** `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json`, `_to_delete/` (all gitignored — `git status --short` shows no `??` entries, which is expected, not a sign they're missing). `git check-ignore -v <path>` before trusting any new root file. **Never `git add -A`.**
21. **Growth factors remain PROVISIONAL; verify a deploy before asking anyone to re-run; a clean run doesn't prove a stochastic prose bug fixed** (carried — and ORPHEUS-121's close rests on a *rejection*, not a clean run, which is the stronger evidence). **Never pin `opsz`; never rename the faces back to "Source …"** (carried).
22. **Email-path items carried:** transactional-email outages are invisible from inside the product; a returning or advisory client completing is NOT an ORPHEUS-119 verification event, but a house-advisor self-serve client's first completion IS; do not use Resend's Auto configure button.

---

## State of the repo right now

`origin/main` and `HEAD` were both at `ff4aee9` at session start, working tree clean, zero untracked entries. **No code, migration, or configuration changed this session.**

One commit: this wrap — CLAUDE.md (Active phase + a Decisions Made entry), PRODUCT_CONTEXT.md (three Build Status rows: Forward Brief computation, Narrative generation, Legal & consent surface), the new handoff, and the retirement of `SESSION_HANDOFF_2026-08-13.md`.

Plane: ORPHEUS-114 + 121 + 126 → Done with closing comments; ORPHEUS-131 + 132 created (Backlog, high); status comments on 119, 120, 130; a live-datapoint comment on 115.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk`
- **Privacy Policy drafting Doc:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting Doc:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — drafting surfaces only; **the canonical published text is the repo markdown** at `frontend/src/content/legal/`.
- **Pending pastes:** ORPHEUS-90 4.6-acceptance entry (carried since 06-24); **ORPHEUS-85's entry is overdue** — sign-up is live in production.
