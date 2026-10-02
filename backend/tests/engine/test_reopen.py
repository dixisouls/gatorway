from gatorway.engine.models import Pathway, Slot, Term
from gatorway.engine.validator import reopen_slot


def _pathway():
    slots = [Slot(slot_id="a", title="x", swappable=True, status="replaced"), Slot(slot_id="b", title="y", status="passed")]
    return Pathway(program_id=1, roadmap_id=1, terms=[Term(position=0, label="T", slots=slots)])


def test_reopen_slot_turns_a_replaced_slot_back_into_a_planned_one_on_a_copy():
    p = _pathway()
    out = reopen_slot(p, "a")
    assert out.find_slot("a")[1].status == "planned"
    assert p.find_slot("a")[1].status == "replaced"  # the original is untouched


def test_reopen_slot_leaves_other_slots_and_unknown_ids_alone():
    p = _pathway()
    assert reopen_slot(p, "b").find_slot("b")[1].status == "passed"
    assert reopen_slot(p, "nope").model_dump() == p.model_dump()
