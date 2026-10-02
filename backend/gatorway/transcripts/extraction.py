"""Shapes returned by the extractor service, and turning them into a clean list of passed course codes."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .grades import is_passing


class ExtractedCourse(BaseModel):
    code: str
    title: str | None = None
    grade: str | None = None
    term: str | None = None


class ExtractedTranscript(BaseModel):
    is_sfsu_transcript: bool
    courses: list[ExtractedCourse] = Field(default_factory=list)


_CODE = re.compile(r"^\s*([A-Za-z&]{2,6})\s*[-_ ]?\s*(\d{2,3}[A-Za-z]{0,3})\s*$")


def normalize_code(raw: str | None) -> str | None:
    """'csc215' / 'CSC-215' / 'CSC 215' -> 'CSC 215'. None if it does not look like a course code."""
    m = _CODE.match((raw or "").replace("\xa0", " "))
    return f"{m.group(1).upper()} {m.group(2).upper()}" if m else None


def passed_courses(extracted: ExtractedTranscript) -> list[ExtractedCourse]:
    """One entry per course code that has at least one passing attempt (a repeat after an F still counts)."""
    best: dict[str, ExtractedCourse] = {}
    for c in extracted.courses:
        code = normalize_code(c.code)
        if code is None or not is_passing(c.grade):
            continue
        best.setdefault(code, c.model_copy(update={"code": code}))
    return sorted(best.values(), key=lambda c: c.code)
