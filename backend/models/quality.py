"""Data quality report models.

Generated during ingestion to flag missing data, parse failures,
and cross-source inconsistencies. Stored as JSONB on ingested_data.
Surfaced to advisors and passed to narrative generation so Claude
can acknowledge data limitations.
"""

from pydantic import BaseModel, Field
from enum import Enum


class IssueSeverity(str, Enum):
    """How much the issue affects scoring or reporting."""
    INFO = "info"          # Worth noting but no impact on scoring
    WARNING = "warning"    # Scoring is degraded — a dimension or sub-dimension is affected
    CRITICAL = "critical"  # A scored dimension cannot be computed at all


class IssueCategory(str, Enum):
    """What kind of data quality issue this is."""
    MISSING_FILE = "missing_file"          # Expected CSV/sheet not found in the export
    MISSING_FIELD = "missing_field"        # A key profile or data field is empty/absent
    EMPTY_DATA = "empty_data"              # File exists but has no usable rows
    PARSE_FAILURE = "parse_failure"        # Rows or fields that couldn't be parsed
    INCONSISTENCY = "inconsistency"        # ZIP and XLSX data tell conflicting stories
    DATE_RANGE = "date_range"              # Data doesn't cover the expected scoring window
    FORMAT_UNEXPECTED = "format_unexpected"  # File layout differs from expected structure


# --------------------------------------------------------------------------- #
# Quality-gate classification (ORPHEUS-88)
# --------------------------------------------------------------------------- #
#
# Two independent classifications drive the ORPHEUS-88 quality gate:
#
#   * BLOCKING — a CRITICAL issue whose category means the *archive itself*
#     is unusable (a core CSV is absent). This is the Basic-archive /
#     corrupt-upload case: it's a data artifact, not a measurement, so the
#     job is rejected at POST /jobs with actionable guidance rather than
#     scored into a confident-looking report. Only MISSING_FILE criticals
#     block — a Complete archive from a genuinely inactive member trips the
#     EMPTY_DATA critical (zero behavioral rows) but is a *valid* low-signal
#     measurement and must be allowed through.
#
#   * DATA-LIMITED — any CRITICAL or WARNING whose category means the data
#     backing the report is incomplete or degraded (missing optional files,
#     empty/sparse behavioral data, dropped rows, short date span). This is
#     surfaced as a client-facing report banner + an advisor/admin chip so
#     nobody mistakes a limited-data report for an authoritative one.
#     MISSING_FIELD warnings (empty headline/about/industry/positions) are
#     deliberately *excluded* — those are legitimate profile-completeness
#     inputs the score is *supposed* to reflect, not a data limitation.
#     INFO issues never surface.

# CRITICAL issues in these categories block job creation at POST /jobs.
BLOCKING_CATEGORIES: set[IssueCategory] = {IssueCategory.MISSING_FILE}

# CRITICAL/WARNING issues in these categories mark a completed report as
# data-limited (banner + chip). Excludes MISSING_FIELD and INFO-only noise.
DATA_LIMITATION_CATEGORIES: set[IssueCategory] = {
    IssueCategory.MISSING_FILE,
    IssueCategory.EMPTY_DATA,
    IssueCategory.PARSE_FAILURE,
    IssueCategory.DATE_RANGE,
}


class QualityIssue(BaseModel):
    """A single data quality finding."""
    severity: IssueSeverity
    category: IssueCategory
    source: str = Field(..., description="Which file or sheet the issue was found in")
    field: str | None = Field(None, description="Specific field or column affected")
    message: str = Field(..., description="Human-readable description of the issue")
    impact: str = Field(..., description="What this affects — which dimension or metric is degraded")
    rows_affected: int | None = Field(None, description="Number of rows dropped or affected, if applicable")


class DataQualityReport(BaseModel):
    """Complete data quality report for a single ingestion job.

    Stored as ingested_data.quality_report (JSONB).
    """
    issues: list[QualityIssue] = Field(default_factory=list)
    zip_files_found: list[str] = Field(
        default_factory=list,
        description="CSV filenames found in the ZIP archive"
    )
    zip_files_expected: list[str] = Field(
        default_factory=list,
        description="CSV filenames the parser looked for"
    )
    xlsx_sheets_found: list[str] = Field(
        default_factory=list,
        description="Sheet names found in the XLSX"
    )
    total_shares: int = Field(0, description="Number of posts parsed from Shares.csv")
    total_comments: int = Field(0, description="Number of comments parsed")
    total_reactions: int = Field(0, description="Number of reactions parsed")
    date_range_start: str | None = Field(None, description="Earliest date in behavioral data")
    date_range_end: str | None = Field(None, description="Latest date in behavioral data")

    @property
    def has_critical(self) -> bool:
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    # ---- ORPHEUS-88 quality-gate helpers ---------------------------------

    def blocking_issues(self) -> list[QualityIssue]:
        """CRITICAL issues that make the archive unusable (missing core CSV).

        These reject the job at POST /jobs — a Basic archive or a corrupt
        upload, not a measurement. An EMPTY_DATA critical (zero behavioral
        rows on an otherwise-complete archive) is NOT blocking: it's a
        valid low-signal report for a genuinely inactive member.
        """
        return [
            i for i in self.issues
            if i.severity == IssueSeverity.CRITICAL
            and i.category in BLOCKING_CATEGORIES
        ]

    @property
    def has_blocking_issue(self) -> bool:
        return bool(self.blocking_issues())

    def data_limitation_issues(self) -> list[QualityIssue]:
        """CRITICAL/WARNING issues that mean the report rests on limited data.

        Drives the client-facing report banner and the advisor/admin chip.
        Excludes MISSING_FIELD (a legitimate profile-completeness score
        input) and INFO (noise).
        """
        return [
            i for i in self.issues
            if i.severity in (IssueSeverity.CRITICAL, IssueSeverity.WARNING)
            and i.category in DATA_LIMITATION_CATEGORIES
        ]

    @property
    def is_data_limited(self) -> bool:
        return bool(self.data_limitation_issues())

    def data_limitation_notices(self) -> list[str]:
        """Human-readable messages for the data-limited banner, dedup'd."""
        seen: set[str] = set()
        notices: list[str] = []
        for i in self.data_limitation_issues():
            if i.message not in seen:
                seen.add(i.message)
                notices.append(i.message)
        return notices

    def summary(self) -> str:
        """One-line summary for logging."""
        counts = {}
        for issue in self.issues:
            counts[issue.severity.value] = counts.get(issue.severity.value, 0) + 1
        parts = [f"{v} {k}" for k, v in sorted(counts.items())]
        return ", ".join(parts) if parts else "no issues"

    def add(
        self,
        severity: IssueSeverity,
        category: IssueCategory,
        source: str,
        message: str,
        impact: str,
        field: str | None = None,
        rows_affected: int | None = None,
    ):
        """Convenience method to append an issue."""
        self.issues.append(QualityIssue(
            severity=severity,
            category=category,
            source=source,
            field=field,
            message=message,
            impact=impact,
            rows_affected=rows_affected,
        ))
