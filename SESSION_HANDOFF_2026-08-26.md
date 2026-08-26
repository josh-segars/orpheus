# Session Handoff — 2026-08-26

Replaces `SESSION_HANDOFF_2026-08-18_part2.md`. This session spanned 08-19 → 08-26 (one long-running cloud session) and resolved the predecessor's sharpest threads:

- **Its Pending 1 (migration 023) is APPLIED** — to production, 2026-08-26, via the session's Supabase connection; registered as `20260826132232`, columns verified. All 48 pre-existing job rows at the no-back-fill default.
- **Its Pending 2 (push) was done 08-19** (reflog-verified) before any other work.
- **Its Pickup 2 (the deploy path) is DONE and both gated tickets are CLOSED.** Worker + API deployed; one real job (`2ebd4432`) ran clean on the first attempt with the marker written; **ORPHEUS-131 and 142 closed 2026-08-26** with conventional closing comments.
- **Its Pending 11 (Andrew publishes from /admin) happened — for the right report.** Andrew published `2ebd4432` (NOT `b03ca0f5`, deliberately — see caveat 9); the ORPHEUS-120 gate held against him as a client beforehand and the release path fired end-to-end. **ORPHEUS-120 closed 2026-08-26.**
- **The deploy surfaced and closed a new production incident same-day:** **ORPHEUS-143** (anthropic SDK 1.0 removed the `temperature` kwarg; fixed by pinning 0.125.0, `e958e0f`).
- **The 134 pause is unchanged** — no prompt or detector work was done. What this session added to that thread is analysis: two Drive prep documents for the claims-layer discussion (the prompt-vs-claims conflict map and the verbatim prompt set — see Shared canon).
- Everything else it carried, carries below, renumbered.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-131 | Prose-gate retry budget → degrade | ✅ **Done 2026-08-26** — 023 applied, worker deployed, real-job marker write verified (provenance chain in the closing comment) |
| ORPHEUS-142 | Prose-number whitelist admits profile figures | ✅ **Done 2026-08-26** — numeric-rich profile clean on first attempt in production |
| ORPHEUS-143 | anthropic SDK 1.0 removed `temperature` (NEW this session) | ✅ **Done 2026-08-26** — pinned 0.125.0 (`e958e0f`), validated same hour |
| ORPHEUS-120 | Advisory draft gate + release side | ✅ **Done 2026-08-26** — gate held against first real dual-role user; publish exercised; report-ready email fired. Trigger-timing question stays open by design |
| ORPHEUS-144 | /admin publish path undiscoverable (NEW) | ⏳ Backlog, **high** — four exhibits from the first real publish; suggested fixes on the ticket |
| ORPHEUS-145 | Deliberate SDK 1.0 migration + pin all deps (NEW) | ⏳ Backlog, medium — GATED on an ORPHEUS-75 harness re-run before the anthropic pin moves |
| ORPHEUS-134 | Spec 2 narrative-prompt guardrails | 🔄 In Progress — **PAUSED by decision [Josh, 2026-08-18], unchanged.** Do NOT resume prompt/detector work without the claims-layer discussion (agenda item 8) |
| ORPHEUS-135 | Signal-legibility footer | ⏳ Backlog, high — settled wording, ship text in the ticket; **now the top small pickup** |
| ORPHEUS-136 | Spec 1: Dim 4 preamble sentence | ⏳ Backlog, high — harness re-run + Andrew sign-off |
| ORPHEUS-138 / 139 / 115 | parser hardening / metrics polish / mislabels | ⏳ Backlog, medium — unchanged (115 carries the 08-18 relabel evidence) |
| ORPHEUS-141 | Active-week config change (Continuity) | ⏳ Backlog, medium — between-cohorts window still open |
| ORPHEUS-116 | "What Travels" reach-driver analysis | ⏳ Backlog — still needs re-scope/re-blessing (contradicts Rulings 2/3) |
| ORPHEUS-132 / 130 / 119 | consent gate / sign-in / narrow event | 🔄 In Progress — events have not fired (Karen re-invite; Tarita re-run; 119's event) |
| ORPHEUS-133 / 140 / 111 / 107 / 99 / 94 / 84 / 48 / 45 / 42 / 41 / 40 | unchanged | ⏳ Backlog |

Baselines: backend pytest **686 green, carried from 08-18, NOT re-run** — the only backend-tree change this session is the requirements pin, which the production run exercised more convincingly than the suite would. Frontend **196 vitest carried from 08-17, not re-run; no tsc needed** (zero frontend changes).

---

## Commits this session

| SHA | Subject | Pushed? |
|---|---|---|
| `e958e0f` | Pin anthropic to 0.125.0: SDK 1.0 removed the temperature kwarg. Refs ORPHEUS-143. | ✅ pushed 08-26, deployed to both services |
| (this wrap) | Session handoff: 2026-08-26. Retire 2026-08-18 part 2. | ❌ push owed |

---

## What changed / what shipped

### The claims-layer analysis (08-19/20) — two Drive documents, no code

Working from the discussion agenda, the narrative prompt was read line-by-line against the shipped Claims rules and the conflicts mapped verbatim. **Key revision to the 08-18 architectural read:** threshold mutation is not purely a stochastic tail — the prompt's own quantitative score-calibration scale *teaches* the banned register ("enough to register but not yet building strong signal" vs rule 1's banned "enough activity to register with the algorithm"). Eight findings, split:

- **Category A — wording self-contradictions, fixable in place under any mechanism:** the calibration scale seeds the threshold register; "ordered by leverage (highest-impact first)" demands a ranking rule 3 forbids stating; the default `behind_curtain` mechanics config bans rule 2's own signal-legibility example (squeezing everything into the human-reader register, where thresholds relocate); the dormant `business_development`/`recruiting` focus instructions literally instruct reach emphasis (a landmine the first advisor config will trip).
- **Category B — structural; only the agenda decisions resolve them:** forward guidance is *required* to be grounded in reach metrics (item 8 decision 1, instrument-vs-coach); the measurable-target invitation + supplied outcome milestones instruct the reach-titled-priorities residual (item 2); Q8's "recommendations should plausibly move the client toward what they described" builds efficacy into selection; and population benchmarks are the only comparison class the rules leave standing (item 8 decision 4) — banning them without supplying a replacement referent pushes the pressure back into thresholds.

Consequence for the acceptance-bar question (8.3): zero-HIGH from prompt work alone is unreachable while the Category B instructions stand. Both docs are in Drive (IDs in Shared canon): the conflict map, and a byte-exact verbatim dump of all three pipeline prompts (Dim 1 + Dim 4 rubric calls as sent at temp 0; the narrative call rendered under platform defaults; all advisor-config variants; the retry-correction and slot scaffolding texts) — extracted programmatically at `58d2f1b`, not retyped. **134 remains paused; none of this was applied to the prompt.**

### The production unblock (08-26) — four tickets closed in one day

**Migration 023 applied** (additive, safe ahead of the worker — old worker never touches the columns). Then worker + API deployed. **The first fresh image build in weeks failed every job at the rubric stage** (`40fa5809`, 3/3): anthropic SDK 1.0.0 (released 08-20) removed `temperature`/`top_p`/`top_k` — API-deprecated, `extra_body` as the escape hatch — and the unpinned `anthropic` line pulled it. Filed **ORPHEUS-143**, pinned 0.125.0 (`e958e0f`, verified against both SDK versions' signatures in the sandbox), redeployed. **Job `2ebd4432` then ran clean: complete, attempt 1, ~2 minutes, no gate rejections, marker written false** — the 131/142 acceptance event. Provenance note for the marker: false is also the column default; the write is attributable because `40fa5809`'s traceback line numbers proved the deployed tree and `e958e0f` changes only requirements.txt.

**The first real publish followed the same afternoon.** Andrew, dual-role, was correctly blocked from both of his complete-but-unpublished reports on View My Reports (the 120 gate holding on first contact) and then published `2ebd4432` from the /admin narrative editor — five per-section status flips, `published_at` stamped 15:01Z on the last one, report-ready email fired (his once-per-client feedback ask). Report reads well per Andrew. The path failed discoverability twice on the way (no publish affordance; editor mounts off-screen below 48 job rows) and surfaced the raw-JSON cheat_sheet editor — all filed as **ORPHEUS-144** with suggested fixes.

### Also this session

The premise "reports are failing because of the prompts/claims discrepancy" was checked against production before acting: **the claims layer is prompt text with no runtime enforcement and cannot fail a job** — the only failure-capable surfaces are the prose gate, the parse/shape validators, and infrastructure. That finding redirected the fix from "remove/modify the claims layer" to "deploy the already-written gate fixes," which is what unblocked everything. Removing the claims layer would have bought zero reliability and reopened ~20 breaches per report.

---

## Architectural notes worth carrying forward

1. **Railway freezes your dependencies by accident and thaws them at the worst time.** Redeploy reuses the image; Deploy Latest Commit (command palette) rebuilds fresh and resolves every unpinned requirement to that day's latest. The 143 incident waited six days after the SDK release for the first true rebuild. Pin everything (ORPHEUS-145).
2. **A marker whose default equals its common value cannot self-prove.** `prose_gate_degraded=false` is indistinguishable from the unwritten default; the write was attributed via a provenance chain (traceback line numbers proved the tree; the delta was pin-only; the code writes unconditionally). When designing markers, consider defaults that differ from any written value — or accept that verification needs external evidence.
3. **The claims layer cannot fail a job — keep the layers straight.** Prompt rules shape text; the gate and validators fail jobs. "Reports failing because of the claims layer" decomposed into a gate-vs-prompt conflict (fixed, 142) and an SDK regression (fixed, 143). Check what actually terminates the flow before choosing what to remove.
4. **The prompt teaches what the detector bans** (conflict-map finding 1). Three passes of detect-and-ban plateaued partly because the calibration scale kept supplying the next threshold paraphrase. Instruction-seeded breaches are not stochastic tails; grep the prompt for the banned register before concluding the model can't follow rules.
5. **First-real-user sessions are UX audits.** Andrew's first publish produced four discoverability defects in ten minutes, none of which any of us could see anymore. Budget for the walk-through; file everything (144).
6. **An admin freetext editor over structured storage bypasses every generation-time gate.** The cheat_sheet row's milestone values are parser-enforced at generation and completely unprotected under /admin edit; the API's defensive parse fails to `null` silently. The safeguard perimeter is only as wide as the narrowest write path.
7. **Carried, all still true:** detect-and-ban measures well and controls poorly; genre defaults regenerate banned content; a surface breach can be a product decision wearing words; an always-on signal carries no information; a sub-agent's brief is part of the evidence chain; the `also_catches` ratchet; mechanical sweep + human read find different things.

---

## Pending — manual steps

1. **Push.** One command covers the wrap commit (`e958e0f` is already pushed and deployed).
2. **Schedule the claims-layer discussion (Josh + Andrew) — still GATES 134.** Live agenda items: 2 (milestones), 4 (band-scale), 5 (cohort roll-up, deferrable), 6 (process), 8 (enforcement strategy, five decisions). Two new pre-reads in Drive: the conflict map (its Category B findings ARE items 2/8.1/8.4 expressed as prompt text) and the verbatim prompt set.
3. **Send Andrew the review docs + agenda + the two new Drive docs** (carried, expanded).
4. **Two one-time provenance checks from the sweeps** (carried): (a) does "$20–30 million annual portfolio, Kyrgyzstan" appear in Andrew's Experience text? (b) confirm 3,246 followers / 972 net new as milestone baseline values.
5. **The 16:48 sweep dumps were never read in full** (carried; noted on 134).
6. **Delete stray Plane comments** (carried verbatim: five escaped comments, three WAF fragments on 134, one misfiled on 140, the ORPHEUS-123 surplus, comment 34819698 on 131).
7. **Re-run Tarita post-deploy** (carried) — closes ORPHEUS-130's event. The deploy is now done; this is unblocked.
8. **Re-invite Karen** (carried) — ORPHEUS-132's validation event.
9. **Decision Log pastes owed:** carried list (rendered-excerpt whitelist, detect-and-ban pause, milestone-starter replacement, ORPHEUS-142's existence, ORPHEUS-131 degrade/publish, Ruling-2 outcome, beta-purge, ORPHEUS-90, ORPHEUS-85) **plus new: the anthropic pin / deliberate-SDK-upgrades decision [2026-08-26] and the "b03ca0f5 stays unpublished" call [Josh+Andrew, 2026-08-26]**.
10. **Two beta testers possibly stuck in the in-app-browser trap** + email-vs-DM ops question (carried).
11. **Tim's confirmation list for Privacy Policy §11 and §7/§9** (carried verbatim).
12. **Empty `_to_delete/`** (carried; grew again — today's git lock files joined the pile).
13. **Andrew comms:** the carried headline items — (a) enforcement-strategy pause + agenda item 8; (b) Kyrgyzstan provenance check is about his own profile text; (c) population benchmarks are his framework call — **plus new: (d) publish flow works, UX fixes filed as ORPHEUS-144; (e) did the report-ready email land in his inbox? (validates the ORPHEUS-98 path); (f) his 08-13 report stays IN REVIEW on his client view deliberately — that's the control text, not a bug.**
14. **Three sweep directories still sit gitignored and un-backed-up on Josh's machine** (carried) — copy to Drive if they should outlive the week.
15. **Vercel MCP shows zero projects under the Orpheus team** (scope/permissions gap, noticed 08-26) — harmless, but the dashboard is the only source of truth for frontend deploy state until fixed.

---

## Pickup plan for next session

1. **NOT ORPHEUS-134.** Still paused by decision. Point at agenda item 8, the conflict map, and this handoff first.
2. **ORPHEUS-135** (footer) — settled, small, unaffected by the pause; ship text is in the ticket, do not paraphrase it.
3. **ORPHEUS-136** — one sentence, temp-0 rubric prompt; harness re-run + Andrew sign-off.
4. **ORPHEUS-144** (publish UX) — high, fresh, self-contained frontend/endpoint work; the suggested fixes on the ticket are independent and any subset helps.
5. **ORPHEUS-138**, then **139 items 1–4 + 115** together; **141** while the between-cohorts window holds.
6. **ORPHEUS-145** on a calm day — remember the harness-re-run gate.
7. **After the claims-layer discussion:** implement the chosen mechanism. Note for that session: the conflict map's Category A fixes (calibration-scale wording, leverage-ordering criterion, behind_curtain reconciliation, focus-instruction cleanup) are mechanism-independent and make any mechanism converge faster — but they are prompt work adjacent to the 134 pause, so confirm with Josh before touching.

---

## Caveats / things that will bite

1. **Unpinned dependencies freeze and thaw with Railway image builds** (see Architectural note 1). Until ORPHEUS-145 lands, any fresh build may resolve new majors for fastapi/uvicorn/supabase/pydantic/openpyxl. If a fresh deploy fails somewhere the code didn't change, suspect the build's dependency resolution first and diff installed versions against the prior image's.
2. **`prose_gate_degraded=false` cannot self-prove a write** — it equals the default. Provenance requires knowing the deployed tree (see 131's closing comment for the worked example).
3. **b03ca0f5 must stay unpublished.** It is the 08-13 claims-review control text (~20 documented Ruling-2 breaches). It shows IN REVIEW on Andrew's client view by design. Publishing it is now one dropdown away in /admin — do not "helpfully" clear that row.
4. **The /admin cheat_sheet row is raw JSON in a freetext editor.** Status dropdown only; a malformed text edit silently serializes `cheat_sheet: null` and the client's card vanishes. Admin edits bypass the milestone parser and every gate (ORPHEUS-144 carries the fix).
5. **Plane's `comment_html` takes REAL HTML tags**; only `&` and literal `<` need escaping. **Plane WAF 403s any comment containing a command-line string** — describe invocations in prose. **`list_project_issues` truncates** — dump to a file and query it.
6. **Cloud-session device workflow** (carried, all still true): whole files via SendUserFile + device_commit_files, md5 both sides; no heredocs through device_bash for real files; device_bash cannot delete (mv to `_to_delete/`); git in the mount leaves lock files — mv them aside before every git invocation; `tmp_obj_*` warnings are cosmetic.
7. **`git fetch`/`ls-remote` fail from device_bash** — push status via the origin/main reflog (`update by push` entries).
8. **A CLOUD session's container CAN run the backend suite** (pip works there; no Supabase/Anthropic egress); device_bash cannot (no network). Anything needing live API/DB is Josh's terminal — except Supabase, which the session reaches directly through the MCP connection (this session applied migration 023 and verified production rows that way).
9. **Untracked-by-intent set** (carried, verified this session): `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json`, `Signal_Score_Dimensions_Reference_*.md`, the LinkedIn review docs, `sweep_*/`, `snapshot_*.json`. `git check-ignore -v` before trusting any new root file. **Never `git add -A`.**
10. **F12 fires on every report by construction; the sweep's flag count under-reports — read the dump; a single clean sweep run is not acceptance.** (All carried; the sweep is paused work but these hold whenever it runs.)
11. **Carried unchanged:** structural evidence over logs; backfilled rows prove nothing; read a closing ticket's "still owed" list; `jobs`/`scores` column traps; closing events fire while nobody watches; never pin `opsz`/rename fonts; Resend items; growth factors PROVISIONAL; module-load URL rewrites preserve `location.hash`; every report figure re-derives from `ingested_data` alone — fix producers, not quoters; a reconciliation failure still fails the job by design.

---

## State of the repo right now

`main` at this wrap commit (unpushed); `e958e0f` pushed and deployed to both Railway services. Working tree otherwise clean; untracked-by-intent set intact (caveat 9). Production: migration 023 applied; worker + API on `e958e0f`; Vercel untouched all session. Database: 48 complete + 2 failed jobs (both June model-404s) + `40fa5809` failed (the 143 incident, documented on the ticket) — `2ebd4432` complete and published.

Plane this session: 131, 142, 143, 120 closed with conventional closing comments; 143, 144, 145 created; 134 untouched (paused).

Docs this session: CLAUDE.md Active-phase tail rewritten to the post-deploy state + one Decisions Made entry (the SDK pin); PRODUCT_CONTEXT.md narrative-row tail updated; this handoff replaces 08-18 part 2. In Drive (not the repo): the conflict map and the verbatim prompt set.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` (Orpheus Social > 06_Operations > Shared Canon)
- **State of the Moment:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA` · **Decision Log:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Foundational Review FINAL 2026-07-16:** `1jTnli4JqpbXhNK3vATKgV7usss1TcUFDSoGRa-_kpwI` · **Andrew's v3 findings (2026-08-13):** `1umi0ZztF-Hha44dA-2Y64e1OSM4BxF0CMvDi8-1_rTU`
- **Claims-layer discussion set (NEW):** agenda (Josh's Drive copy) `17Px6p4uzw5E_UhNK9PlVKPycbSpaI1EbQ_81u0lgfJY` · **Prompt Conflict Map 2026-08-19:** `1TsC4QYwKm5_xYPewPV98ZVZJY-YUlpaU9l8hNCos7_0` · **Model Prompts Verbatim 2026-08-19:** `16KN6tnkijEU2cGRgWfNqI8X-7adknJZ_xCoDgksgLHs`
- **Standup package (2026-08-17), Rev 2:** `1cNIEnhM95dJlmoo7LSI48dtj897RmUqV3zvxn-HN8xY` — exhibits: window evidence `1bjikxZ6MT3ehsRfW2k9tzZZo_iCEHNGwWC_YZLWsLrk`, 90-day addendum prototype `1hV7jn_vcDJKUdgH0XKpRKX8x4Kl8bzX-XhYAjVQgMAc`, value-story threads `138EwhvNhLU1Ol-UPc6wS8jeJ6KBQOoNVD7GV6E8sGUY`.
- **Landing copy:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk` · **Privacy drafting:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — canonical published text is the repo markdown.
- **Pending pastes:** see Pending item 9.
