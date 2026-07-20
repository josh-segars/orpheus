"""Unit tests for backend/ingestion/zip_parser.py — CSV name matching.

ORPHEUS-87: LinkedIn's newer complete archives append the member ID to
per-member behavioral CSVs (Shares_181682616.csv, Comments_181682616.csv,
Reactions_181682616.csv). The original endswith() match could never hit
those, which silently zeroed behavioral scoring (Dims 2/3/4) on any
fresh export — observed live 2026-06-12 as two identical 24.50/Dissonant
runs against a high-activity profile whose old-naming archive scored
81.12/Resonant the same hour.

These tests pin the basename matcher directly: exact names, suffixed
names, exact-over-suffixed preference, nested paths, and the
non-matches that must stay non-matches.
"""

from __future__ import annotations

import io
import zipfile

from datetime import date

from backend.ingestion.zip_parser import (
    _read_csv_from_zip,
    parse_archive_filename,
    parse_zip,
)
from backend.models.quality import IssueCategory, IssueSeverity

MEMBER_ID = "181682616"
CSV_BODY = "Date,ShareLink,ShareCommentary\n2026-06-01,https://x,Hello\n"


def _zip_with(*names: str) -> zipfile.ZipFile:
    """Build an in-memory ZIP containing the given filenames.

    Every entry gets the same minimal CSV body — these tests assert
    which file the matcher picks, not the parse of its contents.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, CSV_BODY)
    buf.seek(0)
    return zipfile.ZipFile(buf)


def test_exact_name_matches():
    zf = _zip_with("Shares.csv")
    rows = _read_csv_from_zip(zf, "Shares.csv")
    assert len(rows) == 1
    assert rows[0]["sharecommentary"] == "Hello"


def test_member_id_suffixed_name_matches():
    """The ORPHEUS-87 regression: Shares_<memberid>.csv must be found."""
    zf = _zip_with(f"Shares_{MEMBER_ID}.csv")
    rows = _read_csv_from_zip(zf, "Shares.csv")
    assert len(rows) == 1


def test_all_three_behavioral_files_suffixed():
    """The exact live shape from Andrew's 2026-06-12 fresh export."""
    zf = _zip_with(
        f"Shares_{MEMBER_ID}.csv",
        f"Comments_{MEMBER_ID}.csv",
        f"Reactions_{MEMBER_ID}.csv",
    )
    for requested in ("Shares.csv", "Comments.csv", "Reactions.csv"):
        assert len(_read_csv_from_zip(zf, requested)) == 1, requested


def test_exact_name_preferred_over_suffixed():
    """When both forms exist, the unsuffixed file wins deterministically."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf_w:
        zf_w.writestr("Shares.csv", "Date,ShareCommentary\n2026-06-01,exact\n")
        zf_w.writestr(
            f"Shares_{MEMBER_ID}.csv",
            "Date,ShareCommentary\n2026-06-01,suffixed\n",
        )
    buf.seek(0)
    rows = _read_csv_from_zip(zipfile.ZipFile(buf), "Shares.csv")
    assert rows[0]["sharecommentary"] == "exact"


def test_nested_path_matches_on_basename():
    zf = _zip_with(f"Export/Shares_{MEMBER_ID}.csv")
    assert len(_read_csv_from_zip(zf, "Shares.csv")) == 1


def test_macosx_metadata_excluded():
    zf = _zip_with("__MACOSX/Shares.csv")
    assert _read_csv_from_zip(zf, "Shares.csv") == []


def test_non_numeric_suffix_does_not_match():
    """Shares_backup.csv is not a member-ID variant; stays unmatched."""
    zf = _zip_with("Shares_backup.csv")
    assert _read_csv_from_zip(zf, "Shares.csv") == []


def test_longer_basename_does_not_match():
    """'Profile Summary.csv' must not satisfy a 'Profile.csv' request."""
    zf = _zip_with("Profile Summary.csv")
    assert _read_csv_from_zip(zf, "Profile.csv") == []


def test_missing_file_returns_empty():
    zf = _zip_with("Connections.csv")
    assert _read_csv_from_zip(zf, "Shares.csv") == []


# --------------------------------------------------------------------------- #
# Missing-file detection must be suffix-tolerant too (regression)
# --------------------------------------------------------------------------- #
#
# ORPHEUS-87 taught the *read* path the _<memberid> suffix but left the
# missing-file *detection* in parse_zip on an exact-name compare. After
# ORPHEUS-88 made a MISSING_FILE critical a hard upload block, a valid
# Complete archive with suffixed CSVs was rejected at upload as if it were
# a Basic archive. These pin the detection path against a realistic
# archive.

_PROFILE_CSV = (
    "First Name,Last Name,Headline,Summary,Industry,Geo Location\n"
    "Ada,Lovelace,Engineer,About me text,Software,London\n"
)
_POSITIONS_CSV = (
    "Company Name,Title,Description,Location,Started On,Finished On\n"
    "Acme,Engineer,Built things,London,Jan 2020,\n"
)
_SKILLS_CSV = "Name\nPython\n"
_RICH_MEDIA_CSV = "Date/Time,Media Description,Media Link\n"
_SHARES_CSV = (
    "Date,ShareLink,ShareCommentary,SharedUrl,Visibility\n"
    "2026-06-01 09:00:00,https://x,Hello world,,PUBLIC\n"
)
_COMMENTS_CSV = "Date,Link,Message\n2026-06-01 09:00:00,https://x,Nice post\n"
_REACTIONS_CSV = "Date,Type,Link\n2026-06-01 09:00:00,LIKE,https://x\n"


def _complete_archive_zip_bytes(member_id: str | None) -> bytes:
    """Build a realistic Complete archive as raw bytes.

    When ``member_id`` is set, the three behavioral CSVs carry the
    ``_<memberid>`` suffix (the modern export shape); otherwise they use
    the classic exact names.
    """
    suffix = f"_{member_id}" if member_id else ""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Profile.csv", _PROFILE_CSV)
        zf.writestr("Positions.csv", _POSITIONS_CSV)
        zf.writestr("Skills.csv", _SKILLS_CSV)
        zf.writestr("Rich_Media.csv", _RICH_MEDIA_CSV)
        zf.writestr(f"Shares{suffix}.csv", _SHARES_CSV)
        zf.writestr(f"Comments{suffix}.csv", _COMMENTS_CSV)
        zf.writestr(f"Reactions{suffix}.csv", _REACTIONS_CSV)
    return buf.getvalue()


def test_suffixed_complete_archive_has_no_missing_file_criticals():
    """A modern Complete export must not report Shares/Comments/Reactions
    as missing, and must not produce any blocking (MISSING_FILE) issue."""
    _, report = parse_zip(_complete_archive_zip_bytes(MEMBER_ID))

    missing = [i.source for i in report.issues if i.category == IssueCategory.MISSING_FILE]
    assert missing == [], f"unexpected missing-file flags: {missing}"
    assert report.has_blocking_issue is False
    # Behavioral data actually parsed through the read path.
    assert report.total_shares == 1
    assert report.total_comments == 1
    assert report.total_reactions == 1


def test_suffixed_and_classic_archives_agree_on_missing_files():
    """The detection path must treat suffixed and classic naming the same."""
    _, suffixed = parse_zip(_complete_archive_zip_bytes(MEMBER_ID))
    _, classic = parse_zip(_complete_archive_zip_bytes(None))

    def missing_files(r):
        return sorted(i.source for i in r.issues if i.category == IssueCategory.MISSING_FILE)

    assert missing_files(suffixed) == missing_files(classic) == []


def test_genuinely_missing_shares_still_flags_and_blocks():
    """The fix must not mask a real Basic archive (no Shares at all)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Profile.csv", _PROFILE_CSV)
        zf.writestr("Positions.csv", _POSITIONS_CSV)
        zf.writestr("Skills.csv", _SKILLS_CSV)
    _, report = parse_zip(buf.getvalue())

    missing = {i.source for i in report.issues if i.category == IssueCategory.MISSING_FILE}
    assert "Shares.csv" in missing
    assert report.has_blocking_issue is True


# --------------------------------------------------------------------------- #
# Complete-fingerprint: zero-activity Complete exports — ORPHEUS-110
# --------------------------------------------------------------------------- #
#
# LinkedIn omits empty per-activity CSVs entirely, so a genuine Complete
# export from a member who has never posted has no Shares.csv — which the
# MISSING_FILE check read as a renamed Basic archive and hard-blocked at
# upload (hit live by a real beta client, 2026-07-20). When the archive
# carries >=2 Complete-only fingerprint files, absent behavioral CSVs are
# EMPTY_DATA (non-blocking, still data-limiting) instead.

_FINGERPRINT_STUB = "Header\nvalue\n"


def _zero_activity_complete_bytes(
    *fingerprints: str, extra: dict[str, str] | None = None
) -> bytes:
    """A Complete-shaped archive with no behavioral CSVs at all."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Profile.csv", _PROFILE_CSV)
        zf.writestr("Positions.csv", _POSITIONS_CSV)
        zf.writestr("Skills.csv", _SKILLS_CSV)
        zf.writestr("Rich_Media.csv", _RICH_MEDIA_CSV)
        for name in fingerprints:
            zf.writestr(name, _FINGERPRINT_STUB)
        for name, body in (extra or {}).items():
            zf.writestr(name, body)
    return buf.getvalue()


def test_zero_activity_complete_export_passes_gate():
    """Fingerprinted archive with no behavioral CSVs must not block."""
    _, report = parse_zip(
        _zero_activity_complete_bytes("Ad_Targeting.csv", "SearchQueries.csv")
    )

    assert report.has_blocking_issue is False
    missing = [i for i in report.issues if i.category == IssueCategory.MISSING_FILE]
    assert missing == [], f"unexpected MISSING_FILE issues: {missing}"
    # Shares absence is reported as a CRITICAL EMPTY_DATA signal instead —
    # non-blocking per the ORPHEUS-88 decision, but still data-limiting.
    shares_empty = [
        i for i in report.issues
        if i.category == IssueCategory.EMPTY_DATA and i.source == "Shares.csv"
    ]
    assert len(shares_empty) == 1
    assert shares_empty[0].severity == IssueSeverity.CRITICAL
    assert report.is_data_limited is True


def test_nicole_shape_reactions_only_complete_export():
    """The exact live shape from 2026-07-20: fingerprints + suffixed
    Reactions with rows, no Shares or Comments anywhere."""
    raw = _zero_activity_complete_bytes(
        "Ad_Targeting.csv",
        "Inferences_about_you.csv",
        "SearchQueries.csv",
        "Logins.csv",
        "Ads Clicked.csv",
        "Security Challenges.csv",
        extra={"Reactions_163027716.csv": _REACTIONS_CSV},
    )
    zip_data, report = parse_zip(raw)

    assert report.has_blocking_issue is False
    assert report.total_reactions == 1  # suffixed file parsed (ORPHEUS-87)
    empty_sources = {
        i.source for i in report.issues
        if i.category == IssueCategory.EMPTY_DATA
    }
    assert "Shares.csv" in empty_sources
    assert "Comments.csv" in empty_sources
    assert "Reactions.csv" not in empty_sources  # present, not absent


def test_single_fingerprint_is_not_enough():
    """One coincidental Complete-only file must not flip the classification
    — a renamed Basic archive stays blocked."""
    _, report = parse_zip(_zero_activity_complete_bytes("Logins.csv"))

    missing = {i.source for i in report.issues if i.category == IssueCategory.MISSING_FILE}
    assert "Shares.csv" in missing
    assert report.has_blocking_issue is True


def test_fingerprint_files_tolerate_member_id_suffix():
    """Fingerprint matching rides _csv_name_matches, so suffixed
    Complete-only files count."""
    _, report = parse_zip(
        _zero_activity_complete_bytes(
            "Ad_Targeting_163027716.csv", "SearchQueries_163027716.csv"
        )
    )
    assert report.has_blocking_issue is False


def test_fingerprint_changes_nothing_when_behavioral_files_present():
    """A normal Complete archive is unaffected: no MISSING_FILE, and no
    per-file EMPTY_DATA entries for files that exist."""
    _, report = parse_zip(_complete_archive_zip_bytes(MEMBER_ID))

    per_file_empty = [
        i for i in report.issues
        if i.category == IssueCategory.EMPTY_DATA
        and i.source in ("Shares.csv", "Comments.csv", "Reactions.csv")
    ]
    assert per_file_empty == []
    assert report.has_blocking_issue is False


# --------------------------------------------------------------------------- #
# parse_archive_filename — ORPHEUS-101
# --------------------------------------------------------------------------- #
#
# Real format (Josh, 2026-07-01): Complete_LinkedInDataExport_06-19-2026.zip.
# Both fields independently optional; the filename is user-renameable.


def test_filename_complete_with_date():
    assert parse_archive_filename(
        "Complete_LinkedInDataExport_06-19-2026.zip"
    ) == ("complete", date(2026, 6, 19))


def test_filename_basic_with_date():
    assert parse_archive_filename(
        "Basic_LinkedInDataExport_01-02-2026.zip"
    ) == ("basic", date(2026, 1, 2))


def test_filename_case_insensitive_prefix():
    t, d = parse_archive_filename("complete_linkedindataexport_06-19-2026.zip")
    assert t == "complete"
    assert d == date(2026, 6, 19)


def test_filename_nested_path_uses_basename():
    t, d = parse_archive_filename(
        "/Users/x/Downloads/Complete_LinkedInDataExport_06-19-2026.zip"
    )
    assert t == "complete"
    assert d == date(2026, 6, 19)


def test_filename_renamed_yields_no_signals():
    assert parse_archive_filename("my linkedin data.zip") == (None, None)


def test_filename_complete_without_date():
    assert parse_archive_filename("Complete_LinkedInDataExport.zip") == (
        "complete",
        None,
    )


def test_filename_invalid_date_ignored():
    # 13-40 isn't a real month/day → date is None, type still resolves.
    assert parse_archive_filename(
        "Complete_LinkedInDataExport_13-40-2026.zip"
    ) == ("complete", None)


def test_filename_none_or_empty():
    assert parse_archive_filename(None) == (None, None)
    assert parse_archive_filename("") == (None, None)
