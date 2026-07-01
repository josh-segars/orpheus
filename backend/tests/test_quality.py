"""Unit tests for the ORPHEUS-88 quality-gate classification helpers on
DataQualityReport (backend/models/quality.py).

Two independent classifications:

  * blocking — CRITICAL + MISSING_FILE (a core CSV absent → Basic/corrupt
    archive). Drives the POST /jobs reject.
  * data-limited — CRITICAL/WARNING in the data-limitation categories
    (missing_file / empty_data / parse_failure / date_range), EXCLUDING
    MISSING_FIELD (a legitimate profile-completeness score input) and INFO.
    Drives the report banner + advisor/admin chip.

The pivotal distinction ORPHEUS-88 turns on: a Basic archive (missing
Shares.csv) blocks; a Complete archive from a genuinely inactive member
(EMPTY_DATA critical, files present but empty) does NOT block — it's a valid
low-signal report — but it IS data-limited.
"""

from __future__ import annotations

from backend.models.quality import (
    DataQualityReport,
    IssueCategory,
    IssueSeverity,
)


def _basic_archive_report() -> DataQualityReport:
    """Missing Shares.csv (critical) + missing Comments/Reactions (warning) +
    zero behavioral (critical). Shape of Brandon's Basic-archive job."""
    r = DataQualityReport()
    r.add(
        IssueSeverity.CRITICAL, IssueCategory.MISSING_FILE, "Shares.csv",
        "Shares.csv not found — this likely indicates a Basic archive",
        "Dim 2, Dim 3, Dim 4",
    )
    r.add(
        IssueSeverity.WARNING, IssueCategory.MISSING_FILE, "Comments.csv",
        "Comments.csv not found", "Dim 3",
    )
    r.add(
        IssueSeverity.CRITICAL, IssueCategory.EMPTY_DATA, "ZIP archive",
        "No behavioral data found", "Dim 2, Dim 3, Dim 4",
    )
    return r


def _inactive_complete_report() -> DataQualityReport:
    """Complete archive, genuinely inactive member: files present but zero
    behavioral rows. EMPTY_DATA critical, NO missing-file critical."""
    r = DataQualityReport()
    r.add(
        IssueSeverity.CRITICAL, IssueCategory.EMPTY_DATA, "ZIP archive",
        "No behavioral data found (zero posts, comments, and reactions)",
        "Dim 2, Dim 3, Dim 4",
    )
    return r


def _healthy_profile_gaps_report() -> DataQualityReport:
    """Only MISSING_FIELD warnings + INFO — legitimate score inputs, not a
    data limitation. Neither blocking nor data-limited."""
    r = DataQualityReport()
    r.add(
        IssueSeverity.WARNING, IssueCategory.MISSING_FIELD, "Profile.csv",
        "About section is empty — completeness floor will fire", "Dim 1",
    )
    r.add(
        IssueSeverity.INFO, IssueCategory.EMPTY_DATA, "Skills.csv",
        "No skills listed", "Profile Completeness",
    )
    return r


# --- Blocking classification ------------------------------------------------


def test_basic_archive_blocks():
    r = _basic_archive_report()
    assert r.has_blocking_issue is True
    blocking = r.blocking_issues()
    # Only the missing-file critical blocks — not the EMPTY_DATA critical,
    # not the missing-file warning.
    assert len(blocking) == 1
    assert blocking[0].source == "Shares.csv"
    assert blocking[0].category == IssueCategory.MISSING_FILE


def test_inactive_complete_archive_does_not_block():
    """The pivotal case: EMPTY_DATA critical must NOT block — a valid
    low-signal report for a genuinely inactive member."""
    r = _inactive_complete_report()
    assert r.has_blocking_issue is False
    assert r.blocking_issues() == []


def test_healthy_report_does_not_block():
    assert _healthy_profile_gaps_report().has_blocking_issue is False


def test_empty_report_does_not_block():
    assert DataQualityReport().has_blocking_issue is False


# --- Data-limited classification --------------------------------------------


def test_inactive_complete_archive_is_data_limited():
    r = _inactive_complete_report()
    assert r.is_data_limited is True
    notices = r.data_limitation_notices()
    assert len(notices) == 1
    assert "No behavioral data found" in notices[0]


def test_basic_archive_is_data_limited():
    r = _basic_archive_report()
    assert r.is_data_limited is True
    # missing-file critical + missing-file warning + empty_data critical all
    # count; three distinct messages.
    assert len(r.data_limitation_notices()) == 3


def test_profile_field_gaps_are_not_data_limited():
    """MISSING_FIELD warnings and INFO issues never mark a report
    data-limited — the score is supposed to reflect an incomplete profile."""
    r = _healthy_profile_gaps_report()
    assert r.is_data_limited is False
    assert r.data_limitation_notices() == []


def test_parse_failure_and_date_range_warnings_are_data_limited():
    r = DataQualityReport()
    r.add(
        IssueSeverity.WARNING, IssueCategory.PARSE_FAILURE, "Comments.csv",
        "44 comment rows had unparseable dates and were dropped", "Dim 3",
    )
    r.add(
        IssueSeverity.WARNING, IssueCategory.DATE_RANGE, "ZIP archive",
        "Behavioral data spans only 90 days", "Recency",
    )
    assert r.is_data_limited is True
    assert len(r.data_limitation_notices()) == 2


def test_data_limitation_notices_dedup():
    r = DataQualityReport()
    for _ in range(3):
        r.add(
            IssueSeverity.WARNING, IssueCategory.EMPTY_DATA, "ZIP archive",
            "Very sparse behavioral data", "Dim 2",
        )
    assert len(r.data_limitation_notices()) == 1


def test_empty_report_is_not_data_limited():
    assert DataQualityReport().is_data_limited is False
