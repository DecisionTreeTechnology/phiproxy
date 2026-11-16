"""Generate the synthetic patient-communications PHI set (deterministic).

Every person, number and address here is invented: names are random first/last
combinations, phone numbers use the reserved 555-01xx range, emails use
example.com/.org. Templates are written to resemble real clinic traffic
(SMS, web chat, call transcripts, referral notes), including the hard cases
that pattern matching misses, so the scores are honest.

    python benchmark/generate.py            # writes benchmark/data/patient_comms_v0.jsonl
"""

from __future__ import annotations

import json
import random
import re
from datetime import date, timedelta
from pathlib import Path

SEED = 20261116
OUT = Path(__file__).parent / "data" / "patient_comms_v0.jsonl"

FIRST = ["Sarah", "Priya", "Maria", "Aisha", "Mei", "Olivia", "Fatima", "Hannah", "Nadia", "Chloe",
         "Grace", "Leila", "Sofia", "Zara", "Emily", "Jessica", "Ana", "Hope", "Ewa", "Noa"]
PARTNER = ["Dave", "Marcus", "Jamal", "Wei", "Tom", "Ravi", "Luis", "Alex", "Sam", "Jordan", "Piotr", "Avi"]
LAST = ["Chen", "Natarajan", "Lopez", "Okafor", "Kowalski", "Haddad", "Nguyen", "Fischer", "Rossi",
        "Cohen", "Singh", "Martin", "Tremblay", "Ahmed", "Novak", "Silva", "Brennan", "Dubois"]
CITIES = ["Toronto", "Sudbury", "Mississauga", "Ottawa", "Hamilton", "Brampton", "Thunder Bay", "Kingston"]
STREETS = ["Maple Grove Rd", "Elm Street", "Birchmount Ave", "Lakeshore Blvd", "Cedar Lane", "Queen Street"]
EMPLOYERS = ["the Tim Hortons on King", "Sudbury General", "the Loblaws downtown", "Northern Hydro"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

# {slot:TYPE} marks a labelled span. Slot names map to generated values below.
TEMPLATES: list[tuple[str, str]] = [
    # --- SMS
    ("sms", "Hi it's {first:NAME}, can I move my bloodwork to {appt:DATE}? My cell is {phone:PHONE}"),
    ("sms", "this is {first_lc:NAME} {last_lc:NAME} my dob is {dob_slash:DATE} pls call back"),
    ("sms", "Hello, {first:NAME} {last:NAME} here. Day 1 started today, CD3 bloodwork on {appt:DATE}?"),
    ("sms", "Can you send the consent forms to {email:EMAIL}? thanks {first:NAME}"),
    ("sms", "my husband {partner:NAME} will drop off the sample at 8"),
    ("sms", "Running late for my {appt_time} appt, {first:NAME} {last:NAME}"),
    ("sms", "Stop texting {phone_alt:PHONE}, use my work number instead"),
    ("sms", "{first:NAME}'s OHIP is {hc:HEALTH_CARD}, she forgot her card"),
    ("sms", "yes I confirm. {first_typo:NAME} {last:NAME}, DOB {dob_text:DATE}"),
    ("sms", "Is donor {donor:DONOR_ID} still available? We picked them last cycle"),
    ("sms", "I'm at {employer:ADDRESS} until 5, call after"),
    ("sms", "Hope you're well! Quick q about the trigger shot"),  # no PHI ("Hope" is not a name here)
    ("sms", "may I come in on day 3 instead"),  # no PHI
    # --- web chat
    ("chat", "My name is {first:NAME} {last:NAME}, I'm {age} and we've been trying for 2 years."),
    ("chat", "We moved to {street_addr:ADDRESS}, {city:ADDRESS} {postal:POSTAL_CODE} - please update my file"),
    ("chat", "Retrieval was {retrieval:DATE} and they said transfer 5 days later, is that {transfer:DATE}?"),
    ("chat", "my partner {partner:NAME} {last:NAME} needs his semen analysis results"),
    ("chat", "Insurance policy number: {policy:ACCOUNT}, member is my wife {first:NAME}"),
    ("chat", "Chart # {mrn:MRN}, I'm following up on my FET"),
    ("chat", "You can reach my mom {first2:NAME} at {phone_alt:PHONE} if I don't answer"),
    ("chat", "I live in {city:ADDRESS} so a virtual visit would be easier"),
    ("chat", "I work at {employer:ADDRESS} nights, can the scan be after 9am?"),
    ("chat", "What does AMH 1.2 mean for someone my age?"),  # no PHI
    ("chat", "Bonjour, je m'appelle {first:NAME} {last:NAME}, mon numéro est {phone:PHONE}"),
    # --- call transcripts (ASR: lowercase, no punctuation, spelled numbers, mishearing)
    ("call", "hi yeah this is {first_lc:NAME} um {last_lc:NAME} calling about my results"),
    ("call", "my number is {phone_words:PHONE}"),
    ("call", "date of birth {dob_words:DATE}"),
    ("call", "its {first_lc:NAME} again my husband {partner_lc:NAME} said you called"),
    ("call", "the health card is {hc_spaced:HEALTH_CARD}"),
    ("call", "we live on {street_lc:ADDRESS} in {city_lc:ADDRESS}"),
    ("call", "can you call me back at {phone:PHONE} thanks"),
    # --- referral notes / staff notes
    ("note", "Referral: {first:NAME} {last:NAME}, DOB {dob_iso:DATE}, OHIP {hc:HEALTH_CARD}. 2y infertility, AMH low."),
    ("note", "Pt {last:NAME}, {first:NAME} (MRN {mrn:MRN}) seen {appt:DATE}. Partner {partner:NAME} present."),
    ("note", "Patient reached at {phone:PHONE}; prefers email {email:EMAIL}. Address {street_addr:ADDRESS}, {city:ADDRESS}."),
    ("note", "Donor egg cycle, donor ID {donor:DONOR_ID}, ER {retrieval:DATE}, ET planned {transfer:DATE}."),
    ("note", "{old_age:AGE} grandmother {first2:NAME} {last2:NAME} accompanied patient"),
]


def _rand_date(rng: random.Random, start: date, span_days: int) -> date:
    return start + timedelta(days=rng.randrange(span_days))


def _phone(rng: random.Random) -> str:
    area = rng.choice(["416", "647", "705", "905", "613"])
    return f"{area}-555-01{rng.randrange(100):02d}"


def _luhn_ohip(rng: random.Random) -> str:
    d = "".join(str(rng.randrange(10)) for _ in range(10))
    return f"{d[:4]}-{d[4:7]}-{d[7:]}-{rng.choice(['AB', 'XK', 'MN', 'TZ'])}"


def _ordinal_words(n: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh",
             8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth",
             14: "fourteenth", 15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth",
             19: "nineteenth", 20: "twentieth", 21: "twenty first", 22: "twenty second",
             23: "twenty third", 24: "twenty fourth", 25: "twenty fifth", 26: "twenty sixth",
             27: "twenty seventh", 28: "twenty eighth", 29: "twenty ninth", 30: "thirtieth",
             31: "thirty first"}
    return words[n]


def _typo(rng: random.Random, name: str) -> str:
    if len(name) < 5:
        return name
    i = rng.randrange(1, len(name) - 1)
    return name[:i] + name[i + 1 :]  # drop one letter


def person(rng: random.Random) -> dict:
    first, last = rng.choice(FIRST), rng.choice(LAST)
    dob = _rand_date(rng, date(1982, 1, 1), 365 * 18)
    phone = _phone(rng)
    hc = _luhn_ohip(rng)
    appt = _rand_date(rng, date(2026, 9, 1), 120)
    retrieval = _rand_date(rng, date(2026, 9, 1), 120)
    city = rng.choice(CITIES)
    street = f"{rng.randrange(1, 999)} {rng.choice(STREETS)}"
    partner = rng.choice(PARTNER)
    return {
        "first": first, "last": last, "first_lc": first.lower(), "last_lc": last.lower(),
        "first_typo": _typo(rng, first),
        "first2": rng.choice(FIRST), "last2": rng.choice(LAST),
        "partner": partner, "partner_lc": partner.lower(),
        "phone": phone, "phone_alt": _phone(rng),
        "phone_words": " ".join(DIGIT_WORDS[int(c)] for c in re.sub(r"\D", "", phone)),
        "email": f"{first.lower()}.{last.lower()}{rng.randrange(10, 99)}@example.com",
        "dob": dob,
        "dob_slash": f"{dob.month}/{dob.day}/{dob.year}",
        "dob_iso": dob.isoformat(),
        "dob_text": f"{MONTHS[dob.month - 1]} {dob.day}, {dob.year}",
        "dob_words": f"{MONTHS[dob.month - 1].lower()} {_ordinal_words(dob.day)} {dob.year}",
        "appt": f"{MONTHS[appt.month - 1][:3]} {appt.day}",
        "appt_time": rng.choice(["9:30", "10am", "2pm"]),
        "retrieval": f"{retrieval.month}/{retrieval.day}",
        "transfer": f"{(retrieval + timedelta(days=5)).month}/{(retrieval + timedelta(days=5)).day}",
        "hc": hc, "hc_spaced": " ".join(re.sub(r"\D", "", hc)),
        "mrn": f"{rng.choice(['A', 'F', ''])}{rng.randrange(100000, 999999)}",
        "donor": f"D-{rng.randrange(1000, 9999)}",
        "policy": f"{rng.choice(['XK', 'GS', 'MB'])}-{rng.randrange(10000, 99999)}",
        "city": city, "city_lc": city.lower(),
        "street_addr": street, "street_lc": street.lower(),
        "postal": f"{rng.choice('MKLNP')}{rng.randrange(10)}{rng.choice('ABCEGHJ')} "
                  f"{rng.randrange(10)}{rng.choice('KLMNPR')}{rng.randrange(10)}",
        "employer": rng.choice(EMPLOYERS),
        "age": rng.choice(["34", "38", "41", "29"]),
        "old_age": rng.choice(["92 y/o", "91-year-old", "94 yrs"]),
    }


SLOT = re.compile(r"\{(\w+)(?::(\w+))?\}")


def render(template: str, p: dict) -> tuple[str, list[dict]]:
    out, spans, pos = [], [], 0
    length = 0
    for m in SLOT.finditer(template):
        lit = template[pos : m.start()]
        out.append(lit)
        length += len(lit)
        value = str(p[m.group(1)])
        if m.group(2):
            spans.append({"start": length, "end": length + len(value), "type": m.group(2)})
        out.append(value)
        length += len(value)
        pos = m.end()
    out.append(template[pos:])
    return "".join(out), spans


def main(n_per_template: int = 8) -> None:
    rng = random.Random(SEED)
    rows = []
    for t_idx, (channel, template) in enumerate(TEMPLATES):
        for k in range(n_per_template):
            p = person(rng)
            text, spans = render(template, p)
            rows.append({
                "id": f"{channel}-{t_idx:02d}-{k}",
                "channel": channel,
                "text": text,
                "spans": spans,
                # What the clinic system would already know about the patient.
                "known": {
                    "names": [f"{p['first']} {p['last']}"],
                    "phones": [p["phone"]],
                    "emails": [p["email"]],
                    "dates_of_birth": [p["dob"].isoformat()],
                    "identifiers": [p["hc"], p["mrn"]],
                },
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} samples, {sum(len(r['spans']) for r in rows)} labelled spans -> {OUT}")


if __name__ == "__main__":
    main()
