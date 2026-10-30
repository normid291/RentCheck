"""The `?next=` redirect must never leave the site, and post-auth `next` may
only return someone to the protected app."""
from __future__ import annotations

import pytest

from app.routers.google_auth import _safe_next
from app.services.redirects import safe_app_next_path, safe_next_path

REJECTED = [
    "//evil.com",
    "/\\evil.com",
    "/%5Cevil.com",
    "https://evil.com",
    "http://evil.com/",
    "//evil.com/%2F..",
    "\\\\evil.com",
    "/\tevil.com",
    "javascript:alert(1)",
    "",
    "evil.com",
    "///evil.com",
    "/%5cEVIL.com",
]

ACCEPTED = [
    "/",
    "/history",
    "/profile?tab=security",
    "/analyses/abc-123#top",
    "/dashboard/new",
]

ACCEPTED_APP = [
    "/dashboard",
    "/dashboard/new",
    "/dashboard/history#top",
    "/history",
    "/profile?tab=security",
]

NOT_APP = [
    "/",
    "/analyse",
    "/analyse?sample=1",
    "/login",
    "/signup",
    "/privacy",
    "/terms",
    "/dashboardish",
    "/historyish",
    "/dashboard/../analyse",
]


@pytest.mark.parametrize("value", REJECTED)
def test_rejects_unsafe(value):
    assert safe_next_path(value, "/") == "/"
    assert safe_app_next_path(value) == "/dashboard"
    assert _safe_next(value) == "/dashboard"


@pytest.mark.parametrize("value", ACCEPTED)
def test_accepts_same_origin_paths(value):
    assert safe_next_path(value, "/") == value


@pytest.mark.parametrize("value", ACCEPTED_APP)
def test_app_next_accepts_only_app_routes(value):
    assert safe_app_next_path(value) == value
    assert _safe_next(value) == value


@pytest.mark.parametrize("value", NOT_APP)
def test_app_next_rejects_public_or_lookalike_routes(value):
    assert safe_app_next_path(value) == "/dashboard"
    assert _safe_next(value) == "/dashboard"


def test_missing_value_uses_fallback():
    assert safe_next_path(None, "/fallback") == "/fallback"
    assert safe_next_path("", "/fallback") == "/fallback"
    assert safe_app_next_path(None) == "/dashboard"
    assert safe_app_next_path(None, "/history") == "/history"
    assert _safe_next(None) == "/dashboard"
