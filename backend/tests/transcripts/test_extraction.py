from gatorway.transcripts.extraction import ExtractedCourse, ExtractedTranscript, normalize_code, passed_courses


def test_normalize_code():
    assert [normalize_code(x) for x in ("csc215", "CSC-215", " MATH\xa0226 ", "BIOL 100GW", "Intro", None)] == ["CSC 215", "CSC 215", "MATH 226", "BIOL 100GW", None, None]


def test_passed_courses_filters_dedupes_and_counts_retakes():
    t = ExtractedTranscript(is_sfsu_transcript=True, courses=[
        ExtractedCourse(code="CSC 215", grade="F"), ExtractedCourse(code="csc215", grade="B"),
        ExtractedCourse(code="MATH 226", grade="W"), ExtractedCourse(code="ENGL 114", grade="IP"),
        ExtractedCourse(code="HIST 100", grade="CR"), ExtractedCourse(code="???", grade="A")])
    assert [(c.code, c.grade) for c in passed_courses(t)] == [("CSC 215", "B"), ("HIST 100", "CR")]
