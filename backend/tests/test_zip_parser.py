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

from backend.ingestion.zip_parser import _read_csv_from_zip

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
