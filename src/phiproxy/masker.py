"""Mask text and LLM payloads before they leave; restore them when replies come back."""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Optional, Sequence

from .dates import is_non_date_context, shift_date_text
from .detectors.base import Detector, fill_text, merge_entities
from .detectors import _names, _spoken
from .detectors.known import COMMON_WORD_NAMES, KnownEntities, KnownEntityDetector
from .detectors.regex import RegexDetector
from .entities import Entity, EntityType
from .staff import _CUE_WORDS, StaffList, _name_words
from .vault import InMemoryVault, Vault


_FILE_INITIAL = re.compile(r"_[A-Z](?![^\W_])")


class PhiproxyError(Exception):
    """Masking failed. Callers must not send the original content (fail closed)."""


class UnsupportedContentError(PhiproxyError):
    """The payload holds content phiproxy cannot mask (images, audio, files)."""


# Detectors whose spans are statistical guesses rather than record or rule matches.
MODEL_SOURCES = frozenset({"presidio", "gliner"})


@dataclass
class Policy:
    # Clinician names are not patient identifiers under Safe Harbor and masking
    # them hurts answers ("Dr. [PROVIDER_1] said..."), so they pass by default.
    disabled_types: set[EntityType] = field(default_factory=lambda: {EntityType.PROVIDER})
    # "token": dates become [DATE_n]. "shift": dates move by a per-session offset,
    # keeping intervals intact; the reply is shifted back.
    date_mode: Literal["token", "shift"] = "token"
    day_first: bool = False  # how to read 03/04/2026 (False = US month first)
    allow_images: bool = False
    allow_audio: bool = False
    allow_files: bool = False
    # The clinic's own details that should reach the model unmasked: its name,
    # phone and fax numbers, address, website, and staff names. A detection that
    # lies wholly inside one of these passes, unless it matched the patient's
    # own record (a patient who shares a staff member's name stays masked).
    # Prefer full names: allowing a bare first name unmasks any patient with it.
    # "@clinic.example.org" allows every address at that email domain.
    allow: Sequence[str] = ()
    # The clinic's staff, full names preferred ("Jocelyn Paré", "Will Barnes").
    # A full name passes anywhere; a first name or surname alone passes only
    # next to a staff cue ("Jocelyn in billing", "AGENT: ... this is Jon",
    # "call Hsu at ext. 2240"). Record matches stay masked. See phiproxy.staff.
    staff: Sequence[str] = ()
    # False: staff first names pass anywhere (unmasks patients who share them).
    staff_need_context: bool = True


def _allow_pattern(value: str) -> Optional[re.Pattern[str]]:
    value = value.strip()
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 7 and len(digits) >= len(re.sub(r"[\s().+\-]", "", value)) - 1:
        # Phone-like: same digits, any separators ("613-555-0100" = "(613) 555 0100").
        # Scanned faxes read 0 as O and 1 as l: "613-555-O188".
        alike = {"0": "[0Oo]", "1": "[1lI]"}
        body = r"[^\w]{0,3}".join(alike.get(d, d) for d in digits[-10:])
        return re.compile(r"(?<![\dOolI])(?:\+?1\D{0,3})?\(?" + body + r"(?![\dOolI])")
    if not value:
        return None
    if value.startswith("@"):
        # Every address at the clinic's email domain: "@clinic.example.org".
        return re.compile(r"[\w.+\-]+" + re.escape(value) + r"(?![\w.\-])", re.IGNORECASE)
    # Scanned text swaps look-alikes: "Cedar Coast Fert1lity", "C1inic".
    alike = {"l": "[lIi1]", "i": "[lIi1]", "1": "[lIi1]", "o": "[oO0]", "0": "[oO0]"}
    # Street words and unit markers are written several ways ("Ave" / "Avenue", "Suite 310" /
    # "Ste 310" / "#310"), with a comma before the unit. The house number and the street name
    # still have to match exactly.
    words = [w for w in re.split(r"[\s,]+", value.replace("#", " # ")) if w]
    parts: list[str] = []
    for i, w in enumerate(words):
        group = _ALLOW_ABBREV.get(w.lower().rstrip("."))
        n = _ordinal_number(w, words[i + 1] if i + 1 < len(words) else "") if i else None
        if n is not None:  # "Eighth Avenue" = "8th Avenue" = "8 Avenue"
            group = rf"(?:{_ORDINAL_WORDS[n - 1]}|{n}(?:st|nd|rd|th)|{n})"
        if group is None:
            group = "".join(alike.get(c.lower(), re.escape(c)) for c in w.rstrip("."))
            if w.endswith("."):
                group += r"\.?"  # an abbreviation's dot is optional
        parts.append(group)
        if i + 1 < len(words):
            nxt_unit = _ALLOW_ABBREV.get(words[i + 1].lower().rstrip(".")) == _ALLOW_UNIT
            if group == _ALLOW_UNIT:
                parts.append(r"[^\S\n]*,?[^\S\n]*")
            elif nxt_unit:
                parts.append(r"[^\S\n]*,?[^\S\n]*(?:\r?\n[^\S\n]*)?")  # the suite may be on the next line
            else:
                # a line break may stand for the comma or space: "Avenue, Suite 4\r\nToronto"
                parts.append(r"(?:[^\S\n]{0,6},?[^\S\n]{0,6}\n[^\S\n]{0,6}|[^\S\n]{0,6},?[^\S\n]{1,6})")
    return re.compile(r"(?<!\w)" + "".join(parts) + r"(?!\w)", re.IGNORECASE)


_ORDINAL_WORDS = (
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh",
    "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth",
)
_STREET_WORD = re.compile(r"(?:st|street|ave|avenue|av|blvd|boulevard|rd|road|dr|drive|ln|lane|ct|court|way|pl|place)\.?", re.I)


def _ordinal_number(word: str, nxt: str) -> Optional[int]:
    """The number in a street name that may be written as a word, an ordinal or a bare digit."""
    w = word.lower().rstrip(".")
    if w in _ORDINAL_WORDS:
        return _ORDINAL_WORDS.index(w) + 1
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", w)
    if m and 1 <= int(m.group(1)) <= 20 and (m.group(0) != m.group(1) or _STREET_WORD.fullmatch(nxt)):
        return int(m.group(1))
    return None


_ALLOW_UNIT = r"(?:suite|ste|unit|#)\.?"
_ALLOW_ABBREV = {
    "suite": _ALLOW_UNIT, "ste": _ALLOW_UNIT, "unit": _ALLOW_UNIT, "#": _ALLOW_UNIT,
    "ave": r"(?:ave|avenue|av)\.?", "avenue": r"(?:ave|avenue|av)\.?",
    "st": r"(?:st|street)\.?", "street": r"(?:st|street)\.?",
    "blvd": r"(?:blvd|boulevard)\.?", "boulevard": r"(?:blvd|boulevard)\.?",
    "rd": r"(?:rd|road)\.?", "road": r"(?:rd|road)\.?",
    "dr": r"(?:dr|drive)\.?", "drive": r"(?:dr|drive)\.?",
    # A compass direction, in full or as its one letter: "King St W" = "King Street West" = "King St. W."
    "west": r"(?:west|w)\.?", "w": r"(?:west|w)\.?", "east": r"(?:east|e)\.?", "e": r"(?:east|e)\.?",
    "north": r"(?:north|n)\.?", "n": r"(?:north|n)\.?", "south": r"(?:south|s)\.?", "s": r"(?:south|s)\.?",
}


# What may sit between allowed pieces of the clinic's own details without being
# allowed itself: a state or province code ("Phoenix AZ 85018"), the country, an
# extension after the clinic's phone ("(602) 555-0700 ext 224").
_COVER_GAP = re.compile(
    r"\b(?-i:[A-Z]{2})\b|\b(?:usa|u\.s\.a?\.?|canada)\b|"
    r"\b(?:ext|extension|x|poste|wewn)\.?\s*\d{1,5}\b|"
    # the clinic's suite written another way than in the allow list ("Suite 900" for "#900")
    r"\b(?:suite|ste|unit|floor|bureau|oficina|piso)\.?\s*#?\s*\d{1,5}[A-Za-z]?\b|#\s*\d{1,5}\b",
    re.IGNORECASE,
)
# Generic words around the clinic's allowed name: "Clinique Bluebonnet", "kliniki
# Bluebonnet", "Bluebonnet coordination", "Équipe Bluebonnet Montréal", "Montreal office".
_ORG_GAP = re.compile(
    r"\b(?:the|our|la|le|les|el|los|las|de|du|des|del|para|pour|for|of|and|et|y|"
    r"clinic|clinics|clinique|cl[ií]nica|klinik[aiąę]?|centre|center|centro|centrum|office|offices|bureau|"
    r"oficina|biuro|team|[ée]quipe|equipo|zesp[oó][łl]|coordination|coordinaci[oó]n|nursing|billing|"
    r"facturation|facturaci[oó]n|lab|labo|laboratory|laboratoire|laboratorio|fertility|fertilit[ée]|"
    r"fertilidad|reproductive|reproductiva|reproduction|reproductive\s+health|salud|sant[ée]|health)\b",
    re.IGNORECASE,
)


# A street address rather than a bare town: a number or a street word.
_STREETISH = re.compile(
    r"\d|\b(?:ulica|ulicy|calle|avenida|carrera|rue|boulevard|chemin|street|avenue|road|drive|lane|court|place)\b|רחוב",
    re.IGNORECASE,
)
# A role or label word that a rule swallowed into a name: "Carrier Ophelia Lund", "Pacjentka Beata".
_ROLE_WORD = re.compile(rf"(?:{_names._RELATIONS}|{_names._PERSON_LABELS}|pacjentka|patientin)", re.IGNORECASE)
_NEXT_CAP = re.compile(r"[ \t]+[A-ZÀ-Þ][^\W\d_'’\-]+(?![^\W\d_])")
_FIRM_AFTER = re.compile(
    r"(?:[ \t,]+(?:Family[ \t]+)?(?:Law|Legal|LLP|LLC|PLLC|PC|P\.C\.|Associates|"
    r"Attorneys|Group|Firm|Inc|Ltd|S\.E\.N\.C\.R\.L)\b)"
)
# "Johnson & Johnson", "Ibarra & Wells LLP": a firm or brand written as a pair.
_CONJ_AFTER = re.compile(r"[ \t]*(?:&amp;|&|and|y|et|und)[ \t]+([A-ZÀ-Þ][^\W\d_]*)")
_CONJ_BEFORE = re.compile(r"([^\W\d_]+)[ \t]*(?:&amp;|&|and|y|et|und)[ \t]+$")
# Drug makers, brands and places that share a spelling with a name: not a person on a later mention.
_ECHO_BRANDS = frozenset(
    """pfizer moderna novartis merck bayer roche sanofi abbott ferring organon gilead astrazeneca glaxosmithkline
    genentech amgen takeda biogen novo nordisk ibsa arbor""".split()
)
_LOWER_NEUTRAL = frozenset(
    "and y et und hi hello hey dear thanks thank name is this call ask for about to from with by also or then".split()
)
_LOCALITY_AFTER = re.compile(
    r"(?P<sep>[ \t,]{0,4}(?:\r?\n[ \t]{0,4})?)"
    r"(?P<city>[A-ZÀ-Þ][^\W\d_]{2,20}(?:[ \t]{1,3}[A-ZÀ-Þ][^\W\d_]{2,20}){0,2})"
    r"(?:[\s,]{0,4}(?P<state>[A-Z]{2})\b)?"
    r"(?:[\s,]{0,4}(?P<zip>\d{5}(?:-\d{4})?|[A-Z]\d[A-Z][ \t]?\d[A-Z]\d))?"
)
_LOCALITY_TYPES = {EntityType.ADDRESS, EntityType.ZIP, EntityType.POSTAL_CODE}
_FIELD_LABEL = re.compile(
    r"[^\S\n]*(?i:city|town|zip(?:\s*code)?|postal\s*code|ville|code\s+postal|ciudad|c[óo]digo\s+postal|miasto|kod)[^\S\n]*[:=][^\S\n]*"
)
_INITIAL_BEFORE = re.compile(r"(?<![\w.])[A-ZÀ-Þ]\.[ \t]?$")
_FILE_INITIAL = re.compile(r"_[A-ZÀ-Þ](?![^\W_])")
# Words that name a person once but are ordinary words elsewhere.
_ECHO_SKIP = (
    _names.STOP_WORDS | _names._NOT_NAME_EXTRA | _names._ORG_NAME_WORDS | _names._ORG_TAIL_WORDS | COMMON_WORD_NAMES
    | {"dr", "mr", "mrs", "ms", "miss", "mme", "baby"}
)

# Last words of a facility, organisation, holiday or document title ("Ross Memorial Hospital",
# "Scott Laboratories", "Davis Report", "Martin Luther King Jr Day"): a person's surname that
# starts such a phrase is not the person.
_FACILITY_TAIL = frozenset(
    _names._ORG_NAME_WORDS
    | set(
        """laboratories labs lab laboratoire laboratorios report reports day days memorial centre center institute
        institut foundation university université college school academy pavilion building wing hall library
        museum church temple mosque synagogue park bridge street avenue road drive lane boulevard plaza
        pharmacy pharmacies imaging labs society association corporation company corp inc ltd llc
        hospitals clinics""".split()
    )
)
# Name-sized words that are also ordinary English nouns, verbs or adjectives. At the start of a
# sentence, followed by an ordinary lowercase word that is not a verb of a subject ("Grant
# access", "Gold standard", "Jack up"), they are the ordinary word, not the person.
_ECHO_HOMONYMS = frozenset(
    """grant gold wood jack hart bell baker cook miller stone field hill bush dean drew fox bird lamb wolf bear
    fish hall hood hook hunt knight lock mason mills moore page park pierce porter potter rich rice rock sharp
    sheen snow steel strong swift tanner taylor thorn ward wells wise wolfe barber carter cooper dyer fisher
    fletcher forester glover gardner archer butler chandler clark clarke mayor marshall parker pope reed
    shepherd smith sweet turner walker weaver wright bank banks bond boyd brace case church cross dale day dawn
    day diamond dunn flowers force ford forest frost gay gill glass gray green hale hardy hayes heart hurt
    kind lord love mace march mint noble nash patch peace penny pound power prince queen rose rush sale salt
    sand scale seal shaw shelf sims slater small speak spencer stamp stark stern stew story swan tate temple
    tide tool trace trial trout vale vine wade wake watch wedge west wheeler whitt wild wind wing wolf wren
    yard york young bill bull cash chance clay coin crane crow dove drake duck finch frank hawk hope lane lee
    long mark may miles pat pitt plant rank rest rich sage will ford lemon lake summer winter spring autumn
    brook brooks bridge house home city town river creek valley mountain beach bay island harbour harbor
    garden orchard meadow grove ridge hollow holly ivy olive berry cherry apple pepper ginger honey sugar
    lily daisy iris violet pearl ruby amber jade coral crystal faith grace joy hunter shepherd sterling
    victor major miles chase dash drew gene guy jay joe kit lance mike nick ray rob sam art
    early pink sun paris fields pool white black brown blue red lilac late fair best good light low high mild
    heavy normal pierce paris florence india israel jordan austin chelsea sydney dallas houston lincoln
    washington adams bishop price rider sparks silver gates fall hurst moss pitt reach ross shell tucker""".split()
)
_ECHO_VERB_NEXT = frozenset(
    """is was are were has had have does did do will would can could should shall may might must said says
    says called calls asked asks told tells wants wanted needs needed prefers preferred lives lived works
    worked goes went came comes got gets thinks thought knows knew likes liked loves loved takes took
    arrived arrives left leaves moved moves sent sends wrote writes replied replies agreed agrees mentioned
    mentions reported reports confirmed confirms booked books signed signs cancelled canceled cancels""".split()
)
_TITLE_BEFORE = re.compile(r"(?i:\b(?:dr|mr|mrs|ms|miss|mx|mme|mlle|sr|sra|se[ñn]or|pan|pani|madame|monsieur)\.?)[ \t]+$")
_SENTENCE_END = tuple(".!?:;\"“(•*-–—\n")
_NEXT_WORD = re.compile(r"[^\S\n]+([^\W\d_][\w'’]*)")


def _sentence_start(text: str, a: int) -> bool:
    before = text[max(0, a - 12):a].rstrip(" \t")
    return not before and (a < 12 or text[:a].strip(" \t") == "") or before.endswith(_SENTENCE_END)


_POSSESSIVE = re.compile(r"['’][sS]$")

_AT_CLINIC = re.compile(
    r"[^\S\n]*,?[^\S\n]*(?:here[^\S\n]+)?(?:at|from|with|de|du|del|z|ze|w|מ|ב)[^\S\n]*"
    r"(?:(?:the|la|le|el|l['’])[^\S\n]+)?(?:(?:clinic|clinique|cl[ií]nica|klinik\w*|centre|center|centro|office|bureau)[^\S\n]+)?",
    re.IGNORECASE,
)
_ADDRESS_AFTER = re.compile(r"(?:[^\S\n]+[^\W\d_][\w'’.\-]*){0,3}?[^\S\n]*<([^<>\s@]+@[^<>\s]+)>")


def _next_to(text: str, street: Entity, place: Entity) -> bool:
    """``place`` follows ("Ave, Minneapolis") or precedes ("in Minneapolis, ulica Lyndale") the street
    within a few characters on one line, with no sentence end between."""
    a, b = (street.end, place.start) if street.end <= place.start else (place.end, street.start)
    return 0 <= b - a <= 20 and not re.search(r"[\n.!?]", text[a:b])


_CITY_TAIL = re.compile(r"[\s,]*[A-ZÀ-Þ][^\W\d_]{2,20}(?:[ \t]+[A-ZÀ-Þ][^\W\d_]{2,20}){0,2}[\s,]*")


# An apartment, unit or floor written right after an address: not the clinic's own suite.
_UNIT_AFTER = re.compile(
    r"[ \t,;]{0,4}(?:\r?\n[ \t]{0,4})?(?:(?:apt|apartment|appt|unit|floor|piso|dpto|apto)\b\.?|#)[ \t]{0,2}#?[ \t]{0,2}(?:[A-Za-z]{1,2}[ \t\-]?)?\d",
    re.IGNORECASE,
)


def _covered(e: Entity, allowed: list[tuple[int, int]]) -> bool:
    """Every letter and digit of ``e`` is inside allowed spans ("1450 West Georgia Street,
    Vancouver" when the street and the city are each allowed), apart from a state or
    province code, the country or a phone extension between them."""
    inside = set()
    for a, b in allowed:
        if a < e.end and e.start < b:
            inside.update(range(max(a, e.start), min(b, e.end)))
    if not inside:
        return False
    rest = "".join(ch if i not in inside else " " for i, ch in enumerate(e.text, e.start))
    if not any(ch.isalnum() for ch in _ORG_GAP.sub(" ", rest)):
        return True
    # Gaps are skipped only inside a full clinic address or phone (the allowed part
    # has a number): an allowed city alone does not cover "Vancouver WA".
    if not any(e.text[i - e.start].isdigit() for i in inside):
        return False
    if not any(ch.isalnum() for ch in _COVER_GAP.sub(" ", _ORG_GAP.sub(" ", rest))):
        return True
    # The clinic's own street and unit with the city written after it, though the city itself is not
    # in the allow list: "123 Main Ave, Suite 4, Toronto".
    last = max(inside)
    return min(inside) == e.start and bool(_CITY_TAIL.fullmatch(e.text[last - e.start + 1:]))


@dataclass
class MaskResult:
    text: str
    entities: list[Entity]  # contains the original PHI - never log this

    def summary(self) -> dict[str, int]:
        """Counts per entity type; safe to log."""
        return dict(Counter(e.type.value for e in self.entities))


_TYPE_ALTERNATION = "|".join(
    sorted((t.value.replace("_", "[ _]?") for t in EntityType), key=len, reverse=True)
)
# Tolerant token matcher: [NAME_1], [name 1], [ NAME-1 ], NAME_1
_TOKEN_RE = re.compile(
    rf"\[\s*(?P<t1>{_TYPE_ALTERNATION})[ _\-]?(?P<n1>\d+)\s*\]|\b(?P<t2>{_TYPE_ALTERNATION})_(?P<n2>\d+)\b",
    re.IGNORECASE,
)

# Keys whose string values are structure, not content.
_STRUCTURAL_KEYS = {
    "role", "type", "id", "tool_call_id", "tool_use_id", "model", "cache_control",
    "media_type", "detail", "format", "index", "finish_reason", "object", "signature",
    "stop_reason", "call_id", "status",
}
_STREAM_HOLD = 48  # chars held back while streaming so tokens/dates are never split


class Masker:
    """Detects identifiers, swaps them for tokens, and swaps them back.

    >>> m = Masker()
    >>> r = m.mask("Call me at 416-555-0142", session_id="s1")
    >>> r.text
    'Call me at [PHONE_1]'
    >>> m.unmask("I will call [PHONE_1] today.", session_id="s1")
    'I will call 416-555-0142 today.'
    """

    def __init__(
        self,
        vault: Optional[Vault] = None,
        detectors: Optional[Sequence[Detector]] = None,
        policy: Optional[Policy] = None,
    ):
        self.vault: Vault = vault if vault is not None else InMemoryVault()
        self.detectors: list[Detector] = list(detectors) if detectors is not None else [RegexDetector()]
        self.policy = policy or Policy()
        self._date_detector = RegexDetector(enabled={EntityType.DATE})
        self._allow = [p for p in (_allow_pattern(v) for v in self.policy.allow) if p is not None]
        self._allow_phones = {
            d[-10:] for d in (re.sub(r"\D", "", v) for v in self.policy.allow) if len(d) >= 7
        }
        self._staff = StaffList(self.policy.staff, need_context=self.policy.staff_need_context)

    # ------------------------------------------------------------------ detect
    def detect(self, text: str, known: Optional[KnownEntities] = None) -> list[Entity]:
        detectors: list[Detector] = list(self.detectors)
        if known is not None and not known.is_empty():
            detectors.insert(0, KnownEntityDetector(known))
        found: list[Entity] = []
        for d in detectors:
            found.extend(d.detect(text))
        # A disabled span (by default a clinician name) also shields model
        # guesses that overlap it: a NER model tags "Dr. Patel" as a person too,
        # and that guess must not mask what the policy lets through. Matches from
        # records or rules are still masked.
        disabled = [e for e in found if e.type in self.policy.disabled_types]
        found = [
            e
            for e in found
            if e.type not in self.policy.disabled_types
            and not (e.source in MODEL_SOURCES and any(e.overlaps(d) for d in disabled))
        ]
        found = [e for e in found if not self._own_handle(e) and not self._own_site(e)]
        allowed: list[tuple[int, int]] = []
        if self._allow:
            allowed = [m.span() for p in self._allow for m in p.finditer(text)]
            patient_place = self._patient_locality(text, found, allowed)
            found = [
                e for e in found
                if e.source == "known" or e in patient_place
                or not (
                    (_covered(e, allowed) and not (e.type is EntityType.ADDRESS and _UNIT_AFTER.match(text, e.end)))
                    or self._allowed_spoken_phone(e)
                )
            ]
            found = found + [e for e in patient_place if e not in found]
        if self._staff:
            names = [e for e in found if e.type is EntityType.NAME and e.source != "known"]
            cued = self._staff.cued_words(text, names, anchors=disabled)
            found = [
                e for e in found
                if e not in names
                or not (
                    self._staff.passes(text, e, cued)
                    or self._staff_sender(text, e, allowed)
                    or self._staff_at_clinic(text, e, allowed)
                )
            ]
        found = self._extend_names(text, found)
        found = found + self._echoed_names(text, found, disabled, allowed)
        return fill_text(text, merge_entities(found))

    _HANDLE_SUFFIX = frozenset("ai clinic fertility ivf official health care hq inc centre center".split())

    def _own_site(self, e: Entity) -> bool:
        """A scheme-less site after a visit/website cue whose host is the clinic's: a domain on the
        allow list, or the domain of an email on it ("info@mfc.ca" allows "portal.mfc.ca")."""
        if e.type is not EntityType.URL or e.source != "regex" or "://" in e.text or re.search(r"[?#@]", e.text):
            return False
        host = e.text.split("/", 1)[0].lower().removeprefix("www.")
        for v in self.policy.allow:
            for d in re.findall(r"(?:@|\b(?:https?://)?(?:www\.)?)((?:[a-z0-9][a-z0-9\-]*\.)+[a-z]{2,})", v.lower()):
                if host == d or host.endswith("." + d):
                    return True
        return False

    def _own_handle(self, e: Entity) -> bool:
        """A social handle that is the clinic's own account (it matches an allow-list value, alone
        or with a generic suffix: "@bluebonnetclinic") or a staff member's ("@jen_alvarez",
        "@nurse_jen" when Jen is on the staff list). Without an allow or staff list the handle stays
        masked: a handle is a personal identifier unless the caller says it is the clinic's."""
        if e.type is not EntityType.ID or e.source != "regex" or not e.text.startswith("@"):
            return False
        name = e.text[1:]
        norm = re.sub(r"[\W_]+", "", name).lower()
        for v in self.policy.allow:
            full = re.sub(r"[\W_]+", "", v).lower()
            bases = [full]
            words = [re.sub(r"[\W_]+", "", w).lower() for w in v.replace("@", " ").split()]
            while len(words) > 1 and words[-1] in self._HANDLE_SUFFIX:
                words.pop()  # "Bluebonnet Fertility Clinic" -> "bluebonnet"
            if len(words) >= 1 and len("".join(words)) >= 6:
                bases.append("".join(words))
            for base in bases:
                if len(base) >= 4 and (norm == base or (norm.startswith(base) and norm[len(base):] in self._HANDLE_SUFFIX)):
                    return True
        # A staff member: the WHOLE handle is the full name or first + last (any order), letters only,
        # with a leading role word allowed ("@dr_jen_alvarez"). One matching token is not enough.
        tokens = [t.lower() for t in re.findall(r"[^\W\d_]{2,}", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name))]
        while tokens and (tokens[0] in ("dr", "mr", "mrs", "ms", "doc") or _CUE_WORDS.match(tokens[0])):
            tokens = tokens[1:]
        letters = "".join(tokens)
        if not letters:
            return False
        for n in self.policy.staff or ():
            ws = _name_words(n)[0]
            while ws and (ws[0] in ("dr", "mr", "mrs", "ms", "doc") or _CUE_WORDS.match(ws[0])):
                ws = ws[1:]
            if len(ws) < 2:
                continue
            combos = {"".join(ws), ws[0] + ws[-1], ws[-1] + ws[0]}
            if letters in combos:
                return True
        return False

    def _patient_locality(self, text: str, found: list[Entity], allowed: list[tuple[int, int]]) -> list[Entity]:
        """The city, ZIP or postal code of a patient's own street address, though the clinic
        allows the same city or ZIP: "1807 Stevens Ave, Minneapolis 55403" (the street is not
        the clinic's), or form fields "city: ..." / "zip: ..." under a street line."""
        streets = [
            e for e in found
            if e.type is EntityType.ADDRESS and _STREETISH.search(e.text) and not _covered(e, allowed)
        ]
        if not streets:
            return []
        out = []
        for e in found:
            if e.type not in _LOCALITY_TYPES or not _covered(e, allowed) or (e.type is EntityType.ADDRESS and _STREETISH.search(e.text)):
                continue  # a clinic street is never a patient locality
            line = text.rfind("\n", 0, e.start) + 1
            if _FIELD_LABEL.match(text, line) and _FIELD_LABEL.match(text, line).end() == e.start:
                out.append(e)  # a labelled field: the street above it is the patient's
            elif any(_next_to(text, s, e) for s in streets):
                out.append(e)
        for s in streets:
            # "55 Oak St Minneapolis MN 55403", "55 Oak St\nMinneapolis, MN 55403": the city and the ZIP
            # after a patient street, with or without a comma, on the same line or the next.
            m = _LOCALITY_AFTER.match(text, s.end)
            if not m:
                continue
            for key, kind in (("city", EntityType.ADDRESS), ("zip", EntityType.ZIP)):
                a, b = m.span(key)
                if a >= 0 and any(x < b and a < y for x, y in allowed):
                    out.append(Entity(kind, a, b, text[a:b], "regex"))
        return out

    def _extend_names(self, text: str, found: list[Entity]) -> list[Entity]:
        """A first initial before a name ("K. Yang") and a file-name initial after it
        ("Lopez_M_labs.pdf") belong to the name."""
        out = []
        for e in found:
            if e.type is EntityType.NAME:
                start, end = e.start, e.end
                m = _INITIAL_BEFORE.search(text, max(0, start - 4), start)
                if m:
                    start = m.start()
                if _FILE_INITIAL.match(text, end):
                    end += 2
                if (start, end) != (e.start, e.end):
                    e = Entity(e.type, start, end, text[start:end], e.source)
            out.append(e)
        return out

    def _echoed_names(
        self, text: str, found: list[Entity], disabled: list[Entity], allowed: list[tuple[int, int]]
    ) -> list[Entity]:
        """A name found once is the same person on its next mention: "Halina Kowalczyk ... Is
        Halina able to come". Capitalized words of 3+ letters from names that a rule or the
        record found; not a clinician, a staff member, an allowed detail or a common word."""
        words: dict[str, str] = {}
        pairs: set[tuple[str, str]] = set()  # consecutive words of one found name
        initialed: set[str] = set()  # surnames found with a file initial: "Lopez_M"
        surnames: set[str] = set()  # last words of a multi-word name that are never its first word
        firsts: set[str] = set()
        for e in found:
            if e.type is EntityType.NAME and e.source in ("regex", "known"):
                initialed.update(x.lower() for x in re.findall(r"([^\W\d_]+)_[A-Z](?![^\W_])", e.text))
                toks = re.findall(r"[^\W\d_](?:[^\W\d_]|['’](?=[^\W\d_]))*", e.text)
                pairs.update((x.lower(), y.lower()) for x, y in zip(toks, toks[1:]))
                if len(toks) >= 2:
                    firsts.update(x.lower() for x in toks[:-1])
                    surnames.add(toks[-1].lower())
                for w in toks:
                    if len(w) >= (4 if w[0].islower() else 3) and not (w.isupper() and len(w) <= 4) and w.lower() not in _ECHO_SKIP and not _ROLE_WORD.fullmatch(w):
                        words.setdefault(w.lower(), w)
        if not words:
            return []
        surnames -= firsts
        taken = [(e.start, e.end) for e in found]
        # A lowercase use of the word counts as "an ordinary word" only when nothing ties it to a
        # person: not "thanks sarah", not next to another word of the name ("sarah cohen").
        lower: set[str] = set()
        for lm in re.finditer(r"(?<![^\W_])[^\W\d_]+(?![^\W_])", text):
            lw = lm.group(0)
            if lw.islower() and lw in words and not self._name_like_lower(text, lm, words):
                lower.add(lw)
        out = []
        for m in re.finditer(r"(?<![^\W_])[^\W\d_](?:[^\W\d_]|['’](?=[^\W\d_]))*(?![^\W_])", text):
            w = m.group(0)
            possessive = False
            if w.lower() not in words and _POSSESSIVE.search(w) and w[:-2].lower() in words:
                w = w[:-2]  # "Sarah's chart": the name without the possessive
                possessive = True
            if w.lower() not in words or w.lower() in _ECHO_BRANDS:
                continue
            if w.islower():
                # a lowercase mention ("thanks sarah", "sarah cohen") only where it plainly names the person
                if w in lower or not self._name_like_lower(text, m, words):
                    continue
            elif w.lower() in lower:
                continue  # also an ordinary word here ("carrier", "prior")
            a, b = m.start(), m.start() + len(w)
            if any(x < b and a < y for x, y in taken) or any(x <= a and b <= y for x, y in allowed):
                continue
            # The whole run of capitalized words around it: "Lawrence Ostrowski, MD", "Ibarra & Wells LLP".
            run_b = b
            while True:
                nxt = _NEXT_CAP.match(text, run_b)
                if not nxt:
                    break
                run_b = nxt.end()
            if any(d.start < b and a < d.end for d in disabled) or _names.is_clinician(text, a, run_b):
                continue
            repeated = self._repeats_full_name(text, w, a, b, pairs)
            if (not repeated and self._facility_phrase(text, a, b, run_b)) or self._ordinary_word(
                text, w, a, b, repeated, possessive
            ):
                continue
            if _FIRM_AFTER.match(text, b) or _FIRM_AFTER.match(text, run_b):
                continue  # a law firm or practice named after a person
            if self._brand_pair(text, w, a, b, run_b, words, pairs, repeated, surnames):
                continue
            tail = _FILE_INITIAL.match(text, b) if w.lower() in initialed else None
            if tail:
                b = tail.end()  # the same person written "Lopez_M": the initial goes with the surname
            e = Entity(EntityType.NAME, a, b, text[a:b] if tail else m.group(0), "regex")
            if self._staff and self._staff.on_roster(e):
                continue
            out.append(e)
        return out

    @staticmethod
    def _name_like_lower(text: str, m: re.Match[str], words: dict[str, str]) -> bool:
        """A lowercase use that is not clearly an ordinary word. It is ordinary ("the carrier plan")
        only when a plain lowercase word, not a cue, conjunction or word of the name, stands on each
        side on the same line. Next to a name word, after a greeting or cue, in a list ("sarah and
        cohen") or alone between punctuation ("sarah.") it plausibly names the person."""
        a, b = m.span()
        prev = re.search(r"([^\W\d_]+)[ \t]+$", text[max(0, a - 30):a])
        nxt = re.compile(r"[ \t]+([^\W\d_]+)").match(text, b)
        if not prev or not nxt:
            return True
        neutral = _LOWER_NEUTRAL
        for x in (prev.group(1), nxt.group(1)):
            if x.lower() in words or x.lower() in neutral:
                return True
        return False

    @staticmethod
    def _brand_pair(
        text: str, w: str, a: int, b: int, run_b: int, words: dict[str, str], pairs: set[tuple[str, str]], repeated: bool,
        surnames: frozenset[str] | set[str] = frozenset(),
    ) -> bool:
        """The word belongs to a capitalized multi-word term ("Ann Arbor", "Grace Kelly" is not one when
        it repeats the name) or to a pair written "Johnson & Johnson" or "Ibarra & Wells LLP". A couple
        ("Ana and Luis") and the person's own full name still echo."""
        lw = w.lower()
        if repeated:
            return False
        conj = _CONJ_AFTER.match(text, b)
        if conj:
            if conj.group(1).lower() == lw:
                return True  # Johnson & Johnson
            if lw in surnames:
                return True  # a surname before "and Pike": a firm or practice, not a couple
            tail = conj.end()
            while not _FIRM_AFTER.match(text, tail):
                nc = _NEXT_CAP.match(text, tail)
                if not nc:
                    return False
                tail = nc.end()
            return True
        before = _CONJ_BEFORE.search(text, max(0, a - 24), a)
        if before and before.group(1).lower() == lw:
            return True
        nc = _NEXT_CAP.match(text, b)
        if nc:
            n = nc.group(0).strip()
            if n.lower() in words or len(n) < 2 or not n[1:].islower():
                return False  # another word of a known name, or an acronym
            return not (lw, n.lower()) in pairs
        return False

    @staticmethod
    def _facility_phrase(text: str, a: int, b: int, run_b: int) -> bool:
        """The word is the first of a capitalized facility, organisation, holiday or report title
        ("Ross Memorial Hospital", "the Davis Report"), not the person."""
        if b == run_b or _INITIAL_BEFORE.search(text, max(0, a - 4), a):
            return False
        if re.search(r"[A-ZÀ-Þ][^\W\d_]*[ \t]+$", text[max(0, a - 40):a]):
            return False  # "Peter Ross Hospital": preceded by a given name
        return any(t.lower() in _FACILITY_TAIL for t in re.findall(r"[^\W\d_]+", text[b:run_b]))

    @staticmethod
    def _repeats_full_name(text: str, w: str, a: int, b: int, pairs: set[tuple[str, str]]) -> bool:
        """The word sits next to the word it was found with ("Jack Lemon" again)."""
        prev = re.search(r"([^\W\d_]+)[ \t]+$", text[max(0, a - 40):a])
        nxt = _NEXT_CAP.match(text, b)
        lw = w.lower()
        if prev and (prev.group(1).lower(), lw) in pairs:
            return True
        return bool(nxt and (lw, nxt.group(0).strip().lower()) in pairs)

    @staticmethod
    def _ordinary_word(text: str, w: str, a: int, b: int, repeated: bool = False, possessive: bool = False) -> bool:
        """A name-sized ordinary word ("Lemon juice", "Lake Ontario", "Day 3 of stimulation", "City
        Hall") is echoed only where it plainly names a person: after a title ("Mr Lemon"), as a
        possessive ("Day's chart"), before a verb of a subject ("Grant said", "Rose is coming"), or
        inside a repeat of the full name ("Jack Lemon" again). Anywhere else it is the ordinary word."""
        if w.lower() not in _ECHO_HOMONYMS:
            return False
        if repeated or possessive:
            return False
        if _TITLE_BEFORE.search(text, max(0, a - 8), a):
            return False
        if _sentence_start(text, a) and re.match(r"[ \t]{0,3}(?:[.,!?;:)]|\r?\n|$)", text[b:b + 6]):
            return False  # the word on its own: a bare repeat of the name
        nxt = _NEXT_WORD.match(text, b)
        return not (nxt and nxt.group(1).lower() in _ECHO_VERB_NEXT)

    def _allowed_spoken_phone(self, e: Entity) -> bool:
        """The clinic's own number read out loud: "seven one three, five five five, zero eight two zero"."""
        if e.type is not EntityType.PHONE or not self._allow_phones or sum(c.isdigit() for c in e.text) >= 7:
            return False
        d = _spoken.digits(e.text)
        return len(d) >= 7 and d[-10:] in self._allow_phones

    def _staff_at_clinic(self, text: str, e: Entity, allowed: list[tuple[int, int]]) -> bool:
        """A staff name followed by the clinic's own name: "Aaliyah here from Bluebonnet"."""
        m = _AT_CLINIC.match(text, e.end)
        return bool(m) and self._staff.on_roster(e) and any(a == m.end() for a, _ in allowed)

    def _staff_sender(self, text: str, e: Entity, allowed: list[tuple[int, int]]) -> bool:
        """A staff name shown with an allowed clinic address: "From: Gordon Tran <gordon.tran@clinic...>"."""
        m = _ADDRESS_AFTER.match(text, e.end)
        if not m or not self._staff.on_roster(e):
            return False
        a, b = m.span(1)
        return any(x <= a and b <= y for x, y in allowed)

    # -------------------------------------------------------------------- mask
    def mask(self, text: str, session_id: str, known: Optional[KnownEntities] = None) -> MaskResult:
        try:
            entities = self.detect(text, known)
            out: list[str] = []
            pos = 0
            offset = None
            for e in entities:
                out.append(text[pos : e.start])
                replacement = None
                if (
                    e.type is EntityType.DATE
                    and self.policy.date_mode == "shift"
                    and not is_non_date_context(text, e.start, e.end)
                ):
                    if offset is None:
                        offset = self.vault.date_offset(session_id)
                    replacement = shift_date_text(e.text, offset, self.policy.day_first)
                if replacement is None:
                    replacement = self.vault.token_for(session_id, e.type, e.value)
                out.append(replacement)
                pos = e.end
            out.append(text[pos:])
            return MaskResult("".join(out), entities)
        except PhiproxyError:
            raise
        except Exception as exc:  # fail closed
            raise PhiproxyError(f"masking failed: {type(exc).__name__}") from exc

    # ------------------------------------------------------------------ unmask
    def unmask(self, text: str, session_id: str) -> str:
        if not text:
            return text
        mapping = self.vault.mapping(session_id)

        def repl(m: re.Match[str]) -> str:
            t = (m.group("t1") or m.group("t2")).upper().replace(" ", "_")
            if "_" not in t:  # "HEALTHCARD" -> "HEALTH_CARD"
                t = next((et.value for et in EntityType if et.value.replace("_", "") == t), t)
            n = m.group("n1") or m.group("n2")
            value = mapping.get(f"[{t}_{n}]")
            return value if value is not None else m.group(0)

        # Shift the dates the model wrote first, then restore the tokens: a restored value (an address
        # that swallowed a date) is the exact original text and must not be shifted again.
        if self.policy.date_mode == "shift":
            text = self._shift_all_dates(text, session_id, direction=-1)
        return _TOKEN_RE.sub(repl, text) if mapping else text

    def remask(self, text: str, session_id: str) -> str:
        """Put tokens back over real values (e.g. before writing a reply to logs)."""
        if not text:
            return text
        mapping = self.vault.mapping(session_id)
        for token, value in sorted(mapping.items(), key=lambda kv: len(kv[1]), reverse=True):
            if len(value) < 2:
                continue
            text = re.sub(r"(?<!\w)" + re.escape(value) + r"(?!\w)", token, text, flags=re.IGNORECASE)
        if self.policy.date_mode == "shift":
            text = self._shift_all_dates(text, session_id, direction=+1)
        return text

    def _shift_all_dates(self, text: str, session_id: str, direction: int) -> str:
        dates = self._date_detector.detect(text)
        if not dates:
            return text
        days = direction * self.vault.date_offset(session_id)
        out, pos = [], 0
        for e in merge_entities(dates):
            shifted = (
                None
                if is_non_date_context(text, e.start, e.end)
                else shift_date_text(text[e.start : e.end], days, self.policy.day_first)
            )
            out.append(text[pos : e.start])
            out.append(shifted if shifted is not None else text[e.start : e.end])
            pos = e.end
        out.append(text[pos:])
        return "".join(out)

    # ---------------------------------------------------------------- payloads
    def mask_payload(self, obj: Any, session_id: str, known: Optional[KnownEntities] = None) -> Any:
        """Mask every content string in a JSON-like payload (messages, content blocks,
        tool calls, tool results). Returns a copy; raises on images/audio/files
        unless the policy allows them (they then pass through *unmasked*)."""
        return _walk(copy.deepcopy(obj), lambda s: self.mask(s, session_id, known).text, self.policy, masking=True)

    def unmask_payload(self, obj: Any, session_id: str) -> Any:
        return _walk(copy.deepcopy(obj), lambda s: self.unmask(s, session_id), self.policy, masking=False)

    def stream_unmasker(self, session_id: str) -> "StreamUnmasker":
        return StreamUnmasker(self, session_id)


def _walk(obj: Any, fn: Callable[[str], str], policy: Policy, masking: bool, key: Optional[str] = None,
          parent: Optional[dict] = None) -> Any:
    if isinstance(obj, str):
        if key in _STRUCTURAL_KEYS:
            return obj
        if key == "name" and not (parent and "role" in parent):
            return obj  # tool/function name, not a participant name
        if key == "arguments":  # tool-call arguments are a JSON string
            try:
                parsed = json.loads(obj)
            except ValueError:
                return fn(obj)
            return json.dumps(_walk(parsed, fn, policy, masking), ensure_ascii=False)
        return fn(obj)
    if isinstance(obj, dict):
        kind = _media_kind(obj)
        if kind is not None:
            if not masking:
                return obj
            if kind == "text_document":
                obj["source"] = _walk(obj["source"], fn, policy, masking, "source", obj)
                return obj
            allowed = {"image": policy.allow_images, "audio": policy.allow_audio, "file": policy.allow_files}[kind]
            if not allowed:
                raise UnsupportedContentError(f"payload contains {kind} content; blocked by policy")
            return obj  # allowed media passes through UNMASKED
        for k in list(obj.keys()):
            obj[k] = _walk(obj[k], fn, policy, masking, k, obj)
        return obj
    if isinstance(obj, list):
        return [_walk(v, fn, policy, masking, key, parent) for v in obj]
    return obj


_MEDIA_TYPES = {
    "image_url": "image", "image": "image", "input_image": "image",
    "input_audio": "audio", "audio": "audio",
    "file": "file", "input_file": "file", "document": "file",
}


def _media_kind(part: dict) -> Optional[str]:
    """Classify a content part by its declared type (OpenAI, Anthropic, Responses API)."""
    t = part.get("type")
    if not isinstance(t, str) or t not in _MEDIA_TYPES:
        return None
    src = part.get("source")
    if t == "document" and isinstance(src, dict) and src.get("type") == "text" and isinstance(src.get("data"), str):
        return "text_document"  # Anthropic plain-text document: maskable
    return _MEDIA_TYPES[t]


class StreamUnmasker:
    """Unmask a streamed reply chunk by chunk without splitting a token or date.

    Holds back the last few dozen characters until it is sure they do not
    start a token. Call ``flush()`` when the stream ends.
    """

    def __init__(self, masker: Masker, session_id: str):
        self.masker = masker
        self.session_id = session_id
        self._buf = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buf += chunk
        cut = len(self._buf) - _STREAM_HOLD
        if cut <= 0:
            return ""
        cut = self._safe_cut(cut)
        out, self._buf = self._buf[:cut], self._buf[cut:]
        return self.masker.unmask(out, self.session_id)

    def flush(self) -> str:
        out, self._buf = self._buf, ""
        return self.masker.unmask(out, self.session_id)

    def _safe_cut(self, cut: int) -> int:
        spans: list[tuple[int, int]] = [m.span() for m in _TOKEN_RE.finditer(self._buf)]
        lb = self._buf.rfind("[", 0, cut)
        if lb != -1 and "]" not in self._buf[lb:cut]:
            spans.append((lb, len(self._buf)))
        if self.masker.policy.date_mode == "shift":
            spans += [(e.start, e.end) for e in self.masker._date_detector.detect(self._buf)]
        for s, e in sorted(spans):
            if s < cut < e:
                cut = s
        return cut


def mask_texts(masker: Masker, texts: Iterable[str], session_id: str,
               known: Optional[KnownEntities] = None) -> list[MaskResult]:
    return [masker.mask(t, session_id, known) for t in texts]
