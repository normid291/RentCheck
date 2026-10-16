"""
Week 3: turn uploaded PDFs / images into plain text for the analysis pipeline.

Design notes:
- PDF: pypdf pulls the text layer. Typed/digital PDFs work directly; a scanned
  PDF has no text layer and is rejected with a helpful message (we cannot render
  PDF pages to images without a heavier dependency like pdf2image + poppler).
- Image: pytesseract + Pillow, which need the Tesseract binary installed.
- Both are imported LAZILY, inside the functions. That keeps the app importable
  and deployable even when the optional OCR stack is not present; the caller
  just gets a clear ExtractionError instead of an ImportError at startup.
"""
import io

# Guard against absurd uploads before we spend CPU on them.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


class ExtractionError(Exception):
    """Raised when an upload cannot be turned into usable text. The message is
    safe to show to the user."""


def extract_text(data: bytes, content_type: str, filename: str = "") -> str:
    """Dispatch on content type / extension and return extracted plain text."""
    if not data:
        raise ExtractionError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ExtractionError("The uploaded file is too large (max 15 MB).")

    kind = _classify(content_type, filename)

    if kind == "pdf":
        return _extract_pdf(data)
    if kind == "image":
        return _extract_image(data)
    if kind == "text":
        return _extract_plain(data)

    raise ExtractionError(
        "Unsupported file type. Upload a PDF, an image (PNG/JPG), or a .txt file."
    )


def _classify(content_type: str, filename: str) -> str:
    content_type = (content_type or "").lower()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if content_type == "application/pdf" or ext == "pdf":
        return "pdf"
    if content_type.startswith("image/") or ext in {"png", "jpg", "jpeg", "webp", "bmp", "tiff"}:
        return "image"
    if content_type.startswith("text/") or ext in {"txt", "md"}:
        return "text"
    return "unknown"


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # optional dependency not installed
        raise ExtractionError(
            "PDF support is not installed on the server (pip install pypdf)."
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise ExtractionError("Could not read the uploaded PDF.") from exc

    text = "\n\n".join(p.strip() for p in pages if p and p.strip())
    if not text.strip():
        raise ExtractionError(
            "This PDF has no selectable text (it looks like a scan). "
            "Try uploading it as an image instead, or paste the text."
        )
    return text


def _extract_image(data: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # optional OCR dependency not installed
        raise ExtractionError(
            "Image OCR is not installed on the server "
            "(pip install pytesseract Pillow, and install Tesseract)."
        ) from exc

    _configure_tesseract(pytesseract)

    try:
        image = Image.open(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("Could not read the uploaded image.") from exc

    try:
        text = pytesseract.image_to_string(image)
    except Exception as exc:
        # Most commonly: the Tesseract binary is not on PATH.
        raise ExtractionError(
            "The OCR engine (Tesseract) is not available on the server."
        ) from exc

    if not text.strip():
        raise ExtractionError(
            "No readable text was found in the image. Try a clearer photo of the document."
        )
    return text


def _configure_tesseract(pytesseract) -> None:
    """Point pytesseract at the Tesseract binary.

    Honors a TESSERACT_CMD env var, then falls back to the default Windows
    install location (the installer does not add it to PATH). Does nothing on
    Linux/macOS where `tesseract` is normally already on PATH.
    """
    import os

    configured = os.environ.get("TESSERACT_CMD")
    if configured:
        pytesseract.pytesseract.tesseract_cmd = configured
        return

    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return
    # Otherwise rely on the binary being on PATH.


def _extract_plain(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Could not decode the uploaded text file.")
