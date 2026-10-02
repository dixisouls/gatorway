import json
from pathlib import Path

import pytest
from sqlalchemy import select

from gatorway.db.models import Program
from gatorway.ingest.loader import ingest_all

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def pid(db):
    ingest_all(db, json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text()))
    db.commit()
    return db.scalar(select(Program.id).where(Program.slug == "bs-mini-computer-science"))


def test_program_search_and_detail_are_public(client, pid):
    assert [p["slug"] for p in client.get("/programs", params={"query": "mini computer"}).json()["programs"]] == ["bs-mini-computer-science"]
    assert [p["slug"] for p in client.get("/programs", params={"level": "minor"}).json()["programs"]] == ["minor-mini-computing"]
    assert len(client.get("/programs", params={"limit": 1}).json()["programs"]) == 1
    detail = client.get(f"/programs/{pid}").json()
    assert detail["degree_type"] == "B.S." and detail["level"] == "undergraduate"


def test_roadmaps_and_requirements(client, pid):
    rms = client.get(f"/programs/{pid}/roadmaps").json()["roadmaps"]
    assert [r["is_default"] for r in rms] == [False, True]
    sections = client.get(f"/programs/{pid}/requirements").json()["sections"]
    assert {s["heading"] for s in sections if s["heading"]} == {"Core Requirements", "Electives"}


@pytest.mark.parametrize("path", ["", "/roadmaps", "/requirements"])
def test_unknown_program_is_a_404_with_the_error_envelope(client, pid, path):
    r = client.get(f"/programs/99999{path}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
