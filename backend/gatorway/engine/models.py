"""Pure domain models for the pathway engine. No database, no network."""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class Slot(BaseModel):
    """One course-sized place in a roadmap term (a 'Take Three' row is split into three)."""

    slot_id: str
    codes: list[str] = Field(default_factory=list)  # 1 course, or 2 for lecture+lab pairs; [] = open slot
    title: str
    units: float = 0
    slot_kind: str = "fixed"  # fixed | major_elective | free_elective
    swappable: bool = False
    pool_section_id: int | None = None
    counts_toward_major: bool = False
    status: str = "planned"  # planned | passed | replaced


class Term(BaseModel):
    position: int
    label: str
    slots: list[Slot]


class Pathway(BaseModel):
    program_id: int
    program_title: str = ""
    program_level: str | None = None
    roadmap_id: int
    roadmap_name: str = ""
    total_units_required: float | None = None
    major_units_required: float | None = None
    terms: list[Term]
    unplaced_passed: list[str] = Field(default_factory=list)

    def all_slots(self) -> list[Slot]:
        return [s for t in sorted(self.terms, key=lambda t: t.position) for s in t.slots]

    def find_slot(self, slot_id: str) -> tuple[Term, Slot] | None:
        for t in self.terms:
            for s in t.slots:
                if s.slot_id == slot_id:
                    return t, s
        return None


class Edit(BaseModel):
    slot_id: str
    new_course_code: str
    reason: str = ""


class Violation(BaseModel):
    rule: str  # slot | pool | duplicate | units | prereq | unknown_course
    slot_id: str | None = None
    message: str

    def key(self) -> tuple:
        return (self.rule, self.slot_id, self.message)


class DroppedEdit(BaseModel):
    edit: Edit
    violations: list[Violation]


class EditsReport(BaseModel):
    pathway: Pathway
    applied: list[Edit] = Field(default_factory=list)
    dropped: list[DroppedEdit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@dataclass
class CourseInfo:
    code: str
    title: str = ""
    units_min: float = 0
    units_max: float = 0
    number_int: int | None = None
    prereq_groups: list[list[str]] = field(default_factory=list)  # AND of ORs
    concurrent_ok: set[str] = field(default_factory=set)
    prereq_warnings: list[str] = field(default_factory=list)


@dataclass
class Catalog:
    courses: dict[str, CourseInfo] = field(default_factory=dict)
    pools: dict[int, set[str]] = field(default_factory=dict)  # requirement_section_id -> course codes
