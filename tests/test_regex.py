import pytest

from phiproxy import EntityType as T
from phiproxy import RegexDetector


def types_in(text):
    return {(e.type, e.text) for e in RegexDetector().detect(text)}


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("email me at jane.doe+ivf@example.org thanks", T.EMAIL, "jane.doe+ivf@example.org"),
        ("call 416-555-0142 please", T.PHONE, "416-555-0142"),
        ("call (416) 555-0142", T.PHONE, "(416) 555-0142"),
        ("cell +1 416 555 0142", T.PHONE, "+1 416 555 0142"),
        ("my number 4165550142", T.PHONE, "4165550142"),
        ("whatsapp +44 20 7946 0958", T.PHONE, "+44 20 7946 0958"),
        ("SSN 123-45-6789", T.SSN, "123-45-6789"),
        ("SIN 046 454 286", T.SIN, "046 454 286"),
        ("OHIP 1234-567-890-AB", T.HEALTH_CARD, "1234-567-890-AB"),
        ("my health card is 9876543210", T.HEALTH_CARD, "9876543210"),
        ("RAMQ ABCD 1234 5678", T.HEALTH_CARD, "ABCD 1234 5678"),
        ("MRN: 00482913", T.MRN, "00482913"),
        ("chart # A-77123", T.MRN, "A-77123"),
        ("donor ID D-4521", T.DONOR_ID, "D-4521"),
        ("embryo code EMB-0091", T.DONOR_ID, "EMB-0091"),
        ("policy number: XK-99812", T.ACCOUNT, "XK-99812"),
        ("retrieval 2026-11-03", T.DATE, "2026-11-03"),
        ("seen 11/03/2026", T.DATE, "11/03/2026"),
        ("born March 5, 1990", T.DATE, "March 5, 1990"),
        ("on the 3rd of May", T.DATE, "3rd of May"),
        ("transfer Nov 8th", T.DATE, "Nov 8th"),
        ("come in 3/14", T.DATE, "3/14"),
        ("grandma is 93 years old", T.AGE, "93 years old"),
        ("I live at 22 Elm Street, apt 4", T.ADDRESS, "22 Elm Street, apt 4"),
        ("PO Box 1234", T.ADDRESS, "PO Box 1234"),
        ("postal code M5V 2T6", T.POSTAL_CODE, "M5V 2T6"),
        ("Austin, TX 78701", T.ZIP, "78701"),
        ("see https://portal.example.com/p/123", T.URL, "https://portal.example.com/p/123"),
        ("from 10.20.30.40", T.IP_ADDRESS, "10.20.30.40"),
        ("Hi, this is Maria Lopez", T.NAME, "Maria Lopez"),
        ("my husband Dave will drive", T.NAME, "Dave"),
        ("My partner's name is Alex", T.NAME, "Alex"),
        ("Thanks, Priya", T.NAME, "Priya"),
        ("Dr. Patel said", T.PROVIDER, "Patel"),
    ],
)
def test_detects(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "I may come in on day 3",  # "may" lowercase is not a month
        "we did 2 rounds in 2025",  # year alone is not PHI
        "she is 34 years old",  # ages under 90 are not PHI
        "this is Tuesday right?",  # weekday is not a name
        "thanks so much",  # lowercase after "thanks" is not a name
        "take 2 tablets at 8pm",
        "ref 123 456 789 on the invoice",  # nine digits, fails Luhn, no SIN keyword
    ],
)
def test_ignores(text):
    assert types_in(text) == set()


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("my number is four one six five five five zero one four two", T.PHONE,
         "four one six five five five zero one four two"),
        ("date of birth march fifteenth 1988", T.DATE, "march fifteenth 1988"),
        ("the twenty first of may", T.DATE, "twenty first of may"),
        ("is donor D-8270 still available", T.DONOR_ID, "D-8270"),
        ("the health card is 1 2 3 4 5 6 7 8 9 0", T.HEALTH_CARD, "1 2 3 4 5 6 7 8 9 0"),
    ],
)
def test_detects_spoken_forms(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text,etype,value",
    [
        # Dates with weekdays, ordinals only, other formats and languages.
        ("can we do Saturday, November 22?", T.DATE, "Saturday, November 22"),
        ("move it to thurs nov 6", T.DATE, "thurs nov 6"),
        ("see you Monday the 9th", T.DATE, "Monday the 9th"),
        ("is the 19th ok", T.DATE, "the 19th"),
        ("DOB 14-AUG-1990", T.DATE, "14-AUG-1990"),
        ("prévu pour 2027-03", T.DATE, "2027-03"),
        ("née le 12 mai 1990", T.DATE, "le 12 mai 1990"),
        ("rendez-vous le 1er décembre", T.DATE, "le 1er décembre"),
        ("cita el jueves 6 de noviembre", T.DATE, "el jueves 6 de noviembre"),
        ("wizyta 12 listopada", T.DATE, "12 listopada"),
        ("הבדיקה מה5 בנובמבר", T.DATE, "5 בנובמבר"),
        # Identifier-shaped codes without a keyword.
        ("my booking is BK-882013", T.ID, "BK-882013"),
        ("straw CB-20418-S3 thawed", T.ID, "CB-20418-S3"),
        ("member W123456789", T.ID, "W123456789"),
        ("chart 0048213 attached", T.ID, "0048213"),
        ("card 4539 1488 0343 6467", T.ACCOUNT, "4539 1488 0343 6467"),
        # Spoken forms in other languages and spelled-out names.
        ("c'est cinq un quatre cinq cinq cinq zéro un huit quatre", T.PHONE,
         "cinq un quatre cinq cinq cinq zéro un huit quatre"),
        ("es nueve cero cinco cinco cinco cinco cero uno dos siete", T.PHONE,
         "nueve cero cinco cinco cinco cinco cero uno dos siete"),
        ("its chen dot wei at example dot com", T.EMAIL, "chen dot wei at example dot com"),
        ("thats k o w a l c z y k", T.NAME, "k o w a l c z y k"),
        ("W-O-J-C-I-K", T.NAME, "W-O-J-C-I-K"),
        ("postal code n one h four k seven", T.POSTAL_CODE, "n one h four k seven"),
        ("profile instagram.com/jess.and.the.tww", T.URL, "instagram.com/jess.and.the.tww"),
        ("Pt Margaret Hollis, age 91.", T.AGE, "91"),
        # Courtesy titles are people, not clinicians.
        ("Mrs. Okafor called", T.NAME, "Okafor"),
        ("Dre Lefebvre a confirmé", T.PROVIDER, "Lefebvre"),
    ],
)
def test_detects_v1_shapes(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "Gonal-f 150 IU and Menopur 75 tonight",
        "embryo graded 4AA, AMH 1.2, E2 2450 pmol/L",
        "CPT 58970 is $450, call ext 214",
        "COVID-19 rules, PGT-A results",
        "the donor says hi",  # keyword followed by a word, not a code
        "account overdue",
        "sent from my iPhone",
    ],
)
def test_ignores_v1_distractors(text):
    assert types_in(text) == set()


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("we live in Sudbury now", T.ADDRESS, "Sudbury"),
        ("driving in from mississauga", T.ADDRESS, "mississauga"),
        ("moved to Normal, IL", T.ADDRESS, "Normal"),
        ("j'habite à Laval", T.ADDRESS, "Laval"),
        ("mieszkam w Toronto", T.ADDRESS, "Toronto"),
        ("née le quatorze mars mille neuf cent quatre-vingt-huit", T.DATE,
         "le quatorze mars mille neuf cent quatre-vingt-huit"),
        ("nací el catorce de febrero de mil novecientos noventa y uno.", T.DATE,
         "el catorce de febrero de mil novecientos noventa y uno"),
        ("urodzona trzeciego lipca tysiąc dziewięćset osiemdziesiąty dziewiąty", T.DATE,
         "trzeciego lipca tysiąc dziewięćset osiemdziesiąty dziewiąty"),
        ("ארבעה עשר בפברואר", T.DATE, "ארבעה עשר בפברואר"),
    ],
)
def test_detects_places_and_spoken_dates(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "results in normal range",  # "Normal" is a city, but lowercase common word
        "Hamilton General lab",  # a city name without a location cue
        "see you in May",
    ],
)
def test_places_need_a_cue(text):
    assert not any(t is T.ADDRESS for t, _ in types_in(text))


@pytest.mark.parametrize(
    "text,etype,value",
    [
        # US insurance and billing text.
        ("claim 2025-118-440921 was denied", T.ACCOUNT, "2025-118-440921"),
        ("Member ID: W2291 77014   Group: 774120", T.ACCOUNT, "774120"),
        ("policy CL-778-20931, certificate 004417.", T.ACCOUNT, "004417"),
        ("try the visa 4539 5555 0142 7719", T.ACCOUNT, "4539 5555 0142 7719"),
        ("card ending 4417 got declined", T.ACCOUNT, "4417"),
        ("the card on file ends in four four one seven", T.ACCOUNT, "four four one seven"),
        ("10/14 pmt Visa xxxx7719 -500.00", T.ACCOUNT, "xxxx7719"),
        ("Billing ledger LFP-A-198803 - guarantor", T.ID, "LFP-A-198803"),
        ("my SIN is 512 483 906 for the tax receipt", T.SIN, "512 483 906"),
        ("new addr 2714 N Kedzie Ave Apt 2R Chicago 60647", T.ZIP, "60647"),
        ("Código postal: 60608", T.ZIP, "60608"),
        ("Agent: and the billing zip\nCaller: six oh six five seven", T.ZIP, "six oh six five seven"),
        ("טל' 03-555-0147", T.PHONE, "03-555-0147"),
        ("medical record number\nCaller: four eight two nine one seven", T.ID, "four eight two nine one seven"),
        ("we reserved donor c b one zero four seven two from the bank", T.ID, "c b one zero four seven two"),
        # Ages over 89 without "years old".
        ("i'm ninety one and i don't do the computer", T.AGE, "ninety one"),
        ("My grandmother, who is 94, wants to pay", T.AGE, "94"),
        ("Deborah's mother Esther, 92, lives with them", T.AGE, "92"),
        # More date shapes.
        ("are they both from the May 2024 retrieval?", T.DATE, "May 2024"),
        ("pour le rdv du 4 déc", T.DATE, "4 déc"),
        ("Esposo Juan Pablo la trae el 14/03 para la punción", T.DATE, "14/03"),
        ("punkcja 9.11, 12 oocytów", T.DATE, "9.11"),
        ("D0B 06/O6/1989", T.DATE, "06/O6/1989"),
        ("date of birth june six eighty nine", T.DATE, "june six eighty nine"),
        ("Caller: his is january ninth eighty five", T.DATE, "january ninth eighty five"),
        ("date of birth the fifth of may nineteen ninety two", T.DATE, "the fifth of may nineteen ninety two"),
        ("date of birth\nCaller: oh two eleven nineteen ninety one", T.DATE, "oh two eleven nineteen ninety one"),
        ("fecha de nacimiento veintiuno de agosto del ochenta y nueve", T.DATE,
         "veintiuno de agosto del ochenta y nueve"),
        ("יש לה החזרה בארבעה עשר במרץ", T.DATE, "בארבעה עשר במרץ"),
    ],
)
def test_detects_v3_shapes(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "Call our 24/7 line at ext 4410",
        "the lot number says l seven seven three nine",
        "E2 is 940 pmol/L and she is 34",
        "her BP is 92/60 today",
        "AMH 9.11 ng/mL",
    ],
)
def test_ignores_v3_lookalikes(text):
    found = {(e.type, e.text) for e in RegexDetector().detect(text)}
    assert not {f for f in found if f[0] in (T.DATE, T.AGE, T.ID, T.ACCOUNT)}, found


@pytest.mark.parametrize(
    "text",
    ["see you at 9:30 with Dr. Lal", "it's a 5 hour drive.", "25 mcg per Dr. Kaur twice daily"],
)
def test_number_then_doctor_is_not_a_street(text):
    assert not [e for e in RegexDetector().detect(text) if e.type is T.ADDRESS]


def test_street_with_unit_still_found():
    found = [e.text for e in RegexDetector().detect("new address is 78 Elm Crescent, Unit 4B, London")]
    assert any(f.startswith("78 Elm Crescent, Unit 4B") for f in found)


def test_streets_named_first_and_city():
    d = RegexDetector()

    def addr(t):
        return [e.text for e in d.detect(t) if e.type is T.ADDRESS]

    assert addr("Notre adresse : 88 rue des Érables, Saint-Jérôme") == ["88 rue des Érables, Saint-Jérôme"]
    assert addr("DIRECCIÓN: 1205 Calle Mayor, Apt 3, San Antonio") == ["1205 Calle Mayor, Apt 3, San Antonio"]
    assert addr("adres: ul. Kościuszki 12/4, Toruń") == ["ul. Kościuszki 12/4, Toruń"]
    assert "רחוב הרצל 14, חיפה" in addr("כתובת: רחוב הרצל 14, חיפה")
    assert addr("22 Pine Ridge Dr, Whitby") == ["22 Pine Ridge Dr, Whitby"]
    assert not addr("la rue est fermée, et le boulevard aussi")
    zips = [e.text for e in d.detect("DIRECCIÓN: Calle Mayor, San Antonio, 78201\nTEL") if e.type is T.ZIP]
    assert zips == ["78201"]


def test_allowed_street_and_city_pass_together():
    from phiproxy import Masker, Policy

    m = Masker(detectors=[RegexDetector()], policy=Policy(allow=["1450 West Georgia Street", "Vancouver"]))
    assert not m.detect("Visit us at 1450 West Georgia Street, Vancouver.")


def test_more_date_forms():
    d = RegexDetector()

    def dates(t):
        return [e.text for e in d.detect(t) if e.type is T.DATE]

    assert "18" in dates("confirmando mis citas del 18 y 20 de noviembre")
    assert "18" in dates("o wizytach 18 i 20 listopada")
    assert "1985 / 06 / 22" in dates("Partner DOB: 1985 / 06 / 22")
    assert any("21 décembre 85" in x for x in dates("Je suis née le 21 décembre 85. Merci"))
    assert [x.replace("le ", "") for x in dates("rendez-vous le 2 décembre 10 h")] == ["2 décembre"]
    assert "3rd day of September, 2025" in dates("Executed this 3rd day of September, 2025.")
    assert "March" in dates("We moved to Burnaby in March.")
    assert "janvier" in dates("Je déménage à Victoria en janvier")
    assert "the twelfth" in dates("we signed in September... the twelfth I think")
    assert not dates("The March for Babies walk is on Sunday, in the park")


@pytest.mark.parametrize(
    "text,typ,value",
    [
        ("mon numéro de compte c'est 77-24709, merci", "ACCOUNT", "77-24709"),
        ("mi número de cuenta es 95-72451 y el monto", "ACCOUNT", "95-72451"),
        ("application reference 29-59296. Thanks", "ACCOUNT", "29-59296"),
        ("Caller: My social is 972-22-8271. Is that ok", "SSN", "972-22-8271"),
        ("Mój nowy numer to 555 418 988. Proszę", "PHONE", "555 418 988"),
        ("Samantha B.\n2908 E Desert Willow Drive\nYuma, AZ 85360", "ADDRESS", "Yuma"),
        ("Calle Sonora 86, San Luis Río Colorado, CP 83868.", "POSTAL_CODE", "83868"),
        ("aleja Pokoju 35/45, Łódź, 64-664.", "POSTAL_CODE", "64-664"),
        ("My mother is 91 and lives with us", "AGE", "91"),
    ],
)
def test_v6_forms(text, typ, value):
    assert (typ, value) in {(e.type.value, e.text) for e in RegexDetector().detect(text)}


def test_appointment_confirmation_stays_masked():
    assert "BK-882013" in {e.text for e in RegexDetector().detect("I want to cancel. confirmation number BK-882013")}


@pytest.mark.parametrize(
    "text",
    [
        "printer on 3 is jammed again, ticket T-66136",
        "Product: hCG trigger kit, LOT T479913, NDC 89067-6591-82",
        "This is the Vietnamese interpreter, ID 20931. Patient: hi",
        "she is 95% sure",
    ],
)
def test_clinic_numbers_not_identifiers(text):
    assert not [e for e in RegexDetector().detect(text) if e.type.value in ("ID", "ACCOUNT", "ZIP", "AGE", "SIN")]


@pytest.mark.parametrize(
    "text,value",
    [
        ("prescription RX 7714402 is ready", "RX 7714402"),
        ("driver's license TX 41982776", "TX 41982776"),
        ("file number 2026-FAM-00418,", "2026-FAM-00418"),
        ("authorization number AUTH 66-120-883, valid", "AUTH 66-120-883"),
        ("dossier 500-17-123456-261 de la Cour", "500-17-123456-261"),
        ("last four of SSN xxx-xx-6291.", "xxx-xx-6291"),
        ("viajamos del 9 al 12 de diciembre", "9 al 12 de diciembre"),
        ("od 9 do 12 grudnia", "9 do 12 grudnia"),
        ("נוסעים מ-9 עד 12 בדצמבר", "9 עד 12 בדצמבר"),
        ("miembro GCM 70 4418 21, fecha", "GCM 70 4418 21"),
    ],
)
def test_v7_forms(text, value):
    assert value in {e.text for e in RegexDetector().detect(text)}


@pytest.mark.parametrize("text", ["NDC 89067-6591-82 and CPT 58970", "Ext 22401 please", "at 9 to 12 in the morning"])
def test_v7_lookalikes(text):
    assert not RegexDetector().detect(text)


@pytest.mark.parametrize(
    "text,typ,value",
    [
        ("my grandmother is ninety-three and she had breast cancer", "AGE", "ninety-three"),
        ("Her mother Abena is 91 and was admitted", "AGE", "91"),
        ("grandpa died June 2 2019 at 91, grandma still alive at 96.", "AGE", "96"),
        ("mi abuela todavía vive, tiene noventa y cuatro años", "AGE", "noventa y cuatro"),
        ("Ma grand-mère Yvrose a quatre-vingt-onze ans", "AGE", "quatre-vingt-onze"),
        ("babcia Helena Wiśniewska, lat 93, cukrzyca", "AGE", "93"),
        ("סבתא מצד אם, רחל אברהם, בת 94, סוכרת", "AGE", "94"),
        ("group number GRP 40218, valid", "ACCOUNT", "GRP 40218"),
        ("The referral number from our PCM is REF 4410-0289.", "ACCOUNT", "REF 4410-0289"),
        ("Número de cuenta para el reembolso: 0043-77120-9.", "ACCOUNT", "0043-77120-9"),
        ("Contrat : G-440219  Certificat : 0071 5583 02", "HEALTH_CARD", "0071 5583 02"),
        ("Mi pasaporte es el AAB204117. Estamos", "ID", "AAB204117"),
        ("Tracking 1Z 999 AA1 01 2345 6784. Deliver", "ID", "1Z 999 AA1 01 2345 6784"),
        ("סבא יעקב נפטר ב2.2.2020 בגיל 92", "DATE", "2.2.2020"),
        ("אני גרה עכשיו ברחוב הנביאים 8, ירושלים\nסוכן", "ADDRESS", "רחוב הנביאים 8, ירושלים"),
        ("Kraków kod 31-147 tak", "POSTAL_CODE", "31-147"),
        ("Hi I'm a grad student at Gulfstream State University and the", "EMPLOYER", "Gulfstream State University"),
        ("employer is Hamilton Steel Workers Local 1005", "EMPLOYER", "Hamilton Steel Workers Local 1005"),
        ("היא עובדת בחברת נטע טק ונמצאת בשנה", "EMPLOYER", "חברת נטע טק"),
        ("Seguro: TRICARE Prime, sponsor Cap. Raúl Armas, SSN", "NAME", "Raúl Armas"),
        ("תמר גולדשטיין, ג ו ל ד ש ט י י ן, אני", "NAME", "ג ו ל ד ש ט י י ן"),
    ],
)
def test_v8_forms(text, typ, value):
    assert (typ, value) in {(e.type.value, e.text) for e in RegexDetector().detect(text)}


@pytest.mark.parametrize(
    "text",
    ["my mom is 95% sure", "the patient is 91 kg", "I work at home most days", "she works at the moment",
     "we're working for Dr. Smith", "member since 2019", "my account has 3 visits", "account balance $1,250 due"],
)
def test_v8_lookalikes(text):
    assert not [e for e in RegexDetector().detect(text) if e.type.value in ("AGE", "EMPLOYER", "ACCOUNT", "HEALTH_CARD", "ID")]


# Found by an adversarial review of the v8 rules (each reproduced before it was fixed).
@pytest.mark.parametrize(
    "text,types",
    [
        ("My mother lives at 95 Elm Street", {"AGE"}),
        ("my mom thinks my TSH is 100", {"AGE"}),
        ("Her mother's fertility was low; AMH is 99", {"AGE"}),
        ("school is Monday to Friday", {"EMPLOYER"}),
        ("I work at Monday morning", {"EMPLOYER"}),
        ("Trabajo en Casa", {"EMPLOYER"}),
        ("pracuję w Warszawie", {"EMPLOYER"}),
        ("Je travaille au Canada", {"EMPLOYER"}),
        ("עובדת בבית חולים", {"EMPLOYER"}),
        ("עובדת בשבת", {"EMPLOYER"}),
        ("The licence fee is 100 200 300", {"ID"}),
        ("license 2024 2025 2026 renewal", {"ID"}),
        ("work permit expires in 2027", {"ID"}),
        ("passport in 3 days I travel 12 June", {"ID"}),
        ("tracking 12 packages 5 and 3", {"ID"}),
        ("Viajamos a Cabo Verde", {"NAME"}),
        ("סעיפים א ב ג ד של החוזה", {"NAME"}),
    ],
)
def test_review_false_positives(text, types):
    assert not [e for e in RegexDetector().detect(text) if e.type.value in types]


@pytest.mark.parametrize(
    "text,value",
    [
        ("I work at Costco I need time off", "Costco"),
        ("I work at TD Bank So I can't", "TD Bank"),
        ("passport number: AB 123456 expires", "AB 123456"),
        ("grandpa died June 2 2019 at 91, grandma still alive at 96.", "91"),
        ("je travaille chez Desjardins", "Desjardins"),
    ],
)
def test_review_spans(text, value):
    assert value in {e.text for e in RegexDetector().detect(text)}
