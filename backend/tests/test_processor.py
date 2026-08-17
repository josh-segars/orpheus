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
    stage_scoring,
    update_job_status,
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


class TestStageScoringPhotoOverride:
    """ORPHEUS-89: stage_scoring forwards the OIDC photo override into
    run_scoring → Forward Brief. Supabase writes are stubbed with a
    MagicMock (the integration write path is exercised live, not here)."""

    _DIM1 = {n: 3 for n in [
        "Headline Clarity", "About Section Coherence",
        "Experience Description Quality", "Profile Completeness",
        "Identity Clarity",
    ]}
    _DIM4 = {"Topic Consistency": 3, "Profile-Content Coherence": 3}

    def _run(self, photo_present_override):
        import asyncio
        from unittest.mock import MagicMock

        from backend.ingestion.types import ZipData

        return asyncio.run(
            stage_scoring(
                zip_data=ZipData(),  # no rich-media → heuristic would be False
                xlsx_data=None,
                dim1_scores=self._DIM1,
                dim4_scores=self._DIM4,
                job_id="job-1",
                supabase=MagicMock(),
                photo_present_override=photo_present_override,
            )
        )

    def test_override_true_wins(self):
        result = self._run(True)
        assert (
            result.forward_brief_data.qualitative_flags
            .visual_professionalism.photo_present
            is True
        )

    def test_override_none_falls_back_to_heuristic(self):
        result = self._run(None)
        assert (
            result.forward_brief_data.qualitative_flags
            .visual_professionalism.photo_present
            is False
        )


class TestStageScoringReconciliationGate:
    """ORPHEUS-114: stage_scoring blocks on failed reconciliation identities
    BEFORE the scores upsert — a bad derived metric never persists."""

    _DIM1 = {n: 3 for n in [
        "Headline Clarity", "About Section Coherence",
        "Experience Description Quality", "Profile Completeness",
        "Identity Clarity",
    ]}
    _DIM4 = {"Topic Consistency": 3, "Profile-Content Coherence": 3}

    def _rigged_output(self):
        """Real scoring output with a bug-A-shaped inconsistency injected."""
        import asyncio
        from datetime import date

        from backend.ingestion.types import ZipData
        from backend.scoring.engine import run_scoring

        output = run_scoring(
            zip_data=ZipData(),
            xlsx_data=None,
            dim1_rubric_scores=self._DIM1,
            dim4_rubric_scores=self._DIM4,
            ref_date=date(2026, 7, 18),
        )
        q = output.forward_brief_data.quantitative
        q.avg_impressions_per_post = 875.4   # the ORPHEUS-112 bad value
        q.post_count = 112
        q.total_impressions = 319511
        return output

    def test_reconciliation_failure_raises_and_skips_upsert(self):
        import asyncio
        from unittest.mock import MagicMock, patch

        import pytest as _pytest

        from backend.ingestion.types import ZipData
        from backend.scoring.reconciliation import ReconciliationError
        from backend.workers import processor as processor_mod

        supabase = MagicMock()
        rigged = self._rigged_output()

        with patch.object(processor_mod, "run_scoring", return_value=rigged):
            with _pytest.raises(ReconciliationError) as exc:
                asyncio.run(
                    stage_scoring(
                        zip_data=ZipData(),
                        xlsx_data=None,
                        dim1_scores=self._DIM1,
                        dim4_scores=self._DIM4,
                        job_id="job-recon",
                        supabase=supabase,
                    )
                )

        # The error names the failed identity — it becomes error_message.
        assert "impressions_per_post_x_post_count" in str(exc.value)
        # Nothing was persisted: no scores upsert, no config_snapshot write.
        supabase.table.assert_not_called()

    def test_clean_output_still_persists(self):
        import asyncio
        from unittest.mock import MagicMock

        from backend.ingestion.types import ZipData

        supabase = MagicMock()
        result = asyncio.run(
            stage_scoring(
                zip_data=ZipData(),  # no operands → identities skip → pass
                xlsx_data=None,
                dim1_scores=self._DIM1,
                dim4_scores=self._DIM4,
                job_id="job-clean",
                supabase=supabase,
            )
        )
        assert result is not None
        supabase.table.assert_any_call("scores")


# --------------------------------------------------------------------------- #
# ORPHEUS-131 — prose-gate degradation marker + error_message hygiene
# --------------------------------------------------------------------------- #


class _FakeTable:
    """Chainable Supabase table stub that records the writes it is handed.

    Every query verb returns `self`; `execute()` returns the canned row for
    the table. Enough to walk `run_pipeline` end to end without touching
    Supabase — the point is the payloads, which the recorder keeps.
    """

    def __init__(self, name: str, data, recorder: list):
        self._name = name
        self._data = data
        self._recorder = recorder

    # ── query verbs (no-ops that keep the chain going) ──
    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def single(self):
        return self

    def order(self, *a, **k):
        return self

    # ── write verbs (recorded) ──
    def update(self, payload):
        self._recorder.append((self._name, "update", payload))
        return self

    def upsert(self, payload, **k):
        self._recorder.append((self._name, "upsert", payload))
        return self

    def insert(self, payload):
        self._recorder.append((self._name, "insert", payload))
        return self

    def delete(self):
        self._recorder.append((self._name, "delete", None))
        return self

    def execute(self):
        from types import SimpleNamespace

        return SimpleNamespace(data=self._data, count=1)


class _FakeSupabase:
    def __init__(self, rows: dict):
        self.writes: list = []
        self._rows = rows

    def table(self, name: str):
        return _FakeTable(name, self._rows.get(name), self.writes)


class TestUpdateJobStatusErrorMessage:
    """ORPHEUS-131 acceptance 3: `complete` jobs carry no error_message.

    The retry path writes the failed attempt's traceback to the row, so a job
    that lost an attempt and recovered used to reach `complete` still carrying
    it — job b03ca0f5 shipped a correct report with an attempt-2 traceback
    attached, which reads as a failure to anyone who looks.
    """

    def _payload(self, status: str, error_message=None):
        import asyncio

        supabase = _FakeSupabase({})
        asyncio.run(
            update_job_status(supabase, "job-1", status, error_message)
        )
        assert len(supabase.writes) == 1
        table, verb, payload = supabase.writes[0]
        assert (table, verb) == ("jobs", "update")
        return payload

    def test_complete_clears_error_message(self):
        payload = self._payload("complete")
        assert payload["status"] == "complete"
        assert payload["error_message"] is None
        assert "completed_at" in payload

    def test_failed_still_records_error_message(self):
        payload = self._payload("failed", "Attempt 3/3: boom")
        assert payload["status"] == "failed"
        assert payload["error_message"] == "Attempt 3/3: boom"

    def test_running_touches_neither(self):
        payload = self._payload("running")
        assert "error_message" not in payload
        assert "started_at" in payload


class TestRunPipelinePersistsProseGateMarker:
    """ORPHEUS-131 acceptance 1 + 2: a degraded narrative lands a marker on
    the job row (the /admin surface) instead of the job landing `failed`.

    The stages are patched out — this pins the persistence contract between
    `NarrativeResult.prose_gate_degraded` and `jobs.prose_gate_degraded`,
    which is where a silent break would cost the most: the report ships and
    nobody can tell it was degraded.
    """

    _JOB = {"id": "job-131", "client_id": "client-1"}
    _ROWS = {
        # Advisory client — keeps the report-ready email path out of it
        # (advisory reports are draft until published, so it early-returns).
        "clients": {
            "id": "client-1",
            "email": "client@example.com",
            "display_name": "Test Client",
            "advisors": {"is_individual": False, "narrative_config": None},
        },
        "questionnaire_responses": {"answers": {}},
    }

    def _run(self, *, degraded: bool, violations):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import patch

        from backend.agents.narrative import NarrativeResult
        from backend.ingestion.types import ZipData
        from backend.workers import processor as processor_mod

        supabase = _FakeSupabase(self._ROWS)
        scoring_output = _minimal_scoring_output()
        narrative_result = NarrativeResult(
            sections={},
            summaries={},
            sub_dimensions={},
            cheat_sheet=None,
            cta_present=None,
            prose_gate_degraded=degraded,
            prose_gate_violations=violations,
        )
        quality = SimpleNamespace(is_data_limited=False)

        async def _ingestion(*a, **k):
            return ZipData(), None, quality

        async def _rubric(*a, **k):
            return {}, {}

        async def _scoring(*a, **k):
            return scoring_output

        async def _narrative(*a, **k):
            return narrative_result

        with patch.object(processor_mod, "stage_ingestion", _ingestion), \
             patch.object(processor_mod, "stage_rubric_scoring", _rubric), \
             patch.object(processor_mod, "stage_scoring", _scoring), \
             patch.object(
                 processor_mod, "stage_narrative_generation", _narrative
             ):
            asyncio.run(
                processor_mod.run_pipeline(supabase, object(), dict(self._JOB))
            )

        return supabase.writes

    @staticmethod
    def _marker_write(writes):
        """The jobs update carrying the marker (not the status update)."""
        for table, verb, payload in writes:
            if table == "jobs" and verb == "update" and (
                "prose_gate_degraded" in payload
            ):
                return payload
        raise AssertionError(f"no marker write found in {writes}")

    def test_degraded_narrative_marks_the_job(self):
        writes = self._run(
            degraded=True,
            violations="section:Behavioral Signal Strength: '2,394'",
        )
        payload = self._marker_write(writes)
        assert payload["prose_gate_degraded"] is True
        assert "2,394" in payload["prose_gate_violations"]
        # The job still completes — that is the whole point of the ticket.
        statuses = [
            p.get("status") for t, v, p in writes
            if t == "jobs" and v == "update" and isinstance(p, dict)
        ]
        assert "complete" in statuses
        assert "failed" not in statuses

    def test_clean_narrative_clears_the_marker(self):
        """Written unconditionally so an ORPHEUS-81 re-run that comes back
        clean doesn't leave a stale flag on the row."""
        writes = self._run(degraded=False, violations=None)
        payload = self._marker_write(writes)
        assert payload["prose_gate_degraded"] is False
        assert payload["prose_gate_violations"] is None

    def test_marker_rides_the_data_limited_update(self):
        """One write, not two — same row, same moment, same reason."""
        writes = self._run(degraded=True, violations="section:X: '999'")
        payload = self._marker_write(writes)
        assert payload["data_limited"] is False
        assert set(payload) == {
            "data_limited", "prose_gate_degraded", "prose_gate_violations",
        }


class TestRegenerateReportRefusesDegradedNarrative:
    """ORPHEUS-131 guard rail: the in-place regeneration script must NOT
    inherit the worker's degrade posture.

    `scripts/regenerate_report.py` used to be protected by accident — a
    fabricated figure raised out of `generate_narratives` and the script never
    reached its write. The degrade removes that exception, and the script's
    own `verify()` has no prose-number check of its own, so without this the
    degrade would silently start overwriting already-delivered reports with
    unverified figures — and invisibly, since the script deliberately never
    touches the job row that carries the marker.
    """

    def _verify(self, *, degraded: bool):
        from backend.agents.narrative import NarrativeResult
        from backend.scripts.regenerate_report import verify

        scoring_output = _minimal_scoring_output()
        narrative_result = NarrativeResult(
            sections={},
            summaries={},
            sub_dimensions={},
            cheat_sheet=None,
            cta_present=None,
            prose_gate_degraded=degraded,
            prose_gate_violations=(
                "section:Behavioral Signal Strength: '2,394'"
                if degraded else None
            ),
        )
        return verify(
            scoring_output, narrative_result,
            milestone_targets=[], stale_values=[],
        )

    def test_degraded_narrative_is_a_verification_failure(self):
        failures = self._verify(degraded=True)
        assert any("prose-number gate degraded" in f for f in failures)
        assert any("2,394" in f for f in failures)

    def test_clean_narrative_adds_no_prose_failure(self):
        failures = self._verify(degraded=False)
        assert not any("prose-number gate" in f for f in failures)
