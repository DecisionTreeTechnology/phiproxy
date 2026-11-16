from datetime import date

from phiproxy import EntityType as T
from phiproxy import KnownEntities, KnownEntityDetector


def found(text, **known):
    return {(e.type, e.text) for e in KnownEntityDetector(KnownEntities(**known)).detect(text)}


def test_full_and_partial_names_any_case():
    hits = found("hi this is SARAH chen, sarah here again", names=["Sarah Chen"])
    assert (T.NAME, "SARAH chen") in hits
    assert (T.NAME, "sarah") in hits


def test_one_typo_in_name():
    assert (T.NAME, "Sara") in found("Sara here", names=["Sarah Chen"])
    assert (T.NAME, "Jenifer") in found("this is Jenifer", names=["Jennifer Wu"])


def test_possessive_keeps_suffix_outside():
    hits = found("Sarah's appointment", names=["Sarah Chen"])
    assert (T.NAME, "Sarah") in hits


def test_common_word_names_need_capital():
    assert found("I have hope it works", names=["Hope Adams"]) == set()
    assert (T.NAME, "Hope") in found("Hope here", names=["Hope Adams"])


def test_canonical_spelling_from_record():
    e = [x for x in KnownEntityDetector(KnownEntities(names=["Sarah Chen"])).detect("sara") if x.type is T.NAME][0]
    assert e.value == "Sarah"


def test_phone_any_format():
    for text in ["416-555-0142", "(416) 555 0142", "+1.416.555.0142", "4165550142"]:
        assert (T.PHONE, text) in found(f"call {text} ok", phones=["416 555 0142"])


def test_dob_variants():
    for text in ["1990-03-05", "3/5/1990", "03/05/1990", "March 5, 1990", "5 Mar 1990", "Mar 5"]:
        assert (T.DATE, text) in found(f"dob {text}.", dates_of_birth=[date(1990, 3, 5)])


def test_identifier_ignores_spacing():
    assert (T.ID, "1234 567 890 ab") in found("card 1234 567 890 ab", identifiers=["1234-567-890-AB"])


def test_from_dict():
    k = KnownEntities.from_dict({"names": "Ana Diaz", "phones": ["6475550100"]})
    assert list(k.names) == ["Ana Diaz"] and not k.is_empty()
