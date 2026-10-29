"""The risk score and, above all, the rule that a thin run is never "low"."""
from __future__ import annotations


from app.services.scoring import (
    BAND_HIGH,
    BAND_LOW,
    BAND_MODERATE,
    BAND_UNKNOWN,
    MIN_COVERAGE,
    Coverage,
    band_for,
    coverage_note,
    risk_band,
    risk_score,
)


def test_fraction_is_evaluated_over_total():
    cov = Coverage(total_clauses=10, matched_clauses=8, evaluated_clauses=5, degraded=False)
    assert cov.fraction == 0.5


def test_fraction_is_zero_without_clauses():
    assert Coverage(0, 0, 0, False).fraction == 0.0


def test_severity_weighting_and_missing_penalty():
    flagged = [{"severity": "high"}, {"severity": "low"}]
    assert risk_score(flagged, []) == 25
    assert risk_score([], [{}, {}]) == 16


def test_score_is_capped():
    flagged = [{"severity": "high"}] * 50
    assert risk_score(flagged, []) == 100


def test_bands_by_score_when_coverage_is_good():
    good = Coverage(10, 10, 9, False)
    assert risk_band(0, good) == BAND_LOW
    assert risk_band(20, good) == BAND_MODERATE
    assert risk_band(60, good) == BAND_HIGH


def test_low_coverage_never_reads_as_low_risk():
    thin = Coverage(100, 10, 8, False)
    assert thin.fraction < MIN_COVERAGE
    assert risk_band(0, thin) == BAND_UNKNOWN


def test_degraded_run_is_unknown_even_at_full_coverage():
    degraded = Coverage(10, 10, 10, True)
    assert risk_band(0, degraded) == BAND_UNKNOWN


def test_band_for_matches_risk_band():
    good = Coverage(10, 10, 9, False)
    assert band_for(60, good.fraction, good.degraded) == BAND_HIGH
    assert band_for(0, 0.1, False) == BAND_UNKNOWN
    assert band_for(0, None, False) == BAND_UNKNOWN


def test_coverage_note_reports_percentage():
    note = coverage_note(Coverage(10, 10, 8, False))
    assert "80%" in note


def test_coverage_note_warns_when_thin():
    note = coverage_note(Coverage(10, 2, 1, False))
    assert "cannot call it low risk" in note


def test_boundary_at_min_coverage_is_trustworthy():
    at_threshold = Coverage(100, 100, int(MIN_COVERAGE * 100), False)
    assert risk_band(0, at_threshold) == BAND_LOW
