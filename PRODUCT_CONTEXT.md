# Orpheus Social — Product Context

> **How to use this file:**
> Paste this file at the start of any AI session (Claude or ChatGPT) to load current project context. It is updated after each working session and lives in the repository at `PRODUCT_CONTEXT.md`.
> At the end of your session, ask your AI to structure any decisions or feedback using the format in the "Contributing" section, then send to Josh to be incorporated.

---

## Project Summary

Orpheus Social is a client portal and diagnostic tool that measures LinkedIn presence health and delivers actionable insights. It supports two use cases:

1. **Advisory (white-glove)** — An advisor manages clients as a white-labeled service. The system generates scores and narratives; the advisor reviews and edits narratives before publishing to the client. Multiple advisors supported from day one.

2. **Individual (self-serve)** — A person signs up, uploads their own LinkedIn data, and receives the Signal Score + Forward Brief automatically. No human review gate.

Both use cases share the same scoring engine and Signal Score framework. The scoring is fully deterministic — no AI is involved in score computation. Claude only generates narratives and Forward Brief copy after scores are calculated. The difference between use cases is in the workflow and delivery layer, not the analysis.

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
| 1 | Narrative & Conversion | Signal Alignment | Do profile signals and content signals align with a clear path to action? | 20 |
| 2 | Resonance | Performance | Does content generate engagement? | 20 |
| 3 | Consistency | Behavior | Is activity sustained and predictable? | 20 |
| 4 | Presence | Foundation | Is the profile structurally complete and interpretable? | 15 |
| 5 | Authority | Audience Quality | Is the audience relevant and appropriately senior? | 15 |
| 6 | Reach | Distribution | How large is the addressable audience? | 10 |

**Weights finalized [Andrew, 2026-03-30].** Ordered by weight. Rationale grounded in LinkedIn's confirmed AI systems — see Platform Intelligence section and Signal Score Architecture Decisions document.

---

### Sub-dimension Summary

Full sub-dimension architecture with scoring methods and point allocations is defined in the Signal Score Architecture Decisions document (master, 2026-03-30). Summary below for reference.

**Narrative & Conversion — 20 points:** Identity Clarity (8, rubric), Profile-Content Alignment (8, rubric), Engagement Invitation (4, three-state). "Engagement Invitation" replaces "Conversion Signal" — scored from About section text only, no commercial intent assumed. See Architecture Decisions Section 5.

**Resonance — 20 points:** Engagement Rate (10, quantitative), Impression Trend (5, quantitative), Avg Engagements Per Post (4, quantitative), Top Post Impressions (1, quantitative). Engagement Rate uses combined total engagements / impressions — LinkedIn's XLSX export does not break out likes, comments, and shares separately. Substantive vs. passive distinction addressed in Forward Brief and advisory notes, not in score.

**Consistency — 20 points:** Recent Activity Strength (6, quantitative — NEW), Active Weeks (5, quantitative), Posts Per Week (4, quantitative), Longest Gap (3, quantitative), Engagement Quality Ratio (2, quantitative — NEW), Weeks Above Median (1, quantitative). Recent Activity Strength captures recency decay — see Architecture Decisions Section 3. Engagement Quality Ratio measures outbound substantive engagement using Comments.csv + Reactions.csv — see Architecture Decisions Section 4.

**Presence — 15 points:** About Clarity (6, rubric), Headline Clarity (3, rubric), Experience Section Clarity (3, rubric), Profile Completeness (2, three-state), Visual Professionalism (1, three-state). Featured section dropped from scoring — advisory note only. Visual Professionalism scored from Rich_Media.csv when present; advisory note when absent.

**Authority — 15 points:** Senior+ Audience (6, quantitative), Target Industry Alignment (4, quantitative), Role Seniority (3, quantitative), Primary Geography (2, quantitative). Top Follower Organizations dropped from scoring — advisory observation only.

**Reach — 10 points:** Unique Members Reached (4, quantitative), New Followers/Week (3, quantitative), Total Followers (2, quantitative), Connections (1, quantitative).

---

## Data Sources

Clients submit two files:

| File | Format | Used For |
|---|---|---|
| LinkedIn Complete archive | ZIP (or unzipped folder) | Presence, Consistency, profile data |
| LinkedIn Analytics export | XLSX (5 sheets) | Reach, Resonance, Authority |

**Critical:** Clients must download the **Complete** archive, not the Basic archive. The Basic export omits `Shares.csv`, which is required for Consistency scoring.

**ZIP → Score mapping:**
- Presence → Profile.csv, Positions.csv, Rich_Media.csv
- Consistency → Shares.csv, Comments.csv, Reactions.csv
- Narrative & Conversion → Profile.csv (About section text), Shares.csv (post content)

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

*Implementation constraints and remaining items before build.*

1. **DISCOVERY sheet is summary-only** — LinkedIn's analytics XLSX provides only period totals (impressions, members reached) on the DISCOVERY sheet, not daily breakdowns. Daily impressions are available on the ENGAGEMENT sheet. The Reach indicator "Unique members reached" must come from the DISCOVERY summary, not a daily time series. [Josh, 2026-03-23]

2. **DEMOGRAPHICS categories differ from schema assumptions** — LinkedIn provides "Job titles," "Locations," and "Industries" — not "seniority," "geography," or "company." The Authority indicators for "Senior+ audience" must be derived from job title analysis (mapping titles to seniority tiers), not a direct seniority field. No company/organization data is provided in the analytics export. [Josh, 2026-03-23]

3. **FOLLOWERS sheet has no cumulative total per day** — Only a summary total in row 0 and daily "New followers" rows. Cumulative follower count over time must be computed backwards from the total. [Josh, 2026-03-23]

4. **Quantitative threshold bands** — Specific threshold values not yet defined for any quantitative sub-dimension. Bands must be set for all quantitative indicators before scoring engine is built. High priority. [Andrew, 2026-03-30]

5. **Three-state scoring definitions** — Profile Completeness and Visual Professionalism three-state conditions need explicit definitions — what constitutes Complete vs. Partial vs. Minimal for each. High priority. [Andrew, 2026-03-30]

6. **Framework reconciliation note** — Relationship between old five-category 0–4 scoring template and new six-dimension Signal Score architecture needs a brief documented reconciliation for internal clarity. Medium priority. [Andrew, 2026-03-30]

7. **360Brew language audit** — All instances of 360Brew as primary framing in schema and documentation should be updated to reference confirmed production systems: LLM-based dual-encoder retrieval (Danchev) and Feed SR sequential ranking model (Hertel et al.). Medium priority. [Andrew, 2026-03-30]

---

## Key Decisions Made

- **Deterministic scoring** — Score computation is pure Python, no AI. Claude handles narratives only.
- **90-day primary window** — Scores reflect the last 90 days, not full year.
- **Photo/banner recency scoring** — Rich_Media.csv upload history used; absence treated as gap.
- **Complete archive required** — Basic LinkedIn export is insufficient; Shares.csv is missing.
- **Qualitative scoring is constrained** — Rubric fields use explicit text only, no inference, fixed 1–5 definitions.
- **6 dimensions** — Narrative & Conversion added as 6th dimension. Weights finalized 2026-03-30.
- **Excluded from scoring** — Endorsements, Recommendations (as a metric), Articles, certifications, summary length, writing quality.
- **Two use cases, unified model** — Advisory (white-glove) and Individual (self-serve) share the same data model. An individual is modeled as an advisor with one client (themselves). This keeps the analysis pipeline on a single code path. [Josh, 2026-03-23]
- **Multi-advisor from day one** — The system supports multiple advisors at launch, not just Andrew. [Josh, 2026-03-23]
- **White-labeling = branding + narrative editing** — Advisors get custom logo, colors, domain, and can edit AI-generated narratives before client delivery. Scoring framework is fixed and shared, not configurable per advisor. [Josh, 2026-03-23]
- **client_id anchors all analysis data** — Jobs, scores, narratives, and reports FK to client, not advisor. This enables advisory→self-serve client migration by re-parenting the client record. [Josh, 2026-03-23]
- **Display name seeded once** — Client display_name is set from the account at creation, then allowed to diverge. No ongoing sync. [Josh, 2026-03-23]
- **Reports snapshot branding** — Each report stores the branding config (logo, colors, practice name) at generation time, not resolved dynamically. Advisory reports retain advisor branding even after client migration. [Josh, 2026-03-23]
- **Pipeline config snapshot on jobs** — Each job stores a JSONB config_snapshot capturing the full scoring config, questionnaire schema hash, and prompt version used. Enables future cross-report comparison without building a version registry now. [Josh, 2026-03-23]
- **Client login included in initial build** — Advisory clients log into the portal to view published reports. Advisor invites client by email (Supabase Auth invite), client accepts and gets a scoped dashboard. Skips manual delivery (PDF/email). Three RLS policy sets: advisor sees all their clients, client sees only their own published reports, self-serve individual sees everything for their own record. [Josh, 2026-03-23]
- **Dimension weights finalized** — Narrative & Conversion 20, Resonance 20, Consistency 20, Presence 15, Authority 15, Reach 10. Grounded in confirmed LinkedIn AI system priorities. [Andrew, 2026-03-30]
- **Dwell time as primary Resonance signal** — Confirmed by Feed SR paper as one of two primary optimization targets. Not available in LinkedIn analytics export — cannot be scored. Appears as an advisory note in diagnostic output and in Forward Brief recommendations. [Andrew, 2026-03-30]
- **Presence carries disproportionate weight for low-activity clients** — Feed SR confirms profile embeddings provide >2% performance improvement for members with <10 interactions. Scoring interpretation flags when activity is low enough that Presence is carrying disproportionate weight. Low-Activity Profile Note required in diagnostic output. [Andrew, 2026-03-30]
- **Recency decay in Consistency scoring** — Feed SR confirms exponential decay with ~2-month half-life on interaction history. Recent Activity Strength added as new Consistency sub-dimension (6 pts) scoring posting activity in most recent 30 days with trend condition. [Andrew, 2026-03-30]
- **Viewer-actor affinity compounding** — Feed SR confirms repeated engagement with the same people is a distinct ranked signal. Forward Brief recommends focused consistent engagement with relevant voices over scattered broad participation. [Andrew, 2026-03-30]
- **Cold-start profile opportunity** — Danchev blog confirms LLM-based retrieval can route content from headline and job title alone without engagement history. Profile work has immediate distribution consequences for passive professionals. Forward Brief entry-level insight. [Andrew, 2026-03-30]
- **Topic routing independent of network size** — Jurka confirms content on specific topics can be routed beyond the immediate network. Consistent topic signals expand addressable reach. Strengthens Narrative & Conversion rationale. [Andrew, 2026-03-30]
- **Featured section dropped from scoring** — Not captured in LinkedIn data export. Appears as advisory note in Presence section + Forward Brief checklist item. [Andrew, 2026-03-30]
- **Services section dropped from scoring** — Not captured in LinkedIn data export. Forward Brief recommendation only. [Andrew, 2026-03-30]
- **Top Follower Organizations dropped from scoring** — Not a confirmed platform ranking signal. Surfaces as advisory observation in diagnostic output. [Andrew, 2026-03-30]
- **Conversion Signal → Engagement Invitation** — Renamed and reframed. Scores whether the profile contains any clear signal inviting engagement, regardless of commercial intent. Three-state scoring from About section text (Profile.csv) only. [Andrew, 2026-03-30]
- **5 rubrics complete** — Headline Clarity, About Clarity, Experience Section Clarity (Presence); Identity Clarity, Profile-Content Alignment (Narrative & Conversion). All 1–5 scale with written criteria for every score point. Observable conditions only, no inference. [Andrew, 2026-03-30]
- **Combined Engagement Rate** — LinkedIn XLSX does not break out likes/comments/shares. Resonance scores a single combined Engagement Rate (10 pts) rather than separate substantive/passive rates. Advisory note explains platform weighting differences. [Andrew, 2026-03-30; Josh, 2026-03-31]
- **Engagement Quality Ratio added to Consistency** — Outbound engagement quality measured from Comments.csv + Reactions.csv (% of engagement that is substantive comments vs. passive reactions). 2 points in Consistency dimension. Captures viewer-actor affinity behavioral signal. [Andrew, 2026-03-30; Josh, 2026-03-31]
- **Visual Professionalism scoring** — Score from Rich_Media.csv when profile/banner photo entries are present. Advisory note when absent (known reliability gap). Client self-report as fallback. Image upload as future option pending user feedback. [Josh, 2026-03-31]

---

## Platform Intelligence

Confirmed findings from first-party LinkedIn engineering sources. These ground the scoring rationale and Forward Brief recommendations.

**Sources:**
- Feed SR: An Industrial-Scale Sequential Recommender for LinkedIn Feed Ranking (Hertel et al., arXiv:2602.12354v1, February 2026)
- LinkedIn Engineering Blog: Engineering the Next Generation of LinkedIn's Feed (Danchev, March 12, 2026)
- How Does the LinkedIn Feed Work? (Jurka, August 11, 2025)

**Confirmed signals and implications:**
- Dwell time and substantive contributions (comments, shares) are the two primary optimization targets for the ranking system (Feed SR)
- Profile embeddings are generated from profile data using a fine-tuned LLM, refreshed daily (Feed SR, Danchev)
- For members with <10 historical interactions, profile embeddings provide measurable performance improvement in retrieval quality (Feed SR)
- Exponential decay weighting on interaction history with ~2-month half-life — recent activity carries full weight, older activity decays (Feed SR)
- Viewer-to-actor affinity tracked across multiple time windows — repeated engagement with the same people is a distinct ranked signal (Feed SR)
- LLM-based retrieval can deduce professional interests from headline and job title alone without engagement history — cold-start advantage (Danchev)
- Content on specific topics can be routed beyond immediate network based on topic relevance and professional identity, independent of network size (Jurka)

**Note on 360Brew:** Referenced in early working model as directional only. Not confirmed as a current production system. Confirmed production systems are the LLM-based dual-encoder retrieval system (Danchev) and the Feed SR sequential ranking model (Hertel et al.).

See the LinkedIn 2026 Working Model for detailed sections on each confirmed finding.

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

**clients** — One row per subject being analyzed. Always belongs to an advisor. For self-serve, the advisor creates one client referencing themselves. For advisory, the advisor invites the client by email; `user_id` is set when the client accepts the invitation.
- `id` (uuid PK), `advisor_id` (FK → advisors), `user_id` (FK → auth.users, nullable — set on invite acceptance), `display_name`, `email`, `invitation_status` (pending / accepted / expired), `status` (active / inactive / migrated), `created_at`

**questionnaire_responses** — Questionnaire answers stored as JSONB. One row per client, updated incrementally.
- `id` (uuid PK), `client_id` (FK → clients, unique), `responses` (JSONB), `schema_version` (string), `completed_at` (nullable), `updated_at`

**jobs** — One row per analysis pipeline run. Carries the config snapshot for reproducibility.
- `id` (uuid PK), `client_id` (FK → clients), `status` (pending / running / complete / failed), `version_label` (string, nullable — human-friendly era tag e.g. "2026-Q1"), `config_snapshot` (JSONB), `attempt_count`, `error_message` (nullable), `created_at`, `started_at`, `completed_at`

**ingested_data** — Parsed LinkedIn data as structured JSONB after ingestion. Preserves intermediate state for re-scoring without re-parsing.
- `id` (uuid PK), `job_id` (FK → jobs, unique), `zip_data` (JSONB), `xlsx_data` (JSONB), `ingested_at`

**scores** — Dimension scores and indicator-level detail. One row per job.
- `id` (uuid PK), `job_id` (FK → jobs, unique), `total_score` (numeric), `dimensions` (JSONB — array of {dimension, score, weight, indicators: [{name, value, status}]}), `scored_at`

**narratives** — AI-generated text, one row per dimension per job. Supports draft→published workflow for advisory editing.
- `id` (uuid PK), `job_id` (FK → jobs), `dimension` (string), `generated_text`, `edited_text` (nullable), `status` (draft / published), `published_at` (nullable), `generated_at`

**reports** — Published deliverable bundle. Snapshots branding at generation time.
- `id` (uuid PK), `job_id` (FK → jobs, unique), `client_id` (FK → clients), `report_type` (advisory / self_serve), `branding_snapshot` (JSONB — logo, colors, practice name), `forward_brief` (JSONB or text), `published_at`

### Config Snapshot Shape (on jobs)

```json
{
  "version_label": "2026-Q1",
  "scoring": {
    "dimensions": [
      {
        "name": "Presence",
        "weight": 20,
        "indicators": [
          {"name": "Profile photo", "source": "Rich_Media.csv", "strength": "within 2 years", "gap": "4+ years or absent"}
        ]
      }
    ],
    "total_points": 100
  },
  "questionnaire_schema_hash": "abc123",
  "narrative_prompt_version": "1.0"
}
```

### Design Notes

- **Unified model**: An individual (self-serve) user is an advisor with `is_individual: true` and one client record pointing back to themselves. The entire pipeline — jobs, scores, narratives, reports — follows the same path for both use cases.
- **Advisory→self-serve migration**: Re-parent the client record to a new self-advisor. All history follows via client_id FKs. Historical reports retain original branding via snapshot.
- **Versioning**: Config snapshot is written once when a job starts and never mutated. Future comparison logic can diff snapshots across reporting cycles. No version registry needed yet.
- **Narrative editing**: Advisory flow sets narratives to `draft` status; advisor edits `edited_text` and publishes. Self-serve auto-publishes with `edited_text` null.
- **RLS pattern**: Three roles — advisor, client, individual. Advisor: full access to all data for their clients. Client: read-only access to their own published reports (narratives must have `status = published`). Individual: full access to their own client record and all pipeline data. All scoped via `user_id` on advisor or client records.
- **Client invitation**: Advisor creates client record with email → Supabase Auth invite sent → client accepts, sets password → `user_id` linked to client record, `invitation_status` set to `accepted`.

---

## Build Status

| Component | Status | Notes |
|---|---|---|
| Database schema | Applied | 8 tables, 5 enums, 26 RLS policies in Supabase |
| Pydantic models | Complete | 10 files, typed JSONB shapes for all entities |
| Ingestion parsers | Validated | ZIP + XLSX parsers tested against 2 real profiles |
| API routes | Complete | Auth, advisors, clients, questionnaires, jobs (5 routers, 15 endpoints) |
| Signup/invitation flow | Complete | Advisor + individual provisioning, client invitation via Supabase Auth |
| Worker skeleton | Complete | Job loop with optimistic locking, 4-stage pipeline with placeholder scoring/narratives |
| Scoring engine | Stub | Weights and rubrics received; blocked on quantitative threshold bands and three-state definitions |
| Narrative generation | Stub | Blocked on prompt templates and scoring engine completion |
| Frontend | Not started | Josh's territory; API exists for it to build against |

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
