"""The `?next=` redirect must never leave the site."""
from __future__ import annotations

import pytest

from app.routers.google_auth import _safe_next
from app.services.redirects import safe_next_path

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
]


@pytest.mark.parametrize("value", REJECTED)
def test_rejects_unsafe(value):
    assert safe_next_path(value, "/") == "/"
    assert _safe_next(value) == "/"


@pytest.mark.parametrize("value", ACCEPTED)
def test_accepts_same_origin_paths(value):
    assert safe_next_path(value, "/") == value
    assert _safe_next(value) == value


def test_missing_value_uses_fallback():
    assert safe_next_path(None, "/fallback") == "/fallback"
    assert safe_next_path("", "/fallback") == "/fallback"
    assert _safe_next(None) == "/"
