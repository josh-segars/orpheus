"""Unit tests for backend/auth.py.

We generate our own RSA keypair and sign tokens with it, then monkey-patch
the JWKS cache to return the matching public key. This exercises the real
PyJWT verification path without needing a live Supabase instance.

Acceptance criteria from ORPHEUS-27:
  - expired token → 401
  - wrong audience → 401
  - unknown kid    → 401
  - missing sub    → 401
  - no clients row → 401
Plus baseline happy-path and malformed-header coverage.
"""

from __future__ import annotations

import json
import os
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


SUPABASE_URL = "https://test.supabase.local"
AUDIENCE = "authenticated"
ISSUER = f"{SUPABASE_URL}/auth/v1"
KID = "test-kid-1"
SUB = "11111111-2222-3333-4444-555555555555"
EMAIL = "jane@example.com"


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

    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", AUDIENCE)

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
    """Minimal stand-in for supabase-py's query builder."""

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
    def __init__(self, clients_row: dict | None):
        self._clients_row = clients_row

    def table(self, name: str):
        if name == "clients":
            return FakeTable(self._clients_row)
        raise AssertionError(f"Unexpected table access: {name}")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_happy_path_returns_current_client(rsa_keypair):
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(), private_key)

    with patch.object(
        auth_mod, "get_service_client", return_value=FakeServiceClient({"id": SUB})
    ):
        current = await auth_mod.get_current_client(f"Bearer {token}")

    assert current.user_id == SUB
    assert current.client_id == SUB
    assert current.email == EMAIL
    assert current.access_token == token


@pytest.mark.asyncio
async def test_expired_token_returns_401(rsa_keypair):
    private_key, _ = rsa_keypair
    claims = _valid_claims(exp=int(time.time()) - 10, iat=int(time.time()) - 3600)
    token = _sign(claims, private_key)

    with patch.object(
        auth_mod, "get_service_client", return_value=FakeServiceClient({"id": SUB})
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_client(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_audience_returns_401(rsa_keypair):
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(aud="some-other-audience"), private_key)

    with patch.object(
        auth_mod, "get_service_client", return_value=FakeServiceClient({"id": SUB})
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_client(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "audience" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_issuer_returns_401(rsa_keypair):
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(iss="https://evil.example.com/auth/v1"), private_key)

    with patch.object(
        auth_mod, "get_service_client", return_value=FakeServiceClient({"id": SUB})
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_client(f"Bearer {token}")

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

    with patch.object(
        auth_mod, "get_service_client", return_value=FakeServiceClient({"id": SUB})
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_client(f"Bearer {token}")

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

    with patch.object(
        auth_mod, "get_service_client", return_value=FakeServiceClient({"id": SUB})
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_client(f"Bearer {token}")

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_no_clients_row_returns_401(rsa_keypair):
    """Token is valid but no public.clients row exists (e.g. unverified email that slipped the trigger)."""
    private_key, _ = rsa_keypair
    token = _sign(_valid_claims(), private_key)

    with patch.object(
        auth_mod, "get_service_client", return_value=FakeServiceClient(None)
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.get_current_client(f"Bearer {token}")

    assert exc.value.status_code == 401
    assert "client profile" in exc.value.detail.lower()


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
        await auth_mod.get_current_client(header)

    assert exc.value.status_code == 401
