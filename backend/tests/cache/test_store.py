import fakeredis
import pytest
import redis

from gatorway.cache.store import Cache, CacheUnavailable, RateLimiter


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def test_intent_cache_normalizes_whitespace_and_case(r):
    c = Cache(r)
    c.set_intent("Web   Dev with NEXT.js ", "m", {"specialization": True})
    assert c.get_intent("web dev with next.js", "m") == {"specialization": True}
    assert c.get_intent("web dev with next.js", "other-model") is None


def test_query_embedding_roundtrip(r):
    c = Cache(r)
    c.set_query_embedding("React", "e", [0.1, 0.2])
    assert c.get_query_embedding("  react ", "e") == [0.1, 0.2] and c.get_query_embedding("react", "other") is None


def test_pathway_key_changes_with_data_version_and_passed_courses_but_not_their_order():
    a = Cache.pathway_key(1, 2, ["A 1", "B 2"], "h", "v1")
    assert a == Cache.pathway_key(1, 2, ["B 2", "A 1"], "h", "v1")
    assert a != Cache.pathway_key(1, 2, ["A 1"], "h", "v1") and a != Cache.pathway_key(1, 2, ["A 1", "B 2"], "h", "v2")


def test_lock_is_exclusive(r):
    c = Cache(r)
    k = Cache.pathway_key(1, 1, [], "h", "v")
    assert c.acquire_lock(k) is True and c.acquire_lock(k) is False
    c.release_lock(k)
    assert c.acquire_lock(k) is True


def test_session_roundtrip_and_update(r):
    c = Cache(r)
    sid = c.create_session({"x": 1}, ["B 2", "A 1"])
    assert c.get_session(sid) == {"pathway": {"x": 1}, "passed": ["A 1", "B 2"]}
    c.update_session_pathway(sid, {"x": 2})
    assert c.get_session(sid)["pathway"] == {"x": 2}
    assert c.get_session("missing") is None


class BrokenRedis:
    def __getattr__(self, name):
        def boom(*a, **k):
            raise redis.ConnectionError("down")
        return boom


def test_redis_down_degrades_caches_but_sessions_raise():
    c = Cache(BrokenRedis())
    assert c.get_intent("x", "m") is None
    c.set_intent("x", "m", {})  # no exception
    assert c.acquire_lock("gw:pathway:k") is True
    with pytest.raises(CacheUnavailable):
        c.create_session({}, [])
    with pytest.raises(CacheUnavailable):
        c.get_session("x")
    assert RateLimiter(BrokenRedis()).hit("login", "ip", 1, 60) == (True, 0)  # fails open


def test_rate_limiter_blocks_after_limit_and_resets_next_window(r):
    t = [1000.0]
    rl = RateLimiter(r, clock=lambda: t[0])
    assert [rl.hit("login", "1.2.3.4", 2, 60)[0] for _ in range(3)] == [True, True, False]
    assert rl.hit("login", "other", 2, 60)[0] is True
    t[0] += 60
    assert rl.hit("login", "1.2.3.4", 2, 60)[0] is True


async def test_wait_for_pathway_returns_a_value_stored_meanwhile(r):
    import asyncio
    c = Cache(r)
    k = Cache.pathway_key(1, 1, [], "h", "v")
    asyncio.get_running_loop().call_later(0.1, c.set_pathway, k, {"ok": True})
    assert await c.wait_for_pathway(k, timeout=2) == {"ok": True}
    assert await c.wait_for_pathway("gw:pathway:none", timeout=0.2) is None
