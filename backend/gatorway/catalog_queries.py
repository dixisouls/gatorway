"""Read queries shared by the REST API and the MCP tools, so both return the same shapes."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from gatorway.db.models import Program, RequirementSection, Roadmap


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
