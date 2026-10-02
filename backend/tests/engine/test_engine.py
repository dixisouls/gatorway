import pytest

from gatorway.engine.baseline import build_baseline, split_seats
from gatorway.engine.models import Catalog, CourseInfo, Edit, Pathway, Slot, Term
from gatorway.engine.validator import prereq_violations, validate_edits


def course(code, units=3, groups=None, conc=None, warn=None):
    return CourseInfo(code=code, title=code, units_min=units, units_max=units,
                      prereq_groups=groups or [], concurrent_ok=set(conc or []), prereq_warnings=warn or [])


@pytest.fixture
def catalog():
    return Catalog(
        courses={
            "CSC 101": course("CSC 101"),
            "CSC 215": course("CSC 215", groups=[["CSC 101"]]),
            "CSC 220": course("CSC 220", groups=[["CSC 215"]]),
            "CSC 600": course("CSC 600", groups=[["CSC 220"]]),
            "CSC 601": course("CSC 601", groups=[["CSC 101"]], warn=["permission of instructor"]),
            "CSC 602": course("CSC 602", groups=[["CSC 101"]], conc=["CSC 101"]),
            "ART 101": course("ART 101"),
            "ART 102": course("ART 102", units=1),
            "WEB 1": course("WEB 1", groups=[["CSC 101", "CSC 215"]]),
        },
        pools={7: {"CSC 600", "CSC 601", "CSC 602", "WEB 1"}},
    )


def slot(sid, codes=(), kind="fixed", swap=False, units=3, pool=None, title=None, major=False):
    return Slot(slot_id=sid, codes=list(codes), title=title or (codes[0] if codes else sid), units=units,
                slot_kind=kind, swappable=swap, pool_section_id=pool, counts_toward_major=major)


def skeleton(terms):
    return Pathway(program_id=1, roadmap_id=1, terms=[Term(position=i, label=f"T{i+1}", slots=s) for i, s in enumerate(terms)])


def basic():
    # T1: CSC 101 + open major elective; T2: CSC 215 + free elective; T3: CSC 220
    return skeleton([
        [slot("a", ["CSC 101"], major=True), slot("e1", kind="major_elective", swap=True, pool=7, major=True)],
        [slot("b", ["CSC 215"]), slot("f1", kind="free_elective", swap=True)],
        [slot("c", ["CSC 220"])],
    ])


# ---- baseline -------------------------------------------------------------
def test_split_seats_divides_units():
    parts = split_seats(slot("9", kind="major_elective", swap=True, units=9), 3)
    assert [p.slot_id for p in parts] == ["9-1", "9-2", "9-3"] and [p.units for p in parts] == [3, 3, 3]


def test_baseline_marks_passed_and_fills_major_elective_from_pool(catalog):
    p = build_baseline(basic(), {"CSC 101", "CSC 601", "ENGL 114"}, catalog)
    st = {s.slot_id: (s.status, s.codes) for s in p.all_slots()}
    assert st["a"][0] == "passed"
    assert st["e1"] == ("passed", ["CSC 601"])
    assert st["f1"] == ("planned", [])  # free electives never auto-filled
    assert p.unplaced_passed == ["ENGL 114"]


def test_baseline_needs_all_codes_of_a_lecture_lab_pair(catalog):
    sk = skeleton([[slot("p", ["CSC 101", "ART 101"])]])
    assert build_baseline(sk, {"CSC 101"}, catalog).all_slots()[0].status == "planned"


# ---- validator: the cases the spec names ------------------------------------
def test_valid_free_elective_swap_is_applied(catalog):
    base = build_baseline(basic(), set(), catalog)
    r = validate_edits(base, [Edit(slot_id="f1", new_course_code="ART 101", reason="x")], set(), catalog)
    assert [e.slot_id for e in r.applied] == ["f1"] and not r.dropped
    assert r.pathway.find_slot("f1")[1].status == "replaced"


def test_swap_that_skips_a_prerequisite_is_rejected(catalog):
    base = build_baseline(basic(), set(), catalog)
    # CSC 600 needs CSC 220, which is scheduled in T3, after the T1 slot
    r = validate_edits(base, [Edit(slot_id="e1", new_course_code="CSC 600")], set(), catalog)
    assert not r.applied and r.dropped[0].violations[0].rule == "prereq"


def test_passed_course_satisfies_prerequisite(catalog):
    base = build_baseline(basic(), {"CSC 220"}, catalog)
    r = validate_edits(base, [Edit(slot_id="e1", new_course_code="CSC 600")], {"CSC 220"}, catalog)
    assert len(r.applied) == 1


def test_or_group_needs_only_one_member(catalog):
    base = build_baseline(basic(), set(), catalog)
    r = validate_edits(base, [Edit(slot_id="e1", new_course_code="WEB 1")], set(), catalog)
    assert len(r.applied) == 0  # CSC 101 is in the SAME term, not earlier -> blocked
    r2 = validate_edits(base, [Edit(slot_id="f1", new_course_code="WEB 1")], set(), catalog)
    assert len(r2.applied) == 1  # T2: CSC 101 (T1) is earlier


def test_same_term_allowed_only_when_concurrent_ok(catalog):
    base = build_baseline(basic(), set(), catalog)
    ok = validate_edits(base, [Edit(slot_id="e1", new_course_code="CSC 602")], set(), catalog)
    bad = validate_edits(base, [Edit(slot_id="e1", new_course_code="CSC 601")], set(), catalog)
    assert len(ok.applied) == 1 and not bad.applied


def test_swap_that_removes_a_course_a_later_one_needs_is_rejected(catalog):
    sk = skeleton([
        [slot("a", ["CSC 101"])],
        [slot("x", kind="free_elective", swap=True)],
        [slot("c", ["CSC 220"])],  # CSC 220 needs CSC 215, which we put in the swappable slot's place below
    ])
    # baseline with CSC 215 sitting in a *swappable* slot
    sk.terms[1].slots[0] = slot("x", ["CSC 215"], kind="free_elective", swap=True)
    base = build_baseline(sk, set(), catalog)
    r = validate_edits(base, [Edit(slot_id="x", new_course_code="ART 101")], set(), catalog)
    assert not r.applied
    assert any(v.rule == "prereq" and v.slot_id == "c" for v in r.dropped[0].violations)


def test_units_may_not_drop_below_the_slot(catalog):
    base = build_baseline(basic(), set(), catalog)
    r = validate_edits(base, [Edit(slot_id="f1", new_course_code="ART 102")], set(), catalog)
    assert r.dropped[0].violations[0].rule == "units"


def test_major_elective_must_come_from_its_pool(catalog):
    base = build_baseline(basic(), set(), catalog)
    r = validate_edits(base, [Edit(slot_id="e1", new_course_code="ART 101")], set(), catalog)
    assert r.dropped[0].violations[0].rule == "pool"


def test_core_passed_and_unknown_slots_are_not_swappable(catalog):
    base = build_baseline(basic(), {"CSC 101"}, catalog)
    for sid in ("b", "a", "nope"):
        r = validate_edits(base, [Edit(slot_id=sid, new_course_code="ART 101")], {"CSC 101"}, catalog)
        assert r.dropped and r.dropped[0].violations[0].rule == "slot"


def test_duplicate_and_unknown_course_rejected(catalog):
    base = build_baseline(basic(), {"ART 101"}, catalog)
    assert validate_edits(base, [Edit(slot_id="f1", new_course_code="ART 101")], {"ART 101"}, catalog).dropped[0].violations[0].rule == "duplicate"
    assert validate_edits(base, [Edit(slot_id="f1", new_course_code="XXX 999")], set(), catalog).dropped[0].violations[0].rule == "unknown_course"


def test_same_slot_cannot_be_edited_twice_and_valid_edits_survive_invalid_ones(catalog):
    base = build_baseline(basic(), set(), catalog)
    edits = [Edit(slot_id="f1", new_course_code="ART 101"), Edit(slot_id="f1", new_course_code="WEB 1"),
             Edit(slot_id="e1", new_course_code="CSC 600")]
    r = validate_edits(base, edits, set(), catalog)
    assert [e.slot_id for e in r.applied] == ["f1"] and len(r.dropped) == 2


def test_preexisting_roadmap_violation_does_not_block_unrelated_edits(catalog):
    sk = skeleton([[slot("c", ["CSC 220"])], [slot("f1", kind="free_elective", swap=True)]])  # roadmap itself is wrong
    base = build_baseline(sk, set(), catalog)
    assert prereq_violations(base, set(), catalog)  # baseline already violates
    assert len(validate_edits(base, [Edit(slot_id="f1", new_course_code="ART 101")], set(), catalog).applied) == 1


def test_non_course_prereq_becomes_warning_not_block(catalog):
    base = build_baseline(basic(), set(), catalog)
    r = validate_edits(base, [Edit(slot_id="f1", new_course_code="CSC 601")], set(), catalog)
    assert len(r.applied) == 1 and any("permission of instructor" in w for w in r.warnings)


def test_unit_warning_when_baseline_is_under_the_stated_minimum(catalog):
    sk = basic(); sk.total_units_required = 120
    base = build_baseline(sk, set(), catalog)
    assert any("requires 120" in w for w in validate_edits(base, [], set(), catalog).warnings)


def test_graduate_courses_are_rejected_for_undergraduate_programs_only(catalog):
    catalog.courses["CSC 850"] = CourseInfo(code="CSC 850", title="Advanced", units_min=3, units_max=3, number_int=850)
    sk = basic()
    sk.program_level = "undergraduate"
    base = build_baseline(sk, set(), catalog)
    r = validate_edits(base, [Edit(slot_id="f1", new_course_code="CSC 850")], set(), catalog)
    assert r.dropped[0].violations[0].rule == "level"
    sk2 = basic()
    sk2.program_level = "graduate"
    assert len(validate_edits(build_baseline(sk2, set(), catalog), [Edit(slot_id="f1", new_course_code="CSC 850")], set(), catalog).applied) == 1
