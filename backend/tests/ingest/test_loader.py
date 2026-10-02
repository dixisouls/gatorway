import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from gatorway.db.models import Course, Meta, Program, RequirementItem, RequirementSection, Roadmap, RoadmapSlot
from gatorway.ingest.loader import ingest_all

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def data():
    return json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text())


def run(db, data):
    report = ingest_all(db, *data)
    db.commit()
    return report


def test_courses_are_loaded_with_prerequisite_logic(db, data):
    report = run(db, data)
    assert report.courses == 8
    c220 = db.scalar(select(Course).where(Course.code == "CSC 220"))
    assert c220.prereq_groups == [["CSC 215", "CSC 210"]] and c220.prereq_warnings == ["permission of the instructor"]
    assert db.scalar(select(Course).where(Course.code == "CSC 600")).concurrent_ok == ["CSC 220"]
    assert db.scalar(select(Course).where(Course.code == "CSC 850")).number_int == 850
    assert db.scalar(select(Course).where(Course.code == "CSC 101")).prereq_groups == []


def test_requirement_sections_items_and_unresolved_codes(db, data):
    report = run(db, data)
    prog = db.scalar(select(Program).where(Program.slug == "bs-mini-computer-science"))
    assert prog.listed_units == 21 and prog.level == "undergraduate"
    kinds = {s.heading: s.kind for s in prog.sections}
    assert kinds["Core Requirements"] == "core" and kinds["Electives"] == "elective"
    elective = next(s for s in prog.sections if s.heading == "Electives")
    assert [i.raw_code for i in elective.items] == ["CSC 600", "CSC 601", "XYZ 999"]
    assert [i.course_id is not None for i in elective.items] == [True, True, False]
    assert report.unresolved_codes == {"XYZ 999"}


def test_roadmaps_default_and_slot_classification(db, data):
    run(db, data)
    prog = db.scalar(select(Program).where(Program.slug == "bs-mini-computer-science"))
    adt, qr = prog.roadmaps
    assert (adt.is_default, qr.is_default) == (False, True)  # the ADT roadmap is never the "common" one
    assert qr.total_units_required == 120 and qr.major_units == 21
    slots = [s for t in qr.terms for s in t.slots]
    by_title = {s.title: s for s in slots}
    major = by_title["Major Elective (6 Units Total) - Take Two"]
    pool = db.scalar(select(RequirementSection).where(RequirementSection.heading == "Electives"))
    assert (major.slot_kind, major.swappable, major.seats, major.units, major.pool_section_id) == ("major_elective", True, 2, 6, pool.id)
    free = by_title["SF State Studies or University Elective"]
    assert (free.slot_kind, free.swappable, free.pool_section_id) == ("free_elective", True, None)
    assert by_title["GE Area 4: Social and Behavioral Sciences"].swappable is False
    core = by_title["Introduction to Computing"]
    assert (core.slot_kind, core.swappable, core.counts_toward_major) == ("fixed", False, True)


def test_program_without_roadmaps_keeps_requirements(db, data):
    run(db, data)
    minor = db.scalar(select(Program).where(Program.slug == "minor-mini-computing"))
    assert minor.roadmaps == [] and len(minor.sections) == 1


def test_ingest_is_idempotent_and_keeps_program_ids(db, data):
    run(db, data)
    first_id = db.scalar(select(Program.id).where(Program.slug == "bs-mini-computer-science"))
    v1 = db.get(Meta, "data_version").value
    report = run(db, data)
    counts = {m: db.scalar(select(func.count()).select_from(m)) for m in (Course, Program, RequirementSection, RequirementItem, Roadmap, RoadmapSlot)}
    assert counts[Course] == 8 and counts[Program] == 2 and counts[Roadmap] == 2
    assert db.scalar(select(Program.id).where(Program.slug == "bs-mini-computer-science")) == first_id
    assert db.get(Meta, "data_version").value != v1 and report.programs == 2


def test_reingest_applies_changed_data(db, data):
    run(db, data)
    data[0][1]["title"] = "Intermediate Programming (renamed)"
    data[1][0]["roadmaps"][1]["content"]["total_units_required"] = 124
    run(db, data)
    assert db.scalar(select(Course.title).where(Course.code == "CSC 215")).endswith("(renamed)")
    assert db.scalar(select(Roadmap.total_units_required).where(Roadmap.is_default)) == 124


def test_program_with_no_elective_list_makes_elective_slots_fixed(db, data):
    courses, programs = data
    programs[0]["requirements"]["sections"] = [s for s in programs[0]["requirements"]["sections"] if s["heading"] != "Electives"]
    report = run(db, (courses, programs))
    major = db.scalar(select(RoadmapSlot).where(RoadmapSlot.title.like("Major Elective%")))
    assert major.swappable is False and major.slot_kind == "fixed"
    assert report.programs_without_elective_pool >= 1
