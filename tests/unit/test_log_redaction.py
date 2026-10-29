"""The redaction backstop: no email, code, or token survives a log call."""
from __future__ import annotations

import logging

from app.logging_config import RedactionFilter, redact_text


def test_email_is_redacted():
    out = redact_text("signup for someone@example.com failed")
    assert "someone@example.com" not in out
    assert "<email>" in out


def test_labelled_code_is_redacted():
    out = redact_text("verification code 483920 was consumed")
    assert "483920" not in out
    assert "<code>" in out


def test_long_opaque_token_is_redacted():
    token = "A" * 40
    out = redact_text(f"token={token}")
    assert token not in out


def test_unlabelled_number_is_left_alone():
    # Latency-style numbers must remain useful.
    assert "1200" in redact_text("took 1200 ms")


def test_filter_scrubs_a_record(caplog):
    logger = logging.getLogger("tenura.test.redaction")
    logger.addFilter(RedactionFilter())
    with caplog.at_level(logging.INFO):
        logger.info("user %s asked for a code", "bob@example.com")
    assert "bob@example.com" not in caplog.text
    assert "<email>" in caplog.text
