"""Unit tests for the ORPHEUS-88 quality gate on POST /jobs (create_job).

A Basic (or corrupt) archive parses fine but is missing the core CSVs.
Scoring it would produce a confident-looking report on data that isn't a
measurement, so create_job rejects it with a 422 and actionable guidance
BEFORE minting a job row. Only MISSING_FILE criticals block; an EMPTY_DATA
critical (Complete archive, genuinely inactive member) is allowed through.

Handler-invocation pattern matching test_jobs_get.py: patch the parse
functions, `_read_upload`, and `get_service_client`, then call create_job
directly. The gate fires before any storage/DB write, so we assert the
raise and that no job row was inserted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.models.quality import (
    DataQualityReport,
    IssueCategory,
    IssueSeverity,
)
from backend.routers import jobs as jobs_router


CLIENT_ID = "11111111-1111-1111-1111-111111111111"

_REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.local",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "RESEND_API_KEY": "test-resend-key",
    "APP_BASE_URL": "https://app.test.local",
}


@pytest.fixture(autouse=True)
def _reset_env_and_cache(monkeypatch):
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    config_mod._reset_settings_cache_for_tests()


def _client_roles() -> SessionRoles:
    return SessionRoles(
        user_id="user-client-uuid",
        email="client@example.com",
        access_token="test-token",
        advisor_id=None,
        client_id=CLIENT_ID,
    )


class _Chain:
    def __init__(self, parent: "FakeSupabase", table: str) -> None:
        self._parent = parent
        self._table = table

    def select(self, *_a: Any, **_k: Any) -> "_Chain":
        return self

    def eq(self, *_a: Any, **_k: Any) -> "_Chain":
        return self

    def in_(self, *_a: Any, **_k: Any) -> "_Chain":
        return self

    def limit(self, *_a: Any, **_k: Any) -> "_Chain":
        return self

    def insert(self, *_a: Any, **_k: Any) -> "_Chain":
        self._parent.inserts.append(self._table)
        return self

    def execute(self) -> SimpleNamespace:
        if self._parent.responses:
            return SimpleNamespace(**self._parent.responses.pop(0))
        return SimpleNamespace(data=[])


class FakeSupabase:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.tables_queried: list[str] = []
        self.inserts: list[str] = []

    def table(self, name: str) -> _Chain:
        self.tables_queried.append(name)
        return _Chain(self, name)


def _blocking_report(source: str) -> DataQualityReport:
    r = DataQualityReport()
    r.add(
        IssueSeverity.CRITICAL, IssueCategory.MISSING_FILE, source,
        f"{source} not found in archive", "scoring",
    )
    return r


def _patches(report: DataQualityReport, fake: FakeSupabase):
    """Patch the create_job collaborators. _has_active_job reads jobs first
    (empty → no active job), then parse_zip returns the blocking report."""
    return [
        patch.object(jobs_router, "get_service_client", return_value=fake),
        patch.object(
            jobs_router, "_read_upload", new=AsyncMock(return_value=b"bytes")
        ),
        patch.object(
            jobs_router, "parse_zip",
            return_value=(SimpleNamespace(), report),
        ),
        patch.object(
            jobs_router, "parse_xlsx", return_value=SimpleNamespace()
        ),
    ]


async def _call_create_job(archive_filename: str = "archive.zip"):
    # archive_filename defaults to a name with no Basic/Complete prefix and
    # no parseable date, so the ORPHEUS-101 filename gate is a no-op unless a
    # test opts into a real LinkedIn-style name.
    return await jobs_router.create_job(
        archive=SimpleNamespace(filename=archive_filename),
        analytics=SimpleNamespace(filename="analytics.xlsx"),
        has_profile_photo=None,
        roles=_client_roles(),
    )


@pytest.mark.asyncio
async def test_missing_shares_rejected_with_basic_archive_guidance():
    """Shares.csv missing → 422 pointing at the Complete/larger archive."""
    fake = FakeSupabase(responses=[{"data": []}])  # _has_active_job → none
    p = _patches(_blocking_report("Shares.csv"), fake)
    with p[0], p[1], p[2], p[3]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job()

    assert exc.value.status_code == 422
    assert "Basic data export" in exc.value.detail
    assert "larger data archive" in exc.value.detail
    # Gate fired before any job row was minted.
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_missing_profile_rejected_with_corrupt_archive_guidance():
    """Profile.csv missing (no Shares issue) → 422 with the generic
    re-download guidance, not the Basic-archive copy."""
    fake = FakeSupabase(responses=[{"data": []}])
    p = _patches(_blocking_report("Profile.csv"), fake)
    with p[0], p[1], p[2], p[3]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job()

    assert exc.value.status_code == 422
    assert "missing core profile data" in exc.value.detail
    assert "Basic data export" not in exc.value.detail
    assert fake.inserts == []


# --------------------------------------------------------------------------- #
# Freshness gate — ORPHEUS-100
# --------------------------------------------------------------------------- #
#
# After the ORPHEUS-88 blocking gate, a non-blocking archive whose analytics
# data ends more than _STALE_ARCHIVE_DAYS (14) before today is rejected with a
# 422 naming the export date. We patch `latest_analytics_date` to control the
# resolved export date independent of XLSX parsing, and use an empty (non-
# blocking) quality report so the 88 gate passes. A fresh / no-date upload
# passes the freshness gate and proceeds to the job insert — which, with no
# insert response queued on the fake, surfaces as a 500 ("Failed to create job
# row"). We assert that 500 as proof the freshness gate let the request
# through, without mocking the whole storage/insert path.


def _empty_report() -> DataQualityReport:
    return DataQualityReport()


def _days_ago(n: int):
    return datetime.now(timezone.utc).date() - timedelta(days=n)


def _freshness_patches(fake: FakeSupabase, export_date):
    return [
        patch.object(jobs_router, "get_service_client", return_value=fake),
        patch.object(
            jobs_router, "_read_upload", new=AsyncMock(return_value=b"bytes")
        ),
        patch.object(
            jobs_router, "parse_zip",
            return_value=(SimpleNamespace(), _empty_report()),
        ),
        patch.object(
            jobs_router, "parse_xlsx", return_value=SimpleNamespace()
        ),
        patch.object(
            jobs_router, "latest_analytics_date", return_value=export_date
        ),
    ]


@pytest.mark.asyncio
async def test_stale_export_rejected():
    """Analytics ending well before today → 422 naming the export date; no
    job row minted."""
    fake = FakeSupabase(responses=[{"data": []}])  # _has_active_job → none
    stale = _days_ago(60)
    ps = _freshness_patches(fake, stale)
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job()

    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail
    assert stale.strftime("%B") in exc.value.detail  # month name in guidance
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_fresh_export_passes_freshness_gate():
    """A recent export clears the freshness gate and proceeds to the job
    insert (which 500s here only because no insert response is queued —
    proving the gate let it through)."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, _days_ago(3))
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job()

    # Reached the insert step → not a freshness rejection.
    assert exc.value.status_code == 500
    assert "out of date" not in (exc.value.detail or "")
    assert fake.inserts == ["jobs"]


@pytest.mark.asyncio
async def test_boundary_exactly_14_days_passes():
    """Exactly 14 days old is NOT stale (gate is age > 14)."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, _days_ago(14))
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job()
    assert exc.value.status_code == 500  # passed freshness, reached insert


@pytest.mark.asyncio
async def test_boundary_15_days_rejected():
    """One day past the threshold is stale."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, _days_ago(15))
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job()
    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail


@pytest.mark.asyncio
async def test_no_analytics_date_skips_freshness_gate():
    """No parseable analytics date (brand-new account) → skip the check;
    the request proceeds past the gate."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, None)
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job()
    assert exc.value.status_code == 500  # reached insert, no freshness reject


# --------------------------------------------------------------------------- #
# Filename gate — ORPHEUS-101 (layered on 88 + 100)
# --------------------------------------------------------------------------- #
#
# The archive filename (Complete_LinkedInDataExport_MM-DD-YYYY.zip) is the
# primary signal: a Basic_ prefix rejects immediately; a parseable filename
# date drives the recency gate ahead of the XLSX date. A renamed/dateless
# filename falls through to the content-based checks.


@pytest.mark.asyncio
async def test_basic_filename_rejected_regardless_of_content():
    """A Basic_ archive filename rejects at the filename gate even when the
    (patched) content report is non-blocking."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, None)  # content empty, analytics date N/A
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job("Basic_LinkedInDataExport_01-02-2026.zip")

    assert exc.value.status_code == 422
    assert "Basic data export" in exc.value.detail
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_filename_date_drives_recency_over_xlsx():
    """A stale filename date rejects even when the XLSX analytics date is
    fresh — the filename is the primary recency signal (ORPHEUS-101)."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, _days_ago(0))  # XLSX says today (fresh)
    stale_name = (
        f"Complete_LinkedInDataExport_{_days_ago(60).strftime('%m-%d-%Y')}.zip"
    )
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job(stale_name)

    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_recency_falls_back_to_xlsx_when_filename_has_no_date():
    """A dateless (but Complete) filename → recency falls back to the XLSX
    analytics date; a stale XLSX date still rejects."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, _days_ago(60))  # XLSX stale
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job("Complete_LinkedInDataExport.zip")

    assert exc.value.status_code == 422
    assert "out of date" in exc.value.detail


@pytest.mark.asyncio
async def test_fresh_filename_date_passes_even_without_xlsx_date():
    """A fresh filename date clears recency even when the XLSX carries no
    parseable date; proceeds to the insert (500 with no response queued)."""
    fake = FakeSupabase(responses=[{"data": []}])
    ps = _freshness_patches(fake, None)  # no XLSX date
    fresh_name = (
        f"Complete_LinkedInDataExport_{_days_ago(2).strftime('%m-%d-%Y')}.zip"
    )
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        with pytest.raises(HTTPException) as exc:
            await _call_create_job(fresh_name)

    assert exc.value.status_code == 500
    assert fake.inserts == ["jobs"]


@pytest.mark.asyncio
async def test_non_client_role_rejected_before_gate():
    """Regression: an advisor-only caller still gets 403 (the gate change
    didn't move the role check)."""
    advisor_roles = SessionRoles(
        user_id="u",
        email="a@ess3.ai",
        access_token="t",
        advisor_id="adv-id",
        client_id=None,
    )
    with pytest.raises(HTTPException) as exc:
        await jobs_router.create_job(
            archive=SimpleNamespace(),
            analytics=SimpleNamespace(),
            has_profile_photo=None,
            roles=advisor_roles,
        )
    assert exc.value.status_code == 403
