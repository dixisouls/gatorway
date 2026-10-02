"""Idempotent loader: scraper JSON -> Postgres (ARCHITECTURE.md section 3, steps 1-4 and 6)."""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gatorway.db.models import (Course, Meta, Program, RequirementItem, RequirementSection, Roadmap, RoadmapSlot, RoadmapTerm)

from .prereqs import build_prereq_groups, non_course_conditions
from .slots import choose_default_roadmap, classify_slot, parse_seats, pick_pool_section, section_kind

BATCH = 500


@dataclass
class IngestReport:
    courses: int = 0
    programs: int = 0
    sections: int = 0
    roadmaps: int = 0
    slots: int = 0
    slots_by_kind: dict[str, int] = field(default_factory=dict)
    unresolved_codes: set[str] = field(default_factory=set)
    programs_without_elective_pool: int = 0


def load_scrape_dir(path: str | Path) -> tuple[list[dict], list[dict]]:
    base = Path(path)
    return (
        json.loads((base / "sfsu_courses.json").read_text(encoding="utf-8")),
        json.loads((base / "sfsu_programs.json").read_text(encoding="utf-8")),
    )


def _code(raw: str) -> str:
    return raw.replace("\xa0", " ").strip()


def _leading_int(number: str | None) -> int | None:
    m = re.match(r"\d+", number or "")
    return int(m.group()) if m else None


def _units(raw: str | None) -> float | None:
    nums = re.findall(r"\d+(?:\.\d+)?", raw or "")
    return float(nums[0]) if nums else None


def ingest_courses(db: Session, records: list[dict]) -> dict[str, int]:
    """Upsert every course by code. Embedding columns are left alone (the embedding step owns them)."""
    rows: dict[str, dict] = {}
    for rec in records:
        code = rec.get("course_code")
        if not code:
            continue
        codes = [_code(c) for c in rec.get("prerequisite_courses") or []]
        groups, concurrent = build_prereq_groups(rec.get("prerequisites"), codes)
        rows[code] = dict(
            code=code, subject=rec.get("subject"), number=rec.get("number"), number_int=_leading_int(rec.get("number")),
            title=rec.get("title") or "", units_min=rec.get("units_min") or 0, units_max=rec.get("units_max") or 0,
            description=rec.get("description"), prereq_text=rec.get("prerequisites"), prereq_codes=codes,
            prereq_groups=groups, concurrent_ok=concurrent, prereq_warnings=non_course_conditions(rec.get("prerequisites"), codes),
            attributes=rec.get("course_attributes") or [],
        )
    values = list(rows.values())
    for i in range(0, len(values), BATCH):
        stmt = insert(Course)
        stmt = stmt.on_conflict_do_update(index_elements=["code"], set_={k: stmt.excluded[k] for k in values[0] if k != "code"})
        db.execute(stmt, values[i : i + BATCH])
    db.flush()
    return {code: cid for code, cid in db.execute(select(Course.code, Course.id))}


def ingest_program(db: Session, rec: dict, code_to_id: dict[str, int], report: IngestReport) -> None:
    prog = db.scalar(select(Program).where(Program.source_url == rec["source_url"])) or Program(source_url=rec["source_url"])
    req = rec.get("requirements") or {}
    prog.slug, prog.title = rec["slug"], rec["title"]
    prog.college, prog.college_slug = rec.get("college"), rec.get("college_slug")
    prog.department, prog.department_slug = rec.get("department"), rec.get("department_slug")
    prog.degree_type, prog.level, prog.concentration = rec.get("degree_type"), rec.get("level"), rec.get("concentration")
    prog.listed_units = req.get("total_units")
    db.add(prog)
    db.flush()  # stable id: saved pathways refer to program ids
    prog.sections.clear()
    prog.roadmaps.clear()
    db.flush()  # children are recreated from scratch on every run

    sections_raw = req.get("sections") or []
    section_objs: list[RequirementSection] = []
    for pos, s in enumerate(sections_raw):
        sec = RequirementSection(
            position=pos, heading=s.get("heading"), units_raw=s.get("units_raw"), units_min=_units(s.get("units_raw")),
            kind=section_kind(s.get("heading")), notes=s.get("notes") or [],
        )
        n = 0
        for row in s.get("rows", []):
            if row.get("type") != "course":
                continue
            for raw in row.get("codes", []):
                code = _code(raw)
                cid = code_to_id.get(code)
                if cid is None:
                    report.unresolved_codes.add(code)
                sec.items.append(RequirementItem(position=n, course_id=cid, raw_code=code, or_with_previous=bool(row.get("or_with_previous"))))
                n += 1
        prog.sections.append(sec)
        section_objs.append(sec)
    db.flush()
    report.sections += len(section_objs)

    pool_index = pick_pool_section(sections_raw)
    pool_id = section_objs[pool_index].id if pool_index is not None else None
    if req and pool_id is None:
        report.programs_without_elective_pool += 1

    major_codes = {
        _code(c) for s in sections_raw if section_kind(s.get("heading")) != "ge"
        for r in s.get("rows", []) if r.get("type") == "course" for c in r.get("codes", [])
    }

    roadmaps_raw = rec.get("roadmaps") or []
    default_index = choose_default_roadmap([r["name"] for r in roadmaps_raw]) if roadmaps_raw else None
    for ri, r in enumerate(roadmaps_raw):
        content = r["content"]
        rm = Roadmap(
            name=r["name"], source_url=r["source_url"], total_units_required=content.get("total_units_required"),
            major_units=content.get("major_units"), is_default=(ri == default_index),
        )
        pos = 0
        for grid in content.get("grids", []):
            for term in grid.get("terms", []):
                t = RoadmapTerm(position=pos, label=term.get("term") or f"Term {pos + 1}")
                pos += 1
                for i, item in enumerate(term.get("items", [])):
                    codes = [_code(c) for c in item.get("codes", [])]
                    report.unresolved_codes.update(c for c in codes if c not in code_to_id)
                    title = item.get("title") or ", ".join(codes) or "Untitled"  # some scraped course rows have no title
                    sc = classify_slot(codes, title, item.get("tags") or [], pool_id is not None, major_codes)
                    t.slots.append(RoadmapSlot(
                        position=i, codes=codes, title=title, tags=item.get("tags") or [], footnotes=item.get("footnotes") or [],
                        units=item.get("units_min") or 0, seats=parse_seats(title) if sc.swappable else 1,
                        slot_kind=sc.slot_kind, swappable=sc.swappable, counts_toward_major=sc.counts_toward_major,
                        pool_section_id=pool_id if sc.slot_kind == "major_elective" else None,
                    ))
                    report.slots += 1
                    report.slots_by_kind[sc.slot_kind] = report.slots_by_kind.get(sc.slot_kind, 0) + 1
                rm.terms.append(t)
        prog.roadmaps.append(rm)
        report.roadmaps += 1
    db.flush()


def ingest_all(db: Session, courses: list[dict], programs: list[dict]) -> IngestReport:
    report = IngestReport()
    code_to_id = ingest_courses(db, courses)
    report.courses = len(code_to_id)
    for rec in programs:
        ingest_program(db, rec, code_to_id, report)
        report.programs += 1
    db.merge(Meta(key="data_version", value=datetime.now(timezone.utc).isoformat()))
    db.flush()
    return report
