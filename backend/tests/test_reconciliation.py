"""ORPHEUS-114 (c) — reconciliation identities against stored operands.

Golden fixtures are Andrew's 21 Jul 2025 – 20 Jul 2026 window (the ticket's
verified numbers, the same profile behind test_scoring.py's
TestAvgImpressionsPerPost): 112 posts; 319,511 total impressions; 67,063
members reached; 8,655 engagements → 2.71% rate; 3,212 followers, +913 net
→ 17.5/week; 2,852.8 avg impressions/post; top post 18,479.

The bug-A regression is the reason this module exists: the pre-ORPHEUS-112
per-DAY value 875.4 fails identity 1 by ~221k where the corrected 2,852.8
passes inside tolerance — the check that would have caught the bug before a
client ever saw it.
"""

from __future__ import annotations

import pytest

from backend.models.scoring import (
    EngagementInvitation,
    ForwardBriefData,
    ForwardBriefQuantitative,
    QualitativeFlags,
    ViewerActorAffinity,
    VisualProfessionalism,
)
from backend.scoring.reconciliation import (
    IdentityResult,
    ReconciliationError,
    assert_reconciled,
    check_reconciliation,
)


def _flags() -> QualitativeFlags:
    return QualitativeFlags(
        viewer_actor_affinity=ViewerActorAffinity(
            concentrated=False, top_targets=[]
        ),
        visual_professionalism=VisualProfessionalism(photo_present=True),
        engagement_invitation=EngagementInvitation(
            services_present=False, contact_visible=False, cta_in_about=False
        ),
    )


def _golden_quantitative(**overrides) -> ForwardBriefQuantitative:
    """Andrew's golden window, exactly as the engine would persist it."""
    fields = dict(
        follower_count=3212,
        follower_growth_rate=17.5,
        unique_members_reached=67063,
        avg_impressions_per_post=2852.8,
        avg_engagement_rate=0.0271,
        top_post_impressions=18479,
        post_count=112,
        total_impressions=319511,
        total_engagements=8655,
        net_new_followers=913,
        followers_weeks_observed=52.14,  # 365 daily rows / 7
        discovery_impressions=319511,
    )
    fields.update(overrides)
    return ForwardBriefQuantitative(**fields)


def _fb(**overrides) -> ForwardBriefData:
    return ForwardBriefData(
        quantitative=_golden_quantitative(**overrides),
        qualitative_flags=_flags(),
    )


def _by_name(results: list[IdentityResult]) -> dict[str, IdentityResult]:
    return {r.name: r for r in results}


class TestGoldenFixtures:
    def test_all_identities_pass_on_golden_values(self):
        results = check_reconciliation(_fb())
        assert results, "expected identities to run on fully-populated data"
        failures = [r for r in results if not r.ok]
        assert failures == []

    def test_all_six_identities_ran(self):
        names = set(_by_name(check_reconciliation(_fb())))
        assert names == {
            "impressions_per_post_x_post_count",
            "follower_rate_x_weeks",
            "engagement_rate_recompute",
            "members_reached_range",
            "discovery_vs_engagement_impressions",
            "top_post_within_total",
        }

    def test_assert_reconciled_passes_silently_on_golden(self):
        assert_reconciled(_fb(), job_id="golden-test")


class TestBugARegression:
    """ORPHEUS-112: the per-day denominator value must fail identity 1."""

    def test_stale_per_day_value_fails(self):
        results = _by_name(
            check_reconciliation(_fb(avg_impressions_per_post=875.4))
        )
        r = results["impressions_per_post_x_post_count"]
        assert r.ok is False
        # The detail names both sides so error_message is actionable.
        assert "875.4" in r.detail
        assert "319,511" in r.detail

    def test_stale_value_raises_blocking(self):
        with pytest.raises(ReconciliationError) as exc:
            assert_reconciled(_fb(avg_impressions_per_post=875.4))
        assert "impressions_per_post_x_post_count" in str(exc.value)


class TestSkipOnMissingOperands:
    """A partial-XLSX job must not fail on data it never had — rows written
    before ORPHEUS-114 lack the operands entirely."""

    def test_no_operands_at_all_runs_nothing(self):
        fb = ForwardBriefData(
            quantitative=ForwardBriefQuantitative(),  # all None
            qualitative_flags=_flags(),
        )
        assert check_reconciliation(fb) == []

    def test_pre_114_row_shape_skips_every_identity(self):
        # A stored pre-114 row: derived metrics present, operands absent.
        fb = ForwardBriefData(
            quantitative=ForwardBriefQuantitative(
                follower_count=3212,
                follower_growth_rate=17.5,
                unique_members_reached=67063,
                avg_impressions_per_post=875.4,  # even the bug-A value
                avg_engagement_rate=0.0271,
                top_post_impressions=18479,
            ),
            qualitative_flags=_flags(),
        )
        assert check_reconciliation(fb) == []

    @pytest.mark.parametrize(
        "missing,identity",
        [
            ("post_count", "impressions_per_post_x_post_count"),
            ("total_impressions", "impressions_per_post_x_post_count"),
            ("net_new_followers", "follower_rate_x_weeks"),
            ("followers_weeks_observed", "follower_rate_x_weeks"),
            ("total_engagements", "engagement_rate_recompute"),
            ("discovery_impressions", "discovery_vs_engagement_impressions"),
        ],
    )
    def test_each_identity_skips_when_its_operand_is_none(
        self, missing, identity
    ):
        results = _by_name(check_reconciliation(_fb(**{missing: None})))
        assert identity not in results

    def test_zero_post_count_skips_identity_1(self):
        results = _by_name(check_reconciliation(_fb(post_count=0)))
        assert "impressions_per_post_x_post_count" not in results


class TestMembersReachedRange:
    """Unique-cumulative: a range check, never a sum-of-dailies equality."""

    def test_exceeding_total_impressions_fails(self):
        results = _by_name(
            check_reconciliation(_fb(unique_members_reached=400000))
        )
        assert results["members_reached_range"].ok is False

    def test_equal_to_total_impressions_passes(self):
        results = _by_name(
            check_reconciliation(_fb(unique_members_reached=319511))
        )
        assert results["members_reached_range"].ok is True


class TestCrossSourceImpressions:
    def test_within_one_percent_passes(self):
        # 319,511 vs 321,000 = 0.47% — LinkedIn's own totals wobble a bit.
        results = _by_name(
            check_reconciliation(_fb(discovery_impressions=321000))
        )
        assert results["discovery_vs_engagement_impressions"].ok is True

    def test_beyond_one_percent_fails(self):
        # 10% apart: the export is internally inconsistent.
        results = _by_name(
            check_reconciliation(_fb(discovery_impressions=351462))
        )
        assert results["discovery_vs_engagement_impressions"].ok is False


class TestTopPostSanity:
    def test_top_post_exceeding_total_fails(self):
        results = _by_name(
            check_reconciliation(_fb(top_post_impressions=400000))
        )
        assert results["top_post_within_total"].ok is False


class TestToleranceBoundaries:
    def test_identity_1_boundary(self):
        # tol = 0.05 × 112 = 5.6. Expected 2,852.8 × 112 = 319,513.6.
        # Just inside tolerance (Δ ≈ 4.6) passes; just outside (Δ ≈ 6.6)
        # fails. The exact boundary is deliberately not pinned — float
        # multiplication makes Δ == tol equality representation-dependent.
        results = _by_name(
            check_reconciliation(_fb(total_impressions=319509))
        )
        assert results["impressions_per_post_x_post_count"].ok is True
        results = _by_name(
            check_reconciliation(_fb(total_impressions=319507))
        )
        assert results["impressions_per_post_x_post_count"].ok is False

    def test_engagement_rate_half_ulp(self):
        # 8,655 / 319,511 rounds to 0.0271; a stored 0.0272 must fail.
        results = _by_name(
            check_reconciliation(_fb(avg_engagement_rate=0.0272))
        )
        assert results["engagement_rate_recompute"].ok is False
