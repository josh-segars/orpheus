# Session Handoff — 2026-08-11

Replaces `SESSION_HANDOFF_2026-08-05.md` — all the threads it described are closed in code or have moved into CLAUDE.md "Decisions Made":

- **The 2026-08-04 GDPR batch is nearly closed.** ORPHEUS-123 (fonts) closed 08-06; **ORPHEUS-124 (self-service deletion) shipped 08-07 and closed 08-10** after live production validation; **ORPHEUS-125 (publish Privacy Policy + ToS) closed 08-11** — both documents are live on both hosts; **ORPHEUS-126 (Route A consent capture) is live** and In Progress only for its per-upload leg. ORPHEUS-127 (DSR runbook) **closed in part 3** — the batch is now fully closed except 126's event-gated leg.
- **Two parallel streams converged today.** This session carried 124 → docs → 125; a second Claude session (`ef20462`, Opus) built 126's consent capture. The seams held — the effective-date coupling it left as an OPEN ITEM was honored exactly — but its backend tests had never run (no pytest in that sandbox) and its migration was committed unapplied. Both were caught here; see the caveats.
- **A live sign-in outage happened and was fixed inside ~30 minutes** (`d076e7f`). The mechanism is caveat 1 below — the single most transferable lesson of the day.
- **Carried unchanged:** the ORPHEUS-114 / 120 / 121 / 115 / 116 cluster, ORPHEUS-119's live-verification remainder, ORPHEUS-111, the ORPHEUS-90 Decision Log paste, the Andrew comms items.
- **Part 2 (same day, second session):** ORPHEUS-128 filed, shipped (`dabe77c`, pushed), and closed — the report page's hidden numeric scores are gone and the ORPHEUS-122 sr-only open thread is resolved. Section below.
- **Part 3 (same day, third session, cloud):** ORPHEUS-127 shipped (`719f2f8`, pushed) and closed — the DSR runbook, every query executed against production before it was written down. Section below.

---

## ORPHEUS-124 — self-service account deletion (shipped 08-07, closed 08-10)

`DELETE /account` (`backend/routers/account.py`, the codebase's first delete handler): ordered teardown — advisor-roster guard (409 while any non-`is_self` client row exists) → storage sweep of everything under `{client_id}/` including abandoned `staging/` (502-aborts with the account intact) → explicit `clients`-row delete (FKs cascade downstream) → `advisors` row → best-effort waitlist sweep → `auth.admin.delete_user()` **last**. Uses `get_verified_session`, not the default dependency — a retry after an auth-step failure is neither-role and would otherwise be 401'd into a stranded auth user (pinned by test). Frontend: Danger Zone on AccountPage, typed-DELETE inline confirmation, blocked-advisor explanation, account-deleted notice on /login.

**Live validation (production, volunteer test-roster account):** before-snapshot 1 job / 5 narratives / 1 report / 2 storage objects → after: every count zero, **no orphaned `clients` row with `user_id IS NULL`** (the SET-NULL failure mode), auth user gone by id and email, whole-DB totals down by exactly her footprint (clients 34→33, jobs 48→47, storage 99→97, advisors unchanged). Blocked-advisor guard verified live on Josh's account. Fresh re-sign-in landed `/not-invited`. All 8 acceptance criteria.

**Retention posture locked [Josh, 2026-08-11]:** raw uploads are retained until self-service deletion — published §10 says exactly that. A standing 30-day sweeper is deliberately **not ticketed** unless that tighter promise is ever wanted back.

The volunteer (Karen) is currently account-less by design — **re-invite her from the test roster whenever she wants a fresh report.**

---

## ORPHEUS-125 — documents published (closed 08-11)

`/privacy` + `/terms` live on both hosts, public, rendered from canonical markdown at `frontend/src/content/legal/{privacy,terms}.md` — the versioned record ToS §19's 30-day change-notice needs. Effective date **August 11, 2026**. Bespoke constrained-markdown renderer (`lib/legalMarkdown.tsx`, no new dependency; tests pin no-markdown-leakage). Real links in both footers ("Confidentiality" → "Privacy Policy"), login agreement line, all ten prototype footers backported; zero footer `href="#"` anywhere.

The published text was converted from the finalized Google Docs after a claim-by-claim codebase review (2026-08-06, `outputs/ORPHEUS-125_Doc_Review_2026-08-06.md`) and two rounds of paste-ready edit files (also in `outputs/`). Every system-behavior claim in the published documents was verified against the code at conversion time — the questionnaire description, the two-stage Anthropic prompt inventory (including the photo-indicator caveat on stage 4), the seven-parsed-files minimization fact, the sub-processor table, retention rows, and the advisor/team access disclosure. **The repo markdown is now the canonical published text; the Drive Docs are the drafting surface.**

Post-deploy fixes from Josh's live review (`d5efb26`): legal pages rebuilt to the canonical `nav / main-interior / footer` column (the first shell wrapped them and bypassed the body-level layout — off-brand chrome), scroll reset on mount (react-router preserves scroll; footer-link entries opened mid-page), document links in `var(--primary)`.

---

## ORPHEUS-126 — Route A consent capture (other session's build; live except one leg)

Built in `ef20462` by the parallel session, Route A [Josh]: **two separate consent records because they are different things** — `terms_acceptances` (account-level, version-scoped, recorded from the /login checkbox; accepted versions ride the OAuth `redirectTo` query string with sessionStorage fallback, the ORPHEUS-92 pattern) and `jobs.upload_consent_at`/`upload_consent_version` (per-submission; `POST /jobs/from-uploads` refuses without it). No back-fill for the pre-existing accounts — a synthesized consent row is fabricated Art. 7(1) evidence.

**Live state:** the first real `terms_acceptances` row was recorded 2026-08-11 16:54 UTC (Josh, versions 2026-08-11/2026-08-11) after the caveat-1 fix. **The per-upload leg has not fired live yet** — the next real submission proves it (check `upload_consent_at` on the new jobs row). That is the only thing holding 126 open; it is event-gated the way 119 is.

This session's contributions to the stream: first execution of its 20 backend test cases (three failed on a `FakeSupabase()` constructor-signature bug in the tests, fixed in `4dae89d`; the consent gate itself passed unchanged → 460 green), migration 020 applied to the cloud DB ahead of the deploy, the caveat-1 incident fix, and the branded consent links.

---

## ORPHEUS-128 — hidden numeric scores removed (part 2, closed 08-11)

The ORPHEUS-122 open thread, decided and shipped in one session [Josh, 2026-08-11]: bands are the composite display in every modality, assistive tech included. `dabe77c` deletes the ORPHEUS-51 sr-only "— composite score N of 100" span from the report hero `<h1>` and drops the "— score N of 100" clause from `BandPillRow`'s aria-label (unused `score` prop removed). No color-only regression — the band label is the announcement. The ORPHEUS-51 test pin retargeted into a negative sweep (no score text anywhere, every aria-label checked); prototype backported. Audit of all client-facing surfaces found **no other leaks**. Two observations recorded on the ticket, not fixed: sub-dim pips are `aria-hidden` (visible 1–5 ratings never announced — the inverse gap), and `GET /jobs/{id}` still carries `composite`/`normalized_score` in JSON (devtools-visible; backend contract change if ever wanted).

---

## ORPHEUS-127 — data-subject request runbook (part 3, closed 08-11)

`Runbook_Data_Subject_Requests_2026-08-11.md` at the repo root (`719f2f8`, with the CLAUDE.md Pointers link in the same commit; dated by write date per the naming convention, not the ticket's 2026-08-04 name). Covers intake + identity verification with the GDPR 30-day / CCPA 45-day clocks; the identity-resolution query; erasure as two paths — self-service (ORPHEUS-124, preferred since signing in *is* the verification) and the ordered manual procedure mirroring `backend/routers/account.py` (roster guard → storage sweep incl. `staging/` → clients row → advisors row → waitlist → auth user **last**); the post-erasure verification query with a dedicated `orphaned_clients` arm for the SET-NULL trap; a single-JSON access/portability package; rectification (manual UPDATE for `display_name`/`email` until ORPHEUS-42); restriction via `status='inactive'`; and the DSR log template.

**Every query ran against production 2026-08-11 (Supabase MCP, cloud session) before it was written down:** resolution surfaced the ORPHEUS-94 mismatch live — Josh's clients row matched via `user_id` under a different email; the access package assembled 14/14 keys for a real account; the orphan catcher was proven against an inserted-then-removed scratch `user_id IS NULL` row (caught, then all-zero re-run); the roster guard counted 11 non-self clients, correctly blocking. `terms_acceptances` (migration 020, post-dates the ticket) is in the package, the sweep, and the FK-trap table.

**Two placement decisions [Josh saw both in-session]:** the filename date, and the DSR log kept **out of the repo** — a log of who exercised privacy rights is itself personal data — living in Shared Canon / 06_Operations as a create-on-first-use sheet. Nothing to create until the first request arrives.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-124 | Self-service account deletion | ✅ Done — `1d4e7e5`, live-validated |
| ORPHEUS-125 | Publish Privacy Policy + ToS in-product | ✅ Done — `4dae89d` + `d5efb26`, all 6 criteria live |
| ORPHEUS-126 | Capture upload consent (Route A) | 🔄 In Progress — live; closes on the next real submission's `upload_consent_at` |
| ORPHEUS-127 | Data-subject request runbook | ✅ Done — `719f2f8` (part 3), all queries production-tested |
| ORPHEUS-128 | Hidden numeric score removal + audit | ✅ Done — `dabe77c`, pushed, closed same day |
| ORPHEUS-114 | Reconciliation gate + metric source/unit registry | ⏳ Backlog (high) — standing top code recommendation |
| ORPHEUS-120 | Advisory draft gate doesn't hold on the read path | ⏳ Backlog (high) — pair with 114 |
| ORPHEUS-121 | Narrative agent fabricates aggregate counts | ⏳ Backlog (high) — rides 114 |
| ORPHEUS-115 / 116 | Prose mislabels / What Travels evidence layer | ⏳ Backlog — 115 needs 114's registry; 116 gated on Andrew |
| ORPHEUS-119 | Report-ready email path | 🔄 In Progress — awaiting a first-time completion under `is_individual = true` |
| ORPHEUS-111 | Upload size caps misaligned | ⏳ Backlog (medium) |
| ORPHEUS-99 / 94 / 84 / 85 / 107 | unchanged | ⏳ Backlog |

Baselines: backend pytest **460 green**, frontend vitest **124 green**, `tsc -b` + vite production build clean. **Measured, not carried** — this session ran in a cloud container with working pip/pytest/npm (see caveat 5). Josh's terminal run should match 460. Part 2 re-confirmed on-device: vitest 124 green, `tsc -b` clean (frontend-only change; backend untouched). Part 3 was docs-only (runbook + doc refreshes) — both baselines carry unchanged.

---

## Pending — manual steps

1. **ORPHEUS-126's closing evidence** — after the next real client submission, verify `upload_consent_at`/`upload_consent_version` on the new jobs row, then close with the conventional comment.
2. **Re-invite Karen** from the test roster when she wants a fresh report (account deleted by design during 124 validation).
3. **Delete the surplus ORPHEUS-123 Plane comments** (carried from 08-05; the Plane MCP has no comment-delete tool — dashboard job). Keep `6a6c67ce`.
4. **Tim's confirmation list for the published Privacy Policy §11 and §7/§9 claims:** MFA on all infrastructure accounts; "logging and monitoring of administrative-access events" (only app logs exist today — soften or build); "a documented incident-response process" (write the one-pager or drop "documented"); the Anthropic commercial-agreement sentence (training prohibition + retention limits); the 90-day backup window (plan-dependent); DPA/SCC close-out per his vendor assessment. Text edits, if any, follow the caveat-2 version-bump discipline.
5. **ORPHEUS-90 Decision Log paste** — carried since 06-24 (`outputs/DecisionLog_ORPHEUS-90_Model_Calibration_2026-06-24.md`); decide whether it will ever happen.
6. **Empty `_to_delete/`** at repo root — session-transfer artifacts plus files retired from the repo root this week; review and delete the folder.
7. **Andrew comms, carried:** (a) Nicole's report is the first real-client exercise of the ORPHEUS-63 score-0 posture; (b) Jenn hasn't retried since the MIME fix — her orphaned `staging/` upload from 07-17 is also still in the bucket; (c) Jodie needs an onboarding nudge; (d) ORPHEUS-120's open question — should the feedback ask wait for advisory publication at all? (e) ~~the ORPHEUS-122 sr-only composite-score question~~ — resolved by ORPHEUS-128 (removed, part 2); (f) growth factors + the ORPHEUS-112 metric-definition caveat.

---

## Recommended pickup for next session

1. **ORPHEUS-120 + 114 together (121 rides)** — the standing code recommendation, unchanged since 08-05 and now the unambiguous top of the board: design the publish boundary once; 114's reconciliation identities are the regression net. (ORPHEUS-127 closed in part 3, so the compliance thread no longer competes for the slot.)
2. ORPHEUS-126 closes itself on the next real submission (pending item 1 below); 119 likewise event-gated. Neither is a work ticket.

---

## Caveats / things that will bite

1. **Module-load URL rewrites must preserve `location.hash`.** Supabase's implicit OAuth flow returns session tokens in the **hash fragment** and supabase-js parses them **asynchronously after** page scripts start. `captureTermsAcceptanceFromUrl()` (main.tsx, module scope) originally rebuilt the URL as pathname + query — erasing the tokens and looping every fresh production sign-in back to /login. Fixed in `d076e7f` with a regression test. Any future code that rewrites the URL early (query-param capture, canonicalization) must carry the fragment.
2. **The document effective date is load-bearing in three places** — `frontend/src/content/legal/*.md`, `CURRENT_*_VERSION` in `frontend/src/lib/consent.ts`, and `backend/consent_versions.py`. They must move together in one commit; tests pin the md↔frontend pairing and the backend fails closed (nobody can sign in or submit) on an unknown version. A §19 change additionally wants the outgoing version kept in `ACCEPTED_*_VERSIONS` during the 30-day notice window.
3. **Committed ≠ applied for migrations.** `ef20462` shipped migration 020 committed-but-unapplied; deploying would have broken every submission against missing columns. It was caught and applied via the **Supabase MCP** (`apply_migration`) before the push — that tool is available from cloud sessions and is now the fastest apply path. Before any deploy that adds tables/columns, verify against `information_schema`, not the migrations folder.
4. **Cross-session work may arrive without its tests run.** The parallel session's sandbox had no pytest; its 20 backend cases were first executed here (3 failed on a test-harness constructor bug — product code was fine). When a commit message says "tests NOT RUN", treat that as a to-do with teeth, not a formality.
5. **Cloud Cowork sessions can run the backend suite.** pip/pytest/npm/vite all work in the cloud container (unlike the on-device sandbox, where PyPI is blocked). This handoff's 460/124 baselines are measured. The device sandbox limitations (no pip, no SSH push, `git fetch` fails, `.lock`/unlink quirks) still apply to on-device sessions — both sets of constraints are real depending on where the session runs; check which environment you're in before assuming.
6. **Device-bridge file transfer can't unlink.** `tar` extraction over existing files fails ("Cannot open: File exists") — extract to `/tmp` and `cp` over; deletions become `mv` into `_to_delete/`. Stale `.git/index.lock` files recur; `mv` them aside before every stage/commit (unchanged from 08-05).
7. **Legal/public pages must use the canonical `nav / main-interior / footer` column** — the body/#root flex layout provides the centering and the 1200px nav/footer caps; wrapping the three in a page-local shell silently breaks the chrome (shipped briefly on 08-11, fixed in `d5efb26`). Also: react-router preserves scroll across client-side navigation — long-page destinations reached from footer links need an explicit scroll reset.
8. **Untracked-by-intent set changed this week.** The compliance drafts (`Orpheus_*_DRAFT_2026-05-07.*`, `LinkedIn_BD_DPA_Review_*`) were retired from the repo root into `_to_delete/` — the published text now lives tracked at `frontend/src/content/legal/`. Current expected `??` set: `Draft_*.md`, `Scoping_*.md`, `Survey_*.md`, `ORPHEUS-*_Decision_Brief_*.md`, `rubric_consistency_results_*.json`, `create_beta_survey_form.gs`, `outputs/`, `.claude/settings.local.json` (all gitignored), plus `_to_delete/` (added to `.gitignore` this session). `git check-ignore -v <path>` before trusting any new root file is protected.
9. **Plane MCP double-escape quirk** (pass raw HTML to `add_issue_comment`; check `comment_html` not `comment_stripped`) — held correct across five comments today; unchanged.
10. **Never pin `opsz`; never rename the faces back to "Source ..."** — carried verbatim from 08-05 (fonts, licence).
11. **A clean run does not prove a stochastic prose bug is fixed; verify the deploy before asking anyone to re-run; growth factors are PROVISIONAL** — carried verbatim.
12. **`python-multipart` is still in `requirements.txt` unused**, comment-flagged; fold the removal into the next backend commit (carried; today's backend changes were router/test additions, deliberately not touched).
13. **Email-path items carried:** outages invisible from inside the product (both send paths swallow `EmailSendError`); a returning/advisory client completing is NOT an ORPHEUS-119 verification event; the ORPHEUS-110 part-1-partial sub-question still needs a real sample; Resend's dashboard still lists GoDaddy as provider — do not use its Auto configure button.

---

## State of the repo right now

Eleven commits since the 08-05 handoff (incl. the part-1 wrap `4cacb15` and the part-2 wrap `8105cce`), all pushed; the part-3 wrap commit is the only thing left to push after this file lands:

- **`4fe4a19`** (08-06) — handoff bookkeeping: 123 closed
- **`1d4e7e5`** (08-07) — ORPHEUS-124: self-service account deletion
- **`ef20462`** (08-11) — ORPHEUS-126: consent capture (parallel session)
- **`4dae89d`** (08-11) — ORPHEUS-125: publish the documents (+ ef20462's test-harness fix)
- **`d076e7f`** (08-11) — the caveat-1 sign-in fix
- **`1cbcefb`** (08-11) — branded consent links
- **`d5efb26`** (08-11) — legal-page chrome + scroll reset
- **`dabe77c`** (08-11 part 2) — ORPHEUS-128: remove hidden numeric scores from the report page
- **`8105cce`** (08-11 part 2) — part-2 session handoff
- **`719f2f8`** (08-11 part 3) — ORPHEUS-127: the data-subject request runbook + CLAUDE.md pointer

**Prod config beyond source:** the four DNS records in the Vercel zone (unchanged), and migration 020 applied to the cloud DB via the Supabase MCP (2026-08-11) — the migrations folder and the live schema agree today; caveat 3 is about keeping it that way.

`outputs/` (gitignored) holds this week's review artifacts: the 2026-08-06 doc review and the two edit-list files.

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Landing copy doc ID:** `12SqEH_6unmQotKSYOj_d3nk3kZMIlL0ePRSwPPBIOlk`
- **Privacy Policy drafting Doc:** `1V7HSDnokEHkWFmjvCBxvvEU8ANTRHJ1RXH3-5TlEJZM` · **ToS drafting Doc:** `14mQyQQlpELrR5q95o2CeJVeskaGyZhRbU6AmlPyMIRo` — drafting surfaces only; **the canonical published text is the repo markdown** at `frontend/src/content/legal/`.
- **Pending paste:** ORPHEUS-90 4.6-acceptance entry. ORPHEUS-85 still owes its entry when it ships.
