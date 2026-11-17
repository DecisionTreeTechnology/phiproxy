"""Policy.staff: the clinic's staff pass unmasked, patients who share their names do not."""

import re

import pytest

from phiproxy import KnownEntities, Masker, Policy, RegexDetector
from phiproxy.detectors.gliner import GlinerDetector

STAFF = ["Jocelyn Paré", "Will Barnes", "Grace Okoye", "Carla Benitez", "Daniel Hsu",
         "Tara Kowalski", "Miguel Reyes", "Jon Pratt", "Sunny Park", "Renee Albright"]


class EveryCapitalizedWord:
    """Stand-in model that tags the listed names as people."""

    def __init__(self, names):
        self.names = names

    def predict_entities(self, text, labels, threshold=0.5):
        out = []
        for n in self.names:
            for m in re.finditer(re.escape(n), text):
                out.append({"start": m.start(), "end": m.end(), "label": "person", "score": 0.9})
        return out


def mask(text, names, staff=STAFF, known=None, **kw):
    m = Masker(
        detectors=[RegexDetector(), GlinerDetector(model=EveryCapitalizedWord(names))],
        policy=Policy(staff=staff, **kw),
    )
    return m.mask(text, "s", known=known).text


@pytest.mark.parametrize(
    "text,name",
    [
        ("Refund was promised by Jocelyn in billing on 10/02.", "Jocelyn"),
        ("Will from the lab will cover the retrieval list.", "Will"),
        ("AGENT: Billing, this is Jon.\nCALLER: hi Jon, about my invoice", "Jon"),
        ("AGENT: Harborview, Grace speaking.", "Grace"),
        ("Please verify and call Hsu at ext. 2240.", "Hsu"),
        ("yes our counsellor renee has openings", "renee"),
        ("Vitrified 5 on straws. Sig: T. Kowalski", "T. Kowalski"),
        ("tank 3 canister B. Sig: T. Kowalski, M. Reyes", "M. Reyes"),
        ("On Mon, Mar 9, Carla Benitez wrote:", "Carla Benitez"),
        ("Grace, our new front-desk coordinator, starts Monday.", "Grace"),
        ("CALLER: hi can I speak to will?", "will"),
    ],
)
def test_staff_pass(text, name):
    assert name in mask(text, [name])


@pytest.mark.parametrize(
    "text,name",
    [
        ("I'm messaging for my daughter Sunny Dhillon (she's 19)", "Sunny Dhillon"),
        ("Sunny started her shots yesterday", "Sunny"),  # no staff cue: could be a patient
        ("hi its will and my partner rosa is the patient", "will"),
        ("Grace is my surrogate", "Grace"),
        ("Witness: Carla Mendes", "Carla Mendes"),  # not on the list
    ],
)
def test_patients_who_share_staff_names_stay_masked(text, name):
    assert name not in mask(text, [name])


def test_record_match_stays_masked_even_with_a_cue():
    known = KnownEntities(names=["Jocelyn Paré"])
    out = mask("Jocelyn Paré in billing called", ["Jocelyn Paré"], known=known)
    assert "Jocelyn" not in out


def test_cue_once_covers_other_mentions_in_the_message():
    text = "Agent: thank you for calling lakeview fertility this is carla\nCaller: hi carla it's faith"
    out = mask(text, ["carla"])
    assert out.count("carla") == 2


def test_without_context_first_names_pass_anywhere():
    assert "Sunny" in mask("Sunny started her shots", ["Sunny"], staff_need_context=False)


def test_no_staff_list_changes_nothing():
    assert "Jocelyn" not in mask("Jocelyn in billing", ["Jocelyn"], staff=())


def test_initials_accents_and_new_cues():
    from phiproxy.entities import Entity, EntityType
    from phiproxy.staff import StaffList

    staff = StaffList(["Chris Nakamura", "Felix Moreau", "Will Thornbury", "Lior Ben-David", "Hannah Wolfe"])

    def ok(text, name):
        i = text.index(name)
        e = Entity(EntityType.NAME, i, i + len(name), name, "gliner")
        return staff.passes(text, e, set())

    assert ok("Signed C. Nakamura today", "C. Nakamura")
    assert ok("ask Nakamura, C about it", "Nakamura, C")
    assert ok("thanks Chris N for the help", "Chris N")
    assert not ok("my son T. Nakamura is coming", "T. Nakamura")
    assert ok("Merci à Félix Moreau", "Félix Moreau")
    assert ok("Will is covering my retrievals", "Will")
    assert ok("Lior cubre la vitrificación", "Lior")
    assert ok("I left 2 voicemails with Chris. Not ok", "Chris")
    assert ok("Pani Hannah z recepcji mówiła", "Pani Hannah")
    assert not ok("Will is picking me up", "Will")
