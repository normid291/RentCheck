from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import SourceType, User
from app.services import analysis_store
from app.services.auth import get_current_user
from app.services.clause_splitter import split_into_clauses
from app.services.document_classifier import (
    TENANCY_AGREEMENT,
    UNREADABLE,
    classify_document,
)
from app.services.clause_matcher import match_clause
from app.services.ai_inference import analyze_clause
from app.services.protections import find_missing_protections, build_questions
from app.services.red_flags import find_deterministic_flags
from app.services.extractor import extract_text, ExtractionError

router = APIRouter()


class AgreementIn(BaseModel):
    text: str


def _run_pipeline(
    text: str,
    source_type: SourceType,
    db: Session,
    user: User | None = None,
) -> dict:
    """Shared core: classify -> split -> match -> AI-verify -> assemble -> (save).

    Used by both the paste-text endpoint and the file-upload endpoint so the
    analysis path is identical no matter how the text arrived.

    `user` decides whether the result is kept. A signed-in user gets the analysis
    (and the text it came from) stored against their account; a guest gets the
    same result and nothing is written. The response therefore carries `saved`,
    which is what the front end uses to offer "keep this by creating an account".

    Nothing is persisted until the run has fully succeeded, so a failure in the
    middle leaves no half-written analysis and no orphaned agreement text.
    """
    # Gate first: is this even a tenancy agreement? Anything else is rejected
    # with a clean 200 and is NEVER saved, for guests and users alike (so it
    # never counts as one of their analyses either).
    verdict = classify_document(text, source_type)
    if verdict["document_type"] != TENANCY_AGREEMENT:
        return _rejection_response(verdict)

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
    risk_score = min(100, len(flagged) * 15 + len(missing) * 10)
    summary = (
        f"{len(flagged)} of {checked} checked clause(s) flagged, "
        f"{len(missing)} expected protection(s) missing "
        f"({len(clauses)} clauses found in total)."
    )

    # Built from local values, not from a saved row, so guests get exactly the
    # same response without anything being written.
    result = {
        "status": "ok",
        "document_type": TENANCY_AGREEMENT,
        "flagged_clauses": flagged,
        "missing_protections": missing,
        "questions_to_ask": questions,
        "summary": summary,
        "risk_score": risk_score,
        "saved": False,
        "analysis_id": None,
    }

    if user is not None:
        analysis = analysis_store.persist(
            db,
            user,
            text=text,
            source_type=source_type,
            flagged_clauses=flagged,
            missing_protections=missing,
            questions_to_ask=questions,
            risk_score=risk_score,
            summary_text=summary,
        )
        result["saved"] = True
        result["analysis_id"] = str(analysis.id)
        result["title"] = analysis.title
        result["recommendation"] = analysis.recommendation

    return result


def _rejection_response(verdict: dict) -> dict:
    """Build the clean 200 response for a non-tenancy / unreadable input."""
    return _notice_response(
        verdict["document_type"], verdict.get("confidence", 0.0), verdict.get("reason", "")
    )


def _notice_response(document_type: str, confidence: float, reason: str) -> dict:
    """Clean 200 response for a non-tenancy / unreadable input.

    No Agreement or Analysis is written, so a rejected upload is never counted as
    a completed analysis. The clause/protection/question arrays are empty.
    """
    reason = (reason or "").strip().rstrip(".")

    if document_type == UNREADABLE:
        status = "unreadable"
        message = (
            "We couldn't read this file clearly. Please upload a sharper photo or a "
            "PDF/text version of your tenancy agreement."
        )
    else:
        status = "not_a_tenancy_agreement"
        message = "This doesn't look like a tenancy agreement."
        if reason:
            message += f" It looks like {_as_noun_phrase(reason)}."
        message += (
            " Please upload your actual tenancy agreement, lease, or rental contract."
        )

    return {
        "status": status,
        "document_type": document_type,
        "confidence": confidence,
        "reason": reason,
        "message": message,
        "flagged_clauses": [],
        "missing_protections": [],
        "questions_to_ask": [],
    }


def _as_noun_phrase(reason: str) -> str:
    """Make a model "reason" read naturally after "It looks like ...".

    The model answers variably: sometimes a noun phrase ("a receipt"), sometimes
    a predicate ("contains a receipt"), sometimes a meta phrase ("text appears to
    be a receipt"). Normalise the common forms.
    """
    import re

    reason = reason.strip()
    reason = re.sub(
        r"^(?:the\s+)?(?:text|document|file|content|image|photo)?\s*appears?\s+to\s+be\s+",
        "",
        reason,
        flags=re.IGNORECASE,
    ).strip()
    reason = re.sub(
        r"^(?:this|it|the\s+document|the\s+file|the\s+text)\s+(?:looks|seems)\s+(?:like|to\s+be)\s+",
        "",
        reason,
        flags=re.IGNORECASE,
    ).strip()

    if not reason:
        return "not a tenancy agreement"

    first = reason.split(" ", 1)[0].lower()
    if first in {
        "a", "an", "the", "it", "this", "that", "one", "some",
        "your", "my", "his", "her", "their", "not", "just",
    }:
        return reason
    # Some models answer with a bare noun ("photo of a landscape",
    # "receipt from a supermarket") that needs an article.
    if first in {
        "photo", "picture", "screenshot", "screen", "scan", "receipt",
        "invoice", "letter", "form", "page", "article", "id", "resume",
        "cv", "menu", "ticket", "poster", "meme", "note", "list", "chat",
    }:
        article = "an" if first[0] in "aeiou" else "a"
        return article + " " + reason
    return "it " + reason


@router.post("/agreements/analyze")
def analyze_agreement(
    payload: AgreementIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """
    Plain text in, structured analysis out.
    Pipeline: split into clauses -> match each against clause_reference ->
    send only the matched, narrow context to the AI model -> assemble result.
    Then deterministically derive missing protections and questions to ask.

    Signed in? The result is saved to the caller's history. Guest? Same result,
    nothing stored — the response's `saved` flag says which.
    """
    return _run_pipeline(payload.text, SourceType.text, db, user)


@router.post("/agreements/analyze-upload")
async def analyze_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """
    PDF / Word (.docx) / image / text file in, same structured analysis out.

    The file is turned into text by app/services/extractor.py (pypdf for PDFs,
    python-docx for Word documents, Tesseract for images), then run through the
    exact same pipeline as paste. The file itself is never written to disk.
    """
    data = await file.read()

    try:
        text = extract_text(data, file.content_type or "", file.filename or "")
    except ExtractionError as exc:
        # A file we simply could not read (blank/blurry photo, empty scan) is a
        # friendly "unreadable" notice, not an error. Everything else keeps its
        # own status: 400 bad/empty file, 413 too large, 500 missing engine.
        if exc.unreadable:
            return _notice_response(UNREADABLE, 0.6, "no readable text")
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if not text.strip():
        return _notice_response(UNREADABLE, 0.6, "no readable text")

    source_type = _source_type_for(file.content_type or "", file.filename or "")
    return _run_pipeline(text, source_type, db, user)


def _source_type_for(content_type: str, filename: str) -> SourceType:
    content_type = content_type.lower()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if content_type == "application/pdf" or ext == "pdf":
        return SourceType.pdf
    if (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or ext == "docx"
    ):
        return SourceType.docx
    if content_type.startswith("image/") or ext in {"png", "jpg", "jpeg", "webp", "bmp", "tiff"}:
        return SourceType.image
    return SourceType.text
