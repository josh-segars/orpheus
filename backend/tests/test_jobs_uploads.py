"""Unit tests for the ORPHEUS-108 browser-direct upload flow.

POST /jobs/upload-urls mints signed Storage upload URLs for a staging
path; POST /jobs/from-uploads downloads the staged bytes server-side,
runs the same submission gates as the legacy multipart handler, mints
the job row, and moves the objects to the worker's
`{client_id}/{job_id}/` path.

Handler-invocation pattern matching test_jobs_post.py: patch the parse
functions and `get_service_client`, call the handlers directly. The
FakeSupabase here is richer than test_jobs_post's — it carries a
FakeStorage (list / download / move / remove / create_signed_upload_url)
and supports upsert/update so the happy path can run end-to-end.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

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
from backend.routers.jobs import CreateJobFromUploadsRequest


CLIENT_ID = "11111111-1111-1111-1111-111111111111"
UPLOAD_ID = "22222222-2222-2222-2222-222222222222"
JOB_ID = "33333333-3333-3333-3333-333333333333"

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


def _advisor_roles() -> SessionRoles:
    return SessionRoles(
        user_id="u",
        email="a@ess3.ai",
        access_token="t",
        advisor_id="adv-id",
        client_id=None,
    )


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class FakeStorage:
    """Storage bucket fake covering the calls the new handlers make."""

    def __init__(
        self,
        list_entries: list[dict[str, Any]] | None = None,
        download_bytes: bytes = b"bytes",
        fail_move: bool = False,
        fail_signed_url: bool = False,
    ) -> None:
        self.list_entries = list_entries if list_entries is not None else []
        self.download_bytes = download_bytes
        self.fail_move = fail_move
        self.fail_signed_url = fail_signed_url
        self.signed_paths: list[str] = []
        self.downloads: list[str] = []
        self.moves: list[tuple[str, str]] = []
        self.removed: list[list[str]] = []

    def create_signed_upload_url(self, path: str) -> dict[str, str]:
        if self.fail_signed_url:
            raise RuntimeError("storage down")
        self.signed_paths.append(path)
        return {
            "signed_url": f"https://storage.test/{path}",
            "token": f"token-for-{path}",
            "path": path,
        }

    def list(self, prefix: str) -> list[dict[str, Any]]:
        return self.list_entries

    def download(self, path: str) -> bytes:
        self.downloads.append(path)
        return self.download_bytes

    def move(self, from_path: str, to_path: str) -> None:
        if self.fail_move:
            raise RuntimeError("move failed")
        self.moves.append((from_path, to_path))

    def remove(self, paths: list[str]) -> None:
        self.removed.append(paths)


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

    def insert(self, payload: Any = None, *_a: Any, **_k: Any) -> "_Chain":
        self._parent.inserts.append((self._table, payload))
        return self

    def upsert(self, payload: Any = None, *_a: Any, **_k: Any) -> "_Chain":
        self._parent.upserts.append((self._table, payload))
        return self

    def update(self, payload: Any = None, *_a: Any, **_k: Any) -> "_Chain":
        self._parent.updates.append((self._table, payload))
        return self

    def execute(self) -> SimpleNamespace:
        if self._parent.responses:
            return SimpleNamespace(**self._parent.responses.pop(0))
        return SimpleNamespace(data=[])


class FakeSupabase:
    def __init__(
        self,
        responses: list[dict[str, Any]],
        storage: FakeStorage | None = None,
    ) -> None:
        self.responses = list(responses)
        self.inserts: list[tuple[str, Any]] = []
        self.upserts: list[tuple[str, Any]] = []
        self.updates: list[tuple[str, Any]] = []
        self._storage = storage or FakeStorage()
        self.storage = SimpleNamespace(from_=lambda _bucket: self._storage)

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)


def _staged_entries(
    archive_size: int = 1024, analytics_size: int = 512
) -> list[dict[str, Any]]:
    return [
        {"name": "archive.zip", "metadata": {"size": archive_size}},
        {"name": "analytics.xlsx", "metadata": {"size": analytics_size}},
    ]


def _gate_patches(fake: FakeSupabase, report: DataQualityReport | None = None):
    """Patch collaborators so the gates pass (or fail per `report`)."""
    zip_model = SimpleNamespace(model_dump=lambda: {"zip": True})
    xlsx_model = SimpleNamespace(model_dump=lambda: {"xlsx": True})
    r = report if report is not None else DataQualityReport()
    return [
        patch.object(jobs_router, "get_service_client", return_value=fake),
        patch.object(
            jobs_router, "parse_zip", return_value=(zip_model, r)
        ),
        patch.object(jobs_router, "parse_xlsx", return_value=xlsx_model),
        patch.object(
            jobs_router, "latest_analytics_date", return_value=None
        ),
    ]


def _request(
    upload_id: str = UPLOAD_ID,
    archive_filename: str | None = "Complete_LinkedInDataExport.zip",
) -> CreateJobFromUploadsRequest:
    return CreateJobFromUploadsRequest(
        upload_id=upload_id,
        archive_filename=archive_filename,
        has_profile_photo=True,
    )


# --------------------------------------------------------------------------- #
# POST /jobs/upload-urls
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_upload_urls_requires_client_role():
    with pytest.raises(HTTPException) as exc:
        await jobs_router.create_upload_urls(roles=_advisor_roles())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_upload_urls_rejects_active_job():
    """The concurrent-run guard fires BEFORE any signed URL is minted, so
    a blocked client never wastes a large transfer."""
    fake = FakeSupabase(responses=[{"data": [{"id": "existing-job"}]}])
    with patch.object(jobs_router, "get_service_client", return_value=fake):
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_upload_urls(roles=_client_roles())
    assert exc.value.status_code == 409
    assert fake._storage.signed_paths == []


@pytest.mark.asyncio
async def test_upload_urls_happy_path_mints_staging_targets():
    fake = FakeSupabase(responses=[{"data": []}])  # no active job
    with patch.object(jobs_router, "get_service_client", return_value=fake):
        res = await jobs_router.create_upload_urls(roles=_client_roles())

    # upload_id is a real UUID and both paths live under the client's
    # staging prefix for that upload.
    import uuid as uuid_mod

    uuid_mod.UUID(res.upload_id)  # raises if not a UUID
    expected_prefix = f"{CLIENT_ID}/staging/{res.upload_id}"
    assert res.archive.path == f"{expected_prefix}/archive.zip"
    assert res.analytics.path == f"{expected_prefix}/analytics.xlsx"
    assert res.archive.token
    assert res.analytics.token
    assert fake._storage.signed_paths == [
        res.archive.path,
        res.analytics.path,
    ]


@pytest.mark.asyncio
async def test_upload_urls_storage_failure_returns_502():
    storage = FakeStorage(fail_signed_url=True)
    fake = FakeSupabase(responses=[{"data": []}], storage=storage)
    with patch.object(jobs_router, "get_service_client", return_value=fake):
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_upload_urls(roles=_client_roles())
    assert exc.value.status_code == 502


# --------------------------------------------------------------------------- #
# POST /jobs/from-uploads
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_from_uploads_requires_client_role():
    with pytest.raises(HTTPException) as exc:
        await jobs_router.create_job_from_uploads(
            body=_request(), roles=_advisor_roles()
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_from_uploads_rejects_non_uuid_upload_id():
    """upload_id is interpolated into storage paths — a non-UUID value is
    a path-traversal attempt and rejects before any storage call."""
    fake = FakeSupabase(responses=[])
    with patch.object(jobs_router, "get_service_client", return_value=fake):
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_job_from_uploads(
                body=_request(upload_id="../../other-client/steal"),
                roles=_client_roles(),
            )
    assert exc.value.status_code == 400
    assert fake._storage.downloads == []


@pytest.mark.asyncio
async def test_from_uploads_missing_staged_object_is_400():
    """Only the archive was staged (browser upload of the analytics never
    finished) → 400 with try-again guidance, no job row."""
    storage = FakeStorage(
        list_entries=[{"name": "archive.zip", "metadata": {"size": 100}}]
    )
    fake = FakeSupabase(responses=[{"data": []}], storage=storage)
    ps = _gate_patches(fake)
    with ps[0], ps[1], ps[2], ps[3]:
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_job_from_uploads(
                body=_request(), roles=_client_roles()
            )
    assert exc.value.status_code == 400
    assert "didn't finish" in exc.value.detail
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_from_uploads_oversized_archive_is_413_and_cleaned_up():
    storage = FakeStorage(
        list_entries=_staged_entries(
            archive_size=jobs_router._MAX_ARCHIVE_BYTES + 1
        )
    )
    fake = FakeSupabase(responses=[{"data": []}], storage=storage)
    ps = _gate_patches(fake)
    with ps[0], ps[1], ps[2], ps[3]:
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_job_from_uploads(
                body=_request(), roles=_client_roles()
            )
    assert exc.value.status_code == 413
    assert storage.removed  # staged objects were cleaned up
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_from_uploads_gate_rejection_cleans_staging():
    """The ORPHEUS-101 filename gate still fires on the browser-side
    filename carried in the JSON body; a rejection removes the staged
    objects so 100+ MB orphans don't accumulate."""
    storage = FakeStorage(list_entries=_staged_entries())
    fake = FakeSupabase(responses=[{"data": []}], storage=storage)
    ps = _gate_patches(fake)
    with ps[0], ps[1], ps[2], ps[3]:
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_job_from_uploads(
                body=_request(
                    archive_filename="Basic_LinkedInDataExport_01-02-2026.zip"
                ),
                roles=_client_roles(),
            )
    assert exc.value.status_code == 422
    assert "Basic data export" in exc.value.detail
    assert storage.removed
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_from_uploads_quality_gate_still_blocks():
    """The ORPHEUS-88 content gate runs identically to the multipart path
    (shared _apply_submission_gates)."""
    report = DataQualityReport()
    report.add(
        IssueSeverity.CRITICAL,
        IssueCategory.MISSING_FILE,
        "Shares.csv",
        "Shares.csv not found in archive",
        "scoring",
    )
    storage = FakeStorage(list_entries=_staged_entries())
    fake = FakeSupabase(responses=[{"data": []}], storage=storage)
    ps = _gate_patches(fake, report=report)
    with ps[0], ps[1], ps[2], ps[3]:
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_job_from_uploads(
                body=_request(), roles=_client_roles()
            )
    assert exc.value.status_code == 422
    assert "Basic data export" in exc.value.detail
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_from_uploads_happy_path_moves_to_worker_path():
    storage = FakeStorage(list_entries=_staged_entries())
    fake = FakeSupabase(
        responses=[
            {"data": []},  # _has_active_job → none
            {
                "data": [
                    {
                        "id": JOB_ID,
                        "status": "pending",
                        "created_at": "2026-07-15T00:00:00Z",
                        "client_id": CLIENT_ID,
                    }
                ]
            },  # job insert
            {"data": [{}]},  # ingested_data upsert
        ],
        storage=storage,
    )
    ps = _gate_patches(fake)
    with ps[0], ps[1], ps[2], ps[3]:
        job = await jobs_router.create_job_from_uploads(
            body=_request(), roles=_client_roles()
        )

    assert job.id == JOB_ID
    assert job.state == "pending"
    # Both staged objects downloaded for the gates...
    prefix = f"{CLIENT_ID}/staging/{UPLOAD_ID}"
    assert storage.downloads == [
        f"{prefix}/archive.zip",
        f"{prefix}/analytics.xlsx",
    ]
    # ...then moved to the exact path the worker reads from.
    assert storage.moves == [
        (f"{prefix}/archive.zip", f"{CLIENT_ID}/{JOB_ID}/archive.zip"),
        (f"{prefix}/analytics.xlsx", f"{CLIENT_ID}/{JOB_ID}/analytics.xlsx"),
    ]
    # Job row carries the OIDC photo signal; parsed data persisted.
    tables_inserted = [t for t, _ in fake.inserts]
    assert tables_inserted == ["jobs"]
    assert fake.inserts[0][1]["oidc_photo_present"] is True
    assert [t for t, _ in fake.upserts] == ["ingested_data"]


@pytest.mark.asyncio
async def test_from_uploads_move_failure_marks_job_failed():
    storage = FakeStorage(list_entries=_staged_entries(), fail_move=True)
    fake = FakeSupabase(
        responses=[
            {"data": []},
            {
                "data": [
                    {
                        "id": JOB_ID,
                        "status": "pending",
                        "created_at": "2026-07-15T00:00:00Z",
                        "client_id": CLIENT_ID,
                    }
                ]
            },
        ],
        storage=storage,
    )
    ps = _gate_patches(fake)
    with ps[0], ps[1], ps[2], ps[3]:
        with pytest.raises(HTTPException) as exc:
            await jobs_router.create_job_from_uploads(
                body=_request(), roles=_client_roles()
            )
    assert exc.value.status_code == 502
    assert fake.updates and fake.updates[0][0] == "jobs"
    assert fake.updates[0][1]["status"] == "failed"
