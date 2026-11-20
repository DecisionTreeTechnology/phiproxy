"""Payment handles, bank and cheque numbers, device serials, file numbers and ID numbers in groups.

Each rule needs its own cue (a payment word, a bank word, "serial", "court file", ...) or a shape
that cannot be anything else. The rules return the same tuples as ``_geo.rules``.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from ..entities import EntityType

Rule = tuple[EntityType, str, int, "int | str", Optional[Callable[[re.Match[str]], bool]]]

I = re.IGNORECASE

# Words that say money is going to or from a handle or an account.
_PAY_CUE = re.compile(
    r"(?i:\b(?:venmo|zelle|paypal|pay\s*pal|cash\s*app|cashapp|cash\s*tag|cashtag|apple\s*pay|google\s*pay|pay\s*me|"
    r"send(?:\s+(?:it|money|payment|the\s+\w+))?\s+(?:to|via|through)|payable\s+to|e-?transfer\s+to|handle|"
    r"mand[ae]r?(?:\s+\w+){0,2}\s+(?:a|por)|enviar(?:\s+\w+){0,2}\s+(?:a|por)|pagar\s+(?:con|por)|pago\s+(?:con|por)|"
    r"payer\s+(?:avec|par)|virement|paiement)\b)"
)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _pay_before(text: str, start: int) -> bool:
    line = text.rfind("\n", 0, start) + 1
    return bool(_PAY_CUE.search(text[max(line, start - 90) : start]))


_CLINIC_PAY_ASK = re.compile(
    r"(?i:\b(?:pay(?:ing|ment|ments)?|send|sending|e-?transfer|transfer|deposit|remit|etransfer)\b[^.!?\n]{0,40}?\b(?:to\s+us|us|the\s+clinic|our\s+clinic)\b"
    r"|\bour\s+(?:venmo|paypal|zelle|cash\s*app|cashapp|handle|e-?transfer)\b"
    r"|\bfor\s+(?:the\s+)?(?:deposits?|clinic\s+fees?|fees?)\b|\bclinic\s+(?:fees?|venmo|paypal|zelle|handle|payments?)\b"
    r"|\be-?transfer\s+to\s+the\s+clinic\b|\buse\s+@\S+\s+to\s+pay\b|\b(?:is\s+)?accepted\b|\bwe\s+accept\b"
    r"|\btag\s+@\S+\s+in\s+your\b|\bfollow\s+us\b|\bfor\s+the\s+[\w\s]{0,20}fee\b)"
)
_PATIENT_OWN_PAY = re.compile(
    r"(?i:\b(?:my|mine|mi|mon|ma)\s+(?:\w+\s+){0,2}(?:venmo|paypal|zelle|cash\s*app|cashapp|handle|username|account)\b)"
)


def _clinic_payment_ask(text: str, start: int, end: int) -> bool:
    """The sentence is the clinic asking to be paid ("pay us via PayPal @x", "for deposits"): the handle is the
    clinic's, not the patient's. A patient's own handle in the same sentence ("my venmo is @x") stays."""
    a = max(text.rfind(c, 0, start) for c in ".!?\n") + 1
    ends = [i for i in (text.find(c, end) for c in ".!?\n") if i >= 0]
    sentence = text[a : min(ends) if ends else len(text)]
    if _PATIENT_OWN_PAY.search(sentence):
        return False
    return bool(_CLINIC_PAY_ASK.search(sentence))


def _clinic_owned(m: re.Match[str]) -> bool:
    from .regex import _clinic_owned as owned

    return owned(m.string, m.start(), m.end()) or _clinic_payment_ask(m.string, m.start(), m.end())


def _pay_handle(m: re.Match[str]) -> bool:
    if _clinic_owned(m):
        return False
    word = m.group(0)[1:]
    # A hyphenated or digit-bearing handle is one on its own; a plain word needs the payment cue.
    return _pay_before(m.string, m.start()) or ("-" in word and bool(re.search(r"\d", word)))


def _cashtag(m: re.Match[str]) -> bool:
    return _pay_before(m.string, m.start()) and not _clinic_payment_ask(m.string, m.start(), m.end())


_BARE_STOP = frozenset(
    """the a an not fine down working ok okay broken blocked set ready linked verified same different here there this that it
    just still also being no yes under on off locked declined pending acting weird so very too now new old can cant
    only mine yours his hers their our your""".split()
)


def _bare_handle(m: re.Match[str]) -> bool:
    """A handle with no "@" right after a payment word: "venmo: jane-doe-12", "my paypal is janedoe"."""
    from .regex import _clinic_owned as owned

    h = m.group("h")
    if owned(m.string, m.start("h"), m.end("h")) or _clinic_payment_ask(m.string, m.start("h"), m.end("h")):
        return False
    marked = bool(re.search(r"[\d\-_.]", h))
    if marked:
        return True
    return bool(m.group("my")) and h.lower() not in _BARE_STOP and len(h) >= 4


_SIN_CUE = re.compile(r"(?-i:\b(?:SIN|NAS)\b)|(?i:\bsocial\s+insurance|\bassurance\s+sociale)")


def _sin_cued(m: re.Match[str]) -> bool:
    """Nine digits in threes with a SIN named earlier in the same message: no checksum needed."""
    d = _digits(m.group(0))
    if len(d) != 9:
        return False
    return bool(_SIN_CUE.search(m.string[max(0, m.start() - 300) : m.start()]))


_HEALTH_CUE = re.compile(
    r"(?i:assurance[\s\-]maladie|\bramq\b|carte\s+(?:sant[ée]|medicare|soleil)|health\s*card|\bmedicare\b|\bmsi\b|\bohip\b)"
)


def _health_before(m: re.Match[str]) -> bool:
    return bool(_HEALTH_CUE.search(m.string[max(0, m.start() - 300) : m.start()]))


def _health_digits(m: re.Match[str]) -> bool:
    v = m.group(1)
    d = _digits(v)
    if not 8 <= len(d) <= 12:
        return False
    return not re.fullmatch(r"(?:19|20)\d\d[\- ]\d\d[\- ]\d\d", v)


def _aba_valid(d: str) -> bool:
    n = [int(c) for c in d]
    return len(n) == 9 and (3 * (n[0] + n[3] + n[6]) + 7 * (n[1] + n[4] + n[7]) + (n[2] + n[5] + n[8])) % 10 == 0


_FILE_EXT = re.compile(r"\.(?:pdf|jpe?g|png|docx?|csv|txt|xlsx?|com|org|net|ca|html?|gif|zip)$", re.IGNORECASE)


# A serial number is a patient's device identifier only when the device is theirs or worn: not the lab's printer.
_PERSONAL_DEVICE = re.compile(
    r"(?i:\b(?:my|his|her|their|patient['’]?s|home|wearable|wrist(?:band)?|pump|cgm|glucometer|glucose\s+monitor|"
    r"(?:heart(?:\s+rate)?|blood\s+pressure|baby|sleep|bp)\s+monitor|meter|thermometer|(?:fitness|activity|sleep)\s+(?:tracker|band)|"
    r"(?:smart|oura)\s+ring|watch|phone|implant|pacemaker|dexcom|oura|fitbit|garmin|whoop|apple\s+watch|mi|mon|ma|su|moje?)\b)"
)


def _personal_device(m: re.Match[str]) -> bool:
    line = m.string.rfind("\n", 0, m.start()) + 1
    window = m.string[max(line, m.start() - 90) : m.start()]
    window = re.split(r"[.!?]\s", window)[-1]
    return bool(_PERSONAL_DEVICE.search(window))


# The patient is the one writing: first person in the sentence ("my cheque", "I mailed", "from me"), or a patient word.
_FIRST_PERSON = re.compile(
    r"(?i:\b(?:i|i['’]?(?:m|ve|ll|d)|me|my|mine|myself|your|his|her|su|tu|votre|ton|tw[óo]j|we|we['’]?(?:ve|ll)|our|ours|us|mon|ma|mes|je|j['’]|moi|nous|notre|nos|"
    r"yo|mi|mis|m[íi]o|pagu[ée]|envi[ée]|mand[ée]|escrib[íi]|firm[ée]|nuestro|nuestra|nosotros|ja|m[óo]j|moja|moje|moim|moj[ąa]|nasz\w*|wys[łl]a[łl]\w*|"
    r"patient|patiente|paciente|pacjent\w*)\b)|(?<!\w)(?:אני|שלי|אנחנו)(?!\w)"
)


def _own_cheque(m: re.Match[str]) -> bool:
    text = m.string
    a = max(text.rfind(c, 0, m.start()) for c in ".!?\n") + 1
    ends = [i for i in (text.find(c, m.end()) for c in ".!?\n") if i >= 0]
    z = min(ends) if ends else len(text)
    return bool(_FIRST_PERSON.search(text[a : z]))


def _user_value(m: re.Match[str]) -> bool:
    v = m.group("v")
    if _FILE_EXT.search(v):
        return False
    cue = m.group(0)[: m.start("v") - m.start(0)].lower()
    if "." in v and not re.search(r"account|screen|nick|profile|display|login", cue):
        return False
    return True


def rules() -> list[Rule]:
    R: list[Rule] = []

    def add(t: EntityType, pat: str, flags: int = 0, group: "int | str" = 0, check=None) -> None:
        R.append((t, pat, flags, group, check))

    A, ID = EntityType.ACCOUNT, EntityType.ID

    # Payment handles with hyphens or dots: "@jlopez-ATL88", "@cassidy-moreau-4", or any "@handle" after a payment word.
    # (Typed ID like other handles, so the clinic's own and staff handles stay allowed.)
    add(ID, r"(?<![\w@.\-])@[A-Za-z][\w.]{1,28}(?:-[\w.]{1,20}){0,3}(?<![.\-])(?![\w@\-])", 0, 0, _pay_handle)
    # The same handle without "@" directly after the payment word: "venmo: jane-doe-12", "my paypal is janedoe".
    add(
        ID,
        r"(?i:(?P<my>\b(?:my|mi|mon|ma|our)[ \t]+)?\b(?:venmo|paypal|pay[ \t]*pal|zelle|cash[ \t]*app|cashapp|cash[ \t]*tag|cashtag)"
        r"(?:[ \t]+(?:handle|username|user[ \t]*name|id|name|account|tag))?[ \t]*(?:is|=|:|-|es|est|jest)[ \t]+)"
        r"(?P<h>(?-i:[A-Za-z][\w.]{1,28}(?:-[\w.]{1,20}){0,3}(?<![.\-])(?![\w@\-])))",
        0,
        "h",
        _bare_handle,
    )
    # Cash App "$cashtags": a letter right after the dollar sign, after a payment word.
    add(A, r"(?<![\w$])\$[A-Za-z][A-Za-z0-9._]{2,24}[A-Za-z0-9](?![\w@])", 0, 0, _cashtag)

    # Canadian bank transit and institution "12345-003", ABA routing numbers: after a bank cue.
    add(
        A,
        r"\b(?:transit|institution|banking|bank|routing|branch|succursale|virement)\b[^\n\d]{0,40}?(?<![\d\-])(\d{5}[\- ]\d{3})(?![\d\-])",
        I,
        1,
    )
    add(
        A,
        r"\b(?:routing|aba|rtn|transit)(?:[ \t]+(?:number|no\.?|#|num[ée]ro|n[úu]mero))?[^\n\d]{0,25}?(?<![\d\-])(\d{9})(?![\d\-])",
        I,
        1,
        lambda m: _aba_valid(m.group(1)) or re.search(r"(?i)routing|aba|rtn", m.group(0)[: m.start(1) - m.start(0)]) is not None,
    )

    # A Polish account number (NRB / IBAN PL, 26 digits) after its name: "numer konta 12 3456 7890 1234 5678 9012 3456".
    add(
        A,
        r"\b(?:numer\s+konta|nr\s+konta|numer\s+rachunku|nr\s+rachunku|konto|konta|iban)\b[^\n\d]{0,25}?(?<![\d])((?:PL[ ]?)?\d{2}(?:[ ]?\d{4}){6})(?!\d)",
        I,
        1,
    )
    # An account number in threes after "account no": "account no: 123 456 789".
    add(
        A,
        r"\b(?:account|acct|cuenta|compte)(?:[ \t]+(?:number|no\.?|num\.?|#|n[úu]mero|num[ée]ro))[ \t]*[:#=]?[ \t]*(?:is|es|est)?[ \t]*(\d{2,4}(?:[ \-]\d{2,4}){2,4})(?![\d\-]|[ ]\d)",
        I,
        1,
        lambda m: 7 <= len(_digits(m.group(1))) <= 17
        and not re.fullmatch(r"(?:19|20)\d\d[ \-]\d\d[ \-]\d\d|\d\d[ \-]\d\d[ \-](?:19|20)\d\d", m.group(1)),
    )
    # Transit and institution numbers given one by one, with the other word of the pair or a bank word on the line:
    # "transit number 12345, institution number 004".
    _bank_line = r"(?i:\b(?:institution|transit|bank|banking|branch|account|cheque|check|routing|deposit|direct\s+deposit|void)\b)"

    def _bank_ctx(m: re.Match[str]) -> bool:
        lo, hi = max(0, m.start() - 120), m.end() + 120
        a = max(lo, m.string.rfind("\n", lo, m.start()) + 1)
        b = m.string.find("\n", m.end(), hi)
        line = m.string[a : b if b >= 0 else hi]
        other = "institution" if m.group(0).lower().startswith("transit") else "transit"
        return other in line.lower() or bool(re.search(r"(?i)\b(?:bank|banking|branch|cheque|deposit)\b", line))

    add(A, r"\btransit(?:[ \t]+(?:number|no\.?|#|num[ée]ro))[ \t]*[:#]?[ \t]*(\d{5})(?![\d\-])", I, 1, _bank_ctx)
    add(A, r"\binstitution(?:[ \t]+(?:number|no\.?|#|num[ée]ro))[ \t]*[:#]?[ \t]*(\d{3})(?![\d\-])", I, 1, _bank_ctx)
    # A routing number said as separate digits: "routing 0 2 1 0 0 0 0 2 1".
    add(
        A,
        r"\b(?:routing|aba)(?:[ \t]+(?:number|no\.?|#))?[ \t]*[:#]?[ \t]*(?:is[ \t]+)?(\d(?:[ \-]\d){8})(?![\d\-]|[ ]\d)",
        I,
        1,
    )
    # A payment link: "cash.app/$janedoe", "paypal.me/jane-doe".
    add(
        ID,
        r"(?i:\b(?:cash\.app|venmo\.com/(?:u|code)|paypal\.me)/)(\$?[A-Za-z0-9][\w.\-]{2,28}[A-Za-z0-9])(?![\w@])",
        0,
        1,
    )
    # "venmo me at jane_doe_ivf": a handle with a digit, underscore or hyphen after the payment word and "me at".
    add(
        ID,
        r"(?i:\b(?:venmo|zelle|paypal|pay\s*pal|cash\s*app|cashapp)[ \t]+(?:me|us)[ \t]+(?:at|on|via|@)[ \t]+)@?((?=[A-Za-z0-9_\-]*[\d_\-])[A-Za-z][A-Za-z0-9_\-]{2,28}[A-Za-z0-9])(?![\w@.]|\.\w)",
        0,
        1,
        lambda m: not _clinic_owned(m),
    )

    # Cheque numbers: "cheque #2218", "check number 1042", "cheque número 1042", "chèque n° 8841".
    # Only a patient's own cheque ("my cheque #2218", "I mailed cheque number 1042"): the clinic's deposit
    # confirmations are not the patient's account.
    add(A, r"\b(?:che(?:ck|que)|ch[èe]que)[ \t]*(#[ \t]?\d{3,8})(?!\d)", I, 1, _own_cheque)
    add(
        A,
        r"\b(?:che(?:ck|que)|ch[èe]que)s?,?[ \t]+(?:(?:number|no\.?|num\.?|n[úu]mero|num[ée]ro|n[°º])[ \t]*:?[ \t]*)(\d{3,8})(?!\d)",
        I,
        1,
        _own_cheque,
    )

    # "numéro de chèque : 1045", "número de cheque 1045", "numero de cheque: 1045".
    add(
        A,
        r"\b(?:num[ée]ro|n[úu]mero|n[°º])[ \t]+de[ \t]+ch[èe]que[ \t]*:?[ \t]*#?[ \t]*(\d{3,8})(?!\d)",
        I,
        1,
        _own_cheque,
    )
    # A bare "chèque 1045" / "cheque 1045" (not the English verb "check"): only a patient's own, and not an amount.
    add(
        A,
        r"(?<!\$)\bch[èe]que[ \t]+(\d{3,8})(?!\d|[ \t]*(?:\$|€|dollars?|d[óo]lares|euros?|dolar|usd|cad|mg|ml))",
        I,
        1,
        _own_cheque,
    )

    # An account number in groups after an account word: "my account number is 1234 5678 9012".
    add(
        A,
        r"\b(?:account|acct|cuenta|compte|konto|konta)\b[^\n\d$€£]{0,30}?(?<![\d\-])(\d{4}(?:[ ]\d{4}){1,4}|\d{5}[ ]\d{5})(?![\d\-]|[ ]\d|[.,]\d)",
        I,
        1,
        lambda m: not all(re.fullmatch(r"(?:19|20)\d\d", g) for g in m.group(1).split()),
    )

    # Other groupings after an account word: 4-4-2 ("cuenta 1234 5678 90"), groups on separate lines after
    # "account number is", and a partial Polish number after "numer konta".
    _acct_cue = r"\b(?:account|acct|cuenta|compte|konto|konta)\b"
    add(
        A,
        rf"{_acct_cue}[^\n\d$€£]{{0,30}}?(?<![\d\-])(\d{{4}}[ ]\d{{4}}[ ]\d{{2,3}})(?![\d\-]|[ ]\d|[.,]\d)",
        I,
        1,
        lambda m: not re.fullmatch(r"(?:19|20)\d\d", m.group(1)[:4]),
    )
    add(
        A,
        rf"{_acct_cue}(?:[ \t]+(?:number|no\.?|num\.?|#|n[úu]mero|num[ée]ro))?[ \t]*(?:is|es|est|:)?[ \t]*\n[ \t]*"
        r"(\d{4}(?:[ \t]*\n[ \t]*\d{2,4}){2,3})(?![\d\-]|[ \t]*\n[ \t]*\d)",
        I,
        1,
        lambda m: not re.fullmatch(r"(?:19|20)\d\d", m.group(1)[:4]),
    )
    add(
        A,
        r"\b(?:numer|nr)[ ]+(?:konta|rachunku)\b[^\n\d]{0,10}?(?<![\d\-])(\d{2}(?:[ ]\d{4}){2,5})(?![\d\-]|[ ]\d)",
        I,
        1,
    )
    # A routing number typed in threes or with hyphens after its cue: "routing 021 000 021", "routing: 021-000-021".
    add(
        A,
        r"\b(?:routing|aba|rtn)(?:[ \t]+(?:number|no\.?|#|num[ée]ro|n[úu]mero))?[^\n\d]{0,25}?(?<![\d\-])(\d{3}[ \-]\d{3}[ \-]\d{3})(?![\d\-]|[ ]\d)",
        I,
        1,
    )

    # The last four of an SSN or a card asked in one line and answered in the next: "Paciente: es 4417".
    _last4 = (
        r"(?:[úu]ltimos\s+(?:4|cuatro)|last\s+(?:4|four)|(?:4|quatre)\s+derniers|ostatnie\s+(?:4|cztery))"
        r"(?:\s+(?:d[íi]gitos|digits|chiffres|cyfry|n[úu]meros))?"
    )
    _reply = (
        r"[ \t]*\??[ \t]*\n(?:[ \t]*\n){0,2}[^\n:]{0,25}:[ \t]*(?:[^\W\d_]+(?:['’][^\W\d_]+)?[ \t]+){0,3}?(\d{4})(?!\d)"
        r"(?:[ \t]+[^\W\d_]{1,8}){0,4}(?:[ \t]+\d{1,4})?[ \t.,!]*(?:\n|$)"
    )
    add(
        EntityType.SSN,
        rf"\b{_last4}[^\n]{{0,25}}\b(?:social|ssn|seguro\s+social|NAS|SIN)\b[^\n]{{0,6}}{_reply}",
        I,
        1,
    )
    add(
        A,
        rf"\b{_last4}[^\n]{{0,25}}\b(?:card|tarjeta|carte|karty)\b[^\n]{{0,6}}{_reply}",
        I,
        1,
    )

    # App accounts and portal user ids after their cue: "user=u_81723", "account name luna_cycle_88",
    # "usr=isandoval_8841", "Account name is mayattc_2026".
    _uv = (
        r"(?P<v>(?=[A-Za-z0-9._]*[A-Za-z])(?=[A-Za-z0-9._]*[_.\d])"
        r"(?:[A-Za-z][A-Za-z0-9]{0,20}[._][A-Za-z0-9._]{1,20}|[A-Za-z]{2,20}\d{2,8}|[A-Za-z0-9]{1,20}_[A-Za-z0-9_]{1,20})[A-Za-z0-9])"
    )
    add(
        ID,
        r"\b(?:usr|uid|user|usuario|(?:app\s+|portal\s+|online\s+)?account\s+name|screen\s*name|nick\s*name|profile\s+name|display\s+name)"
        r"(?:[ \t]*[=:][ \t]*|[ \t]+(?:is|es|est|was)[ \t]*:?[ \t]*|[ \t]+)[\"“'‘]?" + _uv + r"(?![\w@\-]|\.\w)",
        I,
        "v",
        _user_value,
    )

    # Device serials: "serial is SN 3MH0041AB7"; "SN" stays inside the span.
    add(
        ID,
        r"(?<![\w\-])(S/?N[ \t]*[:#]?[ \t]*(?=[A-Z0-9\-]*\d)(?=[A-Z0-9\-]*[A-Z])[A-Z0-9][A-Z0-9\-]{5,19})\b",
        0,
        1,
    )
    add(
        ID,
        r"\b(?:serial|numéro\s+de\s+série|n[úu]mero\s+de\s+serie)(?:[ \t]+(?:number|no\.?|#))?[ \t]*(?:is|es|est|:|=|#)?[ \t]*,?[ \t]*"
        r"((?=[A-Z0-9\-]*\d)[A-Z0-9][A-Z0-9\-]{5,19})\b",
        I,
        1,
        lambda m: bool(re.search(r"\d", m.group(1))) and _personal_device(m),
    )

    # Court and family-court file numbers: "26-FC-04417", "court file number 2026-0044-A".
    add(
        ID,
        r"\b(?:court|docket|case|cause|matter|file|dossier|expediente|sprawa)\b[^\n\d]{0,30}?(?<![\w\-])(\d{2,4}-[A-Z]{1,4}-\d{3,7})(?![\w\-])",
        I,
        1,
    )
    # The same with spaces or a slash, after the word "number" or in Spanish: "court number 2026 FC 1234",
    # "Court file no. 123-26", "numero de causa 1234-2026", "mi expediente de divorcio es 123/2026".
    _file_no = r"(\d{2,4}[ \-][A-Z]{1,4}[ \-]\d{3,7}|\d{3,6}[\-/]\d{2,4})(?![\w\-/]|[ ]\d)"

    def _file_ok(m: re.Match[str]) -> bool:
        v = m.group(1)
        # not a month and year or a day and month
        return not re.fullmatch(r"(?:19|20)\d\d[\-/](?:0?[1-9]|1[0-2])|(?:0?[1-9]|[12]\d|3[01])[\-/](?:0?[1-9]|1[0-2])", v)

    add(
        ID,
        r"\b(?:court|docket|case|cause|matter|file|tribunal)(?:[ \t]+(?:file|case))?[ \t]+(?:number|no\.?|num\.?|#)[ \t]*:?[ \t]*" + _file_no,
        I,
        1,
        _file_ok,
    )
    add(
        ID,
        r"\b(?:(?:n[úu]mero|num[ée]ro|nro\.?|n[°º])[ \t]+de[ \t]+(?:causa|expediente|autos|dossier)|causa|autos)[ \t]*:?[ \t]*(?:n[°º.]|no\.?|#)?[ \t]*" + _file_no,
        I,
        1,
        _file_ok,
    )
    add(
        ID,
        r"\bexpediente(?:[ \t]+de[ \t]+[a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+)?[ \t]*(?:es|:|=|es[ \t]+el)[ \t]*" + _file_no,
        I,
        1,
        _file_ok,
    )
    # A court prefix and a short file number only after a court word: "case SC 1234/26".
    add(
        ID,
        r"(?<![\w\-])(?:SC|FC|FD|DM|CV|CR|FM)[ \t]?\d{2,6}[/\-]\d{2,4}(?![\w\-/])",
        0,
        0,
        lambda m: re.search(r"(?i)\b(?:court|tribunal|juzgado|docket|case|file|filed|hearing|custody|divorce|divorcio)\b", m.string[max(0, m.start() - 80) : m.start()]) is not None,
    )
    add(ID, r"\b\d{2}-(?:FC|FM|FD|DM)-\d{3,7}\b")
    # Israeli court files: "תמ״ש 4417-26", "ת״פ 1234-05-26"; the court word stays in the span.
    add(
        ID,
        "(?<![א-ת])((?:תמ[\"״]ש|ת[\"״]פ|ה[\"״]פ|בג[\"״]ץ|ע[\"״]א|רע[\"״]א|תא[\"״]מ|ע[\"״]פ|בש[\"״]א)[ \t]*\\d{1,6}[\\-/]\\d{1,4}(?:[\\-/]\\d{2})?)(?!\\d)",
    )

    # Military and DoD ids after their cue, before it, or in groups.
    add(
        ID,
        r"\b(?:military|dod|edipi|service|cac|veteran|va|army|navy)[ \t]+(?:id|number|no\.?|#)(?:[ \t]+card)?[^\n\d]{0,20}?(?<![\d\-])(\d{4}-\d{2}-\d{4}|\d{9,10})(?![\d\-])",
        I,
        1,
    )
    add(
        ID,
        r"(?<![\d\-])(\d{4}-\d{2}-\d{4}|\d{3}-\d{2}-\d{4})(?![\d\-])(?=[^\n\d]{0,30}\b(?:military|dod|service)[ \t]+(?:id|number)\b)",
        I,
        1,
    )

    # National and status ids in digit groups after their name: "cédula es 52 418 903", "status card number is 1043 221 87".
    add(
        ID,
        r"(?:\b(?:c[ée]dula|dni|dpi|curp|status\s+(?:card|number|no\.?)|treaty\s+(?:card|number|no\.?)|identity\s+card|id\s+card|national\s+id|"
        r"carte\s+d['’]identit[ée]|documento\s+de\s+identidad)\b)(?:\s+(?:number|no\.?|#|n[úu]mero))?(?:\s+(?:is|es|est|:))?[^\n\d]{0,12}?"
        r"(?<![\d\-])(\d{1,4}(?:[ ]\d{2,4}){2,3})(?![\d\-]|[ ]\d)",
        I,
        1,
        lambda m: 7 <= len(_digits(m.group(1))) <= 12
        and not re.fullmatch(r"\d{1,2} \d{1,2} (?:19|20)\d\d|(?:19|20)\d\d \d{1,2} \d{1,2}", m.group(1)),
    )

    # Health cards in groups after a health-insurance word, any province: "CARTE MEDICARE N.-B.: 021 458 937".
    add(
        EntityType.HEALTH_CARD,
        r"\b(?:health\s*card|carte\s+(?:sant[ée]|medicare|soleil)|medicare|msi|msp|ohip|ramq|mcp|hcn)\b[^\n\d]{0,30}?"
        r"(?<![\d\-])(\d{3,4}(?:[ \-]\d{2,4}){2,3})(?![\d\-]|[ ]\d)",
        I,
        1,
        _health_digits,
    )
    # A Quebec card given in pieces: "C'est BOUA 8703" then, on the next line, "1415".
    add(
        EntityType.HEALTH_CARD,
        r"(?<![\w\-])[A-Z]{4}[ ]\d{4}(?![\d]|[ ]\d)",
        0,
        0,
        _health_before,
    )
    add(
        EntityType.HEALTH_CARD,
        r"(?<![\w\-])[A-Z]{4}[ ]\d{4}[ \t]*\n[^\n:]{0,25}:[ \t]*(?:[^\W\d_]+[ \t]+){0,3}?(\d{4})[ \t.]*(?:\n|$)",
        0,
        1,
        _health_before,
    )

    # Nine digits in threes with a SIN named earlier: "His is 412 880 659".
    add(EntityType.SIN, r"(?<![\d\-])\d{3}[ \-]\d{3}[ \-]\d{3}(?![\d\-]|[ ]\d)", 0, 0, _sin_cued)

    # An insurer's contract number with the insurer's name: "MGEN contrat 4408217".
    add(
        A,
        r"(?<![\w\-])[A-Z]{3,8}[ \t]+(?:contrat|contrato|police|p[óo]liza|polisa)[ \t]*(?:n[°o]\.?|number|no\.?|#)?[ \t]*:?[ \t]*\d{6,12}\b",
        0,
        0,
    )

    # Vehicle plate right after the word "plate": "plate TFR 4418".
    add(
        ID,
        r"\b(?i:plate)[ \t]+(?-i:(?P<p>(?:[A-Z]{2,4}[ \-]\d{2,4}|\d{1,2}[ \-]?[A-Z]{2,4}[ \-]?\d{1,4})\b))",
        0,
        "p",
        lambda m: True,
    )
    return R
