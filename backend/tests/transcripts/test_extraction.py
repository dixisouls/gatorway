from gatorway.transcripts.extraction import ExtractedCourse, ExtractedTranscript, normalize_code, passed_courses


def test_normalize_code():
    assert [normalize_code(x) for x in ("csc215", "CSC-215", " MATH\xa0226 ", "BIOL 100GW", "Intro", None)] == ["CSC 215", "CSC 215", "MATH 226", "BIOL 100GW", None, None]


def test_passed_courses_filters_dedupes_and_counts_retakes():
    t = ExtractedTranscript(is_sfsu_transcript=True, courses=[
        ExtractedCourse(code="CSC 215", grade="F"), ExtractedCourse(code="csc215", grade="B"),
        ExtractedCourse(code="MATH 226", grade="W"), ExtractedCourse(code="ENGL 114", grade="IP"),
        ExtractedCourse(code="HIST 100", grade="CR"), ExtractedCourse(code="???", grade="A")])
    assert [(c.code, c.grade) for c in passed_courses(t)] == [("CSC 215", "B"), ("HIST 100", "CR")]


import json
from pathlib import Path

import pytest


def test_subjects_that_contain_a_space_are_parsed():
    assert [normalize_code(x) for x in ("TH A 130", "c j 100", "I R 301", "AA S 101", "th a130")] == ["TH A 130", "C J 100", "I R 301", "AA S 101", "TH A 130"]


def test_codes_that_look_like_courses_but_do_not_parse_are_kept_not_dropped():
    t = ExtractedTranscript(is_sfsu_transcript=True, courses=[ExtractedCourse(code="ABCDEFGH 12345", grade="A"), ExtractedCourse(code="???", grade="A")])
    assert [c.code for c in passed_courses(t)] == ["ABCDEFGH 12345"]


REAL_CATALOG = Path(__file__).resolve().parents[3] / "scraping/sfsu_output/sfsu_courses.json"


@pytest.mark.skipif(not REAL_CATALOG.exists(), reason="scraped data not present")
def test_every_real_catalog_code_survives_normalisation_unchanged():
    codes = [c["course_code"] for c in json.loads(REAL_CATALOG.read_text()) if c.get("course_code")]
    assert [c for c in codes if normalize_code(c) != c] == []


import pytest as _pytest  # noqa: E402

from gatorway.transcripts.extraction import clean_term  # noqa: E402


@_pytest.mark.parametrize("raw,expected", [
    ("Fall 2023", "Fall 2023"), ("fall  2023", "Fall 2023"), ("SP2025", "Spring 2025"), ("FA 2023", "Fall 2023"), ("SU24", "Summer 2024"),
    ("2023 Fall", "Fall 2023"), ("Winter 2024", "Winter 2024"), ("Transfer Credit", "Transfer credit"),
])
def test_real_terms_are_kept_in_one_readable_form(raw, expected):
    assert clean_term(raw) == expected


@_pytest.mark.parametrize("raw", ["Student ID", "[STUDENT ID]", "SFSU ID: [STUDENT ID]", "923000111", "", None, "Name", "Cumulative GPA 3.5"])
def test_anything_that_is_not_a_term_is_dropped_never_shown_as_a_semester(raw):
    assert clean_term(raw) is None


def test_the_cleaned_term_is_what_gets_saved():
    ex = ExtractedTranscript(is_sfsu_transcript=True, courses=[ExtractedCourse(code="CSC 101", grade="A", term="[STUDENT ID]"), ExtractedCourse(code="CSC 215", grade="B", term="SP2025")])
    assert [(c.code, c.term) for c in passed_courses(ex)] == [("CSC 101", None), ("CSC 215", "Spring 2025")]
