from gatorway.engine.models import Catalog, CourseInfo, Edit, Pathway, Slot, Term
from gatorway.engine.validator import MODEL_KINDS, swap_slot, validate_edits


def _world():
    ge = Slot(slot_id="g", title="GE Area 4: Social and Behavioral Sciences", label="GE Area 4: Social and Behavioral Sciences", units=3, slot_kind="ge", swappable=True)
    pathway = Pathway(program_id=1, roadmap_id=1, program_level="undergraduate", terms=[Term(position=0, label="T", slots=[ge])])

    def info(code, n, attrs, units=3):
        return CourseInfo(code=code, title=f"{code} title", units_min=units, units_max=units, number_int=n, attributes=attrs)

    catalog = Catalog(courses={
        "SOC 100": info("SOC 100", 100, ["4: Social/Behavioral Sciences"]),
        "ANTH 110": info("ANTH 110", 110, ["D1: Social Sciences"]),
        "ART 101": info("ART 101", 101, ["3A: Arts"]),
        "SOC 350": info("SOC 350", 350, ["4: Social/Behavioral Sciences"]),
        "SOC 101": info("SOC 101", 101, ["4: Social/Behavioral Sciences"], units=2),
    })
    return pathway, catalog


def _swap(pathway, catalog, code):
    return swap_slot(pathway, "g", code, set(), catalog)


def test_a_course_labelled_for_the_area_can_fill_a_ge_row():
    pathway, catalog = _world()
    report = _swap(pathway, catalog, "SOC 100")
    assert [e.new_course_code for e in report.applied] == ["SOC 100"] and not report.dropped
    slot = report.pathway.find_slot("g")[1]
    assert slot.codes == ["SOC 100"] and slot.title == "SOC 100 title" and slot.status == "replaced"
    assert slot.label.startswith("GE Area 4")  # the requirement's own wording survives the swap


def test_courses_for_the_wrong_area_or_level_or_units_are_refused():
    pathway, catalog = _world()
    for code, fragment in [("ART 101", "does not count for ge area 4"), ("SOC 350", "does not count for ge area 4"), ("SOC 101", "slot needs")]:
        report = _swap(pathway, catalog, code)
        assert report.dropped and fragment in report.dropped[0].violations[0].message.lower(), (code, report.dropped)


def test_a_swapped_ge_row_can_be_swapped_again_because_it_remembers_its_area():
    pathway, catalog = _world()
    first = _swap(pathway, catalog, "SOC 100").pathway
    second = swap_slot(first, "g", "ANTH 110", set(), catalog)
    assert not second.dropped and second.pathway.find_slot("g")[1].codes == ["ANTH 110"]
    wrong = swap_slot(first, "g", "ART 101", set(), catalog)
    assert wrong.dropped  # still held to Area 4


def test_the_model_may_not_edit_ge_rows_but_students_may():
    pathway, catalog = _world()
    by_model = validate_edits(pathway, [Edit(slot_id="g", new_course_code="SOC 100")], set(), catalog, allowed_kinds=MODEL_KINDS)
    assert by_model.dropped and by_model.dropped[0].violations[0].rule == "slot" and not by_model.applied
    assert not _swap(pathway, catalog, "SOC 100").dropped
