# Patient-communications PHI benchmark

Labelled sets of the kind of text clinics send to LLMs: patient SMS, web chat, phone-call transcripts and voicemails, emails, referral letters, fax and intake text. Most open de-identification datasets cover clinical notes; these cover patient communications. Every person and number in them is invented.

## The sets

| set | messages | labelled identifiers | languages | written by |
|---|---|---|---|---|
| `patient_comms_v0.jsonl` | 288 | 560 | English | generated from templates by the detector authors |
| `patient_comms_blind_v1.jsonl` | 420 (128 with no identifiers) | 684 + 63 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Opus) |
| `patient_comms_blind_v2.jsonl` | 400 (122 with no identifiers) | 778 + 106 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Sonnet), different brief: more fax, intake, voicemail and email text |

**How the blind sets were made.** Each was written by a separate AI agent that had only a brief: the label rules, channels, languages, realistic mess, and a list of things that look like identifiers but are not. It was told not to read the detector code, the tests or the other sets, and it wrote every message from scratch. The sets are independent of the detector code, but they are AI-written, not written by clinic staff.

**Second annotator.** A third agent, also without access to code or detector output, reviewed each blind set against the written label rules and listed missing and wrong labels (`blind/audit_v1.jsonl`, `blind/audit_v2.jsonl`; 45 and 149 corrections, mostly unlabelled repeat mentions of names, staff names and spoken dates). `blind/convert.py` applies them. All scores below use the corrected labels.

**Frozen scoring.** Before each blind set was scored, the detectors were committed and not changed: v1 against commit 082c2e1, v2 against ab99dc9. Those first scores are the fair ones (`results_blind_*_frozen.json`). After a set was scored it was used to find and fix gaps, so its later scores are optimistic. v2 was the re-test of the fixes made on v1.

## Results (recall)

| configuration | v0 | v1 first score | v1 now | v2 first score | v2 now |
|---|---|---|---|---|---|
| regex | 64.3% | 36.0% | 54.4% | 57.3% | 57.3% |
| regex + known entities | 88.6% | 54.1% | 72.1% | 80.2% | 80.2% |
| regex + local model | 98.2% | 77.3% | 90.2% | **87.9%** | 87.9% |
| regex + known + local model | 99.1% | 79.2% | 92.4% | **92.3%** | 92.3% |

- The fixes made on v1 held up on v2: recall with the local model moved from 79% on v1's first score to 92% on v2's first score.
- v0 overstates recall by about 30 points, because it was written by the people who wrote the detectors.
- On v2 the "known entities" rows are optimistic: for some messages the v2 author filled the patient record from the message itself.
- v2 recall with the local model, by channel: SMS 97%, chat 97%, email 98%, notes 95%, calls 83%. By language: en 92%, fr 97%, es 95%, pl 90%, he 85%, mixed 94%.

## Results (over-masking)

| regex + known + local model | precision | messages without identifiers where something was masked |
|---|---|---|
| v1 now | 89.7% | 16% |
| v2 now, default policy | 76.5% | 51% |
| v2 now, clinic details allowed | 80.6% | 35% |

v2 contains many email footers and letterheads with the fictional clinic's own name, phone, fax, address and email. Those are not patient data, so they are not labelled, and phiproxy masks them unless the deployment lists them in `Policy(allow=[...])`. The last row passes the six clinic details in `blind/clinic_v2.json` with `--allow`. Most of the rest is holiday and clinic-closure dates (masked on purpose: a date is never exempted, because it could be a birthday), staff first names that are also words ("Will", "Grace", "Hope"), and staff names without a title.

## Files

- `generate.py`: deterministic generator (fixed seed) for `data/patient_comms_v0.jsonl`.
- `blind/blind_v*.source.jsonl`: the blind sets as written, with inline labels (`[[NAME|jess]]`). `blind/audit_v*.jsonl`: second-annotator corrections. `blind/convert.py v1|v2` builds `data/patient_comms_blind_v*.jsonl`.
- `score.py`: scores every available configuration and prints recall by type, channel and language, precision, and clean-message masking. `--show-misses N`, `--show-false-positives N` and `--allow clinic.json` help with error analysis. The local-model configurations appear when `phiproxy[gliner]` is installed.
- `results_*.json`: scores for the built-in configurations.

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

- The blind sets are AI-written. Real messages are messier, and a set written by people who work in clinics is still the goal.
- Call transcripts are the weakest channel (83% on v2): names and numbers spoken in fragments, voice-to-text errors ("for one six" for 416), and repeated spellings.
- Still missed: some lowercase names that are also words ("joy", "will"), workplaces described in a phrase, Hebrew abbreviations of months, numeric spoken dates ("oh four oh nine eighty two").
- Over-masking costs answer quality, not privacy, but it is real: see the table above.

Contributions are welcome, especially messages written by people who work in clinics (see ../CONTRIBUTING.md). All data must be synthetic.
