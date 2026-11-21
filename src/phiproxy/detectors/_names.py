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

from . import _hebrew

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
    dept department departamento departement service services interpreter interprète intérprete
    tłumacz tłumaczka abogado abogada lawyer attorney avocat avocate prawnik ça cela number
    moving valued patients drs plan maman mamá papa papá trabajadora trabajador social
    travailleuse travailleur facturación facturation equipo équipe zespół
    passed died dead away deceased lives lived works worked moved left stays stayed
    siempre nunca también se médica médico medica enfermera enfermero asistente paciente
    zawsze nigdy też już
    hard easy difficult impossible ready busy correct important possible
    fait hecho oraz lub albo czyli
    """.split()
)
# Words added to STOP_WORDS late: ordinary words that are also rare surnames. A courtesy title or an
# explicit name cue right before a capitalized one ("Mrs. Hard", "My last name is Hard") is stronger evidence.
_LATE_STOP = frozenset("hard easy difficult impossible ready busy correct important possible fait hecho oraz lub albo czyli".split())
_TITLE_CUE_BEFORE = re.compile(
    r"(?i:\b(?:mr|mrs|ms|miss|mx|mme|mlle|sr|sra|srta|pan|pani|pana|panu|panie|se[ñn]or(?:a|ita)?|do[ñn]a|madame|monsieur)\b)\.?[ \t]*$"
)
_NAME_CUE_BEFORE = re.compile(
    r"(?i:\b(?:mr|mrs|ms|miss|mx|mme|mlle|sr|sra|srta|pan|pani|pana|panu|panie|se[ñn]or(?:a|ita)?|do[ñn]a|madame|monsieur|"
    r"(?:(?:last|first|full|sur|family)[ \t]+)?name(?:[ \t]+(?:is|was))?|surname(?:[ \t]+(?:is|was))?|patient|pt|apellido(?:[ \t]+es)?|nombre(?:[ \t]+es)?|nazwisko(?:[ \t]+to)?|"
    r"imi[eę]|nom(?:[ \t]+de[ \t]+famille)?|je[ \t]+m['’]appelle|me[ \t]+llamo|this[ \t]+is|it['’]?s|i[ \t]+am|i['’]m|soy|nazywam[ \t]+si[eę]|mon[ \t]+nom[ \t]+est)\b)"
    r"\.?[ \t]*[:,\-]?[ \t]*$"
)
_HE_STOP = frozenset(
    """
    אני אתה את הוא היא אנחנו הם הן זה זאת זו של עם על אל לא כן שלום היי תודה בעלה אשתו
    בעלי אשתי מתקשר מתקשרת רוצה רציתי יש אין גם רק מה מי איך למה כי אבל או אם עוד כבר
    היום מחר אתמול בבקשה ילידת יליד תאריך לידה טלפון מספר מבקשת מבקש מדבר מדברת רבה
    קידומת אחר כך ואז אז שוב בוקר טוב ערב מהמרפאה מטופלת מטופל שם משפחה פרטי ד״ר ד"ר לד״ר לד"ר דר גב׳ גב' לך לכם
    שלי שלה שלו שלנו שלכם שלהם קיבלתי קיבלנו מראש ביי להתראות בסדר סבבה אוקיי אוקי סליחה
    """.split()
)


def _late_stop_cued(m: re.Match[str]) -> bool:
    before = m.string[max(0, m.start("name") - 30) : m.start("name")]
    if _TITLE_CUE_BEFORE.search(before):
        return True
    return m.group("name")[:1].isupper() and bool(_NAME_CUE_BEFORE.search(before))


def _alt(words) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


_NOT_STOP = rf"(?!(?:{_alt(STOP_WORDS)}){_END})"
_LWORD = rf"{_NOT_STOP}[{_LO}][{_LO}'’]*(?:-[{_LO}]+)*{_END}"
# After a courtesy title the late stop words still name a person: "mrs hard called".
_LWORD_TITLED = rf"(?!(?:{_alt(STOP_WORDS - _LATE_STOP)}){_END})[{_LO}][{_LO}'’]*(?:-[{_LO}]+)*{_END}"
# Lowercase name, up to three words: "jess", "chen wei", "leah cohen katz".
LOWER_NAME = rf"{_LWORD}(?:{_SP}{_LWORD}){{0,2}}"
_HWORD = rf"(?!(?:{_alt(_HE_STOP)})(?![{_HE}]))[{_HE}][{_HE}'׳״\"]*"
# Hebrew name, one or two words, optionally "last, first" or "X and Y" ("רונית ואלון").
HE_NAME = rf"{_HWORD}(?:[ \t](?:(?:בן|בת|בר|אבו)[ \t\-])?{_HWORD})?(?:[ \t]ו{_HWORD})?"
HE_LAST_FIRST = rf"{_HWORD},[ \t]?{_HWORD}"

ANY_NAME = rf"(?:{LAST_FIRST}|{NAMES}|{LOWER_NAME}|{HE_NAME})"
CAP_NAME = rf"(?:{LAST_FIRST}|{NAMES}|{HE_NAME})"

# --- cues -------------------------------------------------------------------

_GREETING = (
    r"hi|hey|hello|yeah\s+hi|yes\s+hi|good\s+(?:morning|afternoon|evening)|salut|bonjour|"
    r"bonsoir|allô|allo|hola|buenos\s+d[ií]as|buenas(?:\s+tardes|\s+noches)?|cze[śs][ćc]|"
    r"dzie[ńn]\s+dobry|dobry\s+wiecz[óo]r|witam|witaj|היי|שלום|בוקר\s+טוב|ערב\s+טוב"
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
    r"jeste[śs]my|jestem|c'est|c’est|soy|tu|m[óo]wi|attention|attn|"
    r"(?:name\s+)?(?:tag|label|labels|chart)\s+(?:says|reads?)"
)
_VALEDICTION = (
    r"thanks(?:\s+(?:so|very)\s+much|\s+again|\s+a\s+lot|\s+a\s+million)?|thank\s+you(?:\s+(?:so|very)\s+much)?|"
    r"thx|ty|cheers|regards|best(?:\s+regards|\s+wishes)?|kind\s+regards|warm(?:est)?\s+regards|warmly|warm\s+wishes|bendiciones|respectfully|gratefully|cordially|take\s+care|"
    r"sincerely|yours(?:\s+truly)?|with\s+(?:love|gratitude|thanks)|love|lots\s+of\s+love|xo+|hugs|"
    r"merci(?:\s+beaucoup|\s+encore)?|cordialement|bisous|bises|amiti[ée]s|"
    r"gracias|saludos(?:\s+cordiales)?|un\s+(?:cordial\s+)?saludo|atentamente|atte|cordialmente|afectuosamente|"
    r"quedo\s+atent[oa]|atenciosamente|amicalement|z\s+wyrazami\s+szacunku|pozdrawiam\s+serdecznie|"
    r"un\s+abrazo|los\s+quiere|te\s+quiere|con\s+cari[ñn]o|"
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
    r"neighbou?r|voisine?|vecin[ao]|babysitter|nanny|caregiver|carer|guardian|foster\s+(?:parent|mother|father|mom|dad|carer)|case\s*worker|"
    r"lawyer|attorney|policy\s*holder|subscriber|insured|guarantor|"
    # French
    r"mari|[ée]poux|[ée]pouse|femme|conjoint|conjointe|chum|blonde|copain|copine|fils|fille|"
    r"m[èe]re|p[èe]re|s(?:œ|oe)ur|fr[èe]re|tante|oncle|ni[èe]ce|neveu|cousine|amie|ami|"
    r"belle-m[èe]re|beau-p[èe]re|m[èe]re\s+porteuse|petite|petit|b[ée]b[ée]|ma[îi]tre|"
    # Spanish
    r"esposo|esposa|marido|mujer|pareja|novio|novia|hijo|hija|madre|padre|mam[áa]|pap[áa]|"
    r"hermana|hermano|t[íi]a|t[íi]o|sobrina|sobrino|prima|primo|cu[ñn]ada|cu[ñn]ado|"
    r"suegra|suegro|amiga|amigo|gestante|"
    # Polish
    r"m[ąa][żz]|m[ęe][żz]a|m[ęe][żz]em|m[ęe][żz]owi|[żz]ona|[żz]ony|[żz]on[ąa]|partnerka|syn|"
    r"c[óo]rka|c[óo]rk[ąa]|matka|ojciec|tata|siostra|siostr[ąa]|brat|bratem|ciocia|wujek|"
    r"te[śs][ćc]|te[śs]ciowa|szwagier|szwagierka|kuzyn|kuzynka|przyjaci[óo][łl]ka|przyjaciel|"
    r"nasza|nasz|c[óo]reczka|synek|pani|pan|"
    # Tagalog and Vietnamese
    r"anak|asawa|nanay|tatay|kapatid|chồng|vợ|con\s+gái|con\s+trai|mẹ|bố"
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
    r"בן\s+הזוג\s+שלי|בת\s+הזוג\s+שלי|בן\s+זוגי|בת\s+זוגי|אבא\s+שלי|עורכת\s+הדין|עורך\s+הדין|"
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
# A transcript line may start with its time: "[00:00:58] Caller: ...".
_TS = r"(?:\[[\d:.]{4,12}\][ \t]*)?"
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
    hmong ojibwe amharic tigrinya arabic mandarin cantonese tagalog urdu hindi farsi
    phone sms mobile cell voicemail morning afternoon evening mail weekday weekdays weekends
    swahili laotian khmer burmese nepali quote quotes calendar google outlook zoom invoice estimate
    colombian québécoise québécois quebecois francophone anglophone type rh pregnant
    mme mlle me m sr sra srta pan pani panią panu mr mrs ms miss mx dr dre dra
    click sign tap stop start wait come right over live work born staying sit look
    write call text email reply book everyone nobody someone anyone
    philippines aadhaar métis metis embryology andrology logistics agency cryo shipping procurement purchasing
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
# Words that open an email or a sentence before "and I" but are not people.
_NOT_ADDRESSEE = frozenset(
    """
    all everyone everybody team folks friends colleagues sir madam madame sirs gentlemen ladies doctor doctors
    hello hi hey dear greetings morning afternoon evening good thanks thank update reminder note summary hello
    you me him her them us we they he she it this that then so but yes no ok okay and or nurse nurses billing
    records reception admin support staff coordinator coordinators parents mom dad family patient patients
    bonjour hola buenos buenas cześć dzień witam monsieur señor señora estimado estimada estimados szanowni
    szanowna szanowny drodzy kochani chers cher chère queridos queridas
    """.split()
)

# Words that make a capitalized phrase a department, a place or a document, not a person.
_ORG_NAME_WORDS = frozenset(
    """
    clinic clinics clinique clínica clinica hospital hôpital hopital pharmacy farmacia pharmacie laboratory
    laboratorio equipo équipe oficina billing facturación facturacion recepción recepcion reception réception
    recursos coordinación coordinacion coordination department departamento services servicios fertility
    fertilidad fertilité results resultados retrieval ultrasound protocol transfer insemination egg ovarian
    équipe equipe zespół zespol
    recepcja rejestracja sekretariat pielęgniarki pielegniarki enfermería enfermeria admisiones admissions admission
    administración administracion administration accueil secrétariat secretariat secretaría secretaria nurses
    nursing scheduling intake קבלה מזכירות המזכירות הקבלה
    """.split()
)

# A job title or program word anywhere in a capitalized phrase: "Donor Program Coordinator",
# "Minnesota Medical Assistance".
_ORG_TAIL_WORDS = frozenset(
    """
    assistance medical program coordinator coordinators technician assistant asistente assistente manager
    director specialist representative supervisor analyst associate dept department services service
    benefit benefits
    """.split()
)

# Pet names that are also common words, still names after "call me".
_NICK_WORDS = frozenset({"baby", "babe", "junior"})
_FILE_EXT = r"(?:pdf|docx?|jpe?g|png|tiff?|txt|xlsx?|csv|heic|hl7|rtf)"
# Words that start a document file name without being a surname.
_FILE_WORDS = frozenset(
    """
    form forms report reports results result lab labs scan scans page pages consent intake referral invoice
    receipt statement summary letter note notes chart image images photo screenshot attachment scanned signed
    updated final draft copy new old bloodwork ultrasound insurance health card license licence passport medical
    ultrasound semen sperm embryo transfer requisition prescription order orders policy claim authorization
    protocol protocols doc docs document documents guide guides guideline guidelines instruction instructions part parts
    version versions rev revision annex annexe appendix form list lists panel panels questionnaire questionnaires
    collection analysis medication medications handout handouts sheet sheets template templates schedule calendar
    checklist brochure booklet manual faq agreement waiver release disclosure information info overview education
    patient stim stimulation spanish english french hebrew polish thyroid egg eggs freezing fertility pre post op
    letrozole clomid lupron gonal menopur progesterone estradiol cycle monitoring ivf iui icsi
    """.split()
)

def _org_like_tail(words: list[str]) -> bool:
    """A phrase ending in a department or program word: "Unity Benefit", "Prior Auth Dept", "Minnesota
    Medical Assistance". A longer phrase with a single tail word ("Priya Sharma Medical", the next
    field of a flattened form) is still a name, as the frozen detector had it."""
    tails = sum(w in _ORG_TAIL_WORDS for w in words)
    return tails >= 2 or (len(words) <= 2 and tails == 1 and words[-1] in _ORG_TAIL_WORDS) or words[-1] in {"dept", "department"}


_TAB_ROW_NEXT = re.compile(r"\n[ \t]*[^\t\n]*\d[^\t\n]*(?:\t[^\t\n]*\d[^\t\n]*)+[ \t]*(?:\n|$)")
_NAME_LIKE_STOP = frozenset({"will", "may", "ty", "said", "pat", "ma"})


def _first(m: re.Match[str]) -> str:
    # Skip initials: "N. Abdulkadir" -> "abdulkadir".
    for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", m.group("name")):
        if len(w) > 1:
            return w.lower()
    return ""


# A clinician's name: "Dr. A. Kaur", "RN T. Boateng", "Beth Alvarado, RN",
# "lek. Ewa Nowak", "Panie doktorze Okafor", "Surgeon Nwosu".
_TITLES = (
    r"dr|dre|dra|doctor|doctora|docteur|docteure|doktor|doktora|doktorze|doktorem|doktorowi|"
    r"doktorka|doktorki|lek|surgeon|nurse|midwife|rn|rpn|np|md|inf|enf"
)
_TITLE_BEFORE = re.compile(rf"(?i:\b(?:{_TITLES})\.?|ד[״\"']ר)\s*$")
_CREDENTIALS = r"RN|RPN|NP|MD|M\.D\.|PhD|DO|RM|LCSW|MSW|CGC|inf\.?"
_CREDENTIAL_AFTER = re.compile(rf"^,?[ \t]*(?:{_CREDENTIALS})(?![^\W\d_])")
_CREDENTIAL_END = re.compile(rf"(?:^|[\s,])(?:{_CREDENTIALS})$")
_TITLE_IN = re.compile(rf"(?:^|\s)(?i:(?:{_TITLES})\.?|ד[״\"']ר)\s")


def is_clinician(text: str, start: int, end: int) -> bool:
    """True when the name at text[start:end] carries a clinician title or credential."""
    span = text[start:end]
    return bool(
        _TITLE_BEFORE.search(text[max(0, start - 16) : start])
        or _TITLE_IN.search(span)
        or _CREDENTIAL_AFTER.match(text[end : end + 10])
        or _CREDENTIAL_END.search(span)
    )


_ARTICLES = frozenset({"el", "la", "los", "las", "un", "una", "le", "les", "the", "a", "an"})
# A pet word right before the name, with at most "name is" / "called" between: "the dog's name is
# Pierogi", "my cat Mimi". A pet word further back ("for my dog, I'm Sarah Lee") does not count.
_PET_BEFORE = re.compile(
    r"(?i:\b(?:dog|cat|puppy|kitten|pet|bird|rabbit|hamster|fish|horse|perro|perra|gato|gata|chien|chienne|pies|suczka|kot|"
    r"mascota|animal)['’]?s?[ \t]+(?:(?:name|nombre|nom|imi[ęe])[ \t]+)?"
    r"(?:(?:is|was|es|est|named|called|se[ \t]+llama|s['’]appelle|to)[ \t]+)?)$"
)
_LABEL_AFTER = re.compile(r"[ \t]*:(?:[ \t]|$)")
# Words that head a chat line as a speaker label ("Asistente: ..."); a first name before a colon is not one.
_SPEAKER_LABELS = frozenset(
    """
    assistant agent bot staff nurse doctor patient clinic support reception receptionist operator system user
    customer caller ai asistente paciente enfermera enfermero médico medico recepción recepcion agente
    asystent pacjent pacjentka lekarz pielęgniarka
    """.split()
)


_TITLE_FIRST = frozenset("dr doctor dre mr mrs ms mx miss prof professor nurse rn np pa md sr sra mme monsieur madame señor señora".split())
_PLURAL_NOT_FAMILY = frozenset(
    """hospitals doctors parents friends mothers fathers champions twins nurses patients girls boys kids
    children women men ladies guys beatles clinics staff students teachers neighbors neighbours donors
    carriers couples families brothers sisters sons daughters grandparents""".split()
)
_PLURAL_PREFIXES = frozenset("pre post co mid sun mount non anti semi inter intra sub".split())
_PLURAL_TAIL = re.compile(r"[ \t]+(?i:syndrome|disease|clinic|group|class|classes|support|program|team|center|centre)\b")
_COMPANY_TAIL = frozenset(
    """life cross shield insurance assurance health group bank inc llc ltd corp co company benefits plan
    healthcare financial mutual""".split()
)
_PAYER_CUE = re.compile(r"(?i)\b(?:billing|insurance|insurer|payer|claims?|coverage|benefits?|underwriting)\b")


def make_checks(not_names: frozenset[str] | set[str]):
    blocked = (set(not_names) | _NOT_NAME_EXTRA | STOP_WORDS) - _NAME_LIKE_STOP

    def _ok(m: re.Match[str], caps: bool, intro: bool = False) -> bool:
        name = m.group("name")
        first = _first(m)
        if not first:
            return False
        if first in _LATE_STOP and _late_stop_cued(m):
            pass  # "Mrs. Hard", "My last name is Hard": the cue outweighs the ordinary word
        elif first in blocked:
            # A newly blocked first word ("Se Park", "Hindi Patel") after a strong cue: drop only that word's
            # veto when a capitalized, unblocked surname follows, and mask the whole name.
            rest = [w for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", m.group("name"))]
            if first in _TITLE_FIRST or not ((caps or intro) and len(rest) > 1 and rest[1][0].isupper() and rest[1].lower() not in blocked):
                return False
        text, start, end = m.string, m.start("name"), m.end("name")
        words = [re.sub(r"^[ld]['’]", "", w.lower()).strip(".,'’") for w in name.split()]
        if words[0] in _ORG_NAME_WORDS or _org_like_tail(words):
            return False  # "Clínica Fertilidad", "Recursos Humanos", "Minnesota Medical Assistance"
        if "\t" in name and (start == 0 or text[start - 1] == "\n") and text[end : end + 1] == "\n" and _TAB_ROW_NEXT.match(text, end):
            # A table header line ("Straw<TAB>Cane<TAB>Tank") above a row whose every cell has a digit: column
            # titles. A person's name is never followed by a line of digit cells, so no patient row matches.
            return False
        if name in _ARTICLES:
            return False  # "soy el asistente": an article, not a name
        if _PET_BEFORE.search(text[max(0, start - 40) : start]):
            return False  # "the dog's name is Pierogi"
        if _LABEL_AFTER.match(text, end) and name.lower() in _SPEAKER_LABELS:
            return False  # "Asistente: ..." is a speaker label
        if name.islower() and " " not in name and re.search(r"(?:ego|(?:on|an|sk|ck|zn|ow|yn)ej)$", name) and len(name) > 6:
            return False  # Polish "ubezpieczonego" ("of the insured"), not a surname
        if _TITLE_BEFORE.search(text[max(0, start - 12) : start]):
            return False
        if _CREDENTIAL_AFTER.match(text[end : end + 10]) or _CREDENTIAL_END.search(name):
            return False
        if name.isupper() and "," not in name:
            # "ID", "IVF", "DONOR MATCH": all-caps words are labels, except
            # after a strong cue or a chart label ("PARTNER: TOMASZ KOWALCZYK").
            return caps and (len(name) > 4 or " " in name)
        return True

    def check(m: re.Match[str]) -> bool:
        return _ok(m, caps=False)

    def check_intro(m: re.Match[str]) -> bool:
        return _ok(m, caps=False, intro=True)

    def check_caps(m: re.Match[str]) -> bool:
        return _ok(m, caps=True)

    def check_initial(m: re.Match[str]) -> bool:
        words = m.group("name").split()
        return words[-1].lower().strip(".") not in _NOT_SURNAMES and check(m)

    def check_greeting_line(m: re.Match[str]) -> bool:
        first = m.group("name").split()[0].lower()
        if first in _NOT_ADDRESSEE or re.fullmatch(rf"(?i:{_VALEDICTION})", m.group("name")):
            return False
        return check(m)

    return check, check_caps, check_initial, check_greeting_line, check_intro


def rules(
    not_names: frozenset[str] | set[str],
) -> list[tuple[str, int, Optional[Callable[[re.Match[str]], bool]]]]:
    """(pattern, flags, check) for NAME. Each pattern has a ``name`` group."""
    check, check_caps, check_initial, check_greeting_line, check_intro = make_checks(not_names)
    start = r"(?:^|(?<=[\s,.!?:;\"'(—–\-]))"

    def check_nick(m: re.Match[str]) -> bool:
        # "everyone calls me Baby": a capitalized pet name is a name after a nickname cue.
        return m.group("name").lower() in _NICK_WORDS and m.group("name")[0].isupper() or check(m)

    def check_file(m: re.Match[str]) -> bool:
        # "Lopez_M_bloodwork.pdf": a surname and an initial, not "Lab_B_results.pdf".
        return m.group("name").split("_")[0].lower() not in _FILE_WORDS and check(m)

    def check_plural(m: re.Match[str]) -> bool:
        # "the Vang-Lees", "we're the Smiths": the family, with its plural s.
        name = m.group("name")
        base = re.sub(r"s$", "", name)
        if len(re.sub(r"[^\w]", "", base)) < 4 or name.lower() in _PLURAL_NOT_FAMILY:
            return False
        if "-" in name and name.split("-")[0].lower() in _PLURAL_PREFIXES:
            return False  # "the Pre-Ops", "the Co-Ops", "the Mid-Atlantics"
        if _PLURAL_TAIL.match(m.string, m.end()):
            return False  # "the Williams Syndrome clinic"
        return check(m)

    def check_contact(m: re.Match[str]) -> bool:
        # "Billing contact is Sun Life", "Insurance contact is Blue Cross": a payer, not a person.
        if m.group("name").split()[-1].lower().strip(".,") in _COMPANY_TAIL:
            return False
        if _PAYER_CUE.search(m.string[max(0, m.start() - 30) : m.start("name")]):
            return False
        return check(m)
    return [
        # "my name is chen wei", "je m'appelle Catherine", "קוראים לי ענת שפירא".
        (rf"(?i:\b(?:{_STRONG}))[ \t]*,?[ \t]*(?P<name>{ANY_NAME})", 0, check_caps),
        # "hi its jess", "caller: hi its bill", "hola, soy Paty", "היי זאת שירה".
        (rf"(?i:(?:\b|(?<=\s)|^)(?:{_GREETING}))(?:[\s,!.—\-]+(?i:{_FILLER}))*[\s,!.—\-]*(?i:(?:{_INTRO}))[ \t]+(?P<name>{ANY_NAME})", 0, check_intro),
        # Speaker line opening with an introduction: "caller: c'est mathieu".
        (rf"(?m:^)[ \t]*{_TS}{_SPEAKER}[ \t]*:(?:[ \t]*(?i:{_FILLER}|{_GREETING})[ \t,]*)*[ \t]*(?i:(?:{_INTRO}))[ \t]+(?P<name>{ANY_NAME})", 0, check),
        # "hi i'm marcus henry i can't...", "i'm beth": lowercase only when the clause ends there.
        (
            rf"(?i:(?:(?:{_GREETING})[\s,]+|(?m:^)[ \t]*{_TS}{_SPEAKER}[ \t]*:[ \t]*)(?:(?:{_FILLER})[\s,]+)*(?:i'?m|i’m|i\s+am))"
            rf"[ \t]+(?P<name>{_LWORD}(?:{_SP}{_LWORD})?)(?=[ \t]*(?:[,.!?\n]|$)|[ \t]+(?i:i|and|calling|from|here|again){_END})",
            0,
            check,
        ),
        # "le conjoint de sandrine côté", "el marido de patricia".
        (rf"(?i:\b(?:conjointe?|mari|femme|chum|blonde|marido|esposo|esposa|pareja)[ \t]+(?:de|del|d'))[ \t]*(?P<name>{LOWER_NAME})", 0, check),
        # An answer to a question about a name: "may i have your name\ncaller: leah cohen katz".
        (
            rf"(?i:\b(?:{_NAME_WORDS})\b)[^\n]{{0,60}}\n[ \t]*{_TS}{_SPEAKER}[ \t]*:[ \t]*"
            rf"(?:(?i:um|uh|yes|yeah|sure|ok|oui|s[íi]|tak|כן)[\s,]+)*(?P<name>{ANY_NAME})",
            0,
            check_caps,
        ),
        # "I'm Kim Park", "we're Hugo et Léa", "under William Tran", "c'est Mathieu".
        (rf"(?i:\b(?:{_WEAK}))[ \t]*,?[ \t]+(?P<name>{CAP_NAME})", 0, check_intro),
        # "Fatima here", "Hola Felipe aquí".
        (rf"{start}(?P<name>{NAME}){_SP}(?i:here|aqu[íi]|ici|tutaj){_END}(?=\s*(?:[,.!:;—\-]|$))", re.MULTILINE, check),
        # "Thanks so much,\nJess", "Los quiere, Ana y Beto", "Pozdrawiamy, Monika i Krzysztof".
        (rf"(?i:\b(?:{_VALEDICTION}))(?:[ \t]*,[ \t]*\n?|[ \t]*[,!.]?[ \t]*\n)[ \t]*(?P<name>{NAMES}|{LAST_FIRST})", 0, check),
        (rf"(?i:\b(?:{_VALEDICTION_SPACE}))[ \t]+(?P<name>{NAMES})", 0, check),
        (rf"(?<!\w)(?:{_HE_VALEDICTION})[ \t]*,?[ \t]*\n?[ \t]*(?P<name>{HE_NAME})(?=[ \t]*(?:[.,!?\n]|$))", 0, check),
        # "the Vang-Lees", "we are the Rivers-Castros" (hyphenated), "we're the Smiths".
        (rf"(?<![\w\-'’])[Tt]he[ \t]+(?P<name>[{_UP}][{_LO}'’]+-[{_UP}][{_LO}'’]*s){_END}", 0, check_plural),
        (rf"(?i:\b(?:we\s+are|we['’]re|this\s+is|it['’]s|from|with))[ \t]+the[ \t]+(?P<name>[{_UP}][{_LO}'’]{{3,}}s){_END}", 0, check_plural),
        # A person named in passing: "somebody at the insurer named Priscilla Dunmore",
        # "we named him Anders", "se llama Rosa".
        (
            rf"\b(?:(?:someone|somebody|person|woman|man|lady|gentleman|adjuster|"
            rf"baby|boy|girl|son|daughter|child|twins?|insurer|neighbou?r|friend|cousin)"
            rf"(?:[ \t]+(?:at|from|with)[ \t]+(?:the[ \t]+)?[\w']+)?[ \t]+named|"
            rf"(?:we|they|i|she|he)[ \t]+(?:named|call(?:ed)?)[ \t]+(?:him|her|them|the[ \t]+baby|our[ \t]+(?:son|daughter|baby|boy|girl)))"
            rf"[ \t]+(?P<name>{NAMES})",
            0,
            check,
        ),
        (rf"\b(?i:se\s+llam(?:a|aba|ar[áa])|s'appelle|nazywa\s+si[ęe])[ \t]+(?P<name>{NAMES})", 0, check),
        # Form fields for a nickname: "Nickname: Josie", "preferred: Yu".
        (rf"(?i:\b(?:nick\s*name|preferred(?:\s+(?:first\s+)?name)?|pref\.?\s*name|goes\s+by|alias|apodo|surnom|przydomek))[ \t]*[:=][ \t]*(?P<name>{NAMES})", 0, check),
        # A nickname told in passing: "(Concha para los amigos)", "(Bea for short)".
        (rf"\([ \t]*(?P<name>{_CW})[ \t]+(?i:para\s+los\s+amigos|for\s+short|to\s+(?:my\s+)?friends|pour\s+les\s+amis|dla\s+przyjaci[óo][łl])[ \t]*\)", 0, check),
        # Filipino terms for an older relative or friend: "Kuya Bong", "Tita Mel" (not "kuya Jun sa lab").
        (rf"(?<![\w])(?i:kuya|ate|tita|tito|lola|lolo|ninang|ninong|manang|manong)[ \t]+(?P<name>{_CW})(?![ \t]+(?i:sa|at|from)[ \t]+(?i:lab|clinic|office|hospital|front))", 0, check),
        # A team hashtag: "#TeamOkonkwo".
        (rf"(?<![\w#])#Team(?P<name>{_CW})", 0, check),
        # A surname and an initial in a file name: "Lopez_M_bloodwork_2026-03-14.pdf", "USG_Sobczak_A.pdf".
        (
            rf"(?<![A-Za-z0-9])(?P<name>[{_UP}][{_LO}'’]{{2,}}(?:-[{_UP}][{_LO}]+)?_[{_UP}])(?![A-Za-z0-9])(?=[^\s]{{0,60}}?\.{_FILE_EXT}\b)",
            0,
            check_file,
        ),
        # Nicknames and preferred names: "I go by Kim", "prefers to be called Mimi", "se hace llamar Paty".
        (
            rf"(?i:\b(?:(?:i|she|he|they|we|who|also|usually|now|mostly|patient|partner)\s+(?:go(?:es)?|went)\s+by|"
            rf"prefer(?:s|red)?\s+(?:to\s+be\s+|being\s+)?called|preferred\s+name(?:\s+is)?|(?:likes?|wants?)\s+to\s+be\s+called|"
            rf"(?:i['’]?m|i\s+am|she['’]?s|he['’]?s|she\s+is|he\s+is)\s+(?:called|known\s+as)|a\.?k\.?a\.?|"
            rf"(?:je\s+me|elle\s+se|il\s+se)\s+fai[ts]\s+appeler|m['’]appellent|m['’]appelle|ll[áa]mame|m[óo]w\s+do\s+mnie|"
            rf"nazywaj[ąa]\s+mnie|tinatawag\s+(?:akong|nila\s+akong)|tawag\s+(?:nila\s+)?sa\s+akin|"
            rf"(?:you\s+can\s+|please\s+|just\s+|everyone\s+|they\s+)?call(?:s)?\s+me|nickname\s+is|se\s+hace\s+llamar|me\s+dicen|"
            rf"me\s+llaman|mi\s+apodo\s+es|on\s+m['’]appelle|appelez[\s\-]moi|m[óo]w\s+mi|m[óo]wi[ąa]\s+na\s+(?:mnie|ni[ąa]|niego)|"
            rf"wo[łl]aj[ąa]\s+na\s+(?:mnie|ni[ąa]|niego)))"
            rf"[ \t]*:?[ \t]+[\"“'‘]?(?P<name>{NAMES})",
            0,
            check_nick,
        ),
        # An email that opens with the addressee's name alone: "\n\nHollis,\n\nThank you".
        (
            rf"(?:(?im:^(?:subject|objet|asunto|temat|to|from|re|cc)[ \t]*:[^\n]*)\r?\n[ \t]*\r?\n(?P<h>)|\A)[ \t]*"
            rf"(?P<name>{_CW}(?:{_SP}{_CW}){{0,2}})[ \t]*[,!][ \t]*\r?\n(?:(?(h)|(?!))(?:[ \t]*\r?\n)?|[ \t]*\r?\n)[ \t]*"
            rf"(?=(?i:thank|thanks|i\s|i['’]|hope|please|just|following|as\s|we\s|we['’]|attached|quick|can\s|could\s|"
            rf"here|regarding|re:|let\s|good|it\s+was|sorry|per\s|hi\b|hello|gracias|muchas|buen[oa]s|hola|espero|le\s+escribo|"
            rf"te\s+escribo|adjunto|merci|bonjour|bonsoir|je\s|j['’]|nous\s|voici|dzi[ęe]kuj|bardzo|dzie[ńn]\s+dobry|"
            rf"piszę|przesyłam|w\s+za[łl][ąa]czniku))",
            0,
            check_greeting_line,
        ),
        # "Lee and I are so grateful", "Marta y yo", "Ania i ja".
        (
            rf"(?:^|(?<=[.!?][ \t])|(?<=[.!?][ \t]{{2}}))(?:(?i:today|yesterday|tonight|so|then|when|now|maybe|and|but|"
            rf"also|hopefully|finally|last\s+(?:night|week)|this\s+morning|hoy|ayer|aujourd['’]hui|hier|dzi[śs]|wczoraj)[ \t,]+)?"
            rf"(?P<name>{NAMES})[ \t]+(?:(?:and|&)[ \t]+I|y[ \t]+yo|et[ \t]+moi|i[ \t]+ja){_END}"
            rf"(?=[ \t]+(?i:are|were|have|had|will|went|would|both|just|also|did|do|can|could|got|met|live|lived|moved|"
            rf"decided|want|wanted|need|needed|tried|plan|planned|hope|look|thank|appreciate|really|still|already|"
            rf"estamos|fuimos|tenemos|queremos|sommes|avons|allons|voulons|jeste[śs]my|mamy|chcemy|byli[śs]my)\b|['’](?:re|ve|ll|d)\b)",
            re.MULTILINE,
            check_greeting_line,
        ),
        # Dash sign-off at the end: "- Raj", "— N. Abdulkadir", "xo - Gabi".
        (rf"(?:^|\s)[-–—~]+\s*(?P<name>{NAMES})\s*[.!]?\s*\Z", 0, check),
        # A name with its role in brackets: "Tessa Marie Holloway (the Donor)", "Raymond and Clara Oyelaran (the Intended Parents)".
        (
            rf"(?P<name>{NAMES})[ \t]+\((?i:the[ \t]+)?(?i:donor|intended[ \t]+parents?|patient|surrogate|gestational[ \t]+carrier|carrier|"
            rf"recipient|applicant|client|spouse|partner|husband|wife|mother|father|sister|brother|cousin|guarantor|subscriber|insured)\)",
            0,
            check,
        ),
        # A name alone before a relation in brackets: "\n\nAoife Kearney\n(sister)".
        (rf"(?:\n[ \t]*\n|(?m:^)--[ \t]*\n)[ \t]*(?P<name>{NAMES})[ \t]*\n[ \t]*\([^)\n]{{2,30}}\)[ \t]*(?:\n|\Z)", 0, check),
        # A contact at another organisation: "HR contact there is Bev Tolliver", "my manager is Karen Lee".
        (
            rf"\b(?i:contact|supervisor|manager|boss|lawyer|attorney|counsel)(?:[ \t]+(?i:there|here|at[ \t]+[\w']+))?[ \t]+(?i:is|was)[ \t]+"
            rf"(?P<name>{_MULTI_NAME})",
            0,
            check_contact,
        ),
        # A relative or contact: "Husband Imran", "Partner: Kevin Nguyen",
        # "surrogate is Tiffany Rhodes", "mi esposo Jorge", "Mój mąż Piotr".
        (
            rf"(?i:\b(?:{_RELATIONS})(?:'s)?(?:[ \t]*\([IVX]{{1,4}}[-–]\d{{1,2}}\))?(?:[ \t]+(?:name[ \t]+is|is|are|est|sont|es|son|jest|to|de|del|d'|of))?)[ \t]*[:,]?[ \t]*"
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
        # "בעלי גיל", also with a one-letter prefix: "לבעלי גיל", "ואחותי מיכל".
        (rf"(?<!\w)[ולבשמ]?(?:{_HE_RELATIONS})[ \t]+(?P<name>{HE_NAME})", 0, check),
        # A lawyer is a private person: "עו״ד אורית בן חיים".
        (rf"(?<!\w)[ולבשמ]?עו[\"״']ד[ \t]+(?P<name>{HE_NAME})", 0, check),
        # Chart labels: "Patient: Kimberly D.", "PATIENT: PARK, Soo-jin", "Pacjent: Wiśniewski, Aleksander".
        (rf"(?i:\b(?:{_LABELS}))[ \t]*:[ \t]*(?P<name>{LAST_FIRST}|{NAMES})", 0, check_caps),
        # Speaker-like labels ("Patient:", "PACJENT:") start transcript lines too, so a
        # single capitalized word there is usually the first word of a sentence.
        (rf"(?i:\b(?:{_PERSON_LABELS}))[ \t]*:[ \t]*(?P<name>{LAST_FIRST}|{_MULTI_NAME})", 0, check_caps),
        (rf"(?<!\w)(?:{_HE_LABELS})[ \t]*:[ \t]*(?P<name>{HE_LAST_FIRST}|{HE_NAME})", 0, check),
        # Greetings and patient cues: "Hi, Anna Kowalski", "Pt P. Raman", "Dear Ms Lee".
        (rf"(?i:\b(?:pt|client|dear|hi|hello|hey|bonjour|hola|cze[śs][ćc]|witam|witaj))[ \t]*,?[ \t]+(?P<name>{NAMES})", 0, check),
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
            rf"(?=\s*\Z|[ \t]+[-–—|][ \t]*\S|\n[ \t]*(?:(?i:tel|t[ée]l|phone|ph|cell|mobile|m[óo]vil|kom)\.?:?[ \t]*)?(?:\(?\+?\d[\d \t().\-]{{6,}}|\S+@\S+|Sent\s+from|Envoy[ée]|Enviado|>)|\n\s*\n[ \t]*(?:On|Le|El|W\s+dniu)\s.{{5,80}}(?:wrote|[ée]crit|escribi|napisa))",
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


_MISS_VERB_BEFORE = re.compile(
    r"(?i:\b(?:i|we|you|they|to|will|would|can|can['’]?t|don['’]?t|didn['’]?t|did|do|might|not|always|really|still|also|just|never|"
    r"so|much|please|and|ll|'ll|’ll|'d|’d|may|could|should|shall|must|he|she)[ \t]+)$"
)


# After "to/and/so much/please" the word "miss" is a title when a surname-like word follows; the verb
# reading wins only when what follows is clearly not a name.
_MISS_AMBIG_BEFORE = re.compile(r"(?i:\b(?:to|and|so|much|please)[ \t]+)$")
_MISS_NOT_NAME_AFTER = frozenset(
    """the my your his her our their its a an it you him them us me this that these those out on in at for with from
    work school class classes appointment appointments period periods dose doses shot shots call calls any some more
    all one another each every home flight bus train meeting meetings visit visits deadline days time
    text texts message messages email it's no not too so very much many anything something everything someone
    again about because but if when while as of off up weeks months years hours minutes nights""".split()
)


def courtesy_rules(
    not_names: frozenset[str] | set[str],
) -> list[tuple[str, int, Optional[Callable[[re.Match[str]], bool]]]]:
    """Courtesy titles name patients and relatives, not clinicians."""
    check, *_ = make_checks(not_names)

    def check_miss(m: re.Match[str]) -> bool:
        # "I miss texts", "we'll miss you": the verb, not the title.
        if m.group(0).lower().startswith("miss"):
            before = m.string[max(0, m.start() - 14) : m.start()]
            # Even after a verb cue ("did not miss garcia") a surname-like word is kept masked; the
            # verb reading wins only when what follows is clearly not a name.
            if _MISS_VERB_BEFORE.search(before) and m.group("name").lower() in _MISS_NOT_NAME_AFTER:
                return False
        return check(m)

    # Courtesy titles and military ranks (a service member is a private person).
    titles = (
        r"Mr|Mrs|Ms|Miss|Mx|Mme|Mlle|Me|Sr|Sra|Srta|Pan|Pani|Panią|Panu|[Ss]e[ñn]or(?:a|ita)?|[Dd]o[ñn]a|Madame|Monsieur|"
        # "Col." is a Mexican neighbourhood (colonia) and "Cabo" a place, so they are left out;
        # "Cap." and "Maj." need their dot.
        r"Capt|Cap(?=\.)|Sgt|SSgt|SFC|Lt|LTC|Cpl|CPL|Maj(?=\.)|Pvt|PFC|Spc|SPC|Sgto|Teniente|Sargento|Capit[aá]n"
    )
    return [
        # "Señora Doctora Lee", "Madame la Docteure Roy": a clinician, not a courtesy-titled patient.
        (rf"\b(?:{titles})\.?\s+(?!(?i:doctora?|docteure?|doktor|dra?\.?|dre?\.?|la\s+docteure?|lekarz)\b)(?P<name>{NAME})", 0, check),
        # Transcripts: "a mrs ostrowski".
        (rf"\b(?:mr|mrs|ms|miss)\.?\s+(?P<name>{_LWORD_TITLED})", 0, check_miss),
    ]


# Spelled-out words ("k o w a l c z y k", "S-Z-C-Z-E-P-A-Ń-S-K-A", "ג-ו-ל-ד-ב-ר-ג").
SPELLED = (
    # "K as in kilo O W A L C H U K", "H A, N G U Y E N"
    # The key word may be capitalised ("F as in Foxtrot") or French ("c comme Charles").
    rf"(?<![\w\-'’])[A-Za-z{_UP}{_LO}](?:[^\S\n]+(?:as[^\S\n]+in|comme|como|for|de)[^\S\n]+[A-Za-z{_UP}{_LO}]+)?"
    rf"(?:(?:[^\S\n]+|-|,[^\S\n]*(?![yY][^\S\n]+[^\W\d_]{{2}}))(?:hyphen[^\S\n]+|dash[^\S\n]+)?[A-Za-z{_UP}{_LO}](?:[^\S\n]+(?:as[^\S\n]+in|comme|como|for|de)[^\S\n]+[A-Za-z{_UP}{_LO}]+)?){{3,}}(?<!,[A-Za-z{_UP}{_LO}][^\S\n][yY])(?<!,[^\S\n][A-Za-z{_UP}{_LO}][^\S\n][yY])(?![\w\-])|"
    rf"(?<![\w\-])[{_HE}](?:-[{_HE}]){{3,}}(?![\w\-])|"
    rf"(?<![\w\-])[{_HE}](?:[ ][{_HE}]){{3,}}(?![\w\-])"
)


# Hebrew first names from the cross-script table, plus short ones that are also
# words ("טל" dew, "גל" wave, "אור" light, "אלון" oak, "שי" gift): a bare Hebrew
# word is too ambiguous, so these count only where the context says "person".
_HE_FIRST_NAMES = sorted(
    {h for h in _hebrew.HEBREW_TO_LATIN if " " not in h and "-" not in h} | {"טל", "גל", "אור", "אלון", "שי", "ליה", "מור"},
    key=len,
    reverse=True,
)
_HF = "(?:" + "|".join(_HE_FIRST_NAMES) + ")"
# An optional surname after a first name, only when the name group ends there.
_HSUR = rf"(?:[ \t](?!ו){_HWORD}(?=[ \t]*(?:[,.;:!?()\n]|$|[ \t]ו)))?"
_HE_PAIR = re.compile(
    rf"(?<![{_HE}])(?P<a>{_HF}{_HSUR})[ \t]+ו(?P<b>{_HF}{_HSUR})(?![{_HE}])", re.MULTILINE
)
_HE_ME_AND = re.compile(rf"(?<![{_HE}])אני[ \t]+ו(?P<b>{_HF}{_HSUR})(?![{_HE}])", re.MULTILINE)
_HE_SIGNOFF = re.compile(
    rf"\n[ \t]*\n[ \t]*(?P<a>{_HF}{_HSUR})(?:[ \t]+ו(?P<b>{_HF}{_HSUR}))?[ \t]*\Z"
)


_HE_WORDLIKE = {"טל", "גל", "אור", "אלון", "שי", "מור", "שירה", "תמר", "גיל", "עדי", "רינה", "קרן", "דוד", "אבי"}
_HE_DOCTOR_BEFORE = re.compile(r"(?:ד[״\"'׳]ר|פרופ['׳]?|דוקטור)[ \t]*$")
_HE_WE = re.compile(r"(?:אנחנו|אני|עם|של|מאת|בברכה|תודה|בשם)[ \t,]*$")


def hebrew_names(text: str) -> list[tuple[int, int]]:
    """Hebrew first names where the context says they are people: "שירה ואיתי",
    "אני ועומר", "רוני וגיל קורן", a name alone on the last line."""
    if not re.search(rf"[{_HE}]", text):
        return []
    out = []
    for pat in (_HE_PAIR, _HE_ME_AND, _HE_SIGNOFF):
        for m in pat.finditer(text):
            if pat is _HE_PAIR:
                if _HE_DOCTOR_BEFORE.search(text[max(0, m.start() - 8) : m.start()]):
                    continue  # "ד״ר נועה פרידמן ויעל מזרחי": clinicians
                firsts = [m.group(g).split()[0] for g in ("a", "b")]
                # "קיבלתי טל ואור" is dew and light; "אנחנו טל ואלון" are people.
                if all(f in _HE_WORDLIKE for f in firsts) and not _HE_WE.search(text[max(0, m.start() - 12) : m.start()]):
                    continue
            for g in ("a", "b"):
                if g in pat.groupindex and m.group(g):
                    out.append(m.span(g))
    return out


# Abbreviations a clinic writes in capitals: never a patient's initials.
CLINICAL_ABBREVIATIONS = frozenset(
    """
    FET IVF ICSI IUI IUD ET ER OHSS HSG AMH PGT PGTA PGTM PGTSR LMP US UK EU UAE USA OB OBGYN GYN RN NP MD DO PA PT OT
    MA CNA LPN RM DOB MRN HCG BHCG E2 P4 LH FSH TSH DHEA BMI BP HR IM IV SC PO PRN BID TID QD QID HX DX TX RX FU PCP GP
    ED OR PACU NPO NICU AM PM TV TVUS NST CBC CT MRI IVM OI STI HIV HPV UTI PCOS AFC FMLA ID OHIP RAMQ SMS PHI DM HTN
    FIV PMA AMP DPI TEC IIU IAC DPN RE FW FWD AW TR RV ASAP FYI TBD NA NB PS CC BCC OK IT HR AI AIH COVID PRP ERA NIPT PGS DNA RNA ICU OTC FDA CVS
    CMV PCR DVT GBS BV SA AFP HCV HBV VTE ASA IBS BRCA CF SMA MTHFR APS NK MFI TTC DOR POI TESE MESA PESA ART SET DET ASRM CDC WHO NHS USG EKG ECG ENT PCO STD OHS EMR EHR IMG
    TB PGD PRL HSV POF TVS OCP SIS SHG PIO QHS STAT ETA ACK
    HRT LOR TESA IMSI PICSI EMMA ALICE LPD LUF POR BFP BFN DPO
    MII OPU ICM LPS NGS AZF DFI TNF APA PAI SIN SSN NAS
    LDN VTO AUB PPI MTX SOB LBP DUB IBD BCP PMS PMH HPI EPT TFMR ZIFT GIFT OCD LAH HTN PTSD GAD MDD ADHD
    IMC DDR FUM CCA ATCD SOPK FCS GEU IVG IMG HTA RCIU TRA RHA OMS
    FAI HLA PTO DPT YOB LOS
    VMX NSR NKA IGF CCT COC REI DOS DOT EOB EOP PMD LOA WFL ROM ROS PSH EDC PIH AFI BPP FHT LIS MSP TRT SSG PET CVA TIA HLD CAD PAD BPD OSA WHR LDH ALT AST ALP GGT BUN
    WNL TBA NAD LDL HDL SLE CKD COS SAB POC DNR AMA LWBS BMP CMP UPT HPT TAB EAB DNC LLQ RLQ RUQ LUQ MFM SCH IUP TWW LBR
    EF LV LVEF EDD CRL FHR RPL RIF COPD CHF AFIB EEG EMG CXR LFT LFTS CRP ESR INR PTT HGB WBC RBC GFR EGFR A1C HBA1C OGTT GTT GDM SVT TSI TPO SHBG PSA CA125 OPK BBT FT3 FT4 T3 T4 DHT
    """.split()
)
# Two-letter clinic abbreviations that are also common initials ("DE" donor egg, "DI" donor insemination,
# "CD" cycle day): not initials only when a clinical noun follows ("patient DE cycle"); otherwise masked.
AMBIGUOUS_ABBREVIATIONS = frozenset("DE DI DC CD TI FP LP GS YS HA HH AF NT BT TE PN GV MI ANA PE NO UA AH PB SM CP RF GI MC MS UC RA SO VM LM NS ZP SQ PR PV FH SH FM DS GC SI YI NG GA TA NR".split())
# Embryology / ultrasound / lab abbreviations that are also initials: a clinical number or noun must follow.
_AMBIG_COUNT_NEXT = frozenset("AF NT BT TE PN GV MI".split())
_AMBIG_NEW = _AMBIG_COUNT_NEXT | {"ANA", "PE", "NO", "UA", "AH", "PB", "SM", "GS"}
_AMBIG_CLINICAL_NEXT = re.compile(
    r"[ \t]+(?i:cycles?|transfers?|retrievals?|donors?|eggs?|embryos?|sperm|insemination|protocol|iui|ivf|fet|icsi|day|scan|labs?|"
    r"flares?|relapse|diagnosis|dx|history|hx|meds?|medications?|treatment|on[ \t]+\w+(?:ate|ine|ide|one|mab|cin)|with[ \t]+[A-Z]{2,}|"
    r"grade|bleeding|full|results?|thickness|level|levels|count|score|normal|abnormal|positive|negative|pos|neg|scheduled|"
    r"at[ \t]+\d+|\d+(?:[.,]\d+)?(?:[ \t]*(?:mm|cm|ml|%|weeks?|wks?|w|d|days?|u/l|iu))?)(?![\w])|[ \t]*[+\-](?![\w])"
)
_AMBIG_CLINICAL_NEXT_EXTRA = re.compile(
    r"[ \t]+(?i:oocytes?|follicles?|count|measurements?|translucency|screen(?:ing)?|biops(?:y|ies)|blastocysts?|titers?|panel|tests?|results?|positive|negative|show|shows|seen|pain|referral|normal|exam|bleeding|stable|culture|cultures|sac|dip|biopsy)\b"
)
_AMBIG_NUM_NEXT = re.compile(r"[ \t]+\d")
# US state and Canadian province codes: not initials after "re:" ("Re: NY trip"); after "pt"/"patient" they stay.
PLACE_CODES = frozenset(
    """AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI
    SC SD TN TX UT VT VA WA WV WI WY DC AB BC MB NB NL NS NT NU ON PE QC PQ SK YT""".split()
)
_ABBR_ALT = "|".join(sorted(CLINICAL_ABBREVIATIONS, key=len, reverse=True))
_NOT_ABBR = rf"(?!(?:{_ABBR_ALT})(?![\w]))"
_INITIALS_TAIL = r"(?![\w\-])(?!['’](?!s\b))(?!\.[A-Za-z0-9])"
# Patient cues for initials: "pt KJ", "patient: A.B.", "re: AB", "Mrs. O".
_PT_CUE = (
    r"(?i:\b(?:pts?|patient|patiente|paciente|pacjent(?:ka|ki|a|owi)?|inicja[łl]y(?:[ \t]+pacjent(?:ka|ki|a))?|re|mrs?|ms|miss|mme|mlle|sra|srta|pani)(?![\w]))"
)
_TITLE_CUE = r"(?i:\b(?:mr|mrs|ms|miss|mx|mme|mlle|sra|srta|sr|pani|pan)\b)"
# Clinical nouns that take a patient: "AB's FET", "FET de AB", "AMH de HG".
_CLIN_NOUN = (
    rf"{_ABBR_ALT}|cycle|retrieval|transfer|consent|labs?|results?|beta|chart|appt|appointment|file|embryos?|scan|"
    rf"ultrasound|bloodwork|protocol|lining|trigger|stims?|ciclo|punci[óo]n|transferencia|endometrio|ecograf[íi]a|"
    rf"protocolo|caso|resultados|an[áa]lisis|dossier|r[ée]sultats|dossier|wyniki|cykl"
)
_HANGUL = "\uac00-\ud7a3"
_KO_CUE = (
    r"(?i:\b(?:emergency\s+contact|contact|name|spouse|husband|wife|partner|mother|father|guardian|"
    r"next\s+of\s+kin|caregiver|interpreter|parent)\b)|이름|성함|남편|아내|배우자|보호자|어머니|아버지|연락처"
)


_KO_NOT_NAMES = frozenset(
    "생년월일 전화번호 주소 이메일 이름 성함 환자 보호자 연락처 병원 의사 간호사 예약 남편 아내 배우자 어머니 아버지 비밀번호 번호".split()
)


def _initials_ok(letters: str) -> bool:
    return letters.replace(".", "") not in CLINICAL_ABBREVIATIONS


def initial_rules(
    not_names: frozenset[str] | set[str],
) -> list[tuple[str, int, Optional[Callable[[re.Match[str]], bool]]]]:
    """NAME rules for a patient written by initials or a bare name, each gated by a cue.

    A patient is often "pt KJ", "re: AB's FET", "Mrs. O" or "M.R. G3P0" in a clinic's own notes. Capital
    letters alone are never a name: a clinical abbreviation ("FET", "OHSS", "ER") is skipped, and the
    masker leaves the initials of the clinic's staff alone."""
    check, *_ = make_checks(not_names)

    def check_initials(m: re.Match[str]) -> bool:
        if m.group("name") in PLACE_CODES and re.match(r"(?i:re)(?![\w])", m.string[m.start() : m.start("name")]):
            return False
        n = m.group("name")
        if n in AMBIGUOUS_ABBREVIATIONS and (
            _AMBIG_CLINICAL_NEXT.match(m.string, m.end("name"))
            or (n in _AMBIG_NEW and _AMBIG_CLINICAL_NEXT_EXTRA.match(m.string, m.end("name")))
            or (n in _AMBIG_COUNT_NEXT and _AMBIG_NUM_NEXT.match(m.string, m.end("name")))
        ):
            return False
        return _initials_ok(m.group("name"))

    def check_baby(m: re.Match[str]) -> bool:
        n = m.group("name")
        last = n.split()[-1]
        return last[-1] == "." or last.lower() not in (set(not_names) | _NOT_NAME_EXTRA | STOP_WORDS)

    def check_file_name(m: re.Match[str]) -> bool:
        return m.group("name").split(",")[0].lower() not in _FILE_WORDS and check(m)

    def check_korean(m: re.Match[str]) -> bool:
        # Not a form label or a verb/adjective ("생년월일", "전화번호", "좋아요").
        n = m.group("name")
        return n not in _KO_NOT_NAMES and n[-1] not in "요다까죠네요함됨"

    def check_caller(m: re.Match[str]) -> bool:
        # "Caller: Ibrahim Yousef, husband of the patient": a summary line, not "Caller: Thank you, ...".
        return check(m) and not m.group("name").isupper()

    return [
        # "pt KJ", "patient: AB", "re: AB's FET", "Pt A.B.", "Mrs. O.R." (2-3 capitals, or dotted initials).
        (
            rf"{_PT_CUE}(?i:(?:['’]s)?[ \t]+initials?(?:[ \t]+(?:are|is))?)?[ \t]*[:.]?[ \t]*{_NOT_ABBR}(?P<name>[A-Z]{{2,3}}|[A-Z](?:\.[A-Z]){{1,2}}\.?|[A-Z]\.(?:[ \t][A-Z]\.){{1,2}}|[A-Z]\.){_INITIALS_TAIL}",
            0,
            check_initials,
        ),
        # Dotted initials after a patient word, with the surname that follows: "patient J.R. Smith called",
        # "patient A. B. C." (two or three initials; one initial and a surname is handled elsewhere).
        (
            rf"(?i:\b(?:pts?|patient|paciente|patiente)(?:['’]s)?)[ \t]*:?[ \t]*{_NOT_ABBR}"
            rf"(?P<name>[A-Z]\.(?:[ \t]?[A-Z]\.){{1,2}}(?:[ \t]+[A-Z][a-z]+(?:['’\-][A-Z]?[a-z]+)?)?)(?![\w\-])",
            0,
            lambda m: check_baby(m) and _initials_ok(m.group("name").split()[0]),
        ),
        # Spaced initials after "pt" or "patient": "Pt: J T", "patient initials J T" (two or three single capitals).
        (
            rf"(?i:\b(?:pts?|patient)(?:['’]s)?(?:[ \t]+initials?)?)[ \t]*:?[ \t]*(?P<name>[A-Z](?:[ \t][A-Z]){{1,2}}){_INITIALS_TAIL}",
            0,
            lambda m: _initials_ok(re.sub(r"\s", "", m.group("name"))) and m.group("name").replace(" ", "") not in PLACE_CODES,
        ),
        # Hebrew initials after the patient word: "הפציינטית: ג.ט.", "המטופלת: ג״ט".
        (
            r"(?<![א-ת])[ובלמהש]{0,2}(?:פציינט(?:ית)?|מטופל(?:ת)?)[ \t]*[:\-]?[ \t]*(?P<name>[א-ת](?:\.[ \t]?[א-ת]){1,2}\.?|[א-ת][\"״׳'][א-ת])(?![א-ת\w])",
            0,
            lambda m: re.sub(r"[\"״׳'.]", "", m.group("name")) not in {"דר", "מר", "גב", "גבר", "עו"},
        ),
        # A courtesy title and one letter: "Mrs. O in rm 5", "Sra. A llamó".
        # The title must not be all capitals ("MS" is multiple sclerosis or a degree), and "I" or "A" starting
        # a sentence is the pronoun ("I have MS. I am tired").
        (rf"(?<![A-Z]){_TITLE_CUE}(?<![A-Z]{{2}})\.?[ \t]+(?P<name>[A-Z]\.?)(?![\w'’\-])(?<!\bI)", 0, None),
        # The possessive of initials before a clinical noun: "AB's FET", "KJ's labs".
        (rf"(?<![\w'’\-.]){_NOT_ABBR}(?P<name>[A-Z]{{2,3}})(?=['’]s[ \t]+(?i:{_CLIN_NOUN})\b){_INITIALS_TAIL}", 0, check_initials),
        # "FET de AB", "AMH de HG", "endometrio de AB": initials after a clinical noun and "of".
        (
            rf"(?i:\b(?:{_CLIN_NOUN})[ \t]+(?:de|del|d['’]|du|dla)[ \t]+(?:la[ \t]+)?){_NOT_ABBR}(?P<name>[A-Z]{{2,3}}){_INITIALS_TAIL}",
            0,
            check_initials,
        ),
        # A note line that opens with dotted initials and a chart detail: "M.R. G3P0 - ecografía", "M.O. (2nd call) - ...".
        (
            rf"(?<![\w.])(?P<name>[A-Z]\.[A-Z]\.(?:[A-Z]\.)?)(?=[ \t]+(?:\(|[-–—](?:[ \t]|$)|G\d+[ \t]?P\d+|\d{{2}}[ \t]?(?i:y/?o|a|ans|l\.?)\b|c/o\b|rm\b|room\b|hab\b))",
            0,
            check_initials,
        ),
        # A relative given by an initial: "Esposo J. contesta", "husband R.".
        (rf"(?i:\b(?:{_LOWER_RELATIONS}))[ \t]+(?P<name>[A-Z]\.)(?=[ \t]+[a-z]|[ \t]*[,;:]|\s*$)", 0, None),
        # A baby named for the adoption or birth record: "Baby Girl M.", "Baby Boy Okafor".
        (rf"(?P<name>(?i:\bbaby[ \t]+(?:girl|boy))[ \t]+(?:[A-Z]\.|{_CW}))", 0, check_baby),
        # A parent or guardian of a named child: "foster parents to Kiara, who is nine".
        (
            rf"(?i:\b(?:parents?|guardians?|mother|father|mom|dad|caregivers?|carers?|grandparents?|grandmother|grandfather)[ \t]+(?:to|of))[ \t]+"
            rf"(?P<name>{_CW})(?=[ \t]*[,.;)]|[ \t]+(?i:who|is|was|has|had|and|age[d]?)\b)",
            0,
            check,
        ),
        # A nickname told in passing: "elle a Espé comme surnom", "con Pepa como apodo".
        (
            rf"(?<![\w'’\-])(?P<name>{_CW})[ \t]+(?i:comme[ \t]+(?:surnom|petit[ \t]+nom)|como[ \t]+apodo|jako[ \t]+(?:przydomek|przezwisko)|as[ \t]+(?:a[ \t]+|her[ \t]+|his[ \t]+)?nick\s*name)\b",
            0,
            check,
        ),
        # "Last, First" in a file name: "Scan - Okafor, Ngozi.pdf".
        (rf"(?<![\w,])(?P<name>{_CW},[ \t]?{_CW})(?=\.{_FILE_EXT}\b)", 0, check_file_name),
        # A caller named on a summary line: "Caller: Ibrahim Yousef, husband of ...".
        (
            rf"(?m:^)[ \t]*(?i:caller|called[ \t]+by|appelant|llamante)(?:[ \t]+name)?[ \t]*:[ \t]*(?P<name>{_MULTI_NAME})(?=[ \t]*(?:,|\(|[-–—]|\n|$))",
            0,
            check_caller,
        ),
        # A Korean name with its romanization: "정민아 (Mina Jung)".
        (rf"(?<![{_HANGUL}])(?P<name>[{_HANGUL}]{{2,4}})(?=[ \t]*\([ \t]*{_CW}(?:[ \t]+{_CW}){{1,2}}[ \t]*\))", 0, check_korean),
        # A Korean name after a cue: "Emergency contact: 정현수 470-555-0112", "환자: 김영희".
        (
            rf"(?:{_KO_CUE})[ \t]*[:：]?[ \t]*(?P<name>[{_HANGUL}]{{2,4}}?)(?=(?:님|씨|은|는|이|가|을|를|의|도|입니다|이에요|예요)?(?![{_HANGUL}]))",
            0,
            check_korean,
        ),
    ]


# Spanish names for letters that are not themselves a letter: "p, e, eñe, a".
SPELLED_ES = (
    r"(?<![\w\-'’])[A-Za-z](?:,[^\S\n]*(?:(?![yY][^\S\n]+[^\W\d_])[A-Za-z]|e[ñn]e|ene|ese|erre|ele|eme|equis|hache|jota|zeta|uve|doble[^\S\n]+ve|i[^\S\n]+griega)(?![\w])){3,}(?![\w\-])"
)


# Letters of a name read out by the names of the letters in Spanish and French ("ve i ele a ele o ve o ese",
# "ele e effe ère a ène cé o i esse"), separated by spaces. Several words are also ordinary words ("de", "te",
# "ve", "ce", "ese"), so the run must have at least five words, three of them letter names of two or more
# letters, and a spelling or "it is" cue right before it.
_LN_STRONG = (
    r"doble[ \t]+ve|double[ \t]+v[ée]|i[ \t]+gri(?:ega|ec)|"
    r"effe|efe|elle|ele|emme|eme|enne|ène|ene|e[ñn]e|erre|ère|ere|esse|ese|equis|iks|hache|ache|jota|ji|ka|"
    r"zeta|z[èe]de|uve|be|b[ée]|ce|c[ée]|de|d[ée]|ge|g[ée]|pe|p[ée]|te|t[ée]|ve|v[ée]|cu|qu"
)
SPELLED_LETTER_NAMES = (
    rf"(?<![\w\-'’])(?:(?:{_LN_STRONG})|[aeiouy])(?:[ \t]+(?:(?:{_LN_STRONG})|[aeiouy])){{4,19}}(?![\w\-'’])"
)
_LN_CUE_BEFORE = re.compile(
    r"(?i:(?:s['’][ée]crit|se[ \t]+escribe|\bes|\best|\bis|it['’]?s|c['’]est|[çc]a)[ \t:,\-–]{0,4})$"
)


def spelled_letter_names_ok(m: re.Match[str], spell_cue: re.Pattern[str]) -> bool:
    """Five or more letter-name words, three of them unambiguous, after a spelling or "it is" cue."""
    text = m.string[max(0, m.start() - 40) : m.start()]
    if not (spell_cue.search(text) or _LN_CUE_BEFORE.search(text)):
        return False
    words = m.group(0).lower().split()
    return sum(len(w) >= 2 and w not in ("doble", "double", "gri") for w in words) >= 3 and len(words) >= 5


_CY_U = "А-ЯЁІЇЄҐ"
_CY_L = "а-яёіїєґ"
_CY_W = rf"[{_CY_U}][{_CY_L}'’ʼ]+(?:-[{_CY_U}][{_CY_L}'’ʼ]+)?"
_CY_NAME = rf"{_CY_W}(?:[ \t]{_CY_W}){{0,2}}"
_CY_END = rf"(?![{_CY_U}{_CY_L}'’ʼ\-])"
# Capitalized Cyrillic words that follow a cue without being a name: polite "you", titles, "everyone".
_CY_NOT_NAMES = frozenset(
    """
    вы вам вас вами ваш ваша ваше ваши ви вам вас вами ваш ваша ваше ваші всем всім всех всіх
    доктор доктору врач лікар лікарю пан пані господин госпожа клиника клініка команда команді
    команде центр центру спасибо дякую дякуємо
    """.split()
)
_CY_VOCATIVE = (
    r"спасибо|спасибі|дякуємо|дякую|благодарю|благодарим|здравствуйте|здрастуйте|добрый\s+день|добрий\s+день|"
    r"доброго\s+дня|добрый\s+вечер|добрий\s+вечір|привет|привіт|вітаю|вітаємо|до\s+свидания|до\s+побачення"
)
_CY_RELATIONS = (
    r"жена|жену|жены|муж|мужа|мама|мать|мати|матір|папа|отец|тато|батько|сестра|сестру|брат|дочь|дочка|"
    r"сын|сына|партн[ёе]р|чоловік|чоловіка|дружина|дружини|донька|доньки|син|опекун|опікун"
)
_CY_LABELS = (
    r"мене\s+звати|мене\s+звуть|меня\s+зовут|мо[єё]\s+ім['’ʼ]?я|мо[ёе]\s+имя|ім['’ʼ]я|имя|прізвище|фамилия|піб|фио|"
    r"пацієнтк[аи]|пацієнт|пациентка|пациент"
)
_CY_INTRO = r"это|це"

_K = "\u4e00-\u9fff々"  # kanji
_KATA = "\u30a1-\u30fa\u30fc"
_JP_NAME = rf"[{_K}{_KATA}]{{1,4}}[ \u3000][{_K}]{{1,4}}(?![{_K}])"
_JP_RELATIONS = (
    r"夫|妻|息子|娘|母|父|パートナー|配偶者|旦那|主人|姉|妹|兄|弟|祖母|祖父|友人|緊急連絡先|保護者|患者"
)
_HE_AGE_RELATIONS = r"אמא|אימא|אבא|סבתא|סבא|דודה|דוד|אחות|אח|בעלי|אשתי|הבת|הבן"
# Present tense only: "Joanna said we can do the thaw" is clinic staff reporting, "Hiro says we should call" is
# family advice, but the tense is all the text gives.
_SAYS = r"says|thinks|insists|suggests"


def script_rules(
    not_names: frozenset[str] | set[str],
) -> list[tuple[str, int, Optional[Callable[[re.Match[str]], bool]]]]:
    """NAME rules for names in Cyrillic, Japanese and Hebrew and a few cues for a single first name.

    Every rule needs a cue: a name label, an introduction, a relation, a greeting or thanks before the name
    (the vocative), a Japanese humble "と申します" after it, or an age after a relative's first name."""
    check, *_ = make_checks(not_names)

    def check_cyr(m: re.Match[str]) -> bool:
        return m.group("name").split()[0].lower() not in _CY_NOT_NAMES

    return [
        # "Мене звати Оксана Мельник", "Фамилия: Громова", "Пацієнтка: Ірина Коваленко".
        (rf"(?<![\w])(?i:{_CY_LABELS})[ \t]*[:\-—]?[ \t]*(?P<name>{_CY_NAME}){_CY_END}", 0, check_cyr),
        # "Это Наталья Громова", "Це Ірина".
        (rf"(?<![\w])(?i:{_CY_INTRO})[ \t]+(?P<name>{_CY_NAME}){_CY_END}", 0, check_cyr),
        # "жена Сергея Мельника", "Мати, Ірина Коваленко".
        (rf"(?<![\w])(?i:{_CY_RELATIONS})[ \t]*[,:]?[ \t]*(?P<name>{_CY_NAME}){_CY_END}", 0, check_cyr),
        # A name in the vocative after thanks or a greeting: "Дякуємо, Оксано,", "Спасибо, Мария."
        (
            rf"(?<![\w])(?i:{_CY_VOCATIVE})[ \t]*,[ \t]*(?P<name>{_CY_W})(?=[ \t]*(?:[,.!?;]|$|\n)){_CY_END}",
            re.MULTILINE,
            check_cyr,
        ),
        # A Japanese name, family and given name apart, after a relation or a label: "夫の山田 太郎と", "氏名：山田 太郎".
        (rf"(?:{_JP_RELATIONS}|氏名|お名前|名前|患者名|姓名)(?:の|は|[:：])?[ \t]*(?P<name>{_JP_NAME})", 0, None),
        # "氏名：山田太郎": a label with a colon, then kanji alone.
        (rf"(?:氏名|お名前|名前|患者名|姓名)[ \t]*[:：][ \t\u3000]*(?P<name>[{_K}]{{2,5}})(?![{_K}])", 0, None),
        # The humble introduction: "山田 花子と申します", "山田花子と申します", "田中 美咲です".
        (rf"(?<![{_K}])(?P<name>[{_K}]{{1,4}}[ \u3000]?[{_K}]{{1,4}})(?=と申します|と言います|といいます)", 0, None),
        (rf"(?<![{_K}])(?P<name>[{_K}]{{1,4}}[ \u3000][{_K}]{{1,4}})(?=です(?![{_K}\u3041-\u3096]))", 0, None),
        # A relative's first name before the age: "אמא טובה בת 62", "אבא דוד בן 70".
        (
            rf"(?<![{_HE}])[ולבשמ]?(?:{_HE_AGE_RELATIONS})[ \t]+(?P<name>{_HWORD})[ \t]+(?:בת|בן)[ \t]*\d{{1,3}}(?!\d)",
            0,
            check,
        ),
        # "Hiro says we should call the clinic": a first name saying what the writer should do.
        (rf"(?<![\w'’\-])(?P<name>{_CW})[ \t]+(?i:{_SAYS})[ \t]+(?i:that[ \t]+)?(?i:we|i|you)[ \t]+(?i:should|need|must|ought)\b", 0, check),
        # "We named her Zara after my grandmother", "named our baby Zara".
        (rf"(?i:\bnamed)[ \t]+(?i:her|him|them|the[ \t]+baby|our[ \t]+(?:baby|daughter|son))[ \t]+(?P<name>{_CW})", 0, check),
        # Tagalog: "ako po si Jocelyn", "ang asawa ko, si Ramon".
        (rf"(?i:\b(?:ako[ \t]+(?:po[ \t]+)?|ang[ \t]+(?:asawa|anak|nanay|tatay|kapatid)[ \t]+(?:ko|niya|namin)[ \t]*,?[ \t]*)si)[ \t]+(?P<name>{_CW})", 0, check),
    ]
