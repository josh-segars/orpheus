"""Pydantic models for v2 Signal Score scoring output.

These models define the data contracts for the scoring stage output,
matching the v2 4-dimension architecture (April 2026).
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# --- Enums ---

class SignalBand(str, Enum):
    """Client-facing signal strength band."""
    WEAK = "Weak"
    EMERGING = "Emerging"
    MODERATE = "Moderate"
    STRONG = "Strong"
    EXCEPTIONAL = "Exceptional"


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
    """Score for a single sub-dimension."""
    name: str
    score: float = Field(..., description="Raw score on the sub-dimension scale")
    scale: str = Field(..., description="Scale range, e.g. '1-5' or '0-5'")
    method: ScoringMethod
    confidence: ConfidenceLabel = ConfidenceLabel.CONFIRMED
    raw_value: Optional[float] = Field(
        None, description="Underlying metric value before band mapping (quantitative only)"
    )


# --- Dimension scores ---

class DimensionScore(BaseModel):
    """Score for a single dimension, containing sub-dimension breakdowns."""
    name: str
    weight: float = Field(..., description="Dimension weight as decimal (e.g. 0.35)")
    confidence: ConfidenceLabel
    normalized_score: float = Field(
        ..., description="(sum - min) / (max - min), range 0.0-1.0"
    )
    contribution: float = Field(
        ..., description="normalized_score × weight × 100, contribution to composite"
    )
    sub_dimensions: list[SubDimensionScore]
    completeness_floor_applied: bool = Field(
        False, description="True if Dim 1 completeness floor capped the contribution"
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
    """Quantitative computed fields for Forward Brief."""
    # From XLSX
    follower_count: Optional[int] = None
    follower_growth_rate: Optional[float] = Field(
        None, description="New followers per week"
    )
    unique_members_reached: Optional[int] = Field(
        None, description="From DISCOVERY sheet summary"
    )
    avg_impressions_per_post: Optional[float] = None
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


class ForwardBriefData(BaseModel):
    """Complete Forward Brief structured data output."""
    quantitative: ForwardBriefQuantitative
    qualitative_flags: QualitativeFlags


# --- Top-level scoring stage output ---

class ScoringStageOutput(BaseModel):
    """Complete output from the scoring stage.

    This is the single object produced by the scoring engine,
    containing both the scored dimensions and the Forward Brief data.
    Both are passed to narrative generation as structured inputs.
    """
    scored_dimensions: ScoredDimensions
    forward_brief_data: ForwardBriefData
