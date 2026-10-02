from gatorway.cache.store import CacheUnavailable
from gatorway.engine import repository as repo
from gatorway.engine.models import Edit, Pathway
from gatorway.engine.validator import MODEL_KINDS, validate_edits as run_validation

from ..deps import Deps


def _compact(pathway: Pathway) -> dict:
    return {
        "program": pathway.program_title, "level": pathway.program_level, "roadmap": pathway.roadmap_name,
        "terms": [{"label": t.label, "slots": [
            {"slot_id": s.slot_id, "codes": s.codes, "title": s.title, "units": s.units, "kind": s.slot_kind,
             "swappable": s.swappable and s.slot_kind in MODEL_KINDS, "status": s.status} for s in t.slots]}
            for t in sorted(pathway.terms, key=lambda t: t.position)],
    }


def load_session(deps: Deps, session_id: str):
    """-> (Pathway, passed set) or None when the session is unknown or expired."""
    sess = deps.cache.get_session(session_id)
    if sess is None:
        return None
    return Pathway.model_validate(sess["pathway"]), set(sess["passed"])


def register(mcp, deps: Deps) -> None:
    @mcp.tool
    def build_baseline(program_id: int, roadmap_id: int | None = None, passed_codes: list[str] | None = None) -> dict:
        """ORCHESTRATOR ONLY. Build the deterministic baseline pathway for a program, marking passed courses."""
        with deps.db() as db:
            try:
                return {"pathway": repo.build_baseline_for(db, program_id, roadmap_id, passed_codes or []).model_dump(mode="json")}
            except LookupError as e:
                return {"error": str(e)}

    @mcp.tool
    def open_session(pathway: dict, passed_codes: list[str]) -> dict:
        """ORCHESTRATOR ONLY. Store a baseline pathway and the passed courses; returns the session_id the model works with."""
        try:
            return {"session_id": deps.cache.create_session(pathway, passed_codes)}
        except CacheUnavailable as e:
            return {"error": f"cache unavailable: {e}"}

    @mcp.tool
    def get_baseline(session_id: str) -> dict:
        """The student's roadmap: terms with slots. Slots with swappable=true may be replaced; everything else is fixed."""
        try:
            loaded = load_session(deps, session_id)
        except CacheUnavailable as e:
            return {"error": f"cache unavailable: {e}"}
        return _compact(loaded[0]) if loaded else {"error": "unknown or expired session_id"}

    @mcp.tool
    def validate_edits(session_id: str, edits: list[dict[str, str]]) -> dict:
        """Dry-run proposed edits. Each edit is an object with slot_id, new_course_code and optional reason.
        Returns which edits are valid (applied) and which are rejected (dropped) with the reasons."""
        try:
            loaded = load_session(deps, session_id)
        except CacheUnavailable as e:
            return {"error": f"cache unavailable: {e}"}
        if loaded is None:
            return {"error": "unknown or expired session_id"}
        pathway, passed = loaded
        parsed = [Edit(slot_id=str(e.get("slot_id", "")), new_course_code=str(e.get("new_course_code", "")), reason=str(e.get("reason", ""))) for e in edits]
        with deps.db() as db:
            report = run_validation(pathway, parsed, passed, repo.get_catalog(db), allowed_kinds=MODEL_KINDS)
        return {
            "applied": [e.slot_id for e in report.applied],
            "dropped": [{"slot_id": d.edit.slot_id, "new_course_code": d.edit.new_course_code, "problems": [v.message for v in d.violations]} for d in report.dropped],
            "warnings": report.warnings,
        }
