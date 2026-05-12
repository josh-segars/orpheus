# Session Handoff — 2026-05-12

Jump-in doc for the next Claude session. Replaces `SESSION_HANDOFF_2026-05-11.md`, which is now stale — the work it described (ORPHEUS-20 + the four side fixes) is all committed, and the three threads it offered (ORPHEUS-20 verification, ORPHEUS-33, ORPHEUS-34) have all been picked up this session.

This was a long session covering four tickets, a major design conversation, and seven new Plane tickets. The pending-commit count is also higher than usual — see below.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-33 | Replace 23-question questionnaire with 9-question intake | ✅ Code complete. Frontend, backend types, prototype, migration 010 all done. **Not yet committed.** |
| ORPHEUS-34 | Rewrite narrative-generation prompt for simplified questionnaire shape | ✅ Code complete. Prompt + formatter + 8 new tests + processor.py column-name fix. **Not yet committed.** |
| ORPHEUS-35 | Add base-schema migration for jobs/scores/ingested_data/narratives | ✅ Code complete — narrow scope only. `001_base_schema.sql` dumps prod faithfully; `011_questionnaire_align_to_spec.sql` reshapes `questionnaire_responses` to match the ORPHEUS-33 spec; 007/008/009/010 marked historical. **Not yet committed.** |
| Decision | Self-serve + advisor invite flow (2026-05-11) | ✅ Drafted in repo at `Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md`. **Not yet committed.** |
| ORPHEUS-36 | Schema: invitation_token columns + retire 007's trigger plan | ⏳ Filed in Plane this session. |
| ORPHEUS-37 | Backend auth refactor: get_current_session_roles | ⏳ Filed. Depends on ORPHEUS-36. |
| ORPHEUS-38 | Invitation flow: /clients/invite + /accept-invitation + /invite/:token (Resend) | ⏳ Filed. Depends on ORPHEUS-36 + ORPHEUS-37. |
| ORPHEUS-39 | Advisor admin UI: /advisor/clients page | ⏳ Filed. Depends on ORPHEUS-37 + ORPHEUS-38. |
| ORPHEUS-40 | Stripe billing + self-serve sign-up flow | ⏳ Filed, beta-deferred. |
| ORPHEUS-41 | Client disconnect from advisor | ⏳ Filed, beta-deferred. |
| ORPHEUS-42 | Self-serve account management page | ⏳ Filed, beta-deferred. |

---

## Pending commits

Ten commits, drafted in this conversation but not yet applied (sandbox can't write to `.git/index.lock`). Paste locally in this order. Squashing inside each ticket's set is fine; commits across tickets shouldn't be squashed.

```bash
# ─── ORPHEUS-33: simplified intake (4 commits) ──────────────────────────

# 1. Migration 010 — DB shape change. Foundational.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add backend/migrations/010_questionnaire_simplified.sql && \
  git commit -m "Add migration 010: simplified 9-question intake questionnaire. Refs ORPHEUS-33.

TRUNCATE public.questionnaire_responses (the new answers JSONB shape is
incompatible with the 23-question, 7-section schema from migration 009)
and DROP COLUMN section_completion. Completion is now derived at read
time from answers content via isQuestionnaireComplete in the frontend.

Refreshes the table + answers column comments to match the new shape.
Pre-launch — no prod data to preserve. Header comment flags the
shape-translation step required if this kind of migration ever ships
after real client answers exist."

# 2. Frontend type contract + question primitives.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add frontend/src/types/questionnaire.ts \
          frontend/src/components/questionnaire/Questions.tsx && \
  git commit -m "Update questionnaire types + primitives for 9-question intake. Refs ORPHEUS-33.

types/questionnaire.ts: new QuestionnaireAnswers shape (q1[], q2[],
q3..q8 strings, q9 free text + qN_other for q1..q4). Adds OTHER_OPTION
constant and isQuestionnaireComplete predicate that encodes the spec's
per-question required rules (≥1 selection on q1/q2, Other-with-empty-
text is incomplete, q9 non-empty after trim). SectionId / SECTION_IDS /
SectionCompletion removed.

components/questionnaire/Questions.tsx: added CheckboxWithOtherQuestion.
API mirrors RadioWithOtherQuestion for symmetry — typing into the other
input auto-checks the Other option, unchecking Other preserves the typed
text. Removed ScaleQuestion + ScaleOption + the no-Other CheckboxQuestion
— no remaining question uses them."

# 3. React port — page, hooks, routes, Groundwork checklist.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add frontend/src/pages/QuestionnairePage.tsx \
          frontend/src/App.tsx \
          frontend/src/hooks/useQuestionnaire.ts \
          frontend/src/hooks/useGroundworkProgress.ts \
          frontend/src/pages/GroundworkPage.tsx && \
  git rm frontend/src/pages/questionnaire/sections.tsx \
         frontend/src/components/questionnaire/SectionLayout.tsx && \
  git commit -m "Port 9-question intake to React; collapse Groundwork to 3 rows. Refs ORPHEUS-33.

Replaces the seven Section{N}Page exports + SectionLayout chrome with a
single QuestionnairePage that inlines its own chrome and all 9
questions. App.tsx routes collapse /questionnaire/s1..s7 to a single
/questionnaire.

Hooks:
  - useSectionDraft → useQuestionnaireDraft. Single draft, single
    autosave debounce (still 700ms), no section_completion writes,
    simplified flush() signature.
  - useGroundworkProgress now reads answers and derives a single
    questionnaireComplete boolean via isQuestionnaireComplete. Per-
    section flags removed from the GroundworkProgress interface.

GroundworkPage drops from 9 checklist rows to 3: Intake Questionnaire
plus the two LinkedIn data items. The 'My Groundwork is Complete'
gating logic simplifies to all-three-rows-complete."

# 4. Prototype HTML — new visual source of truth; retire the obsoleted 7-file flow.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add orpheus-questionnaire-v2.html && \
  git rm orpheus-questionnaire-s1.html \
         orpheus-questionnaire-s2.html \
         orpheus-questionnaire-s3.html \
         orpheus-questionnaire-s4.html \
         orpheus-questionnaire-s5.html \
         orpheus-questionnaire-s6.html \
         orpheus-questionnaire-s7.html && \
  git commit -m "Add orpheus-questionnaire-v2.html; remove obsolete 7-file prototype. Refs ORPHEUS-33.

Single-page, JS-free HTML/CSS prototype as the visual source of truth
for the 9-question intake. Mirrors the canonical option strings used by
QuestionnairePage.tsx so the prototype and the React port stay
isomorphic.

The seven orpheus-questionnaire-sN.html files are obsolete — their
content has been condensed into the single intake and the React port no
longer references the section IDs. Removing them matches how
orpheus-welcome-v6.html and orpheus-groundwork-v1.html are treated as
the canonical visual references for their pages."

# ─── CLAUDE.md refresh + ORPHEUS-34 (2 commits) ────────────────────────

# 5. Refresh CLAUDE.md to match the post-ORPHEUS-33 reality.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add CLAUDE.md && \
  git commit -m "Refresh CLAUDE.md for post-ORPHEUS-33 reality.

Active phase line now reflects that prototype port is done and open work
is the narrative-prompt rewrite (ORPHEUS-34) and base-schema migration
(ORPHEUS-35).

Portal Pages table: seven questionnaire-sN entries collapsed to one
v2.html entry.

Questionnaire Questions Reference: replaced the 23-question, 7-section
table with the 9-question intake from
Spec_Simplified_Intake_Questionnaire_2026-05-11.md. Storage shape
documented inline.

Decisions Made: added the intake simplification note pointing to the
spec and migration 010.

Project structure migrations list: added 009 + 010 entries.

Backend Conventions auth.py note: documents the RS256 + ES256 support
and the new .well-known/jwks.json JWKS path (landed under the side-fix
commits from the 2026-05-08 session)."

# 6. ORPHEUS-34 — narrative prompt rewrite + worker column fix.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add backend/agents/narrative.py \
          backend/tests/test_narrative.py \
          backend/workers/processor.py && \
  git commit -m "Rewrite narrative-generation prompt for 9-question intake. Refs ORPHEUS-34.

backend/agents/narrative.py:
  - QUESTIONNAIRE_QUESTIONS constant carries the verbatim text of all 9
    questions plus their type (multi / single / freetext) and whether
    they have a parallel _other field.
  - _format_questionnaire rewritten. Each question prints with its full
    text on one line and the user's answer indented below. Multi-select
    answers are semicolon-joined. Other selections substitute the
    qN_other text into the rendered answer for both single- and multi-
    select questions. Missing/empty answers render as [no answer].
  - SYSTEM_PROMPT_TEMPLATE gains a '## Using the intake questionnaire'
    section that maps Q1-Q9 to narrative use cases (anchoring relevance,
    opening the Forward Brief, calibrating technical depth, etc.) per
    the spec's 'What the new 9 questions give us' guidance.

backend/tests/test_narrative.py:
  - TestFormatQuestionnaire reworked. Eight cases covering single-select,
    multi-select, single-Other with text, multi-Other with text, Other
    without text, partial/unanswered, empty dict, and None.

backend/workers/processor.py:
  - Column-name fix: 'answers' (was 'responses'). The legacy prod column
    is 'responses'; the post-ORPHEUS-35 011 migration renames it to
    'answers'. The worker now matches the post-011 state. ORDERING:
    apply 011 to prod BEFORE shipping this worker change, or the worker
    will 500 on the questionnaire fetch."

# ─── ORPHEUS-35: base schema + questionnaire alignment (3 commits) ────

# 7. The base schema dump.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add backend/migrations/001_base_schema.sql && \
  git commit -m "Add 001_base_schema.sql — snapshot of prod public schema. Refs ORPHEUS-35.

Faithful dump of the current production public schema (project ref
yqxuddkixzjruxtdjxpr) captured 2026-05-11. 8 tables, 5 enums,
3 functions, indexes, FKs, dual _as_advisor / _as_client RLS policies
with the SECURITY DEFINER get_advisor_id / get_client_id helpers.

Lets a fresh local DB be spun up with the same starting shape as prod
without needing access to the prod project. Header comment lays out
the relationship to the rest of the migration files and the broader
architecture drift between this legacy schema and what migrations
007-010 (and the current frontend/backend code) target.

Verified by replaying the structural body against prod in a
transaction and rolling back — no errors, prod row counts unchanged."

# 8. The questionnaire alignment migration.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add backend/migrations/011_questionnaire_align_to_spec.sql && \
  git commit -m "Add 011_questionnaire_align_to_spec.sql. Refs ORPHEUS-33, ORPHEUS-35.

Reshapes public.questionnaire_responses on top of 001 to match the
ORPHEUS-33 spec:
  - TRUNCATE (legacy q1..q23 shape is incompatible with the 9-question
    intake's shape, and Andrew's pressure-test row is reproducible)
  - DROP columns id, schema_version, completed_at
  - RENAME responses -> answers
  - Promote client_id to PRIMARY KEY (drops surrogate id PK + the
    redundant UNIQUE on client_id)

Defensive against re-runs — every structural change is wrapped in a
DO block that checks current state first, so applying on an
already-aligned DB is a no-op.

Verified by replaying against prod in a transaction and rolling back —
post-migration shape is exactly (client_id PK, answers, updated_at)
with the FK to clients(id) intact.

DEPLOYMENT ORDERING: the worker (backend/workers/processor.py) was
updated to read 'answers' alongside the ORPHEUS-34 work. That change
matches the post-011 state. Until 011 is applied to prod, the worker
will 500 fetching the questionnaire row — apply 011 to prod BEFORE
or AT THE SAME TIME AS shipping the updated worker."

# 9. Historical header comments on 007-010.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add backend/migrations/007_clients_table.sql \
          backend/migrations/008_rls_enable.sql \
          backend/migrations/009_questionnaire_responses.sql \
          backend/migrations/010_questionnaire_simplified.sql && \
  git commit -m "Mark migrations 007-010 as historical record. Refs ORPHEUS-35.

Each of 007 / 008 / 009 / 010 was authored against an empty database
that doesn't exist in our prod. Against prod (and against the new
001_base_schema.sql), they range from silent no-ops (CREATE TABLE IF
NOT EXISTS, DROP COLUMN IF EXISTS) to partial conflicts (e.g. 008's
simpler auth.uid() RLS policies layered on top of prod's
_as_advisor/_as_client framework).

Header comments at the top of each file now explain the drift and
point at the correct path (001 + 011 for fresh setup). The files
themselves are unchanged — they remain in the repo as the historical
record of how the LinkedIn-auth architecture from ORPHEUS-23 was
*intended* to apply, before we discovered the prod schema is on a
different conceptual model."

# ─── Decision page (1 commit) ──────────────────────────────────────────

# 10. The decision page for the self-serve + advisor invite flow.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git add Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md && \
  git commit -m "Add decision: self-serve + advisor invite flow.

Captures the design conversation from 2026-05-11: one auth.users row
can own up to one advisors and up to one clients row simultaneously;
lazy advisors-row creation; two entry paths (invitation link + post-
beta self-serve signup); Resend for email; Stripe gated to post-beta;
soft-confirmation on LinkedIn-email vs invitation-email mismatch; full
advisor admin UI in v1 (no Studio-query workaround).

Supersedes the LinkedIn-1:1 self-serve model from
Decision_LinkedIn_Auth_2026-04-21.md — specifically the migration-007
on_auth_user_created trigger and the clients.id = auth.users.id PK
constraint. The earlier doc stays in the repo as historical record.

Beta scope is 4 tickets (ORPHEUS-36/37/38/39). Post-beta scope is
3 tickets (ORPHEUS-40/41/42) tagged with the new beta-deferred label."

# ─── Optional housekeeping (1 commit) ──────────────────────────────────

# 11. Retire the stale 2026-05-08 and 2026-05-11 handoffs and stage this one.
cd ~/git/orpheus && rm -f .git/index.lock && \
  git rm SESSION_HANDOFF_2026-05-08.md 2>/dev/null; \
  git add SESSION_HANDOFF_2026-05-12.md && \
  git commit -m "Session handoff: 2026-05-12. Retire stale 2026-05-08 handoff.

The 2026-05-11 handoff was committed earlier this session; the 2026-05-08
one was superseded by it but never removed. Drop it now."
```

If you'd rather batch into fewer commits — ORPHEUS-33 as one squash, ORPHEUS-34 + CLAUDE.md as one, ORPHEUS-35 as one, decision page + handoff as one — the contents stay coherent. The split here is just optimized for readable history.

---

## Files added / modified / deleted this session

### ORPHEUS-33

Added:
- `backend/migrations/010_questionnaire_simplified.sql`
- `frontend/src/pages/QuestionnairePage.tsx`
- `orpheus-questionnaire-v2.html`

Modified:
- `frontend/src/types/questionnaire.ts` (rewritten — new `QuestionnaireAnswers` shape, `OTHER_OPTION` constant, `isQuestionnaireComplete` predicate)
- `frontend/src/components/questionnaire/Questions.tsx` (added `CheckboxWithOtherQuestion`; removed `ScaleQuestion` + `CheckboxQuestion` no-Other variant)
- `frontend/src/hooks/useQuestionnaire.ts` (rewritten — `useSectionDraft` → `useQuestionnaireDraft`, no section_completion path)
- `frontend/src/hooks/useGroundworkProgress.ts` (rewritten — single `questionnaireComplete` boolean derived from `answers`)
- `frontend/src/pages/GroundworkPage.tsx` (9 rows → 3 rows; updated doc comment)
- `frontend/src/App.tsx` (collapsed 7 routes to 1)

Deleted:
- `frontend/src/pages/questionnaire/sections.tsx`
- `frontend/src/components/questionnaire/SectionLayout.tsx`
- `orpheus-questionnaire-s{1,2,3,4,5,6,7}.html`

### CLAUDE.md refresh

Modified:
- `CLAUDE.md` (Active phase line; portal pages table; questionnaire reference 23→9; migrations list adds 009+010; backend conventions auth.py note; decisions-made adds intake simplification)

### ORPHEUS-34

Modified:
- `backend/agents/narrative.py` (added `QUESTIONNAIRE_QUESTIONS` constant; rewrote `_format_questionnaire`; added `## Using the intake questionnaire` block to SYSTEM_PROMPT_TEMPLATE)
- `backend/tests/test_narrative.py` (TestFormatQuestionnaire reworked, 8 new cases)
- `backend/workers/processor.py` (column-name fix: `responses` → `answers`)

### ORPHEUS-35

Added:
- `backend/migrations/001_base_schema.sql`
- `backend/migrations/011_questionnaire_align_to_spec.sql`

Modified:
- `backend/migrations/007_clients_table.sql` (added historical-record header)
- `backend/migrations/008_rls_enable.sql` (added historical-record header)
- `backend/migrations/009_questionnaire_responses.sql` (added historical-record header)
- `backend/migrations/010_questionnaire_simplified.sql` (added historical-record header — note this file is also created in ORPHEUS-33 commit #1; the header is added by the 007-010 historical-headers commit)

### Decision page

Added:
- `Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md`

### Session handoff

Added:
- `SESSION_HANDOFF_2026-05-12.md` (this file)

Potentially deleted (housekeeping):
- `SESSION_HANDOFF_2026-05-08.md` (superseded by 05-11, never cleaned up)

### Untracked at session start, still untracked

These were sitting in the working tree at session start and aren't part of this session's work:

- `LinkedIn_BD_DPA_Review_2026-05-07.md`
- `Orpheus_Privacy_Policy_DRAFT_2026-05-07.md`
- `Orpheus_Privacy_Policy_DRAFT_2026-05-07.docx`
- `Orpheus_Terms_of_Service_DRAFT_2026-05-07.md`
- `Orpheus_Terms_of_Service_DRAFT_2026-05-07.docx`

These trace back to the LinkedIn API Terms review from 2026-05-05. They're a separate pre-launch compliance thread. Decide whether to commit them or move them to Drive in a future session.

---

## Plane: what was filed this session

7 new tickets, plus 1 new label.

**Beta scope (4):**
- ORPHEUS-36 — Schema: invitation_token columns on clients + retire migration 007's trigger plan. `infra`, `backend`.
- ORPHEUS-37 — Backend auth refactor: replace get_current_client with get_current_session_roles. `backend`. Blocked by 36.
- ORPHEUS-38 — Invitation flow: /clients/invite + /accept-invitation + /invite/:token (Resend). `backend`, `frontend`. Blocked by 36, 37.
- ORPHEUS-39 — Advisor admin UI: /advisor/clients page. `frontend`. Blocked by 37, 38.

**Post-beta (3), all tagged `beta-deferred`:**
- ORPHEUS-40 — Stripe billing + self-serve sign-up flow. `backend`, `frontend`, `beta-deferred`.
- ORPHEUS-41 — Client disconnect from advisor. `backend`, `frontend`, `beta-deferred`. Blocked by 40 + 42.
- ORPHEUS-42 — Self-serve account management page. `frontend`, `beta-deferred`. Blocked by 40.

**New label:** `beta-deferred` (#6D4350) — applied to 40, 41, 42.

**Plane MCP gap to flag:** the MCP doesn't expose Plane's native blocks/blocked-by relations, only the description field. Dependencies above are encoded in each ticket's description ("Depends on" / "Blocks" sections). To get Plane's dependency-graph view, wire the relations up by hand in the Plane UI.

---

## Pickup plan for the next session

Several reasonable threads. Pick whichever fits.

### Option A — Apply the 10 pending commits, push, deploy

Smallest. Run the commit script above, push to `origin/main`, and decide whether to deploy. **Important deployment-ordering caveat:** the worker change (commit #6) reads `answers` from `questionnaire_responses`, which is the post-011 column name. Apply migration 011 to prod (commit #8) BEFORE deploying the updated worker, or the worker will 500.

Suggested deployment order:
1. Push commits.
2. Apply `001_base_schema.sql` to local Supabase only (prod already has this state). Apply `010_questionnaire_simplified.sql` to local Supabase only.
3. Apply `011_questionnaire_align_to_spec.sql` to prod (via Studio SQL Editor or `supabase db push`).
4. Deploy the worker.
5. Deploy the frontend.

### Option B — Start ORPHEUS-36

Smallest of the beta tickets. Pure DB work. Run the column-add migration, dry-run against prod, commit. ~30 minutes of focused work.

### Option C — Start ORPHEUS-37 (after 36 lands)

The backend auth refactor. Larger. Touches `backend/auth.py`, `backend/routers/`, and `backend/tests/test_auth.py`. Needs the schema columns from 36 only because the invitation flow downstream needs them; the resolver itself is independent.

### Option D — Pick up the privacy / ToS / DPA compliance thread

The five untracked files from 2026-05-07 are pre-launch compliance drafts (privacy policy, ToS, LinkedIn BD DPA review). Untouched this session. Worth a 30-minute pass to decide what to commit, what to move to Drive, and whether the items need their own Plane tickets before client-facing launch.

### Option E — Address the broader architecture drift surfaced this session

The "spec-canonical" reconciliation we did in ORPHEUS-35 was narrowed to `questionnaire_responses` only. The bigger drift remains:

- `clients` table in prod has a different shape than migration 007 creates (advisor-managed-invite vs LinkedIn 1:1).
- RLS in prod uses dual `_as_advisor` / `_as_client` policies with SECURITY DEFINER helpers; migration 008 designs simpler auth.uid() direct checks.
- The `on_auth_user_created` trigger doesn't exist in prod.

The decision page (`Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md`) lays out a new architecture that resolves most of this — but the beta tickets (36–39) are the concrete implementation. So option B/C is effectively this thread, taken one ticket at a time.

---

## Architectural notes worth carrying forward

### From ORPHEUS-33

- **Canonical option strings flow end-to-end.** The strings rendered in QuestionnairePage.tsx are byte-for-byte the strings stored in `questionnaire_responses.answers` and fed to the narrative prompt. No separate value/label split, no localization layer (yet).
- **Completion is derived, not persisted.** `isQuestionnaireComplete(answers)` runs in the Groundwork hook on every read. `section_completion` column is gone.
- **`CheckboxWithOtherQuestion` mirrors `RadioWithOtherQuestion`** for symmetry. Both auto-select Other when the user types in the inline text input.

### From ORPHEUS-34

- **narrative.py was already question-agnostic at the formatter level** (`_format_questionnaire` just dumped keys generically). The 2026-05-11 handoff overstated the staleness. This session's work was less "fix a crash" and more "give Claude the question text and per-question guidance so the prompt is actually useful."
- **The system prompt's `## Using the intake questionnaire` section** is the place to tune narrative voice for the new questionnaire. Per spec decision #8, no Andrew review before merge — iterate from the first generated narrative.

### From ORPHEUS-35

- **`backend/migrations/001_base_schema.sql` is a snapshot, not a foundation.** It documents what prod has today; it does NOT compose cleanly with migrations 007–010 in the repo. The header on each historical migration spells out the conflict.
- **The Supabase MCP `execute_sql` with `BEGIN; … ROLLBACK;`** is a safe way to dry-run migrations against prod. Used twice this session, prod row counts unchanged both times.
- **Prod's RLS framework is more sophisticated than migration 008's design.** `get_advisor_id()` / `get_client_id()` SECURITY DEFINER helpers + dual `_as_advisor` / `_as_client` policies per table. If we ever move off this design we need a careful migration; running 008 over it would create a confused superset.

### From the self-serve + invite design conversation

- **One `auth.users` row → up to one `advisors` row + up to one `clients` row, lazily.** Roles are orthogonal, not alternatives. Andrew (advisor running a practice + analyzing himself) is the motivating case.
- **Invited clients never get an `advisors` row.** Self-serve sign-ups (post-beta) get both. Advisors running a practice for others have only an `advisors` row until they click "Run my own report."
- **Disconnect = one atomic transaction.** Get-or-create the user's own `advisors` row, repoint `clients.advisor_id`. RLS does the rest.
- **Beta is invitation-only.** No `/signup`, no Stripe, no disconnect. The advisor admin UI is the gate. Stripe and self-serve are tagged `beta-deferred` in Plane.

---

## Open threads / things to decide later

1. **Pre-launch compliance docs.** Privacy Policy, ToS, LinkedIn BD DPA review — drafts exist on disk, never committed. Decide commit path before public launch.
2. **Plane native relations.** Dependencies are described in ticket text, not wired into Plane's relations graph. Wire by hand in the UI if the graph view is useful.
3. **Pricing for ORPHEUS-40.** Stripe ticket has open questions on tier(s), annual vs monthly, advisor billing. Pick before that ticket starts.
4. **LinkedIn-first vs Stripe-first** in ORPHEUS-40. Leaning LinkedIn-first; confirm at ticket-start time.
5. **Ghost auth.users cleanup.** When invitation acceptance fails, the `auth.users` row stays. The decision page proposes letting Supabase's existing inactive-users cron handle it. Revisit if ghosts become a meaningful issue.

---

## Caveats / things that will bite during testing

1. **`migration 010` and `migration 011` collide if both are applied.** Migration 010 (drops `section_completion` column from migration-009's table) is for the local-dev path that started from migrations 007/008/009/010. Migration 011 (renames `responses` → `answers`, drops `id`/`schema_version`/`completed_at`) is for the prod path that started from `001_base_schema.sql`. Pick one starting point — don't try to run 010 over the 001 state or 011 over the 009/010 state. The header comments on both files spell this out.

2. **`backend/workers/processor.py` is in a future state.** It reads `answers` from `questionnaire_responses`. Current prod has `responses`. Apply migration 011 to prod BEFORE deploying the worker. Failure mode: worker 500s on every questionnaire fetch.

3. **The decision page describes a model that doesn't exist in code yet.** It lays out the lazy-advisors-row pattern, the `get_current_session_roles` resolver, the invitation flow, etc. None of this is implemented yet — that's the scope of ORPHEUS-36/37/38/39. Don't be surprised if you read the decision page and then can't find the code; it's all in the next batch of tickets.

4. **Pending commits across multiple file rewrites.** Several files are touched by multiple commits in the pending list (e.g. `010_questionnaire_simplified.sql` is created in commit #1 and amended in commit #9 with a historical header). Apply commits in order; out-of-order application will either fail or produce confusing diffs.

5. **The 4 dry-runs against prod this session each rolled back cleanly**, but the user's prod row counts were checked after each. If the next session does more dry-runs, do the same paranoia check (`SELECT count(*) FROM questionnaire_responses; ...`) after each one.

6. **CLAUDE.md is updated mid-stack.** Commit #5 (CLAUDE.md refresh) lands BEFORE the ORPHEUS-35 work, so it doesn't reference 001/011 in the migrations list. If you want CLAUDE.md to fully reflect post-35 reality, add a small follow-up update after commit #9 noting 001 and 011 in the project-structure migrations list.

---

## State of the repo right now (end of session)

```
On branch main
Your branch is ahead of 'origin/main' by 10 commits.

Changes staged but not committed (from this session):
  see "Pending commits" above — 10 commits' worth of work, none applied yet
  due to sandbox .git/index.lock restrictions.

Staged from previous session (still uncommitted):
  SESSION_HANDOFF_2026-05-11.md (would land in commit #11 of the previous
                                  session's plan; user previously deferred)

Untracked:
  SESSION_HANDOFF_2026-05-08.md (stale, retire in commit #11)
  LinkedIn_BD_DPA_Review_2026-05-07.md
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
```

If the previous session's pending handoff (`SESSION_HANDOFF_2026-05-11.md`) is still staged but uncommitted, commit it before applying this session's work — its history is already what the rest of this handoff assumes.
