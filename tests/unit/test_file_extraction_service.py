from unittest.mock import MagicMock, patch

import pytest

from services.file_extraction_service import extract_text_from_pdf


def _mock_reader(pages_text: list[str]):
    reader = MagicMock()
    pages = []
    for text in pages_text:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)
    reader.pages = pages
    return reader


def test_extract_text_from_pdf_joins_pages():
    with patch(
        "services.file_extraction_service.PdfReader",
        return_value=_mock_reader(["Page one text.", "Page two text."]),
    ):
        result = extract_text_from_pdf(b"fake-pdf-bytes")
    assert "Page one text." in result
    assert "Page two text." in result


def test_extract_text_from_pdf_skips_blank_pages():
    with patch(
        "services.file_extraction_service.PdfReader",
        return_value=_mock_reader(["", "Real content.", "   "]),
    ):
        result = extract_text_from_pdf(b"fake-pdf-bytes")
    assert result.strip() == "Real content."


def test_extract_text_from_pdf_raises_on_no_extractable_text():
    with patch(
        "services.file_extraction_service.PdfReader",
        return_value=_mock_reader(["", "  ", ""]),
    ):
        with pytest.raises(ValueError, match="no extractable text"):
            extract_text_from_pdf(b"fake-pdf-bytes")


def test_extract_text_from_pdf_raises_on_unreadable_pdf():
    from pypdf.errors import PdfReadError

    with patch(
        "services.file_extraction_service.PdfReader",
        side_effect=PdfReadError("corrupt"),
    ):
        with pytest.raises(ValueError, match="Could not read PDF"):
            extract_text_from_pdf(b"not-a-pdf")
