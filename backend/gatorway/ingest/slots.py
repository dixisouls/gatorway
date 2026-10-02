"""Rules that turn scraped roadmap rows into slot kinds. See ARCHITECTURE.md section 2.2 / 3."""
from __future__ import annotations

import re
from dataclasses import dataclass

from gatorway.engine.ge import ge_tokens, has_ge_courses

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
_TAKE = re.compile(r"take\s+(one|two|three|four|five|six|\d+)\b", re.I)
_DEFAULT_SKIP = re.compile(r"adt|scholar|5[\s-]*year|transfer|credential", re.I)


@dataclass(frozen=True)
class SlotClass:
    slot_kind: str  # fixed | major_elective | free_elective
    swappable: bool
    counts_toward_major: bool


def parse_seats(title: str) -> int:
    """'Major Elective (15 Units Total) - Take Three' -> 3. No 'Take N' -> 1."""
    m = _TAKE.search(title or "")
    if not m:
        return 1
    word = m.group(1).lower()
    return _NUMBER_WORDS.get(word) or int(word)


def classify_slot(codes: list[str], title: str, tags: list[str], has_elective_pool: bool, major_codes: set[str] | None = None) -> SlotClass:
    """major_codes = courses listed in the program's non-GE requirement sections. Roadmap tags are inconsistent
    ("Core Computer Science Requirement" never says "major"), so a listed course counts toward the major as well."""
    major = any("major" in t.lower() for t in tags) or bool(major_codes and any(c in major_codes for c in codes))
    t = (title or "").lower()
    if codes:
        return SlotClass("fixed", False, major)
    if t.lstrip().startswith("or "):  # an alternate to the row above ("or University Elective if ..."), not an extra course
        return SlotClass("fixed", False, major)
    if re.match(r"\s*ge\s+areas?\b", t) and has_ge_courses(ge_tokens(title)):  # a GE requirement row: any course labelled for that area can fill it
        return SlotClass("ge", True, False)
    if "university elective" in t:
        return SlotClass("free_elective", True, False)
    if has_elective_pool and re.search(r"\bmajor\b.*\belectives?\b|^\s*upper[- ]division electives?\b", t):  # "Major Electives", "Major Upper-Division Electives - Take Two", ...
        return SlotClass("major_elective", True, True)
    return SlotClass("fixed", False, major)


def section_kind(heading: str | None) -> str:
    h = (heading or "").lower()
    if "elective" in h:
        return "elective"
    if "general education" in h or re.search(r"\bge\b", h):
        return "ge"
    if "core" in h or "required" in h or "requirement" in h or "prerequisite" in h:
        return "core"
    return "other"


def pick_pool_section(sections: list[dict]) -> int | None:
    """Index (into `sections`) of the elective section that lists courses; prefer a heading that is exactly 'Electives'."""
    candidates = [
        i for i, s in enumerate(sections)
        if section_kind(s.get("heading")) == "elective" and any(r.get("type") == "course" for r in s.get("rows", []))
    ]
    if not candidates:
        return None
    for i in candidates:
        if (sections[i].get("heading") or "").strip().lower() == "electives":
            return i
    return candidates[0]


def choose_default_roadmap(names: list[str]) -> int:
    """Index of the 'common' roadmap: first one that is not an ADT / scholars / 5-year / transfer / credential plan."""
    for i, n in enumerate(names):
        if not _DEFAULT_SKIP.search(n or ""):
            return i
    return 0
