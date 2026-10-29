"""
Deterministic red-flag rules.

The small AI model is inconsistent: on repeated runs of the SAME clause it
sometimes misses a serious trap (e.g. re-entry "whether or not lawfully
demanded"). For a handful of well-known, high-confidence lurking phrases we do
not want to depend on the model at all, so we detect them here with plain
regex. These run BEFORE the AI call: if a rule fires, we take the deterministic
verdict and skip the (slow, flaky) model call for that clause.

Only add rules that are unambiguously bad when their words appear. When in
doubt, leave it to the model - a noisy rule erodes trust faster than a missed
one. Each rule quotes the matched text as evidence, so the output stays
explainable and consistent with the AI path.

Obligation direction
    A pattern alone is not enough. "structural repairs" is a red flag when the
    TENANT is made responsible for them, and a GOOD clause when the LANDLORD
    is. A rule may therefore carry a ``direction`` ("tenant" | "landlord"): the
    pattern must occur in a sentence whose only named party is that side. When
    both parties are named in the same sentence the rule stays silent - a
    dropped flag is always preferable to a wrong one. Rules without
    ``direction`` fire on the pattern alone (used for traps that are bad
    however the sentence is framed, e.g. "whether or not lawfully demanded").
"""
import re

# severity values must match app.models.db.Severity ("low" | "medium" | "high").
RED_FLAG_RULES = [
    # -- re-entry / forfeiture -------------------------------------------------
    dict(
        clause_type="re_entry_forfeiture",
        pattern=r"whether\s+or\s+not\s+lawfully\s+demanded",
        severity="high",
        reason=(
            "The landlord may re-enter and end the tenancy even without a lawful "
            "demand for the rent - courts normally require a formal demand first."
        ),
    ),
    dict(
        clause_type="re_entry_forfeiture",
        pattern=r"shall\s+absolutely\s+cease\s+and\s+determine",
        severity="high",
        reason=(
            "The tenancy is forfeited automatically on breach with no notice, grace "
            "period, or court process."
        ),
    ),
    # -- caution fee / deposit -------------------------------------------------
    dict(
        clause_type="caution_fee",
        pattern=r"non[\s-]?refundable",
        severity="high",
        reason=(
            "A caution fee or deposit stated as non-refundable is a common red flag; "
            "deposits are normally refundable minus documented damage."
        ),
    ),
    dict(
        clause_type="caution_fee",
        pattern=r"forfeit(?:ed|ure)?\s+(?:of\s+)?(?:the\s+)?(?:caution|deposit|security)",
        severity="high",
        reason="Automatic forfeiture of the tenant's deposit is not standard.",
    ),
    # -- landlord entry --------------------------------------------------------
    dict(
        clause_type="entry_without_notice",
        pattern=r"\b(?:enter|entry|re-?enter|access)\b[^.]{0,40}\bwithout\s+(?:any\s+|prior\s+|previous\s+)?notice\b",
        severity="high",
        reason="The landlord can enter the premises without giving notice.",
    ),
    dict(
        clause_type="entry_without_notice",
        pattern=r"\bat\s+any\s+time\b[^.]{0,30}\bwithout\s+notice\b",
        severity="high",
        reason="The landlord can enter at any time without notice.",
    ),
    # -- rent increase ---------------------------------------------------------
    dict(
        clause_type="rent_increase",
        pattern=r"\bincrease\s+the\s+rent\b[^.]{0,30}\bat\s+any\s+time\b",
        severity="high",
        reason="Rent can be increased at any time with no notice or cap.",
    ),
    # -- subletting / assignment ----------------------------------------------
    dict(
        clause_type="subletting",
        pattern=r"\bconsent\b[^.]{0,60}\b(?:sole|absolute|uncontrolled)\s+discretion\b",
        severity="medium",
        reason="Assignment/subletting consent is entirely at the landlord's discretion, with no reasonableness limit.",
    ),
    # -- taxes and outgoings ---------------------------------------------------
    # The tenant is the payer in the overwhelming majority of framed clauses, so
    # no direction is asserted here; the phrase "all ... whatsoever" is the trap.
    dict(
        clause_type="taxes_and_outgoings",
        pattern=r"\ball\s+(?:taxes|rates|duties|assessments|impositions)\b[^.]{0,80}\bwhatsoever\b",
        severity="medium",
        reason="The tenant is made responsible for all taxes and outgoings without limitation, including ones normally borne by the owner.",
    ),
    # -- repairs ---------------------------------------------------------------
    # Direction matters: structural/major/all repairs are the landlord's job, so
    # this only fires when a sentence names the TENANT (and not the landlord) as
    # responsible. "The Landlord shall be responsible for structural repairs" is
    # a fair clause and must not be flagged.
    dict(
        clause_type="repair_responsibility",
        pattern=r"\b(?:structural|major)\s+repairs?\b",
        severity="medium",
        direction="tenant",
        reason="Structural or major repairs appear to be pushed onto the tenant; these are normally the landlord's responsibility.",
    ),
    dict(
        clause_type="repair_responsibility",
        pattern=r"\ball\s+repairs\b[^.]{0,40}\bhowsoever\s+(?:caused|arising)\b",
        severity="medium",
        direction="tenant",
        reason="The tenant is responsible for all repairs however caused, which removes the landlord's obligation.",
    ),
    # -- permitted use ---------------------------------------------------------
    dict(
        clause_type="permitted_use",
        pattern=r"\bno\s+(?:guests|visitors|lodgers)\b",
        severity="low",
        reason="Banning guests/visitors outright is broader than the normal 'residential use only' restriction.",
    ),
    # -- exit / termination ----------------------------------------------------
    dict(
        clause_type="exit_clause",
        pattern=r"\blandlord\b[^.]{0,60}\bterminat\w*\b[^.]{0,40}\bwithout\s+(?:any\s+)?notice\b",
        severity="high",
        reason="The landlord can end the tenancy without notice, while no matching right is given to the tenant.",
    ),
    # -- utilities -------------------------------------------------------------
    dict(
        clause_type="utilities_responsibility",
        pattern=r"\bservice\s+charge\b[^.]{0,50}\bat\s+(?:his|its|the\s+landlord'?s?)\s+discretion\b",
        severity="medium",
        reason="A service charge left to the landlord's discretion is open-ended for the tenant.",
    ),
    dict(
        clause_type="utilities_responsibility",
        pattern=r"\bpay\s+all\s+(?:charges|utilities|outgoings)\b[^.]{0,40}\bhowsoever\b",
        severity="medium",
        reason="The tenant is made responsible for all charges however arising, with no limit.",
    ),
    # -- rent increase ---------------------------------------------------------
    dict(
        clause_type="rent_increase",
        pattern=r"\brent\b[^.]{0,40}\b(?:increase|review|revise)\w*\b[^.]{0,40}\bat\s+(?:the\s+)?landlord'?s?\s+discretion\b",
        severity="high",
        reason="The landlord can increase or review the rent at will, with no cap or notice.",
    ),
    # -- insurance -------------------------------------------------------------
    dict(
        clause_type="insurance_requirement",
        pattern=r"\b(?:only|solely)\b[^.]{0,50}\b(?:office|insurer|company)\s+approved\s+by\s+the\s+landlord\b",
        severity="medium",
        reason="The tenant must use an insurer solely chosen by the landlord, with no independent choice.",
    ),
    # -- subletting / assignment ----------------------------------------------
    dict(
        clause_type="subletting",
        pattern=r"\bconsent\b[^.]{0,60}\b(?:refuse|refused|withheld|withhold)\b[^.]{0,40}\b(?:for\s+any\s+reason|without\s+reason|arbitrarily)\b",
        severity="medium",
        reason="The landlord may refuse consent for any reason, with no reasonableness standard.",
    ),
]

# Precompile for speed and to fail loudly on a bad pattern at import time.
_COMPILED = [
    (rule, re.compile(rule["pattern"], re.IGNORECASE | re.DOTALL))
    for rule in RED_FLAG_RULES
]

# Sentence boundaries. A direction check runs against the sentence that holds
# the match, so "Tenant keeps interior in repair; Landlord responsible for
# structural repairs" is judged sentence by sentence, not as one blob.
_SENTENCE_SPLIT = re.compile(r"[.;\n]+|(?:\bprovided\s+(?:always\s+)?that\b)", re.IGNORECASE)
_PARTY = {
    "tenant": re.compile(r"\b(?:tenant|lessee)\b", re.IGNORECASE),
    "landlord": re.compile(r"\b(?:landlord|lessor)\b", re.IGNORECASE),
}


def _sentence_for(text: str, index: int) -> str:
    """The sentence of `text` that contains character `index`."""
    start = 0
    for boundary in _SENTENCE_SPLIT.finditer(text):
        if boundary.start() >= index:
            return text[start : boundary.start()].strip()
        start = boundary.end()
    return text[start:].strip()


def _direction_ok(sentence: str, direction: str) -> bool:
    """True when only the named party (tenant/landlord) appears in `sentence`.

    If both parties are named, the sentence is ambiguous and the rule must stay
    silent - a dropped flag is preferable to a wrong one.
    """
    tenant = bool(_PARTY["tenant"].search(sentence))
    landlord = bool(_PARTY["landlord"].search(sentence))
    if direction == "tenant":
        return tenant and not landlord
    if direction == "landlord":
        return landlord and not tenant
    return True


def find_deterministic_flags(clause_text: str, clause_type: str) -> list[dict]:
    """Return rule-based verdicts for this clause, in the same shape the AI
    path returns. Empty list means no rule fired - fall through to the model.

    At most one verdict per clause type is returned (highest severity wins) so a
    clause matching several patterns does not show up as duplicate flags."""
    severity_rank = {"low": 0, "medium": 1, "high": 2}
    best: dict | None = None

    for rule, regex in _COMPILED:
        if rule["clause_type"] != clause_type:
            continue
        match = regex.search(clause_text)
        if not match:
            continue
        direction = rule.get("direction")
        if direction and not _direction_ok(
            _sentence_for(clause_text, match.start()), direction
        ):
            continue
        if best is None or severity_rank[rule["severity"]] > severity_rank[best["severity"]]:
            best = {
                "clause": clause_text,
                "clause_type": clause_type,
                "flag": True,
                "evaluated": True,
                "severity": rule["severity"],
                "evidence": match.group(0).strip(),
                "evidence_start": match.start(),
                "evidence_end": match.end(),
                "reason": rule["reason"],
                "verified": True,  # regex match is its own proof
                "source": "rule",
            }

    return [best] if best else []
