"""Name rules for the pattern detector: people introduced by context.

A name has no fixed shape, so these rules look for the words around it: a
self-introduction ("hi its jess", "je m'appelle", "קוראים לי"), a relative
("Husband Imran", "mi esposo Jorge", "Mój mąż Piotr"), a chart label
("Partner: Kevin Nguyen", "PATIENT: PARK, Soo-jin"), a sign-off ("Thanks so
much,\\nJess", "- Raj"), or an initial ("N. Abdulkadir"). Only the name is
masked, never the cue.

Capitalized names are accepted after any cue. Lowercase names (call
transcripts, texts) and Hebrew names (no capitals) only after strong cues, and
each word must not be a common function word, so "my name is spelled..." does
not mask "spelled".
"""

from __future__ import annotations

import re
from typing import Callable, Optional

# Letters. Latin-1 and Latin Extended-A cover French, Spanish and Polish.
_UP = "A-ZÀ-ÖØ-ÞĀĂĄĆĈĊČĎĐĒĔĖĘĚĜĞĠĢĤĦĨĪĬĮİĴĶĹĻĽĿŁŃŅŇŌŎŐŒŔŖŘŚŜŞŠŢŤŦŨŪŬŮŰŲŴŶŸŹŻŽ"
_LO = "a-zß-öø-ÿāăąćĉċčďđēĕėęěĝğġģĥħĩīĭįıĵķĺļľŀłńņňŋōŏőœŕŗřśŝşšţťŧũūŭůűųŵŷźżž"
_HE = "\u05d0-\u05ea"
_END = rf"(?![{_UP}{_LO}'’\-])"  # end of a word

# Capitalized word ("Okafor", "McLean", "Park-Lee", "MOHAMUD", "Wiśniewska").
_CW = rf"[{_UP}][{_UP}{_LO}'’]*(?:-[{_UP}{_LO}][{_UP}{_LO}'’]*)*[{_UP}{_LO}]{_END}"
_INI = rf"[{_UP}]\."  # initial
_SP = r"[ \t]"  # one space: forms use wider gaps between fields
# "Maria Lopez", "N. Al-Rashid", "Samantha J. Reyes", "Kimberly D.", "Brittany Lou Hanley".
NAME = rf"(?:{_INI}[ \t]?)?{_CW}(?:{_SP}(?:{_INI}|{_CW}))?(?:{_SP}{_CW})?"
# "Cassie & Tom", "Ana y Beto", "Magda i Piotr", "Hugo et Léa".
NAMES = rf"{NAME}(?:\s*&\s*{NAME}|{_SP}(?:and|et|y|e|i|und){_SP}{NAME})?"
# "PARK, Soo-jin", "DUPUIS, Marie-Claude", "Wiśniewski, Aleksander".
LAST_FIRST = rf"{_CW},[ \t]*{_CW}(?:{_SP}(?:{_INI}|{_CW}))?"

# Common words that are not names, in English, French, Spanish and Polish.
# Lowercase names stop at the first of these ("leah cohen katz and my husband").
STOP_WORDS = frozenset(
    """
    i im i'm i’m me my mine you your yours u ur we us our he him his she her hers they them
    their it its it's this that these those there here a an the and or but so if then than
    to too from for of on in at by with about as into out up down off over again now just
    also only still not no yes yeah yep yup ok okay um uh umm uhh hmm like well oh hi hey
    hello is am are was were be been being have has had do does did done will would can
    could should shall may might must going gonna wanna gotta get got gets getting go goes
    went come came coming call calling called calls speaking talking please thanks thank
    sorry regarding back checking wondering trying want wanted wants need needed needs know
    think see said says told tell ask asked asking really very sure fine good great all any
    some what when where who why how which hold wait one sec second minute calling texting
    patient caller agent husband wife partner mom dad mother father son daughter baby
    sister brother doctor nurse clinic office team spelled spell spelt with last first
    name not nope cant can't dont don't didnt didn't isnt isn't wasnt wasn't im ive i've
    she's he's hes shes theyre they're were we're whats what's thats that's
    je j'ai moi toi vous nous il elle ils elles on mon ma mes ton ta tes son sa ses le la
    les un une des de du et ou mais donc que qui quoi c'est est suis es sont ai as avez ont
    pour avec dans sur au aux en pas ne oui non bonjour bonsoir salut merci appelle conjoint
    conjointe mari femme chum blonde enceinte je suis allô allo
    yo tú usted ustedes él ella ellos ellas nosotros mi mis tu tus su sus unos unas los las
    del y o pero es soy son estoy está estamos para con por sí si hola gracias llamo
    llamando esposo esposa marido pareja buenos buenas días tardes noches quiero quería
    ja ty on ona ono my wy oni one mój moja moje twój twoja jest jestem są i a ale że to
    z ze w we na do od dla nie tak cześć dzień dobry dzwonię mąż żona żony męża pani pan
    proszę chciałam chciałem chciałabym mam ma mamy po
    changed change different wrong correct missing misspelled field same below above
    i'd i'll i’d i’ll we'll we've you're you'll dental pharmacy lab hospital reception front desk
    billing records insurance coordinator reminder
    """.split()
)
_HE_STOP = frozenset(
    """
    אני אתה את הוא היא אנחנו הם הן זה זאת זו של עם על אל לא כן שלום היי תודה בעלה אשתו
    בעלי אשתי מתקשר מתקשרת רוצה רציתי יש אין גם רק מה מי איך למה כי אבל או אם עוד כבר
    היום מחר אתמול בבקשה ילידת יליד תאריך לידה טלפון מספר מבקשת מבקש מדבר מדברת רבה
    בוקר טוב ערב מהמרפאה מטופלת מטופל שם משפחה פרטי ד״ר ד"ר לד״ר לד"ר דר גב׳ גב' לך לכם
    """.split()
)


def _alt(words) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


_NOT_STOP = rf"(?!(?:{_alt(STOP_WORDS)}){_END})"
_LWORD = rf"{_NOT_STOP}[{_LO}][{_LO}'’]*(?:-[{_LO}]+)*{_END}"
# Lowercase name, up to three words: "jess", "chen wei", "leah cohen katz".
LOWER_NAME = rf"{_LWORD}(?:{_SP}{_LWORD}){{0,2}}"
_HWORD = rf"(?!(?:{_alt(_HE_STOP)})(?![{_HE}]))[{_HE}][{_HE}'׳״\"]*"
# Hebrew name, one or two words, optionally "last, first" or "X and Y" ("רונית ואלון").
HE_NAME = rf"{_HWORD}(?:[ \t]{_HWORD})?(?:[ \t]ו{_HWORD})?"
HE_LAST_FIRST = rf"{_HWORD},[ \t]?{_HWORD}"

ANY_NAME = rf"(?:{LAST_FIRST}|{NAMES}|{LOWER_NAME}|{HE_NAME})"
CAP_NAME = rf"(?:{LAST_FIRST}|{NAMES}|{HE_NAME})"

# --- cues -------------------------------------------------------------------

_GREETING = (
    r"hi|hey|hello|yeah\s+hi|yes\s+hi|good\s+(?:morning|afternoon|evening)|salut|bonjour|"
    r"bonsoir|allô|allo|hola|buenos\s+d[ií]as|buenas(?:\s+tardes|\s+noches)?|cze[śs][ćc]|"
    r"dzie[ńn]\s+dobry|dobry\s+wiecz[óo]r|היי|שלום|בוקר\s+טוב|ערב\s+טוב"
)
_FILLER = r"um|uh|umm|erm|yeah|yes|ok|okay|so|oui|euh|s[íi]|bueno|tak|no\s+wi[ęe]c"
_INTRO = r"it'?s|it’s|its|this\s+is|c'est|c’est|soy|es|tu|m[óo]wi|זאת|זה|זו|מדבר|מדברת|here'?s"
# Strong: what follows is the speaker's own name, in any case.
_STRONG = (
    r"my\s+name\s+is|my\s+name['’]s|my\s+name\s*:|name\s+is|name['’]s|me\s+llamo|mi\s+nombre\s+es|"
    r"je\s+m['’ ]?appelle|mon\s+nom\s+est|nazywam\s+si[eę]|mam\s+na\s+imi[eę]|"
    r"(?:first|last|full|maiden|middle|legal|family)\s*name(?:\s+is|\s*:)?|sur\s*name(?:\s+is|\s*:)?|"
    r"(?:his|her|their)\s+name(?:\s+is|\s*:)?|apellido(?:\s+es|\s*:)?|nazwisko(?:\s+to|\s*:)?|"
    r"(?:listed|registered|booked|filed|authori[sz]ed(?:\s+me)?)\s+under|under\s+the\s+name|"
    r"(?:name\s+is\s+|is\s+|it'?s\s+)?spel(?:led|t)|name\s+on\s+(?:the\s+)?\w+\s+(?:is|says|reads)|"
    r"nombre\s+en\s+el\s+\w+\s+es|mi\s+nombre|"
    r"קוראים\s+לי|שמי|השם\s+שלי"
)
# Capitalized names only: weaker cues where a lowercase word is rarely a name.
_WEAK = (
    r"it'?s|it’s|its|this\s+is|i\s+am|i'm|i’m|im|signed|we'?re|we\s+are|nous\s+sommes|somos|"
    r"jeste[śs]my|c'est|c’est|soy|tu|m[óo]wi|attention|attn|"
    r"(?:name\s+)?(?:tag|label|labels|chart)\s+(?:says|reads?)"
)
_VALEDICTION = (
    r"thanks(?:\s+(?:so|very)\s+much|\s+again|\s+a\s+lot|\s+a\s+million)?|thank\s+you(?:\s+(?:so|very)\s+much)?|"
    r"thx|ty|cheers|regards|best(?:\s+regards|\s+wishes)?|kind\s+regards|warm(?:est)?\s+regards|"
    r"sincerely|yours(?:\s+truly)?|with\s+(?:love|gratitude|thanks)|love|lots\s+of\s+love|xo+|hugs|"
    r"merci(?:\s+beaucoup|\s+encore)?|cordialement|bisous|bises|amiti[ée]s|"
    r"gracias|saludos|atentamente|un\s+abrazo|los\s+quiere|te\s+quiere|con\s+cari[ñn]o|"
    r"pozdrawiam|pozdrawiamy|dzi[eę]kuj[eę]|dzi[eę]kujemy|dzi[eę]ki|z\s+pozdrowieniami|"
    r"z\s+powa[żz]aniem|signed|bien\s+[àa]\s+vous|salutations"
)
# Valedictions that may be followed by the name with just a space ("Thanks Priya").
_VALEDICTION_SPACE = (
    r"thanks|thank\s+you|cheers|regards|sincerely|merci|gracias|saludos|pozdrawiam|pozdrawiamy|"
    r"dzi[eę]kuj[eę]|dzi[eę]kujemy"
)
_HE_VALEDICTION = r"תודה(?:\s+רבה)?|בברכה|באהבה"
_RELATIONS = (
    # English
    r"husband|hubby|wife|partner|spouse|boyfriend|girlfriend|fianc[eé]e?|son|daughter|"
    r"mom|mum|mother|dad|father|sister|brother|friend|aunt|uncle|cousin|niece|nephew|"
    r"grandmother|grandfather|grandma|grandpa|stepdaughter|stepson|"
    r"(?:mother|father|sister|brother)[ \-]in[ \-]law|little[ \t]+(?:girl|boy|one)|baby|"
    r"donor|surrogate|gestational\s+carrier|carrier|gc|ips|intended\s+parents?|"
    r"emergency\s+contact|agency\s+contact|interpreter|translator|boss|coworker|colleague|"
    r"lawyer|attorney|policy\s*holder|subscriber|insured|guarantor|"
    # French
    r"mari|[ée]poux|[ée]pouse|femme|conjoint|conjointe|chum|blonde|copain|copine|fils|fille|"
    r"m[èe]re|p[èe]re|s(?:œ|oe)ur|fr[èe]re|tante|oncle|ni[èe]ce|neveu|cousine|"
    r"belle-m[èe]re|beau-p[èe]re|m[èe]re\s+porteuse|petite|petit|b[ée]b[ée]|ma[îi]tre|"
    # Spanish
    r"esposo|esposa|marido|mujer|pareja|novio|novia|hijo|hija|madre|padre|mam[áa]|pap[áa]|"
    r"hermana|hermano|t[íi]a|t[íi]o|sobrina|sobrino|prima|primo|cu[ñn]ada|cu[ñn]ado|"
    r"suegra|suegro|amiga|amigo|gestante|"
    # Polish
    r"m[ąa][żz]|m[ęe][żz]a|m[ęe][żz]em|m[ęe][żz]owi|[żz]ona|[żz]ony|[żz]on[ąa]|partnerka|syn|"
    r"c[óo]rka|c[óo]rk[ąa]|matka|ojciec|tata|siostra|siostr[ąa]|brat|bratem|ciocia|wujek|"
    r"te[śs][ćc]|te[śs]ciowa|szwagier|szwagierka|kuzyn|kuzynka|przyjaci[óo][łl]ka|przyjaciel|"
    r"nasza|nasz|c[óo]reczka|synek|pani|pan"
)
# Relations after which a lowercase word may be a name ("my wife hope she...").
_LOWER_RELATIONS = (
    r"husband|hubby|wife|partner|spouse|boyfriend|girlfriend|son|daughter|mom|mum|mother|"
    r"dad|father|sister|brother|friend|little[ \t]+(?:girl|boy)|"
    r"mari|femme|conjointe?|chum|blonde|fils|fille|m[èe]re|s(?:œ|oe)ur|fr[èe]re|"
    r"esposo|esposa|marido|pareja|hijo|hija|hermana|hermano|"
    r"m[ąa][żz]|[żz]ona|c[óo]rka|siostra|brat"
)
# What a full name is often followed by in charts, letters and forms.
_ID_NEXT = (
    r"dob|d\.o\.b\.?|date\s+of\s+birth|born|n[ée]e?|ddn|fdn|ur\.|urodzon[ay]|ת[״\"]ל|"
    r"mrn|chart|file|ohip|health\s+card|member(?:\s+id)?|policy|ramq|hcn|age\s+\d|\d{1,3}\s*[FM]\b"
)
# Nouns that take "for <patient>": "a prescription for", "results for", "coverage for".
_FOR_NOUNS = (
    r"prescription|fax|results?|requisition|referral|coverage|appointment|sample|specimen|"
    r"shipper|shipment|chart|file|records?|consent|consent\s+visit|visit|order|calling|message|"
    r"wristband|label|labels|bracelet|interpreter\s+booked|booked|"
    r"ordonnance|r[ée]sultats|dossier|an[áa]lisis|resultados|receta|wyniki|recepta|skierowanie"
)
# Words that follow a name used as a subject ("my wife hope she had...").
_SUBJECT_NEXT = (
    r"she|he|is|was|has|had|will|and|told|said|says|who|isn't|can't|cant|"
    r"elle|il|est|a|ella|él|es|ona|on|jest|i|y|et"
)
_HE_RELATIONS = (
    r"בעלה\s+של|אשתו\s+של|בעלי|אשתי|בעלה|אשתו|אחותי|אחי|אחותה|אמא\s+שלי|אמא\s+שלה|"
    r"הבת\s+שלי|הבן\s+שלי|גב['׳]|גברת|מר|לגב['׳]"
)
_PERSON_LABELS = (
    r"patient|patients?\s+name|pt|client|name|full\s+name|patiente|nom|paciente|nombre|"
    r"pacjent(?:ka)?|imi[ęe]\s+i\s+nazwisko"
)
# Two or more words: "Kimberly D.", "Samantha J. Reyes", "Maria Lopez".
_MULTI_NAME = rf"(?:{_INI}[ \t]?)?{_CW}{_SP}(?:{_INI}|{_CW})(?:{_SP}{_CW})?"
_LABELS = (
    r"patient\s+name|pt\s+name|full\s+name|partner|spouse|husband|wife|"
    r"subscriber|policy\s*holder|insured|emergency\s+contact|contact|attention|attn|gc|"
    r"surrogate|intended\s+parents?|ips|mother|father|conjointe?|mari|[ée]pouse|"
    r"recipient|applicant|signature|member|cardholder|card\s+holder|given(?:\s+names?)?|surname|"
    r"referral|r[ée]f[ée]rence|referencia|skierowanie|requisition|lab\s+requisition|"
    r"contacto|kontakt|insurance\s+verification|"
    r"esposo|esposa|nazwisko|imi[ęe]|"
    r"m[ąa][żz]|[żz]ona"
)
_HE_LABELS = r"מטופלת|מטופל|שם(?:\s+(?:משפחה|פרטי|המטופלת|המטופל|מלא))?|בן\s+זוג|בת\s+זוג|הפניה"
# Transcript speaker labels that belong to the patient side.
_SPEAKER = (
    r"(?i:caller|user|visitor|guest|patient|client|customer|parent|partner|husband|wife|mom|dad|"
    r"patiente|visiteur|visiteuse|appelant|appelante|paciente|llamante|visitante|usuario|usuaria|"
    r"pacjent|pacjentka|dzwoni[ąa]c[ya]|go[śs][ćc]|מטופלת|מטופל|מתקשר|מתקשרת|לקוח|לקוחה)"
)
_NAME_WORDS = r"name|names|nom|nombre|apellido|nazwisko|nazwiska|imi[eę]|שם|השם|שם\s+המשפחה"

# Sentence starters that follow an initial without being a surname ("plan B. Then").
_NOT_SURNAMES = frozenset(
    """
    the then this that these those we i it he she they you please also and but so if our
    your my call see note take start stop keep let let's no yes ok okay thanks thank in on
    at for to from with after before when while as is are was were will can could should
    would do did does have has had please per each every all any some one two three
    """.split()
)


# Capitalized words that follow "is", "I'm", "my wife is" without being names.
_NOT_NAME_EXTRA = frozenset(
    """
    canadian american british english indian chinese jewish muslim catholic christian hindu
    sikh buddhist polish french spanish mexican filipino filipina korean japanese italian
    portuguese irish scottish black white asian hispanic latina latino arab persian african
    caribbean jamaican haitian nigerian pakistani vietnamese russian ukrainian german greek
    turkish iranian lebanese somali ethiopian eritrean punjabi tamil bengali brazilian
    colombian québécoise québécois quebecois francophone anglophone type rh pregnant
    mme mlle me m sr sra srta pan pani panią panu mr mrs ms miss mx dr dre dra
    click sign tap stop start wait come right over live work born staying sit look
    write call text email reply book everyone nobody someone anyone
    services service billing team office care support reception nursing lab laboratory
    department centre center clinic admin administration accounts finance intake scheduling
    booking portal results education records pharmacy front desk unit room boardroom
    saludos pozdrawiam pozdrawiamy cordialement atentamente regards sincerely cheers best love
    merci gracias thanks thank dziękuję dziękujemy dzięki bises bisous xo xoxo hugs
    doctora docteur docteure doktor doktorze panie
    i'd i'll i've i’d i’ll i’ve am pm a.m p.m
    """.split()
)
# Function words that can still be first names when capitalized ("Thanks, Will").
_NAME_LIKE_STOP = frozenset({"will", "may", "ty", "said", "pat", "ma"})


def _first(m: re.Match[str]) -> str:
    # Skip initials: "N. Abdulkadir" -> "abdulkadir".
    for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", m.group("name")):
        if len(w) > 1:
            return w.lower()
    return ""


# A clinician's name: "Dr. A. Kaur", "RN T. Boateng", "Beth Alvarado, RN".
_TITLE_BEFORE = re.compile(
    r"(?i:\b(?:dr|dre|dra|doctor|doctora|docteur|docteure|nurse|rn|np|md|inf|enf)\.?|ד[״\"']ר)\s*$"
)
_CREDENTIAL_AFTER = re.compile(r"^,?[ \t]*(?:RN|RPN|NP|MD|M\.D\.|PhD|DO|inf\.?|RM)\b")


def make_checks(not_names: frozenset[str] | set[str]):
    blocked = (set(not_names) | _NOT_NAME_EXTRA | STOP_WORDS) - _NAME_LIKE_STOP

    def _ok(m: re.Match[str], caps: bool) -> bool:
        name = m.group("name")
        first = _first(m)
        if not first or first in blocked:
            return False
        text, start, end = m.string, m.start("name"), m.end("name")
        if _TITLE_BEFORE.search(text[max(0, start - 12) : start]):
            return False
        if _CREDENTIAL_AFTER.match(text[end : end + 8]):
            return False
        if name.isupper() and "," not in name:
            # "ID", "IVF", "DONOR MATCH": all-caps words are labels, except
            # after a strong cue or a chart label ("PARTNER: TOMASZ KOWALCZYK").
            return caps and (len(name) > 4 or " " in name)
        return True

    def check(m: re.Match[str]) -> bool:
        return _ok(m, caps=False)

    def check_caps(m: re.Match[str]) -> bool:
        return _ok(m, caps=True)

    def check_initial(m: re.Match[str]) -> bool:
        words = m.group("name").split()
        return words[-1].lower().strip(".") not in _NOT_SURNAMES and check(m)

    return check, check_caps, check_initial


def rules(
    not_names: frozenset[str] | set[str],
) -> list[tuple[str, int, Optional[Callable[[re.Match[str]], bool]]]]:
    """(pattern, flags, check) for NAME. Each pattern has a ``name`` group."""
    check, check_caps, check_initial = make_checks(not_names)
    start = r"(?:^|(?<=[\s,.!?:;\"'(—–\-]))"
    return [
        # "my name is chen wei", "je m'appelle Catherine", "קוראים לי ענת שפירא".
        (rf"(?i:\b(?:{_STRONG}))[ \t]*,?[ \t]*(?P<name>{ANY_NAME})", 0, check_caps),
        # "hi its jess", "caller: hi its bill", "hola, soy Paty", "היי זאת שירה".
        (rf"(?i:(?:\b|(?<=\s)|^)(?:{_GREETING}))(?:[\s,!.—\-]+(?i:{_FILLER}))*[\s,!.—\-]*(?i:(?:{_INTRO}))[ \t]+(?P<name>{ANY_NAME})", 0, check),
        # Speaker line opening with an introduction: "caller: c'est mathieu".
        (rf"(?m:^)[ \t]*{_SPEAKER}[ \t]*:(?:[ \t]*(?i:{_FILLER}|{_GREETING})[ \t,]*)*[ \t]*(?i:(?:{_INTRO}))[ \t]+(?P<name>{ANY_NAME})", 0, check),
        # "hi i'm marcus henry i can't...", "i'm beth": lowercase only when the clause ends there.
        (
            rf"(?i:(?:(?:{_GREETING})[\s,]+|(?m:^)[ \t]*{_SPEAKER}[ \t]*:[ \t]*)(?:(?:{_FILLER})[\s,]+)*(?:i'?m|i’m|i\s+am))"
            rf"[ \t]+(?P<name>{_LWORD}(?:{_SP}{_LWORD})?)(?=[ \t]*(?:[,.!?\n]|$)|[ \t]+(?i:i|and|calling|from|here|again){_END})",
            0,
            check,
        ),
        # "le conjoint de sandrine côté", "el marido de patricia".
        (rf"(?i:\b(?:conjointe?|mari|femme|chum|blonde|marido|esposo|esposa|pareja)[ \t]+(?:de|del|d'))[ \t]*(?P<name>{LOWER_NAME})", 0, check),
        # An answer to a question about a name: "may i have your name\ncaller: leah cohen katz".
        (
            rf"(?i:\b(?:{_NAME_WORDS})\b)[^\n]{{0,60}}\n[ \t]*{_SPEAKER}[ \t]*:[ \t]*"
            rf"(?:(?i:um|uh|yes|yeah|sure|ok|oui|s[íi]|tak|כן)[\s,]+)*(?P<name>{ANY_NAME})",
            0,
            check_caps,
        ),
        # "I'm Kim Park", "we're Hugo et Léa", "under William Tran", "c'est Mathieu".
        (rf"(?i:\b(?:{_WEAK}))[ \t]*,?[ \t]+(?P<name>{CAP_NAME})", 0, check),
        # "Fatima here", "Hola Felipe aquí".
        (rf"{start}(?P<name>{NAME}){_SP}(?i:here|aqu[íi]|ici|tutaj){_END}(?=\s*(?:[,.!:;—\-]|$))", re.MULTILINE, check),
        # "Thanks so much,\nJess", "Los quiere, Ana y Beto", "Pozdrawiamy, Monika i Krzysztof".
        (rf"(?i:\b(?:{_VALEDICTION}))(?:[ \t]*,[ \t]*\n?|[ \t]*[,!.]?[ \t]*\n)[ \t]*(?P<name>{NAMES}|{LAST_FIRST})", 0, check),
        (rf"(?i:\b(?:{_VALEDICTION_SPACE}))[ \t]+(?P<name>{NAMES})", 0, check),
        (rf"(?<!\w)(?:{_HE_VALEDICTION})[ \t]*,?[ \t]*\n?[ \t]*(?P<name>{HE_NAME})(?=[ \t]*(?:[.,!?\n]|$))", 0, check),
        # Dash sign-off at the end: "- Raj", "— N. Abdulkadir", "xo - Gabi".
        (rf"(?:^|\s)[-–—~]+\s*(?P<name>{NAMES})\s*[.!]?\s*\Z", 0, check),
        # A relative or contact: "Husband Imran", "Partner: Kevin Nguyen",
        # "surrogate is Tiffany Rhodes", "mi esposo Jorge", "Mój mąż Piotr".
        (
            rf"(?i:\b(?:{_RELATIONS})(?:'s)?(?:[ \t]+(?:name[ \t]+is|is|are|est|sont|es|son|jest|to|de|del|d'|of))?)[ \t]*[:,]?[ \t]*"
            rf"(?P<name>{LAST_FIRST}|{NAMES})",
            0,
            check,
        ),
        # "my wife hope she...", "my daughter rose told me": lowercase after a possessive.
        (
            rf"(?i:\b(?:my|mi|mon|ma|m[óo]j|moja)[ \t]+(?:{_LOWER_RELATIONS}))[ \t]+(?P<name>{_LWORD})"
            rf"(?=[ \t]*[,.!?;)]|[ \t]+(?:{_SUBJECT_NEXT}){_END})",
            0,
            check,
        ),
        (rf"(?<!\w)(?:{_HE_RELATIONS})[ \t]+(?P<name>{HE_NAME})", 0, check),
        # Chart labels: "Patient: Kimberly D.", "PATIENT: PARK, Soo-jin", "Pacjent: Wiśniewski, Aleksander".
        (rf"(?i:\b(?:{_LABELS}))[ \t]*:[ \t]*(?P<name>{LAST_FIRST}|{NAMES})", 0, check_caps),
        # Speaker-like labels ("Patient:", "PACJENT:") start transcript lines too, so a
        # single capitalized word there is usually the first word of a sentence.
        (rf"(?i:\b(?:{_PERSON_LABELS}))[ \t]*:[ \t]*(?P<name>{LAST_FIRST}|{_MULTI_NAME})", 0, check_caps),
        (rf"(?<!\w)(?:{_HE_LABELS})[ \t]*:[ \t]*(?P<name>{HE_LAST_FIRST}|{HE_NAME})", 0, check),
        # Greetings and patient cues: "Hi, Anna Kowalski", "Pt P. Raman", "Dear Ms Lee".
        (rf"(?i:\b(?:pt|client|dear|hi|hello|hey|bonjour|hola|cze[śs][ćc]))[ \t]*,?[ \t]+(?P<name>{NAMES})", 0, check),
        (rf"(?i:\b(?:patient|patiente|paciente|pacjent(?:ka)?))[ \t]+(?P<name>{LAST_FIRST}|{NAMES})", 0, check),
        # A full name right before an identifier: "Hannah Ostrowski, DOB", "Leona Strand chart MRN",
        # "Adriana Mejía, FDN", "Joanna Dąbrowska, ur.", "Ashley Pruitt (chart 0052004)".
        (rf"(?P<name>{LAST_FIRST}|{_MULTI_NAME})(?:['’]s)?[ \t]*[,(]?[ \t]*\(?(?i:{_ID_NEXT}){_END}", 0, check),
        # Email headers and quotes: "From: Jessica Okafor <jess@...>", "Karen Whitfield wrote:".
        (rf"(?P<name>{NAMES})[ \t]*<[^\s<>@]+@", 0, check),
        (rf"(?P<name>{NAMES})[ \t]+(?:wrote|a\s+[ée]crit|escribi[óo]|napisa[łl]a?)[ \t]*:", 0, check),
        # Subject lines: "Subject: Referral - Hannah Ostrowski", "Complaint - Wanda Ross".
        (rf"(?i:subject|objet|asunto|temat)[ \t]*:[^\n]*?[-–—:][ \t]*(?P<name>{_MULTI_NAME})[ \t]*(?:$|[,(]|(?i:dob))", re.MULTILINE, check),
        # "a prescription for Alina Petrova", "coverage for Sophia Brandt", "Please call Hannah Goldfarb".
        (rf"(?i:\b(?:{_FOR_NOUNS})[ \t]+(?:for|de|para|dla|pour)|\b(?:call|text|email|contact|ask\s+for|speak\s+(?:to|with)))[ \t]+(?P<name>{_MULTI_NAME})", 0, check),
        # Signature block: a name alone on a line after a blank line, at the end or
        # above contact details ("\n\nBen Okafor\n(905) 555-0114", "\n\nLauren").
        (
            rf"(?:\n[ \t]*\n|(?m:^)--[ \t]*\n)[ \t]*(?P<name>{NAMES})[ \t]*[.!]?[ \t]*"
            rf"(?=\s*\Z|[ \t]+[-–—|][ \t]*\S|\n[ \t]*(?:\(?\+?\d[\d \t().\-]{{6,}}|\S+@\S+|Sent\s+from|Envoy[ée]|Enviado|>)|\n\s*\n[ \t]*(?:On|Le|El|W\s+dniu)\s.{{5,80}}(?:wrote|[ée]crit|escribi|napisa))",
            0,
            check,
        ),
        (rf"(?<![{_HE}])(?P<name>{HE_NAME})[ \t]+כאן(?![{_HE}])", 0, check),
        # An initial and a surname at the start of a sentence: "Phone note: C. Wu states".
        (
            rf"(?:^|(?<=[.:!?\n])[ \t]+|(?<=\n))(?P<name>{_INI}[ \t]?{_CW}(?:-{_CW})?)(?=[ \t]+[{_LO}]|[ \t]*[.,]|$)",
            re.MULTILINE,
            check_initial,
        ),
    ]


def courtesy_rules(
    not_names: frozenset[str] | set[str],
) -> list[tuple[str, int, Optional[Callable[[re.Match[str]], bool]]]]:
    """Courtesy titles name patients and relatives, not clinicians."""
    check, _, _ = make_checks(not_names)
    titles = r"Mr|Mrs|Ms|Miss|Mx|Mme|Mlle|Me|Sr|Sra|Srta|Pan|Pani|Panią|Panu"
    return [
        (rf"\b(?:{titles})\.?\s+(?P<name>{NAME})", 0, check),
        # Transcripts: "a mrs ostrowski".
        (rf"\b(?:mr|mrs|ms|miss)\.?\s+(?P<name>{_LWORD})", 0, check),
    ]


# Spelled-out words ("k o w a l c z y k", "S-Z-C-Z-E-P-A-Ń-S-K-A", "ג-ו-ל-ד-ב-ר-ג").
SPELLED = (
    rf"(?<![\w\-])[A-Za-z{_UP}{_LO}](?:(?:\s+|-)(?:hyphen\s+|dash\s+)?[A-Za-z{_UP}{_LO}]){{3,}}(?![\w\-])|"
    rf"(?<![\w\-])[{_HE}](?:-[{_HE}]){{3,}}(?![\w\-])"
)
