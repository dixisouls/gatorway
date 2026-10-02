import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from sqlalchemy import select
from sqlalchemy.orm import Session

from gatorway.api.main import create_app
from gatorway.cache.store import Cache, RateLimiter
from gatorway.db.models import Program, UserCourse
from gatorway.engine.models import Edit
from gatorway.engine.repository import get_catalog
from gatorway.ingest.embeddings import HashingEmbedder, embed_courses
from gatorway.ingest.loader import ingest_all
from gatorway.llm.orchestrator import PathwayService
from gatorway.llm.ports import Intent
from gatorway.mcp_server.deps import Deps
from gatorway.mcp_server.server import create_server

FIX = Path(__file__).resolve().parents[1] / "fixtures"
TOOLS = {"get_baseline", "get_requirements", "search_courses", "validate_edits"}


class ScriptedLlm:
    """Stands in for Gemini: reads the baseline through the real MCP tool, then picks the first free-elective slot."""

    def __init__(self, picks=("ART 101",)):
        self.picks, self.edit_calls = list(picks), 0

    async def parse_intent(self, interest):
        return Intent(specialization=True, topics=["drawing"], keywords=["art"], summary=interest)

    async def propose_edits(self, session_id, mcp, allowed, intent, feedback):
        self.edit_calls += 1
        base = (await mcp.call_tool("get_baseline", {"session_id": session_id})).structured_content
        free = next(s for t in base["terms"] for s in t["slots"] if s["kind"] == "free_elective")
        return [Edit(slot_id=free["slot_id"], new_course_code=c, reason="matches the interest") for c in self.picks]


@pytest.fixture
def world(engine, db, redis_client, make_state):
    ingest_all(db, json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text()))
    db.commit()
    embed_courses(db, HashingEmbedder())

    def build(redis_obj=None, llm=None):
        r = redis_obj if redis_obj is not None else redis_client
        cache = Cache(r)

        @contextmanager
        def session():
            with Session(engine) as s:
                yield s

        server = create_server(Deps(db=session, cache=cache, embedder=HashingEmbedder(), embed_model="hash"))

        def catalog():
            with Session(engine) as s:
                return get_catalog(s)

        llm = llm or ScriptedLlm()
        service = PathwayService(llm=llm, cache=cache, catalog_provider=catalog, mcp_factory=lambda: Client(server), allowed_tools=TOOLS, model_name="m")
        state = make_state(redis=r, cache=cache, limiter=RateLimiter(r), pathway_service=service)
        return TestClient(create_app(state, init_db_on_startup=False)), llm

    pid = db.scalar(select(Program.id).where(Program.slug == "bs-mini-computer-science"))
    minor = db.scalar(select(Program.id).where(Program.slug == "minor-mini-computing"))
    return build, pid, minor


def headers(client, email="s@sfsu.edu"):
    r = client.post("/auth/signup", json={"email": email, "password": "correct-horse-battery"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]["id"]


def slots(result):
    return [s for t in result["pathway"]["terms"] for s in t["slots"]]


def test_no_interest_returns_the_baseline_without_calling_gemini(world):
    build, pid, _ = world
    client, llm = build()
    h, _ = headers(client)
    r = client.post("/pathways", json={"program_id": pid}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] == [] and body["note"] is None and llm.edit_calls == 0
    assert [t["label"] for t in body["pathway"]["terms"]] == ["First Semester", "Second Semester", "Third Semester"]
    assert body["pathway"]["roadmap_name"].endswith("QR Pathway 1/2") and sum(1 for s in slots(body) if s["swappable"]) == 3


def test_interest_swaps_a_free_elective_and_the_result_is_saved_and_listed(world):
    build, pid, _ = world
    client, _ = build()
    h, _ = headers(client)
    body = client.post("/pathways", json={"program_id": pid, "interest": "I like drawing"}, headers=h).json()
    assert [(a["new_course_code"], a["title"]) for a in body["applied"]] == [("ART 101", "Drawing")]
    swapped = next(s for s in slots(body) if s["status"] == "replaced")
    assert swapped["codes"] == ["ART 101"] and body["intent"]["specialization"] is True
    listed = client.get("/pathways", headers=h).json()["pathways"]
    assert len(listed) == 1 and listed[0]["interest"] == "I like drawing"
    again = client.get(f"/pathways/{body['id']}", headers=h).json()
    assert again["applied"] == body["applied"] and again["id"] == body["id"]


def test_passed_courses_from_the_saved_transcript_are_marked(world, db):
    build, pid, _ = world
    client, _ = build()
    h, uid = headers(client)
    db.add(UserCourse(user_id=uid, raw_code="CSC 101")); db.commit()
    body = client.post("/pathways", json={"program_id": pid}, headers=h).json()
    assert next(s for s in slots(body) if s["codes"] == ["CSC 101"])["status"] == "passed"


def test_an_edit_that_would_skip_a_prerequisite_is_dropped_not_applied(world):
    build, pid, _ = world
    client, _ = build(llm=ScriptedLlm(picks=("CSC 600",)))  # CSC 600 needs CSC 220, which is scheduled after the free-elective slot
    h, _ = headers(client)
    body = client.post("/pathways", json={"program_id": pid, "interest": "web apps"}, headers=h).json()
    assert body["applied"] == [] and body["dropped"] and body["dropped"][0]["violations"][0]["rule"] == "prereq"
    assert all(s["status"] != "replaced" for s in slots(body))


def test_unknown_program_and_foreign_roadmap_are_404(world):
    build, pid, minor = world
    client, _ = build()
    h, _ = headers(client)
    r = client.post("/pathways", json={"program_id": 99999}, headers=h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    own_roadmap = client.get(f"/programs/{pid}/roadmaps").json()["roadmaps"][0]["id"]
    assert client.post("/pathways", json={"program_id": minor, "roadmap_id": own_roadmap}, headers=h).status_code == 404
    assert client.post("/pathways", json={"program_id": minor}, headers=h).status_code == 404  # a program with no roadmap


def test_pathways_require_login_and_are_private_to_their_owner(world):
    build, pid, _ = world
    client, _ = build()
    assert client.post("/pathways", json={"program_id": pid}).status_code == 401
    mine, _ = headers(client, "a@sfsu.edu")
    theirs, _ = headers(client, "b@sfsu.edu")
    saved = client.post("/pathways", json={"program_id": pid}, headers=mine).json()
    assert client.get(f"/pathways/{saved['id']}", headers=theirs).status_code == 404
    assert client.get("/pathways", headers=theirs).json()["pathways"] == []


def test_pathway_requests_are_rate_limited(world):
    build, pid, _ = world
    client, _ = build()
    h, _ = headers(client)
    codes = [client.post("/pathways", json={"program_id": pid}, headers=h).status_code for _ in range(21)]
    assert codes[:20] == [200] * 20 and codes[20] == 429


def test_overlong_interest_is_a_validation_error(world):
    build, pid, _ = world
    client, _ = build()
    h, _ = headers(client)
    assert client.post("/pathways", json={"program_id": pid, "interest": "x" * 501}, headers=h).status_code == 422


def test_redis_down_still_returns_the_baseline_with_a_note(world, broken_redis):
    build, pid, _ = world
    client, _ = build(redis_obj=broken_redis)
    h, _ = headers(client)
    plain = client.post("/pathways", json={"program_id": pid}, headers=h)
    assert plain.status_code == 200 and plain.json()["note"] is None
    personal = client.post("/pathways", json={"program_id": pid, "interest": "drawing"}, headers=h)
    assert personal.status_code == 200 and "temporarily unavailable" in personal.json()["note"] and personal.json()["applied"] == []


def test_a_roadmap_with_no_swappable_slots_says_so(world, db):
    from gatorway.db.models import RoadmapSlot
    build, pid, _ = world
    db.execute(RoadmapSlot.__table__.update().values(swappable=False)); db.commit()
    client, llm = build()
    h, _ = headers(client)
    body = client.post("/pathways", json={"program_id": pid, "interest": "drawing"}, headers=h).json()
    assert "no swappable" in body["note"] and llm.edit_calls == 0


def test_a_down_tool_server_is_a_503_not_a_500(world, make_state, redis_client):
    _, pid, _ = world

    class Down:
        async def __aenter__(self):
            raise ConnectionError("refused")

        async def __aexit__(self, *a):
            return False

    service = PathwayService(llm=ScriptedLlm(), cache=Cache(redis_client), catalog_provider=lambda: None, mcp_factory=lambda: Down(),
                             allowed_tools=TOOLS, model_name="m")
    client = TestClient(create_app(make_state(pathway_service=service), init_db_on_startup=False))
    h, _ = headers(client)
    r = client.post("/pathways", json={"program_id": pid}, headers=h)
    assert r.status_code == 503 and r.json()["error"]["code"] == "pathway_unavailable"
