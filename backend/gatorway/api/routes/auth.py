from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gatorway.auth.security import create_access_token, hash_password, is_sfsu_email, normalize_email, verify_password
from gatorway.db.models import User

from ..deps import current_user, get_db, get_state, ip_rate_limit
from ..errors import ApiError
from ..state import AppState

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("not-a-real-password")  # verified against when the email is unknown, so timing does not reveal accounts


class Credentials(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


def _token_response(user: User, state: AppState) -> dict:
    token = create_access_token(user.id, state.settings.jwt_secret, state.settings.jwt_ttl_minutes)
    return {"user": {"id": user.id, "email": user.email}, "access_token": token, "token_type": "bearer"}


@router.post("/signup", status_code=201, dependencies=[Depends(ip_rate_limit("signup", 10, 3600))])
def signup(body: Credentials, db: Session = Depends(get_db), state: AppState = Depends(get_state)):
    email = normalize_email(body.email)
    if not is_sfsu_email(email):
        raise ApiError(422, "invalid_email", "Use your SFSU email address (it must end in sfsu.edu).")
    if db.scalar(select(User.id).where(User.email == email)):
        raise ApiError(409, "email_taken", "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two signups raced
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists.")
    return _token_response(user, state)


@router.post("/login", dependencies=[Depends(ip_rate_limit("login", 10, 60))])
def login(body: Credentials, db: Session = Depends(get_db), state: AppState = Depends(get_state)):
    user = db.scalar(select(User).where(User.email == normalize_email(body.email)))
    password_ok = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if user is None or not password_ok:
        raise ApiError(401, "invalid_credentials", "Invalid email or password.")
    return _token_response(user, state)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email}
