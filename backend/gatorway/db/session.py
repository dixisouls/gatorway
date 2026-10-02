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


# Columns added after their table first existed. create_all never alters a table, so these are added here (idempotent).
_ADDED_COLUMNS = [("user_courses", "title", "text"), ("users", "firebase_uid", "varchar(128)")]
_EXTRA_DDL = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_firebase_uid ON users (firebase_uid)",
    "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL",  # Firebase holds passwords now
]


def init_db(engine: Engine) -> None:
    """Create the pgvector extension and every table (no migration tool for the hackathon)."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, column, sql_type in _ADDED_COLUMNS:
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {sql_type}'))
        for ddl in _EXTRA_DDL:
            conn.execute(text(ddl))


@contextmanager
def session_scope(engine: Engine):
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
