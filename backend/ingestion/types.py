"""Typed models for parsed LinkedIn data.

These define the shape of the JSONB stored in ingested_data.zip_data
and ingested_data.xlsx_data. The scoring engine consumes these types.

Shapes are derived from actual LinkedIn exports (verified 2026-03-17).
"""

from pydantic import BaseModel


# ============================================================
# ZIP archive types (LinkedIn Complete export)
# ============================================================


class ProfileData(BaseModel):
    """Parsed from Profile.csv.

    Actual headers: First Name, Last Name, Maiden Name, Address,
    Birth Date, Headline, Summary, Industry, Zip Code, Geo Location,
    Twitter Handles, Websites, Instant Messengers
    """

    first_name: str = ""
    last_name: str = ""
    headline: str = ""
    summary: str = ""
    industry: str = ""
    geo_location: str = ""
    websites: str = ""


class PositionData(BaseModel):
    """Single role parsed from Positions.csv.

    Actual headers: Company Name, Title, Description, Location,
    Started On, Finished On
    """

    company_name: str = ""
    title: str = ""
    description: str = ""
    location: str = ""
    started_on: str = ""
    finished_on: str = ""


class RichMediaItem(BaseModel):
    """Single media upload parsed from Rich_Media.csv.

    Actual headers: Date/Time, Media Description, Media Link.
    The Date/Time field is a human-readable sentence like:
    "You uploaded a feed document on March 12, 2025 at 10:07 AM (...)"
    "You changed your profile photo on Jan 5, 2024 at 3:22 PM (...)"

    We parse the type (profile photo, background photo, feed document, etc.)
    and date from this sentence.
    """

    type: str = ""
    date_time_raw: str = ""
    media_link: str = ""


class ShareItem(BaseModel):
    """Single post parsed from Shares.csv.

    Actual headers: Date, ShareLink, ShareCommentary,
    SharedUrl, MediaUrl, Visibility
    """

    date: str = ""
    share_link: str = ""
    share_commentary: str = ""
    shared_url: str = ""
    visibility: str = ""


class CommentItem(BaseModel):
    """Single comment parsed from Comments.csv.

    Actual headers: Date, Link, Message.
    Represents a comment the member made on another person's post.
    Used for Engagement Quality Ratio scoring (Consistency dimension).
    """

    date: str = ""
    link: str = ""
    message: str = ""


class ReactionItem(BaseModel):
    """Single reaction parsed from Reactions.csv.

    Actual headers: Date, Type, Link.
    Type values observed: LIKE, INTEREST, PRAISE,
    ENTERTAINMENT, APPRECIATION, EMPATHY, MAYBE.
    Represents a passive engagement action on another person's post.
    Used for Engagement Quality Ratio scoring (Consistency dimension).
    """

    date: str = ""
    reaction_type: str = ""
    link: str = ""


class ZipData(BaseModel):
    """Complete parsed output from the LinkedIn ZIP archive.

    Stored as ingested_data.zip_data in the database.
    """

    profile: ProfileData = ProfileData()
    positions: list[PositionData] = []
    skills: list[str] = []
    rich_media: list[RichMediaItem] = []
    shares: list[ShareItem] = []
    comments: list[CommentItem] = []
    reactions: list[ReactionItem] = []


# ============================================================
# XLSX types (LinkedIn Analytics export)
# ============================================================


class DiscoverySummary(BaseModel):
    """Parsed from the DISCOVERY sheet.

    LinkedIn provides only summary totals for the export period,
    not daily breakdowns. The period is noted in the header row.
    """

    period: str = ""
    impressions: int = 0
    members_reached: int = 0


class EngagementRow(BaseModel):
    """Single daily row from the ENGAGEMENT sheet.

    Actual columns: Date, Impressions, Engagements.
    No breakdown by reactions/comments/reposts — just totals.
    """

    date: str = ""
    impressions: int = 0
    engagements: int = 0


class TopPostItem(BaseModel):
    """Single post from the TOP POSTS sheet.

    LinkedIn provides two side-by-side rankings: top by engagements
    (cols A-C) and top by impressions (cols E-G). We merge these
    into a single list, combining engagement and impression data
    where the same post appears in both rankings.
    """

    post_url: str = ""
    published_date: str = ""
    impressions: int = 0
    engagements: int = 0


class FollowersRow(BaseModel):
    """Single daily row from the FOLLOWERS sheet.

    Actual columns: Date, New followers.
    The total follower count appears only as a summary in row 0.
    """

    date: str = ""
    new_followers: int = 0


class DemographicsData(BaseModel):
    """Parsed from the DEMOGRAPHICS sheet.

    Actual layout: three columns — category label (repeating), value, percentage.
    Categories observed: Job titles, Locations, Industries.
    Note: LinkedIn calls it "Job titles" not "seniority", and "Locations"
    not "geography". No "company" category in the analytics export.

    Each dict maps a label to a percentage (as a float, e.g. 0.025 = 2.5%).
    """

    job_titles: dict[str, float] = {}
    locations: dict[str, float] = {}
    industries: dict[str, float] = {}


class FollowersData(BaseModel):
    """Wrapper for FOLLOWERS sheet data."""

    total_followers: int = 0
    rows: list[FollowersRow] = []


class XlsxData(BaseModel):
    """Complete parsed output from the LinkedIn Analytics XLSX.

    Stored as ingested_data.xlsx_data in the database.
    """

    discovery: DiscoverySummary = DiscoverySummary()
    engagement: list[EngagementRow] = []
    top_posts: list[TopPostItem] = []
    followers: FollowersData = FollowersData()
    demographics: DemographicsData = DemographicsData()
