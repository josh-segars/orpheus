"""Signal Score v2 computation engine.

Deterministic scoring for Dimensions 2 and 3 (quantitative band lookups).
Dimensions 1 and 4 accept pre-computed rubric scores as inputs (applied by
Claude in a separate step).

Also computes Forward Brief structured data in the same pass.

Output: ScoringStageOutput (scored_dimensions + forward_brief_data)
"""

from datetime import datetime, timedelta, date
from collections import Counter

from backend.ingestion.types import ZipData, XlsxData
from backend.models.scoring import (
    SignalBand,
    ConfidenceLabel,
    ScoringMethod,
    SubDimensionScore,
    DimensionScore,
    ScoredDimensions,
    ForwardBriefData,
    ForwardBriefQuantitative,
    QualitativeFlags,
    ViewerActorAffinity,
    VisualProfessionalism,
    EngagementInvitation,
    AudienceSegment,
    ScoringStageOutput,
)
from backend.scoring import config


# ============================================================
# Date helpers
# ============================================================

def _parse_date(date_str: str) -> date | None:
    """Parse a date string from LinkedIn export data.

    LinkedIn uses several formats across CSVs:
    - "2025-03-17" (ISO)
    - "03/17/2025" (US)
    - "Mar 17, 2025"
    Returns None if unparseable.
    """
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _trailing_window(items_with_dates: list[tuple[date, ...]], days: int, ref_date: date) -> list:
    """Filter items to those within trailing N days of ref_date."""
    cutoff = ref_date - timedelta(days=days)
    return [item for item in items_with_dates if item[0] >= cutoff]


# ============================================================
# Band lookup
# ============================================================

def _band_lookup(value: float, thresholds: list[float]) -> int:
    """Map a numeric value to a 0-5 score using threshold bands.

    thresholds is a list of 5 lower bounds for scores 1–5.
    If value < thresholds[0], score is 0.
    If value >= thresholds[4], score is 5.
    """
    score = 0
    for i, threshold in enumerate(thresholds):
        if value >= threshold:
            score = i + 1
        else:
            break
    return score


# ============================================================
# Dimension 2: Behavioral Signal Strength
# ============================================================

def _count_outbound_actions(zip_data: ZipData, ref_date: date) -> tuple[int, int]:
    """Count total outbound actions in trailing 12 months and 60 days.

    Outbound = comments + reactions + shares (+ reposts, which are shares).
    Returns (twelve_month_count, sixty_day_count).
    """
    cutoff_12mo = ref_date - timedelta(days=365)
    cutoff_60d = ref_date - timedelta(days=config.DIM2_RECENCY_WINDOW_DAYS)

    count_12mo = 0
    count_60d = 0

    for item in zip_data.shares:
        d = _parse_date(item.date)
        if d and d >= cutoff_12mo:
            count_12mo += 1
            if d >= cutoff_60d:
                count_60d += 1

    for item in zip_data.comments:
        d = _parse_date(item.date)
        if d and d >= cutoff_12mo:
            count_12mo += 1
            if d >= cutoff_60d:
                count_60d += 1

    for item in zip_data.reactions:
        d = _parse_date(item.date)
        if d and d >= cutoff_12mo:
            count_12mo += 1
            if d >= cutoff_60d:
                count_60d += 1

    return count_12mo, count_60d


def _score_history_depth(total_12mo: int) -> SubDimensionScore:
    """History Depth: total outbound actions, trailing 12 months."""
    score = _band_lookup(total_12mo, config.DIM2_HISTORY_DEPTH_BANDS)
    return SubDimensionScore(
        name="History Depth",
        score=score,
        scale="0-5",
        method=ScoringMethod.QUANTITATIVE,
        confidence=ConfidenceLabel.PROXY,
        raw_value=total_12mo,
    )


def _score_recency(count_60d: int, total_12mo: int) -> SubDimensionScore:
    """Recency: outbound actions in trailing 60 days.

    Hybrid: absolute band + proportional floor at bands 3+.
    """
    raw_score = _band_lookup(count_60d, config.DIM2_RECENCY_BANDS)

    # Apply proportional floor for bands 3+
    if raw_score >= 3 and total_12mo > 0:
        proportion = count_60d / total_12mo
        required = config.DIM2_RECENCY_PROPORTIONAL_FLOORS.get(raw_score, 0)
        if proportion < required:
            # Doesn't meet proportional floor — drop to highest qualifying band
            raw_score = 2
            # Re-check if band 3, 4, or 5 qualifies with proportional
            for check_score in [5, 4, 3]:
                threshold_idx = check_score - 1
                if (count_60d >= config.DIM2_RECENCY_BANDS[threshold_idx] and
                        proportion >= config.DIM2_RECENCY_PROPORTIONAL_FLOORS.get(check_score, 0)):
                    raw_score = check_score
                    break

    return SubDimensionScore(
        name="Recency",
        score=raw_score,
        scale="0-5",
        method=ScoringMethod.QUANTITATIVE_HYBRID,
        confidence=ConfidenceLabel.PROXY,
        raw_value=count_60d,
    )


def _compute_active_weeks(zip_data: ZipData, ref_date: date) -> int:
    """Count active weeks in trailing 52 weeks.

    Active = 3+ posts/comments in a calendar week. Reactions excluded.
    """
    cutoff = ref_date - timedelta(weeks=config.DIM2_CONTINUITY_WINDOW_WEEKS)
    week_counts: Counter[int] = Counter()

    for item in zip_data.shares:
        d = _parse_date(item.date)
        if d and d >= cutoff:
            # ISO week number as (year, week)
            iso = d.isocalendar()
            week_counts[(iso[0], iso[1])] += 1

    for item in zip_data.comments:
        d = _parse_date(item.date)
        if d and d >= cutoff:
            iso = d.isocalendar()
            week_counts[(iso[0], iso[1])] += 1

    return sum(1 for count in week_counts.values()
               if count >= config.DIM2_CONTINUITY_ACTIVE_THRESHOLD)


def _score_continuity(active_weeks: int) -> SubDimensionScore:
    """Continuity: active weeks out of trailing 52."""
    score = _band_lookup(active_weeks, config.DIM2_CONTINUITY_BANDS)
    return SubDimensionScore(
        name="Continuity",
        score=score,
        scale="0-5",
        method=ScoringMethod.QUANTITATIVE,
        confidence=ConfidenceLabel.CONFIRMED,
        raw_value=active_weeks,
    )


def _compute_posting_stats(zip_data: ZipData, ref_date: date) -> tuple[float, float]:
    """Compute posts/week average and proportion of weeks with a post.

    Returns (avg_posts_per_week, pct_weeks_with_post).
    """
    cutoff = ref_date - timedelta(weeks=config.DIM2_CONTINUITY_WINDOW_WEEKS)
    week_post_counts: Counter[tuple[int, int]] = Counter()

    for item in zip_data.shares:
        d = _parse_date(item.date)
        if d and d >= cutoff:
            iso = d.isocalendar()
            week_post_counts[(iso[0], iso[1])] += 1

    total_posts = sum(week_post_counts.values())
    weeks_with_post = len(week_post_counts)
    total_weeks = config.DIM2_CONTINUITY_WINDOW_WEEKS

    avg_per_week = total_posts / total_weeks if total_weeks > 0 else 0.0
    pct_with_post = weeks_with_post / total_weeks if total_weeks > 0 else 0.0

    return avg_per_week, pct_with_post


def _score_posting_presence(avg_per_week: float, pct_with_post: float) -> SubDimensionScore:
    """Posting Presence: average posts/week with consistency ceiling."""
    score = _band_lookup(avg_per_week, config.DIM2_POSTING_BANDS)

    # Consistency ceiling: cap at 3 if < 50% of weeks have a post
    if pct_with_post < config.DIM2_POSTING_CONSISTENCY_THRESHOLD:
        score = min(score, config.DIM2_POSTING_CONSISTENCY_CEILING)

    return SubDimensionScore(
        name="Posting Presence",
        score=score,
        scale="0-5",
        method=ScoringMethod.QUANTITATIVE,
        confidence=ConfidenceLabel.CONFIRMED,
        raw_value=round(avg_per_week, 3),
    )


def score_dimension_2(zip_data: ZipData, ref_date: date) -> DimensionScore:
    """Score Dimension 2: Behavioral Signal Strength."""
    total_12mo, count_60d = _count_outbound_actions(zip_data, ref_date)
    active_weeks = _compute_active_weeks(zip_data, ref_date)
    avg_per_week, pct_with_post = _compute_posting_stats(zip_data, ref_date)

    sub_scores = [
        _score_history_depth(total_12mo),
        _score_recency(count_60d, total_12mo),
        _score_continuity(active_weeks),
        _score_posting_presence(avg_per_week, pct_with_post),
    ]

    return _build_dimension(
        name="Behavioral Signal Strength",
        weight=config.DIMENSION_WEIGHTS["Behavioral Signal Strength"],
        confidence=ConfidenceLabel.CONFIRMED,
        sub_scores=sub_scores,
        scale_min=config.DIM2_SCALE_MIN,
        scale_max=config.DIM2_SCALE_MAX,
    )


# ============================================================
# Dimension 3: Behavioral Signal Quality
# ============================================================

def _count_engagement_presence(zip_data: ZipData, ref_date: date) -> int:
    """Combined comments + reactions, trailing 12 months."""
    cutoff = ref_date - timedelta(days=365)
    count = 0
    for item in zip_data.comments:
        d = _parse_date(item.date)
        if d and d >= cutoff:
            count += 1
    for item in zip_data.reactions:
        d = _parse_date(item.date)
        if d and d >= cutoff:
            count += 1
    return count


def _is_substantive_comment(message: str) -> bool:
    """A comment is substantive if it has 20+ words OR 100+ characters."""
    if len(message) >= config.DIM3_SUBSTANTIVE_CHAR_THRESHOLD:
        return True
    if len(message.split()) >= config.DIM3_SUBSTANTIVE_WORD_THRESHOLD:
        return True
    return False


def _compute_engagement_quality(zip_data: ZipData, ref_date: date) -> float:
    """Engagement Quality Score = substantive comments + (reactions × 0.25).

    Trailing 12 months.
    """
    cutoff = ref_date - timedelta(days=365)

    substantive_count = 0
    for item in zip_data.comments:
        d = _parse_date(item.date)
        if d and d >= cutoff and _is_substantive_comment(item.message):
            substantive_count += 1

    reaction_count = 0
    for item in zip_data.reactions:
        d = _parse_date(item.date)
        if d and d >= cutoff:
            reaction_count += 1

    return substantive_count + (reaction_count * config.DIM3_QUALITY_REACTION_WEIGHT)


def score_dimension_3(zip_data: ZipData, ref_date: date) -> DimensionScore:
    """Score Dimension 3: Behavioral Signal Quality."""
    engagement_count = _count_engagement_presence(zip_data, ref_date)
    quality_score_raw = _compute_engagement_quality(zip_data, ref_date)

    sub_scores = [
        SubDimensionScore(
            name="Outbound Engagement Presence",
            score=_band_lookup(engagement_count, config.DIM3_ENGAGEMENT_PRESENCE_BANDS),
            scale="0-5",
            method=ScoringMethod.QUANTITATIVE,
            confidence=ConfidenceLabel.CONFIRMED,
            raw_value=engagement_count,
        ),
        SubDimensionScore(
            name="Engagement Quality Score",
            score=_band_lookup(quality_score_raw, config.DIM3_QUALITY_BANDS),
            scale="0-5",
            method=ScoringMethod.QUANTITATIVE,
            confidence=ConfidenceLabel.INFERRED,
            raw_value=round(quality_score_raw, 2),
        ),
    ]

    return _build_dimension(
        name="Behavioral Signal Quality",
        weight=config.DIMENSION_WEIGHTS["Behavioral Signal Quality"],
        confidence=ConfidenceLabel.CONFIRMED,
        sub_scores=sub_scores,
        scale_min=config.DIM3_SCALE_MIN,
        scale_max=config.DIM3_SCALE_MAX,
    )


# ============================================================
# Dimension building + composite
# ============================================================

def _build_dimension(
    name: str,
    weight: float,
    confidence: ConfidenceLabel,
    sub_scores: list[SubDimensionScore],
    scale_min: int,
    scale_max: int,
    completeness_floor_applied: bool = False,
) -> DimensionScore:
    """Build a DimensionScore from sub-dimension scores.

    Formula: (sum - min_possible) / (max_possible - min_possible) × weight × 100
    """
    n = len(sub_scores)
    total = sum(s.score for s in sub_scores)
    min_possible = scale_min * n
    max_possible = scale_max * n

    if max_possible == min_possible:
        normalized = 0.0
    else:
        normalized = (total - min_possible) / (max_possible - min_possible)

    contribution = normalized * weight * 100

    return DimensionScore(
        name=name,
        weight=weight,
        confidence=confidence,
        normalized_score=round(normalized, 4),
        contribution=round(contribution, 2),
        sub_dimensions=sub_scores,
        completeness_floor_applied=completeness_floor_applied,
    )


def build_dimension_1_from_rubrics(
    rubric_scores: dict[str, int],
    zip_data: ZipData,
) -> DimensionScore:
    """Build Dimension 1 from Claude-applied rubric scores.

    rubric_scores: mapping of sub-dimension name → score (1–5).
    Expected keys: "Headline Clarity", "About Section Coherence",
    "Experience Description Quality", "Profile Completeness", "Identity Clarity".

    Applies completeness floor if required profile fields are missing.
    """
    sub_scores = []
    for name in config.DIM1_SUB_DIMENSIONS:
        score = rubric_scores.get(name, 1)  # default to minimum if missing
        sub_scores.append(SubDimensionScore(
            name=name,
            score=score,
            scale="1-5",
            method=ScoringMethod.RUBRIC,
            confidence=ConfidenceLabel.CONFIRMED,
        ))

    # Check completeness floor
    floor_applied = False
    profile = zip_data.profile
    missing = (
        not profile.headline.strip() or
        not profile.summary.strip() or
        not profile.industry.strip() or
        len(zip_data.positions) == 0
    )

    dim = _build_dimension(
        name="Profile Signal Clarity",
        weight=config.DIMENSION_WEIGHTS["Profile Signal Clarity"],
        confidence=ConfidenceLabel.CONFIRMED,
        sub_scores=sub_scores,
        scale_min=config.DIM1_SCALE_MIN,
        scale_max=config.DIM1_SCALE_MAX,
    )

    # Apply floor: cap contribution at 50% of max
    if missing:
        max_contribution = config.DIMENSION_WEIGHTS["Profile Signal Clarity"] * 100
        cap = max_contribution * config.DIM1_COMPLETENESS_CAP_PCT
        if dim.contribution > cap:
            dim = dim.model_copy(update={
                "contribution": round(cap, 2),
                "completeness_floor_applied": True,
            })
        else:
            dim = dim.model_copy(update={"completeness_floor_applied": True})

    return dim


def build_dimension_4_from_rubrics(
    rubric_scores: dict[str, int],
) -> DimensionScore:
    """Build Dimension 4 from Claude-applied rubric scores.

    rubric_scores: mapping of sub-dimension name → score (1–5).
    Expected keys: "Topic Consistency", "Profile-Content Coherence".
    """
    sub_scores = []
    for name in config.DIM4_SUB_DIMENSIONS:
        score = rubric_scores.get(name, 1)
        sub_scores.append(SubDimensionScore(
            name=name,
            score=score,
            scale="1-5",
            method=ScoringMethod.RUBRIC,
            confidence=ConfidenceLabel.CONFIRMED,
        ))

    return _build_dimension(
        name="Profile-Behavior Alignment",
        weight=config.DIMENSION_WEIGHTS["Profile-Behavior Alignment"],
        confidence=ConfidenceLabel.CONFIRMED,
        sub_scores=sub_scores,
        scale_min=config.DIM4_SCALE_MIN,
        scale_max=config.DIM4_SCALE_MAX,
    )


def assign_band(composite: float) -> SignalBand:
    """Map a composite score (0–100) to a signal strength band."""
    for name, lo, hi in config.SIGNAL_BANDS:
        if lo <= composite <= hi:
            return SignalBand(name)
    # Edge case: should not happen if bands cover 0–100
    if composite > 100:
        return SignalBand.EXCEPTIONAL
    return SignalBand.WEAK


def compute_composite(dimensions: list[DimensionScore]) -> float:
    """Sum dimension contributions to get composite score (0–100)."""
    return round(sum(d.contribution for d in dimensions), 2)


# ============================================================
# Forward Brief data extraction
# ============================================================

def compute_forward_brief(
    zip_data: ZipData,
    xlsx_data: XlsxData | None,
    ref_date: date,
) -> ForwardBriefData:
    """Extract Forward Brief structured data from ingested data.

    XLSX data is optional — self-serve clients may not provide it,
    and some fields are only available from the analytics export.
    """
    quant = _compute_forward_brief_quantitative(zip_data, xlsx_data, ref_date)
    flags = _compute_qualitative_flags(zip_data)
    return ForwardBriefData(quantitative=quant, qualitative_flags=flags)


def _compute_forward_brief_quantitative(
    zip_data: ZipData,
    xlsx_data: XlsxData | None,
    ref_date: date,
) -> ForwardBriefQuantitative:
    """Compute quantitative fields for Forward Brief."""
    fields: dict = {}

    # --- From XLSX ---
    if xlsx_data:
        # Follower count + growth rate
        fields["follower_count"] = xlsx_data.followers.total_followers
        if xlsx_data.followers.rows:
            total_new = sum(r.new_followers for r in xlsx_data.followers.rows)
            weeks = len(xlsx_data.followers.rows) / 7.0  # rows are daily
            fields["follower_growth_rate"] = round(total_new / weeks, 1) if weeks > 0 else 0.0

        # Discovery summary
        fields["unique_members_reached"] = xlsx_data.discovery.members_reached or None

        # Engagement metrics
        if xlsx_data.engagement:
            total_impressions = sum(r.impressions for r in xlsx_data.engagement)
            total_engagements = sum(r.engagements for r in xlsx_data.engagement)
            # Count posts from top_posts or shares — use engagement rows as proxy
            # for post count: days with impressions > 0
            post_days = sum(1 for r in xlsx_data.engagement if r.impressions > 0)
            if post_days > 0:
                fields["avg_impressions_per_post"] = round(total_impressions / post_days, 1)
            if total_impressions > 0:
                fields["avg_engagement_rate"] = round(total_engagements / total_impressions, 4)

        # Top post
        if xlsx_data.top_posts:
            max_impressions = max(p.impressions for p in xlsx_data.top_posts)
            fields["top_post_impressions"] = max_impressions

        # Demographics
        if xlsx_data.demographics.job_titles:
            fields["audience_seniority"] = xlsx_data.demographics.job_titles

        if xlsx_data.demographics.industries:
            sorted_industries = sorted(
                xlsx_data.demographics.industries.items(),
                key=lambda x: x[1], reverse=True
            )[:5]
            fields["audience_industries"] = [
                AudienceSegment(name=k, pct=v) for k, v in sorted_industries
            ]

        if xlsx_data.demographics.locations:
            sorted_geo = sorted(
                xlsx_data.demographics.locations.items(),
                key=lambda x: x[1], reverse=True
            )[:5]
            fields["audience_geography"] = [
                AudienceSegment(name=k, pct=v) for k, v in sorted_geo
            ]

    # --- From ZIP ---
    # Average comment length
    cutoff = ref_date - timedelta(days=365)
    comment_lengths = []
    for item in zip_data.comments:
        d = _parse_date(item.date)
        if d and d >= cutoff and item.message.strip():
            comment_lengths.append(len(item.message.split()))

    if comment_lengths:
        fields["avg_comment_length_words"] = round(
            sum(comment_lengths) / len(comment_lengths), 1
        )

    # Posting gap distribution
    post_dates = []
    for item in zip_data.shares:
        d = _parse_date(item.date)
        if d and d >= cutoff:
            post_dates.append(d)

    if post_dates:
        post_dates.sort()
        # Longest gap in weeks
        max_gap_days = 0
        for i in range(1, len(post_dates)):
            gap = (post_dates[i] - post_dates[i - 1]).days
            max_gap_days = max(max_gap_days, gap)
        fields["longest_posting_gap_weeks"] = max_gap_days // 7

        # % of weeks with zero posts
        week_set: set[tuple[int, int]] = set()
        for d in post_dates:
            iso = d.isocalendar()
            week_set.add((iso[0], iso[1]))
        total_weeks = config.DIM2_CONTINUITY_WINDOW_WEEKS
        fields["zero_post_week_pct"] = round(
            (total_weeks - len(week_set)) / total_weeks, 2
        )

    return ForwardBriefQuantitative(**fields)


def _compute_qualitative_flags(zip_data: ZipData) -> QualitativeFlags:
    """Compute pre-processed qualitative flags."""

    # --- Viewer-actor affinity ---
    # Count engagement targets from comment and reaction URLs
    target_counts: Counter[str] = Counter()
    for item in zip_data.comments:
        if item.link:
            # Extract the post author's profile URL or post URL as target
            target_counts[item.link] += 1
    for item in zip_data.reactions:
        if item.link:
            target_counts[item.link] += 1

    total_engagements = sum(target_counts.values())
    top_n = target_counts.most_common(config.AFFINITY_TOP_N)
    top_n_total = sum(count for _, count in top_n)
    concentrated = (
        total_engagements > 0 and
        top_n_total / total_engagements >= config.AFFINITY_CONCENTRATION_THRESHOLD
    )
    top_targets = [url for url, _ in top_n] if concentrated else []

    # --- Visual professionalism ---
    photo_present = any(
        "profile photo" in item.type.lower()
        for item in zip_data.rich_media
    )

    # --- Engagement invitation ---
    profile = zip_data.profile
    services_present = False  # Not available in ZIP — will be False unless enriched
    contact_visible = bool(profile.websites.strip())
    cta_in_about = _detect_cta_in_about(profile.summary)

    return QualitativeFlags(
        viewer_actor_affinity=ViewerActorAffinity(
            concentrated=concentrated,
            top_targets=top_targets,
        ),
        visual_professionalism=VisualProfessionalism(
            photo_present=photo_present,
        ),
        engagement_invitation=EngagementInvitation(
            services_present=services_present,
            contact_visible=contact_visible,
            cta_in_about=cta_in_about,
        ),
    )


def _detect_cta_in_about(summary: str) -> bool:
    """Heuristic: does the About section contain a call-to-action?

    Looks for common CTA patterns: email addresses, "reach out",
    "contact me", "let's connect", "DM me", URLs.
    """
    if not summary:
        return False
    lower = summary.lower()
    cta_signals = [
        "reach out", "contact me", "let's connect", "dm me",
        "get in touch", "email me", "send me", "book a",
        "schedule a", "connect with me", "@",
    ]
    return any(signal in lower for signal in cta_signals)


# ============================================================
# Main entry point
# ============================================================

def run_scoring(
    zip_data: ZipData,
    xlsx_data: XlsxData | None,
    dim1_rubric_scores: dict[str, int],
    dim4_rubric_scores: dict[str, int],
    ref_date: date | None = None,
) -> ScoringStageOutput:
    """Run the complete scoring pipeline.

    Args:
        zip_data: Parsed LinkedIn ZIP archive data.
        xlsx_data: Parsed LinkedIn Analytics XLSX data (optional).
        dim1_rubric_scores: Claude-applied rubric scores for Dimension 1.
            Keys: "Headline Clarity", "About Section Coherence",
            "Experience Description Quality", "Profile Completeness",
            "Identity Clarity". Values: 1–5.
        dim4_rubric_scores: Claude-applied rubric scores for Dimension 4.
            Keys: "Topic Consistency", "Profile-Content Coherence".
            Values: 1–5.
        ref_date: Reference date for trailing windows. Defaults to today.

    Returns:
        ScoringStageOutput with scored_dimensions and forward_brief_data.
    """
    if ref_date is None:
        ref_date = date.today()

    # Score all 4 dimensions
    dim1 = build_dimension_1_from_rubrics(dim1_rubric_scores, zip_data)
    dim2 = score_dimension_2(zip_data, ref_date)
    dim3 = score_dimension_3(zip_data, ref_date)
    dim4 = build_dimension_4_from_rubrics(dim4_rubric_scores)

    dimensions = [dim1, dim2, dim3, dim4]
    composite = compute_composite(dimensions)
    band = assign_band(composite)

    scored = ScoredDimensions(
        composite=composite,
        band=band,
        dimensions=dimensions,
    )

    # Compute Forward Brief data
    forward_brief = compute_forward_brief(zip_data, xlsx_data, ref_date)

    return ScoringStageOutput(
        scored_dimensions=scored,
        forward_brief_data=forward_brief,
    )
