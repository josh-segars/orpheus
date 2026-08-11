"""Pydantic models for v2 Signal Score scoring output.

These models define the data contracts for the scoring stage output,
matching the v2 4-dimension architecture (April 2026).
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# --- Enums ---

class SignalBand(str, Enum):
    """Client-facing signal strength band — tuner metaphor.

    Renamed 2026-05-29 from Weak/Emerging/Moderate/Strong/Exceptional
    per ORPHEUS-49. Underlying composite-score thresholds are unchanged.
    """
    DISSONANT = "Dissonant"
    UNTUNED = "Untuned"
    TUNING = "Tuning"
    TUNED = "Tuned"
    RESONANT = "Resonant"


class ConfidenceLabel(str, Enum):
    """Confidence label for scoring elements."""
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    PROXY = "PROXY"
    PROVISIONAL = "PROVISIONAL"


class ScoringMethod(str, Enum):
    """How a sub-dimension score is computed."""
    RUBRIC = "rubric"               # Claude-applied qualitative rubric (Dim 1, Dim 4)
    QUANTITATIVE = "quantitative"   # Band lookup from numeric value (Dim 2, Dim 3)
    QUANTITATIVE_HYBRID = "quantitative_hybrid"  # Band + proportional floor (Recency)


# --- Sub-dimension scores ---

class SubDimensionScore(BaseModel):
    """Score for a single sub-dimension.

    Narrative fields (summary / best_practices / improvements) are populated
    by the narrative generation stage (ORPHEUS-21). They follow a conditional
    curve baked into the slot structure itself rather than calibrated by tone:

      * summary       — always present (every sub-dim, every score)
      * best_practices — only at scores 0–3 (where the client needs the
                         standard articulated)
      * improvements   — only at scores 0–4 (drop entirely at score 5)

    Score 0 (ORPHEUS-63 decision, 2026-06-04): treated the same as score 1
    for slot structure. Quantitative sub-dims that come back at 0 carry the
    full payload of Summary + Best Practices + Improvements; the Summary's
    language is calibrated to acknowledge the absence of measurable activity
    rather than position the client "below the standard."

    Display name swap for client-facing rendering happens on the frontend
    via a SUB_DIM_DISPLAY_NAMES map; the internal name on this model is the
    canonical identifier used in scoring, rubrics, and config.
    """
    name: str
    score: float = Field(..., description="Raw score on the sub-dimension scale")
    scale: str = Field(..., description="Scale range, e.g. '1-5' or '0-5'")
    method: ScoringMethod
    confidence: ConfidenceLabel = ConfidenceLabel.CONFIRMED
    raw_value: Optional[float] = Field(
        None, description="Underlying metric value before band mapping (quantitative only)"
    )
    summary: Optional[str] = Field(
        None,
        description=(
            "Data-grounded observation specific to this person on this "
            "sub-dimension. Up to ~45 words. Always present when narratives "
            "are generated."
        ),
    )
    best_practices: Optional[str] = Field(
        None,
        description=(
            "Generic standard for this sub-dimension (up to ~35 words). "
            "Populated only at scores 0–3 — at 4–5 the standard is "
            "implicit and the slot stays empty."
        ),
    )
    improvements: Optional[list[str]] = Field(
        None,
        description=(
            "Specific, score-aware action bullets (3–5 at scores 0 or 1, "
            "1–2 at score 4). Populated only at scores 0–4 — at score 5 "
            "the slot stays empty."
        ),
    )


# --- Dimension scores ---

class DimensionScore(BaseModel):
    """Score for a single dimension, containing sub-dimension breakdowns.

    The `summary` narrative field is populated by the narrative generation
    stage (ORPHEUS-68) — an always-visible 1–2 sentence teaser for the
    dimension card, distinct from both the combined messaging paragraph
    (which lives in the `narratives` table as the dimension's section row)
    and the per-sub-dim Summary slot. It rides the `scores.dimensions`
    JSONB the same way the sub-dim narrative fields do (ORPHEUS-21), so
    no migration and no admin-edit surface in v1.
    """
    name: str
    weight: float = Field(..., description="Dimension weight as decimal (e.g. 0.35)")
    confidence: ConfidenceLabel
    normalized_score: float = Field(
        ..., description="(sum - min) / (max - min), range 0.0-1.0"
    )
    contribution: float = Field(
        ..., description="normalized_score × weight × 100, contribution to composite"
    )
    band: SignalBand = Field(
        ...,
        description=(
            "Per-dimension band classification. ORPHEUS-22 decision (locked): "
            "reuses the composite SIGNAL_BANDS thresholds, applied to "
            "normalized_score × 100. Server-authoritative so client and "
            "advisor views can't drift."
        ),
    )
    sub_dimensions: list[SubDimensionScore]
    completeness_floor_applied: bool = Field(
        False, description="True if Dim 1 completeness floor capped the contribution"
    )
    summary: Optional[str] = Field(
        None,
        description=(
            "Always-visible 1–2 sentence dimension teaser (up to ~40 words), "
            "populated by the narrative stage (ORPHEUS-68). Distinct from "
            "the combined messaging paragraph (narratives table) and the "
            "sub-dim Summary slots. None on jobs that predate ORPHEUS-68."
        ),
    )


# --- Composite score ---

class ScoredDimensions(BaseModel):
    """Complete scored output from the scoring engine."""
    composite: float = Field(..., description="Composite score, range 0-100")
    band: SignalBand
    dimensions: list[DimensionScore] = Field(
        ..., description="Exactly 4 dimensions in v2"
    )


# --- Forward Brief data ---

class AudienceSegment(BaseModel):
    """A single segment in an audience breakdown."""
    name: str
    pct: float = Field(..., description="Proportion as decimal, e.g. 0.35")


class ViewerActorAffinity(BaseModel):
    """Viewer-actor affinity qualitative flag."""
    concentrated: bool = Field(
        ..., description="Whether engagement is concentrated on a small number of targets"
    )
    top_targets: list[str] = Field(
        default_factory=list, description="URLs or identifiers of most-engaged targets"
    )


class VisualProfessionalism(BaseModel):
    """Visual professionalism qualitative flag."""
    photo_present: bool


class EngagementInvitation(BaseModel):
    """Engagement invitation qualitative flag."""
    services_present: bool
    contact_visible: bool
    cta_in_about: bool


class QualitativeFlags(BaseModel):
    """Pre-processed qualitative flags for Forward Brief."""
    viewer_actor_affinity: ViewerActorAffinity
    visual_professionalism: VisualProfessionalism
    engagement_invitation: EngagementInvitation


class ForwardBriefQuantitative(BaseModel):
    """Quantitative computed fields for Forward Brief.

    ORPHEUS-114: the operand fields (post_count, total_impressions,
    total_engagements, net_new_followers, followers_weeks_observed,
    discovery_impressions) persist the values the derived ratios are built
    from, so the reconciliation identities can be checked against stored
    data and prose figures trace to labelled inputs. All Optional — rows
    written before ORPHEUS-114 lack them and must keep validating.
    """
    # From XLSX
    follower_count: Optional[int] = None
    follower_growth_rate: Optional[float] = Field(
        None, description="New followers per week"
    )
    unique_members_reached: Optional[int] = Field(
        None, description="From DISCOVERY sheet summary"
    )
    avg_impressions_per_post: Optional[float] = Field(
        None,
        description=(
            "Total impressions over the analytics window divided by original "
            "posts published inside the scoring window (ORPHEUS-112). An "
            "approximation, not an identity: the numerator includes "
            "impressions earned by posts published before the window (bounded "
            "in practice by how fast impressions decay after publication), "
            "and the two sides are drawn from windows that differ by a few "
            "days — the numerator's is fixed by the analytics export, the "
            "denominator's is anchored on latest ZIP activity per ORPHEUS-91."
        ),
    )
    avg_engagement_rate: Optional[float] = Field(
        None, description="Engagement rate on received content"
    )
    top_post_impressions: Optional[int] = None
    audience_seniority: Optional[dict[str, float]] = Field(
        None, description="Seniority level → proportion"
    )
    audience_industries: Optional[list[AudienceSegment]] = None
    audience_geography: Optional[list[AudienceSegment]] = None
    top_organizations: Optional[list[str]] = Field(
        None, description="Top represented follower organizations"
    )
    # From ZIP
    avg_comment_length_words: Optional[float] = Field(
        None, description="Average comment length for depth observation"
    )
    longest_posting_gap_weeks: Optional[int] = None
    zero_post_week_pct: Optional[float] = Field(
        None, description="Proportion of weeks with zero posts"
    )
    # --- ORPHEUS-114 operands (persisted so identities are checkable) ---
    post_count: Optional[int] = Field(
        None,
        description=(
            "Original posts published inside the trailing 365-day scoring "
            "window (ZIP Shares.csv, parseable dates only) — the "
            "avg_impressions_per_post denominator (ORPHEUS-112)"
        ),
    )
    total_impressions: Optional[int] = Field(
        None,
        description="sum(ENGAGEMENT daily impressions) over the export window",
    )
    total_engagements: Optional[int] = Field(
        None,
        description="sum(ENGAGEMENT daily engagements) over the export window",
    )
    net_new_followers: Optional[int] = Field(
        None,
        description="sum(FOLLOWERS daily new_followers) over the export window",
    )
    followers_weeks_observed: Optional[float] = Field(
        None,
        description=(
            "len(FOLLOWERS daily rows) / 7 — the follower_growth_rate "
            "denominator"
        ),
    )
    discovery_impressions: Optional[int] = Field(
        None,
        description=(
            "DISCOVERY sheet impressions summary cell — LinkedIn's own "
            "total, cross-checked against total_impressions by the "
            "reconciliation gate (was parsed-but-unread before ORPHEUS-114)"
        ),
    )


class DateExclusion(BaseModel):
    """Per-file date-quality coverage: how many rows scoring can't use.

    ORPHEUS-114 (d). `unparseable` counts rows with a non-empty Date that
    no known format parses (the same predicate scoring uses, via the shared
    DATE_FORMATS); `empty` counts rows with no Date at all — previously
    dropped silently before any count was taken. `total_rows` is every row
    parsed from the CSV.
    """
    unparseable: int = 0
    empty: int = 0
    total_rows: int = 0


class ForwardBriefCoverage(BaseModel):
    """Coverage/exclusion facts about the metrics (ORPHEUS-114 d).

    Formalizes what the narrative previously surfaced ad hoc ("72
    unparseable comment dates"; per-post reach exists for only the top-50
    analytics cap). Rendered as labelled prompt lines so coverage claims in
    prose trace to inputs, and whitelisted by the ORPHEUS-121 prose gate.
    """
    posts_in_window: int = 0
    top_posts_covered: int = Field(
        0,
        description=(
            "len(XLSX TOP POSTS rows) — LinkedIn caps the export at 50, so "
            "per-post reach exists for at most 50 of posts_in_window posts"
        ),
    )
    shares: DateExclusion = DateExclusion()
    comments: DateExclusion = DateExclusion()
    reactions: DateExclusion = DateExclusion()


class ForwardBriefData(BaseModel):
    """Complete Forward Brief structured data output."""
    quantitative: ForwardBriefQuantitative
    qualitative_flags: QualitativeFlags
    # ORPHEUS-114 (d): None on rows written before the coverage facts existed.
    coverage: Optional[ForwardBriefCoverage] = None


# --- Top-level scoring stage output ---

class ScoringStageOutput(BaseModel):
    """Complete output from the scoring stage.

    This is the single object produced by the scoring engine,
    containing both the scored dimensions and the Forward Brief data.
    Both are passed to narrative generation as structured inputs.
    """
    scored_dimensions: ScoredDimensions
    forward_brief_data: ForwardBriefData
