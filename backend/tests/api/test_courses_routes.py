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
