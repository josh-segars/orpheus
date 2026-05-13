"""Session API — the canonical 'who am I' probe (ORPHEUS-38).

The frontend calls this once per authenticated portal render to decide
which UI surface to show:

  * `is_advisor && is_client` → tab toggle ("Manage clients" / "My
    report"). Andrew's case.
  * `is_advisor only`         → /advisor/clients dashboard.
  * `is_client only`          → standard portal (Groundwork → Diagnostic).
  * `neither`                 → /not-invited error page.

The "neither role" case must return 200 with both role fields null —
the whole point of this endpoint is to surface that state cleanly so
the frontend can route the user to the not-invited UI without going
through a confusing 401 cascade.

Uses `get_verified_session` (which allows neither-role) rather than
the default `get_current_session_roles` (which raises 401 on
neither-role). The two role-presence tests test_auth.py covers them
both; here we only assert the shape of the response.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth import SessionRoles, get_verified_session


router = APIRouter(tags=["session"])


class SessionResponse(BaseModel):
    """Canonical session response shape.

    Mirrors the SessionRoles dataclass minus the access_token (which
    the client already holds). `advisor_id` and `client_id` are both
    optional; either may be null, both may be null, or both may be
    set.
    """

    user_id: str
    email: str
    advisor_id: str | None
    client_id: str | None


@router.get("/session", response_model=SessionResponse)
async def get_session(
    roles: Annotated[SessionRoles, Depends(get_verified_session)],
) -> SessionResponse:
    """Return the caller's session identity + role assignments.

    Always 200 for an authenticated request, including the
    neither-role state. Token / header problems still 401 via the
    inherited dependency.
    """
    return SessionResponse(
        user_id=roles.user_id,
        email=roles.email,
        advisor_id=roles.advisor_id,
        client_id=roles.client_id,
    )
