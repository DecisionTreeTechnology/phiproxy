"""Optional local-model layer using GLiNER, run in-process (nothing leaves).

Pattern rules cannot find a lowercase name that is not in the patient's record
("my husband ravi"), a city ("I live in Sudbury") or a workplace. A small
named-entity model can. GLiNER models are zero-shot: they take the entity
labels as plain text, so the same model covers several languages and types.

Install with ``pip install phiproxy[gliner]``. The default model is
``urchade/gliner_multi_pii-v1`` (Apache-2.0, about 1.2 GB, English, French,
Spanish, German, Italian, Portuguese). It is downloaded from Hugging Face on
first use; in production, download it once and point ``model`` at the local
directory, or set ``HF_HUB_OFFLINE=1``. Text is never sent anywhere to detect
PHI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..entities import Entity, EntityType
from ._names import is_clinician

DEFAULT_MODEL = "urchade/gliner_multi_pii-v1"

# Label shown to the model -> phiproxy type. The model sees only the keys.
DEFAULT_LABELS: dict[str, EntityType] = {
    "person": EntityType.NAME,
    "doctor or nurse": EntityType.PROVIDER,
    "city": EntityType.ADDRESS,
    "street address": EntityType.ADDRESS,
    "employer": EntityType.EMPLOYER,
}

_WORD = re.compile(r"\S+")

# NER models sometimes tag pronouns, greetings, role words and transcript
# speaker labels as people ("we", "hi", "my husband", "Patient", "Visiteur:").
# Spans made only of these words are dropped.
_NOT_NAME_WORDS = frozenset(
    """
    i me my mine you your yours ur we us our ours he him his she her hers they them
    their it someone somebody everyone anyone and
    patient patients pt caller agent sir madam maam ma'am
    partner husband hubby wife spouse boyfriend girlfriend fiance fiancee mom mum
    mother dad father baby son daughter sister brother grandson granddaughter
    grandmother grandfather girl boy little kids doctor nurse team
    hi hello hey um uh hmm a an the one two three
    user bot visitor guest staff receptionist assistant system ivr operator
    coordinator embryologist embryologists worker social
    visiteur visiteuse patiente infirmière une un le la les
    visitante agente llamante paciente enfermera una el los las
    gość gosc dzwoniąca dzwoniący pacjent pacjentka konsultant konsultantka
    מתקשרת מתקשר אורח אורחת סוכן סוכנת מטופל מטופלת נציג נציגה
    je moi tu toi vous nous il elle ils elles on mon ma mes bonjour salut
    conjoint conjointe mari femme
    yo tú usted ustedes nosotros nosotras él ella ellos ellas mi hola esposo esposa
    ja ty wy oni ona pan pani mój moja cześć mąż żona
    אני אתה את אנחנו הוא היא הם הן שלום
    appelant appelante appelants persona personas que llama llamó participant participants
    participante participantes addressee recipient recipients donor oocyte sperm egg
    partners neighbor neighbour neighbors neighbours friend friends family relative
    moms mom's mums dads mamá mama mamy papá papa mère père maman babcia babci babcią dziadek
    osoba osobę osoby towarzyszącą towarzysząca alguien quelqu'un ktoś
    dear estimado estimada estimados estimadas cher chère chers chères drodzy szanowni
    pacientes pacjenci pacjentki מטופלים מטופלות יקרים יקרות
    nvm vm hsg hr it reply bueno name s
    kid kiddo toddler infant ex single female male kin next of lady gentleman
    all director physician physicians lab manager compliance sir madam madame monsieur mr mrs ms
    señor señora senor senora pan pani mx dr
    asistente asistenta assistante asystent asystentka מבקר מבקרת
    żony żonie żonę żoną męża mężowi mężem partnera partnerki partnerką
    client clients cliente clienta clientes usuario usuaria utilisateur utilisatrice użytkownik
    użytkowniczka עוזר עוזרת משתמש משתמשת person interpreter interprète intérprete tłumacz
    tłumaczka מתורגמן מתורגמנית courier dispatcher shipper guardian parent parents votre notre
    nuestro nuestra vuestro is shalom billing dept department embryologiste embriólogo
    embrióloga embriolog האמבריולוג האמבריולוגית support medical student students médecin
    bébé bebé cousin cousine prima primo résidents admissibles specjalista המטופלת המטופל valued
    technicienne técnica technik doc
    """.split()
)
# Fertility and common drugs the model reads as names ("Ovitrelle", "אוביטרל").
_DRUGS = frozenset(
    """
    ovitrelle ovidrel gonal gonal-f menopur cetrotide orgalutran ganirelix fyremadel lupron
    leuprolide puregon follistim pregnyl novarel rekovelle elonva luveris pergoveris
    crinone endometrin prometrium utrogestan cyclogest duphaston progesterone estrace
    estradiol progynova climara letrozole femara clomid clomiphene serophene metformin
    decapeptyl synarel suprefact dostinex cabergoline omnitrope medrol prednisone
    doxycycline azithromycin aspirin heparin clexane fragmin lovenox tylenol advil
    אוביטרל אוביטרל גונל גונל-אף מנופור צטרוטייד אורגלוטרן פרגניל אסטרופם קרינון אוטרוגסטן
    לטרוזול פמרה קלומיד דקפפטיל
    """.split()
)

# A place the size of a state or province is not an identifier under Safe Harbor.
_REGIONS = frozenset(
    """
    canada usa us america ontario quebec québec alberta manitoba saskatchewan
    nova-scotia new-brunswick newfoundland labrador pei yukon nunavut bc
    british-columbia prince-edward-island northwest-territories
    alabama alaska arizona arkansas california colorado connecticut delaware
    florida georgia hawaii idaho illinois indiana iowa kansas kentucky louisiana
    maine maryland massachusetts michigan minnesota mississippi missouri montana
    nebraska nevada new-hampshire new-jersey new-mexico new-york north-carolina
    north-dakota ohio oklahoma oregon pennsylvania rhode-island south-carolina
    south-dakota tennessee texas utah vermont virginia washington west-virginia
    wisconsin wyoming
    """.split()
)


def _words(span: str) -> list[str]:
    return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", span.lower())


# Places inside the clinic, phone extensions and lot numbers are not addresses.
_NOT_PLACE = re.compile(
    r"(?i)^(?:ext|extension|x|poste|ext\.|wewn|room|rm|suite|ste|boardroom|office|bureau|"
    r"sala|salle|pokój|lot|lote|front\s+desk|reception|שלוחה|חדר)\b"
)


def _keep(t: EntityType, span: str) -> bool:
    words = _words(span)
    if t is EntityType.NAME:
        # Names have no digits ("embryo 1") and are rarely more than four words.
        if any(ch.isdigit() for ch in span) or len(words) > 4:
            return False
        # One letter is an initial or a list marker ("Reply C"), not a name alone;
        # several are a name spelled out ("K O W").
        if sum(len(w) == 1 for w in words) >= 2:
            return True
        if any(w in _DRUGS or re.sub(r"^[ולבמשה]", "", w) in _DRUGS for w in words):
            return False
        return any(w not in _NOT_NAME_WORDS and len(w) > 1 for w in words)
    if t is EntityType.ADDRESS:
        if _NOT_PLACE.match(span.strip()):
            return False
        # Bare numbers ("401", "ext 214") are not places; nor are provinces/states.
        if not any(ch.isdigit() for ch in span) and not words:
            return False
        if not re.search(r"[^\W\d_]{2,}", span):
            return False
        return "-".join(words) not in _REGIONS
    if t is EntityType.EMPLOYER:
        # A workplace is identifying only when it is named: "the clinic" is not.
        return any(ch.isupper() for ch in span) or len(words) >= 3
    return True


@dataclass
class GlinerDetector:
    """Local NER detector for names, places and workplaces.

    ``threshold`` is deliberately low: a missed name is a disclosure, while an
    extra mask only costs the model a little context.
    """

    name: str = "gliner"
    model: Any = DEFAULT_MODEL  # model id, local path, or a loaded GLiNER instance
    labels: dict[str, EntityType] = field(default_factory=lambda: dict(DEFAULT_LABELS))
    threshold: float = 0.4
    # GLiNER reads at most a few hundred words at once; longer text is cut into
    # overlapping windows so an entity on a boundary is still seen whole.
    window_words: int = 200
    overlap_words: int = 40
    device: Optional[str] = None  # e.g. "cuda", "mps"; default CPU

    def __post_init__(self) -> None:
        if isinstance(self.model, str):
            from gliner import GLiNER  # type: ignore[import-not-found]

            self.model = GLiNER.from_pretrained(self.model)
            if self.device:
                self.model = self.model.to(self.device)
        if self.overlap_words >= self.window_words:
            raise ValueError("overlap_words must be smaller than window_words")

    def detect(self, text: str) -> list[Entity]:
        out: list[Entity] = []
        seen: set[tuple[int, int, EntityType]] = set()
        label_names = list(self.labels)
        for offset, chunk in _windows(text, self.window_words, self.overlap_words):
            for p in self.model.predict_entities(chunk, label_names, threshold=self.threshold):
                t = self.labels.get(p["label"])
                if t is None:
                    continue
                start, end = offset + p["start"], offset + p["end"]
                span = text[start:end]
                if t is EntityType.NAME and is_clinician(text, start, end):
                    # "Dr. Wójcik", "Rohan Iyer, MD": a clinician, not the patient.
                    t = EntityType.PROVIDER
                if (start, end, t) in seen or len(span.strip()) < 2 or not _keep(t, span):
                    continue
                seen.add((start, end, t))
                out.append(Entity(t, start, end, span, self.name, float(p["score"])))
        return out


def _windows(text: str, size: int, overlap: int) -> list[tuple[int, str]]:
    """Split text into (char offset, chunk) windows of ``size`` words."""
    words = list(_WORD.finditer(text))
    if len(words) <= size:
        return [(0, text)]
    out = []
    step = size - overlap
    for i in range(0, len(words), step):
        group = words[i : i + size]
        start, end = group[0].start(), group[-1].end()
        out.append((start, text[start:end]))
        if i + size >= len(words):
            break
    return out
