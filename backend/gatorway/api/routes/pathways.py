from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from gatorway.db.models import SavedPathway, User
from gatorway.engine.repository import data_version, user_passed_codes
from gatorway.llm.orchestrator import PathwayResult, ServiceError

from ..deps import current_user, get_db, get_state, user_rate_limit
from ..errors import ApiError
from ..state import AppState

router = APIRouter(prefix="/pathways", tags=["pathways"])
_NOT_FOUND_HINTS = ("not found", "no roadmap", "does not belong", "no slot")
_SLOT_HINTS = ("not swappable",)


class PathwayRequest(BaseModel):
    program_id: int
    roadmap_id: int | None = None
    interest: str | None = Field(default=None, max_length=500)
    fresh: bool = False
    avoid: list[str] = Field(default_factory=list, max_length=20)


def _service_error(e: ServiceError) -> ApiError:
    message = str(e)
    lowered = message.lower()
    if any(hint in lowered for hint in _NOT_FOUND_HINTS):
        return ApiError(404, "not_found", message)
    if any(hint in lowered for hint in _SLOT_HINTS):
        return ApiError(422, "invalid_slot", message)
    return ApiError(503, "pathway_unavailable", "Pathway planning is temporarily unavailable.")


class BaselineRequest(BaseModel):
    program_id: int
    roadmap_id: int | None = None


@router.post("/baseline", dependencies=[Depends(user_rate_limit("baseline", 60, 3600))])
async def preview_baseline(body: BaselineRequest, user: User = Depends(current_user), db: Session = Depends(get_db), state: AppState = Depends(get_state)):
    if state.pathway_service is None:
        raise ApiError(503, "pathway_unavailable", "Pathway planning is not configured.")
    passed = user_passed_codes(db, user.id)
    try:
        pathway = await state.pathway_service.baseline(program_id=body.program_id, roadmap_id=body.roadmap_id, passed=passed)
    except ServiceError as e:
        raise _service_error(e)
    return {"pathway": pathway.model_dump(mode="json")}


@router.post("", dependencies=[Depends(user_rate_limit("pathways", 20, 3600))])
async def create_pathway(body: PathwayRequest, user: User = Depends(current_user), db: Session = Depends(get_db), state: AppState = Depends(get_state)):
    if state.pathway_service is None:
        raise ApiError(503, "pathway_unavailable", "Pathway planning is not configured.")
    passed = user_passed_codes(db, user.id)
    try:
        result = await state.pathway_service.create(
            program_id=body.program_id, roadmap_id=body.roadmap_id, passed=passed, interest=body.interest, data_version=data_version(db),
            fresh=body.fresh, avoid=body.avoid
        )
    except ServiceError as e:
        raise _service_error(e)
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


def _owned(db: Session, user: User, pathway_id: int) -> SavedPathway:
    row = db.scalar(select(SavedPathway).where(SavedPathway.id == pathway_id, SavedPathway.user_id == user.id))
    if row is None:
        raise ApiError(404, "not_found", f"Pathway {pathway_id} was not found.")
    return row


@router.get("/{pathway_id}")
def get_pathway(pathway_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, pathway_id)
    return {"id": row.id, **row.result}


@router.get("/{pathway_id}/slots/{slot_id}/options", dependencies=[Depends(user_rate_limit("options", 120, 3600))])
async def slot_options(
    pathway_id: int, slot_id: str, query: str = Query("", max_length=200), limit: int = Query(8, ge=1, le=15),
    user: User = Depends(current_user), db: Session = Depends(get_db), state: AppState = Depends(get_state),
):
    row = _owned(db, user, pathway_id)
    if state.pathway_service is None:
        raise ApiError(503, "pathway_unavailable", "Pathway planning is not configured.")
    result = PathwayResult.model_validate(row.result)
    text = query.strip()
    if not text and result.intent is not None and result.intent.specialization:
        text = result.intent.search_text()
    if not text:
        found = result.pathway.find_slot(slot_id)
        text = found[1].title if found else slot_id
    try:
        candidates = await state.pathway_service.options(
            pathway=result.pathway, passed=user_passed_codes(db, user.id), slot_id=slot_id, query=text, limit=limit
        )
    except ServiceError as e:
        raise _service_error(e)
    return {"slot_id": slot_id, "query": text, "candidates": candidates}
