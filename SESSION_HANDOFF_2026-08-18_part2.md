# Session Handoff — 2026-08-18, part 2

Replaces `SESSION_HANDOFF_2026-08-18.md` (same-day; the morning session's wrap) — everything it described carries forward or resolved as follows:

- **Its pickup item 1 (ORPHEUS-142) was taken and is accepted code-side.** The rendered-excerpt whitelist shipped, the acceptance sweep went **0-of-5 degrades** (from 5-of-5), and the gate re-validated live mid-run by rejecting genuinely unsupplied figures and recovering. 142 stays In Progress only because its third acceptance item (the /admin chip meaning something) is deploy-gated — it closes together with 131 after the worker deploys and one real job runs.
- **Its pickup item 2 (134 second pass) was taken — and then the whole enforcement approach was paused by decision.** The second pass shipped and eliminated cheat-sheet attribution homework entirely; a third pass extended the threshold ban to every register and fixed detector gaps; three acceptance sweeps in one day showed real breach density falling ~20 → 1–3 per run and then plateauing on structural residuals. **[Josh, 2026-08-18]: detect-and-ban is too heavy-handed as a control; no further prompt/detector work on 134 until the claims-layer discussion picks a mechanism.** Alternatives are written up as agenda item 8.
- **Its Pending 2 (push) was done** before this session's work started (reflog-verified). Four NEW commits are now unpushed — see Commits.
- Its Pending items otherwise carry, renumbered below. **Migration 023 is still not applied and is still the sharpest item here.**
- Its caveats carry with three updates: the sweep detector is materially stronger (99 patterns) but the flag-counts-under-report caveat stands; F12 fires on every report by construction (see caveats); and one of its assumptions — "the container can't run the backend suite" — is wrong for cloud sessions (see caveat 14).

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-142 | Prose-number whitelist excludes verbatim profile figures | 🔄 **In Progress — FIXED (`16371ff`) and sweep-accepted (0-of-5 degrades). Close together with 131 after the worker deploy + one real job shows the marker/chip live.** |
| ORPHEUS-134 | Spec 2 narrative-prompt guardrails | 🔄 **In Progress — PAUSED by decision [Josh, 2026-08-18].** Second + third passes shipped (`2a30194`, `58ba3f0`, `d133239`); cheat-sheet attribution eliminated; residual is structural. Gated on the claims-layer discussion (agenda item 8). Do NOT resume prompt/detector work without that discussion. |
| ORPHEUS-131 | Prose-gate retry budget | 🔄 In Progress — unblocked code-side by 142; needs deploy (023 first) + one real job, then closes with 142 |
| ORPHEUS-141 | Active-week config change (Continuity) | ⏳ Backlog, medium — between-cohorts window still open |
| ORPHEUS-135 | Signal-legibility footer | ⏳ Backlog, high — settled wording, ship text in the ticket; unaffected by the 134 pause |
| ORPHEUS-136 | Spec 1: Dim 4 preamble sentence | ⏳ Backlog, high — harness re-run + Andrew sign-off |
| ORPHEUS-138 / 139 / 115 | parser hardening / metrics polish / mislabels | ⏳ Backlog, medium — **115 gained fresh evidence: the 19,375-impressions→"people" relabel recurred in 3 of 5 sweep runs; run 5 turned the 12% share into "12 zero-post weeks". Recorded on 134's 2026-08-18 comments.** |
| ORPHEUS-116 | "What Travels" reach-driver analysis | ⏳ Backlog — still needs re-scope/re-blessing (contradicts Rulings 2/3) |
| ORPHEUS-132 / 130 / 120 / 119 | unchanged | 🔄 In Progress — events have not fired |
| ORPHEUS-133 / 140 / 111 / 107 / 99 / 94 / 84 / 48 / 45 / 42 / 41 / 40 | unchanged | ⏳ Backlog |

Baselines: backend pytest **686 green** (641 at session start → 649 with 142 → 670 → 684 → 686 across the 134 passes), measured in the cloud container against the re-tarred post-commit device tree at each step. Frontend untouched this session — **196 vitest carried from 08-17, not re-run; no tsc needed** (zero frontend changes).

---

## Commits this session

All four are **committed on `main` and NOT pushed** (plus this wrap commit):

| SHA | Subject |
|---|---|
| `16371ff` | Whitelist figures from the rendered profile excerpt in the prose gate. Refs ORPHEUS-142. |
| `2a30194` | Ban delegated attribution; reinforce claims rules at the cheat sheet; expand the sweep detector. Refs ORPHEUS-134. |
| `58ba3f0` | Extend the threshold ban to every register; ban reach vocabulary in priority titles; ratchet the detector. Refs ORPHEUS-134. |
| `d133239` | Exclude two detector false positives the 58ba3f0 expansion introduced. Refs ORPHEUS-134. |

All carry the `Co-Authored-By` / `Claude-Session` trailers, consistent with the 08-17/08-18-morning commits.

---

## What changed / what shipped

### ORPHEUS-142 — the whitelist knows the profile now (`16371ff`)

`build_number_whitelist` gained `profile_excerpt`: the **exact** `_format_profile_excerpt` string `generate_narratives` renders into the prompt, not a re-derivation from `zip_data`. Citable == visible-to-the-agent: the $400M/$100M dollar figures, "(80 skills total)", and any figure in a shown post pass; a figure beyond the excerpt's truncation caps stays gated because the agent never saw it. Companion decisions all [Josh, 2026-08-18]: rounding banned prompt-side (exact figure or none), derived arithmetic banned prompt-side, 15 joined the structural allowances (13/14 deliberately did not), profile figures must be framed as the member's words. New Claims rule 6 carries the prompt half; the retry-correction note names the Profile Content section.

**Acceptance, run in Josh's terminal:** 0-of-5 degrades. Run 2 rejected `72` and `2,506` mid-flight (both correctly unsupplied — 2,506 is the usable-comment count, deliberately not a rendered value) and recovered on attempt 3: reject-retry-recover working on real fabrications instead of punishing citations. The ticket's "narrow the whitelist in a scratch run" check is now a **permanent unit test** (fabricated "2,394 total comments" must reject against a numeric-rich excerpt), plus end-to-end pins both ways (with zip_data: clean first attempt; without: reject/degrade).

### ORPHEUS-134 — second pass, third pass, and the pause

**Second pass (`2a30194`):** Claims rule 7 — a review item may ask the member to *observe* what they did, never to *attribute* outcomes to it, with banned/permitted shapes enumerated from the sweep dumps. Rule 3 extended: ranked leverage ("highest-leverage move") is an effect-size claim in words. The Priorities/Rhythm instructions restate the rules at the compressed surface (leverage ordering = internal only; titles name the behavior; review items observation-only). Detector: F5 "doubles as" lookahead, F6 +10 patterns, F2 +4, F8 +2, new REVIEW families F11 (population benchmarks) and F12 (derived window shares), and the **`also_catches` mechanism** — every dump-read miss is pinned in the self-test, so recall only ratchets forward.

**Result:** attribution homework vanished from the cheat sheet — all ~70 rhythm/priority strings across five runs observation-only, many in rule 7's literal register. But thresholds migrated into the *permitted* registers ("above the threshold where a comment reads as a genuine contribution") and reach titles paraphrased around the named example ("Grow Post-Level Reach" — missed by the detector because **hyphenated words broke F2's verb-gap regexes**).

**Third pass (`58ba3f0`):** rule 1 now states the threshold ban holds in EVERY register; the title ban is on the reach vocabulary in any verb form, not the phrase; detector hyphen-tolerant + past-tense verbs + register-migration patterns. **Then (`d133239`)** two false positives the expansion introduced ("do double duty", bare "amplifies") were excluded and pinned.

**Third sweep:** raw 2/1/5/1/1 HIGH → corrected 1/1/3/0/1 real. Two structural conclusions, and they are the reason for the pause: **reach-titled priorities are the supplied outcome milestones (3,550 impressions / 3,550 followers / 3.0%) restated as imperatives** — prompt language cannot win while outcome milestones are supplied, so this residual belongs to the milestone decision (agenda item 2); and **threshold phrasings mutate through every ban** — a stochastic tail raising the acceptance-bar question (zero-HIGH from prompt work, or a standing pre-publish gate?).

**The pause [Josh, 2026-08-18]:** detect-and-ban is clamping content that won't follow enumerated negative rules without constant supervision. Alternatives written to **agenda item 8** (see below). Everything shipped stays — it's the measurement instrument and baseline for whatever mechanism is chosen.

### The claims-layer discussion agenda got its biggest item

`Draft_Claims_Layer_Discussion_Agenda_2026-08-14.md` (repo root, untracked by intent) updated: a status note (item 1's footer wording and item 3's part (b) self-resolved via the Decision Log before the meeting), and **item 8 — enforcement strategy**, carrying the evidence, Josh's position, four alternatives (judge-and-rewrite pass reusing the 131 gate plumbing; structured cheat sheet extending the ORPHEUS-113 pattern; positive-register prompt = the instrument-vs-coach product-voice call; advisory draft-stage highlighting), and the five decisions it needs (voice; mechanism; acceptance bar; population benchmarks; skills-list-curation scope).

### Corrections made during the session — read these before trusting the 08-18-morning comments

- **"12% of the trailing year", "longest gap 2 weeks", "29.1 words" are REGISTERED METRICS** (`zero_post_week_pct`, `longest_posting_gap_weeks`, `avg_comment_length_words`), i.e. supplied citations — the morning read's "derived arithmetic" finding against them was wrong and is corrected on 142's/134's comments. F12's hits on them are the known false-alarm case; F12 fires on every report's Continuity summary by construction (the citation is mandatory), so treat those hits as expected noise.
- **Milestone "label contains digits" readings are a dump-format artifact** — the dump concatenates value + label; the parser enforces digit-free labels.
- **The morning's parallel-reader pass was contaminated by its own brief** (my synthetic test fixture presented as real profile data), which produced a false "laundered figure" narrative. Resolved by cross-checking disputed figures against the delivered control text, which passed the old scoring-only whitelist. Lesson recorded in Architectural notes.

---

## Architectural notes worth carrying forward

1. **Detect-and-ban measures well and controls poorly.** Three passes each killed their named families; the claim classes re-emerged in adjacent wording. The sweep is a good instrument and a bad regulator — don't confuse the two roles again.
2. **Genre defaults regenerate banned content.** The prompt asks for motivational coaching, whose native register IS causal claims and benchmarks, then bans the register's load-bearing moves one enumeration at a time. Negative constraints carve holes in a distribution the rest of the prompt keeps refilling. Positive grammars (allowed move types) beat ban lists — but that's the product-voice decision.
3. **A surface breach can be a product decision wearing words.** The reach-titled priorities are the outcome milestones restated as imperatives. No prompt fixes that; the milestone decision does.
4. **An always-on signal carries no information — twice in one day.** 142's /admin chip (fixed) and F12's Continuity hits (documented). When adding any marker/family, ask what makes it ever be OFF.
5. **A sub-agent's brief is part of the evidence chain.** Feeding readers a wrong "known facts" list produced confident wrong findings; the fix was cross-checking against an independently-validated artifact (the control text). Verify the brief before trusting the reading.
6. **The `also_catches` ratchet:** every phrasing a human read catches becomes permanent detector recall enforced by the self-test. Cheap, compounding, and it makes the arms race at least monotonic.
7. **Carried from the morning handoff, all still true:** mechanical sweep + human read find different things; "ban the claim" ≠ "ban delegating the claim"; compressed surfaces revert to genre defaults; a gate that fires 100% of the time is a tax; validated-by-accident; verify the post-commit tree, not the patch.

---

## Pending — manual steps

1. **Apply migration 023 before deploying the worker.** Carried, unchanged, still the one item that can break production.
2. **Push.** `cd ~/git/orpheus && git push origin main` — covers the four code commits plus this wrap.
3. **Schedule the claims-layer discussion (Josh + Andrew) — this now GATES 134.** Agenda at repo root, updated today with the status note and item 8. Live items: 2 (milestones — now carrying the title-breach mechanism), 4 (band-scale), 5 (cohort roll-up, deferrable), 6 (process), 8 (enforcement strategy — five decisions).
4. **Send Andrew the two review docs + the updated agenda** (carried).
5. **Confirm the deploys** — carried list plus this session's four commits (all backend; Railway worker + API, gated on item 1; nothing for Vercel this session).
6. **Two one-time provenance checks from the sweeps:** (a) does "$20–30 million annual portfolio, Kyrgyzstan" appear in Andrew's Experience text? It passed the gate via structural tokens (20/30), so if absent it's a fabrication the number gate structurally cannot see — worth its own ticket. (b) Confirm 3,246 followers / 972 net new are the milestone baseline values (they recur across runs and baselines are whitelisted).
7. **The 16:48 sweep dumps were never read in full** (flag-plus-context only; noted on 134). Give them a read before 134 closes, or fold into the next sweep's read.
8. **Delete stray Plane comments** (carried verbatim from the morning handoff: five escaped comments, three WAF fragments on 134, one misfiled on 140, the ORPHEUS-123 surplus, comment 34819698 on 131).
9. **Re-run Tarita post-deploy** (carried) — closes ORPHEUS-130's event.
10. **Re-invite Karen** (carried) — ORPHEUS-132's validation event.
11. **Andrew publishes `b03ca0f5` from /admin** (carried) — ORPHEUS-120's publish half.
12. **Decision Log pastes owed:** the rendered-excerpt whitelist decision [Josh, 2026-08-18] and the detect-and-ban pause [Josh, 2026-08-18] join the carried list (milestone-starter replacement, ORPHEUS-142's existence, ORPHEUS-131 degrade/publish, Ruling-2 outcome, beta-purge, ORPHEUS-90, ORPHEUS-85).
13. **Two beta testers possibly stuck in the in-app-browser trap** + email-vs-DM ops question (carried).
14. **Tim's confirmation list for Privacy Policy §11 and §7/§9** (carried verbatim).
15. **Empty `_to_delete/`** (carried; grew again — verify tarballs and git-lock piles from today).
16. **Andrew comms:** carried (a)–(n) from the morning handoff, plus (o) the enforcement-strategy pause and agenda item 8 are the headline for him; (p) the Kyrgyzstan provenance check (item 6a) is about his own profile text; (q) population benchmarks appear 1–4× per run and are undecided — his framework call.

---

## Pickup plan for next session

1. **NOT ORPHEUS-134.** Paused by decision. If Josh starts a session asking for 134 work, point at agenda item 8 and this handoff first.
2. **The deploy path is the highest-value unblocked work:** apply 023 → deploy worker + API → run one real job → observe the marker + /admin chip → close 131 and 142 together with their conventional closing comments.
3. **ORPHEUS-135** (footer) — settled, small, unaffected by the pause; ship text is in the ticket, do not paraphrase it.
4. **ORPHEUS-136** — one sentence, temp-0 rubric prompt; harness re-run + Andrew sign-off.
5. **ORPHEUS-138**, then **139 items 1–4 + 115** together — 115 now has fresh unit-relabel evidence from today's sweeps.
6. **ORPHEUS-141** — the between-cohorts window is still open.
7. **After the claims-layer discussion:** implement whatever mechanism is chosen (judge-and-rewrite spec is sketched in agenda item 8 and reuses the 131 gate plumbing; structured cheat sheet extends ORPHEUS-113).

---

## Caveats / things that will bite

1. **Migration 023 is written but NOT applied.** The worker writes both columns on every completion; an un-migrated database fails the write and takes the job down.
2. **Plane's `comment_html` takes REAL HTML tags**; only `&` and literal `<` need escaping. Read this before your first Plane comment.
3. **Plane WAF 403s any comment containing a command-line string.** Describe invocations in prose and point at the module docstring.
4. **`list_project_issues` truncates.** Dump to a file and `jq` it.
5. **`device_bash` command-size ceiling + corruption modes** (carried verbatim from the morning handoff): no heredocs for real files — `SendUserFile` + `device_commit_files` is byte-exact; patches in <4KB chunks, 76-col base64, md5 both sides.
6. **`device_bash` cannot delete; git in the mount leaves locks.** `mv` locks aside before every git invocation; `tmp_obj_*` warnings are cosmetic.
7. **The sweep's flag count under-reports — read the dump.** Still true at 99 patterns: the third sweep's raw flags included two detector false positives and missed nothing large, but only the read established that.
8. **F12 fires on every report by construction** — `zero_post_week_pct` is a registered metric whose citation is mandatory. Treat Continuity-summary F12 hits as expected; a fabricated share elsewhere is what the family is for.
9. **A single clean sweep run is not acceptance** (07-27 lesson; still true).
10. **Neither the sweep nor unit tests exercise `MILESTONE_STARTERS`** (b03ca0f5 has all four baselines measured).
11. **The sweep validates degrade behaviour, not the persistence path** — 023, the marker write and the chip remain unobserved in production.
12. **A reconciliation failure still fails the job by design** — don't generalize the degrade posture to it.
13. **Every report figure re-derives from `ingested_data` alone**; absence claims need an ingestion check; fix producers, not quoters (all carried).
14. **Correction to the morning handoff's caveat 14: a CLOUD session's container CAN run the backend suite** — `pip install --break-system-packages -r requirements.txt` works there (no Supabase/Anthropic egress, but pytest is fully local). This session ran all five baselines that way against re-tarred device trees. `device_bash` still cannot (no network); anything needing live API/DB is still Josh's terminal. The tar → stage → pytest workflow is in the morning handoff's caveat 14 and works verbatim.
15. **Editing the repo from a cloud session:** whole files via `SendUserFile` + `device_commit_files` (byte-exact, md5-verify both sides after write); this session did four such round-trips cleanly with mtime guards.
16. **`git fetch`/`ls-remote` fail from `device_bash`** — push status via `git reflog show refs/remotes/origin/main` (a real push writes `update by push`).
17. **Untracked-by-intent set** (carried, verified): `Draft_*.md` (including the agenda updated today), `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json`, `Signal_Score_Dimensions_Reference_*.md`, the LinkedIn review docs, `sweep_*/`, `snapshot_*.json`. `git check-ignore -v` before trusting any new root file. **Never `git add -A`.**
18. **Three sweep directories now sit gitignored on Josh's machine** (`..._145926`, `..._161540`, `..._164819`) — they are the day's acceptance evidence and are NOT backed up. Copy to Drive if they need to outlive the week.
19. **Carried unchanged:** structural evidence over logs; backfilled rows prove nothing; read a closing ticket's "still owed" list; `jobs`/`scores` column traps; closing events fire while nobody watches; ORPHEUS-119's narrow event; never pin `opsz`/rename fonts; Resend items; growth factors PROVISIONAL; module-load URL rewrites preserve `location.hash`.

---

## State of the repo right now

`main` at this wrap commit; the four code commits above are **not pushed** — `git push origin main` is owed and covers everything. Working tree otherwise clean; untracked-by-intent set verified (caveat 17), including today's updated agenda draft.

Plane this session: 142 moved to In Progress with the fix + acceptance comments; 134 carries four comments (first-pass acceptance record, second-pass ship, third-sweep reading + structural findings, direction change); nothing closed — 142/131 close together after deploy, 134 is decision-gated.

Docs this session: CLAUDE.md Active-phase tail rewritten to the post-pause state + two Decisions Made entries added (rendered-excerpt whitelist; detect-and-ban pause); PRODUCT_CONTEXT.md Narrative-generation row tail updated; the claims-layer agenda gained its status note and item 8; this handoff replaces the morning's.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` (Orpheus Social > 06_Operations > Shared Canon)
- **State of the Moment:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA` · **Decision Log:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Foundational Review FINAL 2026-07-16:** `1jTnli4JqpbXhNK3vATKgV7usss1TcUFDSoGRa-_kpwI` · **Andrew's v3 findings (2026-08-13):** `1umi0ZztF-Hha44dA-2Y64e1OSM4BxF0CMvDi8-1_rTU`
- **Standup package (2026-08-17), Rev 2:** `1cNIEnhM95dJlmoo7LSI48dtj897RmUqV3zvxn-HN8xY` — exhibits: window evidence `1bjikxZ6MT3ehsRfW2k9tzZZo_iCEHNGwWC_YZLWsLrk`, 90-day addendum prototype `1hV7jn_vcDJKUdgH0XKpRKX8x4Kl8bzX-XhYAjVQgMAc`, value-story threads `138EwhvNhLU1Ol-UPc6wS8jeJ6KBQOoNVD7GV6E8sGUY`.
- **Landing copy:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk` · **Privacy drafting:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — canonical published text is the repo markdown.
- **Pending pastes:** rendered-excerpt whitelist decision (new), detect-and-ban pause (new), milestone-starter replacement, ORPHEUS-142's existence, ORPHEUS-131 degrade/publish, Ruling-2 outcome, beta-purge, ORPHEUS-90 (carried since 06-24), ORPHEUS-85 (overdue).
