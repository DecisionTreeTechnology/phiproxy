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
from . import _hebrew, _names, _spoken, _structured

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
    "unknown", "none", "pending", "same", "tbd", "optional", "required", "redacted",
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
    rf"(?:(?:(?:nineteen|twenty)[\s\-]+)?(?:(?:{_TENS})(?:[\s\-]+(?:{_UNITS}))?|ten|eleven|twelve|thirteen|"
    rf"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|oh[\s\-]+(?:{_UNITS}))|"
    rf"two\s+thousand(?:\s+and)?(?:\s+(?:{_UNITS}|ten|eleven|twelve|thirteen|fourteen|fifteen))?)"
)
_SPOKEN_NUMBER = (
    rf"zero|oh|{_UNITS}|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    rf"nineteen|{_TENS}|thousand|hundred|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|"
    rf"tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|"
    rf"nineteenth|twentieth|thirtieth|jan(?:uary)?|feb(?:ruary)?|march|april|may|june|july|"
    rf"august|september|october|november|december"
)
# Number words in Spanish, French and Polish, for digits inside a spoken email.
_SPOKEN_NUMBER_ML = (
    "cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|veinte|treinta|cuarenta|cincuenta|sesenta|setenta|"
    "ochenta|noventa|cien|un|deux|trois|quatre|cinq|sept|huit|neuf|dix|vingt|trente|quarante|cinquante|soixante|"
    "quatre-vingts?|zero|jeden|dwa|trzy|cztery|pi[eę][cć]|sze[sś][cć]|siedem|osiem|dziewi[eę][cć]|dziesi[eę][cć]"
)
# House and flat numbers said in Spanish, Polish and Hebrew ("dos mil cuatrocientos cincuenta y uno",
# "trzysta dwanaście", "שלוש מאות שתים עשרה").
_ES_NUM = (
    "cero|uno|una|un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|"
    "diecis[ée]is|diecisiete|dieciocho|diecinueve|veinte|veinti\\w{3,8}|treinta|cuarenta|cincuenta|sesenta|"
    "setenta|ochenta|noventa|cien|ciento|doscientos|trescientos|cuatrocientos|quinientos|seiscientos|"
    "setecientos|ochocientos|novecientos|mil"
)
_PL_NUM = (
    "jeden|jedna|dwa|dwie|trzy|cztery|pi[eę][cć]|sze[sś][cć]|siedem|osiem|dziewi[eę][cć]|dziesi[eę][cć]|"
    "jedena[sś]cie|dwana[sś]cie|trzyna[sś]cie|czterna[sś]cie|pi[eę]tna[sś]cie|szesna[sś]cie|siedemna[sś]cie|"
    "osiemna[sś]cie|dziewi[eę]tna[sś]cie|dwadzie[sś]cia|trzydzie[sś]ci|czterdzie[sś]ci|pi[eę][cć]dziesi[aą]t|"
    "sze[sś][cć]dziesi[aą]t|siedemdziesi[aą]t|osiemdziesi[aą]t|dziewi[eę][cć]dziesi[aą]t|sto|dwie[sś]cie|"
    "trzysta|czterysta|pi[eę][cć]set|sze[sś][cć]set|siedemset|osiemset|dziewi[eę][cć]set|tysi[aą]c"
)
_HE_NUM = (
    "אחד|אחת|שניים|שתיים|שתים|שני|שתי|שלוש|שלושה|ארבע|ארבעה|חמש|חמישה|שש|שישה|שבע|שבעה|שמונה|תשע|תשעה|"
    "עשר|עשרה|עשרים|שלושים|ארבעים|חמישים|שישים|שבעים|שמונים|תשעים|מאה|מאתיים|מאות|אלף|אלפיים|אפס"
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


# Embryo grades ("4AA", "3BB", "5AB+") are lab results, not donor identifiers.
_EMBRYO_GRADE = re.compile(r"[1-6][A-D]{1,2}[+\-]?", re.IGNORECASE)


_CARD_WORD = re.compile(r"\b(?:cards?|visa|mastercard|amex|credit|debit|carte|tarjeta|karta|kart[ąy])\b", re.IGNORECASE)
_CARD_EXPIRY_AFTER = re.compile(r"[ \t,;]*(?:exp\w*|valid\w*|cvv2?|cvc2?|security\s+code)\b", re.IGNORECASE)


def _card_context(m: re.Match[str]) -> bool:
    """A 16-digit group is a card when the text around it talks about cards or gives an expiry."""
    text = m.string
    if _PRODUCT_TAIL.search(text[max(0, m.start() - 20) : m.start()]):
        return False
    return bool(_CARD_WORD.search(text[max(0, m.start() - 160) : m.start()]) or _CARD_EXPIRY_AFTER.match(text, m.end()))


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _sin_check(m: re.Match[str]) -> bool:
    d = _digits(m.group(0))
    return len(d) == 9 and _luhn_ok(d)


def _ssn_check(m: re.Match[str]) -> bool:
    a, b, c = m.group(1), m.group(2), m.group(3)
    return a not in ("000", "666") and not a.startswith("9") and b != "00" and c != "0000"


_AGE_OLD = (
    r"9\d|1[01]\d|ninety(?:[\s\-](?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"(?:one|a)\s+hundred(?:\s+(?:and\s+)?(?:one|two|three|four|five|six|seven|eight|nine|ten))?|"
    r"noventa(?:\s+y\s+(?:uno|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve))?|cien(?:to\s+\w+)?|"
    r"quatre[\s\-]vingt[\s\-](?:dix(?:[\s\-](?:sept|huit|neuf))?|onze|douze|treize|quatorze|quinze|seize)|"
    r"dziewi[ęe][ćc]dziesi[ąa]t(?:\s+(?:jeden|dwa|trzy|cztery|pi[ęe][ćc]|sze[śs][ćc]|siedem|osiem|dziewi[ęe][ćc]))?|sto"
)
_AGE_NOT_UNIT = (
    r"(?!\s*(?:%|percent|por\s+ciento|pour\s+cent|mg|mcg|ml|kg|lbs?|cm|mm|pm|am|min|minutes|\$|dollars|"
    r"d[óo]lares|dollars|pmol|iu|bpm|/|[.,]\d|days?|weeks?|months?|hours?|jours?|semaines?|mois|d[íi]as?|semanas?|"
    r"meses|dni|tygodni\w*|miesi[ęe]c\w*|ans\s+de\s+suivi|años\s+de\s+seguimiento))"
)
_RELATIVE = re.compile(
    r"\b(?:grand(?:mother|ma|mom|father|pa|dad|parents?)|great[\s\-]grand\w*|granny|nana|mother|mom|mum|father|dad|"
    r"aunt|uncle|abuel[ao]s?|bisabuel[ao]|madre|padre|t[ií][ao]|grand[\s\-]m[èe]re|grand[\s\-]p[èe]re|"
    r"arri[èe]re[\s\-]grand[\s\-]\w+|m[èe]re|p[èe]re|tante|oncle|babci[aąęe]|dziad(?:ek|ka|kiem)|pradziad\w*|"
    r"prababci\w*|matk[aię]|ojc(?:iec|a)|ciotk[aię]|wuj(?:ek|ka)|patient|patiente|paciente|pacjent\w*|"
    r"husband|wife|spouse|partner|brother|sister|mari|[ée]pouse|conjoint\w*|fr[èe]re|s[œo]eur|esposo|esposa|hermano|hermana|"
    r"m[ąa][żz]|[żz]ona|brat|siostra)\b|"
    r"סבתא|סבא|אמא|אבא|דודה|סבתי|סבי|מטופל|מטופלת",
    re.IGNORECASE,
)


_AGE_SUBJECT_NOT = re.compile(
    r"\b(?:amh|fsh|tsh|lh|hcg|beta|e2|estradiol|progesterone|prolactin|level|levels|count|cost|costs|total|price|"
    r"bill|balance|fee|weight|score|result|results|day|cycle|follicles?|lining|sperm|motility|number|room|suite|"
    r"apt|unit|ext|extension|page|line|address|street|valor|nivel|niveau|prix|cena|poziom|wynik)\b",
    re.IGNORECASE,
)


_AGE_LIFE = re.compile(r"\b(?:died|passed|alive|lived|death|deceased|muri[óo]|d[ée]c[ée]d[ée]e?|zmar[łl]a?)\b|נפטר", re.IGNORECASE)


def _relative_before(m: re.Match[str]) -> bool:
    """A relative is named earlier on the same line ("her mother Abena is 91"), and the number
    is not a lab value, price or street number ("my mom thinks my TSH is 100", "lives at 95 Elm St")."""
    text = m.string
    line_start = text.rfind("\n", 0, m.start()) + 1
    window = text[max(line_start, m.start() - 100) : m.start()]
    rel = None
    for rel in _RELATIVE.finditer(window):
        pass
    if rel is None:
        return False
    if _AGE_SUBJECT_NOT.search(window[rel.end() :]):
        return False
    # A bare "at" only in a death or life sentence: "died June 2 2019 at 91".
    if "v" in m.re.groupindex and m.group("v").lower() == "at" and not _AGE_LIFE.search(window):
        return False
    return not _STREET_SUFFIX_AFTER.match(text, m.end())


_ORG_NOT = re.compile(
    r"^(?:the|a|an|home|night|nights|days?|weekends?|work|the\s+moment|least|bit|all|same|first|last|this|that|my|our|"
    r"bit|clinic|hospital|office|school|university|college|ב?בית|הבית|בבית|שם|כאן|עכשיו|היום|מחר)$",
    re.IGNORECASE,
)


_ORG_STOP = (
    r"I|So|In|Is|It|If|On|At|And|But|Then|Next|Also|We|My|Our|He|She|They|You|Can|Please|Thanks|Thank|"
    r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Tues|Wed|Thu|Thurs|Fri|Sat|Sun|"
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
    r"lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo|enero|febrero|marzo|abril|mayo|junio|julio|"
    r"agosto|septiembre|octubre|noviembre|diciembre|casa|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
    r"janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre|maison|"
    r"poniedzia[łl]ek|wtorek|[śs]roda|czwartek|pi[ąa]tek|sobota|niedziela|domu|home"
)
_ORG_WORD = re.compile(
    r"\b(?:colegio|escuela|universidad|instituto|hospital|cl[íi]nica|banco|empresa|compa[ñn][íi]a|grupo|"
    r"universit[ée]|[ée]cole|coll[èe]ge|lyc[ée]e|h[ôo]pital|clinique|banque|soci[ée]t[ée]|centre|"
    r"szpital|uniwersytet|politechnika|szko[łl]a|firma|bank|sp[óo][łl]ka|inc|llc|ltd|corp|group)\b",
    re.IGNORECASE,
)


def _org_check_foreign(m: re.Match[str]) -> bool:
    """After "trabajo en", "pracuję w": an organisation, not a city or "casa". One word passes
    only after "chez", "para", "dla" ("je travaille chez Desjardins")."""
    if not _org_check(m):
        return False
    org = m.group("org")
    return bool(_ORG_WORD.search(org)) or len(org.split()) >= 2 or m.group("prep").lower() in ("chez", "para", "dla")


def _doc_number_check(m: re.Match[str]) -> bool:
    """A document or tracking number, not "3 days", "2027", "2025-10-04" or "100 200 300"."""
    v = m.group("v")
    if sum(c.isdigit() for c in v) < 5 or re.fullmatch(r"(?:19|20)\d\d(?:[\-/.]\d{1,2}){0,2}", v):
        return False
    groups = re.split(r"[ \-]", v)
    if all(re.fullmatch(r"(?:19|20)\d\d", g) for g in groups):
        return False  # "license 2024 2025 2026 renewal"
    if re.fullmatch(r"\d{2,3}(?:-\d{3,4}){2}", v):
        return True  # "driver licence 99-123-4567"
    return len(groups[0]) >= 4 or any(c.isalpha() for c in groups[0])


_HE_ALEPHBET = "אבגדהוזחטיכלמנסעפצקרשת"


# A bare "@word" is a social handle only with a cue in front or a handle shape (a digit, underscore
# or dot, or capitals after the first letter); "@home", "@clinic", "@nurses" are plain words.
_HANDLE_CUE = re.compile(
    r"(?i:\b(?:instagram|insta|ig|tiktok|tik\s*tok|twitter|x|facebook|fb|snap(?:chat)?|threads|bluesky|handle|"
    r"follow(?:\s+me)?|my\s+account|dm\s+me|tag(?:ged)?(?:\s+me)?|find\s+me|message\s+me|username|user\s*name|mention)\b)\W{0,12}$"
)


_PLATFORM_WORDS = r"(?:page|account|handle|profile|channel|instagram|insta|ig|twitter|x|facebook|fb|tiktok|tik\s*tok|linkedin|youtube|threads|bluesky)"
_CLINIC_OWNS_BEFORE = re.compile(
    rf"(?i:\b(?:follow\s+(?:us|the\s+clinic)|find\s+us|we(?:['’]re|\s+are)\s+on|our\s+(?:\w+\s+){{0,2}}?{_PLATFORM_WORDS}|"
    rf"the\s+clinic(?:['’]s)?\s+(?:\w+\s+){{0,2}}?(?:on|{_PLATFORM_WORDS}))\b)[^\n.!?]{{0,40}}$"
)
_CLINIC_OWNS_AFTER = re.compile(rf"(?i:\W{{0,3}}(?:is|are)\s+our\s+(?:\w+\s+)?{_PLATFORM_WORDS}\b)")


def _clinic_owned(text: str, start: int, end: int) -> bool:
    """The handle or site is introduced as the clinic's own ("follow us on ...", "our page", "the clinic on ...")."""
    return bool(
        _CLINIC_OWNS_BEFORE.search(text[max(0, start - 80) : start]) or _CLINIC_OWNS_AFTER.match(text, end)
    )


def _handle_check(m: re.Match[str]) -> bool:
    if _clinic_owned(m.string, m.start(), m.end()):
        return False
    word = m.group(0)[1:]
    if re.search(r"[\d_.]", word) or re.search(r"[A-Z]", word[1:]):
        return True
    return bool(_HANDLE_CUE.search(m.string[max(0, m.start() - 30) : m.start()]))



_SITE_BUILDERS = re.compile(
    r"(?:wixsite|wix|wordpress|blogspot|blogger|substack|medium|tumblr|weebly|squarespace|webflow|carrd|github|gitlab|"
    r"netlify|vercel|linktr|gofundme|gofund|justgiving|mightycause|kit|notion|bio|about|ghost|typepad)\.",
    re.IGNORECASE,
)
_OWN_SITE_CUE = re.compile(
    r"(?i:\b(?:our|the\s+clinic['’]?s?|clinic['’]s)\s+(?:(?:patient|clinic|new|online|main|public|web)\s+){0,2}"
    r"(?:web\s*site|site|blog|page|portal|channel)(?:\s+(?:is|at|on))?)[ \t:]*$"
)
# Public and institutional hosts (government, education, province or state sites) are not personal.
_INSTITUTION_LABELS = frozenset("gov gouv gob govt gc edu ac mil k12 nhs".split())
_PROVINCE_CODES = frozenset("on qc bc ab mb sk ns nb nl pe yk nt nu".split())
_BARE_PLATFORMS = frozenset(
    "wix.com squarespace.com wordpress.com blogspot.com gofundme.com medium.com substack.com weebly.com".split()
)
_REGION_LABELS = frozenset(
    "canada ontario quebec alberta manitoba saskatchewan novascotia newbrunswick britishcolumbia bc ab on qc mb sk ns nb pe nl yk nt nu".split()
)
_PERSONAL_SITE_CUE = re.compile(
    r"(?i:\b(?:my|our|her|his|their|patient['’]?s|\w+['’]s)\s+(?:personal\s+|new\s+|little\s+|own\s+)?"
    r"(?:web\s*site|site|blog|page|fundraiser|fundraising\s+page|journal|vlog|channel|portfolio)(?:\s+(?:is|at|on))?)[ \t:]*$"
)
_PERSON_SEGMENT = re.compile(r"[A-Za-z]{2,}[\-_.][A-Za-z]{2,}|[A-Za-z]{3,}\d{2,}")


_AT_NOT_LOCAL = frozenset(
    """look looks looking come comes tell me contact him her us them check see find reach email emails write
    text call ask visit go meet send message show give get open try use view click log sign register stop
    available here there it you we they i he she is are be was were at on from now just also please then
    mail e-mail reply respond share post listed found reached sent""".split()
)
_EMAIL_CUE_BEFORE = re.compile(r"(?i)\b(?:e-?mail|correo|courriel|mail)[ \t:]*(?:is|es|est)?[ \t:]*$")


def _plain_at_check(m: re.Match[str]) -> bool:
    """"look at gmail.com" is not an address: a bare word before "at" must be a real local part."""
    local = re.split(r"[ \t@]", m.group(0), maxsplit=1)[0]
    if re.search(r"[.\-_\d]", local):
        return True
    if _EMAIL_CUE_BEFORE.search(m.string[max(0, m.start() - 20) : m.start()]):
        return True
    return local.lower() not in _AT_NOT_LOCAL


def _bare_site_check(m: re.Match[str]) -> bool:
    """A scheme-less domain after a cue is masked when it looks personal: a personal cue ("my blog"),
    a site-builder host, a subdomain, or a person-shaped name or path. A bare public org site
    ("visit mayoclinic.org") stays."""
    url = m.group(1)
    cue_text = m.string[max(0, m.start() - 40) : m.start(1)]
    if _OWN_SITE_CUE.search(cue_text):
        return False
    if _PERSONAL_SITE_CUE.search(cue_text[-20:]):
        return True
    host, _, path = url.partition("/")
    labels = host.lower().split(".")
    if labels[0] == "www":
        labels = labels[1:]
    if _INSTITUTION_LABELS.intersection(labels) or (labels[-1] == "ca" and len(labels) == 2 and labels[0] in _REGION_LABELS):
        return False
    if len(labels) >= 3 and labels[-1] == "ca" and labels[-2] in _PROVINCE_CODES:
        return False  # "mountsinai.on.ca": a provincial institution
    if len(labels) >= 3 and labels[-1] == "us" and "state" in labels[:-1]:
        return False
    if ".".join(labels) in _BARE_PLATFORMS:
        return False  # "visit wix.com": the platform itself, not a person's site on it
    if _SITE_BUILDERS.search(host + "."):
        return True
    if len(labels) >= 3 and labels[0] != "www":
        return True
    if _PERSON_SEGMENT.fullmatch(labels[-2]) or re.fullmatch(r"[A-Za-z]{3,}\d{2,}", labels[-2]):
        return True
    return bool(path and any(_PERSON_SEGMENT.fullmatch(seg) for seg in re.split(r"[/?#]", path) if seg))



def _not_alphabet_run(m: re.Match[str]) -> bool:
    """Spelled letters, not a list of clause letters ("א ב ג ד", "a b c d")."""
    letters = "".join(c for c in m.group(0).lower() if c.isalpha() and len(c) == 1)
    for abc in ("abcdefghijklmnopqrstuvwxyz", _HE_ALEPHBET):
        if len(letters) >= 3 and letters in abc:
            return False
    return True


# Three-letter abbreviations a clinic writes with hyphens or reads out letter by letter.
_ACRONYMS_3 = {
    "IVF", "IUI", "FSH", "TSH", "HCG", "AMH", "LH", "ICSI", "PGT", "DNA", "BMI", "LMP", "PCO", "PCP", "HSG",
    "ERA", "FET", "OHS", "STD", "STI", "HIV", "HPV", "PRP", "CBC", "ECG", "EKG", "MRI", "TTC",
    "OBGYN", "NIPT", "PGS", "DHEA", "GYN", "ENT", "ICU", "ER", "OTC", "FDA", "HIPAA",
}


def _org_check(m: re.Match[str]) -> bool:
    """A real name, not "at home", "at the moment", a generic place or a doctor."""
    org = m.group("org").strip(" .,'’")
    return len(org) >= 3 and not _ORG_NOT.match(org) and not re.match(r"(?i)(?:dr|dre|doctor|mr|mrs|ms)\b", org)


_BIRTH_CUE_BEFORE = re.compile(
    r"(?i:\b(?:dob|d\.o\.b\.?|date\s+of\s+birth|birth\s*date|birthday|b-?day|born)(?:\s+(?:is|was|on|:))?)[\s:.,\-]{0,4}$"
)


def _month_check(m: re.Match[str]) -> bool:
    """A lowercase month that is also an English word ("may", "march") counts only as a date when a
    birth cue ("dob", "born") stands right before it."""
    month = m.group("month")
    if not (month.lower() in _AMBIGUOUS_MONTHS and month[0].islower()):
        return True
    return bool(_BIRTH_CUE_BEFORE.search(m.string[max(0, m.start("month") - 30) : m.start("month")]))


# Cues that make a number-shaped token an expiry, a page or a lab value, not a date.
_EXPIRY_BEFORE = re.compile(
    r"(?i:\bexp(?:iry|ires|ired|iration|\.)?|\bbest\s+before|\buse\s+by|\bvalid\s+(?:thru|until|through)|"
    r"\bdiscard\s+(?:after|by)|\bcaducidad|\bp[ée]remption|\bvence)\W{0,3}$"
)
# A product lot or kit just before the expiry word, in the same clause ("lot 5512 exp 08/28", "kit exp
# 2027-04"), or a payment card number earlier on the line: the expiry belongs to a product or a card.
_PRODUCT_TAIL = re.compile(r"(?i)\b(?:lot|lote|ndc|batch|kit|ref)\b(?:[^\S\n]+[\w#\-]+,?){0,2}[^\S\n]*$")
_PRODUCT_ID = re.compile(r"(?i)\b(?:lot|lote|ndc|batch|kit|ref)\b[\s#:.\-]*(?=[\w\-]{0,12}\d)[\w\-]+")
_CARD_NUMBER = re.compile(r"\d{4}[ \-]\d{4}[ \-]\d{4}[ \-]\d{3,4}")
_PERSONAL_WORD = re.compile(
    r"(?i)\b(?:my|your|her|his|their|our|patient\w*|card|visa|mastercard|passport|licen[cs]e|insurance|health|dob|born)\b"
)
_PAGE_BEFORE = re.compile(r"(?i:\b(?:p|pp|pg|pag|page|p[áa]gina|str|strona|seite|\u05e2\u05de|\u05e2\u05de\u05d5\u05d3))[.'\u05f3]{0,2}\s*$")
# A lab analyte right before a decimal ("FSH 18.4", "AMH level 1.2"): not a day.month date.
_LAB_BEFORE = re.compile(
    r"(?i:\b(?:fsh|lh|amh|tsh|hcg|bhcg|e2|p4|prl|psa|a1c|hba1c|hgb|wbc|rbc|ferritin|estradiol|progesterone|"
    r"testosterone|inhibin|t3|t4)\b(?:\s+(?:level|levels|value|result|results))?\W{0,3})$"
)
_FRACTION_DOSE = re.compile(
    r"(?i)\s*(?:tab(?:s|lets?)?\b|cups?\b|doses?\b|vials?\b|amps?\b|pens?\b|mg\b|ml\b|tsp\b|tbsp\b|teaspoons?\b|cc\b|inch(?:es)?\b|%)"
)
_FRACTION_TIME = re.compile(r"(?i)\s*(?:of\s+an?\s+)?(?:hours?\b|days?\b|weeks?\b|cups?\b|tab(?:s|lets?)?\b)")


def _is_fraction(m: re.Match[str]) -> bool:
    """A proper fraction with a small denominator ("1/2", "3/4"), which a date can only rarely be."""
    parts = re.findall(r"\d+", m.group(0))
    return len(parts) == 2 and int(parts[0]) < int(parts[1]) <= 8


def _not_expiry(m: re.Match[str]) -> bool:
    """Not a lot or card expiry ("exp 08/28", "expiry 2027-04")."""
    return not _is_product_expiry(m)


# What expires decides it: a person's document or card (personal, masked) or a product (not PHI).
_DOC_WORD = re.compile(
    r"(?i)\b(?:cards?|visa|mastercard|amex|passport|passeport|pasaporte|licen[cs]es?|licen[cs]ed|permit|insurance|"
    r"ohip|health|id|identity|cvv2?|cvc2?|dob|born|policy|member|membership|tarjeta|carte|permiso)\b"
)
_PRODUCT_WORD = re.compile(
    r"(?i)\b(?:pens?|vials?|kits?|box(?:es)?|bottles?|syringes?|needles?|ampou?les?|cartridges?|cartons?|packages?|packets?|"
    r"tablets?|pills?|capsules?|injections?|injectables?|medications?|medicines?|drugs?|products?|trigger|shots?|"
    r"supply|supplies|dose|doses|lot|lote|batch|ndc|"
    r"stylo|flacon|bo[iî]te|m[ée]dicaments?|produit|pluma|frasco|jeringa|caja|medicamento|producto|"
    r"gonal|menopur|ovitrelle?|ovidrel|cetrotide|orgalutran|ganirelix|fyremadel|pregnyl|novarel|follistim|puregon|"
    r"lupron|crinone|endometrin|progesterone|estradiol|letrozole|clomid|hcg|heparin|clexane|lovenox|aspirin)\b"
)
_PW = _PRODUCT_WORD.pattern[len("(?i)"):]
# The product is what expires: "pen expires", "Gonal-f exp", "the box says exp", "exp 03/2027 on the vial".
_PRODUCT_SUBJECT = re.compile(
    _PW + r"(?:-\w{1,3})?(?:[^\S\n]+(?:says?|shows?|reads?|states?|is|are|was|label\w*))?\W{0,4}$", re.I
)
_PRODUCT_OBJECT_AFTER = re.compile(
    r"[^\S\n]*(?:on|of|for|from|in)[^\S\n]+(?:the|this|my|a|each|every)[^\S\n]+(?:\w+[^\S\n]+)?" + _PW, re.I
)
# Something a person holds that is not a product: an authorization, approval, referral, coverage, prescription.
_AUTH_WORD = re.compile(
    r"(?i)\b(?:authori[sz]\w*|auth|approv\w*|referral|referrals|coverage|covered|claims?|benefits?|eligib\w*|prior|"
    r"pre-?cert\w*|pre-?auth\w*|prescriptions?|rx|refills?|plan|subscription|appointment|consent|waiver|"
    r"mandate|requisition|order)\b"
)
# "use by" / "best before" / "discard after" are said of products only, never of a person's document.
_PRODUCT_ONLY_CUE = re.compile(r"(?i:\bbest\s+before|\buse\s+by|\bdiscard\s+(?:after|by))\W{0,3}$")


def _is_product_expiry(m: re.Match[str]) -> bool:
    """The span is the expiry of a product (lot, kit, pen, vial, drug), not of a card or a person's
    document. A card number or a card, passport, licence, insurance or ID word near the expiry makes it
    personal even when a product word is also there."""
    before = m.string[max(0, m.start() - 24) : m.start()]
    cue = _EXPIRY_BEFORE.search(before)
    if not cue:
        return False
    line_start = max(m.string.rfind("\n", 0, m.start()) + 1, m.start() - 200)
    cue_at = m.start() - len(before) + cue.start()
    clause = re.split(r"[.;!?]", m.string[line_start:cue_at])[-1]
    after = re.split(r"[.;!?\n]", m.string[m.end() : m.end() + 40])[0]
    product_cue = bool(_PRODUCT_ONLY_CUE.search(before))
    lot_in_clause = bool(re.search(r"(?i)\b(?:lot|lote|ndc|batch|kit|ref)\b", clause))
    if _DOC_WORD.search(clause) or _DOC_WORD.search(after[:30]):
        return False
    if _CARD_NUMBER.search(m.string[line_start:cue_at]) and not (product_cue or lot_in_clause):
        return False
    if _AUTH_WORD.search(clause) or _AUTH_WORD.search(after[:30]):
        return False
    if product_cue:
        return True
    subject = _PRODUCT_SUBJECT.search(clause)
    if subject and not re.search(r"(?i)\b(?:for|of|to|with|from|on|at|under)[^\S\n]+$", clause[: subject.start()]):
        return True
    if _PRODUCT_OBJECT_AFTER.match(after[:40]):
        return True
    # A lot, batch or kit with an identifier, then nothing personal up to the expiry word:
    # "Lot 4471B. Exp 08/2027", "kit, lot 24-0713, qty 6, exp 06/2027".
    for ident in _PRODUCT_ID.finditer(m.string, line_start, cue_at):
        if not _PERSONAL_WORD.search(m.string[ident.start() : cue_at]):
            return True
    tail = _PRODUCT_TAIL.search(clause)
    return bool(tail) and not _PERSONAL_WORD.search(tail.group(0))


# Billing, revision and marketing cues: a month and year after them is a document period, not a person's date.
_DOC_PERIOD_BEFORE = re.compile(
    r"(?i)(?:\b(?:invoice|invoiced|statement|billing|billed|newsletter|version|ver|rev|revision|revised|updated|"
    r"update|valid[^\S\n]+(?:from|as[^\S\n]+of)|effective|price|prices|pricing|offer|promo|hours|stats|statistics|quarter|fiscal|"
    r"issue|edition|published|copyright|release|released)\b|\bv\d|\bQ\d?)[^\n]{0,40}$"
)


def _not_doc_period(m: re.Match[str]) -> bool:
    """Not a billing period, form revision or newsletter month ("Invoice 12/2024", "Rev. 05/2023", "Q3/2024")."""
    start = m.start()
    if start and m.string[start - 1] in "Qq" and (start == 1 or not m.string[start - 2].isalnum()):
        return False
    before = m.string[max(0, start - 45) : start]
    before = re.split(r"[.;!?\n]\s", before)[-1].split("\n")[-1]
    return not _DOC_PERIOD_BEFORE.search(before)


def _short_date_check(m: re.Match[str]) -> bool:
    """A short numeric date, not an expiry, a page number ("p. 1/3") or a fraction ("1/2 tablet")."""
    before = m.string[max(0, m.start() - 24) : m.start()]
    if _is_product_expiry(m) or _PAGE_BEFORE.search(before):
        return False
    if _FRACTION_DOSE.match(m.string, m.end()):
        return False
    return not (_is_fraction(m) and _FRACTION_TIME.match(m.string, m.end()))


def _not_lab_value(m: re.Match[str], dot_only: bool = True) -> bool:
    """Not a result like "FSH 18.4". For a day-first date only a decimal point can be a result; a slash is a date."""
    if dot_only and "." not in m.group(0):
        return True
    return not _LAB_BEFORE.search(m.string[max(0, m.start() - 32) : m.start()])


_SPELLING_WORD = re.compile(r"(?i)\b[a-z][ \t]+(?:as[ \t]+in|comme|como|for)[ \t]+$")


def _as_in_letter(text: str, e: Entity) -> bool:
    """The span is the key word of a spelled letter ("N as in November"): it starts with that letter."""
    m = _SPELLING_WORD.search(text[max(0, e.start - 30) : e.start])
    return bool(m) and m.group(0)[0].lower() == text[e.start].lower()


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
    r"tysi[ąa]c\w*|dwa|jeden|trzy|cztery|pi[ęe][ćc]|sze[śs][ćc]|siedem|osiem|dziewi[ęe][ćc]|dziewi[ęe][ćc]set|osiemset|\w+dziesi[ąa]t\w*|\w+na[śs]cie|"
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
    for n in list(names):  # "Saint Paul" is also written "St. Paul" and "St Paul"
        if n.startswith("saint "):
            for abbr in ("st. ", "st "):
                names.setdefault(abbr + n[6:], names[n])
        elif n.startswith("st. "):
            names.setdefault("saint " + n[4:], names[n])
    alternation = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    cue = (
        r"(?:\b(?:in|from|near|to|into|outside(?:\s+of)?|around|towards?|"
        r"[àa]|au|de|dans|pr[èe]s\s+de|en|desde|cerca\s+de|w|we|z|ze|do|pod|ko[łl]o)\s+)"
    )
    pattern = re.compile(rf"{cue}(?P<place>{alternation})(?![\w\-])", re.IGNORECASE)
    return names, pattern


_STREET = (
    rf"\b\d{{1,6}}[^\S\n]{{1,2}}(?:[A-Za-z0-9'\-]+[^\S\n]{{1,2}}){{0,3}}(?:{_STREET_SUFFIX})\b\.?"
    # A direction after the street word: "Lyndale Ave S", "58 Dupont Ave N".
    r"(?:[^\S\n]+(?-i:[NSEW]|NE|NW|SE|SW)\b\.?(?![\w\-]))?"
    r"(?:,?\s*(?:apt|apartment|unit|suite|ste|#)\.?\s*[A-Za-z0-9\-]+)?"
    # The city right after: "22 Pine Ridge Dr, Whitby", "2240 Maryland Ave E, St. Paul".
    r"(?:,[^\S\n]*(?-i:[A-Z][\w'\-]+(?:(?:(?<=\bSt)|(?<=\bMt)|(?<=\bFt)|(?<=\bSte))\.(?=[^\S\n][A-Z]))?(?:[^\S\n][A-Z][\w'\-]+)?)(?![^\S\n]*(?:\(|\d{3}\b)))?"
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


_TITLE_DR = re.compile(r"[\d'\-\s]*dr\.[^\S\n]+(?-i:[A-Z])", re.IGNORECASE)


_DR_STREET_AFTER = re.compile(
    rf"(?:[^\S\n]+(?-i:[A-Z][\w'’\-]*)\.?){{1,5}}?(?:[^\S\n]+(?i:{_STREET_SUFFIX})\b|,[^\S\n]*(?-i:[A-Z][a-z]))"
)


def _street_check(m: re.Match[str]) -> bool:
    # "416 555 0123 Dr. Smith": digits only, then "Dr." and a capitalised name is a title.
    if _TITLE_DR.match(m.group(0) + m.string[m.end() : m.end() + 3]):
        # "42 Dr. Penfield Ave", "15 Dr. Penfield, Montreal": a street named for a doctor stays masked.
        return bool(_DR_STREET_AFTER.match(m.string, m.end()))
    words = re.findall(r"[A-Za-z]+", m.group(0))
    for i, w in enumerate(words):  # only the words before the street suffix
        if _STREET_SUFFIX_RE.fullmatch(w):
            words = words[:i]
            break
    return not any(w.lower() in _NOT_STREET_WORDS for w in words)


def _moved_check(m: re.Match[str]) -> bool:
    return m.group("place").lower() not in _NOT_NAMES and not re.match(r"(?:le|la|les|el|los)\b", m.group("place"), re.I)


def _place_value_check(m: re.Match[str]) -> bool:
    return m.group("place").lower() not in _NOT_NAMES | {"unknown", "n/a", "same", "none"}


def _place_check(m: re.Match[str]) -> bool:
    names, _ = _places()
    place = m.group("place")
    return not names.get(place.lower(), False) or place[0].isupper()


# Two-letter words that are not a health card's version code ("1234 567 890 if you need it").
_SHORT_WORDS = (
    "if|is|in|it|or|on|at|to|of|so|my|me|we|no|ok|as|by|do|go|he|up|us|am|an|be|et|en|es|la|le|el|de|du|un|ou|"
    "si|ya|lo|mi|tu|ze|na|po|za|od|ja|il|al|se|te|ce"
)


_NOT_USERNAMES = frozenset(
    """
    broken required invalid incorrect wrong missing correct case same not the my your below above different taken
    available blank empty locked expired disabled reset changed working fine ok okay down failed pending unknown
    and also still now here there this that what which it is was correcto incorrecto requerido obligatoire
    """.split()
)


def _username_check(m: re.Match[str]) -> bool:
    """A handle ("hunter.bale", "mgarcia88", or "jsmith" after "username"), not "login is broken"."""
    v = m.group(1)
    if re.search(r"[._\d]", v):
        return True
    cue = m.group(0)[: m.start(1) - m.start(0)].lower()
    if v.lower() in _NOT_USERNAMES or len(v) < 4:
        return False
    # Not the Spanish chat speaker label "Usuario: hola".
    return not (cue.lstrip().startswith("usuario") and ":" in cue)


def _build_rules() -> list[_Rule]:
    I = re.IGNORECASE
    R: list[_Rule] = []

    def add(t: EntityType, pat: str, flags: int = 0, group: int = 0, check=None) -> None:
        R.append(_Rule(t, re.compile(pat, flags), group, check))

    add(EntityType.EMAIL, r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
    # A URL does not end in sentence punctuation ("www.example.org, ok" -> "www.example.org").
    _U = r"[^\s<>\"')\]]*[^\s<>\"')\].,;:!?]"
    add(EntityType.URL, rf"\bhttps?://{_U}|\bwww\.{_U}", I)
    add(EntityType.URL, rf"\b(?:[a-z0-9\-]{{1,63}}\.){{1,8}}(?:com|org|net|ca|io|me|pl|fr|es|il|mx|co)/{_U}", I)
    add(EntityType.IP_ADDRESS, r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")

    # Keyword-anchored identifiers. The keyword stays; only the value is masked.
    add(
        EntityType.HEALTH_CARD,
        r"\b(?:ohip|health\s*card|hcn|health\s*(?:care\s*|insurance\s*)?(?:card\s*)?(?:number|no\.?|#)|phi?n|ramq|carte\s*soleil|sant[ée]\s+manitoba|manitoba\s+health|"
        r"ahs\s*(?:number|no\.?|#)|ahcip|uli|carte\s*(?:de\s*)?sant[ée](?:\s*AB)?|carte\s*d['’]assurance[\s\-]maladie|"
        r"insur(?:ance)?\.?\s*id|tarjeta\s+sanitaria|alberta\s+health(?:\s+care)?|medicare|msp|pesel)"
        # "is", ":", or a few words then a colon ("carte santé comme demandé : 7634 19028").
        r"(?:\s+insurance\s+plan)?(?:\s*(?:card|number|no\.?|#)){0,2}\s*(?:is|est|es|:|#|(?:[^\S\n]+[^\W\d_]+){1,3}[^\S\n]*:)?\s*"
        rf"([A-Z]{{0,4}}[\s\-]?\d(?:[\d\s\-]|\bdash\b){{6,24}}\d(?:[^\S\n]{{0,2}}(?:-|\bdash\b)?[^\S\n]{{0,2}}(?!(?:{_SHORT_WORDS})\b)(?:[A-Z]{{2}}|(?-i:[A-Z][^\S\n]?[A-Z])))?)\b",
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
    # "the donor was number 7719-B", "donor profile no. 4410".
    add(
        EntityType.DONOR_ID,
        r"(?:\b(?:donor|donante|donneur|donneuse|dawc\w*)\b[^\n\d.]{0,25}?(?:\b(?:number|no\.?|id|n[úu]mero|num[ée]ro|numer|nr\.?|"
        r"reference|ref\.?|profile|perfil|profil)|#|\bn\.?\s?º)|\b(?:numer|nr\.?)\s+dawc\w*|\bdonor\s*:)\s*:?\s*"
        r"((?=[A-Z0-9\-]*\d)[A-Z0-9][A-Z0-9\-]{2,19})\b",
        re.IGNORECASE,
        group=1,
    )
    # "donor D-4521", "donor #4521": no keyword, but the value has a digit.
    add(
        EntityType.DONOR_ID,
        r"\b(?:donor|donneu[rs]e?|donante|embryo)\s+#?\s*((?=[A-Z0-9\-]*\d)[A-Z]{0,4}-?\d[A-Z0-9\-]{2,15})\b",
        I,
        group=1,
        check=lambda m: not _EMBRYO_GRADE.fullmatch(m.group(1)),
    )
    add(
        EntityType.ACCOUNT,
        r"\b(?:account|acct|policy|member|insurance\s*id|claim|group|certificate|certificat|contrat|"
        r"contrato|reclamo|grupo|grupa|groupe|p[óo]liza|polisa|ledger|invoice|statement|compte|cuenta|konta|konto|"
        r"(?:application|authori[sz]ation|auth|autorisation|autorizaci[óo]n)\s+(?:reference|ref\.?|r[ée]f[ée]rence|referencia))"
        r"(?:\s*(?:number|no\.?|#|id|num[ée]ro|n[úu]mero|numer))?(?:\s+on\s+the\s+\w+)?\s*"
        r"(?:is|:|#|es|est|to|c['’]est|to\s+jest)?\s*"
        r"((?=[A-Z0-9\-]*\d)[A-Z0-9][A-Z0-9\-]{3,24})\b",
        I,
        group=1,
    )

    # Identifier-shaped codes without a keyword: "SL-4471920-03", "CB-20418-S3",
    # "W123456789", "D4429-60718-55231". Upper-case prefix plus at least three digits.
    add(EntityType.ID, r"\b(?=[A-Z0-9\-]*\d{3})[A-Z]{1,5}\d*(?:-[A-Z]{1,6})*-\d[A-Z0-9]*(?:-[A-Z0-9]+)*\b")
    add(EntityType.ID, r"\b[A-Z]{1,2}\d{6,12}\b")
    # US insurance member IDs with a three-letter prefix: "BSH9017734412", "BSH 440 118 2207".
    add(EntityType.HEALTH_CARD, r"\b[A-Z]{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3,6}\b|\b[A-Z]{3}\d{8,13}\b")
    # IBAN: "PL61 1090 1014 0000 0712 1981 2874".
    add(EntityType.ACCOUNT, r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?\b")
    # UUIDs (e-signature envelopes, portal record ids).
    add(EntityType.ID, r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", I)
    # Any long bare number (chart numbers, national IDs). Phones and other shapes
    # overlap and win on merge; amounts with separators are excluded.
    add(EntityType.ID, r"(?<![\d.,$€£])\b\d{7,}\b(?![.,]\d)")
    # A short letter prefix, a space, then the number: "RX 7714402", "TX 41982776",
    # "AUTH 66-120-883", "RX 3340-882". Not product and billing codes.
    add(
        EntityType.ID,
        r"\b(?!(?:NDC|CPT|ICD|LOT|HCPCS|DRG|REF|EXT|TEL|FAX|PH|DOB|DDN|FDN|DATE)\b)[A-Z]{2,4}[ #:]{1,2}\d[\d\-]{5,}\d\b",
    )
    # Group numbers: "GRP 40218", "Group: GRP 77020". A referral number: "referral number ... REF 4410-0289".
    add(EntityType.ACCOUNT, r"\bGRP[ #:\-]*\d{4,}(?:-\d+)?\b", I)
    add(
        EntityType.ACCOUNT,
        r"\breferral\s+(?:number|no\.?|#)?[^\n\d]{0,25}?\b(REF[ #:\-]*\d[\d\-]{3,}\d)\b",
        I,
        group=1,
    )
    # An account number with words before the value: "Número de cuenta para el reembolso: 0043-77120-9",
    # "חשבון 88-4471".
    add(
        EntityType.ACCOUNT,
        r"(?:\b(?:account|acct|cuenta|compte|konto|konta)\b|(?<![א-ת])חשבון(?![א-ת]))[^\n\d$€£]{0,30}?(\d[\d\-]{3,}\d)\b(?![.,]\d)",
        I,
        group=1,
    )
    # Member and certificate numbers in groups: "Certificat : 0071 5583 02", "מס' חבר: 7003 5521 88",
    # "numer ubezpieczenia to 9921-4470-18".
    add(
        EntityType.HEALTH_CARD,
        r"(?:\b(?:certificat|certificate|certificado|member|membre|miembro|ubezpieczeni[ae]|ubezpieczonego)\b|(?<![א-ת])חבר(?![א-ת]))"
        r"[^\n\d]{0,25}?(?<!\d)(\d{2,6}(?:[ \-]\d{2,6}){2,4})\b",
        I,
        group=1,
    )
    # Identity documents and tracking numbers after their name: "pasaporte es el AAB204117",
    # "permis de travail c'est 1234-5678-90", "Sponsor ID (DBN): 4471 8820 3391", "Tracking 1Z 999 AA1 01 2345 6784".
    add(
        EntityType.ID,
        r"(?:\b(?:passport|pasaporte|passeport|paszport|permis(?:\s+de\s+(?:travail|conduire|s[ée]jour))?|"
        r"work\s+permit|licen[cs]e|licencia|dbn|sponsor\s+id|tracking|c[ée]dula|(?:employee|student)\s+(?:id|number|no\.?)|"
        r"dow[óo]d(?:\s+osobist\w*)?)\b|"
        r"(?<![א-ת])דרכון(?![א-ת]))[^\n\d]{0,40}?"
        r"(?<![\w\-])(?P<v>(?:(?-i:[A-Z]{1,3})[ \-])?[A-Z0-9]{0,12}\d[A-Z0-9]{0,20}(?:[ \-][A-Z0-9]{0,12}\d[A-Z0-9]{0,12}){0,5})\b",
        I,
        group="v",
        check=_doc_number_check,
    )
    # Court and agency file numbers: "2026-FAM-00418", "500-17-123456-261", Colorado "2026DR30418",
    # "24-DR-1183", Polish "II C 1184/26" and "XVI RC 902/25", Israeli "12456-03-26".
    add(EntityType.ID, r"\b(?:19|20)\d{2}-[A-Z]{2,5}-\d{3,}\b")
    _case_types = r"CV|CR|DR|PR|JV|JD|JN|JR|PB|DV|FA|FL|PA|CI|SC|PO|MH|EP|CW|TR|SA|DP"
    add(EntityType.ID, rf"\b(?:19|20)\d{{2}}(?:{_case_types})\d{{3,7}}\b")
    add(EntityType.ID, rf"\b\d{{2}}-(?:{_case_types})-\d{{3,7}}\b")
    # County, case type, year, number: "27-FA-26-4410".
    add(EntityType.ID, rf"\b\d{{1,3}}-(?:{_case_types})-\d{{2}}-\d{{3,7}}\b")
    # A letter prefix, a short number, a slash and a longer number: policy "UB-77/204519".
    add(EntityType.ACCOUNT, r"\b[A-Z]{2,4}-\d{2,4}/\d{5,9}\b")
    add(EntityType.ID, r"\b[IVXL]{1,5}[ \t]+[A-Z][A-Za-z]{0,3}(?:[ \t]+[A-Z][a-z]{0,2})?[ \t]+\d{1,6}/(?:\d{4}|\d{2})\b")
    # A file number named as one: "Case no. 26-D-1183", "Index No. 12345/2026", "caso 0412-B".
    add(
        EntityType.ID,
        r"\b(?:case|index|docket|caso|expediente|dossier|sprawa|sygn\.?(?:\s+akt)?)\s*(?:no\.?|number|#|n[úu]m(?:ero)?\.?|nr\.?)?\s*:?\s*"
        r"(?<![\w\-])((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]{3,20}[A-Z0-9])\b",
        re.IGNORECASE,
        group=1,
        check=lambda m: sum(c.isdigit() for c in m.group(1)) >= 4 and not re.fullmatch(r"(?:19|20)\d\d", m.group(1)),
    )
    add(EntityType.ID, r"(?<![\d\-/.])\d{4,6}-(?:0[1-9]|1[0-2])-\d{2}(?![\d\-/]|\.\d)", check=lambda m: not re.match(r"(?:19|20)\d\d-", m.group(0)))
    # Prescription numbers: "Rx number 5520-1148", "Rx# 7710-4402", "receta n.º 4410-22".
    add(
        EntityType.ID,
        r"(?:\b(?:rx|prescription|receta|ordonnance|recepta)\b|(?<![א-ת])מרשם(?![א-ת]))[ \t]*(?:#|no\.?|nr\.?|n\.?º|number|num[ée]ro|n[úu]mero|numer|מס['׳]?)?"
        r"(?:[ \t]+is)?[ \t]*:?[ \t]*(?<![\w\-])(\d[\d\-]{4,14}\d)\b(?![.,/]\d)",
        re.IGNORECASE,
        group=1,
        check=lambda m: sum(c.isdigit() for c in m.group(1)) >= 6,
    )
    # Venezuelan and Colombian cédulas: "V-18.442.907", "C.C. 1.020.345.678".
    add(EntityType.ID, r"\b[VEJ]-?\d{1,2}\.\d{3}\.\d{3}\b|\bC\.?C\.?[ \t]*\d{1,3}(?:\.\d{3}){2,3}\b")
    add(EntityType.ID, r"\bc[ée]dula\b[^\n\d]{0,20}?(\d{1,3}(?:\.\d{3}){2,3})\b", re.IGNORECASE, group=1)
    # Portal usernames: "my username is hunter.bale", "login: mgarcia88".
    add(
        EntityType.ID,
        r"\b(?:user\s*name|username|login|user\s*id|usuario|nombre\s+de\s+usuario|nom\s+d['’]utilisateur|identifiant|nazwa\s+u[żz]ytkownika)"
        r"(?:[^\S\n]+(?:for|on|in|de|du|na|w)[^\S\n]+[^\W\d_]+(?:[^\S\n]+[^\W\d_]+)?|[^\S\n]*\([^)\n]{1,20}\)|[^\S\n]+I\s+use)?"
        r"(?:[^\S\n]+(?:is|was|es|est|to)[^\S\n]*:?[^\S\n]*|[^\S\n]*[:=][^\S\n]*)[\"“'‘]?@?((?=[\w.\-]*[A-Za-z]|\d{4})[A-Za-z0-9][\w.\-]{1,40}[A-Za-z0-9])",
        re.IGNORECASE,
        group=1,
        check=_username_check,
    )
    # Social handles: "@thaolee_ttc", "@ruiz.baby.hopes" (a letter first, so not "@ 5pm" or "@10am").
    add(EntityType.ID, r"(?<![\w@.])@[A-Za-z_][\w.]{2,28}[A-Za-z0-9_]\b(?!@)", check=_handle_check)
    # A username right after its cue with no "is": "user gwen_larue_77", "Username yael.peretz88".
    add(
        EntityType.ID,
        r"\b(?:user\s*name|username|login|user|usuario)[^\S\n]+[\"“'‘]?"
        r"((?=[A-Za-z0-9._]*[A-Za-z])(?:[A-Za-z][A-Za-z0-9]{1,20}[._][A-Za-z0-9._]{1,20}|[A-Za-z]{3,20}\d{2,6}|[A-Za-z0-9]{2,20}_[A-Za-z0-9_]{1,20})[A-Za-z0-9])(?![\w@\-]|\.\w)",
        re.IGNORECASE,
        group=1,
    )
    # A personal site without a scheme after a cue: "post on amywhitcombe.example.com", "my blog is jane-doe.com".
    add(
        EntityType.URL,
        r"\b(?:web\s*site|site|blog|page|fundraiser|journal|visit|(?:post(?:ing)?|posted|check(?:\s+out)?|go|find\s+(?:us|me))\s+(?:on|at))"
        r"(?:[^\S\n]+(?:is|at|on))?[^\S\n]*:?[^\S\n]+"
        rf"((?:[a-z0-9][a-z0-9\-]{{0,40}}\.){{1,4}}(?:com|org|net|ca|io|me|co|blog)(?:/{_U}|/)?)(?![\w@\-]|\.\w)",
        I,
        group=1,
        check=_bare_site_check,
    )
    # Vehicle plates after their name: "my plate is QXE-J45", "placa ABC 1234".
    add(
        EntityType.ID,
        r"(?i:\b(?:licen[cs]e\s+plate|plate\s+(?:number|no\.?|#)|(?:my|his|her|our|their|car|vehicle)\s+plate|plate\s+is|plate(?=\s*:)|"
        r"placas?|plaque(?:\s+d['’]immatriculation)?|tablic\w*\s+rejestracyjn\w*|numer\s+rejestracyjny|matr[íi]cula|immatriculation)\b)"
        r"[^\n\d]{0,12}?(?<![\w\-])((?=[A-Z0-9\- ]*\d)(?=[A-Z0-9\- ]*[A-Z])[A-Z0-9]{1,4}[\- ]?[A-Z0-9]{1,5}|"
        r"(?=[a-z0-9]*\d)(?=[a-z0-9]*[a-z])[a-z0-9]{5,8})\b",
        group=1,
        check=lambda m: len(m.group(1).replace(" ", "").replace("-", "")) >= 5,
    )
    add(EntityType.ID, r"(?<![א-ת])(?:מספר\s+)?רישוי[^\n\d]{0,10}(\d{2,3}-\d{2,3}-\d{2,3})\b", group=1)
    # Identifiers read out one digit at a time after a number word: "Hospital number 0 0 5 5 2 1 8",
    # "Numer pacjenta 0 0 8 8 1 3 2", "מספר תיק 0 0 7 7 4 1 9".
    add(
        EntityType.ID,
        r"(?:\b(?:hospital|patient|chart|record|file|member|policy|account|case|health\s+card|mrn|id)\s+(?:number|no\.?|#|id)|"
        r"\b(?:numer\w*|nr\.?)\s+(?:pacjent\w*|karty|kartoteki|ubezpieczenia|polisy|konta)\b|"
        r"\bn[úu]mero\s+de\s+(?:expediente|paciente|historia|p[óo]liza|cuenta|miembro)\b|"
        r"\bnum[ée]ro\s+de\s+(?:dossier|patient|police|compte|membre)\b|"
        r"(?<![א-ת])(?:מספר\s+)?(?:תיק|מטופל|חבר|פוליסה)(?![א-ת]))[^\n\d]{0,25}?"
        r"(?<!\d)(?<!\d[ \t,\-])(\d(?P<sep>[ \t]{1,2}|,[ \t]?|-)\d(?:(?P=sep)\d){4,12})(?![ \t,\-]?\d)",
        re.IGNORECASE,
        group=1,
    )
    add(EntityType.ID, r"\b\d{3}-\d{2}-\d{6}-\d{3}\b")
    # Member IDs read off a card in groups after a member keyword: "miembro GCM 70 4418 21".
    add(
        EntityType.HEALTH_CARD,
        rf"\b(?:member|miembro|membre|cz[łl]onk\w*|identificaci[oó]n|id)\b[^\n\d]{{0,25}}?\b((?!(?-i:{_SHORT_WORDS})\b)[A-Z]{{2,4}}(?:[ \-]\d{{2,5}}){{3,4}})\b",
        I,
        group=1,
    )
    # Payment card numbers in 4-4-4-4 groups, Luhn-checked.
    add(
        EntityType.ACCOUNT,
        r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",
        check=lambda m: _luhn_ok(_digits(m.group(0))),
    )

    # Typed into a chat about paying by card, or followed by an expiry: no checksum needed.
    add(
        EntityType.ACCOUNT,
        r"(?<![\d\-])[2-6]\d{3}[ \-]\d{4}[ \-]\d{4}[ \-]\d{4}(?![\d\-])",
        check=_card_context,
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
        rf"\b(?:ending(?:\s+in)?|ends\s+in|last\s+(?:4|four)(?:\s+digits)?(?:\s+of\s+(?:my|the|your|her|his)\s+\w+)?(?:\s+(?:are|is))?|termin[ée]e?\s+par|"
        rf"terminada\s+en)\s*:?\s*(\d{{4}}|{_ANY_DIGIT_WORD}(?:\s+{_ANY_DIGIT_WORD}){{3}})\b",
        I,
        group=1,
    )
    # Other ways to say it, only after a card or account word: "tarjeta que termina en 9027",
    # "kartą kończącą się na 4471", "הכרטיס שלי נגמר ב-3308", "carte finissant par 4471".
    add(
        EntityType.ACCOUNT,
        rf"(?:\b(?:card|carte|tarjeta|karta|kart[ąy]|account|compte|cuenta|konto|visa|mastercard|amex)\b|(?<![א-ת])ו?ה?כרטיס)"
        rf"[^\n\d]{{0,60}}?(?:\b(?:ending\s+with|ends(?:\s+with)?|termina(?:da)?\s+(?:en|con)|acaba\s+en|terminaci[óo]n|z\s+ko[ńn]c[óo]wk[ąa]|"
        rf"(?:se\s+)?termin(?:ant|e)\s+par|finit\s+par|(?:les\s+)?(?:4|quatre)\s+derniers\s+chiffres|"
        rf"ko[ńn]cz[ąa]c[aąey]j?\s+si[ęe]\s+na|ko[ńn]czy\s+si[ęe]\s+na|ostatnie\s+(?:4|cztery)\s+cyfry(?:\s+karty)?|"
        rf"[úu]ltimos\s+(?:4|cuatro)\s+d[íi]gitos|se\s+terminant\s+par|finissant\s+par|qui\s+finit\s+par)|"
        rf"(?<![א-ת])ש?(?:נגמר|נגמרת|מסתיים|מסתיימת)\s+ב-?|(?<![א-ת])(?:4|ארבע)\s+ספרות\s+אחרונות)"
        rf"\s*:?\s*(\d{{4}}|{_ANY_DIGIT_WORD}(?:\s+{_ANY_DIGIT_WORD}){{3}})(?!\w)",
        I,
        group=1,
    )
    add(EntityType.ACCOUNT, r"(?<![\w*•])(?:\d{4}[\s\-]+)?(?:[xX*•]{4}[\s\-]+){1,3}\d{4}\b")
    add(EntityType.ACCOUNT, r"(?:(?<![\w*•])[xX*•]{2,}|(?<=[A-Za-z0-9])[*•]{2,})[\s\-]?\d{4}\b")
    # First digits, a masked middle and the last four: "5500********0004", "411111******1111".
    add(EntityType.ACCOUNT, r"\b\d{2,6}[xX*•]{2,12}\d{4}\b")
    # The card named inside the phrase: "ostatnie 4 cyfry karty: 4471", "últimos cuatro dígitos de mi tarjeta 4471".
    add(
        EntityType.ACCOUNT,
        r"\b(?:ostatnie\s+(?:4|cztery)\s+cyfry\s+karty|[úu]ltimos\s+(?:4|cuatro)\s+d[íi]gitos\s+de\s+(?:la|mi|su)\s+tarjeta|"
        r"(?:4|quatre)\s+derniers\s+chiffres\s+de\s+(?:la|ma|sa)\s+carte)\s*:?\s*(\d{4})\b",
        re.IGNORECASE,
        group=1,
    )

    # Quebec RAMQ: 4 letters + 8 digits.
    add(EntityType.HEALTH_CARD, r"\b[A-Z]{4}\s?\d{4}\s?\d{4}\b")
    # Ontario OHIP in its printed 4-3-3 grouping, optional 2-letter version code.
    add(EntityType.HEALTH_CARD, r"\b\d{4}[\s\-]\d{3}[\s\-]\d{3}(?:[\s\-]?[A-Z]{2})?\b")

    add(EntityType.SSN, r"\b(\d{3})-(\d{2})-(\d{4})\b", check=_ssn_check)
    # Masked SSN with the last four: "xxx-xx-6291", "***-**-6291".
    add(EntityType.SSN, r"(?<![\w*])[xX*]{3}-[xX*]{2}-\d{4}\b")
    # Named as a social security number, any first group: "my social is 972-22-8271".
    add(EntityType.SSN, r"\b(?:social|ssn|seguro\s+social)\b[^\n\d]{0,20}(\d{3}-\d{2}-\d{4})\b", I, group=1)
    # Polish nine-digit phones after a phone word: "Mój nowy numer to 555 418 988".
    add(
        EntityType.PHONE,
        r"\b(?:numer\w*|nr|tel\.?|telefon\w*|kom[óo]rk\w*)\b[^\n\d]{0,20}(?<!\d)(\d{3}[\s\-]\d{3}[\s\-]\d{3}|\d{2}[\s\-]\d{3}[\s\-]\d{2}[\s\-]\d{2})\b(?![\s\-]\d)",
        I,
        group=1,
    )
    # Only the end of the number, after its name: "last 4 of my SSN, 0932", "SSN ends in 0932",
    # "mon NAS finit par 417".
    _partial = (
        r"(?:ends?\s+(?:in|with)|ending(?:\s+(?:in|with))?|finit\s+par|se\s+termine\s+par|termine\s+par|termin[ée]e?\s+par|"
        r"termina\s+(?:en|con)|acaba\s+en|ko[ńn]cz[ąy]\s+si[ęe]\s+na|"
        r"last\s?(?:4|four|3|three)(?:\s+digits)?(?:\s+(?:are|is))?)"
    )
    _last_of = (
        r"(?:last\s?(?:4|four|3|three)(?:\s+(?:digits|numbers))?(?:\s+of)?\s+(?:(?:my|the|your|her|his)\s+)?"
        r"|(?:les\s+)?(?:4|quatre|3|trois)\s+derniers\s+(?:chiffres\s+)?(?:de\s+)?(?:mon\s+|ma\s+|le\s+|la\s+)?)"
    )
    add(
        EntityType.SSN,
        rf"\b(?:ssn|social\s+security(?:\s+number)?|social|(?:n[úu]mero\s+de\s+)?seguro\s+social)\b[^\n\d]{{0,25}}?\b{_partial}\W{{0,3}}(\d{{3,4}})(?!\d)",
        I,
        group=1,
    )
    add(
        EntityType.SIN,
        rf"(?:\b(?-i:SIN|NAS)|\b(?:my|your|her|his|mi|mon)\s+sin|\bsocial\s+insurance(?:\s+number)?)\b[^\n\d]{{0,25}}?\b{_partial}\W{{0,3}}(\d{{3,4}})(?!\d)",
        I,
        group=1,
    )
    add(
        EntityType.ID,
        rf"\b(?:pesel|numer\s+pesel)\b[^\n\d]{{0,25}}?\b{_partial}\W{{0,3}}(\d{{3,4}})(?!\d)",
        I,
        group=1,
    )
    add(
        EntityType.SSN,
        rf"\b{_last_of}(?:ssn|social(?:\s+security)?(?:\s+number)?|seguro\s+social)\b(?:\s+(?:are|is|was))?\W{{0,4}}(\d{{3,4}})(?!\d)",
        I,
        group=1,
    )
    add(
        EntityType.SIN,
        rf"\b{_last_of}(?:(?-i:SIN|NAS)|sin|social\s+insurance(?:\s+number)?)\b(?:\s+(?:are|is|was))?\W{{0,4}}(\d{{3,4}})(?!\d)",
        I,
        group=1,
    )
    add(EntityType.SIN, r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}\b", check=_sin_check)
    add(
        EntityType.SIN,
        r"\b(?:sin|social\s+insurance(?:\s+number)?|nas|num[ée]ro\s+d['’]assurance\s+sociale)\b[^\d\n]{0,25}?"
        r"(\d{3}[\s\-]?\d{3}[\s\-]?\d{3})\b",
        I,
        group=1,
    )
    # National identifiers of international patients.
    # Mexican CURP and RFC: "FUSD880412MDFNLN07", "NAVG800312015".
    add(EntityType.ID, r"\b[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d\b")
    add(EntityType.ID, r"\b[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}\b")
    # Spanish DNI and NIE: "50812345K", "X1234567L".
    add(EntityType.ID, r"\b(?:\d{8}|[XYZ]\d{7})-?[A-HJ-NP-TV-Z]\b")
    # French social security number (NIR): "2 90 03 75 112 233 45".
    add(EntityType.ID, r"\b[12][\s.]?\d{2}[\s.]?(?:0[1-9]|1[0-2]|[2-9]\d)[\s.]?(?:\d{2}|2[AB])[\s.]?\d{3}[\s.]?\d{3}(?:[\s.]?\d{2})?\b")
    # French phone numbers: "06 55 50 01 23", "01.45.55.01.23".
    add(EntityType.PHONE, r"(?<![\d+])\b0[1-9](?:[\s.]\d{2}){4}\b")
    # IPv6: "2001:db8:4a1c::17".
    add(
        EntityType.IP_ADDRESS,
        r"(?<![\w:])[0-9a-f]{1,4}(?::[0-9a-f]{0,4}){2,7}(?![\w:])",
        I,
        check=lambda m: "::" in m.group(0) or m.group(0).count(":") == 7,
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
        r"(?:(?<![\w+])|(?<=(?<!\w)[ולבמהש])|(?<=(?<!\w)[ולבמהש]-))(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\d{3})(?:[ \t]\n|[\s.\-]?|\s*(?:\.\.\.|…)\s*)\d{3}"
        r"(?:[ \t]\n|[\s.\-]?|-[ \t]*\n[ \t]*|\s*(?:\.\.\.|…)\s*)\d{4}\b"
        r"(?:\s*(?:x|ext\.?)\s*\d{1,5})?",
        I,
    )
    # A number split after its first hyphen onto the next line ("651-\n555-0166"); the end of the
    # line after the second one is handled by the general rule above.
    add(
        EntityType.PHONE,
        r"(?<![\w+\-])(?:\(\d{3}\)|\d{3})-[ \t]*\n[ \t]*\d{3}[\s.\-]\d{4}\b",
    )
    # Digits typed with stray dots or spaces ("651 555 0.1.7.2", "651-555-0 1 7 2") and the
    # last digits hidden ("(763) 555-01xx", "612-555-xxxx").
    add(
        EntityType.PHONE,
        r"(?<![\w+.\-])(?:\(\d{3}\)|\d{3})[\s.\-]{1,2}\d{3}[\s.\-]{1,2}\d(?:[ .]\d){3}(?![\w.]\d|\d)"
        r"|(?<![\w+.\-])(?:\(\d{3}\)|\d{3})[\s.\-]{1,2}\d{3}[\s.\-]{1,2}(?:\d{2}[xX*#]{2}|[xX*#]{4})(?![\w])",
    )
    # International numbers written with a leading +.
    add(EntityType.PHONE, r"(?:(?<!\w)|(?<=(?<!\w)[ולבמהש]))\+(?:[2-9]\d{0,2})[\s.\-]?\d(?:[\s.\-]?\d){6,12}\b")

    # International numbers with a trunk digit or an area code in brackets, or a 00 prefix:
    # "+44 (0)20 7946 0958", "+7 (495) 123-45-67", "00 33 6 12 34 56 78".
    add(
        EntityType.PHONE,
        r"(?:(?<![\w+])\+|(?<![\w\d])00[ ])[1-9]\d{0,2}[ .\-]?\(\d{1,4}\)[ .\-]?\d(?:[ .\-]?\d){5,11}\b"
        r"|(?<![\w\d])00[ ][1-9]\d{0,2}[ .]\d(?:[ .]?\d){6,11}\b",
    )
    # Numbers spoken digit by digit (call transcripts): "four one six five five five ..."
    add(EntityType.PHONE, rf"\b{_ANY_DIGIT_WORD}(?:[\s,\-]+{_ANY_DIGIT_WORD}){{6,11}}\b", I)
    # Ten or eleven digits in groups of any size after a phone word: "my number is 41 65 55 01 23",
    # "416-555-01 23".
    add(
        EntityType.PHONE,
        r"\b(?:phone|cell(?:ular)?|mobile|tel|number|call\s+me|text\s+me|reach\s+me|contact\s+me|landline|fax|whatsapp|"
        r"num[ée]ro|t[ée]l[ée]phone|c['’]est\s+le)\b[^\n\d]{0,25}?"
        r"(?<![\d+\-])(\d{1,5}(?:[ .\-]\d{1,5}){2,12})(?![\d]|[ .\-]\d)",
        I,
        group=1,
        check=lambda m: sum(c.isdigit() for c in m.group(1)) in (10, 11),
    )
    # Emails written to dodge filters: "ana [at] example [dot] org", "m_t88(at)example(dot)com", "x (at) example . com".
    # The at-word must sit in brackets, so a plain "at" never triggers this.
    # A plain dot takes no space after it unless it also has one before (" . "), and never a line
    # break: "sarah(at)gmail.com. Bye" ends at "com".
    _dot = r"(?:[ \t]{0,2}[\[({]\s{0,2}dot\s{0,2}[\])}][ \t]{0,2}|[ \t]{1,2}\.[ \t]{1,2}|\.)"
    add(
        EntityType.EMAIL,
        rf"(?<![\w.@])[A-Za-z0-9][\w%+\-]{{0,40}}(?:{_dot}[\w%+\-]{{1,40}}){{0,4}}"
        r"[ \t]{0,2}[\[({]\s{0,2}(?:at|@)\s{0,2}[\])}][ \t]{0,2}"
        rf"[A-Za-z0-9][A-Za-z0-9\-]{{0,40}}(?:{_dot}[A-Za-z0-9][A-Za-z0-9\-]{{0,40}}){{0,3}}"
        rf"{_dot}[A-Za-z]{{2,}}\b",
        I,
    )
    # A written local part may itself hold dots or hyphens: "sarah.k.cohen at gmail dot com".
    _LOCAL_WORD = r"\w+(?:[.\-]\w+){0,4}"
    # "sarah cohen at gmail dot com": a second word in front of the local part is part of the name,
    # unless it is a common word that leads into the address ("email", "is", "call", ...).
    _LEAD_STOP = (
        "my|me|is|it|its|the|a|an|and|or|to|at|on|in|of|for|from|by|with|so|ok|okay|yes|no|then|but|if|i|im|we|you|"
        "email|emails|mail|address|call|text|send|sent|tell|ask|contact|reach|message|write|use|here|there|this|that|"
        "please|thanks|thank|hi|hello|hey|dr|mr|mrs|ms|miss|mon|ma|mi|mis|mes|est|es|c|ce|le|la|el|de|du|et|y|e|o|u|"
        "adres|email|mejl|moj|mój|jest|to|na|do|jak|lub"
    )
    _LEAD_WORD = rf"(?:(?!(?:{_LEAD_STOP})\b)[^\W\d_]{{2,20}}[ \t]+)?"
    # Spoken emails: "chen dot wei at example dot com", "julie point savard arobase ...".
    add(
        EntityType.EMAIL,
        rf"(?<![\w.\-@]){_LEAD_WORD}{_LOCAL_WORD}(?:\s+(?:dot|point|punto|kropka|underscore|dash)\s+{_LOCAL_WORD}(?:[\s\-]+(?:{_SPOKEN_NUMBER}|{_SPOKEN_NUMBER_ML}|\d{{1,4}}|y|et|i|and)){{0,6}}){{0,6}}"
        r"\s+(?:at|arobase|arroba|ma[łl]pa)\s+"
        r"\w+(?:\s+(?:dot|point|punto|kropka)\s+\w+){0,4}\s+(?:dot|point|punto|kropka)\s+"
        r"(?:com|org|net|ca|edu|gov|io|co|uk|fr|es|pl|il)\b",
        I,
    )
    # A spoken at-word before a written domain: "ania małpa gmail.com", "ana arroba wp.pl".
    add(
        EntityType.EMAIL,
        rf"(?<![\w.\-@]){_LEAD_WORD}{_LOCAL_WORD}(?:\s+(?:dot|point|punto|kropka|underscore|dash)\s+{_LOCAL_WORD}(?:[\s\-]+(?:{_SPOKEN_NUMBER}|{_SPOKEN_NUMBER_ML}|\d{{1,4}}|y|et|i|and)){{0,6}}){{0,6}}"
        r"\s+(?:arobase|arroba|ma[łl]p[aąę])\s+"
        r"[A-Za-z0-9][A-Za-z0-9\-]{0,40}(?:\.[A-Za-z0-9][A-Za-z0-9\-]{0,40}){0,3}\.[A-Za-z]{2,10}(?![\w@\-])",
        I,
    )
    # A plain "at" for "@" is an email only when the shape is unmistakable: a local part with a dot,
    # hyphen, underscore or digit before a domain with a TLD ("jane.doe at gmail.com"), or any local part
    # before a webmail provider with a TLD ("jane at gmail com").
    _tld = r"(?:com|org|net|ca|edu|gov|io|co|uk|fr|es|pl|il|info|us|de)"
    _at_sep = r"(?:[ \t]{1,2}at[ \t]{1,2}|[ \t]{1,2}@[ \t]{0,2}|@[ \t]{1,2})"
    _webmail = r"(?:gmail|googlemail|yahoo|ymail|hotmail|outlook|live|msn|icloud|aol|proton(?:mail)?|me|mail)"
    add(
        EntityType.EMAIL,
        rf"(?<![\w.@\-])(?:[A-Za-z][\w%+]{{0,40}}(?:[.\-][\w%+]{{1,40}}){{1,4}}|[A-Za-z][A-Za-z%+]{{0,40}}[\d_][\w%+]{{0,40}})"
        rf"{_at_sep}[A-Za-z0-9][A-Za-z0-9\-]{{0,40}}(?:\.[A-Za-z0-9][A-Za-z0-9\-]{{0,40}}){{0,3}}\.{_tld}(?![\w@])"
        rf"|(?<![\w.@\-])[A-Za-z][\w%+]{{0,40}}{_at_sep}{_webmail}(?:\.|[ \t]{{1,2}}dot[ \t]{{1,2}}|[ \t]{{1,2}}){_tld}(?![\w@])",
            I,
        check=_plain_at_check,
    )
    # Spelled-out words ("k o w a l c z y k", "W-O-J-C-I-K") are almost always names.
    add(EntityType.NAME, _names.SPELLED, check=_not_alphabet_run)
    # Letters each given a key word ("c comme Charles o comme Oscar h comme Hotel", "A as in Alpha N as in
    # November"): three of them, or two after a spelling cue. The word must start with its letter.
    _kw = r"[A-Za-z][ \t]+(?:as[ \t]+in|comme|como|for|de)[ \t]+[^\W\d_]+"
    _kw_ok = lambda m: all(  # noqa: E731
        w[0].lower() == l.lower()
        for l, w in re.findall(r"(?:^|[ \t,])([A-Za-z])[ \t]+(?:as[ \t]+in|comme|como|for|de)[ \t]+([^\W\d_]+)", m.group("name"), re.I)
    )
    add(
        EntityType.NAME,
        rf"(?<![\w\-'’])(?P<name>{_kw}(?:[ \t]*,?[ \t]*{_kw}){{2,8}})(?![\w\-'’])",
        I,
        check=_kw_ok,
    )
    add(
        EntityType.NAME,
        rf"\b(?i:spell(?:ed|ing|s)?|letters?)\b[ \t:,]+(?i:(?:it|that|my\s+name|name)[ \t]+)?(?:is[ \t]+)?"
        rf"(?P<name>{_kw}(?:[ \t]*,?[ \t]*(?:{_kw}|(?-i:[A-Z])(?![\w'’\-]))){{1,8}})(?![\w\-'’])",
        I,
        check=_kw_ok,
    )
    # Only three letters ("A-N-A"): a name when someone is spelling it, not "I-V-F" or "H-C-G".
    add(
        EntityType.NAME,
        r"(?i:\b(?:spell(?:ed|ing|s)?|letters?|(?:it|that)(?:['’]s|\s+is)|is|goes)(?:,?\s+(?:uh|um|so|like))?),?\s+"
        r"((?<![\w\-])[A-Z](?:-[A-Z]){2}(?![\w\-]))",
        group=1,
        check=lambda m: (w := m.group(1).replace("-", "")) not in _ACRONYMS_3 and w.lower() not in "abcdefghijklmnopqrstuvwxyz",
    )
    # Letters given one by one with dots after a spelling or name cue: "my name is S. A. R. A. H."
    add(
        EntityType.NAME,
        r"(?i:\b(?:spell(?:ed|ing|s)?|letters?|(?:my\s+|the\s+)?name\s+is|(?:se\s+)?escribe|nombre\s+es|"
        r"(?:ça\s+)?s['’]écrit|je\s+m['’]appelle|nazywam\s+si[ęe]))[ \t:,]+(?:(?:it|that|is)[ \t]+)?(?P<name>(?-i:[A-Z])\.(?:[ \t]?(?-i:[A-Z])\.){2,9})(?![\w\-])",
        check=lambda m: m.group("name").replace(".", "").replace(" ", "").replace("\t", "").upper() not in _ACRONYMS_3,
    )
    # A social handle given without "@" after a platform word: "ig: jane88doe", "my instagram is jane_88".
    # It must have a digit or underscore, so plain words after the cue ("instagram is private") stay.
    add(
        EntityType.ID,
        r"\b(?:instagram|insta|ig|tiktok|tik\s*tok|twitter|snap(?:chat)?|facebook|fb|threads|bluesky|telegram|handle|"
        r"\u05d4?(?:\u05d0\u05d9\u05e0\u05e1\u05d8\u05d2\u05e8\u05dd|\u05d8\u05d9\u05e7\u05d8\u05d5\u05e7|\u05d8\u05d5\u05d5\u05d9\u05d8\u05e8|\u05e4\u05d9\u05d9\u05e1\u05d1\u05d5\u05e7|\u05e1\u05e0\u05d0\u05e4\u05e6['\u05f3]?\u05d0\u05d8))\b"
        r"(?:[\s:=,@\-]|\b(?:is|it['’]?s|i['’]?m|i\s+am|my|handle|user\s*name|account|name|profile|page|at|on|as|c['’]est|est|es|to|sur|en|na|"
        r"\u05d4\u05d5\u05d0|\u05e9\u05dc\u05d9|\u05d1)\b){1,30}?"
        r"(?<![\w@.])(?!(?:is|it|its|i|im|am|my|handle|user|username|account|name|profile|page|at|on|as|est|es|to|sur|en|na)(?![\w.]))([A-Za-z][A-Za-z0-9._]{1,27}[A-Za-z0-9_])(?![\w@])",
        I,
        group=1,
        check=lambda m: bool(re.search(r"[\d_]", m.group(1))) and not _clinic_owned(m.string, m.start(1), m.end(1)),
    )
    # Postal codes read aloud: "n one h four k seven".
    add(
        EntityType.POSTAL_CODE,
        rf"\b[a-z]\s+{_ANY_DIGIT_WORD}\s+[a-z]\s+{_ANY_DIGIT_WORD}\s+[a-z]\s+{_ANY_DIGIT_WORD}\b",
        I,
    )

    # Dates. Year-only is not PHI under Safe Harbor, so it is not matched.
    add(EntityType.DATE, r"(?<![^\W_])\d{4}-\d{1,2}-\d{1,2}(?:(?![^\W_])|(?=T\d))")
    # Year and month only is still a date element under Safe Harbor.
    add(EntityType.DATE, r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])\b(?!-\d)", check=lambda m: _not_expiry(m) and _not_doc_period(m))
    # Month and year in digits ("SA 12/2025"), not an expiry.
    add(EntityType.DATE, r"(?<![\d/.\-])(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}(?![\d/])", check=lambda m: _not_expiry(m) and _not_lab_value(m, dot_only=False) and _not_doc_period(m))
    # Digits partly hidden in a date of birth: "03/xx/1988", "XX/05/1990", "09/??/1991".
    add(
        EntityType.DATE,
        r"(?<![\w/.\-])(?:(?:0?[1-9]|[12]\d|3[01])[/\-.](?:[xX]{1,2}|\?\?|\*\*|_{2})|(?:[xX]{1,2}|\?\?|\*\*|_{2})[/\-.](?:0?[1-9]|[12]\d|3[01]))"
        r"[/\-.](?:19|20)\d{2}(?![\w/])",
    )
    # The same read aloud in Spanish: "tres, equis equis, mil novecientos ochenta y ocho".
    add(
        EntityType.DATE,
        rf"(?<!\w)(?:{_DAY_WORDS_FR_ES}|\d{{1,2}})(?:,?\s+(?:equis|x))+,?\s+(?:(?:mil|novecientos|ochocientos)\s+)(?:(?:{_YEAR_WORDS})(?!\w)[\s\-]*){{1,6}}",
        I,
    )
    add(EntityType.DATE, rf"\b\d{{1,2}}[\s\-/.](?:{_MONTHS})[\s\-/.]\d{{2,4}}\b", I)
    # With an abbreviated weekday in front, as in a quoted reply header: "lun, 2 mar 2026", "wt., 12 sty 2026".
    add(
        EntityType.DATE,
        r"(?<![\w])(?:(?:lun|mar|mi[ée]|jue|vie|s[áa]b|dom|mer|jeu|ven|sam|dim|pon|wt|[śs]r|czw|pt|sob|niedz|nd)\.?,?\s+)"
        r"\d{1,2}[\s\-/.]+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|f[ée]vr|avr|juil|sept|d[ée]c|ene|abr|ago|dic|"
        r"sty|lut|kwi|cze|lip|sie|wrz|pa[źz]|lis|gru)[a-zé]{0,6}\.?[\s\-/.]+(?:19|20)\d{2}\b",
        I,
    )
    add(EntityType.DATE, r"(?:\b|(?<=[בלמהו]))\d{1,2}[/\-.]\d{1,2}[/\-.](?:\d{4}|\d{2})\b")
    add(
        EntityType.DATE,
        rf"\b(?:(?:{_WEEKDAY}|{_WEEKDAY_ML}),?\s+)?(?P<month>{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?"
        rf"(?:\s*(?:[\u2013\u2014\-]|to|through|thru|until)\s*\d{{1,2}}(?:st|nd|rd|th)?(?!\d|[:/.]\d|\s*(?:am|pm|a\.m|p\.m|h\b|mg|ml)))?"
        rf"(?:,?\s+\d{{4}})?\b",
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
    _day_alone = (
        rf"(?:{_ORDINAL_WORDS.replace(')|first|', ')|', 1)})(?=\s*(?:[.,?!;)/\n]|$|instead|right|then|works|and|"
        rf"i\s+think|so|at\s+(?:\d|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|noon)|or|okay|"
        rf"ok|please|correct|is|was|with\s+(?:dr|doctor|the)|of\s+(?:this|next|the)\s+month))"
    )
    add(EntityType.DATE, rf"\bthe\s+{_day_alone}", I)
    add(EntityType.DATE, rf"(?:^|\n|:)[^\S\n]*({_day_alone})", I | re.M, group=1)
    # French, Spanish, Polish, Hebrew: "le 12 mai 1990", "1er décembre", "jueves 6 de noviembre".
    add(
        EntityType.DATE,
        rf"(?<![0-9A-Za-zÀ-ž])(?:(?:le|el|du|au)\s+)?(?:(?:{_WEEKDAY_ML}),?\s+)?\d{{1,2}}(?:er|re|º|\.|-(?:go|ego))?\s+"
        rf"(?:de\s+|ב)?(?:{_MONTHS_ML})"
        rf"(?:,?\s+(?:del?\s+)?(?:\d{{4}}|este\s+a[ñn]o|\d{{2}}(?![\d:hH]|\s*(?:h\b|heures?|horas?|godz))))?(?!\w)",
        I,
    )
    add(EntityType.DATE, rf"\b(?:{_WEEKDAY_ML})\s+\d{{1,2}}\b(?![:.,]?\d)", I)
    # Spoken: "le quatorze mars mille neuf cent quatre-vingt-huit", "el veinte de
    # noviembre", "trzeciego lipca tysiąc dziewięćset...", "ארבעה עשר בפברואר".
    add(
        EntityType.DATE,
        rf"(?<!\w)(?:(?:le|el)\s+)?(?:{_DAY_WORDS_FR_ES}|{_DAY_WORDS_PL})\s+(?:de\s+)?(?:{_MONTHS_ML})(?!\w)"
        rf"(?:(?:\s+del?)?(?:[\s\-]+(?:{_YEAR_WORDS})(?!\w)){{1,8}}|\s+de\s+(?:este|ese)\s+a[ñn]o(?!\w)|\s+del\s+a[ñn]o\s+pasado(?!\w))?",
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
        r"(?<![\d])\b\d{1,2}(?:er)?[\s\-/]+(?:janv|f[ée]vr|avr|juil|sept|d[ée]c|ene|abr|ago|dic|sty|lut|kwi|cze|lip|sie|wrz|pa[źz]|lis|gru)\b\.?"
        r"(?:[\s\-/]+(?:19|20)\d{2}\b)?",
        I,
    )
    # The first day in a list before a month: "18 y 20 de noviembre", "18 i 20 listopada",
    # "ב-18 וב-20 בנובמבר", "the 18th and 20th of May".
    add(
        EntityType.DATE,
        rf"(?<![\d/.])(?:ב-?)?(\d{{1,2}}(?:st|nd|rd|th|er)?)\s*(?:,|&|and|et|y|e|i|oraz|ו|וב-?|ול-?)\s*(?:ב-?)?"
        rf"\d{{1,2}}(?:st|nd|rd|th|er)?\s+(?:of\s+|de\s+|ב)?(?:{_MONTHS}|{_MONTHS_ML})\b",
        I,
        group=1,
    )
    # A range of days before a month, as one date: "9 al 12 de diciembre", "od 9 do 12 grudnia",
    # "מ-9 עד 12 בדצמבר", "du 24 au 28 décembre", "December 9 to 12" is handled by the month rules.
    add(
        EntityType.DATE,
        rf"(?<![\d/.])\d{{1,2}}(?:st|nd|rd|th|er)?\s*(?:al|a|au|à|do|to|through|thru|till|until|-|–|עד)\s*"
        rf"\d{{1,2}}(?:st|nd|rd|th|er)?\s+(?:of\s+|de\s+|ב)?(?:{_MONTHS}|{_MONTHS_ML})\b",
        I,
    )
    # Spaced dates from scanned forms: "1985 / 06 / 22". "the 3rd day of September, 2025".
    add(EntityType.DATE, r"\b(?:19|20)\d{2}\s*/\s*(?:0?[1-9]|1[0-2])\s*/\s*(?:0?[1-9]|[12]\d|3[01])\b")
    add(EntityType.DATE, rf"\b\d{{1,2}}(?:st|nd|rd|th)\s+day\s+of\s+(?:{_MONTHS})\b(?:,?\s+\d{{4}})?", I)
    # A month on its own after "in", "since", "until": "moved to Burnaby in March",
    # "en janvier", "desde marzo", "w lipcu", "באוגוסט". Capitalized in English.
    add(
        EntityType.DATE,
        r"\b(?i:in|since|until|till|back\s+in|by|from|before|after|during|early|late|mid)[\s\-]+"
        r"(January|February|March|April|June|July|August|September|October|November|December|Sept?|Oct|Nov|Dec|Jan|Feb)\b"
        r"(?!\s+\d)",
        group=1,
    )
    add(
        EntityType.DATE,
        r"\b(?:en|depuis|jusqu['’]en|d['’]ici|desde|hasta|para|w|od|do)\s+"
        r"(janvier|f[ée]vrier|mars|mai|avril|juin|mayo|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre|enero|febrero|marzo|"
        r"abril|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|styczniu|lutym|marcu|kwietniu|maju|czerwcu|"
        r"lipcu|sierpniu|wrze[śs]niu|pa[źz]dzierniku|listopadzie|grudniu)\b(?!\s+\d)",
        I,
        group=1,
    )
    add(EntityType.DATE, r"(?<![א-ת])[בלמ]-?(ינואר|פברואר|מרץ|אפריל|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)(?![א-ת])(?!\s+\d)", group=1)
    # Spanish abbreviated months after "de": "23 de nov", "el 3 de sept.".
    add(EntityType.DATE, r"(?<!\d)\d{1,2}\s+de\s+(?:ene|feb|mar|abr|may|jun|jul|ago|sept?|oct|nov|dic)\b\.?", I)
    # Spanish month first, spoken: "abril cuatro del ochenta y seis".
    add(
        EntityType.DATE,
        rf"(?<!\w)(?:{_MONTHS_ML})\s+(?:{_DAY_WORDS_FR_ES})(?!\w)(?:(?:\s+del?)?(?:[\s\-]+(?:{_YEAR_WORDS})(?!\w)){{1,8}})?",
        I,
    )
    # Hebrew calendar dates: "כ״ג בחשוון תשנ״א", "ט״ו באב", "א׳ באדר ב׳".
    add(
        EntityType.DATE,
        r"(?:(?<![\w״\"'׳])|(?<=(?<![א-ת])[בלמה]))(?:[א-ל][״\"][א-ט]|[א-ל][׳'])\s+ב?(?:תשרי|מרחשוון|חשוון|חשון|כסלו|כסליו|טבת|שבט|"
        r"אדר(?:\s+[אב][׳'])?|ניסן|אייר|סיוון|סיון|תמוז|אב|אלול)(?![א-ת])"
        r"(?:,?\s+(?:ה[׳'])?ת[א-ת]{1,2}[״\"][א-ת])?",
    )
    # The first day of a Hebrew range, with the ה- prefix: "בין ה-3 ל-7 במרץ".
    add(
        EntityType.DATE,
        rf"(?<![\d/.:])(?<!\d[\-])(?<![א-ת])[בהמ]-?(\d{{1,2}})(?=\s+(?:עד|ועד|ל-?|[\-\u2013])\s*(?:ה-?)?\d{{1,2}}\s+ב?(?:{_MONTHS_ML})(?![א-ת]))",
        group=1,
    )
    # Hebrew abbreviated months: "12 בנוב׳".
    add(EntityType.DATE, r"(?<!\d)\d{1,2}\s+ב?(?:ינו|פבר|אפר|יונ|יול|אוג|ספט|אוק|נוב|דצמ)[׳'](?!\w)")
    # Day-first dates without a year: unambiguous ones ("14/03") anywhere, others after a
    # date word ("el 14/03", "punkcja 9.11", "ב-14.3").
    add(
        EntityType.DATE,
        r"(?<![\d/.])\b(?!24/7\b)(?:1[3-9]|2\d|3[01])[/.](?:0?[1-9]|1[0-2])\b(?![/.]?\d)",
        check=lambda m: _short_date_check(m) and _not_lab_value(m),
    )
    add(
        EntityType.DATE,
        r"(?:(?<![\w])(?:el|le|du|au|on|dnia|od|do|ב-?|ל-?|עד|מ-)\s*|\b(?:till|until|through|thru)\s+(?!\d+[/.]\d+\s*(?:mm|cm|mg|mcg|ml|iu|ng|pg|pmol|%|kg|lbs?|units?|days?|weeks?|hours?|hrs?|cycles?)\b)|\b(?:punkcj[aęi]|punci[óo]n|ponction|retrieval|transfer|"
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

    # A day corrected on the spot: "May the fifth, no sorry, the sixth, nineteen eighty-four";
    # "el seis de, no perdón, el siete de abril"; "le cinq, non, le six mai".
    _fix = r"(?:,?\s+(?:no|nope|non|nie|sorry|wait|i\s+mean|perd[óo]n|pardon|przepraszam|disculpa|um|uh|hmm)\b){1,4},?"
    add(
        EntityType.DATE,
        rf"\b(?P<month>{_MONTHS})\s+(?:the\s+)?(?:{_ORDINAL_WORDS}|{_DAY_CARDINALS}){_fix}\s+(?:the\s+)?(?:{_ORDINAL_WORDS}|{_DAY_CARDINALS})"
        rf"(?:,?\s+(?:{_SPOKEN_YEAR}|\d{{4}}))?\b",
        I,
        check=_month_check,
    )
    add(
        EntityType.DATE,
        rf"(?<!\w)(?:{_DAY_WORDS_FR_ES}|{_DAY_WORDS_PL})(?=(?:\s+de)?{_fix}[\s,]*(?:el\s+|le\s+)?(?:{_DAY_WORDS_FR_ES}|{_DAY_WORDS_PL})(?:\s+de)?\s+(?:{_MONTHS_ML}))",
        I,
    )
    # The corrected day after a date: "le vingt-deux février. Non, pardon, le vingt-trois."
    add(
        EntityType.DATE,
        rf"(?<!\w)(?:{_MONTHS_ML})[.,]?{_fix}\s+(?:el\s+|le\s+)?({_DAY_WORDS_FR_ES}|{_DAY_WORDS_PL})(?!\w)",
        I,
        group=1,
    )
    # A day word of another language before an English month: "the primero of June".
    add(
        EntityType.DATE,
        rf"(?<!\w)(?:the\s+)?(?:{_DAY_WORDS_FR_ES})\s+of\s+(?P<month>{_MONTHS})\b",
        I,
        check=_month_check,
    )
    # A day with fillers before it: "to come on the, uh, nineteenth but ...".
    add(
        EntityType.DATE,
        r"\b(?:on|for|by)\s+the,?(?:\s+(?:uh|um|er|erm|hmm),?)+\s+("
        + _ORDINAL_WORDS.replace(")|first|", ")|", 1)
        + r")(?=\s*(?:[.,?!;)]|$|but\b|and\b|or\b|so\b))",
        I,
        group=1,
    )
    # A month tied to a person by what it answers: "due in July", "due about late October",
    # "IUI is this summer, probably July". Capitalized in English.
    _mon_cap = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    _cue_in = r"(?:\s+(?i:in|on|around|about|by|for))*\s+(?:(?i:early|mid|late)[\s\-]+)?"
    add(
        EntityType.DATE,
        rf"\b(?i:(?:i['’]?m|i\s+am|she(?:['’]s|\s+is)|he['’]s|we['’]re|baby(?:\s+is)?)\s+(?:(?:also|now|only)\s+)?)(?i:due){_cue_in}({_mon_cap})\b(?!\s+\d)",
        group=1,
    )
    # "born in May": only the month is masked, the cue words stay.
    add(EntityType.DATE, rf"\b(?i:born){_cue_in}({_mon_cap})\b(?!\s+\d)", group=1)
    add(EntityType.DATE, rf"\b(?i:early|mid|late)[\s\-]+{_mon_cap}\b(?!\s+\d)")
    add(EntityType.DATE, rf"\b(?i:probably|maybe|perhaps|hopefully|sometime\s+in)\s+({_mon_cap})\b(?!\s+\d)", group=1)

    # Short numeric dates like 3/14 (no year).
    add(EntityType.DATE, r"(?<![\d/])\b(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])\b(?![/\d])", check=_short_date_check)

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
    # "My mother is 91", "grandma turned 95", "mi abuela tiene 92".
    add(
        EntityType.AGE,
        r"\b(?:mother|mom|mum|father|dad|grand(?:mother|ma|father|pa)|nana|aunt|uncle|abuel[ao]|madre|padre|"
        r"m[èe]re|p[èe]re|grand-m[èe]re|grand-p[èe]re|babci[ae]|dziadek|mama|tata|she|he)\s+"
        r"(?:is|turned|turns|will\s+be|just\s+turned|est|a|tiene|cumpli[óo]|ma|sko[ńn]czy[łl]a?)\s+"
        r"(9\d|1[01]\d)\b(?!\s*(?:%|mg|kg|lbs?|\$|dollars|min|minutes|mm|cm|ml))",
        I,
        group=1,
    )

    # Ages over 89 of a relative, written or spoken, anywhere on the line after the relative:
    # "her mother Abena is 91", "my dad ... he was ninety-one", "grandma still alive at 96",
    # "tiene noventa y cuatro años", "a quatre-vingt-onze ans", "lat 93", "בת 94", "בגיל 92".
    add(
        EntityType.AGE,
        rf"\b(?P<v>is|was|turned|turns|turning|will\s+be|lived\s+to|died\s+at|passed(?:\s+away)?\s+at|alive\s+at|at|aged?|"
        rf"tiene|ten[ií]a|cumpli[óo]|a\s+los|a|avait|lat|ma|mia[łl]a?|w\s+wieku)\s+(?P<n>{_AGE_OLD})(?![\w\-]){_AGE_NOT_UNIT}",
        I,
        group="n",
        check=_relative_before,
    )
    add(
        EntityType.AGE,
        r"(?<![א-ת])(?:בת|בן|בגיל|גיל)\s+(?P<n>9\d|1[01]\d|תשעים(?:\s+ו[א-ת]+)?)(?!\d)",
        group="n",
        check=_relative_before,
    )

    add(EntityType.ADDRESS, _STREET, I, check=_street_check)
    add(EntityType.ADDRESS, r"\b(?:p\.?\s?o\.?\s*box|postal\s*box)\s*\d+\b", I)
    # Streets named first, in French, Spanish, Polish and Hebrew: "88 rue des Érables",
    # "1205 Calle Mayor", "ul. Kościuszki 12/4", "רחוב הרצל 14", then the city if any.
    add(
        EntityType.ADDRESS,
        r"(?<!\w)(?:\d{1,5}[,\s]+)?(?i:rue|boulevard|boul\.|chemin|calle|avenida|carrera|paseo|ul\.|ulica|ulicy|"
        r"ulic[ęe]|aleja|al\.)[^\S\n]+(?:(?i:de\s+la|des|du|de|del|la|le)\s+)?(?:[A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+|\d{1,3}\b)"
        r"(?:[^\S\n]+[A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+){0,2}(?:[^\S\n]*,?[^\S\n]*(?:\d{1,5}(?:/\d{1,4})?[A-Za-z]?|#\s*\d+-\d+)\b"
        rf"|[^\S\n]+(?i:(?:{_PL_NUM})(?:[^\S\n]+(?:{_PL_NUM})){{0,3}})(?![\w'’]))?"
        r"(?:,[^\S\n]*(?i:apt|apto|apartment|unit|suite|ste|piso|m\.|lok\.|mieszkanie|lokal|apartamento|departamento|appartement)\.?\s*[\w\-]+(?:[^\S\n][A-Za-z]\b)?)?(?:,[^\S\n]*(?!(?i:apt|apto|unit|suite|ste)\b)[A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+(?:[^\S\n][A-ZÀ-Ý][\w'\-]+)?)?",
    )
    # The house number may be digits or words, then the flat: "ברחוב הרצל 14 דירה 7",
    # "ברחוב ליינדייל שלוש מאות שתים עשרה דירה ארבע".
    _hn = rf"(?:{_HE_NUM})(?![א-ת])"
    _hnum = rf"(?:\d{{1,4}}|{_hn}(?:[^\S\n]+ו?{_hn}){{0,4}})"
    add(
        EntityType.ADDRESS,
        r"(?<![א-ת])[בלמו]?(?P<a>(?:רחוב|רח[׳'])[^\S\n]+(?!" + _hn + r")[א-ת][א-ת\-\"״]+"
        rf"(?:[^\S\n]+(?!{_hn})[א-ת][א-ת\-]+)?(?:[^\S\n]+{_hnum})?(?:[^\S\n]+(?:דירה|דירת|כניסה|קומה)[^\S\n]+{_hnum})?"
        r"(?:,[^\S\n]*[א-ת][א-ת\-]+(?:[^\S\n]+[א-ת][א-ת\-]+)?)?)",
        group="a",
    )
    # The city said just before the street: "עכשיו במיניאפוליס, ברחוב ליינדייל".
    add(
        EntityType.ADDRESS,
        r"(?<![א-ת])ב(?P<place>[א-ת]{3,}(?:[^\S\n][א-ת]{3,})?)(?=,[^\S\n]*[בלמ]?(?:רחוב|רח[׳']))",
        group="place",
    )
    # A street said in Spanish with its number first: "el dos mil cuatrocientos cincuenta y uno de la
    # calle Lake, apartamento tres B, Saint Paul".
    add(
        EntityType.ADDRESS,
        rf"(?<![\w])(?i:(?:{_ES_NUM})(?:[^\S\n]+(?:y[^\S\n]+)?(?:{_ES_NUM})){{0,7}})[^\S\n]+(?i:de[^\S\n]+la[^\S\n]+|del[^\S\n]+|de[^\S\n]+)?"
        r"(?i:calle|avenida|carrera|paseo)[^\S\n]+[A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+(?:[^\S\n]+[A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+){0,2}"
        rf"(?:,[^\S\n]*(?i:apartamento|apto\.?|departamento|piso|interior|unidad)[^\S\n]+(?i:(?:{_ES_NUM}|\d{{1,4}}))(?:[^\S\n]+(?i:(?:{_ES_NUM})))?(?:[^\S\n]+[A-Za-z]\b)?)?"
        r"(?:,[^\S\n]*[A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+(?:[^\S\n][A-ZÀ-Ý][\w'\-]+)?)?",
        group=0,
    )
    # A neighbourhood or town someone moved from or to: "j'ai déménagé du Précieux-Sang",
    # "me mudé de Lomas Verdes", "przeprowadziłam się z Mokotowa" (not a drug: only non-English cues).
    add(
        EntityType.ADDRESS,
        r"\b(?i:d[ée]m[ée]nag\w*|mud[ée]|mudamos|mudaron|przeprowadzi\w+\s+si[ęe]|wyprowadzi\w+\s+si[ęe])\s+(?i:de|du|des|d['’]|desde|a|à|au|aux|z|ze|do)\s*"
        r"(?:(?i:la|le|les|l['’]|el|los)\s+)?(?P<place>(?-i:[A-ZÀ-ÝŁŚŻŹĆ][\w]+(?:-[A-ZÀ-ÝŁŚŻŹĆ][\w]+)*(?:[^\S\n][A-ZÀ-ÝŁŚŻŹĆ][\w]+){0,2}))",
        group="place",
        check=_moved_check,
    )
    # A city on a form line: "city: Minneapolis", "ville : Laval".
    add(
        EntityType.ADDRESS,
        r"(?im:^[^\S\n]*(?:city|town|ville|ciudad|miasto)[^\S\n]*[:=][^\S\n]*)(?P<place>(?-i:[A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+(?:[^\S\n][A-ZÀ-ÝŁŚŻŹĆ][\w'\-]+){0,2}))[^\S\n]*$",
        group="place",
        check=_place_value_check,
    )
    # Cities and towns where a person lives or comes from ("I live in Sudbury").
    R.append(_Rule(EntityType.ADDRESS, _places()[1], group=0, check=_place_check))
    # Cities written in Hebrew ("גרה בפתח תקווה", "עוברים לטורונטו"); the prefix stays outside.
    R.append(_Rule(EntityType.ADDRESS, _hebrew.PLACE_RE))

    # Canadian postal code.
    add(
        EntityType.POSTAL_CODE,
        r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][\s\-]?\d[ABCEGHJ-NPRSTV-Z]\d\b",
        I,
    )
    # Polish ("31-147 Kraków") and French ("..., 33000 Bordeaux") postal codes before a city.
    add(EntityType.POSTAL_CODE, r"(?<![\d\-])\b(\d{2}-\d{3})\s+[A-ZŁŚŻŹĆ][\wąćęłńóśźż\-]+", group=1)
    add(EntityType.POSTAL_CODE, r"(?:,|^|\n)[^\S\n]*(\d{5})[^\S\n]+(?:[A-ZÀ-Ý][\wà-ÿ'\-]+)(?!\s+(?:st|street|ave|rd|road|dr)\b)", re.M, group=1)
    # US ZIP only with context (a bare 5-digit number is too ambiguous).
    add(EntityType.ZIP, rf"\b(?:{_US_STATES})\s+(\d{{5}}(?:-\d{{4}})?)\b", group=1)
    # The town on a "City, ST 12345" address line: "Yuma, AZ 85360".
    add(
        EntityType.ADDRESS,
        rf"(?:^|,)[^\S\n]*([A-Z][a-z]+(?:[^\S\n][A-Z][a-z]+){{0,2}}),?[^\S\n]+(?:{_US_STATES})[^\S\n]+\d{{5}}(?:-\d{{4}})?\b",
        re.M,
        group=1,
    )
    # Mexican postal codes: "CP 83868", "C.P. 06700", "código postal 64000".
    add(EntityType.POSTAL_CODE, r"\b(?:C\.?[^\S\n]?P\.?|c[óo]digo\s+postal)[^\S\n]*:?[^\S\n]*(\d{5})\b", I, group=1)
    # Polish postal code after "kod": "Kraków kod 31-147".
    add(EntityType.POSTAL_CODE, r"\bkod(?:\s+pocztowy)?\s*:?\s*(\d{2}-\d{3})\b", I, group=1)
    # Polish postal code after the town: "Łódź, 64-664".
    add(EntityType.POSTAL_CODE, r"[A-ZŁŚŻŹĆ][\wąćęłńóśźż\-]+,[^\S\n]+(\d{2}-\d{3})\b(?!-)", group=1)
    add(EntityType.ZIP, r"\bzip(?:\s*code)?\s*(?:is|:)?\s*(\d{5}(?:-\d{4})?)\b", I, group=1)
    # A city and a ZIP at the end of an address line: "San Antonio, 78201".
    add(EntityType.ZIP, r"\b[A-Z][a-z]+(?:[^\S\n][A-Z][a-z]+)?,?[^\S\n]+(\d{5}(?:-\d{4})?)[^\S\n]*$", re.M, group=1)
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

    # A named workplace or school after a cue: "I'm a grad student at Gulfstream State University",
    # "My contract at Lakeview Memorial", "employer is Hamilton Steel Workers Local 1005",
    # "Trabajo en Colegio Santa Clara", "je travaille chez Desjardins", "עובדת בחברת נטע טק".
    # A word, with inner dots ("U.S") and a short abbreviation's dot before the next word ("St. Mary's").
    _tok = r"[\w&'’\-]{0,30}(?:\.(?=\w)[\w&'’\-]{1,10}){0,3}(?:(?:(?<=\b[A-Z])|(?<=\b[A-Z][a-z]))\.(?=[ \t]+[A-Z]))?"
    # not a sentence word, weekday or month, nor a pronoun contraction that starts the next clause
    # ("school, I'm a teacher", "work at a clinic, she's a nurse")
    _nt = (
        rf"(?!(?i:{_ORG_STOP})(?![\w'’])|"
        r"(?i:(?:i|we|he|she|they|it|you|that|there|here|who)['’](?:m|ve|d|ll|s|re)(?![\w'’])))"
    )
    _org = rf"(?-i:{_nt}[A-Z]{_tok}(?:[ \t]+(?:(?:of|de|del|la|the|and|&|des|du)[ \t]+)?{_nt}[A-Z0-9]{_tok}){{0,6}})"
    add(
        EntityType.EMPLOYER,
        rf"\b(?:student|nurse|teacher|professor|engineer|resident|fellow|accountant|developer|designer|cashier|driver|worker|employee|"
        rf"work(?:s|ing|ed)?(?:\s+(?:nights?|days?|evenings?|weekends?|overnights?|late|early|part[\- ]time|full[\- ]time|shifts?|hard|there|here))*|"
        rf"employed|contract|job|intern(?:ship)?)\s+(?:at|for)\s+"
        rf"(?:the\s+)?(?P<org>{_org})",
        I,
        group="org",
        check=_org_check,
    )
    add(
        EntityType.EMPLOYER,
        rf"\b(?:employer|employeur|empleador|empleadora|pracodawca|school|[ée]cole|escuela|uczelnia)\s*(?:is|:|,|es|est|to)?\s*(?P<org>{_org})",
        I,
        group="org",
        check=_org_check,
    )
    # "My work, Medtronic Plains Biologics, just added...", "my company is Hennepin Roofing".
    add(
        EntityType.EMPLOYER,
        rf"\b(?:my|his|her|our|mi|mon|ma|son|sa)\s+(?:work|company|workplace|job|travail|entreprise|trabajo|empresa)\s*(?:is|:|,|es|est)\s*(?P<org>{_org})(?=\s*[,.;\n]|$)",
        I,
        group="org",
        check=_org_check,
    )
    # A job title and the employer in a signature: "Senior Analyst - Northern Plains Credit Union", "Teacher, Eden Prairie Montessori".
    add(
        EntityType.EMPLOYER,
        rf"\b(?:teacher|professor|engineer|analyst|accountant|developer|designer|consultant|paralegal|technician)[ \t]*(?:,|[-–—]|@)[ \t]*"
        rf"(?P<org>{_org})(?=[ \t]*(?:[,.;]|$))",
        re.I | re.M,
        group="org",
        check=_org_check,
    )
    add(
        EntityType.EMPLOYER,
        rf"\b(?:trabajo|trabaja|trabajamos|estudio|estudia|je\s+travaille|il\s+travaille|elle\s+travaille|"
        rf"j['’][ée]tudie|pracuj[eę]|pracuje|studiuj[eę]|(?:sa|ma|ta|son|mon|ton)\s+(?:job|boulot|emploi|travail)|"
        rf"szef(?:owa)?|kierownik|pracodawc[aąy]|travaill(?:e|ait|ons|ent|er)|travaill[ée]e?)\s+(?P<prep>en|para|chez|à|au|w|we|u|dla)\s+(?:la\s+|el\s+|l['’])?(?P<org>{_org})",
        I,
        group="org",
        check=_org_check_foreign,
    )
    add(
        EntityType.EMPLOYER,
        r"(?<![א-ת])(?:עובדת|עובד|עובדים|לומדת|לומד|מועסקת|מועסק|בעבודה|המנהל|המנהלת|מנהל|מנהלת|הבוס|הבוסית|המעסיק|המעסיקה|עובדי)\s+ב(?P<org>"
        r"(?:חברת|מכללת|אוניברסיטת|ישיבת|בית\s+החולים|בית\s+הספר|בנק|קיבוץ|מפעלי|מפעל|תעשיות|אחזקות|קבוצת|רשת|עיריית|מכון|"
        r"משרד\s+עורכי\s+הדין|סטודיו|מסעדת)"
        r"(?:[^\S\n]+(?!ו|(?:לא|את|של|עם|על|כי|אבל|גם|שלי|שלה|אני|הוא|היא|אותי|אותה)(?![א-ת]))[א-ת][א-ת\"״'׳\-]*){1,2})",
        group="org",
        check=_org_check,
    )
    # A company with no designator in front, but one at the end ("עובדת בזטה טק").
    add(
        EntityType.EMPLOYER,
        r"(?<![א-ת])(?:עובדת|עובד|עובדים|מועסקת|מועסק|בעבודה|המנהל|המנהלת|הבוס|המעסיק)\s+ב(?P<org>(?:[א-ת][א-ת\"״'׳\-]*[^\S\n]+)?"
        r"[א-ת][א-ת\"״'׳\-]*[^\S\n]+(?:טק|טכנולוגיות|בע[\"״]מ|גרופ|סיסטמס|סולושנס|דיגיטל|לוגיסטיקה|מערכות))(?![א-ת])",
        group="org",
    )

    # A relative's workplace: "His wife is Dr. Anita Lee, a paediatrician at Children's North Clinic",
    # "my husband works for Hennepin Roofing".
    add(
        EntityType.EMPLOYER,
        r"\b(?:husband|hubby|wife|partner|spouse|boyfriend|girlfriend|mother|mom|father|dad|sister|brother|son|daughter|"
        r"fianc[eé]e?)\b[^\n]{0,90}?\b(?:works?|working|employed|"
        r"(?:an?|the)\s+(?:[\w\-]+\s+)?(?:[a-z]*(?:ician|ologist|ist|ian)|nurse|teacher|engineer|professor|lawyer|manager|"
        rf"assistant|analyst|clerk|driver|chef|surgeon|physician|doctor|therapist))[ \t]+(?:at|for|with)[ \t]+(?:the[ \t]+)?(?P<org>{_org})",
        I,
        group="org",
        check=_org_check,
    )
    # A shop or site named by its street, after a work cue: "at work till 1 target on lake st".
    add(
        EntityType.EMPLOYER,
        rf"\b(?:at\s+work|work(?:ing|s)?\s+(?:at|till|until|til)|my\s+(?:job|shift))\b[^\n.!?]{{0,30}}?[ \t,]"
        rf"(?P<org>(?!(?:at|the|a|i|im|so|and|but|then|till|until|til|my|me|it)\b)[a-z][\w'&]*(?:[ \t]+[a-z][\w'&]*)?[ \t]+on[ \t]+[a-z][\w']*(?:[ \t]+[a-z][\w']*)?[ \t]+(?:{_STREET_SUFFIX})\b)",
        I,
        group="org",
    )

    # Names introduced by context (see _names.py). The local model or the
    # known-entity list catch names with no cue.
    for pat, flags, check in [*_names.rules(_NOT_NAMES), *_names.courtesy_rules(_NOT_NAMES)]:
        add(EntityType.NAME, pat, flags, check=check)
    # A person who gives a title as their own name and says they are a patient ("my name is Dr. Sarah
    # Cohen", "patient Dr. Sarah Cohen", "I'm Dr. Sarah Cohen and I'm a patient") is a patient, not a
    # clinician. Only a patient cue ties the title to the patient; "Dr. Sarah Cohen said" stays a clinician.
    _T = r"(?i:dr|dre|dra|doctor|doctora|docteur|docteure|doktor)\.?[ \t]+"
    _N = rf"(?P<name>{_names.NAME})"
    _own = (
        r"(?i:my\s+name\s+is|my\s+name['’]s|name\s+is|me\s+llamo|mi\s+nombre\s+es|je\s+m['’ ]?appelle|mon\s+nom\s+est|"
        r"nazywam\s+si[eę]|(?:patient|pt|patiente|paciente|pacjent(?:ka)?)[ \t]*:?)"
    )
    _patient_after = (
        r"(?=[ \t]*(?:[,;\-]|and|&)?[ \t]*(?i:(?:(?:i['’]?m|i\s+am)[ \t]+)?(?:a|an|your|a\s+new)[ \t]+patient\b)"
        r"|[^.!?\n]{0,60}?(?i:\b(?:i['’]?m|i\s+am)\s+(?:booked|scheduled)|\bi\s+have\s+an?\s+(?:appointment|visit|consult)\b|"
        r"\bmy\s+(?:appointment|visit|consult\w*|retrieval|transfer)\b))"
    )
    add(EntityType.NAME, rf"\b{_own}\s+{_T}{_N}", check=_name_check)
    add(
        EntityType.NAME,
        rf"\b(?i:i['’]?m|i\s+am|this\s+is|je\s+suis|soy|jestem)[ \t]+{_T}{_N}{_patient_after}",
        check=_name_check,
    )
    add(
        EntityType.NAME,
        rf"(?:^|(?<=[\s,.!?:;]))(?i:dr|dre|dra|doctor|doctora|docteur|docteure|doktor)\.?[ \t]+{_N}[ \t]+(?i:here|speaking|calling)\b"
        r"(?=[^.!?\n]{0,60}?(?i:\b(?:i['’]?m|i\s+am)\s+(?:booked|scheduled)|\bi\s+have\s+an?\s+(?:appointment|visit|consult)\b|"
        r"\bmy\s+(?:appointment|visit|consult\w*|retrieval|transfer)\b))",
        check=_name_check,
    )
    add(
        EntityType.PROVIDER,
        r"\b(?i:dr|dre|dra|doctor|doctora|docteur|docteure|nurse|enf|inf|np|rn)\.?\s+"
        r"(?P<name>[A-Z][a-zA-Z'\-]+(?:\s+[A-Z](?:\.|(?![\w'’\-])))?(?:\s+[A-Z][a-zA-Z'\-]+)?)",
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
        # Invisible format characters (LRM, RLM, ZWSP, soft hyphen, ...) and Hebrew nikud
        # are dropped for matching; offsets are mapped back to the original text.
        norm, back = _normalise(text)
        out = self._detect_clean(norm)
        if back is None:
            if norm != text:  # only Unicode spaces were replaced: same offsets, original text
                out = [Entity(e.type, e.start, e.end, text[e.start : e.end], e.source) for e in out]
            return out
        mapped: list[Entity] = []
        for e in out:
            a, b = back[e.start], back[e.end - 1] + 1
            mapped.append(Entity(e.type, a, b, text[a:b], e.source))
        return _dedupe(mapped)

    def _detect_clean(self, text: str) -> list[Entity]:
        original = text
        if "\r" in text:
            # Windows line ends: the rules see "\r\n" as " \n" (same offsets).
            text = text.replace("\r", " ")
        out = self._detect(text)
        # Faxed and scanned text: "6O4-555-Ol74", "9l42 337 O58". Read the numbers
        # again with look-alike letters as digits; keep what touches a changed letter.
        shadow = _ocr_shadow(text)
        if shadow != text:
            changed = [i for i, (a, b) in enumerate(zip(text, shadow)) if a != b]
            for e in self._detect(shadow):
                if e.type in _NAME_GROUP_TYPES or not any(e.start <= i < e.end for i in changed):
                    continue
                out.append(Entity(e.type, e.start, e.end, text[e.start : e.end], self.name))
        if original is not text:
            out = [_trimmed(e, original) for e in out]
            out = [e for e in out if e is not None]
        return _dedupe(out)

    def _detect(self, text: str) -> list[Entity]:
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
        # A field value the rules above already found whole is left to them.
        found = [(e.start, e.end) for e in out]
        spoken.extend(
            Entity(t, a, b, text[a:b], self.name)
            for t, a, b in _structured.detect(text)
            if not any(s <= a and b <= e for s, e in found)
        )
        if self.enabled is None or EntityType.NAME in self.enabled:
            out.extend(Entity(EntityType.NAME, a, b, text[a:b], self.name) for a, b in _names.hebrew_names(text))
        if self.enabled is None or EntityType.ID in self.enabled:
            heb_ids = _hebrew.israeli_ids(text)
            # A grouped Israeli ID is also nine digits like a SIN; the cue says which it is.
            out = [e for e in out if not (e.type is EntityType.SIN and (e.start, e.end) in heb_ids)]
            out.extend(Entity(EntityType.ID, a, b, text[a:b], self.name) for a, b in heb_ids)
        out.extend(e for e in spoken if self.enabled is None or e.type in self.enabled)
        out = [e for e in out if not (e.type is EntityType.DATE and _SPELLING_WORD.search(text[max(0, e.start - 30) : e.start]) and _as_in_letter(text, e))]
        # Numbers that belong to the clinic, a product or an interpreter, not a patient:
        # "ticket T-40266", "LOT W486069", "interpreter, ID 20931". Appointment
        # confirmation numbers stay masked: they point to one patient's visit.
        return [
            e for e in out
            if not (
                e.type in _CLINIC_NUMBER_TYPES
                and (_CLINIC_NUMBER_CUE.search(text[max(0, e.start - 40) : e.start]) or _CLINIC_CODE_PREFIX.match(e.text))
            )
        ]


_INVISIBLE = re.compile(
    "[\u00ad\u034f\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff"
    "\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]"
)


_UNICODE_SPACES = {0xA0: " ", 0x202F: " ", 0x2007: " "}


def _normalise(text: str) -> tuple[str, Optional[list[int]]]:
    """``text`` without invisible format characters and Hebrew points, plus a list that maps
    each kept character's index back to the original (None when nothing was dropped)."""
    # Unicode spaces that regexes do not treat as blanks become plain spaces (1:1, offsets unchanged).
    text = text.translate(_UNICODE_SPACES)
    if not _INVISIBLE.search(text):
        return text, None
    kept = [i for i, c in enumerate(text) if not _INVISIBLE.match(c)]
    return "".join(text[i] for i in kept), kept


def _dedupe(entities: list[Entity]) -> list[Entity]:
    """Drop repeats of the same type on the same span (two rules found one value)."""
    seen: set[tuple[EntityType, int, int]] = set()
    out: list[Entity] = []
    for e in entities:
        key = (e.type, e.start, e.end)
        if key not in seen:
            seen.add(key)
            out.append(e)
    # A URL found again inside a longer URL ("example.com/a" in "https://example.com/a") is one value.
    drop: set[int] = set()
    reach = -1
    for i in sorted((i for i, e in enumerate(out) if e.type is EntityType.URL), key=lambda i: (out[i].start, -out[i].end)):
        if out[i].end <= reach:
            drop.add(i)
        else:
            reach = max(reach, out[i].end)
    return [e for i, e in enumerate(out) if i not in drop]


def _trimmed(e: Entity, text: str) -> Optional[Entity]:
    """``e`` without spaces or carriage returns at its ends, its text taken from ``text``."""
    start, end = e.start, e.end
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end <= start:
        return None
    return Entity(e.type, start, end, text[start:end], e.source)


_CLINIC_NUMBER_TYPES = {
    EntityType.ID, EntityType.ACCOUNT, EntityType.ZIP, EntityType.SIN, EntityType.MRN, EntityType.POSTAL_CODE,
}
_CLINIC_NUMBER_CUE = re.compile(
    r"(?:\b(?:ticket|tkt|(?<!straw\s)lot|lote|batch|routing|badge|zg[łl]oszeni[ae])\b(?:no\.|[^\n\d?!.]){0,25}"
    r"|\binterpr[eè]t(?:er|e)\b(?:no\.|[^\n\d?!.]){0,25}"
    # Order-like words count only when the number follows them directly ("PO 4471", "quote #88"):
    # a patient's own ID later in the sentence ("per the quote my member ID: ...") stays masked.
    r"|\b(?:(?:supply|purchase|vendor|equipment|work|service)\s+order|(?-i:PO)|sop|quote|model|"
    r"pedido\s+de\s+suministros|pedido(?=\s*#)|part\s+(?:numbers?|nos?\.?|#))\b(?:\s*(?:no\.?|number|#|:|-)){0,2}[ \t]*)$",
    re.IGNORECASE,
)

# Codes that name their own kind: a helpdesk ticket, SOP, purchase order, quote or tracking number.
_CLINIC_CODE_PREFIX = re.compile(r"(?:TKT|TICKET|SOP|PO|QUOTE|TRK|RMA)-", re.IGNORECASE)

_STREET_RE = re.compile(_STREET, re.IGNORECASE)
_STREET_SUFFIX_AFTER = re.compile(rf"(?:[ \t]+[A-Za-z'’\-]+){{1,3}}[ \t]+(?:{_STREET_SUFFIX})\b", re.IGNORECASE)


def _street_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _STREET_RE.finditer(text) if _street_check(m)]


_OCR_TOKEN = re.compile(r"[0-9A-Za-z]+")
_OCR_DIGIT = str.maketrans("OolI", "0011")


def _ocr_shadow(text: str) -> str:
    """``text`` with O/o/l/I read as digits inside number-like tokens (same length)."""
    toks = list(_OCR_TOKEN.finditer(text))
    numeric = [bool(re.fullmatch(r"[0-9OolI]+", t.group(0))) for t in toks]
    has_digit = [n and any(c.isdigit() for c in t.group(0)) for n, t in zip(numeric, toks)]
    convert = [h and not t.group(0).isdigit() for h, t in zip(has_digit, toks)]
    # Short letter-only tokens joined to a number by "/", "-" or "." ("O9/Ol/199O").
    for _ in range(3):
        for i, t in enumerate(toks):
            if convert[i] or not numeric[i] or len(t.group(0)) > 2:
                continue
            for j in (i - 1, i + 1):
                if 0 <= j < len(toks) and has_digit[j]:
                    a, b = sorted((i, j))
                    if re.fullmatch(r"[/\-.]", text[toks[a].end() : toks[b].start()]):
                        convert[i] = has_digit[i] = True
    if not any(convert):
        return text
    out = list(text)
    for t, c in zip(toks, convert):
        if c:
            out[t.start() : t.end()] = t.group(0).translate(_OCR_DIGIT)
    return "".join(out)
