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


def test_ocr_numbers():
    d = RegexDetector()

    def found(t):
        return {(e.type, e.text) for e in d.detect(t)}

    assert (T.PHONE, "613-555-O188") in found("fax 613-555-O188  P.1")
    assert (T.PHONE, "6O4-555-Ol74") in found("Tel: 6O4-555-Ol74")
    assert (T.DATE, "O9/Ol/199O") in found("DOB: O9/Ol/199O")
    assert (T.HEALTH_CARD, "9l42 337 O58") in found("PHN 9l42 337 O58")
    assert not found("Room I0 is on level 2, see Ollie")


def test_international_ids():
    d = RegexDetector()

    def types(t):
        return {e.type for e in d.detect(t)}

    assert T.ID in types("CURP: FUSD880412MDFNLN07")
    assert T.ID in types("DNI 50812345K")
    assert T.ID in types("n° sécu 2 90 03 75 112 233 45")
    assert T.PHONE in types("Rappelez-moi au 06 55 50 01 23")
    assert T.IP_ADDRESS in types("login from 2001:db8:4a1c::17")
    assert T.POSTAL_CODE in types("ul. Długa 17/4, 31-147 Kraków")
    assert T.POSTAL_CODE in types("12 rue Sainte-Catherine, 33000 Bordeaux")
    assert T.DATE in types("נולדתי כ״ג בחשוון תשנ״א")
    assert not types("the visit is at 10:30:00 and costs 12-150")


def test_spoken_more():
    d = RegexDetector()

    def found(t):
        return {(e.type, e.text) for e in d.detect(t)}

    assert (T.NAME, "K as in kilo O W A L C H U K") in found("that's K as in kilo O W A L C H U K um")
    assert (T.NAME, "H A, N G U Y E N") in found("that's H A, N G U Y E N, my email")
    assert any(t is T.EMAIL for t, _ in found("my email is ha dot nguyen dot eighty eight at example dot net"))
    assert (T.PHONE, "604... 555... 0164") in found("call me back at 604... 555... 0164")
    assert not found("the right side has a nineteen, eighteen and two sixteens, the left has a seventeen")


def test_answers_to_a_question_in_pieces():
    d = RegexDetector()
    call = (
        "Agent: Can I get your date of birth?\n"
        "Caller: fourteen oh seven eighty nine\n"
        "Agent: Sorry, July fourteenth?\n"
        "Caller: Yeah July one four, eighty nine\n"
        "Agent: Got it. You're at seven fifteen, check in at six forty five.\n"
        "Agent: What's a good callback number?\n"
        "Caller: five oh three... five oh three, five five five, zero... sorry, zero one four zero.\n"
        "Agent: Can I get your postal code to verify?\n"
        "Caller: Uh it's V five K one... wait\n"
        "Caller: Hi, I have an appointment on the eighteenth with Doctor Bhatt.\n"
        "Agent: the only openings are the twenty-fourth at two or the twenty-sixth at nine.\n"
        "Caller: Twenty-sixth please.\n"
        "Agent: The second embryo looks good, and the third one too."
    )
    found = {(e.type, e.text) for e in d.detect(call)}
    assert (T.DATE, "fourteen oh seven eighty nine") in found
    assert (T.DATE, "July one four, eighty nine") in found
    assert (T.PHONE, "zero one four zero") in found
    assert any(t is T.POSTAL_CODE and "V five K one" in x for t, x in found)
    for day in ("the eighteenth", "the twenty-fourth", "the twenty-sixth", "Twenty-sixth"):
        assert (T.DATE, day) in found
    texts = " ".join(x for _, x in found)
    assert "seven fifteen" not in texts and "six forty five" not in texts
    assert "second" not in texts and "third" not in texts


def test_v5_formats():
    d = RegexDetector()

    def found(t):
        return {(e.type, e.text) for e in d.detect(t)}

    assert any("A as in apple" in x for _, x in found("claim number A as in apple, seven seven two zero, nine one five"))
    assert (T.HEALTH_CARD, "BSH9017734412") in found("Member ID: BSH9017734412")
    assert (T.URL, "gofundme.example.com/f/baby-moreau-ivf") in found("see gofundme.example.com/f/baby-moreau-ivf")
    assert (T.ACCOUNT, "PL61 1090 1014 0000 0712 1981 2874") in found("IBAN PL61 1090 1014 0000 0712 1981 2874")
    assert any(t is T.ID for t, _ in found("envelope 7c1e44a0-9b2f-4d1c-8e77-20f5d3a1b6c9"))
    assert any("23 de abril del 90" in x for _, x in found("nací el 23 de abril del 90"))
    assert (T.DATE, "abril cuatro del ochenta y seis") in found("es abril cuatro del ochenta y seis")
    assert (T.DATE, "jedenasty listopada osiemdziesiąt dziewięć") in found("jedenasty listopada osiemdziesiąt dziewięć")
    assert not found("CPT 58970 and NDC 0052-0316-10, call ext 2210, as in the past")


def test_amounts_and_times_are_not_identifiers():
    d = RegexDetector()
    call = (
        "Agent: Date of birth?\nCaller: Six, nineteen, eighty-five.\n"
        "Agent: openings Tuesday at eight thirty or nine fifteen.\nCaller: Tuesday eight thirty.\n"
        "Agent: A frozen cycle starts at nineteen thousand five hundred, fresh around thirty-two thousand.\n"
        "Agent: The balance is six hundred twelve dollars."
    )
    texts = [e.text for e in d.detect(call)]
    assert any("Six, nineteen, eighty-five" in x for x in texts)
    for bad in ("eight thirty", "nine fifteen", "nineteen thousand", "two thousand", "six hundred twelve"):
        assert not any(bad in x for x in texts), bad
    assert any("D twenty thousand" in e.text for e in d.detect("donor number D twenty thousand seven seventy-one"))
