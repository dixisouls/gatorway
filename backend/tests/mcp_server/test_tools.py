import json
from contextlib import contextmanager
from pathlib import Path

import fakeredis
import pytest
from fastmcp import Client
from sqlalchemy import select
from sqlalchemy.orm import Session

from gatorway.cache.store import Cache
from gatorway.db.models import Course, Program
from gatorway.engine.models import Pathway
from gatorway.ingest.embeddings import HashingEmbedder, embed_courses
from gatorway.ingest.loader import ingest_all
from gatorway.mcp_server.deps import Deps
from gatorway.mcp_server.server import create_server

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def world(engine, db):
    ingest_all(db, json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text()))
    db.commit()
    embed_courses(db, HashingEmbedder())

    @contextmanager
    def session():
        with Session(engine) as s:
            yield s

    cache = Cache(fakeredis.FakeRedis(decode_responses=True))
    server = create_server(Deps(db=session, cache=cache, embedder=HashingEmbedder(), embed_model="hash"))
    pid = db.scalar(select(Program.id).where(Program.slug == "bs-mini-computer-science"))
    return server, cache, pid


async def call(server, tool, args):
    async with Client(server) as c:
        return (await c.call_tool(tool, args, raise_on_error=False)).structured_content


async def open_session(server, pid, passed=()):
    base = await call(server, "build_baseline", {"program_id": pid, "roadmap_id": None, "passed_codes": list(passed)})
    sess = await call(server, "open_session", {"pathway": base["pathway"], "passed_codes": list(passed)})
    return base["pathway"], sess["session_id"]


async def test_every_tool_module_is_auto_registered(world):
    server, _, _ = world
    async with Client(server) as c:
        names = {t.name for t in await c.list_tools()}
    assert names == {"list_programs", "get_program", "get_roadmaps", "get_requirements", "build_baseline", "open_session",
                     "get_baseline", "validate_edits", "search_courses"}


async def test_program_tools(world):
    server, _, pid = world
    assert (await call(server, "list_programs", {"query": "mini computer"}))["programs"][0]["slug"] == "bs-mini-computer-science"
    assert (await call(server, "get_program", {"program_id": pid}))["degree_type"] == "B.S."
    assert "error" in await call(server, "get_program", {"program_id": 0})
    assert [r["is_default"] for r in (await call(server, "get_roadmaps", {"program_id": pid}))["roadmaps"]] == [False, True]
    elective = next(s for s in (await call(server, "get_requirements", {"program_id": pid}))["sections"] if s["heading"] == "Electives")
    assert "CSC 600" in elective["courses"]


async def test_build_baseline_and_errors(world):
    server, _, pid = world
    base = await call(server, "build_baseline", {"program_id": pid, "roadmap_id": None, "passed_codes": ["CSC 101"]})
    p = Pathway.model_validate(base["pathway"])
    assert p.roadmap_name.endswith("QR Pathway 1/2")
    assert any(s.status == "passed" for s in p.all_slots())
    assert "not found" in (await call(server, "build_baseline", {"program_id": 999, "roadmap_id": None, "passed_codes": []}))["error"]


async def test_session_baseline_is_compact_and_unknown_session_is_an_error(world):
    server, _, pid = world
    _, sid = await open_session(server, pid)
    view = await call(server, "get_baseline", {"session_id": sid})
    swappable = [s for t in view["terms"] for s in t["slots"] if s["swappable"]]
    assert len(swappable) == 3 and {"slot_id", "title", "units", "kind", "status", "codes"} <= set(swappable[0])
    assert "error" in await call(server, "get_baseline", {"session_id": "nope"})


async def test_search_for_a_major_elective_slot_stays_inside_the_pool_and_skips_passed(world):
    server, _, pid = world
    path, sid = await open_session(server, pid, passed=["CSC 101", "CSC 215", "CSC 220"])
    slot = next(s for t in path["terms"] for s in t["slots"] if s["slot_kind"] == "major_elective")
    res = await call(server, "search_courses", {"session_id": sid, "slot_id": slot["slot_id"], "query": "web applications javascript next.js", "limit": 5})
    codes = [c["code"] for c in res["candidates"]]
    assert codes[0] == "CSC 600" and set(codes) <= {"CSC 600", "CSC 601"}  # XYZ 999 is in the pool but not in the catalog


async def test_search_filters_candidates_whose_prerequisites_would_be_skipped(world):
    server, _, pid = world
    path, sid = await open_session(server, pid)  # nothing passed: CSC 600 needs CSC 220, scheduled after the elective slot
    slot = next(s for t in path["terms"] for s in t["slots"] if s["slot_kind"] == "major_elective")
    res = await call(server, "search_courses", {"session_id": sid, "slot_id": slot["slot_id"], "query": "web applications", "limit": 5})
    assert "CSC 600" not in [c["code"] for c in res["candidates"]]


async def test_free_elective_search_excludes_graduate_courses_for_undergrad_programs(world):
    server, _, pid = world
    path, sid = await open_session(server, pid)
    slot = next(s for t in path["terms"] for s in t["slots"] if s["slot_kind"] == "free_elective")
    res = await call(server, "search_courses", {"session_id": sid, "slot_id": slot["slot_id"], "query": "advanced web application development", "limit": 10})
    codes = [c["code"] for c in res["candidates"]]
    assert "CSC 850" not in codes and "ART 101" in codes and "CSC 999" not in codes  # grad excluded; no-embedding course never returned


async def test_search_rejects_non_swappable_and_unknown_slots(world):
    server, _, pid = world
    path, sid = await open_session(server, pid)
    core = next(s for t in path["terms"] for s in t["slots"] if not s["swappable"])
    assert "not swappable" in (await call(server, "search_courses", {"session_id": sid, "slot_id": core["slot_id"], "query": "x", "limit": 3}))["error"]
    assert "error" in await call(server, "search_courses", {"session_id": sid, "slot_id": "nope", "query": "x", "limit": 3})


async def test_search_with_no_feasible_candidate_returns_an_empty_list_not_an_error(world):
    server, _, pid = world
    path, sid = await open_session(server, pid)  # nothing passed: every pool course needs a later-scheduled prerequisite
    slot = next(s for t in path["terms"] for s in t["slots"] if s["slot_kind"] == "major_elective")
    res = await call(server, "search_courses", {"session_id": sid, "slot_id": slot["slot_id"], "query": "anything at all", "limit": 5})
    assert res == {"candidates": []}


async def test_validate_edits_reports_applied_and_dropped_without_changing_the_session(world):
    server, cache, pid = world
    path, sid = await open_session(server, pid, passed=["CSC 101", "CSC 215", "CSC 220"])
    free = next(s for t in path["terms"] for s in t["slots"] if s["slot_kind"] == "free_elective")
    core = next(s for t in path["terms"] for s in t["slots"] if not s["swappable"])
    res = await call(server, "validate_edits", {"session_id": sid, "edits": [
        {"slot_id": free["slot_id"], "new_course_code": "ART 101", "reason": "x"},
        {"slot_id": core["slot_id"], "new_course_code": "ART 102"}]})
    assert res["applied"] == [free["slot_id"]] and res["dropped"][0]["slot_id"] == core["slot_id"] and res["dropped"][0]["problems"]
    assert cache.get_session(sid)["pathway"] == path  # validation is a dry run


async def test_query_embeddings_are_cached(world):
    server, cache, pid = world
    path, sid = await open_session(server, pid)
    slot = next(s for t in path["terms"] for s in t["slots"] if s["slot_kind"] == "free_elective")
    await call(server, "search_courses", {"session_id": sid, "slot_id": slot["slot_id"], "query": "Drawing", "limit": 3})
    assert cache.get_query_embedding("drawing", "hash") is not None
