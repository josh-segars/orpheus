"""Typed application settings, loaded from environment / .env at startup.

Concentrating env reads here gives us:

  * Fail-fast at boot — Pydantic raises a ValidationError listing every
    missing or malformed env var, instead of a confusing 401 cascade or
    KeyError later.
  * One source of truth — db.py / auth.py / main.py all read from
    `get_settings()` instead of sprinkling `os.environ.get(...)` around.
  * A clear contract for ops — every required var has its purpose
    documented in the Field description and mirrored in
    backend/.env.example.

The worker (backend/workers/processor.py) currently keeps its own env
reads. Folding it in is a small follow-up; not strictly part of
ORPHEUS-32.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Required fields fail fast on missing values."""

    model_config = SettingsConfigDict(
        # Reads `<repo-root>/backend/.env` in dev. In production the values
        # arrive via the deploy platform's env vars (Railway), so the file
        # need not exist — pydantic-settings falls back to os.environ
        # when env_file isn't found.
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Supabase --------------------------------------------------------- #

    supabase_url: str = Field(
        ...,
        alias="SUPABASE_URL",
        description="Base URL of the Supabase project (e.g. http://127.0.0.1:54321 locally).",
    )
    supabase_service_key: str = Field(
        ...,
        alias="SUPABASE_SERVICE_KEY",
        description="Service-role API key. Bypasses RLS — keep server-side only.",
    )
    supabase_anon_key: str = Field(
        ...,
        alias="SUPABASE_ANON_KEY",
        description="Anon API key. Used by the user-scoped client to apply RLS via JWT.",
    )
    supabase_jwt_audience: str = Field(
        default="authenticated",
        alias="SUPABASE_JWT_AUDIENCE",
        description="Expected `aud` claim on Supabase-issued JWTs. Default matches Supabase's logged-in user audience.",
    )

    # --- Anthropic -------------------------------------------------------- #

    anthropic_api_key: str = Field(
        ...,
        alias="ANTHROPIC_API_KEY",
        description="Used by the worker for rubric scoring and narrative generation.",
    )

    # --- Auth allowlists -------------------------------------------------- #

    admin_emails: str = Field(
        default="",
        alias="ADMIN_EMAILS",
        description=(
            "Comma-separated emails authorized for /admin endpoints "
            "(ORPHEUS-31). Backend gate; consumed by the "
            "`get_current_admin` dependency. Frontend mirrors this via "
            "VITE_ADMIN_EMAILS — keep both lists in sync. Case-"
            "insensitive comparison."
        ),
    )

    frontend_origins: str = Field(
        default="http://localhost:5173",
        alias="FRONTEND_ORIGINS",
        description="Comma-separated list of allowed CORS origins. Vite dev server by default.",
    )

    # --- Resend / invitation flow (ORPHEUS-38) ---------------------------- #

    resend_api_key: str = Field(
        ...,
        alias="RESEND_API_KEY",
        description=(
            "Resend transactional-email API key. Production keys start with "
            "`re_`. Keys starting with `test_` (or the literal `test`) "
            "trigger sandbox mode in backend/email/resend_client.py — the "
            "wrapper logs the would-be email and returns a fake message id "
            "instead of making a network call. Used in pytest + CI."
        ),
    )

    app_base_url: str = Field(
        ...,
        alias="APP_BASE_URL",
        description=(
            "Public base URL of the frontend app. Used to construct the "
            "invitation link sent in transactional emails "
            "(`{APP_BASE_URL}/invite/<token>`). Prod: "
            "https://app.orpheussocial.com. Local e2e: http://localhost:5173."
        ),
    )

    invitation_expiry_days: int = Field(
        default=14,
        alias="INVITATION_EXPIRY_DAYS",
        description=(
            "Lifetime of an unaccepted invitation, in days. The backend "
            "enforces expiry at acceptance time (no DB-level check), so "
            "shortening this only affects newly issued tokens. Default "
            "matches the spec — 14 days."
        ),
    )

    beta_survey_url: str = Field(
        default="",
        alias="BETA_SURVEY_URL",
        description=(
            "Closed-beta feedback Google Form URL (ORPHEUS-98) — the same "
            "form as the frontend's VITE_BETA_SURVEY_URL. Used by the "
            "report-completion email's feedback CTA. The advisory-"
            "publication send path (admin router) reads it from here; the "
            "worker's self-serve send path reads BETA_SURVEY_URL straight "
            "from os.environ (worker keeps its own env reads). When unset, "
            "the email ships with no feedback block (clean thank-you, no "
            "dead link). Set on BOTH Railway services."
        ),
    )

    # --- Validators ------------------------------------------------------- #

    @field_validator("supabase_url")
    @classmethod
    def _normalize_supabase_url(cls, value: str) -> str:
        if not value:
            raise ValueError("SUPABASE_URL must be set")
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError(
                "SUPABASE_URL must start with http:// or https:// "
                f"(got: {value!r})"
            )
        return value.rstrip("/")

    @field_validator("app_base_url")
    @classmethod
    def _validate_app_base_url(cls, value: str) -> str:
        # The invitation email contains a link built from this value; if it's
        # malformed we'd ship broken links to clients. Cheap to validate at
        # boot.
        if not value:
            raise ValueError("APP_BASE_URL must be set")
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError(
                "APP_BASE_URL must start with http:// or https:// "
                f"(got: {value!r})"
            )
        return value.rstrip("/")

    @field_validator("invitation_expiry_days")
    @classmethod
    def _validate_invitation_expiry_days(cls, value: int) -> int:
        if value < 1:
            raise ValueError(
                "INVITATION_EXPIRY_DAYS must be >= 1 "
                f"(got: {value})"
            )
        return value

    @field_validator("frontend_origins")
    @classmethod
    def _validate_frontend_origins(cls, value: str) -> str:
        # Make sure each entry is a syntactically valid origin before the
        # CORS middleware sees it. Empty list is allowed but odd; we just
        # warn via ValueError so ops sees the problem at boot.
        for raw in value.split(","):
            origin = raw.strip()
            if not origin:
                continue
            if not (origin.startswith("http://") or origin.startswith("https://")):
                raise ValueError(
                    "Each entry in FRONTEND_ORIGINS must start with http:// or https:// "
                    f"(got: {origin!r})"
                )
        return value

    # --- Derived helpers -------------------------------------------------- #

    @property
    def admin_email_set(self) -> set[str]:
        """Lower-cased set for case-insensitive membership checks."""
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def frontend_origin_list(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application Settings singleton.

    The first call validates env vars and may raise pydantic.ValidationError
    if anything required is missing. Subsequent calls return the cached
    instance. Tests should call `_reset_settings_cache_for_tests()` to
    invalidate the cache between cases that monkeypatch env vars.
    """
    return Settings()  # type: ignore[call-arg]


def _reset_settings_cache_for_tests() -> None:
    """Invalidate the get_settings() cache. For test isolation only."""
    get_settings.cache_clear()
