# Conventions

Naming, commit messages, ticket workflow, and document patterns. CLAUDE.md links here from its "First-session quickstart" so a fresh Claude session can absorb the conventions in one read.

---

## File naming

| Pattern | Used for | Example |
|---|---|---|
| `Decision_<Title>_YYYY-MM-DD.md` | Architecture / product decisions captured outside Plane (Plane pages are the source of truth, but markdown drafts get committed for easier diffing and grep) | `Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md` |
| `Spec_<Title>_YYYY-MM-DD.md` | Feature specs (also mirrored to Plane) | `Spec_Simplified_Intake_Questionnaire_2026-05-11.md` |
| `SESSION_HANDOFF_YYYY-MM-DD.md` | End-of-session handoff doc for the next Claude session. Retired by the next handoff in the same commit. | `SESSION_HANDOFF_2026-05-18.md` |
| `SETUP_<phase>_<topic>.md` | Multi-step setup walkthroughs for local-dev or one-time provisioning | `SETUP_phase1_local_auth.md` |
| `orpheus-<screen>-<variant>.html` | HTML/CSS prototype, JS-free, the visual source of truth for design system | `orpheus-questionnaire-v2.html` |
| `orpheus-styles.css` | Single shared stylesheet for the prototype (and reused by the React app) | (one file at repo root) |

All top-level docs live flat at the repo root. Assets go in `assets/screenshots/`.

---

## Commit message convention

```
<one-line subject, imperative, ≤ 72 chars>. Refs ORPHEUS-N.

<optional body — wrap at ~72 chars. Multiple paragraphs OK.
Mention specific files / functions / decisions when useful.>
```

Rules:

- **Subject ends with the period** before `Refs ORPHEUS-N` so log scanning sees the tag at the end.
- **Tag every commit** with the Plane ticket it serves. Multi-ticket commits use `Refs ORPHEUS-N, ORPHEUS-M.`
- **Imperative mood** — "Add X" not "Added X" or "Adds X".
- **Logical splits** — one commit per logical chunk, not one giant commit per ticket. A ticket may produce 5–12 commits depending on scope.
- **Body explains the why** when the diff doesn't.

Recent examples:

```
GET /clients + POST /advisor/self-report endpoints. Refs ORPHEUS-39.

GET /clients lists the calling advisor's clients with each row's most-recent
job summary. Two queries (clients by advisor_id, then jobs filtered with
client_id IN (...)) bucketed in Python.

POST /advisor/self-report is an idempotent get-or-create...
```

```
Document migration-apply step in setup doc; extend 001 recipe to include 012. Refs ORPHEUS-35.
```

```
Frontend hooks: advisor clients list + invite/resend/self-report mutations. Refs ORPHEUS-39.

Four new React Query hooks for the /advisor/clients page:

  useAdvisorClients   — query against GET /clients...
```

---

## Plane workflow

### Workspace and project

| | |
|---|---|
| Workspace slug | `orpheussocial` |
| Project name | `Orpheus` |
| Project identifier | `ORPHEUS` (used in commit messages) |
| Workspace UUID | `be866680-d712-4a3f-a60c-16c237d93ca7` |
| Project UUID | `1270ee67-f8f7-4af1-a245-32c8af50c964` |

### Ticket naming

Tickets are referenced as `ORPHEUS-N` (e.g., `ORPHEUS-39`). Use these in commit messages, PRs, slack/email, and cross-references between Plane pages.

### Ticket states

| State | UUID | Meaning |
|---|---|---|
| Open / Backlog | `04af2a94-45ad-42d8-b128-3fdb6332d380` | Default for new tickets. Either unstarted or in progress; Plane doesn't distinguish at the project level today. |
| Done | `6e50e892-231a-4112-83e2-01dcee696916` | Work is shipped + verified (or, for decision-style tickets, the decision is recorded). Comment cites evidence. |

### Closing a ticket

1. Post a Plane comment summarizing what shipped (commit SHA, file path, decision-doc reference).
2. Move state to Done via `mcp__plane__update_issue` with `state` set to the Done UUID.
3. CLAUDE.md's "Decisions Made" section gets a one-line entry if the ticket was substantial.

### Plane page naming

Plane has both work items (tickets) and pages (long-form decision / spec / architecture / meeting docs). Pages follow:

```
Category: Title (YYYY-MM-DD)
```

Example: `Decision: Self-serve + advisor invite flow (2026-05-11)`.

### Page categories

| Category | Use |
|---|---|
| `Decision` | Why X was chosen over Y. Tech, product, or design. |
| `Spec` | Feature or component requirements + scope. |
| `Architecture` | System design, infra, data models. |
| `Meeting` | Discussion summaries and action items. |

### Publishing workflow

1. Claude drafts the page content in conversation as a `Decision_/Spec_/Architecture_<Title>_YYYY-MM-DD.md` markdown file in the repo (or in chat first if low-stakes).
2. Josh reviews and either approves or requests edits.
3. Claude publishes to the Orpheus project in Plane via `mcp__plane__create_project_page`.

All pages live at the **project level** (Orpheus project), not the workspace level.

---

## Session handoff workflow

End of every Claude session, write a `SESSION_HANDOFF_YYYY-MM-DD.md` at the repo root. The handoff doc replaces the previous one (delete it in the same commit). Structure:

```
# Session Handoff — YYYY-MM-DD

Jump-in doc for the next Claude session. Replaces SESSION_HANDOFF_<prev>.md — the threads it described are all closed:

- ORPHEUS-N: shipped/closed/filed/...
- ...

## Status at a glance

| Ticket | Title | Status |
| ... |

## Commits this session

(list with SHAs + one-line subjects)

## What changed / what shipped

(detail per ticket: what was added, where it lives)

## Architectural notes worth carrying forward

(patterns introduced or reinforced this session)

## Pickup plan for next session

(suggested next ticket + alternative threads)

## Caveats / things that will bite

(known gotchas, deferred items, environment issues)

## State of the repo right now (end of session)

(git status, untracked files, working tree)
```

The 2026-05-13 and 2026-05-18 handoff files are good reference templates.

### When to retire vs keep the previous handoff

Default: retire the previous handoff in the same commit that adds the new one (the new doc captures everything still-relevant from the old one).

Exception: keep the previous handoff if it captures threads that span multiple sessions and the new handoff would lose them. Add a sentence to the new handoff's intro explaining why you're keeping both.

---

## When a ticket has split sessions

If a ticket's work spans multiple Claude sessions:

1. Each session ends with a SESSION_HANDOFF doc capturing what landed and what's left.
2. The receiving session's first action is to read the latest handoff (after CLAUDE.md + PRODUCT_CONTEXT.md).
3. The receiving session commits incremental progress with the same `Refs ORPHEUS-N` tag — the ticket stays open until acceptance criteria are all green.
4. The session that closes the ticket posts the closing Plane comment and moves state to Done.

---

## Versioning

Currently no formal version tags or releases on the repo. Each `main` push deploys directly (Railway + Vercel). Pre-launch, this is fine. Post-launch we'll need a tagging / release-notes convention; not yet defined.

---

## When in doubt

- Diffs over descriptions. Cite line numbers and commit SHAs.
- One commit per logical chunk; commit messages tell the story; the body explains why.
- Plane is the source of truth for tickets; CLAUDE.md is the source of truth for project-level decisions; PRODUCT_CONTEXT.md is the source of truth for scoring framework + pipeline state; the latest `SESSION_HANDOFF_*.md` is the source of truth for what's in flight.
- Ask before mass-modifying tickets or branches. Closing ticket state in bulk is a Josh-approves action; commenting is a Claude-can-do-freely action.
