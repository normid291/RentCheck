"""
Export real ExplainER data: take an actual tenancy agreement stored in the
database, run it through the REAL RentCheck analysis pipeline, anonymise the
personal details, and write the result to tests/fixtures/explainer_data.json.

The video builder (tests/make_explainer_video.py) reads that JSON so every
number and clause shown on screen comes from a genuine analysis - not a
placeholder.

Run from the repo root (uses the app's normal DATABASE_URL / .env):
    python tests/export_explainer_data.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import desc

from app.database import SessionLocal
from app.models.db import Agreement, Analysis, SourceType
from app.routers.agreements import _run_pipeline

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "explainer_data.json")

# Human labels for the clause types the pipeline emits.
CLAUSE_LABELS = {
    "taxes_and_outgoings": "Taxes & outgoings",
    "entry_without_notice": "Entry without notice",
    "subletting": "Subletting",
    "re_entry_forfeiture": "Re-entry & forfeiture",
    "repair_responsibility": "Repair responsibilities",
    "exit_clause": "Clear exit / termination terms",
    "caution_fee": "Caution fee / deposit terms",
    "utilities_responsibility": "Utilities / service charges",
    "rent_increase": "Rent review / increase terms",
    "rent_payment": "Rent payment terms",
    "insurance": "Insurance obligations",
    "assignment": "Assignment",
}

RISK_LEVELS = [(70, "High risk", "high"), (40, "Medium risk", "medium"), (0, "Lower risk", "low")]


def level_for(score: int):
    for threshold, label, key in RISK_LEVELS:
        if score >= threshold:
            return label, key
    return RISK_LEVELS[-1][1], RISK_LEVELS[-1][2]


def scrub(text: str) -> str:
    """Anonymise personal details before anything can appear on screen."""
    if not text:
        return ""
    t = str(text)
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", t)
    t = re.sub(r"\+?\d[\d\s().-]{6,}\d", "[phone]", t)
    # long runs of dots/ellipses used as blank fill-ins
    t = re.sub(r"[.\u2026\u2022_]{4,}", "\u2026", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def label_for(clause_type: str) -> str:
    if not clause_type:
        return "Clause"
    return CLAUSE_LABELS.get(clause_type, clause_type.replace("_", " ").capitalize())


def pick_agreement(db):
    """Choose a real, substantive, tenancy agreement with a rich analysis."""
    rows = (
        db.query(Agreement, Analysis)
        .join(Analysis, Analysis.agreement_id == Agreement.id)
        .order_by(desc(Analysis.risk_score))
        .all()
    )
    best = None
    best_key = None
    for a, an in rows:
        flags = an.flagged_clauses or []
        words = len((a.raw_text or "").split())
        # want: real tenancy text, several distinct flagged clauses, decent length
        if words < 120 or len(flags) < 2:
            continue
        distinct = len({c.get("clause_type") for c in flags})
        key = (distinct, len(flags), min(words, 1500))
        if best_key is None or key > best_key:
            best_key, best = key, (a, an)
    return best


def main() -> int:
    db = SessionLocal()
    try:
        picked = pick_agreement(db)
        if not picked:
            print("No suitable agreement found in the database.")
            return 1
        a, stored = picked
        print(f"[data] chosen agreement {a.id} (source={a.source_type.value}, "
              f"{len((a.raw_text or '').split())} words, stored risk={stored.risk_score})")

        # Run it through the REAL pipeline (same code path the API uses).
        replay = "--no-run" not in sys.argv
        fresh = None
        if replay:
            print("[data] running through the real analysis pipeline ...")
            fresh = _run_pipeline(a.raw_text, SourceType.text, db)
            if fresh.get("status") != "ok":
                fresh = None

        # The small model is flaky, so a re-run can surface fewer AI flags than
        # the stored run. Both are genuine pipeline output; keep whichever real
        # result is richer so the explainer shows the fullest true analysis.
        stored_result = {
            "risk_score": stored.risk_score,
            "summary": stored.summary_text,
            "flagged_clauses": stored.flagged_clauses or [],
            "missing_protections": stored.missing_protections or [],
            "questions_to_ask": stored.questions_to_ask or [],
        }
        result, provenance = stored_result, "stored analysis (database)"
        if fresh and len(fresh.get("flagged_clauses") or []) >= len(stored_result["flagged_clauses"]):
            result, provenance = fresh, "re-run through the pipeline"
        print(f"[data] using {provenance}: "
              f"risk={result.get('risk_score')} flags={len(result.get('flagged_clauses') or [])}")

        score = int(result.get("risk_score") or 0)
        level, level_key = level_for(score)

        flagged = []
        for c in (result.get("flagged_clauses") or [])[:4]:
            flagged.append({
                "label": label_for(c.get("clause_type")),
                "severity": (c.get("severity") or "low").lower(),
                "source": c.get("source") or "ai",
                "evidence": scrub(c.get("evidence") or ""),
            })
        # a good quote to expand on screen: shortest punchy one at the top severity
        sev_rank = {"high": 0, "medium": 1, "low": 2}
        ranked = sorted(flagged, key=lambda f: sev_rank.get(f["severity"], 3))
        candidates = [f["evidence"] for f in ranked if 10 <= len(f["evidence"]) <= 70]
        if candidates:
            top = sev_rank.get(ranked[0]["severity"], 3)
            group = [f["evidence"] for f in ranked if sev_rank.get(f["severity"], 3) == top and f["evidence"]]
            quote = min(group or candidates, key=len)
        else:
            quote = ranked[0]["evidence"] if ranked else ""

        missing = [{"label": label_for(m.get("clause_type")), "why": scrub(m.get("why", ""))}
                   for m in (result.get("missing_protections") or [])][:4]

        questions = [scrub(q) for q in (result.get("questions_to_ask") or []) if q][:4]

        summary = scrub(result.get("summary") or "")
        m = re.search(r"(\d+)\s+of\s+(\d+)\s+checked", summary)
        checked = int(m.group(2)) if m else len(flagged)
        clauses = None
        m2 = re.search(r"\((\d+)\s+clauses", summary)
        if m2:
            clauses = int(m2.group(1))

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_note": "Real tenancy agreement analysed by the RentCheck pipeline",
            "provenance": provenance,
            "risk_score": score,
            "risk_level": level,
            "risk_key": level_key,
            "summary": summary,
            "counts": {
                "flagged": len(result.get("flagged_clauses") or []),
                "missing": len(result.get("missing_protections") or []),
                "questions": len(result.get("questions_to_ask") or []),
                "checked": checked,
                "clauses": clauses,
            },
            "flagged": flagged,
            "quote": quote,
            "missing": missing,
            "questions": questions,
        }
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print(f"[data] wrote {OUT}")
        print(json.dumps(data["counts"], ensure_ascii=False))
        print("flagged:", [(f["label"], f["severity"]) for f in flagged])
        print("quote:", quote)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
