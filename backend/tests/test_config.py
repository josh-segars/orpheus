"""Unit tests for backend/config.py — fail-fast env validation.

The Settings class declares which env vars are required and which have
defaults. These tests pin the contract for the ORPHEUS-38 additions
(`RESEND_API_KEY`, `APP_BASE_URL`) so future refactors don't silently
demote them to optional or skip URL validation.

We bypass the lru_cache on `get_settings()` by instantiating `Settings`
directly, and disable the `.env` file with `_env_file=None` so the dev
repo's real values don't leak into the tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend import config as config_mod


# All four currently-required env vars (pre-ORPHEUS-38). Tests set every
# one of these as a placeholder, then drop or override exactly one to
# isolate the validation rule under test.
_BASE_ENV = {
    "SUPABASE_URL": "https://test.supabase.local",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "RESEND_API_KEY": "re_test_value",
    "APP_BASE_URL": "https://app.example.com",
}


def _apply_env(monkeypatch, overrides: dict[str, str | None]) -> None:
    """Apply a base env, then layer overrides. `None` means unset."""
    # Start from a clean slate for every var the Settings class cares
    # about, otherwise a value present in the shell's actual env would
    # mask a "missing" case we're trying to test.
    for name in _BASE_ENV:
        monkeypatch.delenv(name, raising=False)
    for name, value in _BASE_ENV.items():
        if name in overrides:
            continue
        monkeypatch.setenv(name, value)
    for name, value in overrides.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def _build_settings() -> config_mod.Settings:
    """Instantiate Settings without reading the on-disk .env file."""
    return config_mod.Settings(_env_file=None)  # type: ignore[call-arg]


def test_missing_resend_api_key_fails_to_boot(monkeypatch):
    """ORPHEUS-38: RESEND_API_KEY is required at boot."""
    _apply_env(monkeypatch, {"RESEND_API_KEY": None})

    with pytest.raises(ValidationError) as exc:
        _build_settings()

    # Either the field name or the alias should appear somewhere in the
    # error list; the exact location format varies by pydantic version.
    rendered = str(exc.value)
    assert "RESEND_API_KEY" in rendered or "resend_api_key" in rendered


def test_missing_app_base_url_fails_to_boot(monkeypatch):
    """ORPHEUS-38: APP_BASE_URL is required at boot."""
    _apply_env(monkeypatch, {"APP_BASE_URL": None})

    with pytest.raises(ValidationError) as exc:
        _build_settings()

    rendered = str(exc.value)
    assert "APP_BASE_URL" in rendered or "app_base_url" in rendered


def test_app_base_url_rejects_bare_string(monkeypatch):
    """ORPHEUS-38: APP_BASE_URL must be http:// or https://."""
    _apply_env(monkeypatch, {"APP_BASE_URL": "app.orpheussocial.com"})

    with pytest.raises(ValidationError) as exc:
        _build_settings()

    assert "http://" in str(exc.value)


def test_app_base_url_trims_trailing_slash(monkeypatch):
    """A trailing slash on APP_BASE_URL is normalized — keeps invite-URL building clean."""
    _apply_env(monkeypatch, {"APP_BASE_URL": "https://app.example.com/"})

    settings = _build_settings()

    assert settings.app_base_url == "https://app.example.com"


def test_invitation_expiry_days_default_is_14(monkeypatch):
    """ORPHEUS-38: 14-day token lifetime is the documented default."""
    _apply_env(monkeypatch, {})  # all defaults

    settings = _build_settings()

    assert settings.invitation_expiry_days == 14


def test_invitation_expiry_days_rejects_zero(monkeypatch):
    """An expiry <1 day would issue effectively-instant-dead tokens."""
    _apply_env(monkeypatch, {"INVITATION_EXPIRY_DAYS": "0"})

    with pytest.raises(ValidationError):
        _build_settings()


def test_valid_env_produces_complete_settings(monkeypatch):
    """Sanity: with everything set, Settings instantiates and exposes the new fields."""
    _apply_env(monkeypatch, {})

    settings = _build_settings()

    assert settings.resend_api_key == "re_test_value"
    assert settings.app_base_url == "https://app.example.com"
    assert settings.invitation_expiry_days == 14
