from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import Agreement, Analysis, SourceType
from app.services.clause_splitter import split_into_clauses
from app.services.clause_matcher import match_clause
from app.services.ai_inference import analyze_clause
from app.services.protections import find_missing_protections, build_questions
from app.services.red_flags import find_deterministic_flags
from app.services.extractor import extract_text, ExtractionError

router = APIRouter()


class AgreementIn(BaseModel):
    text: str


def _run_pipeline(text: str, source_type: SourceType, db: Session) -> dict:
    """Shared core: split -> match -> AI-verify -> assemble -> persist.

    Used by both the paste-text endpoint and the file-upload endpoint so the
    analysis path is identical no matter how the text arrived.
    """
    agreement = Agreement(source_type=source_type, raw_text=text)
    db.add(agreement)
    db.commit()
    db.refresh(agreement)

    clauses = split_into_clauses(text)

    flagged = []
    checked = 0
    present_types: set[str] = set()
    for clause_text in clauses:
        reference = match_clause(clause_text, db)
        if reference is None:
            continue  # no known norm to check this clause against yet
        # Record that this clause type appears at all, even if the AI call
        # later fails: the protection is present, not missing.
        present_types.add(reference.clause_type)

        # Deterministic first: if a known high-confidence trap is present, take
        # that verdict and skip the slow, flaky model call for this clause.
        rule_flags = find_deterministic_flags(clause_text, reference.clause_type)
        if rule_flags:
            checked += 1
            flagged.extend(rule_flags)
            continue

        try:
            verdict = analyze_clause(clause_text, reference)
        except Exception as exc:  # one failed AI call must not kill the whole analysis
            print(f"[analyze] AI call failed for {reference.clause_type}: {exc}")
            continue
        checked += 1
        if verdict.get("flag"):
            flagged.append(verdict)

    missing = find_missing_protections(present_types)
    questions = build_questions(flagged, missing)

    analysis = Analysis(
        agreement_id=agreement.id,
        flagged_clauses=flagged,
        missing_protections=missing,
        questions_to_ask=questions,
        risk_score=min(100, len(flagged) * 15 + len(missing) * 10),
        summary_text=(
            f"{len(flagged)} of {checked} checked clause(s) flagged, "
            f"{len(missing)} expected protection(s) missing "
            f"({len(clauses)} clauses found in total)."
        ),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {
        "agreement_id": str(agreement.id),
        "analysis_id": str(analysis.id),
        "flagged_clauses": analysis.flagged_clauses,
        "missing_protections": analysis.missing_protections,
        "questions_to_ask": analysis.questions_to_ask,
        "summary": analysis.summary_text,
        "risk_score": analysis.risk_score,
    }


@router.post("/agreements/analyze")
def analyze_agreement(payload: AgreementIn, db: Session = Depends(get_db)):
    """
    Plain text in, structured analysis out.
    Pipeline: split into clauses -> match each against clause_reference ->
    send only the matched, narrow context to the AI model -> assemble result.
    Then deterministically derive missing protections and questions to ask.
    """
    return _run_pipeline(payload.text, SourceType.text, db)


@router.post("/agreements/analyze-upload")
async def analyze_upload(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """
    PDF / image / text file in, same structured analysis out.

    The file is turned into text by app/services/extractor.py (pypdf for PDFs,
    Tesseract for images), then run through the exact same pipeline as paste.
    """
    data = await file.read()

    try:
        text = extract_text(data, file.content_type or "", file.filename or "")
    except ExtractionError as exc:
        # ExtractionError carries its own status: 400 bad/empty file,
        # 413 too large, 500 when the PDF/OCR engine is missing.
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text could be read from the file.")

    source_type = _source_type_for(file.content_type or "", file.filename or "")
    return _run_pipeline(text, source_type, db)


def _source_type_for(content_type: str, filename: str) -> SourceType:
    content_type = content_type.lower()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if content_type == "application/pdf" or ext == "pdf":
        return SourceType.pdf
    if content_type.startswith("image/") or ext in {"png", "jpg", "jpeg", "webp", "bmp", "tiff"}:
        return SourceType.image
    return SourceType.text
