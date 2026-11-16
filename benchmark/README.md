# Patient-communications PHI benchmark

A labelled set of the kind of text clinics send to LLMs: patient SMS, web chat, phone-call transcripts and referral or staff notes. Most open de-identification datasets cover clinical notes; this one covers patient communications.

## Files

- `generate.py`: deterministic generator (fixed seed). It writes `data/patient_comms_v0.jsonl`.
- `score.py`: scores any detector configuration and prints recall by type and by channel.
- `results_v0.json`: latest scores for the built-in configurations.

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
- A detected span is **correct** when it overlaps any labelled span.
- What counts as an identifier follows HIPAA Safe Harbor (45 CFR 164.514(b)(2)): names of patients and relatives, all date elements except year, ages over 89, geographic units smaller than a state or province (street, city, postal code), contact details, and record, account, plan and other identifying numbers. Workplaces are labelled too because they can identify a person.

## Limits of v0

- It was written by the same team as the detectors, so scores are optimistic.
- It has few non-PHI distractor texts, so the precision figure is not meaningful yet.
- English only, except for one French template.
- It is template-based. Real messages are messier.

Next: an independent set written by people who did not build the detectors, more distractors, and multilingual messages. Contributions are welcome (see ../CONTRIBUTING.md). All data must be synthetic.
