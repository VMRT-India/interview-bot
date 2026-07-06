import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts plain text from a PDF's pages, joined with blank lines.

    Raises ValueError (not pypdf's own exception types) so callers can map this
    to a single, predictable 422 without importing pypdf themselves.
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc

    text = "\n\n".join(p.strip() for p in pages if p.strip())
    if not text:
        raise ValueError("PDF contains no extractable text")
    return text
