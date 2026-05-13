"""Unit tests for backend/email/resend_client.py.

The wrapper has two distinct code paths:

  * Sandbox mode (api key starts with "test_" or is the literal "test")
    — no network call, returns a deterministic fake message id.
  * Real mode — POSTs to Resend's /emails endpoint and returns the
    response's `id` field.

We mock `urllib.request.urlopen` directly because the wrapper uses the
stdlib (no requests / httpx dependency). The fake urlopen is a context
manager because that's how the production code calls it.

Coverage matches the spec's commit #2 inventory: happy path, 4xx, 5xx,
network exception, sandbox mode.
"""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend import config as config_mod
from backend.email import resend_client


TO_EMAIL = "client@example.com"
ADVISOR_NAME = "Andrew Segars"
INVITE_URL = "https://app.example.com/invite/abc123"

# Minimal env so Settings instantiates inside the wrapper.
_BASE_ENV = {
    "SUPABASE_URL": "https://test.supabase.local",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "APP_BASE_URL": "https://app.test.local",
}


def _apply_env(monkeypatch, *, resend_key: str) -> None:
    """Apply the base env plus a specific RESEND_API_KEY."""
    for name in list(_BASE_ENV) + ["RESEND_API_KEY"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in _BASE_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("RESEND_API_KEY", resend_key)
    config_mod._reset_settings_cache_for_tests()


def _fake_urlopen_response(*, status: int, body: dict[str, Any] | str) -> Any:
    """Build a context-manager-compatible mock matching urlopen's shape."""
    payload = body if isinstance(body, str) else json.dumps(body)
    response = MagicMock()
    response.status = status
    response.read.return_value = payload.encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_send_invitation_email_happy_path(monkeypatch):
    """Real API key → POSTs to Resend and returns the message id."""
    _apply_env(monkeypatch, resend_key="re_real_key_value")

    fake_response = _fake_urlopen_response(
        status=200,
        body={"id": "msg_abc123"},
    )

    with patch.object(
        resend_client.urllib.request,
        "urlopen",
        return_value=fake_response,
    ) as fake_urlopen:
        message_id = resend_client.send_invitation_email(
            to_email=TO_EMAIL,
            advisor_name=ADVISOR_NAME,
            invite_url=INVITE_URL,
        )

    assert message_id == "msg_abc123"
    # Pin a few request-shape invariants without over-specifying:
    fake_urlopen.assert_called_once()
    request = fake_urlopen.call_args.args[0]
    assert request.full_url == resend_client.RESEND_ENDPOINT
    assert request.get_method() == "POST"
    assert request.headers["Authorization"] == "Bearer re_real_key_value"
    assert request.headers["Content-type"] == "application/json"

    body = json.loads(request.data.decode("utf-8"))
    assert body["from"] == resend_client.FROM_ADDRESS
    assert body["to"] == [TO_EMAIL]
    assert ADVISOR_NAME in body["subject"]
    assert INVITE_URL in body["html"]
    assert INVITE_URL in body["text"]


# --------------------------------------------------------------------------- #
# Error paths
# --------------------------------------------------------------------------- #

def test_send_invitation_email_4xx_raises_email_send_error(monkeypatch):
    """A 4xx from Resend (e.g. malformed payload, bad key) raises EmailSendError."""
    _apply_env(monkeypatch, resend_key="re_real_key_value")

    error_body = json.dumps({"message": "Invalid `to` field"}).encode("utf-8")
    http_error = urllib.error.HTTPError(
        url=resend_client.RESEND_ENDPOINT,
        code=422,
        msg="Unprocessable Entity",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(error_body),
    )

    with patch.object(
        resend_client.urllib.request,
        "urlopen",
        side_effect=http_error,
    ):
        with pytest.raises(resend_client.EmailSendError) as exc:
            resend_client.send_invitation_email(
                to_email=TO_EMAIL,
                advisor_name=ADVISOR_NAME,
                invite_url=INVITE_URL,
            )

    assert "422" in str(exc.value)
    assert "Invalid `to` field" in str(exc.value)


def test_send_invitation_email_5xx_raises_email_send_error(monkeypatch):
    """A 5xx from Resend (e.g. transient outage) raises EmailSendError too."""
    _apply_env(monkeypatch, resend_key="re_real_key_value")

    error_body = b"Internal Server Error"
    http_error = urllib.error.HTTPError(
        url=resend_client.RESEND_ENDPOINT,
        code=500,
        msg="Internal Server Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(error_body),
    )

    with patch.object(
        resend_client.urllib.request,
        "urlopen",
        side_effect=http_error,
    ):
        with pytest.raises(resend_client.EmailSendError) as exc:
            resend_client.send_invitation_email(
                to_email=TO_EMAIL,
                advisor_name=ADVISOR_NAME,
                invite_url=INVITE_URL,
            )

    assert "500" in str(exc.value)


def test_send_invitation_email_network_exception_raises_email_send_error(monkeypatch):
    """DNS / connection failures raise EmailSendError, not bare URLError."""
    _apply_env(monkeypatch, resend_key="re_real_key_value")

    with patch.object(
        resend_client.urllib.request,
        "urlopen",
        side_effect=urllib.error.URLError("Name or service not known"),
    ):
        with pytest.raises(resend_client.EmailSendError) as exc:
            resend_client.send_invitation_email(
                to_email=TO_EMAIL,
                advisor_name=ADVISOR_NAME,
                invite_url=INVITE_URL,
            )

    assert "network" in str(exc.value).lower()


# --------------------------------------------------------------------------- #
# Sandbox mode
# --------------------------------------------------------------------------- #

def test_sandbox_mode_skips_network_returns_fake_id(monkeypatch):
    """A test_-prefixed key short-circuits before the HTTP call."""
    _apply_env(monkeypatch, resend_key="test_ci_value")

    with patch.object(
        resend_client.urllib.request,
        "urlopen",
        side_effect=AssertionError("network must not be touched in sandbox mode"),
    ):
        message_id = resend_client.send_invitation_email(
            to_email=TO_EMAIL,
            advisor_name=ADVISOR_NAME,
            invite_url=INVITE_URL,
        )

    assert message_id.startswith("test_msg_")
    # Hex-formatted uuid4: 32 chars after the prefix.
    assert len(message_id) == len("test_msg_") + 32
