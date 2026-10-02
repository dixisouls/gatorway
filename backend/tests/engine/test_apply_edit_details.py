from gatorway.engine.models import Catalog, CourseInfo, Edit, Pathway, Slot, Term
from gatorway.engine.validator import validate_edits


def _world():
    slot = Slot(slot_id="s", title="SF State Studies or University Elective", units=3, slot_kind="free_elective", swappable=True)
    pathway = Pathway(program_id=1, roadmap_id=1, terms=[Term(position=0, label="T", slots=[slot])])
    catalog = Catalog(courses={"X 200": CourseInfo(code="X 200", title="Drawing Studio", units_min=4, units_max=4, number_int=200)})
    return pathway, catalog


def test_a_picked_course_gives_its_own_title_and_units_to_the_slot():
    pathway, catalog = _world()
    report = validate_edits(pathway, [Edit(slot_id="s", new_course_code="X 200")], set(), catalog)
    slot = report.pathway.find_slot("s")[1]
    assert slot.codes == ["X 200"] and slot.status == "replaced"
    assert slot.title == "Drawing Studio"  # not the roadmap row's generic "University Elective"
    assert slot.units == 4  # so the card and the term total show the real units
    assert pathway.find_slot("s")[1].title.startswith("SF State")  # the input is untouched
