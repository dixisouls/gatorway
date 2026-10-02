from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from gatorway.auth.security import decode_access_token
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
    uid = decode_access_token(creds.credentials, state.settings.jwt_secret)
    user = db.get(User, uid) if uid is not None else None
    if user is None:
        raise ApiError(401, "invalid_token", "Your session has expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"})
    return user


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
