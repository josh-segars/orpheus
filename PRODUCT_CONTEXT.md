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
- Recency — outbound actions in trailing 60 days. Hybrid absolute + proportional floor at bands 3+, bypassed when total_12mo ≥ 300 (deep histories where absolute counts are inherently meaningful). PROXY measure. Bands: 0(<5), 1(5–14), 2(15–39), 3(40–99 AND ≥15% of 12mo), 4(100–199 AND ≥20% of 12mo), 5(200+ AND ≥20% of 12mo). Bypass threshold: 300 (PROVISIONAL).
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

**Signal strength bands** (client-facing output — tuner metaphor, renamed 2026-05-29 per ORPHEUS-49):

| Band | Score Range |
|---|---|
| Dissonant | 0–24 |
| Untuned | 25–44 |
| Tuning | 45–64 |
| Tuned | 65–79 |
| Resonant | 80–100 |

Bands are unequal by design — narrower at extremes. Numeric scores visible to advisors only; clients see bands. Band breakpoints are PROVISIONAL — recalibration at 50–100 profiles.

**Pressure-test result (confirmed via live pipeline, 2026-04-13):** Andrew Segars scores 77.6/100 → Tuned band (was "Strong" pre-rename). Dim 1: 22.75, Dim 2: 25.50, Dim 3: 20.00, Dim 4: 9.38. Data period: 2025-03-17 to 2026-03-16. Full pipeline (Ingestion → Rubric Scoring → Deterministic Scoring → Narrative Generation) completed end-to-end on Railway + Supabase.

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

**Critical:** Clients must download the **Complete** archive, not the Basic archive. The Basic export omits `Shares.csv`, which is required for behavioral scoring. **Enforced at upload as of 2026-07-01** (ORPHEUS-88 + ORPHEUS-101): POST /jobs rejects a Basic archive (by filename prefix, with a missing-file content backstop) and a stale export (>14 days old, from the filename date or the analytics XLSX) with a 422 + actionable guidance. Reports that complete on otherwise-degraded data (e.g. an inactive-but-Complete archive) carry a `jobs.data_limited` flag surfaced as a client banner + advisor/admin chip. As of ORPHEUS-110 (2026-07-20), a genuine Complete export from a member with no posts/comments — LinkedIn omits empty per-activity CSVs entirely — is distinguished from a renamed Basic archive via a Complete-fingerprint check (≥2 Complete-only files) and passes through as a valid zero-activity, data-limited report instead of being rejected.

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
- Visual professionalism: `photo_present: bool` — from the client's LinkedIn OIDC `picture` claim captured at submission (ORPHEUS-89, `jobs.oidc_photo_present`); falls back to the Rich_Media.csv `profile photo` heuristic when no OIDC signal was captured (NULL — older/advisor-run jobs)
- Engagement invitation: `services_present: bool`, `contact_visible: bool`, `cta_in_about: bool` — from Profile.csv

### Scoring Stage Output Shape

```json
{
  "scored_dimensions": {
    "composite": 77.6,
    "band": "Tuned",
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

4. **Inter-rater consistency testing** — ✅ **RESOLVED 2026-06-10 (ORPHEUS-75).** Dimensions 1 and 4 use Claude-applied rubrics. Run as a two-arm consistency experiment (N=10 per profile per arm against both preserved demo profiles): API-default temperature produced a band-crossing composite spread on a borderline profile (74.12–83.0 on identical data, 6 Tuned / 4 Resonant); temperature 0 produced zero variance (20/20 identical runs). Rubric calls now run at temperature 0 by default (`backend/agents/rubric.py`); the harness at `backend/scripts/rubric_consistency.py` re-measures after any rubric or model change. Note: temp-0 is greedy, not median — borderline profiles get one consistent answer, not a "central" one. [Andrew, 2026-04-08; resolved Josh, 2026-06-10] **Re-measured after the Sonnet 4.6 model swap (ORPHEUS-90, accepted 2026-06-24):** determinism held (0.00 stdev across the swap); 4.6 scores the two rubric dimensions harsher, accepted as the new calibration baseline (no threshold change), so reports under the retired Sonnet-4 snapshot are no longer scale-comparable to 4.6 reports. [Andrew, 2026-06-24]

5. **Recalibration checkpoint** — All PROVISIONAL band boundaries and dimension weights flagged for review at 50–100 profiles. Must be adjustable configuration parameters in the build. [Andrew, 2026-04-08]

---

## Key Decisions Made

### Architecture & Scoring (v2, April 2026)
- **4-dimension architecture** — Replaced 6-dimension model. Dimensions grounded in confirmed LinkedIn retrieval and ranking system inputs, not outcomes. Reach, Resonance, Authority move to Forward Brief. [Andrew, 2026-04-08]
- **One scoring engine, no stream distinction** — Identical engine for advisory and self-serve. No client-type flag or conditional logic. All differences live in report output and delivery layer. [Andrew, 2026-04-08]
- **Dimension weights: 35/30/20/15** — INFERRED and PROVISIONAL. Adjustable config, not hardcoded. Cold-start finding across three papers grounds the profile-heavy weighting. [Andrew, 2026-04-08]
- **Signal strength bands** — Client-facing output is band label (Dissonant/Untuned/Tuning/Tuned/Resonant), not raw number. Numeric scores visible to advisors only. [Andrew + Josh, 2026-04-01; labels renamed to tuner metaphor 2026-05-29 / ORPHEUS-49, Josh]
- **Band breakpoints: 0–24, 25–44, 45–64, 65–79, 80–100** — Unequal by design. PROVISIONAL. [Andrew, 2026-04-08]. The integer ranges are documentation; `assign_band` matches as **half-open lower bounds** (a float composite takes the highest band whose lower bound it meets, top band inclusive of 100) so fractional scores between the integer ranges land in the lower band rather than falling through — fixed 2026-06-23 / ORPHEUS-95 after a 79.13 composite mislabeled as Dissonant. The integer thresholds are unchanged.
- **Sub-dimension combination formula** — `(sum − min) / (max − min) × weight`. Equal weighting within dimensions. Pressure-tested against real data (77.6 → Tuned, formerly Strong). [Andrew, 2026-04-08]
- **Completeness floor on Dimension 1** — Missing headline, About, industry, or job history caps Dim 1 at 50%. Structural check, not a scored sub-dimension. [Andrew, 2026-04-08]
- **Confidence labeling** — Every scoring element labeled CONFIRMED, INFERRED, PROXY, or PROVISIONAL. Labels carry through to client-facing transparency disclosures. [Andrew, 2026-04-08]

### Dimension-Specific (v2)
- **Dimension 2: all bands confirmed** — History Depth, Recency (hybrid absolute + proportional floor, bypassed at total_12mo ≥ 300), Continuity (3+ posts/comments = active week), Posting Presence (1/wk benchmark, 50% consistency ceiling). All bands PROVISIONAL. [Andrew, 2026-04-08; bypass added Josh, 2026-04-13]
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

### Report Structure (June 2026)
- **Forward Brief retired as a standalone deliverable — reaxised into the dimension narratives** — Reverses the [Andrew, 2026-04-08] "Reach, Resonance, Authority move to Forward Brief" framing as a separate document. The R/R/A axis was pitched at a senior international-relations audience; the scored dimensions are the right lens for all audiences. The forward-looking guidance is regenerated per dimension and merged with the dimension score narrative into a combined messaging paragraph (200–400w), each dimension gains an always-visible 1–2 sentence `summary` teaser, and `forward_brief_data` (still computed in the scoring stage, unchanged) renders as a structured metrics block at the bottom of the Signal Score page instead of feeding a standalone narrative. Cheat Sheet is the only remaining standalone deliverable; flow is Signal Score → Cheat Sheet. Shipped under ORPHEUS-67/68/69 (2026-06-10); live cloud validation ORPHEUS-73. [Andrew + Josh, 2026-06-08]

### Calibration (April 13, 2026)
- **Recency proportional floor bypass at 300** — The proportional floor (15–20% of 12mo total) penalizes consistently active users since 60 days is only 16.4% of a year. Skip the floor when total_12mo ≥ 300, where absolute counts are inherently meaningful. PROVISIONAL threshold. [Josh, 2026-04-13]
- **LinkedIn datetime format** — Shares.csv, Comments.csv, Reactions.csv use `YYYY-MM-DD HH:MM:SS` (with timestamp), not date-only. Parser must try datetime format first. [Josh, 2026-04-13]
- **Trailing-window reference date anchored to export's latest activity (not `date.today()`)** — all trailing windows (Recency 60d, History Depth / engagement 12mo, Continuity) measure relative to the most recent dated action in the export, resolved by `resolve_ref_date()`, with `date.today()` only as a no-dated-activity fallback. Makes scores reproducible on identical data (re-running a frozen export days later no longer slides the window past the member's latest posts) and records `ref_date` + `ref_date_anchor` into `config_snapshot` for auditability. "Recent" therefore means "recent relative to data capture," not "active as of the run date." Anchor choice routed from Andrew. [Josh, 2026-06-18; ORPHEUS-91]

### Carried from v1
- **Deterministic scoring** — Score computation is pure Python, no AI. Claude handles rubric application (Dim 1, Dim 4) and narrative generation only.
- **Complete archive required** — Basic LinkedIn export is insufficient; Shares.csv is missing. Modern Complete exports append a member-ID suffix to the behavioral CSVs (`Shares_181682616.csv` etc.); both the parser's read path (ORPHEUS-87) and its missing-file detection (ORPHEUS-103, 2026-07-08) tolerate the suffix via a shared `_csv_name_matches` / `_csv_present` helper, so a suffixed Complete archive is no longer mis-flagged as missing Shares.csv (which, post ORPHEUS-88, would have hard-blocked it at upload). ORPHEUS-110 (2026-07-20) adds the zero-activity case: when the archive carries the Complete fingerprint (≥2 of Ad_Targeting / Inferences_about_you / SearchQueries / Logins / Ads Clicked / Security Challenges), absent behavioral CSVs are reported as EMPTY_DATA (non-blocking, data-limiting) rather than MISSING_FILE — a never-posted member's Complete export has no Shares.csv to include.
- **Two use cases, unified model** — Advisory and individual share the same data model. An individual is an advisor with one client (themselves). [Josh, 2026-03-23]
- **Multi-advisor from day one** — Multiple advisors at launch, not just Andrew. [Josh, 2026-03-23]
- **White-labeling = branding + narrative editing** — Scoring framework is fixed and shared, not configurable per advisor. [Josh, 2026-03-23]
- **client_id anchors all analysis data** — Enables advisory→self-serve migration. [Josh, 2026-03-23]
- **Pipeline config snapshot on jobs** — JSONB config_snapshot for reproducibility. [Josh, 2026-03-23] Records `ref_date` + `ref_date_anchor` since ORPHEUS-91 [Josh, 2026-06-18] and the effective scoring `model` since ORPHEUS-97 [Josh, 2026-07-13] — rows stored before 2026-07-13 have no model key; the 2026-06-12 deploy is the known Sonnet-4/4.6 boundary.
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
- `id` (uuid PK), `job_id` (FK → jobs, unique), `total_score` (numeric), `band` (string — Dissonant/Untuned/Tuning/Tuned/Resonant), `dimensions` (JSONB), `forward_brief_data` (JSONB), `scored_at`

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
    "bands": {"Dissonant": [0, 24], "Untuned": [25, 44], "Tuning": [45, 64], "Tuned": [65, 79], "Resonant": [80, 100]}
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
| Database schema | Applied | Migration 001 = snapshot of prod public schema (2026-05-11, ORPHEUS-35). On top: 011 (questionnaire spec alignment, ORPHEUS-33), 012 (invitation columns, ORPHEUS-36), 013 (band rename, ORPHEUS-49 — applied to cloud 2026-06-01 under ORPHEUS-25). On top later: 014 (one-clients-row-per-user unique index, ORPHEUS-83), 015 (`jobs.oidc_photo_present`, ORPHEUS-89), 016 (`jobs.data_limited`, ORPHEUS-88 — applied to cloud 2026-07-01, no backfill). On top later: 017 (`public.waitlist` write-only table, ORPHEUS-8) + 018 (waitlist first_name/last_name/interests[], ORPHEUS-8) — committed 2026-07-08, **applied to cloud** (ladder shows 2026-07-02 + a harmless idempotent re-apply 2026-07-08; verified 2026-07-15 during ORPHEUS-104). Fresh-DB recipe: `supabase db reset && apply 001 + 011 + 012 + 013 + 014 + 015 + 016 + 017 + 018`. Migrations 007–010 are HISTORICAL — don't apply on top of 001. Migrations 003–006 are baked into 001. |
| Pydantic models | Complete | v2 scoring output models (ScoringStageOutput) in `models/scoring.py`. `SubDimensionScore` carries optional narrative fields (`summary` / `best_practices` / `improvements`) as of ORPHEUS-21 (2026-06-04, commit `c66645a`); narrative agent emits 13 per-sub-dim payloads alongside the 5 top-level sections, with conditional curve baked into the slot structure (Summary always, BP at scores 1–3, Improvements at scores 1–4). Five sub-dim names get a client-facing display swap on the frontend (Experience Description Quality → Experience Narrative, History Depth → Engagement History, Outbound Engagement Presence → Engagement Volume, Engagement Quality Score → Substantive Engagement, Profile-Content Coherence → Profile-Content Match); internal names stay canonical everywhere upstream. Live cloud validation tracked under ORPHEUS-62. |
| Ingestion — ZIP parser | Complete | Tested against real data. Handles None keys, datetime formats. Data quality reporting integrated |
| Ingestion — XLSX parser | Complete | All 5 sheets parsed (DISCOVERY, ENGAGEMENT, TOP POSTS, FOLLOWERS, DEMOGRAPHICS). Tested against real data |
| API routes | Complete | 5 routers (`jobs`, `clients`, `advisor`, `session`, `admin`) registered in `backend/main.py`. All client-facing routes role-gated via `get_current_session_roles` (`SessionRoles.is_advisor()` / `.is_client()`); two routes use `get_verified_session` for the neither-role case (`POST /accept-invitation`, `GET /session`). `GET /jobs/{id}` accepts both client-self and advisor-owns-client paths post-ORPHEUS-46. `GET /jobs` (ORPHEUS-81, 2026-06-12) lists the caller's own jobs newest-first with composite band joined from `scores.band` (+ a `data_limited` flag per ORPHEUS-88) — backs the `/reports` page; `POST /jobs` enforces the one-in-flight-run-per-client guard with a 409, plus (ORPHEUS-88/100/101, 2026-07-01) three ordered upload gates that 422 a Basic/corrupt archive (filename prefix + missing-file content backstop) and a stale export (>14 days, from the filename date or the analytics XLSX). As of ORPHEUS-108 (2026-07-15) submission is browser-direct: `POST /jobs/upload-urls` mints signed Storage upload URLs (staging path, guards first), the browser uploads straight to Supabase Storage, and `POST /jobs/from-uploads` runs the same gates (shared `_apply_submission_gates`) against the staged bytes and moves them to the worker's path — the large body never transits the Railway edge; the legacy multipart `POST /jobs` remains only as a deploy-skew shim — live validation completed 2026-07-20 (ORPHEUS-86/102 closed), so the shim's removal is the outstanding ORPHEUS-108 remainder. `/admin/*` routes use `get_current_admin` (JWT-verify + `ADMIN_EMAILS` allowlist) and bypass RLS via the service-role client — god-mode by design (ORPHEUS-31). |
| Signup/invitation flow | Complete | Resend transactional email + custom backend (`POST /clients/invite`, `POST /accept-invitation`, `POST /clients/{id}/resend-invitation`, all under ORPHEUS-38). Advisor admin UI at `/advisor/clients` (ORPHEUS-39) for managing the roster — list, invite, resend, run-my-own-report. Cloud Supabase + prod LinkedIn OIDC wired under ORPHEUS-25 (2026-06-01). **ORPHEUS-44 closed 2026-06-02 part 2** — full live e2e validated end-to-end against cloud: invite acceptance, questionnaire save, Groundwork → Analysis → Signal Score / Forward Brief / Cheat Sheet placeholder, advisor uncloak (ORPHEUS-46), and admin narrative edit with `edited_text` overlay surfacing to the client on next poll (ORPHEUS-31 + ORPHEUS-59). Two in-flight bugs shipped same session: ORPHEUS-59 (handler payload schema reconcile) + ORPHEUS-61 (advisors.email → auth.users lookup). ORPHEUS-60 filed as the only deferred follow-up (narrative agent emits structured cheat_sheet). **Report-completion feedback email shipped under ORPHEUS-98 (2026-06-24)** — a thank-you + beta-survey CTA (`format_report_ready_email`) sent once per client when their report becomes viewable: self-serve at pipeline completion (worker), advisory at publication (admin narrative PATCH when the last draft flips to published); idempotency + once-per-client ride `reports.published_at`; optional `BETA_SURVEY_URL` env on both Railway services; consent footer deferred for the closed beta. **Resend messaging shipped under ORPHEUS-93 (2026-07-13)** — resend rotates the token (kills the earlier link), so the resend email now says it replaces any earlier invitation, the accept-invitation 401 points at the recovery path, and the advisor's Resend button requires an inline confirm. ORPHEUS-94 (email-mismatch reads as an error) remains open. |
| Worker / job processor | Complete | Job loop with optimistic locking via RPC, 4-stage pipeline, upsert retry safety, deployed on Railway |
| Scoring engine | Complete | 4 dimensions, all bands, formula confirmed. `scoring/config.py` + `scoring/engine.py`. Pressure-test: 77.6 ✓. Per-dimension band classification ships on `DimensionScore.band` as of ORPHEUS-22 (2026-05-30) — reuses composite SIGNAL_BANDS thresholds against `normalized_score × 100`. |
| Forward Brief computation | Complete | Computed in scoring stage (unchanged by ORPHEUS-68). XLSX feeds reach/audience metrics; ZIP feeds qualitative flags. As of ORPHEUS-67/68/69 (2026-06-10) the data no longer feeds a standalone narrative — it grounds the per-dimension forward-looking guidance and renders as the Signal Score page's structured metrics block |
| Claude rubric scoring | Complete | `agents/rubric.py` — Dim 1 (5 rubrics) + Dim 4 (2 rubrics). Temperature pinned at 0 for run-to-run determinism (ORPHEUS-75, 2026-06-10); inter-rater consistency verified — zero variance over 20 runs per profile (Open Question 4 resolved). Re-measure via `backend/scripts/rubric_consistency.py` after any rubric or model change. |
| Narrative generation | Complete | `agents/narrative.py` — receives scored dimensions + forward brief data + quality report + 9-question intake (post-ORPHEUS-34 prompt rewrite). Single Claude call (`max_tokens` 8192) emits 4 dimension sections — each a combined messaging paragraph (up to ~400w, interpretation + forward-looking guidance; length floors dropped across all narrative layers under ORPHEUS-66, 2026-06-10) plus an always-visible 1–2 sentence `summary` teaser (ORPHEUS-68, 2026-06-10; the standalone forward_brief section is retired) — AND 13 per-sub-dim narrative payloads (ORPHEUS-21, score-keyed conditional structure) AND the structured cheat_sheet (ORPHEUS-60). Return type is `NarrativeResult` NamedTuple (`sections` + `summaries` + `sub_dimensions` + `cheat_sheet`); worker's Stage 4b merges sub-dim payloads and dim summaries back into `scoring_output` and re-persists `scores.dimensions` JSONB. Live cloud validation of the ORPHEUS-68 reaxis tracked under ORPHEUS-73. Voice: platform default is **direct second person** (`second_person_direct`) as of ORPHEUS-77 (2026-06-10) — revises the original advisory = third-person split; `third_person_neutral` stays selectable per-advisor via `advisors.narrative_config`. |
| Railway deployment | Complete | Web service (FastAPI) + worker service (background processor). Shared env vars. Worker requires manual redeploy. Build is now pinned in source via repo-root `requirements.txt` (Railpack Python provider auto-detection); the manual dashboard Build Command override is retired as of ORPHEUS-43 (2026-05-31). |
| Vercel deployment | Complete | Frontend deployed at the configured Vercel project. `frontend/vercel.json` adds the SPA fallback rewrite Vite's framework preset doesn't auto-add. Root directory is `frontend`. `VITE_*` env vars set in dashboard (Production / Preview / Development). |
| Frontend | Complete | All portal pages shipped — Welcome, Groundwork, Questionnaire (9-question simplified intake post-ORPHEUS-33), LinkedIn upload Step 1 + Step 2, Analysis-in-Progress, Signal Score (redesigned per ORPHEUS-50 + restructured per ORPHEUS-51 — contained waveform hero with band-keyed assets + dimension cards + 5-pill band rows + 5-pip sub-dimension ratings), Cheat Sheet, Login, `/invite/:token`, `/invite/callback`, `/not-invited`, `/advisor/clients` (ORPHEUS-39), `/admin` (ORPHEUS-31 — email-allowlisted stopgap; clients + jobs + inline narrative editor, plus a read-only waitlist section with signup-count/interests header stats as of ORPHEUS-104, 2026-07-15). React Query + Supabase Auth wiring complete via `frontend/src/lib/`. Dark mode is canonical app-wide as of ORPHEUS-50 (2026-05-29); no light variant. PortalNav identity cluster ("Prepared for / [Name]" + logout, role-aware name source) shipped app-wide under ORPHEUS-52 (2026-05-30), then folded into the account dropdown with "Logged in as" reframe under ORPHEUS-71 (2026-06-08). App-wide palette + chrome refresh under ORPHEUS-70 (2026-06-08) — brighter green/cyan accents, magenta-anchored pip spectrum, deeper `#00080e` page bg, pure-white text, taller nav, and active band pills that take their band's pip color. **Forward Brief page retired under ORPHEUS-69 (2026-06-10)** — dimension cards carry summary + read-more toggle, `forward_brief_data` renders as the metrics block at the bottom of the Signal Score page, flow is Signal Score → Cheat Sheet. Cheat Sheet subtitle resolves the report subject via the ORPHEUS-71 hero pattern as of ORPHEUS-74 (2026-06-10). Client-facing copy renamed under ORPHEUS-76 (2026-06-11): "Signal Score" → "report", "Cheat Sheet" → "Quick Reference Card" (user-facing strings only; routes + internal names unchanged); same pass fixed the login wordmark positioning context and added Figma-spec sub-dim expand carets. **Multi-report support shipped under ORPHEUS-81 (2026-06-12)** — new `/reports` list page is the client landing surface (one row per job: date, band chip in spectrum pip colors, status; in-flight rows link to Analysis), "Run a New Report" re-enters Groundwork (hidden while a job is in flight; backend 409 is authoritative), smart redirect routes any job history to the list, nav "View My Reports" → `/reports`. ORPHEUS-78 verbiage pass same session: "View My Quick Reference Card", shortened dimension display names (Profile Clarity / Signal Strength / Signal Quality / Alignment via `DIM_DISPLAY_NAMES`; internal names canonical upstream), Welcome card retitled. A data-limited report banner + "Limited data" chips (reports list / advisor roster / admin) shipped under ORPHEUS-88 (2026-07-01); ORPHEUS-106 (2026-07-09) made the underlying `parse_failure` classification proportional (a `QualityIssue.total_rows`-driven >10%-of-source threshold in `DataQualityReport.data_limitation_issues()`), so a small unparseable-date tail no longer trips the banner/chip. **Public marketing landing page + waitlist shipped under ORPHEUS-8 (2026-07-08)** — an `isMarketingHost()` branch in `App.tsx` serves a no-auth `LandingPage` at `/` on the www/apex host (portal stays on `app.*`; `/site` previews on localhost), with browser-direct waitlist capture to a write-only `public.waitlist` table (migrations 017/018). Groundwork submission is browser-direct to Supabase Storage as of ORPHEUS-108 (2026-07-15) — `useCreateJob` mints signed upload URLs, uploads via `uploadToSignedUrl`, then submits `POST /jobs/from-uploads`; a failed transfer surfaces as the ORPHEUS-86 `NetworkError` guidance, and as of ORPHEUS-109 (2026-07-20) both files are rebuilt with canonical MIME before upload (Windows reports .zip as `application/x-zip-compressed`, which the Storage bucket allowlist rejected) and a Storage 4xx surfaces the service's own reason via `UploadRejectedError` instead of the connection copy. Frontend test infra (vitest + RTL) stood up under ORPHEUS-47, current baseline **79 green** (as of ORPHEUS-109, 2026-07-20). |

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
