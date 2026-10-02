from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from gatorway import catalog_queries as q

from ..deps import get_db
from ..errors import ApiError

router = APIRouter(prefix="/programs", tags=["programs"])


def _require(db: Session, program_id: int) -> dict:
    detail = q.program_detail(db, program_id)
    if detail is None:
        raise ApiError(404, "not_found", f"Program {program_id} was not found.")
    return detail


@router.get("")
def search(query: str = "", level: str = "", limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return {"programs": q.list_programs(db, query, level, limit, offset)}


@router.get("/{program_id}")
def detail(program_id: int, db: Session = Depends(get_db)):
    return _require(db, program_id)


@router.get("/{program_id}/roadmaps")
def roadmaps(program_id: int, db: Session = Depends(get_db)):
    _require(db, program_id)
    return {"roadmaps": q.roadmaps_of(db, program_id)}


@router.get("/{program_id}/requirements")
def requirements(program_id: int, db: Session = Depends(get_db)):
    _require(db, program_id)
    return {"sections": q.requirements_of(db, program_id)}
