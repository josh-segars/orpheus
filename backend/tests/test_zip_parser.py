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
from backend.models.quality import IssueCategory

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
