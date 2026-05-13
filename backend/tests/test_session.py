"""Unit tests for backend/routers/session.py — GET /session.

The endpoint is a near-trivial wrapper around `get_verified_session`;
the interesting coverage is that the four role permutations
(advisor-only, client-only, both, neither) all return 200 with the
right shape — and especially that neither-role doesn't accidentally
get demoted to 401 by a refactor.

The 401-on-missing-token case is functionally tested in test_auth.py
(`test_verified_session_rejects_missing_header`); we re-pin it at
this layer as a small documentation marker that the /session endpoint
inherits that gate.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend import auth as auth_mod
from backend.auth import SessionRoles
from backend.routers import session as session_router


USER_ID = "user-test-uuid"
EMAIL = "user@example.com"
ADVISOR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CLIENT_ID = "99999999-aaaa-bbbb-cccc-dddddddddddd"


def _roles(
    *,
    advisor_id: str | None = None,
    client_id: str | None = None,
) -> SessionRoles:
    return SessionRoles(
        user_id=USER_ID,
        email=EMAIL,
        access_token="test-token",
        advisor_id=advisor_id,
        client_id=client_id,
    )


# --------------------------------------------------------------------------- #
# Role permutations
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_session_advisor_only():
    """Advisor-only user — advisor_id set, client_id null."""
    response = await session_router.get_session(
        roles=_roles(advisor_id=ADVISOR_ID),
    )

    assert response.user_id == USER_ID
    assert response.email == EMAIL
    assert response.advisor_id == ADVISOR_ID
    assert response.client_id is None


@pytest.mark.asyncio
async def test_session_client_only():
    """Client-only user — client_id set, advisor_id null."""
    response = await session_router.get_session(
        roles=_roles(client_id=CLIENT_ID),
    )

    assert response.advisor_id is None
    assert response.client_id == CLIENT_ID


@pytest.mark.asyncio
async def test_session_both_roles():
    """Dual role — Andrew's case (advisor running his own diagnostic)."""
    response = await session_router.get_session(
        roles=_roles(advisor_id=ADVISOR_ID, client_id=CLIENT_ID),
    )

    assert response.advisor_id == ADVISOR_ID
    assert response.client_id == CLIENT_ID


@pytest.mark.asyncio
async def test_session_neither_role_returns_200_with_nulls():
    """The whole point of this endpoint: surface the 'not invited' state cleanly.

    The frontend uses {advisor_id: null, client_id: null} as its
    canonical signal to route the user to /not-invited rather than
    bouncing them out to /login as if their session had expired.
    A future refactor that demoted this to 401 would break that
    routing — this test exists to catch that regression.
    """
    response = await session_router.get_session(roles=_roles())

    assert response.user_id == USER_ID
    assert response.email == EMAIL
    assert response.advisor_id is None
    assert response.client_id is None


# --------------------------------------------------------------------------- #
# Auth-failure path (sanity duplicate of test_auth.py coverage)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_session_endpoint_inherits_missing_token_rejection():
    """A missing Authorization header still 401s via the dependency.

    `allow_no_roles=True` on get_verified_session relaxes the
    role-presence check, not the authentication check. Unauthenticated
    callers still get a typed 401 — they can't probe /session as an
    anonymous identity oracle.

    The deep coverage of header / JWT / claim failures lives in
    test_auth.py — this one assertion is here to document that
    /session inherits the same gate at the dependency layer.
    """
    with pytest.raises(HTTPException) as exc:
        await auth_mod.get_verified_session(None)

    assert exc.value.status_code == 401
