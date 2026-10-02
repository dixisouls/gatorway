import io
import json

import httpx
import pytest
from reportlab.pdfgen import canvas

from gatorway.transcripts.extractor_client import ExtractorError, HttpExtractor
from gatorway.transcripts.pdf import NoTextError, extract_text
from gatorway.transcripts.redact import StubRedactor


def make_pdf(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines:
        c.drawString(60, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


def test_text_pdf_is_extracted():
    text = extract_text(make_pdf(["San Francisco State University", "Official Transcript", "CSC 101 Introduction to Computing A 3.0"]))
    assert "San Francisco State University" in text and "CSC 101" in text


@pytest.mark.parametrize("data", [make_pdf([]), b"not a pdf at all", b""])
def test_scanned_blank_or_corrupt_pdf_is_rejected(data):
    with pytest.raises(NoTextError):
        extract_text(data)


def test_stub_redactor_passes_text_through_and_warns_once(caplog):
    r = StubRedactor()
    with caplog.at_level("WARNING"):
        assert r.redact("abc") == "abc" and r.redact("def") == "def"
    assert sum("NOT being redacted" in m for m in caplog.messages) == 1


def mock_extractor(handler, key="k"):
    return HttpExtractor("http://extractor.test/", api_key=key, transport=httpx.MockTransport(handler))


async def test_http_extractor_posts_text_with_the_api_key_and_parses_the_answer():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers.get("x-api-key"), json.loads(request.content)
        return httpx.Response(200, json={"is_sfsu_transcript": True, "courses": [{"code": "CSC 101", "grade": "A"}]})

    out = await mock_extractor(handler).extract("hello transcript")
    assert out.is_sfsu_transcript and out.courses[0].code == "CSC 101"
    assert seen == {"url": "http://extractor.test/extract", "key": "k", "body": {"text": "hello transcript"}}


@pytest.mark.parametrize("response", [httpx.Response(500), httpx.Response(401), httpx.Response(200, text="not json"), httpx.Response(200, json={"wrong": "shape"})])
async def test_http_extractor_turns_bad_answers_into_extractor_error(response):
    with pytest.raises(ExtractorError):
        await mock_extractor(lambda request: response).extract("x")


async def test_http_extractor_turns_connection_failures_into_extractor_error():
    def boom(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ExtractorError):
        await mock_extractor(boom).extract("x")
