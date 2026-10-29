"""Turn clause results into an honest risk score and coverage figure.

Two rules drive everything here:

1. Deterministic always. The score is a weighted count of verified flags and
   missing protections — never a number the model produces, so it cannot
   overstate.
2. Never fake certainty. When coverage is low (most clauses were never checked,
   or the model failed on the ones that were), the run must NOT be presented as
   "low risk". It is reported as "unknown", with the coverage shown, so the user
   understands what was and was not reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass

# A run below this fraction of evaluated clauses is not trusted for a "low"
# band, and is flagged as degraded for the UI.
MIN_COVERAGE = 0.6

_SEVERITY_WEIGHT = {"low": 5, "medium": 12, "high": 20}
_MISSING_WEIGHT = 8

BAND_LOW = "low"
BAND_MODERATE = "moderate"
BAND_HIGH = "high"
BAND_UNKNOWN = "unknown"


@dataclass(frozen=True)
class Coverage:
    total_clauses: int
    matched_clauses: int
    evaluated_clauses: int
    degraded: bool

    @property
    def fraction(self) -> float:
        """Share of ALL clauses in the document that got a real verdict."""
        if self.total_clauses <= 0:
            return 0.0
        return round(self.evaluated_clauses / self.total_clauses, 2)

    @property
    def trustworthy(self) -> bool:
        return self.fraction >= MIN_COVERAGE and not self.degraded


def risk_score(flagged: list, missing: list) -> int:
    """Severity-weighted score, capped at 100."""
    points = 0
    for flag in flagged:
        severity = str(flag.get("severity", "medium")).lower()
        points += _SEVERITY_WEIGHT.get(severity, _SEVERITY_WEIGHT["medium"])
    points += _MISSING_WEIGHT * len(missing)
    return min(100, points)


def risk_band(score: int, coverage: Coverage) -> str:
    """Map a score to a band, refusing to say "low" without the coverage."""
    return band_for(score, coverage.fraction, coverage.degraded)


def band_for(score: int, coverage_fraction: float | None, degraded: bool) -> str:
    """Same mapping, from the stored/coverage fields (history and reports)."""
    trustworthy = (
        coverage_fraction is not None
        and coverage_fraction >= MIN_COVERAGE
        and not degraded
    )
    if not trustworthy:
        return BAND_UNKNOWN
    if score >= 40:
        return BAND_HIGH
    if score >= 15:
        return BAND_MODERATE
    return BAND_LOW


BAND_LABELS = {
    BAND_LOW: "Low risk",
    BAND_MODERATE: "Moderate risk",
    BAND_HIGH: "High risk",
    BAND_UNKNOWN: "Review needed",
}


def band_label(band: str) -> str:
    return BAND_LABELS.get(band, BAND_LABELS[BAND_UNKNOWN])


def coverage_note(coverage: Coverage) -> str:
    """A short, plain-language sentence for the coverage banner."""
    pct = round(coverage.fraction * 100)
    if not coverage.trustworthy:
        reason = (
            "the automated check could not evaluate enough of the clauses"
            if coverage.degraded
            else "many clauses did not match a norm we can check"
        )
        return (
            f"We could only review about {pct}% of this agreement because "
            f"{reason}, so we cannot call it low risk. Read the clauses we could "
            "not check yourself, or ask a lawyer."
        )
    return f"We reviewed about {pct}% of this agreement."
