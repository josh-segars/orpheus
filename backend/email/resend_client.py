"""HTTP wrapper around the Resend transactional-email API.

Why hand-rolled instead of using the official Resend Python SDK? Same
reason auth.py fetches Supabase's JWKS by hand: keeping the dependency
surface area small and predictable. Resend's REST API is a single
POST endpoint with a flat JSON body — wrapping it directly costs us
~30 lines and zero new packages.

Public surface:
  * `EmailSendError` — raised on any non-2xx response or network failure.
  * `send_invitation_email(to_email, advisor_name, invite_url)` — the
    only function the routers call. Returns the Resend message id
    (or a deterministic fake one in sandbox mode).

Sandbox mode: if the configured `RESEND_API_KEY` starts with `test_`
(or is the literal string `test`), the wrapper logs the would-be email
and returns `f"test_msg_{uuid4().hex}"` without hitting the network.
This keeps pytest + CI offline and deterministic. Real production keys
start with `re_`, so the trigger is unambiguous.

Body content: commit #2 of ORPHEUS-38 ships with inline subject/html/
text strings. Commit #3 extracts those to `backend/email/templates.py`
without changing this module's public interface — `send_invitation_email`
will import a single `format_invitation_email(...)` and forward the
result. The split keeps the visual design pass isolated from the
HTTP-plumbing review.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

from backend.config import get_settings

logger = logging.getLogger("orpheus.email.resend")


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Locked decision from the spec — branding-stable across providers.
FROM_ADDRESS = "Orpheus Social <hello@orpheussocial.com>"

# Same timeout auth.py uses for JWKS — Resend is similarly lightweight.
HTTP_TIMEOUT_SECONDS = 5


# --------------------------------------------------------------------------- #
# Public exception
# --------------------------------------------------------------------------- #

class EmailSendError(RuntimeError):
    """Raised when Resend rejects a send or the network call fails.

    Callers (the invite / resend-invite endpoints) catch this and decide
    how to surface the failure to the advisor — typically a 502 with
    instructions to retry the resend endpoint. The exception message
    carries the underlying detail (Resend's error string or the network
    exception's `str()`) for log triage.
    """


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def send_invitation_email(
    to_email: str,
    advisor_name: str,
    invite_url: str,
) -> str:
    """Send an invitation email and return the Resend message id.

    Sandbox-mode keys short-circuit the network call (see module
    docstring). Real keys POST to Resend's /emails endpoint.

    Raises:
        EmailSendError: on any non-2xx response, network exception,
            or JSON decode failure on Resend's response.
    """
    settings = get_settings()
    api_key = settings.resend_api_key

    subject, html_body, text_body = _build_invitation_content(
        advisor_name=advisor_name,
        invite_url=invite_url,
    )

    if _is_sandbox_key(api_key):
        return _log_sandbox_send(
            to=to_email,
            subject=subject,
            text_body=text_body,
        )

    payload: dict[str, Any] = {
        "from": FROM_ADDRESS,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }

    return _post_to_resend(api_key=api_key, payload=payload)


# --------------------------------------------------------------------------- #
# Sandbox / network branching
# --------------------------------------------------------------------------- #

def _is_sandbox_key(api_key: str) -> bool:
    """Sandbox triggers: the literal "test" or any key starting with "test_".

    Production Resend keys start with `re_`, so there's no overlap. CI
    typically sets `RESEND_API_KEY=test_ci` to opt in.
    """
    if api_key == "test":
        return True
    return api_key.startswith("test_")


def _log_sandbox_send(*, to: str, subject: str, text_body: str) -> str:
    """Log the would-be email and return a deterministic-looking fake id."""
    fake_id = f"test_msg_{uuid4().hex}"
    logger.info(
        "RESEND SANDBOX — would send email "
        "(to=%s, subject=%r, body=%d chars). Fake message id: %s",
        to,
        subject,
        len(text_body),
        fake_id,
    )
    return fake_id


def _post_to_resend(*, api_key: str, payload: dict[str, Any]) -> str:
    """POST to Resend's /emails endpoint and return the response's `id`.

    Network errors and non-2xx responses are normalized into
    `EmailSendError`. We DON'T retry — the routers may want to keep
    the rotated invitation_token even on a send failure, so retry
    policy is a caller-level concern.
    """
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        RESEND_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            response_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # Resend returns JSON-shaped errors with a `message` key. If the
        # body isn't JSON (rare — proxy errors etc.) fall back to the
        # raw text so we surface SOMETHING actionable in the log.
        detail = _safe_decode_error_body(exc)
        logger.warning(
            "Resend rejected send (status=%s detail=%r)", exc.code, detail
        )
        raise EmailSendError(
            f"Resend rejected the send: {exc.code} {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        logger.warning("Resend network error: %s", exc.reason)
        raise EmailSendError(
            f"Network error reaching Resend: {exc.reason}"
        ) from exc

    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Resend returned a non-JSON body: %r", response_body[:200]
        )
        raise EmailSendError(
            "Resend returned a non-JSON response."
        ) from exc

    message_id = parsed.get("id")
    if not isinstance(message_id, str) or not message_id:
        logger.warning(
            "Resend response missing 'id' field: %r", parsed
        )
        raise EmailSendError(
            "Resend response did not contain a message id."
        )

    return message_id


def _safe_decode_error_body(exc: urllib.error.HTTPError) -> str:
    """Best-effort extraction of the Resend error message from an HTTPError."""
    try:
        raw = exc.read().decode("utf-8")
    except Exception:  # pragma: no cover — depends on exc internals
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:200]
    # Resend uses either `message` or `error` depending on the failure
    # mode; check both, fall back to the raw object.
    for key in ("message", "error"):
        value = parsed.get(key)
        if isinstance(value, str) and value:
            return value
    return str(parsed)[:200]


# --------------------------------------------------------------------------- #
# Invitation body — to be extracted to backend/email/templates.py in commit #3
# --------------------------------------------------------------------------- #

def _build_invitation_content(
    *,
    advisor_name: str,
    invite_url: str,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for the invitation email.

    Inline strings for now. Commit #3 of ORPHEUS-38 extracts these to
    `backend/email/templates.py` and adds a `format_invitation_email`
    entry point this function will delegate to. The interface stays
    the same so the routers don't need to know which commit shipped.
    """
    subject = f"{advisor_name} invited you to a Strategic Presence Diagnostic"

    html_body = (
        f"<p>{advisor_name} invited you to complete a Strategic Presence "
        f"Diagnostic with Orpheus Social.</p>"
        f"<p>To accept the invitation, sign in with LinkedIn:</p>"
        f'<p><a href="{invite_url}">{invite_url}</a></p>'
        f"<p>This link expires in 14 days.</p>"
    )

    text_body = (
        f"{advisor_name} invited you to complete a Strategic Presence "
        f"Diagnostic with Orpheus Social.\n\n"
        f"To accept the invitation, sign in with LinkedIn:\n"
        f"{invite_url}\n\n"
        f"This link expires in 14 days."
    )

    return subject, html_body, text_body
