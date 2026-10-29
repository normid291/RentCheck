"""Production startup guards: refuse to run with an unsafe configuration."""
from __future__ import annotations

import pytest

from app import config
from app.services import email as email_service


def test_no_errors_in_development():
    assert config.production_config_errors() == []


def test_short_or_missing_secret_is_refused(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    errors = config.production_config_errors()
    assert any("SESSION_SECRET" in e for e in errors)

    monkeypatch.setenv("SESSION_SECRET", "too-short")
    errors = config.production_config_errors()
    assert any("SESSION_SECRET" in e for e in errors)


def test_unconfigured_email_is_refused(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setenv("SESSION_SECRET", "x" * 48)
    monkeypatch.setattr(email_service, "provider_name", lambda: "unconfigured")
    errors = config.production_config_errors()
    assert any("Email" in e for e in errors)

    # console is a dev-only provider and is refused in production too.
    monkeypatch.setattr(email_service, "provider_name", lambda: "console")
    assert any("Email" in e for e in config.production_config_errors())


def test_require_raises_and_passes(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        config.require_production_config()

    monkeypatch.setenv("SESSION_SECRET", "x" * 48)
    monkeypatch.setattr(email_service, "provider_name", lambda: "resend")
    config.require_production_config()  # must not raise
