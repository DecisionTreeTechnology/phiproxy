"""The clinic's staff list: staff names pass unmasked, patients who share them do not.

A clinic's messages are full of its own staff: "Jocelyn in billing said...",
"AGENT: Harborview, Grace speaking", "Sig: T. Kowalski". Masking them costs the
model context and is not needed: staff names are not patient identifiers.

Allowing a bare first name everywhere would also unmask any patient with that
name, so this is stricter than ``Policy.allow``:

- a staff member's full name passes anywhere ("Carla Benitez", "Benitez, Carla");
- a first name, surname or initial + surname on its own ("Jocelyn", "Hsu",
  "T. Kowalski") passes only next to a staff cue: a department or role ("in
  billing", "from the lab", "our counsellor"), an agent introducing themself
  ("AGENT: ... this is Jon", "Grace speaking"), an extension ("call Hsu at
  ext. 2240"), or a signature label ("Sig:", "Witness:", "Minutes:"). Once a
  name has a cue in a message, its other mentions in that message pass too;
- anything that matched the patient's own record stays masked (the masker
  never lets a record match through).

Set ``need_context=False`` to pass staff first names anywhere. That unmasks
patients who share a staff member's first name.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

from .entities import Entity

_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")
# Joining and filler words inside a name span ("Marisol and Sunny", "Jocelyn in billing").
_CONNECTORS = frozenset(
    "and & or et ou y e i und lub oraz ו in from at the of our de du del la le el w z "
    "pani pan pana panią panem panu".split()
)

# People's roles (may follow a comma: "Priya Menon, Surrogacy Coordinator").
_PERSON_ROLE = (
    r"coordinator|coordinatrice|coordonnatrice|coordonnateur|coordinadora|coordinador|"
    r"koordynator(?:ka)?|receptionist|réceptionniste|recepcionista|recepcjonistka|"
    r"counsell?or|conseill[eè]re?|consejer[ao]|psycholog(?:ist|ue|a)?|social\s+worker|"
    r"embryologist[e]?|embri[oó]log[ao]?|andrologist|sonographer|[ée]chographiste|"
    r"ecografista|technician|technologist|tech|navigator|navigatrice|scheduler|"
    r"secretary|secr[ée]taire|secretaria|sekretarka|manager|gestionnaire|"
    r"administrator|administratrice|assistant[e]?|asistente|asystentka|educator|"
    r"[ée]ducatrice|phlebotomist|pharmacist|pharmacien(?:ne)?|farmac[ée]utic[ao]|"
    r"case\s+manager|team\s+member|staff|"
    r"מזכירה|מזכיר|רכזת|רכז|יועצת|יועץ|אחות"
)
# Departments and places inside the clinic.
_DEPT = (
    r"billing|front[\s\-]desk|desk|reception|accueil|recepci[oó]n|recepcj[aię]|rejestracj[aię]|"
    r"lab|labo|laboratory|laboratoire|laboratorio|laboratorium|embryology|embryologie|"
    r"embriolog[ií]a|andrology|andrologie|ultrasound|[ée]chographie|ecograf[ií]a|usg|"
    r"pharmacy|pharmacie|farmacia|apteka|front|nursing|scheduling|finance|facturation|"
    r"facturaci[oó]n|rozliczenia|admin|records|intake|team|[ée]quipe|equipo|zesp[oó]ł|"
    r"מעבדה|קבלה|צוות|הנהלת\s+חשבונות"
)
_IT = r"(?-i:IT)"  # "Bill from IT", but not "from it"

_FLAGS = re.IGNORECASE
_AFTER = [
    # "Jocelyn in billing", "Will from the lab", "Teri in embryology", "Carla at the desk"
    re.compile(
        r"^\s*,?\s*(?:in|from|at|of|on|de|du|des|del|w|z|ze|מה|ב)\s+(?:the\s+|la\s+|le\s+|l['’]|el\s+|our\s+)?"
        rf"(?:(?:{_DEPT}|{_PERSON_ROLE})\b|{_IT}\b)",
        _FLAGS,
    ),
    # "Grace, our new front-desk coordinator", "Priya Menon, Surrogacy Coordinator", "(RN)"
    re.compile(
        r"^\s*(?:,|\(|-|–)\s*(?:(?:our|the|your|notre|votre|nuestra|nuestro|su|nasza|nasz)\s+)?"
        rf"(?:new\s+|nouvelle\s+|nouveau\s+|nueva\s+|nuevo\s+|nowa\s+|nowy\s+)?(?:[\w\-]+\s+){{0,2}}?(?:{_PERSON_ROLE})\b",
        _FLAGS,
    ),
    re.compile(r"^\s*,?\s*(?:speaking|ici|al\s+habla|przy\s+telefonie|מדברת|מדבר)\b", _FLAGS),
    # Covering a colleague's work: "Will is covering my retrievals", "Lior cubre la vitrificación".
    re.compile(
        r"^\s*(?:is\s+|will\s+be\s+)?(?:covering|covers|cubre|remplace|zast[ęe]puje|on\s+call|"
        r"de\s+garde|de\s+guardia|na\s+dy[żz]urze)\b",
        _FLAGS,
    ),
    re.compile(r"^\s*(?:at\s+|on\s+|au\s+|al\s+|pod\s+)?(?:ext|extension|x|poste|wewn|שלוחה)\.?\s*\d", _FLAGS),
]
_BEFORE = [
    # "our counsellor renee", "coordinator Grace", "Billing: Jon"
    re.compile(rf"(?:\b(?:{_PERSON_ROLE}|{_DEPT})|{_IT})\s*[:,]?\s*$", _FLAGS),
    # Signature and record labels
    re.compile(
        r"\b(?:sig|signed|sign[ée]e?|firma|firmado|podpis|witness|t[ée]moin|testigo|[śs]wiadek|"
        r"minutes|counsell?ed\s+by|filed\s+by|entered\s+by|ordering|requesting|attending|cc)"
        r"\s*[:.]?\s*(?:by\s+)?$",
        _FLAGS,
    ),
    # An agent introducing themself: "AGENT: Billing, this is Jon."
    re.compile(
        r"(?:^|\n)\s*(?:agent|agente|staff|reception|receptionist|r[ée]ceptionniste|recepcja|נציג|נציגה)"
        r"\s*:[^\n]*?\b(?:this\s+is|it['’]?s|my\s+name\s+is|i['’]?m|c['’]est|je\s+suis|soy|"
        r"(?:le\s+)?habla|m[óo]wi|tu|z\s+tej\s+strony|כאן|מדברת)\s*$",
        _FLAGS,
    ),
    # Asking for a staff member: "can I speak to will?", "a message for Beth"
    re.compile(
        r"\b(?:speak|talk)\s+(?:to|with)\s*$|\bask\s+for\s*$|\bmessage\s+for\s*$|"
        r"\btransfer\w*\s+(?:you\s+)?to\s*$|\bparler\s+(?:à|avec)\s*$|\bhablar\s+con\s*$|"
        r"\brozmawia[ćc]\s+z\s*$|\b(?:voicemails?|messages?)\s+(?:with|for)\s*$|"
        r"\b(?:pass(?:\s+this)?\s+(?:on\s+)?to|forward(?:ed)?\s+(?:this\s+)?to|transmettre\s+[àa]|"
        r"reenviar\s+a|pasar\s+a|przeka[żz]\w*\s+(?:to\s+)?)\s*$",
        _FLAGS,
    ),
]
_LIST_TAIL = re.compile(r"(?:[^\W\d_]\.\s*)?[^\W\d_]+(?:[\s\-][^\W\d_]+)?\s*(?:,|&|\band\b|\bet\b|\by\b|\bi\b)\s*$")
_CUE_WORDS = re.compile(rf"^(?:{_PERSON_ROLE}|{_DEPT})$", _FLAGS)


def _name_words(text: str) -> tuple[list[str], list[str]]:
    """(words of two or more letters, initials), lowercased, without connectors."""
    words, initials = [], []
    for w in _WORD.findall(text):
        # "Félix" and "Felix" are the same staff member.
        lw = "".join(c for c in unicodedata.normalize("NFKD", w.lower()) if not unicodedata.combining(c))
        if lw in _CONNECTORS:
            continue
        (initials if len(lw) == 1 else words).append(lw)
    return words, initials


@dataclass
class StaffList:
    names: Iterable[str] = ()
    need_context: bool = True
    _people: list[tuple[frozenset[str], frozenset[str]]] = field(init=False, default_factory=list)
    _words: frozenset[str] = field(init=False, default=frozenset())

    def __post_init__(self) -> None:
        for n in self.names:
            words, initials = _name_words(n)
            if words:
                self._people.append((frozenset(words), frozenset(w[0] for w in words) | frozenset(initials)))
        self._words = frozenset(w for p, _ in self._people for w in p)

    def __bool__(self) -> bool:
        return bool(self._people)

    def passes(self, text: str, e: Entity, cued: set[str]) -> bool:
        """True if this name span is a staff member. ``cued`` comes from :meth:`cued_words`."""
        all_words, initials = _name_words(e.text)
        words = [w for w in all_words if not _CUE_WORDS.match(w)]
        inner_cue = len(words) < len(all_words)  # the span holds the cue: "Jocelyn in billing"
        if not words or not all(w in self._words for w in words):
            return False
        # Every initial must belong to a staff member who has one of the words ("T. Kowalski").
        for i in initials:
            if not any(i in inits and p & set(words) for p, inits in self._people):
                return False
        if len(words) >= 2 and any(set(words) <= p for p, _ in self._people):
            return True  # a full name: "Carla Benitez", "Benitez, Carla"
        if len(words) == 1 and initials and any(
            words[0] in p and set(initials) <= {w[0] for w in p if w != words[0]} for p, _ in self._people
        ):
            return True  # "C. Nakamura", "Okafor, G", "Carmen R.", "Sam K"
        if not self.need_context:
            return True
        if inner_cue or self._has_cue(text, e.start, e.end):
            return True
        return all(w in cued for w in words)

    def cued_words(self, text: str, spans: Iterable[Entity]) -> set[str]:
        """Staff words that appear with a cue somewhere in this text."""
        out: set[str] = set()
        for e in spans:
            words = [w for w in _name_words(e.text)[0] if w in self._words]
            if words and self._has_cue(text, e.start, e.end):
                out.update(words)
        return out

    @staticmethod
    def _has_cue(text: str, start: int, end: int) -> bool:
        after = text[end : end + 60]
        line_start = text.rfind("\n", 0, start) + 1
        before = text[max(line_start, start - 120) : start]
        if any(p.search(after) for p in _AFTER) or any(p.search(before) for p in _BEFORE):
            return True
        # Later names in a list after the cue: "Sig: T. Kowalski, M. Reyes".
        for _ in range(3):
            shorter = _LIST_TAIL.sub("", before)
            if shorter == before:
                return False
            before = shorter
            if any(p.search(before) for p in _BEFORE):
                return True
        return False
