"""Clause -> norm matching, within a jurisdiction."""
from __future__ import annotations

from app.services.clause_matcher import ClauseNorm, match_clause, score_clause


def norm(clause_type: str, keywords: list[str], jurisdiction: str = "NG", applies_to=("tenant",)) -> ClauseNorm:
    return ClauseNorm(
        clause_type=clause_type,
        jurisdiction=jurisdiction,
        norm_description=f"norm for {clause_type}",
        red_flag_pattern="pattern",
        severity_default="medium",
        keywords=tuple(keywords),
        legal_basis="market_norm",
        applies_to=tuple(applies_to),
        consequence="",
        counter_clause="",
        tenant_question="",
        version="1",
    )


REPAIR = norm("repair_responsibility", ["repair", "maintenance", "upkeep", "structural"])
EXIT = norm("exit_clause", ["notice", "terminate", "termination", "vacate", "quit"])
ENTRY = norm("entry_without_notice", ["right to enter", "landlord may enter", "enter the premises"])
NORMS = [REPAIR, EXIT, ENTRY]


def test_plural_matches_singular_keyword():
    # "repairs" must match the curated "repair"; substring matching does this.
    clause = "The Tenant shall be responsible for all structural repairs to the roof."
    assert match_clause(clause, NORMS, "NG-LA").clause_type == "repair_responsibility"


def test_fair_landlord_repair_clause_still_matches_the_topic():
    # The matcher matches the TOPIC; whether it is a red flag is decided later
    # by obligation direction (see test_red_flags). It must not crash or pick a
    # different norm.
    clause = "The Landlord shall be responsible for structural repairs to the premises."
    assert match_clause(clause, NORMS, "NG-LA").clause_type == "repair_responsibility"


def test_phrase_keyword_is_a_strong_signal():
    clause = "The Landlord may enter the premises at any time without notice."
    assert match_clause(clause, [ENTRY, EXIT], "NG-LA").clause_type == "entry_without_notice"


def test_ambiguous_tie_yields_nothing():
    # "notice" matches exit; "structural" matches repair; a clause containing one
    # of each ties and must be left unmatched rather than guessed.
    clause = "The structural notice clause."
    assert match_clause(clause, NORMS, "NG-LA") is None


def test_no_keyword_yields_nothing():
    assert match_clause("The parties agree to be friends.", NORMS, "NG-LA") is None


def test_generic_ng_norm_applies_to_a_state_document():
    clause = "The Tenant shall vacate and give quit notice."
    assert match_clause(clause, [EXIT], "NG-LA") is not None
    assert match_clause(clause, [EXIT], "NG-FC") is not None


def test_state_specific_norm_does_not_leak_to_another_state():
    lagos_only = norm("caution_fee", ["caution fee"], jurisdiction="NG-LA")
    clause = "A caution fee of 10% is payable."
    assert match_clause(clause, [lagos_only], "NG-LA") is not None
    assert match_clause(clause, [lagos_only], "NG-FC") is None


def test_applies_to_other_party_is_skipped():
    landlord_only = norm("landlord_duty", ["repair"], applies_to=("landlord",))
    clause = "The Landlord shall carry out repairs."
    assert match_clause(clause, [landlord_only], "NG-LA") is None


def test_scores_are_deterministically_ordered():
    clause = "The Tenant shall maintain and repair the structural parts."
    scored = score_clause(clause, NORMS, "NG-LA")
    assert scored
    assert all(scored[i][0] >= scored[i + 1][0] for i in range(len(scored) - 1))
