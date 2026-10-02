from sqlalchemy import or_, select

from gatorway.cache.store import CacheUnavailable
from gatorway.db.models import Course
from gatorway.engine import repository as repo
from gatorway.engine.models import Edit
from gatorway.engine.validator import validate_edits

from ..deps import Deps
from .pathway import load_session

OVERFETCH = 4  # candidates are filtered by the validator afterwards, so fetch extra


def register(mcp, deps: Deps) -> None:
    def query_vector(text: str) -> list[float]:
        cached = deps.cache.get_query_embedding(text, deps.embed_model)
        if cached is not None:
            return cached
        vec = deps.embedder.embed_query(text)
        deps.cache.set_query_embedding(text, deps.embed_model, vec)
        return vec

    @mcp.tool
    def search_courses(session_id: str, slot_id: str, query: str, limit: int = 8) -> dict:
        """Find courses that fit a topic for ONE swappable slot. Results already respect that slot's allowed course list,
        exclude courses already passed or planned, and only include courses whose prerequisites would be met at that point."""
        try:
            loaded = load_session(deps, session_id)
        except CacheUnavailable as e:
            return {"error": f"cache unavailable: {e}"}
        if loaded is None:
            return {"error": "unknown or expired session_id"}
        pathway, passed = loaded
        found = pathway.find_slot(slot_id)
        if found is None:
            return {"error": f"no slot {slot_id}"}
        slot = found[1]
        if not slot.swappable:
            return {"error": f"slot {slot_id} is not swappable"}
        if slot.status != "planned":
            return {"error": f"slot {slot_id} is already {slot.status}"}
        limit = max(1, min(limit, 15))
        taken = set(passed) | {c for s in pathway.all_slots() for c in s.codes}
        with deps.db() as db:
            catalog = repo.get_catalog(db)
            stmt = select(Course.code, Course.description, Course.embedding.cosine_distance(query_vector(query)).label("dist")).where(
                Course.embedding.is_not(None)
            )
            if taken:
                stmt = stmt.where(Course.code.not_in(taken))
            if slot.slot_kind == "major_elective":
                pool = catalog.pools.get(slot.pool_section_id or -1, set())
                if not pool:
                    return {"candidates": []}
                stmt = stmt.where(Course.code.in_(pool))
            if pathway.program_level == "undergraduate":
                stmt = stmt.where(or_(Course.number_int.is_(None), Course.number_int < 700))
            rows = db.execute(stmt.order_by("dist").limit(limit * OVERFETCH)).all()
        out = []
        for code, description, dist in rows:
            report = validate_edits(pathway, [Edit(slot_id=slot_id, new_course_code=code)], passed, catalog)
            if not report.applied:
                continue
            info = catalog.courses[code]
            out.append({"code": code, "title": info.title, "units": info.units_min, "similarity": round(1 - float(dist), 3),
                        "summary": (description or "")[:240], "warnings": report.warnings})
            if len(out) == limit:
                break
        return {"candidates": out}
