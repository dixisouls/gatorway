from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from sqlalchemy.orm import Session

from gatorway.cache.store import Cache
from gatorway.ingest.embeddings import Embedder


@dataclass
class Deps:
    db: Callable[[], AbstractContextManager[Session]]  # `with deps.db() as session:`
    cache: Cache
    embedder: Embedder
    embed_model: str
