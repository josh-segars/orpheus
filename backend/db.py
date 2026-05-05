"""Supabase client factories.

Two usage patterns, per Decision: LinkedIn Auth (ORPHEUS-23):

  1. Service-role client — used by the worker (backend/workers/processor.py)
     and admin-only API routes. Bypasses RLS by design.

  2. User-scoped client  — used by client-facing API routes. Configured with
     the caller's Supabase JWT so all queries execute under the user's
     auth.uid() and RLS policies apply.

The existing worker file (backend/workers/processor.py) still constructs its
own client for historical reasons; consolidating that onto `get_service_client`
is a small refactor left for a follow-up ticket.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is not set. See backend/.env.example."
        )
    return value


@lru_cache(maxsize=1)
def get_service_client() -> "Client":
    """Service-role Supabase client. RLS-bypassing. Long-lived, cached.

    Use for worker code, admin endpoints, and the JWT-verification dependency
    itself (which needs to read public.clients before any user context is
    available).
    """
    from supabase import create_client

    return create_client(
        _require_env("SUPABASE_URL"),
        _require_env("SUPABASE_SERVICE_KEY"),
    )


def user_scoped_supabase(access_token: str) -> "Client":
    """Return a Supabase client configured with the caller's JWT.

    Queries executed with this client will have `auth.uid()` resolve to the
    token's `sub` claim, so RLS policies see the correct user. This is what
    client-facing route handlers must use so the 008 RLS migration actually
    enforces ownership.

    We create a fresh client per request rather than caching — the access
    token is request-scoped and the supabase-py client holds the token as
    state. Reusing a cached client across users would cause auth bleed.
    """
    from supabase import create_client

    client = create_client(
        _require_env("SUPABASE_URL"),
        _require_env("SUPABASE_ANON_KEY"),
    )
    # supabase-py attaches the JWT to PostgREST via postgrest.auth(). This
    # is stable public API across v1.x and v2.x of the Python client.
    client.postgrest.auth(access_token)
    return client
