"""Where someone lives or can be found, beyond street addresses and the big-city list.

Rural routes, GPS coordinates, directions to a home, counties, First Nations,
small towns behind a strong "I live in" cue, military and campus addresses,
colonias, mailbox numbers and the schools of a patient's children.

Every rule needs its own cue or shape; a capitalised word alone is never a place.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from ..entities import EntityType

Rule = tuple[EntityType, str, int, "int | str", Optional[Callable[[re.Match[str]], bool]]]

I = re.IGNORECASE

# Capitalised words after a cue that are not a town: sentence words, titles, calendar words,
# stages of treatment, countries, states and provinces (not identifying under Safe Harbor).
NOT_PLACES = frozenset(
    """
    casa fase cuarto urgencias consulta espera tratamiento tipo piel trabajar trabajo hacerme viaje camino clase cama reposo ciclo
    semana mes control cita oficina escuela vacaciones licencia baja estimulación estimulacion transferencia descanso proceso duda
    dolor centro cerca lejos aquí aqui allí alli
    proximité proximite route chemin cours traitement attente consultation vacances repos maison travail congé conge arrêt arret
    bureau hôpital hopital ville phase cycle proche près pres loin ici
    pobliżu poblizu trakcie mężem mezem żoną zona mamą mama domu pracy szpitalu klinice drodze centrum wizycie leczeniu urlopie
    blisko daleko tutaj tam
    downtown uptown close near nearby far here there suburbs coffee
    the a an my our your his her their it this that there here these those who what when where how why
    i we you he she they me us not no yes ok okay hi hello hey thanks thank please also then and but so or if
    dr dre dra mr mrs ms mx miss sr sra sir madam nurse doctor doctora docteur docteure prof professor
    monday tuesday wednesday thursday friday saturday sunday today tomorrow tonight yesterday
    january february march april may june july august september october november december
    janvier février mars avril mai juin juillet août septembre octobre novembre décembre
    enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre
    lunes martes miércoles jueves viernes sábado domingo lundi mardi mercredi jeudi vendredi samedi dimanche
    regards best cheers sincerely warmly bye
    day week month year cycle round phase stage step trimester room bed ward floor line page
    home work school clinic hospital office lab pharmacy church mosque temple hotel airport
    ivf icsi iui fet pgt er or icu nicu pacu rn np md
    waiting stims stimulation transfer retrieval trigger monitoring
    canada usa us america states united mexico méxico mexique france spain españa espagne poland polska polsce pologne
    israel israël izrael haiti haïti nigeria india china japan korea vietnam philippines brazil colombia peru cuba
    jamaica ukraine russia germany italy portugal ireland england scotland wales uk britain australia egypt iran
    iraq syria lebanon liban jordan turkey pakistan bangladesh ethiopia somalia kenya ghana senegal morocco maroc
    algeria algérie tunisia tunisie argentina chile venezuela ecuador guatemala honduras nicaragua panama
    canadá francia kanada kanadzie europe asia africa
    ontario québec quebec alberta manitoba saskatchewan georgia florida texas alabama tennessee california
    carolina virginia ohio
    english french spanish polish hebrew arabic canadian american haitian
    alaska arizona arkansas colorado connecticut delaware hawaii idaho illinois indiana iowa kansas kentucky louisiana
    maine maryland massachusetts michigan minnesota mississippi missouri montana nebraska nevada oklahoma oregon
    pennsylvania tennessee utah vermont wisconsin wyoming
    newfoundland labrador nunavut yukon
    cameroun cameroon congo rwanda uganda tanzania sudan libya angola mozambique zimbabwe zambia
    afghanistan nepal sri indonesia thailand malaysia singapore taiwan mongolia kazakhstan uzbekistan armenia georgia
    belgium belgique netherlands switzerland suisse austria sweden norway denmark finland greece romania bulgaria
    hungary serbia croatia albania ukraine belarus lithuania latvia estonia
    bolivia uruguay paraguay brasil costa rica salvador cuba dominicana
    allemagne italie portugal irlande angleterre écosse chine japon corée vietnam inde iran irak syrie égypte
    turquie russie pays colombie pérou brésil argentine chili venezuela équateur bolivie
    alemania italia portugal irlanda inglaterra escocia china japón corea india irán irak siria egipto turquía rusia
    niemcy włochy francji hiszpanii anglii chinach indiach ukrainie rosji
    europy azji afryki ameryki australii oceanii europa asia africa america américa amérique afrique asie áfrica
    polski ukrainy niemiec kanady meksyku izraela wietnamu indii chin rosji włoch anglii szwecji norwegii holandii belgii
    grecji turcji filipin jamajki nigerii pakistanu iranu iraku egiptu libanu brazylii kolumbii peru kuby litwy białorusi
    czech słowacji rumunii węgier portugalii irlandii australii
    """.split()
) | frozenset(
    {
        "nova scotia", "new brunswick", "british columbia", "prince edward island", "newfoundland and labrador",
        "north carolina", "south carolina", "west virginia", "united states", "estados unidos", "états-unis",
        "etats-unis", "ee.uu", "new mexico", "north america", "south america", "cape breton island",
    }
)

# The clinic giving directions to itself ("Find us in the red house past ..."): not a patient's home.
_CLINIC_SPEAKING = re.compile(
    r"(?i:(?:\b(?:find[ \t]+us|come[ \t]+(?:to|by)|visit[ \t]+us|we[ \t]+are[ \t]+located|we['’]re[ \t]+located)[ \t]+(?:in|at|on|to)?[ \t]*"
    r"|\bdirections?[ \t]+to[ \t]+(?:the|our)[ \t]+(?:clinic|office|centre|center|lab|building|parking)[ \t]*[:\-][ \t]*"
    r"|\b(?:agent|staff|clinic|reception|front[ \t]+desk|bot|assistant)[ \t]*:[ \t]*))$"
)
_CAP = r"[A-ZÀ-ÝŁŚŻŹĆ][\w'’\-]+"
_STATE_NAMES = (
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|"
    "Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|"
    "New[ \t]+Hampshire|New[ \t]+Jersey|New[ \t]+Mexico|New[ \t]+York|North[ \t]+Carolina|North[ \t]+Dakota|Ohio|Oklahoma|Oregon|"
    "Pennsylvania|Rhode[ \t]+Island|South[ \t]+Carolina|South[ \t]+Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
    "West[ \t]+Virginia|Wisconsin|Wyoming|Ontario|Quebec|Québec|Alberta|Manitoba|Saskatchewan|British[ \t]+Columbia|Nova[ \t]+Scotia|"
    "New[ \t]+Brunswick|Newfoundland|Prince[ \t]+Edward[ \t]+Island"
)
_CAP1 = r"[A-ZÀ-ÝŁŚŻŹĆ][\w'’&\-]*"
# "St.", "Ste." or "Mt." in front of a place name belongs to the span: "St. Louis County".
_SAINT = r"(?:(?-i:(?:St|Ste|Mt)\.?[ \t]+))?"
_CAP3 = rf"{_CAP}(?:[ \t]+(?:(?i:de|du|des|del|de\s+la|la|le|of|the|d['’]|l['’])[ \t]*)?{_CAP}){{0,3}}"
# A town: up to four capitalised words, "Pointe-de-l'Église", "Lac Mégantic".
_PLACE = rf"(?-i:{_CAP3})"


def _grp(m: re.Match[str]) -> str:
    d = m.groupdict()
    return d.get("place") or d.get("pl") or ""


# A fertility drug after "moved to" / "switched from" is not a town.
_DRUG = re.compile(
    r"(?i)(?:gonal|menopur|ovitrelle?|ovidrel|cetrotide|orgalutran|ganirelix|fyremadel|pregnyl|novarel|follistim|puregon|"
    r"lupron|crinone|endometrin|prometrium|progesterone|estradiol|estrace|letrozole|femara|clomi|cabergoline|dostinex|metformin|"
    r"lovenox|clexane|heparin|aspirin|bravelle|luveris|rekovelle|elonva|suprefact|decapeptyl|buserelin|synarel|ovaleap|bemfola|"
    r"delestrogen|provera|medrol|prednisone|doxycycline|dexamethasone|synthroid|levothyroxine|hcg|fsh|lh\b)"
)
_GROUP_AFTER = re.compile(r"[ \t]+(?:community|people|family|families|church|mosque|temple|clinic|office|team|hospital|group|men|women|food|culture)\b")


_STREET_WORDS = frozenset(
    "st street ave avenue road rd dr drive unit units mg iu ml lane ln blvd boulevard court ct way suite apt".split()
)

# Departments, wards, institutions and insurers are never a home town ("I'm from Sick Kids", "moved to Recovery").
_INSTITUTION_WORDS = frozenset(
    """reception billing recovery gate triage admitting lab labs pharmacy radiology ultrasound hospital clinic clinics centre center
    health life insurance sinai sick fertility associates practice services department dept unit program institute university
    college school care medical cycle treatment emergency registration admissions outpatient inpatient surgery ward parking lobby entrance waiting""".split()
)


def _residence_ok(m: re.Match[str]) -> bool:
    return not (set(_grp(m).lower().replace("-", " ").split()) & _INSTITUTION_WORDS)


def place_ok(m: re.Match[str]) -> bool:
    """The captured place is not a sentence word, calendar word, country or province, nor a group
    ("from the Nigerian community")."""
    p = _grp(m).lower().rstrip(".,")
    if _GROUP_AFTER.match(m.string, m.end()):
        return False
    return p not in NOT_PLACES and p.split()[0] not in NOT_PLACES and len(p) >= 3 and not _DRUG.match(p)


_HE_STOP = frozenset(
    """
    בית דירה עיר יישוב ישוב צפון דרום מרכז קיבוץ מושב רחוב שכונה כפר אזור ארץ בניין קומה מקום אותו אותה הבית הדירה
    העיר הכפר הארץ חו״ל חוץ ישראל קנדה ארהב אמריקה אנגליה צרפת פולין מקסיקו רוסיה אירופה אסיה אפריקה
    שם כאן פה עכשיו היום מחר אנחנו אני הוא היא הם עם של כי לא גם אבל כבר
    """.split()
)
_HE_RESIDENCE_VERBS = frozenset("גר גרה גרים גרות גרנו גרתי מתגורר מתגוררת מתגוררים עברנו עברתי עוברים עוברת תושב תושבת תושבי".split())
_HE_FUNCTION = frozenset("אני אנחנו הוא היא הם הן עם של כי לא גם אבל כבר עכשיו מאז כל כמעט בערך כרגע ליד קרוב רחוק את או אם".split())


def he_place_ok(m: re.Match[str]) -> bool:
    words = m.group("place").split()
    return words[0] not in _HE_STOP and not (len(words) > 1 and (words[1] in _HE_FUNCTION or words[1][0] in "ובלמהש"))


# A letter name said aloud, for a postal code read out ("bee three ell, two cee four").
_LETTER_NAMES = r"(?:ay|bee|cee|see|ee|gee|aitch|jay|kay|ell|em|en|pee|are|ess|tee|vee|ex|why)"
_DIGIT_WORD = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine|\d)"


def _coords_ok(m: re.Match[str]) -> bool:
    lat = float(m.group("lat"))
    lon = float(m.group("lon"))
    if abs(lat) > 90 or abs(lon) > 180:
        return False
    signed = m.group("lat")[0] == "-" or bool(m.group("lonsign"))
    if signed:
        return True
    before = m.string[max(0, m.start() - 60) : m.start()]
    return bool(_COORD_CUE.search(before))


def _hemisphere_ok(m: re.Match[str]) -> bool:
    lat = float(re.match(r"\d+(?:\.\d+)?", m.group("lat")).group(0))  # type: ignore[union-attr]
    lon = float(re.match(r"\d+(?:\.\d+)?", m.group("lon")).group(0))  # type: ignore[union-attr]
    if lat > 90 or lon > 180:
        return False
    return bool(_COORD_CUE.search(m.string[max(0, m.start() - 60) : m.start()]))


_RURAL_CUE = re.compile(
    r"(?i)\b(?:live|lives|living|lived|reside\w*|address|adresse|habite|habitons|direcci[o\u00f3]n|domicilio|adres|mieszkam|mailing|mail|ship\w*|send|deliver\w*|moved|farm)\b[^.!?\n]*$"
)
_COORD_CUE = re.compile(
    r"(?i)\b(?:coordinates?|coords?|gps|lat(?:itude)?|lon(?:gitude)?|location|pin|coordenadas|coordonn[ée]es|"
    r"wsp[óo][łl]rz[ęe]dne|maps?)\b"
)

_COURT_BEFORE = re.compile(
    r"(?i)\b(?:court|tribunal|juzgado|corte|cour|sheriff|jury|trial|docket|expediente|chancery|probate|v\.|petition|custody)\b[^.\n]{0,90}$"
)
# A county that names an agency or court ("Fulton County Family Services"), not a home.
_ORG_AFTER = (
    r"[ \t]+(?:[A-Z]\w+[ \t]+){0,2}(?:Family|Child|Social|Sheriff|Court|Department|Dept|Health|Schools?|District|Jail|Police|"
    r"Services?|Government|Clerk|Board|Library|Hospital|Superior|Probate|Juvenile|DFCS|Public)\b"
)


# A county, reserve, colonia or base named as a public place or route, not a home: "Visit Cobb County office",
# "Take Mission Road Reserve exit", "Colonia Roma Norte clinic". A residence cue before it keeps it masked.
_INST_AFTER = re.compile(
    r"(?i)[ \t]+(?:(?:[a-z]+[ \t]+){0,1}(?:offices?|exits?|clinics?|hospitals?|courts?|courthouse|librar(?:y|ies)|schools?|"
    r"government|building|health[ \t]+(?:department|centre|center|unit|system)|(?:medical|health|regional|community)[ \t]+(?:centre|center)|"
    r"medical|regional[ \t]+hospital|jail|sheriff|fair(?:grounds)?|airport|department|dept|oficina|hospital|cl[ií]nica|"
    r"clinique|bureau|urz[aą]d|szpital)\b)"
)
_INST_BEFORE = re.compile(r"(?i)\b(?:visit|visiting|take|taking|exit)[ \t]+(?:the[ \t]+)?$")
_RESIDENCE_NEAR = re.compile(
    r"(?i)\b(?:live|lives|living|lived|home|house|address|reside|resides|residing|resident|moved|moving|vivo|vive|"
    r"domicile|habite|mieszkam|my[ \t]+place|apartment|apt)\b"
)


def _public_place(m: re.Match[str]) -> bool:
    """True when the place is a public institution or route (not a residence)."""
    s = m.string
    if _RESIDENCE_NEAR.search(s[max(0, m.start() - 60) : m.start()]) or _RESIDENCE_NEAR.search(s[m.end() : m.end() + 30]):
        return False
    return bool(_INST_AFTER.match(s, m.end()) or _INST_BEFORE.search(s[max(0, m.start() - 20) : m.start()]))


def _not_public(inner=None):
    def check(m: re.Match[str]) -> bool:
        return (inner is None or inner(m)) and not _public_place(m)

    return check


def rules() -> list[Rule]:
    R: list[Rule] = []

    def add(t: EntityType, pat: str, flags: int = 0, group: "int | str" = 0, check=None) -> None:
        R.append((t, pat, flags, group, check))

    A = EntityType.ADDRESS
    _CAPL = r"[A-ZÀ-ÝŁŚŻŹĆ][a-zà-ÿł'’]+(?:-[A-ZÀ-ÝŁŚŻŹĆ]?[a-zà-ÿł'’]+)*"
    town_after = rf"(?:,[^\S\n]*(?P<city>(?-i:{_CAPL}(?:[ \t]+{_CAPL})?)))?"

    # Rural routes: "RR 2, Site 4, Box 12, Shubenacadie", "Rural Route 3, Truro".
    _rr_tail = r"(?:,?[^\S\n]*(?i:site|box|comp(?:artment)?|lot|concession)[^\S\n]*\d{1,4}\b){0,3}"
    add(
        A,
        rf"\b(?:(?i:rural[^\S\n]+(?:route|rte\.?)|route[^\S\n]+rurale)[^\S\n]*#?\d{{1,3}}\b{_rr_tail}"
        rf"|(?-i:RR|R\.R\.)[^\S\n]*#?\d{{1,3}}\b(?=,?[^\S\n]*(?i:site|box|comp)\b){_rr_tail}){town_after}",
        0,
        0,
        lambda m: not m.group("city") or m.group("city").lower() not in NOT_PLACES,
    )
    # Short rural routes with the town after them: "RR 2, Smithville", "R.R.#2 Smithville ON", "RR#2, Lacombe AB",
    # "RR2 Smithville". Plain "RR" is also a medical ratio, so it needs a "#", a comma before the town or an address word.
    _rr_town = rf"(?P<city>(?-i:(?!(?:Patients?|Results?|Women|Men|Group|Groups|Trial|Study|Studies|CI|Cohort|Data|Table|Figure|Total|Overall)\b){_CAPL}(?:[ \t]+{_CAPL})?))"
    add(
        A,
        rf"(?<![\w.])(?:R\.[^\S\n]?R\.[^\S\n]*#?[^\S\n]*\d{{1,3}}(?![\d.]\d)\b,?|RR[^\S\n]*(?:#[^\S\n]*\d{{1,3}}(?![\d.]\d)\b,?|\d{{1,3}}(?![\d.]\d)\b,))"
        rf"[^\S\n]*{_rr_town}",
        0,
        0,
        lambda m: m.group("city").split()[0].lower() not in NOT_PLACES,
    )
    add(
        A,
        rf"(?<![\w.])RR[^\S\n]*\d{{1,3}}(?![\d.]\d)\b[^\S\n]+{_rr_town}",
        0,
        0,
        lambda m: m.group("city").split()[0].lower() not in NOT_PLACES
        and (re.match(r"RR\d", m.group(0)) is not None or bool(re.search(r"(?i)\b(?:live|lives|living|address|at|from|mail|send|ship|reside|moved|located|farm|box|route)\b", m.string[max(m.string.rfind("\n", 0, m.start()) + 1, m.start() - 80) : m.start()]))),
    )
    # A box number with the town after it: "PO Box 118, Cartersville".
    add(
        A,
        rf"\b(?:P\.?[^\S\n]?O\.?[^\S\n]*Box|Postal[^\S\n]+Box)[^\S\n]*\d{{1,6}}(?:,[^\S\n]*(?!(?i:station|stn|succ|succursale|rpo)\b)(?P<city>(?-i:{_CAPL}(?:[ \t]+{_CAPL})?)))",
        I,
        0,
        lambda m: m.group("city").split()[0].lower() not in NOT_PLACES,
    )
    # A Canadian box at a station: "PO Box 12, Station A", "PO Box 12 Stn B, Toronto".
    add(
        A,
        rf"\b(?:P\.?[^\S\n]?O\.?[^\S\n]*Box|Postal[^\S\n]+Box|C\.?P\.?)[^\S\n]*\d{{1,6}},?[^\S\n]*(?i:station|stn\.?|succ(?:ursale)?\.?|rpo)[^\S\n]+(?-i:[A-Z]\b(?:[^\S\n]+(?:Main|Centre|Center))?)"
        rf"(?:,[^\S\n]*(?P<city>(?-i:{_CAPL}(?:[ \t]+{_CAPL})?)))?",
        I,
        0,
        lambda m: m.group("city") is None or m.group("city").split()[0].lower() not in NOT_PLACES,
    )

    # A GPS pair: signed, or after a cue ("the drop location is at 34.0522, -84.2980").
    add(
        A,
        r"(?<![\d.\-])(?P<lat>-?\d{1,2}\.\d{4,8})[^\S\n]*[,;][^\S\n]*(?P<lonsign>-|(?i:menos|minus|moins)[^\S\n]+)?(?P<lon>\d{1,3}\.\d{4,8})(?!\d|\.\d)",
        0,
        0,
        _coords_ok,
    )

    # Rural lines after an address cue: "Route rurale no 2, Saint-Jean", "Rang 3", "Concession 5 Lot 12, Elgin",
    # "Lot 12 Concession 4, Perth", "rr 1 site 5 comp 3". Each needs a cue that says someone lives or mails there.
    _rural_el = r"(?i:(?:route[ \t]+rurale|rural[ \t]+route|rang|concession|lot|rr|r\.r\.|site|comp(?:artment)?|box)[ \t]*(?:no\.?|n\u00b0|#)?[ \t]*\d{1,4}[A-Z]?\b)"
    add(
        A,
        rf"(?<![\w.]){_rural_el}(?:,?[ \t]*{_rural_el}){{0,3}}{town_after}",
        0,
        0,
        lambda m: _RURAL_CUE.search(m.string[max(m.string.rfind("\n", max(0, m.start() - 80), m.start()) + 1, m.start() - 80) : m.start()]) is not None
        and not re.match(r"(?i)(?:box|site|comp\w*)\b", m.group(0))
        # a lone "Lot 12" is a product lot unless a town follows
        and not (re.match(r"(?i)lot\b", m.group(0)) and not m.group("city") and len(re.findall(r"\d+", m.group(0))) < 2)
        and (not m.group("city") or m.group("city").lower() not in NOT_PLACES),
    )

    # A GPS pair with hemisphere letters or degree marks after a cue: "GPS is 44.65 N, 63.57 W",
    # "coords: 44°39'N, 63°34'W", "44.65°N 63.57°W". Plain decimals need the cue right before them.
    _dms = r"\d{1,3}(?:\.\d{1,8})?(?:[°º](?:[^\S\n]*\d{1,2}(?:\.\d+)?['′](?:[^\S\n]*\d{1,2}(?:\.\d+)?[\"″])?)?)?"
    add(
        A,
        rf"(?<![\w.\-])(?P<lat>{_dms})[^\S\n]*(?-i:[NS])\b[^\S\n]*[,;]?[^\S\n]*(?P<lon>{_dms})[^\S\n]*(?-i:[EWO])\b",
        0,
        0,
        _hemisphere_ok,
    )
    # Degrees and decimal minutes with spaces, after a cue: "my GPS is 44 39.5 N 63 34.2 W".
    add(
        A,
        r"(?<![\w.\-])(?P<lat>\d{1,2}[^\S\n]+\d{1,2}(?:\.\d+)?)[^\S\n]*(?-i:[NS])\b[^\S\n]*[,;]?[^\S\n]*(?P<lon>\d{1,3}[^\S\n]+\d{1,2}(?:\.\d+)?)[^\S\n]*(?-i:[EWO])\b",
        0,
        0,
        lambda m: _hemisphere_ok(m) and int(m.group("lat").split()[1].split(".")[0]) < 60 and int(m.group("lon").split()[1].split(".")[0]) < 60,
    )
    # The hemisphere letter first, after a cue: "GPS: N 44.65 W 63.57".
    add(
        A,
        r"(?<![\w.\-])(?-i:[NS])[^\S\n]*(?P<lat>\d{1,2}\.\d{2,8})[^\S\n]*[,;]?[^\S\n]*(?-i:[EWO])[^\S\n]*(?P<lon>\d{1,3}\.\d{2,8})(?![\d.])",
        0,
        0,
        _hemisphere_ok,
    )
    # Labelled latitude and longitude: "lat 44.6488 lon -63.5752", "latitude: 44.65, longitude: -63.57".
    add(
        A,
        r"\b(?i:lat(?:itude)?)\b\.?[^\S\n]*[:=]?[^\S\n]*-?(?P<lat>\d{1,2}\.\d{2,8})[^\S\n]*[,;]?[^\S\n]*(?i:lon(?:g(?:itude)?)?|lng)\b\.?[^\S\n]*[:=]?[^\S\n]*-?(?P<lon>\d{1,3}\.\d{2,8})(?![\d.])",
        0,
        0,
        lambda m: float(m.group("lat")) <= 90 and float(m.group("lon")) <= 180,
    )
    add(
        A,
        r"(?i:\b(?:gps|coords?|coordinates?|coordenadas|coordonn[ée]es)\b)[^\S\n]*[:=\-]?[^\S\n]*(?:is|es|est|are|at)?[^\S\n]*(?P<c>-?\d{1,2}\.\d{1,8}[^\S\n]*[,;][^\S\n]*-?\d{1,3}\.\d{1,8})(?![\d.])",
        0,
        "c",
        lambda m: abs(float(re.split(r"[,;]", m.group("c"))[0])) <= 90 and abs(float(re.split(r"[,;]", m.group("c"))[1])) <= 180,
    )

    # Directions to a home: "the blue house past the Circle K on Hwy 20, and then the second gravel drive on the left".
    _home = r"(?:house|home|cabin|trailer|cottage|bungalow|farmhouse|farm|barn|chalet|mobile[ \t]+home)"
    _rel = r"(?:just[ \t]+)?(?:past|after|before|behind|beyond|next[ \t]+to|across[ \t]+from|opposite|off|near|down[ \t]+from|up[ \t]+from|at[ \t]+the[ \t]+end[ \t]+of)"
    _street_w = r"(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|crescent|cres|way|boulevard|blvd|trail|line)"
    _land_noun = r"(?:church|school|store|station|bridge|barn|silo|mailbox|gate|tower|sign|crossroads|intersection|hall|lake|creek|pond|farm|market|diner|pub|mill)"
    _road_head = r"(?:Hwy|Highway|Route|Rte|Rd|Road|CR|County[ \t]+Road|Trunk|Exit)"
    _land = (
        rf"(?:(?-i:{_CAP1}(?:(?![ \t]+{_road_head}\b)[ \t]+{_CAP1}){{0,3}})(?:[ \t]+{_land_noun}\b)?|(?:[a-z]+[ \t]+){{0,2}}{_land_noun})"
    )
    _dir_end = r"(?-i:(?:[ \t]+(?:North|South|East|West|[NSEW])\b)?)"
    _on_road = (
        rf"(?:[ \t]+(?:on|off|at)[ \t]+(?:the[ \t]+)?(?:(?-i:{_road_head}\.?[ \t]*\w{{1,4}}\b){_dir_end}"
        rf"|(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}})[ \t]+(?i:{_street_w})\b)"
        rf"|[ \t]+(?-i:(?:Hwy|Highway|Route|Rte|CR|County[ \t]+Road)\.?[ \t]*\d{{1,4}}\b){_dir_end})?"
    )
    _tail = (
        r"(?:,?[ \t]*(?:and[ \t]+)?(?:then[ \t]+)?(?:take[ \t]+)?the[ \t]+(?:first|second|third|fourth|next|last)[ \t]+"
        r"(?:[a-z]+[ \t]+){0,2}(?:drive|driveway|road|lane|turn|turnoff|left|right|gate|mailbox|house)(?:[ \t]+on[ \t]+the[ \t]+(?:left|right))?)?"
    )
    add(
        A,
        rf"\b(?i:(?:the|our|my)[ \t]+(?:[a-z]+[ \t]+){{0,2}}{_home}[ \t]+{_rel}[ \t]+(?:the[ \t]+)?{_land}{_on_road}{_tail})",
        0,
        0,
        lambda m: not m.group(0).lower().startswith("the ")
        or not _CLINIC_SPEAKING.search(m.string[max(0, m.start() - 40) : m.start()]),
    )
    # The same in French: "notre maison est après le Tim Hortons sur la route 7".
    _fr_rel = r"(?:apr[èe]s|avant|derri[èe]re|pr[èe]s[ \t]+d(?:u|e|e[ \t]+la|['’])|en[ \t]+face[ \t]+d(?:u|e|e[ \t]+la|['’])|[àa][ \t]+c[ôo]t[ée][ \t]+d(?:u|e|e[ \t]+la|['’]))"
    add(
        A,
        rf"\b(?i:(?:notre|ma)[ \t]+(?:[a-zé]+[ \t]+){{0,2}}(?:maison|chalet|ferme|roulotte)[ \t]+(?:est[ \t]+)?(?:juste[ \t]+)?{_fr_rel}[ \t]*(?:le|la|l['’]|les)?[ \t]*)"
        rf"(?-i:{_CAP1}(?:[ \t]+{_CAP1}){{0,3}})(?:[ \t]+(?i:sur|dans)[ \t]+(?:la[ \t]+|le[ \t]+)?(?i:route|rue|chemin|rang|autoroute|boulevard|montée)[ \t]+(?:\w{{1,4}}\b|(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}})))?",
    )
    # A bare reply on the line after an address question: "Where do you live?" / "Sudbury".
    _ask_where = (
        r"(?i:(?:where|which[ \t]+(?:town|city|street|neighbou?rhood))[ \t]+(?:do|are|did)[ \t]+you[ \t]+(?:live|stay|from|in)\b[^\n?]{0,20}"
        r"|what(?:['’]s|[ \t]+is)[ \t]+your[ \t]+(?:town|city|street|neighbou?rhood)[^\n?]{0,10}"
        r"|[¿]?(?:en[ \t]+)?(?:qu[ée]|cu[áa]l)[ \t]+(?:calle|ciudad|colonia|pueblo|barrio)[^\n?]{0,25}"
        r"|[¿]?d[óo]nde[ \t]+vive[ns]?[^\n?]{0,20}"
        r"|o[ùu][ \t]+habitez-vous[^\n?]{0,15}|dans[ \t]+quelle[ \t]+(?:ville|rue)[^\n?]{0,25}"
        r"|gdzie[ \t]+mieszkasz[^\n?]{0,15}|w[ \t]+jakim[ \t]+mie[śs]cie[^\n?]{0,25}|na[ \t]+jakiej[ \t]+ulicy[^\n?]{0,25})"
    )
    _capw = r"[A-ZÀ-ÝŁŚŻŹĆŃ][^\W\d_]*(?:['’\-][^\W\d_]+)?"
    add(
        A,
        rf"{_ask_where}\?[ \t]*\n(?:[ \t]*\n)?[ \t]*(?:[A-Za-z][\w ]{{0,20}}:[ \t]*)?(?P<r>(?-i:{_capw}(?:[ \t]+(?:(?i:de|del|la|las|los|du|of|le|y)[ \t]+)?{_capw}){{0,3}}))[ \t]*[.!]?[ \t]*(?:\n|$)",
        0,
        "r",
        lambda m: all(w.lower().strip(".,!") not in NOT_PLACES for w in m.group("r").split()),
    )

    # Counties and parishes.
    add(
        A,
        rf"\b(?P<pl>{_SAINT}(?-i:(?:Lac|Lake|Fort|Port|Mount|Cape|Rio|San|Santa|Los|Las|El)[ \t]{_CAP}[ \t]{_CAP}|{_CAP}(?:[ \t\-]{_CAP})?))[ \t]+(?:County|Parish|(?-i:county))\b(?!{_ORG_AFTER})",
        0,
        0,
        _not_public(lambda m: place_ok_first(m) and not _COURT_BEFORE.search(m.string[max(0, m.start() - 110) : m.start()])),
    )
    add(
        A,
        rf"\b(?i:condado|parroquia|hrabstwo|hrabstwa|hrabstwie)[ \t]+(?i:de[ \t]+|del[ \t]+)?(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))",
        0,
        0,
        lambda m: place_ok(m) and not _COURT_BEFORE.search(m.string[max(0, m.start() - 110) : m.start()]),
    )
    add(
        A,
        rf"\b(?i:comt[ée])[ \t]+(?i:de|du|d['’])[ \t]*(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))",
        0,
        0,
        lambda m: place_ok(m) and not _COURT_BEFORE.search(m.string[max(0, m.start() - 110) : m.start()]),
    )
    # Polish districts: "powiat wielicki", "w powiecie krakowskim" (the adjective names the district).
    add(
        A,
        r"\b(?i:powiat(?:u|em|owi)?|powiecie)[ \t]+(?P<pl>(?i:[a-ząćęłńóśźż]{3,}(?:sk|ck|dzk|[sc]z)(?:i|ie|iego|im|iemu|a|iej|ą|ich|imi))\b)",
        0,
        0,
        lambda m: not _COURT_BEFORE.search(m.string[max(0, m.start() - 110) : m.start()]),
    )
    add(A, r"(?<![א-ת])[ובלמה]?(?P<a>קאונטי[^\S\n]+[א-ת][א-ת'׳\-]{2,}|[א-ת][א-ת'׳\-]{2,}[^\S\n]+קאונטי)(?![א-ת])", 0, "a")

    # Residence cue required for these variants: "I live in the county of Simcoe", "vivo en el municipio de Zapopan",
    # "mieszkam w gminie Lesznowola", "I live on Tyendinaga Mohawk Territory".
    def _lives_before(m: re.Match[str]) -> bool:
        return bool(_LIVES.search(m.string[max(0, m.start() - 80) : m.start()]))

    add(
        A,
        rf"\b(?i:(?:county|parish)[ \t]+of)[ \t]+(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))",
        0,
        0,
        lambda m: place_ok(m) and _lives_before(m) and not _COURT_BEFORE.search(m.string[max(0, m.start() - 110) : m.start()]),
    )
    add(
        A,
        rf"\b(?i:municipio|ayuntamiento|alcald[íi]a)[ \t]+(?i:de|del)[ \t]+(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))",
        0,
        0,
        lambda m: place_ok(m) and _lives_before(m),
    )
    add(
        A,
        rf"\b(?i:gmin(?:a|ie|y))[ \t]+(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,1}}))",
        0,
        0,
        lambda m: place_ok(m) and _lives_before(m),
    )
    add(
        A,
        rf"\b(?P<pl>{_SAINT}(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}[ \t]+(?:Mohawk|Unceded|Indian)[ \t]+Territory))\b",
        0,
        0,
        lambda m: place_ok_first(m) and _lives_before(m),
    )

    # First Nations and reserves: "Millbrook First Nation", "Première Nation de Kahnawake".
    add(
        A,
        rf"\b(?P<pl>{_SAINT}(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))[ \t]+(?:First[ \t]+Nation|Indian[ \t]+(?:Reserve|Band)|Band[ \t]+Council)\b",
        0,
        0,
        _not_public(place_ok_first),
    )
    # "Six Nations Reserve", "Wikwemikong Unceded Reserve", "Reserve No. 40", "Curve Lake IR 35", "réserve de Kahnawake".
    # Not a nature, bank or military reserve.
    _res_stop = frozenset(
        "federal nature marine wildlife game forest biosphere army air naval navy national military bird conservation "
        "ecological wilderness animal tiger strategic gold central the bank".split()
    )
    add(
        A,
        rf"\b(?P<pl>{_SAINT}(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))[ \t]+(?:Unceded[ \t]+|Indian[ \t]+)?(?-i:Reserve)\b(?:[ \t]+(?:No\.?|Number|#)[ \t]*\d{{1,3}}[A-Z]?\b)?",
        0,
        0,
        _not_public(lambda m: place_ok_first(m) and not (set(m.group("pl").lower().replace("-", " ").split()) & _res_stop)),
    )
    add(A, r"\b(?-i:Reserve)[ \t]+(?:No\.?|Number|#)[ \t]*\d{1,3}[A-Z]?\b")
    add(
        A,
        rf"\b(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))[ \t]+(?-i:IR)[ \t]*#?[ \t]*\d{{1,3}}[A-Z]?\b",
        0,
        0,
        place_ok_first,
    )
    add(
        A,
        rf"\b(?i:r[ée]serve)[ \t]+(?i:de|du|d['’])[ \t]*(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))",
        0,
        0,
        place_ok,
    )
    add(A, rf"\b(?i:premi[èe]res?[ \t]+nations?)[ \t]+(?i:de|du|d['’]|des)[ \t]*(?P<pl>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))", 0, 0, place_ok)

    # Small towns behind a cue that says a person lives, moved or comes from there. Only true residence or origin
    # cues with a person subject: "come to Reception", "reach out to Billing", "stay in Fasting mode" are not.
    _subj = (
        r"(?:i|we|they|she|he|(?:i|we|they)['’](?:ve|d)|(?:my|our)[ \t]+[a-z]+(?:[ \t]+and[ \t]+[a-z]+)?|[a-z]+[ \t]+and[ \t]+i)"
    )
    _adv = r"(?:(?:out|up|down|over|back|just|now|right|currently|originally|still|also|all)[ \t]+)*"
    _live_verb = r"(?:live|lives|living|lived|reside|resides|resided|residing|grew[ \t]+up|grow[ \t]+up)"
    _move_verb = r"(?:moved|moving|relocated|relocating|immigrated|migrated|(?:have|had)[ \t]+moved)"
    _the = r"(?:the[ \t]+)?"
    # a place of up to four words that stops before a state or province written right after "County"
    _CAP3S = (
        rf"{_CAP}(?:(?!(?<=County)[ \t]+(?-i:{_STATE_NAMES})\b)[ \t]+(?:(?i:de|du|des|del|de\s+la|la|le|of|the|d['’]|l['’])[ \t]*)?{_CAP}){{0,3}}"
    )
    add(
        A,
        rf"\b(?i:(?:{_live_verb}[ \t]+{_adv}(?:in|at|to|from|near|outside(?:[ \t]+of)?|out[ \t]+of)"
        rf"|{_subj}[ \t]+{_adv}{_move_verb}[ \t]+{_adv}(?:to|from|in)"
        rf"|(?:{_subj}|(?:i|we|she|he|they)['’](?:m|re|s))[ \t]+{_adv}(?:(?:am|are|is|was|were)[ \t]+)?(?:(?:come|comes|came|arrived|immigrated|migrated)[ \t]+)?from"
        rf"|(?:i|we|she|he|they)['’](?:m|re|s)[ \t]+{_adv}(?:past|outside(?:[ \t]+of)?)"
        rf"|originally[ \t]+from)[ \t]+{_the})(?P<place>(?-i:{_CAP3S}))",
        0,
        0,
        lambda m: place_ok(m) and _residence_ok(m),
    )
    # "we are now in the Harbourview area": a person and the name of a neighbourhood right before "area".
    add(
        A,
        rf"\b(?i:(?:i|we)(?:['’]m|['’]re|[ \t]+am|[ \t]+are)[ \t]+{_adv}in[ \t]+the[ \t]+)(?P<place>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}))(?=[ \t]+(?i:area|neighbou?rhood)\b)",
        0,
        0,
        lambda m: place_ok(m) and _residence_ok(m),
    )
    # A landmark whose name ends in a single capital letter, with the road after it: "We live past the Circle K on Hwy 20".
    add(
        A,
        rf"\b(?i:(?:{_live_verb}|{_move_verb}|(?:i['’]m|i[ \t]+am|we['’]re|we[ \t]+are)[ \t]+{_adv}(?:just[ \t]+)?)[ \t]+{_adv}"
        rf"(?:past|near|beyond|behind|after|next[ \t]+to|across[ \t]+from)[ \t]+{_the})"
        rf"(?P<place>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}}[ \t]+[A-Z]\b){_on_road})",
        0,
        0,
        place_ok,
    )
    # "c'est Stéphanie d'Entremont de Pubnico" (not English "this is Dana from Acme": that is a caller's employer).
    add(
        A,
        rf"\b(?i:c['’]est|je[ \t]+m['’]appelle|me[ \t]+llamo|soy)[ \t]+(?-i:{_CAP}(?:[ \t]+(?:(?i:de|d['’])[ \t]*)?{_CAP}){{0,2}})"
        rf"[ \t]+(?i:de|d['’]|desde)[ \t]*(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        place_ok,
    )
    # French, Spanish and Polish residence cues.
    add(
        A,
        rf"\b(?i:(?:j['’]habite|nous[ \t]+habitons|on[ \t]+habite|j['’]ai[ \t]+d[ée]m[ée]nag[ée]|on[ \t]+a[ \t]+d[ée]m[ée]nag[ée]|"
        rf"nous[ \t]+vivons|on[ \t]+vit|je[ \t]+vis|je[ \t]+viens|nous[ \t]+venons|on[ \t]+vient|originaires?|"
        rf"patiente?|famille|habitons|r[ée]sidons|r[ée]sidente?|demeure|demeurons)[ \t]+(?:(?:maintenant|actuellement|encore|toujours)[ \t]+)?"
        rf"(?:(?-i:[àa])[ \t]+|(?:au|aux|en|dans|de|du|des|sur|pr[èe]s[ \t]+de)[ \t]+|d['’][ \t]*)(?:(?:la|le)[ \t]+|l['’][ \t]*)?)(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        lambda m: place_ok(m) and _residence_ok(m),
    )
    add(
        A,
        rf"\b(?i:(?:vivo|vivimos|vive|viven|resido|residimos|soy|somos|vengo|venimos|mud[ée]|mudamos|nac[ií]|nacimos|"
        rf"estoy|estamos|paciente)[ \t]+(?:(?:ahora|actualmente|todav[ií]a)[ \t]+)?(?:en|de|desde|por|cerca[ \t]+de)[ \t]+(?:(?:la|el)[ \t]+)?)(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        lambda m: place_ok(m) and _residence_ok(m),
    )
    add(
        A,
        rf"\b(?i:(?:mieszkam|mieszkamy|mieszka|mieszkaj[ąa]|mieszka[łl]am|mieszka[łl]em|pochodz[ęe]|pochodzimy)[ \t]+(?:(?:teraz|obecnie)[ \t]+)?"
        rf"(?:w|we|z|ze|do|pod|ko[łl]o|niedaleko|blisko)[ \t]+|(?:jestem|jeste[śs]my|pacjentka|pacjent)[ \t]+(?:z|ze)[ \t]+)(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        lambda m: place_ok(m) and _residence_ok(m),
    )
    # A town and its province: "de Wolfville, N.-É.", "Chéticamp, Nova Scotia".
    add(
        A,
        rf"(?<![\w'’\-])(?P<place>(?-i:{_CAPL}(?:[ \t]+{_CAPL}){{0,2}})),[ \t]*(?-i:N\.-[ÉB]\.|Î\.-P\.-É\.|T\.-N\.-L\.|(?:NS|NB|NL|PE|PEI|QC|MB|SK|AB|BC)(?=[ \t]+[A-Z]\d[A-Z]|[ \t]*(?:[.;,)\n]|$))|"
        r"Nova[ \t]+Scotia|New[ \t]+Brunswick|Newfoundland|Prince[ \t]+Edward[ \t]+Island|Nouvelle-[ÉE]cosse|Nouveau-Brunswick|Québec|Quebec|Manitoba|Saskatchewan|"
        r"Alberta|British[ \t]+Columbia|Colombie-Britannique)(?![\w])",
        0,
        0,
        place_ok,
    )
    # A town before a Korean "lives in" or "moved to": "저희 Suwanee로 이사했어요", "저희는 Duluth 살아요".
    add(
        A,
        r"(?<![\w'’\-])(?P<place>[A-Z][A-Za-z'’\-]{2,}(?:[ \t][A-Z][a-z]+)?)(?=(?:은|는|이|가|으로|로|에서|에)?[^\S\n]*(?:이사|살|거주|삽니다))",
        0,
        0,
        place_ok,
    )
    # Haitian Creole and Arabic residence cues: "Nou rete nan Clarkston", "Nou nan Stone Mountain", "أنا أسكن في Bedford".
    add(
        A,
        rf"\b(?i:(?:nou|mwen)[ \t]+(?:rete|abite|ap[ \t]+viv|viv)?[ \t]*nan|(?:rete|abite|viv)[ \t]+nan|ap[ \t]+viv)[ \t]+(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        place_ok,
    )
    add(
        A,
        rf"(?<![\u0600-\u06ff])(?:أسكن|نسكن|ساكن|ساكنة|أعيش|نعيش|مقيم|مقيمة|نحن|أنا)[^\S\n]+(?:في|ب)[^\S\n]*(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        place_ok,
    )
    # A relative or patient introduced with a name and a town: "my niece Tiffany Marshall from Membertou".
    add(
        A,
        rf"\b(?i:niece|nephew|sister|brother|daughter|son|wife|husband|mother|father|friend|cousin|patient|aunt|uncle|grandmother|grandfather)[ \t]+"
        rf"(?-i:{_CAP}(?:[ \t]+{_CAP}){{1,2}})[ \t]+(?i:from)[ \t]+(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        place_ok,
    )
    # A town after a reserve or county that was just named: "Millbrook First Nation near Truro".
    add(
        A,
        rf"\b(?:First[ \t]+Nation|Reserve|County|Parish)[ \t]+(?i:near|outside(?:[ \t]+of)?|by|close[ \t]+to)[ \t]+(?P<place>(?-i:{_CAP3}))",
        0,
        0,
        place_ok,
    )
    # A town on a signature or address line before a state code: "Roswell, GA", "רוזוול, GA".
    # without the codes that are also credentials or words (MD, PA, MA, MS, ID, IN, OR, OK, ME, HI, AL, LA, DE, CO, NE)
    _states = "AK|AZ|AR|CA|CT|FL|GA|IL|IA|KS|KY|MI|MN|MO|MT|NV|NH|NJ|NM|NY|NC|ND|OH|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
    add(
        A,
        rf"(?m:^[^\S\n]*)(?P<place>(?-i:{_CAPL}(?:[ \t]+{_CAPL}){{0,2}})),[ \t]*(?-i:{_states})[ \t]*$",
        re.M,
        0,
        place_ok,
    )
    # (a residence verb first on the line is not part of the town: "גרה באלפרטה, GA" is caught by the verb rule)
    add(
        A,
        rf"(?m:^[^\S\n]*)(?P<place>[א-ת]{{3,}}(?:[^\S\n][א-ת]{{3,}})?),[ \t]*(?-i:{_states})[ \t]*$",
        re.M,
        0,
        lambda m: place_ok(m) and m.group("place").split()[0] not in _HE_RESIDENCE_VERBS,
    )
    # The town after a Polish or French postal code: "31-120 Kraków", ", 46004 Valencia".
    add(A, r"(?:,|^|\n)[^\S\n]*\d{2}-\d{3}[ \t]+(?P<place>[A-ZŁŚŻŹĆ][\wąćęłńóśźż\-]+)", 0, 0, place_ok)
    add(
        A,
        r"(?:,|^|\n)[^\S\n]*\d{5}[^\S\n]+(?P<place>[A-ZÀ-Ý][\wà-ÿ'\-]+(?:[ \t]+(?!(?i:please|thanks?|thank|and|call|my|is|the|i|we|our|can|it|if|so|or|but|then|also|hi|dr|mr|mrs|ms|on|in|at)\b)[A-ZÀ-Ý][a-zà-ÿ'\-]+){0,2})(?!\s+(?i:st|street|ave|road|rd|dr|units?|mg|iu|ml)\b)",
        0,
        0,
        lambda m: place_ok(m) and not (set(m.group("place").lower().split()[1:]) & _STREET_WORDS),
    )
    # A Canadian postal code and then the town, which may be two or three words: "M5V 2T6 Niagara Falls ON".
    add(
        A,
        r"(?:,|^|\n)[^\S\n]*[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ \-]?\d[ABCEGHJ-NPRSTV-Z]\d[^\S\n]+(?P<place>[A-ZÀ-Ý][a-zà-ÿ'\-]+(?:[ \t]+(?!(?i:please|thanks?|thank|and|call|my|is|the|i|we|our|can|it|if|so|or|but|then|also|hi|dr|mr|mrs|ms|on|in|at)\b)[A-ZÀ-Ý][a-zà-ÿ'\-]+){0,2})",
        0,
        0,
        lambda m: place_ok(m) and not (set(m.group("place").lower().split()) & _STREET_WORDS),
    )
    # Hebrew: "גרה באלפרטה", "גרים בסנדי ספרינגס", "גרה בAlpharetta" (a transliterated town is not in the city list).
    add(
        A,
        r"(?<![א-ת])(?:גר|גרה|גרים|גרות|גרנו|גרתי|מתגורר|מתגוררת|מתגוררים|עברנו|עברתי|עוברים|עוברת|תושב|תושבת|תושבי)[^\S\n]+[בל]"
        r"(?P<place>[א-ת][א-ת'׳\-]{2,}(?:[^\S\n]+[א-ת][א-ת'׳\-]{2,})?|[A-Z][A-Za-z'’\-]{2,}(?:[ \t][A-Z][a-z]+)?)(?![א-ת\w])",
        0,
        "place",
        he_place_ok,
    )

    # Military and campus addresses.
    _elem = (
        r"(?:(?i:unit|bldg\.?|building|barracks|rm|room|apt|box)[ \t]+[A-Z]?\d{1,5}[A-Z]?"
        r"|(?-i:[A-Z][\w'’]*[ \t]+){1,2}(?i:row|hall|barracks|loop)[ \t]+\d{1,4}[A-Z]?)"
    )
    _base = r"(?:(?i:fort|ft\.?|camp|cfb|base|nas|naval|mcas|mcb|afb)[ \t]+(?-i:[A-Z][\w'’\-]+(?:[ \t]+[A-Z][\w'’\-]+)?))"
    add(A, rf"\b{_elem}(?:,[ \t]*{_elem}){{0,3}},[ \t]*{_base}", 0, 0, _not_public())
    add(EntityType.ZIP, rf"\b{_base},[ \t]*(?:[A-Z]{{2}}[ \t]+)?(\d{{5}}(?:-\d{{4}})?)\b", 0, 1)
    add(A, r"(?-i:\b(?:PSC|CMR|UNIT)[ \t]+\d{3,5}(?:,?[ \t]*(?:Box|BOX)[ \t]+\d{1,5})?)(?=,?[ \t]*(?:APO|FPO|DPO)\b)", 0)
    add(EntityType.ZIP, r"\b(?:APO|FPO|DPO),?[ \t]+(?:AE|AP|AA)[ \t]+(\d{5}(?:-\d{4})?)\b", 0, 1)
    # The whole military mailing line, on one line or two: "Unit 2050 Box 4190, APO AP", "PSC 802 Box 74\nFPO AE".
    add(
        A,
        r"(?-i:\b(?:PSC|CMR|[Uu]nit|UNIT)[ \t]+\d{1,5}(?:,?[ \t]*(?:Box|BOX)[ \t]+\d{1,5})?(?:,[ \t]*|[ \t]*\n[ \t]*|[ \t]+)(?:APO|FPO|DPO),?[ \t]+(?:AE|AP|AA)\b)",
        0,
    )
    add(
        A,
        r"(?-i:\b[A-Z][\w'’\-]*(?:[ \t]+[A-Z][\w'’\-]*){0,2})[ \t]+(?i:residence(?:[ \t]+hall)?|hall|dorm(?:itory)?)\b,?[ \t]*(?i:room|rm|apt|suite)\.?[ \t]*#?\w{1,5}\b",
        0,
    )

    # A colonia: "Colonia del Valle, San Pedro Garza García", "colonia Santa María la Ribera", ", Col. Arcos Vallarta".
    _colname = rf"(?-i:{_CAP})(?:[ \t]+(?:(?i:de|del|la|las|los|y)[ \t]+)*(?-i:{_CAP})){{0,4}}"
    add(
        A,
        rf"(?:\b(?i:colonia)|(?<=,[ \t])Col\.)[ \t]+(?:(?i:del|de[ \t]+la|de[ \t]+los|de)[ \t]+)?{_colname}"
        rf"(?:,[ \t]*(?-i:{_CAP})(?:[ \t]+(?:(?i:de|del|la|los|las)[ \t]+)?(?-i:{_CAP})){{0,3}})?",
        0,
        0,
        _not_public(),
    )

    # Post boxes and neighbourhoods after an address cue: "mailing address is mailbox 123, Sudbury",
    # "mi dirección es casilla 123", "I live at skrytka pocztowa 123", "col. Del Valle", "fraccionamiento Las Palmas",
    # "osiedle Słoneczne 12", "kibbutz Ein Gedi".
    def _cued(m: re.Match[str]) -> bool:
        return _RURAL_CUE.search(m.string[max(m.string.rfind("\n", max(0, m.start() - 80), m.start()) + 1, m.start() - 80) : m.start()]) is not None

    add(
        A,
        rf"(?<![\w.])(?i:mail[ \t]?box|casilla(?:[ \t]+postal)?|skrytka(?:[ \t]+pocztowa)?)[ \t]*(?i:n[°º.]|no\.?|nr\.?|#)?[ \t]*\d{{1,6}}\b{town_after}",
        0,
        0,
        lambda m: _cued(m) and (not m.group("city") or m.group("city").lower() not in NOT_PLACES),
    )
    add(
        A,
        rf"(?<![\w.])(?i:colonia|col\.|fraccionamiento|fracc\.|osiedle|kibbutz|kibutz|moshav)[ \t]+(?:(?i:del|de[ \t]+la|de[ \t]+los|de)[ \t]+)?{_colname}(?:[ \t]+\d{{1,3}}[A-Z]?\b)?",
        0,
        0,
        lambda m: _cued(m) and not _public_place(m),
    )

    # A mailbox number: "hay un buzón con el número 4418", "une boîte aux lettres rouge avec le 4409 écrit dessus".
    add(
        A,
        r"(?i:\b(?:buz[óo]n|bo[iî]te[ \t]+aux[ \t]+lettres|mailbox|skrzynk\w+)\b[^.\n]{0,50}?\b(?:n[úu]mero|num[ée]ro|numer|number|with|avec|le|el|con)[ \t]+(?:the[ \t]+)?)(?P<n>\d{2,5}[A-Za-z]?)\b",
        0,
        "n",
    )

    # A house number said on its own after an address question; the street comes next.
    _spoken_n = (
        r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[ \t\-](?:one|two|three|four|five|six|seven|eight|nine))?"
        r"|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)"
        r"(?:[ \t\-]hundred(?:[ \t]+(?:and[ \t]+)?(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[ \t\-](?:one|two|three|four|five|six|seven|eight|nine))?|"
        r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)))?)?)"
    )
    add(
        A,
        rf"\b(?i:(?:the|house|street|building)[ \t]+number[ \t]+is[ \t]+)(?P<n>(?i:{_spoken_n}))(?![\w\-])",
        0,
        "n",
        lambda m: _address_asked(m.string, m.start()),
    )
    # The street itself, alone, in an answer after an address question: "Oak Hollow Lane."
    add(
        A,
        rf"(?m:^[^\S\n]*(?:[A-Za-z][\w ]{{0,20}}:[^\S\n]*)?)(?P<s>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}})[ \t]+(?i:street|road|avenue|lane|drive|court|crescent|way|boulevard|trail|cove|place|loop|row|terrace|circle|ave|rd|blvd)\b(?-i:(?:[ \t]+(?:North|South|East|West|[NSEW]|NE|NW|SE|SW)\b\.?)?))(?=\.?[^\S\n]*(?:$|[A-Z]))",
        re.M,
        "s",
        lambda m: _address_asked(m.string, m.start("s")) and not _asks_about_clinic(m.string, m.start("s")),
    )
    # A street named after "on", "off", "sur" in a sentence about where someone lives: "We live in Duluth, off Pleasant
    # Hill Road", "J'habite sur Quinpool Road". A lot, a lab or a pharmacy "on Main Street" is not a home.
    add(
        A,
        rf"\b(?i:on|off|sur|sobre|przy)[ \t]+(?P<s>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,2}})[ \t]+(?i:{_street_w}|cove|loop|row|terrace)\b"
        rf"(?:(?<=oad)[ \t]+\d{{1,3}}\b(?![ \t]*(?i:min|hr|hour|km|mile|mg|ml|day|week|month|year|time|%|am|pm)))?)",
        0,
        "s",
        lambda m: m.group("s").split()[0].lower() not in NOT_PLACES and bool(_LIVES.search(m.string[max(0, m.start() - 80) : m.start()])),
    )

    # A postal code read out with letter names: "bee three ell, two cee four".
    add(
        EntityType.POSTAL_CODE,
        rf"(?<![\w])(?i:{_LETTER_NAMES}[ \t]+{_DIGIT_WORD}[ \t]+{_LETTER_NAMES}[ \t,]+{_DIGIT_WORD}[ \t]+{_LETTER_NAMES}[ \t]+{_DIGIT_WORD})(?![\w])",
        0,
    )
    add(EntityType.POSTAL_CODE, r"우편번호[^\S\n]*:?[^\S\n]*(\d{5})\b", 0, 1)

    # Schools of a patient's children, or where a patient teaches: "Indian Creek Elementary", "Hillcrest Montessori".
    _school_w = r"(?:Elementary|Montessori|Academy|Preschool|Primary[ \t]+School|Middle[ \t]+School|High[ \t]+School|Junior[ \t]+High|Secondary[ \t]+School|Daycare|Day[ \t]+Care|Collegiate|Kindergarten)"
    add(
        EntityType.EMPLOYER,
        rf"\b(?P<org>(?-i:{_CAP}(?:[ \t]+{_CAP}){{0,3}})[ \t]+{_school_w})\b",
        0,
        "org",
        lambda m: m.group("org").split()[0].lower() not in NOT_PLACES and m.group("org").split()[0].lower() not in _SCHOOL_STOP,
    )
    # A Hebrew workplace with no designator word: two words after "עובד ב".
    add(
        EntityType.EMPLOYER,
        r"(?<![א-ת])(?:עובד|עובדת|עובדים|עובדות)[^\S\n]+ב(?P<place>[א-ת][א-ת'׳\"״\-]{2,}[^\S\n]+[א-ת][א-ת'׳\-]{2,})(?![א-ת])",
        0,
        "place",
        lambda m: he_org_ok(m),
    )
    return R


_SCHOOL_STOP = frozenset(
    "her his their our my your elementary middle high junior secondary primary senior grade the in at to from for with of".split()
)

_HE_ORG_STOP = frozenset(
    """
    בית משרד בנק חברה מפעל בניין מקום עבודה תחום משמרות משמרת שעות משרה יום ימים לילה לילות בוקר ערב
    ראשון שני שלישי רביעי חמישי שישי שבת ימי ימים ערבי סופי עיר אחרת אחר חצי מלאה מלא חלקית עם של כי לא גם אבל כבר עכשיו מאז כל כמעט בערך כרגע ליד קרוב רחוק מאוד קשה הרבה
    """.split()
)


def he_org_ok(m: re.Match[str]) -> bool:
    words = m.group("place").split()
    if any(w in _HE_ORG_STOP or w in _HE_FUNCTION for w in words):
        return False
    return words[1][0] not in "ובלמהש" and not words[0].startswith("ה")


def place_ok_first(m: re.Match[str]) -> bool:
    return _grp(m).split()[0].lower() not in NOT_PLACES


_LIVES = re.compile(
    r"(?i)\b(?:live|lives|living|lived|reside|resides|residing|home|habite|habitons|habitait|vivo|vivimos|vive|mieszkam|mieszkamy)\b[^.!?\n]*$"
)

_ADDRESS_ASK = re.compile(
    r"(?i)\b(?:address|street|mailing|deliver\w*|ship\w*|courier|direcci[óo]n|domicilio|adresse|livraison|adres|dostaw\w*|rue|calle)\b"
)


_CLINIC_WORD = re.compile(
    r"(?i)\b(?:clinic|clinique|cl[íi]nica|klinik\w*|office|cabinet|consultorio|gabinet\w*|pharmacy|pharmacie|farmacia|apteka|apteki|"
    r"hospital|h[ôo]pital|szpital\w*|labs?|laborator\w+|centre|center|centro|dentist|dentiste|"
    r"which[ \t]+(?:address|location|site|branch)|closest|nearest|pick[ \t\-]?up|drop[ \t\-]?off|works[ \t]+(?:best|for))\b"
)
_HOME_ASK = re.compile(
    r"(?i)\byou[ \t]+(?:live|stay|reside)|\byour[ \t]+(?:home|mailing|billing|street|address|residence|house)\b|"
    r"\b(?:vive|vives|viven|vivez|habitez|mieszkasz|tu[ \t]+casa|su[ \t]+casa|votre[ \t]+domicile)\b"
)


def _asks_about_clinic(text: str, pos: int) -> bool:
    """The street question is about the clinic, a pharmacy or a lab, not where the patient lives."""
    window = text[max(0, pos - 240) : pos]
    hits = list(_ADDRESS_ASK.finditer(window))
    if not hits:
        return False
    a = hits[-1].start()
    # the whole line (every sentence of the question), not only the sentence that holds the address word
    start = window.rfind("\n", 0, a) + 1
    end = window.find("\n", a)
    sentence = window[start : end if end >= 0 else len(window)]
    return bool(_CLINIC_WORD.search(sentence)) and not _HOME_ASK.search(sentence)


def _address_asked(text: str, pos: int) -> bool:
    return bool(_ADDRESS_ASK.search(text[max(0, pos - 240) : pos]))
