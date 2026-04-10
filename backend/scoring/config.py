"""Scoring configuration — all PROVISIONAL parameters live here.

Every threshold, weight, and band boundary is a config value, not a
hardcoded constant. This entire module is serialized into the job's
config_snapshot for reproducibility.

Recalibration checkpoint: 50–100 profiles.
"""

# === Dimension weights ===
# INFERRED + PROVISIONAL — grounded in cold-start literature
# but LinkedIn does not publish dimension weights.

DIMENSION_WEIGHTS = {
    "Profile Signal Clarity": 0.35,
    "Behavioral Signal Strength": 0.30,
    "Behavioral Signal Quality": 0.20,
    "Profile-Behavior Alignment": 0.15,
}


# === Signal strength bands ===
# Client-facing. Unequal by design — narrower at extremes.
# PROVISIONAL — recalibrate at 50–100 profiles.

SIGNAL_BANDS = [
    ("Weak", 0, 24),
    ("Emerging", 25, 44),
    ("Moderate", 45, 64),
    ("Strong", 65, 79),
    ("Exceptional", 80, 100),
]


# === Dimension 1: Profile Signal Clarity ===
# 5 sub-dimensions, scale 1–5, rubric scoring by Claude.
# Completeness floor: if any required field is missing, cap at 50%.

DIM1_SUB_DIMENSIONS = [
    "Headline Clarity",
    "About Section Coherence",
    "Experience Description Quality",
    "Profile Completeness",
    "Identity Clarity",
]

DIM1_SCALE_MIN = 1
DIM1_SCALE_MAX = 5

# Fields whose absence triggers the completeness floor
DIM1_COMPLETENESS_REQUIRED_FIELDS = ["headline", "about", "industry", "job_history"]
DIM1_COMPLETENESS_CAP_PCT = 0.5  # 50% of max contribution


# === Dimension 2: Behavioral Signal Strength ===
# 4 sub-dimensions, scale 0–5, quantitative band lookups.
# All band boundaries are PROVISIONAL.

# History Depth: total outbound actions (comments + reactions + shares + reposts),
# trailing 12 months. PROXY measure.
# Bands: 0(<10), 1(10–29), 2(30–99), 3(100–299), 4(300–599), 5(600+)
DIM2_HISTORY_DEPTH_BANDS = [10, 30, 100, 300, 600]

# Recency: outbound actions in trailing 60 days.
# Hybrid absolute + proportional floor at bands 3+.
# Bands: 0(<5), 1(5–14), 2(15–39), 3(40–99 AND ≥15%), 4(100–199 AND ≥20%), 5(200+ AND ≥20%)
DIM2_RECENCY_BANDS = [5, 15, 40, 100, 200]
DIM2_RECENCY_PROPORTIONAL_FLOORS = {
    3: 0.15,  # ≥15% of 12-month total
    4: 0.20,  # ≥20% of 12-month total
    5: 0.20,  # ≥20% of 12-month total
}
DIM2_RECENCY_WINDOW_DAYS = 60

# Continuity: active weeks (3+ posts/comments = active) out of trailing 52 weeks.
# Posts + comments only, not reactions.
# Bands: 0(<5), 1(5–12), 2(13–25), 3(26–37), 4(38–46), 5(47–52)
DIM2_CONTINUITY_BANDS = [5, 13, 26, 38, 47]
DIM2_CONTINUITY_ACTIVE_THRESHOLD = 3  # posts + comments per week to count as active
DIM2_CONTINUITY_WINDOW_WEEKS = 52

# Posting Presence: average posts/week over 52 weeks. Posts only.
# Consistency ceiling: if <50% of weeks have a post, capped at score 3.
# Bands: 0(none), 1(<0.25/wk), 2(0.25–0.49), 3(0.5–0.99), 4(1.0–1.99), 5(2.0+)
DIM2_POSTING_BANDS = [0.001, 0.25, 0.50, 1.0, 2.0]  # lower bounds for scores 1-5
DIM2_POSTING_CONSISTENCY_CEILING = 3  # max score if < threshold % of weeks have a post
DIM2_POSTING_CONSISTENCY_THRESHOLD = 0.50  # 50% of weeks must have a post

DIM2_SCALE_MIN = 0
DIM2_SCALE_MAX = 5


# === Dimension 3: Behavioral Signal Quality ===
# 2 sub-dimensions, scale 0–5, quantitative.

# Outbound Engagement Presence: combined comments + reactions, trailing 12 months.
# Bands: 0(<10), 1(10–49), 2(50–149), 3(150–499), 4(500–999), 5(1000+)
DIM3_ENGAGEMENT_PRESENCE_BANDS = [10, 50, 150, 500, 1000]

# Engagement Quality Score: substantive comments + (reactions × 0.25).
# Substantive = 20 words or 100 characters.
# Bands: 0(0–4), 1(5–24), 2(25–74), 3(75–199), 4(200–399), 5(400+)
DIM3_QUALITY_BANDS = [5, 25, 75, 200, 400]
DIM3_QUALITY_REACTION_WEIGHT = 0.25  # INFERRED + PROVISIONAL — 4:1 weighting
DIM3_SUBSTANTIVE_WORD_THRESHOLD = 20
DIM3_SUBSTANTIVE_CHAR_THRESHOLD = 100

DIM3_SCALE_MIN = 0
DIM3_SCALE_MAX = 5


# === Dimension 4: Profile-Behavior Alignment ===
# 2 sub-dimensions, scale 1–5, rubric scoring by Claude.

DIM4_SUB_DIMENSIONS = [
    "Topic Consistency",
    "Profile-Content Coherence",
]

DIM4_SCALE_MIN = 1
DIM4_SCALE_MAX = 5


# === Viewer-Actor Affinity detection (Forward Brief) ===
# A target is "concentrated" if the top N targets account for ≥ threshold of engagements.

AFFINITY_TOP_N = 5
AFFINITY_CONCENTRATION_THRESHOLD = 0.25  # 25% of total outbound to top N


# === Serializable config for snapshot ===

def build_config_snapshot(version_label: str = "2026-Q2") -> dict:
    """Build a serializable config snapshot for the jobs table.

    This captures all PROVISIONAL parameters at the time the job runs,
    ensuring reproducibility even if thresholds change later.
    """
    return {
        "version_label": version_label,
        "scoring": {
            "dimension_weights": DIMENSION_WEIGHTS,
            "bands": {name: [lo, hi] for name, lo, hi in SIGNAL_BANDS},
            "dim2": {
                "history_depth_bands": DIM2_HISTORY_DEPTH_BANDS,
                "recency_bands": DIM2_RECENCY_BANDS,
                "recency_proportional_floors": {
                    str(k): v for k, v in DIM2_RECENCY_PROPORTIONAL_FLOORS.items()
                },
                "recency_window_days": DIM2_RECENCY_WINDOW_DAYS,
                "continuity_bands": DIM2_CONTINUITY_BANDS,
                "continuity_active_threshold": DIM2_CONTINUITY_ACTIVE_THRESHOLD,
                "posting_bands": DIM2_POSTING_BANDS,
                "posting_consistency_ceiling": DIM2_POSTING_CONSISTENCY_CEILING,
                "posting_consistency_threshold": DIM2_POSTING_CONSISTENCY_THRESHOLD,
            },
            "dim3": {
                "engagement_presence_bands": DIM3_ENGAGEMENT_PRESENCE_BANDS,
                "quality_bands": DIM3_QUALITY_BANDS,
                "quality_reaction_weight": DIM3_QUALITY_REACTION_WEIGHT,
                "substantive_word_threshold": DIM3_SUBSTANTIVE_WORD_THRESHOLD,
                "substantive_char_threshold": DIM3_SUBSTANTIVE_CHAR_THRESHOLD,
            },
            "dim1_completeness_floor": {
                "required_fields": DIM1_COMPLETENESS_REQUIRED_FIELDS,
                "cap_pct": DIM1_COMPLETENESS_CAP_PCT,
            },
        },
    }
