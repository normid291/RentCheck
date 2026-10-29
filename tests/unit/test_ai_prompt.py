"""Prompt grounding, injection resistance, and evidence-or-drop in the judge."""
from __future__ import annotations

from app.services import ai_inference
from app.services.clause_matcher import ClauseNorm


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def make_norm(jurisdiction: str = "NG-LA", legal_basis: str = "market_norm") -> ClauseNorm:
    return ClauseNorm(
        clause_type="caution_fee",
        jurisdiction=jurisdiction,
        norm_description="Caution fees are normally refundable minus damage.",
        red_flag_pattern="A non-refundable caution fee.",
        severity_default="medium",
        keywords=("caution fee",),
        legal_basis=legal_basis,
        applies_to=("tenant",),
        consequence="",
        counter_clause="",
        tenant_question="",
        version="1",
    )


def test_prompt_carries_jurisdiction_and_delimiters(monkeypatch):
    captured: dict = {}

    def fake_post(url, payload):
        captured["payload"] = payload
        return _FakeResponse('{"flag": false, "severity": "low", "evidence": "", "reason": "ok"}')

    monkeypatch.setattr(ai_inference, "_post_with_retries", fake_post)
    ai_inference.analyze_clause("The Tenant shall pay a caution fee.", make_norm())

    prompt = captured["payload"]["messages"][0]["content"]
    assert "<<<CLAUSE>>>" in prompt and "<<<END CLAUSE>>>" in prompt
    assert "NG-LA" in prompt
    assert "common practice" in prompt
    assert "ignore" in prompt.lower()  # the anti-injection rule is present


def test_static_basis_is_named_as_law(monkeypatch):
    captured: dict = {}

    def fake_post(url, payload):
        captured["payload"] = payload
        return _FakeResponse('{"flag": false, "severity": "low", "evidence": "", "reason": "ok"}')

    monkeypatch.setattr(ai_inference, "_post_with_retries", fake_post)
    ai_inference.analyze_clause("clause", make_norm(legal_basis="statute"))
    assert "Nigerian law" in captured["payload"]["messages"][0]["content"]


def test_unsupported_flag_is_dropped(monkeypatch):
    # The model claims a problem but quotes words that are NOT in the clause.
    monkeypatch.setattr(
        ai_inference,
        "_post_with_retries",
        lambda url, payload: _FakeResponse(
            '{"flag": true, "severity": "high", "evidence": "the landlord may keep everything", "reason": "bad"}'
        ),
    )
    result = ai_inference.analyze_clause("The Tenant shall pay a caution fee.", make_norm())
    assert result["flag"] is False
    assert result["evaluated"] is True


def test_verified_flag_keeps_offsets(monkeypatch):
    clause = "The Tenant shall pay a non-refundable caution fee of 50%."
    monkeypatch.setattr(
        ai_inference,
        "_post_with_retries",
        lambda url, payload: _FakeResponse(
            '{"flag": true, "severity": "high", "evidence": "non-refundable caution fee", "reason": "not refundable"}'
        ),
    )
    result = ai_inference.analyze_clause(clause, make_norm())
    assert result["flag"] is True
    assert result["evidence_start"] is not None
    assert clause[result["evidence_start"] : result["evidence_end"]] == "non-refundable caution fee"


def test_bad_severity_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(
        ai_inference,
        "_post_with_retries",
        lambda url, payload: _FakeResponse(
            '{"flag": true, "severity": "banana", "evidence": "non-refundable caution fee", "reason": "x"}'
        ),
    )
    result = ai_inference.analyze_clause(
        "The Tenant shall pay a non-refundable caution fee.", make_norm()
    )
    assert result["severity"] == "medium"


def test_unparseable_answer_is_unevaluated_not_a_flag(monkeypatch):
    monkeypatch.setattr(
        ai_inference, "_post_with_retries", lambda url, payload: _FakeResponse("sorry, no json")
    )
    result = ai_inference.analyze_clause("The Tenant shall pay a caution fee.", make_norm())
    assert result["flag"] is False
    assert result["evaluated"] is False
