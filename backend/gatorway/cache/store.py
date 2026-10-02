"""Redis cache, sessions, locks and rate limiting. Key layout and TTLs: ARCHITECTURE.md section 6."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid

import redis

log = logging.getLogger(__name__)

PREFIX = "gw"
ENGINE_VERSION = "1"  # bump when engine / validator rules change; it is part of every pathway cache key
TTL_SESSION = 30 * 60
TTL_INTENT = 7 * 86400
TTL_EMBQ = 7 * 86400
TTL_PATHWAY = 86400
TTL_LOCK = 60


class CacheUnavailable(RuntimeError):
    """Raised only by operations that cannot degrade (pathway sessions)."""


def normalize_interest(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _sha(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


class Cache:
    def __init__(self, client: redis.Redis):
        self._r = client

    # ---- best-effort primitives: a Redis outage means "no cache", never an error ----
    def _get(self, key: str):
        try:
            raw = self._r.get(key)
        except redis.RedisError as e:
            log.warning("redis get failed: %s", e)
            return None
        return json.loads(raw) if raw else None

    def _set(self, key: str, value, ttl: int) -> None:
        try:
            self._r.set(key, json.dumps(value), ex=ttl)
        except redis.RedisError as e:
            log.warning("redis set failed: %s", e)

    # ---- interest parses ----
    def intent_key(self, interest: str, model: str) -> str:
        return f"{PREFIX}:intent:{_sha(normalize_interest(interest), model)}"

    def get_intent(self, interest: str, model: str) -> dict | None:
        return self._get(self.intent_key(interest, model))

    def set_intent(self, interest: str, model: str, intent: dict) -> None:
        self._set(self.intent_key(interest, model), intent, TTL_INTENT)

    # ---- query embeddings ----
    def get_query_embedding(self, text: str, model: str) -> list[float] | None:
        return self._get(f"{PREFIX}:embq:{_sha(normalize_interest(text), model)}")

    def set_query_embedding(self, text: str, model: str, vec: list[float]) -> None:
        self._set(f"{PREFIX}:embq:{_sha(normalize_interest(text), model)}", vec, TTL_EMBQ)

    # ---- finished pathways ----
    @staticmethod
    def pathway_key(program_id: int, roadmap_id: int, passed: list[str], intent_hash: str, data_version: str) -> str:
        digest = _sha(program_id, roadmap_id, ",".join(sorted(passed)), intent_hash, data_version, ENGINE_VERSION)
        return f"{PREFIX}:pathway:{digest}"

    def intent_hash(self, interest: str, model: str) -> str:
        return _sha(normalize_interest(interest), model)

    def get_pathway(self, key: str) -> dict | None:
        return self._get(key)

    def set_pathway(self, key: str, value: dict) -> None:
        self._set(key, value, TTL_PATHWAY)

    # ---- single-flight lock so identical concurrent requests do the work once ----
    def acquire_lock(self, key: str) -> bool:
        try:
            return bool(self._r.set(key.replace(":pathway:", ":lock:pathway:"), "1", nx=True, ex=TTL_LOCK))
        except redis.RedisError:
            return True  # no Redis -> no coordination; just do the work

    def release_lock(self, key: str) -> None:
        try:
            self._r.delete(key.replace(":pathway:", ":lock:pathway:"))
        except redis.RedisError:
            pass

    async def wait_for_pathway(self, key: str, timeout: float = 30.0, interval: float = 0.05) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            hit = self.get_pathway(key)
            if hit is not None:
                return hit
            await asyncio.sleep(interval)
        return None

    # ---- pathway sessions (Gemini only ever sees the id) ----
    def create_session(self, pathway: dict, passed: list[str]) -> str:
        sid = uuid.uuid4().hex
        try:
            self._r.set(f"{PREFIX}:session:{sid}", json.dumps({"pathway": pathway, "passed": sorted(passed)}), ex=TTL_SESSION)
        except redis.RedisError as e:
            raise CacheUnavailable(str(e)) from e
        return sid

    def get_session(self, sid: str) -> dict | None:
        try:
            raw = self._r.get(f"{PREFIX}:session:{sid}")
        except redis.RedisError as e:
            raise CacheUnavailable(str(e)) from e
        return json.loads(raw) if raw else None

    def update_session_pathway(self, sid: str, pathway: dict) -> None:
        sess = self.get_session(sid)
        if sess is None:
            return
        sess["pathway"] = pathway
        try:
            self._r.set(f"{PREFIX}:session:{sid}", json.dumps(sess), ex=TTL_SESSION)
        except redis.RedisError as e:
            raise CacheUnavailable(str(e)) from e


class RateLimiter:
    """Fixed-window counter. Fails open if Redis is down."""

    def __init__(self, client: redis.Redis, clock=time.time):
        self._r, self._clock = client, clock

    def hit(self, endpoint: str, who: str, limit: int, window_s: int) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        key = f"{PREFIX}:rl:{endpoint}:{who}:{int(now // window_s)}"
        try:
            n = self._r.incr(key)
            if n == 1:
                self._r.expire(key, window_s)
        except redis.RedisError as e:
            log.warning("rate limiter unavailable, failing open: %s", e)
            return True, 0
        if n > limit:
            return False, max(1, int(window_s - (now % window_s)))
        return True, 0
