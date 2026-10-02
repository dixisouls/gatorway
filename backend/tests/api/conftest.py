import io

import pytest
import redis as redis_lib
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from gatorway.api.main import create_app
from gatorway.api.state import AppState
from gatorway.cache.store import Cache, RateLimiter
from gatorway.auth.firebase import Identity, InvalidToken
from gatorway.config import Settings
from gatorway.transcripts.redact import StubRedactor


def bearer(email: str, uid: str | None = None, verified: bool = True) -> dict:
    """Headers carrying a token the FakeVerifier understands (Firebase itself is not involved in these tests)."""
    return {"Authorization": f"Bearer fake:{uid or 'uid-' + email}|{email}|{int(verified)}"}


class FakeVerifier:
    """Stands in for Firebase: 'fake:<uid>|<email>|<verified 0/1>' is a good token, anything else is not."""

    def verify(self, token: str) -> Identity:
        if not token.startswith("fake:"):
            raise InvalidToken("not a fake token")
        uid, email, verified = token[5:].split("|")
        return Identity(uid=uid, email=email.strip().lower(), email_verified=verified == "1")


class BrokenRedis:
    """Every call raises, like a Redis that went away."""

    def __getattr__(self, name):
        def boom(*a, **k):
            raise redis_lib.ConnectionError("down")
        return boom


@pytest.fixture
def broken_redis():
    return BrokenRedis()


@pytest.fixture
def make_state(engine, db, redis_client):
    """Factory for an AppState wired to the test DB and fakeredis; pass keyword overrides for any field."""

    def _make(**overrides) -> AppState:
        r = overrides.pop("redis", redis_client)
        base = dict(settings=Settings(_env_file=None, firebase_project_id="test-project"), verifier=FakeVerifier(), engine=engine, redis=r, cache=Cache(r),
                    limiter=RateLimiter(r), redactor=StubRedactor())
        base.update(overrides)
        return AppState(**base)

    return _make


@pytest.fixture
def client(make_state):
    return TestClient(create_app(make_state(), init_db_on_startup=False))


@pytest.fixture
def signup(client):
    def _signup(email="student@sfsu.edu", password=None):
        headers = bearer(email)
        assert client.get("/auth/me", headers=headers).status_code == 200
        return headers

    return _signup


@pytest.fixture
def make_pdf():
    def _make(lines):
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        y = 800
        for line in lines:
            c.drawString(60, y, line)
            y -= 18
        c.save()
        return buf.getvalue()

    return _make
