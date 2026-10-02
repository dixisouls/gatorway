from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gatorway import catalog_queries as q
from gatorway.db.models import Course, User, UserCourse
from gatorway.transcripts.extraction import passed_courses
from gatorway.transcripts.extractor_client import ExtractorError
from gatorway.transcripts.pdf import NoTextError, extract_text
from gatorway.transcripts.program_match import rank_programs

from ..deps import current_user, get_db, get_state, user_rate_limit
from ..errors import ApiError
from ..state import AppState

log = logging.getLogger(__name__)
router = APIRouter(tags=["transcripts"])
MAX_PDF_BYTES = 10 * 1024 * 1024


def _payload(db: Session, user: User) -> dict:
    rows = db.scalars(select(UserCourse).where(UserCourse.user_id == user.id).order_by(UserCourse.raw_code)).all()
    raw = user.transcript_program
    return {
        "program": {"raw": raw, "candidates": rank_programs(raw, q.all_programs(db)) if raw else []},
        "count": len(rows),
        "courses": [{"code": r.raw_code, "title": r.title, "grade": r.grade, "term": r.term, "flagged": r.flagged} for r in rows],
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

    try:
        redacted = await run_in_threadpool(state.redactor.redact, text)
    except Exception:  # fail closed: if redaction cannot run, the text goes nowhere
        log.exception("redaction failed; transcript not sent to the extractor")
        raise ApiError(503, "redaction_unavailable", "We couldn't prepare your transcript safely, so nothing was sent. Please try again shortly.")
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
        db.add(UserCourse(user_id=user.id, raw_code=c.code, course_id=ids.get(c.code), grade=c.grade, term=c.term, title=c.title, flagged=c.code not in ids))
    user.transcript_program = (extracted.program or "").strip()[:255] or None
    db.commit()
    return _payload(db, user)


@router.get("/me/courses")
def my_courses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _payload(db, user)


@router.delete("/me/courses", status_code=204)
def delete_my_courses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(UserCourse).where(UserCourse.user_id == user.id))
    user.transcript_program = None
    db.commit()
    return Response(status_code=204)
