# Session Handoff — 2026-08-17

Replaces `SESSION_HANDOFF_2026-08-14_part2.md` — everything it described carries forward or resolved as follows:

- **Its top recommendation was taken.** The 08-14 handoff said: hold the claims-layer discussion, and if it hasn't happened yet, do **ORPHEUS-131** first because it's decision-independent, high, small, and ORPHEUS-134 raises the retry pressure it fixes. The discussion hasn't happened; 131 is now code-complete and pushed.
- Its Pending items all carry (renumbered below), with item 3 (confirm the build) gaining this session's commits and a new hard dependency: **migration 023 must be applied before the worker deploy.**
- Its live-validation watch class (119 / 120 / 130 / 132) gains **131** — same shape, closes on an event nobody is watching for.
- The claims-layer batch (134–139) is untouched and still the main front. Nothing in this session changed the prompt, the rubric, or any client-facing copy.
- **One correction to its caveats:** caveat 9 says Plane's `comment_html` double-escapes and entities should be pre-escaped. That is wrong, and following it cost a comment this session — see caveat 9 below for what it actually does.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-131 | Prose-gate retry budget | 🔄 **In Progress — code complete + pushed**; closes on a live degrade + migration 023 applied |
| ORPHEUS-140 | Stages 2/3 re-run on narrative-only failure | 🆕 Backlog, low — filed this session, deliberately deferred |
| ORPHEUS-134 | Spec 2 narrative-prompt guardrails (Ruling 2/3) | ⏳ Backlog, high — the main front, untouched |
| ORPHEUS-135 | Signal-legibility footer | ⏳ Backlog, high — wording agenda-gated |
| ORPHEUS-136 | Spec 1: Dim 4 preamble sentence in `rubric.py` | ⏳ Backlog, high — harness re-run required |
| ORPHEUS-137 | Recommendations absence-assertions + ingest-vs-exclude | ⏳ Backlog, high — part (b) is Andrew's |
| ORPHEUS-138 | Comments.csv fragmentation + validator label | ⏳ Backlog, medium |
| ORPHEUS-139 | 80–100 range, window labels, engagement numerator | ⏳ Backlog, medium |
| ORPHEUS-133 | Beta-end account purge | ⏳ Backlog, medium |
| ORPHEUS-132 | Invite-flow consent gate | 🔄 In Progress — code shipped (`8bbc8f0`); closes on the next real invitation acceptance |
| ORPHEUS-119 / 120 / 130 | unchanged | 🔄 In Progress — events have not fired |
| ORPHEUS-115 / 111 / 116 / 99 / 94 / 84 / 107 | unchanged | ⏳ Backlog |

Baselines: backend pytest **575 green** (562 at session start, 573 after the main three commits); frontend vitest **196 green** (194 at session start); `tsc -b --noEmit` clean. **Both baselines were run and verified this session** — see caveat 10, the sandbox limitation the old handoffs record no longer applies.

---

## Commits this session

All four are **pushed** (`refs/remotes/origin/main` reflog shows `update by push` → `b434a96` at 14:55 local).

| SHA | Subject |
|---|---|
| `d2263fd` | Degrade the prose-number gate on its final attempt. Refs ORPHEUS-131. |
| `f802d92` | Persist the degradation marker; clear error_message on complete. Refs ORPHEUS-131. |
| `13f7f6c` | Surface prose-gate degradation in /admin. Refs ORPHEUS-131. |
| `b434a96` | Keep regenerate_report from writing a degraded narrative. Refs ORPHEUS-131. |

Plus this wrap (docs + handoff).

---

## What changed / what shipped

### ORPHEUS-131 — the gate no longer fails a job on prose alone

**The degrade** (`backend/agents/narrative.py`). `generate_narratives` retries 3× internally and the worker's `process_one` retries the whole pipeline 3× on top of it. A generation that kept quoting an unwhitelisted figure burned up to nine 8192-token calls and could land the job `failed` — with the client's data entirely fine. Job `b03ca0f5` spent two of its three worker attempts this way (six minutes vs a normal one) and passed on the third; one more unlucky generation and it fails.

Attempts 1 and 2 now behave exactly as before — reject, append the violation to the user message, retry. The final attempt returns the narrative with `prose_gate_degraded=True` and `prose_gate_violations=<describe_violations summary>` instead of raising. `NarrativeResult` gained both fields (defaulted, so every other caller is unaffected).

Two deliberate edges:

- **`log` mode marks too.** It is a global kill switch; without a per-job marker, every report served during an incident would hide its unverified figures — which is the invisibility the ticket exists to remove.
- **`off` never marks.** It doesn't scan, so claiming anything about it would be a false negative in the other direction.

Parse failures still raise. There is no partial narrative to serve there, and the trailing `raise` now carries a comment saying so, because "why doesn't this path degrade too" is the obvious next question.

**The marker** (`backend/migrations/023_jobs_prose_gate_degraded.sql`). `jobs.prose_gate_degraded boolean NOT NULL DEFAULT false` plus `jobs.prose_gate_violations text`. Two columns rather than one, unlike ORPHEUS-88's `data_limited`: there is no per-job JSONB to read the detail back out of, and "which figure" is the only question an admin asks on seeing the chip. `run_pipeline` writes both alongside `data_limited`, **unconditionally** rather than only-when-true, so an ORPHEUS-81 re-run that comes back clean clears a stale flag instead of leaving it on the row. No back-fill — the gate postdates every earlier report, so re-deriving would mean judging pre-whitelist prose against a whitelist it never saw.

**`/admin`** (`routers/admin.py`, `useAdmin.ts`, `AdminPage.tsx`, `AdminPage.css`). An "unverified figures" chip beside the limited-data chip, offending figures in the `title`. Both fields are optional on the wire and absent reads as false, so pre-023 rows render clean rather than 500ing.

**`error_message` hygiene** (`update_job_status`). Cleared when a job reaches `complete`. The retry path writes the failed attempt's traceback to the row, so a job that lost an attempt and recovered carried it into success — `b03ca0f5` shipped a correct report with its attempt-2 traceback attached, which reads as a failure to anyone who looks.

**The catch that wasn't in the ticket.** `scripts/regenerate_report.py` was protected only by the exception the degrade removes. Its own `verify()` has no prose-number check — the `prose_numbers` module docstring claimed the script's verify step consumed the gate, but it never did; it consumed the `ValueError`. Left alone, the degrade would have quietly started overwriting **already-delivered** reports with unverified figures, and invisibly, since that script deliberately never touches the job row that carries the marker. `verify()` now fails on `prose_gate_degraded`, and the docstring is corrected.

**Decision locked.** A degraded report publishes on the normal path [Josh, 2026-08-17]. The marker is the review surface, not a hold. Parking degraded self-serve reports as `draft` was the alternative and was rejected: self-serve is precisely the path with nobody watching, so a parked report becomes a report that never arrives — worse for the client than one soft figure an admin can fix via `edited_text`. Recorded in CLAUDE.md "Decisions Made".

**Test surface added** (+13 backend, +2 frontend): `TestProseGateFinalAttemptDegrade` (degrade instead of raise; every retry still spent first; recovery inside the window is NOT marked; `off` never marks; parse failure still raises), `TestUpdateJobStatusErrorMessage`, `TestRunPipelinePersistsProseGateMarker` (patches the four stages, asserts the marker write lands and the job still reaches `complete`), `TestRegenerateReportRefusesDegradedNarrative`, an `/admin/jobs` case with a pre-023-shaped row alongside a degraded one, and two `AdminPage` chip tests.

### ORPHEUS-140 — filed, not started

The ticket's third item (don't re-run stages 2 and 3 on a narrative-only failure), deliberately deferred [Josh, 2026-08-17]. Filed at low priority with the traps documented, because the cheap version of that optimization silently skips ORPHEUS-114's reconciliation gate, which lives inside stage 3.

---

## Architectural notes worth carrying forward

1. **The degrade/refuse split is the transferable idea.** The same violation gets opposite treatment depending on who is downstream: the worker serves a degraded report (a client with no report is worse than one soft figure, and there's an /admin surface to catch it), while the hand-run regeneration script refuses (it overwrites something already delivered, a human is present, and there's no surface). When adding a gate, ask *per caller* what the right failure posture is — a single global one was what made the 121 kill switch too blunt.
2. **A nested retry loop multiplies, and the inner one usually shouldn't be fatal.** The inner gate raising into an outer pipeline retry is what turned a phrasing quirk into a 9-generation, job-killing path. Any future inner-loop gate should degrade-and-mark rather than raise, unless there is genuinely nothing to serve.
3. **A marker column needs a clearing story.** Writing `prose_gate_*` unconditionally (rather than only on violation) is what makes re-runs correct. Same trap class as any denormalized flag: the write path that sets it must also be the write path that unsets it.
4. **"Protected by accident" is a real category.** `regenerate_report.py`'s safety came from an exception nobody had documented as a dependency — and the docstring asserted a protection that didn't exist. When removing a raise, grep every caller for what it was relying on, and don't trust a docstring's claim about who consumes what.
5. **Absent-reads-as-false keeps a migration deploy-order-tolerant on the read side.** `bool(j.get(...))` in the API plus optional TS fields mean the frontend and API can ship before the migration. The *write* side has no such tolerance — hence the deploy ordering below.

---

## Pending — manual steps

1. **Apply migration 023 before deploying the worker.** New this session and the sharpest item here. The worker writes both columns on every completion, so a worker running against an un-migrated database fails that write and takes the job down with it — turning a ticket about not failing jobs into one that fails all of them. Frontend and API are safe in either order. Prior migrations went to cloud via the Supabase MCP (see PRODUCT_CONTEXT's Database schema row for the 020/021/022 precedent).
2. **Delete the escaped Plane comment on ORPHEUS-131** — comment `34819698`, posted with its tags HTML-escaped so it renders as raw markup. The MCP has no edit or delete for comments; the corrected repost sits directly below it. Joins the carried "delete the surplus ORPHEUS-123 comments (keep `6a6c67ce`)" item.
3. **Schedule the claims-layer discussion** (Josh + Andrew; Tim not needed) — agenda at repo root, `Draft_Claims_Layer_Discussion_Agenda_2026-08-14.md` (untracked). Decisions unblock ORPHEUS-135 wording, 137(b), and the milestone question that gates parts of 134/139. Still the highest-leverage unblock in the backlog.
4. **Send Andrew the two review docs + agenda** — his v3 asks are all answered in `outputs/Review_Reconciliation_b03ca0f5_2026-08-14.md`.
5. **Confirm the deploys** — now covering `0aca889`, `8bbc8f0`, and this session's four (Vercel for the /admin chip; Railway for the worker + API, gated on item 1). Blocks items 6–7.
6. **Re-run Tarita** post-deploy: `https://app.orpheussocial.com/signup?code=ORPH-Z32A-K7VA` (closes ORPHEUS-130's event).
7. **Re-invite Karen** (carried) — her acceptance is also ORPHEUS-132's validation event, and she'll see the new consent checkbox where the link used to be instant (heads-up first).
8. **Andrew publishes `b03ca0f5` from /admin** (carried) — closes ORPHEUS-120's publish half; the report under review is a draft, so post-discussion edits can land via `edited_text` before release.
9. **Decision Log pastes owed:** the ORPHEUS-131 degrade/publish decision (new) joins the Ruling-2 outcome, the beta-purge decision [Josh, 2026-08-14], ORPHEUS-90 (4.6 acceptance, carried since 06-24), and ORPHEUS-85 (self-serve revision, overdue).
10. **Two beta testers possibly stuck in the in-app-browser trap** (carried) + the email-vs-DM invitation ops question.
11. **Tim's confirmation list for Privacy Policy §11 and §7/§9 claims** (carried verbatim).
12. **Empty `_to_delete/`** (carried, and it grew — see State of the repo).
13. **Andrew comms, carried:** (a)–(h) from the 08-14 morning handoff unchanged (Nicole score-0 posture; Jenn MIME retry; Jodie nudge; growth factors + 112 caveat; the 14 unsent feedback asks; tolerances/registry review; self-serve rosters; recruited beta user), plus (i) invite links now show a consent checkbox — tell invitees; (j) recommendations ingest-vs-exclude is his call on ORPHEUS-137; (k) the Jun 23 consolidated rubric doc refresh rides ORPHEUS-136. Nothing from this session needs Andrew — 131 is internal.

---

## Pickup plan for next session

1. **Hold the discussion, then implement per its decisions** — ORPHEUS-134 + 135 (+ 136 alongside) is the batch that retires the claims-layer exposure, and it is now the only high-priority work that isn't decision-blocked-or-shipped. 131's degrade also means 134 can raise retry pressure without risking failed jobs, which was the sequencing reason to do 131 first.
2. **ORPHEUS-138** (fragmentation parser hardening) — decision-independent, recovers real data, kills the mislabeled sentence at its producer. 137's part (a) can ride any prompt-touching session.
3. **ORPHEUS-139** — small, mostly render work; keep its agenda-gated exclusions (milestone baselines, band-scale visibility) out.
4. **Not ORPHEUS-140** — filed, deliberately parked, and it only earns attention if a multi-minute wall clock shows up again.

---

## Caveats / things that will bite

1. **Migration 023 is written but NOT applied.** Repeated from Pending 1 because it is the one item that can break production: the worker's completion write fails against an un-migrated database. If a job fails right after a deploy with a column-not-found error, this is why.
2. **131's closing event is stochastic and nobody is watching for it.** A clean run proves nothing (the 07-27 lesson, which caught Andrew's own reviewer on 08-14). The honest close is either a real degraded job showing the chip or a deliberate probe — e.g. temporarily narrowing the whitelist in a scratch run. Don't close it on green tests.
3. **The claims-layer canon lives in Drive, not the repo** — Foundational Review FINAL 2026-07-16 is `1jTnli4JqpbXhNK3vATKgV7usss1TcUFDSoGRa-_kpwI` (Rulings 2/3, Specs 1/2, open call #7); Andrew's v3 findings are `1umi0ZztF-Hha44dA-2Y64e1OSM4BxF0CMvDi8-1_rTU`. Read both before touching narrative prompts, milestones, or report copy.
4. **The recorded test baseline was wrong and had been for a while.** The 08-14 handoff said backend 558; the tree measured **562** before any of this session's work. The 4-test gap predates 08-17. Treat a handoff's test count as a claim to re-measure, not a fact — measuring is cheap now (caveat 10).
5. **Every report figure re-derives from `ingested_data` alone** (carried) — zip_data/xlsx_data recompute in SQL against jsonb; `quality_report.zip_files_found` is the archive manifest. Stronger than trusting persisted operands.
6. **An absence-claim in prose needs an ingestion check, not just an operand check** (carried) — and prose can quote a wrong input faithfully; fix producers, not quoters.
7. **A reconciliation failure fails the job by design, and that is now the *only* gate in the narrative path that does.** The prose gate degrades; ORPHEUS-114's reconciliation still hard-fails inside stage 3. Don't generalize the 131 posture to it — a bad derived metric must never persist, and unlike prose there's no "one soft figure" version of it.
8. **ORPHEUS-136 is one sentence but framework-affecting** (carried) — temp-0 rubric prompt, so Dim 4 can shift deterministically; harness re-run + Andrew sign-off before trusting scores.
9. **Plane MCP quirks — CORRECTED.** `comment_html` takes **real HTML tags**; only entities inside the text (`&`, a literal `<`) need escaping. The previous handoff's "pre-escape entities" advice, read literally, produces a comment that renders as visible markup — that's what happened to comment `34819698`, and there is no edit-or-delete tool to fix it, so the only remedy is repost + manual delete. `create_issue`'s `description_html` behaves the same way (plain HTML — held across seven issues now). `list_project_issues` still truncates; dump to a file and parse.
10. **Sandbox limits — LARGELY OBSOLETE, and the workaround is worth keeping.** Old handoffs say no pip and no pytest from the sandbox. In a cloud-Cowork session the *container* has network and the *device* has the repo, so both suites do run: `tar` the backend into `_to_delete/`, stage the tarball into the container, `pip install --break-system-packages -r requirements.txt`, run pytest there. The device has `node_modules` already, so `npx vitest run` and `npx tsc -b --noEmit` run directly via `device_bash` (keep vitest under the ~45s device_bash timeout — the full suite takes ~31s). Verify by re-tarring the device's post-commit tree and re-running, which also catches patch-application drift.
11. **`device_bash` cannot delete, and `git` in the mount leaves locks behind.** `rm` is refused, so retired files get `mv`'d into `_to_delete/`. Worse, `git apply` and `git commit` can't unlink their own `.git/index.lock`, `.git/HEAD.lock`, `.git/objects/maintenance.lock`, or `tmp_obj_*` scratch — the operation still succeeds, but the next git command blocks on a stale lock. Move them aside before each git invocation. The `tmp_obj_*` warnings are cosmetic.
12. **Editing the repo from a cloud session: patch, don't push files.** Staging a file into the container and committing it back needs a `SendUserFile` round trip per file. Generating a unified diff in the container, gzip+base64-ing it into `device_bash` heredocs, and `git apply`-ing it on the device is cleaner, reviewable (`git apply --check --stat` first), and cheap. Chunk the base64 at ~6KB per heredoc.
13. **`git fetch` / `ls-remote` fail from `device_bash` (no SSH agent), but the push status is still knowable.** Use `git reflog show refs/remotes/origin/main` — a real `git push` writes an `update by push` entry, so the ref moving is evidence of an actual push, not a local artifact. This is how this session's four commits were confirmed pushed. Ahead/behind counts against a stale ref are the thing not to trust.
14. **Untracked-by-intent set** (carried, verified this session): `Draft_*.md` covers the agenda; `outputs/` covers the review docs; `_to_delete/` covers all session scratch. `git check-ignore -v` before trusting any new root file. **Never `git add -A`.**
15. **Carried unchanged:** structural evidence over logs; backfilled rows prove nothing; actor's role can hide the behavior; `jobs.error_message` persists on complete jobs — **now false, 131 clears it, but historical rows still carry stale tracebacks**; read a closing ticket's "still owed" list; `jobs`/`scores` column-name traps; closing events fire while nobody watches; ORPHEUS-119's narrow event (house-advisor first completion); never pin `opsz` / never rename fonts; Resend items; growth factors PROVISIONAL; module-load URL rewrites preserve `location.hash` (three writers via `withAcceptanceParams`).

---

## State of the repo right now

`main` at this wrap commit; the four ORPHEUS-131 commits are pushed (caveat 13 for how that was confirmed). Working tree otherwise clean.

Untracked by intent, verified this session with `git check-ignore -v` (all ignored, none touched): `Draft_Claims_Layer_Discussion_Agenda_2026-08-14.md`, `Draft_Cohort_Rubric_2026-07-13.md`, `Draft_Unit_Narrative_Questionnaire_2026-07-13.md`, `Scoping_B2B_Cohort_Assessment_2026-07-13.md`, `Scoping_Free_Tier_And_Premium_Recommendations_2026-07-01.md`, `ORPHEUS-90_Model_Calibration_Decision_Brief_2026-06-17.md`, `Signal_Score_Dimensions_Reference_2026-05-20.md`, `Survey_Closed_Beta_Feedback_2026-06-08.md`, `LinkedIn_BD_DPA_Review_2026-05-07.md`, `LinkedIn_API_Terms_Review_2026-05-05.docx`, and the two review docs in `outputs/`.

**Drift found while verifying that list:** the `Orpheus_Privacy_Policy_DRAFT_*` and `Orpheus_Terms_of_Service_DRAFT_*` files are **no longer at the repo root**. Prior handoffs carried them as untracked-pending-a-commit-vs-Drive decision, and the wrap ritual still names them as the canonical example of what `git add -A` would sweep. Nothing this session moved them — most likely they were retired after ORPHEUS-125 published the versioned markdown in `frontend/src/content/legal/`, which is now the canonical text. Worth confirming they exist somewhere intentional (Drive) rather than only in someone's trash, and then dropping them from the caveat list so it stops guarding files that aren't there.

`_to_delete/` grew and is worth emptying (Pending 12). It now holds: the retired `SESSION_HANDOFF_2026-08-14.md` and `SESSION_HANDOFF_2026-08-14_part2.md`; four backend tarballs from the test-and-verify loop (`orpheus_backend.tgz`, `verify_backend.tgz`, `final_backend.tgz`); `patch/` with the two applied diffs and their base64 chunks; and `gitlocks/` with the stale `.git` locks and `tmp_obj_*` files `device_bash` couldn't unlink (caveat 11). All of it is disposable, and `_to_delete/` is gitignored so none of it can reach a commit.

Plane this session: ORPHEUS-131 → In Progress with a full code-complete comment; ORPHEUS-140 created (Backlog, low); one surplus escaped comment on 131 awaiting manual deletion. Nothing closed.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` (Orpheus Social > 06_Operations > Shared Canon)
- **State of the Moment:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA` · **Decision Log:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Foundational Review FINAL 2026-07-16:** `1jTnli4JqpbXhNK3vATKgV7usss1TcUFDSoGRa-_kpwI` · **Andrew's v3 findings (2026-08-13):** `1umi0ZztF-Hha44dA-2Y64e1OSM4BxF0CMvDi8-1_rTU`
- **Landing copy:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk` · **Privacy drafting:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — canonical published text is the repo markdown.
- **Pending pastes:** ORPHEUS-131 degrade/publish (new), Ruling-2 outcome, beta-purge decision, ORPHEUS-90 4.6 acceptance (carried since 06-24), ORPHEUS-85 self-serve revision (overdue).
