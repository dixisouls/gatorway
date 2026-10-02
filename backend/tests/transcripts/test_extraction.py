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
