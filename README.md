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

> **Status: pre-alpha (0.1.0a9).** APIs will change. Do not rely on it as your only control.

## Read this first

- **phiproxy reduces how much PHI reaches an LLM provider. It does not make an unapproved provider compliant.** No detector catches 100% of identifiers; every miss is a disclosure. Send PHI only to providers you have a BAA (HIPAA) or equivalent agreement (e.g. PHIPA agent agreement) with, and use phiproxy as an extra layer on top.
- Audio, images and files cannot be masked as text. phiproxy **blocks** them by default.
- Get privacy or legal review before relying on de-identification for any workload.

## What makes it different

- **Your own records as a detector.** Pass the identifiers you already hold for the patient (name, DOB, phone, health card). Exact and one-typo matching against them catches lowercase names and misspellings that pattern matching misses. On the blind benchmark below this lifts recall from 57% to 80%.
- **Optional local model.** `phiproxy[gliner]` adds a small named-entity model that runs on your own machine and finds names, cities and workplaces that no rule or record covers ("my husband ravi", "I live in Sudbury"). With it, recall on the newest blind set, scored once before any fix, was 93%, at about 50 ms per message on CPU.
- **Your clinic's own details pass.** `Policy(allow=["Harborview Reproductive Centre", "613-555-0100", "@clinic.example.org"])` lets the clinic's name, phone numbers, address and email domain reach the model unmasked, so answers keep them. Anything that matches the patient's own record is still masked.
- **Your staff pass, patients who share their names do not.** `Policy(staff=["Jocelyn Paré", "Will Barnes"])`: a staff member's full name passes anywhere; a first name or surname alone passes only next to a staff cue ("Jocelyn in billing", "AGENT: ... this is Will", "call Hsu at ext. 2240", "Sig: T. Kowalski", "Attendees: Hsu, Reyes", "Dr. Paré and Will", "it's Grace at Harborview Fertility"). "Will is picking me up" stays masked, because a patient's husband can be called Will too.
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
      allow: ["Harborview Reproductive Centre", "613-555-0100", "@harborview.example.org"]
      staff: ["Jocelyn Paré", "Will Barnes"]     # optional; see above

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
| `NAME` | "hi its jess", "me llamo Yolanda Pérez", "Husband Imran", "PATIENT: PARK, Soo-jin", "Thanks so much,\nJess", "Amelia Frost, DOB…", any name from your records (any case, one typo), "Can Omar come in with me?" | regex context + known + local model |
| `PHONE` | 416-555-0142, (416) 555 0142, +44 20 7946 0958, "four one six five five five…" | regex + known |
| `EMAIL`, `URL`, `IP_ADDRESS` | | regex |
| `DATE` | 2026-11-03, 11/3, March 5, 1990, Nov 8th, May 2024, "january ninth eighty five" (year alone is not masked) | regex + known DOB |
| `AGE` | ages over 89 only (Safe Harbor): "93 years old", "i'm ninety one", "who is 94" | regex |
| `ADDRESS`, `POSTAL_CODE`, `ZIP` | 22 Elm Street apt 4, PO Box 12, M5V 2T6, TX 78701, "…Ave Apt 2R Chicago 60647", "I live in Sudbury" | regex + known + local model |
| `HEALTH_CARD`, `SIN`, `SSN` | OHIP 1234-567-890-AB, RAMQ, keyword + number, SIN (Luhn-checked, or any 9 digits after "SIN"/"NAS") | regex + known |
| `MRN`, `ACCOUNT`, `DONOR_ID`, `ID` | "MRN: 00482913", "policy number: XK-99812", "claim 2025-118-440921", "card ending 4417", "donor D-4521", record numbers read out digit by digit | regex + known |
| `PROVIDER` | "Dr. Patel" (passes by default, as clinician names are not patient identifiers; enable with `Policy(disabled_types=set())`) | regex + local model |
| `EMPLOYER` | "I work at the Tim Hortons on Barton" | local model |

Names are found from context in English, French, Spanish, Polish and Hebrew without a model: self-introductions (also lowercase, as in call transcripts), relatives with or without "my", chart labels, sign-offs and signature blocks, email headers, and full names next to a date of birth or chart number. Names with no cue word need the local model or your records. Dates are also matched in French, Spanish, Polish and Hebrew, written or spoken ("le 12 mai 1990", "el catorce de febrero de mil novecientos noventa y uno", "trzeciego lipca", "5 בנובמבר"), and spoken digits in those languages. Numbers read out loud in calls are rebuilt before matching: grouped and compound number words in all five languages ("eight hundred, five five five, oh one four two", "dziewięćset pięć, pięćset pięćdziesiąt pięć..."), spelled letters and the phonetic alphabet ("T three A, four B seven", "november sierra hotel four zero zero..."), so spoken phone numbers, postal codes, health cards, member and donor codes, and street numbers ("eighteen forty two west cermak road") are masked. Canadian and US cities and towns over 15,000 people (from [GeoNames](https://www.geonames.org/), CC BY 4.0) are masked after a location cue ("I live in Sudbury", "j'habite à Laval", "mieszkam w Toronto"); names that are also common words, such as Normal or Mobile, must be capitalized. Code-shaped identifiers without a keyword ("SL-4471920-03", "W123456789", any bare number of 7+ digits) are masked as `ID`.

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

`benchmark/` holds eight synthetic **patient communications** sets: SMS, web chat, call transcripts and voicemails, emails, referral letters, insurance letters and intake text, the kind of text clinics actually send to LLMs. Most existing de-identification work targets clinical notes instead. All people and numbers are invented.

- **v0** (288 messages, English): template-based, written by the detector authors.
- **blind v1 to v7** (420, 400, 360, 400, 400, 400 and 400 messages): English, French, Spanish, Polish, Hebrew and mixed, each written by an AI model (Opus, Sonnet, Fable, then Opus, Fable, Opus and Opus again with new briefs) that never saw the detector code, each with about 30% of messages containing no identifiers but full of lookalikes (drug doses, embryo grades, billing codes). v3 is US-heavy and mentions people without cue words ("Can Omar come in with me?"). v4 comes from a British Columbia clinic with international patients, and has spoken and corrected numbers, scanned faxes, internal staff notes, the clinic's own staff roster, and patients who share a staff member's name. v5 comes from a New Jersey clinic, with conversations with the clinic's AI assistant, names from many backgrounds and US insurance paperwork. v6 comes from an Arizona clinic with a Winnipeg office: a quarter calls, first names with no cue word, staff handoffs and internal chat, cross-border surrogacy; its author generated messages from templates, so it is less varied than the others. v7, written by hand, comes from a Houston clinic with a Montreal office: email threads, intake forms, male factor and LGBTQ+ families, specialty-pharmacy calls. A second annotator, also blind to the code, corrected the labels.

Each blind set was scored once with the detectors frozen, then used to find gaps. So each set's first score is a test of the fixes made on the sets before it:

| recall, first score on unseen text | v1 | v2 | v3 | v4 | v5 | v6 | v7 |
|---|---|---|---|---|---|---|---|
| regex | 36.0% | 57.3% | 58.4% | 66.1% | 73.7% | 80.2% | 75.7% |
| regex + known entities | 54.1% | 80.2% | 68.3% | 73.8% | 80.9% | 88.8% | 84.9% |
| regex + local model | 77.3% | 87.9% | 84.2% | 86.5% | 91.2% | 96.8% | 93.1% |
| regex + known + local model | 79.2% | 92.3% | 88.1% | 88.4% | 93.1% | 97.5% | **94.7%** |

| first score, regex + known + local model | v5 | v6 (template-built) | v7 |
|---|---|---|---|
| by channel | SMS 95%, chat 93%, email 93%, notes 93%, calls 92% | SMS 97%, chat 99%, email 97%, notes 99%, calls 97% | SMS 100%, chat 95%, email 93%, notes 96%, calls 95% |
| by language | en 94%, fr 96%, es 90%, pl 93%, he 86%, mixed 94% | en 98%, fr 97%, es 97%, pl 96%, he 99%, mixed 99% | en 95%, fr 95%, es 94%, pl 95%, he 87%, mixed 100% |
| precision (default / clinic details allowed / plus staff list) | 79.4% / 85.8% / 87.6% | 64.4% / 74.4% / 77.4% | 66.6% / 72.5% / 78.4% |
| messages without identifiers where something was masked | 48% / 27% / 27% | 68% / 56% / 55% | 40% / 34% / 32% |

**How to read this honestly:**
- Expect real traffic to score lower: these sets are AI-written, not written by clinic staff. v0 overstated recall by about 30 points.
- Without the local model, names not in your records are the main gap. On v3, where names often come with no cue, the pattern rules alone found 43% of names.
- After the gaps found on each set were fixed, the current code scores 95% to 99% with the local model on the seven blind sets. Those numbers are optimistic, which is why the table above shows first scores. v4 showed how much: the code that scored 95% to 97% on v1 to v3 scored 88% on v4. After the Hebrew, call and date work, the next unseen set (v5) scored 93%, v6 then scored 97.5%, but it was built from templates and is probably easier; v7, written by hand, scored 94.7%. Each set's brief differs, so expect roughly 90% to 95% on new text of this kind, and less on real traffic.
- Over-masking is real: v6, full of staff talking about staff, had 55% of its clean messages masked with the clinic and staff lists at first; the staff-list cues added after it bring that to 34%. Most of it is the clinic's own contact details (pass them in `Policy(allow=...)`), staff names (pass them in `Policy(staff=...)`), and holiday dates, which stay masked on purpose.
- Details, label rules, the corrections and full tables are in [`benchmark/README.md`](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/benchmark/README.md).

## Deployment shapes

- **Gateway:** LiteLLM + phiproxy as one container inside your private network, Redis as the shared vault. Apps change only their base URL. This gives one enforcement and audit point.
- **Library:** call `mask` / `unmask` in your own code. It is the smallest footprint, but every code path must remember to call it.
- **Sidecar (planned):** a small HTTP wrapper for apps in other languages (.NET, Java, Node).

The vault holds real values. Protect Redis like the PHI store it is: private network, auth, TLS, short TTL, no persistence.

## Roadmap

- A benchmark set written by people who work in clinics
- Better call-transcript handling (fragments, voice-to-text errors)
- Smaller and faster local models (distilled or ONNX)
- HTTP sidecar; Anthropic `/v1/messages` streaming
- Masked logging hook for LiteLLM

## Contributing and security

See [CONTRIBUTING.md](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/CONTRIBUTING.md) (DCO sign-off required). Report vulnerabilities and detection misses that could leak PHI privately, as described in [SECURITY.md](https://github.com/DecisionTreeTechnology/phiproxy/blob/main/SECURITY.md). **Never put real patient data in issues, tests or benchmark files.**

## License

Apache-2.0. Copyright 2026 Decision Tree Technology.

Built by [Decision Tree Technology](https://decisiontree.tech/), the team behind [Fertiligent](https://fertiligent.ai/).
