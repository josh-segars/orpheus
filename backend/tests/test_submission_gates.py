"""Unit tests for the three submission gates in `_apply_submission_gates`.

Gate policy, in order (see the function docstring for the full rationale):

  * 2a filename (ORPHEUS-101) — a ``Basic_`` archive filename rejects
    immediately, and the filename's ``MM-DD-YYYY`` stamp is the *primary*
    recency signal;
  * 2b quality (ORPHEUS-88) — only CRITICAL+MISSING_FILE blocks (Basic or
    corrupt archive). An EMPTY_DATA critical from a genuinely inactive
    member is a valid low-signal report and passes through;
  * 2c freshness (ORPHEUS-100) — an export older than
    ``_STALE_ARCHIVE_DAYS`` rejects, falling back to the analytics XLSX
    date when the filename carries none.

These cases used to drive the gates through the multipart POST /jobs
handler, asserting "no job row was inserted" for rejections and a
downstream 500 as proof-of-pass. That handler was deleted with the
ORPHEUS-108 shim (2026-07-27), so they now target the shared gate
function directly — which is the actual unit under test, and lets a
passing gate be asserted as "returns the parsed data" instead of "fails
later for an unrelated reason". Both live entry points (POST
/jobs/from-uploads today, anything future) route through this function,
so the policy stays pinned here regardless of how the bytes arrive;
`test_jobs_uploads.py` keeps the handler-level parity smoke.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.models.quality import (
    DataQualityReport,
    IssueCategory,
    IssueSeverity,
)
from backend.routers import jobs as jobs_router


CLIENT_ID = "11111111-1111-1111-1111-111111111111"

# A filename with no Basic/Complete prefix and no parseable date, so the
# ORPHEUS-101 filename gate is a no-op unless a test opts into a real
# LinkedIn-style name.
NEUTRAL_FILENAME = "archive.zip"


def _blocking_report(source: str) -> DataQualityReport:
    r = DataQualityReport()
    r.add(
        IssueSeverity.CRITICAL, IssueCategory.MISSING_FILE, source,
        f"{source} not found in archive", "scoring",
    )
    return r


def _empty_report() -> DataQualityReport:
    return DataQualityReport()


def _days_ago(n: int) -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=n)


def _gate(
    *,
    report: DataQualityReport | None = None,
    analytics_date: date | None = None,
    filename: str = NEUTRAL_FILENAME,
):
    """Run the gates with parsing stubbed out.

    `parse_archive_filename` is deliberately NOT patched — the filename
    gate's parsing is part of what these tests cover.
    """
    zip_data = SimpleNamespace()
    xlsx_data = SimpleNamespace()
    with (
        patch.object(
            jobs_router, "parse_zip",
            return_value=(zip_data, report if report is not None else _empty_report()),
        ),
        patch.object(jobs_router, "parse_xlsx", return_value=xlsx_data),
        patch.object(
            jobs_router, "latest_analytics_date", return_value=analytics_date
        ),
    ):
        return jobs_router._apply_submission_gates(
            CLIENT_ID, b"archive-bytes", b"analytics-bytes", filename
        )


# --------------------------------------------------------------------------- #
# Quality gate — ORPHEUS-88
# --------------------------------------------------------------------------- #


def test_missing_shares_rejected_with_basic_archive_guidance():
    """Shares.csv missing → 422 pointing at the Complete/larger archive."""
    with pytest.raises(HTTPException) as exc:
        _gate(report=_blocking_report("Shares.csv"))

    assert exc.value.status_code == 422
    assert "Basic data export" in exc.value.detail
    assert "larger data archive" in exc.value.detail


def test_missing_profile_rejected_with_corrupt_archive_guidance():
    """Profile.csv missing (no Shares issue) → 422 with the generic
    re-download guidance, not the Basic-archive copy."""
    with pytest.raises(HTTPException) as exc:
        _gate(report=_blocking_report("Profile.csv"))

    assert exc.value.status_code == 422
    assert "missing core profile data" in exc.value.detail
    assert "Basic data export" not in exc.value.detail


# --------------------------------------------------------------------------- #
# Freshness gate — ORPHEUS-100
# --------------------------------------------------------------------------- #


def test_stale_export_rejected():
    """Analytics ending well before today → 422 naming the export date."""
    stale = _days_ago(60)
    with pytest.raises(HTTPException) as exc:
        _gate(analytics_date=stale)

    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail
    assert stale.strftime("%B") in exc.value.detail  # month name in guidance


def test_fresh_export_passes_freshness_gate():
    """A recent export clears every gate and returns the parsed payload."""
    zip_data, quality_report, xlsx_data = _gate(analytics_date=_days_ago(3))

    assert zip_data is not None
    assert xlsx_data is not None
    assert not quality_report.has_blocking_issue


def test_boundary_exactly_14_days_passes():
    """Exactly 14 days old is NOT stale (gate is age > 14)."""
    assert _gate(analytics_date=_days_ago(14)) is not None


def test_boundary_15_days_rejected():
    """One day past the threshold is stale."""
    with pytest.raises(HTTPException) as exc:
        _gate(analytics_date=_days_ago(15))

    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail


def test_no_analytics_date_skips_freshness_gate():
    """No parseable analytics date (brand-new account) → skip the check."""
    assert _gate(analytics_date=None) is not None


# --------------------------------------------------------------------------- #
# Filename gate — ORPHEUS-101 (layered on 88 + 100)
# --------------------------------------------------------------------------- #


def test_basic_filename_rejected_regardless_of_content():
    """A Basic_ archive filename rejects at the filename gate even when the
    content report is non-blocking — the filename check runs first."""
    with pytest.raises(HTTPException) as exc:
        _gate(filename="Basic_LinkedInDataExport_01-02-2026.zip")

    assert exc.value.status_code == 422
    assert "Basic data export" in exc.value.detail


def test_filename_date_drives_recency_over_xlsx():
    """A stale filename date rejects even when the XLSX analytics date is
    fresh — the filename is the primary recency signal (ORPHEUS-101)."""
    stale_name = (
        f"Complete_LinkedInDataExport_{_days_ago(60).strftime('%m-%d-%Y')}.zip"
    )
    with pytest.raises(HTTPException) as exc:
        _gate(analytics_date=_days_ago(0), filename=stale_name)

    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail


def test_recency_falls_back_to_xlsx_when_filename_has_no_date():
    """A dateless (but Complete) filename → recency falls back to the XLSX
    analytics date; a stale XLSX date still rejects."""
    with pytest.raises(HTTPException) as exc:
        _gate(
            analytics_date=_days_ago(60),
            filename="Complete_LinkedInDataExport.zip",
        )

    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail


def test_fresh_filename_date_passes_even_without_xlsx_date():
    """A fresh filename date clears recency even when the XLSX carries no
    parseable date."""
    fresh_name = (
        f"Complete_LinkedInDataExport_{_days_ago(2).strftime('%m-%d-%Y')}.zip"
    )
    assert _gate(analytics_date=None, filename=fresh_name) is not None
