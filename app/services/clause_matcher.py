from sqlalchemy.orm import Session
from app.models.db import ClauseReference


def match_clause(clause_text: str, db: Session) -> ClauseReference | None:
    """
    Finds the closest known clause_reference entry for a given clause,
    using simple keyword overlap. Deliberately simple for Week 1 —
    this can be upgraded to embedding similarity later if keyword
    matching proves too weak on real agreements, but keyword matching
    is cheap, fast, and explainable, which matters when a 3B model
    is the one consuming the result.
    """
    clause_lower = clause_text.lower()
    references = db.query(ClauseReference).all()

    best_match = None
    best_score = 0

    for ref in references:
        score = sum(1 for kw in ref.keywords if kw.lower() in clause_lower)
        if score > best_score:
            best_score = score
            best_match = ref

    return best_match if best_score > 0 else None
