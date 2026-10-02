"""PDF -> text, locally. A PDF with no extractable text (a scan) is rejected: there is no OCR (D13)."""
from __future__ import annotations

import io

import pdfplumber


class NoTextError(ValueError):
    pass


def extract_text(pdf_bytes: bytes, min_chars: int = 40) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
    except Exception as e:  # corrupt / not a PDF
        raise NoTextError(f"could not read PDF: {e}") from e
    text = "\n".join(pages).strip()
    if len(text) < min_chars:
        raise NoTextError("no extractable text in PDF (scanned transcripts are not supported)")
    return text
