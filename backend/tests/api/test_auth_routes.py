from sqlalchemy import select

from gatorway.config import Settings
from gatorway.db.models import User

from .conftest import bearer


def test_me_creates_the_local_user_on_first_sight_and_reuses_it(client, db):
    first = client.get("/auth/me", headers=bearer("student@sfsu.edu")).json()
    again = client.get("/auth/me", headers=bearer("student@sfsu.edu")).json()
    assert first == again and first["email"] == "student@sfsu.edu"
    row = db.scalar(select(User).where(User.email == "student@sfsu.edu"))
    assert row.firebase_uid == "uid-student@sfsu.edu" and row.password_hash is None  # Firebase holds the password; we store only who they are


def test_no_token_or_a_bad_token_is_a_401_with_the_error_envelope(client):
    none = client.get("/auth/me")
    assert none.status_code == 401 and none.json()["error"]["code"] == "not_authenticated"
    bad = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_token"


def test_only_sfsu_addresses_are_let_in_even_with_a_valid_firebase_account(client):
    for email in ("someone@gmail.com", "x@evilsfsu.edu", "x@sfsu.edu.evil.com"):
        r = client.get("/auth/me", headers=bearer(email))
        assert r.status_code == 403 and r.json()["error"]["code"] == "invalid_email", email
    assert client.get("/auth/me", headers=bearer("Student@MAIL.SFSU.EDU")).json()["email"] == "student@mail.sfsu.edu"


def test_an_existing_local_user_is_linked_to_firebase_by_email(client, db):
    db.add(User(email="old@sfsu.edu", password_hash="legacy")); db.commit()
    old_id = db.scalar(select(User.id).where(User.email == "old@sfsu.edu"))
    assert client.get("/auth/me", headers=bearer("old@sfsu.edu")).json()["id"] == old_id  # their saved data stays theirs
    assert db.scalar(select(User.firebase_uid).where(User.id == old_id)) == "uid-old@sfsu.edu"


def test_a_changed_firebase_email_updates_the_same_user(client):
    a = client.get("/auth/me", headers=bearer("before@sfsu.edu", uid="same-uid")).json()
    b = client.get("/auth/me", headers=bearer("after@sfsu.edu", uid="same-uid")).json()
    assert a["id"] == b["id"] and b["email"] == "after@sfsu.edu"


def test_email_verification_is_only_required_when_switched_on(make_state):
    from fastapi.testclient import TestClient

    from gatorway.api.main import create_app

    relaxed = TestClient(create_app(make_state(), init_db_on_startup=False))
    assert relaxed.get("/auth/me", headers=bearer("new@sfsu.edu", verified=False)).status_code == 200
    strict = TestClient(create_app(make_state(settings=Settings(_env_file=None, firebase_project_id="p", require_email_verified=True)), init_db_on_startup=False))
    r = strict.get("/auth/me", headers=bearer("other@sfsu.edu", verified=False))
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"
    assert strict.get("/auth/me", headers=bearer("other@sfsu.edu", verified=True)).status_code == 200


def test_the_old_password_endpoints_are_gone(client):
    assert client.post("/auth/signup", json={"email": "a@sfsu.edu", "password": "correct-horse-battery"}).status_code in (404, 405)
    assert client.post("/auth/login", json={"email": "a@sfsu.edu", "password": "correct-horse-battery"}).status_code in (404, 405)


def test_an_email_that_belongs_to_a_different_firebase_account_is_refused_not_handed_over(client):
    assert client.get("/auth/me", headers=bearer("taken@sfsu.edu", uid="first")).status_code == 200
    r = client.get("/auth/me", headers=bearer("taken@sfsu.edu", uid="second"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "account_conflict"
