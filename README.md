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

> **Status: pre-alpha (0.1.0a3).** APIs will change. Do not rely on it as your only control.

## Read this first

- **phiproxy reduces how much PHI reaches an LLM provider. It does not make an unapproved provider compliant.** No detector catches 100% of identifiers; every miss is a disclosure. Send PHI only to providers you have a BAA (HIPAA) or equivalent agreement (e.g. PHIPA agent agreement) with, and use phiproxy as an extra layer on top.
- Audio, images and files cannot be masked as text. phiproxy **blocks** them by default.
- Get privacy or legal review before relying on de-identification for any workload.

## What makes it different

- **Your own records as a detector.** Pass the identifiers you already hold for the patient (name, DOB, phone, health card). Exact and one-typo matching against them catches lowercase names and misspellings that pattern matching misses. On the blind benchmark below this lifts recall from 51% to 68%.
- **Optional local model.** `phiproxy[gliner]` adds a small named-entity model that runs on your own machine and finds names, cities and workplaces that no rule or record covers ("my husband ravi", "I live in Sudbury"). It lifts blind-benchmark recall to 92%, at about 50 ms per message on CPU.
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
| `NAME` | "this is Maria Lopez", "my husband Dave", any name from your records (any case, one typo), "my husband ravi" | regex context + known + local model |
| `PHONE` | 416-555-0142, (416) 555 0142, +44 20 7946 0958, "four one six five five five…" | regex + known |
| `EMAIL`, `URL`, `IP_ADDRESS` | | regex |
| `DATE` | 2026-11-03, 11/3, March 5, 1990, Nov 8th, "march fifteenth 1988" (year alone is not masked) | regex + known DOB |
| `AGE` | ages over 89 only (Safe Harbor) | regex |
| `ADDRESS`, `POSTAL_CODE`, `ZIP` | 22 Elm Street apt 4, PO Box 12, M5V 2T6, TX 78701, "I live in Sudbury" | regex + known + local model |
| `HEALTH_CARD`, `SIN`, `SSN` | OHIP 1234-567-890-AB, RAMQ, keyword + number, Luhn-checked SIN | regex + known |
| `MRN`, `ACCOUNT`, `DONOR_ID`, `ID` | "MRN: 00482913", "policy number: XK-99812", "donor D-4521" | regex + known |
| `PROVIDER` | "Dr. Patel" (passes by default, as clinician names are not patient identifiers; enable with `Policy(disabled_types=set())`) | regex + local model |
| `EMPLOYER` | "I work at the Tim Hortons on Barton" | local model |

Dates are also matched in French, Spanish, Polish and Hebrew ("le 12 mai 1990", "jueves 6 de noviembre", "5 בנובמבר"), and spoken digits in those languages. Code-shaped identifiers without a keyword ("SL-4471920-03", "W123456789", any bare number of 7+ digits) are masked as `ID`.

### Optional local model

```bash
pip install "phiproxy[gliner]"
```

```python
from phiproxy import Masker, RegexDetector
from phiproxy.detectors.gliner import GlinerDetector

masker = Masker(detectors=[RegexDetector(), GlinerDetector()])
```

`GlinerDetector` uses [GLiNER](https://github.com/urchade/GLiNER) with the Apache-2.0 model `urchade/gliner_multi_pii-v1` (about 1.2 GB). It runs in-process: nothing is sent anywhere to detect PHI. The model is downloaded from Hugging Face on first use, so in production download it once and pass its local path as `model=`, or set `HF_HUB_OFFLINE=1`. Model guesses never override the policy: a guess on "Dr. Haddad" does not mask a clinician name that the policy lets through.

Presidio is also supported: `pip install phiproxy[presidio]` and add `PresidioDetector()`.

## Benchmark

`benchmark/` holds two synthetic **patient communications** sets: SMS, web chat, call transcripts, emails and referral notes, the kind of text clinics actually send to LLMs. Most existing de-identification work targets clinical notes instead. All people and numbers are invented.

- **v0** (288 messages, English): template-based, written by the detector authors.
- **blind v1** (420 messages; English, French, Spanish, Polish, Hebrew and mixed; 129 messages with no identifiers but full of lookalikes such as drug doses and embryo grades): written by a separate AI agent that never saw the detector code.

| recall | v0 | blind v1, first score | blind v1, now |
|---|---|---|---|
| regex | 61.4% | 36.6% | 50.5% |
| regex + known entities | 85.7% | 54.4% | 67.8% |
| regex + known + local model | 99.1% | 80.1% | **92.2%** |

| blind v1, regex + known + local model | |
|---|---|
| by channel | SMS 94%, chat 91%, email 96%, notes 94%, call transcripts 86% |
| by language | en 91%, fr 94%, es 93%, pl 95%, he 92%, mixed 97% |
| precision | 86.9% |
| messages without identifiers where something was masked | 19% |

**How to read this honestly:**
- The first blind score is the fair one: the detectors were frozen before v1 was scored. "Now" includes fixes made after looking at v1's misses, so it is optimistic. A new blind set will re-test it.
- v0 overstated recall by about 30 points. Expect real traffic to score lower than v1 too.
- Known misses: dates spoken in words outside English, some cities, workplaces described in a phrase, and lowercase names that are also words ("joy", "will"). Without the local model, cities and names not in your records are mostly missed.
- Details, label rules and the full tables are in [`benchmark/README.md`](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/benchmark/README.md).

## Deployment shapes

- **Gateway:** LiteLLM + phiproxy as one container inside your private network, Redis as the shared vault. Apps change only their base URL. This gives one enforcement and audit point.
- **Library:** call `mask` / `unmask` in your own code. It is the smallest footprint, but every code path must remember to call it.
- **Sidecar (planned):** a small HTTP wrapper for apps in other languages (.NET, Java, Node).

The vault holds real values. Protect Redis like the PHI store it is: private network, auth, TLS, short TTL, no persistence.

## Roadmap

- A benchmark set written by clinic staff, and a second blind AI-written set to re-test the current numbers
- Gazetteer for cities the model misses; spoken dates in French, Spanish, Polish and Hebrew
- Smaller and faster local models (distilled or ONNX)
- HTTP sidecar; Anthropic `/v1/messages` streaming
- Masked logging hook for LiteLLM

## Contributing and security

See [CONTRIBUTING.md](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/CONTRIBUTING.md) (DCO sign-off required). Report vulnerabilities and detection misses that could leak PHI privately, as described in [SECURITY.md](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/SECURITY.md). **Never put real patient data in issues, tests or benchmark files.**

## License

Apache-2.0. Copyright 2026 Decision Tree Technology.

Built by [Decision Tree Technology](https://decisiontree.tech/), the team behind [Fertiligent](https://fertiligent.ai/).
