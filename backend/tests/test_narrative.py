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
    MILESTONE_GROWTH_FACTORS,
    MILESTONE_STARTERS,
    QUANTITATIVE_METRIC_LABELS,
    SUPPRESSED_RAW_VALUE_SUB_DIMS,
    USER_PROMPT_TEMPLATE,
    MilestoneTarget,
    NarrativeResult,
    build_milestone_targets,
    _build_system_prompt,
    _format_milestone_targets,
    _growth_target,
    _parse_cheat_sheet_payload,
    _parse_narrative_response,
    _format_scored_dimensions,
    _format_forward_brief_data,
    _format_profile_excerpt,
    _format_questionnaire,
    _format_quality_report,
)
from backend.ingestion.types import (
    ZipData,
    ProfileData,
    PositionData,
    ShareItem,
    CommentItem,
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

def _make_scoring_output(composite=77.6, band=SignalBand.TUNED):
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
                    band=SignalBand.TUNED,  # 0.650 × 100 = 65 → Tuned
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
                    band=SignalBand.RESONANT,  # 0.850 × 100 = 85 → Resonant
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
                    band=SignalBand.RESONANT,  # 1.0 × 100 = 100 → Resonant
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
                    band=SignalBand.TUNING,  # 0.625 × 100 = 62.5 → Tuning
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
    """Build a valid Claude response JSON string.

    ORPHEUS-68 shape: 4 dimension sections (no forward_brief), each with a
    required `summary` teaser plus the combined messaging `narrative`.
    """
    return json.dumps({
        "sections": [
            {"section": "Profile Signal Clarity", "summary": "The profile reads clearly overall.", "narrative": "The profile presents a clear professional identity. " * 10},
            {"section": "Behavioral Signal Strength", "summary": "Activity is consistent and recent.", "narrative": "Activity levels over the trailing period show. " * 10},
            {"section": "Behavioral Signal Quality", "summary": "Engagement quality is substantive.", "narrative": "The engagement pattern demonstrates. " * 8},
            {"section": "Profile-Behavior Alignment", "summary": "Content matches the declared identity.", "narrative": "Content and profile signals are aligned. " * 8},
        ]
    })


# ============================================================
# Test: Response parsing
# ============================================================

class TestParseResponse:
    """ORPHEUS-21 changed the return type from dict[str, str] to a
    NarrativeResult NamedTuple — existing assertions navigate through
    `.sections` now, but the section-only validation behavior on the
    no-scoring-output path is unchanged.
    """

    def test_valid_response(self):
        result = _parse_narrative_response(_make_valid_response())
        assert isinstance(result, NarrativeResult)
        assert set(result.sections.keys()) == EXPECTED_SECTIONS
        assert all(isinstance(v, str) and len(v) > 0 for v in result.sections.values())
        # ORPHEUS-68: summaries parsed alongside narratives, same keys.
        assert set(result.summaries.keys()) == EXPECTED_SECTIONS
        assert all(isinstance(v, str) and len(v) > 0 for v in result.summaries.values())
        # No scoring_output passed → sub_dimensions parsed best-effort; the
        # legacy fixture doesn't include the array, so result is empty here.
        assert result.sub_dimensions == {}
        # Same best-effort posture for cheat_sheet (ORPHEUS-60): the legacy
        # fixture omits it, parser returns None rather than raising so
        # pre-60 callers still work.
        assert result.cheat_sheet is None
        # ORPHEUS-96: legacy fixture omits cta_present → None (best-effort).
        assert result.cta_present is None

    def test_cta_present_parsed_true(self):
        data = {
            "sections": [
                {"section": s, "summary": "S.", "narrative": "Text."}
                for s in EXPECTED_SECTIONS
            ],
            "cta_present": True,
        }
        result = _parse_narrative_response(json.dumps(data))
        assert result.cta_present is True

    def test_cta_present_parsed_false(self):
        data = {
            "sections": [
                {"section": s, "summary": "S.", "narrative": "Text."}
                for s in EXPECTED_SECTIONS
            ],
            "cta_present": False,
        }
        result = _parse_narrative_response(json.dumps(data))
        assert result.cta_present is False

    def test_cta_present_non_bool_is_none(self):
        # A non-bool (e.g. a string) is treated as absent rather than raising.
        data = {
            "sections": [
                {"section": s, "summary": "S.", "narrative": "Text."}
                for s in EXPECTED_SECTIONS
            ],
            "cta_present": "yes",
        }
        result = _parse_narrative_response(json.dumps(data))
        assert result.cta_present is None

    def test_with_code_fences(self):
        raw = "```json\n" + _make_valid_response() + "\n```"
        result = _parse_narrative_response(raw)
        assert set(result.sections.keys()) == EXPECTED_SECTIONS

    def test_missing_section_raises(self):
        data = {
            "sections": [
                {"section": "Profile Signal Clarity", "summary": "S.", "narrative": "Some text."},
                {"section": "Behavioral Signal Strength", "summary": "S.", "narrative": "Some text."},
                # Missing 2 sections
            ]
        }
        with pytest.raises(ValueError, match="Missing sections"):
            _parse_narrative_response(json.dumps(data))

    def test_empty_narrative_raises(self):
        data = {
            "sections": [
                {"section": "Profile Signal Clarity", "summary": "S.", "narrative": ""},
                {"section": "Behavioral Signal Strength", "summary": "S.", "narrative": "Text."},
                {"section": "Behavioral Signal Quality", "summary": "S.", "narrative": "Text."},
                {"section": "Profile-Behavior Alignment", "summary": "S.", "narrative": "Text."},
            ]
        }
        with pytest.raises(ValueError, match="Empty narrative"):
            _parse_narrative_response(json.dumps(data))

    def test_unexpected_section_raises(self):
        data = {
            "sections": [
                {"section": "Made Up Section", "summary": "S.", "narrative": "Text."},
                {"section": "Profile Signal Clarity", "summary": "S.", "narrative": "Text."},
                {"section": "Behavioral Signal Strength", "summary": "S.", "narrative": "Text."},
                {"section": "Behavioral Signal Quality", "summary": "S.", "narrative": "Text."},
                {"section": "Profile-Behavior Alignment", "summary": "S.", "narrative": "Text."},
            ]
        }
        with pytest.raises(ValueError, match="Unexpected section"):
            _parse_narrative_response(json.dumps(data))

    def test_forward_brief_section_raises(self):
        """ORPHEUS-68: a stray forward_brief entry is an unexpected section
        — a half-migrated Claude response should retry, not silently ship
        the old shape."""
        data = {
            "sections": [
                {"section": "Profile Signal Clarity", "summary": "S.", "narrative": "Text."},
                {"section": "Behavioral Signal Strength", "summary": "S.", "narrative": "Text."},
                {"section": "Behavioral Signal Quality", "summary": "S.", "narrative": "Text."},
                {"section": "Profile-Behavior Alignment", "summary": "S.", "narrative": "Text."},
                {"section": "forward_brief", "summary": "S.", "narrative": "## Reach\nText."},
            ]
        }
        with pytest.raises(ValueError, match="Unexpected section"):
            _parse_narrative_response(json.dumps(data))

    def test_missing_summary_raises(self):
        data = json.loads(_make_valid_response())
        del data["sections"][0]["summary"]
        with pytest.raises(ValueError, match="summary"):
            _parse_narrative_response(json.dumps(data))

    def test_empty_summary_raises(self):
        data = json.loads(_make_valid_response())
        data["sections"][2]["summary"] = "   "
        with pytest.raises(ValueError, match="summary"):
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
                {"section": "Profile Signal Clarity", "summary": "S.", "narrative": "   \n  "},
                {"section": "Behavioral Signal Strength", "summary": "S.", "narrative": "Text."},
                {"section": "Behavioral Signal Quality", "summary": "S.", "narrative": "Text."},
                {"section": "Profile-Behavior Alignment", "summary": "S.", "narrative": "Text."},
            ]
        }
        with pytest.raises(ValueError, match="Empty narrative"):
            _parse_narrative_response(json.dumps(data))


# ============================================================
# Test: System prompt assembly
# ============================================================

class TestSystemPrompt:

    def test_default_config(self):
        # ORPHEUS-77: the platform default voice is second_person_direct.
        prompt = _build_system_prompt()
        assert "second person" in prompt.lower()
        assert "Address the client directly" in prompt
        assert "coaching" in prompt.lower() or "could" in prompt
        assert "Do NOT reference" in prompt  # behind_curtain mechanics

    def test_second_person_voice(self):
        prompt = _build_system_prompt({"voice": "second_person_direct"})
        assert "second person" in prompt.lower()
        assert "Your headline" in prompt or "Your profile" in prompt

    def test_third_person_voice_still_selectable(self):
        # ORPHEUS-77 flipped the default but kept third_person_neutral as a
        # selectable per-advisor option (advisors.narrative_config).
        prompt = _build_system_prompt({"voice": "third_person_neutral"})
        assert "third-person" in prompt.lower() or "third person" in prompt.lower()
        assert "an advisor can present and personalize" in prompt

    def test_score_calibration_examples_in_second_person(self):
        # ORPHEUS-77 register audit: the static score-to-narrative examples
        # match the platform-default second-person register, and the prompt
        # carries the Voice-section-wins precedence note for advisors who
        # select a different voice.
        prompt = _build_system_prompt()
        assert "Your headline does not communicate" in prompt
        assert "The headline does not communicate" not in prompt
        assert "the Voice section wins" in prompt

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
        # Should fall back to the platform default — second_person_direct
        # since ORPHEUS-77.
        assert "Address the client directly" in prompt
        assert "warm" in prompt.lower()

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
        # ORPHEUS-68: forward_brief retired from the output schema; each
        # section entry carries a summary field instead.
        assert '"section": "forward_brief"' not in prompt
        assert '"summary"' in prompt
        # ORPHEUS-66: word floors dropped, ceilings kept — narrative up to
        # ~400 words, summary up to ~40 words.
        assert "up to ~400 words" in prompt
        assert "up to ~40 words" in prompt


# ============================================================
# Test: Data formatting
# ============================================================

class TestFormatScoredDimensions:

    def test_contains_composite(self):
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        assert "77.6" in text
        assert "Tuned" in text

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
        # ORPHEUS-117: the underlying metric is still surfaced, now carrying
        # its unit and window rather than as a bare number.
        assert "750 outbound actions" in text  # History Depth

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
        # ORPHEUS-96: CTA/contact are no longer surfaced as forward-brief
        # hints — the agent determines the CTA from the verbatim About text
        # directly (returned as cta_present), and contact was retired.
        assert "Call-to-action detected" not in text
        assert "Contact info detected" not in text

    def test_services_present_no_longer_surfaced(self):
        # ORPHEUS-96: services_present is unknowable from the ZIP (hardcoded
        # False in the engine), so it must not be surfaced to the narrative
        # agent — it would otherwise assert "absent" for every client.
        output = _make_scoring_output()
        text = _format_forward_brief_data(output)
        # The services_present flag line must be gone. Guard against the
        # specific flag phrasing only — a bare "Services" substring would
        # collide with audience industries like "Financial Services".
        assert "Services section" not in text
        assert "Services section:" not in text
        assert "services_present" not in text

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


class TestFormatProfileExcerpt:
    """ORPHEUS-96: the verbatim profile + content excerpt threaded into the
    narrative prompt so the agent can ground profile-content claims in
    observed text rather than restating a brittle flag."""

    def _zip(self) -> ZipData:
        return ZipData(
            profile=ProfileData(
                headline="Founder, ess3.ai | Former Senior Diplomat",
                summary=(
                    "I'm a former diplomat turned founder. If any of that "
                    "resonates, I'd welcome a conversation. Or, if you're ever "
                    "in Portugal, a meal."
                ),
                industry="Software Development",
                geo_location="Portugal",
                websites="https://ess3.ai",
            ),
            positions=[
                PositionData(
                    company_name="ess3.ai",
                    title="Founder",
                    description="Building AI-powered software around real problems.",
                    started_on="2023",
                ),
            ],
            skills=["AI Strategy", "Diplomacy", "Product"],
            shares=[
                ShareItem(
                    date="2026-05-01",
                    share_commentary="A post about applied AI and trust.",
                ),
                ShareItem(
                    date="2026-04-01",
                    share_commentary="A post about communication and credibility.",
                ),
            ],
            comments=[
                CommentItem(date="2026-05-02", message="Great point on signal clarity."),
            ],
        )

    def test_includes_verbatim_headline_and_about(self):
        text = _format_profile_excerpt(self._zip())
        assert "Founder, ess3.ai | Former Senior Diplomat" in text
        # The conversational CTA is present verbatim so the agent can see it
        # rather than relying on the (wrong) cta_in_about heuristic.
        assert "I'd welcome a conversation" in text

    def test_includes_positions_skills_and_websites(self):
        text = _format_profile_excerpt(self._zip())
        assert "Founder at ess3.ai" in text
        assert "Building AI-powered software" in text
        assert "AI Strategy" in text
        assert "https://ess3.ai" in text

    def test_includes_post_and_comment_sample(self):
        text = _format_profile_excerpt(self._zip())
        assert "applied AI and trust" in text
        assert "signal clarity" in text

    def test_caps_post_sample_count(self):
        z = self._zip()
        z.shares = [
            ShareItem(date=f"2026-01-{i:02d}", share_commentary=f"post number {i}")
            for i in range(1, 60)
        ]
        text = _format_profile_excerpt(z, max_posts=40)
        # Most recent 40 shown (sorted by date desc); the oldest are excluded.
        assert "post number 59" in text  # most recent
        assert "post number 1" not in text  # oldest, beyond the cap

    def test_handles_empty_profile(self):
        text = _format_profile_excerpt(ZipData())
        assert "HEADLINE: [not provided]" in text
        assert "[No original posts with text found" in text


class TestProfileExcerptWiredIntoPrompt:
    """The excerpt + grounding instructions are present in the prompt
    templates (the API call itself is not exercised in unit tests)."""

    def test_user_template_has_profile_section(self):
        assert "Profile Content (verbatim" in USER_PROMPT_TEMPLATE
        assert "{profile_excerpt}" in USER_PROMPT_TEMPLATE

    def test_system_prompt_has_text_wins_rule(self):
        prompt = _build_system_prompt()
        # The flag-override rule must be present so the agent prefers observed
        # text over a brittle heuristic flag (the ORPHEUS-96 fix).
        assert "the profile text wins" in prompt
        assert "verbatim Profile Content" in prompt

    def test_system_prompt_frames_questionnaire_as_goals(self):
        prompt = _build_system_prompt()
        assert "are NOT observations about the profile" in prompt


class TestFormatQuestionnaire:
    """Covers the 9-question intake shape from ORPHEUS-33.

    The formatter prints each question's verbatim text and the user's
    answer in human-readable form. q1/q2 are multi-select arrays;
    q3..q8 are single-select strings; q9 is free text. q1..q4 have a
    parallel `<key>_other` field that's substituted when the user
    picked the literal "Other" option.
    """

    def test_formats_single_select_answer(self):
        q = {
            "q3": "A specific transition or career moment",
            "q9": "Nothing to add",
        }
        text = _format_questionnaire(q)
        # Question text appears verbatim
        assert "What is driving your interest in this engagement now?" in text
        # Answer is rendered after the arrow
        assert "A specific transition or career moment" in text
        # Free-text answer flows through
        assert "Nothing to add" in text

    def test_formats_multi_select_answer(self):
        q = {
            "q2": [
                "Board positions",
                "Speaking opportunities",
                "Thought leadership",
            ],
        }
        text = _format_questionnaire(q)
        # All selected canonical labels appear
        assert "Board positions" in text
        assert "Speaking opportunities" in text
        assert "Thought leadership" in text
        # Semicolon-joined in the rendered line
        assert "Board positions; Speaking opportunities; Thought leadership" in text

    def test_other_text_substituted_for_single_select(self):
        q = {
            "q3": "Other",
            "q3_other": "Preparing for a board search",
        }
        text = _format_questionnaire(q)
        assert "Preparing for a board search" in text
        # Literal "Other" still appears so Claude knows the canonical
        # bucket; the typed text is shown alongside.
        assert "Other (specified:" in text

    def test_other_text_substituted_for_multi_select(self):
        q = {
            "q1": ["Independent consultant, advisor, or principal", "Other"],
            "q1_other": "Operating partner at a PE firm",
        }
        text = _format_questionnaire(q)
        assert "Independent consultant, advisor, or principal" in text
        assert "Operating partner at a PE firm" in text

    def test_other_without_text_marked_as_missing(self):
        # Defensive: the frontend predicate blocks submission in this state,
        # but a draft fetched mid-write could still hit the worker. The
        # formatter shouldn't crash or silently swallow the Other selection.
        q = {"q3": "Other", "q3_other": ""}
        text = _format_questionnaire(q)
        assert "Other (no detail provided)" in text

    def test_unanswered_questions_render_as_missing(self):
        # Partial answers — only q1 is populated. The other 8 should still
        # appear in the prompt context as "[no answer]" so Claude sees the
        # full structure, not just a sparse slice.
        q = {"q1": ["Between roles"]}
        text = _format_questionnaire(q)
        assert "Between roles" in text
        assert "[no answer]" in text
        # All 9 question keys should appear in the rendered output.
        for key in ["Q1.", "Q2.", "Q3.", "Q4.", "Q5.", "Q6.", "Q7.", "Q8.", "Q9."]:
            assert key in text

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

    def test_default_voice_is_second_person_direct(self):
        # ORPHEUS-77: platform default flipped from third_person_neutral.
        assert DEFAULT_NARRATIVE_CONFIG["voice"] == "second_person_direct"

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
        # ORPHEUS-68: forward_brief retired; the 4 dimensions are the only
        # top-level sections.
        assert len(EXPECTED_SECTIONS) == 4
        assert "forward_brief" not in EXPECTED_SECTIONS


# ============================================================
# Test: Edge cases
# ============================================================

class TestEdgeCases:

    def test_dissonant_band_output(self):
        output = _make_scoring_output(composite=15.0, band=SignalBand.DISSONANT)
        text = _format_scored_dimensions(output)
        assert "15.0" in text
        assert "Dissonant" in text

    def test_resonant_band_output(self):
        output = _make_scoring_output(composite=95.0, band=SignalBand.RESONANT)
        text = _format_scored_dimensions(output)
        assert "95.0" in text
        assert "Resonant" in text


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


# ============================================================
# Test: Sub-dimension parsing (ORPHEUS-21)
# ============================================================
#
# The 13 expected sub-dims in _make_scoring_output() carry this score
# distribution:
#
#   Profile Signal Clarity        Headline Clarity              4
#                                 About Section Coherence       4
#                                 Experience Description Quality 3
#                                 Profile Completeness          3
#                                 Identity Clarity              4
#   Behavioral Signal Strength    History Depth                 5
#                                 Recency                       4
#                                 Continuity                    4
#                                 Posting Presence              4
#   Behavioral Signal Quality     Outbound Engagement Presence  5
#                                 Engagement Quality Score      5
#   Profile-Behavior Alignment    Topic Consistency             4
#                                 Profile-Content Coherence     3
#
# Score-aware slot expectations:
#   score 3 → summary + best_practices + improvements  (3 entries)
#   score 4 → summary + improvements                   (7 entries)
#   score 5 → summary only                             (3 entries)


def _sub_dim_entry(
    dimension: str,
    sub_dimension: str,
    score: int,
    *,
    summary: str | None = "Substantive summary text. " * 4,
    best_practices: str | None = None,
    improvements: list[str] | None = None,
) -> dict:
    """Build one sub-dim entry per the wire shape.

    Default slot population matches the conditional curve as updated by
    ORPHEUS-63 (score 0 = full payload, mirroring score 1): BP at scores
    0–3, Improvements at 0–4. Callers can override for negative tests.
    """
    entry: dict = {
        "dimension": dimension,
        "sub_dimension": sub_dimension,
    }
    if summary is not None:
        entry["summary"] = summary
    if best_practices is None and score in (0, 1, 2, 3):
        entry["best_practices"] = "Generic standard for this sub-dimension."
    elif best_practices is not None:
        entry["best_practices"] = best_practices
    if improvements is None and score in (0, 1, 2, 3, 4):
        entry["improvements"] = [
            "Specific action one for this sub-dim.",
            "Specific action two.",
        ]
    elif improvements is not None:
        entry["improvements"] = improvements
    return entry


# Score lookup mirroring _make_scoring_output() so test fixtures can
# generate matching entries without hardcoding 13 calls.
_FIXTURE_SCORES: list[tuple[str, str, int]] = [
    ("Profile Signal Clarity", "Headline Clarity", 4),
    ("Profile Signal Clarity", "About Section Coherence", 4),
    ("Profile Signal Clarity", "Experience Description Quality", 3),
    ("Profile Signal Clarity", "Profile Completeness", 3),
    ("Profile Signal Clarity", "Identity Clarity", 4),
    ("Behavioral Signal Strength", "History Depth", 5),
    ("Behavioral Signal Strength", "Recency", 4),
    ("Behavioral Signal Strength", "Continuity", 4),
    ("Behavioral Signal Strength", "Posting Presence", 4),
    ("Behavioral Signal Quality", "Outbound Engagement Presence", 5),
    ("Behavioral Signal Quality", "Engagement Quality Score", 5),
    ("Profile-Behavior Alignment", "Topic Consistency", 4),
    ("Profile-Behavior Alignment", "Profile-Content Coherence", 3),
]


def _valid_sub_dim_payload() -> list[dict]:
    return [
        _sub_dim_entry(dim, sub, score) for dim, sub, score in _FIXTURE_SCORES
    ]


def _valid_cheat_sheet_payload() -> dict:
    """Minimal well-shaped cheat_sheet matching the ORPHEUS-60 wire contract.

    5 priorities, 3 cadence sections in canonical order, 3 milestones.
    Values are placeholder strings — the parser only validates shape and
    presence, not content.
    """
    return {
        "priorities": [
            {"title": f"Priority {i + 1}", "action": f"Action step {i + 1}."}
            for i in range(5)
        ],
        "rhythm": [
            {
                "cadence": "Every Day",
                "items": ["Do daily thing one.", "Do daily thing two."],
            },
            {
                "cadence": "Every Week",
                "items": ["Do weekly thing one.", "Do weekly thing two."],
            },
            {
                "cadence": "Every Month",
                "items": ["Do monthly thing one."],
            },
        ],
        "milestones": [
            {"value": "10", "label": "Posts published"},
            {"value": "3", "label": "New recommendations"},
            {"value": "12", "label": "Weeks consistent"},
        ],
    }


def _full_response_with_sub_dims(
    sub_dim_payload: list[dict] | None = None,
    cheat_sheet: dict | None = None,
) -> str:
    """Build a complete 4-section + sub-dim response JSON (ORPHEUS-68 shape).

    The cheat_sheet object is included only when explicitly passed —
    matches the parser's best-effort posture so existing
    sub-dim-focused tests don't change behavior. Cheat-sheet-specific
    tests pass `cheat_sheet=_valid_cheat_sheet_payload()` (or a
    deliberately-malformed dict for negative cases).
    """
    if sub_dim_payload is None:
        sub_dim_payload = _valid_sub_dim_payload()
    body: dict = {
        "sections": [
            {"section": "Profile Signal Clarity", "summary": "Profile teaser.", "narrative": "Profile narrative. " * 10},
            {"section": "Behavioral Signal Strength", "summary": "Strength teaser.", "narrative": "Strength narrative. " * 10},
            {"section": "Behavioral Signal Quality", "summary": "Quality teaser.", "narrative": "Quality narrative. " * 8},
            {"section": "Profile-Behavior Alignment", "summary": "Alignment teaser.", "narrative": "Alignment narrative. " * 8},
        ],
        "sub_dimensions": sub_dim_payload,
    }
    if cheat_sheet is not None:
        body["cheat_sheet"] = cheat_sheet
    return json.dumps(body)


class TestParseSubDimensions:
    """Validates the ORPHEUS-21 sub-dim parser cross-references slots
    against actual scores and enforces the conditional curve.
    """

    def test_valid_13_entry_response_succeeds(self):
        output = _make_scoring_output()
        result = _parse_narrative_response(_full_response_with_sub_dims(), output)
        assert len(result.sub_dimensions) == 13
        # Score-3 entry: BP + improvements both present.
        score3_entry = result.sub_dimensions[
            ("Profile Signal Clarity", "Experience Description Quality")
        ]
        assert "summary" in score3_entry
        assert "best_practices" in score3_entry
        assert "improvements" in score3_entry
        # Score-4 entry: improvements present, BP dropped per curve.
        score4_entry = result.sub_dimensions[
            ("Profile Signal Clarity", "Headline Clarity")
        ]
        assert "summary" in score4_entry
        assert "best_practices" not in score4_entry
        assert "improvements" in score4_entry
        # Score-5 entry: summary only.
        score5_entry = result.sub_dimensions[
            ("Behavioral Signal Strength", "History Depth")
        ]
        assert "summary" in score5_entry
        assert "best_practices" not in score5_entry
        assert "improvements" not in score5_entry

    def test_missing_summary_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        # Strip summary off the first entry
        del payload[0]["summary"]
        with pytest.raises(ValueError, match="'summary' is required"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_empty_summary_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        payload[0]["summary"] = "   "
        with pytest.raises(ValueError, match="'summary' is required"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_score_3_missing_best_practices_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        # Experience Description Quality is score 3; strip its BP slot.
        for entry in payload:
            if entry["sub_dimension"] == "Experience Description Quality":
                del entry["best_practices"]
        with pytest.raises(ValueError, match="'best_practices' is required at scores 0.3"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_score_3_missing_improvements_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        for entry in payload:
            if entry["sub_dimension"] == "Profile Completeness":
                del entry["improvements"]
        with pytest.raises(ValueError, match="'improvements' is required at scores 0.4"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_score_4_missing_improvements_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        for entry in payload:
            if entry["sub_dimension"] == "Headline Clarity":  # score 4
                del entry["improvements"]
        with pytest.raises(ValueError, match="'improvements' is required at scores 0.4"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_score_4_with_stray_best_practices_is_dropped(self):
        """Claude sometimes can't resist over-emitting. At score 4 the parser
        tolerates and drops the unwanted best_practices rather than failing."""
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        for entry in payload:
            if entry["sub_dimension"] == "Headline Clarity":  # score 4
                entry["best_practices"] = "Stray BP that should not be here."
        result = _parse_narrative_response(_full_response_with_sub_dims(payload), output)
        score4_entry = result.sub_dimensions[
            ("Profile Signal Clarity", "Headline Clarity")
        ]
        assert "best_practices" not in score4_entry  # silently dropped
        assert "improvements" in score4_entry  # legitimate slot retained

    def test_score_5_with_stray_slots_are_dropped(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        for entry in payload:
            if entry["sub_dimension"] == "History Depth":  # score 5
                entry["best_practices"] = "Should not be here."
                entry["improvements"] = ["Should not be here either."]
        result = _parse_narrative_response(_full_response_with_sub_dims(payload), output)
        score5_entry = result.sub_dimensions[
            ("Behavioral Signal Strength", "History Depth")
        ]
        assert "summary" in score5_entry
        assert "best_practices" not in score5_entry
        assert "improvements" not in score5_entry

    def test_score_5_summary_only_is_valid(self):
        output = _make_scoring_output()
        result = _parse_narrative_response(_full_response_with_sub_dims(), output)
        # All three score-5 entries in the fixture should land summary-only.
        for sub_name in (
            "History Depth",
            "Outbound Engagement Presence",
            "Engagement Quality Score",
        ):
            entry = None
            for key in result.sub_dimensions:
                if key[1] == sub_name:
                    entry = result.sub_dimensions[key]
                    break
            assert entry is not None, f"missing {sub_name}"
            assert "summary" in entry
            assert "best_practices" not in entry
            assert "improvements" not in entry

    def test_duplicate_entry_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        # Inject a duplicate of the first entry
        payload.append(dict(payload[0]))
        with pytest.raises(ValueError, match="Duplicate sub-dimension"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_unexpected_pair_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        # Replace one entry with a (dim, sub_dim) pair that doesn't exist
        payload[0] = _sub_dim_entry(
            "Profile Signal Clarity", "Made Up Sub-Dim", 3
        )
        with pytest.raises(ValueError, match="Unexpected sub-dimension"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_missing_entry_raises_with_count(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        # Drop two entries
        payload = payload[:-2]
        with pytest.raises(ValueError, match="Missing 2 sub-dimension entries"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_empty_improvements_list_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        for entry in payload:
            if entry["sub_dimension"] == "Profile Completeness":
                entry["improvements"] = []
        with pytest.raises(ValueError, match="empty or not a list"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_improvements_bullet_blank_raises(self):
        output = _make_scoring_output()
        payload = _valid_sub_dim_payload()
        for entry in payload:
            if entry["sub_dimension"] == "Profile Completeness":
                entry["improvements"] = ["Real bullet.", "   "]
        with pytest.raises(ValueError, match="empty entry"):
            _parse_narrative_response(_full_response_with_sub_dims(payload), output)

    def test_no_scoring_output_skips_coverage_check(self):
        """Legacy callers that don't pass scoring_output get best-effort
        parsing — the 13-entry coverage check is skipped so partial
        responses don't fail the parser."""
        partial = _valid_sub_dim_payload()[:3]  # only 3 of 13
        result = _parse_narrative_response(_full_response_with_sub_dims(partial))
        # Sub-dims parsed but coverage not enforced.
        assert len(result.sub_dimensions) == 3


# ============================================================
# Test: _format_scored_dimensions raw_value rendering
# (ORPHEUS-21 layout, relabeled by ORPHEUS-117)
# ============================================================


class TestFormatScoredDimensionsRawValue:
    """Pinning the layout change that surfaces the underlying metric on its
    own line — pre-ORPHEUS-21 it was an inline " (raw value: X)" suffix.
    Sub-dim Summaries are expected to reference the metric, so it needs to be
    visible to Claude, not buried in parens.

    ORPHEUS-117 keeps the dedicated line but replaces the bare "raw value: N"
    with a `measured signal` line carrying the unit and measurement window.
    Fed a number with no unit, the agent invented one and quoted it to the
    client ("a raw archive value of 6,316 activity units").
    """

    def test_integer_metric_formatted_without_trailing_zero(self):
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        # History Depth raw_value = 750 (integer) → "750", not "750.0".
        assert "measured signal: 750 outbound actions" in text
        assert "750.0" not in text

    def test_float_metric_renders_with_one_decimal(self):
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        # Posting Presence raw_value = 1.5 → "1.5", not "1.50" or "2".
        assert "measured signal: 1.5 original posts per week" in text

    def test_large_metric_gets_thousands_separator(self):
        """Outbound Engagement Presence raw_value = 1200. The client-facing
        summary quotes this figure, so it should read as a human number."""
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        assert "measured signal: 1,200 engagement actions" in text

    def test_metric_on_own_line_indented(self):
        """The metric sits on its own line so Claude can ground sub-dim
        Summaries on it. The pre-ORPHEUS-21 inline form was easy to skip."""
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        history_lines = [l for l in text.splitlines() if l.strip().startswith("History Depth:")]
        assert len(history_lines) == 1
        assert "measured signal" not in history_lines[0]
        assert any(
            l.strip().startswith("measured signal: 750 outbound actions")
            for l in text.splitlines()
        )

    def test_every_metric_line_carries_a_unit_and_window(self):
        """The whole point of ORPHEUS-117: no measured-signal line may present
        a naked number. Each must state what is being counted and over what
        period, so the agent never has to supply a unit itself."""
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        signal_lines = [
            l.strip() for l in text.splitlines()
            if l.strip().startswith("measured signal:")
        ]
        # Five of the six quantitative sub-dims are citeable; the sixth
        # (Engagement Quality Score) is suppressed.
        assert len(signal_lines) == 5
        for line in signal_lines:
            assert any(
                lbl.unit in line and lbl.window in line
                for lbl in QUANTITATIVE_METRIC_LABELS.values()
            ), f"measured-signal line carries no registered unit/window: {line}"

    def test_engagement_quality_score_raw_value_is_withheld(self):
        """Engagement Quality Score's raw_value is a weighted internal index
        (substantive comments + reactions x 0.25) with no client-facing
        meaning. The fixture sets it to 480 — the score line must still
        render, but the number must not reach the prompt."""
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        assert "Engagement Quality Score" in SUPPRESSED_RAW_VALUE_SUB_DIMS
        assert "Engagement Quality Score: 5" in text
        assert "480" not in text

    def test_unregistered_metric_fails_closed(self):
        """A quantitative sub-dim with no registry entry must be rendered
        without its raw value rather than with an unlabeled one — so adding a
        sub-dim can't silently reintroduce this bug."""
        output = _make_scoring_output()
        dim2 = next(
            d for d in output.scored_dimensions.dimensions
            if d.name == "Behavioral Signal Strength"
        )
        dim2.sub_dimensions[0].name = "Brand New Metric"
        text = _format_scored_dimensions(output)
        assert "Brand New Metric: 5" in text
        assert "750" not in text

    def test_no_internal_unit_language_anywhere(self):
        """Regression pin on the exact phrasings observed live in job
        b902bd06's delivered report."""
        output = _make_scoring_output()
        text = _format_scored_dimensions(output)
        lowered = text.lower()
        for phrase in ("raw value", "raw archive value", "activity units",
                       "quality score raw"):
            assert phrase not in lowered


class TestQuantitativeMetricRegistry:
    """The registry has to stay in step with the scoring engine (ORPHEUS-117).

    Names are read off a real engine run rather than hand-copied, so a rename
    or a new quantitative sub-dim shows up here instead of silently losing its
    figure from the prompt.
    """

    def _engine_quantitative_sub_dims(self) -> set[str]:
        from datetime import date

        from backend.ingestion.types import ZipData
        from backend.scoring.engine import score_dimension_2, score_dimension_3

        ref = date(2026, 7, 20)
        empty = ZipData()
        return {
            sub.name
            for dim in (score_dimension_2(empty, ref), score_dimension_3(empty, ref))
            for sub in dim.sub_dimensions
        }

    def test_registry_and_suppression_list_are_disjoint(self):
        assert not (
            set(QUANTITATIVE_METRIC_LABELS) & SUPPRESSED_RAW_VALUE_SUB_DIMS
        )

    def test_every_engine_quantitative_sub_dim_is_accounted_for(self):
        """Each quantitative sub-dim must be either labeled or explicitly
        suppressed. An unaccounted one still fails closed at render time, but
        that's a silent loss of grounding — catch it here instead."""
        accounted = set(QUANTITATIVE_METRIC_LABELS) | SUPPRESSED_RAW_VALUE_SUB_DIMS
        assert self._engine_quantitative_sub_dims() <= accounted

    def test_registry_has_no_entries_the_engine_never_emits(self):
        assert set(QUANTITATIVE_METRIC_LABELS) <= self._engine_quantitative_sub_dims()

    def test_windows_track_config_constants(self):
        """Labels interpolate the scoring config rather than restating it, so a
        threshold change can't desync the client-facing window from the
        measurement."""
        from backend.scoring import config

        assert (
            f"{config.DIM2_RECENCY_WINDOW_DAYS} days"
            in QUANTITATIVE_METRIC_LABELS["Recency"].window
        )
        assert (
            f"{config.DIM2_CONTINUITY_WINDOW_WEEKS} weeks"
            in QUANTITATIVE_METRIC_LABELS["Continuity"].window
        )


class TestMilestoneTargets:
    """ORPHEUS-113. Milestone values are computed from measured baselines, not
    generated. The bug being closed: on b902bd06 the agent emitted
    {"value": "1,100+", "label": "Avg impressions per post (up from current
    875)"} — against the true 2,853 baseline that told the client to cut his
    reach by 60%.
    """

    def test_growth_target_always_exceeds_its_baseline(self):
        """The acceptance criterion, enforced by construction rather than by
        validation. Swept across magnitudes because rounding is what breaks
        this: a step wider than the growth increment pulls the target back
        onto or under the baseline."""
        for baseline in (0.01, 0.1, 0.5, 1, 4.9, 9.99, 10, 50, 99, 100,
                         999, 1000, 2852.8, 14489, 872569):
            for factor in MILESTONE_GROWTH_FACTORS.values():
                target = _growth_target(baseline, factor)
                assert target > baseline, (baseline, factor, target)

    def test_targets_are_rounded_to_readable_goals(self):
        # 3,200 x 1.25 = 4,000 exactly; 2,852.8 x 1.25 = 3,566 -> 3,550.
        assert _growth_target(3200, 1.25) == 4000
        assert _growth_target(2852.8, 1.25) == 3550

    def test_fixture_profile_yields_four_computed_milestones(self):
        targets = build_milestone_targets(_make_scoring_output())
        assert [t.key for t in targets] == [
            "posts_per_week", "impressions_per_post", "followers",
            "engagement_rate",
        ]
        assert [t.value for t in targets] == ["1.9", "4,000", "13,750", "4.8%"]

    def test_no_label_carries_a_digit(self):
        """Labels are digit-free by construction so the supplied wording can't
        seed the 'up from current 875' shape."""
        for t in build_milestone_targets(_make_scoring_output()):
            assert not any(ch.isdigit() for ch in t.label)
        for t in MILESTONE_STARTERS:
            assert not any(ch.isdigit() for ch in t.label)

    def test_deterministic_across_calls(self):
        a = build_milestone_targets(_make_scoring_output())
        b = build_milestone_targets(_make_scoring_output())
        assert a == b

    def test_zero_and_missing_baselines_are_skipped(self):
        """A baseline of 0 can't be grown from — no target is invented for it."""
        output = _make_scoring_output()
        q = output.forward_brief_data.quantitative
        q.avg_impressions_per_post = 0
        q.follower_count = None
        q.avg_engagement_rate = None
        targets = build_milestone_targets(output)
        assert [t.key for t in targets][0] == "posts_per_week"
        assert "impressions_per_post" not in [t.key for t in targets]
        assert "followers" not in [t.key for t in targets]

    def test_starters_top_up_to_three_for_a_dormant_client(self):
        """A member with nothing measurable still gets three milestones, and
        their values are code-owned constants rather than agent inventions."""
        output = _make_scoring_output()
        q = output.forward_brief_data.quantitative
        q.avg_impressions_per_post = None
        q.follower_count = None
        q.avg_engagement_rate = None
        for dim in output.scored_dimensions.dimensions:
            for sub in dim.sub_dimensions:
                if sub.name == "Posting Presence":
                    sub.raw_value = 0
        targets = build_milestone_targets(output)
        assert len(targets) == 3
        assert targets == list(MILESTONE_STARTERS[:3])

    def test_never_exceeds_four(self):
        assert len(build_milestone_targets(_make_scoring_output())) <= 4

    def test_prompt_block_states_the_values_are_fixed(self):
        text = _format_milestone_targets(build_milestone_targets(_make_scoring_output()))
        assert "you do not choose them" in text
        assert "no digits" in text
        assert '"4,000"' in text


class TestCheatSheetMilestoneValidation:
    """The parser side of ORPHEUS-113 — the agent echoes values and phrases
    labels, and drift in either direction sends it back for a retry.
    """

    TARGETS = [
        MilestoneTarget("impressions_per_post", "3,550", "Average impressions per post", "2,853"),
        MilestoneTarget("followers", "3,550", "Followers", "3,212"),
        MilestoneTarget("weeks_with_a_post", "12", "Weeks with at least one post", None),
    ]

    def _payload(self, milestones):
        return {
            "priorities": [
                {"title": f"Priority {i}", "action": "Do the thing."}
                for i in range(5)
            ],
            "rhythm": [
                {"cadence": c, "items": ["Item one.", "Item two."]}
                for c in ("Every Day", "Every Week", "Every Month")
            ],
            "milestones": milestones,
        }

    def _valid_milestones(self):
        return [{"value": t.value, "label": t.label} for t in self.TARGETS]

    def test_matching_values_parse(self):
        result = _parse_cheat_sheet_payload(
            self._payload(self._valid_milestones()), self.TARGETS
        )
        assert [m["value"] for m in result["milestones"]] == ["3,550", "3,550", "12"]

    def test_drifted_value_raises(self):
        milestones = self._valid_milestones()
        milestones[0]["value"] = "1,100+"
        with pytest.raises(ValueError, match="reproduce the supplied target"):
            _parse_cheat_sheet_payload(self._payload(milestones), self.TARGETS)

    def test_label_with_a_digit_raises(self):
        """The exact shape of the live bug: a baseline comparison smuggled
        into the label."""
        milestones = self._valid_milestones()
        milestones[0]["label"] = "Avg impressions per post (up from current 875)"
        with pytest.raises(ValueError, match="must not contain"):
            _parse_cheat_sheet_payload(self._payload(milestones), self.TARGETS)

    def test_wrong_count_raises(self):
        with pytest.raises(ValueError, match="one per supplied target"):
            _parse_cheat_sheet_payload(
                self._payload(self._valid_milestones()[:2] + [
                    {"value": "9", "label": "Extra"},
                    {"value": "9", "label": "Another"},
                ]),
                self.TARGETS,
            )

    def test_reworded_label_is_accepted(self):
        """Claude keeps the phrasing role — only digits and value drift are
        rejected."""
        milestones = self._valid_milestones()
        milestones[0]["label"] = "Typical reach per post"
        result = _parse_cheat_sheet_payload(self._payload(milestones), self.TARGETS)
        assert result["milestones"][0]["label"] == "Typical reach per post"

    def test_no_targets_supplied_keeps_legacy_best_effort_behavior(self):
        """Callers without scoring context (and the pre-113 fixtures) still
        parse, matching the parser's established posture."""
        milestones = [
            {"value": "1,100+", "label": "Avg impressions per post (up from 875)"},
            {"value": "12", "label": "Weeks"},
            {"value": "2", "label": "Recommendations"},
        ]
        result = _parse_cheat_sheet_payload(self._payload(milestones), None)
        assert len(result["milestones"]) == 3


class TestSystemPromptMetricCitationRules:
    """ORPHEUS-117's prompt-side half: the agent is told which figure it may
    cite and forbidden from inventing units for the rest."""

    def test_core_rules_forbid_quoting_internal_values(self):
        prompt = _build_system_prompt()
        assert "never quote internal scoring values" in prompt
        assert "do not invent a unit for it" in prompt

    def test_sub_dim_summary_instruction_points_at_measured_signal(self):
        prompt = _build_system_prompt()
        assert "`measured signal`" in prompt
        assert "raw metric value" not in prompt

    def test_milestone_instruction_removes_the_agent_s_discretion(self):
        """ORPHEUS-113: the old instruction was 'Pick milestones... where
        possible', which is what licensed the invented target."""
        prompt = _build_system_prompt()
        assert "You do not choose these values" in prompt
        assert "Labels must contain no digits" in prompt
        assert "Pick milestones" not in prompt

    def test_user_prompt_carries_the_milestone_slot(self):
        assert "{milestone_targets}" in USER_PROMPT_TEMPLATE
        assert "Milestone Targets" in USER_PROMPT_TEMPLATE


# ============================================================
# Test: Score-0 slot treatment (ORPHEUS-63)
# ============================================================
#
# Score 0 is treated identically to score 1 for slot structure: full
# payload of Summary + Best Practices + Improvements. The Summary's
# language is calibrated by the prompt to acknowledge absence honestly
# rather than position the client "below the standard"; the parser
# only enforces slot presence, which is what these tests cover.


def _scoring_output_with_zero_score(target_sub_name: str) -> ScoringStageOutput:
    """Build a scoring output with one sub-dim mutated to score 0.

    The base fixture has no score-0 entries (its lowest is 3); for
    score-0 testing we mutate a specific sub-dim in-place. Behavioral
    sub-dims (Dim 2, Dim 3) are the realistic candidates since Dim 1 +
    Dim 4 are rubric-driven and unlikely to ever hit 0.
    """
    output = _make_scoring_output()
    for dim in output.scored_dimensions.dimensions:
        for sub in dim.sub_dimensions:
            if sub.name == target_sub_name:
                sub.score = 0
                return output
    raise AssertionError(f"sub_dim {target_sub_name!r} not in fixture")


def _payload_with_zero_score(target_sub_name: str) -> list[dict]:
    """Build the matching sub_dim payload with the same target at score 0."""
    out: list[dict] = []
    for dim_name, sub_name, default_score in _FIXTURE_SCORES:
        score = 0 if sub_name == target_sub_name else default_score
        out.append(_sub_dim_entry(dim_name, sub_name, score))
    return out


class TestParseSubDimensionsScoreZero:
    """ORPHEUS-63 (locked 2026-06-04): score 0 follows the score-1 slot
    posture — Summary + Best Practices + Improvements all required.
    """

    def test_score_zero_with_full_payload_succeeds(self):
        output = _scoring_output_with_zero_score("Posting Presence")
        payload = _payload_with_zero_score("Posting Presence")
        result = _parse_narrative_response(
            _full_response_with_sub_dims(payload), output
        )
        entry = result.sub_dimensions[
            ("Behavioral Signal Strength", "Posting Presence")
        ]
        assert "summary" in entry
        assert "best_practices" in entry
        assert "improvements" in entry
        # Improvements is the same list shape as score-1; bullet count
        # spec (3–5) is enforced by the prompt, not the parser. We
        # don't assert on count here for the same reason we don't at
        # score 1.

    def test_score_zero_missing_best_practices_raises(self):
        output = _scoring_output_with_zero_score("Posting Presence")
        payload = _payload_with_zero_score("Posting Presence")
        for entry in payload:
            if entry["sub_dimension"] == "Posting Presence":
                del entry["best_practices"]
        with pytest.raises(
            ValueError, match="'best_practices' is required at scores 0.3"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(payload), output
            )

    def test_score_zero_missing_improvements_raises(self):
        output = _scoring_output_with_zero_score("Posting Presence")
        payload = _payload_with_zero_score("Posting Presence")
        for entry in payload:
            if entry["sub_dimension"] == "Posting Presence":
                del entry["improvements"]
        with pytest.raises(
            ValueError, match="'improvements' is required at scores 0.4"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(payload), output
            )

    def test_multiple_score_zero_entries_all_validate(self):
        """The 6-zero case from the ORPHEUS-62 live test — Josh's profile
        had 6 quantitative sub-dims at 0. Each should validate the same
        way, no per-dim short-circuit logic.
        """
        output = _make_scoring_output()
        # Mutate all 6 quantitative sub-dims (Dim 2 + Dim 3) to score 0.
        for dim in output.scored_dimensions.dimensions:
            if dim.name in (
                "Behavioral Signal Strength",
                "Behavioral Signal Quality",
            ):
                for sub in dim.sub_dimensions:
                    sub.score = 0
        zero_sub_names = {
            "History Depth",
            "Recency",
            "Continuity",
            "Posting Presence",
            "Outbound Engagement Presence",
            "Engagement Quality Score",
        }
        payload: list[dict] = []
        for dim_name, sub_name, default_score in _FIXTURE_SCORES:
            score = 0 if sub_name in zero_sub_names else default_score
            payload.append(_sub_dim_entry(dim_name, sub_name, score))
        result = _parse_narrative_response(
            _full_response_with_sub_dims(payload), output
        )
        # All 6 zero-score entries should carry the full payload.
        for key, entry in result.sub_dimensions.items():
            if key[1] in zero_sub_names:
                assert "best_practices" in entry, (
                    f"score-0 {key} missing best_practices"
                )
                assert "improvements" in entry, (
                    f"score-0 {key} missing improvements"
                )


# ============================================================
# Test: Cheat sheet parsing (ORPHEUS-60)
# ============================================================


class TestParseCheatSheet:
    """ORPHEUS-60 added a structured cheat_sheet payload to the agent's
    response. Parser validates shape strictly when present, returns None
    when absent (best-effort posture mirrors sub_dimensions).
    """

    def test_valid_cheat_sheet_parses_to_dict(self):
        output = _make_scoring_output()
        raw = _full_response_with_sub_dims(
            cheat_sheet=_valid_cheat_sheet_payload()
        )
        result = _parse_narrative_response(raw, output)
        assert result.cheat_sheet is not None
        assert len(result.cheat_sheet["priorities"]) == 5
        assert [
            p["title"] for p in result.cheat_sheet["priorities"]
        ] == [f"Priority {i + 1}" for i in range(5)]
        assert [
            r["cadence"] for r in result.cheat_sheet["rhythm"]
        ] == ["Every Day", "Every Week", "Every Month"]
        assert len(result.cheat_sheet["milestones"]) == 3

    def test_missing_cheat_sheet_returns_none(self):
        """Best-effort: an agent response that omits cheat_sheet still
        parses (legacy / partial fixture path). Wire surfaces null;
        CheatSheetPage falls back to the not-ready surface.
        """
        output = _make_scoring_output()
        raw = _full_response_with_sub_dims()  # no cheat_sheet kwarg
        result = _parse_narrative_response(raw, output)
        assert result.cheat_sheet is None

    def test_priorities_wrong_count_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["priorities"] = cs["priorities"][:4]  # only 4
        with pytest.raises(
            ValueError, match="priorities must be a list of exactly 5"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_priority_missing_title_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        del cs["priorities"][0]["title"]
        with pytest.raises(
            ValueError, match=r"priorities\[0\]\.title is required"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_priority_empty_action_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["priorities"][2]["action"] = "   "
        with pytest.raises(
            ValueError, match=r"priorities\[2\]\.action is required"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_rhythm_wrong_count_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["rhythm"] = cs["rhythm"][:2]
        with pytest.raises(
            ValueError, match="rhythm must be a list of 3 entries"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_rhythm_wrong_cadence_label_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["rhythm"][1]["cadence"] = "Weekly"  # should be 'Every Week'
        with pytest.raises(
            ValueError, match=r"rhythm\[1\]\.cadence must be 'Every Week'"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_rhythm_empty_items_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["rhythm"][0]["items"] = []
        with pytest.raises(
            ValueError, match=r"rhythm\[0\]\.items must be a non-empty list"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_milestones_too_few_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["milestones"] = cs["milestones"][:2]
        with pytest.raises(
            ValueError, match="milestones must be a list of 3 or 4"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_milestones_too_many_raises(self):
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["milestones"] = cs["milestones"] + [
            {"value": "1", "label": "Extra one"},
            {"value": "2", "label": "Extra two"},
        ]
        with pytest.raises(
            ValueError, match="milestones must be a list of 3 or 4"
        ):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=cs), output
            )

    def test_milestones_four_entries_accepted(self):
        """Spec allows 3–4 entries; the 4-entry case should parse cleanly."""
        output = _make_scoring_output()
        cs = _valid_cheat_sheet_payload()
        cs["milestones"] = cs["milestones"] + [
            {"value": "1", "label": "Fourth milestone"},
        ]
        result = _parse_narrative_response(
            _full_response_with_sub_dims(cheat_sheet=cs), output
        )
        assert result.cheat_sheet is not None
        assert len(result.cheat_sheet["milestones"]) == 4

    def test_non_dict_cheat_sheet_raises(self):
        output = _make_scoring_output()
        with pytest.raises(ValueError, match="cheat_sheet must be an object"):
            _parse_narrative_response(
                _full_response_with_sub_dims(cheat_sheet=["not", "a", "dict"]),  # type: ignore[arg-type]
                output,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
