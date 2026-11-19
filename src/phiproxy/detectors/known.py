"""Known-entity detection: match the identifiers you already hold for this patient.

The application usually knows who the conversation is about (the patient's name,
date of birth, phone, health card number...). Matching those exact values is the
highest-recall, lowest-cost layer: it catches casual first names, lowercase
spellings and one-letter typos that generic NER misses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Mapping, Optional, Sequence, Union

from ..entities import Entity, EntityType
from . import _hebrew

_HEBREW = re.compile(r"[\u0590-\u05FF]")

# First names that are also common English words. A lowercase match of these
# ("I have hope") is not treated as the name; a capitalized one is.
COMMON_WORD_NAMES = {
    "hope", "faith", "grace", "joy", "will", "may", "june", "april", "rose", "mark", "bill",
    "art", "page", "sky", "summer", "autumn", "dawn", "eve", "ray", "rich", "max", "pat",
    "sue", "hunter", "chase", "lane", "brook", "river", "star", "sunny", "honey", "ginger",
    "iris", "lily", "daisy", "ivy", "ruby", "amber", "crystal", "angel", "major", "young",
    "white", "black", "brown", "green", "long", "short", "little", "king", "price", "cash",
    "love", "christian", "miles", "frank", "jean", "gay", "deb", "dick", "guy", "an", "bo",
    "winter", "spring", "storm", "rain", "sage", "wren", "robin", "jade", "pearl", "hazel", "olive",
    "precious", "blessing", "destiny", "harmony", "patience", "charity", "mercy", "noble", "royal",
}

# Particles inside a surname ("Lucía de la Cruz", "Jan van der Berg"): they match as part of
# the full name, never alone (a lone "de" is the Spanish word).
NAME_PARTICLES = {
    "de", "del", "della", "di", "da", "du", "des", "la", "le", "los", "las", "van", "von",
    "der", "den", "ter", "ten", "dos", "das", "do", "bin", "ibn", "el",
}

# True particles: a middle one is matched alone only when it is capitalised in the text
# ("Van called" for "Nguyen Van Anh", a given name); the lowercase word is the ordinary word.
_LOWER_PARTICLES = frozenset("de la del van von der da di du le bin ibn al".split())

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
]


def _damerau_leq1(a: str, b: str) -> bool:
    """True if a and b are within one edit (insert, delete, substitute, adjacent swap)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        if len(diff) == 2 and diff[1] == diff[0] + 1:
            i, j = diff
            return a[i] == b[j] and a[j] == b[i]
        return False
    if la > lb:
        a, b = b, a
    # b is longer by one: try deleting each char of b
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def _date_variants(d: date) -> list[str]:
    m = _MONTH_NAMES[d.month - 1]
    mon = m[:3]
    return [
        d.isoformat(),
        f"{d.month}/{d.day}/{d.year}",
        f"{d.month:02d}/{d.day:02d}/{d.year}",
        f"{d.day}/{d.month}/{d.year}",
        f"{d.day:02d}/{d.month:02d}/{d.year}",
        f"{d.month}/{d.day}/{d.year % 100:02d}",
        f"{d.month:02d}/{d.day:02d}/{d.year % 100:02d}",
        f"{d.month}-{d.day}-{d.year}",
        f"{d.day}.{d.month}.{d.year}",
        f"{m} {d.day}, {d.year}",
        f"{m} {d.day} {d.year}",
        f"{mon} {d.day}, {d.year}",
        f"{mon} {d.day} {d.year}",
        f"{mon}. {d.day}, {d.year}",
        f"{d.day} {m} {d.year}",
        f"{d.day} {mon} {d.year}",
        f"{m} {d.day}",
        f"{mon} {d.day}",
    ]


DateLike = Union[date, str]


@dataclass
class KnownEntities:
    """Identifiers the application already holds for the people in this conversation.

    All fields are optional. Pass whatever you have; more is better.
    """

    names: Sequence[str] = ()  # full names of the patient, partner, donor, ...
    phones: Sequence[str] = ()
    emails: Sequence[str] = ()
    dates_of_birth: Sequence[DateLike] = ()
    identifiers: Sequence[str] = ()  # health card, MRN, chart #, donor ID, account #
    addresses: Sequence[str] = ()
    other: Mapping[str, Sequence[str]] = field(default_factory=dict)  # EntityType name -> values

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "KnownEntities":
        def seq(key: str) -> list:
            v = data.get(key) or []
            return [v] if isinstance(v, (str, date)) else list(v)  # type: ignore[arg-type]

        return cls(
            names=seq("names"),
            phones=seq("phones"),
            emails=seq("emails"),
            dates_of_birth=seq("dates_of_birth"),
            identifiers=seq("identifiers"),
            addresses=seq("addresses"),
            other=dict(data.get("other") or {}),  # type: ignore[arg-type]
        )

    def is_empty(self) -> bool:
        return not any(
            [self.names, self.phones, self.emails, self.dates_of_birth,
             self.identifiers, self.addresses, self.other]
        )


def _flex_pattern(value: str) -> str:
    """Regex for a value where spaces, dashes and dots between characters are optional."""
    chars = [re.escape(c) for c in re.sub(r"[\s\-.]", "", value)]
    return r"[\s\-.]?".join(chars)


@dataclass
class KnownEntityDetector:
    known: KnownEntities
    name: str = "known"
    fuzzy_names: bool = True  # allow one typo against record names of 5+ letters

    def detect(self, text: str) -> list[Entity]:
        out: list[Entity] = []
        k = self.known
        out += self._names(text, k.names)
        for p in k.phones:
            digits = re.sub(r"\D", "", p)
            if len(digits) >= 10:
                digits = digits[-10:]
                pat = (
                    r"(?<!\d)(?:\+?1[\s.\-]?)?\(?" + digits[:3] + r"\)?[\s.\-]?"
                    + digits[3:6] + r"[\s.\-]?" + digits[6:] + r"(?!\d)"
                )
                out += self._find(text, pat, EntityType.PHONE)
            elif len(digits) >= 7:
                out += self._find(text, r"(?<!\d)" + _flex_pattern(digits) + r"(?!\d)", EntityType.PHONE)
        for e in k.emails:
            out += self._find(text, re.escape(e), EntityType.EMAIL, re.IGNORECASE)
        for d in k.dates_of_birth:
            out += self._dates(text, d)
        for ident in k.identifiers:
            if len(re.sub(r"[\s\-.]", "", ident)) >= 4:
                out += self._find(text, r"(?<![A-Za-z0-9])" + _flex_pattern(ident) + r"(?![A-Za-z0-9])",
                                  EntityType.ID, re.IGNORECASE)
        for a in k.addresses:
            pat = r"\s+".join(re.escape(w) for w in a.split())
            out += self._find(text, pat, EntityType.ADDRESS, re.IGNORECASE)
        for type_name, values in k.other.items():
            t = EntityType(type_name)
            for v in values:
                out += self._find(text, re.escape(v), t, re.IGNORECASE)
        return out

    def _find(self, text: str, pattern: str, t: EntityType, flags: int = 0,
              canonical: Optional[str] = None) -> list[Entity]:
        return [
            Entity(t, m.start(), m.end(), m.group(0), self.name, canonical=canonical)
            for m in re.finditer(pattern, text, flags)
            if m.end() > m.start()
        ]

    def _dates(self, text: str, d: DateLike) -> list[Entity]:
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                return self._find(text, re.escape(d), EntityType.DATE, re.IGNORECASE)
        out: list[Entity] = []
        for v in _date_variants(d):
            out += self._find(text, r"(?<![\d/\-.])" + re.escape(v) + r"(?![\d])", EntityType.DATE, re.IGNORECASE)
        return out

    def _names(self, text: str, names: Iterable[str]) -> list[Entity]:
        out: list[Entity] = []
        tokens: dict[str, str] = {}  # lowercase -> spelling from the record
        mid_only: set[str] = set()  # tokens that are only a middle particle of a record name
        outer: set[str] = set()
        for full in names:
            full = full.strip()
            if not full:
                continue
            # The full name first (also catches it across line breaks / extra spaces).
            parts = full.split()
            pat = r"\b" + r"\s+".join(re.escape(p) for p in parts) + r"\b"
            out += self._find(text, pat, EntityType.NAME, re.IGNORECASE, canonical=" ".join(parts))
            pieces = re.split(r"[\s\-]+", full)
            for i, p in enumerate([*pieces, *re.findall(r"\w+-\w+", full)]):
                p = p.strip(".,'")
                # Short Hebrew name parts are also words: בן (son), בת, טל (dew), גל (wave).
                # Only a particle in the middle of the name is left out ("de", "la" in "Lucía de la
                # Cruz"); a first or last part ("Das", "Van", "Le") is a name on its own.
                if i >= len(pieces) or not (p.lower() in NAME_PARTICLES and 0 < i < len(pieces) - 1):
                    outer.add(p.lower())
                elif p.lower() in _LOWER_PARTICLES:
                    mid_only.add(p.lower())
                if len(p) >= 2 and not (_HEBREW.search(p) and len(p) <= 2 and p != full):
                    tokens.setdefault(p.lower(), p)
                    # The same name in the other script: "Noa" <-> "נועה".
                    for other in _hebrew.LATIN_TO_HEBREW.get(p.lower(), set()) | _hebrew.HEBREW_TO_LATIN.get(p, set()):
                        tokens.setdefault(other.lower(), "")  # "": unmask as written in the text
        if not tokens:
            return out
        words = []
        for m in re.finditer(r"[^\W\d_](?:[^\W\d_]|['\-](?=[^\W\d_]))*", text):
            words.append((m.start(), m.group(0)))
            if "-" in m.group(0) and m.group(0).lower() not in tokens:
                # "Kowalska-Nowak": each part on its own too.
                for p in re.finditer(r"[^\-]+", m.group(0)):
                    words.append((m.start() + p.start(), p.group(0)))
        for wstart, raw in words:
            lead = 0
            word = raw
            if word not in tokens and word[0] in "ובלמהשכ":
                # Hebrew prefixes stay outside the mask: "ולנועה" -> "נועה".
                for rest in _hebrew.unprefixed(word):
                    if rest in tokens:
                        lead, word = len(word) - len(rest), rest
                        break
            if word.lower().endswith("'s"):  # possessive: keep the 's outside the mask
                word = word[:-2]
            if len(word) < 2:
                continue
            lw = word.lower()
            match = tokens.get(lw)
            if match is None and self.fuzzy_names and len(lw) >= 4 and not _HEBREW.search(lw):
                match = next(
                    (orig for t, orig in tokens.items()
                     if len(t) >= 5 and t[0] == lw[0] and _damerau_leq1(lw, t)),
                    None,
                )
            if match is None:
                continue
            if lw in COMMON_WORD_NAMES and not word[0].isupper():
                continue
            if lw in mid_only and lw not in outer and word == lw:
                continue  # a lowercase middle particle is the ordinary word
            start = wstart + lead
            # The particles in front of a surname belong to it: "de la Cruz", "El Amrani".
            first = start
            while True:
                prev = re.search(r"([^\W\d_]+)[ \t]+$", text[max(0, first - 12) : first])
                if not prev or prev.group(1).lower() not in NAME_PARTICLES:
                    break
                first -= len(prev.group(0))
            if first != start:
                out.append(Entity(EntityType.NAME, first, start + len(word), text[first : start + len(word)], self.name))
                continue
            out.append(Entity(EntityType.NAME, start, start + len(word), word, self.name, canonical=match or None))
        return out
