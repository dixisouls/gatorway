"""Password hashing, SFSU email check and JWT helpers."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# sfsu.edu itself or any subdomain (students use mail.sfsu.edu); never evilsfsu.edu or sfsu.edu.evil.com
_SFSU_EMAIL = re.compile(r"^[^@\s]+@([a-z0-9-]+\.)*sfsu\.edu$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_sfsu_email(email: str) -> bool:
    return bool(_SFSU_EMAIL.fullmatch(normalize_email(email)))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, secret: str, ttl_minutes: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=ttl_minutes)}, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> int | None:
    try:
        return int(jwt.decode(token, secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
