from gatorway.engine.ge import counts_for_ge, ge_tokens, has_ge_courses


def test_ge_tokens_read_the_areas_a_row_names():
    assert ge_tokens("GE Area 4: Social and Behavioral Sciences") == ["4"]
    assert ge_tokens("GE Area 4UD: Upper-Division Social and Behavioral Sciences") == ["4UD"]
    assert ge_tokens("GE Area 5UD or 2UD: Upper-Division Science or Math") == ["5UD", "2UD"]
    assert ge_tokens("GE Areas 5A + 5C: Physical Science and Laboratory") == ["5A", "5C"]
    assert ge_tokens("GE Area UD") == [] and ge_tokens("Introduction to Computing") == []


def test_a_course_counts_when_its_label_matches_the_area_and_level():
    assert counts_for_ge(["4: Social/Behavioral Sciences"], 100, ["4"])
    assert counts_for_ge(["D1: Social Sciences"], 110, ["4"])  # the older letter label counts too
    assert not counts_for_ge(["4: Social/Behavioral Sciences"], 350, ["4"])  # upper division does not fill a lower-division row
    assert counts_for_ge(["4: Social/Behavioral Sciences"], 350, ["4UD"])
    assert not counts_for_ge(["3A: Arts"], 100, ["4"])
    assert counts_for_ge(["3A: Arts"], 100, ["3"]) and counts_for_ge(["3B: Humanities"], 100, ["3"])  # Area 3 = 3A + 3B
    assert not counts_for_ge([], 100, ["4"])


def test_only_areas_with_labelled_courses_can_be_chosen_from():
    assert has_ge_courses(["4"]) and has_ge_courses(["5UD", "2UD"])
    assert not has_ge_courses(["2"]) and not has_ge_courses([])  # math has no labelled courses in the catalog
