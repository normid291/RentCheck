"""
Run this once after the DB is provisioned: python -m app.seed_clause_reference

Starting set of common Nigerian tenancy clause types. Expand this list as
coverage gaps show up on real agreements — this table is the backbone of the
whole analysis, so more curated entries directly means better coverage.

PROVENANCE, PLEASE READ
    Every entry here is `legal_basis="market_norm"`: it states common Nigerian
    market practice, NOT a verified provision of law. The `source_*` and
    `reviewed_*` fields are deliberately left empty. They are the places a human
    legal reviewer fills in (title, section, URL, quote, who reviewed it) before
    a norm may ever be described as a legal requirement. No statute or section
    number is invented here. The UI must therefore phrase these as "common
    practice in Nigeria", never "the law requires".
"""
from app.database import SessionLocal
from app.models.db import (
    LEGAL_BASIS_MARKET_NORM,
    ClauseReference,
    Severity,
)

# The generic Nigerian jurisdiction package. State-specific packs (e.g. NG-LA)
# would override individual entries here; the matcher accepts a document's own
# jurisdiction plus these generic "NG" rows.
NG = "NG"
TENANT = ["tenant"]


def _entry(
    clause_type: str,
    norm_description: str,
    red_flag_pattern: str,
    severity: Severity,
    keywords: list[str],
    *,
    consequence: str,
    counter_clause: str,
    tenant_question: str,
) -> dict:
    return dict(
        clause_type=clause_type,
        jurisdiction=NG,
        norm_description=norm_description,
        red_flag_pattern=red_flag_pattern,
        severity_default=severity,
        keywords=keywords,
        legal_basis=LEGAL_BASIS_MARKET_NORM,
        applies_to=TENANT,
        consequence=consequence,
        counter_clause=counter_clause,
        tenant_question=tenant_question,
        version="1",
    )


SEED_DATA = [
    _entry(
        "caution_fee",
        "Caution fees are typically refundable (minus damages) and usually "
        "range 10-20% of annual rent.",
        "Non-refundable caution fee, or caution fee exceeding 25-30% of annual rent.",
        Severity.high,
        ["caution fee", "caution deposit", "security deposit"],
        consequence=(
            "If you accept this, you may lose a large sum that is not returned "
            "when you leave, even if the premises are in good condition."
        ),
        counter_clause=(
            "A refundable caution fee of [amount], returnable within [X] days of "
            "vacation, less the reasonable cost of repairing damage you caused "
            "(fair wear and tear excepted)."
        ),
        tenant_question="Is the caution fee refundable, and within how many days after I move out?",
    ),
    _entry(
        "repair_responsibility",
        "Tenant handles interior/day-to-day upkeep; landlord handles structural "
        "repairs and major systems.",
        "All repairs (including structural/major) pushed onto tenant with no "
        "landlord obligation at all.",
        Severity.medium,
        ["repair", "maintenance", "upkeep", "structural"],
        consequence=(
            "If you accept this, you could be made to pay for major structural "
            "works such as the roof, foundations, or wiring."
        ),
        counter_clause=(
            "The Tenant shall keep the interior in good repair (fair wear and "
            "tear excepted); the Landlord shall be responsible for structural "
            "repairs and the major systems (roof, walls, plumbing, wiring)."
        ),
        tenant_question="Who is responsible for structural repairs such as the roof and wiring?",
    ),
    _entry(
        "exit_clause",
        "Agreement should specify notice period (commonly 1-3 months) for either "
        "party to terminate.",
        "No exit/termination clause at all, or one-sided notice requirement "
        "(tenant must give 3 months, landlord gives none).",
        Severity.high,
        ["notice", "terminate", "termination", "vacate", "quit"],
        consequence=(
            "If you accept this, the landlord may be able to end the tenancy "
            "abruptly while you are bound to a long notice period."
        ),
        counter_clause=(
            "Either party may terminate by giving [X] months' written notice; "
            "the same notice period applies to both parties."
        ),
        tenant_question="What notice must each side give to end the tenancy, and is it the same for both?",
    ),
    _entry(
        "rent_increase",
        "Rent increase terms, if any, should state frequency and a reasonable "
        "cap or review process.",
        "Landlord can increase rent at will, any time, with no notice or cap.",
        Severity.medium,
        ["rent increase", "review rent", "adjust rent"],
        consequence=(
            "If you accept this, the rent could be raised at any time without "
            "notice, making it hard to budget."
        ),
        counter_clause=(
            "Rent may be reviewed no more than once every [12] months, on at "
            "least [X] months' written notice, and by no more than [Y]%."
        ),
        tenant_question="How often can the rent be increased, and how much notice will I get?",
    ),
    _entry(
        "utilities_responsibility",
        "Agreement should clearly state who pays for utilities (electricity, "
        "water, waste) and any shared service charge.",
        "Ambiguous or missing utility responsibility, or tenant billed for "
        "undefined 'service charges'.",
        Severity.low,
        ["utility", "utilities", "service charge", "electricity", "water rate"],
        consequence=(
            "If you accept this, you could receive bills for charges that were "
            "never clearly agreed or capped."
        ),
        counter_clause=(
            "The Tenant shall pay for [electricity / water] used at the premises; "
            "the Landlord shall pay [service charge / waste]; no other charges apply."
        ),
        tenant_question="Exactly which utility bills am I responsible for, and which are the landlord's?",
    ),
    _entry(
        "entry_without_notice",
        "Landlord should give reasonable notice (commonly 24-48 hours) before "
        "entering the premises.",
        "Landlord reserves right to enter at any time without notice.",
        Severity.high,
        ["right to enter", "landlord may enter", "right of entry", "access the premises", "enter the premises", "enter and view", "to enter and"],
        consequence=(
            "If you accept this, the landlord could enter your home at any time "
            "without warning."
        ),
        counter_clause=(
            "The Landlord may enter at reasonable times, on at least 24 hours' "
            "written notice, except in a genuine emergency."
        ),
        tenant_question="How much notice will I get before the landlord enters the premises?",
    ),
    _entry(
        "subletting",
        "Requiring the landlord's written consent before subletting or assigning "
        "is normal, especially where consent cannot be unreasonably withheld.",
        "A flat ban with no way to obtain consent, an excessive penalty for "
        "breach, or consent that the landlord may refuse for any reason.",
        Severity.low,
        ["sublet", "sub-let", "assign the premises", "underlet"],
        consequence=(
            "If you accept this, you may be unable to share the home or move on "
            "to another place without breaking the agreement."
        ),
        counter_clause=(
            "The Tenant may sublet or assign with the Landlord's written "
            "consent, which shall not be unreasonably withheld."
        ),
        tenant_question="Can I sublet or assign the tenancy, and on what terms?",
    ),
    _entry(
        "taxes_and_outgoings",
        "In many Nigerian leases tenant pays rates/taxes on the premises, but "
        "major property tax/land use charges are typically a landlord "
        "responsibility unless clearly shared.",
        "Tenant made responsible for ALL taxes, duties, and outgoings without "
        "limitation, including ones normally borne by property owners.",
        Severity.medium,
        ["taxes", "rates", "duties", "assessments", "outgoings"],
        consequence=(
            "If you accept this, you could be billed for property taxes and "
            "charges that are normally the owner's responsibility."
        ),
        counter_clause=(
            "The Tenant shall pay rates and charges arising from their own "
            "occupation; taxes on the ownership of the property remain the "
            "Landlord's responsibility."
        ),
        tenant_question="Which taxes and rates am I expected to pay, and which stay with the landlord?",
    ),
    _entry(
        "insurance_requirement",
        "Tenant may be required to insure the premises against fire/damage, with "
        "proof of policy provided on request.",
        "Tenant forced to use an insurer solely chosen/approved by the landlord "
        "(no independent choice), or insurance sum set unreasonably high "
        "relative to property value.",
        Severity.medium,
        ["insured against", "insurance policy", "approved by the landlord", "premium paid"],
        consequence=(
            "If you accept this, you may be forced to pay for insurance you "
            "cannot shop for, at a price you cannot question."
        ),
        counter_clause=(
            "The Tenant may insure with a reputable insurer of their choice and "
            "shall provide proof of cover on request."
        ),
        tenant_question="Must I use a particular insurer, and can I choose my own?",
    ),
    _entry(
        "re_entry_forfeiture",
        "Landlord may re-enter only after rent is genuinely overdue, after a "
        "formal written demand and a reasonable grace period, and by lawful "
        "process (a court order or proper statutory notices).",
        "Landlord may re-enter and end the tenancy automatically, even without "
        "any demand or notice, or after a very short arrears period, without "
        "going through the courts.",
        Severity.high,
        ["re-enter", "re-entry", "reenter", "forfeit", "cease and determine", "whether or not lawfully demanded"],
        consequence=(
            "If you accept this, the landlord could lock you out or end the "
            "tenancy over a short delay, without a demand or a court order."
        ),
        counter_clause=(
            "The Landlord may re-enter only after a written demand and [X] days "
            "to remedy the breach, and only by due process of law."
        ),
        tenant_question="What happens if I'm late with rent — how much grace do I get, and what process is followed?",
    ),
    _entry(
        "permitted_use",
        "Standard to restrict premises to private residential use only; this is "
        "normal and not inherently unfair.",
        "Use restriction combined with an unreasonable penalty, or a restriction "
        "so broad it limits ordinary household activity (e.g. banning "
        "guests/visitors entirely).",
        Severity.low,
        ["private dwelling", "trade or business", "business or trade", "residential use only"],
        consequence=(
            "If you accept this, ordinary use of your own home (having guests, "
            "working from home) could be treated as a breach."
        ),
        counter_clause=(
            "The premises shall be used as a private residence only; nothing "
            "restricts ordinary household use, including receiving guests."
        ),
        tenant_question="Can I have guests stay, or work from home, without breaching the agreement?",
    ),
    _entry(
        "governing_law",
        "A governing-law clause should name the jurisdiction whose courts hear "
        "disputes, and it should be the jurisdiction where the property is.",
        "Governing law names a foreign jurisdiction, or the clause is so broad "
        "the tenant cannot tell where disputes would be heard.",
        Severity.low,
        ["governing law", "governed by", "jurisdiction", "courts of"],
        consequence=(
            "If you accept this, a dispute might have to be heard in a court far "
            "from the property."
        ),
        counter_clause=(
            "This agreement is governed by the laws of the jurisdiction where "
            "the premises are located."
        ),
        tenant_question="Which courts would hear a dispute under this agreement?",
    ),
    _entry(
        "dispute_resolution",
        "A dispute-resolution clause should give both parties a clear, fair "
        "path (negotiation, mediation, then the courts) and not force only one "
        "side to arbitrate at its own cost.",
        "Dispute resolution one-sided (only the tenant must arbitrate), or "
        "arbitrator chosen solely by the landlord, or costs pushed entirely onto "
        "the tenant.",
        Severity.low,
        ["dispute", "arbitration", "arbitrator", "mediation", "resolution"],
        consequence=(
            "If you accept this, resolving a disagreement could be slow, "
            "expensive, and controlled by the landlord."
        ),
        counter_clause=(
            "The parties shall first try to resolve any dispute amicably; "
            "failing that, either party may refer it to mediation or the courts, "
            "with each side bearing its own costs."
        ),
        tenant_question="If we disagree, how is it resolved, and who pays for that process?",
    ),
]


def run():
    """Sync the table with SEED_DATA: insert new clause types, update existing
    ones (so keyword/wording/provenance tweaks reach the database without wiping
    it). Matching is by clause_type: within the generic NG pack there is one row
    per type, and this also upgrades pre-Phase-1 rows (which had no jurisdiction)
    in place rather than duplicating them.
    """
    db = SessionLocal()
    try:
        added = updated = 0
        for entry in SEED_DATA:
            existing = (
                db.query(ClauseReference)
                .filter(ClauseReference.clause_type == entry["clause_type"])
                .first()
            )
            if existing is None:
                db.add(ClauseReference(**entry))
                added += 1
            else:
                for key, value in entry.items():
                    setattr(existing, key, value)
                updated += 1
        db.commit()
        print(f"clause_reference synced: {added} added, {updated} updated.")
        return added, updated
    finally:
        db.close()


if __name__ == "__main__":
    run()
