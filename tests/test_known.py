from datetime import date

import pytest

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


def test_hebrew_names_prefixes_and_scripts():
    from phiproxy.detectors.known import KnownEntityDetector

    def found(rec, text):
        return [e.text for e in KnownEntityDetector(KnownEntities(names=rec)).detect(text)]

    assert found(["שירה אברהמי"], "שירה מרגישה מצוין. שירה ואיתי") == ["שירה", "שירה"]
    assert found(["מיכל בן-דוד"], "שלום ומיכל") == ["מיכל"]
    assert found(["Noa Ben-Ami"], "אשתי, נועה, ולנועה") == ["נועה", "נועה"]
    assert found(["נועה רוזנברג"], "Noa called") == ["Noa"]
    assert found(["Michał Kowalczyk"], "Michał i Michała") == ["Michał", "Michała"]
    assert found(["Anna Kowalska"], "Kowalska-Nowak") == ["Kowalska"]
    assert found(["מיכל כהן"], "מיכאל הגיע") == []  # no fuzzy matching in Hebrew


def test_hebrew_places():
    from phiproxy import RegexDetector, EntityType

    def places(t):
        return [e.text for e in RegexDetector().detect(t) if e.type is EntityType.ADDRESS]

    assert places("אנחנו עוברים לטורונטו באוגוסט") == ["טורונטו"]
    assert places("אני גרה בפתח תקווה") == ["פתח תקווה"]
    assert places("נולדתי בחיפה, גרה בתל אביב") == ["חיפה", "תל אביב"]
    assert places("ברחובות העיר") == []


def test_short_hebrew_name_parts_are_words():
    from phiproxy.detectors.known import KnownEntityDetector

    found = [e.text for e in KnownEntityDetector(KnownEntities(names=["מיכל בן-דוד"])).detect("הבן שלי בא")]
    assert found == []


@pytest.mark.parametrize(
    "text,names",
    [
        ("תודה ענקית לד\"ר נוואסו.\n\nשירה ואיתי\nרחוב באת'רסט 3200", {"שירה", "איתי"}),
        ("ואם אני לא עונה אז לבעלי גיל, 973-555-0189", {"גיל"}),
        ("עורכת הדין שלי היא עו\"ד אורית בן חיים, טלפון", {"אורית בן חיים"}),
        ("הורים מיועדים איתי שגב ונדב רוזן (אזרחי ישראל)", {"איתי שגב", "נדב רוזן"}),
        ("אנחנו טל ואלון לוי, מנתניה.", {"טל", "אלון לוי"}),
        ("תודה! אני ועומר נוסעים בדצמבר", {"עומר"}),
        ("הפגישה בקונסוליה בתאריך 25.12.2026.\n\nטל", {"טל"}),
    ],
)
def test_hebrew_names_in_context(text, names):
    from phiproxy import RegexDetector

    found = {e.text for e in RegexDetector().detect(text) if e.type.value == "NAME"}
    assert names <= found


@pytest.mark.parametrize("text", ["קיבלתי טל ואור בבוקר", "גיל 35, AMH נמוך", "בדיקות דם ושתן בבוקר"])
def test_hebrew_words_that_are_names_stay_words(text):
    from phiproxy import RegexDetector

    assert not [e for e in RegexDetector().detect(text) if e.type.value == "NAME"]


def test_hebrew_pair_after_doctor_title_is_not_patients():
    from phiproxy.detectors import _names

    assert _names.hebrew_names("עוזר: כן! ד״ר נועה פרידמן ויעל מזרחי מדברות עברית.") == []
