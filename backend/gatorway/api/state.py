"""Everything a request handler needs, built once at startup (and swapped for fakes in tests)."""
from __future__ import annotations

from dataclasses import dataclass

import redis
from fastmcp import Client
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from gatorway.cache.store import Cache, RateLimiter
from gatorway.config import Settings, get_settings
from gatorway.db.session import get_engine
from gatorway.engine.models import Catalog
from gatorway.engine.repository import get_catalog
from gatorway.llm.gemini import GeminiLlm
from gatorway.llm.orchestrator import PathwayService
from gatorway.transcripts.extractor_client import ExtractorClient, HttpExtractor
from gatorway.transcripts.redact import Redactor, StubRedactor


@dataclass
class AppState:
    settings: Settings
    engine: Engine
    redis: redis.Redis
    cache: Cache
    limiter: RateLimiter
    redactor: Redactor
    extractor: ExtractorClient | None = None
    pathway_service: PathwayService | None = None


class UnavailableLlm:
    """Used when GEMINI_API_KEY is not set. The orchestrator degrades to the baseline roadmap with a note."""

    async def parse_intent(self, interest: str):
        raise RuntimeError("GEMINI_API_KEY is not set")

    async def propose_edits(self, *args, **kwargs):
        raise RuntimeError("GEMINI_API_KEY is not set")


def build_state(settings: Settings | None = None) -> AppState:
    settings = settings or get_settings()
    engine = get_engine()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    cache = Cache(r)
    if settings.gemini_api_key:
        from google import genai

        llm = GeminiLlm(genai.Client(api_key=settings.gemini_api_key), settings.gemini_model)
    else:
        llm = UnavailableLlm()

    def catalog() -> Catalog:
        with Session(engine) as db:
            return get_catalog(db)

    service = PathwayService(
        llm=llm, cache=cache, catalog_provider=catalog, mcp_factory=lambda: Client(settings.mcp_url),
        allowed_tools=settings.gemini_tool_set, model_name=settings.gemini_model,
    )
    return AppState(
        settings=settings, engine=engine, redis=r, cache=cache, limiter=RateLimiter(r), redactor=StubRedactor(),
        extractor=HttpExtractor(settings.extractor_url, settings.extractor_api_key), pathway_service=service,
    )
