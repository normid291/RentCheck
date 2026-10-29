"""The jurisdiction gate: a foreign agreement is refused, an unknown one asks.

These tests stub the classifier (its own logic is unit-tested in
tests/unit/test_jurisdiction.py) so they exercise the PIPELINE's decision:
what happens to a document once its jurisdiction is known.
"""
from __future__ import annotations

from conftest import requires_db

pytestmark = requires_db

NG_TEXT = (
    "TENANCY AGREEMENT\n\n"
    "This tenancy is made under the Lagos State Tenancy Law. The yearly rent is "
    "₦2,500,000 payable in advance. A caution fee of 10% is required. The Tenant "
    "shall give the Landlord one month quit notice."
)


def _verdict(jurisdiction: str, confidence: float = 0.9) -> dict:
    from app.services.document_classifier import TENANCY_AGREEMENT

    return {
        "document_type": TENANCY_AGREEMENT,
        "confidence": 0.95,
        "reason": "",
        "jurisdiction": jurisdiction,
        "jurisdiction_confidence": confidence,
        "jurisdiction_evidence": [],
        "jurisdiction_source": "text",
    }


def _stub_classifier(monkeypatch, jurisdiction: str):
    from app.routers import agreements as agreements_router

    monkeypatch.setattr(
        agreements_router, "classify_document", lambda text, source_type: _verdict(jurisdiction)
    )


def test_non_nigerian_is_out_of_scope_and_not_saved(client, make_user, monkeypatch):
    make_user()  # authenticated, so a saved run WOULD show up in history
    _stub_classifier(monkeypatch, "NON_NG")

    response = client.post("/api/agreements/analyze", json={"text": NG_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "out_of_scope"
    assert body["jurisdiction"] == "NON_NG"
    assert body["flagged_clauses"] == []
    assert body["saved"] is False
    assert body["analysis_id"] is None

    history = client.get("/api/analyses").json()
    assert history["analyses"] == []


def test_unknown_jurisdiction_asks_and_is_not_saved(client, make_user, monkeypatch):
    make_user()
    _stub_classifier(monkeypatch, "UNKNOWN")

    response = client.post("/api/agreements/analyze", json={"text": NG_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_jurisdiction"
    assert body["saved"] is False

    history = client.get("/api/analyses").json()
    assert history["analyses"] == []


def test_nigerian_agreement_is_judged_and_carries_coverage(client, make_user, monkeypatch):
    make_user()
    _stub_classifier(monkeypatch, "NG-LA")

    response = client.post("/api/agreements/analyze", json={"text": NG_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["jurisdiction"] == "NG-LA"
    assert body["saved"] is True
    assert 0.0 <= body["coverage"] <= 1.0
    assert body["risk_band"] in {"low", "moderate", "high", "unknown"}
    assert body["coverage_note"]


def test_thin_run_is_never_low_risk(client, monkeypatch):
    _stub_classifier(monkeypatch, "NG-LA")
    # A tenancy agreement with no clauses our norms recognise: coverage is zero.
    thin = (
        "TENANCY AGREEMENT between the parties concerning a house in Lagos, "
        "on terms to be agreed from time to time."
    )
    response = client.post("/api/agreements/analyze", json={"text": thin})
    body = response.json()
    assert body["status"] == "ok"
    assert body["coverage"] < 0.6
    # Even though missing protections push the raw score up, a run that checked
    # almost nothing must not present as a confident band.
    assert body["risk_band"] == "unknown"


def test_fair_landlord_repair_clause_is_not_flagged(client, monkeypatch):
    _stub_classifier(monkeypatch, "NG-LA")
    text = (
        "TENANCY AGREEMENT\n\n"
        "The Landlord shall be responsible for structural repairs to the "
        "premises, and the Tenant shall keep the interior in good repair."
    )
    body = client.post("/api/agreements/analyze", json={"text": text}).json()
    assert body["status"] == "ok"
    repair_flags = [
        f for f in body["flagged_clauses"] if f.get("clause_type") == "repair_responsibility"
    ]
    assert repair_flags == []
