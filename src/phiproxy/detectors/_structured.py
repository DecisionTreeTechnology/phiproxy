"""Identifiers in machine-shaped text: JSON fields, ``key: value`` dumps, CSV rows and HL7 v2 segments.

Field names say what a value is ("last_name", "zip", "tz", "Carte santé"), so these
values are found by their column or key, not by their shape. Only names on the
lists below count; an unknown key or column is left to the other rules. Each value
must still look like what its key says (a name, a phone number, a code), so
"Phone: press 1" or "Last name: TBD" are not masked.
"""

from __future__ import annotations

import json
import re
import unicodedata

from ..entities import EntityType
from ._names import STOP_WORDS

_T = EntityType


def _norm(key: str) -> str:
    key = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", key.strip().strip("\"'"))  # "patientName" -> "patient_Name"
    key = unicodedata.normalize("NFKD", key.lower())
    key = "".join(c for c in key if not unicodedata.combining(c))
    return re.sub(r"[\s\-./]+", "_", key).strip("_")


def _keys(words: str) -> set[str]:
    return {_norm(k) for k in words.split()}


_FIELDS: dict[str, EntityType] = {}
for _type, _words in {
    _T.NAME: (
        "first_name firstname fname given_name givenname last_name lastname lname surname family_name familyname "
        "middle_name middlename full_name fullname patient_name legal_name preferred_name nickname partner_name "
        "spouse_name emergency_contact guarantor_name subscriber_name insured_name nombre apellido apellidos "
        "nombre_completo prenom nom_de_famille imie nazwisko שם_פרטי שם_משפחה nom_complet nom_et_prenom "
        "nombre_y_apellidos name_on_card cardholder cardholder_name card_holder imie_i_nazwisko שם_מלא "
        # Ambiguous alone: they count only next to another personal field (see _WEAK).
        "first last given middle name nom patient שם"
    ),
    _T.DATE: (
        "dob date_of_birth birth_date birthdate birthday fecha_de_nacimiento fecha_nacimiento date_de_naissance "
        "date_naissance ddn data_urodzenia תאריך_לידה"
    ),
    _T.PHONE: (
        "phone phone_number phonenumber mobile mobile_phone cell cell_phone cellphone tel telephone home_phone "
        "work_phone telefono telefon numer_telefonu טלפון נייד"
    ),
    _T.EMAIL: "email e_mail email_address correo courriel",
    _T.ADDRESS: (
        "address address1 address_1 address_line_1 address_line1 street street_address city town direccion "
        "ciudad adresse ville adres miasto ulica כתובת עיר"
    ),
    _T.ZIP: "zip zipcode zip_code",
    _T.POSTAL_CODE: "postal postal_code postalcode postcode code_postal codigo_postal kod_pocztowy מיקוד",
    _T.SSN: "ssn social_security",
    _T.SIN: "sin nas",
    _T.MRN: "mrn chart_number patient_id medical_record_number",
    _T.HEALTH_CARD: (
        "member_id memberid member_number subscriber_id insurance_id health_card health_card_number hcn phn "
        "ahcip uli ohip ramq carte_sante tarjeta_sanitaria"
    ),
    _T.ACCOUNT: "account_number policy_number group_number",
    _T.ID: (
        "tz teudat_zehut ת_ז תז national_id passport passport_number licence_number license_number drivers_license "
        "driver_license student_id employee_id username user_name login pesel dni nie curp nir nss "
        "numero_de_seguro_social dowod_osobisty"
    ),
}.items():
    for _k in _keys(_words):
        _FIELDS[_k] = _type

_WEAK = _keys("first last given middle name nom patient שם")
# Strong enough to make a one-column table: "Patient Name,Notes".
_STRONG_HEADER = _keys("patient_name full_name first_name last_name legal_name dob date_of_birth mrn member_id")

_EMPTY = {
    "", "null", "none", "nil", "n/a", "na", "true", "false", "-", "--", "unknown", "optional", "required", "tbd",
    "tba", "pending", "not provided", "not available", "unavailable", "see above", "same", "redacted", "x", "xx",
}
# Words in a value that say it is not a person's name: "Clinique Fertilité", "IVF drugs".
_NOT_NAME_WORDS = {
    "clinic", "clinique", "clinica", "hospital", "centre", "center", "centro", "pharmacy", "farmacia", "pharmacie",
    "lab", "laboratory", "laboratorio", "bank", "banco", "team", "office", "billing", "department", "services",
    "fertility", "fertilite", "fertilidad", "ivf", "test", "results", "drugs", "morning", "afternoon", "evening",
    "night", "visit", "cycle", "period", "history", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "patient", "patients", "staff", "doctor", "nurse",
}
# A word after a comma in a name field that starts a remark, not a given name.
_REMARKS = {
    "mother", "father", "mom", "dad", "wife", "husband", "partner", "spouse", "sister", "brother", "son", "daughter",
    "friend", "self", "patient", "guardian", "parent", "aunt", "uncle", "grandmother", "grandfather", "cell", "home",
    "mobile", "phone", "tel", "email", "mère", "père", "madre", "padre", "esposo", "esposa", "matka", "ojciec", "mąż",
    "żona", "please", "same", "see", "ok", "pending",
}
_CHAT_WORDS = {"bye", "ok", "okay", "yes", "no", "see", "you", "soon", "cheers", "regards", "thx", "ty", "lol", "np"}
_PARTICLES = {"de", "del", "la", "le", "da", "di", "van", "von", "der", "den", "bin", "bint", "ibn", "al", "el", "y", "e"}
_PHONE_VALUE = re.compile(r"\+?[\d\s().\-]{7,22}(?:\s*(?:x|ext\.?)\s*\d{1,5})?", re.IGNORECASE)
_MONTHS = re.compile(
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|févr|avr|mai|juin|juil|août|déc|ene|abr|ago|dic|"
    r"sty|lut|kwi|cze|lip|sie|wrz|paź|lis|gru",
    re.IGNORECASE,
)
_CODE_TOKEN = re.compile(r"[A-Z]{1,4}|[A-Za-z0-9#]*\d[A-Za-z0-9#./\-]*")
_USERNAME = re.compile(r"[A-Za-z0-9][\w.\-@]{1,40}")


_MARKS = "\u200e\u200f\u200b\u2066\u2067\u2068\u2069\u00a0\u202f\"'“”„«»‘’"


def _decode(v: str) -> str:
    """JSON escapes ("Mar\\u00eda") as text, without direction marks and quotes around it."""
    v = v.strip().strip(_MARKS).strip()
    if "\\" not in v:
        return v
    try:
        return json.loads(f'"{v}"')
    except ValueError:
        return v


def _name_ok(v: str, lower_ok: bool = False, filter_words: bool = True) -> bool:
    v = v.strip(_MARKS)
    words = v.replace(",", " ").split()
    if not 1 <= len(words) <= 6 or any(ch.isdigit() or ch in "@/:;()" for ch in v):
        return False
    if lower_ok and v.islower() and len(words) <= 3 and not any(_norm(w) in _NOT_NAME_WORDS or w in STOP_WORDS or w in _CHAT_WORDS for w in words):
        return True  # "first_name: maria"
    for w in words:
        lw = _norm(w)
        if filter_words and lw in _NOT_NAME_WORDS:
            return False
        if lw in _PARTICLES:
            continue
        if w[0].isalpha() and w[0].lower() == w[0].upper():
            continue  # no case: Hebrew and other scripts
        if not (w[0].isupper() or (len(w) > 1 and w[0] in "'’" and w[1].isupper())):
            return False
    return True


def _value_ok(t: EntityType, raw: str, sure: bool = True) -> bool:
    v = _decode(raw).strip().strip("\"'")
    if v.lower() in _EMPTY or not re.search(r"\w", v):
        return False
    digits = sum(c.isdigit() for c in v)
    if t is _T.NAME:
        # A field named for a name holds one ("first_name: Sunday"); a bare "name" may not.
        return _name_ok(v, lower_ok=sure, filter_words=not sure)
    if t is _T.PHONE:
        return digits >= 7 and bool(_PHONE_VALUE.fullmatch(v))
    if t is _T.EMAIL:
        return "@" in v and " " not in v
    if t is _T.DATE:
        rest = _MONTHS.sub("", re.sub(r"[\d\s,./\-:TZ+]", "", v))
        return digits >= 3 and len(rest) <= 3
    if t is _T.ZIP:
        return bool(re.fullmatch(r"\d{5}(?:-\d{4})?", v))
    if t is _T.POSTAL_CODE:
        return bool(re.fullmatch(r"[A-Za-z]\d[A-Za-z][ \-]?\d[A-Za-z]\d|\d{5}|\d{2}-\d{3}|\d{7}", v))
    if t is _T.ADDRESS:
        if len(v) > 80 or re.search(r"[;!?]|\b(?:and|then|please|if|or|et|y|i|und)\b", v):
            return False
        return digits > 0 or _name_ok(v)
    if t is _T.ID and _USERNAME.fullmatch(v) and not v.isdigit():
        return bool(re.search(r"[._\d]", v)) and digits < len(v)  # usernames: "hunter.bale", "mgarcia88"
    # Codes: every word holds a digit or is a short upper-case prefix ("AB 112 553 084", "GRP 8820145").
    tokens = v.split()
    return digits >= 4 and len(v) <= 40 and all(_CODE_TOKEN.fullmatch(tok) for tok in tokens)


def _span(text: str, start: int, end: int) -> tuple[int, int]:
    """Trim spaces, quotes and carriage returns from both ends of ``text[start:end]``."""
    while start < end and (text[start] in _MARKS or text[start] in " \t\r"):
        start += 1
    while end > start and (text[end - 1] in _MARKS or text[end - 1] in " \t\r,;"):
        end -= 1
    return start, end


_JSON = re.compile(
    r"(?P<q>[\"'])(?P<k>[^\"'\n]{1,40})(?P=q)\s*:\s*"
    r"(?:(?P<q2>[\"'])(?P<s>(?:(?!(?P=q2))[^\\\n]|\\.){0,160})(?P=q2)|(?P<n>-?\d[\d\-]{3,30})(?![\d.]))"
)
_XML = re.compile(r"<(?P<k>[A-Za-z_][\w\-.]{0,40})>(?P<s>[^<>\n]{1,160})</(?P=k)>")
# "preferred_name: Ana", "legal_name = Aiyana Redcrow": one field per line. The value ends
# before a remark in brackets or after a dash.
_KV = re.compile(
    r"(?m)^[ \t\u200e\u200f]*(?P<k>[^\W\d][\w \-.'/]{0,30}?)[ \t\u00a0\u202f\u200e\u200f]*[:=]"
    r"[ \t\u00a0\u202f]*(?P<v>[^\n:=]{1,120}?)[ \t\r]*$"
)
_KV_CUT = re.compile(r"[ \t]+[(\[]|[ \t]+[-–—][ \t]")
_HL7_LINE = re.compile(r"(?m)^(?P<seg>[A-Z][A-Z0-9]{2})\|(?P<rest>[^\n\r]*)")


def _json(text: str, out: list) -> None:
    for m in [*_JSON.finditer(text), *_XML.finditer(text)]:
        key = _norm(m.group("k"))
        t = _FIELDS.get(key)
        g = "n" if "n" in m.groupdict() and m.group("s") is None else "s"
        if t is not None and _value_ok(t, m.group(g), sure=key not in _WEAK):
            out.append((t, *_span(text, *m.span(g)), key if key in _WEAK else None))


def _key_values(text: str, out: list) -> None:
    for m in _KV.finditer(text):
        key = _norm(m.group("k"))
        t = _FIELDS.get(key)
        if t is None:
            continue
        start, end = m.span("v")
        cut = _KV_CUT.search(text, start, end)
        if cut and not _value_ok(t, text[start:end], sure=key not in _WEAK):
            end = cut.start()
        if t is _T.NAME:
            # "John Smith, 416-555-0123", "Maria Lopez, mother": the name ends at the comma
            # unless the value is "Last, First".
            comma = text.find(",", start, end)
            if comma > 0:
                after = text[comma + 1 : end].strip().lower()
                if re.search(r"\d|@", after) or after.split()[:1] and after.split()[0] in _REMARKS:
                    end = comma
        weak = key in _WEAK
        if _value_ok(t, text[start:end], sure=not weak):
            out.append((t, *_span(text, start, end), key if weak else None))


def _cells(line: str, sep: str) -> list[tuple[int, str]]:
    """(offset, cell) for one CSV line; a quoted cell may hold the separator."""
    cells, start, quoted, i = [], 0, False, 0
    while i < len(line):
        c = line[i]
        if c == '"':
            if quoted and line[i + 1 : i + 2] == '"':
                i += 2
                continue
            quoted = not quoted
        elif c == sep and not quoted:
            cells.append((start, line[start:i]))
            start = i + 1
        i += 1
    cells.append((start, line[start:]))
    return cells


def _csv(text: str, out: list) -> None:
    lines, pos = [], 0
    for line in text.split("\n"):
        lines.append((pos, line.rstrip("\r")))
        pos += len(line) + 1
    i = 0
    while i < len(lines):
        line = lines[i][1]
        sep = max(",;\t|", key=line.count)
        if not line.count(sep) or _HL7_LINE.match(line):
            i += 1
            continue
        header = [c for _, c in _cells(line, sep)]
        keys = [_norm(c) for c in header]
        cols = [_FIELDS.get(k) for k in keys]
        known = sum(c is not None for c in cols)
        # A header row: short cells, and at least two known field names making up at least
        # half of them (or one unmistakable one: "Patient Name,Notes").
        strong = any(k in _STRONG_HEADER for k in keys) or (len(cols) <= 4 and _T.NAME in cols)
        if (known < 2 or 2 * known < len(cols)) and not (strong and len(cols) <= 6):
            i += 1
            continue
        if any(len(c) > 30 for c in header):
            i += 1
            continue
        i += 1
        blank = 0
        while i < len(lines):
            row_start, row = lines[i]
            if not row.strip():
                blank += 1
                if blank > 2:
                    break
                i += 1
                continue
            if sep not in row:
                break
            cells = _cells(row, sep)
            if any(_norm(c) in _FIELDS for _, c in cells):
                break  # another header: the outer loop reads it
            # A short or long row still lines up from the left ("Maria,Lopez" under "first,last,dob").
            pairs = [
                (col, key, off, cell)
                for col, key, (off, cell) in zip(cols, keys, cells)
                if col is not None and _decode(cell).lower() not in _EMPTY
            ]
            fits = [_value_ok(col, cell, sure=key not in _WEAK) for col, key, off, cell in pairs]
            if pairs and not all(fits):
                if blank:
                    break  # prose after the table
                i += 1
                continue  # a row that is not data ("This is a sentence, with a comma.")
            blank = 0
            for col, key, off, cell in pairs:
                out.append((col, *_span(text, row_start + off, row_start + off + len(cell)), key if key in _WEAK else None))
            i += 1


# HL7 v2 field numbers: (segment, field) -> what the field holds. "name" and "address"
# are split into their components.
_HL7: dict[tuple[str, int], object] = {
    ("PID", 2): _T.MRN, ("PID", 3): _T.MRN, ("PID", 4): _T.MRN, ("PID", 5): "name", ("PID", 6): "name",
    ("PID", 7): _T.DATE, ("PID", 9): "name", ("PID", 11): "address", ("PID", 13): _T.PHONE,
    ("PID", 14): _T.PHONE, ("PID", 18): _T.ACCOUNT, ("PID", 19): _T.SSN, ("PID", 20): _T.ID,
    ("NK1", 2): "name", ("NK1", 4): "address", ("NK1", 5): _T.PHONE, ("NK1", 6): _T.PHONE,
    ("GT1", 3): "name", ("GT1", 5): "address", ("GT1", 6): _T.PHONE, ("GT1", 8): _T.DATE, ("GT1", 12): _T.SSN,
    ("IN1", 16): "name", ("IN1", 18): _T.DATE, ("IN1", 19): "address", ("IN1", 36): _T.ACCOUNT,
    ("IN1", 49): _T.HEALTH_CARD,
}
_HL7_ADDRESS = {0: _T.ADDRESS, 1: _T.ADDRESS, 2: _T.ADDRESS, 4: _T.ZIP}  # street, other, city, (state), zip


def _hl7(text: str, out: list) -> None:
    for m in _HL7_LINE.finditer(text):
        seg = m.group("seg")
        pos = m.start("rest")
        for n, field in enumerate(m.group("rest").split("|"), start=1):
            kind = _HL7.get((seg, n))
            if kind is not None and field:
                rpos = pos
                for rep in field.split("~"):
                    cpos = rpos
                    for c, comp in enumerate(rep.split("^")):
                        t = None
                        if kind == "name":
                            # family^given^middle; a one-letter middle initial counts.
                            ok = c < 3 and (len(comp) == 1 and comp.isalpha() or _name_ok(comp))
                            t = _T.NAME if ok else None
                        elif kind == "address":
                            t = _HL7_ADDRESS.get(c)
                        elif c == 0:
                            t = kind  # type: ignore[assignment]
                        if t is not None and comp.strip() and re.search(r"\w", comp):
                            out.append((t, cpos, cpos + len(comp), None))
                        cpos += len(comp) + 1
                    rpos += len(rep) + 1
            pos += len(field) + 1


def detect(text: str) -> list[tuple[EntityType, int, int]]:
    """(type, start, end) for values in fields whose name says what they hold."""
    if not any(ch in text for ch in ":=|,;\t<"):
        return []
    out: list[tuple[EntityType, int, int, str | None]] = []
    _json(text, out)
    _key_values(text, out)
    _csv(text, out)
    _hl7(text, out)
    # "name", "first", "patient" count only beside a field that is surely personal, or
    # beside another of them ("Last: Lopez / First: Maria").
    weak_keys = {k for *_, k in out if k is not None}
    full_name = any(
        k is not None and t is _T.NAME and len(text[a:b].split()) >= 2 and all(len(w) > 2 for w in text[a:b].split())
        and _name_ok(text[a:b])
        for t, a, b, k in out
    )
    sure = any(k is None for *_, k in out) or len(weak_keys) >= 2 or full_name
    return [(t, a, b) for t, a, b, k in out if b > a and (sure or k is None)]
