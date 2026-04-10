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
