"""Identifiers read out loud in call transcripts."""

import pytest

from phiproxy import EntityType as T
from phiproxy import RegexDetector


def found(text):
    return {(e.type, e.text) for e in RegexDetector().detect(text)}


def covered(text, span):
    """True if some detection covers the whole of span."""
    i = text.index(span)
    return any(e.start <= i and i + len(span) <= e.end for e in RegexDetector().detect(text))


@pytest.mark.parametrize(
    "text,span",
    [
        # Phones in groups, compound words, pauses
        ("it's eight hundred, five five five, oh one four two", "eight hundred, five five five, oh one four two"),
        ("call me at four one six... five five five... zero one one seven", "four one six... five five five... zero one one seven"),
        ("dziewięćset pięć, pięćset pięćdziesiąt pięć, zero jeden jeden siedem",
         "dziewięćset pięć, pięćset pięćdziesiąt pięć, zero jeden jeden siedem"),
        ("cuatro uno seis... cinco cinco cinco... uno uno siete cero", "cuatro uno seis... cinco cinco cinco... uno uno siete cero"),
        ("תחזרו אליי לתשע אפס חמש חמש חמש חמש אפס אחת שבע חמש", "תשע אפס חמש חמש חמש חמש אפס אחת שבע חמש"),
        # Postal codes spelled out
        ("my postal code is T three A, four B seven", "T three A, four B seven"),
        ("kod pocztowy L pięć B, dwa K dziewięć", "L pięć B, dwa K dziewięć"),
        ("code postal H deux X, un G quatre", "H deux X, un G quatre"),
        # Health card, codes, phonetic alphabet
        ("four seven two nine dash one one eight dash three oh five and then k t",
         "four seven two nine dash one one eight dash three oh five and then k t"),
        ("member number C F seven seven eight one", "C F seven seven eight one"),
        ("it's november sierra hotel four zero zero two one eight seven seven three zero one",
         "november sierra hotel four zero zero two one eight seven seven three zero one"),
        ("donor c b dash two zero four one eight dash s three", "c b dash two zero four one eight dash s three"),
        ("four five three nine five five five five zero one four two seven seven one nine",
         "four five three nine five five five five zero one four two seven seven one nine"),
        ("the IP was one nine eight dot five one dot one hundred dot seven",
         "one nine eight dot five one dot one hundred dot seven"),
        # Street number in words
        ("send it to eighteen forty two west cermak road apartment two", "eighteen forty two west cermak road apartment two"),
    ],
)
def test_spoken_identifiers(text, span):
    assert covered(text, span)


@pytest.mark.parametrize(
    "text",
    [
        "take two hundred twenty five units at nine thirty, then one fifty tomorrow",
        "I'm thirty eight, we did one transfer in twenty twenty four",
        "she's on day five, follicles at fifteen, sixteen and eighteen",
        "E2 was one thousand two hundred and LH four point five",
        "ten thirty a.m works",
        "fax 613-555-O188  P.1",
        "no one called, I waited from nine to five",
        "un rendez-vous à neuf heures, deux ampoules",
    ],
)
def test_spoken_lookalikes(text):
    assert not [e for e in RegexDetector().detect(text) if e.type is not T.DATE]


def test_spoken_dates():
    from phiproxy import RegexDetector

    d = RegexDetector()

    def dates(t):
        return [e.text for e in d.detect(t) if e.type.value == "DATE"]

    assert dates("my date of birth is one four, oh seven, nineteen eighty-nine, ok")
    assert dates("date of birth two twenty-six, ninety-four. We need")
    assert any("ninety-one" in x for x in dates("born the third of May, ninety-one."))
    assert dates("caller: yes um can we do the twentieth instead")
    assert dates("agent: ok i have you down for the eighth / caller: no")
    assert dates("it's oh seven one four nineteen eighty nine")
    assert dates("שאיבה 12 בנוב׳ 07:30")
    assert any("תשעים" in x for x in dates("מתקשרת: עשרים ושניים בנובמבר, תשעים"))
    assert dates("can we move from dec 2 to dec 4?") == ["dec 2", "dec 4"]
    # Not dates
    assert not dates("we transferred the second embryo")
    assert not dates("this is the third time I call")
    assert not dates("it's the first, right")
    assert not dates("lot number one two three four five six seven eight")
