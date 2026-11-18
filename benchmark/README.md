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
| `patient_comms_blind_v5.jsonl` | 400 (128 with no identifiers) | 1,503 + 218 staff and clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Fable), different brief: a New Jersey clinic with an Ottawa office, conversations with the clinic's AI assistant, names from many backgrounds, modern family structures, US insurance paperwork, personal fundraiser and social pages |
| `patient_comms_blind_v6.jsonl` | 400 (130 with no identifiers) | 1,047 + 247 staff and clinician names | en, fr, es, pl, he, mixed | blind AI author (Claude Opus), different brief: an Arizona clinic with a Winnipeg office, a quarter calls (interpreters, numbers read out and corrected), first names with no cue word, staff handoffs and internal chat, teenagers referred from oncology, cross-border surrogacy and embryo shipping |

**How the blind sets were made.** Each was written by a separate AI agent that had only a brief: the label rules, channels, languages, realistic mess, and a list of things that look like identifiers but are not. It was told not to read the detector code, the tests or the other sets, and it wrote every message from scratch. The v4 to v6 authors also wrote the clinic's own details (`blind/clinic_v4.json` to `blind/clinic_v6.json`) and a 25- or 26-person staff roster (`blind/staff_v4.json` to `blind/staff_v6.json`) before writing any message, as a clinic would configure them. The v6 author wrote small generator scripts with message templates and filled them with different names, numbers and dates, so v6 is less varied than the other sets: 378 of its 400 messages start differently, and 48 messages (12%) are close pairs. The sets are independent of the detector code, but they are AI-written, not written by clinic staff.

**Second annotator.** A third agent, also without access to code or detector output, reviewed each blind set against the written label rules and listed missing and wrong labels (`blind/audit_v1.jsonl` to `blind/audit_v6.jsonl`; 45, 149, 2, 50, 6 and 11 corrections, mostly unlabelled repeat mentions of names, staff names, spoken dates and numbers read back by the agent). `blind/convert.py` applies them. All scores below use the corrected labels.

**Frozen scoring.** Before each blind set was scored, the detectors were committed and not changed: v1 against commit 082c2e1, v2 against ab99dc9, v3 against 1dd13f2, v4 against 1f548b0, v5 against b1e794b, v6 against dc33528 (0.1.0a8). Those first scores are the fair ones (`results_blind_*_frozen.json`). After a set was scored it was used to find and fix gaps, so its later scores are optimistic. Each set is the re-test of the fixes made on the sets before it. v4 was also scored against 5762fb9, a spoken-date change committed before v4 was seen: it caught one more identifier (88.5% instead of 88.4%) and masked two more non-identifiers, so the spoken-date forms fixed from v1 to v3 were not the ones v4 used.

## Results (recall)

First score of the frozen code on each set it had never seen:

| configuration | v1 | v2 | v3 | v4 | v5 | v6 |
|---|---|---|---|---|---|---|
| regex | 36.0% | 57.3% | 58.4% | 66.1% | 73.7% | 80.2% |
| regex + known entities | 54.1% | 80.2% | 68.3% | 73.8% | 80.9% | 88.8% |
| regex + local model | 77.3% | 87.9% | 84.2% | 86.5% | 91.2% | **96.8%** |
| regex + known + local model | 79.2% | 92.3% | 88.1% | 88.4% | 93.1% | **97.5%** |

The current code ("now", optimistic: every set below was used to find gaps):

| configuration | v0 | v1 | v2 | v3 | v4 | v5 | v6 |
|---|---|---|---|---|---|---|---|
| regex | 87.1% | 84.8% | 83.7% | 68.8% | 75.2% | 75.3% | 81.7% |
| regex + known entities | 97.1% | 89.3% | 94.1% | 78.7% | 84.2% | 82.4% | 90.3% |
| regex + local model | 98.6% | 95.2% | 95.8% | 93.0% | 93.7% | 92.8% | 98.1% |
| regex + known + local model | 99.1% | 96.5% | 98.1% | 96.4% | 95.8% | 94.7% | 98.9% |

- "First" is the score of the frozen code on a set it had never seen. "Now" is the current code, after fixes informed by that set, so it is optimistic.
- v3 tested the name rules added after v2 (finding names from self-introductions, relatives, chart labels, sign-offs and signature blocks, without a model). On v3, before those rules, the pattern detector found 8% of names and 43.1% of all identifiers; with them, 43% of names and 58.4% overall, at the same precision. With the local model the gain is smaller (82.1% to 84.2%), because the model already finds most names.
- v0 overstates recall, because it was written by the people who wrote the detectors.
- On v2 the "known entities" rows are optimistic: for some messages the v2 author filled the patient record from the message itself.
- Spoken identifiers: after the v3 first score, numbers read out loud are rebuilt before matching (grouped and compound number words in five languages, spelled letters, the phonetic alphabet). "Now" recall on call transcripts with the local model rose from 91% to 94% (v1), 88% to 94% (v2) and 94% to 96% (v3); without the model, from 82% to 86%, 79% to 86% and 77% to 80%. False positives did not rise on any set.
- v6 is the fair test of 0.1.0a8 (everything fixed through v5): 97.5% with the local model, 88.8% without it. Read it with care: v6 was built from templates (see above), so it repeats forms and has fewer of the hard cases than v1 to v5, and it is probably easier. By channel: SMS 97%, chat 99%, email 97%, notes 99%, calls 97%. By language: en 98%, fr 97%, es 97%, pl 96%, he 99%, mixed 99%. The 26 misses: claim and account numbers in "29-59296" form and after "numéro de compte" or "número de cuenta" (7), a corrected spoken phone number, Polish nine-digit phones, a Manitoba health number listed second, an SSN given after "my social is", first names with no cue word, "Yuma, AZ" on an address line, Mexican and Polish postal codes, "my mother is 91". v6's main finding is over-masking, below.
- After the v6 first score: account numbers after "numéro de compte", "número de cuenta" and "application reference", an SSN named as such whatever its first digits, Polish nine-digit phones after "numer", the town on a "City, ST 12345" line, Mexican postal codes after "CP", Polish postal codes after the town, ages over 89 after "my mother is". These are "now" numbers.
- v5 is the fair test of everything fixed through v4 (Hebrew, calls, dates; frozen at b1e794b, the detection code of 0.1.0a7): 93.1% with the local model, 80.9% without it. v5's brief was different again (a New Jersey clinic, conversations with the clinic's AI assistant, names from many backgrounds, US insurance paperwork), so part of the change from v4's 88.4% may be the text, not the code. By channel: SMS 95%, chat 93%, email 93%, notes 93%, calls 92%. By language: en 94%, fr 96%, es 90%, pl 93%, he 86%, mixed 94%. Weakest types: personal URLs written without "https://" (43%), member IDs with a three-letter prefix (73%), single first names with no cue word.
- After the v5 first score: member IDs with a three-letter prefix ("BSH9017734412"), personal pages without "https://", IBANs, envelope IDs (UUIDs), "A as in apple" inside spoken codes, "23 de abril del 90", "23 de nov", "abril cuatro del ochenta y seis", Polish years ending in a unit ("osiemdziesiąt dziewięć"). Fewer false positives: amounts read out ("nineteen thousand five hundred", "six hundred twelve dollars") and clock times after a weekday or in a list ("Tuesday eight thirty", "at eight thirty or nine fifteen") are not identifiers; a spoken-year pattern that matched "two thousand" anywhere was fixed; role words ("All Staff", "Lab Director", "madame") are not names.
- v4 is the fair test of everything fixed on v1 to v3: 88.4% with the local model, the same as v3's first score (88.1%), while v1 to v3 "now" scored 95% to 97% at that commit. Fixing gaps found on a set lifts that set much more than unseen text, so expect about 88% on new text of this kind, not 95%.
- v4 first score with the local model, by channel: chat 92%, SMS 92%, email 91%, notes 87%, calls 83%. By language: en 89%, fr 83%, es 91%, pl 89%, he 80%, mixed 98%. Weakest types: dates (74%, mostly bare days and months like "the twelfth", "until January"), health card and member numbers (67%, many scanned with O for 0 and l for 1), SSNs (40%, French and spoken).
- After the v4 first score: scanned numbers are read again with look-alike letters as digits ("6O4-555-Ol74", "O9/Ol/199O"); spelled names with "as in" ("K as in kilo O W..."); spoken emails with numbers; Mexican CURP and RFC, Spanish DNI and NIE, French social security numbers, French phone numbers, IPv6; Polish and French postal codes; streets named first ("88 rue des Érables", "ul. Kościuszki 12/4", "רחוב הרצל 14") and the city after a street; Hebrew calendar dates ("כ״ג בחשוון"); follicle sizes read out are no longer IDs; fertility drug names and role words are no longer names. These are "now" numbers.
- Hebrew, after the v4 first score: the patient-record matcher now reads Hebrew words (it read Latin letters only), with one-letter prefixes kept outside the mask ("ולנועה"), matches common Israeli names across scripts (a record "Noa Ben-Ami" matches "נועה" in the message, and the reverse), and Hebrew and Polish letters no longer split words ("Michał"). Cities written in Hebrew (Israeli cities and the cities patients move to, "טורונטו") are found. Hebrew "now" recall with the local model: v3 88% to 96%, v4 86% to 94%; without the model, v3 55% to 71%, v4 58% to 85%. Optimistic, like all "now" numbers.
- Calls, after the v4 first score: callers give numbers in pieces with fillers and corrections ("six oh four five five five sorry five five five ...", "oh seven... oh seven fourteen?"), so each piece is too short to have an identifier's shape. When the other side asked for one in the last three lines ("date of birth?", "callback number?", "postal code?", "Rx number", in five languages), spoken pieces of three or more digits in the answer are masked as what was asked; times ("at seven fifteen") and a year alone are not. A spoken day of the month on its own is a date when no noun follows ("on the eighteenth with Doctor Bhatt", "Twenty-sixth please"). v4 call recall "now": 86% to 96% with the local model, 79% to 88% without. v1 to v3 calls did not change (their remaining misses are names and workplaces).
- Dates, after the calls round: the first day in a list before a month ("18 y 20 de noviembre", "18 i 20 listopada", "ב-18 וב-20 בנובמבר"), spaced dates from scanned forms ("1985 / 06 / 22"), a two-digit year after a French, Spanish or Polish month ("21 décembre 85"), "the 3rd day of September", and a month alone after "in", "since", "until" ("moved to Burnaby in March", "en janvier", "w lipcu", "באוגוסט"). A day said alone now masks "the" with it ("the eighteenth"). The cost: holiday closures written as a list ("24 y 25 de diciembre") are masked whole, as other holiday dates already were.
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
| v4 now, clinic details and staff list | 83.4% | 39% |
| v5 first score, default policy | 79.4% | 48% |
| v5 first score, clinic details allowed | 85.8% | 27% |
| v5 first score, clinic details and staff list | 87.6% | 27% |
| v5 now, clinic details and staff list | 88.8% | 22% |
| v6 first score, default policy | 64.4% | 68% |
| v6 first score, clinic details allowed | 74.4% | 56% |
| v6 first score, clinic details and staff list | 77.4% | 55% |
| v6 now, clinic details and staff list | 85.8% | 34% |

v2 and v3 contain many email footers and letterheads with the fictional clinic's own name, phone, fax, address and email. Those are not patient data, so they are not labelled, and phiproxy masks them unless the deployment lists them in `Policy(allow=[...])`. The "clinic details allowed" rows pass `blind/clinic_v2.json` or `blind/clinic_v3.json` with `--allow`. Most of the rest is holiday and clinic-closure dates (masked on purpose: a date is never exempted, because it could be a birthday), staff first names that are also words ("Will", "Grace", "Hope"), staff names without a title, and card last-four digits the label rules did not ask for.

After the v3 first score, the local model's guesses were filtered further: speaker labels and role words in French, Spanish, Polish and Hebrew ("Appelante", "Persona que llama", "Estimados pacientes") are dropped; a person with a clinician title or credential ("dr Wójcik", "Panie doktorze Okafor", "Rohan Iyer, MD", "N. Haddad RN") is treated as a clinician and passes like other clinician names; phone extensions, rooms and lot numbers are no longer places. On v3 this removed a third of the false positives (123 to 84 with clinic details allowed), and recall did not change on any set. These are "now" numbers, measured on the sets used to find the problems.

v4 over-masks more than v3 because its brief asked for it: staff first names that are ordinary words (Hope, Will, Grace, Rose, Sky, Amber, Patience), internal staff notes, and patients who share a staff member's name. The record matcher masks the patient's own name wherever it appears, including when a staff member has the same first name ("this is Rose, I'm calling for Rose"). v4's clinic list includes "Vancouver", the clinic's city, so with clinic details allowed a patient who lives in Vancouver is not masked; the rules-only recall drops by one identifier (78.5% to 78.4%).

After the v4 first score, the staff list also passes a staff member's initial and surname ("C. Nakamura", "Okafor, G", "Carmen R."), ignores accents ("Félix" for Felix) and Polish honorifics ("Pani Hannah"), and takes more cues ("Will is covering my retrievals", "Lior cubre la vitrificación", "two voicemails with Chris", "transmettre à Patience", "Joy in ultrasound"). The clinic's own details pass in scanned form too ("Cedar Coast Fert1lity", "613-555-O188"), and a street and city that are each allowed pass together.

v6 over-masked most of all, again because of its brief: staff talking about staff ("Attendees: Okafor, Wrobel, Odette", "Staff chat. Priya: did you call..."), patients thanking staff by first name, and footers with both clinic addresses. Of 282 false positives with clinic details and staff list, 113 were staff names with no cue, about 33 were chat speaker labels the model took for names ("Client:", "Usuario:", "עוזר:"), about 30 were the clinic's own address with the state or province code between allowed pieces ("..., Phoenix AZ 85018"), and 12 were ticket, lot and interpreter numbers. After the v6 first score:

- the staff list also passes a staff name in a list after "Attendees:", "Speakers:", "On call:"; a staff name joined by "and" or a comma to a clinician or a staff name that passes ("Dr. Castellanos and Darnell", "Okafor, Wrobel, Odette"); a staff name followed by the clinic or a health organisation ("it's Brittany at Saguaro Fertility"); a speaker in a message headed as staff chat; and a staff name shown with an allowed clinic email address ("From: Gordon Tran <gordon.tran@clinic...>"). A name right after a relative word ("my sister Grace") never passes on a cue;
- a state or province code, the country or a phone extension between allowed pieces of the clinic's address or phone is allowed with them; an allowed city alone does not cover "Vancouver WA";
- numbers right after "ticket", "lot", "batch", "routing", "badge" or an interpreter are not identifiers. Appointment confirmation numbers stay masked (v1 labels them);
- chat speaker labels and role words ("Client", "Usuario", "Utilisateur", "עוזר", "משתמש", "interpreter", "courier", "Prior Auth Dept", "el abogado") are not names.

On v6 this took false positives from 282 to 162 and clean messages masked from 55% to 34%, with recall unchanged by these filters. On v1 to v5 no labelled identifier was lost (each set was re-scored against the frozen 0.1.0a8 code), and precision rose slightly on v1, v2, v3 and v5. The remaining v6 over-masking is mostly staff first names with no cue at all ("Thank you Priya!!", "Can Solheim text me the zoom link?"), the clinic's addresses given by the model in pieces, and holiday dates.

**Staff list.** `Policy(staff=[...])` passes the clinic's staff names: a full name anywhere, a first name or surname alone only next to a staff cue ("Jocelyn in billing", "AGENT: Billing, this is Jon", "call Hsu at ext. 2240", "Sig: T. Kowalski, M. Reyes"). The v2 and v3 authors were not asked for a staff roster, so `blind/staff_v2.json` and `blind/staff_v3.json` were compiled by reading each set for the people who work at the clinic, the way a clinic knows its own staff; surnames the sets never mention were made up. With them, false positives fell from 145 to 122 on v2 and from 84 to 66 on v3, and recall did not change: no labelled patient name passed, including v3's patient Sunny Dhillon, who shares a first name with a staff member. Staff named with no cue ("Faith and Hope are both out Friday", "- Dawn" at the end of a note) stay masked, because the same words in a patient's message would be a relative or the patient.

## Files

- `generate.py`: deterministic generator (fixed seed) for `data/patient_comms_v0.jsonl`.
- `blind/blind_v*.source.jsonl`: the blind sets as written, with inline labels (`[[NAME|jess]]`). `blind/audit_v*.jsonl`: second-annotator corrections. `blind/clinic_v*.json` and `blind/staff_v*.json`: clinic details and staff rosters for `--allow` and `--staff`. `blind/convert.py v1|...|v6` builds `data/patient_comms_blind_v*.jsonl`.
- `score.py`: scores every available configuration and prints recall by type, channel and language, precision, and clean-message masking. `--show-misses N`, `--show-false-positives N`, `--allow clinic.json` and `--staff staff.json` help with error analysis. The local-model configurations appear when `phiproxy[gliner]` is installed.
- `results_*.json`: scores for the built-in configurations (v2 to v6 with the clinic details allowed; the frozen first scores with the default policy).

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
- Call transcripts were the weakest channel (86% on v3's first score, 83% on v4's, then 92% on v5's and 97% on v6's): names and numbers spoken in fragments and corrected mid-number, voice-to-text errors ("pre may" for Priya, "for one six" for 416). Faxed notes were 84% on v3's first score and 87% on v4's.
- Hebrew was the weakest language (77% on v3's first score, 80% on v4's, 86% on v5's; 99% on v6's, which has 25 Hebrew messages).
- Staff named with no cue at all ("Thank you Priya!!") stay masked, so internal staff traffic over-masks even with the staff list.
- Bare days and months tied to a patient ("the twelfth", "until January") are often missed: a bare month is too ambiguous to mask everywhere.
- Still missed without the local model: names with no cue word ("Can Omar come in with me?"), lowercase names that are also words ("joy", "will"). Also missed: workplaces described in a phrase, Hebrew abbreviations of months.
- Over-masking costs answer quality, not privacy, but it is real: see the table above.

Contributions are welcome, especially messages written by people who work in clinics (see ../CONTRIBUTING.md). All data must be synthetic.
