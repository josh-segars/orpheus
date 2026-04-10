"""Tests for the narrative generation agent.

Tests cover prompt assembly, response parsing, advisor config handling,
and data formatting — everything except the actual Claude API call.
"""

import json
import pytest

from backend.agents.narrative import (
    DEFAULT_NARRATIVE_CONFIG,
    VOICE_INSTRUCTIONS,
    DIRECTNESS_INSTRUCTIONS,
    MECHANICS_INSTRUCTIONS,
    FOCUS_INSTRUCTIONS,
    EXPECTED_SECTIONS,
    _build_system_prompt,
    _parse_narrative_response,
    _format_scored_dimensions,
    _format_forward_brief_data,
    _format_questionnaire,
    _format_quality_report,
)
from backend.models.quality import (
    DataQualityReport,
    QualityIssue,
    IssueSeverity,
    IssueCategory,
)
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


# ============================================================
# Fixtures — realistic scoring output
# ============================================================

def _make_scoring_output(composite=77.6, band=SignalBand.STRONG):
    """Build a realistic ScoringStageOutput for testing."""
    return ScoringStageOutput(
        scored_dimensions=ScoredDimensions(
            composite=composite,
            band=band,
            dimensions=[
                DimensionScore(
                    name="Profile Signal Clarity",
                    weight=0.35,
                    confidence=ConfidenceLabel.CONFIRMED,
                    normalized_score=0.650,
                    contribution=22.75,
                    sub_dimensions=[
                        SubDimensionScore(name="Headline Clarity", score=4, scale="1-5", method=ScoringMethod.RUBRIC),
                        SubDimensionScore(name="About Section Coherence", score=4, scale="1-5", method=ScoringMethod.RUBRIC),
                        SubDimensionScore(name="Experience Description Quality", score=3, scale="1-5", method=ScoringMethod.RUBRIC),
                        SubDimensionScore(name="Profile Completeness", score=3, scale="1-5", method=ScoringMethod.RUBRIC),
                        SubDimensionScore(name="Identity Clarity", score=4, scale="1-5", method=ScoringMethod.RUBRIC),
                    ],
                    completeness_floor_applied=False,
                ),
                DimensionScore(
                    name="Behavioral Signal Strength",
                    weight=0.30,
                    confidence=ConfidenceLabel.CONFIRMED,
                    normalized_score=0.850,
                    contribution=25.50,
                    sub_dimensions=[
                        SubDimensionScore(name="History Depth", score=5, scale="0-5", method=ScoringMethod.QUANTITATIVE, raw_value=750),
                        SubDimensionScore(name="Recency", score=4, scale="0-5", method=ScoringMethod.QUANTITATIVE_HYBRID, raw_value=120),
                        SubDimensionScore(name="Continuity", score=4, scale="0-5", method=ScoringMethod.QUANTITATIVE, raw_value=42),
                        SubDimensionScore(name="Posting Presence", score=4, scale="0-5", method=ScoringMethod.QUANTITATIVE, raw_value=1.5),
                    ],
                ),
                DimensionScore(
                    name="Behavioral Signal Quality",
                    weight=0.20,
                    confidence=ConfidenceLabel.CONFIRMED,
                    normalized_score=1.0,
                    contribution=20.0,
                    sub_dimensions=[
                        SubDimensionScore(name="Outbound Engagement Presence", score=5, scale="0-5", method=ScoringMethod.QUANTITATIVE, raw_value=1200),
                        SubDimensionScore(name="Engagement Quality Score", score=5, scale="0-5", method=ScoringMethod.QUANTITATIVE, raw_value=480),
                    ],
                ),
                DimensionScore(
                    name="Profile-Behavior Alignment",
                    weight=0.15,
                    confidence=ConfidenceLabel.INFERRED,
                    normalized_score=0.625,
                    contribution=9.38,
                    sub_dimensions=[
                        SubDimensionScore(name="Topic Consistency", score=4, scale="1-5", method=ScoringMethod.RUBRIC),
                        SubDimensionScore(name="Profile-Content Coherence", score=3, scale="1-5", method=ScoringMethod.RUBRIC),
                    ],
                ),
            ],
        ),
        forward_brief_data=ForwardBriefData(
            quantitative=ForwardBriefQuantitative(
                follower_count=12500,
                follower_growth_rate=45.2,
                unique_members_reached=285000,
                avg_impressions_per_post=3200,
                avg_engagement_rate=0.042,
                top_post_impressions=28500,
                audience_seniority={"Senior": 0.32, "Manager": 0.28, "Director": 0.15},
                audience_industries=[
                    AudienceSegment(name="Technology", pct=0.35),
                    AudienceSegment(name="Financial Services", pct=0.18),
                ],
                audience_geography=[
                    AudienceSegment(name="United States", pct=0.45),
                    AudienceSegment(name="United Kingdom", pct=0.12),
                ],
                top_organizations=["Google", "Microsoft", "Amazon"],
                avg_comment_length_words=26.3,
                longest_posting_gap_weeks=2,
                zero_post_week_pct=0.29,
            ),
            qualitative_flags=QualitativeFlags(
                viewer_actor_affinity=ViewerActorAffinity(concentrated=False, top_targets=[]),
                visual_professionalism=VisualProfessionalism(photo_present=True),
                engagement_invitation=EngagementInvitation(
                    services_present=False,
                    contact_visible=True,
                    cta_in_about=True,
                ),
            ),
        ),
    )


def _make_valid_response():
    """Build a valid Claude response JSON string."""
    return json.dumps({
        "sections": [
            {"section": "Profile Signal Clarity", "narrative": "The profile presents a clear professional identity. " * 10},
            {"section": "Behavioral Signal Strength", "narrative": "Activity levels over the trailing period show. " * 10},
            {"section": "Behavioral Signal Quality", "narrative": "The engagement pattern demonstrates. " * 8},
            {"section": "Profile-Behavior Alignment", "narrative": "Content and profile signals are aligned. " * 8},
            {"section": "forward_brief", "narrative": "## Reach\nFollower base of 12,500. " * 20},
        ]
    })


# ============================================================
# Test: Response parsing
# ============================================================

class TestParseResponse:

    def test_valid_response(self):
        result = _parse_narrative_response(_make_valid_response())
        assert set(result.keys()) == EXPECTED_SECTIONS
        assert all(isinstance(v, str) and len(v) > 0 for v in result.values())

    def test_with_code_fences(self):
        raw = "```json\n" + _make_valid_response() + "\n```"
        result = _parse_narrative_response(raw)
        assert set(result.keys()) == EXPECTED_SECTIONS

    def test_missing_section_raises(self):
        data = {
            "sections": [
                {"section": "Profile Signal Clarity", "narrative": "Some text."},
                {"section": "Behavioral Signal Strength", "narrative": "Some text."},
                # Missing 3 sections
            ]
        }
        with pytest.raises(ValueError, match="Missing sections"):
            _parse_narrative_response(json.dumps(data))

    def test_empty_narrative_raises(self):
        data = {
            "sections": [
                {"section": "Profile Signal Clarity", "narrative": ""},
                {"section": "Behavioral Signal Strength", "narrative": "Text."},
                {"section": "Behavioral Signal Quality", "narrative": "Text."},
                {"section": "Profile-Behavior Alignment", "narrative": "Text."},
                {"section": "forward_brief", "narrative": "Text."},
            ]
        }
        with pytest.raises(ValueError, match="Empty narrative"):
            _parse_narrative_response(json.dumps(data))

    def test_unexpected_section_raises(self):
        data = {
            "sections": [
                {"section": "Made Up Section", "narrative": "Text."},
                {"section": "Profile Signal Clarity", "narrative": "Text."},
                {"section": "Behavioral Signal Strength", "narrative": "Text."},
                {"section": "Behavioral Signal Quality", "narrative": "Text."},
                {"section": "Profile-Behavior Alignment", "narrative": "Text."},
                {"section": "forward_brief", "narrative": "Text."},
            ]
        }
        with pytest.raises(ValueError, match="Unexpected section"):
            _parse_narrative_response(json.dumps(data))

    def test_missing_sections_key_raises(self):
        with pytest.raises(ValueError, match="missing 'sections'"):
            _parse_narrative_response('{"narratives": []}')

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_narrative_response("not json at all")

    def test_whitespace_only_narrative_raises(self):
        data = {
            "sections": [
                {"section": "Profile Signal Clarity", "narrative": "   \n  "},
                {"section": "Behavioral Signal Strength", "narrative": "Text."},
                {"section": "Behavioral Signal Quality", "narrative": "Text."},
                {"section": "Profile-Behavior Alignment", "narrative": "Text."},
                {"section": "forward_brief", "narrative": "Text."},
            ]
        }
        with pytest.raises(ValueError, match="Empty narrative"):
            _parse_narrative_response(json.dumps(data))


# ============================================================
# Test: System prompt assembly
# ============================================================

class TestSystemPrompt:

    def test_default_config(self):
        prompt = _build_system_prompt()
        assert "third-person" in prompt.lower() or "third person" in prompt.lower()
        assert "coaching" in prompt.lower() or "could" in prompt
        assert "Do NOT reference" in prompt  # behind_curtain mechanics

    def test_second_person_voice(self):
        prompt = _build_system_prompt({"voice": "second_person_direct"})
        assert "second person" in prompt.lower()
        assert "Your headline" in prompt or "Your profile" in prompt

    def test_prescriptive_style(self):
        prompt = _build_system_prompt({"recommendation_style": "prescriptive"})
        assert "clear, specific instructions" in prompt.lower() or "action verbs" in prompt.lower()

    def test_technical_mechanics(self):
        prompt = _build_system_prompt({"system_mechanics": "technical"})
        assert "retrieval" in prompt.lower()
        assert "embeddings" in prompt.lower() or "embedding" in prompt.lower()

    def test_practice_focus(self):
        prompt = _build_system_prompt({"practice_focus": "thought_leadership"})
        assert "content quality" in prompt.lower() or "topic consistency" in prompt.lower()

    def test_custom_instructions(self):
        prompt = _build_system_prompt({"custom_instructions": "Always mention the client's industry."})
        assert "Always mention the client's industry" in prompt

    def test_unknown_voice_falls_back(self):
        prompt = _build_system_prompt({"voice": "nonexistent_voice"})
        # Should fall back to third_person_neutral
        assert "third-person" in prompt.lower() or "third person" in prompt.lower()

    def test_no_focus_when_none(self):
        prompt = _build_system_prompt({"practice_focus": None})
        # Should not contain any focus-specific instructions
        assert "thought_leadership" not in prompt
        assert "business_development" not in prompt

    def test_all_options_combined(self):
        prompt = _build_system_prompt({
            "voice": "second_person_formal",
            "recommendation_style": "balanced",
            "system_mechanics": "light_reference",
            "practice_focus": "career_transition",
            "custom_instructions": "Keep paragraphs short.",
        })
        assert "formal" in prompt.lower()
        assert "Blend observation" in prompt or "blend" in prompt.lower()
        assert "repositioning" in prompt.lower()
        assert "Keep paragraphs short" in prompt

    def test_output_format_present(self):
        prompt = _build_system_prompt()
        assert '"section": "Profile Signal Clarity"' in prompt
        assert '"section": "forward_brief"' in prompt
        assert "150" in prompt and "300" in prompt  # word counts


# ============================================================
# Test: Data formatting
# ============================================================

class TestFormatScoredDimensions:

    def test_contains_composite(self):
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        assert "77.6" in text
        assert "Strong" in text

    def test_contains_all_dimensions(self):
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        assert "Profile Signal Clarity" in text
        assert "Behavioral Signal Strength" in text
        assert "Behavioral Signal Quality" in text
        assert "Profile-Behavior Alignment" in text

    def test_contains_sub_dimensions(self):
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        assert "Headline Clarity" in text
        assert "History Depth" in text
        assert "Topic Consistency" in text

    def test_contains_raw_values(self):
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        assert "raw value: 750" in text  # History Depth

    def test_completeness_floor_flag(self):
        output = _make_scoring_output()
        # Modify to trigger floor
        output.scored_dimensions.dimensions[0].completeness_floor_applied = True
        text = _format_scored_dimensions(output)
        assert "COMPLETENESS FLOOR APPLIED" in text


class TestFormatForwardBriefData:

    def test_contains_reach_metrics(self):
        output = _make_scoring_output()
        text = _format_forward_brief_data(output)
        assert "12,500" in text  # follower count
        assert "45.2" in text  # growth rate
        assert "285,000" in text  # members reached

    def test_contains_audience_data(self):
        output = _make_scoring_output()
        text = _format_forward_brief_data(output)
        assert "Technology" in text
        assert "United States" in text
        assert "Senior" in text

    def test_contains_qualitative_flags(self):
        output = _make_scoring_output()
        text = _format_forward_brief_data(output)
        assert "distributed" in text  # not concentrated
        assert "present" in text  # photo present
        assert "CTA in About: yes" in text

    def test_handles_missing_optional_fields(self):
        output = ScoringStageOutput(
            scored_dimensions=_make_scoring_output().scored_dimensions,
            forward_brief_data=ForwardBriefData(
                quantitative=ForwardBriefQuantitative(),  # all None
                qualitative_flags=QualitativeFlags(
                    viewer_actor_affinity=ViewerActorAffinity(concentrated=False, top_targets=[]),
                    visual_professionalism=VisualProfessionalism(photo_present=False),
                    engagement_invitation=EngagementInvitation(
                        services_present=False, contact_visible=False, cta_in_about=False
                    ),
                ),
            ),
        )
        text = _format_forward_brief_data(output)
        # Should not crash, should still contain qualitative flags
        assert "absent" in text  # photo absent
        assert "QUALITATIVE FLAGS" in text


class TestFormatQuestionnaire:

    def test_formats_simple_answers(self):
        q = {
            "Q1": "I lead digital transformation initiatives",
            "Q8": "C-suite executives in healthcare",
        }
        text = _format_questionnaire(q)
        assert "digital transformation" in text
        assert "healthcare" in text

    def test_formats_list_answers(self):
        q = {"Q12": ["Build thought leadership", "Generate leads", "Expand network"]}
        text = _format_questionnaire(q)
        assert "Build thought leadership" in text
        assert "Generate leads" in text

    def test_empty_questionnaire(self):
        text = _format_questionnaire({})
        assert "No questionnaire" in text

    def test_none_questionnaire(self):
        text = _format_questionnaire(None)
        assert "No questionnaire" in text


# ============================================================
# Test: Config defaults
# ============================================================

class TestConfigDefaults:

    def test_default_config_keys(self):
        assert "voice" in DEFAULT_NARRATIVE_CONFIG
        assert "recommendation_style" in DEFAULT_NARRATIVE_CONFIG
        assert "system_mechanics" in DEFAULT_NARRATIVE_CONFIG
        assert "practice_focus" in DEFAULT_NARRATIVE_CONFIG
        assert "custom_instructions" in DEFAULT_NARRATIVE_CONFIG

    def test_all_voice_options_have_instructions(self):
        for key in VOICE_INSTRUCTIONS:
            assert len(VOICE_INSTRUCTIONS[key]) > 50

    def test_all_directness_options_have_instructions(self):
        for key in DIRECTNESS_INSTRUCTIONS:
            assert len(DIRECTNESS_INSTRUCTIONS[key]) > 50

    def test_all_mechanics_options_have_instructions(self):
        for key in MECHANICS_INSTRUCTIONS:
            assert len(MECHANICS_INSTRUCTIONS[key]) > 50

    def test_all_focus_options_have_instructions(self):
        for key in FOCUS_INSTRUCTIONS:
            assert len(FOCUS_INSTRUCTIONS[key]) > 50

    def test_expected_sections_count(self):
        assert len(EXPECTED_SECTIONS) == 5
        assert "forward_brief" in EXPECTED_SECTIONS


# ============================================================
# Test: Edge cases
# ============================================================

class TestEdgeCases:

    def test_weak_band_output(self):
        output = _make_scoring_output(composite=15.0, band=SignalBand.WEAK)
        text = _format_scored_dimensions(output)
        assert "15.0" in text
        assert "Weak" in text

    def test_exceptional_band_output(self):
        output = _make_scoring_output(composite=95.0, band=SignalBand.EXCEPTIONAL)
        text = _format_scored_dimensions(output)
        assert "95.0" in text
        assert "Exceptional" in text


# ============================================================
# Test: Quality report formatting
# ============================================================

class TestFormatQualityReport:

    def test_none_report(self):
        result = _format_quality_report(None)
        assert result == ""

    def test_empty_report(self):
        report = DataQualityReport()
        result = _format_quality_report(report)
        assert result == ""

    def test_info_only_issues_excluded(self):
        """Info-level issues should not appear in the prompt."""
        report = DataQualityReport()
        report.add(
            severity=IssueSeverity.INFO,
            category=IssueCategory.MISSING_FIELD,
            source="Profile.csv",
            message="No profile photo detected",
            impact="Visual professionalism flag in Forward Brief",
        )
        result = _format_quality_report(report)
        assert result == ""

    def test_warning_issues_included(self):
        report = DataQualityReport()
        report.add(
            severity=IssueSeverity.WARNING,
            category=IssueCategory.PARSE_FAILURE,
            source="Shares.csv",
            message="12 share dates could not be parsed",
            impact="Consistency dimension: active weeks count may be understated",
            rows_affected=12,
        )
        result = _format_quality_report(report)
        assert "WARNING" in result
        assert "12 share dates" in result
        assert "Shares.csv" in result
        assert "Rows affected: 12" in result
        assert "Consistency dimension" in result

    def test_critical_issues_included(self):
        report = DataQualityReport()
        report.add(
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.MISSING_FILE,
            source="ZIP archive",
            message="Shares.csv not found — this may be a Basic export instead of Complete",
            impact="Behavioral Signal Strength and Quality dimensions cannot be scored",
        )
        result = _format_quality_report(report)
        assert "CRITICAL" in result
        assert "Shares.csv not found" in result
        assert "cannot be scored" in result

    def test_mixed_severities_filters_info(self):
        """Only warning and critical should appear; info should be filtered out."""
        report = DataQualityReport()
        report.add(
            severity=IssueSeverity.INFO,
            category=IssueCategory.MISSING_FIELD,
            source="Profile.csv",
            message="No profile photo",
            impact="Forward Brief visual professionalism flag",
        )
        report.add(
            severity=IssueSeverity.WARNING,
            category=IssueCategory.DATE_RANGE,
            source="Shares.csv",
            message="Data covers only 120 days (less than 180-day recommended minimum)",
            impact="Consistency metrics may not be representative",
        )
        report.add(
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.EMPTY_DATA,
            source="Comments.csv",
            message="Comments.csv is present but contains 0 parseable rows",
            impact="Comment-based metrics will be zero",
            rows_affected=0,
        )
        result = _format_quality_report(report)
        # Info excluded
        assert "No profile photo" not in result
        # Warning included
        assert "120 days" in result
        # Critical included
        assert "0 parseable rows" in result

    def test_contains_guidance_text(self):
        """The formatted report should include instructions for Claude."""
        report = DataQualityReport()
        report.add(
            severity=IssueSeverity.WARNING,
            category=IssueCategory.MISSING_FIELD,
            source="Profile.csv",
            message="Headline is empty",
            impact="Profile Signal Clarity may be understated",
        )
        result = _format_quality_report(report)
        assert "Acknowledge relevant limitations" in result
        assert "Do not fabricate" in result

    def test_rows_affected_omitted_when_none(self):
        report = DataQualityReport()
        report.add(
            severity=IssueSeverity.WARNING,
            category=IssueCategory.MISSING_FIELD,
            source="Profile.csv",
            message="Summary field is empty",
            impact="Profile Signal Clarity completeness floor",
        )
        result = _format_quality_report(report)
        assert "Rows affected" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
