"""Client for the extractor service (Cloud Run in production, localhost in dev)."""
from __future__ import annotations

from typing import Protocol

import httpx

from .extraction import ExtractedTranscript


class ExtractorError(RuntimeError):
    """The extractor was unreachable, rejected the request, or answered with something unusable."""


class ExtractorClient(Protocol):
    async def extract(self, text: str) -> ExtractedTranscript: ...


class HttpExtractor:
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 90.0, transport: httpx.AsyncBaseTransport | None = None):
        self._base, self._key, self._timeout, self._transport = base_url.rstrip("/"), api_key, timeout, transport

    async def extract(self, text: str) -> ExtractedTranscript:
        headers = {"X-Api-Key": self._key} if self._key else {}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                resp = await client.post(f"{self._base}/extract", json={"text": text}, headers=headers)
        except httpx.HTTPError as e:
            raise ExtractorError(f"extractor unreachable: {e}") from e
        if resp.status_code != 200:
            raise ExtractorError(f"extractor returned HTTP {resp.status_code}")
        try:
            return ExtractedTranscript.model_validate(resp.json())
        except ValueError as e:
            raise ExtractorError("extractor returned an invalid response") from e
