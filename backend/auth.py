"""FastAPI auth dependencies for client-facing and admin-facing routes.

Ships with ORPHEUS-27 (client) — ORPHEUS-31 adds the admin dependency.

The flow:

  1. Request arrives with Authorization: Bearer <supabase_jwt>.
  2. `get_current_client` parses the header, fetches the Supabase project's
     JWKS (RS256 public keys), verifies signature + iss + aud + exp,
     extracts `sub`, looks up the matching public.clients row via the
     service-role client, and returns a typed CurrentClient.
  3. Route handlers depend on `get_current_client` and use
     `user_scoped_supabase(token)` from backend/db.py for all data queries
     so RLS policies see auth.uid() == client_id.

The JWKS is cached with a TTL so we're not fetching on every request but
key rotation still lands within a reasonable window.

Testing: backend/tests/test_auth.py covers the edge cases called out in
ORPHEUS-27 (expired, wrong audience, unknown kid, missing clients row).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from backend.db import get_service_client

logger = logging.getLogger("orpheus.auth")


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Supabase uses `authenticated` as the JWT audience for logged-in users.
DEFAULT_JWT_AUDIENCE = "authenticated"

# Re-fetch the JWKS at most this often. Supabase rotates keys rarely; a
# 10-minute TTL is a reasonable balance for key rotation latency.
JWKS_CACHE_SECONDS = 600


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CurrentClient:
    """Resolved identity for a logged-in portal client.

    `user_id` and `client_id` are the same uuid (public.clients.id == auth.users.id),
    but we expose both so call sites can express intent clearly.
    """

    user_id: str
    client_id: str
    email: str
    access_token: str  # passed through so route handlers can build a user-scoped Supabase client


# --------------------------------------------------------------------------- #
# JWKS cache
# --------------------------------------------------------------------------- #

class _JWKSCache:
    """Tiny TTL cache for the Supabase JWKS endpoint.

    We deliberately don't use `functools.lru_cache` here — we need time-based
    invalidation, not LRU.
    """

    def __init__(self, ttl: int = JWKS_CACHE_SECONDS) -> None:
        self._ttl = ttl
        self._fetched_at: float = 0.0
        self._keys: dict[str, Any] = {}

    def get_key(self, kid: str, supabase_url: str) -> Any:
        """Return the public key matching `kid`, refreshing if cache is stale."""
        now = time.time()
        if now - self._fetched_at > self._ttl or kid not in self._keys:
            self._refresh(supabase_url)
        key = self._keys.get(kid)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"No JWKS entry matches kid={kid!r}.",
            )
        return key

    def _refresh(self, supabase_url: str) -> None:
        # Imported lazily so unit tests can run without requests/httpx.
        import urllib.request
        import json as _json

        url = f"{supabase_url.rstrip('/')}/auth/v1/jwks"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                raw = _json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover — network-dependent
            logger.exception("Failed to fetch Supabase JWKS from %s", url)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not reach Supabase JWKS endpoint.",
            ) from exc

        keys_by_kid: dict[str, Any] = {}
        for jwk in raw.get("keys", []):
            kid = jwk.get("kid")
            if not kid:
                continue
            keys_by_kid[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(_json.dumps(jwk))

        self._keys = keys_by_kid
        self._fetched_at = time.time()
        logger.info("Refreshed Supabase JWKS cache — %d keys", len(keys_by_kid))


_jwks_cache = _JWKSCache()


def _reset_jwks_cache_for_tests() -> None:
    """Test hook — wipes the module-level cache so tests don't leak into each other."""
    global _jwks_cache
    _jwks_cache = _JWKSCache()


# --------------------------------------------------------------------------- #
# Token verification
# --------------------------------------------------------------------------- #

def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1].strip()


def _verify_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase-issued JWT and return its claims.

    Raises HTTPException(401) on any verification failure.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL is not configured on the server.",
        )
    audience = os.environ.get("SUPABASE_JWT_AUDIENCE", DEFAULT_JWT_AUDIENCE)
    issuer = f"{supabase_url.rstrip('/')}/auth/v1"

    # Step 1: parse header to find the key id.
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT header: {exc}",
        ) from exc

    kid = header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT header missing 'kid'.",
        )

    public_key = _jwks_cache.get_key(kid, supabase_url)

    # Step 2: verify signature + iss + aud + exp.
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT has expired.",
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT audience mismatch.",
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT issuer mismatch.",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT: {exc}",
        ) from exc

    return claims


# --------------------------------------------------------------------------- #
# FastAPI dependencies
# --------------------------------------------------------------------------- #

async def get_current_client(
    authorization: str | None = Header(default=None),
) -> CurrentClient:
    """FastAPI dependency resolving the caller to a CurrentClient.

    Raises 401 if any step of verification fails, or if no public.clients row
    exists for the token's subject. The "no clients row" branch should only
    fire if something broke between auth.users insertion and the
    on_auth_user_created trigger (migration 007). In practice that means
    unverified emails, which the trigger explicitly aborts — so a 401 here is
    the correct response, not a 404.
    """
    token = _extract_bearer_token(authorization)
    claims = _verify_jwt(token)

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing required claims (sub, email).",
        )

    service = get_service_client()
    result = (
        service.table("clients")
        .select("id")
        .eq("id", sub)
        .limit(1)
        .execute()
    )

    if not result.data:
        # Auth row exists but no business row — treat as "unknown client".
        # Most commonly: a pre-trigger sign-in that was aborted, or a row
        # deleted out of band. Either way, the caller is not authorized.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No client profile is associated with this account.",
        )

    return CurrentClient(
        user_id=str(sub),
        client_id=str(sub),
        email=str(email),
        access_token=token,
    )


# Alias for route handlers that prefer a named dependency.
CurrentClientDep = Depends(get_current_client)
