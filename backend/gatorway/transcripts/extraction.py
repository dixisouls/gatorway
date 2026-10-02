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
    program: str | None = None  # the degree or major as printed on the transcript
    courses: list[ExtractedCourse] = Field(default_factory=list)


# subjects are 1-5 letters, optionally followed by one more short word ("TH A", "C J", "I R", "AA S")
_CODE = re.compile(r"^([A-Za-z&]{1,5}(?: [A-Za-z&]{1,4})?)\s*[-_]?\s*(\d{2,3}[A-Za-z]{0,3})$")


def _squash(raw: str | None) -> str:
    return re.sub(r"\s+", " ", (raw or "").replace("\xa0", " ")).strip()


def normalize_code(raw: str | None) -> str | None:
    """'csc215' / 'CSC-215' / 'th a130' -> 'CSC 215' / 'TH A 130'. None if it does not look like a course code."""
    m = _CODE.match(_squash(raw))
    return f"{m.group(1).upper()} {m.group(2).upper()}" if m else None


def _loose_code(raw: str | None) -> str | None:
    """A code we cannot parse but that still looks like one (letters and digits): kept, never silently dropped."""
    s = _squash(raw).upper()
    return s if 3 <= len(s) <= 32 and re.search(r"[A-Z]", s) and re.search(r"\d", s) else None


def passed_courses(extracted: ExtractedTranscript) -> list[ExtractedCourse]:
    """One entry per course code that has at least one passing attempt (a repeat after an F still counts)."""
    best: dict[str, ExtractedCourse] = {}
    for c in extracted.courses:
        code = normalize_code(c.code) or _loose_code(c.code)
        if code is None or not is_passing(c.grade):
            continue
        best.setdefault(code, c.model_copy(update={"code": code, "term": clean_term(c.term)}))
    return sorted(best.values(), key=lambda c: c.code)


_SEASONS = {"fall": "Fall", "fa": "Fall", "spring": "Spring", "sp": "Spring", "spr": "Spring", "summer": "Summer", "su": "Summer", "sum": "Summer",
            "winter": "Winter", "wi": "Winter", "win": "Winter"}


def clean_term(raw: str | None) -> str | None:
    """A real semester in one readable form ("Fall 2023"), or None. The extractor sometimes puts a nearby label there ("Student ID",
    a redaction placeholder, a number); that must never be shown as a semester."""
    t = re.sub(r"\s+", " ", (raw or "").strip())
    if not t:
        return None
    if re.fullmatch(r"transfer( credit)?", t, re.I):
        return "Transfer credit"
    m = re.fullmatch(r"([A-Za-z]{2,6})\.?\s*(\d{4}|\d{2})", t)
    season, year = (m.group(1), m.group(2)) if m else (None, None)
    if not m and (m2 := re.fullmatch(r"(\d{4})\s+([A-Za-z]{2,6})", t)):
        year, season = m2.group(1), m2.group(2)
    if not season or season.lower() not in _SEASONS:
        return None
    return f"{_SEASONS[season.lower()]} {year if len(year) == 4 else '20' + year}"
