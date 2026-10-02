"""POST /pathways logic (ARCHITECTURE.md section 4.4): baseline -> intent -> Gemini edits -> authoritative validation."""
from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from pydantic import BaseModel, Field

from gatorway.cache.store import Cache, CacheUnavailable
from gatorway.engine.models import Catalog, DroppedEdit, Edit, Pathway
from gatorway.engine.validator import validate_edits

from .ports import Intent, LlmPort

log = logging.getLogger(__name__)

MAX_RETRIES = 2  # extra Gemini rounds after the first, fed with the validator's reasons


class ServiceError(RuntimeError):
    pass


class AppliedEdit(BaseModel):
    slot_id: str
    new_course_code: str
    title: str = ""
    reason: str = ""


class PathwayResult(BaseModel):
    pathway: Pathway
    applied: list[AppliedEdit] = Field(default_factory=list)
    dropped: list[DroppedEdit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    intent: Intent | None = None
    note: str | None = None
    cached: bool = False


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


class PathwayService:
    def __init__(
        self,
        *,
        llm: LlmPort,
        cache: Cache,
        catalog_provider: Callable[[], Catalog],
        mcp_factory: Callable[[], AbstractAsyncContextManager[Any]],
        allowed_tools: set[str],
        model_name: str = "gemini",
    ):
        self._llm, self._cache, self._catalog = llm, cache, catalog_provider
        self._mcp_factory, self._allowed, self._model = mcp_factory, allowed_tools, model_name

    async def create(self, *, program_id: int, roadmap_id: int | None, passed: list[str], interest: str | None, data_version: str) -> PathwayResult:
        async with self._mcp_factory() as mcp:
            baseline = await self._build_baseline(mcp, program_id, roadmap_id, passed)
            if not (interest or "").strip():
                return PathwayResult(pathway=baseline)

            if not any(sl.swappable and sl.status == "planned" for sl in baseline.all_slots()):
                return PathwayResult(pathway=baseline, note="This roadmap has no swappable elective slots; showing the standard roadmap.")

            try:
                intent = await self._intent(interest)
            except Exception as e:  # Gemini down / bad output: still useful to show the baseline
                log.warning("intent parsing failed: %s", e)
                return PathwayResult(pathway=baseline, note="Your interest could not be interpreted right now; showing the standard roadmap.")
            if not intent.specialization:
                return PathwayResult(pathway=baseline, intent=intent, note="No specific interest detected; showing the standard roadmap.")

            key = Cache.pathway_key(program_id, baseline.roadmap_id, passed, self._cache.intent_hash(interest, self._model), data_version)
            hit = self._cache.get_pathway(key)
            if hit is not None:
                return PathwayResult.model_validate({**hit, "cached": True})

            if not self._cache.acquire_lock(key):
                waited = await self._cache.wait_for_pathway(key)
                if waited is not None:
                    return PathwayResult.model_validate({**waited, "cached": True})
            try:
                result = await self._edit(mcp, baseline, passed, intent)
                if result.note is None:  # never cache a degraded answer
                    self._cache.set_pathway(key, result.model_dump(mode="json"))
                return result
            finally:
                self._cache.release_lock(key)

    # ------------------------------------------------------------------
    async def _call(self, mcp: Any, tool: str, args: dict) -> dict:
        res = await mcp.call_tool(tool, args, raise_on_error=False)
        if res.is_error:
            raise ServiceError(" ".join(getattr(c, "text", "") for c in res.content) or f"{tool} failed")
        data = res.structured_content if res.structured_content is not None else res.data
        if isinstance(data, dict) and data.get("error"):
            raise ServiceError(str(data["error"]))
        return data

    async def _build_baseline(self, mcp: Any, program_id: int, roadmap_id: int | None, passed: list[str]) -> Pathway:
        data = await self._call(mcp, "build_baseline", {"program_id": program_id, "roadmap_id": roadmap_id, "passed_codes": passed})
        return Pathway.model_validate(data["pathway"])

    async def _intent(self, interest: str) -> Intent:
        cached = self._cache.get_intent(interest, self._model)
        if cached is not None:
            return Intent.model_validate(cached)
        intent = await self._llm.parse_intent(interest)
        self._cache.set_intent(interest, self._model, intent.model_dump())
        return intent

    async def _edit(self, mcp: Any, baseline: Pathway, passed: list[str], intent: Intent) -> PathwayResult:
        try:
            opened = await self._call(mcp, "open_session", {"pathway": baseline.model_dump(mode="json"), "passed_codes": passed})
            session_id = opened["session_id"]
        except (ServiceError, CacheUnavailable, KeyError) as e:
            log.warning("could not open pathway session: %s", e)
            return PathwayResult(pathway=baseline, intent=intent, note="Personalising is temporarily unavailable; showing the standard roadmap.")

        catalog, passed_set = self._catalog(), set(passed)
        current, applied, warnings = baseline, [], []
        all_dropped: list[DroppedEdit] = []
        feedback: list[str] | None = None
        note = None
        for _ in range(MAX_RETRIES + 1):
            try:
                edits: list[Edit] = await self._llm.propose_edits(session_id, mcp, self._allowed, intent, feedback)
            except Exception as e:
                log.warning("gemini edit loop failed: %s", e)
                note = "Personalising failed part-way; showing what could be applied safely."
                break
            report = validate_edits(current, edits, passed_set, catalog)
            applied += report.applied
            all_dropped += report.dropped
            warnings += report.warnings
            current = report.pathway
            if not report.dropped:
                break
            try:
                self._cache.update_session_pathway(session_id, current.model_dump(mode="json"))
            except CacheUnavailable:
                break
            feedback = [
                f"slot {d.edit.slot_id} <- {d.edit.new_course_code}: " + "; ".join(v.message for v in d.violations) for d in report.dropped
            ]

        edited_slots = {e.slot_id for e in applied}
        return PathwayResult(
            pathway=current,
            applied=[
                AppliedEdit(slot_id=e.slot_id, new_course_code=e.new_course_code, reason=e.reason,
                            title=catalog.courses[e.new_course_code].title if e.new_course_code in catalog.courses else "")
                for e in applied
            ],
            dropped=[d for d in all_dropped if d.edit.slot_id not in edited_slots],
            warnings=_dedupe(warnings),
            intent=intent,
            note=note,
        )
