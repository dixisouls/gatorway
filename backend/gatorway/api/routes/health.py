from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_state
from ..state import AppState

router = APIRouter(tags=["health"])


@router.get("/health")
def health(state: AppState = Depends(get_state)):
    postgres = redis_ok = False
    try:
        with Session(state.engine) as db:
            db.execute(text("select 1"))
        postgres = True
    except Exception:
        pass
    try:
        state.redis.ping()
        redis_ok = True
    except Exception:
        pass
    body = {"ok": postgres and redis_ok, "postgres": postgres, "redis": redis_ok}
    return JSONResponse(body, status_code=200 if body["ok"] else 503)
