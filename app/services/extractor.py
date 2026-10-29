"""
Week 3: turn uploaded PDFs / Word docs / images / text into plain text for the
analysis pipeline.

Design notes:
- PDF: pypdf pulls the text layer. Typed/digital PDFs work directly. A scanned
  PDF (no text layer) is rasterised with pypdfium2 and run through Tesseract OCR.
- DOCX: python-docx reads the paragraph/table text out of the Word XML.
- Image: pytesseract + Pillow, which need the Tesseract binary installed.
- All optional libraries are imported LAZILY, inside the functions. That keeps
  the app importable and deployable even when a format's stack is not present;
  the caller just gets a clear ExtractionError instead of an ImportError at
  startup.
"""
import io

# Guard against absurd uploads before we spend CPU on them.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

# OCR is CPU-heavy; cap how much of a scanned PDF we rasterise per request.
OCR_DPI = 200
MAX_OCR_PAGES = 25

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOCX_EXTS = {"docx"}
IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"}
TEXT_EXTS = {"txt", "md", "markdown"}


class ExtractionError(Exception):
    """Raised when an upload cannot be turned into usable text. The message is
    safe to show to the user, and `status_code` lets the router return the right
    HTTP status (400 for a bad/empty file, 413 for too large, 502 when the OCR
    engine itself is unavailable).

    `unreadable=True` marks the specific case where the file is a legitimate
    upload we simply could not read (a blank/blurry photo, a scan with no text):
    the router turns this into a friendly "we couldn't read this" notice rather
    than an error.
    """

    def __init__(self, message: str, status_code: int = 400, unreadable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.unreadable = unreadable


def extract_text(data: bytes, content_type: str, filename: str = "") -> str:
    """Dispatch on content type / extension and return extracted plain text."""
    if not data:
        raise ExtractionError("The uploaded file is empty.", status_code=400)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ExtractionError(
            f"The uploaded file is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
            status_code=413,
        )

    kind = _classify(content_type, filename)

    if kind == "pdf":
        return _extract_pdf(data)
    if kind == "docx":
        return _extract_docx(data)
    if kind == "image":
        return _extract_image(data)
    if kind == "text":
        return _extract_plain(data)

    if kind == "doc":
        raise ExtractionError(
            "Legacy .doc files are not supported. Save the document as .docx or "
            "PDF and try again.",
            status_code=400,
        )

    raise ExtractionError(
        "Unsupported file type. Upload a PDF, a Word document (.docx), an image "
        "(PNG/JPG/WEBP), or a .txt file.",
        status_code=400,
    )


def _classify(content_type: str, filename: str) -> str:
    content_type = (content_type or "").lower()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if content_type == "application/pdf" or ext == "pdf":
        return "pdf"
    if content_type == DOCX_MIME or ext in DOCX_EXTS:
        return "docx"
    if ext == "doc":  # legacy binary Word — give a specific, helpful error
        return "doc"
    if content_type.startswith("image/") or ext in IMAGE_EXTS:
        return "image"
    if content_type.startswith("text/") or ext in TEXT_EXTS:
        return "text"
    return "unknown"


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # optional dependency not installed
        raise ExtractionError(
            "PDF support is not installed on the server (pip install pypdf).",
            status_code=500,
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise ExtractionError("Could not read the uploaded PDF.", status_code=400) from exc

    text = "\n\n".join(p.strip() for p in pages if p and p.strip())
    if text.strip():
        return text

    # No text layer -> likely a scan. Fall back to OCR.
    return _ocr_pdf(data)


def _ocr_pdf(data: bytes) -> str:
    """Rasterise a (scanned) PDF and OCR each page with Tesseract.

    Uses pypdfium2 (pip-only, no Poppler/ghostscript needed) to render pages.
    """
    try:
        import pypdfium2 as pdfium
        import pytesseract
        from PIL import Image  # noqa: F401  (availability probe for the OCR stack)
    except ImportError as exc:  # optional OCR stack not installed
        raise ExtractionError(
            "This PDF has no selectable text (it looks like a scan) and server-side "
            "PDF OCR is not installed. Try uploading the scan as an image, or paste "
            "the text.",
            status_code=400,
        ) from exc

    _configure_tesseract(pytesseract)

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:
        raise ExtractionError("Could not read the uploaded PDF.", status_code=400) from exc

    scale = OCR_DPI / 72.0
    pages_text: list[str] = []
    try:
        for index in range(min(len(pdf), MAX_OCR_PAGES)):
            page = pdf[index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            page_text = pytesseract.image_to_string(image)
            if page_text and page_text.strip():
                pages_text.append(page_text.strip())
    except Exception as exc:
        message = str(exc).lower()
        if "tesseract" in message or "not found" in message:
            raise ExtractionError(
                "The OCR engine (Tesseract) is not available on the server.",
                status_code=500,
            ) from exc
        raise ExtractionError(
            "Could not OCR the scanned PDF on the server.", status_code=400
        ) from exc
    finally:
        try:
            pdf.close()
        except Exception:
            pass

    text = "\n\n".join(pages_text)
    if not text.strip():
        raise ExtractionError(
            "No readable text was found in this scanned PDF. Try a clearer scan or "
            "photo of the document, or paste the text.",
            status_code=400,
            unreadable=True,
        )
    return text


def _extract_docx(data: bytes) -> str:
    """Pull paragraph and table text out of a .docx (Office Open XML) file."""
    try:
        import docx  # provided by the python-docx package
    except ImportError as exc:  # optional dependency not installed
        raise ExtractionError(
            "Word (.docx) support is not installed on the server "
            "(pip install python-docx).",
            status_code=500,
        ) from exc

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError(
            "Could not read the uploaded Word document. If it is an old .doc file, "
            "save it as .docx or PDF first.",
            status_code=400,
        ) from exc

    parts = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    text = "\n".join(parts)
    if not text.strip():
        raise ExtractionError(
            "No text was found in the Word document. If the agreement is an image "
            "inside the file, try uploading it as a PDF or image instead.",
            status_code=400,
        )
    return text


def _extract_image(data: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # optional OCR dependency not installed
        raise ExtractionError(
            "Image OCR is not installed on the server "
            "(pip install pytesseract Pillow, and install Tesseract).",
            status_code=500,
        ) from exc

    _configure_tesseract(pytesseract)

    try:
        image = Image.open(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("Could not read the uploaded image.", status_code=400) from exc

    try:
        text = pytesseract.image_to_string(image)
    except Exception as exc:
        # Most commonly: the Tesseract binary is not on PATH.
        raise ExtractionError(
            "The OCR engine (Tesseract) is not available on the server.",
            status_code=500,
        ) from exc

    if not text.strip():
        raise ExtractionError(
            "No readable text was found in the image. Try a clearer photo of the document.",
            status_code=400,
            unreadable=True,
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
    raise ExtractionError("Could not decode the uploaded text file.", status_code=400)
