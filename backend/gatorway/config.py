"""Application settings. Values come from the environment or a .env file (repo root or backend/)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://gatorway:gatorway@localhost:5432/gatorway"
    test_database_url: str = "postgresql+psycopg://gatorway:gatorway@localhost:5432/gatorway_test"
    redis_url: str = "redis://localhost:6379/0"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_ttl_minutes: int = 1440

    extractor_url: str = "http://127.0.0.1:8080"
    extractor_api_key: str = ""

    mcp_url: str = "http://127.0.0.1:8001/mcp"
    gemini_tools: str = "get_baseline,get_requirements,search_courses,validate_edits"

    scrape_dir: str = "scraping/sfsu_output"

    @property
    def gemini_tool_set(self) -> set[str]:
        return {t.strip() for t in self.gemini_tools.split(",") if t.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
