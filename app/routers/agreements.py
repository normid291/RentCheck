import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

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
from app.services.clause_matcher import load_norms, match_clause
from app.services.ai_inference import RUMPTY_AI_MODEL, analyze_clause
from app.services.jurisdiction import NON_NG, UNKNOWN, is_nigerian
from app.services.protections import find_missing_protections, build_questions
from app.services.red_flags import find_deterministic_flags
from app.services.scoring import Coverage, coverage_note, risk_band, risk_score
from app.services.extractor import extract_text, ExtractionError

router = APIRouter()

logger = logging.getLogger("tenura.analyze")

# Provenance stamped on every stored analysis, so an old result can always be
# tied to the pipeline/prompt/model that produced it.
PIPELINE_VERSION = "2"
PROMPT_VERSION = "2"
CLAUSE_REFERENCE_VERSION = "1"

# Cap on an uploaded file, enforced while reading so a huge upload cannot be
# buffered into memory. 15 MB comfortably fits a photographed lease.
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))


class AgreementIn(BaseModel):
    text: str


def _attach_norm(verdict: dict, norm) -> dict:
    """Copy the norm's guidance onto a flag, so each flag can stand alone in the
    UI: what it means, a fair counter-clause, and a question to ask."""
    enriched = dict(verdict)
    enriched["jurisdiction"] = norm.jurisdiction
    enriched["legal_basis"] = norm.legal_basis
    enriched["consequence"] = norm.consequence
    enriched["counter_clause"] = norm.counter_clause
    enriched["tenant_question"] = norm.tenant_question
    return enriched


def _run_pipeline(
    text: str,
    source_type: SourceType,
    db: Session,
    user: User | None = None,
) -> dict:
    """Shared core: classify -> jurisdiction gate -> split -> match -> AI-verify
    -> assemble -> (save).

    Used by both the paste-text endpoint and the file-upload endpoint so the
    analysis path is identical no matter how the text arrived.

    `user` decides whether the result is kept. A signed-in user gets the analysis
    (and the text it came from) stored against their account; a guest gets the
    same result and nothing is written. The response therefore carries `saved`,
    which is what the front end uses to offer "keep this by creating an account".

    Jurisdiction gate: a clearly non-Nigerian agreement is refused with a clean
    200 (`status="out_of_scope"`) and is NEVER saved; an agreement whose
    jurisdiction cannot be told is met with `status="needs_jurisdiction"` so the
    user can say where it is from. Only an NG-* agreement is judged, and it is
    judged against the norms for that jurisdiction.

    Nothing is persisted until the run has fully succeeded, so a failure in the
    middle leaves no half-written analysis and no orphaned agreement text.
    """
    # Gate first: is this even a tenancy agreement? Anything else is rejected
    # with a clean 200 and is NEVER saved, for guests and users alike (so it
    # never counts as one of their analyses either).
    verdict = classify_document(text, source_type)
    if verdict["document_type"] != TENANCY_AGREEMENT:
        return _rejection_response(verdict)

    # Second gate: whose norms apply? Never silently judge a foreign agreement
    # with Nigerian norms.
    jurisdiction = verdict.get("jurisdiction", UNKNOWN)
    if not is_nigerian(jurisdiction):
        return _jurisdiction_response(verdict, jurisdiction)

    # Load the norms (ORM access) and detach them, then end the read
    # transaction: the database connection is released BEFORE the slow AI calls,
    # so a request does not sit on a pooled connection waiting on the model.
    norms = load_norms(db)
    db.rollback()

    clauses = split_into_clauses(text)

    flagged: list[dict] = []
    checked = 0
    matched = 0
    present_types: set[str] = set()
    degraded = False
    for clause_text in clauses:
        norm = match_clause(clause_text, norms, jurisdiction)
        if norm is None:
            continue  # no known norm to check this clause against yet
        matched += 1
        # Record that this clause type appears at all, even if the AI call
        # later fails: the protection is present, not missing.
        present_types.add(norm.clause_type)

        # Deterministic first: if a known high-confidence trap is present, take
        # that verdict and skip the slow, flaky model call for this clause.
        rule_flags = find_deterministic_flags(clause_text, norm.clause_type)
        if rule_flags:
            checked += 1
            flagged.extend(_attach_norm(flag, norm) for flag in rule_flags)
            continue

        try:
            clause_verdict = analyze_clause(clause_text, norm)
        except Exception as exc:  # one failed AI call must not kill the whole analysis
            logger.warning(
                "AI call failed for clause type %s (%s)",
                norm.clause_type,
                type(exc).__name__,
            )
            degraded = True
            continue
        # A verdict that could not be evaluated is a gap in coverage, not a pass.
        if not clause_verdict.get("evaluated", False):
            degraded = True
            continue
        checked += 1
        if clause_verdict.get("flag"):
            flagged.append(_attach_norm(clause_verdict, norm))

    missing = find_missing_protections(present_types)
    questions = build_questions(flagged, missing)
    coverage = Coverage(
        total_clauses=len(clauses),
        matched_clauses=matched,
        evaluated_clauses=checked,
        degraded=degraded,
    )
    score = risk_score(flagged, missing)
    band = risk_band(score, coverage)
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
        "jurisdiction": jurisdiction,
        "flagged_clauses": flagged,
        "missing_protections": missing,
        "questions_to_ask": questions,
        "summary": summary,
        "risk_score": score,
        "risk_band": band,
        "coverage": coverage.fraction,
        "coverage_note": coverage_note(coverage),
        "degraded": coverage.degraded,
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
            risk_score=score,
            summary_text=summary,
            jurisdiction=jurisdiction,
            coverage=coverage.fraction,
            degraded=coverage.degraded,
            pipeline_version=PIPELINE_VERSION,
            prompt_version=PROMPT_VERSION,
            model_id=RUMPTY_AI_MODEL,
            clause_reference_version=CLAUSE_REFERENCE_VERSION,
        )
        result["saved"] = True
        result["analysis_id"] = str(analysis.id)
        result["title"] = analysis.title
        result["recommendation"] = analysis.recommendation

    return result


def _jurisdiction_response(verdict: dict, jurisdiction: str) -> dict:
    """Clean 200 for an out-of-scope or unknown jurisdiction (never saved)."""
    if jurisdiction == NON_NG:
        status = "out_of_scope"
        message = (
            "This looks like a tenancy agreement from outside Nigeria. Tenura "
            "only reviews Nigerian tenancy agreements, and judging it against "
            "Nigerian rules would be misleading. If it is a Nigerian agreement, "
            "re-upload a version that names the Nigerian state or shows the rent "
            "in naira."
        )
    else:
        status = "needs_jurisdiction"
        message = (
            "We couldn't tell which country this agreement is for. Tenura only "
            "reviews Nigerian tenancy agreements. If this is a Nigerian "
            "agreement, add the state (for example Lagos or Abuja) or state the "
            "rent in naira, and try again."
        )

    return {
        "status": status,
        "document_type": verdict.get("document_type", TENANCY_AGREEMENT),
        "jurisdiction": jurisdiction,
        "jurisdiction_confidence": verdict.get("jurisdiction_confidence", 0.0),
        "jurisdiction_evidence": verdict.get("jurisdiction_evidence", []),
        "message": message,
        "flagged_clauses": [],
        "missing_protections": [],
        "questions_to_ask": [],
        "coverage": 0.0,
        "degraded": False,
        "saved": False,
        "analysis_id": None,
    }


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

    The read is capped so an oversized upload cannot be buffered into memory,
    and the blocking extraction + AI work runs in a worker thread so it does not
    stall the event loop.
    """
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. The limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    def _extract() -> str:
        return extract_text(data, file.content_type or "", file.filename or "")

    try:
        text = await run_in_threadpool(_extract)
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
    return await run_in_threadpool(_run_pipeline, text, source_type, db, user)


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
