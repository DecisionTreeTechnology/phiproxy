"""GlinerDetector logic with a stand-in model (no download, no torch)."""

import re

from phiproxy import EntityType as T
from phiproxy import Masker, RegexDetector
from phiproxy.detectors.gliner import GlinerDetector, _windows


class FakeModel:
    """Returns a fixed label for every listed word found in the chunk."""

    def __init__(self, spans: dict[str, str], score: float = 0.9):
        self.spans = spans
        self.score = score
        self.calls: list[str] = []

    def predict_entities(self, text, labels, threshold=0.5):
        self.calls.append(text)
        out = []
        for word, label in self.spans.items():
            if label not in labels or self.score < threshold:
                continue
            for m in re.finditer(re.escape(word), text):
                out.append({"start": m.start(), "end": m.end(), "label": label, "score": self.score})
        return out


def detect(spans, text, **kw):
    g = GlinerDetector(model=FakeModel(spans), **kw)
    return {(e.type, e.text) for e in g.detect(text)}


def test_maps_labels_to_types():
    found = detect(
        {"ravi": "person", "Sudbury": "city", "Tim Hortons": "employer"},
        "my husband ravi works at Tim Hortons in Sudbury",
    )
    assert found == {(T.NAME, "ravi"), (T.ADDRESS, "Sudbury"), (T.EMPLOYER, "Tim Hortons")}


def test_drops_pronouns_roles_and_greetings():
    spans = {"we": "person", "my husband": "person", "Patient": "person", "hi": "person",
             "embryo 1": "person", "Ontario": "city", "401": "city", "clinic": "employer"}
    assert detect(spans, "hi, we and my husband (Patient) saw embryo 1 at the clinic on the 401 in Ontario") == set()


def test_threshold_is_passed_to_the_model():
    g = GlinerDetector(model=FakeModel({"ravi": "person"}, score=0.3), threshold=0.4)
    assert g.detect("ravi") == []


def test_long_text_is_windowed_with_offsets_intact():
    text = " ".join(["word"] * 500) + " Katarzyna " + " ".join(["word"] * 10)
    model = FakeModel({"Katarzyna": "person"})
    g = GlinerDetector(model=model, window_words=200, overlap_words=40)
    found = g.detect(text)
    assert len(model.calls) > 1
    assert [(e.type, text[e.start : e.end]) for e in found] == [(T.NAME, "Katarzyna")]


def test_windows_cover_every_word():
    text = " ".join(f"w{i}" for i in range(450))
    covered = set()
    for offset, chunk in _windows(text, 200, 40):
        assert text[offset : offset + len(chunk)] == chunk
        covered.update(chunk.split())
    assert covered == set(text.split())


def test_model_guess_on_a_clinician_is_not_masked():
    g = GlinerDetector(model=FakeModel({"Dr. Haddad": "person", "Sarah": "person"}))
    m = Masker(detectors=[RegexDetector(), g])
    out = m.mask("Dr. Haddad will call Sarah", "s").text
    assert out == "Dr. Haddad will call [NAME_1]"


def test_drops_speaker_labels_and_role_words_in_other_languages():
    spans = {"Appelante": "person", "Persona que llama": "person", "mi mamá": "person",
             "Estimados pacientes": "person", "Reply C": "person", "pani Nadii": "person",
             "K O W": "person"}
    text = ("Appelante: oui\nPersona que llama: sí, mi mamá\nEstimados pacientes,\n"
            "Reply C to cancel. Dziękujemy pani Nadii! CALLER: K O W.")
    assert detect(spans, text) == {(T.NAME, "pani Nadii"), (T.NAME, "K O W")}


def test_person_with_a_title_or_credential_is_a_clinician():
    spans = {"dr Wójcik": "person", "wójcika": "person", "Rohan Iyer": "person",
             "Panie doktorze Okafor": "person", "N. Haddad": "person", "Ewa Nowak": "person",
             "Sarah": "person"}
    text = ("dr Wójcik kazała, wizyta u doktora wójcika. Rohan Iyer, MD\n"
            "Panie doktorze Okafor. - N. Haddad RN\nlek. Ewa Nowak\nSarah called")
    found = detect(spans, text)
    assert {x for x in found if x[0] is T.NAME} == {(T.NAME, "Sarah")}
    assert len({x for x in found if x[0] is T.PROVIDER}) == 6


def test_extensions_rooms_and_lots_are_not_places():
    spans = {"ext. 2240": "city", "extension two zero four": "city", "Room 108": "city",
             "boardroom A": "city", "lot 4412-C": "city", "front desk": "city", "Sudbury": "city"}
    text = ("call ext. 2240 or extension two zero four, Room 108, boardroom A, "
            "lot 4412-C at the front desk. I live in Sudbury")
    assert detect(spans, text) == {(T.ADDRESS, "Sudbury")}
