import json

import pytest

litellm = pytest.importorskip("litellm")

from litellm import ModelResponse  # noqa: E402
from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices  # noqa: E402

from phiveil.integrations.litellm import PhiveilGuardrail  # noqa: E402


def guard(**kw):
    return PhiveilGuardrail(guardrail_name="phiveil", event_hook=["pre_call", "post_call"], default_on=True, **kw)


def request(content, **metadata):
    return {
        "model": "gpt-x",
        "messages": [{"role": "user", "content": content}],
        "metadata": {"session_id": "conv-1", **metadata},
    }


async def test_pre_call_masks_and_drops_known():
    g = guard()
    data = request(
        "hi it's sarah, my phone is 416 555 0142",
        phiveil_known={"names": ["Sarah Chen"], "phones": ["416-555-0142"]},
    )
    out = await g.async_pre_call_hook(None, None, data, "completion")
    sent = json.dumps(out["messages"])
    assert "sarah" not in sent.lower() and "555" not in sent
    assert "phiveil_known" not in out["metadata"]
    assert out["metadata"]["phiveil_session_id"] == "conv-1"


async def test_client_cannot_opt_out():
    g = guard()
    data = request("call 416-555-0142", disable_global_guardrail=True, guardrails=[])
    out = await g.async_pre_call_hook(None, None, data, "completion")
    assert "416" not in json.dumps(out["messages"])


async def test_post_call_unmasks_message_and_tool_args():
    g = guard()
    data = await g.async_pre_call_hook(None, None, request("call 416-555-0142"), "completion")
    resp = ModelResponse(
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Calling [PHONE_1] now.",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "dial", "arguments": '{"to": "[PHONE_1]"}'}}],
            },
        }]
    )
    out = await g.async_post_call_success_hook(data, None, resp)
    msg = out.choices[0].message
    assert msg.content == "Calling 416-555-0142 now."
    assert json.loads(msg.tool_calls[0].function.arguments) == {"to": "416-555-0142"}


async def test_streaming_unmask_across_chunk_boundaries():
    g = guard()
    data = await g.async_pre_call_hook(None, None, request("email jane@example.com"), "completion")
    text = "Sure, I'll write to [EMAIL_1] today."
    pieces = ["Sure, I'll write to [EM", "AIL", "_1] tod", "ay."]

    async def stream():
        for p in pieces:
            yield ModelResponseStream(choices=[StreamingChoices(index=0, delta=Delta(content=p))])
        yield ModelResponseStream(choices=[StreamingChoices(index=0, delta=Delta(), finish_reason="stop")])

    out = []
    async for chunk in g.async_post_call_streaming_iterator_hook(None, stream(), data):
        out.append(chunk.choices[0].delta.content or "")
    assert "".join(out) == text.replace("[EMAIL_1]", "jane@example.com")


async def test_image_rejected_fail_closed():
    g = guard()
    data = request([{"type": "image_url", "image_url": {"url": "https://x/y.png"}}])
    with pytest.raises(Exception) as exc:
        await g.async_pre_call_hook(None, None, data, "completion")
    assert "phiveil" in str(exc.value.__dict__ or exc.value)


async def test_known_entities_provider(monkeypatch):
    import types, sys

    mod = types.ModuleType("fake_lookup")

    async def lookup(session_id, metadata):
        assert metadata["patient_id"] == "p-1"
        return {"names": ["Priya Natarajan"]}

    mod.lookup = lookup
    monkeypatch.setitem(sys.modules, "fake_lookup", mod)
    g = guard(known_entities_provider="fake_lookup:lookup")
    out = await g.async_pre_call_hook(None, None, request("priya here, quick question", patient_id="p-1"), "completion")
    assert "priya" not in json.dumps(out["messages"]).lower()
