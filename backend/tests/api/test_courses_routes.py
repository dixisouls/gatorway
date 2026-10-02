import json
from pathlib import Path

import pytest

from gatorway.ingest.loader import ingest_all

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def loaded(db):
    ingest_all(db, json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text()))
    db.commit()


def test_course_details_by_code_are_public_and_skip_unknown_codes(client, loaded):
    r = client.get("/courses", params={"codes": "CSC 101,CSC 220,NOPE 1"})
    assert r.status_code == 200
    courses = r.json()["courses"]
    assert set(courses) == {"CSC 101", "CSC 220"}
    c = courses["CSC 220"]
    assert c["title"] == "Data Structures" and c["units_min"] == 3 and c["description"] == "Lists, trees and graphs."
    assert c["prereq_text"].startswith("Prerequisites:") and c["prereq_groups"]
    assert courses["CSC 101"]["prereq_groups"] == []


def test_empty_or_blank_codes_return_nothing(client, loaded):
    assert client.get("/courses").json() == {"courses": {}}
    assert client.get("/courses", params={"codes": " , ,"}).json() == {"courses": {}}


def test_only_the_first_sixty_distinct_codes_are_looked_up(client, loaded):
    codes = ",".join(["CSC 101"] * 100 + [f"X {i}" for i in range(70)] + ["CSC 220"])
    assert set(client.get("/courses", params={"codes": codes}).json()["courses"]) == {"CSC 101"}  # CSC 220 is the 72nd distinct code


@pytest.fixture
def ge_courses(db):
    from gatorway.db.models import Course

    def c(code, number, title, attrs):
        return Course(code=code, subject=code.split()[0], number=str(number), number_int=number, title=title, units_min=3, units_max=3, attributes=attrs, description=f"About {title}.")

    db.add_all([
        c("SOC 100", 100, "Intro Sociology", ["4: Social/Behavioral Sciences", "Social Justice"]),
        c("ANTH 110", 110, "Old-style Anthropology", ["D1: Social Sciences"]),
        c("SOC 350", 350, "Upper Sociology", ["4: Social/Behavioral Sciences"]),
        c("ART 101", 101, "Drawing", ["3A: Arts"]),
        c("ENG 114", 114, "First Year Writing", ["1A: English Composition"]),
        c("BIOL 100", 100, "Biology", ["5B: Biological Science"]),
        c("BIOL 101", 101, "Biology Lab", ["5C: Laboratory"]),
        c("CSC 101", 101, "Computing", []),
    ])
    db.commit()


def test_ge_course_list_for_an_area_uses_both_current_and_old_labels(client, ge_courses):
    r = client.get("/courses/ge", params={"areas": "4"})
    assert r.status_code == 200
    assert [c["code"] for c in r.json()["courses"]] == ["ANTH 110", "SOC 100"]  # lower division only; old D1 label counts
    first = r.json()["courses"][0]
    assert {"code", "title", "units_min", "description", "attributes"} <= set(first)


def test_upper_division_ge_rows_list_upper_division_courses(client, ge_courses):
    assert [c["code"] for c in client.get("/courses/ge", params={"areas": "4UD"}).json()["courses"]] == ["SOC 350"]


def test_a_combined_ge_row_lists_every_area_it_names_and_groups_expand(client, ge_courses):
    assert [c["code"] for c in client.get("/courses/ge", params={"areas": "5B,5C"}).json()["courses"]] == ["BIOL 100", "BIOL 101"]
    assert [c["code"] for c in client.get("/courses/ge", params={"areas": "3"}).json()["courses"]] == ["ART 101"]  # Area 3 = 3A + 3B
    assert [c["code"] for c in client.get("/courses/ge", params={"areas": "1"}).json()["courses"]] == ["ENG 114"]  # Area 1 = 1A + 1B + 1C


def test_unknown_or_missing_ge_areas_return_an_empty_list_not_an_error(client, ge_courses):
    assert client.get("/courses/ge").json()["courses"] == []
    assert client.get("/courses/ge", params={"areas": "99,xyz"}).json()["courses"] == []
