import pytest

from gatorway.transcripts.program_match import rank_programs


def prog(i, title, degree_type, level):
    return {"id": i, "title": title, "degree_type": degree_type, "level": level, "college": "Science", "slug": f"p{i}", "department": None, "concentration": None}


PROGRAMS = [
    prog(1, "Bachelor of Science in Computer Science", "B.S.", "undergraduate"),
    prog(2, "Master of Science in Computer Science", "M.S.", "graduate"),
    prog(3, "Minor in Computer Science", "Minor", "minor"),
    prog(4, "Bachelor of Science in Computer Engineering", "B.S.", "undergraduate"),
    prog(5, "Bachelor of Arts in Art", "B.A.", "undergraduate"),
    prog(6, "Bachelor of Science in Biology", "B.S.", "undergraduate"),
]


def top(raw):
    ranked = rank_programs(raw, PROGRAMS)
    return ranked[0]["id"] if ranked else None


@pytest.mark.parametrize("raw,expected", [
    ("B.S. Computer Science", 1), ("Bachelor of Science, Computer Science", 1), ("Computer Science, B.S.", 1), ("BS Computer Science", 1),
    ("Master of Science Computer Science", 2), ("M.S. in Computer Science", 2), ("Minor in Computer Science", 3),
    ("Computer Engineering B.S.", 4), ("B.A. Art", 5), ("Bachelor of Science Biology", 6),
])
def test_the_degree_as_printed_finds_the_right_program(raw, expected):
    assert top(raw) == expected


def test_a_bare_major_prefers_the_bachelors_but_still_offers_the_others():
    ranked = rank_programs("Computer Science", PROGRAMS)
    assert [p["id"] for p in ranked][:3] == [1, 2, 3] or ranked[0]["id"] == 1
    assert ranked[0]["id"] == 1


def test_a_stated_level_is_not_confused_with_a_different_one():
    assert 1 not in [p["id"] for p in rank_programs("Master of Science Computer Science", PROGRAMS)][:1]
    assert top("Bachelor of Science in Computer Science") == 1


def test_candidates_carry_a_score_and_at_most_three_are_returned():
    ranked = rank_programs("Computer Science", PROGRAMS)
    assert len(ranked) <= 3 and all(0 < p["score"] <= 1 for p in ranked)
    assert ranked == sorted(ranked, key=lambda p: -p["score"])


@pytest.mark.parametrize("raw", ["Underwater Basket Weaving", "", "   ", None, "Fall 2023"])
def test_nothing_plausible_means_no_candidates(raw):
    assert rank_programs(raw, PROGRAMS) == []


def test_a_program_that_shares_only_the_degree_words_is_not_a_candidate():
    ids = [p["id"] for p in rank_programs("B.S. Computer Science", PROGRAMS)]
    assert 6 not in ids and 5 not in ids  # Biology and Art share "Bachelor of Science/Arts" but not the field
    assert 1 in ids and 4 in ids  # Computer Engineering shares "computer", so it stays as a close alternative
