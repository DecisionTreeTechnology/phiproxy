# Patient-communications PHI benchmark

Labelled sets of the kind of text clinics send to LLMs: patient SMS, web chat, phone-call transcripts and voicemails, emails, referral letters, fax and intake text. Most open de-identification datasets cover clinical notes; these cover patient communications. Every person and number in them is invented.

## The sets

| set | messages | labelled identifiers | languages | written by |
|---|---|---|---|---|
| `patient_comms_v0.jsonl` | 288 | 560 | English | generated from templates by the detector authors |
| `patient_comms_blind_v1.jsonl` | 420 (128 with no identifiers) | 684 + 63 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Opus) |
| `patient_comms_blind_v2.jsonl` | 400 (122 with no identifiers) | 778 + 106 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Sonnet), different brief: more fax, intake, voicemail and email text |
| `patient_comms_blind_v3.jsonl` | 360 (110 with no identifiers) | 956 + 109 clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Fable), different brief: US insurance and billing text, forwarded threads, people mentioned without cue words |
| `patient_comms_blind_v4.jsonl` | 400 (152 with no identifiers) | 1,114 + 332 staff and clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Opus), different brief: a British Columbia clinic with international patients, spoken and corrected numbers in calls, faxed and scanned documents, internal staff notes, patients who share a staff member's name |

**How the blind sets were made.** Each was written by a separate AI agent that had only a brief: the label rules, channels, languages, realistic mess, and a list of things that look like identifiers but are not. It was told not to read the detector code, the tests or the other sets, and it wrote every message from scratch. The v4 author also wrote the clinic's own details (`blind/clinic_v4.json`) and a 26-person staff roster (`blind/staff_v4.json`) before writing any message, as a clinic would configure them. The sets are independent of the detector code, but they are AI-written, not written by clinic staff.

**Second annotator.** A third agent, also without access to code or detector output, reviewed each blind set against the written label rules and listed missing and wrong labels (`blind/audit_v1.jsonl` to `blind/audit_v4.jsonl`; 45, 149, 2 and 50 corrections, mostly unlabelled repeat mentions of names, staff names, spoken dates and numbers read back by the agent). `blind/convert.py` applies them. All scores below use the corrected labels.

**Frozen scoring.** Before each blind set was scored, the detectors were committed and not changed: v1 against commit 082c2e1, v2 against ab99dc9, v3 against 1dd13f2, v4 against 1f548b0. Those first scores are the fair ones (`results_blind_*_frozen.json`). After a set was scored it was used to find and fix gaps, so its later scores are optimistic. Each set is the re-test of the fixes made on the sets before it. v4 was also scored against 5762fb9, a spoken-date change committed before v4 was seen: it caught one more identifier (88.5% instead of 88.4%) and masked two more non-identifiers, so the spoken-date forms fixed from v1 to v3 were not the ones v4 used.

## Results (recall)

| configuration | v0 | v1 first | v2 first | v3 first | v4 first | v1 now | v2 now | v3 now | v4 now |
|---|---|---|---|---|---|---|---|---|---|
| regex | 87.1% | 36.0% | 57.3% | 58.4% | 66.1% | 84.1% | 82.9% | 67.7% | 70.8% |
| regex + known entities | 97.1% | 54.1% | 80.2% | 68.3% | 73.8% | 88.6% | 93.2% | 77.0% | 78.5% |
| regex + local model | 98.6% | 77.3% | 87.9% | 84.2% | **86.5%** | 94.6% | 95.2% | 92.3% | 89.5% |
| regex + known + local model | 99.1% | 79.2% | 92.3% | 88.1% | **88.4%** | 95.9% | 97.6% | 95.6% | 91.4% |

- "First" is the score of the frozen code on a set it had never seen. "Now" is the current code, after fixes informed by that set, so it is optimistic.
- v3 tested the name rules added after v2 (finding names from self-introductions, relatives, chart labels, sign-offs and signature blocks, without a model). On v3, before those rules, the pattern detector found 8% of names and 43.1% of all identifiers; with them, 43% of names and 58.4% overall, at the same precision. With the local model the gain is smaller (82.1% to 84.2%), because the model already finds most names.
- v0 overstates recall, because it was written by the people who wrote the detectors.
- On v2 the "known entities" rows are optimistic: for some messages the v2 author filled the patient record from the message itself.
- Spoken identifiers: after the v3 first score, numbers read out loud are rebuilt before matching (grouped and compound number words in five languages, spelled letters, the phonetic alphabet). "Now" recall on call transcripts with the local model rose from 91% to 94% (v1), 88% to 94% (v2) and 94% to 96% (v3); without the model, from 82% to 86%, 79% to 86% and 77% to 80%. False positives did not rise on any set.
- v4 is the fair test of everything fixed on v1 to v3: 88.4% with the local model, the same as v3's first score (88.1%), while v1 to v3 "now" scored 95% to 97% at that commit. Fixing gaps found on a set lifts that set much more than unseen text, so expect about 88% on new text of this kind, not 95%.
- v4 first score with the local model, by channel: chat 92%, SMS 92%, email 91%, notes 87%, calls 83%. By language: en 89%, fr 83%, es 91%, pl 89%, he 80%, mixed 98%. Weakest types: dates (74%, mostly bare days and months like "the twelfth", "until January"), health card and member numbers (67%, many scanned with O for 0 and l for 1), SSNs (40%, French and spoken).
- After the v4 first score: scanned numbers are read again with look-alike letters as digits ("6O4-555-Ol74", "O9/Ol/199O"); spelled names with "as in" ("K as in kilo O W..."); spoken emails with numbers; Mexican CURP and RFC, Spanish DNI and NIE, French social security numbers, French phone numbers, IPv6; Polish and French postal codes; streets named first ("88 rue des Érables", "ul. Kościuszki 12/4", "רחוב הרצל 14") and the city after a street; Hebrew calendar dates ("כ״ג בחשוון"); follicle sizes read out are no longer IDs; fertility drug names and role words are no longer names. These are "now" numbers.
- v3 first score with the local model, by channel: chat 93%, SMS 90%, email 89%, calls 86%, notes 84%. By language: en 88%, fr 88%, es 86%, pl 91%, he 77%, mixed 96%. By type, the weakest were account numbers (49%: claim, group and certificate numbers without a colon) and donor and embryo codes (38%). Those were fixed after the first score.

## Results (over-masking)

| regex + known + local model | precision | messages without identifiers where something was masked |
|---|---|---|
| v1 now | 91.5% | 16% |
| v2 now, clinic details allowed | 83.6% | 29% |
| v3 first score, default policy | 82.6% | 31% |
| v3 first score, clinic details allowed | 87.1% | 20% |
| v3 now, default policy | 86.5% | 26% |
| v3 now, clinic details allowed | 91.2% | 15% |
| v2 now, clinic details and staff list | 85.9% | 27% |
| v3 now, clinic details and staff list | 93.0% | 15% |
| v4 first score, default policy | 71.9% | 61% |
| v4 first score, clinic details allowed | 74.6% | 54% |
| v4 first score, clinic details and staff list | 78.8% | 48% |
| v4 now, clinic details and staff list | 83.0% | 39% |

v2 and v3 contain many email footers and letterheads with the fictional clinic's own name, phone, fax, address and email. Those are not patient data, so they are not labelled, and phiproxy masks them unless the deployment lists them in `Policy(allow=[...])`. The "clinic details allowed" rows pass `blind/clinic_v2.json` or `blind/clinic_v3.json` with `--allow`. Most of the rest is holiday and clinic-closure dates (masked on purpose: a date is never exempted, because it could be a birthday), staff first names that are also words ("Will", "Grace", "Hope"), staff names without a title, and card last-four digits the label rules did not ask for.

After the v3 first score, the local model's guesses were filtered further: speaker labels and role words in French, Spanish, Polish and Hebrew ("Appelante", "Persona que llama", "Estimados pacientes") are dropped; a person with a clinician title or credential ("dr Wójcik", "Panie doktorze Okafor", "Rohan Iyer, MD", "N. Haddad RN") is treated as a clinician and passes like other clinician names; phone extensions, rooms and lot numbers are no longer places. On v3 this removed a third of the false positives (123 to 84 with clinic details allowed), and recall did not change on any set. These are "now" numbers, measured on the sets used to find the problems.

v4 over-masks more than v3 because its brief asked for it: staff first names that are ordinary words (Hope, Will, Grace, Rose, Sky, Amber, Patience), internal staff notes, and patients who share a staff member's name. The record matcher masks the patient's own name wherever it appears, including when a staff member has the same first name ("this is Rose, I'm calling for Rose"). v4's clinic list includes "Vancouver", the clinic's city, so with clinic details allowed a patient who lives in Vancouver is not masked; the rules-only recall drops by one identifier (78.5% to 78.4%).

After the v4 first score, the staff list also passes a staff member's initial and surname ("C. Nakamura", "Okafor, G", "Carmen R."), ignores accents ("Félix" for Felix) and Polish honorifics ("Pani Hannah"), and takes more cues ("Will is covering my retrievals", "Lior cubre la vitrificación", "two voicemails with Chris", "transmettre à Patience", "Joy in ultrasound"). The clinic's own details pass in scanned form too ("Cedar Coast Fert1lity", "613-555-O188"), and a street and city that are each allowed pass together.

**Staff list.** `Policy(staff=[...])` passes the clinic's staff names: a full name anywhere, a first name or surname alone only next to a staff cue ("Jocelyn in billing", "AGENT: Billing, this is Jon", "call Hsu at ext. 2240", "Sig: T. Kowalski, M. Reyes"). The v2 and v3 authors were not asked for a staff roster, so `blind/staff_v2.json` and `blind/staff_v3.json` were compiled by reading each set for the people who work at the clinic, the way a clinic knows its own staff; surnames the sets never mention were made up. With them, false positives fell from 145 to 122 on v2 and from 84 to 66 on v3, and recall did not change: no labelled patient name passed, including v3's patient Sunny Dhillon, who shares a first name with a staff member. Staff named with no cue ("Faith and Hope are both out Friday", "- Dawn" at the end of a note) stay masked, because the same words in a patient's message would be a relative or the patient.

## Files

- `generate.py`: deterministic generator (fixed seed) for `data/patient_comms_v0.jsonl`.
- `blind/blind_v*.source.jsonl`: the blind sets as written, with inline labels (`[[NAME|jess]]`). `blind/audit_v*.jsonl`: second-annotator corrections. `blind/clinic_v*.json` and `blind/staff_v*.json`: clinic details and staff rosters for `--allow` and `--staff`. `blind/convert.py v1|v2|v3|v4` builds `data/patient_comms_blind_v*.jsonl`.
- `score.py`: scores every available configuration and prints recall by type, channel and language, precision, and clean-message masking. `--show-misses N`, `--show-false-positives N`, `--allow clinic.json` and `--staff staff.json` help with error analysis. The local-model configurations appear when `phiproxy[gliner]` is installed.
- `results_*.json`: scores for the built-in configurations (v2 to v4 with the clinic details allowed; the frozen first scores with the default policy).

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
- Call transcripts are the weakest channel (83% on v4's first score, 86% on v3's): names and numbers spoken in fragments and corrected mid-number, voice-to-text errors ("pre may" for Priya, "for one six" for 416). Faxed notes were 84% on v3's first score and 87% on v4's.
- Hebrew is the weakest language (80% on v4's first score, 77% on v3's), then French (83% on v4).
- Bare days and months tied to a patient ("the twelfth", "until January") are often missed: a bare month is too ambiguous to mask everywhere.
- Still missed without the local model: names with no cue word ("Can Omar come in with me?"), lowercase names that are also words ("joy", "will"). Also missed: workplaces described in a phrase, Hebrew abbreviations of months.
- Over-masking costs answer quality, not privacy, but it is real: see the table above.

Contributions are welcome, especially messages written by people who work in clinics (see ../CONTRIBUTING.md). All data must be synthetic.
