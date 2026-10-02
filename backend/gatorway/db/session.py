from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from gatorway.config import get_settings
from .models import Base


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    return make_engine()


def init_db(engine: Engine) -> None:
    """Create the pgvector extension and every table (no migration tool for the hackathon)."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine):
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
