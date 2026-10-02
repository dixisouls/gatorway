"""Embedders (local sentence-transformers model, Gemini, and an offline hashing stand-in) and the step that fills courses.embedding."""
from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from tqdm import tqdm

from gatorway.db.models import EMBED_DIM, Course, Meta


class Embedder(Protocol):
    dim: int
    identity: str  # provider + model + dimension; recorded so search never compares vectors from different embedders

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _l2(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class HashingEmbedder:
    """Deterministic bag-of-words embedding. Offline and free: used by tests and `--embeddings hashing`.
    Related texts share words, so they land closer; it is NOT a semantic model."""

    dim = EMBED_DIM
    identity = f"hashing:{EMBED_DIM}"

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


class LocalEmbedder:
    """Runs a sentence-transformers model on this machine (no API, no quota). bge-base is 768-dim, matching the vector column."""

    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge convention: queries get it, documents do not

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5", model=None, batch: int = 32):
        self._name, self._model, self._batch = model_name, model, batch
        self.dim = EMBED_DIM
        self.identity = f"local:{model_name}:{self.dim}"

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # heavy import, so only when first used

            self._model = SentenceTransformer(self._name)
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self._load().encode(texts, batch_size=self._batch, normalize_embeddings=True, show_progress_bar=False)
        return [_l2([float(x) for x in v]) for v in vecs]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([self.QUERY_PREFIX + text])[0]


class GeminiEmbedder:
    def __init__(self, client, model: str, dim: int = EMBED_DIM, batch: int = 100, retries: int = 6, backoff_s: float = 5.0):
        self._backoff = backoff_s
        self._c, self._model, self.dim, self._batch, self._retries = client, model, dim, batch, retries
        self.identity = f"gemini:{model}:{dim}"

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
                    time.sleep(self._backoff * 2**attempt)  # per-minute quotas: 5s, 10s, 20s, 40s, 80s
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


def build_embedder(kind: str, settings) -> Embedder:
    if kind == "hashing":
        return HashingEmbedder()
    if kind == "local":
        return LocalEmbedder(settings.local_embed_model)
    if kind == "gemini":
        from gatorway.llm.client import make_genai_client

        return GeminiEmbedder(make_genai_client(settings), settings.embed_model, settings.embed_dim)
    raise ValueError(f"unknown embedder {kind!r}")


def course_text(code: str, title: str, description: str | None) -> str:
    return f"{code} {title}. {description or ''}".strip()


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


IDENTITY_KEY = "embedding_identity"


def assert_embedding_matches(db: Session, embedder: Embedder) -> None:
    """The search server calls this at startup: query vectors must come from the same embedder as the stored course vectors."""
    stored = db.scalar(select(Meta.value).where(Meta.key == IDENTITY_KEY))
    if stored is None:
        raise RuntimeError("Course vectors have no recorded embedder. Run `python -m gatorway.ingest` first.")
    if stored != embedder.identity:
        raise RuntimeError(
            f"Stored course vectors were made by {stored!r} but this server embeds queries with {embedder.identity!r}. "
            "Set EMBED_PROVIDER to match, or re-run `python -m gatorway.ingest` with the embedder you want."
        )


def embed_courses(db: Session, embedder: Embedder, batch_size: int = 32, progress: bool = False) -> int:
    """Embed courses that have a description and whose text or embedder changed (or that have no vector yet). Commits per batch."""
    rows = db.execute(select(Course.id, Course.code, Course.title, Course.description, Course.text_hash, Course.embedding.is_(None))).all()
    todo = []
    for cid, code, title, desc, old_hash, missing in rows:
        if not desc:
            continue
        text = course_text(code, title, desc)
        h = _hash(f"{embedder.identity}|{text}")  # the embedder is part of the hash, so switching provider re-embeds everything
        if missing or h != old_hash:
            todo.append((cid, text, h))
    if todo:
        db.merge(Meta(key=IDENTITY_KEY, value=f"incomplete:{embedder.identity}"))  # a half-finished run must not look usable
        db.commit()
    bar = tqdm(total=len(todo), desc="Embedding courses", unit="course", disable=not progress)
    for i in range(0, len(todo), batch_size):
        chunk = todo[i : i + batch_size]
        vectors = embedder.embed_documents([t for _, t, _ in chunk])
        for (cid, _, h), vec in zip(chunk, vectors):
            db.execute(update(Course).where(Course.id == cid).values(embedding=vec, text_hash=h))
        db.commit()
        bar.update(len(chunk))
    bar.close()
    if todo:
        db.merge(Meta(key=IDENTITY_KEY, value=embedder.identity))
        db.commit()
    return len(todo)
