"""POST /consent/terms — ORPHEUS-126.

The ToS + Privacy acceptance is given by a checkbox on /login, before the
LinkedIn OIDC hop, so there is no authenticated identity at the moment of the
affirmative act. The frontend carries the accepted versions across the
redirect (frontend/src/lib/consent.ts) and posts them here on the first
authenticated render.

What these tests pin, in rough order of how much it would hurt to get wrong:

  * A version pair we don't publish is refused. Recording consent against a
    document version that never existed produces a row indistinguishable
    from a real one, which is worse than no row at all.
  * The endpoint is idempotent — the frontend retries across refreshes, and
    two tabs finishing the OAuth hop together must not 500 at a user who did
    everything right.
  * It tolerates a neither-role caller. A brand-new self-serve user has no
    clients row yet and an advisor-invited user posts this before
    /accept-invitation runs; the strict dependency would 401 both and lose
    the consent record. Same reasoning ORPHEUS-124's DELETE /account applies
    to its own retry path.

Handler-invocation pattern follows test_account_delete.py: patch
`get_service_client`, call the handler directly.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend import config as config_mod
from backend.auth import SessionRoles
from backend.consent_versions import (
    CURRENT_PRIVACY_VERSION,
    CURRENT_TERMS_VERSION,
)
from backend.routers import consent as consent_router
from backend.routers.consent import RecordTermsAcceptanceRequest


USER_ID = "44444444-4444-4444-4444-444444444444"

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


def _roles(advisor_id: str | None = None, client_id: str | None = None):
    return SessionRoles(
        user_id=USER_ID,
        email="client@example.com",
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


def _body(
    terms_version: str | None = None,
    privacy_version: str | None = None,
) -> RecordTermsAcceptanceRequest:
    return RecordTermsAcceptanceRequest(
        terms_version=terms_version or CURRENT_TERMS_VERSION,
        privacy_version=privacy_version or CURRENT_PRIVACY_VERSION,
    )


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class FakeQuery:
    def __init__(self, parent: "FakeSupabase", table: str) -> None:
        self._parent = parent
        self._table = table
        self._filters: dict[str, Any] = {}

    def select(self, *_args: Any) -> "FakeQuery":
        return self

    def eq(self, column: str, value: Any) -> "FakeQuery":
        self._filters[column] = value
        return self

    def limit(self, _n: int) -> "FakeQuery":
        return self

    def insert(self, payload: dict[str, Any]) -> "FakeQuery":
        self._payload = payload
        return self

    def execute(self) -> Any:
        if hasattr(self, "_payload"):
            if self._parent.insert_error is not None:
                raise self._parent.insert_error
            self._parent.inserts.append((self._table, self._payload))
            return type("R", (), {"data": [self._payload]})()
        # Read path — return whatever the fixture was seeded with.
        matched = [
            row
            for row in self._parent.rows
            if all(row.get(k) == v for k, v in self._filters.items())
        ]
        return type("R", (), {"data": matched})()


class FakeSupabase:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        insert_error: Exception | None = None,
    ) -> None:
        self.rows = rows or []
        self.insert_error = insert_error
        self.inserts: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)


# --------------------------------------------------------------------------- #
# Version validation
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_rejects_unknown_terms_version():
    fake = FakeSupabase()
    with patch.object(consent_router, "get_service_client", return_value=fake):
        with pytest.raises(HTTPException) as exc:
            await consent_router.record_terms_acceptance(
                body=_body(terms_version="1999-01-01"), roles=_roles()
            )
    assert exc.value.status_code == 400
    assert "terms version" in exc.value.detail.lower()
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_rejects_unknown_privacy_version():
    fake = FakeSupabase()
    with patch.object(consent_router, "get_service_client", return_value=fake):
        with pytest.raises(HTTPException) as exc:
            await consent_router.record_terms_acceptance(
                body=_body(privacy_version="1999-01-01"), roles=_roles()
            )
    assert exc.value.status_code == 400
    assert "privacy policy version" in exc.value.detail.lower()
    assert fake.inserts == []


# --------------------------------------------------------------------------- #
# Recording
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_records_the_acceptance_against_the_caller():
    fake = FakeSupabase()
    with patch.object(consent_router, "get_service_client", return_value=fake):
        result = await consent_router.record_terms_acceptance(
            body=_body(), roles=_roles(client_id="client-uuid")
        )

    assert result.recorded is True
    assert len(fake.inserts) == 1
    table, payload = fake.inserts[0]
    assert table == "terms_acceptances"
    assert payload["user_id"] == USER_ID
    assert payload["terms_version"] == CURRENT_TERMS_VERSION
    assert payload["privacy_version"] == CURRENT_PRIVACY_VERSION
    # accepted_at is the column default — the server's clock, never the
    # client's assertion.
    assert "accepted_at" not in payload


@pytest.mark.asyncio
async def test_accepts_a_neither_role_caller():
    """A brand-new user has no clients row when this fires. Refusing them
    would lose the acceptance we just collected."""
    fake = FakeSupabase()
    with patch.object(consent_router, "get_service_client", return_value=fake):
        result = await consent_router.record_terms_acceptance(
            body=_body(), roles=_roles(advisor_id=None, client_id=None)
        )
    assert result.recorded is True
    assert len(fake.inserts) == 1


@pytest.mark.asyncio
async def test_is_idempotent_when_the_acceptance_already_exists():
    """The frontend re-posts across refreshes until it sees a success, so a
    second call must be a no-op rather than a duplicate row."""
    fake = FakeSupabase(
        rows=[
            {
                "id": "existing",
                "user_id": USER_ID,
                "terms_version": CURRENT_TERMS_VERSION,
                "privacy_version": CURRENT_PRIVACY_VERSION,
            }
        ]
    )
    with patch.object(consent_router, "get_service_client", return_value=fake):
        result = await consent_router.record_terms_acceptance(
            body=_body(), roles=_roles()
        )

    assert result.recorded is False
    assert fake.inserts == []


@pytest.mark.asyncio
async def test_a_different_version_pair_admits_a_new_row():
    """An existing acceptance for another version must NOT satisfy the
    current one — that is the whole point of versioning under ToS s19."""
    fake = FakeSupabase(
        rows=[
            {
                "id": "old",
                "user_id": USER_ID,
                "terms_version": "2026-01-01",
                "privacy_version": "2026-01-01",
            }
        ]
    )
    with patch.object(consent_router, "get_service_client", return_value=fake):
        result = await consent_router.record_terms_acceptance(
            body=_body(), roles=_roles()
        )
    assert result.recorded is True
    assert len(fake.inserts) == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_is_treated_as_recorded_not_a_failure():
    """Two tabs finishing the OAuth hop together trip the unique index. The
    end state is exactly what we wanted, so don't 500 at the user."""
    err = Exception('duplicate key value violates unique constraint (23505)')
    fake = FakeSupabase(insert_error=err)
    with patch.object(consent_router, "get_service_client", return_value=fake):
        result = await consent_router.record_terms_acceptance(
            body=_body(), roles=_roles()
        )
    assert result.recorded is False


@pytest.mark.asyncio
async def test_a_real_insert_failure_is_a_502():
    """Anything that isn't a unique violation is a genuine failure and must
    surface, so the frontend keeps the pending value and retries."""
    fake = FakeSupabase(insert_error=RuntimeError("connection reset"))
    with patch.object(consent_router, "get_service_client", return_value=fake):
        with pytest.raises(HTTPException) as exc:
            await consent_router.record_terms_acceptance(
                body=_body(), roles=_roles()
            )
    assert exc.value.status_code == 502


def test_unique_violation_detection_shapes():
    """The supabase client wraps PostgREST errors rather than raising
    psycopg exceptions, so there is no class to catch — detection is by
    code attribute or message text."""
    assert consent_router._is_unique_violation(
        type("E", (Exception,), {"code": "23505"})()
    )
    assert consent_router._is_unique_violation(
        Exception("duplicate key value violates unique constraint")
    )
    assert consent_router._is_unique_violation(Exception("... 23505 ..."))
    assert not consent_router._is_unique_violation(
        Exception("connection reset by peer")
    )
