"""Application settings. Values come from the environment or a .env file (repo root or backend/)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://gatorway:gatorway@localhost:5432/gatorway"
    test_database_url: str = "postgresql+psycopg://gatorway:gatorway@localhost:5432/gatorway_test"
    redis_url: str = "redis://localhost:6379/0"

    # Gemini auth: Vertex AI via gcloud Application Default Credentials (no key), or an AI Studio key
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    local_embed_model: str = "BAAI/bge-base-en-v1.5"  # 768-dim sentence-transformers model
    embed_provider: str = "local"  # local | gemini | hashing (offline stand-in); must match how the stored course vectors were made

    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_ttl_minutes: int = 1440

    # transcript redaction: "gliner" = local PII model (nvidia/gliner-PII), "stub" = no redaction (tests and demos only)
    redactor: str = "gliner"
    gliner_model: str = "nvidia/gliner-PII"
    gliner_threshold: float = 0.5
    gliner_person_threshold: float = 0.3

    extractor_url: str = "http://127.0.0.1:8080"
    extractor_api_key: str = ""

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"  # comma-separated browser origins allowed to call the API
    mcp_url: str = "http://127.0.0.1:8001/mcp"
    gemini_thinking_level: str = "off"  # off | LOW | MEDIUM | HIGH, or blank for the model default (gemini-3.8-flash rejects MINIMAL)
    edit_timeout_s: float = 120  # whole Gemini personalisation (several tool rounds, ~6 s each); then the baseline is shown
    gemini_tools: str = "get_baseline,get_requirements,search_courses,validate_edits"

    scrape_dir: str = "scraping/sfsu_output"

    @property
    def gemini_tool_set(self) -> set[str]:
        return {t.strip() for t in self.gemini_tools.split(",") if t.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
