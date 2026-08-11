"""Metric source/unit registry — the golden-source map (ORPHEUS-114 a+b).

Every client-facing metric is registered here with its authoritative source
(which file/sheet owns it and what operation derives it), its unit, its
explicit denominator where it is a rate, its measurement window, and its
display formatting. The registry is the single owner of metric labels:

  * `backend/agents/narrative.py` renders the forward-brief prompt block by
    iterating `REACH_METRICS` / `BEHAVIORAL_METRICS` (previously hand-written
    f-strings — the gap where bug C lived: "17.5/week" and "875/day"
    presented as peers with no denominator in sight).
  * `QUANTITATIVE_METRIC_LABELS` (ORPHEUS-117, sub-dim measured-signal lines)
    is now a thin adapter over `SUB_DIM_METRICS` below, so both layers draw
    units and windows from one place.
  * `backend/scoring/reconciliation.py` (ORPHEUS-114 c) checks the identities
    that relate these metrics to their persisted operands before anything is
    written.
  * `backend/agents/prose_numbers.py` (ORPHEUS-121) builds its whitelist of
    citable figures from registered values and their display variants.

Golden-source note on dates (ORPHEUS-114 e): there is NO ID-decoded date
anywhere in this codebase — verified 2026-08-11. The date sources are exactly:
ZIP CSV `Date` strings parsed via `engine._parse_date` (formats shared in
`backend/scoring/dates.py`), XLSX cells via `xlsx_parser._parse_date_cell`,
and the archive filename's `MM-DD-YYYY` stamp. LinkedIn URN/snowflake IDs in
ShareLink/Link columns are never decoded (a comment's `Link` carries the
TARGET post's activity URN, so decoding it would yield the wrong timestamp).
Shares.csv timestamps are already the canonical share dates.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.scoring import config


@dataclass(frozen=True)
class MetricSpec:
    """One client-facing metric's provenance and presentation.

    `source` is the golden source: the file/sheet that owns the value and
    the operation that derives it (documentation + tests; never rendered to
    the client). `unit`/`denominator`/`window` are structured metadata —
    every rate carries an explicit denominator (bug C). `detail` is the
    authored clause rendered after the value in the prompt line, which is
    where the unit and denominator reach the agent in readable form.
    """

    key: str                      # ForwardBriefQuantitative field / canonical sub-dim name
    source: str                   # golden source: file + sheet + operation
    unit: str                     # unit as a plural noun phrase
    label: str                    # prompt/display label
    window: str = ""              # measurement window, trailing prepositional phrase
    denominator: str | None = None  # explicit denominator for rates
    decimals: int = 0             # display precision
    percent: bool = False         # render as a percentage
    detail: str = ""              # authored trailing clause for the prompt line
    gloss: str | None = None      # optional clarification (sub-dim lines)


def format_metric_value(spec: MetricSpec, value: float | int) -> str:
    """Render a metric value at its registered display precision."""
    if spec.percent:
        return f"{value:.{spec.decimals}%}"
    return f"{value:,.{spec.decimals}f}"


def format_metric_line(spec: MetricSpec, value: float | int) -> str:
    """Render one labeled prompt line: `Label: value detail`."""
    line = f"{spec.label}: {format_metric_value(spec, value)}"
    if spec.detail:
        line += f" {spec.detail}"
    return line


# --------------------------------------------------------------------------- #
# Forward-brief metrics — keyed by ForwardBriefQuantitative field name.
# Tuples are ordered: prompt rendering iterates them in order per section.
# --------------------------------------------------------------------------- #

# Section 1 — REACH & AUDIENCE (from Analytics)
REACH_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="follower_count",
        source="XLSX FOLLOWERS sheet, total-followers summary cell",
        unit="followers",
        label="Followers",
        window="at export",
        detail="(total at export)",
    ),
    MetricSpec(
        key="net_new_followers",
        source=(
            "XLSX FOLLOWERS daily rows, new_followers summed over the "
            "export window"
        ),
        unit="net new followers",
        label="Net new followers",
        window="over the analytics export window",
        detail="over the analytics export window",
    ),
    MetricSpec(
        key="follower_growth_rate",
        source=(
            "XLSX FOLLOWERS daily rows: sum(new_followers) / (row count / 7) "
            "— net new divided by weeks observed"
        ),
        unit="new followers per week",
        label="New followers/week",
        denominator="weeks observed in the analytics export",
        decimals=1,
        detail="(net new followers ÷ weeks observed in the analytics export)",
    ),
    MetricSpec(
        key="unique_members_reached",
        source=(
            "XLSX DISCOVERY sheet, members-reached summary cell. "
            "UNIQUE-CUMULATIVE over the export window — never a sum of "
            "daily rows (members repeat across days)"
        ),
        unit="unique members",
        label="Unique members reached",
        window="over the analytics export window",
        detail="unique members over the analytics export window",
    ),
    MetricSpec(
        key="total_impressions",
        source=(
            "XLSX ENGAGEMENT daily rows, impressions summed over the "
            "export window"
        ),
        unit="impressions",
        label="Total impressions",
        window="over the analytics export window",
        detail="over the analytics export window",
    ),
    MetricSpec(
        key="avg_impressions_per_post",
        source=(
            "total_impressions (XLSX ENGAGEMENT dailies) / post_count "
            "(ZIP Shares.csv, posts published in the scoring window) — "
            "ORPHEUS-112 denominator"
        ),
        unit="impressions per original post",
        label="Avg impressions/post",
        denominator="original posts published in the scoring window",
        decimals=0,
        detail=(
            "(total impressions ÷ original posts published in the "
            "scoring window)"
        ),
    ),
    MetricSpec(
        key="avg_engagement_rate",
        source=(
            "XLSX ENGAGEMENT dailies: sum(engagements) / sum(impressions) — "
            "an aggregate ratio over the whole window, not an average of "
            "per-post rates"
        ),
        unit="engagements per impression",
        label="Avg engagement rate",
        denominator="total impressions across the export window",
        decimals=1,
        percent=True,
        detail=(
            "(total engagements ÷ total impressions, aggregate over the "
            "export window)"
        ),
    ),
    MetricSpec(
        key="top_post_impressions",
        source="XLSX TOP POSTS sheet, max impressions across listed posts",
        unit="impressions",
        label="Top post impressions",
        detail="(single best post in the analytics window)",
    ),
)

# Section 2 — BEHAVIORAL DEPTH (from Archive)
BEHAVIORAL_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="post_count",
        source=(
            "ZIP Shares.csv rows with a parseable date inside the trailing "
            "365-day scoring window (anchored on latest ZIP activity, "
            "ORPHEUS-91)"
        ),
        unit="original posts",
        label="Original posts in scoring window",
    ),
    MetricSpec(
        key="avg_comment_length_words",
        source="ZIP Comments.csv, mean word count of in-window comments",
        unit="words per comment",
        label="Avg comment length",
        denominator="comments written in the scoring window",
        decimals=1,
        detail="words per comment",
    ),
    MetricSpec(
        key="longest_posting_gap_weeks",
        source=(
            "ZIP Shares.csv, longest gap between consecutive in-window posts"
        ),
        unit="weeks",
        label="Longest posting gap",
        detail="weeks",
    ),
    MetricSpec(
        key="zero_post_week_pct",
        source=(
            "ZIP Shares.csv: share of the trailing "
            f"{config.DIM2_CONTINUITY_WINDOW_WEEKS}-week window with no posts"
        ),
        unit="of weeks",
        label="Zero-post weeks",
        denominator=f"trailing {config.DIM2_CONTINUITY_WINDOW_WEEKS} weeks",
        decimals=0,
        percent=True,
        detail=f"of the trailing {config.DIM2_CONTINUITY_WINDOW_WEEKS} weeks",
    ),
)

FORWARD_BRIEF_METRICS: dict[str, MetricSpec] = {
    spec.key: spec for spec in (*REACH_METRICS, *BEHAVIORAL_METRICS)
}


# --------------------------------------------------------------------------- #
# Sub-dimension measured signals — keyed by canonical SubDimensionScore.name.
# Subsumes ORPHEUS-117's QUANTITATIVE_METRIC_LABELS (narrative.py keeps a
# thin adapter under that name). Rendering fails closed: an unregistered
# quantitative sub-dim's raw_value never reaches the prompt.
# --------------------------------------------------------------------------- #

SUB_DIM_METRICS: dict[str, MetricSpec] = {
    "History Depth": MetricSpec(
        key="History Depth",
        source=(
            "ZIP Shares.csv + Comments.csv + Reactions.csv, in-window "
            "row count"
        ),
        unit="outbound actions",
        label="History Depth",
        window="over the trailing 12 months",
        gloss="original posts, comments, and reactions combined",
    ),
    "Recency": MetricSpec(
        key="Recency",
        source="ZIP behavioral CSVs, in-recency-window row count",
        unit="outbound actions",
        label="Recency",
        window=f"in the trailing {config.DIM2_RECENCY_WINDOW_DAYS} days",
        gloss="original posts, comments, and reactions combined",
    ),
    "Continuity": MetricSpec(
        key="Continuity",
        source="ZIP behavioral CSVs, weeks meeting the active threshold",
        unit="active weeks",
        label="Continuity",
        window=f"out of the trailing {config.DIM2_CONTINUITY_WINDOW_WEEKS} weeks",
        gloss=(
            f"a week counts as active at "
            f"{config.DIM2_CONTINUITY_ACTIVE_THRESHOLD} "
            "or more posts or comments"
        ),
    ),
    "Posting Presence": MetricSpec(
        key="Posting Presence",
        source="ZIP Shares.csv, in-window posts / window weeks",
        unit="original posts per week",
        label="Posting Presence",
        window=(
            "averaged over the trailing "
            f"{config.DIM2_CONTINUITY_WINDOW_WEEKS} weeks"
        ),
        denominator=f"trailing {config.DIM2_CONTINUITY_WINDOW_WEEKS} weeks",
        decimals=1,
    ),
    "Outbound Engagement Presence": MetricSpec(
        key="Outbound Engagement Presence",
        source="ZIP Comments.csv + Reactions.csv, in-window row count",
        unit="engagement actions",
        label="Outbound Engagement Presence",
        window="over the trailing 12 months",
        gloss="comments and reactions on other people's content",
    ),
}

# Quantitative sub-dims whose raw_value is a composite internal index with no
# human unit, deliberately withheld from the prompt (ORPHEUS-117 decision
# [Josh, 2026-07-27]). Moved here from narrative.py so the registry owns the
# whole citable/suppressed partition; narrative.py re-exports it.
SUPPRESSED_SUB_DIMS: frozenset[str] = frozenset({
    "Engagement Quality Score",
})
