"""Process-level configuration and production startup guards.

Kept deliberately tiny and import-light: nothing here imports the database or
the routers, so it is safe to import from anywhere (including the app factory).

The guards exist because a misconfigured production deploy is worse than a
refused one: a missing SESSION_SECRET silently signs everyone out on every
restart, and an unconfigured email provider silently fails every sign-up. Both
are hard failures that only surface when a real user hits them, so we refuse to
start instead.
"""
from __future__ import annotations

import os

APP_ENV = (os.environ.get("APP_ENV") or "development").strip().lower()
IS_PRODUCTION = APP_ENV in ("production", "prod")

# A session secret shorter than this is not meaningfully better than a guess.
MIN_SECRET_LENGTH = 32


def production_config_errors() -> list[str]:
    """Return the reasons this process must not start in production (may be empty)."""
    if not IS_PRODUCTION:
        return []

    errors: list[str] = []

    secret = (os.environ.get("SESSION_SECRET") or "").strip()
    if len(secret) < MIN_SECRET_LENGTH:
        errors.append(
            "SESSION_SECRET must be set to a random string of at least "
            f"{MIN_SECRET_LENGTH} characters (it signs every session cookie)."
        )

    # Imported lazily so this module stays free of heavier imports at top level.
    from app.services import email as email_service

    if email_service.provider_name() in ("unconfigured", "console"):
        errors.append(
            "Email must be configured for production: set RESEND_API_KEY and "
            "EMAIL_FROM (EMAIL_PROVIDER=console is refused in production)."
        )

    return errors


def require_production_config() -> None:
    """Raise RuntimeError (aborting startup) if production config is unsafe."""
    errors = production_config_errors()
    if errors:
        raise RuntimeError("Refusing to start in production: " + " ".join(errors))
