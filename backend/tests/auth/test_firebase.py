import pytest
from firebase_admin import auth as fb_auth

from gatorway.auth.firebase import FirebaseVerifier, Identity, InvalidToken


def claims(**over):
    return {"uid": "u1", "email": "Jane@SFSU.edu", "email_verified": True, **over}


def test_a_valid_firebase_token_becomes_an_identity(monkeypatch):
    monkeypatch.setattr(fb_auth, "verify_id_token", lambda token, app=None, **kw: claims())
    assert FirebaseVerifier("my-project").verify("tok") == Identity(uid="u1", email="jane@sfsu.edu", email_verified=True)


@pytest.mark.parametrize("error", [
    fb_auth.InvalidIdTokenError("bad signature"), fb_auth.ExpiredIdTokenError("expired", None),
    fb_auth.RevokedIdTokenError("revoked"), ValueError("malformed"),
])
def test_any_token_problem_is_an_invalid_token(monkeypatch, error):
    def boom(token, app=None, **kw):
        raise error

    monkeypatch.setattr(fb_auth, "verify_id_token", boom)
    with pytest.raises(InvalidToken):
        FirebaseVerifier("my-project").verify("tok")


def test_a_token_without_an_email_cannot_be_an_sfsu_account(monkeypatch):
    monkeypatch.setattr(fb_auth, "verify_id_token", lambda token, app=None, **kw: claims(email=None))
    with pytest.raises(InvalidToken):
        FirebaseVerifier("my-project").verify("tok")


def test_the_verifier_needs_a_project_id():
    with pytest.raises(ValueError):
        FirebaseVerifier("")


def test_unreachable_signing_keys_are_an_availability_problem_not_a_bad_token(monkeypatch):
    from gatorway.auth.firebase import AuthUnavailable

    def down(token, app=None, **kw):
        raise fb_auth.CertificateFetchError("no network", None)

    monkeypatch.setattr(fb_auth, "verify_id_token", down)
    with pytest.raises(AuthUnavailable):
        FirebaseVerifier("my-project").verify("tok")
