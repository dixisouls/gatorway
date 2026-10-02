"""Embedders (Gemini + an offline hashing stand-in) and the step that fills courses.embedding."""
from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from gatorway.db.models import EMBED_DIM, Course


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _l2(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class HashingEmbedder:
    """Deterministic bag-of-words embedding. Offline and free: used by tests and `--embeddings hashing`.
    Related texts share words, so they land closer; it is NOT a semantic model."""

    dim = EMBED_DIM

    def _one(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in re.findall(r"[a-z0-9\.\+#]+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        if not any(v):
            v[0] = 1.0
        return _l2(v)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._one(text)


class GeminiEmbedder:
    def __init__(self, client, model: str, dim: int = EMBED_DIM, batch: int = 100, retries: int = 4):
        self._c, self._model, self.dim, self._batch, self._retries = client, model, dim, batch, retries

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        from google.genai import types

        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            chunk = texts[i : i + self._batch]
            for attempt in range(self._retries):
                try:
                    resp = self._c.models.embed_content(
                        model=self._model, contents=chunk,
                        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dim),
                    )
                    out += [_l2(list(e.values)) for e in resp.embeddings]
                    break
                except Exception:
                    if attempt == self._retries - 1:
                        raise
                    time.sleep(2**attempt)  # rate limits: 1s, 2s, 4s
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


def build_embedder(kind: str, settings) -> Embedder:
    if kind == "hashing":
        return HashingEmbedder()
    if kind == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (use --embeddings hashing for an offline run)")
        from google import genai

        return GeminiEmbedder(genai.Client(api_key=settings.gemini_api_key), settings.embed_model, settings.embed_dim)
    raise ValueError(f"unknown embedder {kind!r}")


def course_text(code: str, title: str, description: str | None) -> str:
    return f"{code} {title}. {description or ''}".strip()


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def embed_courses(db: Session, embedder: Embedder, batch_size: int = 100) -> int:
    """Embed courses that have a description and whose text changed (or that have no vector yet). Commits per batch."""
    rows = db.execute(select(Course.id, Course.code, Course.title, Course.description, Course.text_hash, Course.embedding.is_(None))).all()
    todo = []
    for cid, code, title, desc, old_hash, missing in rows:
        if not desc:
            continue
        text = course_text(code, title, desc)
        h = _hash(text)
        if missing or h != old_hash:
            todo.append((cid, text, h))
    for i in range(0, len(todo), batch_size):
        chunk = todo[i : i + batch_size]
        vectors = embedder.embed_documents([t for _, t, _ in chunk])
        for (cid, _, h), vec in zip(chunk, vectors):
            db.execute(update(Course).where(Course.id == cid).values(embedding=vec, text_hash=h))
        db.commit()
    return len(todo)
