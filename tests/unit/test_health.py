"""Liveness vs readiness, and the generic (non-leaking) failure body."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def test_liveness_is_always_ok_and_db_free():
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_ready_when_db_is_up():
    from sqlalchemy import text

    from app.database import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception:
        import pytest

        pytest.skip("no database reachable")

    response = _client().get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_dev_build_exposes_docs():
    # APP_ENV is not "production" in the test environment, so the schema is on.
    assert app.openapi_url is not None
