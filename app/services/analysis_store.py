"""Saving, listing, renaming and deleting a user's analyses.

Everything here takes the owning `User` and filters by `user_id`, so a caller
cannot reach another account's records even by guessing an id: the ownership
check is part of the query, not a separate step someone can forget. Lookups that
do not match return None, which the router turns into a 404 — so asking for
someone else's analysis is indistinguishable from asking for one that does not
exist.

Deleting is deliberately thorough: the analysis AND its agreement text go, in one
transaction, so "delete" really means the document is gone.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.db import Agreement, Analysis, SourceType, User
from app.services.scoring import band_for, band_label

# Legacy score thresholds, kept for callers that only have a score. New code
# should go through scoring.band_for, which refuses to call a low-coverage run
# "low risk".
RISK_HIGH = 55
RISK_MEDIUM = 25

TITLE_MAX = 80
PREVIEW_CHARS = 400


def risk_level(score: int) -> tuple[str, str]:
    """(key, human label) for a risk score, ignoring coverage."""
    if score >= RISK_HIGH:
        return "high", "High risk"
    if score >= RISK_MEDIUM:
        return "medium", "Moderate risk"
    return "low", "Low risk"


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    word = singular if n == 1 else (plural or singular + "s")
    return f"{n} {word}"


def build_title(text: str) -> str:
    """A short label from the first meaningful line of the agreement.

    Skips headings that are only page furniture (short lines, digits, symbols) so
    a letterhead like "1." or "TENANCY AGREEMENT ... page 2" does not become the
    title.
    """
    for raw in (text or "").splitlines():
        line = " ".join(raw.split()).strip(" \t.-–—:;,|/\\")
        if len(line) < 3:
            continue
        if not any(ch.isalpha() for ch in line):
            continue
        return line if len(line) <= TITLE_MAX else line[: TITLE_MAX - 1].rstrip() + "…"
    return "Untitled agreement"


def build_recommendation(
    risk_score: int,
    flagged: list,
    missing: list,
    band: str | None = None,
) -> str:
    """The one-line "what should I do" shown in the history list.

    Built from the counts, never from the model, so it cannot overstate the
    result. Deliberately practical rather than a legal opinion. `band` comes from
    scoring.band_for; when it is "unknown" (low coverage or a degraded run) the
    line says so rather than pretending the agreement is low risk.
    """
    if band is None:
        band = {"high": "high", "medium": "moderate", "low": "low"}[
            risk_level(risk_score)[0]
        ]
    n_flagged = len(flagged or [])
    n_missing = len(missing or [])

    if band == "unknown":
        return (
            "Not enough of this agreement could be checked automatically to "
            "give it a risk rating. Read the unchecked clauses yourself, or ask "
            "a lawyer before you sign."
        )
    if band == "high":
        return (
            f"High risk — {_plural(n_flagged, 'flagged clause')} and "
            f"{_plural(n_missing, 'missing protection')}. "
            "Have a lawyer look at this before you sign."
        )
    if band == "moderate":
        return (
            f"Moderate risk — {_plural(n_flagged, 'flagged clause')}, "
            f"{_plural(n_missing, 'missing protection')}. "
            "Worth clarifying with your landlord before you sign."
        )
    if n_missing:
        return (
            "Low risk — nothing serious found. "
            f"{_plural(n_missing, 'protection')} still worth asking about."
        )
    return "Low risk — nothing serious found."


def persist(
    db: Session,
    user: User,
    *,
    text: str,
    source_type: SourceType,
    flagged_clauses: list,
    missing_protections: list,
    questions_to_ask: list,
    risk_score: int,
    summary_text: str,
    jurisdiction: str | None = None,
    coverage: float | None = None,
    degraded: bool = False,
    pipeline_version: str | None = None,
    prompt_version: str | None = None,
    model_id: str | None = None,
    clause_reference_version: str | None = None,
) -> Analysis:
    """Store one analysis (and the text it came from) for `user`.

    The agreement row is written only here, at the end of a successful run, so an
    analysis that fails part-way leaves no orphaned text behind.
    """
    band = band_for(risk_score, coverage, degraded)
    agreement = Agreement(source_type=source_type, raw_text=text)
    db.add(agreement)
    db.flush()  # assign agreement.id without committing the pair separately

    analysis = Analysis(
        agreement_id=agreement.id,
        user_id=user.id,
        title=build_title(text),
        flagged_clauses=flagged_clauses,
        missing_protections=missing_protections,
        questions_to_ask=questions_to_ask,
        risk_score=risk_score,
        summary_text=summary_text,
        recommendation=build_recommendation(
            risk_score, flagged_clauses, missing_protections, band
        ),
        jurisdiction=jurisdiction,
        coverage=coverage,
        degraded=degraded,
        pipeline_version=pipeline_version,
        prompt_version=prompt_version,
        model_id=model_id,
        clause_reference_version=clause_reference_version,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def _owned_query(db: Session, user: User):
    return db.query(Analysis).filter(Analysis.user_id == user.id)


def list_for_user(db: Session, user: User, limit: int = 100) -> list[dict]:
    """Summaries for the history list, newest first."""
    rows = (
        _owned_query(db, user)
        .order_by(Analysis.created_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [summary_of(a) for a in rows]


def summary_of(analysis: Analysis) -> dict:
    flagged = analysis.flagged_clauses or []
    missing = analysis.missing_protections or []
    score = analysis.risk_score or 0
    band = band_for(score, analysis.coverage, bool(analysis.degraded))
    return {
        "id": str(analysis.id),
        "title": analysis.title or "Untitled agreement",
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "risk_score": score,
        "risk_level": band,
        "risk_label": band_label(band),
        "jurisdiction": analysis.jurisdiction,
        "coverage": analysis.coverage,
        "degraded": bool(analysis.degraded),
        "flagged_count": len(flagged),
        "missing_count": len(missing),
        "recommendation": analysis.recommendation
        or build_recommendation(score, flagged, missing, band),
    }


def get_owned(db: Session, user: User, analysis_id) -> Analysis | None:
    try:
        aid = analysis_id if isinstance(analysis_id, uuid.UUID) else uuid.UUID(str(analysis_id))
    except (ValueError, TypeError, AttributeError):
        return None
    return _owned_query(db, user).filter(Analysis.id == aid).one_or_none()


def detail_of(analysis: Analysis) -> dict:
    """The full saved analysis.

    Returns a capped preview of the agreement rather than the whole text: the
    flagged clauses already quote the parts that matter, and there is no reason
    to push the entire document back over the wire on every open.
    """
    data = summary_of(analysis)
    text = ""
    if analysis.agreement is not None:
        text = analysis.agreement.raw_text or ""

    data.update(
        {
            "flagged_clauses": analysis.flagged_clauses or [],
            "missing_protections": analysis.missing_protections or [],
            "questions_to_ask": analysis.questions_to_ask or [],
            "summary": analysis.summary_text or "",
            "agreement_preview": text[:PREVIEW_CHARS],
            "agreement_truncated": len(text) > PREVIEW_CHARS,
        }
    )
    return data


def rename(db: Session, user: User, analysis_id, title: str) -> Analysis | None:
    analysis = get_owned(db, user, analysis_id)
    if analysis is None:
        return None
    cleaned = " ".join((title or "").split())
    analysis.title = (cleaned[:120].rstrip() or "Untitled agreement")
    db.commit()
    db.refresh(analysis)
    return analysis


def delete(db: Session, user: User, analysis_id) -> bool:
    """Delete an analysis and, permanently, the agreement text behind it."""
    analysis = get_owned(db, user, analysis_id)
    if analysis is None:
        return False

    agreement_id = analysis.agreement_id
    db.delete(analysis)
    db.flush()

    # Only remove the text once nothing else points at it. In practice there is
    # one analysis per agreement, but this keeps the cleanup honest if that ever
    # changes.
    remaining = (
        db.query(Analysis).filter(Analysis.agreement_id == agreement_id).count()
    )
    if remaining == 0:
        agreement = db.get(Agreement, agreement_id)
        if agreement is not None:
            db.delete(agreement)

    db.commit()
    return True
