"""Identifiers read out loud in call transcripts.

Callers say numbers in groups ("four one six... five five five... one one
seven", "eight hundred, five five five, oh one four two"), in compound words
("dziewięćset pięć, pięćset pięćdziesiąt pięć"), and spell letters, sometimes
with the phonetic alphabet ("november sierra hotel four zero zero ...").

This module turns each spoken run into digits and letters ("4165550117",
"T3A4B7", "NSH4002187730"), keeps where every character came from, checks the
result against strict identifier shapes, and returns spans in the original
text. A spoken street number is rewritten so the street-address rule can see it
("eighteen forty two west cermak road" -> "1842 west cermak road").
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from ..entities import Entity, EntityType

_UNITS = {
    # en
    "zero": 0, "oh": 0, "o": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
    # fr
    "zéro": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "sept": 7, "huit": 8, "neuf": 9,
    # es
    "cero": 0, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    # pl
    "jeden": 1, "jedna": 1, "dwa": 2, "dwie": 2, "trzy": 3, "cztery": 4, "pięć": 5,
    "sześć": 6, "siedem": 7, "osiem": 8, "dziewięć": 9,
    # he
    "אפס": 0, "אחת": 1, "אחד": 1, "שתיים": 2, "שניים": 2, "שתים": 2, "שלוש": 3, "שלושה": 3,
    "ארבע": 4, "ארבעה": 4, "חמש": 5, "חמישה": 5, "שש": 6, "שישה": 6, "שבע": 7, "שבעה": 7,
    "שמונה": 8, "תשע": 9, "תשעה": 9,
}
_TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciséis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "dziesięć": 10, "jedenaście": 11, "dwanaście": 12, "trzynaście": 13, "czternaście": 14,
    "piętnaście": 15, "szesnaście": 16, "siedemnaście": 17, "osiemnaście": 18,
    "dziewiętnaście": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
    "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
    "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90,
    "dwadzieścia": 20, "trzydzieści": 30, "czterdzieści": 40, "pięćdziesiąt": 50,
    "sześćdziesiąt": 60, "siedemdziesiąt": 70, "osiemdziesiąt": 80, "dziewięćdziesiąt": 90,
}
# Words that are a whole number of hundreds on their own.
_HUNDREDS = {
    "cent": 100, "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300,
    "cuatrocientos": 400, "quinientos": 500, "seiscientos": 600, "setecientos": 700,
    "ochocientos": 800, "novecientos": 900,
    "sto": 100, "dwieście": 200, "trzysta": 300, "czterysta": 400, "pięćset": 500,
    "sześćset": 600, "siedemset": 700, "osiemset": 800, "dziewięćset": 900,
}
_MULTIPLIERS = {"hundred": 100, "thousand": 1000, "mille": 1000, "mil": 1000, "tysiąc": 1000}
_REPEAT = {"double": 2, "triple": 3, "doble": 2, "triple": 3, "podwójne": 2}
_NATO = {
    "alpha": "A", "alfa": "A", "bravo": "B", "charlie": "C", "delta": "D", "echo": "E",
    "foxtrot": "F", "golf": "G", "hotel": "H", "india": "I", "juliet": "J", "juliett": "J",
    "kilo": "K", "lima": "L", "mike": "M", "november": "N", "oscar": "O", "papa": "P",
    "quebec": "Q", "romeo": "R", "sierra": "S", "tango": "T", "uniform": "U",
    "victor": "V", "whiskey": "W", "whisky": "W", "xray": "X", "x-ray": "X",
    "yankee": "Y", "zulu": "Z",
}
# Spoken separators inside one identifier.
_JOINERS = {
    "dash", "hyphen", "slash", "space", "then", "and", "y", "et", "i",
    "tiret", "trait", "guion", "guión", "myślnik", "kreska", "מקף",
}
_DOT_WORDS = {"dot", "point", "punto", "kropka", "נקודה"}

_PAUSES = (",", "...", "…", "-", "/")
_TOKEN = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*|\d+|\.\.\.|…|[,.\-/]")
_HE_PREFIX = re.compile(r"^[ולבמש](?=[֐-׿]{2,})")


def _number_word(w: str) -> Optional[tuple[str, int]]:
    """(kind, value) for one lowercased word, or None."""
    if w in _UNITS:
        return "unit", _UNITS[w]
    if w in _TEENS:
        return "teen", _TEENS[w]
    if w in _TENS:
        return "tens", _TENS[w]
    if w in _HUNDREDS:
        return "hundreds", _HUNDREDS[w]
    if w in _MULTIPLIERS:
        return "mult", _MULTIPLIERS[w]
    if w in _REPEAT:
        return "repeat", _REPEAT[w]
    if w.isdigit():
        return "digits", int(w)
    if len(w) > 2 and _HE_PREFIX.match(w) and w[1:] in _UNITS:
        return "unit", _UNITS[w[1:]]
    return None


class _Run:
    """Spoken characters with the text span each came from."""

    def __init__(self) -> None:
        self.chars: list[tuple[str, int, int]] = []  # (char, start, end)
        self.groups: list[tuple[str, int, int]] = []  # pending number group
        self.open: Optional[str] = None  # kind of the open group ("tens", "hundreds", ...)
        self.value = 0
        self.span = (0, 0)
        self.repeat = 1
        self.spoken = 0  # number words and phonetic letters (not written digits)

    def _flush(self) -> None:
        if self.open is not None:
            s, e = self.span
            for ch in str(self.value):
                self.chars.append((ch, s, e))
        self.open = None

    def number(self, kind: str, v: int, s: int, e: int, raw: str = "") -> None:
        if kind == "repeat":
            self._flush()
            self.repeat = v
            return
        if kind == "digits":
            self._flush()
            for ch in raw:
                self.chars.append((ch, s, e))
            return
        if kind == "unit" and self.repeat > 1:
            self._flush()
            for _ in range(self.repeat):
                self.chars.append((str(v), s, e))
            self.repeat = 1
            return
        if kind == "mult":
            if self.open is not None:
                self.value *= v
                self.span = (self.span[0], e)
                self.open = "hundreds"
            elif self.chars and self.chars[-1][0].isdigit():
                ch, cs, _ = self.chars.pop()
                self.value, self.span, self.open = int(ch) * v, (cs, e), "hundreds"
            return
        if self.open == "hundreds" and kind in ("unit", "teen", "tens"):
            self.value += v
            self.span = (self.span[0], e)
            self.open = "tens" if kind == "tens" else "done"
            if kind != "tens":
                self._flush()
            return
        if self.open == "tens" and kind == "unit" and self.value % 10 == 0:
            self.value += v
            self.span = (self.span[0], e)
            self._flush()
            return
        self._flush()
        if kind == "unit":
            self.chars.append((str(v), s, e))
        else:
            self.value, self.span, self.open = v, (s, e), kind

    def letter(self, ch: str, s: int, e: int) -> None:
        self._flush()
        self.chars.append((ch.upper(), s, e))

    def dot(self, s: int, e: int) -> None:
        self._flush()
        self.chars.append((".", s, e))

    def finish(self) -> list[tuple[str, int, int]]:
        self._flush()
        while self.chars and self.chars[-1][0] == ".":
            self.chars.pop()
        return self.chars


def _runs(text: str) -> list[list[tuple[str, int, int]]]:
    """Every maximal spoken run, as (char, start, end) lists."""
    out = []
    run = _Run()
    joins = 0  # separator words since the last spoken character ("and then")

    def close() -> None:
        nonlocal run, joins
        chars = run.finish()
        # Identifiers written in figures are the pattern rules' job.
        if chars and run.spoken:
            out.append(chars)
        run = _Run()
        joins = 0

    tokens = list(_TOKEN.finditer(text))
    prev_end = 0
    for i, m in enumerate(tokens):
        raw = m.group(0)
        w = raw.lower()
        s, e = m.span()
        if text[prev_end:s].strip():
            close()  # "9:30", "$350", "(": not a pause inside a spoken number
        prev_end = e
        if raw in _PAUSES or (raw == "." and (run.chars or run.open)):
            run._flush()  # a pause ends a number group: "eight hundred, five five five"
            continue
        if raw == ".":
            close()
            continue
        parts = w.split("-") if "-" in w and w not in _NATO else [w]
        kinds = [_number_word(p) for p in parts]
        if all(kinds):
            for (kind, v) in kinds:  # type: ignore[misc]
                run.number(kind, v, s, e, raw if kind == "digits" else "")
                # A lone "o" is a zero only beside other spoken numbers (OCR: "555-O188").
                run.spoken += kind != "digits" and w not in ("o", "oh")
            joins = 0
            continue
        if w in _NATO:
            run.letter(_NATO[w], s, e)
            run.spoken += 1
            joins = 0
            continue
        if len(w) == 1 and w.isalpha() and w.isascii():
            # A single letter belongs to a run only beside a number or another letter.
            nxt = next((t.group(0).lower() for t in tokens[i + 1 :] if t.group(0) not in _PAUSES), "")
            ahead = bool(_number_word(nxt)) or (len(nxt) == 1 and nxt.isalpha()) or nxt in _NATO
            # Lowercase "i" and "a" are also words: "... oh one four two i think".
            if ahead or ((run.chars or run.open) and (raw.isupper() or w not in ("i", "a"))):
                run.letter(w, s, e)
                joins = 0
                continue
        if w in _DOT_WORDS and run.chars:
            run.dot(s, e)
            continue
        if w in _JOINERS and (run.chars or run.open) and joins < 2:
            joins += 1
            continue
        close()
    close()
    return out


def _span(chars: list[tuple[str, int, int]]) -> tuple[int, int]:
    return chars[0][1], chars[-1][2]


# Shapes a spoken run must have to count as an identifier.
_POSTAL = re.compile(r"[A-Z]\d[A-Z]\d[A-Z]\d")
_IP = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")


def _classify(s: str) -> Optional[EntityType]:
    plain = s.replace(".", "")
    digits = sum(c.isdigit() for c in plain)
    letters = sum(c.isalpha() for c in plain)
    if re.fullmatch(r"\d{1,4}[AP]M?", plain):
        return None  # "ten thirty a.m."
    if _IP.fullmatch(s):
        return EntityType.IP_ADDRESS
    if _POSTAL.fullmatch(plain):
        return EntityType.POSTAL_CODE
    if letters == 0:
        if digits in (7, 10) or (digits == 11 and plain[0] == "1"):
            return EntityType.PHONE
        if digits >= 9:
            return EntityType.ACCOUNT if digits >= 13 else EntityType.ID
        return None
    if digits == 10 and letters == 2 and plain[-2:].isalpha():
        return EntityType.HEALTH_CARD
    # Letter-digit codes: chart, donor, member numbers ("C F seven seven eight one").
    if digits >= 4 and digits + letters >= 6 and letters <= digits + 3:
        return EntityType.ID
    return None


def detect(text: str) -> list[Entity]:
    out: list[Entity] = []
    for chars in _runs(text):
        s = "".join(c for c, _, _ in chars)
        t = _classify(s)
        if t is None:
            continue
        start, end = _span(chars)
        out.append(Entity(t, start, end, text[start:end], "regex"))
    return out


def street_numbers(text: str, street: Callable[[str], list[tuple[int, int]]]) -> list[Entity]:
    """Street addresses whose house number is spoken: "eighteen forty two west cermak road"."""
    out: list[Entity] = []
    for chars in _runs(text):
        s = "".join(c for c, _, _ in chars)
        if not s.isdigit() or len(s) > 6:
            continue
        start, end = _span(chars)
        if not re.search(r"[^\W\d_]", text[start:end]):
            continue  # already digits; the plain rule sees it
        shadow = s + text[end : end + 80]
        for a, b in street(shadow):
            if a == 0 and b > len(s):
                stop = end + (b - len(s))
                out.append(Entity(EntityType.ADDRESS, start, stop, text[start:stop], "regex"))
    return out
