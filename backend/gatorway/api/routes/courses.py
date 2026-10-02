from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from gatorway import catalog_queries as q

from ..deps import get_db

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("")
def by_codes(codes: str = Query("", max_length=2000, description="comma-separated course codes"), db: Session = Depends(get_db)):
    return {"courses": q.courses_by_codes(db, codes.split(","))}
