"""Logging setup with a PII redaction backstop.

Two things work together:

1. The code that logs is careful: agreement text, clause text, evidence quotes,
   emails, OTP codes and tokens are simply not logged.
2. This filter is the backstop for the human who forgets. Even if one of those
   values reaches a `logger.info("... %s", value)`, the message is scrubbed
   before it leaves the process.

The filter only ever removes text, never adds it, so it cannot itself leak.
"""
from __future__ import annotations

import logging
import re

# An email address, e.g. someone@example.com
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# A code that is explicitly labelled ("code 123456", "code: 123456").
_LABELLED_CODE = re.compile(r"(?i)\b(code\b[^0-9]{0,12})(\d{6})\b")
# A long opaque run: session tokens, API keys, hashes.
_OPAQUE = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")


def redact_text(message: str) -> str:
    """Remove emails, labelled one-time codes, and long opaque tokens."""
    if not message:
        return message
    text = _EMAIL.sub("<email>", message)
    text = _LABELLED_CODE.sub(r"\1<code>", text)
    text = _OPAQUE.sub("<redacted>", text)
    return text


class RedactionFilter(logging.Filter):
    """Scrub each record's message (and string args) before it is formatted."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(str(record.msg))
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        key: redact_text(value) if isinstance(value, str) else value
                        for key, value in record.args.items()
                    }
                else:
                    record.args = tuple(
                        redact_text(arg) if isinstance(arg, str) else arg
                        for arg in record.args
                    )
        except Exception:  # a logging filter must never raise
            pass
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Install one stderr handler with the redaction filter, once."""
    root = logging.getLogger()
    if getattr(root, "_tenura_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.addFilter(RedactionFilter())

    root.handlers = [handler]
    root.setLevel(level)
    root._tenura_configured = True  # type: ignore[attr-defined]
