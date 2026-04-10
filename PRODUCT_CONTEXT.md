# Orpheus Social — Product Context

> **How to use this file:**
> Paste this file at the start of any AI session (Claude or ChatGPT) to load current project context. It is updated after each working session and lives in the repository at `PRODUCT_CONTEXT.md`.
> At the end of your session, ask your AI to structure any decisions or feedback using the format in the "Contributing" section, then send to Josh to be incorporated.

---

## Project Summary

Orpheus Social is a client portal and diagnostic tool that measures LinkedIn presence health and delivers actionable insights. It supports two use cases:

1. **Advisory (white-glove)** — An advisor manages clients as a white-labeled service. The system generates scores and narratives; the advisor reviews and edits narratives before publishing to the client. Multiple advisors supported from day one.

2. **Individual (self-serve)** — A person signs up, uploads their own LinkedIn data, and receives the Signal Score + Forward Brief automatically. No human review gate.

Both use cases share the same scoring engine and Signal Score framework. **One scoring engine, no stream distinction.** There is no client-type flag, no stream identifier, and no conditional scoring logic. The same dimensions, formulas, rubrics, and band labels apply to every client. All differences between advisory and automated streams live in the report output and delivery layer — not in the scoring engine.

**Design principles:**
- Reliability over completeness — only score what can be consistently captured and explained
- Observable over inferred — use platform data where possible, rubric scoring only for explicit signals
- Separation of concerns — Score = measurement. Advisory = interpretation. Do not mix them.
- This score measures **presence health**, not strategic excellence
- Every scoring element carries a confidence label: CONFIRMED, INFERRED, PROXY, or PROVISIONAL

**Fundamental reframe (v2, April 2026):** The Signal Score measures whether a member's profile and behavior provide the kinds of signals LinkedIn's confirmed retrieval and ranking systems are documented to use. It does not measure outcomes. Two confirmed inputs drive everything: profile language (what the retrieval system reads to build the member embedding) and behavioral history (what the ranking system reads to understand trajectory and predict future engagement).

---

## Current Schema State (v2)

### Dimensions

| # | Dimension | Weight | Confidence | What It Measures |
|---|---|---|---|---|
| 1 | Profile Signal Clarity | 35% | CONFIRMED | Does the profile give the retrieval system clear language to build an accurate member embedding? |
| 2 | Behavioral Signal Strength | 30% | CONFIRMED | Has the member built sufficient, recent, coherent engagement history for the ranking model? |
| 3 | Behavioral Signal Quality | 20% | CONFIRMED/INFERRED | Is the member generating the action types the optimization targets reward? |
| 4 | Profile-Behavior Alignment | 15% | CONFIRMED/INFERRED | Is content topically and semantically consistent with the declared professional identity? |

**Weights confirmed [Andrew, 2026-04-08].** Labeled INFERRED and PROVISIONAL — well-grounded in cold-start literature across three papers but LinkedIn does not publish dimension weights. Must be adjustable configuration parameters, not hardcoded constants. Recalibration expected at 50–100 profiles.

**What moved to Forward Brief (not scored):** Reach (followers, connections, members reached), Resonance (impressions, engagement rates on received content), Authority (audience seniority, industry, geography), Engagement Invitation / CTA, viewer-actor affinity, and visual professionalism. These are computed and displayed as advisory context but do not contribute to the composite score. Rationale: these are outputs of the system, not inputs — they measure what happened, not whether the member provides signals the system is documented to use.

---

### Sub-dimension Summary

**Dimension 1 — Profile Signal Clarity (35%):** 5 sub-dimensions, scale 1–5, qualitative rubric scoring applied by Claude. Equal weighting within dimension.
- Headline Clarity — rubric complete
- About Section Coherence — rubric complete
- Experience Description Quality — rubric complete
- Profile Completeness — structural check (completeness floor: if headline, About, industry, or job history are missing, Dimension 1 capped at 50% of max)
- Identity Clarity — rubric complete

**Dimension 2 — Behavioral Signal Strength (30%):** 4 sub-dimensions, scale 0–5, quantitative bands computed from archive data. All band boundaries PROVISIONAL — recalibration at 50–100 profiles.
- History Depth — total outbound actions (comments + reactions + shares + reposts), trailing 12 months. PROXY measure. Bands: 0(<10), 1(10–29), 2(30–99), 3(100–299), 4(300–599), 5(600+). The <10 threshold is a confirmed Feed SR sparse disadvantage anchor.
- Recency — outbound actions in trailing 60 days. Hybrid absolute + proportional floor at bands 3+. PROXY measure. Bands: 0(<5), 1(5–14), 2(15–39), 3(40–99 AND ≥15% of 12mo), 4(100–199 AND ≥20% of 12mo), 5(200+ AND ≥20% of 12mo).
- Continuity — active weeks (3+ posts/comments = active) out of trailing 52 weeks. Posts + comments only, not reactions. Bands: 0(<5), 1(5–12), 2(13–25), 3(26–37), 4(38–46), 5(47–52).
- Posting Presence — average posts/week over 52 weeks. Posts only. Consistency ceiling: if <50% of weeks have a post, capped at score 3. Bands: 0(none), 1(<0.25/wk), 2(0.25–0.49), 3(0.5–0.99), 4(1.0–1.99, confirmed 1/wk benchmark), 5(2.0+).

**Dimension 3 — Behavioral Signal Quality (20%):** 2 sub-dimensions, scale 0–5, quantitative. Viewer-actor affinity confirmed as real signal but not scored — moved to Forward Brief.
- Outbound Engagement Presence — combined comments + reactions, trailing 12 months. Bands: 0(<10), 1(10–49), 2(50–149), 3(150–499), 4(500–999), 5(1,000+).
- Engagement Quality Score — formula: substantive comments + (reactions × 0.25). Substantive = 20 words or 100 characters. The 4:1 weighting is INFERRED and PROVISIONAL. Bands: 0(0–4), 1(5–24), 2(25–74), 3(75–199), 4(200–399), 5(400+).

**Dimension 4 — Profile-Behavior Alignment (15%):** 2 sub-dimensions, scale 1–5, qualitative rubric scoring applied by Claude. Full rubric criteria written (5 score points each, observable-over-inferred, rare-5 rule).
- Topic Consistency — do posts and comments cohere into a recognizable professional identity? Multiple topics allowed if semantically connected.
- Profile-Content Coherence — does content reinforce the professional identity the profile declares? Requires reading both profile fields and content together.

---

### Scoring Formula

**Sub-dimension combination within a dimension:** `(sum of scores − minimum possible) / (maximum possible − minimum possible) × dimension weight = dimension contribution`

Dimensions 1 and 4 use a 1–5 scale (minimum = number of sub-dimensions). Dimensions 2 and 3 use a 0–5 scale (minimum = 0, formula simplifies to sum / max × weight). Equal weighting within each dimension.

**Composite score:** Sum of all four dimension contributions. Range: 0–100.

**Completeness floor (Dimension 1 only):** If any of headline, About, industry, or job history are missing, Dimension 1 contribution is capped at 50% of its maximum (17.5).

**Signal strength bands** (client-facing output):

| Band | Score Range |
|---|---|
| Weak | 0–24 |
| Emerging | 25–44 |
| Moderate | 45–64 |
| Strong | 65–79 |
| Exceptional | 80–100 |

Bands are unequal by design — narrower at extremes. Numeric scores visible to advisors only; clients see bands. Band breakpoints are PROVISIONAL — recalibration at 50–100 profiles.

**Pressure-test result:** Andrew Segars scores 77.6/100 → Strong band. Dim 1: 22.75%, Dim 2: 25.50%, Dim 3: 20.00%, Dim 4: 9.38%.

---

## Confidence Labels

Every scoring element carries one or more labels. Defined in the Transparency and Proxy Disclosure document.

| Label | Meaning | External Use |
|---|---|---|
| CONFIRMED | Direct evidence from primary-source LinkedIn engineering publications | Can cite directly |
| INFERRED | Strong synthesis across credible sources; logical extension of confirmed findings | Describe as "evidence-based interpretation" |
| PROXY | Underlying signal confirmed; measurement indirect from available data | Note the gap honestly |
| PROVISIONAL | Directionally grounded; requires calibration against real population data | Present as "calibrated estimate" |

All PROVISIONAL elements must be adjustable configuration parameters. Recalibration checkpoint: 50–100 profiles.

---

## Data Sources

Clients submit two files:

| File | Format | Used For |
|---|---|---|
| LinkedIn Complete archive | ZIP (or unzipped folder) | All 4 scored dimensions + Forward Brief |
| LinkedIn Analytics export | XLSX (5 sheets) | Forward Brief only (Reach, Resonance, Authority) |

**Critical:** Clients must download the **Complete** archive, not the Basic archive. The Basic export omits `Shares.csv`, which is required for behavioral scoring.

**ZIP → Scored Dimensions:**
- Dimension 1 (Profile Signal Clarity) → Profile.csv, Positions.csv, Education.csv, Skills.csv, Languages.csv
- Dimension 2 (Behavioral Signal Strength) → Shares.csv, Comments.csv, Reactions.csv
- Dimension 3 (Behavioral Signal Quality) → Comments.csv, Reactions.csv
- Dimension 4 (Profile-Behavior Alignment) → Profile.csv (About section), Shares.csv (post content)

**ZIP → Forward Brief:**
- Comment depth analysis → Comments.csv
- Posting gap distribution → Shares.csv
- Viewer-actor affinity patterns → Comments.csv, Reactions.csv (URL patterns)
- Visual professionalism → Rich_Media.csv (photo present/absent)

**XLSX → Forward Brief:**
- Reach → DISCOVERY sheet, FOLLOWERS sheet
- Resonance → ENGAGEMENT sheet, TOP POSTS sheet
- Authority → DEMOGRAPHICS sheet

---

## Reporting Window

| Window | Length | Purpose |
|---|---|---|
| History depth | Trailing 12 months | Matches Feed SR one-year history window |
| Recency | Trailing 60 days | Matches Feed SR ~2-month half-life |
| Continuity / Posting | Trailing 52 weeks | Active week and posting frequency metrics |
| Forward Brief analytics | Per XLSX export period | Typically 365 days |

---

## Pipeline Architecture

### Two Output Pipelines

The scoring stage produces two structured outputs that feed narrative generation together:

1. **Scored dimensions output** — four dimension scores, sub-dimension scores, composite score, band label. Deterministic computation.

2. **Forward Brief structured data output** — computed values for Reach, Resonance, Authority, plus qualitative flags. Structured, reproducible output — not impressionistic narrative.

Both are computed in the **scoring stage** (single stage, not separate). Claude receives both as structured inputs and generates the full report.

### Forward Brief Data Contract

**Quantitative computed fields (from XLSX):**
- Follower count and growth rate (new followers/week)
- Unique members reached (trailing period)
- Average impressions per post
- Average engagement rate on received content
- Top post performance (impressions, engagement)
- Audience seniority distribution
- Audience industry distribution (top 3–5)
- Audience geography (top countries/regions)
- Top represented organizations

**Quantitative computed fields (from ZIP):**
- Average comment length (chars/words) — comment depth observation
- Posting gap distribution (longest gap, % zero-post weeks) — consistency beyond Continuity score

**Qualitative flags (pre-processed into structured fields):**
- Viewer-actor affinity: `concentrated_engagement: bool` + `top_targets: list` — from URL patterns in Comments.csv/Reactions.csv
- Visual professionalism: `photo_present: bool` — from Rich_Media.csv
- Engagement invitation: `services_present: bool`, `contact_visible: bool`, `cta_in_about: bool` — from Profile.csv

### Scoring Stage Output Shape

```json
{
  "scored_dimensions": {
    "composite": 77.6,
    "band": "Strong",
    "dimensions": [
      {
        "name": "Profile Signal Clarity",
        "weight": 0.35,
        "confidence": "CONFIRMED",
        "normalized_score": 0.650,
        "contribution": 22.75,
        "completeness_floor_applied": false,
        "sub_dimensions": [
          {"name": "Headline Clarity", "score": 3, "scale": "1-5", "method": "rubric"},
          {"name": "About Section Coherence", "score": 4, "scale": "1-5", "method": "rubric"}
        ]
      }
    ]
  },
  "forward_brief_data": {
    "quantitative": {
      "follower_count": 12500,
      "follower_growth_rate": 45.2,
      "unique_members_reached": 285000,
      "avg_impressions_per_post": 3200,
      "avg_engagement_rate": 0.042,
      "top_post_impressions": 28500,
      "audience_seniority": {"Senior": 0.32, "Manager": 0.28, "Director": 0.15},
      "audience_industries": [{"name": "Technology", "pct": 0.35}],
      "audience_geography": [{"name": "United States", "pct": 0.45}],
      "avg_comment_length_words": 26.3,
      "longest_posting_gap_weeks": 2,
      "zero_post_week_pct": 0.29
    },
    "qualitative_flags": {
      "viewer_actor_affinity": {"concentrated": true, "top_targets": ["url1", "url2"]},
      "visual_professionalism": {"photo_present": true},
      "engagement_invitation": {"services_present": false, "contact_visible": true, "cta_in_about": true}
    }
  }
}
```

---

## Open Questions

*Remaining items before or during build.*

1. **DISCOVERY sheet is summary-only** — LinkedIn's analytics XLSX provides only period totals (impressions, members reached) on the DISCOVERY sheet, not daily breakdowns. The Forward Brief field "Unique members reached" must come from the DISCOVERY summary. [Josh, 2026-03-23]

2. **DEMOGRAPHICS categories differ from schema assumptions** — LinkedIn provides "Job titles," "Locations," and "Industries." Audience seniority for Forward Brief must be derived from job title analysis. No company/organization data in the analytics export. [Josh, 2026-03-23]

3. **FOLLOWERS sheet has no cumulative total per day** — Only a summary total in row 0 and daily "New followers" rows. Cumulative count must be computed backwards from the total. [Josh, 2026-03-23]

4. **Inter-rater consistency testing** — Dimensions 1 and 4 use Claude-applied rubrics. Must run sample profiles through rubrics twice under identical prompting and compare outputs before launch. [Andrew, 2026-04-08]

5. **Recalibration checkpoint** — All PROVISIONAL band boundaries and dimension weights flagged for review at 50–100 profiles. Must be adjustable configuration parameters in the build. [Andrew, 2026-04-08]

---

## Key Decisions Made

### Architecture & Scoring (v2, April 2026)
- **4-dimension architecture** — Replaced 6-dimension model. Dimensions grounded in confirmed LinkedIn retrieval and ranking system inputs, not outcomes. Reach, Resonance, Authority move to Forward Brief. [Andrew, 2026-04-08]
- **One scoring engine, no stream distinction** — Identical engine for advisory and self-serve. No client-type flag or conditional logic. All differences live in report output and delivery layer. [Andrew, 2026-04-08]
- **Dimension weights: 35/30/20/15** — INFERRED and PROVISIONAL. Adjustable config, not hardcoded. Cold-start finding across three papers grounds the profile-heavy weighting. [Andrew, 2026-04-08]
- **Signal strength bands** — Client-facing output is band label (Weak/Emerging/Moderate/Strong/Exceptional), not raw number. Numeric scores visible to advisors only. [Andrew + Josh, 2026-04-01]
- **Band breakpoints: 0–24, 25–44, 45–64, 65–79, 80–100** — Unequal by design. PROVISIONAL. [Andrew, 2026-04-08]
- **Sub-dimension combination formula** — `(sum − min) / (max − min) × weight`. Equal weighting within dimensions. Pressure-tested against real data (77.6 → Strong). [Andrew, 2026-04-08]
- **Completeness floor on Dimension 1** — Missing headline, About, industry, or job history caps Dim 1 at 50%. Structural check, not a scored sub-dimension. [Andrew, 2026-04-08]
- **Confidence labeling** — Every scoring element labeled CONFIRMED, INFERRED, PROXY, or PROVISIONAL. Labels carry through to client-facing transparency disclosures. [Andrew, 2026-04-08]

### Dimension-Specific (v2)
- **Dimension 2: all bands confirmed** — History Depth, Recency (hybrid absolute + proportional floor), Continuity (3+ posts/comments = active week), Posting Presence (1/wk benchmark, 50% consistency ceiling). All bands PROVISIONAL. [Andrew, 2026-04-08]
- **Dimension 3: quantitative, not rubric** — Outbound Engagement Presence (comments + reactions) and Engagement Quality Score (substantive comments + reactions × 0.25). 20-word/100-char substantive threshold. 4:1 weighting INFERRED and PROVISIONAL. [Andrew, 2026-04-08]
- **Dimension 4: rubrics complete** — Topic Consistency and Profile-Content Coherence, full 1–5 criteria with written definitions for each score point. Rare-5 rule, observable-over-inferred. [Andrew, 2026-04-08]
- **v1 Recent Activity Strength not carried over** — Replaced by Recency and Posting Presence sub-dimensions. Trend modifier dropped (not grounded in primary source). [Andrew, 2026-04-08]
- **Visual Professionalism dropped from scoring** — No primary source names photo/banner as retrieval or ranking input. Forward Brief note only. [Andrew, 2026-04-08]
- **Viewer-actor affinity: Forward Brief only** — Confirmed signal (0.3% Long Dwell AUC) but not measurable from archive. Unscored advisory context. [Andrew, 2026-04-08]
- **Engagement Invitation: Forward Brief only** — Not scored. Qualitative flag for services, contact visibility, CTA in About. [Andrew, 2026-04-08]

### Pipeline & Data (v2)
- **Forward Brief computed in scoring stage** — Single computation stage produces both scored dimensions and Forward Brief structured data. No separate pre-processing stage. [Josh, 2026-04-08]
- **Qualitative flags pre-processed** — Viewer-actor affinity, visual professionalism, and engagement invitation are structured fields (booleans/categoricals), not raw data for Claude. Ensures reproducibility. [Josh, 2026-04-08]
- **History depth proxy** — Total outbound actions (comments + reactions + shares + reposts), trailing 12 months. Conservative undercount by design — misses long dwell events. PROXY label. [Andrew, 2026-04-08]
- **Scores table gains forward_brief_data column** — JSONB column alongside existing dimensions JSONB. One row per job, two output sections. [Josh, 2026-04-08]

### Carried from v1
- **Deterministic scoring** — Score computation is pure Python, no AI. Claude handles rubric application (Dim 1, Dim 4) and narrative generation only.
- **Complete archive required** — Basic LinkedIn export is insufficient; Shares.csv is missing.
- **Two use cases, unified model** — Advisory and individual share the same data model. An individual is an advisor with one client (themselves). [Josh, 2026-03-23]
- **Multi-advisor from day one** — Multiple advisors at launch, not just Andrew. [Josh, 2026-03-23]
- **White-labeling = branding + narrative editing** — Scoring framework is fixed and shared, not configurable per advisor. [Josh, 2026-03-23]
- **client_id anchors all analysis data** — Enables advisory→self-serve migration. [Josh, 2026-03-23]
- **Pipeline config snapshot on jobs** — JSONB config_snapshot for reproducibility. [Josh, 2026-03-23]
- **Client login included in initial build** — Advisor invites client, scoped dashboard. [Josh, 2026-03-23]
- **5 Dimension 1 rubrics complete** — Headline Clarity, About Clarity, Experience Section Clarity, Identity Clarity, Profile-Content Alignment. All 1–5 scale. [Andrew, 2026-03-30]

---

## Platform Intelligence

Confirmed findings from first-party LinkedIn engineering sources. These ground the scoring rationale and Forward Brief recommendations. Full annotated bibliography maintained separately (April 2026).

**Tier 1 — Primary/Structural Sources:**
- Feed SR: An Industrial-Scale Sequential Recommender for LinkedIn Feed Ranking (Hertel et al., arXiv:2602.12354v1, February 2026)
- LinkedIn Engineering Blog: Engineering the Next Generation of LinkedIn's Feed (Danchev, March 12, 2026)
- How Does the LinkedIn Feed Work? (Jurka, August 11, 2025)
- Updates to the LinkedIn Feed (Jurka, March 12, 2026)
- Large Scale Retrieval for the LinkedIn Feed using Causal Language Models (arXiv:2510.14223, 2025)
- LinkedIn Post Embeddings (Ramanujam et al., arXiv:2405.11344, 2025)
- LiGNN: Graph Neural Networks at LinkedIn (Hou et al., arXiv:2402.11139, 2024)
- 360Brew: A Decoder-Only Foundation Model (arXiv:2501.16450, 2025 — recalled)

**Confirmed signals and implications:**
- Dwell time and substantive contributions (comments, shares) are the two primary optimization targets (Feed SR)
- Profile embeddings generated from profile data using a fine-tuned LLM, refreshed daily (Feed SR, Danchev)
- Retrieval system explicitly reads: headline, About, industry, skills, location, job history, education, certifications, languages (Retrieval paper)
- For members with <10 historical interactions, profile embeddings provide measurable performance improvement (Feed SR) — grounds cold-start advantage and Dim 1 weighting
- Exponential decay weighting on interaction history with ~2-month half-life (Feed SR)
- Viewer-to-actor affinity is a distinct ranked signal — removing it costs 0.3% Long Dwell AUC (Feed SR)
- LLM-based retrieval can deduce professional interests from headline and job title alone (Danchev) — cold-start advantage
- Content routed by topic relevance beyond immediate network, independent of network size (Jurka)
- 50-dimensional semantic post embeddings generated within minutes of creation, used in retrieval and ranking (Post Embeddings paper)
- Engagement pods and comment automation actively suppressed; authentic engagement rewarded (Jurka, March 2026)

**Note on 360Brew:** Referenced in early working model as directional only. The paper describes architecture and performance but not confirmed rollout timing. Confirmed production systems are the LLM-based dual-encoder retrieval system (Retrieval paper, Danchev) and the Feed SR sequential ranking model (Hertel et al.).

---

## Entity Model

Designed 2026-03-23. Applied to Supabase 2026-03-23 (migrations: `initial_schema`, `rls_policies`). RLS enabled with 26 policies across all tables. API routes, auth flow, and worker skeleton built 2026-03-23.

### Relationship Map

```
auth.users 1──1 advisors 1──∞ clients 1──1 questionnaire_responses
                                  │
                                  1──∞ jobs
                                        │
                                        ├── 1──1 ingested_data
                                        ├── 1──1 scores
                                        ├── 1──∞ narratives
                                        └── 1──1 reports
```

### Tables

**advisors** — One row per advisor (or self-serve individual). Linked 1:1 to auth.users.
- `id` (uuid PK), `user_id` (FK → auth.users, unique), `is_individual` (bool), `practice_name`, `logo_url`, `color_primary`, `color_accent`, `custom_domain`, `created_at`

**clients** — One row per subject being analyzed. Always belongs to an advisor. For self-serve, the advisor creates one client referencing themselves.
- `id` (uuid PK), `advisor_id` (FK → advisors), `user_id` (FK → auth.users, nullable), `display_name`, `email`, `invitation_status` (pending / accepted / expired), `status` (active / inactive / migrated), `created_at`

**questionnaire_responses** — Questionnaire answers stored as JSONB. One row per client, updated incrementally.
- `id` (uuid PK), `client_id` (FK → clients, unique), `responses` (JSONB), `schema_version` (string), `completed_at` (nullable), `updated_at`

**jobs** — One row per analysis pipeline run. Carries the config snapshot for reproducibility.
- `id` (uuid PK), `client_id` (FK → clients), `status` (pending / running / complete / failed), `version_label` (string, nullable), `config_snapshot` (JSONB), `attempt_count`, `error_message` (nullable), `created_at`, `started_at`, `completed_at`

**ingested_data** — Parsed LinkedIn data as structured JSONB after ingestion.
- `id` (uuid PK), `job_id` (FK → jobs, unique), `zip_data` (JSONB), `xlsx_data` (JSONB), `ingested_at`

**scores** — Dimension scores, Forward Brief data, and composite. One row per job.
- `id` (uuid PK), `job_id` (FK → jobs, unique), `total_score` (numeric), `band` (string — Weak/Emerging/Moderate/Strong/Exceptional), `dimensions` (JSONB), `forward_brief_data` (JSONB), `scored_at`

**narratives** — AI-generated text, one row per section per job. Supports draft→published workflow.
- `id` (uuid PK), `job_id` (FK → jobs), `section` (string — dimension name or "forward_brief"), `generated_text`, `edited_text` (nullable), `status` (draft / published), `published_at` (nullable), `generated_at`

**reports** — Published deliverable bundle. Snapshots branding at generation time.
- `id` (uuid PK), `job_id` (FK → jobs, unique), `client_id` (FK → clients), `report_type` (advisory / self_serve), `branding_snapshot` (JSONB), `published_at`

### Config Snapshot Shape (on jobs)

```json
{
  "version_label": "2026-Q2",
  "scoring": {
    "dimensions": [
      {
        "name": "Profile Signal Clarity",
        "weight": 0.35,
        "confidence": "CONFIRMED",
        "sub_dimensions": [
          {"name": "Headline Clarity", "scale": "1-5", "method": "rubric"},
          {"name": "About Section Coherence", "scale": "1-5", "method": "rubric"},
          {"name": "Experience Description Quality", "scale": "1-5", "method": "rubric"},
          {"name": "Profile Completeness", "scale": "1-5", "method": "rubric"},
          {"name": "Identity Clarity", "scale": "1-5", "method": "rubric"}
        ],
        "completeness_floor": {
          "required_fields": ["headline", "about", "industry", "job_history"],
          "cap_pct": 0.5
        }
      },
      {
        "name": "Behavioral Signal Strength",
        "weight": 0.30,
        "confidence": "CONFIRMED",
        "sub_dimensions": [
          {"name": "History Depth", "scale": "0-5", "method": "quantitative", "bands": [10, 30, 100, 300, 600]},
          {"name": "Recency", "scale": "0-5", "method": "quantitative_hybrid"},
          {"name": "Continuity", "scale": "0-5", "method": "quantitative", "bands": [5, 13, 26, 38, 47]},
          {"name": "Posting Presence", "scale": "0-5", "method": "quantitative", "consistency_ceiling": 0.5}
        ]
      }
    ],
    "bands": {"Weak": [0, 24], "Emerging": [25, 44], "Moderate": [45, 64], "Strong": [65, 79], "Exceptional": [80, 100]}
  },
  "questionnaire_schema_hash": "abc123",
  "narrative_prompt_version": "2.0"
}
```

### Design Notes

- **Unified model**: An individual (self-serve) user is an advisor with `is_individual: true` and one client record pointing back to themselves.
- **Advisory→self-serve migration**: Re-parent the client record. All history follows via client_id FKs.
- **Versioning**: Config snapshot is written once when a job starts and never mutated.
- **Narrative editing**: Advisory flow sets narratives to `draft` status; advisor edits `edited_text` and publishes. Self-serve auto-publishes with `edited_text` null.
- **RLS pattern**: Three roles — advisor, client, individual. All scoped via `user_id`.
- **AI in scoring**: Claude is used in two places only — Dimension 1 rubric scoring (5 rubrics) and Dimension 4 rubric scoring (2 rubrics). All other scoring is deterministic computation.
- **Schema change needed**: `scores` table needs `band` (string) and `forward_brief_data` (JSONB) columns added. Migration required.

---

## Build Status

| Component | Status | Notes |
|---|---|---|
| Database schema | Applied (needs migration) | 8 tables in Supabase. Needs: `band` and `forward_brief_data` columns on `scores` table |
| Pydantic models | Needs update | Current models reflect v1 architecture. Need new scoring output models matching v2 |
| Ingestion parsers | Validated | ZIP + XLSX parsers tested against real data. No changes needed for v2 |
| API routes | Complete | Auth, advisors, clients, questionnaires, jobs (5 routers, 15 endpoints) |
| Signup/invitation flow | Complete | Advisor + individual provisioning, client invitation via Supabase Auth |
| Worker skeleton | Complete | Job loop with optimistic locking, 4-stage pipeline with placeholder scoring/narratives |
| Scoring engine | Ready to build | All specifications complete. 4 dimensions, all bands defined, formula pressure-tested |
| Forward Brief computation | Ready to build | Data contract defined. Computed in scoring stage alongside dimensions |
| Narrative generation | Stub | Blocked on prompt templates. Must receive scored_dimensions + forward_brief_data as structured inputs |
| Claude rubric prompts | Not started | Dim 1 (5 rubrics) and Dim 4 (2 rubrics). Inter-rater consistency testing required before launch |
| Frontend | Not started | Josh's territory; API exists for it to build against |

---

## Tech Stack (reference)

| Layer | Technology |
|---|---|
| Frontend | React → Vercel |
| Backend | FastAPI (Python) → Railway |
| Database | Supabase (PostgreSQL) |
| AI | Anthropic API — Claude (rubric scoring + narrative generation) |
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
