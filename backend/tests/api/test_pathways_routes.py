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
        self.picks, self.edit_calls, self.feedback = list(picks), 0, []

    async def parse_intent(self, interest):
        return Intent(specialization=True, topics=["drawing"], keywords=["art"], summary=interest)

    async def propose_edits(self, session_id, mcp, allowed, intent, feedback):
        self.feedback.append(feedback)
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


def test_baseline_preview_is_not_saved_and_never_calls_gemini(world):
    build, pid, _ = world
    client, llm = build()
    h, _ = headers(client)
    r = client.post("/pathways/baseline", json={"program_id": pid}, headers=h)
    assert r.status_code == 200 and set(r.json()) == {"pathway"}
    assert [t["label"] for t in r.json()["pathway"]["terms"]] == ["First Semester", "Second Semester", "Third Semester"]
    assert llm.edit_calls == 0
    assert client.get("/pathways", headers=h).json()["pathways"] == []


def test_baseline_preview_needs_login_and_a_real_program(world):
    build, pid, minor = world
    client, _ = build()
    assert client.post("/pathways/baseline", json={"program_id": pid}).status_code == 401
    h, _ = headers(client)
    assert client.post("/pathways/baseline", json={"program_id": 99999}, headers=h).status_code == 404
    assert client.post("/pathways/baseline", json={"program_id": minor}, headers=h).status_code == 404  # no roadmap


def test_refresh_asks_gemini_again_instead_of_returning_the_cached_answer(world):
    build, pid, _ = world
    client, llm = build()
    h, _ = headers(client)
    body = {"program_id": pid, "interest": "I like drawing"}
    client.post("/pathways", json=body, headers=h)
    again = client.post("/pathways", json=body, headers=h).json()
    assert again["cached"] is True and llm.edit_calls == 1
    fresh = client.post("/pathways", json={**body, "fresh": True}, headers=h).json()
    assert fresh["cached"] is False and llm.edit_calls == 2


def test_refresh_tells_the_model_which_earlier_picks_to_avoid(world):
    build, pid, _ = world
    client, llm = build()
    h, _ = headers(client)
    client.post("/pathways", json={"program_id": pid, "interest": "drawing", "fresh": True, "avoid": ["ART 101", "CSC 601"]}, headers=h)
    assert llm.feedback[-1] == ["Earlier picks to avoid if another good match exists: ART 101, CSC 601"]


def test_avoid_list_is_bounded(world):
    build, pid, _ = world
    client, _ = build()
    h, _ = headers(client)
    r = client.post("/pathways", json={"program_id": pid, "interest": "x", "avoid": [f"C {i}" for i in range(21)]}, headers=h)
    assert r.status_code == 422


def _passed(db, uid, *codes):
    for c in codes:
        db.add(UserCourse(user_id=uid, raw_code=c))
    db.commit()


def test_slot_options_list_valid_alternatives_for_a_swappable_slot(world, db):
    build, pid, _ = world
    client, _ = build()
    h, uid = headers(client)
    _passed(db, uid, "CSC 215", "CSC 220")
    saved = client.post("/pathways", json={"program_id": pid}, headers=h).json()
    free = next(s for s in slots(saved) if s["slot_kind"] == "free_elective")
    r = client.get(f"/pathways/{saved['id']}/slots/{free['slot_id']}/options", params={"query": "relational databases"}, headers=h)
    assert r.status_code == 200 and r.json()["slot_id"] == free["slot_id"] and r.json()["query"] == "relational databases"
    codes = [c["code"] for c in r.json()["candidates"]]
    assert "CSC 601" in codes and "CSC 101" not in codes and "CSC 850" not in codes  # planned / graduate courses are never offered
    first = r.json()["candidates"][0]
    assert {"code", "title", "units", "similarity", "summary", "warnings"} <= set(first)


def test_slot_options_without_a_query_use_the_saved_interest(world, db):
    build, pid, _ = world
    client, _ = build()
    h, uid = headers(client)
    _passed(db, uid, "CSC 215", "CSC 220")
    saved = client.post("/pathways", json={"program_id": pid, "interest": "I like drawing"}, headers=h).json()
    free = next(s for s in slots(saved) if s["slot_kind"] == "free_elective")
    r = client.get(f"/pathways/{saved['id']}/slots/{free['slot_id']}/options", headers=h)
    assert r.status_code == 200 and r.json()["query"] == "drawing art"  # the stub intent's topics + keywords


def test_slot_options_refuse_fixed_slots_unknown_slots_and_other_users(world):
    build, pid, _ = world
    client, _ = build()
    h, _ = headers(client)
    saved = client.post("/pathways", json={"program_id": pid}, headers=h).json()
    fixed = next(s for s in slots(saved) if not s["swappable"])
    base = f"/pathways/{saved['id']}/slots"
    bad = client.get(f"{base}/{fixed['slot_id']}/options", headers=h)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_slot"
    assert client.get(f"{base}/nope/options", headers=h).status_code == 404
    other, _ = headers(client, "other@sfsu.edu")
    assert client.get(f"{base}/{fixed['slot_id']}/options", headers=other).status_code == 404
    assert client.get("/pathways/99999/slots/x/options", headers=h).status_code == 404


def _swap(client, h, saved, slot_id, code):
    return client.post(f"/pathways/{saved['id']}/swap", json={"slot_id": slot_id, "new_course_code": code}, headers=h)


def test_student_can_swap_a_slot_and_it_is_saved(world, db):
    build, pid, _ = world
    client, _ = build()
    h, uid = headers(client)
    _passed(db, uid, "CSC 215", "CSC 220")
    saved = client.post("/pathways", json={"program_id": pid}, headers=h).json()
    free = next(s for s in slots(saved) if s["slot_kind"] == "free_elective")
    r = _swap(client, h, saved, free["slot_id"], "ART 101")
    assert r.status_code == 200
    body = r.json()
    swapped = next(s for s in slots(body) if s["slot_id"] == free["slot_id"])
    assert swapped["codes"] == ["ART 101"] and swapped["status"] == "replaced"
    assert [(a["slot_id"], a["new_course_code"], a["reason"]) for a in body["applied"]] == [(free["slot_id"], "ART 101", "Your choice")]
    again = client.get(f"/pathways/{saved['id']}", headers=h).json()
    assert next(s for s in slots(again) if s["slot_id"] == free["slot_id"])["codes"] == ["ART 101"]


def test_a_slot_that_was_swapped_before_can_be_swapped_again(world, db):
    build, pid, _ = world
    client, _ = build()
    h, uid = headers(client)
    _passed(db, uid, "CSC 215", "CSC 220")
    saved = client.post("/pathways", json={"program_id": pid, "interest": "I like drawing"}, headers=h).json()  # the model picks ART 101
    free = next(s for s in slots(saved) if s["status"] == "replaced")
    assert free["codes"] == ["ART 101"]
    r = _swap(client, h, saved, free["slot_id"], "CSC 600")
    assert r.status_code == 200
    body = r.json()
    assert next(s for s in slots(body) if s["slot_id"] == free["slot_id"])["codes"] == ["CSC 600"]
    assert [a["new_course_code"] for a in body["applied"]] == ["CSC 600"]  # one entry per slot, the latest


def test_a_swap_the_validator_refuses_is_a_422_and_changes_nothing(world, db):
    build, pid, _ = world
    client, _ = build()
    h, uid = headers(client)
    saved = client.post("/pathways", json={"program_id": pid}, headers=h).json()
    free = next(s for s in slots(saved) if s["slot_kind"] == "free_elective")
    fixed = next(s for s in slots(saved) if not s["swappable"])
    for slot_id, code, fragment in [(free["slot_id"], "CSC 850", "graduate"), (free["slot_id"], "NOPE 1", "not in the catalog"),
                                    (fixed["slot_id"], "ART 101", "not swappable"), (free["slot_id"], "CSC 600", "needs csc 220 before")]:
        r = _swap(client, h, saved, slot_id, code)
        assert r.status_code == 422 and r.json()["error"]["code"] == "swap_rejected", (code, r.text)
        assert fragment in r.json()["error"]["message"].lower(), (code, r.text)
        assert r.json()["error"]["details"]
    untouched = client.get(f"/pathways/{saved['id']}", headers=h).json()
    assert all(s["status"] != "replaced" for s in slots(untouched))


def test_swaps_are_private_to_the_owner_and_need_login(world):
    build, pid, _ = world
    client, _ = build()
    mine, _ = headers(client, "a@sfsu.edu")
    theirs, _ = headers(client, "b@sfsu.edu")
    saved = client.post("/pathways", json={"program_id": pid}, headers=mine).json()
    free = next(s for s in slots(saved) if s["slot_kind"] == "free_elective")
    assert _swap(client, theirs, saved, free["slot_id"], "ART 101").status_code == 404
    assert client.post(f"/pathways/{saved['id']}/swap", json={"slot_id": "x", "new_course_code": "ART 101"}).status_code == 401


def test_pathway_responses_carry_the_raw_interest(world):
    build, pid, _ = world
    client, _ = build()
    h, _ = headers(client)
    made = client.post("/pathways", json={"program_id": pid, "interest": "I like drawing"}, headers=h).json()
    assert made["interest"] == "I like drawing"
    assert client.get(f"/pathways/{made['id']}", headers=h).json()["interest"] == "I like drawing"
    assert client.post("/pathways", json={"program_id": pid}, headers=h).json()["interest"] is None
