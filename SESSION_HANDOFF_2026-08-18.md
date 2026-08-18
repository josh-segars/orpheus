# Session Handoff — 2026-08-18

Replaces `SESSION_HANDOFF_2026-08-17.md` — everything it described carries forward or resolved as follows:

- **Its pickup plan item 1 was taken.** It said: hold the claims-layer discussion, then implement 134 + 135 (+136). The discussion still has not happened, but two of the four decisions it was meant to settle had *already been made in the Decision Log on 08-15 and 08-16* and nobody had noticed — so 135 and 137(b) were never actually blocked. 134 + 137's first pass shipped instead.
- **Its caveat 2 resolved, and then reopened.** 131's closing event ("stochastic, nobody is watching for it") fired five times during the 134 acceptance sweep. The degrade path works exactly as designed. But the reason it fired is a new bug — see ORPHEUS-142 — so 131 stays open.
- **Its caveat 9 (Plane `comment_html` takes real tags) was correct and I violated it anyway.** Cost five comments. There is now a *second* Plane quirk on top of it: a WAF rule that 403s any comment containing a command-line string. Both are in caveats below.
- Its Pending items all carry, renumbered below. Migration 023 is still not applied and is still the sharpest item here.
- The 08-17 test baselines (575 backend / 196 frontend) were re-measured against the pre-change tree and were correct.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-134 | Spec 2 narrative-prompt guardrails | 🔄 **In Progress — first pass shipped + swept; SECOND PASS REQUIRED.** Scope is in the ticket description. |
| ORPHEUS-137 | Absence-assertion ban + recommendations excluded | 🔄 **In Progress — prompt half shipped and verified clean (0 hits vs 10 in control); code-owned half untested.** |
| ORPHEUS-142 | Prose-number whitelist excludes verbatim profile figures | 🆕 **Backlog, high — filed this session. Blocks closing 131.** |
| ORPHEUS-141 | Active-week config change (Continuity) | ⏳ Backlog, medium — filed this session, owed since the 08-15 decision |
| ORPHEUS-131 | Prose-gate retry budget | 🔄 In Progress — degrade validated live ×5; **hold open until 142 lands** |
| ORPHEUS-135 | Signal-legibility footer | ⏳ Backlog, high — **no longer agenda-gated**; ship text is in the ticket |
| ORPHEUS-136 | Spec 1: Dim 4 preamble sentence | ⏳ Backlog, high — never decision-blocked; needs harness re-run + Andrew sign-off |
| ORPHEUS-138 | Comments.csv fragmentation | ⏳ Backlog, medium — decision-independent |
| ORPHEUS-139 | 80–100 range, window labels, engagement numerator | ⏳ Backlog, medium — **gained item 4** (third-party attribution, per the 08-15 follow-up) |
| ORPHEUS-115 | Narrative restates/mislabels metrics | ⏳ Backlog, medium — its open "which label" question is answered by the 08-15 decision; land with 139 |
| ORPHEUS-116 | "What Travels" reach-driver analysis | ⏳ Backlog, medium — **flagged: its decided scope contradicts Rulings 2/3.** Needs re-scope or re-blessing before anyone builds it |
| ORPHEUS-132 / 130 / 120 / 119 | unchanged | 🔄 In Progress — events have not fired |
| ORPHEUS-133 / 140 / 111 / 107 / 99 / 94 / 84 / 48 / 45 / 42 / 41 / 40 | unchanged | ⏳ Backlog |

Baselines: backend pytest **641 green** (575 at session start → 590 after 134/137 → 641 with the sweep's tests); frontend vitest **196 green**; `tsc -b --noEmit` clean. All measured, and the backend count was re-verified by re-tarring the post-commit tree rather than trusting the patch.

---

## Commits this session

All three are **committed on `main` and NOT pushed.**

| SHA | Subject |
|---|---|
| `73aead8` | Ban reach claims and unverifiable absence claims in narrative prompts. Refs ORPHEUS-134, ORPHEUS-137. |
| `0ebf031` | Drop the recommendations milestone starter. Refs ORPHEUS-137. |
| `b63d92e` | Add the claims-layer acceptance sweep. Refs ORPHEUS-134, ORPHEUS-137. |

Plus this wrap (docs + handoff). These three commits carry `Co-Authored-By` / `Claude-Session` trailers, which no earlier commit in this repo does — flagged to Josh at the time; amend if you want the log uniform.

---

## What changed / what shipped

### The session started as a review, not a build

Josh asked for a cross-check of every open ticket against the Decision Log and Andrew's 2026-08-17 standup package. That review is the reason the rest of the session happened, and its finding generalises: **two high-priority tickets had been unblocked for days and their bodies still described them as blocked.**

- **ORPHEUS-135** — the footer wording was settled 2026-08-16, but the ticket still quoted the Foundational Review sentence ("*Signal Scores* measure whether…") as the copy to ship. Building from the ticket would have shipped the public-vocabulary violation the decision exists to prevent.
- **ORPHEUS-137** — part (b) was answered twice (08-15, 08-16), and the 08-16 entry's own follow-up assigned the rewrite to Josh.
- **ORPHEUS-141 did not exist.** The 08-15 active-week decision says "Josh creates the config ticket." Nothing had been filed.
- **ORPHEUS-139** was assigned the third-party-attribution rule verbatim by the 08-15 follow-up and had not received it.
- **ORPHEUS-116's** decided scope (2026-07-22, "contrarian openers break out 75% and reach ~10.5k — lead with that structure") is the arithmetic Ruling 2 bans and the effect size Ruling 3 forbids. Nothing formally overrode it; it predates the Review's implementation.

All ticket bodies were corrected and 141 was filed. **The transferable lesson: a decision recorded only in the Decision Log does not reach the person building from a ticket.** The 08-15 entry says this about itself ("This needs a Plane ticket rather than staying in prose — this is exactly the decision class the Spec 2 drift came from") and it happened again to the same decision.

### ORPHEUS-134 + 137 first pass — `73aead8`

A `## Claims layer` section in `SYSTEM_PROMPT_TEMPLATE` (`backend/agents/narrative.py`), plus Core rule 9 pointing at it.

**The v3 Part 1 ask turned out to be moot in a useful way.** It asked whether the guardrail was applied to the sub-dimension generator or only the dimension generator. `generate_narratives` makes a *single* Claude call, so the four dimension narratives, all 13 sub-dimension payloads and the cheat sheet read one prompt — one insertion covers every surface. The section still enumerates the surfaces it binds, because the compressed forms otherwise read as exempt.

Five rules: reach-claim ban with the vocabulary enumerated (reach, impressions, visibility, distribution, exposure, algorithmic favor) and the hedged forms named as the same claim; threshold ban quoting the released report's own phrasing; the two permitted framings with human-reader preferred; the absence-assertion ban quoting the b03ca0f5 failure verbatim and adding *an absence you cannot verify may never become an action item*; and recommendations/endorsements/skill-ordering out of scope entirely.

One guard against over-correction: the section states explicitly that observable gaps remain fair game, or the ban would have collapsed the score-calibration section that legitimately names what the profile does not do.

**Two finds neither ticket had.** The prompt's own cheat-sheet priorities example read `**Target: 2 new recommendations in 30 days.**` — it was modelling the exact action item 137 forbids, sitting next to the instruction. And `frontend/src/mocks/fixtures/signalScoreJob.ts` carried a full "Request Recommendations Strategically" priority, which is what the app renders in dev. Both replaced.

**Deliberately NOT included:** the trajectory addendum's register rules (side-by-side never causal, no member-level recency claims). Andrew's standup package Section 6 asks for them inside 134's guardrail set, but they are his position for discussion, not a decision. They sit on the ticket as PROPOSED.

### ORPHEUS-137's code-owned half — `0ebf031`

`MILESTONE_STARTERS` contained `MilestoneTarget("new_recommendations", "2", "New recommendations", None)`. **Prompt text could never have policed this** — the value is code-owned and handed to the agent to phrase, so it never passes through the prompt. A member with no measurable baseline would still have been handed "2 / New recommendations" on their cheat sheet, and the sparse-member card is exactly where it would have gone unnoticed.

Replaced rather than deleted: `_parse_cheat_sheet_payload` requires 3–4 milestones and there were exactly three starters, so dropping to two fails a zero-baseline member's job on a count validation error — a claims fix becoming an outage for the members least able to absorb one. Decision and rationale are in CLAUDE.md "Decisions Made".

### The acceptance sweep — `b63d92e`

`backend/scripts/claims_sweep.py`. Twelve breach families from Rulings 2/3, the five critical v3 findings and the 08-16 exclusion decision. Read-only by construction, with a test asserting at source level that the file contains no mutation call and every `.table()` carries a `.select()` — because it is pointed at delivered reports and `regenerate_report.py` sits in the same package doing the opposite.

Three properties that make its output worth reading:

1. **Self-test that aborts the run.** Every HIGH family must catch its own verbatim v3 exemplar, and 14 sentences of permitted-register prose must not trip HIGH.
2. **A control pass over the stored delivered text.** Known to contain 20 breaches, so it is the only evidence the detector fires on real prose rather than only its own fixtures. Zero HIGH on the control makes the script say so loudly.
3. **A full per-run text dump**, with the summary stating that the dump is the acceptance artifact and the exit code is not.

**The tiering was corrected during the build and that correction is worth keeping.** Two patterns were HIGH in the first draft and fired on legitimate prose: `"you do not have"` hits observable gaps that Core rule 3 permits, and bare `"recommendations"` has an ordinary advice sense. Both moved to REVIEW, because whether they are breaches depends on ingested-set membership a regex cannot see. Measured after: 14/14 breach shapes caught at HIGH, 0 false positives across 14 permitted sentences. Both cases are pinned in tests.

`.gitignore` gained `sweep_*/` and `snapshot_*.json`. The second closes a pre-existing hole: `regenerate_report.py` has described its snapshots as untracked-by-default since ORPHEUS-112 and nothing enforced it, while the wrap ritual still runs `git add -A`.

### The sweep RAN — and this is the most important section here

Josh ran it in his terminal (the container has no egress; `device_bash` has no network either). Control: 56 strings, **26 HIGH**, and the hits landed 1:1 on v3's documented findings — F1 on Posting Presence, F2/F3 on Behavioral Signal Strength, F4 on Signal Quality, F5 on Alignment + priority 1, F6 on both rhythm items, F7/F8 on priority 4 and the completeness improvements. The detector is validated on real prose.

Five fresh generations: flagged **0, 1, 3, 0, 1**.

**Then the dump read corrected that to 5 of 5.** The attribution-instruction shape appears in every run; the detector caught three. Missed: "Review your top-performing posts for common patterns… and adjust your content approach accordingly", "which posts drew the most meaningful responses", "examine what made it *travel further* than the others". One false positive inflated run 3 — F5 matched "doubles" in "doubles **as** a positioning statement".

Corrected picture:

- **Clean:** all four dimension narratives, all thirteen sub-dimension slots, all five runs. 137's families scored **0** against 10 in the control — recommendations, endorsements and skill-ordering are gone from generated text entirely.
- **Not clean:** the cheat sheet. Three rhythm items and one priority ("a pace that consistently produces stronger reach").
- **Uncovered:** the attribution-instruction family. The first pass bans *making* a reach claim and not *delegating it to the member*. v3 named this family explicitly and the implementation missed it.

### ORPHEUS-142 — found by accident, and it matters more than 134's residual

The prose gate degraded on **all five runs**, and every rejected figure was a *correct* citation: `$400 million`/`$100 million` from Andrew's own Experience descriptions, `80 listed skills`, `13-entry experience history`, `88 percent` derived from a whitelisted 46/52, `6,700` as a rounded 6,740.

Root cause: `build_number_whitelist(scoring_output, milestone_targets)` never receives `zip_data`, so **no figure appearing only in the verbatim Profile Content can ever be whitelisted** — while the prompt *requires* profile claims to be grounded in exactly that text. The prompt says cite the profile; the gate rejects it for doing so.

Consequences: 3× generation cost and latency for any member with numbers in their profile (this is 131's own six-minute job, misread as an unlucky generation); `prose_gate_degraded` set on essentially every report, so /admin's chip carries no information; and 131's degrade is masking this rather than fixing it.

---

## Architectural notes worth carrying forward

1. **A mechanical sweep and a human read find different things, and you need both.** The sweep found a borderline claim in `Topic Consistency.best_practices` that v3's human pass missed. The human read of the sweep's own dumps found six breaches the sweep missed. Neither is a substitute; the sweep's job is to say where to look first.
2. **"Ban the claim" and "ban delegating the claim" are different rules.** Guardrails written against observed breach text will inherit that text's blind spots. v3 listed the attribution items separately from the claim items and the implementation still merged them into one idea and lost half.
3. **Compressed surfaces revert to genre defaults.** Every residual breach landed in cheat-sheet priorities and rhythm items, none in prose. A six-word imperative has no room to hedge, so the model falls back on the register of ordinary social-media advice. Constraints need restating *at* the compressed surface, not only in a general section.
4. **A gate that fires 100% of the time is not a gate, it is a tax.** And its marker column becomes decoration. Whenever a rejection rate looks high, check whether the thing being rejected is actually wrong before hardening the response.
5. **"Protected by accident" has a sibling: "validated by accident."** 131's closing event fired five times inside a sweep built for a different ticket. Worth asking, when building any harness, which *other* open questions it happens to observe.
6. **Verify a patch by re-reading the post-commit tree, not the patch.** Every claim of "N tests green" in this handoff was measured by re-tarring the device's committed tree and re-running, with md5s compared against what was tested.

---

## Pending — manual steps

1. **Apply migration 023 before deploying the worker.** Carried, unchanged, and still the one item that can break production: the worker writes both columns on every completion, so an un-migrated database fails that write and takes the job down. Prior migrations went to cloud via the Supabase MCP.
2. **Push.** `cd ~/git/orpheus && git push origin main` — covers all three code commits plus this wrap.
3. **Delete stray Plane comments.** The MCP has no edit or delete, so these need doing by hand. **Five escaped comments** (posted with tags HTML-escaped, rendering as raw markup; corrected reposts sit directly below each): `f14e9bf3` on 135, `25b1eb11` on 137, `841f734f` on 134, `71928dc8` on 139, `8de5b917` on 116. **Three WAF-workaround fragments on 134:** `092af115`, `f370635f`, and one probe comment. **One misfiled comment on ORPHEUS-140:** `3997333d` (a placeholder that belonged on 131; the real 131 comment is `19c863dc`). Joins the carried "delete the surplus ORPHEUS-123 comments (keep `6a6c67ce`)" and comment `34819698` on 131.
4. **Schedule the claims-layer discussion** (Josh + Andrew; Tim not needed) — agenda at repo root, `Draft_Claims_Layer_Discussion_Agenda_2026-08-14.md` (untracked). **Its scope is now narrower:** 135 and 137(b) are settled, so what remains is milestones/card design, band-scale visibility (Josh + Tim, routed with the 8/13 memo), whether the trajectory addendum satisfies the comparison-view launch dependency (Josh), and ORPHEUS-116's re-scope.
5. **Send Andrew the two review docs + agenda** — his v3 asks are answered in `outputs/Review_Reconciliation_b03ca0f5_2026-08-14.md`.
6. **Confirm the deploys** — `0aca889`, `8bbc8f0`, the four ORPHEUS-131 commits, and this session's three (Vercel for the /admin chip and the mock fixture; Railway for the worker + API, gated on item 1).
7. **Re-run Tarita** post-deploy: `https://app.orpheussocial.com/signup?code=ORPH-Z32A-K7VA` (closes ORPHEUS-130's event).
8. **Re-invite Karen** (carried) — her acceptance is ORPHEUS-132's validation event, and she'll see the new consent checkbox where the link used to be instant (heads-up first).
9. **Andrew publishes `b03ca0f5` from /admin** (carried) — closes ORPHEUS-120's publish half.
10. **Decision Log pastes owed:** the milestone-starter replacement decision [Josh, 2026-08-17] and the existence of ORPHEUS-142 join the ORPHEUS-131 degrade/publish decision, the Ruling-2 outcome, the beta-purge decision [Josh, 08-14], ORPHEUS-90 (4.6 acceptance, carried since 06-24), and ORPHEUS-85 (self-serve revision, overdue).
11. **Two beta testers possibly stuck in the in-app-browser trap** (carried) + the email-vs-DM invitation ops question.
12. **Tim's confirmation list for Privacy Policy §11 and §7/§9 claims** (carried verbatim).
13. **Empty `_to_delete/`** (carried, and it grew again — see State of the repo).
14. **Andrew comms, carried:** (a)–(k) from the 08-17 handoff unchanged, plus (l) the replacement milestone starter's value of 12 is PROVISIONAL and his to tune; (m) ORPHEUS-116's scope needs his re-blessing or re-scope; (n) the `Topic Consistency.best_practices` line ("content that clusters around the problem they solve tends to build stronger audience recognition") is a borderline hedged causal claim whose object sits in the permitted human-reader register — his call, and v3's human pass did not flag it.

---

## Pickup plan for next session

1. **ORPHEUS-142** (high, new). It blocks closing 131, it makes every future acceptance sweep noisy, and it is costing 3× on every report right now. Four sub-decisions in the ticket; the profile-content whitelist is the main one. Do not widen to "any number in the input" — that defeats ORPHEUS-121.
2. **ORPHEUS-134 second pass**, then re-run the sweep. Three items in the ticket description: the attribution ban (observe, never attribute), cheat-sheet-specific reinforcement on priorities and rhythm, and the two detector fixes without which the next run cannot verify itself.
3. **ORPHEUS-135** — small, settled, and it qualifies the claims 134 constrains. Ship text is in the ticket; do not paraphrase it.
4. **ORPHEUS-136** — one sentence, but temp-0 rubric prompt, so harness re-run + Andrew sign-off on any Dim 4 movement.
5. **ORPHEUS-138**, then **139 items 1–3 + 115** together (same figures, adjacent surfaces).
6. **ORPHEUS-141** — the between-cohorts window is open *now* (no cohorts running). Landing it later means waiting for the next gap.
7. **Not ORPHEUS-140** — still parked.

---

## Caveats / things will bite

1. **Migration 023 is written but NOT applied.** Repeated from Pending 1 because it is the one item that can break production.
2. **Plane's `comment_html` takes REAL HTML tags** — only entities inside the text (`&`, a literal `<`) need escaping. The 08-17 handoff said exactly this and it was violated anyway, costing five comments. `description_html` behaves the same way. **Read this caveat before your first Plane comment, not after.**
3. **Plane has a WAF rule that 403s any comment containing a command-line string.** `python -m backend.scripts.claims_sweep --self-test` in a comment returns 403; the same comment with the commands described in prose posts fine. Confirmed with a one-line probe. It is not a length limit — a 4KB comment posts, a 200-byte one with a command does not. Describe invocations in prose and point at the module docstring.
4. **`list_project_issues` still truncates.** Dump to a file and `jq` it.
5. **`device_bash` has a hard command-size ceiling, and content near it fails two different ways.** A ~13KB command containing a heredoc was silently *truncated* — bash reported `here-document delimited by end-of-file`, so nothing was written. Below that, a 6000-character single-*line* base64 chunk twice arrived with a checksum mismatch (corrupted, not truncated), while the same payload wrapped at 76 columns in 32–55 line chunks arrived clean. Practical rules: **for a single file of any real size, don't use heredocs at all — `SendUserFile` then `device_commit_files` is the supported path and it is exact** (this handoff went that way after the heredoc route failed). For patches, keep each chunk under ~4KB, wrap base64 at 76 columns, and **md5 every chunk on both sides** plus the decoded result before `git apply`. A silent corruption here would apply a mangled patch.
6. **`device_bash` cannot delete, and git in the mount leaves locks.** `rm` is refused; retired files get `mv`'d into `_to_delete/`. `git apply`/`git commit`/`git add` cannot unlink their own `.git/*.lock` — the operation succeeds but the next git command blocks. Move locks aside before *every* git invocation; a shell function is worth the two lines.
7. **The sweep's flag count under-reports. Read the dump.** Three of five runs read clean on flags while every one of them contained a breach. This is not a bug to fix so much as the nature of the tool, and the script says so in its own summary — but it is very easy to read `0 HIGH` and move on.
8. **A single clean sweep run is not acceptance** (the 07-27 lesson, now with direct evidence). Spot-check several generations and read them.
9. **Neither the sweep nor the unit tests exercise `MILESTONE_STARTERS`.** b03ca0f5 has measured baselines for all four milestones, so the starter path never fires. Anything about starters needs a sparse member's job or a synthetic scoring output.
10. **The sweep validates the degrade *behaviour*, not the persistence path.** It calls `generate_narratives` directly and never writes, so migration 023, the `run_pipeline` marker write and the /admin chip remain unobserved in production. 131's acceptance items 2 and 3 are still untested live.
11. **A reconciliation failure still fails the job by design** and is now the only gate in the narrative path that does. Don't generalise 131's degrade posture to it.
12. **Every report figure re-derives from `ingested_data` alone** (carried). **An absence-claim in prose needs an ingestion check, not an operand check** (carried) — and prose can quote a wrong input faithfully; fix producers, not quoters.
13. **ORPHEUS-136 is one sentence but framework-affecting** (carried) — temp-0 rubric prompt, so Dim 4 can shift deterministically.
14. **Sandbox limits — the workaround is worth keeping.** Both suites run: `tar` the backend into `_to_delete/`, stage the tarball into the container, `pip install --break-system-packages -r requirements.txt`, run pytest there. The device has `node_modules`, so `npx vitest run` and `npx tsc -b --noEmit` run via `device_bash` (keep vitest under the ~45s timeout — the full suite takes ~31s). **Neither the container nor `device_bash` has network access to Supabase or the Anthropic API** — anything that needs a live API call is Josh's terminal.
15. **Editing the repo from a cloud session: patch for edits, `device_commit_files` for whole files.** For edits to existing files, generate a unified diff in the container, gzip+base64 it in wrapped chunks with per-chunk md5s, `git apply --check` then apply. For a new or wholly-rewritten file, skip all that and use `SendUserFile` + `device_commit_files` — one call, byte-exact, no chunking. Splitting one change into two commits is cheap: build the intermediate tree in the container, transfer only the *second* patch, apply it in reverse to reach the intermediate state, commit, then re-apply forward and commit again.
16. **`git fetch`/`ls-remote` fail from `device_bash` (no SSH agent)** but push status is knowable via `git reflog show refs/remotes/origin/main` — a real push writes an `update by push` entry.
17. **Untracked-by-intent set** (carried, verified this session): `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json`, `Signal_Score_Dimensions_Reference_*.md`, the LinkedIn review docs, and now `sweep_*/` + `snapshot_*.json`. `git check-ignore -v` before trusting any new root file. **Never `git add -A`.**
18. **Carried unchanged:** structural evidence over logs; backfilled rows prove nothing; actor's role can hide the behavior; read a closing ticket's "still owed" list; `jobs`/`scores` column-name traps; closing events fire while nobody watches; ORPHEUS-119's narrow event; never pin `opsz` / never rename fonts; Resend items; growth factors PROVISIONAL; module-load URL rewrites preserve `location.hash`.

---

## State of the repo right now

`main` at this wrap commit. The three code commits are committed and **not pushed** — `git push origin main` is owed. Working tree otherwise clean.

Untracked by intent, verified: the list in caveat 17. Both `sweep_b03ca0f5_2026-08-17_180624/` and `sweep_b03ca0f5_2026-08-17_181025/` are correctly ignored by the new `sweep_*/` rule — the second contains the five run dumps and the control dump that constitute the ORPHEUS-134 acceptance evidence. **They are local to Josh's machine and gitignored, so they are not backed up anywhere.** If that evidence matters beyond this week, copy it to Drive.

`_to_delete/` grew again and is worth emptying (Pending 13). It now also holds `orpheus_backend_134.tgz`, `verify_134.tgz`, `verify_sweep.tgz`, `patch134/`, `patchC/`, and a further pile of `gitlocks/`.

Plane this session: ORPHEUS-142 and 141 created; 134 and 137 moved to In Progress with full comments and rewritten scope; 135, 139 and 116 bodies corrected; progress comments on 131, 134, 137; 137 retitled. Nothing closed — nothing finished.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` (Orpheus Social > 06_Operations > Shared Canon)
- **State of the Moment:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA` · **Decision Log:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Foundational Review FINAL 2026-07-16:** `1jTnli4JqpbXhNK3vATKgV7usss1TcUFDSoGRa-_kpwI` · **Andrew's v3 findings (2026-08-13):** `1umi0ZztF-Hha44dA-2Y64e1OSM4BxF0CMvDi8-1_rTU`
- **Standup package (2026-08-17), Rev 2:** `1cNIEnhM95dJlmoo7LSI48dtj897RmUqV3zvxn-HN8xY` — Section 1 is decided-of-record and checks out against the Decision Log; Sections 2–6 are Andrew's position for discussion. Its exhibits: window evidence `1bjikxZ6MT3ehsRfW2k9tzZZo_iCEHNGwWC_YZLWsLrk`, 90-day addendum prototype `1hV7jn_vcDJKUdgH0XKpRKX8x4Kl8bzX-XhYAjVQgMAc`, value-story threads `138EwhvNhLU1Ol-UPc6wS8jeJ6KBQOoNVD7GV6E8sGUY`.
- **Landing copy:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk` · **Privacy drafting:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — canonical published text is the repo markdown.
- **Pending pastes:** milestone-starter replacement (new), ORPHEUS-142's existence (new), ORPHEUS-131 degrade/publish, Ruling-2 outcome, beta-purge decision, ORPHEUS-90 4.6 acceptance (carried since 06-24), ORPHEUS-85 self-serve revision (overdue).
