# Patient-communications PHI benchmark

Labelled sets of the kind of text clinics send to LLMs: patient SMS, web chat, phone-call transcripts, emails and referral or staff notes. Most open de-identification datasets cover clinical notes; these cover patient communications. Every person and number in them is invented.

## The two sets

| set | messages | labelled identifiers | languages | written by |
|---|---|---|---|---|
| `patient_comms_v0.jsonl` | 288 | 560 | English (one French template) | generated from templates by the detector authors |
| `patient_comms_blind_v1.jsonl` | 420 (129 with no identifiers) | 664 + 57 clinician names | en 260, fr 50, es 40, pl 30, he 20, mixed 20 | written blind, see below |

**How v1 was written.** v1 was written by a separate AI agent (Claude) that was given only a brief: the label rules, the channels, the languages, realistic mess (typos, lowercase names, spoken numbers, spelled-out names) and a list of things that look like identifiers but are not (drug doses, embryo grades, cycle days, billing codes). It was told not to read the detector code, the tests or v0, and it wrote every message from scratch. So v1 is independent of the detector code, but it is not independent of AI-written text. A set written by clinic staff is still the goal.

**How v1 was scored.** The local-model detector was tuned on v0 only. Its settings were committed (082c2e1) and v1 was then scored once. Those first scores are kept in `results_blind_v1_frozen.json`. After that, v1 was used to find and fix gaps, so the current v1 numbers are optimistic in the same way v0's always were. The next blind set will re-test them.

| recall | v0 (current) | v1 first blind score | v1 after fixes from v1 |
|---|---|---|---|
| regex | 61.4% | 36.6% | 50.5% |
| regex + known entities | 85.7% | 54.4% | 67.8% |
| regex + local model | 98.2% | 78.2% | 89.9% |
| regex + known + local model | 99.1% | 80.1% | 92.2% |

The 30-point gap between v0 and v1 is the honest lesson: a set written by the people who wrote the detectors flatters them.

## Files

- `generate.py`: deterministic generator (fixed seed). It writes `data/patient_comms_v0.jsonl`.
- `blind/blind_v1.source.jsonl`: v1 as written, with inline labels (`[[NAME|jess]]`). `blind/convert.py` turns it into `data/patient_comms_blind_v1.jsonl`.
- `score.py`: scores every available detector configuration and prints recall by type, channel and language. The local-model configurations appear when `phiproxy[gliner]` is installed.
- `results_v0.json`, `results_blind_v1.json`, `results_blind_v1_frozen.json`: scores for the built-in configurations.

Run `python benchmark/score.py` for v0 and `python benchmark/score.py --data benchmark/data/patient_comms_blind_v1.jsonl` for v1.

## Record format

```json
{
  "id": "sms-00-3",
  "channel": "sms",
  "text": "Hi it's Priya, can I move my bloodwork to Oct 3? My cell is 647-555-0112",
  "spans": [{"start": 8, "end": 13, "type": "NAME"}, ...],
  "known": {"names": ["Priya Natarajan"], "phones": ["647-555-0112"], ...}
}
```

`known` is what the clinic system would already hold about the patient. It lets the benchmark measure the known-entity layer.

## Scoring rules

- A labelled span is **caught** when detected spans cover at least 80% of its characters. The detected type does not have to match, because catching a phone number as an `ID` still protects it.
- Scoring uses the default policy, under which clinician names pass through. Clinician names (`PROVIDER`) are therefore not counted in recall, and masking one counts as a false positive.
- A detected span is **correct** when it overlaps a labelled identifier. **Clean messages masked** is the share of messages without identifiers in which something was masked anyway.
- What counts as an identifier follows HIPAA Safe Harbor (45 CFR 164.514(b)(2)): names of patients and relatives, all date elements except year, ages over 89, geographic units smaller than a state or province (street, city, postal code), contact details, and record, account, plan and other identifying numbers. Workplaces are labelled too because they can identify a person.

## Known limits

- v0 is template-based and was written by the detector authors, so its scores are optimistic.
- v1 is AI-written. Real messages are messier still, and the labels have a few judgment calls: the author labelled some weekdays ("Sunday") and "yesterday" as dates, left some cities unlabelled, mostly where they are the clinic's location ("are you a clinic in Hamilton or only Toronto?"), left clinic holiday dates unlabelled, and did not label a few spelled-out names. These are left as written.
- Still missed on v1: dates spoken in words in French, Spanish, Polish and Hebrew, some cities the model does not know ("Hamilton", "kitchener"), workplaces described in a phrase ("the canada post depot on lakeshore"), and lowercase names that are also words ("joy", "will").
- With the local model, something is masked in 19% of messages that contain no identifiers (drug names such as Gonal-f, staff first names, holidays, phone extensions, and role words such as "Paciente"). That costs answer quality, not privacy.

Contributions are welcome, especially messages written by people who work in clinics (see ../CONTRIBUTING.md). All data must be synthetic.
