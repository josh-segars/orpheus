"""Unit tests for the ORPHEUS-100 analytics-freshness helper
(backend/ingestion/xlsx_parser.py::latest_analytics_date).

The newest date the analytics export covers is the freshness signal the
POST /jobs gate uses. It comes from the ENGAGEMENT/FOLLOWERS daily series
(max), falling back to the DISCOVERY period-end string, and is None when
nothing is parseable.
"""

from __future__ import annotations

from datetime import date

from backend.ingestion.types import (
    DiscoverySummary,
    EngagementRow,
    FollowersData,
    FollowersRow,
    XlsxData,
)
from backend.ingestion.xlsx_parser import latest_analytics_date


def _xlsx(
    *,
    engagement_dates: list[str] | None = None,
    follower_dates: list[str] | None = None,
    period: str = "",
) -> XlsxData:
    return XlsxData(
        discovery=DiscoverySummary(period=period),
        engagement=[EngagementRow(date=d) for d in (engagement_dates or [])],
        followers=FollowersData(
            rows=[FollowersRow(date=d) for d in (follower_dates or [])]
        ),
    )


def test_max_across_engagement_and_followers():
    x = _xlsx(
        engagement_dates=["2026-06-25", "2026-06-28"],
        follower_dates=["2026-06-27", "2026-06-20"],
    )
    assert latest_analytics_date(x) == date(2026, 6, 28)


def test_followers_can_be_the_newest():
    x = _xlsx(
        engagement_dates=["2026-06-01"],
        follower_dates=["2026-06-30"],
    )
    assert latest_analytics_date(x) == date(2026, 6, 30)


def test_unparseable_daily_dates_ignored():
    x = _xlsx(engagement_dates=["not-a-date", "2026-05-10", ""])
    assert latest_analytics_date(x) == date(2026, 5, 10)


def test_falls_back_to_period_end_when_no_daily_rows():
    x = _xlsx(period="3/17/2025 - 3/16/2026")
    assert latest_analytics_date(x) == date(2026, 3, 16)


def test_daily_rows_win_over_period_end():
    """When both are present the daily series is used (period is a fallback)."""
    x = _xlsx(
        engagement_dates=["2026-06-28"],
        period="3/17/2025 - 3/16/2026",
    )
    assert latest_analytics_date(x) == date(2026, 6, 28)


def test_none_when_nothing_parseable():
    x = _xlsx(engagement_dates=["bad"], period="garbage-no-range")
    assert latest_analytics_date(x) is None


def test_none_on_empty_export():
    assert latest_analytics_date(XlsxData()) is None
