import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from gatorway.api.main import create_app
from gatorway.auth.security import create_access_token
from gatorway.db.models import User


def test_signup_creates_an_account_with_a_hashed_password_and_returns_a_token(client, db):
    r = client.post("/auth/signup", json={"email": "  Jane.Doe@MAIL.SFSU.EDU ", "password": "correct-horse-battery"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "jane.doe@mail.sfsu.edu" and body["token_type"] == "bearer" and body["access_token"]
    stored = db.scalar(select(User).where(User.email == "jane.doe@mail.sfsu.edu"))
    assert stored.password_hash.startswith("$argon2") and "correct-horse" not in stored.password_hash


@pytest.mark.parametrize("email", ["jane@evilsfsu.edu", "jane@sfsu.edu.evil.com", "jane@gmail.com", "@sfsu.edu", "not-an-email"])
def test_signup_rejects_non_sfsu_emails(client, email):
    r = client.post("/auth/signup", json={"email": email, "password": "correct-horse-battery"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_email"


def test_signup_rejects_duplicates_case_insensitively_and_short_passwords(client):
    assert client.post("/auth/signup", json={"email": "a@sfsu.edu", "password": "correct-horse-battery"}).status_code == 201
    dup = client.post("/auth/signup", json={"email": "A@SFSU.EDU", "password": "correct-horse-battery"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "email_taken"
    short = client.post("/auth/signup", json={"email": "b@sfsu.edu", "password": "short"})
    assert short.status_code == 422 and short.json()["error"]["code"] == "validation_error"


def test_login_success_and_identical_failures_for_wrong_password_and_unknown_user(client, signup):
    signup("a@sfsu.edu", "correct-horse-battery")
    ok = client.post("/auth/login", json={"email": "A@sfsu.edu", "password": "correct-horse-battery"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    wrong = client.post("/auth/login", json={"email": "a@sfsu.edu", "password": "wrong-password-1"})
    unknown = client.post("/auth/login", json={"email": "nobody@sfsu.edu", "password": "wrong-password-1"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_me_requires_a_valid_token(client, signup):
    headers = signup("a@sfsu.edu")
    assert client.get("/auth/me", headers=headers).json()["email"] == "a@sfsu.edu"
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).json()["error"]["code"] == "invalid_token"


def test_expired_token_is_rejected(client, signup):
    from datetime import datetime, timedelta, timezone
    uid = client.get("/auth/me", headers=signup("c@sfsu.edu")).json()["id"]
    old = create_access_token(uid, "t" * 40, 1, now=datetime.now(timezone.utc) - timedelta(hours=3))
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_login_is_rate_limited_per_ip(client):
    codes = [client.post("/auth/login", json={"email": "x@sfsu.edu", "password": "whatever-123"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
    limited = client.post("/auth/login", json={"email": "x@sfsu.edu", "password": "whatever-123"})
    assert int(limited.headers["Retry-After"]) >= 1 and limited.json()["error"]["code"] == "rate_limited"


def test_login_still_works_when_redis_is_down(make_state, broken_redis):
    from gatorway.cache.store import Cache, RateLimiter
    broken = broken_redis
    client = TestClient(create_app(make_state(redis=broken, cache=Cache(broken), limiter=RateLimiter(broken)), init_db_on_startup=False))
    assert client.post("/auth/signup", json={"email": "a@sfsu.edu", "password": "correct-horse-battery"}).status_code == 201
    assert client.post("/auth/login", json={"email": "a@sfsu.edu", "password": "correct-horse-battery"}).status_code == 200
