"""FastAPI auth dependencies for client-facing and admin-facing routes.

Refactored under ORPHEUS-37 to support the post-2026-05-11 decision
(Decision_Self_Serve_And_Advisor_Invite_2026-05-11.md):

  A single `auth.users` row can own up to one `public.advisors` row AND
  up to one `public.clients` row at the same time. Andrew (the advisor
  running the practice + analyzing himself) is the motivating case.

The flow:

  1. Request arrives with Authorization: Bearer <supabase_jwt>.
  2. `_resolve_session` parses the header, fetches the Supabase project's
     JWKS (RS256 or ES256 public keys), verifies signature + iss + aud +
     exp, extracts `sub`.
  3. Two independent SELECTs against `public.advisors` and
     `public.clients` keyed on `user_id = sub` populate the optional
     `advisor_id` and `client_id` fields of a `SessionRoles` dataclass.
  4. Two public dependencies wrap `_resolve_session`:
       * `get_current_session_roles` raises a clean 401 ("not invited")
         when neither business row exists. This is the right behavior for
         the 99% of authenticated routes that need a known role —
         downstream RLS would otherwise return empty result sets that
         surface as confusing 500s.
       * `get_verified_session` (ORPHEUS-38) accepts the neither-role
         case and returns a SessionRoles with both role fields `None`.
         Used by `/accept-invitation` (where the caller is freshly
         signed in but the clients row hasn't been linked yet) and by
         `GET /session` (the canonical "is the user invited" probe).
  5. Route handlers depend on the appropriate variant and gate themselves
     on `roles.is_client()` / `roles.is_advisor()` to express which
     role(s) they require. For data queries they use
     `user_scoped_supabase(token)` from backend/db.py so RLS policies see
     auth.uid() and the prod `get_advisor_id()` / `get_client_id()`
     SECURITY DEFINER helpers resolve correctly.

The JWKS is cached with a TTL so we're not fetching on every request but
key rotation still lands within a reasonable window.

Replaces the pre-ORPHEUS-37 `CurrentClient` / `get_current_client`
single-role dependency. That model assumed `clients.id = auth.users.id`
(LinkedIn 1:1, migration 007). Prod has been on the advisor-managed
invite shape for a while now: `clients.id` is a separate uuid, linked
to `auth.users.id` via `clients.user_id`, and the same auth user can
simultaneously own an `advisors` row.

Testing: backend/tests/test_auth.py covers the role permutations
(advisor-only / client-only / both / neither) plus the inherited token-
verification edge cases (expired, wrong audience, wrong issuer, unknown
kid, missing sub, malformed/missing header).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Header, HTTPException, status

from backend.config import get_settings
from backend.db import get_service_client

logger = logging.getLogger("orpheus.auth")


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Re-fetch the JWKS at most this often. Supabase rotates keys rarely; a
# 10-minute TTL is a reasonable balance for key rotation latency.
JWKS_CACHE_SECONDS = 600


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SessionRoles:
    """Resolved identity + role assignments for a logged-in Supabase user.

    `user_id` is always populated from the JWT `sub` claim. `advisor_id`
    and `client_id` are the matching business-row PKs (NOT the auth user
    id — `clients.id` and `advisors.id` are separate uuids that link to
    auth.users via their `user_id` column). Either may be `None` if the
    user holds only one role; both may be set if the user is both an
    advisor and a client (e.g. Andrew running his own diagnostic).

    `access_token` is passed through so route handlers can construct a
    per-request user-scoped Supabase client for RLS-bounded data queries.

    The "neither role" case (`advisor_id is None and client_id is None`)
    only ever reaches handlers via `get_verified_session` — the default
    `get_current_session_roles` dependency raises 401 before constructing
    such an instance. Endpoints that legitimately need the neither-role
    state (`/accept-invitation`, `GET /session`) depend on
    `get_verified_session` explicitly.
    """

    user_id: str
    email: str
    access_token: str
    advisor_id: str | None
    client_id: str | None

    def is_advisor(self) -> bool:
        return self.advisor_id is not None

    def is_client(self) -> bool:
        return self.client_id is not None


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

        # Supabase Auth (GoTrue v2) exposes JWKS at the standard well-known
        # path. Older versions used /auth/v1/jwks (no longer routed by
        # Kong). The well-known path is what `iss + /.well-known/jwks.json`
        # would be too — keep this in sync with whatever Supabase ships.
        url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
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
            keys_by_kid[kid] = _public_key_from_jwk(jwk)

        self._keys = keys_by_kid
        self._fetched_at = time.time()
        logger.info("Refreshed Supabase JWKS cache — %d keys", len(keys_by_kid))


def _public_key_from_jwk(jwk: dict[str, Any]) -> Any:
    """Build a PyJWT-compatible public key from a JWK, dispatching on `kty`.

    Supabase has historically issued RS256-signed tokens (`kty: "RSA"`). Newer
    Supabase CLI / GoTrue versions issue ES256-signed tokens (`kty: "EC"`,
    P-256 curve). We support both so the same backend code works against any
    in-use Supabase version, local or hosted, without redeploys.
    """
    import json as _json

    kty = jwk.get("kty")
    payload = _json.dumps(jwk)
    if kty == "RSA":
        return jwt.algorithms.RSAAlgorithm.from_jwk(payload)
    if kty == "EC":
        return jwt.algorithms.ECAlgorithm.from_jwk(payload)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Unsupported JWK key type: {kty!r}.",
    )


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
    settings = get_settings()
    supabase_url = settings.supabase_url
    audience = settings.supabase_jwt_audience
    issuer = f"{supabase_url}/auth/v1"

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
            # Supabase signs with RS256 (legacy) or ES256 (current GoTrue).
            # PyJWT picks the matching algorithm based on the public key's
            # type, so listing both is safe — it doesn't loosen verification.
            algorithms=["RS256", "ES256"],
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
# Role lookup
# --------------------------------------------------------------------------- #

def _lookup_role_id(table: str, user_id: str) -> str | None:
    """Return `{table}.id` for the row where `user_id = user_id`, or None.

    Uses the service-role client because we don't have user RLS context
    yet — the whole point of this lookup is to establish that context.
    The query is keyed on `user_id` (FK to auth.users), not on `id`, so
    it works for both the advisors and clients tables, which both use
    surrogate uuid PKs distinct from auth.users.id.
    """
    service = get_service_client()
    result = (
        service.table(table)
        .select("id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return str(result.data[0]["id"])


# --------------------------------------------------------------------------- #
# FastAPI dependencies
# --------------------------------------------------------------------------- #

async def _resolve_session(
    authorization: str | None,
    *,
    allow_no_roles: bool,
) -> SessionRoles:
    """Shared implementation behind `get_current_session_roles` /
    `get_verified_session`.

    Verifies the bearer JWT, then issues two independent SELECTs against
    `public.advisors` and `public.clients` keyed on `user_id = sub`. The
    queries are sequential but semantically parallel — each table has
    its own RLS scope (here bypassed via service-role) and the results
    don't depend on each other.

    Behavior is identical between the two public wrappers EXCEPT for the
    neither-role case:

      * `allow_no_roles=False` (default in `get_current_session_roles`)
        raises 401 when neither row exists. Right for routes that
        require a known role.
      * `allow_no_roles=True` (used by `get_verified_session`) returns
        a SessionRoles with both fields `None`. Right for routes that
        legitimately serve users mid-flow (`/accept-invitation`) or
        that exist precisely to surface the neither-role state
        (`GET /session`).

    Raises 401 in BOTH variants if:
      - The Authorization header is missing or malformed.
      - The JWT fails signature / iss / aud / exp / required-claims checks.
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

    advisor_id = _lookup_role_id("advisors", str(sub))
    client_id = _lookup_role_id("clients", str(sub))

    if advisor_id is None and client_id is None and not allow_no_roles:
        # The token is cryptographically valid but no business row owns
        # the user. Most commonly: a Supabase signup that never received
        # an invitation (or whose invitation hasn't been accepted yet).
        # The frontend treats this as a typed "not invited" state — but
        # only routes that explicitly opt into `get_verified_session`
        # see the SessionRoles; everything else gets the typed 401.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No advisor or client profile is associated with this account.",
        )

    return SessionRoles(
        user_id=str(sub),
        email=str(email),
        access_token=token,
        advisor_id=advisor_id,
        client_id=client_id,
    )


async def get_current_session_roles(
    authorization: str | None = Header(default=None),
) -> SessionRoles:
    """FastAPI dependency resolving the caller to a SessionRoles dataclass.

    Default session dependency — used by the 99% of authenticated routes
    that require at least one business-row role. Raises 401 in the
    neither-role case so the frontend gets a typed "not invited" signal
    instead of redirecting to /login as if the session had expired.
    """
    return await _resolve_session(authorization, allow_no_roles=False)


async def get_verified_session(
    authorization: str | None = Header(default=None),
) -> SessionRoles:
    """FastAPI dependency that allows the neither-role case (ORPHEUS-38).

    Variant of `get_current_session_roles` used by the small set of
    routes that need to serve freshly-authenticated users whose
    `clients` row hasn't been linked yet:

      * `POST /accept-invitation` — caller is post-OAuth but the
        invitation acceptance is the very thing that links the
        `clients` row to their auth user.
      * `GET /session` — the canonical "is the user invited" probe;
        returning `{advisor_id: null, client_id: null}` IS the
        meaningful response for not-yet-invited users.

    Still raises 401 on token / header / claims problems. The only
    semantic difference from `get_current_session_roles` is that the
    neither-role case returns a SessionRoles instance with both role
    fields set to `None`, rather than raising 401.
    """
    return await _resolve_session(authorization, allow_no_roles=True)
