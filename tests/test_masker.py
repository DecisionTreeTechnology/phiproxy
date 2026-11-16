import json

import pytest

from phiveil import KnownEntities, Masker, PhiveilError, Policy, UnsupportedContentError
from phiveil.detectors.regex import RegexDetector

KNOWN = KnownEntities(names=["Sarah Chen"], phones=["416-555-0142"], dates_of_birth=["1990-03-05"])


def test_round_trip_and_consistency():
    m = Masker()
    a = m.mask("Hi, this is Sarah Chen, call 416-555-0142", "s", KNOWN)
    b = m.mask("Sarah Chen again; same number 416 555 0142", "s", KNOWN)
    assert "Sarah" not in a.text and "416" not in a.text
    assert "[NAME_1]" in a.text and "[NAME_1]" in b.text  # same value, same token
    assert "[PHONE_1]" in b.text  # formatting differences normalize to the same token
    assert m.unmask("Thanks [NAME_1], we'll call [PHONE_1].", "s") == "Thanks Sarah Chen, we'll call 416-555-0142."


def test_sessions_are_isolated():
    m = Masker()
    m.mask("call 416-555-0142", "s1")
    assert m.unmask("[PHONE_1]", "s2") == "[PHONE_1]"


def test_tolerant_unmask_and_unknown_tokens():
    m = Masker()
    m.mask("email jane@example.com", "s")
    for variant in ["[EMAIL_1]", "[email_1]", "[ EMAIL 1 ]", "EMAIL_1", "[EMAIL-1]"]:
        assert m.unmask(f"to {variant}.", "s") == "to jane@example.com."
    assert m.unmask("[EMAIL_9] and [NAME_1]", "s") == "[EMAIL_9] and [NAME_1]"


def test_token_is_not_derived_from_value():
    m = Masker()
    t1 = m.mask("call 416-555-0142", "a").text
    t2 = m.mask("call 647-555-0199", "b").text
    assert t1 == t2 == "call [PHONE_1]"


def test_remask_for_logs():
    m = Masker()
    m.mask("this is Sarah Chen", "s", KNOWN)
    assert m.remask("Hello sarah chen!", "s") == "Hello [NAME_1]!"


def test_provider_names_pass_by_default():
    assert Masker().mask("Dr. Patel said so", "s").text == "Dr. Patel said so"
    m = Masker(policy=Policy(disabled_types=set()))
    assert m.mask("Dr. Patel said so", "s").text == "Dr. [PROVIDER_1] said so"


def test_date_shift_round_trip():
    m = Masker(policy=Policy(date_mode="shift"))
    text = "retrieval 2026-11-03, transfer Nov 8th"
    masked = m.mask(text, "s").text
    assert "2026-11-03" not in masked and "[DATE" not in masked
    assert m.unmask(masked, "s") == text


def test_fail_closed_on_detector_error():
    class Boom:
        name = "boom"

        def detect(self, text):
            raise RuntimeError("model crashed")

    with pytest.raises(PhiveilError):
        Masker(detectors=[RegexDetector(), Boom()]).mask("call 416-555-0142", "s")


def test_openai_messages_payload():
    m = Masker()
    messages = [
        {"role": "system", "content": "You are a clinic assistant."},
        {"role": "user", "content": [{"type": "text", "text": "I'm Sarah Chen, 416-555-0142"}]},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "lookup_patient",
                                         "arguments": json.dumps({"phone": "416-555-0142"})}}],
        },
        {"role": "tool", "tool_call_id": "c1", "content": '{"dob": "1990-03-05", "name": "Sarah Chen"}'},
    ]
    out = m.mask_payload(messages, "s", KNOWN)
    dumped = json.dumps(out)
    assert "Sarah" not in dumped and "416-555" not in dumped and "1990-03-05" not in dumped
    assert out[2]["tool_calls"][0]["function"]["name"] == "lookup_patient"
    assert json.loads(out[2]["tool_calls"][0]["function"]["arguments"]) == {"phone": "[PHONE_1]"}
    assert messages[1]["content"][0]["text"].startswith("I'm Sarah")  # input untouched
    back = m.unmask_payload(out, "s")
    assert json.loads(back[2]["tool_calls"][0]["function"]["arguments"]) == {"phone": "416-555-0142"}


def test_anthropic_blocks_payload():
    m = Masker()
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "My email is sarah@example.com"},
        {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "MRN: 00482913"}]},
        {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": "SSN 123-45-6789"}},
    ]}]
    dumped = json.dumps(m.mask_payload(msgs, "s"))
    assert "sarah@" not in dumped and "00482913" not in dumped and "123-45-6789" not in dumped
    assert '"tool_use_id": "t1"' in dumped


def test_images_blocked_unless_allowed():
    msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}]}]
    with pytest.raises(UnsupportedContentError):
        Masker().mask_payload(msg, "s")
    assert Masker(policy=Policy(allow_images=True)).mask_payload(msg, "s") == msg


def test_stream_unmasker_never_splits_tokens():
    m = Masker()
    m.mask("Hi this is Sarah Chen at 416-555-0142", "s", KNOWN)
    reply = "Thanks [NAME_1]! We will call you at [PHONE_1] tomorrow. " * 3
    expected = m.unmask(reply, "s")
    for size in (1, 2, 3, 5, 7, 13):
        u = m.stream_unmasker("s")
        out = "".join(u.feed(reply[i : i + size]) for i in range(0, len(reply), size)) + u.flush()
        assert out == expected, size


def test_stream_unmasker_shift_mode_dates():
    m = Masker(policy=Policy(date_mode="shift"))
    masked = m.mask("transfer on 2026-11-08 and check 11/20/2026", "s").text
    u = m.stream_unmasker("s")
    out = "".join(u.feed(ch) for ch in masked) + u.flush()
    assert out == "transfer on 2026-11-08 and check 11/20/2026"
