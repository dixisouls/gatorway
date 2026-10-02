from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from gatorway.db.models import SavedPathway, User
from gatorway.engine.repository import data_version, user_passed_codes
from gatorway.llm.orchestrator import ServiceError

from ..deps import current_user, get_db, get_state, user_rate_limit
from ..errors import ApiError
from ..state import AppState

router = APIRouter(prefix="/pathways", tags=["pathways"])
_NOT_FOUND_HINTS = ("not found", "no roadmap", "does not belong")


class PathwayRequest(BaseModel):
    program_id: int
    roadmap_id: int | None = None
    interest: str | None = Field(default=None, max_length=500)


@router.post("", dependencies=[Depends(user_rate_limit("pathways", 20, 3600))])
async def create_pathway(body: PathwayRequest, user: User = Depends(current_user), db: Session = Depends(get_db), state: AppState = Depends(get_state)):
    if state.pathway_service is None:
        raise ApiError(503, "pathway_unavailable", "Pathway planning is not configured.")
    passed = user_passed_codes(db, user.id)
    try:
        result = await state.pathway_service.create(
            program_id=body.program_id, roadmap_id=body.roadmap_id, passed=passed, interest=body.interest, data_version=data_version(db)
        )
    except ServiceError as e:
        message = str(e)
        if any(hint in message.lower() for hint in _NOT_FOUND_HINTS):
            raise ApiError(404, "not_found", message)
        raise ApiError(503, "pathway_unavailable", "Pathway planning is temporarily unavailable.")
    payload = result.model_dump(mode="json")
    saved = SavedPathway(user_id=user.id, program_id=body.program_id, roadmap_id=result.pathway.roadmap_id,
                         interest_raw=body.interest, intent=payload["intent"], result=payload)
    db.add(saved)
    db.commit()
    return {"id": saved.id, **payload}


@router.get("")
def list_pathways(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedPathway).where(SavedPathway.user_id == user.id).order_by(SavedPathway.id.desc())).all()
    return {"pathways": [{"id": r.id, "program_id": r.program_id, "interest": r.interest_raw, "created_at": r.created_at.isoformat()} for r in rows]}


@router.get("/{pathway_id}")
def get_pathway(pathway_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(SavedPathway).where(SavedPathway.id == pathway_id, SavedPathway.user_id == user.id))
    if row is None:
        raise ApiError(404, "not_found", f"Pathway {pathway_id} was not found.")
    return {"id": row.id, **row.result}
