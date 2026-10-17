"""
Decide whether an input actually IS a tenancy agreement, before we analyse it.

This runs at the very start of the pipeline (paste, PDF, image, .txt, .docx).
Without it, a random photo or an unrelated contract still produced "flagged
clauses" because the clause pipeline happily matched anything against the
clause norms.

Design:
- Deterministic first. Most inputs are obvious (a real lease teems with words
  like "landlord", "tenant", "demised premises"; a receipt or a selfie has
  none), so we decide those from text volume + keyword signals with no AI call.
- Only genuinely ambiguous text is sent to the model, in ONE call that returns
  {document_type, confidence, reason}. If the model is unavailable we fall back
  to the keyword signal rather than failing the request.
"""
import json
import re

from app.models.db import SourceType
from app.services.ai_inference import (
    RUMPTY_AI_BASE_URL,
    RUMPTY_AI_MODEL,
    _post_with_retries,
)

TENANCY_AGREEMENT = "tenancy_agreement"
NOT_TENANCY_AGREEMENT = "not_tenancy_agreement"
UNREADABLE = "unreadable"

# Below this, we treat the old 0.6 rule from the spec as "not confident enough".
CONFIDENCE_THRESHOLD = 0.6

# Fewer words than this and there is not enough to judge.
MIN_WORDS = 8

# Character budget for the excerpt we send to the model.
EXCERPT_CHARS = 1800

# How far into the document we look for a *title* signal. Real agreements
# announce themselves ("DEED OF LEASE", "ASSURED SHORTHOLD TENANCY AGREEMENT",
# "LICENCE TO OCCUPY", "CONTRAT DE LOCATION"). Financial/employment contracts
# often mention "lease"/"landlord" in their body, so requiring a title signal
# before a deterministic accept stops those being waved through.
TITLE_CHARS = 400

# Signals that a document is about renting a home. Single words are matched on
# word boundaries (so "lease" does not match "release"); phrases are substrings.
STRONG_SIGNALS = [
    "tenancy",
    "landlord",
    "tenant",
    "lease",
    "lessor",
    "lessee",
    "demised premises",
    "deed of lease",
    "rental agreement",
    "tenancy agreement",
    "sublease",
    "sub-lease",
    "quit notice",
    "rent hereby",
    "monthly rent",
    "annual rent",
    "yearly rent",
    # Nigerian forms (Lagos tenancy law etc.)
    "licence to occupy",
    "license to occupy",
    "leave and license",
    "leave and licence",
    "tenancy at will",
    "yearly tenancy",
    "annual tenancy",
    "periodic tenancy",
    # Other common forms
    "assured shorthold",
    "shorthold tenancy",
    "protected tenancy",
    # French (bail / contrat de location)
    "contrat de location",
    "bail d habitation",
    "bailleur",
    "locataire",
    # Spanish (contrato de arrendamiento / alquiler)
    "contrato de arrendamiento",
    "arrendamiento",
    "arrendador",
    "arrendatario",
    "alquiler",
    # German (Mietvertrag)
    "mietvertrag",
    "vermieter",
    "mieter",
    "wohnung",
    "mietzins",
    "untermiete",
]

SUPPORT_SIGNALS = [
    "rent",
    "premises",
    "covenant",
    "arrears",
    "forfeiture",
    "re-entry",
    "reentry",
    "sublet",
    "caution fee",
    "service charge",
    "hereby",
    "dwelling",
    "occupier",
    "assignment",
    "notice",
]

_SIGNAL_CACHE: dict[tuple[str, ...], list[re.Pattern]] = {}


def classify_document(text: str, source_type: SourceType) -> dict:
    """Return {"document_type", "confidence", "reason"} for the given text.

    `source_type` matters only to distinguish OCR'd images (where short/garbled
    text means "unreadable") from digital documents (where short text just means
    "not a tenancy agreement").
    """
    normalised = _normalise(text or "")
    words = normalised.split()
    is_image = source_type == SourceType.image

    if len(words) < MIN_WORDS:
        if is_image:
            return _verdict(UNREADABLE, 0.6, "too little legible text to tell what it is")
        return _verdict(NOT_TENANCY_AGREEMENT, 0.9, "a file that contains almost no text")

    strong, support = _signal_counts(normalised)
    title_strong = _count_terms(normalised[:TITLE_CHARS], STRONG_SIGNALS)

    # Clear-positive: several telling tenancy words AND at least one of them in
    # the title/head (so a finance contract that merely references a lease in
    # its body is not waved through).
    if strong >= 2 and title_strong >= 1:
        return _verdict(TENANCY_AGREEMENT, 0.95, "a rental/tenancy agreement")
    if strong == 1 and support >= 2 and title_strong >= 1:
        return _verdict(TENANCY_AGREEMENT, 0.85, "a rental/tenancy agreement")

    # Clear-negative: no tenancy words at all and nothing that even hints at it.
    ambiguous = (
        strong >= 1
        or support >= 3
        or is_image
        or _looks_non_english(text or "")
    )
    if not ambiguous:
        return _verdict(NOT_TENANCY_AGREEMENT, 0.9, "an unrelated document")

    # Ambiguous: let the model adjudicate (one call).
    llm = _llm_classify(text)
    if llm is None:
        # AI unavailable - fall back to the title signal instead of failing.
        # A real agreement names itself up front; something that only mentions
        # lease words deep in its body is treated as not a tenancy agreement.
        if title_strong >= 1:
            return _verdict(
                TENANCY_AGREEMENT, 0.6, "a rental/tenancy agreement (AI unavailable)"
            )
        return _verdict(NOT_TENANCY_AGREEMENT, 0.7, "an unrelated document (AI unavailable)")

    dtype, confidence, reason = llm

    if dtype == UNREADABLE:
        return _verdict(UNREADABLE, confidence, reason or "too little or garbled text")

    if dtype == TENANCY_AGREEMENT:
        if confidence >= CONFIDENCE_THRESHOLD:
            return _verdict(TENANCY_AGREEMENT, confidence, reason or "a rental/tenancy agreement")
        # Not confident enough to treat as a lease -> reject (per spec).
        return _verdict(
            NOT_TENANCY_AGREEMENT,
            confidence,
            reason or "not clearly a tenancy agreement",
        )

    return _verdict(NOT_TENANCY_AGREEMENT, confidence, reason or "not a tenancy agreement")


def _verdict(document_type: str, confidence: float, reason: str) -> dict:
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "document_type": document_type,
        "confidence": round(confidence, 2),
        "reason": (reason or "").strip(),
    }


def _normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _patterns(terms: tuple[str, ...]) -> list[re.Pattern]:
    cached = _SIGNAL_CACHE.get(terms)
    if cached is None:
        compiled = []
        for term in terms:
            if " " in term:
                compiled.append(re.compile(re.escape(term)))
            else:
                compiled.append(re.compile(r"\b" + re.escape(term) + r"\b"))
        _SIGNAL_CACHE[terms] = compiled
        cached = compiled
    return cached


def _signal_counts(normalised: str) -> tuple[int, int]:
    strong = _count_terms(normalised, STRONG_SIGNALS)
    support = _count_terms(normalised, SUPPORT_SIGNALS)
    return strong, support


def _count_terms(normalised: str, terms: list[str]) -> int:
    return sum(1 for p in _patterns(tuple(terms)) if p.search(normalised))


def _looks_non_english(text: str) -> bool:
    """Heuristic: a document with a meaningful run of accented/non-Latin letters
    is probably not English. Its English keyword signals are meaningless, so we
    must not use them to reject it deterministically - send it to the model
    (which reads the actual language) instead.
    """
    foreign = sum(1 for ch in text if ord(ch) > 0x7F and not ch.isspace())
    letters = sum(1 for ch in text if ch.isalpha())
    if letters == 0:
        return False
    return foreign >= 10 and foreign / max(letters, 1) > 0.01


CLASSIFY_PROMPT = """You are a document triage assistant for a service that reviews residential \
tenancy agreements. Decide whether the text below is a residential TENANCY AGREEMENT.

Respond with ONLY this JSON object, no other text:
{{"document_type": "tenancy_agreement" | "not_tenancy_agreement" | "unreadable", "confidence": 0.0, "reason": "what the file appears to be, max 20 words"}}

Definitions:
- tenancy_agreement: a lease, tenancy agreement, deed of lease, rental contract or tenancy renewal between a landlord/lessor and a tenant/lessee about renting premises.
- not_tenancy_agreement: anything else - a photo, receipt, invoice, ID card, chat message, employment letter, other contract type, article, or unrelated text.
- unreadable: too little or too garbled text to tell what the document is.

RULES:
- Do not invent clauses. If the document is not a tenancy agreement, say so and do not analyze it.
- Judge only from the text given.

Text:
\"\"\"{excerpt}\"\"\"

Answer:"""


def _llm_classify(text: str) -> tuple[str, float, str] | None:
    """One model call. Returns (document_type, confidence, reason) or None on failure."""
    excerpt = text.strip()[:EXCERPT_CHARS]
    prompt = CLASSIFY_PROMPT.format(excerpt=excerpt)

    try:
        response = _post_with_retries(
            f"{RUMPTY_AI_BASE_URL}/chat/completions",
            {
                "model": RUMPTY_AI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 120,
            },
        )
        raw = response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # network, auth, timeout - never crash the request
        print(f"[classify] model call failed: {exc}")
        return None

    print(f"[classify] model: {raw}")
    parsed = _extract_json(raw)
    if parsed is None:
        return None

    dtype = str(parsed.get("document_type", "")).strip().lower()
    if dtype not in (TENANCY_AGREEMENT, NOT_TENANCY_AGREEMENT, UNREADABLE):
        return None

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    reason = str(parsed.get("reason", "") or "").strip()
    return dtype, confidence, reason


def _extract_json(raw: str) -> dict | None:
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
