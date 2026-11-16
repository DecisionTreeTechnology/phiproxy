# phiproxy

**Your patients' stand-in on the way to any LLM, and back.** · [Project page](https://decisiontree.tech/open-source/phiproxy) · [PyPI](https://pypi.org/project/phiproxy/)

phiproxy is a proxy in two senses:

1. **A proxy for the patient.** Before a prompt leaves your network, every identifier (name, date of birth, phone, health card number...) is replaced by a stand-in such as `[NAME_1]`. The AI provider only ever sees the stand-ins.
2. **A proxy server.** It sits between your apps and every LLM provider as a [LiteLLM](https://github.com/BerriAI/litellm) guardrail, so there is one enforcement point for OpenAI, Anthropic, Azure, Bedrock and Gemini. It also works as a plain Python library.

When the reply comes back, phiproxy swaps the stand-ins for the real values, so your users and your tools see the right patient. The round trip is the point: the model can still reason about the conversation without ever seeing who it is about.

```
"Hi, this is Sarah Chen, DOB 1990-03-05. Call me at 416-555-0142."
        │ phiproxy (inside your network)
        ▼
"Hi, this is [NAME_1], DOB [DATE_1]. Call me at [PHONE_1]."   ──►  any LLM provider
        ▲
        │ reply: "Thanks [NAME_1], we'll call [PHONE_1] today."
"Thanks Sarah Chen, we'll call 416-555-0142 today."            ◄──
```

> **Status: pre-alpha (0.1.0a2).** APIs will change. Do not rely on it as your only control.

## Read this first

- **phiproxy reduces how much PHI reaches an LLM provider. It does not make an unapproved provider compliant.** No detector catches 100% of identifiers; every miss is a disclosure. Send PHI only to providers you have a BAA (HIPAA) or equivalent agreement (e.g. PHIPA agent agreement) with, and use phiproxy as an extra layer on top.
- Audio, images and files cannot be masked as text. phiproxy **blocks** them by default.
- Get privacy or legal review before relying on de-identification for any workload.

## What makes it different

- **Your own records as a detector.** Pass the identifiers you already hold for the patient (name, DOB, phone, health card). Exact and one-typo matching against them catches lowercase names, nicknames in context and misspellings that pattern matching misses. On the benchmark below this lifts recall from 61% to 86%.
- **Stable tokens per conversation.** The same value gets the same token on every turn of a session, so the model can follow who is who and provider prompt caching keeps working. Tokens are sequential, not derived from the value (see 45 CFR 164.514(c)).
- **Fail closed.** If masking errors, or a request holds media the policy does not allow, the request is rejected and nothing is sent. Clients cannot switch the guardrail off through request metadata.
- **Clinic-specific identifiers.** Canadian health card numbers (OHIP, RAMQ), SIN, donor and embryo IDs, spoken numbers and dates from call transcripts.
- **Date shifting (optional).** Instead of `[DATE_1]`, move every date in a session by the same random offset. Intervals stay true (retrieval → transfer 5 days later) and the reply is shifted back.
- **Streaming and tool calls.** Tokens split across stream chunks are restored correctly; tool-call arguments are masked going out and restored coming back, so your tools receive real values.

## Quick start: library

```bash
pip install phiproxy                 # library
pip install "phiproxy[litellm]"      # + LiteLLM guardrail
```

```python
from phiproxy import Masker, KnownEntities

masker = Masker()
known = KnownEntities(names=["Sarah Chen"], phones=["416-555-0142"], dates_of_birth=["1990-03-05"])

masked = masker.mask("hi it's sarah, dob march 5 1990", session_id="conv-42", known=known)
masked.text        # 'hi it's [NAME_1], dob [DATE_1]'
masked.summary()   # {'NAME': 1, 'DATE': 1}  - safe to log; masked.entities is not

reply = call_your_llm(masked.text)
masker.unmask(reply, session_id="conv-42")
```

Whole payloads (OpenAI or Anthropic message lists, tool calls, tool results):

```python
safe_messages = masker.mask_payload(messages, session_id="conv-42", known=known)
restored = masker.unmask_payload(response_message, session_id="conv-42")
```

Streaming:

```python
u = masker.stream_unmasker("conv-42")
for chunk in stream:
    print(u.feed(chunk), end="")
print(u.flush())
```

## Quick start: LiteLLM gateway

```yaml
# config.yaml
guardrails:
  - guardrail_name: phiproxy
    litellm_params:
      guardrail: phiproxy.integrations.litellm.PhiproxyGuardrail
      mode: [pre_call, post_call]
      default_on: true
      redis_url: os.environ/PHIPROXY_REDIS_URL   # optional; in-memory if unset

litellm_settings:
  turn_off_message_logging: true   # otherwise LiteLLM logs hold the restored reply
```

Clients pass the conversation id and, optionally, known identifiers in `metadata`:

```python
client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    extra_body={"metadata": {
        "session_id": "conv-42",
        "phiproxy_known": {"names": ["Sarah Chen"], "phones": ["416-555-0142"]},
    }},
)
```

`phiproxy_known` is removed from the request before anything is forwarded. Instead of sending identifiers, you can configure `known_entities_provider: "yourapp.phi:lookup"`, an (async) function that receives `session_id` and `metadata` (e.g. a patient id) and returns them from your own system.

A ready-to-run gateway (LiteLLM + phiproxy + Redis vault) is in [`deploy/`](https://github.com/DecisionTreeTechnology/phiproxy/tree/main/deploy):

```bash
cp deploy/.env.example deploy/.env      # add provider keys
docker compose -f deploy/docker-compose.yml up --build
```

`examples/e2e/run_e2e.py` runs the real LiteLLM proxy against a fake provider that records every request. It checks that the provider received only tokens, that the client got the PHI back (plain and streaming), that images are blocked and that client opt-out is ignored. It runs in CI.

## What it detects

| Type | Examples | Layer |
|---|---|---|
| `NAME` | "this is Maria Lopez", "my husband Dave", any name from your records (any case, one typo) | regex context + known |
| `PHONE` | 416-555-0142, (416) 555 0142, +44 20 7946 0958, "four one six five five five…" | regex + known |
| `EMAIL`, `URL`, `IP_ADDRESS` | | regex |
| `DATE` | 2026-11-03, 11/3, March 5, 1990, Nov 8th, "march fifteenth 1988" (year alone is not masked) | regex + known DOB |
| `AGE` | ages over 89 only (Safe Harbor) | regex |
| `ADDRESS`, `POSTAL_CODE`, `ZIP` | 22 Elm Street apt 4, PO Box 12, M5V 2T6, TX 78701 | regex + known |
| `HEALTH_CARD`, `SIN`, `SSN` | OHIP 1234-567-890-AB, RAMQ, keyword + number, Luhn-checked SIN | regex + known |
| `MRN`, `ACCOUNT`, `DONOR_ID`, `ID` | "MRN: 00482913", "policy number: XK-99812", "donor D-4521" | regex + known |
| `PROVIDER` | "Dr. Patel" (passes by default, as clinician names are not patient identifiers; enable with `Policy(disabled_types=set())`) | regex |

Optional NER layer: `pip install phiproxy[presidio]` and add `PresidioDetector()` to the detector list. It runs in-process; nothing is sent anywhere to detect PHI.

## Benchmark

`benchmark/` holds a synthetic **patient communications** set: SMS, web chat, call transcripts and referral notes, the kind of text clinics actually send to LLMs. Most existing de-identification work targets clinical notes instead. All people and numbers are invented. Run it with `python benchmark/score.py`.

v0 results (288 messages, 560 labelled spans):

| config | recall | missed |
|---|---|---|
| regex | 61.4% | 216 |
| regex + known entities | **85.7%** | 80 |

| recall by channel | regex | regex + known |
|---|---|---|
| SMS | 55% | 95% |
| web chat | 74% | 84% |
| call transcripts | 50% | 80% |
| referral notes | 63% | 79% |

**How to read this honestly:**
- v0 was written by the same team that wrote the detectors. Expect real-world recall to be **lower**. An independent, larger set is the next milestone, and contributions are welcome.
- Precision is reported as 100% on v0, but v0 has almost no non-PHI distractor text, so that number means little yet.
- Known misses today: **cities and workplaces** ("I live in Sudbury", "I work at the Tim Hortons on King") and **names not in your records written in lowercase** ("my husband ravi"). These need the NER layer or a local model, which is on the roadmap.

## Deployment shapes

- **Gateway:** LiteLLM + phiproxy as one container inside your private network, Redis as the shared vault. Apps change only their base URL. This gives one enforcement and audit point.
- **Library:** call `mask` / `unmask` in your own code. It is the smallest footprint, but every code path must remember to call it.
- **Sidecar (planned):** a small HTTP wrapper for apps in other languages (.NET, Java, Node).

The vault holds real values. Protect Redis like the PHI store it is: private network, auth, TLS, short TTL, no persistence.

## Roadmap

- Larger independent benchmark with distractor text, plus multilingual sets (French, Polish, Hebrew, Spanish)
- Local small-model detector for names, places and workplaces
- Gazetteer for cities and regions
- HTTP sidecar; Anthropic `/v1/messages` streaming
- Masked logging hook for LiteLLM

## Contributing and security

See [CONTRIBUTING.md](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/CONTRIBUTING.md) (DCO sign-off required). Report vulnerabilities and detection misses that could leak PHI privately, as described in [SECURITY.md](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/SECURITY.md). **Never put real patient data in issues, tests or benchmark files.**

## License

Apache-2.0. Copyright 2026 Decision Tree Technology.

Built by [Decision Tree Technology](https://decisiontree.tech/), the team behind [Fertiligent](https://fertiligent.ai/).
