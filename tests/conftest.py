"""Shared pytest fixtures.

The legacy script-style suites (test_accounts.py, test_google_signin.py,
test_document_type.py) run at import time and need a live database + live AI, so
pytest must not collect them. They stay runnable as `python tests/<file>.py` and
as the optional end-to-end CI job.
"""
from __future__ import annotations

import os
import re
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Files that run code at import: keep them out of the pytest run.
collect_ignore_glob = [
    "test_accounts.py",
    "test_google_signin.py",
    "test_document_type.py",
]

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real")


def fixture_text(name: str) -> str:
    """Read a real fixture file by name."""
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture
def ng_agreement() -> str:
    return fixture_text("ng_deed_text.txt")


def _db_available() -> bool:
    try:
        from sqlalchemy import text

        from app.database import engine

        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="no database reachable at DATABASE_URL"
)


@pytest.fixture
def captured_email(monkeypatch):
    """Stub outbound email and return the list it captures."""
    from app.services import email as email_service

    sent: list[dict] = []
    monkeypatch.setattr(
        email_service,
        "send_email",
        lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}),
    )
    return sent


@pytest.fixture
def client(monkeypatch, captured_email):
    """A TestClient with email and the per-clause AI call stubbed.

    Classification is also stubbed to a confident Nigerian verdict so the
    jurisdiction gate does not send every test through the model. Tests that
    care about jurisdiction override this themselves.
    """
    from app.routers import agreements as agreements_router
    from app.services.document_classifier import TENANCY_AGREEMENT
    from app.services.ratelimit import limiter

    limiter.clear()

    def _ng_tenancy(text, source_type):
        return {
            "document_type": TENANCY_AGREEMENT,
            "confidence": 0.95,
            "reason": "",
            "jurisdiction": "NG-LA",
            "jurisdiction_confidence": 0.95,
            "jurisdiction_evidence": ["lagos"],
        }

    def _fake_analyze(clause_text, reference):
        if reference.clause_type == "re_entry_forfeiture":
            return {
                "flag": True,
                "clause_type": "re_entry_forfeiture",
                "severity": "high",
                "reason": "Re-entry without a demand.",
                "evidence": " ".join(clause_text.split())[:70],
                "source": "ai",
                "clause": clause_text,
                "verified": True,
            }
        return {"flag": False, "clause_type": reference.clause_type, "source": "ai"}

    monkeypatch.setattr(agreements_router, "classify_document", _ng_tenancy)
    monkeypatch.setattr(agreements_router, "analyze_clause", _fake_analyze)

    from fastapi.testclient import TestClient

    from app.main import app

    tc = TestClient(app, base_url="https://testserver")
    tc.sent = captured_email  # type: ignore[attr-defined]
    yield tc


@pytest.fixture
def make_user(client):
    """Create + verify an account via the API and return (client, email, password)."""
    password = "correct-horse-battery"
    created: list[str] = []

    def _make() -> str:
        email = f"pytest-{uuid.uuid4().hex[:10]}@example.com"
        resp = client.post("/api/auth/signup", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        body = client.sent[-1]["body"]
        code = re.search(r"\b(\d{6})\b", body).group(1)
        verified = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
        assert verified.status_code == 200, verified.text
        created.append(email)
        return email

    yield _make

    # Cleanup: delete any accounts this fixture created, cascade included.
    try:
        from app.database import SessionLocal
        from app.models.db import Analysis, Agreement, OtpCode, User

        db = SessionLocal()
        try:
            for address in created:
                user = db.query(User).filter(User.email == address).first()
                if not user:
                    continue
                for analysis in db.query(Analysis).filter(Analysis.user_id == user.id).all():
                    agreement = db.get(Agreement, analysis.agreement_id)
                    db.delete(analysis)
                    if agreement is not None:
                        db.delete(agreement)
                db.query(OtpCode).filter(OtpCode.user_id == user.id).delete()
                db.delete(user)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass
