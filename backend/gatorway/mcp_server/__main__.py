"""python -m gatorway.mcp_server  -> serves the tools over streamable HTTP on 127.0.0.1:8001/mcp"""
from __future__ import annotations

import logging
from contextlib import contextmanager

import redis
from sqlalchemy.orm import Session

from gatorway.cache.store import Cache
from gatorway.config import get_settings
from gatorway.db.session import get_engine
from gatorway.ingest.embeddings import assert_embedding_matches, build_embedder

from .deps import Deps
from .server import create_server


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine = get_engine()

    @contextmanager
    def session():
        with Session(engine) as s:
            yield s

    embedder = build_embedder(settings.embed_provider, settings)
    with session() as db:
        assert_embedding_matches(db, embedder)  # refuse to start if the stored vectors came from a different embedder
    deps = Deps(
        db=session,
        cache=Cache(redis.Redis.from_url(settings.redis_url, decode_responses=True)),
        embedder=embedder,
        embed_model=embedder.identity,  # cache key for query vectors: never reuse one from another embedder
    )
    create_server(deps).run(transport="http", host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
