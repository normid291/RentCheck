"""
Week 2: deterministic "missing protections" and "questions to ask".

Keeping these rules in code (not the AI) follows the same principle as clause
splitting and matching. The small model is good at judging ONE clause against
ONE norm, but unreliable at reasoning about what an entire agreement omits.
Code can answer "which expected protections never appeared anywhere?" reliably.
"""
from typing import Iterable

# Protections a fair Nigerian tenancy agreement should contain. Each entry is
# keyed by the SAME clause_type strings used in the clause_reference seed data
# (app/seed_clause_reference.py). If none of a clause type's keywords appear
# anywhere in the agreement, the matcher never returns it, so it never shows up
# in `present_types` and the protection is treated as missing.
EXPECTED_PROTECTIONS = [
    dict(
        clause_type="exit_clause",
        label="Clear exit / termination terms",
        why="No notice period is stated, so either side could end the tenancy without a clear process.",
        question=(
            "There is no exit or termination clause. Ask what notice period applies "
            "if either side wants to end the tenancy, and get it written in."
        ),
    ),
    dict(
        clause_type="caution_fee",
        label="Caution fee / deposit terms",
        why="The agreement does not say what deposit is required or whether it is refundable.",
        question=(
            "The agreement does not mention a caution fee or deposit. Ask how much is "
            "required and confirm in writing that it is refundable, minus documented damage."
        ),
    ),
    dict(
        clause_type="repair_responsibility",
        label="Repair responsibilities",
        why="The agreement does not say who handles repairs, leaving it open for all repairs to be pushed onto the tenant.",
        question=(
            "The agreement does not split repair duties. Ask in writing who handles "
            "day-to-day upkeep versus structural and major repairs."
        ),
    ),
    dict(
        clause_type="utilities_responsibility",
        label="Utilities / service charges",
        why="The agreement does not say who pays for electricity, water, waste, or any shared service charge.",
        question=(
            "The agreement does not say who pays utilities. Ask which utilities are "
            "yours and whether any service charge is fixed and itemised."
        ),
    ),
    dict(
        clause_type="rent_increase",
        label="Rent review / increase terms",
        why="The agreement does not state how or when rent can be increased, leaving the tenant exposed to arbitrary review.",
        question=(
            "The agreement does not cover rent increases. Ask how often rent can be "
            "reviewed, by how much, and on what notice."
        ),
    ),
]

# Question to ask when a clause type IS present but the AI flagged it as unfair.
FLAG_QUESTIONS = {
    "caution_fee": (
        "Ask what the caution fee covers and confirm in writing that it is "
        "refundable, minus any documented damage."
    ),
    "repair_responsibility": (
        "Ask for a written split of repairs so structural and major repairs stay "
        "the landlord's responsibility."
    ),
    "exit_clause": (
        "Ask exactly what notice each side must give to end the tenancy, and make "
        "sure it applies to the landlord too."
    ),
    "rent_increase": (
        "Ask how often rent can be reviewed, by how much, and on what notice, and "
        "get a cap or review process written in."
    ),
    "utilities_responsibility": (
        "Ask which utilities you pay for and whether any 'service charge' is fixed "
        "and itemised rather than open-ended."
    ),
    "entry_without_notice": (
        "Ask for a clause requiring the landlord to give you advance written notice "
        "before entering the premises."
    ),
    "subletting": (
        "Ask for subletting or assignment to be allowed with the landlord's written "
        "consent, which cannot be unreasonably withheld."
    ),
    "taxes_and_outgoings": (
        "Ask which taxes and rates are yours versus the landlord's, and remove "
        "open-ended 'all outgoings' language."
    ),
    "insurance_requirement": (
        "Ask whether you can choose your own insurer and how the insured sum was set."
    ),
    "re_entry_forfeiture": (
        "Ask that re-entry require a written demand, a grace period, and lawful "
        "process instead of automatic forfeiture."
    ),
    "permitted_use": (
        "Ask whether ordinary household use such as guests or working from home is "
        "allowed under the 'residential use only' clause."
    ),
}


def find_missing_protections(present_types: Iterable[str]) -> list[dict]:
    """Return the expected protections whose clause type never appeared in the
    agreement (i.e. the matcher never matched anything of that type)."""
    present = set(present_types)
    return [
        {
            "clause_type": p["clause_type"],
            "label": p["label"],
            "why": p["why"],
            "question": p["question"],
        }
        for p in EXPECTED_PROTECTIONS
        if p["clause_type"] not in present
    ]


def build_questions(flagged: list[dict], missing: list[dict]) -> list[str]:
    """Turn flagged clauses and missing protections into a de-duplicated list of
    concrete questions the tenant should ask before signing. Still purely
    deterministic - each clause type has a curated question."""
    questions: list[str] = []
    seen: set[str] = set()

    def add(question: str | None) -> None:
        if question and question not in seen:
            seen.add(question)
            questions.append(question)

    # Flagged clauses first: these are problems in what the agreement DOES say.
    for verdict in flagged:
        add(FLAG_QUESTIONS.get(verdict.get("clause_type", "")))

    # Then gaps: protections the agreement does not contain at all.
    for item in missing:
        add(item.get("question"))

    return questions
