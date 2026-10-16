"""
Run this once after the DB is provisioned: python -m app.seed_clause_reference

Starting set of common Nigerian tenancy clause types. Expand this list
during Week 2 — this table is the backbone of the whole analysis, so more
curated entries directly means better coverage on real agreements.
"""
from app.database import SessionLocal
from app.models.db import ClauseReference, Severity

SEED_DATA = [
    dict(
        clause_type="caution_fee",
        norm_description="Caution fees are typically refundable (minus damages) and usually range 10-20% of annual rent.",
        red_flag_pattern="Non-refundable caution fee, or caution fee exceeding 25-30% of annual rent.",
        severity_default=Severity.high,
        keywords=["caution fee", "caution deposit", "security deposit"],
    ),
    dict(
        clause_type="repair_responsibility",
        norm_description="Tenant handles interior/day-to-day upkeep; landlord handles structural repairs and major systems.",
        red_flag_pattern="All repairs (including structural/major) pushed onto tenant with no landlord obligation at all.",
        severity_default=Severity.medium,
        keywords=["repair", "maintenance", "upkeep", "structural"],
    ),
    dict(
        clause_type="exit_clause",
        norm_description="Agreement should specify notice period (commonly 1-3 months) for either party to terminate.",
        red_flag_pattern="No exit/termination clause at all, or one-sided notice requirement (tenant must give 3 months, landlord gives none).",
        severity_default=Severity.high,
        keywords=["notice", "terminate", "termination", "vacate", "quit"],
    ),
    dict(
        clause_type="rent_increase",
        norm_description="Rent increase terms, if any, should state frequency and a reasonable cap or review process.",
        red_flag_pattern="Landlord can increase rent at will, any time, with no notice or cap.",
        severity_default=Severity.medium,
        keywords=["rent increase", "review rent", "adjust rent"],
    ),
    dict(
        clause_type="utilities_responsibility",
        norm_description="Agreement should clearly state who pays for utilities (electricity, water, waste) and any shared service charge.",
        red_flag_pattern="Ambiguous or missing utility responsibility, or tenant billed for undefined 'service charges'.",
        severity_default=Severity.low,
        keywords=["utility", "utilities", "service charge", "electricity", "water rate"],
    ),
    dict(
        clause_type="entry_without_notice",
        norm_description="Landlord should give reasonable notice (commonly 24-48 hours) before entering the premises.",
        red_flag_pattern="Landlord reserves right to enter at any time without notice.",
        severity_default=Severity.high,
        keywords=["right to enter", "landlord may enter", "right of entry", "access the premises", "enter the premises", "enter and view", "to enter and"],
    ),
    dict(
        clause_type="subletting",
        norm_description="Requiring the landlord's written consent before subletting or assigning is normal, especially where consent cannot be unreasonably withheld.",
        red_flag_pattern="A flat ban with no way to obtain consent, an excessive penalty for breach, or consent that the landlord may refuse for any reason.",
        severity_default=Severity.low,
        keywords=["sublet", "sub-let", "assign the premises", "underlet"],
    ),
    dict(
        clause_type="taxes_and_outgoings",
        norm_description="In many Nigerian leases tenant pays rates/taxes on the premises, but major property tax/land use charges are typically a landlord responsibility unless clearly shared.",
        red_flag_pattern="Tenant made responsible for ALL taxes, duties, and outgoings without limitation, including ones normally borne by property owners.",
        severity_default=Severity.medium,
        keywords=["taxes", "rates", "duties", "assessments", "outgoings"],
    ),
    dict(
        clause_type="insurance_requirement",
        norm_description="Tenant may be required to insure the premises against fire/damage, with proof of policy provided on request.",
        red_flag_pattern="Tenant forced to use an insurer solely chosen/approved by the landlord (no independent choice), or insurance sum set unreasonably high relative to property value.",
        severity_default=Severity.medium,
        keywords=["insured against", "insurance policy", "approved by the landlord", "premium paid"],
    ),
    dict(
        clause_type="re_entry_forfeiture",
        norm_description="Landlord may re-enter only after rent is genuinely overdue, after a formal written demand and a reasonable grace period, and by lawful process (a court order or proper statutory notices).",
        red_flag_pattern="Landlord may re-enter and end the tenancy automatically, even without any demand or notice, or after a very short arrears period, without going through the courts.",
        severity_default=Severity.high,
        keywords=["re-enter", "re-entry", "reenter", "forfeit", "cease and determine", "whether or not lawfully demanded"],
    ),
    dict(
        clause_type="permitted_use",
        norm_description="Standard to restrict premises to private residential use only; this is normal and not inherently unfair.",
        red_flag_pattern="Use restriction combined with an unreasonable penalty, or a restriction so broad it limits ordinary household activity (e.g. banning guests/visitors entirely).",
        severity_default=Severity.low,
        keywords=["private dwelling", "trade or business", "business or trade", "residential use only"],
    ),
]


def run():
    """Sync the table with SEED_DATA: insert new clause types, update existing
    ones (so keyword/wording tweaks reach the database without wiping it)."""
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
    finally:
        db.close()


if __name__ == "__main__":
    run()
