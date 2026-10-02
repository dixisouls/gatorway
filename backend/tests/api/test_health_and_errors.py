from fastapi.testclient import TestClient

from gatorway.api.main import create_app
from gatorway.cache.store import Cache, RateLimiter


def test_health_reports_both_services(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"ok": True, "postgres": True, "redis": True}


def test_health_is_503_when_redis_is_down(make_state, broken_redis):
    broken = broken_redis
    c = TestClient(create_app(make_state(redis=broken, cache=Cache(broken), limiter=RateLimiter(broken)), init_db_on_startup=False))
    r = c.get("/health")
    assert r.status_code == 503 and r.json() == {"ok": False, "postgres": True, "redis": False}


def test_unknown_routes_and_bad_bodies_use_the_error_envelope(client):
    nf = client.get("/nope")
    assert nf.status_code == 404 and set(nf.json()["error"]) == {"code", "message", "details"}
    bad = client.post("/auth/login", json={"email": 5})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error" and bad.json()["error"]["details"]


def test_cors_allows_both_local_frontend_origins_and_nothing_else(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        r = client.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
        assert r.headers.get("access-control-allow-origin") == origin
    r = client.options("/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
