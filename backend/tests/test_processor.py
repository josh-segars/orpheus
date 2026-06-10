"""Tests for the worker pipeline helpers in backend/workers/processor.py.

Covers `_merge_sub_dim_narratives` (ORPHEUS-21) and `_merge_dim_summaries`
(ORPHEUS-68) — the rest of the processor module is integration-shaped
(Supabase + Anthropic side effects) and exercised live in the e2e
walk-throughs rather than under pytest.

Both helpers are in-place mutation steps that land the narrative agent's
payloads onto the ScoringStageOutput model before the `scores.dimensions`
JSONB is re-persisted. A bug here surfaces as silently-empty narrative
slots on the wire even when Claude generated them correctly, so they're
worth their own test surface independent of the parser.
"""

from __future__ import annotations

from backend.models.scoring import (
    AudienceSegment,
    ConfidenceLabel,
    DimensionScore,
    EngagementInvitation,
    ForwardBriefData,
    ForwardBriefQuantitative,
    QualitativeFlags,
    ScoredDimensions,
    ScoringMethod,
    ScoringStageOutput,
    SignalBand,
    SubDimensionScore,
    ViewerActorAffinity,
    VisualProfessionalism,
)
from backend.workers.processor import (
    _merge_dim_summaries,
    _merge_sub_dim_narratives,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _minimal_scoring_output() -> ScoringStageOutput:
    """A two-dim, three-sub-dim scoring output — enough surface to test
    the merge without dragging in all 13 sub-dims from the production
    distribution. Sub-dim narrative fields start unset (None).
    """
    return ScoringStageOutput(
        scored_dimensions=ScoredDimensions(
            composite=58.0,
            band=SignalBand.TUNING,
            dimensions=[
                DimensionScore(
                    name="Profile Signal Clarity",
                    weight=0.35,
                    confidence=ConfidenceLabel.CONFIRMED,
                    normalized_score=0.60,
                    contribution=21.0,
                    band=SignalBand.TUNING,
                    sub_dimensions=[
                        SubDimensionScore(
                            name="Headline Clarity",
                            score=3,
                            scale="1-5",
                            method=ScoringMethod.RUBRIC,
                        ),
                        SubDimensionScore(
                            name="Identity Clarity",
                            score=5,
                            scale="1-5",
                            method=ScoringMethod.RUBRIC,
                        ),
                    ],
                ),
                DimensionScore(
                    name="Behavioral Signal Strength",
                    weight=0.30,
                    confidence=ConfidenceLabel.CONFIRMED,
                    normalized_score=0.55,
                    contribution=16.5,
                    band=SignalBand.TUNING,
                    sub_dimensions=[
                        SubDimensionScore(
                            name="History Depth",
                            score=4,
                            scale="0-5",
                            method=ScoringMethod.QUANTITATIVE,
                            raw_value=320,
                        ),
                    ],
                ),
            ],
        ),
        forward_brief_data=ForwardBriefData(
            quantitative=ForwardBriefQuantitative(),
            qualitative_flags=QualitativeFlags(
                viewer_actor_affinity=ViewerActorAffinity(
                    concentrated=False, top_targets=[]
                ),
                visual_professionalism=VisualProfessionalism(photo_present=True),
                engagement_invitation=EngagementInvitation(
                    services_present=False,
                    contact_visible=False,
                    cta_in_about=False,
                ),
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


class TestMergeSubDimNarratives:

    def test_applies_summary_only_at_score_5(self):
        output = _minimal_scoring_output()
        narratives = {
            ("Profile Signal Clarity", "Identity Clarity"): {
                "summary": "Identity clarity is exceptional across the profile.",
                # BP and Improvements deliberately absent — parser already
                # dropped them per the score-5 rule.
            },
        }
        _merge_sub_dim_narratives(output, narratives)

        identity_sub = output.scored_dimensions.dimensions[0].sub_dimensions[1]
        assert identity_sub.name == "Identity Clarity"
        assert identity_sub.summary == (
            "Identity clarity is exceptional across the profile."
        )
        assert identity_sub.best_practices is None
        assert identity_sub.improvements is None

    def test_applies_all_three_slots_at_score_3(self):
        output = _minimal_scoring_output()
        narratives = {
            ("Profile Signal Clarity", "Headline Clarity"): {
                "summary": "Summary text for headline.",
                "best_practices": "Generic standard for headlines.",
                "improvements": ["Action one.", "Action two."],
            },
        }
        _merge_sub_dim_narratives(output, narratives)

        headline_sub = output.scored_dimensions.dimensions[0].sub_dimensions[0]
        assert headline_sub.summary == "Summary text for headline."
        assert headline_sub.best_practices == "Generic standard for headlines."
        assert headline_sub.improvements == ["Action one.", "Action two."]

    def test_applies_summary_and_improvements_at_score_4(self):
        output = _minimal_scoring_output()
        narratives = {
            ("Behavioral Signal Strength", "History Depth"): {
                "summary": "History depth covers 320 outbound actions.",
                "improvements": ["Tighten posting cadence."],
            },
        }
        _merge_sub_dim_narratives(output, narratives)

        history_sub = output.scored_dimensions.dimensions[1].sub_dimensions[0]
        assert history_sub.summary == (
            "History depth covers 320 outbound actions."
        )
        assert history_sub.best_practices is None
        assert history_sub.improvements == ["Tighten posting cadence."]

    def test_missing_entry_tolerated(self):
        """A sub-dim not present in the narrative dict shouldn't crash —
        the parser's coverage check already enforced completeness, so
        anything missing here is by definition deliberate."""
        output = _minimal_scoring_output()
        narratives: dict = {}  # nothing to merge
        _merge_sub_dim_narratives(output, narratives)

        for dim in output.scored_dimensions.dimensions:
            for sub in dim.sub_dimensions:
                assert sub.summary is None
                assert sub.best_practices is None
                assert sub.improvements is None

    def test_merge_round_trips_through_json(self):
        """The end-to-end test: after merging, model_dump_json should
        include the new fields so the worker's UPDATE on scores.dimensions
        actually carries them to the wire."""
        output = _minimal_scoring_output()
        narratives = {
            ("Profile Signal Clarity", "Headline Clarity"): {
                "summary": "Summary text.",
                "best_practices": "BP text.",
                "improvements": ["Action."],
            },
        }
        _merge_sub_dim_narratives(output, narratives)
        dumped = output.scored_dimensions.model_dump_json()
        assert '"summary":"Summary text."' in dumped
        assert '"best_practices":"BP text."' in dumped
        assert '"improvements":["Action."]' in dumped


class TestMergeDimSummaries:
    """ORPHEUS-68: the per-dimension summary teaser rides the same
    scores.dimensions JSONB path as the sub-dim slots."""

    def test_applies_summaries_by_dimension_name(self):
        output = _minimal_scoring_output()
        summaries = {
            "Profile Signal Clarity": "Profile teaser sentence.",
            "Behavioral Signal Strength": "Strength teaser sentence.",
        }
        _merge_dim_summaries(output, summaries)

        dims = {d.name: d for d in output.scored_dimensions.dimensions}
        assert dims["Profile Signal Clarity"].summary == "Profile teaser sentence."
        assert dims["Behavioral Signal Strength"].summary == "Strength teaser sentence."

    def test_missing_summary_tolerated(self):
        """A dimension absent from the summaries dict keeps summary=None —
        same tolerance posture as _merge_sub_dim_narratives."""
        output = _minimal_scoring_output()
        _merge_dim_summaries(output, {"Profile Signal Clarity": "Only one."})

        dims = {d.name: d for d in output.scored_dimensions.dimensions}
        assert dims["Profile Signal Clarity"].summary == "Only one."
        assert dims["Behavioral Signal Strength"].summary is None

    def test_empty_dict_is_noop(self):
        output = _minimal_scoring_output()
        _merge_dim_summaries(output, {})
        for dim in output.scored_dimensions.dimensions:
            assert dim.summary is None

    def test_summary_round_trips_through_json(self):
        """After merging, model_dump_json carries the dimension summary so
        the worker's UPDATE on scores.dimensions reaches the wire."""
        output = _minimal_scoring_output()
        _merge_dim_summaries(output, {"Profile Signal Clarity": "Wire teaser."})
        dumped = output.scored_dimensions.model_dump_json()
        assert '"summary":"Wire teaser."' in dumped
