# Orpheus Social — Project Context

Orpheus Social is a client portal and diagnostic tool for improving presence
and personal narrative on LinkedIn. It is designed to guide advisors with one
to many clients and self-serve customers through a structured data-gathering
phase ("Groundwork"), then delivers a **Signal Score** diagnostic and
**Forward Brief** action plan.

**Current state:** two parallel implementations.

- **HTML/CSS prototype** (14 screens, JS-free) lives flat in the repo root and renders via VS Code Live Server. It is the visual source of truth for the design system.
- **Production stack** is in active development: FastAPI backend (Railway), Supabase Postgres with Auth + RLS, Vite + React frontend (Vercel). As of 2026-05-06, LinkedIn (OIDC) sign-in works end-to-end against local Supabase; the React shell renders Signal Score, Forward Brief, and Cheat Sheet pages with auth, RLS, and the typed JWT contract in place.

**Active phase:** the prototype's product flow is ported (Welcome, Groundwork, questionnaire, LinkedIn upload, Analysis-in-Progress all live in React). The advisor admin UI (`/advisor/clients`) shipped 2026-05-14 under ORPHEUS-39, with advisor-aware `GET /jobs/{id}` and the View report uncloak following on 2026-05-18 under ORPHEUS-46. Signal Score band labels renamed to the tuner metaphor on 2026-05-29 under ORPHEUS-49 (Dissonant/Untuned/Tuning/Tuned/Resonant). The whole-app dark mode + Signal Score page redesign shipped 2026-05-29 under ORPHEUS-50 — dark is canonical (no light variant), the accent shifts app-wide from warm gold to green, primary action color shifts from deep slate to blue, and the redesigned Signal Score page is a waveform hero plus per-dimension cards with 5-pill band rows and 5-pip sub-dimension ratings. ORPHEUS-51 (2026-05-30) followed up by restructuring the hero into a contained section inside `main-interior`, wiring band-keyed waveform images (one per tuner band), and adding sr-only accessibility fallbacks for the composite + per-dimension scores. ORPHEUS-52 (2026-05-30, same day) made the PortalNav identity cluster app-wide — `Prepared for` eyebrow + report-subject name (resolved per route via `useJob` + the advisor roster) + avatar + dedicated logout icon button; the prior dropdown menu is retired. ORPHEUS-22 (2026-05-30, same day) closed out the per-dimension band classifier by moving it server-side onto `DimensionScore.band` (reuses the composite SIGNAL_BANDS thresholds against `normalized_score × 100`); the client-side `dimensionBand()` helper is retired and the HTML prototype was backported in the same session to bring its nav cluster + Signal Score hero markup back in sync with the React app. ORPHEUS-43 (2026-05-31) pinned the Railway build in source by promoting `backend/requirements.txt` to repo-root `requirements.txt`; the manual dashboard Build Command override is retired. ORPHEUS-31 (2026-05-31, same day) shipped the email-allowlisted `/admin` stopgap — god-mode view of every client + job across all advisors, plus an inline narrative editor that writes to `public.narratives.edited_text` / `status`; new `get_current_admin` dependency in `backend/auth.py` enforces the `ADMIN_EMAILS` env allowlist server-side, mirrored client-side by `VITE_ADMIN_EMAILS` + `AdminRoute` as a UX gate. Open code work is per-sub-dimension narrative fields (ORPHEUS-21, pending Andrew's Forward Brief revisions) and the live e2e walk-through against cloud Supabase (ORPHEUS-44, gated on ORPHEUS-25). See the latest `SESSION_HANDOFF_*.md` and the Plane backlog for the current state.

---

## First-session quickstart

A fresh Claude session can be productive in 5 minutes by:

### 1. Read these three docs in order

1. **This file (CLAUDE.md)** — auto-loaded by the agent; you're reading it.
2. **`PRODUCT_CONTEXT.md`** — Signal Score framework, scoring formulas, pipeline architecture, decisions, build status. The canonical product spec.
3. **The latest `SESSION_HANDOFF_*.md`** at the repo root — what shipped most recently, what's in flight, suggested pickup plans for the next ticket.

Then `CONVENTIONS.md` and `CREDENTIALS.md` when you need them (linked from below).

### 2. Confirm tool availability

This project expects these MCP servers to be connected on the team account:

| MCP | What it does | Critical? |
|---|---|---|
| **Plane** (`mcp__plane__*`) | Project management — read/update tickets, post comments, create pages. Used every session. | Yes |
| **Supabase** (`mcp__supabase__*`) | Database operations against the prod project — apply migrations, run queries, list tables. | Yes for schema work; optional for code-only sessions |
| **Workspace bash** (`mcp__workspace__bash`) | Shell access in an isolated Linux sandbox. Reads the repo from `/sessions/<id>/mnt/orpheus/`. | Yes |
| **Filesystem tools** (Read/Write/Edit/Glob/Grep) | Direct repo access via the user's filesystem at `/Users/josh/git/orpheus/`. | Yes |
| **Claude in Chrome** (`mcp__claude-in-chrome__*`) | Browser automation for web apps that have no MCP. Used occasionally. | Optional |
| **Computer-use** (`mcp__computer-use__*`) | Native desktop control. Rarely needed for this project. | Optional |
| **Scheduled tasks** (`mcp__scheduled-tasks__*`) | Recurring/deferred work. Not currently used. | Optional |

If a critical MCP is missing, ask the user to connect it before starting work. Don't fall back to web scraping or pixel-hunting when an API-backed MCP is the right tool.

The `anthropic-skills` pack (pdf, docx, xlsx, pptx, schedule, setup-cowork, skill-creator) should be installed for document-creation work. Most sessions don't need it; code-and-prose work doesn't trigger any of them.

### 3. Verify wiring

Quick checklist a fresh session can run:

1. `mcp__plane__get_projects` → should return at least the Orpheus project.
2. `git remote -v` (via workspace bash) → should show `git@github.com:josh-segars/orpheus.git`.
3. The user's working directory mount is `/sessions/<id>/mnt/orpheus/`; the same files are reachable via the file tools at `/Users/josh/git/orpheus/`.

If any of those fail, see `CREDENTIALS.md` for the system-by-system inventory.

### 4. Pointers

- **People & decision authority** — see "People & roles" section below.
- **External systems / credentials** — `CREDENTIALS.md` (Plane, Supabase, Railway, Vercel, Resend, LinkedIn Developer, GitHub, Anthropic).
- **Naming, commits, Plane workflow** — `CONVENTIONS.md` (file naming patterns, commit message format, ticket states, page categories, handoff workflow).
- **Local-dev setup** — `SETUP_phase1_local_auth.md` (one-time onboarding: install Supabase CLI, create the dev LinkedIn app, apply migrations 001 + 011 + 012).

### 5. Sandbox quirks worth knowing

- **SSH egress is blocked** from the workspace sandbox. `git push origin main` only works from the user's terminal — Claude must commit locally and hand off the push instruction.
- **`.git/*.lock` files cannot be unlinked** by the sandbox. Every git commit leaves a phantom lock that needs `mv` (not `rm`) before the next operation. Pattern: `find .git -name "*.lock" -type f | while read f; do mv "$f" "$f.moved.$$" 2>/dev/null; done` before each commit.
- **PyPI access is blocked.** `pip install` doesn't work in the sandbox. `pytest` cannot be run from sandbox; runs must happen on the user's machine.
- **The file tools and bash tools see different paths for the same file** — file tools use `/Users/josh/git/orpheus/`, bash uses `/sessions/<id>/mnt/orpheus/`. Same files underneath, different mount roots.

---

## People & roles

**Josh Segars** (`josh@ess3.ai`) — engineering lead, project manager, product manager/designer, AI workflow operator. Owns:

- Codebase decisions (architecture, scaffolding, refactors, libraries).
- Schema and migration decisions.
- Ticket grooming and prioritization in Plane.
- Naming conventions, commit / handoff format.
- AI session workflow (these docs, the SESSION_HANDOFF pattern, the audit pattern).
- Frontend port strategy and visual fidelity to the HTML prototype.
- Build sequencing and deploy mechanics (Railway, Vercel).
- Signal Score and Forward Brief as products — the decision of whether and how Andrew's framework design lands in the product (what surfaces to the client, when, in what form). Andrew is consulted as SME and framework author.

When the user message in this session is from `josh@ess3.ai`, it's Josh.

**Andrew Segars** — product lead, advisor practice owner, domain authority. Owns:

- Signal Score and Forward Brief framework design — what is measured, how it's measured, dimensions, weights, bands, sub-dimensions, rubrics, score-to-band mapping. Andrew is SME and framework author; Josh owns the product application of the design.
- Narrative voice and advisory framing (third-person neutral for advisory, etc.).
- Final call on anything the advisor practice depends on.

Decisions in `PRODUCT_CONTEXT.md` "Decisions Made" tagged `[Andrew, YYYY-MM-DD]` are Andrew's; `[Josh, YYYY-MM-DD]` are Josh's; joint decisions are tagged `[Andrew + Josh, YYYY-MM-DD]`.

**Tim Segars** (`tim@ess3.ai`) — CEO, operations, finance, legal. Owns:

- All legal decisions (terms of service, privacy policy, contracts, vendor agreements).
- LinkedIn API terms review, pricing (when Stripe lands).
- Final call on anything legal, compliance, and financial.

**Decision routing for AI sessions:**

- **Code shape, naming, refactors, library choices** → Josh's call. Claude can propose and ship.
- **Signal Score / Forward Brief framework design (what's measured, how it's measured)** → Andrew's call. Claude drafts, Josh routes, Andrew approves.
- **Signal Score / Forward Brief product application (whether/how the framework lands in the product)** → Josh's call. Andrew consulted as SME and framework author.
- **Narrative content and advisor practice** → Andrew's call. Claude drafts, Josh routes, Andrew approves.
- **Schema and migration mechanics** → Josh's call.
- **Product UX (what the client sees and when)** → Andrew's call for substantive change; Josh's call for minor polish.
- **Legal, compliance, financial, vendor / contract decisions** → Tim's call. Claude drafts, Josh routes, Tim approves.

When in doubt, prefer Josh's approval to ship → he'll route to Andrew or Tim if needed.

---

## File Naming Convention

```
orpheus-[screen]-[variant/version].html
orpheus-styles.css
```

All files live flat in the repo root. Assets go in `assets/screenshots/`.

---

## Design System

### Fonts
- **Source Serif 4** — headings, numbers, display (variable, use `opsz` axis)
- **Source Sans 3** — body, UI, labels
- Both loaded from Google Fonts in each HTML file's `<head>`

### Color Tokens (defined in `orpheus-styles.css` `:root`)

Dark mode is canonical as of ORPHEUS-50 (2026-05-29). There is no light variant.

Role-based tokens (preferred for new code):
```
--bg-page:           #010c16   (page background)
--bg-surface:        #010c16   (card surface — typically transparent + --border)
--surface-elevated:  #1C2B3A   (avatars, footer band, role-tab inactive, inputs)
--text-strong:       #f9f6f0   (headings, wordmark, primary text on dark bg)
--text-body:         #e8f3f7   (body copy)
--text-muted:        #91a7af   (secondary text, placeholders, labels)
--border:            #364048   (card borders, dividers, input borders)
--accent:            #67ac6c   (eyebrows, Social wordmark, hover accents)
--accent-strong:     #218f29   (active band pill, success states)
--accent-tint-soft:  rgba(103, 172, 108, 0.08)
--accent-tint-hover: rgba(103, 172, 108, 0.16)
--primary:           #0160d5   (primary buttons, role-tab active)
--primary-hover:     #1a78ed
--issue:             #bf2923   (error/issue tone, alerts)
--shadow-dark:       rgba(0, 0, 0, 0.5)

Audio-spectrum palette — 5-step rating pips on the Signal Score page, low → high:
--pip-1: #bf2923  (red)
--pip-2: #e17800  (orange)
--pip-3: #e7ce41  (yellow)
--pip-4: #218f29  (green)
--pip-5: #006cf1  (blue)
```

Legacy aliases — preserved so existing `var(--warm-*)` / `var(--deep-slate)` references continue to resolve to their dark equivalents. Most map cleanly; three legacy names (`--deep-slate`, `--warm-ivory` as a text color, and a handful of placeholder-text refs) served multiple semantic roles in light mode and were updated per-rule during the ORPHEUS-50 migration:
```
--deep-slate     → var(--surface-elevated)
--warm-gold      → var(--accent)
--warm-ivory     → var(--bg-page)
--warm-parchment → var(--bg-surface)
--warm-text      → var(--text-body)
--warm-stone     → var(--text-muted)
--warm-border    → var(--border)
--red-clay       → var(--issue)
```

New code should prefer the role-based tokens. Legacy aliases stay defined indefinitely so the rename never has to ripple through every CSS file.

### Border Radius
10px throughout — no exceptions.

### Input Interaction Pattern (HTML prototype only)
`:has(input:checked)` CSS selector for radio/checkbox selected states. No JavaScript in the prototype HTML — all interaction is CSS. The React app naturally uses JS but mirrors the same visual pattern via state-driven `className` toggles.

---

## Shared Stylesheet (`orpheus-styles.css`)

Contains all shared patterns. Do not duplicate these in page `<style>` blocks:
- Reset, body, tokens
- `.nav`, `.wordmark`, `.nav-client` (navigation)
- `.footer`, `.wordmark-sm`, `.footer-links`
- `.back-link`, `.back-arrow`
- `.main-interior` (interior page layout — max-width 820px)
- `.section-header`, `.section-eyebrow`, `.section-title`, `.section-intro`
- `.questions`, `.question`, `.question-label`, `.question-number`, `.question-text`, `.question-helper`
- `textarea`
- `.radio-group`, `.radio-option`, `.radio-indicator`, `.option-text`
- `.other-input` (inline text inside a radio option)
- `.checkbox-group`, `.checkbox-option`, `.checkbox-indicator`, `.checkbox-check`
- `.scale-group`, `.scale-options`, `.scale-option`, `.scale-pip`, `.scale-label`
- `.actions`, `.btn-primary`, `.btn-secondary`
- `.info-notice`, `.info-notice-text`, `.info-notice-label`, `.info-notice-body`
- `.steps`, `.step`, `.step-number`, `.step-content`, `.step-title`, `.step-body`, `.step-note`
- `.screenshot-placeholder`, `.screenshot-label`
- `.upload-section`, `.upload-label`, `.upload-area`, `.upload-icon`, `.upload-primary`, `.upload-secondary`, `.upload-file-type`

Page-specific styles (welcome layout, groundwork checklist, etc.) stay in
a `<style>` block in the page's `<head>`.

---

## Button Naming

| Class | Use |
|---|---|
| `.btn-primary` | Primary action ("This Section is Complete", "This Step is Complete") |
| `.btn-secondary` | Secondary action ("Save My Answers", "Save My Progress") |
| `.btn-start` | Welcome page only ("Get Started") |
| `.btn-complete` | Groundwork page only ("My Groundwork is Complete") — has disabled/active states |

---

## Portal Pages & Status

| File | Screen | Status |
|---|---|---|
| `orpheus-welcome-v6.html` | Welcome / entry | ✅ Complete |
| `orpheus-groundwork-v1.html` | Groundwork Checklist | ✅ Complete |
| `orpheus-linkedin-step1.html` | LinkedIn Data — Step 1: Request Archive | ✅ Complete |
| `orpheus-linkedin-step2.html` | LinkedIn Data — Step 2: Export Analytics | ✅ Complete |
| `orpheus-questionnaire-v2.html` | Intake Questionnaire (Q1–Q9, single page) | ✅ Complete |
| `orpheus-analysis.html` | Analysis in Progress (holding state) | ✅ Complete |
| `orpheus-signal-score.html` | Signal Score delivery | ✅ Complete |
| `orpheus-forward-brief.html` | Forward Brief delivery | ✅ Complete |

---

## Navigation Flow

```
Welcome → Groundwork Checklist → [any item] → [item page] → Groundwork Checklist
                                                                      ↓
                                                         My Groundwork is Complete
                                                                      ↓
                                                         Analysis in Progress
                                                                      ↓
                                                              Signal Score
                                                                      ↓
                                                            Forward Brief
```

All questionnaire sections and LinkedIn steps return to Groundwork Checklist
via back link and both action buttons. Navigation is non-linear — clients
can complete items in any order.

---

## LinkedIn Data Inputs

Two files collected from clients during Groundwork:

1. **ZIP archive** — from LinkedIn Settings > Data privacy > Download your data >
   **"Download larger data archive" (Complete, not Basic)**. Basic export omits
   Shares.csv, which is required for behavioral scoring. Contains CSVs: Profile,
   Positions, Education, Skills, Connections, Recommendations, Endorsements,
   Shares, Comments, Reactions, Rich_Media, Inferences_about_you, etc.

2. **Analytics XLSX** — from linkedin.com/analytics/creator/content/ (accessed via
   "Post impressions" link in feed left column). Export set to "Past 365 days".
   Sheets: DISCOVERY, ENGAGEMENT, TOP POSTS, FOLLOWERS, DEMOGRAPHICS.

PDF export was evaluated and deemed redundant — ZIP CSVs contain same profile data.

---

## Questionnaire Questions Reference

The intake questionnaire was simplified from 23 questions across 7 sections to 9 questions on a single page on 2026-05-11 (ORPHEUS-33). See `Spec_Simplified_Intake_Questionnaire_2026-05-11.md` for the verbatim question text and locked decisions.

| # | Topic | Type |
|---|---|---|
| 1 | Current situation | Checkboxes (5 options + Other w/ inline text, select all that apply) |
| 2 | Actively pursuing | Checkboxes (8 options + "None of these" + Other w/ inline text, select all that apply) |
| 3 | What's driving interest now | Radio (4 options + Other w/ inline text) |
| 4 | Current LinkedIn approach | Radio (5 options + Other w/ inline text) |
| 5 | Comfort with current presence | Radio (5 options) |
| 6 | Familiarity with how LinkedIn works | Radio (4 options) |
| 7 | Understanding of online-presence impact | Radio (4 options) |
| 8 | 12-month success picture | Radio (4 options + "All of the above", stored literal) |
| 9 | Anything else | Open text (required, "Nothing to add" acceptable) |

Storage shape: flat JSONB map with `q1`/`q2` as canonical-label string arrays, `q3`/`q4` as canonical-label strings (plus `qN_other` for Other text on q1–q4), `q5`–`q8` as canonical-label strings, `q9` as free text. Completion is derived at read time by `isQuestionnaireComplete` — no persisted completion flag.

---

## Decisions Made

- HTML prototype is JS-free — all interaction via CSS `:has()` selector. React app uses standard JS and mirrors the same visuals via state.
- No PDF export step (redundant with ZIP)
- Data retention: delete after AI processing; Signal Score is the durable record
- **Authentication: LinkedIn (OIDC) only**, via Supabase Auth. Self-serve sign-up; verified-email gate enforced by the `on_auth_user_created` trigger. Client-side and server-side identity both flow from a single Supabase session. See ORPHEUS-23 / `Decision_LinkedIn_Auth_2026-04-21.md` for the full architecture.
- **Account deletion: hard cascade.** Deleting `auth.users` cascades through `clients` to `jobs`, `ingested_data`, `scores`, and `narratives`. Clients retain their Signal Score / Forward Brief deliverables out-of-band (PDF copy held by Andrew).
- Confidentiality / AI data handling: LinkedIn API Terms reviewed in `LinkedIn_API_Terms_Review_2026-05-05.docx` (Drive). Project privacy policy + ToS still deferred — compliance follow-up tickets to be cut from that review before public launch.
- Screenshot assets for LinkedIn instruction pages: deferred
- "My Groundwork is Complete" button stays disabled (`opacity: 0.35`) in the prototype; React port will gate via backend completion state.
- Client identity in the React `PortalNav` is sourced from the Supabase session (LinkedIn OIDC `name` + `picture`, falling back to initials). The `Jane Doe` placeholder only survives in the HTML prototype.
- **Intake questionnaire simplified to 9 questions on a single page on 2026-05-11** (ORPHEUS-33). Replaces the 23-question, 7-section flow. Completion derived at read time from answers content; `section_completion` column dropped in migration 010. See `Spec_Simplified_Intake_Questionnaire_2026-05-11.md` for the locked decisions.
- **Self-serve + advisor invite flow adopted 2026-05-11** (ORPHEUS-36 onward). One `auth.users` row can own up to one `advisors` row and up to one `clients` row simultaneously, created lazily. Beta is invitation-only (no `/signup`, no Stripe). Supersedes the LinkedIn-1:1 self-serve model from `Decision_LinkedIn_Auth_2026-04-21.md` — specifically the migration-007 `on_auth_user_created` trigger and the `clients.id = auth.users.id` PK constraint. See `Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md` for the full architecture.
- **Invitation flow shipped 2026-05-13** (ORPHEUS-38). Resend transactional email wired up, `/clients/invite` + `/accept-invitation` + `/clients/{id}/resend-invitation` + `/session` live behind appropriate role gates, three new public frontend pages (`/invite/:token`, `/invite/callback`, `/not-invited`), 43 new pytest cases (114 → 157 green). Migration 012 applied to prod; database cleaned of leftover seed data. Live e2e walkthrough deferred to ORPHEUS-44 — gated on ORPHEUS-25 (cloud Supabase LinkedIn OIDC provider configuration).
- **Advisor admin UI shipped 2026-05-14** (ORPHEUS-39). New `/advisor/clients` React page with three regions: page header + "Run my own report" button, inline two-field invite form (optimistic insert into the list cache), and a list of the advisor's clients with invitation-status + latest-job chips and a Resend action on pending/expired rows. Backed by two new endpoints: `GET /clients` (advisor-gated, returns each row's most-recent job via a single bucketed query) and `POST /advisor/self-report` (idempotent get-or-create of the advisor's self-clients row). Route gated by a new `AdvisorRoute` guard inside `ProtectedRoute`; `SmartIndexRedirect` gains an advisor-only branch so an advisor without a client row lands at `/advisor/clients`. `PortalNav` gains a role-aware middle tab: dual-role users (Andrew, advisor + client) get a "Manage clients / My report" toggle; advisor-only users see a single "Manage clients" pill; client-only users see the unchanged nav. 11 new pytest cases (157 → 168 green). Implementer decisions locked: top-button self-report (not row-in-list), tab-toggle nav (not separate advisor nav bar), empty state hides the list section entirely. "Edit" action button left for follow-up (ORPHEUS-45) — no concrete use case yet.
- **Advisor-aware `GET /jobs/{id}` shipped 2026-05-18** (ORPHEUS-46). Relaxed the role gate from `is_client()`-only to "is_client() AND owns-job OR is_advisor() AND manages-client". The handler now builds an `allowed_client_ids` set from the caller's role(s) — `{roles.client_id}` for clients, `SELECT id FROM clients WHERE advisor_id = roles.advisor_id` for advisors, union for dual-role — and filters jobs via `.in_("client_id", allowed_client_ids)`. Switched from `user_scoped_supabase` to `get_service_client` to match the pattern in `GET /clients`; the 404-not-403 leak-resistance contract is preserved by the handler. Frontend uncloak: `ClientsPage.tsx` drops the `client.is_self &&` guard on the View report Link so it surfaces for any row with `latest_job.status === 'complete'`. 5 new pytest cases (168 → 173 green) in `backend/tests/test_jobs_get.py`.
- **Frontend test infra shipped 2026-05-19** (ORPHEUS-47). Stood up vitest + React Testing Library — first frontend test runner in the project. Six new devDependencies (`vitest`, `@vitest/coverage-v8`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`). Three new `npm` scripts: `test`, `test:watch`, `test:coverage`. Vitest config lives inline in `frontend/vite.config.ts` under `test:` (jsdom env, globals enabled) with a triple-slash `/// <reference types="vitest" />` directive; setup file `src/test-setup.ts` registers `@testing-library/jest-dom/vitest` matchers and an `afterEach(cleanup)` so DOM nodes don't leak between tests. `tsconfig.app.json` gets `"types": ["vitest/globals", "@testing-library/jest-dom"]` so `tsc -b` is happy with the implicit globals. First smoke test at `src/pages/advisor/__tests__/ClientsPage.test.tsx` — vi.mocks the four data hooks (useAdvisorClients, useInviteClient, useResendInvitation, useSelfReport) plus `lib/auth` (to avoid Supabase module-load), wraps in `MemoryRouter`, asserts the page header, the invite form, and the View report Link on a non-self complete-job row (ORPHEUS-46 uncloak regression). 3 vitest cases green. CI: `npm run test -- --run` runs after `npm run build` in the existing frontend job. Convention locked: **vi.mock the data hooks** rather than running a Node MSW server — matches the post-ORPHEUS-28 empty-handlers.ts posture; future tests colocate under `__tests__/` next to the component.
- **Signal Score band labels renamed to tuner metaphor 2026-05-29** (ORPHEUS-49). Weak/Emerging/Moderate/Strong/Exceptional → Dissonant/Untuned/Tuning/Tuned/Resonant. Pure nomenclature; numeric thresholds (0–24, 25–44, 45–64, 65–79, 80–100) and underlying scoring math are unchanged. Renamed surfaces: `backend/scoring/config.py` (SIGNAL_BANDS), `backend/models/scoring.py` (SignalBand enum), `backend/migrations/013_band_rename.sql` (drops + re-adds `scores_band_check` CHECK constraint, migrates existing rows via CASE), `frontend/src/types/scoring.ts` (SignalBand union), `frontend/src/components/signal-meter/bands.ts`, `frontend/src/mocks/fixtures/signalScoreJob.ts`, `frontend/src/pages/design/SignalMeterPlayground.tsx`, `orpheus-signal-score.html`. Test assertions in `backend/tests/test_narrative.py` and pressure-test docstrings in `backend/tests/test_scoring.py` updated to match. **Rubric scoring scale labels in `backend/agents/rubric.py` and `backend/agents/narrative.py` were left as-is** — those words ("Weak clarity", "Strong activity", "Exceptional volume") describe the 1–5 sub-dimension score scale, are internal Claude prompt vocabulary, and never surface to the client. Ownership: labels are product application (Josh's call). Numeric thresholds and band concept are framework design (Andrew, unchanged). Decision Log canon entry drafted for cross-stakeholder visibility.
- **Signal Score / Forward Brief ownership clarified + shared canon adopted 2026-05-20** (Cowork session; meta/coordination work, no Plane ticket). Two changes locked in the same session. (1) Ownership split: Andrew owns the framework's **design** — what is measured, how it's measured, dimensions, weights, bands, sub-dimension rubrics, score-to-band mapping — as SME and framework author. Josh owns the **product application** — whether and how the design lands in product, what surfaces to the client, when, in what form. "People & roles" (both Josh's and Andrew's "Owns" lists) and the "Decision routing for AI sessions" section reflect the split. Andrew's authority over substantive product UX for non-Signal-Score surfaces is preserved. (2) Shared canon: a two-doc structure — **"State of the Moment"** (daily-refreshed snapshot, with a Tim-only weekly "For Tim" block at the top, refreshed Mondays only) and **"Decision Log"** (append-only, cross-stakeholder record with required "Implications for product" field on every entry) — lives in the Ess3 shared drive at `Orpheus Social > 06_Operations > Shared Canon`. Each person's individual Claude session reads both docs at start-of-session and refreshes them at end-of-session via extended `orpheus-session-start` / `orpheus-session-wrap` skills (Josh applied skill edits in-session; the diff lived in `outputs/skill_updates_canon_2026-05-20.md`). The canon is the new sync surface across Josh, Andrew, and Tim's distributed Claude sessions — engineering canon stays in the repo, but cross-stakeholder decisions (especially Tim's legal/compliance moves that shape what we can build) now have a discoverable home. Initial Decision Log entries seeded: ownership clarification (entry #1) and canon adoption (entry #2). Known gap: the Drive MCP exposed in Cowork is read-only for Doc *content* edits (only create + read are available), so in-place State of the Moment refreshes are currently a manual step in the doc UI; the Decision Log's append-only model works fine with create-then-read.
- **Signal Score page redesign + whole-app dark mode shipped 2026-05-29** (ORPHEUS-50). Five phased commits (`80740c1`/`f29d3d0`/`5f55589`/`617dc0b`/`65e9425`). Dark mode is canonical going forward; there is no light variant and no toggle. `orpheus-styles.css` `:root` is rewritten with role-based tokens (`--bg-page`, `--surface-elevated`, `--text-strong`/`--text-body`/`--text-muted`, `--border`, `--accent`/`--accent-strong`/`--accent-tint-soft`/`--accent-tint-hover`, `--primary`/`--primary-hover`, `--issue`, `--shadow-dark`) plus the audio-spectrum pip palette (`--pip-1`..`--pip-5`). Legacy `--warm-*` / `--deep-slate` names stay defined as aliases so existing CSS keeps resolving — see the refreshed Color Tokens section above. Two app-wide color shifts: the accent moves from warm gold (`#C4902A`) to green (`#67ac6c` lighter for eyebrows/Social wordmark, `#218f29` darker for active states like the band pill), and the primary action color moves from deep slate to blue (`#0160d5`); deep slate is repurposed as `--surface-elevated` for avatars, footer band, role-tabs container, dropdown surface. Cards adopt a transparent-bg + `--border` pattern across every surface (dimension cards, checklist items, priority cards, rhythm blocks, milestones band, advisor list rows). Signal Score page rebuilt per the approved Figma: full-bleed waveform hero (`assets/images/waves.jpg`, mirrored at `frontend/src/assets/waves.jpg` so Vite resolution stays inside the project root) shows the composite band label only — no needle, no number; each of the four dimensions is a card with a 5-pill band row (one pill highlighted), the dimension narrative paragraph, and an expandable sub-dimension list rendered as 5-pip rating rows in the audio-spectrum palette. Dimension-level band derivation is client-side from `normalized_score × 100` against the composite SIGNAL_BANDS thresholds — an interim until ORPHEUS-22 moves it server-side. Sub-dim narrative payload wires to the existing `SubDimensionScore.summary` / `.best_practices` / `.improvements` fields; ORPHEUS-21 fills the text when it lands without a contract change. The aspirational Figma sub-dimension labels (Headline specificity, About-section substance, Experience narrative, Skills coherence, Recommendations social proof) are visual reference only — code sub-dim names remain the existing spec. `SignalMeter` + `SubSignalDial` components retire from the production client-facing Signal Score path but stay in-tree for `SignalMeterPlayground` (dev-only) and future reuse. New frontend test at `frontend/src/pages/__tests__/SignalScorePage.test.tsx` (5 cases — hero band, four dim cards, band-pills groups, action links, expand toggle) brings the frontend vitest baseline to **8 green** (was 3). Backend pytest unchanged at 173. Ownership: this entire ticket is product application (Josh's call); Andrew sees via the Decision Log entry.
- **Signal Score hero restructure + per-band waveforms shipped 2026-05-30** (ORPHEUS-51). Single commit (`9a363e5`). Follow-up to ORPHEUS-50 after Josh updated the Figma. Hero moves from a full-bleed page-top band (`.score-hero` was a sibling of `<main>` with `margin-top: -120px` tucking under the nav) into a contained section inside `<main className="main-interior signal-main">`. Waveform image acts as a billboard positioned absolutely inside the contained section. Hybrid-responsive width: default `100vw`, pinned to native 1438px at viewports ≥1440px (the natural threshold — below 1438 the native image would horizontal-scroll). CSS mask dropped; text sits directly over the waveform top, and band-specific assets are expected to carry their own top-edge contrast. Vertical bleed of ~100px into the dimensions section is preserved (a `-24px` negative margin on `.score-hero` plus the natural overflow of the 360px image past the 247px section box, net of main-interior's 36px flex gap). Five band-keyed PNG assets land at `assets/images/wave-{1-5}-{band}.png` with the frontend mirror at `frontend/src/assets/` (same Vite-fs.allow workaround as ORPHEUS-50's `waves.jpg`). A `bandToWaveform(band)` helper in `SignalScorePage.tsx` maps composite band → image at render. Accessibility: composite numeric score is sr-only inside the hero `<h1>` (`"Tuning — composite score 58 of 100"` to screen readers; `"Tuning"` visually). `BandPillRow` aria-label is constructed per-card with `${dim} band: ${activeBand} — score ${N} of 100` so the color-only band indicator has a text fallback for assistive tech. New `.sr-only` utility class added to `orpheus-styles.css` (standard visually-hidden-but-readable pattern; reusable app-wide). Frontend vitest baseline goes 8 → **10 green** (2 new SignalScorePage cases — band-keyed asset selection via stubbed import strings, and sr-only composite-score text presence). Out of scope and filed separately: PortalNav identity cluster (ORPHEUS-52, app-wide), server-side per-dimension band classification (ORPHEUS-22, existing). Known gap not introduced here: sub-dim expand carets are in the Figma but not in the code (pre-existing from ORPHEUS-50); `frontend/src/assets/waves.jpg` is now unreferenced (one-line cleanup, deferred). Ownership: product application (Josh's call); 51 is iteration on 50, no new cross-stakeholder Decision Log entry needed.
- **PortalNav identity cluster shipped 2026-05-30** (ORPHEUS-52). Single commit (`d39a02a`). Same-day follow-up to ORPHEUS-51 — the cluster appeared in the updated Figma but is app-wide, not Signal-Score-only, so it landed as its own ticket. `PortalNav.tsx` replaces the prior `Confidential Portal for [name]` label + dropdown menu with: a two-line "Prepared for / [report subject's name]" text block (eyebrow `--text-muted`, name `--text-strong`, copy is sentence-case in source with CSS `text-transform: uppercase` doing the visual lift), the existing 40×40 circular avatar (kept — visual identity matters cross-surface and the Figma's omission was overruled), and a dedicated 24×24 logout icon button (`--text-muted` → `--text-strong` on hover; inline SVG, no icon library). The dropdown menu is fully retired. **Name-source decision tree:** routes without `:jobId` → session user's LinkedIn `name`; pure client on own report → session user; advisor viewing a client's job → that client's `display_name` from `useAdvisorClients()` (GET /clients roster); dual-role advisor on own self-report → session user, with the `is_self=true` flag on the matched roster row short-circuiting the lookup so the advisor's free-text self-label (e.g. "Andrew (self)") doesn't win over the LinkedIn name. Backed by `useParams` + the existing `useJob` and `useAdvisorClients` hooks — no new backend work; `GET /jobs/{id}` already returned `client_id` (ORPHEUS-46) and `GET /clients` already returned `display_name` + `is_self` (ORPHEUS-39). CSS: `.nav-client` flips from a vertical column (text-above-avatar with dropdown beneath) to a horizontal row (text → avatar → logout button, 14px gap); `.nav-client-label` recolored from `--accent` to `--text-muted`; `.nav-client-trigger` and the entire `.nav-client-menu*` rule family removed; new `.nav-logout-button` styles added. Frontend vitest baseline goes 10 → **14 green** (4 new PortalNav cases at `frontend/src/components/layout/__tests__/PortalNav.test.tsx` — three name-source branches plus a signOut-click regression; uses the ORPHEUS-47 vi.mock-the-data-hooks convention). Known transient flagged in the closing comment: on an advisor's first nav into a client's job there's a brief flicker where the cluster shows the advisor's session name before the roster lookup resolves — acceptable for now, can gate the render on hook completion if it becomes noticeable. Cross-surface oddity flagged: "Prepared for [own name]" reads slightly odd on `/advisor/clients` (a list, not a report); the Figma only mocks the Signal Score surface, so the surface-agnostic fallback is a judgment call to revisit if it grates. Ownership: product application (Josh's call). No new Decision Log entry — 52 is iteration on 50/51, not a new cross-stakeholder decision.
- **Server-side per-dimension band classification shipped 2026-05-30** (ORPHEUS-22). Single commit (`f76b9d9`). Closes the open execution work for a decision that had been locked under ORPHEUS-50: dimensions reuse the composite `SIGNAL_BANDS` thresholds (0–24 Dissonant / 25–44 Untuned / 45–64 Tuning / 65–79 Tuned / 80–100 Resonant) against `normalized_score × 100`. `DimensionScore` gains a required `band: SignalBand` field; `backend/scoring/engine.py`'s `_build_dimension` sets it via `assign_band(normalized * 100)`. The completeness floor only adjusts contribution, so the per-dimension band stays tied to the raw measurement — matches the pre-22 client-side derivation behavior. Frontend mirrors the contract: `frontend/src/types/scoring.ts` adds the required `band` field, `SignalScorePage.tsx` reads `dimension.band` instead of calling the local `dimensionBand()` helper (which is deleted), and the four-dimension fixture in `mocks/fixtures/signalScoreJob.ts` gets matching band values. `SubSignalDial` keeps `bandForNormalizedScore` — that's the dev-only playground path, intentionally unchanged. No migration: `scores.scored_dimensions` is JSONB and Pydantic serialization carries the new field through; ORPHEUS-25 (cloud Supabase LinkedIn OIDC) isn't shipped yet, so no real production scores predate this change. New `TestDimensionBand` class in `backend/tests/test_scoring.py` (7 cases: Dissonant/Untuned/Tuning/Tuned/Resonant coverage, the 80 boundary, `run_scoring` output band consistency, JSONB round-trip serialization) plus four `band=` kwargs in `test_narrative.py` fixtures. Frontend vitest: 14 → **15 green** (+1 new SignalScorePage band-from-fixture assertion); backend pytest unverified from sandbox (PyPI blocked) — Josh's terminal expected to confirm 173 → ~180 green. Ownership: product application (Josh's call); the framework decision was Andrew's and landed under ORPHEUS-50.
- **Railway build pinned in source 2026-05-31** (ORPHEUS-43). Three commits (`120dccd`, `e77882f`, `f567b19`) — two pivots before the final shape landed. Ticket was filed 2026-05-13 after the ORPHEUS-38 deploy crashed with `ModuleNotFoundError: No module named 'pydantic_settings'`; the workaround was a manual Build Command override (`pip install -r backend/requirements.txt`) on both Railway services, brittle because it lived in the dashboard rather than source control. Final fix: **`backend/requirements.txt` was promoted to repo-root `requirements.txt`** (single canonical Python deps file at the standard location). Railpack's Python provider auto-detects the root file and runs `pip install -r requirements.txt` against it; the dashboard override was cleared on both services and both came up green on a fresh build. Same commit deleted the vestigial `nixpacks.toml` (Railpack supersedes it). The pivot history is preserved in commits rather than collapsed: `120dccd` tried option 1 (`railpack.json` with `steps.install.commands` override) but the override dropped the auto-generated step's input layer so `backend/requirements.txt` wasn't visible at build time; `e77882f` tried option 2's literal form (a forwarder `requirements.txt` containing `-r backend/requirements.txt`) but the same layer-scope issue applied — Railpack only copies the root `requirements.txt` into the install context, not the surrounding repo, so the `-r` directive couldn't resolve; `f567b19` did the rename-to-root. **The actual root cause of the original ticket's `ModuleNotFoundError`** turned out to be a *stale* root `requirements.txt` (committed before the project's Python deps list grew, missing `pydantic-settings` / `python-multipart` / `PyJWT` / `cryptography` / `pytest*`): Railpack auto-detected that outdated root copy and installed its packages, and the dashboard override masked the issue by superseding what auto-detection saw. `120dccd` deleted that stale file along with `nixpacks.toml`; `f567b19` recreated it correctly as the canonical full list. Verification: frontend `tsc -b` clean + vitest 15 green (sandbox); backend pytest unverified from sandbox (PyPI blocked) but layout unchanged from ORPHEUS-22's ~180 green baseline; live: backend + worker Railway services boot green from a fresh build with the explicit pip install step in logs. Same session also rolled in a recompressed-PNG refresh of `assets/images/wave-{1-5}-*.png` and the matching `frontend/src/assets/wave-{1-5}-*.png` mirror — visually identical, just smaller file sizes. Ownership: deploy mechanics (Josh's call).
- **`/admin` stopgap shipped 2026-05-31** (ORPHEUS-31). Single commit (`fa380c9`). Ticket was filed 2026-04-21 as Phase 8 of the LinkedIn Auth rollout (ORPHEUS-23) but had sat in the backlog because the operational need hadn't surfaced; ORPHEUS-39's advisor-scoped `/advisor/clients` covered the day-to-day surface, and the all-clients god-mode view stayed deferred until an admin needed to look at any-client-by-id outside their own advisor roster. Two scope decisions locked at session start: (1) all-clients god-mode (not advisor-scoped — distinct from `/advisor/clients`), and (2) ship the inline narrative editor now against the current `public.narratives` schema (`generated_text` + `edited_text` + `status` + `published_at`) rather than waiting on Andrew's Forward Brief revisions; ORPHEUS-21's pending sub-dim narrative fields will extend the editor when they land without a contract change. **Backend** — `backend/auth.py` gains `get_current_admin`: same JWT verification path as `get_current_session_roles` / `get_verified_session` (RS256 or ES256, JWKS cache, audience + issuer + exp), allows the neither-role case (an admin doesn't need an advisors or clients row of their own — the whole point of the surface is god-mode access regardless of role), then layers an env-allowlist check on top via `settings.admin_email_set`. Empty `ADMIN_EMAILS` → 403 with "allowlist is empty" detail; non-admin email → 403 with "not authorized"; bad token still → 401. Case-insensitive membership (lowercases both sides). New `backend/routers/admin.py` with four endpoints, all gated by `get_current_admin` and using `get_service_client()` (RLS bypassed intentionally — that's the point): `GET /admin/clients` (every clients row across all advisors with owning advisor + latest-job nested via three round trips — clients ordered desc, jobs bucketed by client_id, advisors looked up by unique advisor_id set); `GET /admin/jobs` (every jobs row with optional `?client_id` filter; three round trips — jobs, owning clients for label fields, narratives metadata only — id + section + status + has_edited_text + timestamps, no full text); `GET /admin/narratives/{id}` (full narrative payload); `PATCH /admin/narratives/{id}` (`UpdateAdminNarrativeRequest` with optional `edited_text` and / or `status` — Pydantic `exclude_unset` distinguishes field-omitted from field-set-to-null, invalid status → 400 from in-code validation rather than DB enum constraint for a cleaner error message, missing row → 404, empty body → no-op returning current row). `backend/main.py` registers the new router alongside the existing four; `backend/config.py` refreshes the `ADMIN_EMAILS` docstring (no longer "leave blank until the admin router ships"). 16 new pytest cases in `backend/tests/test_admin.py` — 5 for `get_current_admin` (accepts listed, case-insensitive match, rejects non-admin, rejects empty allowlist, still-401 on bad token), 11 for the router (happy paths + empty-table short-circuits + narrative read/update/404/no-op/invalid-status). **Frontend** — new `src/pages/AdminPage.tsx` + `AdminPage.css`: three-pane workflow on a single route (clients table → jobs table filterable by selected client → inline narrative editor on chip click). Editor's form-local state syncs from React Query data via `useEffect([narrativeQuery.data])` so clicking a different narrative chip swaps the editor cleanly; React Query memo-stabilises `data` so the effect only fires on actual id change or successful PATCH. CSS uses the canonical dark-mode role tokens; visual treatment is intentionally lo-fi (internal tool). `src/hooks/useAdmin.ts` exposes four React Query hooks (`useAdminClients`, `useAdminJobs(clientId)`, `useAdminNarrative(id)`, `useUpdateAdminNarrative`) plus an `isAdminEmail` resolver against `VITE_ADMIN_EMAILS`. All queries gate on (a) authenticated session and (b) signed-in email present in the allowlist so non-admins never fire a request guaranteed to 403; `useUpdateAdminNarrative` onSuccess invalidates the `['admin', 'jobs']` prefix so the section's `has_edited_text` / `status` chips refresh after a save. `src/lib/apiClient.ts` gains `apiPatchJson` (PATCH + JSON body + bearer auth, same `ApiError` shape as `apiPostJson`). `src/App.tsx` registers the `/admin` route inside `ProtectedRoute` under a new `AdminRoute` guard that mirrors `AdvisorRoute`'s posture: signed-in email must appear in `VITE_ADMIN_EMAILS` or we redirect to `/`. **AdminRoute is a UX gate, not security** — the backend re-enforces the allowlist via `get_current_admin`; the client-side check exists so non-admins navigating directly to `/admin` never see the page chrome. Same pattern as `ADMIN_EMAILS` / `VITE_ADMIN_EMAILS` (kept in sync manually; backend enforces). 5 new vitest cases at `frontend/src/pages/__tests__/AdminPage.test.tsx` — renders clients table from hook data, renders unfiltered jobs by default, client-row click filters the jobs pane + shows Clear filter, narrative chip click opens editor with loaded text, Save fires the mutation with the form values. Uses the ORPHEUS-47 convention (vi.mock the data hooks). Frontend vitest baseline goes 15 → **20 green**; backend pytest unverified from sandbox (PyPI blocked); 16 new cases land on top of the ~180-green ORPHEUS-22 baseline — confirmation via Josh's terminal. Known follow-ups deferred and flagged in the closing comment: (a) AdminRoute could be tightened to also call `useSessionRoles` so admins get the page-loading placeholder instead of a flash of null state — minor, not currently observed; (b) pagination on `/admin/clients` + `/admin/jobs` is a deliberate scope-cut, ~500 clients is the rough threshold; (c) edit endpoint on clients rows is out of scope, file as ORPHEUS-45's twin if Andrew hits the need. Ownership: product application (Josh's call). No new Decision Log entry — `/admin` is a stopgap surface scoped to operate inside framework decisions that are already documented.
- **HTML prototype backport: ORPHEUS-51/52 sync shipped 2026-05-30** (no Plane ticket; same-day follow-up to ORPHEUS-22 in the same session). Two commits (`9f137f9`, `b029253`). The ORPHEUS-51 and ORPHEUS-52 sessions had shipped CSS-only updates (including removing rules — `.nav-client-trigger`, `.nav-client-menu*`) without updating the HTML prototype markup, so Live Server was visually broken: every prototype page rendered the old nav with no matching CSS, and `orpheus-signal-score.html` still pointed at the pre-51 full-bleed hero with `waves.jpg`. The backport replaces the old `<div class="nav-client"><span class="nav-client-label">Confidential Portal for</span><span class="nav-client-name">Jane Doe</span></div>` cluster across **all 9 prototype pages** with the new identity cluster (`.nav-client-text` with "Prepared for" eyebrow + name, `.nav-client-avatar` with initials fallback, `.nav-logout-button` with inline SVG door+arrow glyph) — mirrors `PortalNav.tsx` exactly so the prototype and React app render the same DOM tree. `orpheus-signal-score.html` additionally gets the ORPHEUS-51 hero treatment: `<section class="score-hero">` moves inside `<main class="main-interior signal-main">`, inline CSS swapped from the old full-bleed pattern (`-120px` margin-top, 560px height, mask gradient) to the new contained billboard pattern (247px height, waveform absolutely positioned centered on viewport with `width:100vw` default and `min-width:1440px` pinned at 1438px), waveform source swapped from `waves.jpg` to `wave-3-tuning.png` (matches the prototype's Tuning composite), sr-only composite-score span added to the hero `<h1>` (`"Tuning — composite score 58 of 100"` to assistive tech), and the four dimension band-pills rows get the score-aware aria-label form (`"<DimName> band: <Band> — score <N> of 100"`) following ORPHEUS-51's React-side accessibility posture. The `body { align-items: stretch }` override the old full-bleed hero needed is dropped — the contained pattern uses the default centered layout. Bug caught + fixed mid-session: the first hero-CSS edit accidentally removed the opening `<style>` tag; restored before commit. Ownership: product application (Josh's call) — pure sync to already-shipped tickets, no new design decision. Reinforces the CLAUDE.md contract that the HTML prototype is "the visual source of truth for the design system" — future React-only tickets that change shared CSS should land prototype updates in the same session unless explicitly deferred.

---

## Signal Score Framework (v2)

4 dimensions, weighted to 100-point composite. The score measures whether a member's profile and behavior provide signals LinkedIn's retrieval and ranking systems are documented to use. It does not measure outcomes.

| Dimension | Weight | What It Measures |
|---|---|---|
| Profile Signal Clarity | 35% | Does the profile give the retrieval system clear language to build an accurate member embedding? |
| Behavioral Signal Strength | 30% | Has the member built sufficient, recent, coherent engagement history for the ranking model? |
| Behavioral Signal Quality | 20% | Is the member generating the action types the optimization targets reward? |
| Profile-Behavior Alignment | 15% | Is content topically and semantically consistent with the declared professional identity? |

Dimensions 1 and 4 are scored by Claude via rubrics (1–5 scale). Dimensions 2 and 3 are deterministic band lookups (0–5 scale). All PROVISIONAL parameters are adjustable config, not hardcoded.

Client-facing output is a **signal strength band** (Dissonant/Untuned/Tuning/Tuned/Resonant — the tuner metaphor, renamed 2026-05-29 per ORPHEUS-49), not a raw number. Numeric scores visible to advisors only.

**What moved to Forward Brief (not scored):** Reach, Resonance, Authority, viewer-actor affinity, visual professionalism, engagement invitation.

Pressure-test confirmed via live pipeline (2026-04-13): Andrew Segars scores 77.6 → Tuned band (data: 2025-03-17 to 2026-03-16).

See `PRODUCT_CONTEXT.md` for full sub-dimension specifications, band thresholds, scoring formula, and Forward Brief data contract.

---

## Production Stack

Backend deployed on Railway, database on Supabase, frontend scaffolded with Vite + React. Local development uses Supabase CLI + Docker; see `SETUP_phase1_local_auth.md` for first-time onboarding.

### Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React | Dynamic client portal, score display, review delivery |
| Backend | FastAPI (Python) | Async; Claude SDK support; scoring scripts already in Python |
| Database | Supabase (PostgreSQL) | Auth, job queue, result storage; free tier for beta |
| AI | Anthropic API — Claude | Rubric scoring (Dim 1 + 4) and narrative generation |
| Hosting — frontend | Vercel | Free tier |
| Hosting — backend | Railway | Free tier / ~$5/mo |
| Project management | Plane (cloud) | workspace: `orpheussocial`, project: `Orpheus`, identifier: `ORPHEUS` |
| CI/CD | GitHub Actions | Existing repo |

### Project Structure

```
/
├── CLAUDE.md
├── PRODUCT_CONTEXT.md                 # Full scoring specs, schema, decisions
├── SETUP_phase1_local_auth.md         # Onboarding: local Supabase + dev LinkedIn app + apply migrations 001/011/012
├── Decision_LinkedIn_Auth_2026-04-21.md  # Source markdown for ORPHEUS-23
├── orpheus-*.html                     # HTML/CSS prototype (visual source of truth)
├── orpheus-styles.css                 # Shared design system stylesheet
├── supabase/
│   └── config.toml                    # Local Supabase CLI config — LinkedIn provider via env interpolation
├── frontend/                          # Vite + React app
│   ├── .env.local.example             # Template for VITE_SUPABASE_* / VITE_API_BASE_URL / VITE_ADMIN_EMAILS
│   ├── package.json                   # @supabase/supabase-js, @tanstack/react-query, react-router-dom
│   ├── vercel.json                    # SPA rewrite — all paths fall through to index.html
│   └── src/
│       ├── App.tsx                    # Routes; ProtectedRoute checks Supabase session + GET /session roles
│       ├── main.tsx
│       ├── test-setup.ts              # Vitest setup — jest-dom matchers + afterEach(cleanup) (ORPHEUS-47)
│       ├── lib/
│       │   ├── supabase.ts            # Singleton browser client (fail-fast on missing VITE_SUPABASE_*)
│       │   ├── auth.ts                # useSession, signInWithLinkedIn, signOut
│       │   ├── apiClient.ts           # Bearer-token-attaching fetch wrapper (GET / POST JSON / POST multipart)
│       │   └── invitation.ts          # sessionStorage helpers for the pending invitation token
│       ├── hooks/
│       │   ├── useAcceptInvitation.ts # React Query mutation against POST /accept-invitation; invalidates ['session'] on success
│       │   ├── useSessionRoles.ts     # React Query against GET /session; gated on auth, staleTime Infinity
│       │   ├── useAdvisorClients.ts   # React Query against GET /clients (ORPHEUS-39)
│       │   ├── useInviteClient.ts     # Mutation against POST /clients/invite with optimistic list insert
│       │   ├── useResendInvitation.ts # Mutation against POST /clients/{id}/resend-invitation
│       │   ├── useSelfReport.ts       # Mutation against POST /advisor/self-report; invalidates ['session'] on success
│       │   └── ...                    # plus useJob / useCreateJob / useGroundworkProgress / useQuestionnaire
│       ├── pages/                     # LoginPage, InviteLandingPage, InviteCallbackPage, NotInvitedPage,
│       │                              # SignalScorePage, ForwardBriefPage, CheatSheetPage, GroundworkPage, etc.
│       │   └── advisor/               # Advisor-only surface
│       │       ├── ClientsPage.tsx    # /advisor/clients — invite, list, resend, self-report (ORPHEUS-39)
│       │       └── __tests__/         # Vitest colocation — ClientsPage.test.tsx (ORPHEUS-47)
│       ├── components/                # PortalLayout, PortalNav, SignalMeter, SubSignalDial, EmailMismatchConfirmation
│       ├── types/                     # job.ts + scoring.ts (mirror backend models)
│       └── mocks/                     # MSW handlers (empty by default; real backend serves /jobs)
├── backend/                           # FastAPI app
│   ├── main.py                        # App entry; CORS allowlist + Settings validation at boot
│   ├── config.py                      # Pydantic BaseSettings — fail-fast validation of required env
│   ├── db.py                          # get_service_client (RLS-bypass) + user_scoped_supabase(token)
│   ├── auth.py                        # get_current_session_roles + get_verified_session JWT dependencies
│   ├── routers/                       # API route handlers
│   │   ├── __init__.py
│   │   ├── jobs.py                    # POST /jobs + GET /jobs/{id}
│   │   ├── clients.py                 # GET /clients, POST /clients/invite, /accept-invitation, /clients/{id}/resend-invitation
│   │   ├── advisor.py                 # POST /advisor/self-report (idempotent get-or-create of advisor's self-clients row)
│   │   └── session.py                 # GET /session (canonical "who am I" probe, 200 even for neither-role)
│   ├── email/                         # Transactional email (ORPHEUS-38)
│   │   ├── resend_client.py           # HTTP wrapper around Resend's REST API; sandbox mode on test_ keys
│   │   └── templates.py               # Invitation email subject + html + text formatter
│   ├── models/                        # Pydantic data models
│   │   ├── job.py                     # Job state model
│   │   ├── scoring.py                 # v2 scoring output models (ScoringStageOutput)
│   │   └── quality.py                 # Data quality report
│   ├── ingestion/                     # LinkedIn ZIP + XLSX parsing
│   │   ├── types.py                   # JSONB shape models for parsed data
│   │   ├── zip_parser.py              # ZIP archive parser
│   │   └── xlsx_parser.py             # Analytics XLSX parser
│   ├── scoring/                       # Deterministic Signal Score computation
│   │   ├── config.py                  # All PROVISIONAL thresholds and weights
│   │   └── engine.py                  # run_scoring() entry point
│   ├── agents/                        # Claude API calls (2 calls in pipeline)
│   │   ├── rubric.py                  # Dim 1 + Dim 4 rubric scoring
│   │   └── narrative.py               # Narrative generation + data quality integration
│   ├── workers/                       # Background job processor (separate Railway service)
│   │   └── processor.py               # Job loop with optimistic locking, 4-stage pipeline
│   ├── migrations/                    # SQL migrations (applied via Studio SQL Editor or `supabase db push`)
│   │   ├── 001_base_schema.sql        # Snapshot of prod public schema as of 2026-05-11 (ORPHEUS-35)
│   │   ├── 003_v2_scoring_columns.sql
│   │   ├── 004_rename_narratives_dimension.sql
│   │   ├── 005_quality_report_column.sql
│   │   ├── 006_claim_next_job_rpc.sql
│   │   ├── 007_clients_table.sql      # HISTORICAL — LinkedIn 1:1 design, on_auth_user_created trigger retired by ORPHEUS-36
│   │   ├── 008_rls_enable.sql         # HISTORICAL — simpler RLS than prod's _as_advisor/_as_client framework
│   │   ├── 008_rls_verify.sql         # Companion: two-tenant isolation check (BEGIN ... ROLLBACK)
│   │   ├── 009_questionnaire_responses.sql  # HISTORICAL — superseded by 010 (and by 011 against the prod-base path)
│   │   ├── 010_questionnaire_simplified.sql # HISTORICAL — local-dev path; on the prod-base path use 011 instead
│   │   ├── 011_questionnaire_align_to_spec.sql  # Reshape questionnaire_responses to ORPHEUS-33 spec on top of 001 (ORPHEUS-35)
│   │   └── 012_clients_invitation_columns.sql   # invitation_token + invitation_expires_at on public.clients (ORPHEUS-36)
│   ├── tests/                         # Test suite (pytest) — 168 total post-ORPHEUS-39
│   │   ├── test_scoring.py            # 48 tests for scoring engine
│   │   ├── test_narrative.py          # 8 tests for quality report formatting
│   │   ├── test_auth.py               # JWT verification + role permutations + get_verified_session
│   │   ├── test_config.py             # Boot-fail-fast tests for required env (RESEND_API_KEY, APP_BASE_URL)
│   │   ├── test_resend_client.py      # Resend HTTP wrapper (4xx / 5xx / network / sandbox)
│   │   ├── test_email_templates.py    # Invitation email snapshot invariants
│   │   ├── test_clients_invite.py     # POST /clients/invite happy + 403 + 409 + 502
│   │   ├── test_clients_list.py       # GET /clients happy + is_self flag + empty + 403 role-gating
│   │   ├── test_accept_invitation.py  # /accept-invitation state machine (mismatch + replay + expired)
│   │   ├── test_resend_invitation.py  # /clients/{id}/resend-invitation rotates token, 409 on accepted
│   │   ├── test_advisor_self_report.py # POST /advisor/self-report idempotency + display_name fallbacks + 403
│   │   └── test_session.py            # GET /session role-permutation coverage
│   └── .env.example                   # Required + optional env vars (mirror Settings class)
├── requirements.txt                   # Canonical Python deps (repo root, post-ORPHEUS-43)
└── .github/
    └── workflows/                     # GitHub Actions CI/CD
```

### Analysis Pipeline

The pipeline has four stages. Claude is used in two of them (rubric scoring and narrative generation). All other scoring is deterministic.

1. **Ingestion** — Parse LinkedIn ZIP (CSVs) and Analytics XLSX into structured data. Pure Python, deterministic. Parsers validated against real export data.

2. **Rubric scoring** — Claude applies written rubrics to profile data (Dim 1: 5 sub-dimensions) and profile+content data (Dim 4: 2 sub-dimensions). Returns integer scores (1–5) per sub-dimension. Full rubric text is in `agents/rubric.py`.

3. **Deterministic scoring** — Computes Dim 2 and Dim 3 from archive data (quantitative band lookups). Combines all four dimensions using the formula `(sum − min) / (max − min) × weight`. Also extracts Forward Brief structured data (Reach, Resonance, Authority from XLSX; qualitative flags from ZIP). Single entry point: `scoring/engine.py → run_scoring()`. Output: `ScoringStageOutput` (scored_dimensions + forward_brief_data).

4. **Narrative generation** — Claude receives both scored_dimensions and forward_brief_data as structured inputs, plus questionnaire answers. Generates dimension narratives and Forward Brief text. Prompt must map score ranges to narrative guidance explicitly.

Keeping scoring deterministic and separate from narrative generation makes scores auditable, reproducible, and comparable across reporting cycles.

### Job Queue Pattern

Ingestion + scoring + Claude call takes 20–60 seconds — too long for a synchronous web request. The job queue pattern decouples submission from processing:

1. Client submits LinkedIn data → FastAPI creates a `pending` job in Supabase → returns `job_id` immediately
2. Client sees the Analysis in Progress screen (already built)
3. Background worker claims the job, runs the full pipeline, saves results
4. Frontend polls `/jobs/{job_id}` every few seconds → updates UI on completion

**Job states:** `pending → running → complete` (failed jobs retry up to 3×, then surface an error)

**Queue implementation for beta:** Supabase `jobs` table with `claim_next_job` RPC function using `FOR UPDATE SKIP LOCKED` for atomic job claiming. Worker is a separate Railway service that requires manual redeploy after pushes.

### Environment Variables

Backend (validated by `backend/config.py` Pydantic `Settings`; missing required vars block boot with a clear `ValidationError`):

```
# Required
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SUPABASE_ANON_KEY=
ANTHROPIC_API_KEY=
RESEND_API_KEY=                                          # ORPHEUS-38; test_ prefix triggers sandbox mode
APP_BASE_URL=                                            # ORPHEUS-38; invite-link host, http(s) URL-validated

# Optional with defaults
ADMIN_EMAILS=                                            # CSV; consumed by ORPHEUS-31 admin stopgap
FRONTEND_ORIGINS=http://localhost:5173                   # CSV; CORS allowlist
SUPABASE_JWT_AUDIENCE=authenticated                      # JWT aud claim
INVITATION_EXPIRY_DAYS=14                                # ORPHEUS-38; soft expiry on issued invitations

# For Supabase CLI env interpolation (local dev only — not read by backend)
SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_CLIENT_ID=
SUPABASE_AUTH_EXTERNAL_LINKEDIN_OIDC_SECRET=
```

Frontend (`frontend/.env.local`, validated at module load by `src/lib/supabase.ts`):

```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_ADMIN_EMAILS=                                       # mirrors backend ADMIN_EMAILS for /admin UX gate
VITE_API_BASE_URL=http://localhost:8000
```

None of these are committed. Templates with inline comments live at `backend/.env.example` and `frontend/.env.local.example`.

**Deploy-platform mirror.** The same vars need to be set in the deploy dashboards or services won't boot / the frontend bundle won't be able to talk to anyone. Out of repo by necessity, but worth knowing about:

- **Railway** (Settings → Variables, on BOTH the backend service and the worker service): every backend Required var above. `FRONTEND_ORIGINS` must include the production frontend origin (`https://app.orpheussocial.com`) or CORS rejects every request from the deployed UI. Build Command is auto-detected by Railpack from the repo-root `requirements.txt` post-ORPHEUS-43 (2026-05-31); no manual override needed.
- **Vercel** (Settings → Environment Variables, applied to all environments): every `VITE_*` var above. These are baked into the JS bundle at build time, so missing values surface as a runtime "Missing Supabase configuration" error on the deployed site, not a build failure. After saving, trigger a redeploy so the new bundle picks them up.

### Backend Conventions

- Use `async/await` throughout — FastAPI and Supabase client are both async
- All env reads flow through `backend.config.get_settings()` (Pydantic `BaseSettings`). The app fails fast at boot when required vars are missing. Worker process still has its own three `os.environ` reads — consolidating is a small follow-up.
- API routes live in `/backend/routers/` — one file per resource. Client-facing routes depend on `get_current_session_roles` (in `backend/auth.py`), which JWT-verifies the Bearer token against the cached Supabase JWKS and then runs two independent SELECTs against `public.advisors` and `public.clients` (keyed on `user_id = sub`) to populate a typed `SessionRoles(user_id, email, access_token, advisor_id, client_id)`. A user may hold one role, both, or — for the typed 401 "not invited" case — neither. Route handlers gate themselves on `roles.is_advisor()` / `roles.is_client()` and raise 403 if their required role is missing. `auth.py` supports both RS256 and ES256 signatures and reads JWKS from `/auth/v1/.well-known/jwks.json` (the post-GoTrue-v2 path). Replaces the pre-ORPHEUS-37 `CurrentClient` / `get_current_client` single-role dependency.
- `get_verified_session` is the variant for the small set of routes that must legitimately serve neither-role callers (ORPHEUS-38): `POST /accept-invitation` (caller is post-OAuth but the clients row isn't linked yet) and `GET /session` (returning `{advisor_id: null, client_id: null}` IS the meaningful response). Same JWT verification path; only the role-presence gate is relaxed. ~99% of authenticated routes still use `get_current_session_roles`.
- Transactional email lives in `/backend/email/` — `resend_client.py` is a hand-rolled `urllib.request` wrapper around Resend's REST API (no SDK; matches the JWKS-fetch pattern in `auth.py`), `templates.py` owns the invitation subject + html + text content. Sandbox mode on the wrapper triggers when `RESEND_API_KEY` starts with `test_` or is the literal `test` — logs and returns a fake message id without making the HTTP call. Real keys start with `re_` so there's no overlap. The invitation routes catch `EmailSendError` and return 502 with detail directing the advisor to the resend endpoint; the persisted clients row is intentionally not rolled back on send failure.
- `backend/routers/clients.py` hosts two `APIRouter` instances side by side: `router` (prefix=`/clients`) for advisor-owned routes (`GET /clients`, `POST /clients/invite`, `POST /clients/{client_id}/resend-invitation`), and `accept_router` (no prefix) for `POST /accept-invitation` — the latter lives outside `/clients` because its caller has no clients row yet. Both are registered in `backend/main.py`. `GET /clients` (ORPHEUS-39) is the advisor admin list view; it runs two queries — clients filtered on `advisor_id`, then jobs filtered on `client_id IN (...)` ordered desc, bucketed in Python — and returns `{id, display_name, email, invitation_status, is_self, latest_job}` per row. `is_self` flags the row whose `user_id == auth.uid()` so the UI can render the advisor's own self-clients row distinctly.
- `backend/routers/advisor.py` hosts `POST /advisor/self-report` (ORPHEUS-39) — the idempotent get-or-create endpoint for the advisor's self-clients row. Lives outside `/clients` because the caller is acting on their own behalf rather than managing another client. Optional `display_name` field falls back to the email local-part server-side so the schema's NOT-NULL constraint is always satisfied. Idempotent: a second call returns `{client_id: <existing>, created: false}` without an INSERT.
- Acceptance preserves `invitation_token` and `invitation_expires_at` on the UPDATE (only `invitation_status` flips to `accepted` and `user_id` is set). This deliberately deviates from the spec's literal "null both" instruction so the "replay by same user → 200 with existing client_id" case works as documented — the SELECT-by-token lookup would otherwise fail. The partial unique index `WHERE invitation_token IS NOT NULL` still enforces uniqueness on active invitations; resend-invitation refuses to overwrite accepted rows.
- Two Supabase client patterns:
  - `get_service_client()` — service-role, RLS-bypassing. Cached. Used by the worker, admin endpoints, and the JWT-verification dependency itself (which needs to read `public.clients` before any user context is available).
  - `user_scoped_supabase(access_token)` — fresh per-request, JWT attached via `postgrest.auth(token)`. Client-facing routes must use this so the migration-008 RLS policies enforce ownership. Caching this client across requests would cause auth bleed.
- RLS posture: enabled on `clients` and `jobs` (and conditionally on `ingested_data`/`scores`/`narratives` where they exist). Policies key on `auth.uid()`. The `on_auth_user_created` trigger in migration 007 enforces the LinkedIn `email_verified` gate; unverified sign-ins abort cleanly with no orphan rows.
- Ingestion logic lives in `/backend/ingestion/` — one file per source (zip_parser.py, xlsx_parser.py)
- Scoring logic lives in `/backend/scoring/` — `config.py` holds all PROVISIONAL thresholds, `engine.py` is the orchestrator
- Claude calls live in `/backend/agents/` — `rubric.py` (Dim 1 + 4 scoring) and `narrative.py` (report generation)
- Job queue state managed via `jobs` table in Supabase
- Pydantic models in `/backend/models/` define the data contracts between pipeline stages
- Worker runs as a separate process (`python -m backend.workers`) — uses service-role client, optimistic locking for job claims
- All PROVISIONAL scoring parameters serialized into `config_snapshot` on the jobs table for reproducibility

### Frontend Conventions

- Vite + React 18 + TypeScript. React Query for server state. React Router v6 for routing. `@supabase/supabase-js` for auth.
- `frontend/src/lib/supabase.ts` is the singleton Supabase browser client; throws at module load if `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` are missing.
- `frontend/src/lib/auth.ts` exposes `useSession()`, `signInWithLinkedIn(redirectTo?)`, and `signOut()`. `useSession()` clears the React Query cache on `SIGNED_OUT` to avoid stale data leaking between sessions.
- Authenticated routes live under a `ProtectedRoute` wrapper in `App.tsx`. `ProtectedRoute` checks two gates: the Supabase session via `useSession()`, then the backend session roles via `useSessionRoles()` (a React Query hook against `GET /session`). Neither-role responses redirect to `/not-invited`. Public routes (no `ProtectedRoute`) are `/login`, `/invite/:token`, `/invite/callback`, `/not-invited`, and the dev-only `/design/signal-meter` playground.
- Advisor-only routes (`/advisor/*`) layer an `AdvisorRoute` guard inside `ProtectedRoute` (ORPHEUS-39). `AdvisorRoute` redirects non-advisors to `/` rather than rendering a 403 page — combined with `SmartIndexRedirect`'s advisor-only branch (advisor with no clients row → `/advisor/clients`), the URL bounces are coherent for every role permutation. The `PortalNav` component renders a role-aware middle tab toggle: dual-role users see "Manage clients / My report"; advisor-only users see a single "Manage clients" pill; client-only users see no extra nav.
- `useSessionRoles` caches with `staleTime: Infinity` and `retry: false` — roles don't change across JWT refreshes, and a 401 from `/session` is meaningful rather than transient. The `['session']` query gets invalidated on accept-invitation success so the post-acceptance role state is observed without a full page reload.
- The invitation flow's frontend lives across three pages and one shared lib module: `pages/InviteLandingPage.tsx` (public, side-effect-only redirect into LinkedIn OAuth — stashes the token in `sessionStorage` via `lib/invitation.ts`), `pages/InviteCallbackPage.tsx` (public, post-OAuth state machine: loading / mismatch / success / error), and `pages/NotInvitedPage.tsx` (public landing for authenticated-but-not-linked users). The `EmailMismatchConfirmation` component is presentational; the callback page wires sign-out + navigation for the Cancel action.
- API calls go through `frontend/src/lib/apiClient.ts`, which attaches `Authorization: Bearer <session.access_token>` to every outgoing request automatically. Three flavors: `apiGet`, `apiPostJson`, `apiPostMultipart`. All throw a typed `ApiError(message, status, body)` on non-2xx so callers can extract `body.detail` for user-facing messages.
- Design tokens come from the shared `orpheus-styles.css` (same file the prototype uses). Per-page styles sit in a sibling `*.css` next to the page component.
- `frontend/vercel.json` rewrites every non-asset request to `/index.html` so direct nav to `/login`, `/invite/<token>`, etc. is handled by React Router instead of 404-ing on Vercel's static layer. Required because Vercel's Vite framework preset doesn't auto-add this rewrite.
- MSW handlers are intentionally empty (the real backend serves all client-facing routes). Bring back the demo-job handler in `mocks/handlers.ts` only when iterating on UI offline.
- Tests run via **vitest + React Testing Library** (ORPHEUS-47). Command is `npm run test` (watch via `npm run test:watch`, coverage via `npm run test:coverage`). Vitest config lives in `frontend/vite.config.ts` under `test:` — jsdom env, globals enabled. `frontend/src/test-setup.ts` registers `@testing-library/jest-dom` matchers and runs `cleanup()` after each test. Tests colocate in `__tests__/` directories next to the component (e.g. `src/pages/advisor/__tests__/ClientsPage.test.tsx`). The convention is to **`vi.mock` the data hooks** (useAdvisorClients, useInviteClient, etc.) rather than running a Node MSW server — keeps tests fast and matches the empty-`handlers.ts` posture. CI runs `npm run test -- --run` after `npm run build` in the frontend job. Baseline as of ORPHEUS-47: 3 tests green (ClientsPage smoke).

---

## Plane Documentation Conventions

Plane is the source of truth for tasks and documentation. Do not maintain a duplicate task list in this file.

Work items are referenced as `ORPHEUS-[n]` (e.g. `ORPHEUS-12`). Use these identifiers in commit messages and PRs to link work to Plane issues.

Full conventions — file naming patterns, commit message format, Plane ticket states + UUIDs, page categories, page publishing workflow, and the session handoff pattern — live in **`CONVENTIONS.md`**. Keep that file in sync when conventions change; don't duplicate the content here.

---

## Deferred / Pending

See the Orpheus project in Plane for the current task list. Plane is the source of truth — do not maintain a parallel list here.
