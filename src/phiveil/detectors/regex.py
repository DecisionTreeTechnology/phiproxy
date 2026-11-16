"""Pattern-based detection for identifiers with a fixed shape.

Everything here runs locally with the standard library. Patterns aim for recall:
a false positive costs some answer quality, a false negative leaks PHI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..entities import Entity, EntityType

_MONTHS = (
    "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    "sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
# Month words that are also ordinary English words; only count them when capitalized.
_AMBIGUOUS_MONTHS = {"may", "mar", "march", "jan", "june", "july", "aug", "sep", "dec"}

_US_STATES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|"
    "NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
)

_STREET_SUFFIX = (
    "street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct|crescent|cres|"
    "way|place|pl|terrace|ter|circle|cir|parkway|pkwy|highway|hwy|trail|trl|square|sq"
)

# Capitalized words that follow "this is", "Dr." etc. but are not names.
_NOT_NAMES = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "today", "tomorrow", "yesterday",
    "hi", "hello", "hey", "thanks", "thank", "please", "yes", "no", "ok", "okay",
    "the", "a", "an", "my", "your", "our", "it", "this", "that", "not", "just", "so",
    "clinic", "office", "doctor", "nurse", "team", "everyone", "all", "regarding",
    "urgent", "important", "about", "re", "fwd", "ivf", "iui", "fet",
}

_RELATIONS = (
    "husband|wife|partner|spouse|boyfriend|girlfriend|fianc[eé]e?|son|daughter|"
    "mom|mother|mum|dad|father|sister|brother|friend|donor|surrogate|carrier|"
    "grandmother|grandfather|aunt|uncle|cousin|niece|nephew|boss|employer|coworker|colleague"
)

_NAME = r"[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?"

_DIGIT_WORDS = "zero|oh|one|two|three|four|five|six|seven|eight|nine"
_ORDINAL_WORDS = (
    "(?:twenty|thirty)[\\s\\-]?(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)|"
    "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|"
    "thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|thirtieth"
)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass
class _Rule:
    type: EntityType
    pattern: re.Pattern[str]
    group: int = 0  # which capture group is the identifier
    check: Optional[Callable[[re.Match[str]], bool]] = None


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _sin_check(m: re.Match[str]) -> bool:
    d = _digits(m.group(0))
    return len(d) == 9 and _luhn_ok(d)


def _ssn_check(m: re.Match[str]) -> bool:
    a, b, c = m.group(1), m.group(2), m.group(3)
    return a not in ("000", "666") and not a.startswith("9") and b != "00" and c != "0000"


def _month_check(m: re.Match[str]) -> bool:
    month = m.group("month")
    return not (month.lower() in _AMBIGUOUS_MONTHS and month[0].islower())


def _name_check(m: re.Match[str]) -> bool:
    first = m.group("name").split()[0].lower()
    return first not in _NOT_NAMES


def _build_rules() -> list[_Rule]:
    I = re.IGNORECASE
    R: list[_Rule] = []

    def add(t: EntityType, pat: str, flags: int = 0, group: int = 0, check=None) -> None:
        R.append(_Rule(t, re.compile(pat, flags), group, check))

    add(EntityType.EMAIL, r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
    add(EntityType.URL, r"\bhttps?://[^\s<>\"')\]]+|\bwww\.[^\s<>\"')\]]+", I)
    add(EntityType.IP_ADDRESS, r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")

    # Keyword-anchored identifiers. The keyword stays; only the value is masked.
    add(
        EntityType.HEALTH_CARD,
        r"\b(?:ohip|health\s*card|hcn|health\s*(?:insurance\s*)?(?:number|no\.?|#)|phn|ramq|carte\s*soleil)"
        r"(?:\s*(?:number|no\.?|#))?\s*(?:is|:|#)?\s*([A-Z]{0,4}[\s\-]?\d[\d\s\-]{6,24}\d(?:[\s\-]?[A-Z]{2})?)\b",
        I,
        group=1,
    )
    add(
        EntityType.MRN,
        r"\b(?:mrn|medical\s*record(?:\s*(?:number|no\.?|#))?|chart\s*(?:number|no\.?|#)|"
        r"patient\s*(?:id|number|no\.?|#))\s*(?:is|:|#)?\s*([A-Z0-9][A-Z0-9\-]{3,19})\b",
        I,
        group=1,
    )
    add(
        EntityType.DONOR_ID,
        r"\b(?:donor|embryo|egg\s*bank|sperm\s*bank|straw)\s*(?:id|code|number|no\.?|#)\s*(?:is|:|#)?\s*"
        r"([A-Z0-9][A-Z0-9\-]{2,19})\b",
        I,
        group=1,
    )
    # "donor D-4521", "donor #4521": no keyword, but the value has a digit.
    add(
        EntityType.DONOR_ID,
        r"\b(?:donor|embryo)\s+#?\s*((?=[A-Z0-9\-]*\d)[A-Z]{0,4}-?\d[A-Z0-9\-]{2,15})\b",
        I,
        group=1,
    )
    add(
        EntityType.ACCOUNT,
        r"\b(?:account|acct|policy|member|insurance\s*id|claim)\s*(?:number|no\.?|#|id)?\s*(?:is|:|#)\s*"
        r"([A-Z0-9][A-Z0-9\-]{3,24})\b",
        I,
        group=1,
    )

    # Quebec RAMQ: 4 letters + 8 digits.
    add(EntityType.HEALTH_CARD, r"\b[A-Z]{4}\s?\d{4}\s?\d{4}\b")
    # Ontario OHIP in its printed 4-3-3 grouping, optional 2-letter version code.
    add(EntityType.HEALTH_CARD, r"\b\d{4}[\s\-]\d{3}[\s\-]\d{3}(?:[\s\-]?[A-Z]{2})?\b")

    add(EntityType.SSN, r"\b(\d{3})-(\d{2})-(\d{4})\b", check=_ssn_check)
    add(EntityType.SIN, r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}\b", check=_sin_check)

    # North American phone numbers, any common formatting.
    add(
        EntityType.PHONE,
        r"(?<![\w+])(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}\b"
        r"(?:\s*(?:x|ext\.?)\s*\d{1,5})?",
        I,
    )
    # International numbers written with a leading +.
    add(EntityType.PHONE, r"(?<!\w)\+(?:[2-9]\d{0,2})[\s.\-]?\d(?:[\s.\-]?\d){6,12}\b")

    # Numbers spoken digit by digit (call transcripts): "four one six five five five ..."
    add(EntityType.PHONE, rf"\b(?:{_DIGIT_WORDS})(?:[\s,\-]+(?:{_DIGIT_WORDS})){{6,11}}\b", I)

    # Dates. Year-only is not PHI under Safe Harbor, so it is not matched.
    add(EntityType.DATE, r"\b\d{4}-\d{1,2}-\d{1,2}\b")
    add(EntityType.DATE, r"\b\d{1,2}[/\-.]\d{1,2}[/\-.](?:\d{4}|\d{2})\b")
    add(
        EntityType.DATE,
        rf"\b(?P<month>{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
        I,
        check=_month_check,
    )
    add(
        EntityType.DATE,
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<month>{_MONTHS})\.?(?:,?\s+\d{{4}})?\b",
        I,
        check=_month_check,
    )
    # Spoken dates: "march fifteenth 1988", "the twenty first of may". A following
    # ordinal word makes even lowercase "march"/"may" unambiguous.
    add(
        EntityType.DATE,
        rf"\b(?P<month>{_MONTHS})\s+(?:the\s+)?(?:{_ORDINAL_WORDS})(?:,?\s+(?:\d{{4}}|(?:nineteen|twenty)[\w\s\-]{{3,20}}?(?=\W|$)))?",
        I,
    )
    add(EntityType.DATE, rf"\b(?:{_ORDINAL_WORDS})\s+of\s+(?P<month>{_MONTHS})\b(?:,?\s+\d{{4}})?", I)
    # Short numeric dates like 3/14 (no year).
    add(EntityType.DATE, r"(?<![\d/])\b(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])\b(?![/\d])")

    add(EntityType.AGE, r"\b(?:9\d|1[01]\d)\s*(?:-\s*)?(?:years?[\s\-]*old|yrs?|y/?o)\b", I)

    add(
        EntityType.ADDRESS,
        rf"\b\d{{1,6}}\s+(?:[A-Za-z0-9'\-]+\s+){{0,3}}(?:{_STREET_SUFFIX})\b\.?"
        r"(?:,?\s*(?:apt|apartment|unit|suite|ste|#)\.?\s*[A-Za-z0-9\-]+)?",
        I,
    )
    add(EntityType.ADDRESS, r"\b(?:p\.?\s?o\.?\s*box|postal\s*box)\s*\d+\b", I)

    # Canadian postal code.
    add(
        EntityType.POSTAL_CODE,
        r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][\s\-]?\d[ABCEGHJ-NPRSTV-Z]\d\b",
        I,
    )
    # US ZIP only with context (a bare 5-digit number is too ambiguous).
    add(EntityType.ZIP, rf"\b(?:{_US_STATES})\s+(\d{{5}}(?:-\d{{4}})?)\b", group=1)
    add(EntityType.ZIP, r"\bzip(?:\s*code)?\s*(?:is|:)?\s*(\d{5}(?:-\d{4})?)\b", I, group=1)

    # Names introduced by context. Presidio or the known-entity list catch the rest.
    add(
        EntityType.NAME,
        r"\b(?i:my\s+name\s+is|name'?s|this\s+is|it'?s|i\s+am|i'm|signed|regards|sincerely|"
        r"thanks|thank\s+you|cheers)\s*,?\s+(?P<name>" + _NAME + r")",
        group=0,
        check=_name_check,
    )
    add(
        EntityType.NAME,
        r"\b(?i:my\s+(?:" + _RELATIONS + r")(?:'s\s+name\s+is|\s+is|,)?)\s+(?P<name>" + _NAME + r")",
        group=0,
        check=_name_check,
    )
    add(
        EntityType.NAME,
        r"\b(?i:patient|pt|client|for|from|to|dear|hi|hello|hey)\s*:?\s+(?P<name>" + _NAME + r")",
        group=0,
        check=_name_check,
    )
    add(
        EntityType.PROVIDER,
        r"\b(?:Dr|Doctor|Nurse|NP|RN|Mr|Mrs|Ms|Miss|Mx)\.?\s+(?P<name>" + _NAME + r")",
        group=0,
        check=_name_check,
    )
    return R


_RULES = _build_rules()

# Rules where only the named "name" group should be masked.
_NAME_GROUP_TYPES = {EntityType.NAME, EntityType.PROVIDER}


@dataclass
class RegexDetector:
    """Detects fixed-shape identifiers (phones, emails, dates, health card numbers, ...)."""

    name: str = "regex"
    enabled: Optional[set[EntityType]] = None  # None = all
    extra_rules: list[_Rule] = field(default_factory=list)

    def detect(self, text: str) -> list[Entity]:
        out: list[Entity] = []
        for rule in [*_RULES, *self.extra_rules]:
            if self.enabled is not None and rule.type not in self.enabled:
                continue
            for m in rule.pattern.finditer(text):
                if rule.check is not None and not rule.check(m):
                    continue
                if rule.type in _NAME_GROUP_TYPES and "name" in m.groupdict():
                    start, end = m.span("name")
                else:
                    start, end = m.span(rule.group)
                if end <= start:
                    continue
                out.append(Entity(rule.type, start, end, text[start:end], self.name))
        return out
