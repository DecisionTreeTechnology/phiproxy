# Patient-communications PHI benchmark

Labelled sets of the kind of text clinics send to LLMs: patient SMS, web chat, phone-call transcripts and voicemails, emails, referral letters, fax and intake text. Most open de-identification datasets cover clinical notes; these cover patient communications. Every person and number in them is invented.

## The sets

| set | messages | labelled identifiers | languages | written by |
|---|---|---|---|---|
| `patient_comms_v0.jsonl` | 288 | 560 | English | generated from templates by the detector authors |
| `patient_comms_blind_v1.jsonl` | 420 (128 with no identifiers) | 684 + 63 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Opus) |
| `patient_comms_blind_v2.jsonl` | 400 (122 with no identifiers) | 778 + 106 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Sonnet), different brief: more fax, intake, voicemail and email text |
| `patient_comms_blind_v3.jsonl` | 360 (110 with no identifiers) | 956 + 109 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Fable), different brief: US insurance and billing text, forwarded threads, people mentioned without cue words |

**How the blind sets were made.** Each was written by a separate AI agent that had only a brief: the label rules, channels, languages, realistic mess, and a list of things that look like identifiers but are not. It was told not to read the detector code, the tests or the other sets, and it wrote every message from scratch. The sets are independent of the detector code, but they are AI-written, not written by clinic staff.

**Second annotator.** A third agent, also without access to code or detector output, reviewed each blind set against the written label rules and listed missing and wrong labels (`blind/audit_v1.jsonl`, `blind/audit_v2.jsonl`, `blind/audit_v3.jsonl`; 45, 149 and 2 corrections, mostly unlabelled repeat mentions of names, staff names and spoken dates). `blind/convert.py` applies them. All scores below use the corrected labels.

**Frozen scoring.** Before each blind set was scored, the detectors were committed and not changed: v1 against commit 082c2e1, v2 against ab99dc9, v3 against 1dd13f2. Those first scores are the fair ones (`results_blind_*_frozen.json`). After a set was scored it was used to find and fix gaps, so its later scores are optimistic. v2 was the re-test of the fixes made on v1, and v3 the re-test of the fixes made on v1 and v2.

## Results (recall)

| configuration | v0 | v1 first | v2 first | v3 first | v1 now | v2 now | v3 now |
|---|---|---|---|---|---|---|---|
| regex | 84.3% | 36.0% | 57.3% | 58.4% | 80.8% | 77.9% | 65.5% |
| regex + known entities | 94.3% | 54.1% | 80.2% | 68.3% | 85.5% | 88.9% | 74.9% |
| regex + local model | 98.6% | 77.3% | 87.9% | **84.2%** | 93.4% | 92.5% | 91.3% |
| regex + known + local model | 99.1% | 79.2% | 92.3% | **88.1%** | 94.7% | 94.9% | 94.7% |

- "First" is the score of the frozen code on a set it had never seen. "Now" is the current code, after fixes informed by that set, so it is optimistic.
- v3 tested the name rules added after v2 (finding names from self-introductions, relatives, chart labels, sign-offs and signature blocks, without a model). On v3, before those rules, the pattern detector found 8% of names and 43.1% of all identifiers; with them, 43% of names and 58.4% overall, at the same precision. With the local model the gain is smaller (82.1% to 84.2%), because the model already finds most names.
- v0 overstates recall, because it was written by the people who wrote the detectors.
- On v2 the "known entities" rows are optimistic: for some messages the v2 author filled the patient record from the message itself.
- v3 first score with the local model, by channel: chat 93%, SMS 90%, email 89%, calls 86%, notes 84%. By language: en 88%, fr 88%, es 86%, pl 91%, he 77%, mixed 96%. By type, the weakest were account numbers (49%: claim, group and certificate numbers without a colon) and donor and embryo codes (38%). Those were fixed after the first score.

## Results (over-masking)

| regex + known + local model | precision | messages without identifiers where something was masked |
|---|---|---|
| v1 now | 91.5% | 16% |
| v2 now, clinic details allowed | 83.4% | 29% |
| v3 first score, default policy | 82.6% | 31% |
| v3 first score, clinic details allowed | 87.1% | 20% |
| v3 now, default policy | 86.5% | 26% |
| v3 now, clinic details allowed | 91.2% | 15% |

v2 and v3 contain many email footers and letterheads with the fictional clinic's own name, phone, fax, address and email. Those are not patient data, so they are not labelled, and phiproxy masks them unless the deployment lists them in `Policy(allow=[...])`. The "clinic details allowed" rows pass `blind/clinic_v2.json` or `blind/clinic_v3.json` with `--allow`. Most of the rest is holiday and clinic-closure dates (masked on purpose: a date is never exempted, because it could be a birthday), staff first names that are also words ("Will", "Grace", "Hope"), staff names without a title, and card last-four digits the label rules did not ask for.

After the v3 first score, the local model's guesses were filtered further: speaker labels and role words in French, Spanish, Polish and Hebrew ("Appelante", "Persona que llama", "Estimados pacientes") are dropped; a person with a clinician title or credential ("dr Wójcik", "Panie doktorze Okafor", "Rohan Iyer, MD", "N. Haddad RN") is treated as a clinician and passes like other clinician names; phone extensions, rooms and lot numbers are no longer places. On v3 this removed a third of the false positives (123 to 84 with clinic details allowed), and recall did not change on any set. These are "now" numbers, measured on the sets used to find the problems.

## Files

- `generate.py`: deterministic generator (fixed seed) for `data/patient_comms_v0.jsonl`.
- `blind/blind_v*.source.jsonl`: the blind sets as written, with inline labels (`[[NAME|jess]]`). `blind/audit_v*.jsonl`: second-annotator corrections. `blind/convert.py v1|v2|v3` builds `data/patient_comms_blind_v*.jsonl`.
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
- Call transcripts and faxed notes are the weakest channels (86% and 84% on v3's first score): names and numbers spoken in fragments, voice-to-text errors ("pre may" for Priya, "for one six" for 416), OCR errors ("APR1L", "847-555-O163").
- Hebrew is the weakest language (77% on v3's first score).
- Still missed without the local model: names with no cue word ("Can Omar come in with me?"), lowercase names that are also words ("joy", "will"). Also missed: workplaces described in a phrase, Hebrew abbreviations of months.
- Over-masking costs answer quality, not privacy, but it is real: see the table above.

Contributions are welcome, especially messages written by people who work in clinics (see ../CONTRIBUTING.md). All data must be synthetic.
