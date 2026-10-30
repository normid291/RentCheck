"""Owner-only access rules for the private admin dashboard.

The allowlist is read from `ADMIN_EMAILS` on every check. It is comma-separated,
case-insensitive, and deliberately fails closed: an unset or empty value denies
everyone. An admin must also have a signed-in session and a verified email, so
an unverified account that somehow used an allowlisted address still gets a 404.
"""
from __future__ import annotations

import os

from app.models.db import User


def admin_emails() -> frozenset[str]:
    """The configured allowlist. Empty means nobody is an admin."""
    raw = os.environ.get("ADMIN_EMAILS") or ""
    return frozenset(
        value.strip().lower()
        for value in raw.split(",")
        if value.strip()
    )


def is_admin(user: User | None) -> bool:
    """True only for a verified signed-in user on the server-side allowlist."""
    if user is None or not user.is_verified:
        return False
    allowed = admin_emails()
    if not allowed:
        return False
    return (user.email or "").strip().lower() in allowed
