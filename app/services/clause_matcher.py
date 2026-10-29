"""Match one clause to the closest known norm, within a jurisdiction.

Why not embeddings
    The corpus is tiny (a few dozen curated norms) and every match has to be
    explainable to a renter and cheap enough to run on every clause. A
    deterministic token-overlap score with a minimum-score AND a margin over the
    runner-up is enough, and it can say *why* it matched. It is deliberately
    conservative: when two norms score alike, it returns nothing rather than
    guessing, so a clause is never judged against the wrong norm.

Jurisdiction is an input, not an afterthought. A document accepted as Nigerian
is matched against its own jurisdiction pack plus the generic "NG" pack; a norm
belonging to another jurisdiction is never applied to it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import cast

from sqlalchemy.orm import Session

from app.models.db import LEGAL_BASIS_MARKET_NORM, ClauseReference

logger = logging.getLogger("tenura.matcher")

# How many keyword hits (or phrase hits, worth 2) the best norm needs. One
# distinctive hit is enough on its own, but the runner-up margin below is what
# stops a generic word like "notice" attaching a clause to the wrong norm.
MIN_SCORE = 1
# The best match must beat the runner-up by this much; otherwise the clause is
# ambiguous and gets no norm.
MIN_MARGIN = 1


@dataclass(frozen=True)
class ClauseNorm:
    """A plain, detached view of a ClauseReference row.

    The pipeline loads these once, then releases the database connection before
    the (slow) AI calls, so a request never sits on a pooled connection while
    waiting on the model.
    """

    clause_type: str
    jurisdiction: str
    norm_description: str
    red_flag_pattern: str
    severity_default: str
    keywords: tuple[str, ...]
    legal_basis: str
    applies_to: tuple[str, ...]
    consequence: str
    counter_clause: str
    tenant_question: str
    version: str


def to_norm(reference: ClauseReference) -> ClauseNorm:
    # SQLAlchemy's declarative attributes are typed as Column[...]; at runtime
    # they are the row's values. cast() tells the type checker that, without
    # changing behaviour.
    severity = reference.severity_default
    return ClauseNorm(
        clause_type=cast(str, reference.clause_type),
        jurisdiction=cast(str, reference.jurisdiction) or "NG",
        norm_description=cast(str, reference.norm_description) or "",
        red_flag_pattern=cast(str, reference.red_flag_pattern) or "",
        severity_default=getattr(severity, "value", "medium") or "medium",
        keywords=tuple(cast(list, reference.keywords) or ()),
        legal_basis=cast(str, reference.legal_basis) or LEGAL_BASIS_MARKET_NORM,
        applies_to=tuple(cast(list, reference.applies_to) or ()),
        consequence=cast(str, reference.consequence) or "",
        counter_clause=cast(str, reference.counter_clause) or "",
        tenant_question=cast(str, reference.tenant_question) or "",
        version=cast(str, reference.version) or "1",
    )


def load_norms(db: Session) -> list[ClauseNorm]:
    """Read every norm once and detach it from the session."""
    return [to_norm(row) for row in db.query(ClauseReference).all()]


def _applies(norm: ClauseNorm, jurisdiction: str, applies_to: str | None) -> bool:
    # A generic "NG" norm applies to any Nigerian document; a more specific
    # norm (NG-LA) applies only to that jurisdiction.
    if norm.jurisdiction not in (jurisdiction, "NG"):
        return False
    if applies_to is not None and norm.applies_to and applies_to not in norm.applies_to:
        return False
    return True


def score_clause(
    clause_text: str, norms: list[ClauseNorm], jurisdiction: str
) -> list[tuple[int, ClauseNorm]]:
    """All (score, norm) pairs with a positive score, best first.

    A keyword is a hit when it appears in the clause as a substring, so the
    curated singular "repair" still matches "repairs". A multi-word keyword
    ("right to enter") is worth two, since it is far more specific than a single
    common word.
    """
    lowered = (clause_text or "").lower()
    scored: list[tuple[int, ClauseNorm]] = []

    for norm in norms:
        if not _applies(norm, jurisdiction, "tenant"):
            continue
        score = 0
        for keyword in norm.keywords:
            term = (keyword or "").lower().strip()
            if term and term in lowered:
                score += 2 if " " in term else 1
        if score:
            scored.append((score, norm))

    scored.sort(key=lambda pair: (-pair[0], pair[1].clause_type))
    return scored


def match_clause(
    clause_text: str, norms: list[ClauseNorm], jurisdiction: str = "NG"
) -> ClauseNorm | None:
    """The single best norm for a clause, or None when it is not confident.

    Returns a norm only when the best score clears MIN_SCORE and leads the
    runner-up by MIN_MARGIN. Otherwise the clause is left unchecked — a gap in
    coverage, which the scoring layer surfaces, rather than a wrong verdict.
    """
    scored = score_clause(clause_text, norms, jurisdiction)
    if not scored:
        return None

    best_score, best = scored[0]
    if best_score < MIN_SCORE:
        return None
    if len(scored) > 1 and best_score - scored[1][0] < MIN_MARGIN:
        logger.debug(
            "ambiguous clause (%s vs %s at %d/%d); no norm applied",
            best.clause_type,
            scored[1][1].clause_type,
            best_score,
            scored[1][0],
        )
        return None
    return best
