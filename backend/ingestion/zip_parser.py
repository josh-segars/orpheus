"""Parse the LinkedIn Complete archive (ZIP) into structured data.

The Complete archive contains CSVs with profile, positions, skills,
media uploads, and post history. The Basic archive is insufficient —
it omits Shares.csv, which is required for Consistency scoring.

Verified against actual LinkedIn export from 2026-03-17.
"""

import csv
import io
import logging
import zipfile
from pathlib import Path

from .types import (
    ZipData,
    ProfileData,
    PositionData,
    RichMediaItem,
    ShareItem,
    CommentItem,
    ReactionItem,
)
from backend.models.quality import (
    DataQualityReport,
    IssueSeverity,
    IssueCategory,
)

logger = logging.getLogger(__name__)


# Files the parser looks for in every archive
EXPECTED_CSV_FILES = [
    "Profile.csv",
    "Positions.csv",
    "Skills.csv",
    "Rich_Media.csv",
    "Shares.csv",
    "Comments.csv",
    "Reactions.csv",
]


def _normalize_header(header: str) -> str:
    """Normalize a CSV header to snake_case for consistent field access.

    LinkedIn CSV headers use title casing and spaces:
    'First Name', 'Company Name', 'Started On', etc.
    """
    if header is None:
        return ""
    return header.strip().lower().replace(" ", "_").replace("/", "_")


def _read_csv_from_zip(
    zf: zipfile.ZipFile, filename: str
) -> list[dict[str, str]]:
    """Read a CSV file from the ZIP archive and return rows as dicts.

    Handles UTF-8 BOM encoding that LinkedIn includes.
    LinkedIn nests CSVs in a subdirectory or at root — we match by name.
    Returns an empty list if the file is not found.
    """
    matching = [
        name for name in zf.namelist()
        if name.lower().endswith(filename.lower())
        and not name.startswith("__MACOSX")
    ]

    if not matching:
        logger.warning("CSV not found in archive: %s", filename)
        return []

    if len(matching) > 1:
        logger.warning(
            "Multiple matches for %s: %s — using first",
            filename, matching,
        )

    with zf.open(matching[0]) as f:
        text = f.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            normalized = {
                _normalize_header(k): v
                for k, v in row.items()
                if k is not None  # trailing commas produce None keys
            }
            rows.append(normalized)
        return rows


def _get(row: dict[str, str], *keys: str, default: str = "") -> str:
    """Get the first matching key from a row dict.

    Checks multiple possible column names for resilience
    across LinkedIn export versions.
    """
    for key in keys:
        if key in row and row[key]:
            return row[key].strip()
    return default


def _parse_profile(rows: list[dict[str, str]]) -> ProfileData:
    """Parse Profile.csv — single row with profile fields.

    Known headers: first_name, last_name, maiden_name, address,
    birth_date, headline, summary, industry, zip_code, geo_location,
    twitter_handles, websites, instant_messengers
    """
    if not rows:
        logger.warning("Profile.csv is empty")
        return ProfileData()

    row = rows[0]
    return ProfileData(
        first_name=_get(row, "first_name"),
        last_name=_get(row, "last_name"),
        headline=_get(row, "headline"),
        summary=_get(row, "summary"),
        industry=_get(row, "industry"),
        geo_location=_get(row, "geo_location", "location"),
        websites=_get(row, "websites"),
    )


def _parse_positions(rows: list[dict[str, str]]) -> list[PositionData]:
    """Parse Positions.csv — one row per role.

    Known headers: company_name, title, description, location,
    started_on, finished_on
    """
    positions = []
    for row in rows:
        positions.append(
            PositionData(
                company_name=_get(row, "company_name"),
                title=_get(row, "title"),
                description=_get(row, "description"),
                location=_get(row, "location"),
                started_on=_get(row, "started_on"),
                finished_on=_get(row, "finished_on"),
            )
        )
    return positions


def _parse_skills(rows: list[dict[str, str]]) -> list[str]:
    """Parse Skills.csv — one row per skill.

    Known headers: name
    """
    skills = []
    for row in rows:
        name = _get(row, "name")
        if name:
            skills.append(name)
    return skills


def _parse_rich_media(rows: list[dict[str, str]]) -> list[RichMediaItem]:
    """Parse Rich_Media.csv — media uploads including profile/banner photos.

    Known headers: date_time, media_description, media_link
    (original: Date/Time, Media Description, Media Link)

    The date_time field is a human-readable sentence like:
    "You changed your profile photo on Jan 5, 2024 at 3:22 PM"
    "You uploaded a background photo on March 1, 2023 at 1:00 PM"
    "You uploaded a feed document on March 12, 2025 at 10:07 AM"

    We extract the media type from this sentence.
    """
    type_keywords = {
        "profile photo": "PROFILE_PHOTO",
        "background photo": "BACKGROUND_PHOTO",
        "profile image": "PROFILE_PHOTO",
        "background image": "BACKGROUND_PHOTO",
        "banner": "BACKGROUND_PHOTO",
        "feed document": "FEED_DOCUMENT",
        "feed image": "FEED_IMAGE",
        "feed video": "FEED_VIDEO",
        "article cover photo": "ARTICLE_COVER",
        "article inline photo": "ARTICLE_INLINE",
    }

    items = []
    for row in rows:
        raw = _get(row, "date_time")
        link = _get(row, "media_link")

        # Determine type from the sentence
        media_type = "OTHER"
        raw_lower = raw.lower()
        for keyword, mtype in type_keywords.items():
            if keyword in raw_lower:
                media_type = mtype
                break

        items.append(
            RichMediaItem(
                type=media_type,
                date_time_raw=raw,
                media_link=link,
            )
        )

    return items


def _parse_shares(rows: list[dict[str, str]]) -> list[ShareItem]:
    """Parse Shares.csv — post history with dates and content.

    Known headers: date, sharelink, sharecommentary,
    sharedurl, mediaurl, visibility
    """
    shares = []
    for row in rows:
        share_date = _get(row, "date")
        if share_date:
            shares.append(
                ShareItem(
                    date=share_date,
                    share_link=_get(row, "sharelink"),
                    share_commentary=_get(row, "sharecommentary"),
                    shared_url=_get(row, "sharedurl"),
                    visibility=_get(row, "visibility"),
                )
            )
    return shares


def _parse_comments(rows: list[dict[str, str]]) -> list[CommentItem]:
    """Parse Comments.csv — one row per comment on another person's post.

    Known headers: date, link, message
    (original: Date, Link, Message)

    Used for Engagement Quality Ratio scoring — the ratio of
    substantive outbound engagement (comments) to passive engagement
    (reactions) within the scoring window.
    """
    comments = []
    for row in rows:
        comment_date = _get(row, "date")
        if comment_date:
            comments.append(
                CommentItem(
                    date=comment_date,
                    link=_get(row, "link"),
                    message=_get(row, "message"),
                )
            )
    return comments


def _parse_reactions(rows: list[dict[str, str]]) -> list[ReactionItem]:
    """Parse Reactions.csv — one row per reaction on another person's post.

    Known headers: date, type, link
    (original: Date, Type, Link)

    Type values observed: LIKE, INTEREST, PRAISE,
    ENTERTAINMENT, APPRECIATION, EMPATHY, MAYBE.

    Used alongside Comments.csv for Engagement Quality Ratio scoring.
    """
    reactions = []
    for row in rows:
        reaction_date = _get(row, "date")
        if reaction_date:
            reactions.append(
                ReactionItem(
                    date=reaction_date,
                    reaction_type=_get(row, "type"),
                    link=_get(row, "link"),
                )
            )
    return reactions


def _check_date_parseable(date_str: str) -> bool:
    """Check if a date string is parseable by the scoring engine."""
    if not date_str or not date_str.strip():
        return False
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            datetime.strptime(date_str.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def _find_date_range(items_with_dates: list[dict]) -> tuple[str | None, str | None]:
    """Find the earliest and latest parseable dates in a list of items.

    Items are dicts with a 'date' key (from parsed CSVs).
    Returns (earliest, latest) as ISO strings, or (None, None).
    """
    from datetime import datetime
    dates = []
    for item in items_with_dates:
        d = item.get("date", "")
        if not d:
            continue
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
            try:
                dates.append(datetime.strptime(d.strip(), fmt).date())
                break
            except ValueError:
                continue
    if not dates:
        return None, None
    return str(min(dates)), str(max(dates))


def validate_zip_data(
    zip_data: ZipData,
    report: DataQualityReport,
    share_rows: list[dict],
    comment_rows: list[dict],
    reaction_rows: list[dict],
):
    """Run field-level quality checks on parsed ZIP data.

    Mutates the report in place, adding issues as they're found.
    """
    profile = zip_data.profile

    # --- Profile field checks (affect Dim 1 completeness floor) ---
    if not profile.headline:
        report.add(
            IssueSeverity.WARNING, IssueCategory.MISSING_FIELD,
            "Profile.csv", "Headline is empty — completeness floor will fire, capping Dim 1 at 50%",
            "Dim 1 (Profile Signal Clarity)", field="headline",
        )

    if not profile.summary:
        report.add(
            IssueSeverity.WARNING, IssueCategory.MISSING_FIELD,
            "Profile.csv", "About section is empty — completeness floor will fire, capping Dim 1 at 50%",
            "Dim 1 (Profile Signal Clarity)", field="summary",
        )

    if not profile.industry:
        report.add(
            IssueSeverity.WARNING, IssueCategory.MISSING_FIELD,
            "Profile.csv", "Industry field is empty — completeness floor will fire, capping Dim 1 at 50%",
            "Dim 1 (Profile Signal Clarity)", field="industry",
        )

    if not zip_data.positions:
        report.add(
            IssueSeverity.WARNING, IssueCategory.MISSING_FIELD,
            "Positions.csv", "No job history found — completeness floor will fire, capping Dim 1 at 50%",
            "Dim 1 (Profile Signal Clarity)", field="job_history",
        )
    else:
        # Check current role has a description
        current = zip_data.positions[0]
        if not current.description:
            report.add(
                IssueSeverity.INFO, IssueCategory.MISSING_FIELD,
                "Positions.csv",
                f"Current role ({current.title} at {current.company_name}) has no description",
                "Dim 1 — Experience Description Quality sub-dimension",
                field="description",
            )

    # --- Skills ---
    if not zip_data.skills:
        report.add(
            IssueSeverity.INFO, IssueCategory.EMPTY_DATA,
            "Skills.csv", "No skills listed — affects Profile Completeness sub-dimension",
            "Dim 1 — Profile Completeness sub-dimension",
        )

    # --- Behavioral data: date parsing ---
    bad_share_dates = sum(1 for r in share_rows if r.get("date") and not _check_date_parseable(r["date"]))
    if bad_share_dates:
        report.add(
            IssueSeverity.WARNING, IssueCategory.PARSE_FAILURE,
            "Shares.csv",
            f"{bad_share_dates} post(s) have unparseable dates and will be excluded from scoring",
            "Dim 2 (Behavioral Signal Strength) — Posting Presence, Continuity",
            field="date", rows_affected=bad_share_dates,
        )

    bad_comment_dates = sum(1 for r in comment_rows if r.get("date") and not _check_date_parseable(r["date"]))
    if bad_comment_dates:
        report.add(
            IssueSeverity.WARNING, IssueCategory.PARSE_FAILURE,
            "Comments.csv",
            f"{bad_comment_dates} comment(s) have unparseable dates and will be excluded from scoring",
            "Dim 2 — Continuity; Dim 3 — Engagement Quality",
            field="date", rows_affected=bad_comment_dates,
        )

    bad_reaction_dates = sum(1 for r in reaction_rows if r.get("date") and not _check_date_parseable(r["date"]))
    if bad_reaction_dates:
        report.add(
            IssueSeverity.WARNING, IssueCategory.PARSE_FAILURE,
            "Reactions.csv",
            f"{bad_reaction_dates} reaction(s) have unparseable dates and will be excluded from scoring",
            "Dim 2 — History Depth; Dim 3 — Engagement Quality",
            field="date", rows_affected=bad_reaction_dates,
        )

    # --- Behavioral data volume ---
    total_behavioral = len(zip_data.shares) + len(zip_data.comments) + len(zip_data.reactions)
    if total_behavioral == 0:
        report.add(
            IssueSeverity.CRITICAL, IssueCategory.EMPTY_DATA,
            "ZIP archive",
            "No behavioral data found (zero posts, comments, and reactions) — "
            "Dimensions 2, 3, and 4 cannot be scored meaningfully",
            "Dim 2, Dim 3, Dim 4",
        )
    elif total_behavioral < 10:
        report.add(
            IssueSeverity.WARNING, IssueCategory.EMPTY_DATA,
            "ZIP archive",
            f"Very sparse behavioral data ({total_behavioral} total actions) — "
            f"scores will reflect minimal activity",
            "Dim 2, Dim 3",
        )

    # --- Date range coverage ---
    all_dated_rows = share_rows + comment_rows + reaction_rows
    earliest, latest = _find_date_range(all_dated_rows)
    report.date_range_start = earliest
    report.date_range_end = latest

    if earliest and latest:
        from datetime import date as date_type
        start = date_type.fromisoformat(earliest)
        end = date_type.fromisoformat(latest)
        span_days = (end - start).days
        if span_days < 180:
            report.add(
                IssueSeverity.WARNING, IssueCategory.DATE_RANGE,
                "ZIP archive",
                f"Behavioral data spans only {span_days} days ({earliest} to {latest}) — "
                f"the scoring window is 365 days. Recency and History Depth may be understated.",
                "Dim 2 — History Depth, Recency",
            )

    # --- Rich media (photo check for Forward Brief) ---
    has_photo = any(item.type == "PROFILE_PHOTO" for item in zip_data.rich_media)
    if not has_photo and zip_data.rich_media:
        report.add(
            IssueSeverity.INFO, IssueCategory.MISSING_FIELD,
            "Rich_Media.csv",
            "No profile photo upload found in media history — "
            "this does not affect scoring but is noted in the Forward Brief",
            "Forward Brief — Visual Professionalism flag",
            field="profile_photo",
        )


def parse_zip(source: bytes | str | Path) -> tuple[ZipData, DataQualityReport]:
    """Parse a LinkedIn Complete archive into structured data.

    Args:
        source: Either raw bytes of the ZIP file, or a path to it.

    Returns:
        Tuple of (ZipData, DataQualityReport). The quality report
        contains any issues found during parsing.

    Raises:
        zipfile.BadZipFile: If the source is not a valid ZIP.
        FileNotFoundError: If source is a path that doesn't exist.
    """
    report = DataQualityReport(
        zip_files_expected=EXPECTED_CSV_FILES,
    )

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"ZIP file not found: {path}")
        zf = zipfile.ZipFile(path, "r")
    else:
        zf = zipfile.ZipFile(io.BytesIO(source), "r")

    with zf:
        # Discover what's in the archive
        all_names = zf.namelist()
        csv_files = [
            n for n in all_names
            if n.lower().endswith(".csv") and not n.startswith("__MACOSX")
        ]
        report.zip_files_found = csv_files
        logger.info("ZIP contains %d CSV files: %s", len(csv_files), csv_files)

        # Read all CSVs
        profile_rows = _read_csv_from_zip(zf, "Profile.csv")
        position_rows = _read_csv_from_zip(zf, "Positions.csv")
        skill_rows = _read_csv_from_zip(zf, "Skills.csv")
        media_rows = _read_csv_from_zip(zf, "Rich_Media.csv")
        share_rows = _read_csv_from_zip(zf, "Shares.csv")
        comment_rows = _read_csv_from_zip(zf, "Comments.csv")
        reaction_rows = _read_csv_from_zip(zf, "Reactions.csv")

        # Check for missing files
        found_lower = {n.split("/")[-1].lower() for n in csv_files}

        if "profile.csv" not in found_lower:
            report.add(
                IssueSeverity.CRITICAL, IssueCategory.MISSING_FILE,
                "Profile.csv", "Profile.csv not found in archive — cannot score Dimension 1",
                "Dim 1 (Profile Signal Clarity)",
            )

        if "shares.csv" not in found_lower:
            report.add(
                IssueSeverity.CRITICAL, IssueCategory.MISSING_FILE,
                "Shares.csv",
                "Shares.csv not found — this likely indicates a Basic archive "
                "was uploaded instead of Complete. Behavioral scoring (Dim 2, 3, 4) "
                "will be severely limited.",
                "Dim 2, Dim 3, Dim 4",
            )

        if "comments.csv" not in found_lower:
            report.add(
                IssueSeverity.WARNING, IssueCategory.MISSING_FILE,
                "Comments.csv",
                "Comments.csv not found — Engagement Quality scoring will use "
                "reactions only. Continuity metric will undercount active weeks.",
                "Dim 2 — Continuity; Dim 3 — Engagement Quality Score",
            )

        if "reactions.csv" not in found_lower:
            report.add(
                IssueSeverity.WARNING, IssueCategory.MISSING_FILE,
                "Reactions.csv",
                "Reactions.csv not found — Engagement Presence and Quality "
                "scoring will use comments only.",
                "Dim 2 — History Depth; Dim 3 — Outbound Engagement Presence",
            )

        # Parse data
        zip_data = ZipData(
            profile=_parse_profile(profile_rows),
            positions=_parse_positions(position_rows),
            skills=_parse_skills(skill_rows),
            rich_media=_parse_rich_media(media_rows),
            shares=_parse_shares(share_rows),
            comments=_parse_comments(comment_rows),
            reactions=_parse_reactions(reaction_rows),
        )

        # Record counts
        report.total_shares = len(zip_data.shares)
        report.total_comments = len(zip_data.comments)
        report.total_reactions = len(zip_data.reactions)

        # Run field-level validation
        validate_zip_data(zip_data, report, share_rows, comment_rows, reaction_rows)

        logger.info(
            "ZIP parsed — %d shares, %d comments, %d reactions. Quality: %s",
            report.total_shares, report.total_comments, report.total_reactions,
            report.summary(),
        )

        return zip_data, report
