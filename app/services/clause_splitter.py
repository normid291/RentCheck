import re


def split_into_clauses(raw_text: str) -> list[str]:
    """
    Splits a tenancy agreement into individual clauses using simple
    structural rules — numbered sections, line breaks on blank lines.
    Deliberately NOT using AI here: this is a mechanical text-processing
    step and keeping it deterministic means one less place for the small
    model to introduce errors.
    """
    text = raw_text.strip()

    # Try splitting on numbered clauses first: "1.", "2)", "Clause 3:", etc.
    numbered_pattern = re.compile(
        r"(?:^|\n)\s*(?:\d{1,2}[\.\)]|Clause\s+\d{1,2}[:\.])\s+", re.IGNORECASE
    )
    parts = numbered_pattern.split(text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) >= 3:  # looks like numbered clauses worked
        return _split_nested_subclauses(parts)

    # Fallback: split on blank-line-separated paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if paragraphs:
        return paragraphs

    # Last resort: treat the whole thing as one clause
    return [text]


def _split_nested_subclauses(parts: list[str]) -> list[str]:
    """
    Some agreements nest covenants under a single numbered clause using
    roman-numeral or lettered sub-items: (i), (ii), (iii)... or (a), (b), (c)...
    Found in real Nigerian deed-of-lease templates, where "2. The Tenant
    covenants..." is followed by six separate sub-covenants that each need
    their own clause-matching pass rather than being treated as one blob.
    """
    sub_pattern = re.compile(r"(?:^|\n)\s*\([ivxlcdm]{1,5}\)\s+|(?:^|\n)\s*\([a-z]\)\s+", re.IGNORECASE)

    result = []
    for part in parts:
        sub_parts = sub_pattern.split(part)
        sub_parts = [p.strip() for p in sub_parts if p.strip()]

        if len(sub_parts) >= 2:
            # First sub_part is the intro line ("The Tenant covenants as follows:")
            # — keep it attached to context but treat each sub-item as its own clause.
            result.extend(sub_parts)
        else:
            result.append(part)

    # A "Provided that ..." proviso (re-entry, forfeiture) is a separate legal
    # term, not part of the sub-item written just above it. Split it out so it
    # gets its own check instead of hiding inside the previous clause.
    proviso = re.compile(r"\n\s*(?=Provided\s+(?:always\s+)?that\b)", re.IGNORECASE)
    final = []
    for part in result:
        pieces = [p.strip() for p in proviso.split(part) if p.strip()]
        final.extend(pieces if pieces else [part])
    return final
