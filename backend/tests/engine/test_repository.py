import json
from pathlib import Path

import pytest
from sqlalchemy import select

from gatorway import catalog_queries as q
from gatorway.db.models import Meta, Program, RequirementSection, User, UserCourse
from gatorway.engine import repository as repo
from gatorway.ingest.loader import ingest_all

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def loaded(db):
    ingest_all(db, json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text()))
    db.commit()
    return db


def program_id(db):
    return db.scalar(select(Program.id).where(Program.slug == "bs-mini-computer-science"))


def test_catalog_has_prereq_groups_and_pools(loaded):
    cat = repo.get_catalog(loaded)
    assert cat.courses["CSC 215"].prereq_groups == [["CSC 101"]] and cat.courses["CSC 220"].prereq_warnings == ["permission of the instructor"]
    pool_id = loaded.scalar(select(RequirementSection.id).where(RequirementSection.heading == "Electives"))
    assert cat.pools[pool_id] == {"CSC 600", "CSC 601", "XYZ 999"}


def test_catalog_is_cached_per_data_version_and_refreshed_after_reingest(loaded):
    assert repo.get_catalog(loaded) is repo.get_catalog(loaded)
    old = repo.get_catalog(loaded)
    loaded.merge(Meta(key="data_version", value="changed")); loaded.commit()
    assert repo.get_catalog(loaded) is not old


def test_default_roadmap_is_chosen_and_take_two_rows_are_split_per_seat(loaded):
    pid = program_id(loaded)
    path = repo.build_baseline_for(loaded, pid, None, [])
    assert path.roadmap_name.endswith("QR Pathway 1/2") and path.total_units_required == 120 and path.program_level == "undergraduate"
    slots = {s.slot_id: s for s in path.all_slots()}
    seats = [s for s in slots.values() if s.slot_kind == "major_elective"]
    assert len(seats) == 2 and all(s.units == 3 and s.swappable and s.pool_section_id for s in seats)
    assert seats[0].slot_id.endswith("-1") and seats[1].slot_id.endswith("-2")
    assert [t.label for t in path.terms] == ["First Semester", "Second Semester", "Third Semester"]


def test_baseline_marks_passed_and_fills_a_major_elective_from_the_pool(loaded):
    path = repo.build_baseline_for(loaded, program_id(loaded), None, ["CSC 101", "CSC 601", "ENGL 114"])
    by_title = {s.title: s for s in path.all_slots()}
    assert by_title["Introduction to Computing"].status == "passed"
    filled = [s for s in path.all_slots() if s.slot_kind == "major_elective" and s.status == "passed"]
    assert [s.codes for s in filled] == [["CSC 601"]] and path.unplaced_passed == ["ENGL 114"]


def test_explicit_roadmap_must_belong_to_the_program(loaded):
    pid = program_id(loaded)
    minor = loaded.scalar(select(Program.id).where(Program.slug == "minor-mini-computing"))
    other_roadmap = repo.pick_roadmap(loaded, pid, None).id
    with pytest.raises(repo.RoadmapNotFound):
        repo.build_baseline_for(loaded, minor, other_roadmap, [])
    with pytest.raises(repo.RoadmapNotFound):  # a program with no roadmaps
        repo.build_baseline_for(loaded, minor, None, [])
    with pytest.raises(repo.ProgramNotFound):
        repo.build_baseline_for(loaded, 99999, None, [])


def test_user_passed_codes(loaded):
    u = User(email="a@sfsu.edu", password_hash="x"); loaded.add(u); loaded.commit()
    loaded.add_all([UserCourse(user_id=u.id, raw_code="CSC 101"), UserCourse(user_id=u.id, raw_code="MATH 226", flagged=True)]); loaded.commit()
    assert sorted(repo.user_passed_codes(loaded, u.id)) == ["CSC 101", "MATH 226"]


def test_catalog_queries(loaded):
    pid = program_id(loaded)
    assert [p["slug"] for p in q.list_programs(loaded, query="mini computer")] == ["bs-mini-computer-science"]
    assert [p["slug"] for p in q.list_programs(loaded, level="minor")] == ["minor-mini-computing"]
    detail = q.program_detail(loaded, pid)
    assert detail["title"].startswith("Bachelor of Science") and detail["degree_type"] == "B.S." and q.program_detail(loaded, 0) is None
    rms = q.roadmaps_of(loaded, pid)
    assert [r["is_default"] for r in rms] == [False, True] and rms[1]["total_units_required"] == 120
    reqs = q.requirements_of(loaded, pid)
    elective = next(s for s in reqs if s["heading"] == "Electives")
    assert elective["courses"] == ["CSC 600", "CSC 601", "XYZ 999"] and elective["kind"] == "elective" and elective["notes"] == ["Choose two."]
