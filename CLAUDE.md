# Orpheus Social — Project Context

Orpheus Social is a client portal and diagnostic tool for **Andrew Segars'
Strategic Digital Presence Advisory** practice. It guides senior executive
clients through a structured data-gathering phase ("Groundwork"), then
delivers a **Signal Score** diagnostic and **Forward Brief** action plan.

**Current state:** Fully functional prototype — pure HTML/CSS, no JavaScript, no framework, hosted locally via VS Code Live Server. All 14 portal screens complete.

**Next phase:** Transitioning to a hosted production stack with a Python backend, database, and React frontend. See "Planned Production Stack" section below.

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
--warm-gold:      #C4902A   (accent, active states, highlights)
--warm-ivory:     #F9F6F0   (page background)
--warm-parchment: #EDE9E1   (card/input backgrounds)
--warm-text:      #271D10   (body text)
--warm-stone:     #7A6A56   (secondary text, placeholders)
--warm-border:    #DDD5C8   (borders, dividers)
```

### Border Radius
10px throughout — no exceptions.

### Input Interaction Pattern
`:has(input:checked)` CSS selector for radio/checkbox selected states.
No JavaScript for any UI behavior.

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
   "Download larger data archive". Contains CSVs: Profile, Positions, Education,
   Skills, Connections, Recommendations, Endorsements, Shares, Inferences_about_you, etc.
   No analytics data in ZIP.

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

- No JavaScript — all interaction via CSS `:has()` selector
- No PDF export step (redundant with ZIP)
- Data retention: delete after AI processing; Signal Score is the durable record
- Confidentiality / AI data handling policy: deferred, to be discussed with Andrew
- Screenshot assets for LinkedIn instruction pages: deferred
- "My Groundwork is Complete" button stays disabled (`opacity: 0.35`) until
  completion logic is implemented (requires JS or backend)
- Client name "Jane Doe" is the placeholder throughout — will be personalized per client

---

## Signal Score Framework

5 dimensions, weighted to 100-point total:

| Dimension | Weight | What It Measures |
|---|---|---|
| Presence | 20 | Profile depth & credibility (skills, endorsements, recs, summary, honors) |
| Reach | 20 | Audience size & growth (followers, connections, new follower rate) |
| Resonance | 25 | Content engagement quality (rate, avg per post, top post, trend) |
| Consistency | 20 | Content volume & cadence (posts/week, active weeks, variance) |
| Authority | 15 | Audience composition (seniority %, industry alignment, geography) |

Placeholder scores used in current prototype: Presence 7.2, Reach 4.8, Resonance 6.1, Consistency 5.3, Authority 8.4 → Total 64.7 ("Moderate Signal Strength")

Andrew Segars test scores (from actual data, 2025-03-17 to 2026-03-16): Presence 9.5, Reach 10.0, Resonance 9.0, Consistency 8.5, Authority 10.0 → Total 93.4

---

## Sub-Metric Schema (Signal Score Indicators)

Each dimension exposes 4 fixed indicators on every report — same metrics every cycle to support longitudinal comparison. Status is derived from thresholds: strength (filled gold dot), watch (gray dot), gap (hollow dot).

Thresholds will evolve as the practice calibrates against real client data.

| Dimension | Indicator | Strength | Gap |
|---|---|---|---|
| Presence | Summary | 1,000+ chars | < 500 chars |
| Presence | Skills & Endorsements | 40+ skills | < 25 skills |
| Presence | Recommendations received | 5+ | < 3 |
| Presence | Articles published | 3+ | 0 |
| Reach | Total followers | 2,500+ | < 1,000 |
| Reach | Connections | 2,000+ | < 500 |
| Reach | New followers / week | 10+ avg | < 5 avg |
| Reach | Unique members reached | 50,000+ / yr | < 20,000 / yr |
| Resonance | Engagement rate | 3%+ | < 1% |
| Resonance | Avg engagements / post | 30+ | < 15 |
| Resonance | Top post impressions | 10,000+ | < 5,000 |
| Resonance | Impression trend | +10% vs prior period | < −10% |
| Consistency | Posts per week | 3+ avg | < 1 avg |
| Consistency | Active weeks | 90%+ of period | < 75% |
| Consistency | Longest gap | ≤ 1 week | > 3 weeks |
| Consistency | Weeks above median | 60%+ | < 40% |
| Authority | Senior+ audience | 50%+ | < 30% |
| Authority | Target industry alignment | 30%+ | < 15% |
| Authority | Primary geography | 20%+ in target market | < 10% |
| Authority | Top follower organizations | Named alignment with target sector | — |

Authority indicators 3 and 4 are client-specific — "target industries" and "primary geography" are defined by questionnaire answers (Target Audiences section), not derived from LinkedIn data alone.

---

## Planned Production Stack

The prototype is pure HTML/CSS/Python running locally. Production adds a backend, database, and hosted frontend.

### Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React | Dynamic client portal, score display, review delivery |
| Backend | FastAPI (Python) | Async; Claude SDK support; scoring scripts already in Python |
| Database | Supabase (PostgreSQL) | Auth, job queue, result storage; free tier for beta |
| AI | Anthropic API — Claude | Narrative generation and Forward Brief synthesis only |
| Hosting — frontend | Vercel | Free tier |
| Hosting — backend | Railway or Render | Free tier / ~$5/mo |
| CI/CD | GitHub Actions | Existing repo |

### Project Structure

```
/
├── CLAUDE.md
├── frontend/              # React app
│   └── src/
├── backend/               # FastAPI app
│   ├── main.py
│   ├── agents/            # Claude calls — narrative generation, Forward Brief
│   ├── scoring/           # Deterministic Signal Score computation (5 dimensions)
│   ├── ingestion/         # LinkedIn ZIP + XLSX parsing
│   ├── workers/           # Background job processor
│   └── models/            # Pydantic data models
└── .github/
    └── workflows/         # GitHub Actions CI/CD
```

### Analysis Pipeline

The analysis has three distinct stages — only the third involves Claude:

1. **Ingestion** — Parse LinkedIn ZIP (CSVs) and Analytics XLSX into structured data. Pure Python, deterministic. Proof-of-concept scripts already exist from prototype work.

2. **Scoring** — Compute 5-dimension Signal Score using weighted thresholds. Pure Python, deterministic. Output: dimension scores (1–10), sub-metric values, and status flags (strength / watch / gap) for each of the 20 indicators.

3. **Narrative generation** — Claude receives scored data + questionnaire answers and generates: dimension narratives, score interpretation, and Forward Brief priorities. This is the only AI step. Structured output, one agent call.

Keeping scoring deterministic and separate from the AI call makes scores auditable, reproducible, and comparable across reporting cycles without re-running Claude.

### Job Queue Pattern

Ingestion + scoring + Claude call takes 20–60 seconds — too long for a synchronous web request. The job queue pattern decouples submission from processing:

1. Client submits LinkedIn data → FastAPI creates a `pending` job in Supabase → returns `job_id` immediately
2. Client sees the Analysis in Progress screen (already built)
3. Background worker claims the job, runs the full pipeline, saves results
4. Frontend polls `/jobs/{job_id}` every few seconds → updates UI on completion

**Job states:** `pending → running → complete` (failed jobs retry up to 3×, then surface an error)

**Queue implementation for beta:** Supabase `jobs` table using `SELECT ... FOR UPDATE SKIP LOCKED` to prevent duplicate claims if workers scale.

### Environment Variables

```
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
```

Never committed. Document required keys in `.env.example`.

### Backend Conventions

- Use `async/await` throughout — FastAPI and Supabase client are both async
- Ingestion logic lives in `/backend/ingestion/` — one file per source (zip_parser.py, xlsx_parser.py)
- Scoring logic lives in `/backend/scoring/` — separate from agent calls, no Claude dependency
- All Claude calls live in `/backend/agents/` — one file per agent
- Job queue state managed via `jobs` table in Supabase
- Pydantic models in `/backend/models/` define the data contracts between pipeline stages

---

## Deferred / Pending

- Screenshot assets for LinkedIn step pages (3 in step1, 3 in step2)
- Confidentiality policy and AI data handling disclosure
- Backend / form submission (currently all front-end static)
- "My Groundwork is Complete" button disabled state (currently always active — requires JS or backend to enable only when all items checked)
- PDF export of Forward Brief
- Per-client personalization (name, scores, priorities) — currently all static placeholders
