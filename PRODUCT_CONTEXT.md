# Orpheus Social — Product Context

> **How to use this file:**
> Paste this file at the start of any AI session (Claude or ChatGPT) to load current project context. It is updated after each working session and lives in the repository at `PRODUCT_CONTEXT.md`.
> At the end of your session, ask your AI to structure any decisions or feedback using the format in the "Contributing" section, then send to Josh to be incorporated.

---

## Project Summary

Orpheus Social is a client portal and diagnostic tool for Andrew Segars' Strategic Digital Presence Advisory practice. It guides senior executive clients through a structured data-gathering phase ("Groundwork"), then delivers a **Signal Score** diagnostic and **Forward Brief** action plan.

The Signal Score measures LinkedIn presence health across multiple dimensions using a combination of quantitative data (LinkedIn ZIP archive + Analytics XLSX) and qualitative rubric scoring. Scoring is fully deterministic — no AI is involved in score computation. Claude only generates narratives and Forward Brief copy after scores are calculated.

**Design principles:**
- Reliability over completeness — only score what can be consistently captured and explained
- Observable over inferred — use platform data where possible, rubric scoring only for explicit signals
- Separation of concerns — Score = measurement. Advisory = interpretation. Do not mix them.
- This score measures **presence health**, not strategic excellence

---

## Current Schema State

### Dimensions

| # | Dimension | Layer | Question | Weight |
|---|---|---|---|---|
| 1 | Presence | Foundation | Is the profile structurally complete and interpretable? | TBD |
| 2 | Reach | Distribution | How large is the addressable audience? | TBD |
| 3 | Resonance | Performance | Does content generate engagement? | TBD |
| 4 | Consistency | Behavior | Is activity sustained and predictable? | TBD |
| 5 | Authority | Audience Quality | Is the audience relevant and appropriately senior? | TBD |
| 6 | Narrative & Conversion | Signal Alignment | Do profile signals and content signals align with a clear path to action? | TBD |

**Note:** Weights are not yet finalized for the 6-dimension model. Prior 5-dimension weights were: Presence 20, Reach 20, Resonance 25, Consistency 20, Authority 15.

---

### Presence Indicators

| Indicator | Source | Scoring |
|---|---|---|
| Profile photo | Rich_Media.csv | Recency-based (see below) |
| Banner image | Rich_Media.csv | Recency-based (see below) |
| Headline clarity | Profile.csv | Rubric 1–5 (definitions TBD) |
| About clarity | Profile.csv | Rubric 1–5 (definitions TBD) |
| Experience depth | Positions.csv | Role count, threshold logic |
| Experience structure | Positions.csv | % of roles with descriptions |
| Featured usage | **TBD** | Present / absent |
| Recent activity | Shares.csv | Post within last 30 days |
| Top skills | Skills.csv | Count, threshold logic |

**Photo/Banner recency scoring (decided):**
- Upload found, within 2 years → strength
- Upload found, 2–4 years → watch
- Upload found, 4+ years → gap
- No upload found → gap (photo absent or predates tracking)

### Reach Indicators
- Total followers
- Connections
- New followers/week (rolling average)
- Unique members reached (from DISCOVERY sheet)

### Resonance Indicators
- Engagement rate (total engagements / total impressions)
- Avg engagements per post
- Top post impressions
- Impression trend (second half vs. first half of period)

### Consistency Indicators
- Posts per week (average)
- Active weeks (% of weeks with at least one post)
- Longest gap (consecutive weeks without posting)
- Weeks above median

### Authority Indicators
- Role seniority (standardized mapping from current title)
- Senior+ audience (% of followers with senior titles)
- Target industry alignment (% in client-defined industries)
- Primary geography (% in client's primary market)
- Top follower organizations (top 3 by representation)

**Note:** Authority currently has 5 indicators. Decision pending on whether to standardize at 4 per dimension.

### Narrative & Conversion Indicators
- Identity clarity — rubric score (definitions TBD)
- Profile-content alignment — rubric score (definitions TBD)
- Conversion signal — present/absent (services enabled OR explicit contact language)

---

## Data Sources

Clients submit two files:

| File | Format | Used For |
|---|---|---|
| LinkedIn Complete archive | ZIP (or unzipped folder) | Presence, Consistency, profile data |
| LinkedIn Analytics export | XLSX (5 sheets) | Reach, Resonance, Authority |

**Critical:** Clients must download the **Complete** archive, not the Basic archive. The Basic export omits `Shares.csv`, which is required for Consistency scoring.

**ZIP → Score mapping:**
- Presence → Profile.csv, Positions.csv, Skills.csv, Rich_Media.csv, Shares.csv
- Consistency → Shares.csv
- Narrative & Conversion → Profile.csv (partial; Featured/Services TBD)

**XLSX → Score mapping:**
- Reach → DISCOVERY sheet, FOLLOWERS sheet
- Resonance → ENGAGEMENT sheet, TOP POSTS sheet
- Authority → DEMOGRAPHICS sheet

---

## Reporting Window

| Window | Length | Purpose |
|---|---|---|
| Primary scoring | 90 days (most recent) | All performance metrics |
| Comparison | Prior 90 days | Trajectory / trend validation |
| Contextual | Full 365 days | Historical context only — does not impact score |

---

## Open Questions

*These require alignment before the scoring engine can be built.*

1. **Featured section data source** — Not present in the LinkedIn ZIP export. Options: (a) manual advisor audit, (b) client questionnaire self-report, (c) drop from schema.

2. **Conversion signal data source** — "Services enabled" is a LinkedIn profile feature not captured in the ZIP. Contact/offering language *can* be parsed from About text. Decision needed: parse About text alone, or require an additional input?

3. **Rubric definitions** — Headline clarity, About clarity, Identity clarity, and Profile-content alignment require fixed 1–5 scoring rubrics. Definitions must be written before the scoring engine is built.

4. **6th dimension weighting** — Adding Narrative & Conversion requires redistributing 100 points across 6 dimensions. Proposed weights needed from Andrew.

5. **Authority indicator count** — 5 indicators currently vs. 4 for other dimensions. Standardize at 4, or allow variable count?

---

## Key Decisions Made

- **Deterministic scoring** — Score computation is pure Python, no AI. Claude handles narratives only.
- **90-day primary window** — Scores reflect the last 90 days, not full year.
- **Photo/banner recency scoring** — Rich_Media.csv upload history used; absence treated as gap.
- **Complete archive required** — Basic LinkedIn export is insufficient; Shares.csv is missing.
- **Qualitative scoring is constrained** — Rubric fields use explicit text only, no inference, fixed 1–5 definitions.
- **6 dimensions** — Narrative & Conversion added as 6th dimension (pending weight finalization).
- **Excluded from scoring** — Endorsements, Recommendations (as a metric), Articles, certifications, summary length, writing quality.

---

## Tech Stack (reference)

| Layer | Technology |
|---|---|
| Frontend | React → Vercel |
| Backend | FastAPI (Python) → Railway |
| Database | Supabase (PostgreSQL) |
| AI | Anthropic API — Claude (narrative generation only) |
| Project management | Plane (orpheussocial workspace) |

---

## Contributing to This File

At the end of a working session, ask your AI to structure any outputs using this format, then send to Josh:

**Decision made:**
> [Title] — [What was decided and why, in one or two sentences]

**Open question resolved:**
> [Question] — [Resolution]

**New open question:**
> [Question] — [Context and options considered]

Josh's AI will incorporate updates, commit to the repository, and sync to Plane.
