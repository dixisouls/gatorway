"""Read queries shared by the REST API and the MCP tools, so both return the same shapes."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gatorway.db.models import Course, Program, RequirementSection, Roadmap


def _brief(p: Program) -> dict:
    return {"id": p.id, "title": p.title, "slug": p.slug, "college": p.college, "department": p.department,
            "degree_type": p.degree_type, "level": p.level, "concentration": p.concentration}


def list_programs(db: Session, query: str = "", level: str = "", limit: int = 20, offset: int = 0) -> list[dict]:
    stmt = select(Program).order_by(Program.title).limit(max(1, min(limit, 100))).offset(max(0, offset))
    if query.strip():
        stmt = stmt.where(Program.title.ilike(f"%{query.strip()}%"))
    if level:
        stmt = stmt.where(Program.level == level)
    return [_brief(p) for p in db.scalars(stmt)]


def program_detail(db: Session, program_id: int) -> dict | None:
    p = db.get(Program, program_id)
    if p is None:
        return None
    return {**_brief(p), "listed_units": p.listed_units, "source_url": p.source_url}


def roadmaps_of(db: Session, program_id: int) -> list[dict]:
    rows = db.scalars(select(Roadmap).where(Roadmap.program_id == program_id).order_by(Roadmap.id))
    return [{"id": r.id, "name": r.name, "is_default": r.is_default, "total_units_required": r.total_units_required,
             "major_units": r.major_units, "source_url": r.source_url} for r in rows]


def requirements_of(db: Session, program_id: int) -> list[dict]:
    rows = db.scalars(select(RequirementSection).where(RequirementSection.program_id == program_id).order_by(RequirementSection.position))
    return [{"id": s.id, "heading": s.heading, "kind": s.kind, "units": s.units_raw, "notes": s.notes or [],
             "courses": [i.raw_code for i in s.items]} for s in rows]


MAX_COURSE_CODES = 60


def courses_by_codes(db: Session, codes: list[str]) -> dict[str, dict]:
    """Display details for the given course codes. Unknown codes are left out."""
    wanted = list(dict.fromkeys(c.strip() for c in codes if c.strip()))[:MAX_COURSE_CODES]
    if not wanted:
        return {}
    rows = db.scalars(select(Course).where(Course.code.in_(wanted)))
    return {
        c.code: {
            "code": c.code, "title": c.title, "units_min": c.units_min, "units_max": c.units_max, "description": c.description,
            "prereq_text": c.prereq_text, "prereq_groups": c.prereq_groups or [], "attributes": c.attributes or [],
        }
        for c in rows
    }


# General education: courses carry their GE area in `attributes`, under the current label ("4: Social/Behavioral Sciences")
# and the older letter scheme ("D1: Social Sciences"). Area 2 (math) has no labelled courses in the catalog.
GE_ATTRIBUTES = {
    "1A": ("1A:", "A2:"), "1B": ("1B:", "A3:"), "1C": ("1C:", "A1:"),
    "3A": ("3A:", "C1:"), "3B": ("3B:", "C2:", "C3 or C2:"),
    "4": ("4:", "D1:", "D2:", "D3:"),
    "5A": ("5A:", "B1:"), "5B": ("5B:", "B2:"), "5C": ("5C:", "B3:"),
    "6": ("6:", "GE-F:"),
}
GE_GROUPS = {"1": ("1A", "1B", "1C"), "3": ("3A", "3B"), "5": ("5A", "5B", "5C")}
UPPER_DIVISION = 300


def ge_courses(db: Session, areas: list[str], limit: int = 80) -> list[dict]:
    """Courses that count for the given GE areas ("4", "5B", "3UD"...). A "UD" area lists upper-division courses, the others lower-division."""
    prefixes: set[str] = set()
    upper = False
    for raw in areas:
        token = raw.strip().upper()
        if token.endswith("UD"):
            upper, token = True, token[:-2]
        for base in GE_GROUPS.get(token, (token,)):
            prefixes.update(GE_ATTRIBUTES.get(base, ()))
    if not prefixes:
        return []
    rows = db.scalars(select(Course).where(func.jsonb_array_length(Course.attributes) > 0).order_by(Course.code))
    out = []
    for c in rows:
        if not any(a.startswith(p) for a in c.attributes or [] for p in prefixes):
            continue
        n = c.number_int
        if (n is not None and n >= UPPER_DIVISION) != upper:
            continue
        out.append({"code": c.code, "title": c.title, "units_min": c.units_min, "units_max": c.units_max,
                    "description": (c.description or "")[:240], "attributes": c.attributes or []})
        if len(out) == limit:
            break
    return out
