import pytest
from fastmcp import Client, FastMCP
from google.genai import types

from gatorway.llm.gemini import GeminiLlm, parse_edits
from gatorway.llm.ports import Intent


def fn_call(name, args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))]))])


def text_resp(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]))])


class FakeClient:
    """Scripted stand-in for genai.Client: .aio.models.generate_content pops queued responses."""

    def __init__(self, responses):
        self.calls, self._q = [], list(responses)
        outer = self

        class _Models:
            async def generate_content(self, **kw):
                outer.calls.append(kw)
                return outer._q.pop(0)

        class _Aio:
            models = _Models()

        self.aio = _Aio()


def make_mcp():
    mcp = FastMCP("t")

    @mcp.tool
    def get_baseline(session_id: str) -> dict:
        """baseline"""
        return {"session": session_id, "slots": ["f1"]}

    @mcp.tool
    def secret_admin(session_id: str) -> dict:
        """not allowed"""
        return {"x": 1}

    return mcp


INTENT = Intent(specialization=True, topics=["web development"], keywords=["Next.js"], summary="wants web dev")


async def test_tool_loop_then_json_edits():
    client = FakeClient([fn_call("get_baseline", {"session_id": "S1"}),
                         text_resp('Here you go:\n```json\n{"edits":[{"slot_id":"f1","new_course_code":"CSC 667","reason":"web"}]}\n```')])
    async with Client(make_mcp()) as mcp:
        edits = await GeminiLlm(client, "m").propose_edits("S1", mcp, {"get_baseline"}, INTENT, None)
    assert [(e.slot_id, e.new_course_code) for e in edits] == [("f1", "CSC 667")]
    # the tool result was fed back to the model as a function response
    last_user = client.calls[1]["contents"][-1]
    assert last_user.parts[0].function_response.response["result"] == {"session": "S1", "slots": ["f1"]}
    # only allowed tools were declared to the model
    decl_names = [d.name for d in client.calls[0]["config"].tools[0].function_declarations]
    assert decl_names == ["get_baseline"]


async def test_disallowed_tool_call_is_refused_not_executed():
    client = FakeClient([fn_call("secret_admin", {"session_id": "S1"}), text_resp('{"edits": []}')])
    async with Client(make_mcp()) as mcp:
        edits = await GeminiLlm(client, "m").propose_edits("S1", mcp, {"get_baseline"}, INTENT, None)
    assert edits == []
    assert client.calls[1]["contents"][-1].parts[0].function_response.response["result"] == {"error": "unknown tool secret_admin"}


async def test_tool_error_is_returned_to_the_model():
    client = FakeClient([fn_call("get_baseline", {}), text_resp('{"edits": []}')])  # missing session_id
    async with Client(make_mcp()) as mcp:
        await GeminiLlm(client, "m").propose_edits("S1", mcp, {"get_baseline"}, INTENT, None)
    assert "error" in client.calls[1]["contents"][-1].parts[0].function_response.response["result"]


async def test_no_edits_when_the_closing_answer_has_nothing_usable():
    from gatorway.llm.gemini import MAX_TURNS

    client = FakeClient([fn_call("get_baseline", {"session_id": "S"})] * MAX_TURNS + [text_resp("I could not decide.")])
    async with Client(make_mcp()) as mcp:
        assert await GeminiLlm(client, "m").propose_edits("S", mcp, {"get_baseline"}, INTENT, None) == []


async def test_parse_intent_uses_structured_output():
    r = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=INTENT.model_dump_json())]))])
    r.parsed = INTENT
    out = await GeminiLlm(FakeClient([r]), "m").parse_intent("web dev with Next.js")
    assert out.specialization and out.keywords == ["Next.js"]


def test_parse_edits_tolerates_garbage():
    assert parse_edits(None) == [] and parse_edits("no json here") == [] and parse_edits("{bad json}") == []
    assert parse_edits('{"edits":[{"slot_id":"a"},{"slot_id":"b","new_course_code":"X 1"}]}')[0].slot_id == "b"


async def test_thinking_off_is_applied_to_intent_and_edit_calls():
    client = FakeClient([text_resp('{"specialization": false, "topics": [], "keywords": [], "summary": ""}'), text_resp('{"edits": []}')])
    llm = GeminiLlm(client, "m", thinking_level="off")
    await llm.parse_intent("anything")
    async with Client(make_mcp()) as mcp:
        await llm.propose_edits("S1", mcp, {"get_baseline"}, INTENT, None)
    for call in client.calls:
        assert call["config"].thinking_config.thinking_budget == 0


async def test_no_thinking_config_when_level_is_blank():
    client = FakeClient([text_resp('{"specialization": false, "topics": [], "keywords": [], "summary": ""}')])
    await GeminiLlm(client, "m", thinking_level="").parse_intent("x")
    assert client.calls[0]["config"].thinking_config is None


async def test_named_thinking_level_is_passed_through():
    client = FakeClient([text_resp('{"specialization": false, "topics": [], "keywords": [], "summary": ""}')])
    await GeminiLlm(client, "m", thinking_level="low").parse_intent("x")
    assert client.calls[0]["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW


async def test_when_the_tool_rounds_run_out_the_model_is_asked_for_its_answer_without_tools():
    from gatorway.llm.gemini import MAX_TURNS

    searching = [fn_call("get_baseline", {"session_id": "S1"}) for _ in range(MAX_TURNS)]
    final = text_resp('{"edits":[{"slot_id":"f1","new_course_code":"CSC 667","reason":"web"}]}')
    client = FakeClient(searching + [final])
    async with Client(make_mcp()) as mcp:
        edits = await GeminiLlm(client, "m").propose_edits("S1", mcp, {"get_baseline"}, INTENT, None)
    assert [(e.slot_id, e.new_course_code) for e in edits] == [("f1", "CSC 667")]
    last = client.calls[-1]
    assert not last["config"].tools  # the closing call cannot search again
    assert "final" in last["contents"][-1].parts[0].text.lower()


def test_prompt_tells_the_model_to_search_all_swappable_slots_in_one_step():
    from gatorway.llm.gemini import SYSTEM

    assert "same step" in SYSTEM.lower() or "in parallel" in SYSTEM.lower()
