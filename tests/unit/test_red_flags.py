"""Every deterministic red-flag rule: one positive fixture + one negative.

The convention this file enforces: a rule that cannot point at a clause which
must fire AND a clause which must stay silent is not a rule we trust. The
negative fixtures are deliberately the FAIR counterpart of each trap, which is
where the obligation-direction bug lived ("structural repairs" is good when the
landlord owns it).
"""
from __future__ import annotations

import pytest

from app.services.red_flags import RED_FLAG_RULES, find_deterministic_flags

# (clause_type, positive must-flag, negative must-not-flag)
CASES = [
    (
        "re_entry_forfeiture",
        "If the rent is in arrears for 21 days whether or not lawfully demanded, "
        "the Landlord may re-enter and the term shall determine.",
        "If the rent remains unpaid for 30 days after a written demand, the Landlord "
        "may apply to the court for possession.",
    ),
    (
        "re_entry_forfeiture",
        "On any breach the term shall absolutely cease and determine.",
        "The term shall not determine except by an order of the court.",
    ),
    (
        "caution_fee",
        "The caution fee is non-refundable under any circumstance.",
        "The caution fee is refundable, less any documented damage.",
    ),
    (
        "caution_fee",
        "The Landlord may forfeit the deposit on any breach.",
        "The deposit shall be returned to the Tenant within 14 days of vacant possession.",
    ),
    (
        "entry_without_notice",
        "The Landlord may enter the premises without notice.",
        "The Landlord may enter the premises after giving 48 hours written notice.",
    ),
    (
        "entry_without_notice",
        "The Landlord may enter at any time without notice.",
        "The Tenant shall keep the premises clean at all times.",
    ),
    (
        "rent_increase",
        "The Landlord may increase the rent at any time.",
        "The rent may be reviewed once every two years on three months written notice.",
    ),
    (
        "subletting",
        "The Tenant shall not assign the premises without the consent in the "
        "Landlord's sole discretion.",
        "The Tenant may not assign without the Landlord's consent, which shall not be "
        "unreasonably withheld.",
    ),
    (
        "taxes_and_outgoings",
        "The Tenant shall pay all taxes, rates, duties and outgoings whatsoever.",
        "The Tenant shall pay the rates and refuse levy charged on the premises.",
    ),
    (
        "repair_responsibility",
        "The Tenant shall be responsible for all structural and major repairs.",
        "The Landlord shall be responsible for structural and major repairs.",
    ),
    (
        "repair_responsibility",
        "The Tenant shall bear all repairs howsoever caused.",
        "The Landlord shall bear all repairs howsoever arising.",
    ),
    (
        "permitted_use",
        "No guests or visitors are permitted in the premises.",
        "The premises shall be used for private residential purposes only.",
    ),
    (
        "exit_clause",
        "The Landlord may terminate this tenancy without notice.",
        "Either party may terminate this tenancy on one month's written notice.",
    ),
    (
        "utilities_responsibility",
        "The service charge shall be fixed at the Landlord's discretion.",
        "The service charge shall be reviewed annually and itemised.",
    ),
    (
        "utilities_responsibility",
        "The Tenant shall pay all charges howsoever arising.",
        "The Tenant shall pay the electricity and water charges for the premises.",
    ),
    (
        "rent_increase",
        "The rent may be reviewed at the Landlord's discretion.",
        "The rent may be reviewed once every two years.",
    ),
    (
        "insurance_requirement",
        "The Tenant shall insure the premises only with an insurer approved by the Landlord.",
        "The Tenant shall insure the premises with an insurer of the Tenant's choice.",
    ),
    (
        "subletting",
        "The Landlord's consent may be withheld for any reason.",
        "The Landlord shall not unreasonably withhold consent to assignment.",
    ),
]


@pytest.mark.parametrize("clause_type,positive,negative", CASES, ids=range(len(CASES)))
def test_positive_fixture_flags(clause_type, positive, negative):
    flags = find_deterministic_flags(positive, clause_type)
    assert flags, f"expected a flag for {clause_type}: {positive!r}"
    assert flags[0]["flag"] is True
    assert flags[0]["clause_type"] == clause_type
    assert flags[0]["severity"] in {"low", "medium", "high"}


@pytest.mark.parametrize("clause_type,positive,negative", CASES, ids=range(len(CASES)))
def test_negative_fixture_stays_silent(clause_type, positive, negative):
    assert find_deterministic_flags(negative, clause_type) == [], (
        f"false positive for {clause_type}: {negative!r}"
    )


def test_every_rule_has_a_case():
    """Guard against a new rule landing without its positive/negative pair."""
    covered = {(c[0],) for c in CASES}
    for rule in RED_FLAG_RULES:
        assert (rule["clause_type"],) in covered, (
            f"rule for {rule['clause_type']} ({rule['pattern']!r}) has no fixture"
        )


# The four clauses called out explicitly in the brief.
def test_fair_landlord_repair_clause_is_not_flagged():
    assert find_deterministic_flags(
        "The Landlord shall be responsible for structural and major repairs.",
        "repair_responsibility",
    ) == []


def test_mixed_sentence_is_not_flagged():
    assert find_deterministic_flags(
        "Tenant keeps interior in repair; Landlord responsible for structural repairs.",
        "repair_responsibility",
    ) == []


def test_tenant_structural_repairs_is_flagged():
    flags = find_deterministic_flags(
        "The Tenant shall be responsible for all structural and major repairs.",
        "repair_responsibility",
    )
    assert flags and flags[0]["severity"] == "medium"


def test_tenant_all_repairs_howsoever_caused_is_flagged():
    flags = find_deterministic_flags(
        "Tenant shall bear all repairs howsoever caused.",
        "repair_responsibility",
    )
    assert flags and flags[0]["flag"] is True


def test_rule_only_fires_for_its_own_clause_type():
    text = "The Tenant shall be responsible for all structural and major repairs."
    assert find_deterministic_flags(text, "caution_fee") == []
