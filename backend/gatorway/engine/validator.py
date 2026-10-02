"""Deterministic, authoritative rules. See ARCHITECTURE.md section 4.3."""
from __future__ import annotations

from .models import Catalog, DroppedEdit, Edit, EditsReport, Pathway, Violation


def _ordered_terms(pathway: Pathway):
    return sorted(pathway.terms, key=lambda t: t.position)


def prereq_violations(pathway: Pathway, passed: set[str], catalog: Catalog) -> list[Violation]:
    """Every planned course must have each prerequisite group met by a passed course, a course
    in an earlier term, or (only for concurrent_ok codes) a course in the same term."""
    done = set(passed)
    for s in pathway.all_slots():
        if s.status == "passed":
            done.update(s.codes)
    out: list[Violation] = []
    for term in _ordered_terms(pathway):
        in_term = {c for s in term.slots if s.status != "passed" for c in s.codes}
        for s in term.slots:
            if s.status == "passed":
                continue
            for code in s.codes:
                info = catalog.courses.get(code)
                if info is None:
                    continue
                for group in info.prereq_groups:
                    ok = any(g in done or (g in in_term and g != code and g in info.concurrent_ok) for g in group)
                    if not ok:
                        out.append(
                            Violation(
                                rule="prereq",
                                slot_id=s.slot_id,
                                message=f"{code} needs {' or '.join(group)} before {term.label}",
                            )
                        )
        done |= in_term
    return out


def edit_violations(pathway: Pathway, edit: Edit, passed: set[str], catalog: Catalog) -> list[Violation]:
    found = pathway.find_slot(edit.slot_id)
    if found is None:
        return [Violation(rule="slot", slot_id=edit.slot_id, message=f"no slot {edit.slot_id}")]
    _, slot = found
    code = edit.new_course_code
    if not slot.swappable:
        return [Violation(rule="slot", slot_id=slot.slot_id, message=f"slot '{slot.title}' is not swappable")]
    if slot.status != "planned":
        return [Violation(rule="slot", slot_id=slot.slot_id, message=f"slot already {slot.status}")]
    info = catalog.courses.get(code)
    if info is None:
        return [Violation(rule="unknown_course", slot_id=slot.slot_id, message=f"{code} is not in the catalog")]
    out: list[Violation] = []
    if slot.slot_kind == "major_elective":
        pool = catalog.pools.get(slot.pool_section_id or -1, set())
        if code not in pool:
            out.append(Violation(rule="pool", slot_id=slot.slot_id, message=f"{code} is not in this program's elective list"))
    elif slot.slot_kind != "free_elective":
        out.append(Violation(rule="slot", slot_id=slot.slot_id, message=f"slot kind {slot.slot_kind} is not swappable"))
    if pathway.program_level == "undergraduate" and info.number_int is not None and info.number_int >= 700:
        out.append(Violation(rule="level", slot_id=slot.slot_id, message=f"{code} is a graduate course (700+); this is an undergraduate program"))
    taken = set(passed) | {c for s in pathway.all_slots() for c in s.codes}
    if code in taken:
        out.append(Violation(rule="duplicate", slot_id=slot.slot_id, message=f"{code} is already passed or planned"))
    if slot.units > 0 and info.units_min < slot.units:
        out.append(
            Violation(rule="units", slot_id=slot.slot_id, message=f"{code} is {info.units_min:g} units; slot needs {slot.units:g}")
        )
    return out


def apply_edit(pathway: Pathway, edit: Edit) -> Pathway:
    new = pathway.model_copy(deep=True)
    found = new.find_slot(edit.slot_id)
    assert found is not None
    _, slot = found
    slot.codes = [edit.new_course_code]
    slot.status = "replaced"
    return new


def unit_warnings(pathway: Pathway) -> list[str]:
    """Edits can never lower a slot's units (see edit_violations), so totals cannot fall below the
    baseline. These warnings only say when even the baseline is under the stated minimum."""
    out: list[str] = []
    slots = pathway.all_slots()
    total = sum(s.units for s in slots)
    if pathway.total_units_required and total < pathway.total_units_required:
        out.append(f"Roadmap totals {total:g} units; the degree requires {pathway.total_units_required:g}.")
    major = sum(s.units for s in slots if s.counts_toward_major)
    if pathway.major_units_required and major and major < pathway.major_units_required:
        out.append(f"Major slots total {major:g} units; the major requires {pathway.major_units_required:g}.")
    return out


def validate_edits(baseline: Pathway, edits: list[Edit], passed: set[str], catalog: Catalog) -> EditsReport:
    """Apply edits one at a time; keep each valid one, drop each invalid one with the reasons.
    Only violations *introduced* by an edit block it: the university's own roadmap may already
    break a rule (e.g. a prerequisite scheduled late), and that is not the edit's fault."""
    existing = {v.key() for v in prereq_violations(baseline, passed, catalog)}
    current = baseline
    applied: list[Edit] = []
    dropped: list[DroppedEdit] = []
    warnings: list[str] = []
    for edit in edits:
        problems = edit_violations(current, edit, passed, catalog)
        trial = None
        if not problems:
            trial = apply_edit(current, edit)
            problems = [v for v in prereq_violations(trial, passed, catalog) if v.key() not in existing]
        if problems:
            dropped.append(DroppedEdit(edit=edit, violations=problems))
            continue
        current = trial
        applied.append(edit)
        info = catalog.courses[edit.new_course_code]
        for w in info.prereq_warnings:
            warnings.append(f"{info.code}: {w}")
    warnings.extend(unit_warnings(current))
    return EditsReport(pathway=current, applied=applied, dropped=dropped, warnings=warnings)


def reopen_slot(pathway: Pathway, slot_id: str) -> Pathway:
    """A slot an earlier swap already replaced can be changed again: on a copy, treat it as open for the next edit."""
    new = pathway.model_copy(deep=True)
    found = new.find_slot(slot_id)
    if found is not None and found[1].status == "replaced":
        found[1].status = "planned"
    return new
