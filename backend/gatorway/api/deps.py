from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from gatorway.auth.firebase import AuthUnavailable, InvalidToken
from gatorway.auth.security import is_sfsu_email
from gatorway.auth.users import AccountConflict, resolve_user
from gatorway.db.models import User

from .errors import ApiError
from .state import AppState

_bearer = HTTPBearer(auto_error=False)


def get_state(request: Request) -> AppState:
    return request.app.state.gw


def get_db(state: AppState = Depends(get_state)) -> Iterator[Session]:
    with Session(state.engine) as session:
        yield session


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    state: AppState = Depends(get_state),
) -> User:
    if creds is None:
        raise ApiError(401, "not_authenticated", "Sign in first.", headers={"WWW-Authenticate": "Bearer"})
    try:
        identity = state.verifier.verify(creds.credentials)
    except InvalidToken:
        raise ApiError(401, "invalid_token", "Your session has expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"})
    except AuthUnavailable:
        raise ApiError(503, "auth_unavailable", "Sign-in is temporarily unavailable. Please try again shortly.")
    if not is_sfsu_email(identity.email):
        raise ApiError(403, "invalid_email", "Use your SFSU email address (it must end in sfsu.edu).")
    if state.settings.require_email_verified and not identity.email_verified:
        raise ApiError(403, "email_not_verified", "Verify your email address first, then sign in again.")
    try:
        return resolve_user(db, identity)
    except AccountConflict:
        raise ApiError(409, "account_conflict", "This email is linked to a different sign-in. Please contact support.")


def _enforce(state: AppState, endpoint: str, who: str, limit: int, window_s: int) -> None:
    allowed, retry_after = state.limiter.hit(endpoint, who, limit, window_s)
    if not allowed:
        raise ApiError(429, "rate_limited", "Too many requests. Please try again later.", headers={"Retry-After": str(retry_after)})


def ip_rate_limit(endpoint: str, limit: int, window_s: int):
    def dependency(request: Request, state: AppState = Depends(get_state)) -> None:
        _enforce(state, endpoint, request.client.host if request.client else "unknown", limit, window_s)

    return dependency


def user_rate_limit(endpoint: str, limit: int, window_s: int):
    def dependency(state: AppState = Depends(get_state), user: User = Depends(current_user)) -> None:
        _enforce(state, endpoint, str(user.id), limit, window_s)

    return dependency
