import json, os
from pathlib import Path
import pytest
from gatorway.ingest.prereqs import build_prereq_groups as g, non_course_conditions
from gatorway.ingest.slots import SlotClass, choose_default_roadmap, classify_slot, parse_seats, pick_pool_section, section_kind
from gatorway.transcripts.grades import is_passing


def test_prereq_groups_cases():
    assert g("Prerequisites: ENGR 221*, ENGR 281* or ENGR 282*, and MATH 245* with grades of C- or better.",
             ["ENGR 221", "ENGR 281", "ENGR 282", "MATH 245"]) == (
        [["ENGR 221"], ["ENGR 281", "ENGR 282"], ["MATH 245"]], ["ENGR 221", "ENGR 281", "ENGR 282", "MATH 245"])
    assert g("Prerequisites: MATH 226, MATH 227, or MATH 228.", ["MATH 226", "MATH 227", "MATH 228"])[0] == [["MATH 226", "MATH 227", "MATH 228"]]
    assert g("Prerequisite: Concurrent enrollment in ACCT 100*.", ["ACCT 100"]) == ([["ACCT 100"]], ["ACCT 100"])
    assert g("Prerequisites: CSC 210 or CSC 215; MATH 226.", ["CSC 210", "CSC 215", "MATH 226"])[0] == [["CSC 210", "CSC 215"], ["MATH 226"]]


def test_prereq_shorthand_and_empty_fall_back_to_strict():
    assert g("Prerequisite: MATH 226, 227 or 228.", ["MATH 226", "MATH 227", "MATH 228"])[0] == [["MATH 226"], ["MATH 227"], ["MATH 228"]]
    assert g("Prerequisite: permission of instructor.", []) == ([], [])


def test_non_course_conditions():
    assert non_course_conditions("Prerequisites: Restricted to graduate students; MKTG 431* and MKTG 688; or permission of the instructor.",
                                 ["MKTG 431", "MKTG 688"]) == ["Restricted to graduate students", "or permission of the instructor"]
    assert non_course_conditions("Prerequisite: GE Area 1C/A1*.", []) == ["GE Area 1C/A1*"]
    assert non_course_conditions(None, []) == []


def test_parse_seats():
    assert parse_seats("Major Elective (15 Units Total) - Take Three") == 3
    assert parse_seats("University Elective - Take 2") == 2
    assert parse_seats("University Elective") == 1


def test_classify_slot():
    assert classify_slot(["CSC 101"], "Intro", ["Major Core"], True) == SlotClass("fixed", False, True)
    assert classify_slot([], "SF State Studies or University Elective", [], True).slot_kind == "free_elective"
    assert classify_slot([], "Major Elective (15 Units Total) - Take Two", [], True).slot_kind == "major_elective"
    assert classify_slot([], "Major Elective (15 Units Total)", [], False).swappable is False  # no pool -> fixed
    assert classify_slot([], "GE Area 4: Social and Behavioral Sciences", [], True).swappable is False
    assert classify_slot([], "Select One (Major Core):", [], True).swappable is False


def test_pool_section_and_default_roadmap():
    secs = [{"heading": "Core", "rows": [{"type": "course"}]}, {"heading": "Concentration Electives", "rows": [{"type": "course"}]},
            {"heading": "Electives", "rows": [{"type": "course"}]}, {"heading": "Empty Electives", "rows": []}]
    assert pick_pool_section(secs) == 2
    assert pick_pool_section([{"heading": "Core", "rows": []}]) is None
    assert choose_default_roadmap(["BS ADT Roadmap", "QR Pathway 1/2 Roadmap", "QR Pathway 3/4"]) == 1
    assert choose_default_roadmap(["ADT Roadmap"]) == 0
    assert section_kind("General Education Requirements") == "ge" and section_kind("Electives (15 units)") == "elective"


def test_grades():
    assert [is_passing(x) for x in ("A", "c-", "CR", "F", "W", "NC", "IP", None)] == [True, True, True, False, False, False, False, False]


REAL = str(Path(__file__).resolve().parents[3] / "scraping/sfsu_output/sfsu_programs.json")
@pytest.mark.skipif(not os.path.exists(REAL), reason="scraped data not present")
def test_real_data_has_some_swappable_slots():
    P = json.load(open(REAL))
    n = 0
    for p in P:
        secs = p["requirements"]["sections"] if p["requirements"] else []
        pool = pick_pool_section(secs) is not None
        for rm in p["roadmaps"]:
            for gr in rm["content"]["grids"]:
                for t in gr["terms"]:
                    for i in t["items"]:
                        if classify_slot(i["codes"], i["title"], i["tags"], pool).swappable:
                            n += 1
    assert n > 1000
    print("swappable roadmap rows:", n)


def test_alternate_rows_that_start_with_or_are_never_swappable():
    for title in ("or University Elective if US History requirement is met", "Or SF State Studies or University Elective"):
        sc = classify_slot([], title, [], True)
        assert (sc.slot_kind, sc.swappable) == ("fixed", False)
    assert classify_slot([], "SF State Studies or University Elective", [], True).swappable is True


def test_course_counts_toward_major_when_it_is_in_the_programs_requirement_sections():
    # the roadmap tag "Core Computer Science Requirement" never says "major", but the degree requirements list the course
    in_reqs = classify_slot(["CSC 101"], "Intro", ["Core Computer Science Requirement"], True, major_codes={"CSC 101"})
    assert in_reqs.counts_toward_major is True and in_reqs.slot_kind == "fixed" and in_reqs.swappable is False
    assert classify_slot(["CSC 101"], "Intro", ["Core Computer Science Requirement"], True, major_codes=set()).counts_toward_major is False
    assert classify_slot(["ART 100"], "Art", ["GE 3"], True, major_codes={"CSC 101"}).counts_toward_major is False


def test_plural_and_qualified_major_elective_rows_are_swappable_too():
    for title in ("Major Electives", "Major Upper-Division Electives - Take Two", "Major Concentration Elective", "Major Approved Elective", "Upper-Division Electives"):
        assert classify_slot([], title, [], True).slot_kind == "major_elective", title
    assert classify_slot([], "Major Electives", [], False).swappable is False  # still needs a pool of allowed courses
    for title in ("Select One (Major Core):", "Concentration Elective", "Graduate Elective", "GE Area 3: Arts and Humanities"):
        assert classify_slot([], title, [], True).swappable is False, title
