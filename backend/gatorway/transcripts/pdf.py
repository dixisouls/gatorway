"""PDF -> text, locally. A PDF with no extractable text (a scan) is rejected: there is no OCR (D13)."""
from __future__ import annotations

import io
import logging

import pdfplumber


log = logging.getLogger(__name__)


class NoTextError(ValueError):
    pass


def extract_text(pdf_bytes: bytes, min_chars: int = 40) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    pages.append(page.extract_text(layout=True) or "")  # layout keeps the table columns (course | title | grade) apart
                except Exception as e:  # one bad page must not lose the whole transcript
                    log.warning("could not read PDF page %d: %s", i, e)
                    pages.append("")
    except Exception as e:  # corrupt / not a PDF
        raise NoTextError(f"could not read PDF: {e}") from e
    text = "\n\n".join(p for p in pages if p).strip()
    if len(text) < min_chars:
        raise NoTextError("no extractable text in PDF (scanned transcripts are not supported)")
    return text
