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
from gatorway.llm.client import gemini_configured, make_genai_client
from gatorway.llm.gemini import GeminiLlm
from gatorway.llm.orchestrator import PathwayService
from gatorway.transcripts.extractor_client import ExtractorClient, HttpExtractor
from gatorway.auth.firebase import FirebaseVerifier, TokenVerifier
from gatorway.transcripts.pii import GlinerRedactor
from gatorway.transcripts.redact import Redactor, StubRedactor


@dataclass
class AppState:
    settings: Settings
    engine: Engine
    redis: redis.Redis
    cache: Cache
    limiter: RateLimiter
    redactor: Redactor
    verifier: TokenVerifier
    extractor: ExtractorClient | None = None
    pathway_service: PathwayService | None = None


class UnavailableLlm:
    """Used when no Gemini credentials are configured. The orchestrator degrades to the baseline roadmap with a note."""

    async def parse_intent(self, interest: str):
        raise RuntimeError("Gemini is not configured")

    async def propose_edits(self, *args, **kwargs):
        raise RuntimeError("Gemini is not configured")


def check_auth(settings: Settings) -> None:
    """Sign-in is Firebase: without a project id no token can be checked, so refuse to start."""
    if not settings.firebase_project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID is not set. Use the projectId from your Firebase web app config (see .env.example).")


def build_redactor(settings: Settings) -> Redactor:
    if settings.redactor == "stub":
        return StubRedactor()
    if settings.redactor == "gliner":
        return GlinerRedactor(settings.gliner_model, settings.gliner_threshold, settings.gliner_person_threshold)  # loads lazily
    raise ValueError(f"unknown REDACTOR {settings.redactor!r} (use gliner or stub)")


def build_state(settings: Settings | None = None) -> AppState:
    settings = settings or get_settings()
    check_auth(settings)
    engine = get_engine()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    cache = Cache(r)
    if gemini_configured(settings):
        llm = GeminiLlm(make_genai_client(settings), settings.gemini_model, settings.gemini_thinking_level)
    else:
        llm = UnavailableLlm()

    def catalog() -> Catalog:
        with Session(engine) as db:
            return get_catalog(db)

    service = PathwayService(
        llm=llm, cache=cache, catalog_provider=catalog, mcp_factory=lambda: Client(settings.mcp_url),
        allowed_tools=settings.gemini_tool_set, model_name=settings.gemini_model,
        edit_timeout_s=settings.edit_timeout_s,
    )
    return AppState(
        settings=settings, engine=engine, redis=r, cache=cache, limiter=RateLimiter(r), redactor=build_redactor(settings), verifier=FirebaseVerifier(settings.firebase_project_id),
        extractor=HttpExtractor(settings.extractor_url, settings.extractor_api_key), pathway_service=service,
    )
