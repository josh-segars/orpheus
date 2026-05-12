"""Unit tests for backend/auth.py.

We generate our own RSA keypair and sign tokens with it, then monkey-patch
the JWKS cache to return the matching public key. This exercises the real
PyJWT verification path without needing a live Supabase instance.

Coverage:
  Token-verification (inherited from ORPHEUS-27):
    - expired token → 401
    - wrong audience → 401
    - wrong issuer → 401
    - unknown kid → 401
    - missing sub → 401
    - malformed or missing Authorization header → 401
  Role resolution (ORPHEUS-37):
    - advisor-only user → SessionRoles with advisor_id set, client_id None
    - client-only user → SessionRoles with client_id set, advisor_id None
    - both roles → SessionRoles with both populated
    - neither role → 401 with "not invited" detail (NOT 500)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from backend import auth as auth_mod
from backend import config as config_mod


SUPABASE_URL = "https://test.supabase.local"
AUDIENCE = "authenticated"
ISSUER = f"{SUPABASE_URL}/auth/v1"
KID = "test-kid-1"
SUB = "11111111-2222-3333-4444-555555555555"
EMAIL = "jane@example.com"
ADVISOR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CLIENT_ID = "99999999-8888-7777-6666-555555555555"

# Required env vars for backend.config.Settings to instantiate. The auth
# module under test only reads supabase_url + supabase_jwt_audience, but
# the Settings class declares the other three as required, so we provide
# placeholder values here.
_REQUIRED_PLACEHOLDERS = {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "SUPABASE_JWT_AUDIENCE": AUDIENCE,
}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[Any, Any]:
    """Generate a throwaway RSA keypair shared across all tests in this module."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(autouse=True)
def _reset_env_and_cache(monkeypatch, rsa_keypair):
    """Ensure every test starts from a clean module-level cache and env."""
    private_key, public_key = rsa_keypair

    for name, value in _REQUIRED_PLACEHOLDERS.items():
        monkeypatch.setenv(name, value)

    # Settings is cached via lru_cache; clear it so each test re-reads the
    # monkeypatched env. Do this BEFORE the JWKS cache reset since the JWKS
    # refresh path calls get_settings().
    config_mod._reset_settings_cache_for_tests()

    auth_mod._reset_jwks_cache_for_tests()

    # Pre-populate the cache so _refresh is never called (no network).
    auth_mod._jwks_cache._keys = {KID: public_key}
    auth_mod._jwks_cache._fetched_at = time.time()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _pem(private_key) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _sign(claims: dict, private_key, kid: str = KID) -> str:
    return jwt.encode(claims, _pem(private_key), algorithm="RS256", headers={"kid": kid})


def _valid_claims(**overrides) -> dict:
    now = int(time.time())
    base = {
        "sub": SUB,
        "email": EMAIL,
        "aud": AUDIENCE,
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    base.update(overrides)
    return base


@dataclass
class FakeResult:
    data: list


class FakeTable:
    """Minimal stand-in for supabase-py's query builder.

    Accepts any chain of `.select(...).eq(...).limit(...)` and returns a
    pre-baked row (or empty list) on `.execute()`. The chain isn't
    actually inspected — we trust the caller to construct it correctly
    and only assert on the resolver's externally observable behavior.
    """

    def __init__(self, row: dict | None):
        self._row = row

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def execute(self):
        return FakeResult(data=[self._row] if self._row else [])


class FakeServiceClient:
    """Fake supabase service client supporting independent advisors + clients rows.

    Pass `advisors_row` and/or `clients_row` to model each of the four
    role permutations (advisor-only, client-only, both, neither). Each
    table call is dispatched to its own FakeTable so the resolver's two
    SELECTs are exercised independently.
    """

    def __init__(
        self,
        *,
        advisors_row: dict | None = None,
        clients_row: dict | None = None,
    ):
        self._advisors_row = advisors_row
        self._clients_row = clients_row

    def table(self, name: str):
        if name == "advisors":
            return FakeTable(self._advisors_row)
        if name == "clients":
            return FakeTable(self._clients_row)
        raise AssertionError(f"Unexpected table access: {name}")


def _service_client_with(
    *,
    advisors_row: dict | None = None,
    clients_row: dict | None = None,
):
    """Build a `patch.object(auth_mod, 'get_service_client', return_value=...)` context."""
    return patch.object(
        auth_mod,
        "get_service_client",
        return_value=FakeServiceClient(
            advisors_row=advisors_row,
            clients_row=clients_row,
        ),
    )


# --------------------------------------------------------------------------- #
# Happy paths — role permutations
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_advisor_only_role(rsa_keypair):
    """User has an advisors row but no clients row — advisor_id set, client_id None."""
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(), private_key)

    with _service_client_with(advisors_row={"id": ADVISOR_ID}, clients_row=None):
        roles = await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert roles.user_id == SUB
    assert roles.email == EMAIL
    assert roles.access_token == token
    assert roles.advisor_id == ADVISOR_ID
    assert roles.client_id is None
    assert roles.is_advisor() is True
    assert roles.is_client() is False


@pytest.mark.asyncio
async def test_client_only_role(rsa_keypair):
    """User has a clients row but no advisors row — client_id set, advisor_id None."""
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(), private_key)

    with _service_client_with(advisors_row=None, clients_row={"id": CLIENT_ID}):
        roles = await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert roles.user_id == SUB
    assert roles.advisor_id is None
    assert roles.client_id == CLIENT_ID
    assert roles.is_advisor() is False
    assert roles.is_client() is True


@pytest.mark.asyncio
async def test_both_roles(rsa_keypair):
    """User holds both an advisors row and a clients row — Andrew's case."""
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(), private_key)

    with _service_client_with(
        advisors_row={"id": ADVISOR_ID},
        clients_row={"id": CLIENT_ID},
    ):
        roles = await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert roles.advisor_id == ADVISOR_ID
    assert roles.client_id == CLIENT_ID
    assert roles.is_advisor() is True
    assert roles.is_client() is True


@pytest.mark.asyncio
async def test_neither_role_returns_401(rsa_keypair):
    """Token is valid but no advisors or clients row exists — clean 401, not a 500."""
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(), private_key)

    with _service_client_with(advisors_row=None, clients_row=None):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "advisor or client profile" in exc.value.detail.lower()


# --------------------------------------------------------------------------- #
# Token-verification edge cases
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_expired_token_returns_401(rsa_keypair):
    private_key, _ = rsa_keypair
    claims = _valid_claims(exp=int(time.time()) - 10, iat=int(time.time()) - 3600)
    token = _sign(claims, private_key)

    with _service_client_with(clients_row={"id": CLIENT_ID}):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_audience_returns_401(rsa_keypair):
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(aud="some-other-audience"), private_key)

    with _service_client_with(clients_row={"id": CLIENT_ID}):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "audience" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_issuer_returns_401(rsa_keypair):
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(iss="https://evil.example.com/auth/v1"), private_key)

    with _service_client_with(clients_row={"id": CLIENT_ID}):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "issuer" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_unknown_kid_returns_401(rsa_keypair, monkeypatch):
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(), private_key, kid="unknown-kid")

    # Prevent network refresh attempts.
    def _no_refresh(self, supabase_url):  # noqa: ARG001
        # no-op: the stale cache has only KID, not "unknown-kid"
        return

    monkeypatch.setattr(auth_mod._JWKSCache, "_refresh", _no_refresh)

    with _service_client_with(clients_row={"id": CLIENT_ID}):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "kid" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_missing_sub_returns_401(rsa_keypair):
    """A token signed correctly but without a sub claim is rejected.

    PyJWT's `options={"require": ["sub", ...]}` surfaces this as a MissingRequiredClaimError
    subclass of PyJWTError, which our handler maps to 401 with an "Invalid JWT" detail.
    """
    private_key, _ = rsa_keypair
    claims = _valid_claims()
    claims.pop("sub")
    token = _sign(claims, private_key)

    with _service_client_with(clients_row={"id": CLIENT_ID}):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_session_roles(f"Bearer {token}")

    assert exc.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Bearer",
        "Bearer ",
        "Basic abc",
        "Token xyz",
    ],
)
async def test_malformed_or_missing_header_returns_401(header):
    with pytest.raises(HTTPException) as exc:
        await auth_mod.get_current_session_roles(header)

    assert exc.value.status_code == 401
