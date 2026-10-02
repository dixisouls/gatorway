import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gatorway.api.main import create_app
from gatorway.ingest.loader import ingest_all
from gatorway.transcripts.extraction import ExtractedCourse, ExtractedTranscript
from gatorway.transcripts.extractor_client import ExtractorError

from .conftest import bearer

FIX = Path(__file__).resolve().parents[1] / "fixtures"
TEXT = ["San Francisco State University", "Official Transcript", "CSC 101 Introduction to Computing A", "CSC 215 Intermediate Programming B"]


class FakeExtractor:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.received = result, error, []

    async def extract(self, text):
        self.received.append(text)
        if self.error:
            raise self.error
        return self.result


class SpyRedactor:
    def redact(self, text):
        return "[REDACTED]\n" + text


def transcript(*courses, sfsu=True):
    return ExtractedTranscript(is_sfsu_transcript=sfsu, courses=[ExtractedCourse(code=c, grade=g) for c, g in courses])


@pytest.fixture
def catalog(db):
    ingest_all(db, json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text()))
    db.commit()


def make_client(make_state, extractor, **kw):
    return TestClient(create_app(make_state(extractor=extractor, **kw), init_db_on_startup=False))


def upload(client, headers, pdf, name="t.pdf"):
    return client.post("/transcripts", files={"file": (name, pdf, "application/pdf")}, headers=headers)


def auth(client, email="s@sfsu.edu"):
    return bearer(email)


def test_upload_saves_passed_courses_and_flags_unknown_codes(make_state, make_pdf, catalog):
    ex = FakeExtractor(transcript(("CSC 101", "A"), ("CSC 215", "B"), ("MATH 226", "W"), ("XYZ 100", "A"), ("ENGL 114", "IP"), ("csc101", "A")))
    client = make_client(make_state, ex)
    r = upload(client, auth(client), make_pdf(TEXT))
    assert r.status_code == 201
    body = r.json()
    assert [c["code"] for c in body["courses"]] == ["CSC 101", "CSC 215", "XYZ 100"] and body["count"] == 3
    assert body["flagged"] == ["XYZ 100"]  # not in our catalog, but kept


def test_the_extractor_only_ever_receives_redacted_text(make_state, make_pdf, catalog):
    ex = FakeExtractor(transcript(("CSC 101", "A")))
    client = make_client(make_state, ex, redactor=SpyRedactor())
    upload(client, auth(client), make_pdf(TEXT))
    assert ex.received[0].startswith("[REDACTED]\n") and "San Francisco State University" in ex.received[0]


def test_reupload_replaces_the_saved_list_and_get_and_delete_work(make_state, make_pdf, catalog):
    ex = FakeExtractor(transcript(("CSC 101", "A"), ("CSC 215", "B")))
    client = make_client(make_state, ex)
    h = auth(client)
    upload(client, h, make_pdf(TEXT))
    ex.result = transcript(("ART 101", "A"))
    upload(client, h, make_pdf(TEXT))
    assert [c["code"] for c in client.get("/me/courses", headers=h).json()["courses"]] == ["ART 101"]
    assert client.delete("/me/courses", headers=h).status_code == 204
    assert client.get("/me/courses", headers=h).json() == {"count": 0, "courses": [], "flagged": []}


def test_non_sfsu_transcript_is_rejected_and_the_saved_list_is_kept(make_state, make_pdf, catalog):
    ex = FakeExtractor(transcript(("CSC 101", "A")))
    client = make_client(make_state, ex)
    h = auth(client)
    upload(client, h, make_pdf(TEXT))
    ex.result = transcript(("BIO 100", "A"), sfsu=False)
    r = upload(client, h, make_pdf(["UC Berkeley", "Transcript", "BIO 100 Biology A", "More text to pass the minimum length"]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_sfsu_transcript"
    assert [c["code"] for c in client.get("/me/courses", headers=h).json()["courses"]] == ["CSC 101"]


@pytest.mark.parametrize("payload", [lambda mk: mk([]), lambda mk: b"just some text, not a pdf"])
def test_unreadable_uploads_are_rejected_before_reaching_the_extractor(make_state, make_pdf, payload):
    ex = FakeExtractor(transcript())
    client = make_client(make_state, ex)
    r = upload(client, auth(client), payload(make_pdf))
    assert r.status_code == 422 and r.json()["error"]["code"] == "unreadable_pdf" and ex.received == []


def test_oversized_upload_is_rejected(make_state):
    client = make_client(make_state, FakeExtractor(transcript()))
    r = upload(client, auth(client), b"%PDF-" + b"0" * (10 * 1024 * 1024 + 10))
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_extractor_outage_is_a_502_and_changes_nothing(make_state, make_pdf, catalog):
    client = make_client(make_state, FakeExtractor(error=ExtractorError("down")))
    h = auth(client)
    r = upload(client, h, make_pdf(TEXT))
    assert r.status_code == 502 and r.json()["error"]["code"] == "extractor_unavailable"
    assert client.get("/me/courses", headers=h).json()["count"] == 0


def test_a_new_student_with_no_passed_courses_gets_an_empty_list_not_an_error(make_state, make_pdf, catalog):
    client = make_client(make_state, FakeExtractor(transcript(("CSC 101", "IP"))))
    r = upload(client, auth(client), make_pdf(TEXT))
    assert r.status_code == 201 and r.json() == {"count": 0, "courses": [], "flagged": []}


def test_endpoints_require_a_login_and_uploads_are_rate_limited(make_state, make_pdf):
    client = make_client(make_state, FakeExtractor(transcript(("CSC 101", "A"))))
    assert client.post("/transcripts", files={"file": ("t.pdf", make_pdf(TEXT), "application/pdf")}).status_code == 401
    assert client.get("/me/courses").status_code == 401 and client.delete("/me/courses").status_code == 401
    h = auth(client)
    codes = [upload(client, h, make_pdf(TEXT)).status_code for _ in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_the_transcript_title_is_kept_so_odd_lines_can_be_recognised(make_state, make_pdf, catalog):
    ex = FakeExtractor(ExtractedTranscript(is_sfsu_transcript=True, courses=[
        ExtractedCourse(code="ENGL 1A", title="College Composition", grade="A", term="Fall 2022"),
        ExtractedCourse(code="CSC 101", title="Introduction to Computing", grade="A", term="Fall 2023"),
    ]))
    client = make_client(make_state, ex)
    h = auth(client)
    body = upload(client, h, make_pdf(TEXT)).json()
    assert [(c["code"], c["title"], c["flagged"]) for c in body["courses"]] == [("CSC 101", "Introduction to Computing", False), ("ENGL 1A", "College Composition", True)]
    assert client.get("/me/courses", headers=h).json()["courses"][1]["title"] == "College Composition"


def test_when_redaction_fails_nothing_is_sent_to_the_extractor(make_state, make_pdf, catalog):
    from gatorway.transcripts.pii import RedactionError

    class BrokenRedactor:
        def redact(self, text):
            raise RedactionError("model missing")

    ex = FakeExtractor(transcript(("CSC 101", "A")))
    client = make_client(make_state, ex, redactor=BrokenRedactor())
    r = upload(client, auth(client), make_pdf(TEXT))
    assert r.status_code == 503 and r.json()["error"]["code"] == "redaction_unavailable"
    assert ex.received == []  # fail closed: unredacted text never leaves
