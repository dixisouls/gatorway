"""Redaction port (ARCHITECTURE.md section 7). The real local redactor plugs in here later."""
from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Redactor(Protocol):
    def redact(self, text: str) -> str: ...


class StubRedactor:
    """Pass-through placeholder. Fine for demo transcripts; real student data must not be used until a real redactor replaces it."""

    def __init__(self) -> None:
        self._warned = False

    def redact(self, text: str) -> str:
        if not self._warned:
            log.warning("StubRedactor is active: transcript text is NOT being redacted before it is sent to the extractor")
            self._warned = True
        return text
