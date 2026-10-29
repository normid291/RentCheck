"""Evidence-or-drop: a flag must quote the clause, and we can point at where."""
from __future__ import annotations

from app.services.ai_inference import locate_evidence, verify_evidence

CLAUSE = (
    "The Tenant shall pay a caution fee of 50% of the annual rent, "
    "which shall be non-refundable under any circumstance."
)


def test_exact_quote_verifies():
    assert verify_evidence(CLAUSE, "50% of the annual rent") is True


def test_case_and_punctuation_differences_still_verify():
    assert verify_evidence(CLAUSE, "NON REFUNDABLE UNDER ANY CIRCUMSTANCE") is True


def test_invented_quote_is_rejected():
    assert verify_evidence(CLAUSE, "the landlord may keep the entire deposit") is False


def test_blank_placeholder_is_rejected():
    clause = "The Tenant shall pay the sum of N.............. annually."
    assert verify_evidence(clause, "N..............") is False


def test_too_short_quote_is_rejected():
    assert verify_evidence(CLAUSE, "the") is False


def test_accents_do_not_break_verification():
    clause = "Le loyer est de 900 € par mois, payable d'avance."
    # The euro sign and accented text are normalised consistently on both sides.
    assert verify_evidence(clause, "900 € par mois") is True


def test_locate_evidence_returns_the_span():
    span = locate_evidence(CLAUSE, "non-refundable under any circumstance")
    assert span is not None
    start, end = span
    assert "non-refundable under any circumstance" in CLAUSE[start:end]


def test_locate_evidence_tolerates_case_and_punctuation():
    span = locate_evidence(CLAUSE, "non refundable under any circumstance")
    assert span is not None


def test_locate_evidence_none_when_absent():
    assert locate_evidence(CLAUSE, "monthly payment in bitcoin") is None


def test_locate_evidence_none_for_empty():
    assert locate_evidence(CLAUSE, "") is None
