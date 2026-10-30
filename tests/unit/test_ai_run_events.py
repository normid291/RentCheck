"""Run-event logging is metadata-only and never breaks the analysis."""
from __future__ import annotations

import pytest

from app.models.db import AiRunEvent, SourceType
from app.routers import agreements
from app.services import ai_run_events


def test_event_model_has_no_document_or_output_columns():
    columns = set(AiRunEvent.__table__.columns.keys())
    forbidden = {
        "text",
        "raw_text",
        "content",
        "clause",
        "clauses",
        "title",
        "summary",
        "output",
        "flagged_clauses",
        "missing_protections",
        "questions_to_ask",
        "agreement_id",
    }
    assert not (columns & forbidden)


def test_source_is_restricted_to_known_labels():
    assert ai_run_events.normalise_source("sample") == "sample"
    assert ai_run_events.normalise_source("UPLOAD") == "upload"
    assert ai_run_events.normalise_source("something-else") == "paste"
    assert ai_run_events.normalise_source("something-else", default="upload") == "upload"


def test_record_run_swallows_session_failure(monkeypatch):
    def boom():
        raise RuntimeError("database is down")

    monkeypatch.setattr(ai_run_events, "SessionLocal", boom)
    # Must not raise: the caller is in the analysis request path.
    ai_run_events.record_run(
        user_id=None,
        is_guest=True,
        source="paste",
        status="success",
        duration_ms=10,
    )


def test_pipeline_result_survives_logging_failure(monkeypatch):
    def fake_core(text, source_type, db, user):
        return {"status": "ok", "saved": False, "analysis_id": None}

    def boom(**kwargs):
        raise RuntimeError("telemetry failed")

    monkeypatch.setattr(agreements, "_run_pipeline_core", fake_core)
    monkeypatch.setattr(agreements.ai_run_events, "record_run", boom)

    result = agreements._run_pipeline("text", SourceType.text, None, None, "sample")
    assert result["status"] == "ok"


def test_unreadable_upload_is_recorded_as_a_failed_run(monkeypatch):
    calls = []
    monkeypatch.setattr(
        agreements.ai_run_events, "record_run", lambda **kwargs: calls.append(kwargs)
    )

    agreements._record_upload_failure(None, "unreadable")

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["error_code"] == "unreadable"
    assert calls[0]["source"] == "upload"
    assert calls[0]["is_guest"] is True


def test_pipeline_failure_is_reraised_after_logging(monkeypatch):
    calls = []

    def fake_core(text, source_type, db, user):
        raise ValueError("model blew up")

    def capture(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(agreements, "_run_pipeline_core", fake_core)
    monkeypatch.setattr(agreements.ai_run_events, "record_run", capture)

    with pytest.raises(ValueError):
        agreements._run_pipeline("text", SourceType.text, None, None, "paste")

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["error_code"] == "ValueError"
    assert calls[0]["source"] == "paste"
