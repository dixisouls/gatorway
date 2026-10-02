"""Firebase Authentication. The browser signs the student in with Firebase; every API request carries the Firebase ID token and it is
verified here against Google's public keys (no secret and no service account needed, only the project id).
Firebase holds the password. We keep only the uid and email locally, so saved courses and pathways have an owner."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import firebase_admin
from firebase_admin import auth

from .security import normalize_email


class InvalidToken(Exception):
    """The token is missing, malformed, expired, revoked or has no email."""


class AuthUnavailable(Exception):
    """Google's signing keys could not be fetched, so no token can be checked right now."""


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str
    email_verified: bool


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Identity: ...


class FirebaseVerifier:
    def __init__(self, project_id: str):
        if not project_id:
            raise ValueError("a Firebase project id is required")
        self._project_id = project_id
        self._app = None

    def _get_app(self):
        if self._app is None:
            name = f"gatorway-{self._project_id}"
            try:
                self._app = firebase_admin.get_app(name)
            except ValueError:
                self._app = firebase_admin.initialize_app(options={"projectId": self._project_id}, name=name)
        return self._app

    def verify(self, token: str) -> Identity:
        try:
            claims = auth.verify_id_token(token, app=self._get_app())
        except auth.CertificateFetchError as e:
            raise AuthUnavailable(str(e)) from e
        except (auth.InvalidIdTokenError, auth.ExpiredIdTokenError, auth.RevokedIdTokenError, ValueError) as e:
            raise InvalidToken(str(e)) from e
        email = normalize_email(claims.get("email") or "")
        if not email or not claims.get("uid"):
            raise InvalidToken("the token has no email")
        return Identity(uid=claims["uid"], email=email, email_verified=bool(claims.get("email_verified")))
