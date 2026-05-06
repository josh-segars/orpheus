# Orpheus Social — Project Context

Orpheus Social is a client portal and diagnostic tool for **Andrew Segars'
Strategic Digital Presence Advisory** practice. It guides senior executive
clients through a structured data-gathering phase ("Groundwork"), then
delivers a **Signal Score** diagnostic and **Forward Brief** action plan.

**Current state:** two parallel implementations.

- **HTML/CSS prototype** (14 screens, JS-free) lives flat in the repo root and renders via VS Code Live Server. It is the visual source of truth for the design system.
- **Production stack** is in active development: FastAPI backend (Railway), Supabase Postgres with Auth + RLS, Vite + React frontend (Vercel). As of 2026-05-06, LinkedIn (OIDC) sign-in works end-to-end against local Supabase; the React shell renders Signal Score, Forward Brief, and Cheat Sheet pages with auth, RLS, and the typed JWT contract in place.

**Active phase:** porting the prototype's product flow (Welcome, Groundwork, questionnaire, LinkedIn upload, Analysis-in-Progress) into the React app. See the Plane backlog for the open ORPHEUS-n tickets.

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
```
--deep-slate:     #1C2B3A   (primary dark, nav bg, buttons)
--warm-gold:      #C4902A   (accent, active states, highlights, watch tone)
--warm-ivory:     #F9F6F0   (page background)
--warm-parchment: #EDE9E1   (card/input backgrounds)
--warm-text:      #271D10   (body text)
--warm-stone:     #7A6A56   (secondary text, placeholders, strength tone)
--warm-border:    #DDD5C8   (borders, dividers)
--red-clay:       #BD3F3A   (gap/issue tone — sub-dimension icons, alerts)
```

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
| `orpheus-questionnaire-s1.html` | Q: Professional Identity (Q1–Q4) | ✅ Complete |
| `orpheus-questionnaire-s2.html` | Q: Career Stage & Context (Q5–Q7) | ✅ Complete |
| `orpheus-questionnaire-s3.html` | Q: Target Audiences (Q8–Q10) | ✅ Complete |
| `orpheus-questionnaire-s4.html` | Q: Goals (Q11–Q13) | ✅ Complete |
| `orpheus-questionnaire-s5.html` | Q: Current LinkedIn Relationship (Q14–Q17) | ✅ Complete |
| `orpheus-questionnaire-s6.html` | Q: Voice & Style (Q18–Q20) | ✅ Complete |
| `orpheus-questionnaire-s7.html` | Q: Practical Parameters (Q21–Q23) | ✅ Complete |
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

| # | Section | Type |
|---|---|---|
| 1–4 | Professional Identity | Open text |
| 5 | Career Stage & Context | Radio (5 options + Other w/ inline text) |
| 6 | Career Stage & Context | Radio (4 options) |
| 7 | Career Stage & Context | Open text |
| 8–10 | Target Audiences | Open text |
| 11 | Goals | Open text |
| 12 | Goals | Checkboxes (7 options, select all that apply) |
| 13 | Goals | Open text |
| 14 | Current LinkedIn Relationship | Radio (5 options) |
| 15 | Current LinkedIn Relationship | Radio (5 options) |
| 16 | Current LinkedIn Relationship | Scale 1–5 |
| 17 | Current LinkedIn Relationship | Open text |
| 18–20 | Voice & Style | Open text |
| 21 | Practical Parameters | Radio (4 options) |
| 22 | Practical Parameters | Radio (3 options, "Yes" has inline text) |
| 23 | Practical Parameters | Open text |

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

Client-facing output is a **signal strength band** (Weak/Emerging/Moderate/Strong/Exceptional), not a raw number. Numeric scores visible to advisors only.

**What moved to Forward Brief (not scored):** Reach, Resonance, Authority, viewer-actor affinity, visual professionalism, engagement invitation.

Pressure-test confirmed via live pipeline (2026-04-13): Andrew Segars scores 77.6 → Strong band (data: 2025-03-17 to 2026-03-16).

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
├── SETUP_phase1_local_auth.md         # Onboarding: local Supabase + dev LinkedIn app
├── Decision_LinkedIn_Auth_2026-04-21.md  # Source markdown for ORPHEUS-23
├── orpheus-*.html                     # HTML/CSS prototype (visual source of truth)
├── orpheus-styles.css                 # Shared design system stylesheet
├── supabase/
│   └── config.toml                    # Local Supabase CLI config — LinkedIn provider via env interpolation
├── frontend/                          # Vite + React app
│   ├── .env.local.example             # Template for VITE_SUPABASE_* / VITE_API_BASE_URL / VITE_ADMIN_EMAILS
│   ├── package.json                   # @supabase/supabase-js, @tanstack/react-query, react-router-dom
│   └── src/
│       ├── App.tsx                    # Routes; ProtectedRoute wraps the portal; /login is public
│       ├── main.tsx
│       ├── lib/
│       │   ├── supabase.ts            # Singleton browser client (fail-fast on missing VITE_SUPABASE_*)
│       │   ├── auth.ts                # useSession, signInWithLinkedIn, signOut
│       │   └── apiClient.ts           # Bearer-token-attaching fetch wrapper
│       ├── pages/                     # LoginPage, SignalScorePage, ForwardBriefPage, CheatSheetPage, NotFoundPage
│       ├── components/                # PortalLayout, PortalNav (session-aware), SignalMeter, SubSignalDial
│       ├── types/                     # job.ts + scoring.ts (mirror backend models)
│       └── mocks/                     # MSW handlers (empty by default; real backend serves /jobs)
├── backend/                           # FastAPI app
│   ├── main.py                        # App entry; CORS allowlist + Settings validation at boot
│   ├── config.py                      # Pydantic BaseSettings — fail-fast validation of required env
│   ├── db.py                          # get_service_client (RLS-bypass) + user_scoped_supabase(token)
│   ├── auth.py                        # get_current_client dependency: JWT verification via cached Supabase JWKS
│   ├── routers/                       # API route handlers
│   │   ├── __init__.py
│   │   └── jobs.py                    # GET /jobs/{id} — depends on get_current_client + user_scoped_supabase
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
│   │   ├── 003_v2_scoring_columns.sql
│   │   ├── 004_rename_narratives_dimension.sql
│   │   ├── 005_quality_report_column.sql
│   │   ├── 006_claim_next_job_rpc.sql
│   │   ├── 007_clients_table.sql      # public.clients + on_auth_user_created trigger + jobs.client_id FK + backfill
│   │   ├── 008_rls_enable.sql         # RLS policies on clients/jobs and (where present) ingested_data/scores/narratives
│   │   └── 008_rls_verify.sql         # Companion: two-tenant isolation check (BEGIN ... ROLLBACK)
│   ├── tests/                         # Test suite (pytest)
│   │   ├── test_scoring.py            # 48 tests for scoring engine
│   │   ├── test_narrative.py          # 8 tests for quality report formatting
│   │   └── test_auth.py               # 13 tests for JWT verification edge cases
│   ├── .env.example                   # Required + optional env vars (mirror Settings class)
│   └── requirements.txt
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

# Optional with defaults
ADMIN_EMAILS=                                            # CSV; consumed by ORPHEUS-31 admin stopgap
FRONTEND_ORIGINS=http://localhost:5173                   # CSV; CORS allowlist
SUPABASE_JWT_AUDIENCE=authenticated                      # JWT aud claim

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

### Backend Conventions

- Use `async/await` throughout — FastAPI and Supabase client are both async
- All env reads flow through `backend.config.get_settings()` (Pydantic `BaseSettings`). The app fails fast at boot when required vars are missing. Worker process still has its own three `os.environ` reads — consolidating is a small follow-up.
- API routes live in `/backend/routers/` — one file per resource. Client-facing routes depend on `get_current_client` (in `backend/auth.py`), which JWT-verifies the Bearer token against the cached Supabase JWKS, fetches the matching `public.clients` row, and returns a typed `CurrentClient(user_id, client_id, email, access_token)`.
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
- Authenticated routes live under a `ProtectedRoute` wrapper in `App.tsx`. `/login` is the only public route in the portal. The `/design/signal-meter` playground is dev-only and bypasses auth and the layout shell.
- API calls go through `frontend/src/lib/apiClient.ts`, which attaches `Authorization: Bearer <session.access_token>` to every outgoing request automatically.
- Design tokens come from the shared `orpheus-styles.css` (same file the prototype uses). Per-page styles sit in a sibling `*.css` next to the page component.
- MSW handlers are intentionally empty (the real backend serves all client-facing routes). Bring back the demo-job handler in `mocks/handlers.ts` only when iterating on UI offline.

---

## Plane Documentation Conventions

Plane is the source of truth for tasks and documentation. Do not maintain a duplicate task list in this file.

Work items are referenced as `ORPHEUS-[n]` (e.g. `ORPHEUS-12`). Use these identifiers in commit messages and PRs to link work to Plane issues.

**Page naming format:** `Category: Title (YYYY-MM-DD)`
Example: `Decision: Auth Strategy (2026-03-18)`

**Page categories:**
- `Decision` — why X was chosen over Y (tech, product, design)
- `Spec` — feature or component requirements and scope
- `Architecture` — system design, infrastructure, data models
- `Meeting` — discussion summaries and action items

**Publishing workflow:**
1. Claude drafts page content in the conversation
2. Josh reviews and approves (or requests edits)
3. Claude publishes to the Orpheus project in Plane

All pages are published to the **Orpheus project** (project-level, not workspace-level).

---

## Deferred / Pending

See the Orpheus project in Plane for the current task list. Plane is the source of truth — do not maintain a parallel list here.
