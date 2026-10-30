"""The admin allowlist must be server-side and fail closed."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import admin_access
from app.services.auth import require_admin


def user(email: str, verified: bool = True):
    return SimpleNamespace(email=email, is_verified=verified)


def test_unset_allowlist_denies_everyone(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    assert admin_access.is_admin(user("owner@example.com")) is False


def test_empty_or_comma_only_allowlist_denies_everyone(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", " , , ")
    assert admin_access.is_admin(user("owner@example.com")) is False


def test_allowlisted_verified_user_is_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "other@example.com, Owner@Example.com")
    assert admin_access.is_admin(user("owner@example.com")) is True


def test_unverified_allowlisted_user_is_not_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.com")
    assert admin_access.is_admin(user("owner@example.com", verified=False)) is False


def test_non_allowlisted_user_is_not_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.com")
    assert admin_access.is_admin(user("member@example.com")) is False


def test_require_admin_returns_404_for_non_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.com")
    with pytest.raises(HTTPException) as caught:
        require_admin(user("member@example.com"))
    assert caught.value.status_code == 404


def test_require_admin_returns_404_for_logged_out(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.com")
    with pytest.raises(HTTPException) as caught:
        require_admin(None)
    assert caught.value.status_code == 404
