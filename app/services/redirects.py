"""Same-origin redirect validation, shared by every `?next=` hop.

A "next" parameter is attacker-controllable: it arrives in a link a victim
clicks. The only safe values are paths that stay on this site, so the rule is:

  - must be a path beginning with a single "/" (never "//", which a browser
    reads as a protocol-relative absolute URL)
  - no backslashes, raw or percent-encoded ("/\\evil.com" and "/%5Cevil.com"
    are both treated as "//evil.com" by browsers)
  - no control characters (header/CRLF smuggling, and magic URL handling)
  - parsed with urlsplit and rejected if it carries a scheme or a netloc

Anything that fails returns the fallback. The same rule is mirrored in
app/static/common.js so the client cannot be tricked into a cross-origin
redirect either; keep the two in step.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_BACKSLASH = re.compile(r"\\|%5c", re.IGNORECASE)


def safe_next_path(value: str | None, fallback: str = "/") -> str:
    """Return `value` if it is a safe same-origin path, else `fallback`."""
    if not value:
        return fallback

    candidate = value.strip()
    if not candidate:
        return fallback

    if _CONTROL_CHARS.search(candidate):
        return fallback
    if _BACKSLASH.search(candidate):
        return fallback
    if not candidate.startswith("/") or candidate.startswith("//"):
        return fallback

    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        return fallback

    return candidate
