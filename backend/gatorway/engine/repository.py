"""Database -> engine objects. The engine itself never touches the database."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from gatorway.db.models import Course, Meta, Program, RequirementItem, RequirementSection, Roadmap, UserCourse

from .baseline import build_baseline, split_seats
from .models import Catalog, CourseInfo, Pathway, Slot, Term


class ProgramNotFound(LookupError):
    pass


class RoadmapNotFound(LookupError):
    pass


_catalog_cache: dict[str, Catalog] = {}


def data_version(db: Session) -> str:
    return db.scalar(select(Meta.value).where(Meta.key == "data_version")) or "0"


def get_catalog(db: Session) -> Catalog:
    """All courses (without embeddings) and every elective pool, cached for the current data_version."""
    version = data_version(db)
    cached = _catalog_cache.get(version)
    if cached is not None:
        return cached
    courses = {}
    cols = (Course.code, Course.title, Course.units_min, Course.units_max, Course.number_int, Course.prereq_groups, Course.concurrent_ok, Course.prereq_warnings, Course.attributes)
    for code, title, umin, umax, num, groups, conc, warns, attrs in db.execute(select(*cols)):
        courses[code] = CourseInfo(code=code, title=title, units_min=umin or 0, units_max=umax or 0, number_int=num,
                                   prereq_groups=groups or [], concurrent_ok=set(conc or []), prereq_warnings=warns or [], attributes=attrs or [])
    pools: dict[int, set[str]] = {}
    stmt = select(RequirementItem.section_id, RequirementItem.raw_code).join(RequirementSection).where(RequirementSection.kind == "elective")
    for section_id, code in db.execute(stmt):
        pools.setdefault(section_id, set()).add(code)
    catalog = Catalog(courses=courses, pools=pools)
    _catalog_cache.clear()
    _catalog_cache[version] = catalog
    return catalog


def pick_roadmap(db: Session, program_id: int, roadmap_id: int | None = None) -> Roadmap:
    if roadmap_id is not None:
        rm = db.scalar(select(Roadmap).where(Roadmap.id == roadmap_id, Roadmap.program_id == program_id))
        if rm is None:
            raise RoadmapNotFound(f"roadmap {roadmap_id} does not belong to program {program_id}")
        return rm
    rm = db.scalar(select(Roadmap).where(Roadmap.program_id == program_id, Roadmap.is_default.is_(True)).limit(1)) or db.scalar(
        select(Roadmap).where(Roadmap.program_id == program_id).order_by(Roadmap.id).limit(1)
    )
    if rm is None:
        raise RoadmapNotFound(f"program {program_id} has no roadmap")
    return rm


def load_skeleton(program: Program, roadmap: Roadmap) -> Pathway:
    terms = []
    for t in roadmap.terms:
        slots: list[Slot] = []
        for s in t.slots:
            base = Slot(slot_id=str(s.id), label=s.title, codes=list(s.codes or []), title=s.title, units=s.units or 0, slot_kind=s.slot_kind,
                        swappable=s.swappable, pool_section_id=s.pool_section_id, counts_toward_major=s.counts_toward_major)
            slots.extend(split_seats(base, s.seats if s.swappable else 1))
        terms.append(Term(position=t.position, label=t.label, slots=slots))
    return Pathway(program_id=program.id, program_title=program.title, program_level=program.level, roadmap_id=roadmap.id,
                   roadmap_name=roadmap.name, total_units_required=roadmap.total_units_required,
                   major_units_required=roadmap.major_units, terms=terms)


def build_baseline_for(db: Session, program_id: int, roadmap_id: int | None, passed: list[str]) -> Pathway:
    program = db.get(Program, program_id)
    if program is None:
        raise ProgramNotFound(f"program {program_id} not found")
    roadmap = pick_roadmap(db, program_id, roadmap_id)
    return build_baseline(load_skeleton(program, roadmap), set(passed), get_catalog(db))


def user_passed_codes(db: Session, user_id: int) -> list[str]:
    return list(db.scalars(select(UserCourse.raw_code).where(UserCourse.user_id == user_id)))
