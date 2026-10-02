"""Deterministic baseline: the roadmap as-is, passed courses marked, 'Take N' rows split per course."""
from __future__ import annotations

from .models import Catalog, Pathway, Slot, Term


def split_seats(slot: Slot, seats: int) -> list[Slot]:
    if seats <= 1:
        return [slot]
    per = slot.units / seats if slot.units else 0
    out = []
    for k in range(1, seats + 1):
        out.append(slot.model_copy(update={"slot_id": f"{slot.slot_id}-{k}", "units": round(per, 2)}))
    return out


def build_baseline(skeleton: Pathway, passed: set[str], catalog: Catalog) -> Pathway:
    """`skeleton` has one Slot per roadmap row (seats already expanded by the repository).
    1) a slot whose courses were ALL passed is marked passed;
    2) an open major-elective slot is filled with a passed course from its pool;
    3) free electives and GE are never auto-filled (a passed course there can't be attributed safely).
    Passed courses not placed anywhere are returned in `unplaced_passed`."""
    path = skeleton.model_copy(deep=True)
    remaining = set(passed)
    slots = path.all_slots()
    for s in slots:
        if s.codes and all(c in passed for c in s.codes):
            s.status = "passed"
            remaining.difference_update(s.codes)
    for s in slots:
        if s.codes or s.slot_kind != "major_elective" or s.status != "planned":
            continue
        pool = catalog.pools.get(s.pool_section_id or -1, set())
        pick = next((c for c in sorted(remaining) if c in pool), None)
        if pick:
            s.codes = [pick]
            s.status = "passed"
            remaining.discard(pick)
    path.unplaced_passed = sorted(remaining)
    return path
