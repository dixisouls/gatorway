from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from gatorway import catalog_queries as q

from ..deps import get_db

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("")
def by_codes(codes: str = Query("", max_length=2000, description="comma-separated course codes"), db: Session = Depends(get_db)):
    return {"courses": q.courses_by_codes(db, codes.split(","))}


@router.get("/ge")
def ge(areas: str = Query("", max_length=200, description="comma-separated GE areas, e.g. 4 or 5B,5C or 3UD"), db: Session = Depends(get_db)):
    wanted = [a for a in areas.split(",") if a.strip()]
    return {"areas": wanted, "courses": q.ge_courses(db, wanted)}
