"""Pre-publish reconciliation identities (ORPHEUS-114 c).

Derived metrics must reconcile to their stored operands before anything is
persisted or published. Bug A (ORPHEUS-112) — avg impressions per post
understated 3.3x–23.7x — is exactly the class this catches:
`impressions_per_post × post_count ≈ total_impressions` fails loudly on the
old per-day denominator (875.4 × 112 vs 319,511 misses by ~221k).

Semantics:

  * Each identity is SKIPPED when any operand is None — a partial-XLSX job
    (no analytics upload, empty sheets) must not fail on data it never had.
    Rows written before ORPHEUS-114 lack the operands entirely and are never
    retro-checked (the gate runs in the worker on fresh scoring output).
  * Tolerances derive from stored rounding: a value rounded to 0.1 carries
    up to 0.05 of hidden precision per multiplied unit.
  * `unique_members_reached` gets a RANGE check, never a sum-of-dailies
    equality — it is unique-cumulative over the window; members repeat
    across days, so no arithmetic over daily rows reproduces it.
  * Failure is blocking: `stage_scoring` raises ReconciliationError before
    the scores upsert, the worker's retry loop exhausts (deterministic
    input → deterministic failure), and the job lands `failed` with every
    failed identity in error_message. Passing identities are logged (the
    flagging half). Nothing half-checked ever reaches a client.

Fits the ORPHEUS-88 shape: classification lives on the model
(IdentityResult), one transport-independent policy function
(`check_reconciliation`), callers decide block-vs-log. Consumed by
`backend/workers/processor.py` (blocking) and
`backend/scripts/regenerate_report.py` (verify step).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.models.scoring import ForwardBriefData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentityResult:
    """Outcome of one reconciliation identity."""

    name: str
    ok: bool
    detail: str  # expected vs actual vs tolerance, human-readable


class ReconciliationError(Exception):
    """One or more reconciliation identities failed (blocking)."""

    def __init__(self, failures: list[IdentityResult]) -> None:
        self.failures = failures
        super().__init__(
            "Reconciliation failed: "
            + "; ".join(f"{f.name}: {f.detail}" for f in failures)
        )


def check_reconciliation(fb: ForwardBriefData) -> list[IdentityResult]:
    """Run every applicable identity against a ForwardBriefData.

    Returns one IdentityResult per identity that could run (operands
    present); identities with missing operands are silently skipped.
    """
    q = fb.quantitative
    results: list[IdentityResult] = []

    # 1. impressions_per_post × post_count ≈ total_impressions (bug A).
    #    Stored value is rounded to 0.1 → tolerance 0.05 per post, plus a
    #    1-impression floor for tiny profiles.
    if (
        q.avg_impressions_per_post is not None
        and q.post_count is not None
        and q.post_count > 0
        and q.total_impressions is not None
    ):
        expected = q.avg_impressions_per_post * q.post_count
        tolerance = max(1.0, 0.05 * q.post_count)
        delta = abs(expected - q.total_impressions)
        results.append(
            IdentityResult(
                name="impressions_per_post_x_post_count",
                ok=delta <= tolerance,
                detail=(
                    f"{q.avg_impressions_per_post:,.1f} × {q.post_count} = "
                    f"{expected:,.1f} vs total_impressions "
                    f"{q.total_impressions:,} (|Δ|={delta:,.1f}, "
                    f"tol={tolerance:,.1f})"
                ),
            )
        )

    # 2. follower_growth_rate × weeks_observed ≈ net_new_followers.
    #    Rate rounded to 0.1 → tolerance 0.05 per week, 1-follower floor.
    if (
        q.follower_growth_rate is not None
        and q.followers_weeks_observed is not None
        and q.followers_weeks_observed > 0
        and q.net_new_followers is not None
    ):
        expected = q.follower_growth_rate * q.followers_weeks_observed
        tolerance = max(1.0, 0.05 * q.followers_weeks_observed)
        delta = abs(expected - q.net_new_followers)
        results.append(
            IdentityResult(
                name="follower_rate_x_weeks",
                ok=delta <= tolerance,
                detail=(
                    f"{q.follower_growth_rate:.1f}/wk × "
                    f"{q.followers_weeks_observed:.2f} wks = {expected:,.1f} "
                    f"vs net_new_followers {q.net_new_followers:,} "
                    f"(|Δ|={delta:,.1f}, tol={tolerance:,.1f})"
                ),
            )
        )

    # 3. engagement_rate == engagements / impressions, recomputed exactly.
    #    Stored at 4dp → half-ulp tolerance.
    if (
        q.avg_engagement_rate is not None
        and q.total_engagements is not None
        and q.total_impressions is not None
        and q.total_impressions > 0
    ):
        expected = round(q.total_engagements / q.total_impressions, 4)
        delta = abs(expected - q.avg_engagement_rate)
        results.append(
            IdentityResult(
                name="engagement_rate_recompute",
                ok=delta <= 0.00005,
                detail=(
                    f"{q.total_engagements:,} / {q.total_impressions:,} = "
                    f"{expected:.4f} vs stored {q.avg_engagement_rate:.4f} "
                    f"(|Δ|={delta:.5f}, tol=0.00005)"
                ),
            )
        )

    # 4. members_reached range check — unique-cumulative, NEVER summed from
    #    dailies. It must be positive and cannot exceed total impressions
    #    (each unique member contributes at least one impression).
    if (
        q.unique_members_reached is not None
        and q.total_impressions is not None
        and q.total_impressions > 0
    ):
        ok = 0 < q.unique_members_reached <= q.total_impressions
        results.append(
            IdentityResult(
                name="members_reached_range",
                ok=ok,
                detail=(
                    f"unique_members_reached {q.unique_members_reached:,} "
                    f"must be in (0, total_impressions "
                    f"{q.total_impressions:,}]"
                ),
            )
        )

    # 5. Cross-source: DISCOVERY's own impressions total vs the ENGAGEMENT
    #    dailies sum. Same export, same window — beyond 1% the export is
    #    internally inconsistent and no derived reach metric can be trusted.
    if (
        q.discovery_impressions is not None
        and q.discovery_impressions > 0
        and q.total_impressions is not None
        and q.total_impressions > 0
    ):
        delta = abs(q.discovery_impressions - q.total_impressions)
        tolerance = 0.01 * max(q.discovery_impressions, q.total_impressions)
        results.append(
            IdentityResult(
                name="discovery_vs_engagement_impressions",
                ok=delta <= tolerance,
                detail=(
                    f"DISCOVERY impressions {q.discovery_impressions:,} vs "
                    f"sum(ENGAGEMENT dailies) {q.total_impressions:,} "
                    f"(|Δ|={delta:,}, tol={tolerance:,.0f} = 1%)"
                ),
            )
        )

    # 6. Sanity: the single best post can't out-impress the whole window.
    if (
        q.top_post_impressions is not None
        and q.total_impressions is not None
        and q.total_impressions > 0
    ):
        results.append(
            IdentityResult(
                name="top_post_within_total",
                ok=q.top_post_impressions <= q.total_impressions,
                detail=(
                    f"top_post_impressions {q.top_post_impressions:,} must "
                    f"not exceed total_impressions {q.total_impressions:,}"
                ),
            )
        )

    return results


def assert_reconciled(fb: ForwardBriefData, job_id: str = "") -> None:
    """Blocking wrapper: log every identity, raise on any failure."""
    results = check_reconciliation(fb)
    failures = [r for r in results if not r.ok]
    prefix = f"[{job_id}] " if job_id else ""
    for r in results:
        if r.ok:
            logger.info("%sRECONCILIATION ok — %s: %s", prefix, r.name, r.detail)
        else:
            logger.error(
                "%sRECONCILIATION FAILED — %s: %s", prefix, r.name, r.detail
            )
    if failures:
        raise ReconciliationError(failures)
