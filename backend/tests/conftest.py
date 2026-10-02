"""Shared fixtures. The `engine`/`db` fixtures need the docker Postgres to be up (docker compose up -d)."""
import fakeredis
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from gatorway.config import get_settings


@pytest.fixture(scope="session")
def engine():
    from gatorway.db.models import Base  # noqa: F401  (imported so metadata is populated)
    from gatorway.db.session import init_db

    url = make_url(get_settings().test_database_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("select 1 from pg_database where datname = :n"), {"n": url.database})
        if not exists:
            conn.execute(text(f'create database "{url.database}"'))
    admin.dispose()
    eng = create_engine(url)
    init_db(eng)
    Base.metadata.drop_all(eng)  # always start from the current schema, never an old one
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    from gatorway.db.models import Base

    with Session(engine) as session:
        yield session
    with engine.begin() as conn:
        names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)
