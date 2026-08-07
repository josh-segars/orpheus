"""Unit tests for backend/routers/account.py — DELETE /account
(ORPHEUS-124).

Direct-handler-invocation pattern (test_advisor_self_report.py et al.):
build a SessionRoles, monkey-patch `get_service_client`, call the route
function. The fake supabase here is richer than the invite tests' — it
tracks deletes per table, exposes a fake storage bucket with a nested
folder tree, and records the *order* of destructive calls so the
auth-user-last invariant is pinned.

Coverage map (ticket acceptance criteria in parens):

  - Client-only happy path: storage swept, clients row deleted, auth
    user deleted last (AC 1, 2, 3).
  - Nested storage walk: {client}/{job}/ files AND abandoned
    {client}/staging/{upload}/ files are both collected (AC 3).
  - Dual-role user whose only roster row is their own is_self row:
    clients + advisors rows both deleted (AC 6).
  - Advisor with a non-empty roster: 409, nothing touched (AC 5).
  - Advisor-only caller: advisors row deleted, no storage sweep.
  - Neither-role caller (the partial-failure retry): only the auth
    user is deleted — get_verified_session keeps the retry path open.
  - Storage listing failure → 502, no DB or auth deletes (AC 7).
  - Storage remove failure → 502, no DB or auth deletes (AC 7).
  - clients-row delete failure → 502, auth user NOT deleted (AC 7).
  - Auth-user delete failure → 502 with retry guidance; data deletes
    already ran (documented partial state).
  - Waitlist sweep: case-insensitive email match deleted by id;
    non-matching rows untouched.
  - Waitlist sweep failure is non-fatal — deletion still completes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.routers import account as account_router


USER_ID = "user-uuid-1111"
CLIENT_ID = "cccccccc-1111-2222-3333-444444444444"
ADVISOR_ID = "aaaaaaaa-5555-6666-7777-888888888888"
EMAIL = "client@example.com"

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


def _roles(
    *,
    advisor_id: str | None = None,
    client_id: str | None = None,
    email: str = EMAIL,
) -> SessionRoles:
    return SessionRoles(
        user_id=USER_ID,
        email=email,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

def _file_entry(name: str) -> dict[str, Any]:
    """A storage list() entry shaped like a file (has id + metadata)."""
    return {"name": name, "id": f"obj-{name}", "metadata": {"size": 123}}


def _folder_entry(name: str) -> dict[str, Any]:
    """A storage list() entry shaped like a folder (no id, no metadata)."""
    return {"name": name, "id": None, "metadata": None}


class FakeStorage:
    """Prefix → list-result map, plus removal capture."""

    def __init__(self, tree: dict[str, list[dict[str, Any]]]) -> None:
        self.tree = tree
        self.removed: list[list[str]] = []
        self.list_error: Exception | None = None
        self.remove_error: Exception | None = None

    def list(self, prefix: str) -> list[dict[str, Any]]:
        if self.list_error is not None:
            raise self.list_error
        return self.tree.get(prefix, [])

    def remove(self, paths: list[str]) -> None:
        if self.remove_error is not None:
            raise self.remove_error
        self.removed.append(list(paths))


class _Chain:
    def __init__(self, parent: "FakeSupabase", table_name: str) -> None:
        self._parent = parent
        self._table = table_name
        self._op = "select"

    def select(self, *_a: Any, **_k: Any) -> "_Chain":
        self._op = "select"
        return self

    def eq(self, column: str, value: Any) -> "_Chain":
        self._filter = (column, value)
        return self

    def in_(self, column: str, values: list[Any]) -> "_Chain":
        self._filter = (column, list(values))
        return self

    def delete(self) -> "_Chain":
        self._op = "delete"
        return self

    def execute(self) -> SimpleNamespace:
        parent = self._parent
        if self._op == "delete":
            if parent.delete_error is not None and self._table in (
                "clients",
                "advisors",
            ):
                raise parent.delete_error
            if (
                parent.waitlist_delete_error is not None
                and self._table == "waitlist"
            ):
                raise parent.waitlist_delete_error
            parent.calls.append(("delete", self._table, getattr(self, "_filter", None)))
            return SimpleNamespace(data=[])
        # select
        parent.calls.append(("select", self._table, getattr(self, "_filter", None)))
        if self._table == "clients":
            return SimpleNamespace(data=list(parent.roster_rows))
        if self._table == "waitlist":
            if parent.waitlist_select_error is not None:
                raise parent.waitlist_select_error
            return SimpleNamespace(data=list(parent.waitlist_rows))
        return SimpleNamespace(data=[])


class FakeAuthAdmin:
    def __init__(self, parent: "FakeSupabase") -> None:
        self._parent = parent

    def delete_user(self, user_id: str) -> None:
        if self._parent.auth_delete_error is not None:
            raise self._parent.auth_delete_error
        self._parent.calls.append(("auth_delete", user_id, None))


class FakeSupabase:
    def __init__(
        self,
        *,
        storage_tree: dict[str, list[dict[str, Any]]] | None = None,
        roster_rows: list[dict[str, Any]] | None = None,
        waitlist_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.fake_storage = FakeStorage(storage_tree or {})
        self.roster_rows = roster_rows or []
        self.waitlist_rows = waitlist_rows or []
        self.calls: list[tuple[str, str, Any]] = []
        self.delete_error: Exception | None = None
        self.waitlist_select_error: Exception | None = None
        self.waitlist_delete_error: Exception | None = None
        self.auth_delete_error: Exception | None = None
        self.storage = SimpleNamespace(from_=lambda _bucket: self.fake_storage)
        self.auth = SimpleNamespace(admin=FakeAuthAdmin(self))

    def table(self, name: str) -> _Chain:
        return _Chain(self, name)

    # Convenience views over the call log ---------------------------------
    def deletes(self, table: str) -> list[Any]:
        return [c for c in self.calls if c[0] == "delete" and c[1] == table]

    def auth_deletes(self) -> list[Any]:
        return [c for c in self.calls if c[0] == "auth_delete"]


def _patch_supabase(fake: FakeSupabase):
    return patch.object(account_router, "get_service_client", return_value=fake)


def _client_storage_tree() -> dict[str, list[dict[str, Any]]]:
    """{client}/{job}/ files plus an abandoned staging upload."""
    return {
        CLIENT_ID: [_folder_entry("job-1"), _folder_entry("staging")],
        f"{CLIENT_ID}/job-1": [
            _file_entry("archive.zip"),
            _file_entry("analytics.xlsx"),
        ],
        f"{CLIENT_ID}/staging": [_folder_entry("upload-abc")],
        f"{CLIENT_ID}/staging/upload-abc": [_file_entry("analytics.xlsx")],
    }


# --------------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_client_only_deletes_storage_rows_and_auth_user():
    fake = FakeSupabase(storage_tree=_client_storage_tree())

    with _patch_supabase(fake):
        response = await account_router.delete_account(
            roles=_roles(client_id=CLIENT_ID)
        )

    assert response.deleted is True

    # Storage: both the job files and the abandoned staging file removed.
    assert len(fake.fake_storage.removed) == 1
    removed = set(fake.fake_storage.removed[0])
    assert removed == {
        f"{CLIENT_ID}/job-1/archive.zip",
        f"{CLIENT_ID}/job-1/analytics.xlsx",
        f"{CLIENT_ID}/staging/upload-abc/analytics.xlsx",
    }

    # Clients row deleted explicitly; no advisors delete for a pure client.
    assert fake.deletes("clients") == [("delete", "clients", ("id", CLIENT_ID))]
    assert fake.deletes("advisors") == []

    # Auth user deleted, and deleted LAST.
    assert fake.auth_deletes() == [("auth_delete", USER_ID, None)]
    destructive = [c for c in fake.calls if c[0] in ("delete", "auth_delete")]
    assert destructive[-1][0] == "auth_delete"


@pytest.mark.asyncio
async def test_client_with_empty_storage_skips_remove():
    fake = FakeSupabase(storage_tree={})

    with _patch_supabase(fake):
        response = await account_router.delete_account(
            roles=_roles(client_id=CLIENT_ID)
        )

    assert response.deleted is True
    assert fake.fake_storage.removed == []
    assert len(fake.deletes("clients")) == 1
    assert len(fake.auth_deletes()) == 1


@pytest.mark.asyncio
async def test_dual_role_self_only_roster_deletes_both_rows():
    """Advisor whose only roster row is their own is_self row (AC 6)."""
    fake = FakeSupabase(
        storage_tree=_client_storage_tree(),
        roster_rows=[{"id": CLIENT_ID, "user_id": USER_ID}],
    )

    with _patch_supabase(fake):
        response = await account_router.delete_account(
            roles=_roles(advisor_id=ADVISOR_ID, client_id=CLIENT_ID)
        )

    assert response.deleted is True
    assert fake.deletes("clients") == [("delete", "clients", ("id", CLIENT_ID))]
    assert fake.deletes("advisors") == [
        ("delete", "advisors", ("id", ADVISOR_ID))
    ]
    # clients row goes before advisors row; auth user last.
    destructive = [c for c in fake.calls if c[0] in ("delete", "auth_delete")]
    tables = [c[1] for c in destructive]
    assert tables.index("clients") < tables.index("advisors")
    assert destructive[-1][0] == "auth_delete"


@pytest.mark.asyncio
async def test_advisor_only_deletes_advisor_row_without_storage_sweep():
    fake = FakeSupabase(roster_rows=[])

    with _patch_supabase(fake):
        response = await account_router.delete_account(
            roles=_roles(advisor_id=ADVISOR_ID)
        )

    assert response.deleted is True
    assert fake.fake_storage.removed == []
    assert fake.deletes("clients") == []
    assert fake.deletes("advisors") == [
        ("delete", "advisors", ("id", ADVISOR_ID))
    ]
    assert len(fake.auth_deletes()) == 1


@pytest.mark.asyncio
async def test_neither_role_retry_deletes_only_auth_user():
    """Partial-failure retry: business rows already gone, auth remains.

    get_verified_session (not get_current_session_roles) is what makes
    this reachable — pinned here so a refactor back to the default
    dependency fails a test instead of stranding half-deleted users.
    """
    fake = FakeSupabase()

    with _patch_supabase(fake):
        response = await account_router.delete_account(roles=_roles())

    assert response.deleted is True
    assert fake.deletes("clients") == []
    assert fake.deletes("advisors") == []
    assert fake.auth_deletes() == [("auth_delete", USER_ID, None)]


# --------------------------------------------------------------------------- #
# Advisor-roster guard (AC 5)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_advisor_with_roster_blocked_409_nothing_touched():
    fake = FakeSupabase(
        storage_tree=_client_storage_tree(),
        roster_rows=[
            {"id": CLIENT_ID, "user_id": USER_ID},  # own is_self row: fine
            {"id": "other-client-1", "user_id": "someone-else"},
            {"id": "other-client-2", "user_id": None},  # pending invite
        ],
    )

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await account_router.delete_account(
                roles=_roles(advisor_id=ADVISOR_ID, client_id=CLIENT_ID)
            )

    assert exc.value.status_code == 409
    assert "2 clients" in exc.value.detail
    # Nothing destructive ran — no storage, no row deletes, no auth.
    assert fake.fake_storage.removed == []
    assert fake.deletes("clients") == []
    assert fake.deletes("advisors") == []
    assert fake.auth_deletes() == []


# --------------------------------------------------------------------------- #
# Partial-failure safety (AC 7)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_storage_list_failure_aborts_before_any_delete():
    fake = FakeSupabase(storage_tree=_client_storage_tree())
    fake.fake_storage.list_error = RuntimeError("storage down")

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await account_router.delete_account(
                roles=_roles(client_id=CLIENT_ID)
            )

    assert exc.value.status_code == 502
    assert "nothing has been deleted" in exc.value.detail
    assert fake.deletes("clients") == []
    assert fake.auth_deletes() == []


@pytest.mark.asyncio
async def test_storage_remove_failure_aborts_before_any_delete():
    fake = FakeSupabase(storage_tree=_client_storage_tree())
    fake.fake_storage.remove_error = RuntimeError("remove failed")

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await account_router.delete_account(
                roles=_roles(client_id=CLIENT_ID)
            )

    assert exc.value.status_code == 502
    assert fake.deletes("clients") == []
    assert fake.auth_deletes() == []


@pytest.mark.asyncio
async def test_clients_delete_failure_leaves_auth_user_alone():
    fake = FakeSupabase(storage_tree={})
    fake.delete_error = RuntimeError("db down")

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await account_router.delete_account(
                roles=_roles(client_id=CLIENT_ID)
            )

    assert exc.value.status_code == 502
    assert "still active" in exc.value.detail
    assert fake.auth_deletes() == []


@pytest.mark.asyncio
async def test_auth_delete_failure_returns_502_with_retry_guidance():
    fake = FakeSupabase(storage_tree={})
    fake.auth_delete_error = RuntimeError("gotrue down")

    with _patch_supabase(fake):
        with pytest.raises(HTTPException) as exc:
            await account_router.delete_account(
                roles=_roles(client_id=CLIENT_ID)
            )

    assert exc.value.status_code == 502
    # Data is gone; the message must send the user back to retry, not
    # claim nothing happened.
    assert "data has been removed" in exc.value.detail
    assert len(fake.deletes("clients")) == 1


# --------------------------------------------------------------------------- #
# Waitlist sweep
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_waitlist_sweep_matches_case_insensitively():
    fake = FakeSupabase(
        storage_tree={},
        waitlist_rows=[
            {"id": "w-1", "email": "Client@Example.COM"},  # match
            {"id": "w-2", "email": "someone@else.com"},  # no match
            {"id": "w-3", "email": "  client@example.com "},  # match, padded
        ],
    )

    with _patch_supabase(fake):
        await account_router.delete_account(roles=_roles(client_id=CLIENT_ID))

    waitlist_deletes = fake.deletes("waitlist")
    assert len(waitlist_deletes) == 1
    _, _, (column, ids) = waitlist_deletes[0]
    assert column == "id"
    assert set(ids) == {"w-1", "w-3"}


@pytest.mark.asyncio
async def test_waitlist_sweep_skips_delete_when_no_match():
    fake = FakeSupabase(
        storage_tree={},
        waitlist_rows=[{"id": "w-2", "email": "someone@else.com"}],
    )

    with _patch_supabase(fake):
        await account_router.delete_account(roles=_roles(client_id=CLIENT_ID))

    assert fake.deletes("waitlist") == []


@pytest.mark.asyncio
async def test_waitlist_failure_is_non_fatal():
    fake = FakeSupabase(storage_tree={})
    fake.waitlist_select_error = RuntimeError("waitlist read failed")

    with _patch_supabase(fake):
        response = await account_router.delete_account(
            roles=_roles(client_id=CLIENT_ID)
        )

    # Deletion still completed end-to-end.
    assert response.deleted is True
    assert len(fake.deletes("clients")) == 1
    assert len(fake.auth_deletes()) == 1
