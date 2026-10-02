from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gatorway.db.models import Course, User, UserCourse
from gatorway.transcripts.extraction import passed_courses
from gatorway.transcripts.extractor_client import ExtractorError
from gatorway.transcripts.pdf import NoTextError, extract_text

from ..deps import current_user, get_db, get_state, user_rate_limit
from ..errors import ApiError
from ..state import AppState

log = logging.getLogger(__name__)
router = APIRouter(tags=["transcripts"])
MAX_PDF_BYTES = 10 * 1024 * 1024


def _payload(db: Session, user_id: int) -> dict:
    rows = db.scalars(select(UserCourse).where(UserCourse.user_id == user_id).order_by(UserCourse.raw_code)).all()
    return {
        "count": len(rows),
        "courses": [{"code": r.raw_code, "grade": r.grade, "term": r.term, "flagged": r.flagged} for r in rows],
        "flagged": [r.raw_code for r in rows if r.flagged],
    }


@router.post("/transcripts", status_code=201, dependencies=[Depends(user_rate_limit("transcripts", 5, 3600))])
async def upload_transcript(file: UploadFile, user: User = Depends(current_user), db: Session = Depends(get_db), state: AppState = Depends(get_state)):
    data = await file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise ApiError(413, "file_too_large", "The PDF is larger than 10 MB.")
    if not data.startswith(b"%PDF"):
        raise ApiError(422, "unreadable_pdf", "Upload your transcript as a PDF file.")
    try:
        text = await run_in_threadpool(extract_text, data)
    except NoTextError as e:
        raise ApiError(422, "unreadable_pdf", str(e))

    redacted = state.redactor.redact(text)
    try:
        extracted = await state.extractor.extract(redacted)
    except ExtractorError as e:
        log.warning("extractor failed: %s", e)
        raise ApiError(502, "extractor_unavailable", "Transcript reading is temporarily unavailable. Please try again shortly.")
    if not extracted.is_sfsu_transcript:
        raise ApiError(422, "not_sfsu_transcript", "This does not look like an SFSU transcript. Only SFSU transcripts are supported.")

    passed = passed_courses(extracted)
    ids = dict(db.execute(select(Course.code, Course.id).where(Course.code.in_([c.code for c in passed]))).all()) if passed else {}
    db.execute(delete(UserCourse).where(UserCourse.user_id == user.id))
    for c in passed:
        db.add(UserCourse(user_id=user.id, raw_code=c.code, course_id=ids.get(c.code), grade=c.grade, term=c.term, flagged=c.code not in ids))
    db.commit()
    return _payload(db, user.id)


@router.get("/me/courses")
def my_courses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _payload(db, user.id)


@router.delete("/me/courses", status_code=204)
def delete_my_courses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(UserCourse).where(UserCourse.user_id == user.id))
    db.commit()
    return Response(status_code=204)
