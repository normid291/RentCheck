"""Record privacy-safe analysis metadata for the owner dashboard.

The event is written in its own short-lived session AFTER the user's analysis
has finished, and every failure is swallowed. A logging outage must never turn a
successful analysis into an error or roll back a saved result.

Never add document text, clause content, model output, email addresses, titles,
or filenames to this table. The fields here are deliberately account and timing
metadata only.
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.database import SessionLocal
from app.models.db import AiRunEvent

logger = logging.getLogger("tenura.ai_events")

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_REJECTED_NON_NIGERIAN = "rejected_non_nigerian"
STATUS_RATE_LIMITED = "rate_limited"

SOURCES = frozenset({"paste", "upload", "sample"})


def normalise_source(value: str | None, default: str = "paste") -> str:
    """Only the three public source labels are stored."""
    candidate = (value or "").strip().lower()
    return candidate if candidate in SOURCES else default


def record_run(
    *,
    user_id,
    is_guest: bool,
    source: str,
    status: str,
    duration_ms: int | None = None,
    model_name: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_code: str | None = None,
) -> None:
    """Best-effort insert. Callers must never depend on this succeeding."""
    db = None
    try:
        db = SessionLocal()
        db.add(
            AiRunEvent(
                created_at=datetime.utcnow(),
                user_id=user_id,
                is_guest=bool(is_guest),
                source=normalise_source(source),
                status=status,
                duration_ms=duration_ms,
                model_name=(model_name or None),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_code=(error_code or None),
            )
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - logging must never break analysis
        if db is not None:
            db.rollback()
        # Type only: messages could contain values from a failed statement.
        logger.warning("Could not record AI run event (%s)", type(exc).__name__)
    finally:
        if db is not None:
            db.close()
