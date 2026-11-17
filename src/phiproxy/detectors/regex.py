"""Pattern-based detection for identifiers with a fixed shape.

Everything here runs locally with the standard library. Patterns aim for recall:
a false positive costs some answer quality, a false negative leaks PHI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Callable, Optional

from ..entities import Entity, EntityType
from . import _names, _spoken

_MONTHS = (
    "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    "sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
# Month words that are also ordinary English words; only count them when capitalized.
_AMBIGUOUS_MONTHS = {"may", "mar", "march", "jan", "june", "july", "sep"}

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
    "dr", "dre", "dra", "doctor", "mr", "mrs", "ms", "miss", "mx", "sent", "subject",
    "dear", "i'm", "im", "je", "agent", "user", "bot", "intake", "file", "canada",
}


_DIGIT_WORDS = "zero|oh|one|two|three|four|five|six|seven|eight|nine"
# Digits spoken in French, Spanish, Polish and Hebrew (call transcripts).
_DIGIT_WORDS_ML = (
    "z[ée]ro|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|"
    "cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|"
    "jeden|jedna|dwa|trzy|cztery|pi[eę][cć]|sze[sś][cć]|siedem|osiem|dziewi[eę][cć]|"
    "אפס|אחת|אחד|שתיים|שניים|שתים|שלוש|ארבע|חמש|שש|שבע|שמונה|תשע"
)
_ANY_DIGIT_WORD = f"(?:{_DIGIT_WORDS}|{_DIGIT_WORDS_ML})"
_WEEKDAY = (
    r"(?:monday|mon|tuesday|tues|tue|wednesday|weds|wed|thursday|thurs|thur|thu|friday|fri|"
    r"saturday|sat|sunday|sun)\.?"
)
_WEEKDAY_ML = (
    r"lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
    r"lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo|"
    r"poniedzia[łl]ek|wtorek|[śs]roda|czwartek|pi[ąa]tek|sobota|niedziela|"
    r"יום\s+(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)"
)
# Month names in French, Spanish, Polish (nominative and genitive) and Hebrew.
_MONTHS_ML = (
    "janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre|"
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|se?ptiembre|octubre|noviembre|diciembre|"
    "stycze[nń]|stycznia|luty|lutego|marzec|marca|kwiecie[nń]|kwietnia|maj|maja|czerwiec|czerwca|"
    "lipiec|lipca|sierpie[nń]|sierpnia|wrzesie[nń]|wrze[sś]nia|pa[zź]dziernik|pa[zź]dziernika|"
    "listopad|listopada|grudzie[nń]|grudnia|"
    "ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר"
)
_DAY_CARDINALS = (
    "(?:twenty|thirty)[\\s\\-]?(?:one|two|three|four|five|six|seven|eight|nine)|"
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    "fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty"
)
_TENS = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
_UNITS = "one|two|three|four|five|six|seven|eight|nine"
# "eighty five", "nineteen ninety two", "two thousand one", "oh three".
_SPOKEN_YEAR = (
    rf"(?:(?:nineteen|twenty)[\s\-]+)?(?:(?:{_TENS})(?:[\s\-]+(?:{_UNITS}))?|ten|eleven|twelve|thirteen|"
    rf"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|oh[\s\-]+(?:{_UNITS}))|"
    rf"two\s+thousand(?:\s+and)?(?:\s+(?:{_UNITS}|ten|eleven|twelve|thirteen|fourteen|fifteen))?"
)
_SPOKEN_NUMBER = (
    rf"zero|oh|{_UNITS}|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    rf"nineteen|{_TENS}|thousand|hundred|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|"
    rf"tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|"
    rf"nineteenth|twentieth|thirtieth|jan(?:uary)?|feb(?:ruary)?|march|april|may|june|july|"
    rf"august|september|october|november|december"
)
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



# Days of the month spoken in French and Spanish ("quatorze", "vingt et un",
# "veintitrés", "primero"), Polish ordinals ("trzeciego") and Hebrew numbers.
_DAY_WORDS_FR_ES = (
    r"premier|primero|(?:vingt|trente)(?:[\s\-](?:et[\s\-])?(?:un|deux|trois|quatre|cinq|six|sept|huit|neuf))?|"
    r"dix(?:[\s\-](?:sept|huit|neuf))?|onze|douze|treize|quatorze|quinze|seize|"
    r"un|deux|trois|quatre|cinq|six|sept|huit|neuf|"
    r"uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|"
    r"dieci(?:s[ée]is|siete|ocho|nueve)|veinte|veinti\w+|treinta(?:\s+y\s+uno)?"
)
_DAY_WORDS_PL = (
    r"(?:(?:dwudziest|trzydziest)\w*\s+)?(?:pierwsz|drug|trzec|czwart|pi[ąa]t|sz[óo]st|si[óo]dm|[óo]sm|"
    r"dziewi[ąa]t|dziesi[ąa]t|jedenast|dwunast|trzynast|czternast|pi[ęe]tnast|szesnast|siedemnast|"
    r"osiemnast|dziewi[ęe]tnast|dwudziest|trzydziest)\w*"
)
_DAY_WORDS_HE = r"(?:אחד|אחת|שניים|שתיים|שני|שלושה|שלוש|ארבעה|ארבע|חמישה|חמש|שישה|שש|שבעה|שבע|שמונה|תשעה|תשע|עשרה|עשר|עשרים|שלושים|ו)+"
# Words that make up a spoken year ("mille neuf cent quatre-vingt-huit",
# "mil novecientos noventa y uno", "tysiąc dziewięćset osiemdziesiąty").
_YEAR_WORDS = (
    r"mille|mil|cent|cents|vingts?|trente|quarante|cinquante|soixante|quatre-vingts?(?:-\w+)?|dix-\w+|"
    r"novecientos|ochocientos|dos|uno|una|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
    r"veinte|veinti\w+|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|y|et|"
    r"un|deux|trois|quatre|cinq|six|sept|huit|neuf|onze|douze|treize|quatorze|quinze|seize|"
    r"tysi[ąa]c\w*|dwa|dziewi[ęe][ćc]set|osiemset|\w+dziesi[ąa]t\w*|\w+na[śs]cie|"
    r"(?:pierwsz|drug|trzec|czwart|pi[ąa]t|sz[óo]st|si[óo]dm|[óo]sm|dziewi[ąa]t)\w*|roku|"
    r"אלף|מאות|תשע|שמונה|תשעים|שמונים|ו?אחת|ו?אחד|ו?שתיים|ו?שלוש|ו?ארבע|ו?חמש|ו?שש|ו?שבע|ו?שמונה|ו?תשע"
)


@lru_cache(maxsize=1)
def _places() -> tuple[dict[str, bool], re.Pattern[str]]:
    """Canadian and US places (GeoNames, CC BY 4.0) -> ambiguous flag, and a matcher.

    A place counts only after a location cue ("in", "from", "near", "moved to",
    "à", "près de", "en", "w"...), so "Hamilton" in "Dr. Hamilton" is not a
    place. Names that are also common words ("Normal", "Mobile") must be
    capitalized.
    """
    text = resources.files("phiproxy.data").joinpath("places_ca_us.tsv").read_text(encoding="utf-8")
    names: dict[str, bool] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, flag = line.split("\t")
        names[name.lower()] = flag == "1"
    alternation = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    cue = (
        r"(?:\b(?:in|from|near|to|into|outside(?:\s+of)?|around|towards?|"
        r"[àa]|au|de|pr[èe]s\s+de|en|desde|cerca\s+de|w|we|z|ze|do|pod|ko[łl]o)\s+)"
    )
    pattern = re.compile(rf"{cue}(?P<place>{alternation})(?![\w\-])", re.IGNORECASE)
    return names, pattern


_STREET = (
    rf"\b\d{{1,6}}\s+(?:[A-Za-z0-9'\-]+\s+){{0,3}}(?:{_STREET_SUFFIX})\b\.?"
    r"(?:,?\s*(?:apt|apartment|unit|suite|ste|#)\.?\s*[A-Za-z0-9\-]+)?"
)
_STREET_SUFFIX_RE = re.compile(f"(?:{_STREET_SUFFIX})", re.I)

# "30 with Dr. Lal", "25 mcg per Dr.", "a 5 hour drive": a number, then words that
# cannot be part of a street name, then a street suffix.
_NOT_STREET_WORDS = frozenset(
    """
    with per at am pm a m p and or to for the by on in of from is was
    hour hours hr hrs min mins minute minutes sec day days week weeks month months
    mg mcg ml iu units unit mm cm kg lb lbs oz percent
    """.split()
)


def _street_check(m: re.Match[str]) -> bool:
    words = re.findall(r"[A-Za-z]+", m.group(0))
    for i, w in enumerate(words):  # only the words before the street suffix
        if _STREET_SUFFIX_RE.fullmatch(w):
            words = words[:i]
            break
    return not any(w.lower() in _NOT_STREET_WORDS for w in words)


def _place_check(m: re.Match[str]) -> bool:
    names, _ = _places()
    place = m.group("place")
    return not names.get(place.lower(), False) or place[0].isupper()


def _build_rules() -> list[_Rule]:
    I = re.IGNORECASE
    R: list[_Rule] = []

    def add(t: EntityType, pat: str, flags: int = 0, group: int = 0, check=None) -> None:
        R.append(_Rule(t, re.compile(pat, flags), group, check))

    add(EntityType.EMAIL, r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
    add(EntityType.URL, r"\bhttps?://[^\s<>\"')\]]+|\bwww\.[^\s<>\"')\]]+", I)
    add(EntityType.URL, r"\b[a-z0-9\-]+\.(?:com|org|net|ca|io|me)/[^\s<>\"')\]]+", I)
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
        r"patient\s*(?:id|number|no\.?|#))\s*(?:is|:|#)?\s*((?=[A-Z0-9\-]*\d)[A-Z0-9][A-Z0-9\-]{3,19})\b",
        I,
        group=1,
    )
    add(
        EntityType.DONOR_ID,
        r"\b(?:donor|embryo|egg\s*bank|sperm\s*bank|straw)\s*(?:id|code|number|no\.?|#)\s*(?:is|:|#)?\s*"
        r"((?=[A-Z0-9\-]*\d)[A-Z0-9][A-Z0-9\-]{2,19})\b",
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
        r"\b(?:account|acct|policy|member|insurance\s*id|claim|group|certificate|certificat|contrat|"
        r"contrato|reclamo|grupo|p[óo]liza|polisa|ledger|invoice|statement)"
        r"(?:\s*(?:number|no\.?|#|id|num[ée]ro|n[úu]mero|numer))?(?:\s+on\s+the\s+\w+)?\s*(?:is|:|#|es|est|to)?\s*"
        r"((?=[A-Z0-9\-]*\d)[A-Z0-9][A-Z0-9\-]{3,24})\b",
        I,
        group=1,
    )

    # Identifier-shaped codes without a keyword: "SL-4471920-03", "CB-20418-S3",
    # "W123456789", "D4429-60718-55231". Upper-case prefix plus at least three digits.
    add(EntityType.ID, r"\b(?=[A-Z0-9\-]*\d{3})[A-Z]{1,5}\d*(?:-[A-Z]{1,6})*-\d[A-Z0-9]*(?:-[A-Z0-9]+)*\b")
    add(EntityType.ID, r"\b[A-Z]{1,2}\d{6,12}\b")
    # Any long bare number (chart numbers, national IDs). Phones and other shapes
    # overlap and win on merge; amounts with separators are excluded.
    add(EntityType.ID, r"(?<![\d.,$€£])\b\d{7,}\b(?![.,]\d)")
    # Payment card numbers in 4-4-4-4 groups, Luhn-checked.
    add(
        EntityType.ACCOUNT,
        r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",
        check=lambda m: _luhn_ok(_digits(m.group(0))),
    )

    # A card named as such needs no checksum ("visa 4539 5555 0142 7719").
    add(
        EntityType.ACCOUNT,
        r"\b(?:visa|mastercard|master\s*card|amex|card|carte|tarjeta|karta|kart[ąa])\s*(?:number|no\.?|#|is|:)?\s*"
        r"(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{2,4})\b",
        I,
        group=1,
    )
    # "card ending 4417", "ends in four four one seven", "xxxx7719".
    add(
        EntityType.ACCOUNT,
        rf"\b(?:ending(?:\s+in)?|ends\s+in|last\s+(?:4|four)(?:\s+digits)?(?:\s+(?:are|is))?|termin[ée]e?\s+par|"
        rf"terminada\s+en|ko[ńn]c[zą]c[aąe]\s+si[ęe]\s+na)\s*:?\s*(\d{{4}}|{_ANY_DIGIT_WORD}(?:\s+{_ANY_DIGIT_WORD}){{3}})\b",
        I,
        group=1,
    )
    add(EntityType.ACCOUNT, r"\b[xX*•]{2,}[\s\-]?\d{4}\b")

    # Quebec RAMQ: 4 letters + 8 digits.
    add(EntityType.HEALTH_CARD, r"\b[A-Z]{4}\s?\d{4}\s?\d{4}\b")
    # Ontario OHIP in its printed 4-3-3 grouping, optional 2-letter version code.
    add(EntityType.HEALTH_CARD, r"\b\d{4}[\s\-]\d{3}[\s\-]\d{3}(?:[\s\-]?[A-Z]{2})?\b")

    add(EntityType.SSN, r"\b(\d{3})-(\d{2})-(\d{4})\b", check=_ssn_check)
    add(EntityType.SIN, r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}\b", check=_sin_check)
    add(
        EntityType.SIN,
        r"\b(?:sin|social\s+insurance(?:\s+number)?|nas|num[ée]ro\s+d['’]assurance\s+sociale)\b[^\d\n]{0,25}?"
        r"(\d{3}[\s\-]?\d{3}[\s\-]?\d{3})\b",
        I,
        group=1,
    )
    # Israeli and other local numbers with a leading 0 area code: "03-555-0147", "054-555-0147".
    add(EntityType.PHONE, r"(?<![\w\-])0\d{1,2}-\d{3}-\d{4}\b")
    # Numbers read out digit by digit after an ID keyword: "medical record number ... four eight two nine one seven",
    # and spoken letter-digit codes: "c b one zero four seven two".
    add(
        EntityType.ID,
        rf"(?<!lot\s)\b(?:record|mrn|chart|member|claim|id|i\s+d|donor|policy|account|group|dossier|historia)\b[^\n]{{0,40}}?(?:\n[^:\n]{{1,20}}:[ \t]*)?"
        rf"\b((?:(?:{_ANY_DIGIT_WORD}|[a-z])\b[\s,\-]+){{3,}}{_ANY_DIGIT_WORD})\b",
        I,
        group=1,
        check=lambda m: sum(1 for w in re.split(r"[\s,\-]+", m.group(1)) if len(w) > 1) >= 4,
    )

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
    add(EntityType.PHONE, rf"\b{_ANY_DIGIT_WORD}(?:[\s,\-]+{_ANY_DIGIT_WORD}){{6,11}}\b", I)
    # Spoken emails: "chen dot wei at example dot com", "julie point savard arobase ...".
    add(
        EntityType.EMAIL,
        r"\b\w+(?:\s+(?:dot|point|punto|kropka|underscore|dash)\s+\w+)*\s+(?:at|arobase|arroba|ma[łl]pa)\s+"
        r"\w+(?:\s+(?:dot|point|punto|kropka)\s+\w+)*\s+(?:dot|point|punto|kropka)\s+"
        r"(?:com|org|net|ca|edu|gov|io|co|uk|fr|es|pl|il)\b",
        I,
    )
    # Spelled-out words ("k o w a l c z y k", "W-O-J-C-I-K") are almost always names.
    add(EntityType.NAME, _names.SPELLED)
    # Postal codes read aloud: "n one h four k seven".
    add(
        EntityType.POSTAL_CODE,
        rf"\b[a-z]\s+{_ANY_DIGIT_WORD}\s+[a-z]\s+{_ANY_DIGIT_WORD}\s+[a-z]\s+{_ANY_DIGIT_WORD}\b",
        I,
    )

    # Dates. Year-only is not PHI under Safe Harbor, so it is not matched.
    add(EntityType.DATE, r"\b\d{4}-\d{1,2}-\d{1,2}\b")
    # Year and month only is still a date element under Safe Harbor.
    add(EntityType.DATE, r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])\b(?!-\d)")
    add(EntityType.DATE, rf"\b\d{{1,2}}[\s\-/.](?:{_MONTHS})[\s\-/.]\d{{2,4}}\b", I)
    add(EntityType.DATE, r"\b\d{1,2}[/\-.]\d{1,2}[/\-.](?:\d{4}|\d{2})\b")
    add(
        EntityType.DATE,
        rf"\b(?:(?:{_WEEKDAY}|{_WEEKDAY_ML}),?\s+)?(?P<month>{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
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
    # A day of the month without the month: "the 19th", "Monday the 9th", "Friday 14th".
    add(EntityType.DATE, rf"\b(?:(?:{_WEEKDAY})\s+(?:the\s+)?|the\s+)\d{{1,2}}(?:st|nd|rd|th)\b", I)
    add(
        EntityType.DATE,
        rf"\b(?:{_WEEKDAY})\s+(?:the\s+)?(?:{_ORDINAL_WORDS})\b",
        I,
    )
    # A spoken day of the month on its own: "can we do the twentieth instead?", "no,
    # the eighteenth". Only when no noun follows ("the third embryo", "the second time").
    add(
        EntityType.DATE,
        rf"\b(?:on|for|to|from|until|till|by|before|after|do|is|no|not|it'?s)\s+the\s+"
        rf"((?:{_ORDINAL_WORDS.replace(')|first|', ')|', 1)}))(?=\s*(?:[.,?!;)/\n]|$|instead|right|then|works|"
        rf"so|at|or|okay|ok|please|correct|is|was|of\s+(?:this|next|the)\s+month))",
        I,
        group=1,
    )
    # French, Spanish, Polish, Hebrew: "le 12 mai 1990", "1er décembre", "jueves 6 de noviembre".
    add(
        EntityType.DATE,
        rf"(?<![0-9A-Za-zÀ-ž])(?:(?:le|el|du|au)\s+)?(?:(?:{_WEEKDAY_ML}),?\s+)?\d{{1,2}}(?:er|re|º|\.)?\s+"
        rf"(?:de\s+|ב)?(?:{_MONTHS_ML})"
        rf"(?:,?\s+(?:de\s+)?\d{{4}})?(?!\w)",
        I,
    )
    add(EntityType.DATE, rf"\b(?:{_WEEKDAY_ML})\s+\d{{1,2}}\b(?![:.,]?\d)", I)
    # Spoken: "le quatorze mars mille neuf cent quatre-vingt-huit", "el veinte de
    # noviembre", "trzeciego lipca tysiąc dziewięćset...", "ארבעה עשר בפברואר".
    add(
        EntityType.DATE,
        rf"(?<!\w)(?:(?:le|el)\s+)?(?:{_DAY_WORDS_FR_ES}|{_DAY_WORDS_PL})\s+(?:de\s+)?(?:{_MONTHS_ML})(?!\w)"
        rf"(?:(?:\s+del?)?(?:[\s\-]+(?:{_YEAR_WORDS})(?!\w)){{1,8}})?",
        I,
    )
    add(
        EntityType.DATE,
        rf"(?<!\w)[בלמ]?-?{_DAY_WORDS_HE}(?:\s+{_DAY_WORDS_HE})*\s+ב(?:{_MONTHS_ML})(?!\w)"
        rf"(?:,?\s+(?:{_YEAR_WORDS})(?!\w)){{0,8}}",
    )
    # Month and year: "May 2024", "Feb 2021", "août 2025", "marzo de 2024".
    add(
        EntityType.DATE,
        rf"\b(?P<month>{_MONTHS})\.?,?\s+(?:of\s+)?(?:19|20)\d{{2}}\b",
        I,
        check=_month_check,
    )
    add(EntityType.DATE, rf"(?<![\w])(?:{_MONTHS_ML})(?:\s+de)?\s+(?:19|20)\d{{2}}\b", I)
    # Abbreviated French, Spanish and Polish months after a day: "4 déc", "12 sept.", "3 ene".
    add(
        EntityType.DATE,
        r"(?<![\d])\b\d{1,2}(?:er)?\s+(?:janv|f[ée]vr|avr|juil|sept|d[ée]c|ene|abr|ago|dic|sty|lut|kwi|cze|lip|sie|wrz|pa[źz]|lis|gru)\b\.?",
        I,
    )
    # Hebrew abbreviated months: "12 בנוב׳".
    add(EntityType.DATE, r"(?<!\d)\d{1,2}\s+ב?(?:ינו|פבר|אפר|יונ|יול|אוג|ספט|אוק|נוב|דצמ)[׳'](?!\w)")
    # Day-first dates without a year: unambiguous ones ("14/03") anywhere, others after a
    # date word ("el 14/03", "punkcja 9.11", "ב-14.3").
    add(EntityType.DATE, r"(?<![\d/.])\b(?!24/7\b)(?:1[3-9]|2\d|3[01])[/.](?:0?[1-9]|1[0-2])\b(?![/.]?\d)")
    add(
        EntityType.DATE,
        r"(?:(?<![\w])(?:el|le|du|au|on|dnia|od|do|ב-?|ל-?|עד|מ-)\s*|\b(?:punkcj[aęi]|punci[óo]n|ponction|retrieval|transfer|"
        r"transfert|transferencia|transfer|iui|ET|שאיבה|החזרה)\s+)"
        r"((?:0?[1-9]|[12]\d|3[01])[/.](?:0?[1-9]|1[0-2]))\b(?![/.]?\d)",
        I,
        group=1,
    )
    # OCR'd numeric dates with O for 0: "06/O6/1989", "17/O4/1987".
    add(
        EntityType.DATE,
        r"\b[\dOo]{1,2}/[\dOo]{1,2}/[\dOo]{4}\b",
        check=lambda m: sum(ch.isdigit() for ch in m.group(0)) >= 5,
    )
    # Spoken dates of birth: "january ninth eighty five", "june six eighty nine",
    # "the fifth of may nineteen ninety two", "oh two eleven nineteen ninety one".
    add(
        EntityType.DATE,
        rf"\b(?P<month>{_MONTHS})\s+(?:the\s+)?(?:{_ORDINAL_WORDS}|{_DAY_CARDINALS})(?:,?\s+{_SPOKEN_YEAR})?\b",
        I,
        check=_month_check,
    )
    add(
        EntityType.DATE,
        rf"\b(?:the\s+)?(?:{_ORDINAL_WORDS})\s+of\s+(?P<month>{_MONTHS}),?\s+{_SPOKEN_YEAR}\b",
        I,
    )
    add(
        EntityType.DATE,
        rf"\b(?:date\s+of\s+birth|birth\s*date|d\.?o\.?b\.?|born(?:\s+on)?)\b[^\n]{{0,25}}?(?:\n[^:\n]{{1,20}}:[ \t]*)?"
        rf"(?:(?:it'?s|his\s+is|hers?\s+is|is|um|uh)[\s,]+)*"
        rf"((?:(?:{_SPOKEN_NUMBER})(?:\s*,\s*|[\s\-]+)){{2,9}}(?:{_SPOKEN_NUMBER}))\b",
        I,
        group=1,
    )

    # Short numeric dates like 3/14 (no year).
    add(EntityType.DATE, r"(?<![\d/])\b(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])\b(?![/\d])")

    add(EntityType.AGE, r"\b(?:9\d|1[01]\d)\s*(?:-\s*)?(?:years?[\s\-]*old|yrs?|y/?o|ans|años|lat)\b", I)
    add(EntityType.AGE, r"\b(?:age[ds]?|aged|âgée?|edad|wiek)\s*:?\s*(9\d|1[01]\d)\b", I, group=1)
    _old = r"9\d|1[01]\d|ninety(?:[\s\-](?:one|two|three|four|five|six|seven|eight|nine))?|one\s+hundred(?:\s+and\s+\w+)?"
    _not_unit = r"(?!\s*(?:%|percent|mg|mcg|ml|kg|lbs?|cm|mm|pm|am|min|minutes|\$|dollars|pmol|iu|bpm|/))"
    add(
        EntityType.AGE,
        rf"\b(?:i'?m|i\s+am|she'?s|he'?s|who\s+is|who'?s|turn(?:s|ed|ing)?|is\s+now)\s+({_old})\b{_not_unit}",
        I,
        group=1,
    )
    # "Esther, 92, lives with them": a capitalized name, then the age between commas.
    add(EntityType.AGE, rf"\b[A-Z][a-z]+,\s+(9\d|1[01]\d),", group=1)

    add(EntityType.ADDRESS, _STREET, I, check=_street_check)
    add(EntityType.ADDRESS, r"\b(?:p\.?\s?o\.?\s*box|postal\s*box)\s*\d+\b", I)
    # Cities and towns where a person lives or comes from ("I live in Sudbury").
    R.append(_Rule(EntityType.ADDRESS, _places()[1], group=0, check=_place_check))

    # Canadian postal code.
    add(
        EntityType.POSTAL_CODE,
        r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][\s\-]?\d[ABCEGHJ-NPRSTV-Z]\d\b",
        I,
    )
    # US ZIP only with context (a bare 5-digit number is too ambiguous).
    add(EntityType.ZIP, rf"\b(?:{_US_STATES})\s+(\d{{5}}(?:-\d{{4}})?)\b", group=1)
    add(EntityType.ZIP, r"\bzip(?:\s*code)?\s*(?:is|:)?\s*(\d{5}(?:-\d{4})?)\b", I, group=1)
    add(
        EntityType.ZIP,
        r"\b(?:c[óo]digo\s+postal|code\s+postal|kod(?:\s+pocztowy)?|zip|מיקוד)\s*:?\s*(\d{5}(?:-\d{4})?)\b",
        I,
        group=1,
    )
    # Street address then city then ZIP: "...Ave Apt 2R Chicago 60647".
    add(
        EntityType.ZIP,
        rf"\b(?:{_STREET_SUFFIX})\b\.?[^\n]{{0,40}}?\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,?\s+(\d{{5}}(?:-\d{{4}})?)\b(?![.,]\d)",
        I,
        group=1,
    )
    add(
        EntityType.ZIP,
        rf"\bzip(?:\s*code)?\b[^\n]{{0,30}}?(?:\n[^:\n]{{1,20}}:[ \t]*)?((?:{_ANY_DIGIT_WORD})(?:\s+(?:{_ANY_DIGIT_WORD})){{4}})\b",
        I,
        group=1,
    )

    # Names introduced by context (see _names.py). The local model or the
    # known-entity list catch names with no cue.
    for pat, flags, check in [*_names.rules(_NOT_NAMES), *_names.courtesy_rules(_NOT_NAMES)]:
        add(EntityType.NAME, pat, flags, check=check)
    add(
        EntityType.PROVIDER,
        r"\b(?i:dr|dre|dra|doctor|doctora|docteur|docteure|nurse|enf|inf|np|rn)\.?\s+"
        r"(?P<name>[A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-zA-Z'\-]+)?)",
        check=_name_check,
    )
    add(EntityType.PROVIDER, r"ד[״\"']ר\s+\S+")
    return R


_RULES = _build_rules()

# Rules where only the named "name" group should be masked ("my husband Dave" -> "Dave").
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
                elif "place" in m.groupdict():
                    start, end = m.span("place")
                else:
                    start, end = m.span(rule.group)
                if end <= start:
                    continue
                out.append(Entity(rule.type, start, end, text[start:end], self.name))
        # Identifiers read out loud: "four one six... five five five...", "T three A".
        spoken = [*_spoken.detect(text), *_spoken.street_numbers(text, _street_spans)]
        out.extend(e for e in spoken if self.enabled is None or e.type in self.enabled)
        return out


_STREET_RE = re.compile(_STREET, re.IGNORECASE)


def _street_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _STREET_RE.finditer(text) if _street_check(m)]
