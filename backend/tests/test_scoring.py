"""Tests for Signal Score v2 scoring engine.

Run from repo root: python -m pytest backend/tests/test_scoring.py -v

Includes:
- Unit tests for band lookup, date parsing, individual sub-dimensions
- Integration test against Andrew Segars' known pressure-test result (77.6 → Strong)
- Edge cases: empty data, completeness floor, consistency ceiling
"""

import pytest
from datetime import date
from backend.scoring.engine import (
    _band_lookup,
    _parse_date,
    _is_substantive_comment,
    _detect_cta_in_about,
    _build_dimension,
    build_dimension_1_from_rubrics,
    build_dimension_4_from_rubrics,
    score_dimension_2,
    score_dimension_3,
    compute_composite,
    assign_band,
    compute_forward_brief,
    run_scoring,
)
from backend.scoring.config import (
    DIM2_HISTORY_DEPTH_BANDS,
    DIM3_QUALITY_BANDS,
    DIM3_ENGAGEMENT_PRESENCE_BANDS,
)
from backend.ingestion.types import (
    ZipData, ProfileData, PositionData, ShareItem,
    CommentItem, ReactionItem, RichMediaItem,
    XlsxData, DiscoverySummary, EngagementRow,
    TopPostItem, FollowersData, FollowersRow, DemographicsData,
)
from backend.models.scoring import (
    SignalBand, ConfidenceLabel, ScoringMethod, SubDimensionScore,
)


# ============================================================
# Helpers to build test data
# ============================================================

def _make_shares(dates: list[str]) -> list[ShareItem]:
    return [ShareItem(date=d, share_commentary=f"Post on {d}") for d in dates]


def _make_comments(dates: list[str], messages: list[str] | None = None) -> list[CommentItem]:
    if messages is None:
        messages = ["Short comment"] * len(dates)
    return [CommentItem(date=d, message=m) for d, m in zip(dates, messages)]


def _make_reactions(dates: list[str]) -> list[ReactionItem]:
    return [ReactionItem(date=d, reaction_type="LIKE") for d in dates]


def _make_profile(headline="CTO", summary="Long about section " * 50,
                  industry="Technology", positions=True) -> tuple[ProfileData, list[PositionData]]:
    p = ProfileData(
        first_name="Test", last_name="User",
        headline=headline, summary=summary, industry=industry,
    )
    pos = [PositionData(company_name="Acme", title="CTO")] if positions else []
    return p, pos


# ============================================================
# Unit tests: band lookup
# ============================================================

class TestBandLookup:
    def test_below_all_thresholds(self):
        assert _band_lookup(5, DIM2_HISTORY_DEPTH_BANDS) == 0

    def test_at_first_threshold(self):
        assert _band_lookup(10, DIM2_HISTORY_DEPTH_BANDS) == 1

    def test_between_thresholds(self):
        assert _band_lookup(50, DIM2_HISTORY_DEPTH_BANDS) == 2

    def test_at_top_threshold(self):
        assert _band_lookup(600, DIM2_HISTORY_DEPTH_BANDS) == 5

    def test_well_above_top(self):
        assert _band_lookup(10000, DIM2_HISTORY_DEPTH_BANDS) == 5

    def test_zero(self):
        assert _band_lookup(0, DIM2_HISTORY_DEPTH_BANDS) == 0


# ============================================================
# Unit tests: date parsing
# ============================================================

class TestDateParsing:
    def test_iso_format(self):
        assert _parse_date("2025-03-17") == date(2025, 3, 17)

    def test_us_format(self):
        assert _parse_date("03/17/2025") == date(2025, 3, 17)

    def test_short_month_format(self):
        assert _parse_date("Mar 17, 2025") == date(2025, 3, 17)

    def test_long_month_format(self):
        assert _parse_date("March 17, 2025") == date(2025, 3, 17)

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_garbage(self):
        assert _parse_date("not a date") is None

    def test_whitespace(self):
        assert _parse_date("  2025-03-17  ") == date(2025, 3, 17)


# ============================================================
# Unit tests: substantive comment detection
# ============================================================

class TestSubstantiveComment:
    def test_short_comment(self):
        assert _is_substantive_comment("Great post!") is False

    def test_long_by_words(self):
        msg = " ".join(["word"] * 20)
        assert _is_substantive_comment(msg) is True

    def test_long_by_chars(self):
        msg = "a" * 100
        assert _is_substantive_comment(msg) is True

    def test_barely_under_word_threshold(self):
        msg = " ".join(["word"] * 19)
        assert _is_substantive_comment(msg) is False

    def test_empty(self):
        assert _is_substantive_comment("") is False


# ============================================================
# Unit tests: CTA detection
# ============================================================

class TestCTADetection:
    def test_no_cta(self):
        assert _detect_cta_in_about("I am a professional.") is False

    def test_reach_out(self):
        assert _detect_cta_in_about("Reach out to discuss opportunities.") is True

    def test_email(self):
        assert _detect_cta_in_about("Contact me at user@example.com") is True

    def test_empty(self):
        assert _detect_cta_in_about("") is False


# ============================================================
# Unit tests: band assignment
# ============================================================

class TestBandAssignment:
    def test_weak(self):
        assert assign_band(0) == SignalBand.WEAK
        assert assign_band(24) == SignalBand.WEAK

    def test_emerging(self):
        assert assign_band(25) == SignalBand.EMERGING
        assert assign_band(44) == SignalBand.EMERGING

    def test_moderate(self):
        assert assign_band(45) == SignalBand.MODERATE
        assert assign_band(64) == SignalBand.MODERATE

    def test_strong(self):
        assert assign_band(65) == SignalBand.STRONG
        assert assign_band(79) == SignalBand.STRONG

    def test_exceptional(self):
        assert assign_band(80) == SignalBand.EXCEPTIONAL
        assert assign_band(100) == SignalBand.EXCEPTIONAL


# ============================================================
# Dimension 1: rubric input + completeness floor
# ============================================================

class TestDimension1:
    def test_perfect_scores(self):
        profile, positions = _make_profile()
        scores = {name: 5 for name in [
            "Headline Clarity", "About Section Coherence",
            "Experience Description Quality", "Profile Completeness",
            "Identity Clarity",
        ]}
        dim = build_dimension_1_from_rubrics(scores, ZipData(
            profile=profile, positions=positions,
        ))
        assert dim.name == "Profile Signal Clarity"
        assert dim.weight == 0.35
        # (25 - 5) / (25 - 5) = 1.0, × 0.35 × 100 = 35.0
        assert dim.contribution == 35.0
        assert dim.completeness_floor_applied is False

    def test_minimum_scores(self):
        profile, positions = _make_profile()
        scores = {name: 1 for name in [
            "Headline Clarity", "About Section Coherence",
            "Experience Description Quality", "Profile Completeness",
            "Identity Clarity",
        ]}
        dim = build_dimension_1_from_rubrics(scores, ZipData(
            profile=profile, positions=positions,
        ))
        # (5 - 5) / (25 - 5) = 0.0
        assert dim.contribution == 0.0

    def test_completeness_floor_missing_headline(self):
        profile, positions = _make_profile(headline="")
        scores = {name: 5 for name in [
            "Headline Clarity", "About Section Coherence",
            "Experience Description Quality", "Profile Completeness",
            "Identity Clarity",
        ]}
        dim = build_dimension_1_from_rubrics(scores, ZipData(
            profile=profile, positions=positions,
        ))
        assert dim.completeness_floor_applied is True
        # Max contribution = 35.0, capped at 50% = 17.5
        assert dim.contribution == 17.5

    def test_completeness_floor_no_positions(self):
        profile, _ = _make_profile(positions=False)
        scores = {name: 4 for name in [
            "Headline Clarity", "About Section Coherence",
            "Experience Description Quality", "Profile Completeness",
            "Identity Clarity",
        ]}
        dim = build_dimension_1_from_rubrics(scores, ZipData(
            profile=profile, positions=[],
        ))
        assert dim.completeness_floor_applied is True

    def test_completeness_floor_not_triggered_for_low_scores(self):
        """Floor only caps — if score is already below cap, just flag it."""
        profile, positions = _make_profile(headline="")
        scores = {name: 2 for name in [
            "Headline Clarity", "About Section Coherence",
            "Experience Description Quality", "Profile Completeness",
            "Identity Clarity",
        ]}
        dim = build_dimension_1_from_rubrics(scores, ZipData(
            profile=profile, positions=positions,
        ))
        assert dim.completeness_floor_applied is True
        # (10 - 5) / (25 - 5) × 35 = 8.75, which is < 17.5 cap
        assert dim.contribution == 8.75


# ============================================================
# Dimension 2: quantitative scoring
# ============================================================

class TestDimension2:
    def test_empty_data(self):
        dim = score_dimension_2(ZipData(), date(2026, 3, 16))
        assert dim.name == "Behavioral Signal Strength"
        # All zeros → all sub-scores = 0
        for sub in dim.sub_dimensions:
            assert sub.score == 0
        assert dim.contribution == 0.0

    def test_active_user(self):
        """User with moderate activity across 6 months."""
        from datetime import timedelta
        ref = date(2026, 3, 16)
        base = date(2025, 9, 16)
        # 150 shares spread across ~26 weeks (≈ 6 months)
        share_dates = []
        for week in range(26):
            d = base + timedelta(weeks=week)
            for _ in range(5):  # 5 posts per week
                share_dates.append(d.isoformat())

        # 100 comments spread over 200 days
        comment_dates = []
        for i in range(100):
            d = base + timedelta(days=i * 2)
            if d <= ref:
                comment_dates.append(d.isoformat())

        # 200 reactions spread over 200 days
        reaction_dates = []
        for i in range(200):
            d = base + timedelta(days=i)
            if d <= ref:
                reaction_dates.append(d.isoformat())

        zip_data = ZipData(
            shares=_make_shares(share_dates),
            comments=_make_comments(comment_dates),
            reactions=_make_reactions(reaction_dates),
        )
        dim = score_dimension_2(zip_data, ref)
        assert dim.contribution > 0
        assert dim.weight == 0.30

    def test_consistency_ceiling(self):
        """Posts concentrated in a few weeks should hit the ceiling."""
        ref = date(2026, 3, 16)
        # 100 posts all in one week — avg is high but only 1/52 weeks has posts
        share_dates = [date(2026, 3, 10).isoformat()] * 100
        zip_data = ZipData(shares=_make_shares(share_dates))
        dim = score_dimension_2(zip_data, ref)
        posting = next(s for s in dim.sub_dimensions if s.name == "Posting Presence")
        assert posting.score <= 3  # consistency ceiling


# ============================================================
# Dimension 3: quality scoring
# ============================================================

class TestDimension3:
    def test_empty_data(self):
        dim = score_dimension_3(ZipData(), date(2026, 3, 16))
        for sub in dim.sub_dimensions:
            assert sub.score == 0

    def test_substantive_comments_boost_quality(self):
        from datetime import timedelta
        ref = date(2026, 3, 16)
        base = date(2026, 1, 1)
        # 50 substantive comments + 100 reactions
        long_msg = "This is a very thoughtful comment that really adds value " * 5
        comments = _make_comments(
            [(base + timedelta(days=i % 74)).isoformat() for i in range(50)],
            [long_msg] * 50,
        )
        reactions = _make_reactions(
            [(base + timedelta(days=i % 74)).isoformat() for i in range(100)],
        )
        zip_data = ZipData(comments=comments, reactions=reactions)
        dim = score_dimension_3(zip_data, ref)

        quality = next(s for s in dim.sub_dimensions
                       if s.name == "Engagement Quality Score")
        # 50 substantive + 100 × 0.25 = 75 → band 3 (75–199)
        assert quality.score == 3
        assert quality.raw_value == 75.0


# ============================================================
# Dimension 4: rubric input
# ============================================================

class TestDimension4:
    def test_perfect(self):
        dim = build_dimension_4_from_rubrics({
            "Topic Consistency": 5,
            "Profile-Content Coherence": 5,
        })
        # (10 - 2) / (10 - 2) = 1.0, × 0.15 × 100 = 15.0
        assert dim.contribution == 15.0

    def test_minimum(self):
        dim = build_dimension_4_from_rubrics({
            "Topic Consistency": 1,
            "Profile-Content Coherence": 1,
        })
        assert dim.contribution == 0.0

    def test_mixed(self):
        dim = build_dimension_4_from_rubrics({
            "Topic Consistency": 4,
            "Profile-Content Coherence": 3,
        })
        # (7 - 2) / (10 - 2) = 0.625, × 0.15 × 100 = 9.375
        assert dim.contribution == 9.38  # rounded


# ============================================================
# Composite + band
# ============================================================

class TestComposite:
    def test_sum_of_contributions(self):
        """Composite should be the sum of dimension contributions."""
        profile, positions = _make_profile()
        dim1 = build_dimension_1_from_rubrics(
            {n: 3 for n in ["Headline Clarity", "About Section Coherence",
             "Experience Description Quality", "Profile Completeness",
             "Identity Clarity"]},
            ZipData(profile=profile, positions=positions),
        )
        dim4 = build_dimension_4_from_rubrics(
            {"Topic Consistency": 3, "Profile-Content Coherence": 3},
        )

        # Use simple sub-dimension scores for dim2/dim3
        dim2_sub = SubDimensionScore(
            name="test", score=3, scale="0-5",
            method=ScoringMethod.QUANTITATIVE,
            confidence=ConfidenceLabel.CONFIRMED,
        )
        from backend.scoring.engine import _build_dimension
        dim2 = _build_dimension("Dim2", 0.30, ConfidenceLabel.CONFIRMED,
                                [dim2_sub] * 4, 0, 5)
        dim3 = _build_dimension("Dim3", 0.20, ConfidenceLabel.CONFIRMED,
                                [dim2_sub] * 2, 0, 5)

        composite = compute_composite([dim1, dim2, dim3, dim4])
        expected = dim1.contribution + dim2.contribution + dim3.contribution + dim4.contribution
        assert composite == round(expected, 2)


# ============================================================
# Pressure test: Andrew Segars → 77.6 → Strong
# ============================================================

class TestAndrewPressureTest:
    """Validate against the known pressure-test result from PRODUCT_CONTEXT.md.

    Andrew's scores:
    - Dim 1: contribution 22.75% → normalized (22.75 / 35) = 0.65
    - Dim 2: contribution 25.50% → normalized (25.50 / 30) = 0.85
    - Dim 3: contribution 20.00% → normalized (20.00 / 20) = 1.0
    - Dim 4: contribution 9.38%  → normalized (9.38 / 15) = 0.625
    - Composite: 77.63 → rounds to 77.63, band = Strong

    We can back-calculate rubric scores:
    Dim 1: normalized 0.65 = (sum - 5) / 20, so sum = 18 → avg 3.6 per rubric
      e.g. scores of [4, 4, 4, 3, 3] = 18
    Dim 4: normalized 0.625 = (sum - 2) / 8, so sum = 7 → scores [4, 3]
    """

    def test_andrew_composite(self):
        profile, positions = _make_profile(
            headline="Founder & Strategic Advisor",
            summary="Helping leaders build meaningful digital presence " * 30,
            industry="Management Consulting",
        )

        # Dim 1: rubric scores that yield ~22.75 contribution
        dim1_scores = {
            "Headline Clarity": 4,
            "About Section Coherence": 4,
            "Experience Description Quality": 4,
            "Profile Completeness": 3,
            "Identity Clarity": 3,
        }
        dim1 = build_dimension_1_from_rubrics(
            dim1_scores,
            ZipData(profile=profile, positions=positions),
        )
        # (18 - 5) / (25 - 5) × 35 = 22.75
        assert dim1.contribution == 22.75

        # Dim 4: rubric scores that yield ~9.375 contribution
        dim4_scores = {
            "Topic Consistency": 4,
            "Profile-Content Coherence": 3,
        }
        dim4 = build_dimension_4_from_rubrics(dim4_scores)
        # (7 - 2) / (10 - 2) × 15 = 9.375 → 9.38
        assert dim4.contribution == 9.38

        # Dim 2 and Dim 3: we need sub-scores that yield the right contributions.
        # Dim 2: 25.50 contribution → normalized 0.85 → sum = 17 out of 20
        # e.g. [5, 4, 4, 4] = 17
        from backend.scoring.engine import _build_dimension
        dim2_subs = [
            SubDimensionScore(name="History Depth", score=5, scale="0-5",
                              method=ScoringMethod.QUANTITATIVE, confidence=ConfidenceLabel.PROXY),
            SubDimensionScore(name="Recency", score=4, scale="0-5",
                              method=ScoringMethod.QUANTITATIVE_HYBRID, confidence=ConfidenceLabel.PROXY),
            SubDimensionScore(name="Continuity", score=4, scale="0-5",
                              method=ScoringMethod.QUANTITATIVE, confidence=ConfidenceLabel.CONFIRMED),
            SubDimensionScore(name="Posting Presence", score=4, scale="0-5",
                              method=ScoringMethod.QUANTITATIVE, confidence=ConfidenceLabel.CONFIRMED),
        ]
        dim2 = _build_dimension("Behavioral Signal Strength", 0.30,
                                ConfidenceLabel.CONFIRMED, dim2_subs, 0, 5)
        # 17/20 × 30 = 25.5
        assert dim2.contribution == 25.5

        # Dim 3: 20.00 contribution → normalized 1.0 → sum = 10 out of 10
        # [5, 5]
        dim3_subs = [
            SubDimensionScore(name="Outbound Engagement Presence", score=5, scale="0-5",
                              method=ScoringMethod.QUANTITATIVE, confidence=ConfidenceLabel.CONFIRMED),
            SubDimensionScore(name="Engagement Quality Score", score=5, scale="0-5",
                              method=ScoringMethod.QUANTITATIVE, confidence=ConfidenceLabel.INFERRED),
        ]
        dim3 = _build_dimension("Behavioral Signal Quality", 0.20,
                                ConfidenceLabel.CONFIRMED, dim3_subs, 0, 5)
        assert dim3.contribution == 20.0

        composite = compute_composite([dim1, dim2, dim3, dim4])
        assert composite == 77.63
        assert assign_band(composite) == SignalBand.STRONG


# ============================================================
# Forward Brief data extraction
# ============================================================

class TestForwardBrief:
    def test_empty_data(self):
        fb = compute_forward_brief(ZipData(), None, date(2026, 3, 16))
        assert fb.quantitative.follower_count is None
        assert fb.qualitative_flags.visual_professionalism.photo_present is False

    def test_with_xlsx_data(self):
        xlsx = XlsxData(
            discovery=DiscoverySummary(
                period="2025-03-17 to 2026-03-16",
                impressions=500000,
                members_reached=285000,
            ),
            followers=FollowersData(
                total_followers=12500,
                rows=[FollowersRow(date=f"2026-01-{i+1:02d}", new_followers=3)
                      for i in range(30)],
            ),
            top_posts=[
                TopPostItem(post_url="url1", impressions=28500, engagements=1200),
            ],
            demographics=DemographicsData(
                job_titles={"Senior": 0.32, "Manager": 0.28},
                industries={"Technology": 0.35, "Finance": 0.20},
                locations={"United States": 0.45},
            ),
        )
        fb = compute_forward_brief(ZipData(), xlsx, date(2026, 3, 16))
        assert fb.quantitative.follower_count == 12500
        assert fb.quantitative.unique_members_reached == 285000
        assert fb.quantitative.top_post_impressions == 28500
        assert fb.quantitative.audience_seniority == {"Senior": 0.32, "Manager": 0.28}
        assert len(fb.quantitative.audience_industries) == 2

    def test_photo_detection(self):
        zip_data = ZipData(
            rich_media=[RichMediaItem(type="You changed your profile photo", date_time_raw="Jan 5, 2024")],
        )
        fb = compute_forward_brief(zip_data, None, date(2026, 3, 16))
        assert fb.qualitative_flags.visual_professionalism.photo_present is True

    def test_cta_detection(self):
        profile = ProfileData(summary="Reach out to discuss how we can work together.")
        zip_data = ZipData(profile=profile)
        fb = compute_forward_brief(zip_data, None, date(2026, 3, 16))
        assert fb.qualitative_flags.engagement_invitation.cta_in_about is True


# ============================================================
# Full pipeline
# ============================================================

class TestRunScoring:
    def test_returns_complete_output(self):
        profile, positions = _make_profile()
        zip_data = ZipData(profile=profile, positions=positions)
        result = run_scoring(
            zip_data=zip_data,
            xlsx_data=None,
            dim1_rubric_scores={n: 3 for n in [
                "Headline Clarity", "About Section Coherence",
                "Experience Description Quality", "Profile Completeness",
                "Identity Clarity",
            ]},
            dim4_rubric_scores={
                "Topic Consistency": 3,
                "Profile-Content Coherence": 3,
            },
            ref_date=date(2026, 3, 16),
        )
        assert result.scored_dimensions.composite >= 0
        assert result.scored_dimensions.composite <= 100
        assert result.scored_dimensions.band in SignalBand
        assert len(result.scored_dimensions.dimensions) == 4
        assert result.forward_brief_data is not None

    def test_serializes_to_json(self):
        """Output must be JSON-serializable for DB storage."""
        profile, positions = _make_profile()
        zip_data = ZipData(profile=profile, positions=positions)
        result = run_scoring(
            zip_data=zip_data,
            xlsx_data=None,
            dim1_rubric_scores={n: 3 for n in [
                "Headline Clarity", "About Section Coherence",
                "Experience Description Quality", "Profile Completeness",
                "Identity Clarity",
            ]},
            dim4_rubric_scores={
                "Topic Consistency": 3,
                "Profile-Content Coherence": 3,
            },
            ref_date=date(2026, 3, 16),
        )
        import json
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        assert "scored_dimensions" in parsed
        assert "forward_brief_data" in parsed
        assert parsed["scored_dimensions"]["band"] in [b.value for b in SignalBand]
