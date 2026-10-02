from fastapi.testclient import TestClient
from google.genai import types

from app import ExtractResponse, create_app


class FakeClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, []
        outer = self

        class M:
            async def generate_content(self, **kw):
                outer.calls.append(kw)
                return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=outer.payload)]))])
        class A: models = M()
        self.aio = A()


def test_extractor_returns_structured_json_and_guards_the_key():
    payload = ExtractResponse(is_sfsu_transcript=True, courses=[{"code": "CSC 101", "grade": "A"}]).model_dump_json()
    fc = FakeClient(payload)
    c = TestClient(create_app(client=fc, model="m", api_key="k"))
    assert c.post("/extract", json={"text": "x"}).status_code == 401
    r = c.post("/extract", json={"text": "San Francisco State University\nCSC 101 A"}, headers={"X-Api-Key": "k"})
    assert r.status_code == 200 and r.json()["is_sfsu_transcript"] is True and r.json()["courses"][0]["code"] == "CSC 101"
    assert "<transcript>" in fc.calls[0]["contents"]
    assert c.post("/extract", json={"text": "  "}, headers={"X-Api-Key": "k"}).status_code == 422
    assert c.post("/extract", json={"text": "a" * 200_001}, headers={"X-Api-Key": "k"}).status_code == 413


def test_extractor_not_sfsu_is_reported_not_errored():
    fc = FakeClient('{"is_sfsu_transcript": false, "courses": []}')
    r = TestClient(create_app(client=fc, model="m", api_key="", allow_anonymous=True)).post("/extract", json={"text": "UC Berkeley transcript"})
    assert r.status_code == 200 and r.json() == {"is_sfsu_transcript": False, "program": None, "courses": []}



def test_the_extractor_refuses_to_start_without_an_api_key_unless_anonymous_is_explicit(monkeypatch):
    import pytest

    monkeypatch.delenv("EXTRACTOR_API_KEY", raising=False)
    monkeypatch.delenv("EXTRACTOR_ALLOW_ANONYMOUS", raising=False)
    with pytest.raises(RuntimeError, match="EXTRACTOR_API_KEY"):
        create_app(client=FakeClient("{}"), model="m")
    create_app(client=FakeClient("{}"), model="m", allow_anonymous=True)
    monkeypatch.setenv("EXTRACTOR_ALLOW_ANONYMOUS", "true")
    create_app(client=FakeClient("{}"), model="m")


def test_the_extractor_also_reads_the_degree_program_and_asks_for_it():
    fc = FakeClient(ExtractResponse(is_sfsu_transcript=True, program="B.S. Computer Science", courses=[]).model_dump_json())
    r = TestClient(create_app(client=fc, model="m", api_key="", allow_anonymous=True)).post("/extract", json={"text": "San Francisco State University\nProgram: B.S. Computer Science"})
    assert r.json()["program"] == "B.S. Computer Science"
    assert "program" in fc.calls[0]["contents"].lower() and "major" in fc.calls[0]["contents"].lower()
