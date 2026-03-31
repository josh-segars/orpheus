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

logger = logging.getLogger(__name__)


def _normalize_header(header: str) -> str:
    """Normalize a CSV header to snake_case for consistent field access.

    LinkedIn CSV headers use title casing and spaces:
    'First Name', 'Company Name', 'Started On', etc.
    """
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
            normalized = {_normalize_header(k): v for k, v in row.items()}
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


def parse_zip(source: bytes | str | Path) -> ZipData:
    """Parse a LinkedIn Complete archive into structured data.

    Args:
        source: Either raw bytes of the ZIP file, or a path to it.

    Returns:
        ZipData with all parsed sections populated.

    Raises:
        zipfile.BadZipFile: If the source is not a valid ZIP.
        FileNotFoundError: If source is a path that doesn't exist.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"ZIP file not found: {path}")
        zf = zipfile.ZipFile(path, "r")
    else:
        zf = zipfile.ZipFile(io.BytesIO(source), "r")

    with zf:
        csv_files = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        logger.info("ZIP contains %d CSV files: %s", len(csv_files), csv_files)

        profile_rows = _read_csv_from_zip(zf, "Profile.csv")
        position_rows = _read_csv_from_zip(zf, "Positions.csv")
        skill_rows = _read_csv_from_zip(zf, "Skills.csv")
        media_rows = _read_csv_from_zip(zf, "Rich_Media.csv")
        share_rows = _read_csv_from_zip(zf, "Shares.csv")
        comment_rows = _read_csv_from_zip(zf, "Comments.csv")
        reaction_rows = _read_csv_from_zip(zf, "Reactions.csv")

        if not share_rows:
            logger.warning(
                "Shares.csv not found or empty — this may indicate a Basic "
                "archive was uploaded instead of Complete. "
                "Consistency scoring will be unavailable."
            )

        if not comment_rows or not reaction_rows:
            logger.warning(
                "Comments.csv or Reactions.csv not found or empty — "
                "Engagement Quality Ratio scoring will be unavailable."
            )

        return ZipData(
            profile=_parse_profile(profile_rows),
            positions=_parse_positions(position_rows),
            skills=_parse_skills(skill_rows),
            rich_media=_parse_rich_media(media_rows),
            shares=_parse_shares(share_rows),
            comments=_parse_comments(comment_rows),
            reactions=_parse_reactions(reaction_rows),
        )
