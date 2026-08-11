"""Shared date-format knowledge for LinkedIn export data (ORPHEUS-114).

One tuple, three consumers: the scoring engine's `_parse_date`
(backend/scoring/engine.py), the quality validator's `_check_date_parseable`
and `_find_date_range` (backend/ingestion/zip_parser.py). Before ORPHEUS-114
the format list was duplicated verbatim at all three sites — a real drift
risk, because `_check_date_parseable` decides which rows are counted as
"unparseable" in the quality report and coverage facts, while `_parse_date`
decides which rows actually score. A format added to one and not the other
silently changes the exclusion count without changing scoring, or vice versa.

Timezone posture (documented, not changed here): LinkedIn export date strings
are naive — no tzinfo is ever attached, and `.date()` truncation discards the
time component. An event near midnight can land in the adjacent day/week
depending on whatever zone LinkedIn exported in. Accepted as-is; all
consumers share the same behavior so windows are at least self-consistent.
"""

# Formats observed across LinkedIn export CSVs:
#   "2025-03-17 11:12:43" — ISO datetime (Shares, Comments, Reactions)
#   "2025-03-17"          — ISO date
#   "03/17/2025"          — US
#   "Mar 17, 2025" / "March 17, 2025"
DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%b %d, %Y",
    "%B %d, %Y",
)
