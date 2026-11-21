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


@pytest.mark.parametrize(
    "text,value",
    [
        # Court and agency file numbers.
        ("court file 2026DR30418. I need", "2026DR30418"),
        ("Case No. 2026PR000884 / In re", "2026PR000884"),
        ("Case number 24-DR-1183, fax", "24-DR-1183"),
        ("sygnatura II C 1184/26. Proszę", "II C 1184/26"),
        ("pod sygn. XVI RC 902/25.", "XVI RC 902/25"),
        ("תיק 12456-03-26. נא לשלוח", "12456-03-26"),
        # Prescription, licence, cédula, plate, username.
        ("Rx number 5520-1148, progesterone", "5520-1148"),
        ("Rx# 7710-4402   Filled", "7710-4402"),
        ("Colorado driver licence 99-123-4567. Address", "99-123-4567"),
        ("licencia de conducir de Colorado número 93-441-2807.", "93-441-2807"),
        ("Mi cédula es V-18.442.907 y", "V-18.442.907"),
        ("My plate is QXE-J45. The notice", "QXE-J45"),
        ("My username is hunter.bale and I can't", "hunter.bale"),
        # Health numbers named in other ways.
        ("my Alberta health care number is 53117 4429. I'm", "53117 4429"),
        ("My AHS number is 48217 6639 if the lab needs it", "48217 6639"),
        ("Voici ma carte santé comme demandé : 76341 9028.", "76341 9028"),
        ("CARTE SANTÉ AB : 402 118 337", "402 118 337"),
        ("Insur ID: HK 9920 5518 ...", "HK 9920 5518"),
        # Identifiers read one digit at a time.
        ("Hospital number 0 0 5 5 2 1 8.", "0 0 5 5 2 1 8"),
        ("Numer pacjenta 0 0 8 8 1 3 2.", "0 0 8 8 1 3 2"),
        ("מספר תיק 0 0 7 7 4 1 9.", "0 0 7 7 4 1 9"),
        # Card endings in other languages.
        ("opłacony kartą kończącą się na 4471, proszę", "4471"),
        ("la tarjeta que termina en 9027, please", "9027"),
        ("והכרטיס שלי נגמר ב-3308", "3308"),
        ("cambiar la tarjeta del plan. La nueva termina en cuatro cuatro uno siete.", "cuatro cuatro uno siete"),
        # Donors, groups, phones after a Hebrew prefix, ages, timestamps.
        ("I was told the donor was number 7719-B at the sperm bank", "7719-B"),
        ("(tank 2, canister B, straw lot ST-4402-19)", "ST-4402-19"),
        ("PL-77-340192 i grupa G4410. To", "G4410"),
        ("חזרו אליה ל303-555-0182.", "303-555-0182"),
        ("נא לשלוח פקס ל+972-50-555-0177.", "+972-50-555-0177"),
        ("מטופל: אילן סובול, בן 93\n", "93"),
        ("Pacjent: Ilona Sobczak, lat 93\nRp.", "93"),
        ('{"ts":"2026-11-16T22:41:07Z"}', "2026-11-16"),
        # Names: nicknames, greeting lines, "X and I", signatures above a phone label.
        ("Note: patient prefers to be called Mimi.", "Mimi"),
        ("Isnt that covered? I go by Kim.", "Kim"),
        ("Subject: Agreement\n\nHollis,\n\nThank you for the redline.", "Hollis"),
        ("720-555-0169\nLee and I are so grateful.", "Lee"),
        ("Quedo atenta.\n\nClaudia R.\nTel. (720) 555-0153", "Claudia R."),
        ("Cordialmente,\nHernán Giraldo", "Hernán Giraldo"),
        ("AI summary: Caller Liezel Santos (anak Aya) asked", "Aya"),
        ("Tôi gọi về vợ Lan của tôi", "Lan"),
    ],
)
def test_v9_spans(text, value):
    assert value in {e.text for e in RegexDetector().detect(text)}


@pytest.mark.parametrize(
    "text,types",
    [
        ("Usuario: hola, quiero una cita", {"ID"}),
        ("I forgot my username and password", {"ID"}),
        ("Confirmation number is 7 7 4 1 0 9.", {"ID"}),
        ("sent me Ganirelix twice and no Menopur and I trigger in two days", {"NAME"}),
        ("Warmly,\nthe team", {"NAME"}),
        ("Cordialmente,\nHernán Giraldo", set()),
        ("Kochani,\n\nspotkanie zespołu w piątek", {"NAME"}),
        ("Hello,\n\nPlease find attached", {"NAME"}),
        ("Plate 2 of 4 in the incubator", {"ID"}),
        ("a 96-well plate, lot 4471", {"ID", "ACCOUNT"}),
        ("Rx: 30 mL, refills 2", {"ID"}),
        ("The licence fee is 100 200 300", {"ID"}),
        ("We met on 2026-03-26 at noon", {"ID"}),
    ],
)
def test_v9_lookalikes(text, types):
    found = [e for e in RegexDetector().detect(text) if e.type.value in types]
    if text.startswith("Cordialmente"):
        found = [e for e in RegexDetector().detect(text) if e.text == "Cordialmente"]
    assert not found


@pytest.mark.parametrize(
    "text",
    [
        "the plate 3B1 was contaminated",
        "plate A4 well 12",
        "termina en 2026 el contrato",
        "Kończąca się na 2026 umowa",
        "health card number: please bring it, appointment at 10 30 11 2026",
        "Insur ID card scanned on 11 03 2026",
        "login is broken since 11:30",
        "login: failed attempt count 3",
        "Menopur,\n\nTake daily",
        "Egg Retrieval,\n\nis scheduled",
        "the protocol known as Antagonist",
        "a drug known as Clomid",
        "went by Walgreens",
        "le dicen Metformina",
        "Cordialmente,\nRecepción",
        "Atentamente,\nRecursos Humanos",
        "Warmly,\nFertility Clinic",
        "Last name: Unknown",
        "Case 2026 was hard",
    ],
)
def test_v9_review_false_positives(text):
    assert not RegexDetector().detect(text)


@pytest.mark.parametrize(
    "text,value",
    [
        ("My OHIP is ab1234567890 thanks", "ab1234567890"),
        ("Health card number:\nH 1234 5678", "H 1234 5678"),
        ("My OHIP\nAB 1234 567 890", "AB 1234 567 890"),
        ("My AHS number is 48217 6639 if needed", "48217 6639"),
        ("Respectfully,\nClaudia Ramos", "Claudia Ramos"),
        ("Z wyrazami szacunku,\nAnna Kowalska", "Anna Kowalska"),
        ("You can call me Kim.", "Kim"),
        ("Mi apodo es Paty", "Paty"),
        ("Appelez-moi Kim", "Kim"),
        ("Subject: x\r\n\r\nHollis,\r\n\r\nThank you", "Hollis"),
        ("Lee & I are grateful.", "Lee"),
        ("my card ending with 4471", "4471"),
        ("karta kończy się na 4471", "4471"),
        ("tarjeta, últimos cuatro dígitos 4471", "4471"),
        ("Hospital number 0-0-5-5-2-1-8", "0-0-5-5-2-1-8"),
        ("Hospital number 0, 0, 5, 5, 2, 1, 8", "0, 0, 5, 5, 2, 1, 8"),
        ("my username for the portal is hunter.bale", "hunter.bale"),
        ("usuario: mgarcia88", "mgarcia88"),
        ("My plate is WE 12345", "WE 12345"),
        ("tablica rejestracyjna KR 1234A", "KR 1234A"),
        ("Rx number is 5520-1148", "5520-1148"),
        ("sygn. akt II C 1184/2026", "II C 1184/2026"),
        ("Case no. 26-D-1183", "26-D-1183"),
        ("dawca nr 4410", "4410"),
        ("cédula 18.442.907", "18.442.907"),
    ],
)
def test_v9_review_spans(text, value):
    assert value in {e.text for e in RegexDetector().detect(text)}


@pytest.mark.parametrize(
    "text,value",
    [
        # Round-2 review: privacy regressions from round-1 fixes stay fixed.
        ("Mon numéro est +33 6 12 34 56 78", "+33 6 12 34 56 78"),
        ("Hi, I'm Aisha Khan Results came back", "Aisha Khan"),
        ("Name: Semen Kovalenko\nDOB: 1990-02-14", "Semen Kovalenko"),
        ("Thanks,\nRachel Bank", "Rachel Bank"),
        ("My name is Dan Center", "Dan Center"),
        # Round-2 review: variants.
        ("my username is jsmith", "jsmith"),
        ("username (portal): hunter.bale", "hunter.bale"),
        ("last 4 digits of my card: 4471", "4471"),
        ("mi tarjeta acaba en 4471", "4471"),
        ("ostatnie 4 cyfry karty: 4471", "4471"),
        ("Visa ****4471", "****4471"),
        ("I am known as Kim", "Kim"),
        ("Je me fais appeler Mimi", "Mimi"),
        ("Subject: x\n\nHollis,\n\nQuick question", "Hollis"),
        ("donante nº 4410", "4410"),
        ("numer dawcy 4410", "4410"),
        ("plate: 7ABC123", "7ABC123"),
        ("מספר רישוי 12-345-67", "12-345-67"),
        ("Alberta Health Care: 12345 6789", "12345 6789"),
        ("dowód osobisty ABC 123456", "ABC 123456"),
    ],
)
def test_v9_round2_spans(text, value):
    assert any(value in e.text for e in RegexDetector().detect(text))


@pytest.mark.parametrize(
    "text",
    [
        "Medications:\nI take Menopur daily",
        "Allergies:\nPlease note penicillin",
        "Progesterone,\nPlease confirm",
        "username is required",
        "my plate is 3 days late",
    ],
)
def test_v9_round2_lookalikes(text):
    assert not RegexDetector().detect(text)


def test_dob_label_is_not_an_id():
    assert {(e.type, e.text) for e in RegexDetector().detect("DOB: 2026-11-19")} == {(T.DATE, "2026-11-19")}


@pytest.mark.parametrize(
    "text,value",
    [
        ("Thanks,\r\nClaudia Ramos", "Claudia Ramos"),
        ("Thanks,\r\n\r\nClaudia Ramos", "Claudia Ramos"),
        ("Tom and I went", "Tom"),
        ("Today Sarah and I went", "Sarah"),
        ("+44 (0)20 7946 0958", "+44 (0)20 7946 0958"),
        ("00 33 6 12 34 56 78", "00 33 6 12 34 56 78"),
        ("Numer telefonu 22 123 45 67", "22 123 45 67"),
        ("My Medicare card is 1234 56789 1 and", "1234 56789 1"),
        ("username: jsmith", "jsmith"),
        ("user id: 12345", "12345"),
        ("the card ends 4471", "4471"),
        ("Charged to Visa****4471 yesterday", "****4471"),
        ("my member id gcm 70 4418 21", "gcm 70 4418 21"),
        ("Witam Anna,\n\nDziękuję", "Anna"),
        ("Jestem Anna Kowalska", "Anna Kowalska"),
        ("Nazywają mnie Ania", "Ania"),
        ("Mon amie Marie Tremblay est enceinte", "Marie Tremblay"),
    ],
)
def test_v9_round3_spans(text, value):
    assert value in {e.text for e in RegexDetector().detect(text)}


@pytest.mark.parametrize(
    "text",
    [
        "patient is 91 days post transfer",
        "Clomid and I get along",
        "Maybe Sarah and I should",
        "Merci,\nL'équipe de la clinique",
        "CPT 58970 and NDC 0052-0316-10",
    ],
)
def test_v9_round3_lookalikes(text):
    found = [e for e in RegexDetector().detect(text) if e.type.value in ("AGE", "NAME", "PHONE")]
    assert not found or text.startswith("Maybe") and all(e.text == "Sarah" for e in found)


def test_v9_round4():
    from phiproxy import Masker

    for text in ["Dziękuję,\nRecepcja", "Gracias,\nEnfermería", "Thanks,\nAdmissions", "תודה,\nקבלה", "Cordialement,\nAccueil"]:
        assert Masker().mask(text, "s").text == text
    assert Masker().mask("The card on file is 5500********0004, please", "s").text == "The card on file is [ACCOUNT_1], please"
    assert Masker().mask("ID: ON 1234 5678 90", "s").text == "ID: [HEALTH_CARD_1]"
    assert Masker().mask("my member id ON 70 4418 21", "s").text == "my member id [HEALTH_CARD_1]"


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("write me: ana [at] example [dot] org ok", T.EMAIL, "ana [at] example [dot] org"),
        ("mkim [dot] 88 [at] example [dot] net", T.EMAIL, "mkim [dot] 88 [at] example [dot] net"),
        ("mail marisol_t88(at)example(dot)com please", T.EMAIL, "marisol_t88(at)example(dot)com"),
        ("it is ximena.tb [at] example.org", T.EMAIL, "ximena.tb [at] example.org"),
        ("x (at) example . com", T.EMAIL, "x (at) example . com"),
        ("a punto beltran punto ochenta y ocho arroba example punto com", T.EMAIL,
         "a punto beltran punto ochenta y ocho arroba example punto com"),
        ("j dot nguyen at example dot org", T.EMAIL, "j dot nguyen at example dot org"),
        ("jean point roy arobase example point ca", T.EMAIL, "jean point roy arobase example point ca"),
        ("jan kropka nowak małpa example kropka pl", T.EMAIL, "jan kropka nowak małpa example kropka pl"),
        ("insta @thaolee_ttc if you want", T.ID, "@thaolee_ttc"),
        ("Instagram is @ruiz.baby.hopes too.", T.ID, "@ruiz.baby.hopes"),
        ("user gwen_larue_77 locked", T.ID, "gwen_larue_77"),
        ("Username yael.peretz88. Can you reset", T.ID, "yael.peretz88"),
        ("we will post on amywhitcombe.example.com soon", T.URL, "amywhitcombe.example.com"),
        ("my blog is jane-doe.com", T.URL, "jane-doe.com"),
    ],
)
def test_v10_email_handle_url(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "meet at 3pm @ 10am",
        "dose 5 mg @ bedtime, @5pm",
        "the user logged in. user is locked",
        "login failed, user 12345 tried",
        "user session timed out",
        "please visit the page tomorrow",
        "call me at (416) 555-0142 at home",
        "arrive at noon at the clinic",
    ],
)
def test_v10_email_handle_url_lookalikes(text):
    assert not [e for e in RegexDetector().detect(text) if e.type in (T.EMAIL, T.ID, T.URL)]


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("call me back at 416-555-\n0166 sorry", T.PHONE, "416-555-\n0166"),
        ("number is 416-\n555-0166 thanks", T.PHONE, "416-\n555-0166"),
        ("the number is 416 555 0.1.7.2, dots from my keyboard", T.PHONE, "416 555 0.1.7.2"),
        ("Phone: (763) 555-01xx pt did not finish", T.PHONE, "(763) 555-01xx"),
        ("[DTMF: 4 1 6 5 5 5 0 1 4 4 #]", T.PHONE, "4 1 6 5 5 5 0 1 4 4"),
        ("System: enter your medical record number.\n[DTMF: 0 0 7 4 1 2 9 #]", T.ID, "0 0 7 4 1 2 9"),
        ("el número de miembro: W, 4, 4, 1, 9, 0, 0, 7, 2.", T.ID, "W, 4, 4, 1, 9, 0, 0, 7, 2"),
        ("member number is Z X 9 1 4 4 4 0 2 7, group", T.ID, "Z X 9 1 4 4 4 0 2 7"),
        ("Claim number C L M dash 7 7 3 0 2 1 4 4. I spoke to", T.ID, "C L M dash 7 7 3 0 2 1 4 4"),
        ("And the group number? Paciente: ¿Grupo? uh, G 7 7 3.", T.ID, "G 7 7 3"),
        ("grupa jest... ee... grupa cztery cztery jeden. Ubezpieczyciel", T.ID, "grupa cztery cztery jeden"),
        ("קבוצה... אה... קבוצה ארבע ארבע אחת. חברת הביטוח", T.ID, "קבוצה ארבע ארבע אחת"),
        ("מספר הביטוח הוא W K 3 8 8 1 0 6 5, קבוצה", T.ID, "W K 3 8 8 1 0 6 5"),
        ("Call me at 612-555-0192, that's six one two, five five five, then zero one nine and the letter L.", T.PHONE,
         "six one two, five five five, then zero one nine"),
        ("Farah is F as in Foxtrot A R A H", T.NAME, "F as in Foxtrot A R A H"),
        ("that's P-R-I-Y-A-N-K-A and R as in Robert, A, M, A, N.", T.NAME, "R as in Robert, A, M, A, N"),
        ("c comme Charles, l, a, i, r, e.", T.NAME, "c comme Charles, l, a, i, r, e"),
        ("It is, uh, A-N-A, then underscore", T.NAME, "A-N-A"),
        ("ת.ז. שלו 312 555 874, לא, טעות, זה שלי. שלו 058 555 761. סורי", T.ID, "058 555 761"),
        ("ת.ז. 3O5 555 412\nאבחנה", T.ID, "3O5 555 412"),
        ("מספר זהות: 204-555-119", T.ID, "204-555-119"),
    ],
)
def test_v10_spoken_spaced_identifiers(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "Follow-up scheduled 1 2 3 4 5 6 7 weeks, no",
        "Day 1 2 3 4 5 6 7 of stims",
        "Counting: 0 1 2 3 4 5 6 7 8 9",
        "Reply Y 1 2 3 to confirm",
        "We spoke. I think we should go on Thursday at 5 5",
        "Trigger at 9 PM, then 2 tablets, 3 times a day, 5 days",
        "ultrasound showed I-V-F cycle, H-C-G and F-S-H are back",
        "the group number is 441 and the abc is A-B-C",
        "ת.ז. ושם: אבא, 12 ילדים, 3 נשים",
    ],
)
def test_v10_spoken_spaced_lookalikes(text):
    got = [e for e in RegexDetector().detect(text) if e.type in (T.ID, T.NAME, T.PHONE)]
    assert not got, got


@pytest.mark.parametrize(
    "text,value",
    [
        ("I'll be away Mar 3–7 for work", "Mar 3–7"),
        ("transfer the week of March 16-20, ok", "March 16-20"),
        ("screening April 6 to 8 at the clinic", "April 6 to 8"),
        ("ok so DOB 03/xx/1988 and the rest", "03/xx/1988"),
        ("Fecha de nac.: 09/XX/1991", "09/XX/1991"),
        ("Attachment: Smith_J_labs_2026-03-14.pdf", "2026-03-14"),
        ("el mar, 7 abr 2026 a las 9:14", "7 abr 2026"),
        ("Fecha: lun, 2 mar 2026 18:02", "lun, 2 mar 2026"),
        ("Nac.: 12-ago-1985", "12-ago-1985"),
        ("W dniu wt., 12 sty 2026 o 9:14", "12 sty 2026"),
        ("urodzona 3-go maja 1991.", "3-go maja 1991"),
        ("SA 12/2025: 4 M/mL, motility 22 pct", "12/2025"),
        ("She is due in July. She wants to book", "July"),
        ("I'm due about late October.", "late October"),
        ("Mi mamá murió el tres de enero de este año, de cáncer", "el tres de enero de este año"),
        ("Un transfert en mai, est-ce possible", "mai"),
        ("hay que cancelar desde mayo", "mayo"),
        ("I am on a trip till 12.12. Thanks", "12.12"),
        ("the surrogate visit on the primero of June.", "the primero of June"),
    ],
)
def test_v10_date_forms(text, value):
    assert (T.DATE, value) in types_in(text)


@pytest.mark.parametrize(
    "text,value",
    [
        ("Es date: May the fifth, no sorry, the sixth, nineteen eighty-four.", "May the fifth, no sorry, the sixth, nineteen eighty-four"),
        ("Y la fecha, es tres, equis equis, mil novecientos ochenta y ocho, no más", "tres, equis equis, mil novecientos ochenta y ocho"),
        ("Quiero cambiar el, el seis de, no perdón, el siete de abril", "seis"),
        ("c'est le cinq, non, le six mai, c'est ça?", "cinq"),
        ("le vingt-deux février. Non, pardon, le vingt-trois.", "vingt-trois"),
        ("Przyjadę piątego, nie przepraszam, szóstego maja na pobranie", "piątego"),
        ("to come on the, uh, nineteenth but she can't", "nineteenth"),
        ("operación en el hospital el 7 de enero", "el 7 de enero"),
        ("zabieg w ciągu 5 dni, bez maiła", None),
    ],
)
def test_v10_date_spoken_corrections(text, value):
    if value is None:
        assert not [e for e in RegexDetector().detect(text) if e.type is T.DATE]
    else:
        assert (T.DATE, value) in types_in(text)


def test_v10_date_hebrew_prefixed_gematria_day():
    got = types_in('הניתוח היה בכ"ג בתשרי.')
    assert (T.DATE, 'כ"ג בתשרי') in got


@pytest.mark.parametrize(
    "text",
    [
        "p. 1/3 of the fax",
        "--- page 2/3 ---",
        "str. 1/2 wypisu",
        "עמ' 1/2",
        "take 1/2 tablet daily and 1/3 cup water",
        "FSH 18.4, testosterone 290",
        "AMH 24.3 pmol/L today",
        "new lot of Menopur, lot 8A331, expiry 2027-04; Gonal-f ok",
        "NDC 12345-678-90 Lot A4417Z Exp 2027-01",
        "lote 220481, caducidad 06/2027",
        "LOT 5K021 DISCARD AFTER 12/2027",
        "dose 2.5 to 12.5 mg; trip until 12.5 mg",
    ],
)
def test_v10_date_lookalikes(text):
    got = [e for e in RegexDetector().detect(text) if e.type is T.DATE]
    assert not got, got


def test_v10_date_range_not_time():
    got = [e.text for e in RegexDetector().detect("open Mar 3 to 7pm, then Mar 3 - 4 mg") if e.type is T.DATE]
    assert "Mar 3 to 7" not in got and "Mar 3 - 4" not in got, got


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("The court file number is 27-FA-26-4410, thanks", T.ID, "27-FA-26-4410"),
        ("insurance card nr UB-77/204519, what do I do", T.ACCOUNT, "UB-77/204519"),
        ("Ua tsaug. Can we get an interpreter? Acct# 88412-07 for the payment plan", T.ACCOUNT, "88412-07"),
        ("oh too late lol, 4929 5550 0142 0042 exp 08/28", T.ACCOUNT, "4929 5550 0142 0042"),
        ("Please don't type card numbers here.\nPatient: sorry 4111 2222 3333 4445", T.ACCOUNT, "4111 2222 3333 4445"),
        ("the card is a Visa **** **** **** 3318.", T.ACCOUNT, "**** **** **** 3318"),
        ("Mon numéro Santé Manitoba est 123 456 789.", T.HEALTH_CARD, "123 456 789"),
        ("PHIN 987 654 32l\nDx: azoospermia", T.HEALTH_CARD, "987 654 32l"),
        ("Can I give just the last 4 of my SSN, 0932? Not the whole thing", T.SSN, "0932"),
        ("my SSN ends in 4417 only", T.SSN, "4417"),
        ("mon NAS finit par 417, je donne pas le reste", T.SIN, "417"),
        ("sperme de donneur D-5513.", T.DONOR_ID, "D-5513"),
        ("My husband Gerald passed away in January. He was ninety-one.", T.AGE, "ninety-one"),
        ("for my sister Kiara. Our uncle Walter is 91 and wants to come", T.AGE, "91"),
        ("pedido de suministros #TF-20933 fue enviado", None, None),
    ],
)
def test_v10_id_account_forms(text, etype, value):
    found = types_in(text)
    if etype is None:
        assert not {f for f in found if f[0] in (T.ID, T.ACCOUNT)}, found
    else:
        assert (etype, value) in found, found


@pytest.mark.parametrize(
    "text",
    [
        "Ticket TKT-5521 opened. Quote Q-55810 for tank model CT-300. Part numbers: SEAL-114.",
        "Order PO-30771 shipped. See SOP-114 v3.2.",
        "Supply order #TF-48213 has shipped. Reply STOP to opt out.",
        "Embryo 4AA, 3BB, 3BC. Transfer one.",
        "embryo 5AB+ was frozen",
        "Take the last 4 weeks off. Cost 4929 5550 0142 dose",
        "my husband is 100% on board, wife is 95 kg",
        "Lot 4929 5550 0142 0042 expires 08/28 (lot of syringes)",
        "SSN not needed. The sin of omission ended in 2024.",
        "Room 27-FA 26 4410 is booked",
    ],
)
def test_v10_id_account_lookalikes(text):
    found = [e for e in RegexDetector().detect(text) if e.type in (T.ID, T.ACCOUNT, T.SSN, T.SIN, T.DONOR_ID, T.AGE, T.HEALTH_CARD)]
    assert not found, found


# --- v10 names, addresses and employers --------------------------------------------------------
def _masked(text, known=None, **policy):
    from phiproxy import KnownEntities, Masker, Policy

    m = Masker(policy=Policy(**policy))
    return m.mask(text, "s", known=KnownEntities(names=known) if known else None).text


@pytest.mark.parametrize(
    "text,value",
    [
        ("Files: Lopez_M_bloodwork_2026-03-14.pdf", "Lopez_M"),
        ("see USG_Sobczak_A.pdf", "Sobczak_A"),
        ("the Vang-Lees are coming", "Vang-Lees"),
        ("we're the Hendersons and we booked", "Hendersons"),
        ("somebody at the insurer named Priscilla Dunmore called", "Priscilla Dunmore"),
        ("we named him Anders yesterday", "Anders"),
        ("Nickname: Josie", "Josie"),
        ("everyone calls me Baby", "Baby"),
        ("soy Concepción (Concha para los amigos)", "Concha"),
        ("Kuya Bong will pick it up", "Bong"),
        ("#TeamOkonkwo is almost at transfer", "Okonkwo"),
        ("between Tessa Marie Holloway (the Donor) and the agency", "Tessa Marie Holloway"),
    ],
)
def test_v10_name_cues(text, value):
    assert any(value in e.text for e in RegexDetector().detect(text))


@pytest.mark.parametrize(
    "text",
    [
        "Files: Lab_B_results.pdf and Form_A.pdf",
        "the Rh-Negatives group",
        "a drug named Menopur was started",
        "The dog's name is Pierogi",
        "my dad passed on 10/02/2026",
        "From: Calendar <calendar@clinic.example.org>",
        "Reference: Quote Q-55810",
        "Donor Program Coordinator\nMinnesota Medical Assistance",
        "Asistente: Versión del portal 4.12.3",
        "Hola, soy médica, la Dra. Cárdenas",
        "mi nombre siempre lo escriben mal",
        "Preferred: Email or phone",
        "Kuya Jun sa lab will call",
        "Interpreter: Hmong line, three-way",
        "תודה, קיבלתי. תודה מראש. תודה רבה, ביי.",
    ],
)
def test_v10_not_names(text):
    assert not [e for e in RegexDetector().detect(text) if e.type is T.NAME]


def test_v10_echoed_names_and_initials():
    out = _masked("Her name is Halina Kowalczyk. Is Halina able to come? The carrier signed.")
    assert out.count("[NAME_") == 2 and "Halina" not in out and "carrier" in out
    out = _masked("calendar: FET - K. Yang, Dec 14. I'm Kou Yang.", known=["Kou Yang"])
    assert "K." not in out and "Yang" not in out
    # a clinician, a law firm and a lower-case word stay
    out = _masked("My name is Marta Brandt. Dr. Brandt will call. Brandt & Pike LLP wrote. The brandt of it.")
    assert "Dr. Brandt" in out and "Brandt & Pike" in out


def test_v10_family_name_with_particles_in_known():
    out = _masked("Lucía de la Cruz called. Gracias de nada. Ms. de la Cruz agreed.", known=["Lucía de la Cruz"])
    assert out.count("[NAME_") == 2 and "de nada" in out and "de la Cruz" not in out


@pytest.mark.parametrize(
    "text,value",
    [
        ("dos mil cuatrocientos cincuenta y uno de la calle Lake, apartamento tres B, Saint Paul", "apartamento tres B, Saint Paul"),
        ("ulica Lyndale trzysta dwanaście, mieszkanie cztery", "mieszkanie cztery"),
        ("ברחוב הרצל 14 דירה 7", "דירה 7"),
        ("עכשיו במיניאפוליס, ברחוב ליינדייל שלוש מאות שתים עשרה דירה ארבע", "דירה ארבע"),
        ("j'ai déménagé du Précieux-Sang le mois passé", "Précieux-Sang"),
        ("4408 Chicago Ave S Apt 2B, Minneapolis", "Ave S Apt 2B, Minneapolis"),
        ("2240 Maryland Ave E, St. Paul, 55119", "St. Paul"),
        ("addr1: 1807 Stevens Ave\ncity: Winona\nzip: 55987", "Winona"),
    ],
)
def test_v10_addresses(text, value):
    assert any(value in e.text for e in RegexDetector().detect(text))


def test_v10_addresses_not_over_matched():
    assert not [e for e in RegexDetector().detect("Call 1200 Wellington Street, Ottawa. Tel 613") if "Tel" in e.text]
    assert not [e for e in RegexDetector().detect("moved to Menopur 75 and moved from Gonal-f") if e.type is T.ADDRESS]
    assert not [e for e in RegexDetector().detect("city: unknown") if e.type is T.ADDRESS]


@pytest.mark.parametrize(
    "text,value",
    [
        ("ya at work till 1 target on lake st", "target on lake st"),
        ("His wife is Dr. Anita Lee, a paediatrician at Children's North Clinic; they", "Children's North Clinic"),
        ("my husband works nights at Prairie Cold Storage so", "Prairie Cold Storage"),
        ("My work, Medtronic Plains Biologics, just added coverage", "Medtronic Plains Biologics"),
        ("Greta - Teacher, Eden Prairie Montessori", "Eden Prairie Montessori"),
        ("su empleador, Distribuidora Andina", "Distribuidora Andina"),
        ("המנהל במפעלי אורן לא משחרר אותי", "מפעלי אורן"),
        ("אני עובדת בזטה טק", "זטה טק"),
        ("je perds ma job chez Transcona Foods", "Transcona Foods"),
    ],
)
def test_v10_employers(text, value):
    assert any(e.type is T.EMPLOYER and value in e.text for e in RegexDetector().detect(text))


def test_v10_employers_not_for_vendors():
    text = "I'm the pharmacist at the Harmon Place Pharmacy. Hi, this is Raj, pharmacist at Crestline Specialty."
    assert not [e for e in RegexDetector().detect(text) if e.type is T.EMPLOYER]


def _v10r1_spans(text, kind):
    return [e.text for e in RegexDetector().detect(text) if e.type is kind]


def test_v10_review1_obfuscated_email_dotted_local():
    for text, want in [
        ("my email is sarah.k.test at example dot com", "sarah.k.test at example dot com"),
        ("email me at jane.doe AT example DOT org", "jane.doe AT example DOT org"),
        ("email sarah-test AT example DOT net please", "sarah-test AT example DOT net"),
    ]:
        assert want in _v10r1_spans(text, T.EMAIL)


def test_v10_review1_plain_at_email():
    assert "sarah.test at example.ca" in _v10r1_spans("email sarah.test at example.ca", T.EMAIL)
    assert "jane at gmail com" in _v10r1_spans("jane at gmail com", T.EMAIL)
    assert _v10r1_spans("look at example.com for details", T.EMAIL) == []
    assert _v10r1_spans("meet me at the clinic org chart", T.EMAIL) == []


def test_v10_review1_bracket_email_span_stops_at_domain():
    assert _v10r1_spans("sarah(at)example.com.\nBye", T.EMAIL) == ["sarah(at)example.com"]
    assert _v10r1_spans("sarah(at)example.com. Bye now", T.EMAIL) == ["sarah(at)example.com"]
    assert _v10r1_spans("x (at) example . com", T.EMAIL) == ["x (at) example . com"]


def test_v10_review1_bare_handle_after_cue():
    for text, want in [("ig: jane88doe", "jane88doe"), ("my instagram is jane88doe", "jane88doe"),
                       ("on tiktok I'm janedoe88", "janedoe88"), ("my snap is janedoe_88", "janedoe_88")]:
        assert want in _v10r1_spans(text, T.ID)
    assert _v10r1_spans("my instagram is private", T.ID) == []


def test_v10_review1_phone_split_groups():
    for text in ["my number is 41 65 55 01 23", "my number is 416-555-01 23", "my number is 416 55 50123",
                 "c'est le 416 55 50 12 3"]:
        assert _v10r1_spans(text, T.PHONE), text
    assert _v10r1_spans("my number is 12 34 56", T.PHONE) == []


def test_v10_review1_partial_ssn_are():
    assert _v10r1_spans("last four digits of my social security number are 1234", T.SSN) == ["1234"]


def test_v10_review1_hebrew_range_prefix():
    spans = _v10r1_spans("בין ה-3 ל-7 במרץ", T.DATE)
    assert "3" in spans


def test_v10_review1_spelled_stops_at_newline():
    assert _v10r1_spans("spell: S A R A H\r\nA: yes", T.NAME) == ["S A R A H"]
    assert _v10r1_spans("S A R A H\nS. later", T.NAME) == ["S A R A H"]


def test_v10_review1_duplicate_spans_and_card_prefix():
    ents = RegexDetector().detect("OHIP 1234-567-890-AB")
    assert [(e.type, e.text) for e in ents].count((T.HEALTH_CARD, "1234-567-890-AB")) == 1
    assert "4111-xxxx-xxxx-1111" in _v10r1_spans("card 4111-xxxx-xxxx-1111", T.ACCOUNT)


def test_v10_review1_lab_month_year_not_date():
    assert _v10r1_spans("AMH 1/2024", T.DATE) == []


def test_v10_review2_employer_cue_skips_clause_starter():
    d = RegexDetector()
    for t in ("my employer is a school, I'm a teacher", "I work at a school, I’m a teacher",
              "I work at a clinic, she's a nurse", "my school, we're moving", "I work at a school, I've been there"):
        assert not [e for e in d.detect(t) if e.type is T.EMPLOYER], t
    got = [e.text for e in d.detect("I work at Acme Roofing, I'm a nurse") if e.type is T.EMPLOYER]
    assert got == ["Acme Roofing"]


def _v10r2_dates(text):
    return [e.text for e in RegexDetector().detect(text) if e.type is T.DATE]


def test_v10_review2_fraction_filter_needs_word_boundary():
    for t, want in (
        ("My appointment is 3/14 of next month", "3/14"),
        ("She was born 5/12 of last year", "5/12"),
        ("Can I come in on 3/14 weekend? My surgery is 3/20 weekday", "3/14"),
        ("Her due date is 11/20 daytime shifts", "11/20"),
        ("I can do 3/14 hours 10-2", "3/14"),
    ):
        assert want in _v10r2_dates(t), t
    for t in ("take 1/2 tab", "3/4 cup", "1/2 hour", "add 1/2 tsp"):
        assert _v10r2_dates(t) == [], t


def test_v10_review2_lab_cue_does_not_hide_day_first_dates():
    for t in ("Visit date = 14/03", "result 14/03 was my egg retrieval", "my surgery, total 14/03",
              "Retrieval ~14/03 or 15/03", "score: 14/03", "result 05/2024"):
        assert _v10r2_dates(t), t
    assert len(_v10r2_dates("Retrieval ~14/03 or 15/03")) == 2
    for t in ("FSH 18.4", "AMH level 13.4", "AMH = 13.4", "AMH 1/2024"):
        assert _v10r2_dates(t) == [], t


def test_v10_review2_product_expiry_only_in_same_clause():
    for t in ("I have a lot to say. My card expires 05/29.", "Visa exp 09/27, passport exp 2028-09",
              "kit ordered, health card exp 06/27", "Ref 1234, passport expiry 2027-04",
              "Lot 33 kit; patient's health card expiry 2027-06", "batch 55, health card valid thru 2026-08"):
        assert _v10r2_dates(t), t
    for t in ("lot 5512 exp 08/28", "kit exp 2027-04", "lot 8A331, expiry 2027-04", "Lot 4471B. Exp 08/2027",
              "Item: kit, lot 24-0713, qty 6, exp 06/2027"):
        assert _v10r2_dates(t) == [], t


def test_v10_review2_ordinal_day_list_covers_suffix():
    from phiproxy import Masker

    assert Masker().mask("between 3rd and 7th May 2023", "s").text == "between [DATE_1] and [DATE_2]"
    assert Masker().mask("on 1st and 2nd June", "s").text == "on [DATE_1] and [DATE_2]"
    assert Masker().mask("March 3rd to 7th", "s").text == "[DATE_1]"
    assert Masker().mask("the 3rd-7th of March", "s").text == "[DATE_1]"


def _mtext(text):
    from phiproxy import Masker

    return Masker().mask(text, "s").text


def test_v10_review2_spoken_nine_digit_id():
    for t in ("my ID is 0 3 4 5 6 7 8 9 1", "תעודת זהות שלי 0 3 4 5 6 7 8 9 1", "המספר שלי 0 5 2 3 4 5 6 7 8"):
        assert "[ID_1]" in _mtext(t) and _mtext(t).count("[ID_1]") == 1 and "9" not in _mtext(t), t
    # a plain count is still a list
    assert _mtext("count 1 2 3 4 5 6 7 8 9") == "count 1 2 3 4 5 6 7 8 9"


def test_v10_review2_handle_after_platform_cue():
    for t in (
        "my instagram is janedoe88", "mon instagram c'est janedoe88", "mi instagram es janedoe88",
        "mój instagram to janedoe88", "האינסטגרם שלי הוא janedoe88", "you can find me on twitter as janedoe_88",
        "my handle is jane.doe88",
    ):
        assert "janedoe" not in _mtext(t) and "jane.doe" not in _mtext(t), t
    assert _mtext("my instagram is private") == "my instagram is private"


def test_v10_review2_partial_national_id():
    for t in (
        "last 4 of social: 1234", "last4 of my SSN 1234", "mi seguro social termina en 1234",
        "mój pesel kończy się na 1234", "my sin ends in 789",
    ):
        assert "1234" not in _mtext(t) and "789" not in _mtext(t), t
    assert ("SIN" in {e.type.value for e in RegexDetector().detect("my sin ends in 789")})


def test_v10_review2_health_card_dash_and_spaces():
    for t in ("health card 1234 dash 567 dash 890 dash AB", "OHIP 1234 - 567 - 890 - AB", "my health card is 1234-567-890-A B"):
        assert _mtext(t).endswith("[HEALTH_CARD_1]") and "AB" not in _mtext(t) and "A B" not in _mtext(t), t


def test_v10_review2_patient_with_doctor_title():
    assert _mtext("My name is Dr Sarah Cohen") == "My name is Dr [NAME_1]"
    assert _mtext("I'm Dr. Sarah Cohen, a patient") == "I'm Dr. [NAME_1], a patient"
    assert _mtext("patient Dr. Sarah Cohen called") == "patient Dr. [NAME_1] called"
    assert _mtext("I'm Dr. Sarah Cohen and I'm a patient") == "I'm Dr. [NAME_1] and I'm a patient"
    assert _mtext("Dr Sarah Cohen here, I'm booked tomorrow").startswith("Dr [NAME_1] here")
    # clinicians stay readable
    assert _mtext("Dr. Sarah Cohen said to come in") == "Dr. Sarah Cohen said to come in"
    assert _mtext("I'm Dr. Sarah Cohen, the clinician") == "I'm Dr. Sarah Cohen, the clinician"
    assert _mtext("Dr Sarah Cohen here, I have a patient waiting") == "Dr Sarah Cohen here, I have a patient waiting"


def test_v10_review2_phone_across_crlf():
    for t in ("my number is 416 555\r\n0123 thanks", "call 416-555\r\n0123 now", "call 416-555-\r\n0123 now"):
        assert "[PHONE_1]" in _mtext(t) and "0123" not in _mtext(t), t


def test_v10_review2_ssn_type_beats_account():
    types = {e.type for e in __import__("phiproxy").Masker().mask("SSN ends in 1234. ok", "s").entities}
    assert types == {T.SSN}
    assert _mtext("SSN ends in 1234. ok") == "SSN ends in [SSN_1]. ok"
    assert _mtext("SIN ends in 789") == "SIN ends in [SIN_1]"


def test_v10_review2_file_initial_follows_surname_on_echo():
    assert _mtext("Lopez_M_2024.pdf and Lopez_M. Lopez_M, Lopez_M_") == "[NAME_1]_2024.pdf and [NAME_1]. [NAME_1], [NAME_1]_"


def test_v10_review2_url_trailing_punctuation_and_duplicates():
    def urls(t):
        return [e.text for e in RegexDetector().detect(t) if e.type is T.URL]

    assert urls("my site: www.sarahcohen.ca, ok") == ["www.sarahcohen.ca"]
    assert urls("visit sarahcohen.com/about. Thanks") == ["sarahcohen.com/about"]
    assert urls("see https://example.com/a, and https://example.org/b.") == ["https://example.com/a", "https://example.org/b"]
    assert _mtext("my site: www.sarahcohen.ca, ok") == "my site: [URL_1], ok"


def test_v10_review2_spoken_email_spelled_name_as_in_words():
    assert _mtext("mój mail to ania małpa gmail.com. Dzięki") == "mój mail to [EMAIL_1]. Dzięki"
    assert _mtext("ania małpa example.org") == "[EMAIL_1]"
    assert _mtext("c comme Charles o comme Oscar h comme Hotel, merci") == "[NAME_1], merci"
    out = _mtext("spelled A as in Alpha N as in November A. Then I")
    assert "November" not in out and "[NAME_1]" in out and "DATE" not in out
    assert "[DATE" in _mtext("I was born in November")


def test_v10_review3_echo_multiword_terms_and_brands():
    out = _masked("Call me Ann. Ann Arbor is far. Ann said hi. Ann's chart.")
    assert "Ann Arbor" in out and "[NAME_1] said hi" in out and "[NAME_1]'s chart" in out
    out = _masked("My name is Pat Johnson. Johnson & Johnson makes it. Johnson's baby powder")
    assert "Johnson & Johnson" in out and "[NAME_2]'s baby" in out
    assert "Pfizer vaccine" in _masked("My name is Amy Pfizer. Pfizer vaccine")
    # the person's own surname after the first name still echoes
    assert "Ann" not in _masked("Call me Ann Lee. Ann Lee will come.")


def test_v10_review3_echo_couples():
    for tail in ("Sarah and Mark came", "Sarah & Mark came", "Sarah Cohen and Mark are coming", "Ana y Luis"):
        name = "Ana Ruiz" if tail.startswith("Ana") else "Sarah Cohen"
        out = _masked(f"my name is {name}. {tail}")
        assert tail.split()[0] not in out
    assert "Brandt & Pike" in _masked("My name is Marta Brandt. Brandt & Pike LLP wrote.")


def test_v10_review3_echo_case_and_scripts():
    out = _masked("My name is Sarah Cohen. Sarah's Cohen's. sarah. COHEN. cohen. Cohen,Sarah")
    assert "Sarah" not in out and "ohen" not in out and "sarah" not in out and "COHEN" not in out
    out = _masked("My name is Ana Ruiz. ANA called. Thanks ana")
    assert "ANA" not in out and "ana" not in out
    out = _masked("my name is שרה כהן. שרה אמרה, כהן")
    assert "שרה" not in out and "כהן" not in out
    out = _masked("My name is Marta Brandt. The brandt of it.")
    assert "brandt of it" in out


def test_v10_review3_patient_locality_no_comma_and_newline():
    allow = ["1420 Nicollet Ave, Suite 310", "Minneapolis", "MN", "55403"]
    for t in (
        "55 Oak St\nMinneapolis, MN 55403",
        "Address:\n55 Oak St\r\nMinneapolis MN 55403",
        "I live at 55 Oak St Apt 4 Minneapolis MN 55403",
        "12 Elm Street Minneapolis",
    ):
        out = _masked(t, allow=allow)
        assert "Minneapolis" not in out and "55403" not in out, out
    out = _masked("Visit us at 1420 Nicollet Ave, Suite 310, Minneapolis, MN 55403", allow=allow)
    assert "Minneapolis" in out and "55403" in out


def test_v10_review3_allow_list_unit_and_city_on_next_line():
    allow = ["123 Main Avenue, Suite 4, Toronto"]
    for t in (
        "Come to 123 Main Avenue\nSuite 4\nToronto",
        "Come to 123 Main Avenue\r\nSuite 4\r\nToronto",
        "Come to 123 Main Avenue, Suite 4\r\nToronto",
        "Come to 123 Main Avenue\r\nSuite 4, Toronto",
    ):
        assert _masked(t, allow=allow, staff=["Dr. Smith"]) == t
    assert "123 Main" not in _masked("Come to 124 Main Avenue\nSuite 4\nToronto", allow=allow)


def _r3(text):
    from phiproxy import Masker

    m = Masker()
    r = m.mask(text, "r3")
    assert m.unmask(r.text, "r3") == text
    return r.text


@pytest.mark.parametrize(
    "text",
    [
        "my email is sarah.cohen [@] example.com",
        "my email is sarah.cohen {at} example.com",
        "sarah.cohen @ example.com",
        "x{dot}y {at} example{dot}org",
    ],
)
def test_v10_review3_obfuscated_email(text):
    assert "[EMAIL_1]" in _r3(text)
    assert "sarah" not in _r3(text) and "example" not in _r3(text)


def test_v10_review3_spaced_at_is_not_an_email_without_domain():
    assert _r3("meet @ 5pm at home.com") == "meet @ 5pm at home.com"
    assert _r3("see you @ clinic.ca tomorrow") == "see you @ clinic.ca tomorrow"


@pytest.mark.parametrize(
    "text,left",
    [
        ("my instagram handle is janedoe88", "janedoe88"),
        ("IG handle: sarah88", "sarah88"),
        ("my tiktok handle is sarah88", "sarah88"),
        ("ig @ jane88doe", "jane88doe"),
        ("my instagram name is sarah88", "88"),
    ],
)
def test_v10_review3_handle_after_cue_word(text, left):
    out = _r3(text)
    assert left not in out and "[ID_1]" in out


def test_v10_review3_plain_words_after_platform_cue_stay():
    assert _r3("my instagram handle is private") == "my instagram handle is private"


@pytest.mark.parametrize(
    "text,tag",
    [
        ("last 4 ssn: 1234", "[SSN_1]"),
        ("last 4 ssn 1234", "[SSN_1]"),
        ("the last 4 digits ssn 5678", "[SSN_1]"),
        ("last four of my sin is 1234", "[SIN_1]"),
    ],
)
def test_v10_review3_partial_ssn_cue_order(text, tag):
    out = _r3(text)
    assert tag in out and "1234" not in out and "5678" not in out


def test_v10_review3_partial_ssn_still_ignores_plain_sins():
    assert _r3("the last 4 sins 1234") == "the last 4 sins 1234"


@pytest.mark.parametrize(
    "text,gone",
    [
        ("se escribe S de Sara A R A H", ["Sara", "S de"]),
        ("my name is S. A. R. A. H.", ["S. A"]),
        ("spell it S. A. R. A. H. thanks", ["S. A"]),
        ("sara cohen arroba gmail punto com", ["sara", "cohen"]),
        ("my email is sarah cohen at gmail dot com", ["sarah", "cohen"]),
        ("sara cohen arroba gmail.com", ["sara", "cohen"]),
    ],
)
def test_v10_review3_spoken_and_spelled_names(text, gone):
    out = _r3(text)
    assert not any(g in out for g in gone), out


def test_v10_review3_spoken_email_keeps_lead_in_words():
    assert _r3("my email is sarah at gmail dot com").startswith("my email is [EMAIL")
    assert _r3("it is U.S.A.") == "it is U.S.A."


@pytest.mark.parametrize(
    "text",
    ["ת.ז. 03456789-1", "תעודת זהות 034-567-891", "ת.ז 034 567 891", "ת.ז. 034567891"],
)
def test_v10_review3_hebrew_id_layouts(text):
    out = _r3(text)
    assert out.endswith("[ID_1]") and not any(c.isdigit() for c in out.replace("_1]", ""))


@pytest.mark.parametrize(
    "text,kept",
    [
        ("call 416 555\r\n0123 Dr. Smith. Thanks", "Dr. Smith"),
        ("my number is 4 1 6 5 5 5 0 1 2 3 Dr. Smith", "Dr. Smith"),
        ("call 416-555-0123 Dr. Smith will call", "Dr. Smith"),
    ],
)
def test_v10_review3_title_dr_is_not_drive(text, kept):
    ents = RegexDetector().detect(text)
    assert not any(e.type is T.ADDRESS for e in ents)
    assert all("Dr" not in e.text for e in ents)
    assert kept in _r3(text)


def test_v10_review3_drive_still_an_address():
    assert any(e.type is T.ADDRESS for e in RegexDetector().detect("I live at 22 Pine Ridge Dr, Whitby"))
    assert any(e.type is T.ADDRESS for e in RegexDetector().detect("55 Oak Dr."))


@pytest.mark.parametrize(
    "text",
    [
        "תעודת זהות: ‎034‎-567-891",
        "phone 416‎-555-0123",
        "כתובת מייל: sarah‏(at)example.com",
        "נולדתי ב-3 בְּמַרְץ 1990",
        "שמי שָׂרָה כֹּהֵן.",
        "call 4 1 6​ 5 5 5 0 1 2 3",
        "DOB 1990-05​-03",
        "sar­ah@example.com",
    ],
)
def test_v10_review3_invisible_characters(text):
    out = _r3(text)
    assert not any(c.isdigit() for c in out.replace("_1]", "")), out
    assert "sarah" not in out and "שרה" not in out and "מרץ" not in out


def test_v10_review3_invisible_offsets_exact():
    text = "a‎ phone 416‎-555-0123 ‏ end"
    (e,) = [e for e in RegexDetector().detect(text) if e.type is T.PHONE]
    assert text[e.start : e.end] == e.text == "416‎-555-0123"
    plain = "no marks here 416-555-0123"
    (p,) = RegexDetector().detect(plain)
    assert plain[p.start : p.end] == "416-555-0123"


def test_v10_review4_product_expiry_needs_product_subject():
    from phiproxy import Masker
    m = Masker()
    for t in ("My prior authorization for Lupron expires 05/29", "Her referral for Menopur expires 05/29",
              "coverage for Gonal-f pen expires 05/29", "My prescription for letrozole expires 05/29"):
        assert "05/29" not in m.mask(t, "s").text, t
    for t in ("pen expires 03/2027", "Gonal-f exp 03/2027", "vial expiry: 03/2027", "Expiry: 03/2027 on the vial"):
        assert "[DATE_" not in m.mask(t, "s").text, t


def test_v10_review4_filename_initial_needs_surname():
    from phiproxy import Masker
    for t in ("Protocol_B.pdf", "Policy_Annex_A.docx", "Instructions_Part_A.pdf", "Pre_Op_Instructions_D.pdf",
              "Medication_List_J.pdf", "Thyroid_Panel_K.pdf", "Egg_Freezing_Guide_V2.pdf", "Semen_Analysis_Guide_Rev_B.pdf"):
        assert Masker().mask(t, "s").text == t, t
    assert "Lopez" not in Masker().mask("Lopez_M_labs.pdf", "s").text
    assert "Okafor" not in Masker().mask("Report_Okafor_J.pdf", "s").text


def test_v10_review4_month_year_not_after_billing_cues():
    from phiproxy import Masker
    for t in ("Invoice 12/2024", "Billing period 11/2024 to 12/2024", "Last updated 11/2024", "Version 03/2025",
              "Consent form rev 05/2023", "Offer valid until 01/2025", "Clinic stats for Q3/2024", "Newsletter 2024-11"):
        assert Masker().mask(t, "s").text == t, t
    for t in ("born 03/1990", "LMP 12/2025", "surgery in 06/2023"):
        assert "[DATE_" in Masker().mask(t, "s").text, t


def test_v10_review4_unicode_spaces_in_name_cues():
    from phiproxy import Masker
    for t in ("My name is Sarah Cohen.", "My name is Sarah Cohen.", "My name is Sarah Cohen."):
        out = Masker().mask(t, "s").text
        assert "Cohen" not in out and "Sarah" not in out, (t, out)


@pytest.mark.parametrize(
    "text,values",
    [
        (
            "Patient: what is the new phone number?\nPatient: the area code is 212\nPatient: then 555\nPatient: 0147\n"
            "Assistant: Just to confirm: 212-555-0147?\nPatient: sorry, 0174 not 0147\n",
            ["212", "555", "0147", "0174"],
        ),
        (
            "Paciente: mi numero de telefono\nPaciente: el codigo de area es 305\nPaciente: luego 555\nPaciente: termina en 0133\n"
            "Paciente: perdon, es 0138\n",
            ["305", "555", "0133", "0138"],
        ),
        ("Caller: Sure. The area code is 646, then 555, then 0119.\n", ["646", "555", "0119"]),
        ("Pacjent: numer telefonu?\nPacjent: kierunkowy 312\nPacjent: potem 555\nPacjent: i 0104\n", ["312", "555", "0104"]),
    ],
)
def test_v11_phone_in_pieces(text, values):
    got = [e.text for e in RegexDetector().detect(text) if e.type is T.PHONE and len(e.text) <= 4]
    for v in values:
        assert v in got


@pytest.mark.parametrize(
    "text",
    [
        # no phone talk near the groups
        "Patient: the code is 212\nPatient: then 555\nPatient: 0147\n",
        # times, doses and extensions after a phone question: not a NANP sequence of pieces
        "Agent: what is your phone number?\nPatient: see you at 0930\nPatient: my dose is 150 mg\nPatient: ext 4412\n",
        "Agent: what is the best number to reach you?\nPatient: 0845h works\nPatient: and 0930\n",
        # area code and exchange only: no line number follows
        "Agent: your phone number?\nPatient: area code 212\nPatient: then 555\nPatient: let me look it up\n",
    ],
)
def test_v11_phone_in_pieces_lookalikes(text):
    assert not [e for e in RegexDetector().detect(text) if e.type is T.PHONE]


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("Pod numer plus 48 555 010 203. Dziękuję.", T.PHONE, "plus 48 555 010 203"),
        ("me llaman al más 52 555 010 2030 gracias", T.PHONE, "más 52 555 010 2030"),
        ("Caller: mi, k, e, l, l, i, s, o, n, eight eight, at example dot com", T.EMAIL, "k, e, l, l, i, s, o, n, eight eight, at example dot com"),
        ("L'adresse, c, tremblay, tiret, roy, arobase example point org.", T.EMAIL, "c, tremblay, tiret, roy, arobase example point org"),
        ("y el apellido p, e, eñe, a. Es la cita", T.NAME, "p, e, eñe, a"),
        ("số điện thoại em là bốn không bốn, năm năm năm, không một tám hai", T.PHONE, "bốn không bốn, năm năm năm, không một tám hai"),
    ],
)
def test_v11_spoken_and_spelled_pieces(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "Add plus 2 more vials and 100 units",
        "plus 20 30 40",
        "Blood type A, B, O are all fine to donate",
        "yes, sure, ok, at example dot com",
        "ba năm trước tôi đến đây",
    ],
)
def test_v11_pieces_lookalikes(text):
    got = {e.type for e in RegexDetector().detect(text)}
    assert not (got & {T.PHONE, T.EMAIL})


def test_v11_phone_pieces_later_number_not_a_correction():
    text = "Agent: phone number?\nPatient: 212\nPatient: 555\nPatient: 0147\nPatient: room 3300 please\nPatient: 0930\n"
    got = [e.text for e in RegexDetector().detect(text) if e.type is T.PHONE]
    assert got == ["212", "555", "0147"]


def test_v11_vietnamese_three_needs_vietnamese_neighbour():
    assert (T.PHONE, "ba không bốn, năm năm năm, không một tám hai") in types_in("số điện thoại em là ba không bốn, năm năm năm, không một tám hai")
    assert not [e for e in RegexDetector().detect("Dish B: #7 5AA, #8 4BA. Lot BA06431") if e.type is T.PHONE]


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("please use RR 5, Site 2, Box 31, Greenfield NS B0X 1A0 for the courier", T.ADDRESS, "RR 5, Site 2, Box 31, Greenfield"),
        ("ship to Rural Route 7, Pinecrest please", T.ADDRESS, "Rural Route 7, Pinecrest"),
        ("She lives at PO Box 204, Oakvale. Thanks", T.ADDRESS, "PO Box 204, Oakvale"),
        ("meet at the pull-off near 45.1234, -64.5678, bring the cooler", T.ADDRESS, "45.1234, -64.5678"),
        ("coordenadas 19.1234, menos 99.5678 cerca del mercado", T.ADDRESS, "19.1234, menos 99.5678"),
        ("the drop location is at 33.1234, 84.5678 near the barn", T.ADDRESS, "33.1234, 84.5678"),
        ("it's the red house past the Shell on Hwy 7, then the second gravel drive on the left", T.ADDRESS,
         "the red house past the Shell on Hwy 7, then the second gravel drive on the left"),
        ("we're in Pinewood County so it is a drive", T.ADDRESS, "Pinewood County"),
        ("vivo en el condado de Larkin y es lejos", T.ADDRESS, "condado de Larkin"),
        ("אנחנו גרים בקאונטי לרקין ואני מחכה", T.ADDRESS, "קאונטי לרקין"),
        ("We live in Fairhaven First Nation near the lake", T.ADDRESS, "Fairhaven First Nation"),
        ("I'm from Tidewater and about three hours out", T.ADDRESS, "Tidewater"),
        ("we are now in the Harbourview area", T.ADDRESS, "Harbourview"),
        ("J'habite à Rivière-du-Moulin depuis un an", T.ADDRESS, "Rivière-du-Moulin"),
        ("Vivimos en Villanueva del Rio desde marzo", T.ADDRESS, "Villanueva del Rio"),
        ("Mieszkamy w Zielonowie od roku", T.ADDRESS, "Zielonowie"),
        ("אני גרה בנווה צדק עכשיו", T.ADDRESS, "נווה צדק"),
        ("referral, de Millhaven, N.-É. Diagnostic: SOPK", T.ADDRESS, "Millhaven"),
        ("Unit 9, Maple Row 22, Fort Calder, 31999", T.ADDRESS, "Unit 9, Maple Row 22, Fort Calder"),
        ("Unit 9, Maple Row 22, Fort Calder, 31999", T.ZIP, "31999"),
        ("mail to PSC 1234, Box 55, APO AE 09999", T.ADDRESS, "PSC 1234, Box 55"),
        ("mail to PSC 1234, Box 55, APO AE 09999", T.ZIP, "09999"),
        ("vivo en Hartley Residence Hall, room 305", T.ADDRESS, "Hartley Residence Hall, room 305"),
        ("Nuestro domicilio es Calle Sol 12, Colonia del Prado, San Marcos", T.ADDRESS, "Colonia del Prado, San Marcos"),
        ("cerca del mercado en colonia Santa Clara del Sur. Mi número", T.ADDRESS, "colonia Santa Clara del Sur"),
        ("hay un buzón con el número 5521. Si me llaman", T.ADDRESS, "5521"),
        ("une boîte aux lettres rouge avec le 3377 écrit dessus", T.ADDRESS, "3377"),
        ("My postal code is bee three ell, two cee four.", T.POSTAL_CODE, "bee three ell, two cee four"),
        ("저희 Suwanee로 이사했어요. 우편번호 30099", T.POSTAL_CODE, "30099"),
        ("저희 Suwanee로 이사했어요.", T.ADDRESS, "Suwanee"),
        ("Nou rete nan Westfield kounye a", T.ADDRESS, "Westfield"),
        ("my niece Anna Brook from Eastport", T.ADDRESS, "Eastport"),
        ("we live in Duluth, off Candle Road, so we will leave early", T.ADDRESS, "Candle Road"),
        ("Agent: mailing address?\nCaller: Okay. The number is forty-one.\nAgent: Forty-one what?\nCaller: Oak Row Lane. Hold on", T.ADDRESS, "forty-one"),
        ("Agent: mailing address?\nCaller: Okay. The number is forty-one.\nAgent: Forty-one what?\nCaller: Oak Row Lane. Hold on", T.ADDRESS, "Oak Row Lane"),
        ("My daughter goes to Hillside Elementary and I need to pick her up", T.EMPLOYER, "Hillside Elementary"),
        ("our kids attend Cedar Montessori", T.EMPLOYER, "Cedar Montessori"),
        ("3 Birchwood Cove, Marietta", T.ADDRESS, "3 Birchwood Cove, Marietta"),
        ("send it to 4B-123 Main St", T.ADDRESS, "4B-123 Main St"),
        ("2210 Briarcliff Road, mieszkanie 4B", T.ADDRESS, "2210 Briarcliff Road, mieszkanie 4B"),
        ("send to 123, rue Principale, app. 4, Dieppe", T.ADDRESS, "123, rue Principale, app. 4, Dieppe"),
    ],
)
def test_v11_places_and_addresses(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "TSH 2.4567, 3.1234 mIU/L",
        "Is the lot on Dundas Street open? And the pharmacy off Bay Road?",
        "Dear Dr. Lee, thank you",
        "this is Dana from Garden State Mutual calling about the claim",
        "the court of Marion County, docket 1234; condado de Larkin, expediente 55",
        "I'm in Day 3 of stims and from Monday I am off",
        "I'm from Canada originally, we speak French",
        "We moved to Menopur 75 and switched from Gonal-f",
        "I live in a house past the church",
        "back in April we met; now in Week 8",
        "the Fulton County Family Services caseworker called",
        "the case is at the court of Marion County",
        "Go to Hillcrest Pharmacy on Monday",
        "We are from the Nigerian community in the city",
        "RR 2 interval was normal",
        "the blue house is nice and the other house is green",
        "my number is forty-one and I'll call back",
        "pick up my son's school bag, Elementary school ok",
        "Hello, Mark, NS here",
    ],
)
def test_v11_places_lookalikes_not_masked(text):
    got = {e.text for e in RegexDetector().detect(text) if e.type in {T.ADDRESS, T.EMPLOYER, T.ZIP, T.POSTAL_CODE}}
    assert not got


@pytest.mark.parametrize(
    "text,value",
    [
        ("Best regards,\nJoanna Kral\nRidgefield, GA\nblog: example.net", "Ridgefield"),
        ("Pozdrawiam\nAnna\nזמני\nרידג'פילד, GA\nx", None),
        ("zam. ul. Lipowa 4/2, 31-120 Wieliczka, tel. 555", "Wieliczka"),
    ],
)
def test_v11_town_on_signature_or_after_postal_code(text, value):
    got = [e.text for e in RegexDetector().detect(text) if e.type is T.ADDRESS]
    if value:
        assert value in got


def test_v11_signature_lookalikes():
    for text in ["Thanks, OK\nsee you", "Regards, IN\nbye", "Hello, ME\n"]:
        assert not [e for e in RegexDetector().detect(text) if e.type is T.ADDRESS]


def _texts(text):
    return {e.text for e in RegexDetector().detect(text)}


def _covers(text, value):
    start = text.index(value)
    ents = RegexDetector().detect(text)
    return all(any(e.start <= i < e.end for e in ents) for i in range(start, start + len(value)))


@pytest.mark.parametrize(
    "text,value",
    [
        ("paid via Venmo @rsmith-ATL77 yesterday", "@rsmith-ATL77"),
        ("my Zelle handle is @ana-gomez-4 ok", "@ana-gomez-4"),
        ("I can send via Venmo @pat-lee-12 if you have one", "@pat-lee-12"),
        ("Venmo @piperj", "@piperj"),
        ("Cash App, it's $rsmith77.", "$rsmith77"),
        ("tengo cash app $ana.m.0412 y zelle", "$ana.m.0412"),
        ("su venmo es @lu-perez-12 y el mio es $luperez88", "$luperez88"),
        ("בוונמו מהחשבון @dan-levi-88 תודה", "@dan-levi-88"),
    ],
)
def test_v11_payment_handles(text, value):
    assert _covers(text, value)


@pytest.mark.parametrize(
    "text",
    [
        "the deposit is $400 and the balance $1,200 due",
        "costs $5k per cycle or $2.50 each",
        "see you @ 5pm at the clinic",
        "follow our page @magnolia-ra-clinic for news",
        "send it to billing@example.org",
        "meet me at the front-desk, not the side door",
    ],
)
def test_v11_payment_handle_lookalikes(text):
    got = {e.text for e in RegexDetector().detect(text) if e.type in {T.ACCOUNT, T.ID}}
    assert not got


def test_v11_bank_numbers_after_cue():
    assert _covers("my transit and institution are 54321-004, account 1234567", "54321-004")
    assert _covers("bank transit 54321 004 and", "54321 004")
    assert _covers("My bank is routing 021000021 account 0012345678", "021000021")
    assert _covers("el routing es 123456780 y la cuenta", "123456780")  # cue present: no checksum needed
    assert _covers("ABA 011401533", "011401533")
    # no bank cue: a bare nine digits or a postal-like 5-3 group is not an account
    assert "021000021" not in {e.text for e in RegexDetector().detect("Order 021000021 shipped") if e.type is T.ACCOUNT}
    assert not [e for e in RegexDetector().detect("room 54321-004 is free") if e.type is T.ACCOUNT]


def test_v11_cheque_numbers():
    assert _covers("I mailed cheque #2218 for $1,500", "#2218")
    assert _covers("my check number 1042 bounced", "1042")
    assert _covers("su cheque número 7788 fue devuelto", "7788")
    assert not [e for e in RegexDetector().detect("please check number of vials and cheque or card") if e.type is T.ACCOUNT]
    assert not [e for e in RegexDetector().detect("check #1 done, cheque 2 later") if e.type is T.ACCOUNT]


def test_v11_last_four_answered_on_next_line():
    t = "Asistente: Los últimos cuatro del seguro social?\nPaciente: es 4417\nAsistente: Gracias."
    assert _covers(t, "4417")
    t = "Agent: Can you give me the last four of the card?\nCaller: it is 8821."
    assert _covers(t, "8821")
    # not a last-four question: the next line's number stays
    assert "4417" not in _texts("Asistente: Cuándo es su cita?\nPaciente: es 4417 el cuarto piso")


def test_v11_card_ending_not_a_lot_number():
    assert "0457" not in _texts("the lot number on the box ends in 0457")
    assert "0457" not in _texts("batch is stamped, serial ends in 0457")
    assert "7702" in _texts("Card ending 7702")


@pytest.mark.parametrize(
    "text,value",
    [
        ("log: login ok user=u_55102 ip=203.0.113.9", "u_55102"),
        ("app account name is moon_phase_21 on the app", "moon_phase_21"),
        ("usr=jdoe_7741 download", "jdoe_7741"),
        ("Account name: mtorres_2026", "mtorres_2026"),
        ("my pump serial is SN 4KT0071XZ2 thanks", "SN 4KT0071XZ2"),
        ("my wearable band serial, WQ-44-12345", "WQ-44-12345"),
    ],
)
def test_v11_app_accounts_and_device_serials(text, value):
    assert _covers(text, value)


@pytest.mark.parametrize(
    "text",
    [
        "user error occurred twice",
        "the label printer serial ZX9Q-1234-5678 was replaced",
        "Pipette set serial 33AB-4455 checked",
        "account name changed",
    ],
)
def test_v11_account_and_serial_lookalikes(text):
    got = {e.text for e in RegexDetector().detect(text) if e.type in {T.ACCOUNT, T.ID}}
    assert not got


def test_v11_court_and_military_ids():
    assert _covers("court file number 24-FC-01234, hearing in May", "24-FC-01234")
    assert _covers("matter 25-DR-99871 pending", "25-DR-99871")
    assert _covers("מספר ההליך תמ״ש 1234-25 בבית המשפט", "תמ״ש 1234-25")
    assert _covers("I'm 1234-56-7890 for the military ID if you need it", "1234-56-7890")
    assert _covers("my DoD ID number is 1234567890", "1234567890")
    assert not [e for e in RegexDetector().detect("the 2026-11-03 visit, 12-34-5678 pages") if e.type is T.ID]


def test_v11_ids_in_digit_groups_after_cue():
    assert _covers("Mi cédula es 12 345 678 y mi pasaporte", "12 345 678")
    assert _covers("her status card number is 1234 567 89 thanks", "1234 567 89")
    assert not [e for e in RegexDetector().detect("Insur ID card scanned on 11 03 2026") if e.type is T.ID]
    assert not [e for e in RegexDetector().detect("la cédula quedó en 12 sala") if e.type is T.ID]


def test_v11_health_cards_in_groups_and_pieces():
    assert _covers("CARTE MEDICARE N.-B.: 123 456 789", "123 456 789")
    assert _covers("MSI card 123 456 789 expires", "123 456 789")
    t = "Bot: numéro de votre carte d'assurance maladie?\nPatiente: C'est ABCD 1234\nPatiente: 5678\nBot: merci"
    assert _covers(t, "ABCD 1234") and _covers(t, "5678")
    # no health-card word before it: a letters+digits label is not a card
    assert not [e for e in RegexDetector().detect("tube EDTA 1234\nnext: 5678") if e.type is T.HEALTH_CARD]
    assert not [e for e in RegexDetector().detect("Medicare visit on 2026-11-03") if e.type is T.HEALTH_CARD]


def test_v11_sin_named_earlier_needs_no_checksum():
    t = "The form asks for my SIN, which is 123 456 782. His is 412 880 659. Thanks."
    assert _covers(t, "412 880 659")
    # no SIN named: nine digits that fail the checksum are not a SIN
    assert not [e for e in RegexDetector().detect("ref 412 880 659 for the shipment") if e.type is T.SIN]


def test_v11_insurer_contract_and_plate():
    assert _covers("ma mutuelle est la ACME contrat 4408217.", "ACME contrat 4408217")
    assert not [e for e in RegexDetector().detect("HIPAA policy 164 applies") if e.type is T.ACCOUNT]
    assert _covers("a grey Subaru, plate ABC 1234, Georgia", "ABC 1234")
    assert not [e for e in RegexDetector().detect("the plate was warm, 37 degrees") if e.type is T.ID]


def test_v11_time_and_spanish_sin_are_not_ids():
    assert not [e for e in RegexDetector().detect("first one at 0800h. Two FETs at 1030h") if e.type is T.ID]
    assert not [e for e in RegexDetector().detect("esperé sin que nadie avisara, FSH de 11 y un AMH de 0.6") if e.type is T.ID]
    assert not [e for e in RegexDetector().detect("Lote del medio: LOT-5503 y TRK-90044172") if e.type in {T.ID, T.ACCOUNT}]


def _v11d(text):
    return {e.text for e in RegexDetector().detect(text) if e.type is T.DATE}


def _v11d_has(text, value):
    return any(value in t or t in value for t in _v11d(text))


@pytest.mark.parametrize(
    "text,value",
    [
        ("Attached: IMG_20260314_sam.jpg", "20260314"),
        ("see IMG-20250102.jpg", "20250102"),
        ("Assistant: Please give your date of birth.\nPatient: June\nAssistant: Which day?", "June"),
        ("Paciente: julio\nAsistente: Y el año?", "julio"),
        ("normal HSG last April. Seen by Dr. Lee", "last April"),
        ("Is it the twenty-second still? That is what I wrote", "the twenty-second"),
        ("mon rendez-vous est jeudi le 21 avec le docteur", "jeudi le 21"),
        ("de mardi le 12 parce que mon mari travaille", "mardi le 12"),
        ("생년월일은 1991년 8월 14일", "1991년 8월 14일"),
        ("Interpreter: 1994년 2월 9일입니다.", "1994년 2월 9일"),
        ("em sinh ngày mười hai tháng ba năm 1990, số điện thoại", "ngày mười hai tháng ba năm 1990"),
        ("sinh 12 tháng 3 năm 1990", "12 tháng 3 năm 1990"),
        ("מתורגמן: שלושה במאי שבעים ותשע.", "שלושה במאי שבעים ותשע"),
        ("pacjentami od marca", "marca"),
        ("my retrieval is 31.2", "31.2"),
        ("pain started 5/10", "5/10"),
        ("retrieval 11/12", "11/12"),
        ("recalibrated 11/12 for you", "11/12"),
        ("closed Dec 24, my appointment is Dec 23", "Dec 23"),
        ("Coverage effective January 1", "January 1"),
        ("the clinic is closed Monday. My retrieval is January 1", "January 1"),
    ],
)
def test_v11_dates_masked(text, value):
    assert _v11d_has(text, value), (text, _v11d(text))


@pytest.mark.parametrize(
    "text",
    [
        "BMI 31.2 means metformin first",
        "my BMI was 29.4 at the consult",
        "IMC de 31.2",
        "pain >7/10 go to the ER",
        "pain 4/10, voided",
        "rated 8/10",
        "dispose when 3/4 full",
        "Incubator 2 recalibrated 11/12, no embryos affected",
        "Patient: may",
        "hai tháng ba lần",
        "the third embryo looks good",
    ],
)
def test_v11_dates_lookalikes_not_masked(text):
    assert not _v11d(text), (text, _v11d(text))


def _v11n(text):
    return {e.text for e in RegexDetector().detect(text) if e.type is T.NAME}


@pytest.mark.parametrize(
    "text,value",
    [
        ("Triage 1420h. Pt KJ 34yo G2P1 c/o cramping", "KJ"),
        ("nurse huddle: also re: QX's FET, consent unsigned", "QX"),
        ("RE: RE: FET de QX - protocolo", "QX"),
        ("revisa el caso de la FET de QX antes del huddle", "QX"),
        ("LLAMAR: lab re: AMH de ZV (0.4, repetir?)", "ZV"),
        ("Mrs. Q rm 3 - retrieval today", "Q"),
        ("Hab 1: Sra. Q - HSG 0830h", "Q"),
        ("pt Z.Q. rm 3 wants the 1400 slot", "Z.Q."),
        ("Hab 2: Z.Q. G3P0 - ecografía", "Z.Q."),
        ("Z.Q. (2nd call) - bleeding after transfer", "Z.Q."),
        ("the matched child, Baby Girl Z., is placed through the agency", "Baby Girl Z."),
        ("Esposo Z. contesta el teléfono fijo", "Z."),
        ("they are foster parents to Zadie, who is nine", "Zadie"),
        ("Voici Zoé, elle a Zozo comme surnom", "Zozo"),
        ("Attached: Scan - Zeller, Ngozi.pdf (the other lab)", "Zeller, Ngozi"),
        ("Emergency contact: 정현수 470-555-0112", "정현수"),
        ("Patient: 정민아 (Mina Zeller), DOB 1990-05-22", "정민아"),
        ("Se escribe a-l-t-a, y el apellido p, e, eñe, a. Es la cita", "p, e, eñe, a"),
        ("la señora Karla Zeller tiene su domicilio en Macon", "Karla Zeller"),
        ("Caller: Ibrahim Zeller, husband of the patient\nSummary follows", "Ibrahim Zeller"),
    ],
)
def test_v11_name_initials_and_cued_names(text, value):
    assert any(value in n or n in value for n in _v11n(text)), (text, _v11n(text))


@pytest.mark.parametrize(
    "text",
    [
        "pt FET day 5, beta Friday",
        "pt ER visit, OHSS watch",
        "RE: FET de IVF - protocolo",
        "lab for CPT 83001 and 84702",
        "bill from the lab for ICSI add-on",
        "Dr. Zeller M.D. (REI) - 0830h",
        "O.R. - 0830h, E.R. 4 pm",
        "client IP 198.51.100.24, call dropped",
        "Partner PHN: ___ (out of province)",
        "DONOR EGG RESERVATION CONFIRMATION",
        "Patient: 좋아요. Thank you",
        "생년월일은 1991년 8월 14일, 전화번호가 바뀌었어요",
        "I miss texts about the beta",
        "Caller: It's hard to find, I'm up the road",
        "Conjointe de fait",
        "Proszę o imię i nazwisko oraz datę urodzenia.",
        "Pt PT 2x/wk",
        "foster parents to a boy, who is nine",
        "a Scan, Results.pdf",
    ],
)
def test_v11_name_initials_lookalikes_not_masked(text):
    assert not _v11n(text), (text, _v11n(text))


def test_v11_long_inputs_stay_fast_and_do_not_crash():
    import time

    d = RegexDetector()
    d.detect("1" * 70000)  # a digit run past Python's int() limit must not raise
    t0 = time.time()
    d.detect("ngày " + "hai mươi " * 3000)
    assert time.time() - t0 < 20


def _v11r1_vals(text, typ=None):
    return [(e.type.name, e.text) for e in RegexDetector().detect(text) if typ is None or e.type.name == typ]


@pytest.mark.parametrize(
    "text",
    [
        "Answer a, b, c, d to the quiz",
        "Opciones a, b, c, d",
        "Survey answers: a, b, c, d, e",
        "Questions 1-4: a, b, c, d",
        "Opcje a, b, c, d",
        "apellido: a, b, c, d",
    ],
)
def test_v11_review1_comma_letters_need_name_cue(text):
    assert _v11r1_vals(text, "NAME") == []


@pytest.mark.parametrize(
    "text,value",
    [
        ("el apellido p, e, eñe, a", "p, e, eñe, a"),
        ("mi apellido es p, e, eñe, a, y mi nombre es Ana", "p, e, eñe, a"),
        ("my last name is k, o, w, a, l", "k, o, w, a, l"),
        ("apellido: c, a, s, a, l, a, s y", "c, a, s, a, l, a, s"),
        ("k o w a l c z y k", "k o w a l c z y k"),
        ("w i l l y", "w i l l y"),
    ],
)
def test_v11_review1_comma_letters_with_cue_stay_masked_without_y(text, value):
    assert ("NAME", value) in _v11r1_vals(text)


@pytest.mark.parametrize(
    "text,value",
    [
        ("my cheque #2218", "#2218"),
        ("I mailed cheque number 1042", "1042"),
        ("cheque #2218 from me", "#2218"),
        ("mon chèque n° 8841", "8841"),
    ],
)
def test_v11_review1_patient_cheque_masked(text, value):
    assert ("ACCOUNT", value) in _v11r1_vals(text)


@pytest.mark.parametrize(
    "text",
    ["Cheque #4521 was deposited", "Please mail the cheque to the clinic, cheque number 12345", "Cheque number 12345 has cleared"],
)
def test_v11_review1_clinic_cheque_unmasked(text):
    assert _v11r1_vals(text, "ACCOUNT") == []


def test_v11_review1_device_serial_needs_personal_device():
    assert _v11r1_vals("Device serial CryoTank-4421 is calibrated", "ID") == []
    assert _v11r1_vals("The monitor serial number CRYO44210 was replaced", "ID") == []
    assert ("ID", "ABC123456") in _v11r1_vals("my pump serial is ABC123456")
    assert ("ID", "XY12345678") in _v11r1_vals("home glucometer serial is XY12345678")
    assert ("ID", "3MH0041AB7") in _v11r1_vals("her dexcom serial 3MH0041AB7")


@pytest.mark.parametrize("text", ["IMG_20261114.jpg", "PXL_20261114_1.jpg", "Screenshot_20261114.png", "VID_20261114.mp4"])
def test_v11_review1_photo_name_date_masked(text):
    assert ("DATE", "20261114") in _v11r1_vals(text)


@pytest.mark.parametrize("text", ["scan_20261114.pdf", "consent_form_20261114.pdf", "Form_20261114.pdf", "report_20261114.pdf"])
def test_v11_review1_clinic_file_name_date_unmasked(text):
    assert _v11r1_vals(text, "DATE") == []


def test_v11_review1_numbers_list_is_not_phone_pieces():
    assert _v11r1_vals("Estradiol numbers: 350, 420, 1100", "PHONE") == []
    assert _v11r1_vals("AMH numbers 250, 300, 1200", "PHONE") == []
    assert ("PHONE", "0100") in _v11r1_vals("phone numbers: 613, 555, 0100")
    assert ("PHONE", "0100") in _v11r1_vals("my number is 613\n555\n0100")
    assert ("PHONE", "1200") in _v11r1_vals("Here are my AMH numbers\n250\n300\n1200\nare they ok?")


@pytest.mark.parametrize("text", ["Re: TB test results", "Re: PGD", "Re: NY trip", "Re: BC pills", "Re: PRL", "Re: HSV", "pt POF; pt PGD; pt TVS", "Re: OCP"])
def test_v11_review1_abbreviations_not_initials(text):
    assert _v11r1_vals(text, "NAME") == []


@pytest.mark.parametrize("text,value", [("pt JT, 34yo", "JT"), ("Re: JT", "JT"), ("Re: KJ's FET", "KJ"), ("pt NY", "NY")])
def test_v11_review1_real_initials_stay(text, value):
    assert ("NAME", value) in _v11r1_vals(text)


def test_v11_review1_three_letters_cue_keeps_member_id_letters():
    got = _v11r1_vals("empieza con tres letras, W, B, K y luego 90284715")
    assert ("NAME", "W, B, K") in got
    assert _v11r1_vals("tres letras, A, B, C", "NAME") == []


@pytest.mark.parametrize(
    "text,value",
    [
        ("email: k - e - l - l - i at gmail dot com", "k - e - l - l - i at gmail dot com"),
        ("my email is k e l l i at gmail dot com", "k e l l i at gmail dot com"),
        ("my email is k. e. l. l. i at gmail dot com", "k. e. l. l. i at gmail dot com"),
        ("email: k e l l i 8 8 at gmail dot com", "k e l l i 8 8 at gmail dot com"),
        ("my email is k e l l i@gmail.com", "k e l l i@gmail.com"),
    ],
)
def test_v11_review1_spelled_email_variants(text, value):
    assert (T.EMAIL, value) in types_in(text)


@pytest.mark.parametrize("text", ["I am at the gmail dot com", "k e at home", "a b at the clinic dot com today"])
def test_v11_review1_spelled_email_lookalikes_stay(text):
    assert not any(t is T.EMAIL and len(v) > 12 for t, v in types_in(text))


@pytest.mark.parametrize("text", ["my phone number is\n404-\n555-\n1234", "my cell: 404-\n555-\n1234"])
def test_v11_review1_phone_pieces_with_trailing_dashes(text):
    got = types_in(text)
    assert {(T.PHONE, "404"), (T.PHONE, "555"), (T.PHONE, "1234")} <= got


def test_v11_review1_dashed_pieces_need_phone_cue_and_sequence():
    assert not types_in("the dose is\n250-\n500-\n750")
    assert not types_in("my phone number is\n404-\n555-\n")


@pytest.mark.parametrize(
    "text,value",
    [
        ("my account number is 1234 5678 9012", "1234 5678 9012"),
        ("account: 1234 5678 9012", "1234 5678 9012"),
        ("bank account 1234 5678 9012 3456", "1234 5678 9012 3456"),
    ],
)
def test_v11_review1_account_in_groups_of_four(text, value):
    assert (T.ACCOUNT, value) in types_in(text)


def test_v11_review1_account_groups_lookalikes():
    assert (T.ACCOUNT, "2024 2025") not in types_in("my account 2024 2025")
    assert not any(v == "1234 5678" for _, v in types_in("on page 1234 5678 there is a table"))


@pytest.mark.parametrize(
    "text,value",
    [
        ("I live on the Six Nations Reserve", "Six Nations Reserve"),
        ("I live on Wikwemikong Unceded Reserve", "Wikwemikong Unceded Reserve"),
        ("Six Nations Reserve No. 40", "Six Nations Reserve No. 40"),
        ("Curve Lake IR 35", "Curve Lake IR 35"),
        ("M'Chigeeng Reserve", "M'Chigeeng Reserve"),
        ("réserve de Kahnawake", "réserve de Kahnawake"),
        ("Reserve No. 40", "Reserve No. 40"),
    ],
)
def test_v11_review1_first_nation_reserves(text, value):
    assert (T.ADDRESS, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    ["the Federal Reserve raised rates", "Nature Reserve Park", "Reserve Bank of India", "réserve ovarienne basse", "réserve de sperme", "The Marine Reserve is closed"],
)
def test_v11_review1_reserve_lookalikes_stay(text):
    assert not any(t is T.ADDRESS for t, _ in types_in(text))


@pytest.mark.parametrize(
    "text,value",
    [
        ("I am at RR 2, Smithville", "RR 2, Smithville"),
        ("R.R.#2 Smithville ON", "R.R.#2 Smithville"),
        ("RR#2, Lacombe AB", "RR#2, Lacombe"),
        ("I live at R.R. #2, Smithville", "R.R. #2, Smithville"),
        ("RR2 Smithville", "RR2 Smithville"),
        ("Route rurale 2, Saint-Jean", "Route rurale 2, Saint-Jean"),
    ],
)
def test_v11_review1_rural_route_variants(text, value):
    assert (T.ADDRESS, value) in types_in(text)


@pytest.mark.parametrize("text", ["RR 2.5 (95% CI)", "RR 2 Results show", "RR 2, Patients", "the RR 2 was low"])
def test_v11_review1_rr_ratio_lookalikes_stay(text):
    assert not any(t is T.ADDRESS for t, _ in types_in(text))


@pytest.mark.parametrize(
    "text,value",
    [
        ("mieszkam w powiecie krakowskim", "powiecie krakowskim"),
        ("powiat wielicki", "powiat wielicki"),
        ("in Cobb county", "Cobb county"),
    ],
)
def test_v11_review1_counties_polish_and_lowercase(text, value):
    assert (T.ADDRESS, value) in types_in(text)


@pytest.mark.parametrize("text", ["w powiecie", "in the county hospital", "rotation of the county sheriff"])
def test_v11_review1_county_lookalikes_stay(text):
    assert not any(t is T.ADDRESS for t, _ in types_in(text))


@pytest.mark.parametrize(
    "text",
    [
        "Voici mon numéro de chèque : 1045",
        "J'ai envoyé le numero de cheque: 1045",
        "Mi número de cheque 1045",
        "I sent cheque 1045",
    ],
)
def test_v11_review1_cheque_number_fr_es(text):
    assert (T.ACCOUNT, "1045") in types_in(text)


@pytest.mark.parametrize(
    "text",
    ["cheque 1045", "The clinic sent cheque 1045", "numéro de chèque : 1045 reçu par la clinique", "I sent a cheque 500 dollars", "please check 1045 patients"],
)
def test_v11_review1_cheque_lookalikes_stay(text):
    assert (T.ACCOUNT, "1045") not in types_in(text)


@pytest.mark.parametrize(
    "text,value",
    [
        ("Pt: J T", "J T"),
        ("Pt initials JT", "JT"),
        ("patient initials: JT", "JT"),
        ("הפציינטית: ג.ט.", "ג.ט."),
        ("המטופלת: ג.ט.", "ג.ט."),
        ("המטופלת: ג״ט", "ג״ט"),
    ],
)
def test_v11_review1_patient_initials_variants(text, value):
    assert (T.NAME, value) in types_in(text)


@pytest.mark.parametrize("text", ["Pt: I V", "re: A B", "patient: A B", "המטופלת היא אישה"])
def test_v11_review1_initials_lookalikes_stay(text):
    assert not any(t is T.NAME for t, _ in types_in(text))


def test_v11_review1_directions_with_owner_landmark_and_tail():
    got = types_in("the cabin behind the Smith barn, then the first road on the right. Please call")
    assert (T.ADDRESS, "the cabin behind the Smith barn, then the first road on the right") in got
    assert (T.ADDRESS, "the cabin behind the barn") in types_in("the cabin behind the barn")


@pytest.mark.parametrize(
    "text",
    [
        "last 4 of your ssn?\nPatient: it's 4417\nThanks",
        "last 4 of your ssn?\n\nPatient: 4417\n",
        "last four of ssn?\nPatient: 4417 and then 9\n",
        "last 4 of your ssn?\nPatient: es 4417",
    ],
)
def test_v11_review1_last_four_reply_variants(text):
    assert (T.SSN, "4417") in types_in(text)


def test_v11_review1_last_four_reply_lookalikes_stay():
    assert not any(t is T.SSN for t, _ in types_in("last 4 of your ssn?\nPatient: no idea\n"))
    assert not any(t is T.SSN for t, _ in types_in("last 4 of your ssn?\nPatient: 44171\n"))


def test_v11_review1_hebrew_doctor_abbreviation_is_not_initials():
    assert not any(t is T.NAME for t, _ in types_in('המטופל ד"ר כהן הגיע'))
    assert not any(t is T.NAME for t, _ in types_in("המטופלת ד״ר"))


def test_v11_review1_spoken_plus_needs_phone_shape():
    d = RegexDetector()
    for t in ("plus 5 10 15 20 25 30 35", "más 1 2 3 4 5 6 7 8 9 10", "plus 20 100 200 300 units"):
        assert not [e for e in d.detect(t) if e.type is T.PHONE], t
    for t in ("plus 48 555 010 203", "más 34 612 345 678"):
        assert [e for e in d.detect(t) if e.type is T.PHONE], t


def test_v11_review1_miss_surname_after_verb_cue_masked():
    from phiproxy import Masker

    assert Masker().mask("did not miss garcia", "s").text == "did not miss [NAME_1]"
    for t in ("I miss texts", "we'll miss you", "i will miss work tomorrow", "to miss the appointment"):
        assert Masker().mask(t, "s").text == t


@pytest.mark.parametrize(
    "text",
    [
        "My insurance policy is effective January 1, 2026",
        "My coverage policy was effective from March 3 2025",
        "My treatment schedule effective Nov 14",
        "Mi póliza de seguro vigente schedule effective March 3 2025, mis datos",
    ],
)
def test_v11_review2_personal_effective_date_stays_masked(text):
    assert any(t is T.DATE for t, _ in types_in(text))


@pytest.mark.parametrize("text", ["My GPS is 45.4215, -75.6972.", "gps: 45.4215,-75.6972."])
def test_v11_review2_gps_pair_before_full_stop(text):
    found = RegexDetector().detect(text)
    assert [e.text for e in found if e.type is T.ADDRESS] == [text.split("is ")[-1].split(": ")[-1][:-1]]


def test_v11_review2_gps_lookalike_keeps_old_behaviour():
    assert not any(t is T.ADDRESS for t, _ in types_in("gps 45.4215, -75.6972.5"))


@pytest.mark.parametrize(
    "text,span",
    [
        ("PO Box 12, Station A", "PO Box 12, Station A"),
        ("Mail to PO Box 12 Stn B", "PO Box 12 Stn B"),
        ("PO Box 118, Cartersville", "PO Box 118, Cartersville"),
    ],
)
def test_v11_review2_po_box_station_span(text, span):
    assert span in [e.text for e in RegexDetector().detect(text) if e.type is T.ADDRESS]


def test_v11_review2_plate_span_excludes_cue():
    ids = [e.text for e in RegexDetector().detect("plate ABC 123.") if e.type is T.ID]
    assert ids == ["ABC 123"]
    assert [e.text for e in RegexDetector().detect("the plate TFR 4418 was seen") if e.type is T.ID] == ["TFR 4418"]


def test_v11_review2_initials_do_not_swallow_possessive():
    names = [e.text for e in RegexDetector().detect("pt MJ's chart") if e.type is T.NAME]
    assert names and all(n == "MJ" for n in names)


def test_v11_review2_spelled_accent_letters_keep_conjunction():
    names = [e.text for e in RegexDetector().detect("apellido: G, a, r, c, í, a, y mi nombre es Ana") if e.type is T.NAME]
    assert "G, a, r, c, í, a" in names and not any(n.endswith("y") for n in names)


def test_v11_review2_toneless_vietnamese_phone_needs_cue():
    got = [e.text for e in RegexDetector().detect("so dien thoai cua toi la khong mot hai ba bon nam sau bay tam chin") if e.type is T.PHONE]
    assert got == ["khong mot hai ba bon nam sau bay tam chin"]
    assert not RegexDetector().detect("khong mot hai ba bon nam sau bay tam chin")
    assert not RegexDetector().detect("sdt khong mot hai ba bon")


@pytest.mark.parametrize(
    "text,value",
    [
        ("patient J.R. Smith called", "J.R. Smith"),
        ("Patient J.T. Smith, 34F", "J.T. Smith"),
        ("patient A. B. C.", "A. B. C."),
    ],
)
def test_v11_review3_dotted_initials_take_the_surname(text, value):
    got = [e.text for e in RegexDetector().detect(text) if e.type is T.NAME]
    assert value in got


@pytest.mark.parametrize("text", ["patient e.g. Smith", "see plan B. Then call", "the patient A.B. then called"])
def test_v11_review3_dotted_initials_lookalikes(text):
    got = [e.text for e in RegexDetector().detect(text) if e.type is T.NAME]
    assert not any(len(g) > 5 for g in got)


# ---- v11 review round 3 (fixer b) -------------------------------------------------------------


def _found(text):
    return {(e.type.value, e.text) for e in RegexDetector().detect(text)}


@pytest.mark.parametrize(
    "text,value",
    [
        ("My GPS is 44.65 N, 63.57 W", "44.65 N, 63.57 W"),
        ("gps: 44.65 N, 63.57 W", "44.65 N, 63.57 W"),
        ("GPS: 44°39'N, 63°34'W", "44°39'N, 63°34'W"),
        ("our GPS pin is 44.65°N 63.57°W", "44.65°N 63.57°W"),
        ("my coords: 44.65 N 63.57 W", "44.65 N 63.57 W"),
        ("my GPS is 44.65,-63.57", "44.65,-63.57"),
    ],
)
def test_v11_review3_gps_hemisphere(text, value):
    assert ("ADDRESS", value) in _found(text)


@pytest.mark.parametrize("text", ["The flight was 44.65 N then 63 W", "temp 12.5 N, 3.4 W", "dose 44.65 N, 63.57 W"])
def test_v11_review3_gps_lookalikes_stay(text):
    assert not [e for e in _found(text) if e[0] == "ADDRESS"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("Mail me at Unit 2050 Box 4190, APO AP 96278", "Unit 2050 Box 4190, APO AP"),
        ("my mailing address: Unit 2050 Box 4190\nAPO AP 96278", "Unit 2050 Box 4190\nAPO AP"),
        ("Unit 2050 Box 4190, APO, AE 09012", "Unit 2050 Box 4190, APO, AE"),
        ("send it to PSC 802 Box 74, FPO AA 34090", "PSC 802 Box 74, FPO AA"),
    ],
)
def test_v11_review3_military_mail_line(text, value):
    assert ("ADDRESS", value) in _found(text)


def test_v11_review3_military_lookalike_stays():
    assert not _found("Unit 4 is the lab, Box 12 is lunch")


@pytest.mark.parametrize(
    "text,value",
    [
        ("I live at Route rurale no 2, Saint-Jean", "Route rurale no 2, Saint-Jean"),
        ("I live at Rang 3, Saint-Jean", "Rang 3, Saint-Jean"),
        ("I live at Concession 5 Lot 12, Elgin", "Concession 5 Lot 12, Elgin"),
        ("I live at Lot 12 Concession 4, Perth", "Lot 12 Concession 4, Perth"),
        ("I live at rr 1 site 5 comp 3", "rr 1 site 5 comp 3"),
        ("my address: Rang 3", "Rang 3"),
    ],
)
def test_v11_review3_rural_forms(text, value):
    assert ("ADDRESS", value) in _found(text)


@pytest.mark.parametrize("text", ["take the route 7 to the clinic", "Lot 12 of the vials", "the vial lot 12 expires soon", "send my vial lot 4471B to the lab"])
def test_v11_review3_rural_lookalikes_stay(text):
    assert not _found(text)


@pytest.mark.parametrize(
    "text",
    ["los últimos cuatro 1234", "les quatre derniers chiffres 1234", "ostatnie cztery cyfry 1234", "last four 1234"],
)
def test_v11_review3_last_four_other_languages(text):
    assert ("ACCOUNT", "1234") in _found(text)


@pytest.mark.parametrize("text", ["the last four weeks 1234 times", "los últimos cuatro días fueron duros", "ostatnie cztery dni"])
def test_v11_review3_last_four_lookalikes_stay(text):
    assert not _found(text)


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("numer konta 12 3456 7890 1234 5678 9012 3456", "ACCOUNT", "12 3456 7890 1234 5678 9012 3456"),
        ("account no: 123 456 789", "ACCOUNT", "123 456 789"),
        ("transit number 12345, institution number 004", "ACCOUNT", "12345"),
        ("transit number 12345, institution number 004", "ACCOUNT", "004"),
        ("routing 0 2 1 0 0 0 0 2 1", "ACCOUNT", "0 2 1 0 0 0 0 2 1"),
        ("cash.app/$janedoe", "ID", "$janedoe"),
        ("venmo me at jane_doe_ivf", "ID", "jane_doe_ivf"),
    ],
)
def test_v11_review3_payment_and_bank_forms(text, etype, value):
    assert (etype, value) in _found(text)


@pytest.mark.parametrize(
    "text",
    ["venmo me at lunch", "transit number 12345 for the bus", "numer konta nieznany 12 34", "routing 0 2 1"],
)
def test_v11_review3_payment_lookalikes_stay(text):
    assert ("ACCOUNT", "2026 11 20") not in _found("account no: 2026 11 20")
    assert not [e for e in _found(text) if e[0] in ("ACCOUNT", "ID")]


@pytest.mark.parametrize(
    "text,value",
    [
        ("court number 2026 FC 1234", "2026 FC 1234"),
        ("case number 2026 FC 1234", "2026 FC 1234"),
        ("Court file no. 123-26", "123-26"),
        ("numero de causa 1234-2026", "1234-2026"),
        ("mi expediente de divorcio es 123/2026", "123/2026"),
        ("court: SC 1234/26", "SC 1234/26"),
    ],
)
def test_v11_review3_court_numbers(text, value):
    assert ("ID", value) in _found(text)


@pytest.mark.parametrize("text", ["SC 1234/26", "the case number 5 was a twin cycle", "court number 12/03"])
def test_v11_review3_court_lookalikes_stay(text):
    assert not [e for e in _found(text) if e[0] == "ID"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("Where do you live?\nElm Street", "Elm Street"),
        ("¿En qué calle vive?\nHidalgo", "Hidalgo"),
        ("Which town do you live in?\nSudbury", "Sudbury"),
        ("Où habitez-vous?\nSudbury", "Sudbury"),
        ("Gdzie mieszkasz?\nKraków", "Kraków"),
        ("you'll see our blue house after the Shell station on Hwy 7", "our blue house after the Shell station on Hwy 7"),
        ("notre maison est après le Tim Hortons sur la route 7", "notre maison est après le Tim Hortons sur la route 7"),
    ],
)
def test_v11_review3_bare_reply_and_directions(text, value):
    assert ("ADDRESS", value) in _found(text)


@pytest.mark.parametrize(
    "text",
    ["Where do you live?\nNot sure yet, maybe later today", "Where do you live?\nYes", "Where do you live?\nthanks", "my house after the transfer"],
)
def test_v11_review3_bare_reply_lookalikes_stay(text):
    assert not [e for e in _found(text) if e[0] == "ADDRESS"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("mailing address is mailbox 123, Sudbury", "mailbox 123, Sudbury"),
        ("mi dirección es casilla 123", "casilla 123"),
        ("I live at skrytka pocztowa 123", "skrytka pocztowa 123"),
        ("I live at col. Del Valle", "col. Del Valle"),
        ("I live at fraccionamiento Las Palmas", "fraccionamiento Las Palmas"),
        ("I live at osiedle Słoneczne 12", "osiedle Słoneczne 12"),
        ("I live at kibbutz Ein Gedi", "kibbutz Ein Gedi"),
    ],
)
def test_v11_review3_postbox_and_neighbourhood(text, value):
    assert ("ADDRESS", value) in _found(text)


@pytest.mark.parametrize("text", ["the mailbox 123 at the clinic", "col. Del Valle clinic opens at nine", "the kibbutz Ein Gedi trip"])
def test_v11_review3_postbox_lookalikes_stay(text):
    assert not _found(text)


@pytest.mark.parametrize(
    "text,value",
    [
        ("apellido se escribe ge, a, erre, ce, i, a", "ge, a, erre, ce, i, a"),
        ("se escribe ese, i, ele, ve, a", "ese, i, ele, ve, a"),
    ],
)
def test_v11_review3_spanish_letter_name_spelling(text, value):
    assert ("NAME", value) in _found(text)


def test_v11_review3_spelled_email_is_one_span():
    assert _found("my email is kelli dash smith at gmail dot com") == {("EMAIL", "kelli dash smith at gmail dot com")}
    assert _found("email k, e, l, l, i, 8, 8 at gmail dot com") == {("EMAIL", "k, e, l, l, i, 8, 8 at gmail dot com")}


def test_v11_review3_spanish_letters_need_cue():
    assert not _found("las opciones son ge, a, erre, ce, i, a")


@pytest.mark.parametrize(
    "text,value",
    [
        ("90210 Beverly Hills CA and my phone", "Beverly Hills"),
        ("10001 New York NY", "New York"),
        ("I live at 12 Oak St, 90210 Los Angeles", "Los Angeles"),
        ("M5V 2T6 Niagara Falls ON", "Niagara Falls"),
    ],
)
def test_v11_review3_town_after_postal_code(text, value):
    assert ("ADDRESS", value) in _found(text)


@pytest.mark.parametrize(
    "text,value",
    [
        ("90210 Beverly Hills Please call me", "Beverly Hills"),
        ("12 Oak St, 90210 Los Angeles. Thanks", "Los Angeles"),
    ],
)
def test_v11_review3_town_after_postal_code_stops(text, value):
    assert ("ADDRESS", value) in _found(text)
    assert not [e for e in _found(text) if "Please" in e[1] or "Thanks" in e[1]]


@pytest.mark.parametrize(
    "text,value",
    [
        ("St. Louis County, MO", "St. Louis County"),
        ("Mt. Pleasant County", "Mt. Pleasant County"),
        ("my address is St. John's First Nation", "St. John's First Nation"),
        ("I live in Ste. Anne Reserve No. 4", "Ste. Anne Reserve No. 4"),
        ("Cobb County", "Cobb County"),
    ],
)
def test_v11_review3_saint_prefix_in_span(text, value):
    assert ("ADDRESS", value) in _found(text)


@pytest.mark.parametrize(
    "text",
    ["patient HRT", "patient LOR", "patient DE cycle", "patient BFP", "pt CD day 3"],
)
def test_v11_review3_clinical_abbreviations_pass(text):
    assert not [e for e in _found(text) if e[0] == "NAME"]


@pytest.mark.parametrize("text,value", [("Re: JK", "JK"), ("Re: TL's IUI", "TL"), ("patient DE", "DE"), ("pt TI", "TI"), ("patient DC", "DC")])
def test_v11_review3_true_initials_stay_masked(text, value):
    assert ("NAME", value) in _found(text)


@pytest.mark.parametrize("text,value", [("inicjały pacjentki: AK", "AK"), ("patiente M. T.", "M. T."), ("inicjały: AK", "AK")])
def test_v11_review3_patient_initials_cues(text, value):
    assert ("NAME", value) in _found(text)


def test_v11_review3_vietnamese_digit_words_need_seven():
    assert not _found("số điện thoại không có, một hai ba ngày nữa")
    assert not _found("Số điện thoại của tôi? Năm nay tôi đi hai lần")
    assert _found("số điện thoại của tôi là không chín bốn một hai ba bốn năm sáu")


def test_v11_review3_dates_lists_of_values():
    for text in ["Scores 7/10, 8/10", "BMI 24.5, 26.1", "pain 4/10, 6/10 and 8/10"]:
        assert not [e for e in _found(text) if e[0] == "DATE"], text
    # not after a clinical word
    assert [e for e in _found("we met 13.4, 14.5") if e[0] == "DATE"]
    assert [e for e in _found("Call me 7/10, 8/10") if e[0] == "DATE"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("Patient initials: J. T.", "J. T."),
        ("re: J. T.", "J. T."),
        ("pacjentka J. K.", "J. K."),
        ("patient initials: J. T. S.", "J. T. S."),
    ],
)
def test_v11_review4_spaced_dotted_initials_one_span(text, value):
    assert ("NAME", value) in [(e.type.name, e.text) for e in RegexDetector().detect(text)]
    assert ("NAME", "J.") not in [(e.type.name, e.text) for e in RegexDetector().detect(text)]


def test_v11_review4_hebrew_signature_town_without_verb():
    spans = [e.text for e in RegexDetector().detect("גרה באלפרטה, GA")]
    assert "גרה באלפרטה" not in spans and "אלפרטה" in spans
    assert "אלפרטה" in [e.text for e in RegexDetector().detect("אלפרטה, GA")]


def _kinds(text):
    return [(e.type.name, e.text) for e in RegexDetector().detect(text)]


@pytest.mark.parametrize(
    "text",
    [
        "Patient AF scan done", "patient MII oocytes 8", "patient OPU done", "Patient NT scan", "patient ICM", "patient LPS",
        "patient NGS", "patient AZF", "patient DFI", "patient TNF", "patient APA", "patient PAI", "paciente OPU", "Re: MII",
        "Re: OPU", "pt AF 10 right", "patient AF 12 on the right", "patient TE biopsy", "pacjentka OPU", "La patiente MII",
    ],
)
def test_v11_review4_embryology_abbreviations_not_initials(text):
    assert not [e for e in _kinds(text) if e[0] == "NAME"]


def test_v11_review4_embryology_abbreviation_no_second_span():
    assert [e for e in _kinds("patient OPU Monday") if e[0] == "NAME"] == [("NAME", "OPU Monday")]


@pytest.mark.parametrize("text,value", [("patient AB scan", "AB"), ("pt KJ 12", "KJ"), ("patient AF", "AF"), ("patient GV", "GV"), ("pt AB called", "AB")])
def test_v11_review4_embryology_lookalike_initials_stay(text, value):
    assert ("NAME", value) in _kinds(text)


@pytest.mark.parametrize(
    "text",
    [
        "Find us in the red brick house past the Starbucks on King St",
        "Come to the yellow house past the Circle K on Hwy 20",
        "Visit us at the red house past the Tim Hortons on Main St",
    ],
)
def test_v11_review4_clinic_directions_not_a_home(text):
    assert not [e for e in _kinds(text) if e[0] == "ADDRESS"]


@pytest.mark.parametrize(
    "text",
    [
        "we live in the red brick house past the Starbucks on King St",
        "my house is the red brick house past the Starbucks on King St",
        "Come to my house past the Circle K on Hwy 20",
    ],
)
def test_v11_review4_home_directions_stay(text):
    assert [e for e in _kinds(text) if e[0] == "ADDRESS"]


@pytest.mark.parametrize(
    "text",
    [
        "Which street is the clinic on?\nMain Street",
        "What's the address of the clinic?\nKing Street West",
        "What street is the pharmacy on?\nBloor Street",
    ],
)
def test_v11_review4_street_reply_about_clinic_not_masked(text):
    assert not [e for e in _kinds(text) if e[0] == "ADDRESS"]


def test_v11_review4_street_reply_about_home_keeps_direction():
    assert ("ADDRESS", "King Street West") in _kinds("What street do you live on?\nKing Street West")
    assert ("ADDRESS", "Elm Street E") in _kinds("your address?\nElm Street E")
    assert ("ADDRESS", "Bloor Street") in _kinds("What is your street?\nBloor Street")


@pytest.mark.parametrize(
    "text",
    [
        "Nang trứng: hai, ba, năm, sáu, bảy, tám, chín, mười",
        "Tiêm một hai ba bốn năm sáu bảy",
        "Sau khi chuyển phôi, một hai ba bốn năm sáu bảy ngày sau thử thai",
        "Kích thước nang: hai, ba, bốn, năm, sáu, bảy, tám",
    ],
)
def test_v11_review4_vietnamese_counts_not_phone(text):
    assert not [e for e in _kinds(text) if e[0] == "PHONE"]


def test_v11_review4_vietnamese_phone_with_cue_stays():
    assert [e for e in _kinds("số điện thoại của tôi là một hai ba bốn năm sáu bảy tám chín") if e[0] == "PHONE"]
    assert [e for e in _kinds("số điện thoại: không chín tám bảy sáu năm bốn ba hai") if e[0] == "PHONE"]


@pytest.mark.parametrize(
    "text",
    ["Pay us via PayPal @torontofertility", "Cash App $torontofert for deposits", "Please send the deposit to our venmo @clinicpay"],
)
def test_v11_review4_clinic_payment_handle_not_masked(text):
    assert not [e for e in _kinds(text) if e[0] in ("ID", "ACCOUNT")]


@pytest.mark.parametrize(
    "text,value",
    [
        ("my venmo is @jane-doe-12", "@jane-doe-12"),
        ("I paid with Venmo @jane-doe-12", "@jane-doe-12"),
        ("Pay us via PayPal, my venmo is @jane-doe-12", "@jane-doe-12"),
    ],
)
def test_v11_review4_patient_payment_handle_stays(text, value):
    assert ("ID", value) in _kinds(text)


def test_v11_review4_payment_handle_allow_list():
    from phiproxy import Masker, Policy

    out = Masker(policy=Policy(allow=["@clinic-2"])).mask("Venmo: @clinic-2", "s").text
    assert "@clinic-2" in out


@pytest.mark.parametrize(
    "text,pieces",
    [
        ("my phone number is\n501\n234\n567", ["501", "234", "567"]),
        ("mi celular es:\n55\n1234\n5678", ["55", "1234", "5678"]),
        ("mój numer telefonu:\n501\n234\n567", ["501", "234", "567"]),
        ("mój telefon komórkowy to\n501\n234\n567", ["501", "234", "567"]),
        ("numer telefonu:\n22\n123\n45\n67", ["22", "123", "45", "67"]),
    ],
)
def test_v11_review4_phone_pieces_other_shapes(text, pieces):
    got = [v for t, v in _kinds(text) if t == "PHONE"]
    assert all(p in got for p in pieces)


@pytest.mark.parametrize(
    "text",
    ["call me\n501\n234\n567", "Version\n501\n234\n567", "Estradiol numbers\n501\n234\n567", "my phone number is\n12\n34"],
)
def test_v11_review4_phone_pieces_lookalikes(text):
    assert not [e for e in _kinds(text) if e[0] == "PHONE"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("mi número de cuenta es 1234 5678 90", "1234 5678 90"),
        ("account 1234 5678 90", "1234 5678 90"),
        ("Account number is\n1234\n5678\n9012", "1234\n5678\n9012"),
        ("numer konta 12 3456 7890", "12 3456 7890"),
        ("my routing number is 021 000 021", "021 000 021"),
        ("routing: 021-000-021", "021-000-021"),
    ],
)
def test_v11_review4_account_and_routing_groups(text, value):
    assert ("ACCOUNT", value) in _kinds(text)


@pytest.mark.parametrize("text", ["account 12 34", "the account\n1234\n5678", "Ticket 021 000 021", "call routing 604 555 0123"])
def test_v11_review4_account_group_lookalikes(text):
    assert not [e for e in _kinds(text) if e[0] == "ACCOUNT" and len(e[1]) > 6]


@pytest.mark.parametrize(
    "text,value",
    [
        ("my coordinates are lat 44.6488 lon -63.5752", "lat 44.6488 lon -63.5752"),
        ("GPS: N 44.65 W 63.57", "N 44.65 W 63.57"),
        ("my GPS is 44 39.5 N 63 34.2 W", "44 39.5 N 63 34.2 W"),
        ("coordonnées GPS 45.50 N, 73.57 O", "45.50 N, 73.57 O"),
    ],
)
def test_v11_review4_gps_other_forms(text, value):
    assert ("ADDRESS", value) in _kinds(text)


@pytest.mark.parametrize("text", ["lat 44.6 lon", "N 44.65 W 63.57", "score 44 39.5 N 63 34.2 W", "Group N 5 O 6"])
def test_v11_review4_gps_other_forms_need_cue(text):
    assert not [e for e in _kinds(text) if e[0] == "ADDRESS"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("my email is k-e-l-l-i-at-gmail-dot-com", "k-e-l-l-i-at-gmail-dot-com"),
        ("email: k, e, l, l, i, at, gmail dot com", "k, e, l, l, i, at, gmail dot com"),
        ("האימייל שלי הוא kelli שטרודל gmail נקודה com", "kelli שטרודל gmail נקודה com"),
    ],
)
def test_v11_review4_spelled_email_variants(text, value):
    assert ("EMAIL", value) in _kinds(text)


@pytest.mark.parametrize("text", ["a-b-c-at-home-dot-com", "my plan is to-do-at-noon", "ללא שטרודל gmail נקודה com"])
def test_v11_review4_spelled_email_lookalikes(text):
    assert not [e for e in _kinds(text) if e[0] == "EMAIL"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("I live on Tyendinaga Mohawk Territory", "Tyendinaga Mohawk Territory"),
        ("I live in the county of Simcoe", "county of Simcoe"),
        ("I live on Township Road 512", "Township Road 512"),
        ("vivo en el municipio de Zapopan, Jalisco", "municipio de Zapopan"),
        ("mieszkam w gminie Lesznowola", "gminie Lesznowola"),
    ],
)
def test_v11_review4_county_and_territory_variants(text, value):
    assert ("ADDRESS", value) in _kinds(text)


@pytest.mark.parametrize(
    "text",
    ["the county of Simcoe is large", "I visited Mohawk Territory", "el municipio de Zapopan aprobó la ley", "Township Road 512 is closed"],
)
def test_v11_review4_county_variants_need_residence_cue(text):
    assert not [e for e in _kinds(text) if e[0] == "ADDRESS"]


@pytest.mark.parametrize(
    "text,value",
    [
        ("pagué con el cheque #4521", "#4521"),
        ("pagué con cheque 4521", "4521"),
        ("I wrote you a cheque, number 4521", "4521"),
    ],
)
def test_v11_review4_cheque_first_person_verbs(text, value):
    assert ("ACCOUNT", value) in _kinds(text)


@pytest.mark.parametrize("text", ["cheque no. 4521", "chèque #4521", "the cheque number 4521", "pagó con cheque 4521"])
def test_v11_review4_cheque_bare_stay_visible(text):
    assert not [e for e in _kinds(text) if e[0] == "ACCOUNT"]


# ---- v11 final round 5, findings 1-7 ----
def _fin_masker():
    from phiproxy import Masker, Policy

    return Masker(policy=Policy(staff=["Dr. Sarah Lee"], allow=["100 Main Street, Suite 200, Toronto"]))


@pytest.mark.parametrize(
    "text",
    [
        "Please come to Reception at 8 am for your scan.",
        "Arrived at Mount Sinai at 8.",
        "Please stay in Fasting mode.",
        "I'm in Recovery now, Room 4.",
        "Please come to Billing to pay.",
        "Arrived at Gate B.",
        "Community of Practice for Fertility.",
        "City of Toronto Public Health guidelines apply.",
        "We are near Fertility Centre.",
        "Thanks for reaching out to Maple Fertility!",
        "Please make the cheque out to Maple Fertility Clinic.",
        "We reach out to Sun Life for pre-authorization.",
        "Please reach out to Billing if you have questions.",
        "You will need to go back to Northside Associates for records.",
        "Send results back to Mount Sinai.",
        "Currently in Treatment Cycle 2.",
        "Come back to Maple for the scan.",
        "I moved to Recovery after the procedure.",
        "Jestem z Polski. Mąż z Ukrainy.",
        "patient ASAP",
        "Patient ENROLLED in study, patient ENDOMETRIOSIS stage 3",
        "patient ACTH",
        "patient ADHD",
        "patient aPTT",
        "patient DUPLICATE CHART",
        "patient AUTOIMMUNE",
    ],
)
def test_v11_final_ordinary_text_not_masked(text):
    assert _fin_masker().mask(text, "s").text == text


@pytest.mark.parametrize(
    "text,value",
    [
        ("We live in Oakville now.", "Oakville"),
        ("I grew up in Pickering.", "Pickering"),
        ("We moved to Wolfville last year.", "Wolfville"),
        ("I'm from Truro.", "Truro"),
        ("She's originally from Sackville.", "Sackville"),
        ("My husband and I live near Oakville.", "Oakville"),
        ("Pochodzę z Krakowa.", "Krakowa"),
        ("Mieszkam w Gdyni.", "Gdyni"),
        ("J'habite à Wolfville.", "Wolfville"),
        ("patiente à Wolfville", "Wolfville"),
        ("My husband and I arrived from Aleppo.", "Aleppo"),
        ("We're out past Indian Brook.", "Indian Brook"),
    ],
)
def test_v11_final_real_residence_cues_still_masked(text, value):
    assert value not in _fin_masker().mask(text, "s").text


@pytest.mark.parametrize(
    "text",
    [
        "patient WNL", "patient TBA", "patient NAD", "patient LDL", "patient SLE", "patient CKD", "patient COS",
        "patient SAB", "patient NO show", "patient POC results", "patient LLQ pain", "patient CMP normal",
        "patient MFM referral", "patient GS seen", "patient SCH", "patient IUP", "patient TWW", "patient PE exam",
        "patient UA results", "patient PB biopsy", "patient SM results", "patient AH exam", "patient LBR",
    ],
)
def test_v11_final_chart_abbreviations_not_initials(text):
    assert _fin_masker().mask(text, "s").text == text


@pytest.mark.parametrize("text", ["Pt AB called re: IUI", "patient KJ called", "patient PE called"])
def test_v11_final_initials_lookalikes_still_masked(text):
    out = _fin_masker().mask(text, "s").text
    assert "[NAME_1]" in out


@pytest.mark.parametrize(
    "text",
    [
        "Cell count\n250\n300\n150",
        "Cell culture\n250\n300\n450",
        "Phone number confirmed. Doses today:\n150\n225\n300",
        "Número de teléfono\n150\n225\n300",
        "Phone number confirmed. Doses today:\n225\n300\n150",
    ],
)
def test_v11_final_pieces_not_phone(text):
    assert _fin_masker().mask(text, "s").text == text


@pytest.mark.parametrize(
    "text",
    ["Phone number\n604\n555\n0199", "My cell\n604\n555\n0199", "Numer telefonu\n600\n123\n456"],
)
def test_v11_final_pieces_real_phone_still_masked(text):
    out = _fin_masker().mask(text, "s").text
    assert "[PHONE_1]" in out and "0199" not in out and "123" not in out.replace("[PHONE_1]", "")


def test_v11_final_street_reply_after_clinic_question():
    m = _fin_masker()
    t = "Which clinic location? Yonge Street or Main Street?\nMain Street"
    assert m.mask(t, "s").text == t
    # a home-address question still masks the bare street reply
    assert "Oak Hollow" not in m.mask("What is your home address?\nOak Hollow Lane", "s").text


def test_v11_final_spoken_plus_pair_grouped_phone():
    d = RegexDetector()
    for t in ("Appelez plus 33 6 12 34 56 78. Trois jours.", "plus 1 4 1 6 5 5 5 0 1 8 2 and then 3 vials", "más 34 612 345 678"):
        assert [e for e in d.detect(t) if e.type is T.PHONE], t
    for t in ("plus 5 10 15 20 25 30 35", "más 1 2 3 4 5 6 7 8 9 10", "plus 20 100 200 300 units", "plus 2 4 6 8 10 12 14"):
        assert not [e for e in d.detect(t) if e.type is T.PHONE], t


@pytest.mark.parametrize(
    "text",
    ["Patiente IMC 24.", "Patiente: CCA ok", "Pacjent IMC 24.", "Paciente FUM 3 de octubre."],
)
def test_v11_final4_non_english_chart_abbreviations_not_initials(text):
    assert not [e for e in RegexDetector().detect(text) if e.type is T.NAME], text


def _ids(text):
    return [e.text for e in RegexDetector().detect(text) if e.type in (T.ID, T.HEALTH_CARD)]


@pytest.mark.parametrize(
    "text,value",
    [
        ("Landing tonight, booking ref ABX7KM, thanks", "ABX7KM"),
        ("itinerary PNR 4HD8ZT", "4HD8ZT"),
        ("record locator: QW3R7Y", "QW3R7Y"),
        ("Hotel reservation LM9P2X for two nights", "LM9P2X"),
        ("vuelo IB 6123, localizador XT4P8K", "XT4P8K"),
        ("code de réservation : 7HJ2MQ", "7HJ2MQ"),
        ("kod rezerwacji 5ZXC3N", "5ZXC3N"),
        ("קוד הזמנה P8D2QW בבקשה", "P8D2QW"),
        ("e-ticket 131-5550123456 for Monday", "131-5550123456"),
        ("bilet elektroniczny 080 5550 1234 56", "080 5550 1234 56"),
        ("Aadhaar: 5550 1234 5678", "5550 1234 5678"),
        ("PhilSys ID ko po: 5550-1234-5678-9012", "5550-1234-5678-9012"),
        ("my NIN is 55501234567", "55501234567"),
        ("registre national 55.01.23-456.78 merci", "55.01.23-456.78"),
        ("Counsel for the IPs, WSBA No. 55512", "55512"),
        ("Attorney bar number is 55512.", "55512"),
        ("nr w izbie BAR 55512, podpisze", "BAR 55512"),
        ("numéro de membre du Barreau est le 555123-4", "555123-4"),
        ("Notary commission no. NP 555123", "NP 555123"),
        ("Parentage case number is 26-3-05512-1 SEA.", "26-3-05512-1 SEA"),
        ("expediente del juzgado es FAM-2025/5512", "FAM-2025/5512"),
        ("PESEL: 8S0555O4531", "8S0555O4531"),
        ("band number is 0555-1234", "0555-1234"),
        ("パスポート番号はAB1234567です", "AB1234567"),
        ("ホテルの予約番号はHB-5512004。", "HB-5512004"),
    ],
)
def test_v12_travel_legal_and_foreign_ids(text, value):
    assert any(value in v or v in value for v in _ids(text)), _ids(text)


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("insurance card number WXA 4410 2287 on the form", T.HEALTH_CARD, "WXA 4410 2287"),
        ("subscriber, member ID OH 9921 4420 7.", T.HEALTH_CARD, "OH 9921 4420 7"),
        ("מספר חבר WAX 2241 8830, פוליסה", T.HEALTH_CARD, "WAX 2241 8830"),
        ("כרטיס בריאות SK: 555 345 789 |", T.HEALTH_CARD, "555 345 789"),
    ],
)
def test_v12_member_card_in_letter_digit_groups(text, etype, value):
    assert value in [e.text for e in RegexDetector().detect(text) if e.type is etype]


@pytest.mark.parametrize(
    "text",
    [
        "the bar is open until 11, booking 2 nights, confirmation code sent by email",
        "booking ref is in the email; confirmation number 1234",
        "reservation MONDAY for 4 at the bar 5pm",  # no digit in the word, bar cue without a long number
        "e-ticket sent, flight 131 on 2026-12-01",
        "member since 2019, insurance plan AB 12",
        "case number is pending, bar number unknown",
        "PNR is on the screen",
        "Aadhaar was requested, phone 555 010 2288",
        "national ID 12345",
    ],
)
def test_v12_id_lookalikes_not_masked(text):
    assert not _ids(text), _ids(text)


def test_v12_e_ticket_not_a_helpdesk_ticket():
    # an IT "ticket" number still passes, an airline e-ticket never does
    assert not _ids("ticket 5551234567890 opened with IT")
    assert _ids("e-ticket 5551234567890 for the flight")


def test_v12_re_ticket_still_helpdesk():
    # "Re ticket": the "e" belongs to "Re", not to "e-ticket"
    assert not _ids("Re ticket #XY-20931: escalated")


def _v12_vals(text, kind):
    return [e.text for e in RegexDetector().detect(text) if e.type is kind]


@pytest.mark.parametrize(
    "text,value",
    [
        ("- Paternal grandfather: Ed Smith, d. June 2011 at 93, cause unknown", "93"),
        ("I-2: maternal grandmother, Ann Lee, d. at 92, no cancer", "92"),
        ("- Grandmother, Rita Jones, alive, 93, diabetes", "93"),
        ("Maternal grandmother, 91, alive", "91"),
        ("II-3 mother (94), diabetes", "94"),
        ("d. 2019 aged 92, grandfather", "92"),
        ("Grandma died in 1987 at 91 of cancer, so she was 91.", "91"),
        ("Бабуся померла у 93 роки", "93 роки"),
    ],
)
def test_v12_old_age_in_pedigree(text, value):
    assert value in _v12_vals(text, T.AGE)


@pytest.mark.parametrize(
    "text",
    [
        "- Grandfather, Ed Smith, died 1998-11-02 aged 58, heart attack",
        "Dad d. at 85",
        "my brother died at 61",
        "Maternal grandmother, 89, alive",
        "my brother, 100 mg daily",
        "Mother Anna 91 Elm Street",
        "alive 95 days ago",
        "Patient: I live in unit 95, alive and well",
    ],
)
def test_v12_old_age_lookalikes(text):
    assert not _v12_vals(text, T.AGE)


@pytest.mark.parametrize(
    "text,value",
    [
        ("Прилетимо до міста 14 грудня.", "14 грудня"),
        ("Мы прилетим 14 декабря 2026, рейс поздно.", "14 декабря 2026"),
        ("Приём 3-го марта в клинике", "3-го марта"),
    ],
)
def test_v12_cyrillic_dates(text, value):
    assert value in _v12_vals(text, T.DATE)


@pytest.mark.parametrize(
    "text",
    [
        "У меня 14 котов",
    ],
)
def test_v12_date_lookalikes(text):
    assert not _v12_vals(text, T.DATE)


def test_v12_real_dates_kept():
    assert "the 4th" in _v12_vals("Can we do the 4th at noon?", T.DATE)
    assert "3.5-12" in _v12_vals("seen 3.5-12 ok", T.DATE)


def _v12_found(text):
    return {(e.type.name, e.text) for e in RegexDetector().detect(text)}


def test_v12_foreign_addresses_and_postcodes():
    f = _v12_found("Our address: Lot 7 Block 3 Palm Heights, Davao City, 8000. Thanks")
    assert ("ADDRESS", "Lot 7 Block 3 Palm Heights, Davao City") in f and ("POSTAL_CODE", "8000") in f
    assert ("ADDRESS", "9 Elmwood Rise, Leeds") in _v12_found("Please invoice 9 Elmwood Rise, Leeds.")
    assert ("POSTAL_CODE", "560001") in _v12_found("agency in Bengaluru, pin 560001.")
    assert ("POSTAL_CODE", "2000") in _v12_found("postcode 2000 for the courier")
    assert ("ADDRESS", "Calle Mayor 14, 3º B") in _v12_found("vivo en Calle Mayor 14, 3º B, 28013 Madrid")
    assert ("ADDRESS", "Calle 5 de Mayo 77, Tepic") in _v12_found("Domicilio: Calle 5 de Mayo 77, Tepic, Nayarit")
    assert ("ADDRESS", "rue Principale nord, au 305") in _v12_found("sur la rue Principale nord, au 305.")
    assert ("POSTAL_CODE", "03940") in _v12_found("domiciliados en Av. Reforma 12, piso 4, Col. Centro, Ciudad de México, 03940, y la gestante")
    assert ("ZIP", "98101") in _v12_found("¿Y el código postal?\n[00:00:18] Speaker 2: Nueve ocho uno cero uno, creo. No, espere, 98101, ese.")
    assert ("ADDRESS", "Tilo") in _v12_found("I live on the reserve near Tilo and drive down")
    assert ("ADDRESS", "Obolon, Kyiv") in _v12_found("Our home is Obolon, Kyiv if you need to send anything.")
    assert ("ADDRESS", "Cebu") in _v12_found("I moved to Regina in March from Cebu, I work as an aide.")
    assert ("ADDRESS", "Pune") in _v12_found("We're from Pune and arrive Monday.")


def test_v12_foreign_address_lookalikes_not_masked():
    for t in [
        "My pin 4412 for the portal",  # a four-digit PIN is not a postcode
        "Lot 5512 expires soon, block of 12 vials",  # a product lot, not a lot-and-block address
        "FSH levels rise in 3 days, then close the cycle",
        "We moved to Recovery after the procedure.",
        "I moved from Gonal-f to Menopur 75.",
        "We are from the Nigerian community.",
        "We are from Poland.",
        "I'm from Canada.",
        "address on file, 2026",  # a year after an address cue is not a postcode
        "She lives well, 4000 steps a day",
    ]:
        assert not {x for x in _v12_found(t) if x[0] in ("ADDRESS", "POSTAL_CODE", "ZIP")}, t


def test_v12_school_and_hospital_employer():
    assert ("EMPLOYER", "Liceum Ogólnokształcącego im. Kopernika") in _v12_found("Chodzi do szkoły Liceum Ogólnokształcącego im. Kopernika. Mam")
    assert ("EMPLOYER", "Uniwersytecie Jagiellońskim") in _v12_found("Studiuje na Uniwersytecie Jagiellońskim w Krakowie.")
    assert ("EMPLOYER", "Hospital Infantil Santa Ana") in _v12_found("Mi hijo trabaja en Hospital Infantil Santa Ana hoy.")
    assert ("EMPLOYER", "תיכון ליד האוניברסיטה") in _v12_found("בית הספר: תיכון ליד האוניברסיטה. שמי")
    assert ("EMPLOYER", "אוניברסיטת חיפה") in _v12_found("מלמדת באוניברסיטת חיפה, והבעל")
    # Lowercase words after the institution word are not part of the name.
    assert ("EMPLOYER", "Hospital Infantil Santa Ana hoy") not in _v12_found("Mi hijo trabaja en Hospital Infantil Santa Ana hoy.")
    assert not [x for x in _v12_found("Chodzi do szkoły w Gdańsku.") if x[0] == "EMPLOYER"]


def test_v12_uk_postcode_and_town_postcode():
    assert ("POSTAL_CODE", "AB12 3CD") in _v12_found("Postcode AB12 3CD please")
    assert ("POSTAL_CODE", "M1 1AE") in _v12_found("Send to 4 Rowan Close, Salford M1 1AE.")
    assert ("POSTAL_CODE", "45600") in _v12_found("Dirección de entrega: Av. Norte 12, Col. Sol, Tlaquepaque 45600. Gracias")
    assert ("POSTAL_CODE", "06600") in _v12_found("domiciliados en Calle Sur 22, Piso 9, Ciudad de México, 06600 (los padres)")
    # Capitals and digits in other shapes are not a postcode.
    assert not [x for x in _v12_found("Lab tube AB123 CD and sample X12 ready") if x[0] == "POSTAL_CODE"]
    assert not [x for x in _v12_found("Dirección: calle Sur 1, 2026 fue el año") if x[0] == "POSTAL_CODE"]


def _b1_found(text):
    return {(e.type.name, e.text) for e in RegexDetector().detect(text)}


def _b1_masked(text):
    from phiproxy import Masker, Policy

    return Masker(policy=Policy()).mask(text, "s").text


@pytest.mark.parametrize(
    "text",
    [
        "your portal PIN 123456",
        "reset your pin 123456",
        "My PIN: 123456 for the portal",
        "the bank PIN is 123456",
        "pin 1234",
    ],
)
def test_v12_review1_pin_secret_not_postcode(text):
    assert not [x for x in _b1_found(text) if x[0] in ("POSTAL_CODE", "ZIP")]


def test_v12_review1_pin_in_address_still_postcode():
    assert ("POSTAL_CODE", "560001") in _b1_found("agency in Bengaluru, pin 560001.")
    assert ("POSTAL_CODE", "411001") in _b1_found("Our address: 12 MG Road, Pune pin 411001")
    assert ("POSTAL_CODE", "560001") in _b1_found("PIN code 560001")
    assert not _b1_found("reset your PIN code 123456")


def test_v12_review1_postal_code_one_type():
    f = _b1_found("postal code 12345 format")
    assert [x for x in f if x[0] in ("POSTAL_CODE", "ZIP")] == [("POSTAL_CODE", "12345")]
    assert ("ZIP", "98101") in _b1_found("¿Y el código postal?\n[00:00:18] Speaker 2: Nueve ocho uno cero uno, creo. No, espere, 98101, ese.")


@pytest.mark.parametrize(
    "text",
    [
        "va al Hospital Regina",
        "je vais à l'Hôpital Regina",
        "je vais à la Clinique de fertilité",
        "voy a la Clínica Santa Ana mañana",
        "Pracuje w Szpitalu",
        "chodzi do szkoły Liceum",
        "idę do Szpitala Bielańskiego jutro",
        "trabaja en la Clínica de fertilidad",
    ],
)
def test_v12_review1_employer_no_visit_or_generic(text):
    assert not [x for x in _b1_found(text) if x[0] == "EMPLOYER" and (len(x[1]) > 7 or " " in x[1])]


def test_v12_review1_employer_named_still_masked():
    assert ("EMPLOYER", "Hospital Infantil Santa Ana") in _b1_found("Mi hijo trabaja en Hospital Infantil Santa Ana hoy.")
    assert ("EMPLOYER", "Université de Montréal") in _b1_found("elle étudie à l'Université de Montréal")
    assert ("EMPLOYER", "Liceum Ogólnokształcącego im. Kopernika") in _b1_found("Chodzi do szkoły Liceum Ogólnokształcącego im. Kopernika. Mam")
    assert not [x for x in _b1_found("trabaja en la Clínica de fertilidad") if "de" in x[1].split()]


@pytest.mark.parametrize(
    "text,age",
    [
        ("babcia zmarła mając 92 lata", "92"),
        ("dziadek zmarł mając 95 lat", "95"),
        ("Passed away in 2015 at the age of 94", "94"),
        ("died in 2015 aged 92", "92"),
        ("Died in 2015 at 94", "94"),
    ],
)
def test_v12_review1_age_after_death_word(text, age):
    assert ("AGE", age) in _b1_found(text)


@pytest.mark.parametrize("text", ["He died at 95 Elm St", "She passed away at 100 mg", "He died on June 3 at 10 pm", "died in 2015 at 5 pm"])
def test_v12_review1_age_after_death_lookalikes(text):
    assert not [x for x in _b1_found(text) if x[0] == "AGE"]


def test_v12_review1_indian_address_with_pin():
    assert _b1_masked("House no 45, Sector 21, Gurgaon 122001") == "[ADDRESS_1]"
    assert _b1_masked("Flat 301, Sunrise Apts, MG Road, Bangalore - 560001") == "[ADDRESS_1]"
    for t in ["Flat 301 is nice", "House no 45 is fine, call 122001 times", "Bangalore - 560001"]:
        assert not [x for x in _b1_found(t) if x[0] == "ADDRESS"], t


def test_v12_review1_uk_mexico_phone_after_cue():
    assert _b1_masked("Call me on 07911 123456") == "Call me on [PHONE_1]"
    assert _b1_masked("phone: 07911 123 456 thanks") == "phone: [PHONE_1] thanks"
    assert _b1_masked("My number is (55) 1234-5678") == "My number is [PHONE_1]"
    for t in ["07911 123456", "(55) 1234-5678", "order 07911 123456 shipped"]:
        assert not [x for x in _b1_found(t) if x[0] == "PHONE"], t


def test_v12_review1_philippine_brgy_address():
    assert _b1_masked("Blk 5 Lot 7 Brgy. San Antonio, Quezon City") == "[ADDRESS_1]"
    assert _b1_masked("Blk 5 Lot 7 Brgy San Antonio, Quezon City.") == "[ADDRESS_1]."
    assert not [x for x in _b1_found("Brgy. is a unit") if x[0] == "ADDRESS"]


def test_v12_review1_nhs_and_my_number_masked():
    # The value must be masked; its type may be PHONE (phone rules are never suppressed by a nearby "NHS").
    assert "943 476 5919" not in _b1_masked("My NHS number is 943 476 5919")
    assert "1234 5678 9012" not in _b1_masked("My Number 1234 5678 9012")
    assert "[PHONE" in _b1_masked("my number is 416 555 0147")
    assert "416-555-0142" not in _b1_masked("I spoke to NHS, my number is 416-555-0142")


def test_v12_final2_age_rule_linear_and_ranges_masked():
    import time

    d = RegexDetector()
    t0 = time.time()
    d.detect("alive" + " " * 20000)
    d.detect("My grandfather died" + "\n" * 8000 + "and the clinic called.")
    assert time.time() - t0 < 20
    # A d.m-yy shape stays a possible date even after a range word (no exclusion: "DOB (ref) 3.5-12").
    assert [e for e in d.detect("DOB (ref) 3.5-12") if e.type is T.DATE]


def _v13n(text):
    return [e.text for e in RegexDetector().detect(text) if e.type is T.NAME]


def test_v13_header_last_first_names():
    assert "OKAFOR, DANIELA R" in _v13n("Page 2 of 3 / OKAFOR, DANIELA R / MRN 0012345")
    assert "LUNDGREN, PETRA T" in _v13n("CONSENT FORM\nPage 4 of 4 / LUNDGREN, PETRA T / DOB 1990-01-02 / MRN 55")
    assert "LUNDGREN, PETRA" in _v13n("report text | LUNDGREN, PETRA | Page 2 of 3")
    # No page or field next to it: not a header.
    assert not any("TUBAL" in n for n in _v13n("Findings: TUBAL, PATENT bilaterally"))
    assert not any("IVF" in n for n in _v13n("Page 2 of 3 / IVF, ICSI / MRN 0012345"))


def test_v13_sign_off_name_list():
    assert any("Pip" in n and "Tess" in n for n in _v13n("Love,\nMo, Pip and Tess"))
    # The list must end the line; ordinary words after a thanks are not names.
    assert not any("Monday" in n for n in _v13n("Thanks,\nMonday, Tuesday and Friday"))


def test_v13_heard_as_and_works_at():
    assert "Aliff" in _v13n("AI note: husband's name was heard as 'Aliff', corrected by the nurse.")
    assert not any("Cycle" in n for n in _v13n("The word was heard as 'Cycle' on the call."))
    assert "Dex" in _v13n("Dex works at Harbor Freight and I teach.")
    assert not any("Clomid" in n for n in _v13n("Clomid works for most patients."))
    assert not any("works" in n for n in _v13n("it works at night"))


def test_v13_couple_second_name_echo():
    from phiproxy import Masker

    m = Masker(detectors=[RegexDetector()])
    out = m.mask("Help Hannah and Rob bring home a baby.\nMy name is Hannah Weir.\nRob works at Pine Roofing.", "s1").text
    assert "Rob" not in out and "Hannah" not in out


def test_v13_devanagari_lao_hebrew_names():
    assert "प्रकाश राई" in _v13n("Hello, मेरो नाम प्रकाश राई हो। Thanks")
    assert "सरिता गुरुङ" in _v13n("नमस्ते, म सरिता गुरुङ हुँ। See you")
    assert "सरिता गुरुङ" in _v13n("धन्यवाद,\nसरिता गुरुङ")
    assert not _v13n("म धेरै खुसी हुँ")
    assert not _v13n("मेरो नाम हो")
    assert "ມະນີ ສີສຸວັນ" in _v13n("ສະບາຍດີ, ຂ້ອຍຊື່ ມະນີ ສີສຸວັນ. I want to move it")
    assert "שוורץ" in _v13n("Nazywam się Alina Szwarc, po hebrajsku שוורץ.")
    assert not any("תודה" in n for n in _v13n("I wrote this in Hebrew: תודה רבה."))


def test_v13_english_letter_names_spelled():
    assert "gee you zed em ay en" in _v13n("My last name is spelled gee you zed em ay en, thanks")
    assert not _v13n("you are an ex and why not")
    assert not any("gee" in n for n in _v13n("gee you zed em ay en"))  # no spelling or name cue


def test_v13_new_rules_linear():
    import time

    d = RegexDetector()
    t0 = time.time()
    for cue in ("Page 1 of 2 /", "name was heard as", "works at", "मेरो नाम", "ຊື່"):
        for fill in (" ", "\n"):
            d.detect(cue + fill * 20000)
    assert time.time() - t0 < 60


@pytest.mark.parametrize(
    "text,value",
    [
        ("موعدي في ١٢ ديسمبر — please confirm", "١٢ ديسمبر"),
        ("إجازة من ١ فبراير", "١ فبراير"),
        ("12 كانون الأول 1990", "12 كانون الأول 1990"),
        ("Taariikhda waa labaatan iyo shan Maajo 1989.", "labaatan iyo shan Maajo 1989"),
        ("waa shan Luuliyo", "shan Luuliyo"),
        ("Tuesday is fine, martes veintisiete de este mes", "martes veintisiete"),
        ("jeudi vingt-sept", "jeudi vingt-sept"),
        ("Please confirm your date of birth.\nVisitor: 09 30 1988\nthanks", "09 30 1988"),
        ("DOB 1988 09 30", "1988 09 30"),
        ("charged from, I think, the third of last month.", "third of last month"),
        ("I lost the pregnancy in May.", "May"),
        ("Our retrieval is planned for January.", "January"),
        ("Nous attendons un bébé pour juillet!", "juillet"),
    ],
)
def test_v13_date_forms(text, value):
    assert value in _v12_vals(text, T.DATE)


@pytest.mark.parametrize(
    "text",
    [
        "Hace ٣ días",
        "waa shan nin",
        "martes dos pacientes",
        "el martes veinte pacientes vinieron",
        "my number is 09 30 1988 in the ledger",
        "I may go in May's clinic",
        "Please ask May Chen about it",
        "Thanks for May's invoice",
        "the third of the cakes",
        "she said she would go for it",
        "pour mars' dossier",
    ],
)
def test_v13_date_lookalikes(text):
    assert not _v12_vals(text, T.DATE)


@pytest.mark.parametrize(
    "text,value",
    [
        ("My grandmother lived to 96 and her sister to 93, so", "93"),
        ("dzwoniąca, Danuta Kowal (lat 91), to babcia", "91"),
        ("המתקשרת, חנה כהן (בת 92), היא סבתא", "92"),
    ],
)
def test_v13_old_age_forms(text, value):
    assert value in _v12_vals(text, T.AGE)


@pytest.mark.parametrize(
    "text",
    [
        "my sister moved to 95 Elm Street",
        "my sister to 93 people",
        "Clinic (lat 45)",
        "(lat 91 items)",
    ],
)
def test_v13_old_age_lookalikes(text):
    assert not _v12_vals(text, T.AGE)


def test_v13_date_rules_linear():
    import time

    d = RegexDetector()
    t0 = time.time()
    for cue in ("date of birth", "DOB:", "martes", "shan", "12", "for", "in", "the third of", "(lat", "my sister to", "12 "):
        for fill in (" ", "\n", "\t", "9 "):
            d.detect(cue + fill * 4000)
    assert time.time() - t0 < 60


# --- v13 identifiers: handles, documents, short numbers, partial digits, ZIPs ---------------------
def _v13_ids(text, *kinds):
    kinds = kinds or (T.ID, T.ACCOUNT, T.SSN, T.MRN, T.HEALTH_CARD, T.URL, T.ZIP)
    return [e.text for e in RegexDetector().detect(text) if e.type in kinds]


@pytest.mark.parametrize(
    "text,value",
    [
        ("Posted by river_otter_41 on Oct 3", "river_otter_41"),
        ("Reply from QuietLakeMorning: thanks all", "QuietLakeMorning"),
        ("\nmapleleaf_mama88 replied:\n> hi", "mapleleaf_mama88"),
        ("> TTC_in_OH wrote: has anyone", "TTC_in_OH"),
        ("@ember_fox: hey\nsam.k: hi there", "sam.k"),
    ],
)
def test_v13_forum_handles(text, value):
    assert value in _v13_ids(text, T.ID)


@pytest.mark.parametrize(
    "text",
    [
        "Posted by Monday morning staff",
        "Reply from Dr Smith about the results",
        "Thread started by Maria last week",
        "Laura wrote: see you at 3",
        "the nurse replied: yes",
        "sam.k: hi there",  # a label alone, no handle speakers in the transcript
    ],
)
def test_v13_forum_handle_lookalikes(text):
    assert not _v13_ids(text, T.ID)


@pytest.mark.parametrize(
    "text,value",
    [
        ("Passport is C0482917, issued in Canada. Husband's is P7731884K", "P7731884K"),
        ("Her pasaporte vence pronto. El de él es G5512096", "G5512096"),
    ],
)
def test_v13_second_passport(text, value):
    assert value in _v13_ids(text, T.ID)


def test_v13_passport_shape_needs_the_cue():
    assert not _v13_ids("Passport copy sent. The model is X12 and the room is B4", T.ID)
    assert not _v13_ids("Passport copy attached. The kit code is AB123", T.ID)


def test_v13_plate_after_vehicle_words():
    assert "TN 8K4 2217" in _v13_ids("Plate on his gray truck TN 8K4 2217. Security notified", T.ID)
    assert "OH 5TR 9021" in _v13_ids("license plate OH 5TR 9021", T.ID)
    assert not _v13_ids("Plate 3 was read on Tuesday at 4 pm", T.ID)
    assert not _v13_ids("plate of food and some water", T.ID)


def test_v13_cpf_and_itin():
    assert "123.456.789-09" in _v13_ids("Meu CPF é 123.456.789-09, obrigada", T.ID)
    assert "12345678909" in _v13_ids("CPF 12345678909", T.ID)
    assert "912-70-5531" in _v13_ids("me piden un ITIN y es 912-70-5531", T.SSN)
    assert "989-71-4040" in _v13_ids("My taxpayer ID number is 989-71-4040", T.SSN)
    assert not _v13_ids("the version is 1.234.567 and 12-70-5531", T.ID, T.SSN)


@pytest.mark.parametrize(
    "text,value",
    [
        ("los últimos cuatro, 4417", "4417"),
        ("ostatnie cztery cyfry: 4417", "4417"),
        ("les 4 derniers chiffres : 4417", "4417"),
    ],
)
def test_v13_last_four_after_cue(text, value):
    assert value in _v13_ids(text, T.ID)


@pytest.mark.parametrize("text", ["últimos cuatro días 4417", "the last four weeks of 2026"])
def test_v13_last_four_lookalikes(text):
    assert not _v13_ids(text, T.ID)


def test_v13_partial_mrn_cues():
    assert "4417" in _v13_ids("mi MRN termina en 4417", T.MRN)
    assert "4417" in _v13_ids("MRN kończy się na 4417", T.MRN)
    assert "4417" in _v13_ids("ostatnie 4 cyfry MRN: 4417", T.MRN)
    q = "> Please reply with your last name and the last four digits of your MRN.\n\nDuong, 4417\n\n> And your date of birth?\n\n3/14/88"
    assert "4417" in _v13_ids(q, T.MRN)
    assert not _v13_ids("Send the last four digits of your MRN. We are at 2118 Elm Hill Pike", T.MRN)
    assert not _v13_ids("Send the last four digits of your MRN by Friday", T.MRN)


@pytest.mark.parametrize(
    "text,value",
    [
        ("The employee number on your file is 428-1190 ok", "428-1190"),
        ("Mon numéro d'employée, c'est 88-4210", "88-4210"),
        ("le dossier de police est le 26-118342", "26-118342"),
        ("matricula consular, number CM 0045 8871", "CM 0045 8871"),
        ("participant number 774-5120", "774-5120"),
    ],
)
def test_v13_short_ids_after_cue(text, value):
    assert value in _v13_ids(text, T.ID)


@pytest.mark.parametrize(
    "text,value",
    [
        ("numéro de police 774512-08", "774512-08"),
        ("el grupo es el G 77412", "G 77412"),
    ],
)
def test_v13_policy_group_numbers(text, value):
    assert value in _v13_ids(text, T.ACCOUNT)


@pytest.mark.parametrize(
    "text",
    [
        "group 3 meets at 4 pm",
        "the claim was denied on 11-15-2026",
        "claim filed 2026-11-03",
        "participant 12-3 of 40",
        "the employee 2024 2025 review",
        "policy renewal 2026-11",
        "grupo 4 y 5",
    ],
)
def test_v13_short_id_lookalikes(text):
    assert not _v13_ids(text, T.ID, T.ACCOUNT)


@pytest.mark.parametrize(
    "text,value",
    [
        ("Ubezpieczenie: Plan A, ID członka XJK884201, polisa", "XJK884201"),
        ("ביטוח: Plan A, מספר חבר XJK884201", "XJK884201"),
        ("member ID QWE55512390", "QWE55512390"),
    ],
)
def test_v13_alphanumeric_health_card(text, value):
    assert value in _v13_ids(text, T.HEALTH_CARD)


def test_v13_alphanumeric_health_card_lookalikes():
    assert not _v13_ids("Ubezpieczenie: Plan A, ID członka 12", T.HEALTH_CARD)
    assert not _v13_ids("the ticket XJK884201 was closed", T.HEALTH_CARD)
    assert not _v13_ids("member since JAN2020", T.HEALTH_CARD)


def test_v13_hebrew_spoken_health_card():
    text = "מספר כרטיס הביטוח תשע תשע אחת שתיים שלוש ארבע. Agent: תודה"
    assert [e for e in RegexDetector().detect(text) if e.type is T.ID and "תשע" in e.text]
    assert not [e for e in RegexDetector().detect("הכרטיס הביטוח ישן") if e.type is T.ID]


def test_v13_zip_after_po_box_and_unit():
    assert "37202" in _v13_ids("Mail to PO Box 7719, Nashville 37202 please", T.ZIP)
    assert "37212" in _v13_ids("Delivery to: 1907 Belmont Road, Apt 4, 37212. Signature", T.ZIP)
    assert "37211" in _v13_ids("1840 Pike Apt 6B, Nashville 37211.", T.ZIP)
    assert not _v13_ids("PO Box 7719 opens at 9", T.ZIP)
    assert not _v13_ids("Apt 4, 30000 IU were ordered", T.ZIP)
    assert not _v13_ids("Unit 5, 12345 mg", T.ZIP)


def test_v13_personal_site_in_other_languages():
    assert "amy-et-bob.example.com" in _v13_ids("Voir mon blogue au amy-et-bob.example.com merci", T.URL)
    assert "casa-de-ana.example.net" in _v13_ids("mi sitio web es casa-de-ana.example.net", T.URL)
    assert "anna-nowak.example.org" in _v13_ids("moja strona to anna-nowak.example.org", T.URL)
    assert not _v13_ids("mon site est wix.com", T.URL)
    assert not _v13_ids("ma page est canada.gc.ca", T.URL)


def test_v13_id_rules_linear():
    import time

    d = RegexDetector()
    cues = (
        "posted by", "reply from", "wrote", "ab_cd1", "plate", "licence plate x", "employee", "claim number", "policy", "group",
        "CPF", "ITIN", "last four", "ostatnie cztery cyfry", "los últimos cuatro", "MRN", "last four digits of your MRN",
        "PO Box 12", "Apt 4", "mon site", "member", "ביטוח", "@abc:", "x\nsam.k:",
    )
    t0 = time.time()
    for cue in cues:
        for fill in (" ", "\n", "A ", ", ", "_"):
            d.detect(cue + fill * 3000)
            d.detect(cue + " " + fill * 3000 + "4417")
    assert time.time() - t0 < 120


def test_v13_social_profile_not_passed_by_clinic_allow():
    from phiproxy import Masker, Policy

    m = Masker(policy=Policy(allow=["instagram.com/clinicname_official", "facebook.com/ClinicNameOfficial"]))
    out = m.mask("Photos on my page, instagram.com/janedoe_mom and facebook.com/jane.doe.77 ok", "s").text
    assert "janedoe_mom" not in out and "jane.doe.77" not in out
    own = m.mask("Follow us at instagram.com/clinicname_official", "s").text
    assert "clinicname_official" in own


def test_v13_known_identifier_last_four():
    from phiproxy import KnownEntities, Masker

    m = Masker()
    k = KnownEntities(identifiers=["SSN 612-55-4417"])
    assert "4417" not in m.mask("los últimos cuatro, 4417", "s", known=k).text
    assert "4417" not in m.mask("4417", "s", known=KnownEntities(identifiers=["MRN 0004417"])).text
    assert "4417" in m.mask("room 4417", "s").text
    # v13 review1: a year-shaped tail is masked unless it is a bare year in a year context with no last-four cue
    assert "2026" in m.mask("see you in 2026", "s", known=KnownEntities(identifiers=["MRN 0002026"])).text
    assert "2026" not in m.mask("see you 2026", "s", known=KnownEntities(identifiers=["MRN 0002026"])).text


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("He drives for Cedar Ridge Freight. Plan: follow up.", T.EMPLOYER, "Cedar Ridge Freight"),
        ("הביטוח דרך העבודה באלון תעשיות. אפשר לעדכן?", T.EMPLOYER, "אלון תעשיות"),
        ("ואני עובדת בבית ספר אורנים, אז החופשה", T.EMPLOYER, "בית ספר אורנים"),
        ("מקום עבודה: ריברגייט ציוד רפואי", T.EMPLOYER, "ריברגייט ציוד רפואי"),
        ("מספר עובד EMP-40817, ברמת הנגב פלסט, זכאית לחופשה", T.EMPLOYER, "רמת הנגב פלסט"),
        ("אני וגרה בהנדרסונוויל. תודה", T.ADDRESS, "הנדרסונוויל"),
    ],
)
def test_v13_employer_address_cues(text, etype, value):
    assert (etype, value) in types_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "he drives for the kids sometimes",
        "she drives for me",
        "עובדת בבית ספר שלי",
        "מקום עבודה: לא ידוע",
        "גרה בבית שלי",
        "גרה בדירה קטנה",
        "גרה בעיר",
    ],
)
def test_v13_employer_address_lookalikes(text):
    assert not {e for e in types_in(text) if e[0] in (T.EMPLOYER, T.ADDRESS)}


@pytest.mark.parametrize(
    "text,value",
    [
        ("Page 1 of 3 / SMITH-JONES, MARY ANN B / MRN 123", "SMITH-JONES, MARY ANN B"),
        ("Page 1 of 3 / DOE, JANE M K / MRN 123", "DOE, JANE M K"),
        ("Page 1 of 3 / GARCIA LOPEZ, MARIA J / MRN 123", "GARCIA LOPEZ, MARIA J"),
        ("Page 2 of 3 / VAN DER BERG, ANNA / MRN 1", "VAN DER BERG, ANNA"),
        ("Page 2 of 3 / DE LA CRUZ, MARIA / MRN 1", "DE LA CRUZ, MARIA"),
        ("Page 2 of 3 / OKAFOR JR, DANIELA / MRN 1", "OKAFOR JR, DANIELA"),
        ("Page 2 of 3 / KIM, MIN JUN / MRN 0012345", "KIM, MIN JUN"),
        ("Page 2 of 3 / CHAN, MEI LING / MRN 0012345", "CHAN, MEI LING"),
        ("Page 2 of 3 / OKAFOR, DANIELA R. M. / MRN 1", "OKAFOR, DANIELA R. M."),
        ("Page 2 of 3 / O'NEIL, SEAN P / MRN 1", "O'NEIL, SEAN P"),
        ("DOE, JANE M.\nDOB: 04/05/1980", "DOE, JANE M."),
        ("DOE, JANE MARIE / DOB 1/2/80", "DOE, JANE MARIE"),
        ("Page 1 sur 3 / DOE, JANE M / NIP 123", "DOE, JANE M"),
        ("Página 1 de 3 / PÉREZ GARCÍA, ANA / DNI 1", "PÉREZ GARCÍA, ANA"),
        ("Strona 1 z 3 / KOWALSKA, ANNA / PESEL 1", "KOWALSKA, ANNA"),
        ("Page 1 of 3\nSMITH-JONES, MARY ANN B\nDOB: 03/04/1985", "SMITH-JONES, MARY ANN B"),
        ("Page 2 of 3\r\nOKAFOR, DANIELA R\r\nMRN 0012345", "OKAFOR, DANIELA R"),
        ("OKAFOR, DANIELA R\nPage 2 of 3", "OKAFOR, DANIELA R"),
        ("Page 2 of 3 / MA, YUE / MRN 0012345", "MA, YUE"),
        ("Page 2 of 3 / DO, THANH / MRN 0012345", "DO, THANH"),
        ("Page 2 of 3 / PA, TOUA / MRN 1", "PA, TOUA"),
        ("Page 2 of 3 / NGUYỄN, THỊ / MRN 1", "NGUYỄN, THỊ"),
    ],
)
def test_v13_review1_header_full_name(text, value):
    assert value in _v13n(text)


@pytest.mark.parametrize(
    "text",
    [
        "CONSENT FORM, SECTION A / Page 1 of 3",
        "Page 1 of 3\nCONSENT FORM, SECTION A\nDOB 1",
        "Page 2 of 3 / IVF, ICSI / MRN 0012345",
        "Page 2 of 3 / INFORMATION FORM, PART B / MRN 1",
        "Formulaire de consentement, Section B / Page 1 sur 3",
        "Findings: TUBAL, PATENT bilaterally",
    ],
)
def test_v13_review1_header_lookalikes(text):
    assert not any(n for n in _v13n(text) if "," in n and n.upper() == n)


def test_v13_review1_header_needs_a_neighbour():
    assert not any("," in n and n.isupper() for n in _v13n("SMITH, JOHN\nthe clinic called back"))


@pytest.mark.parametrize(
    "text,value",
    [
        ("नाम: डा. राम बहादुर थापा मगर", "राम बहादुर थापा मगर"),
        ("मेरो नाम डा. राम बहादुर थापा हो", "राम बहादुर थापा"),
        ("नाम: श्री राम बहादुर थापा", "राम बहादुर थापा"),
        ("मेरो नाम श्री सीता कुमारी शर्मा हुँ", "सीता कुमारी शर्मा"),
        ("ຊື່ ນາງ ບົວ ສີ ວົງ ສະຫວັນ", "ບົວ ສີ ວົງ ສະຫວັນ"),
        ("ຊື່: ນາງ ບົວ ສີ ວົງ", "ບົວ ສີ ວົງ"),
        ("धन्यवाद,\nसीता कुमारी शर्मा थापा", "सीता कुमारी शर्मा थापा"),
        ("धन्यवाद, सीता", "सीता"),
        ("म सीता हुँ", "सीता"),
        ("धन्यवाद\nआपका\nसरिता गुरुङ", "सरिता गुरुङ"),
        ("धन्यवाद\n\nआपका\n\nसीता शर्मा\n", "सीता शर्मा"),
        ("मेरा नाम अनीता शर्मा मुझे आज डॉक्टर से मिलना है", "अनीता शर्मा"),
        ("मेरा नाम अनीता शर्मा उम्र 30 है", "अनीता शर्मा"),
        ("मेरो नाम प्रकाश राई उमेर ३० हो", "प्रकाश राई"),
        ("ຊື່ ມະນີ ສີສຸວັນ ອາຍຸ ສາມສິບ", "ມະນີ ສີສຸວັນ"),
    ],
)
def test_v13_review1_devanagari_lao_whole_name(text, value):
    assert value in _v13n(text)


@pytest.mark.parametrize(
    "text",
    [
        "मैं बहुत ठीक हूँ",
        "मैं बहुत परेशान हूँ",
        "मैं आज अस्पताल आई हूँ",
        "म आज बहुत थकित हुँ",
        "मैं दिल्ली में हूँ",
        "धन्यवाद\nआपका",
        "धन्यवाद, डॉक्टर",
        "धन्यवाद\nकल आऊँगी",
    ],
)
def test_v13_review1_devanagari_lookalikes(text):
    assert not _v13n(text)


def test_v13_review1_sign_off_never_masks_closing_word():
    for t in ("धन्यवाद\nआपका\nसरिता गुरुङ", "धन्यवाद\nआपकी\nसरिता गुरुङ"):
        assert not any("आपका" in n or "आपकी" in n for n in _v13n(t))


def test_v13_review1_english_letter_names_long_and_trailing_words():
    assert _v13n("Name: gee you zed em ay en you are fine") == ["gee you zed em ay en"]
    run = "gee you zed em ay en " * 5
    got = _v13n("name: " + run)
    assert any(n == run.strip() for n in got)
    assert "gee you zed em ay en you are ay bee cee" in _v13n("name: gee you zed em ay en you are ay bee cee")
    assert not _v13n("you are an ex and why not")


def test_v13_review1_new_rules_linear():
    import re
    import time

    from phiproxy.detectors import _names

    # The rules themselves, not the whole detector: other rules are slow on some of these strings in every version.
    rules = [re.compile(p, f) for p, f, _ in _names.script_rules(frozenset())]
    rules.append(re.compile(_names.SPELLED_LETTER_NAMES_EN, re.IGNORECASE))
    n = 100000
    adversarial = [
        "Page 1 of 3 /" + " " * n,
        "Page 1 of 3\n" + " \t" * (n // 2),
        "SMITH, " + "JOHN " * (n // 5),
        "SMITH " * (n // 6) + ", X",
        "A-" * (n // 2),
        "AB'" * (n // 3),
        "Page 1 of 3 / " + "VAN " * (n // 4) + ", JOHN",
        "Page 1 of 3\n" + "SMITH, JOHN\n" * (n // 12),
        "धन्यवाद" + "\n" * n,
        "धन्यवाद\n" + " \n" * (n // 2),
        "आपका\n\n" * (n // 8) + "x",
        "मेरो नाम " + "राम " * (n // 5),
        "नाम:" + " " * n,
        "ຊື່ " + "ມະ " * (n // 4),
        "name: " + "you " * (n // 4),
        "name: " + "you are " * (n // 8),
        "name: " + "gee you zed em ay en " * (n // 22) + "fine",
    ]
    for text in adversarial:
        t0 = time.time()
        for r in rules:
            for _ in r.finditer(text):
                pass
        assert time.time() - t0 < 5, text[:30]


def _b1(text, kind):
    return [e.text for e in RegexDetector().detect(text) if e.type == kind]


@pytest.mark.parametrize(
    "text,value",
    [
        ("We did a Day 5 transfer in March and I lost the pregnancy in May.", "May"),
        ("Our retrieval is planned for January.", "January"),
        ("Nous attendons un bébé pour juillet!", "juillet"),
        ("Your appointment is for January.", "January"),
    ],
)
def test_v13_review1_month_alone_personal_event(text, value):
    assert value in _b1(text, T.DATE)


@pytest.mark.parametrize(
    "text",
    [
        "We are closed in May for renovations.",
        "The clinic is closed for July.",
        "the pharmacy will open for September",
        "Le bureau est fermé pour juillet.",
        "Revenez avant mars.",
    ],
)
def test_v13_review1_month_alone_clinic_notice_unmasked(text):
    assert _b1(text, T.DATE) == []


@pytest.mark.parametrize(
    "text,value",
    [
        ("born on 09 30 1988", "09 30 1988"),
        ("DOB 9 30 88", "9 30 88"),
        ("DOB 09  30  1988", "09  30  1988"),
        ("DOB 30 09 88", "30 09 88"),
        ("date of birth 9 30 88", "9 30 88"),
        ("born 09 30 1988", "09 30 1988"),
        ("fecha de nacimiento 09 30 1988", "09 30 1988"),
        ("nací el 12  03  90", "12  03  90"),
        ("date de naissance 30 09 1988", "30 09 1988"),
        ("data urodzenia 30 09 1988", "30 09 1988"),
        ("תאריך לידה 30 09 88", "30 09 88"),
        ("נולדתי 30 09 1988", "30 09 1988"),
    ],
)
def test_v13_review1_dob_typed_with_spaces(text, value):
    assert value in _b1(text, T.DATE)


def test_v13_review1_spaced_numbers_without_birth_cue_unmasked():
    assert _b1("Room 09 30 1988 units", T.DATE) == []
    assert _b1("take 1 2 3 daily", T.DATE) == []


@pytest.mark.parametrize(
    "text,value",
    [
        ("تولدم ۱۲ اسفند ۱۳۶۳", "۱۲ اسفند ۱۳۶۳"),
        ("۵ فروردین ۱۳۶۰", "۵ فروردین ۱۳۶۰"),
        ("१२ मार्च १९८५", "१२ मार्च १९८५"),
        ("१२ बैशाख २०४२", "१२ बैशाख २०४२"),
        ("12-ka Janaayo", "12-ka Janaayo"),
        ("12ka Janaayo 1985", "12ka Janaayo 1985"),
        ("kowda Janaayo", "kowda Janaayo"),
    ],
)
def test_v13_review1_persian_devanagari_somali_dates(text, value):
    assert value in _b1(text, T.DATE)


def test_v13_review1_persian_devanagari_words_without_day_unmasked():
    assert _b1("مهر و محبت", T.DATE) == []
    assert _b1("मार्च में", T.DATE) == []


@pytest.mark.parametrize(
    "text,value",
    [
        ("She lived to 93.", "93"),
        ("he lived to 93 and died", "93"),
        ("she lived until 93", "93"),
        ("he lived to be 93", "93"),
        ("vivió hasta los 93", "93"),
        ("dożyła 93 lat", "93 lat"),
        ("vécu jusqu'à 93 ans", "93 ans"),
        ("(ans 91)", "91"),
        ("(años 91)", "91"),
        ("(a. 91)", "91"),
        ("aged 94", "94"),
        ("היא בת 92", "92"),
        ("הוא בן 93", "93"),
    ],
)
def test_v13_review1_ages_over_89_lived_to_brackets_hebrew(text, value):
    assert value in _b1(text, T.AGE)


@pytest.mark.parametrize("text", ["(91)", "She lived to 83.", "היא בת 82", "(ans 61)", "lived to 2024 times"])
def test_v13_review1_ages_lookalikes_unmasked(text):
    assert _b1(text, T.AGE) == []


def test_v13_review1_new_rules_adversarial_timing():
    import time

    n = 100_000
    texts = [
        "DOB" + " " * n, "born" + "\t" * n, "date of birth" + "\n" * n, "born 1 " * (n // 6),
        "in May " * (n // 7), "for" + " " * n + "May", "pour mars " * (n // 10),
        "۱۲" + " " * n + "اسفند", "१२ मार्च " * (n // 10), "12-ka " * (n // 6), "lived to " * (n // 9),
        "(a." + " " * n + "91)",
    ]
    d = RegexDetector()
    for text in texts:
        t0 = time.time()
        d.detect(text)
        assert time.time() - t0 < 30, text[:20]


@pytest.mark.parametrize(
    "text,value",
    [
        ("license plate CA 7ABC123", "CA 7ABC123"),
        ("plate CA 7ABC123", "CA 7ABC123"),
        ("plate ON BXRT 482", "ON BXRT 482"),
        ("plate XYZ 99", "XYZ 99"),
    ],
)
def test_v13_review1_plates(text, value):
    assert value in _v13_ids(text, T.ID)


def test_v13_review1_plates_several_in_one_sentence():
    ids = _v13_ids("license plate CA 7ABC123 and also plate XYZ 99", T.ID)
    assert "CA 7ABC123" in ids and "XYZ 99" in ids
    ids = _v13_ids("plates CA 7ABC123 and ON BXRT 482", T.ID)
    assert "CA 7ABC123" in ids and "ON BXRT 482" in ids


@pytest.mark.parametrize("text", ["I live in CA 7 miles away", "We are on ON 401 east", "Ontario ON M5V 2T6 is the postal code"])
def test_v13_review1_plates_lookalikes(text):
    assert not _v13_ids(text, T.ID)


@pytest.mark.parametrize(
    "text,value",
    [
        ('"fertilityfan88" wrote:', "fertilityfan88"),
        ("“fertilityfan88” wrote:", "fertilityfan88"),
        ('Posted by "fertilityfan88" yesterday', "fertilityfan88"),
        ("Reply from 'sunflower_mom82':", "sunflower_mom82"),
    ],
)
def test_v13_review1_quoted_usernames(text, value):
    assert value in _v13_ids(text, T.ID)


@pytest.mark.parametrize("text", ['"thanks" wrote:', 'Posted by "Dr" yesterday', '"fine" said the nurse'])
def test_v13_review1_quoted_usernames_lookalikes(text):
    assert not _v13_ids(text, T.ID)


@pytest.mark.parametrize(
    "text,value",
    [
        ("employee # 48213", "48213"),
        ("emp no. 48213", "48213"),
        ("matricule 48213", "48213"),
        ("numéro d'employé: 48213", "48213"),
        ("número de empleado: 4821", "4821"),
        ("numer pracownika: 48213", "48213"),
        ("מספר עובד: 48213", "48213"),
        ("participant number 4821", "4821"),
        ("numéro de participant 4821", "4821"),
        ("employee number: 2019", "2019"),
    ],
)
def test_v13_review1_plain_employee_numbers(text, value):
    assert value in _v13_ids(text, T.ID)


@pytest.mark.parametrize("text", ["employee since 2019", "the employee 2024 2025 review", "employee 12 of 40", "participant 7 of 12"])
def test_v13_review1_plain_employee_lookalikes(text):
    assert not _v13_ids(text, T.ID)


@pytest.mark.parametrize(
    "text,value",
    [
        ("4 derniers chiffres du NAS 6789", "6789"),
        ("ostatnie 4 cyfry PESEL 6789", "6789"),
        ("ostatnie 4 cyfry PESEL: 6789", "6789"),
        ("últimos 4 de mi seguro social 6789", "6789"),
        ("los últimos 4 dígitos de mi seguro social son 6789", "6789"),
        ("les quatre derniers 4417", "4417"),
        ("What's the last four of your social?\nSure, it's 4417.", "4417"),
        ("Last four of your SSN?\nIt's 1987", "1987"),
        ("last 4 of SSN: 1987", "1987"),
        ("los últimos cuatro, 1987", "1987"),
    ],
)
def test_v13_review1_partial_last_four_cues(text, value):
    assert value in _v13_ids(text, T.ID, T.SSN, T.MRN)


@pytest.mark.parametrize("text", ["the last four of the social events were fun", "in the last four years of 2026"])
def test_v13_review1_partial_last_four_lookalikes(text):
    assert not _v13_ids(text, T.ID, T.SSN, T.MRN)


@pytest.mark.parametrize(
    "text,value",
    [
        ("CPF 123 456 789 01", "123 456 789 01"),
        ("CPF 123.456.789.01", "123.456.789.01"),
        ("ITIN 912 70 1234", "912 70 1234"),
        ("SSN 123 45 6789", "123 45 6789"),
        ("social security number 123 45 6789", "123 45 6789"),
    ],
)
def test_v13_review1_spaced_national_numbers(text, value):
    assert any(value in v for v in _v13_ids(text, T.ID, T.SSN, T.HEALTH_CARD))


@pytest.mark.parametrize("text", ["SSN 123 45", "I paid 123 45 6789 dollars", "CPF 123 456"])
def test_v13_review1_spaced_national_lookalikes(text):
    assert not any(c.isdigit() for v in _v13_ids(text, T.ID, T.SSN, T.HEALTH_CARD) for c in v)


@pytest.mark.parametrize(
    "text",
    [
        "linktr.ee/janedoe",
        "janedoe.carrd.co",
        "beacons.ai/janedoe",
        "sites.google.com/view/janedoe",
        "janedoe.github.io",
        "janedoe.wixsite.com/mysite",
        "my page is janedoe.wixsite.com/mysite today",
    ],
)
def test_v13_review1_link_in_bio_hosts(text):
    assert _v13_ids(text, T.URL)


@pytest.mark.parametrize("text", ["visit wix.com", "see github.io docs", "support@carrd.co", "sites.google.com is Google's"])
def test_v13_review1_link_in_bio_lookalikes(text):
    assert not _v13_ids(text, T.URL)


def test_v13_review1_shared_host_allow_covers_only_own_path():
    from phiproxy import Masker, Policy

    m = Masker(policy=Policy(allow=["linktr.ee/ourclinic"]))
    assert "janedoe" not in m.mask("find me at linktr.ee/janedoe", "s").text


def test_v13_review1_year_shaped_last_four_masked_with_cue():
    from phiproxy import KnownEntities, Masker

    m = Masker()
    k = KnownEntities(identifiers=["MRN 00481987"])
    assert "1987" not in m.mask("los últimos cuatro, 1987", "s", known=k).text
    assert "1987" not in m.mask("last four digits of your MRN\n\nDuong, 1987", "s", known=k).text
    assert "1987" in m.mask("born in 1987", "s", known=k).text


def test_v13_review1_timing_adversarial():
    import time

    junk = [
        "plate " + "CA " * 20000,
        "plate" + " " * 20000 + "CA 7ABC123",
        'Posted by "' + "ab" * 50000,
        "employee" + " \t" * 50000 + "4821",
        "employee # " + "9 " * 50000,
        "last four of your " + "social " * 15000,
        "ostatnie 4 cyfry" + " " * 1000 + "PESEL 6789",
        "SSN" + " " * 20000 + "123 45 6789",
        "CPF " + "123 " * 25000,
        "linktr.ee/" + "a" * 20000,
        "a." * 5000 + "github.io",
        "plate CA " + "7ABC123 " * 12000,
        "\n".join(["employee #"] * 10000),
    ]
    d = RegexDetector()
    for j in junk:
        t0 = time.time()
        d.detect(j)
        assert time.time() - t0 < 20


def _he_types(text, t):
    return {e.text for e in RegexDetector().detect(text) if e.type is t}


@pytest.mark.parametrize(
    "text",
    [
        "מעסיק: ללא",
        "מעסיק: אין",
        "מקום עבודה: לא עובדת",
        "העבודה בשעות הלילה",
        "העבודה בשעות הלילה פלסט",
        "מורה בבית ספר יסודי",
        "אני עובדת בבית ספר יסודי",
        "אני עובדת בתיכון",
        "אני עובד בבית חולים",
        "אני עובד בבית",
        "אני עובדת בעירייה",
        "אני עובד בלילה",
        "אני עובדת בבוקר",
        "אני עובד בשעות הערב",
        "אני עובד במשמרות",
        "אני עובד בגן ילדים",
        "אני עובדת בחצי משרה",
        "העבודה בבנק",
    ],
)
def test_v13_review1_hebrew_workplace_generic_stays_unmasked(text):
    assert not _he_types(text, T.EMPLOYER)


@pytest.mark.parametrize(
    "text,org",
    [
        ("אני עובד בבית חולים הדסה", "בית חולים הדסה"),
        ("אני עובדת במשרד עורכי דין לוי", "משרד עורכי דין לוי"),
        ("אני עובד בגוגל", "גוגל"),
        ("המעסיק שלי: אלביט", "אלביט"),
        ("מקום העבודה שלי: חברת אלביט", "חברת אלביט"),
        ("מקום העבודה שלי: אלביט", "אלביט"),
        ("אני מועסקת באלביט", "אלביט"),
        ("העבודה בבנק לאומי", "בנק לאומי"),
        ("מספר עובד 4421 במכבי", "מכבי"),
        ("מספר עובד 4421 בבנק לאומי", "בנק לאומי"),
        ("תודה, העבודה בבנק לאומי קשה", "בנק לאומי"),
        ("מורה בבית ספר יסודי אורנים", "בית ספר יסודי אורנים"),
    ],
)
def test_v13_review1_hebrew_workplace_named_masked(text, org):
    assert org in _he_types(text, T.EMPLOYER)


def test_v13_review1_hebrew_residence_variants():
    assert "הרצל 12" in _he_types("הכתובת שלי היא הרצל 12", T.ADDRESS)
    assert "הרצל 12" in _he_types("אני גר בהרצל 12", T.ADDRESS)
    assert "קיבוץ גבעת ברנר" in _he_types("אני גר בקיבוץ גבעת ברנר", T.ADDRESS)
    assert not _he_types("אני גר בבית", T.ADDRESS)


def test_v13_review1_hebrew_workplace_timing():
    import time

    junk = [
        "מקום העבודה שלי" + " " * 100000,
        "מקום העבודה שלי:" + " " * 100000 + "אלביט",
        "אני עובד ב" + "גוגל " * 20000,
        "אני עובד בבית חולים" + " הדסה" * 20000,
        "העבודה בבנק" + " לאומי" * 20000,
        "מספר עובד " + "1" * 100000 + " במכבי",
        "אני גר ב" + "הרצל " * 20000 + "1",
        "אני גר בקיבוץ" + " גבעת" * 20000,
        "מעסיק" + "\t" * 100000 + "\n" * 1000,
        ("עובד ב" + "\t") * 20000,
    ]
    for j in junk:
        t0 = time.perf_counter()
        RegexDetector().detect(j)
        assert time.perf_counter() - t0 < 5


def test_v13_review1_hebrew_employer_place_and_days_unmasked():
    assert not _he_types("הביטוח של המעסיק בטנסי מכסה משהו", T.EMPLOYER)
    assert not _he_types("ואתם עובדים בימי ראשון?", T.EMPLOYER)
    assert "אלביט" in _he_types("מקום העבודה שלי באלביט", T.EMPLOYER)


def test_v13_review1_verify_lookalikes_unmasked():
    from phiproxy import Masker

    for t in ("Page 1 of 3 / ACME, INC / Account 4", "Page 4 of 4\nTERMS, CONDITIONS\nRev 2", "אני עובד בלילות"):
        assert Masker().mask(t, "s").text == t
    assert "REED" not in Masker().mask("Page 1 of 3 / REED, MARCUS / MRN 5", "s").text


def test_v13_final1_tax_id_lists_and_separators():
    from phiproxy import Masker, Policy
    m = Masker(policy=Policy())
    for t, gone in (("SSN 123-45-6789 and 987-65-4321", ["987-65-4321", "123-45-6789"]),
                    ("TIN 912-70-5531 and spouse's 913-71-5532", ["913-71-5532", "912-70-5531"]),
                    ("ITIN: 912.70.5531", ["912.70.5531"]), ("ITIN 912/70/5531", ["912/70/5531"]),
                    ("ITIN is 9127 05531", ["9127 05531"])):
        out = m.mask(t, "s").text
        assert not any(g in out for g in gone), out
    # lookalikes: nine digits only, sentence end, no cue
    assert "9127 055311" in m.mask("ITIN is 9127 055311", "s").text
    assert "[SSN" not in m.mask("Call 555-0100 and 123 45 6789", "s").text
    assert "987-65-4321" in m.mask("Room 987-65-4321 and 912.70.5531", "s").text


def test_v13_final1_passport_and_plate_extras():
    from phiproxy import Masker, Policy
    m = Masker(policy=Policy())
    for t, gone in (("passport: C0482917; his: p7731884k", ["p7731884k", "C0482917"]),
                    ("Passport C0482917. Spouse: G 1234567", ["G 1234567", "1234567"]),
                    ("his plate is 8K4 2217 and hers is 9K4 3318", ["9K4 3318", "8K4 2217"]),
                    ("plate no. 8K4-2217-X", ["-X", "2217"])):
        out = m.mask(t, "s").text
        assert not any(g in out for g in gone), out
    assert "Rex 1234" in m.mask("plate is ABC 123 and the dog is Rex 1234", "s").text
    assert "G 12" in m.mask("Grade G 12 and passport is not needed", "s").text


@pytest.mark.parametrize(
    "text",
    [
        "DOB reminder: please state your DOB at check-in. 12 05 2024 retrieval.",
        "Date of birth form 5 3 2025 submitted",
        "DOB: 3 4 transfer date",
        "Fecha de nacimiento: 3 4 cita",
        "DOB please 09 30 1988",
        "born in the clinic 09 30 1988",
    ],
)
def test_v13_final1_spaced_dob_needs_cue_directly_before(text):
    assert _b1(text, T.DATE) == []


@pytest.mark.parametrize(
    "text,value",
    [
        ("DOB is 09 30 1988", "09 30 1988"),
        ("DOB - 09 30 1988", "09 30 1988"),
        ("Date of birth: 09 30 88", "09 30 88"),
        ("fecha de nacimiento es 09 30 1988", "09 30 1988"),
        ("What is your DOB? 09 30 1988", "09 30 1988"),
        ("Assistant: Please confirm your date of birth.\nVisitor: 09 30 1988\nok", "09 30 1988"),
    ],
)
def test_v13_final1_spaced_dob_direct_forms_still_masked(text, value):
    assert value in _b1(text, T.DATE)


# --- v13 final review 2 -------------------------------------------------------------------------------------------
def _f2_leaks(text, *values):
    out = _b1_masked(text)
    return [v for v in values if v in out]


@pytest.mark.parametrize(
    "text,value",
    [
        ("numer członkowski: 123456", "123456"),
        ("nr członkowski 1234567", "1234567"),
        ("ID członka 123456", "123456"),
        ("מספר חבר: 123456", "123456"),
        ("מס' חבר 1234567", "1234567"),
        ("מספר החבר 9988776", "9988776"),
    ],
)
def test_v13_final2_member_number_pl_he(text, value):
    assert _f2_leaks(text, value) == []


@pytest.mark.parametrize(
    "text",
    ["numer członkowski: 1234", "nr członkowski", "מספר חברים 123456", "ID członka potrzebny", "numer członkowski jest ważny do 2027"],
)
def test_v13_final2_member_number_lookalikes(text):
    assert _b1_masked(text) == text


@pytest.mark.parametrize(
    "text,values",
    [
        ("derniers quatre chiffres de mon NAS: 1234", ["1234"]),
        ("derniers quatre chiffres de mon NAS : 1234 et 5678", ["1234", "5678"]),
        ("the last four digits? 1234 and 5678", ["1234", "5678"]),
        ("the last four digits are 1234, 5678", ["1234", "5678"]),
        ("What are the last four digits? 1234", ["1234"]),
        ("last four of my SSN: 1234 and 5678", ["1234", "5678"]),
        ("últimos cuatro dígitos: 1234 y 5678", ["1234", "5678"]),
    ],
)
def test_v13_final2_last_four_word_order_and_lists(text, values):
    assert _f2_leaks(text, *values) == []


@pytest.mark.parametrize(
    "text",
    [
        "derniers quatre chiffres",
        "les derniers jours de mai",
        "What are the last four digits? We will call you at 10",
        "last four digits of the card, thanks, 12 weeks",
    ],
)
def test_v13_final2_last_four_lookalikes(text):
    assert _b1_masked(text) == text


@pytest.mark.parametrize(
    "text,values",
    [
        ("passeport 12AB34567 et 98ZY76543", ["12AB34567", "98ZY76543"]),
        ("pasaporte PAB123456 y PCD654321", ["PAB123456", "PCD654321"]),
        ("paszport AB1234567 i CD7654321", ["AB1234567", "CD7654321"]),
        ("דרכון 12AB34567 ו 98ZY76543", ["12AB34567", "98ZY76543"]),
        ("Mon passeport est 12AB34567 et celui de mon mari 98ZY76543", ["12AB34567", "98ZY76543"]),
    ],
)
def test_v13_final2_second_passport_non_english(text, values):
    assert _f2_leaks(text, *values) == []


@pytest.mark.parametrize(
    "text",
    ["pasaporte y 12 meses", "I need a passport and 3 forms", "passeport et 2 enfants"],
)
def test_v13_final2_second_passport_lookalikes(text):
    assert _b1_masked(text) == text


def test_v13_final2_second_passport_sentence_break_stops():
    assert "98ZY76543" in _b1_masked("passeport 12AB34567. Et 98ZY76543 est un code")


@pytest.mark.parametrize(
    "text,values",
    [
        ("मेरो नाम सीता कुमारी श्रेष्ठ र मेरो श्रीमान् राम बहादुर थापा", ["राम", "बहादुर", "थापा"]),
        ("मेरो नाम सीता कुमारी श्रेष्ठ अनि मेरी पत्नी गीता थापा", ["गीता", "थापा"]),
        ("र श्रीमती गीता थापा", ["गीता", "थापा"]),
        ("धन्यवाद\n\n सीता\nकुमारी", ["सीता", "कुमारी"]),
        ("धन्यवाद\nसीता\nकुमारी\nश्रेष्ठ", ["सीता", "कुमारी", "श्रेष्ठ"]),
    ],
)
def test_v13_final2_devanagari_second_person_and_split_signoff(text, values):
    assert _f2_leaks(text, *values) == []


@pytest.mark.parametrize(
    "text", ["र मेरो श्रीमान् आज आए", "धन्यवाद\n\nटीम\nआईवीएफ", "और मेरे पति को", "धन्यवाद"]
)
def test_v13_final2_devanagari_lookalikes(text):
    assert _b1_masked(text) == text


@pytest.mark.parametrize(
    "text,kind,value",
    [
        ("Posted by: Jane D.", "[NAME_", "Jane"),
        ("Submitted by: Mara Quill", "[NAME_", "Quill"),
        ("I volunteer for Hope Meadow Foundation", "[EMPLOYER_", "Meadow"),
        ("She volunteers at Hope Meadow Foundation", "[EMPLOYER_", "Meadow"),
    ],
)
def test_v13_final2_byline_and_volunteer(text, kind, value):
    out = _b1_masked(text)
    assert kind in out and value not in out


@pytest.mark.parametrize(
    "text",
    ["Posted by: Staff", "Posted by admin", "I volunteer for the hospital", "volunteers at the clinic", "volunteer for Monday"],
)
def test_v13_final2_byline_and_volunteer_lookalikes(text):
    assert _b1_masked(text) == text


@pytest.mark.parametrize(
    "text,leak",
    [
        ("gee you zed zed ee tee tee ee, that's my name", "zed"),
        ("gee you zed zed ee tee tee ee, is my name", "zed"),
        ("gee you zed zed ee tee tee ee is my last name", "zed"),
        ("Jan, jay ay en ee", "jay"),
        ("my name is Jan, jay ay en ee, doe: dee oh ee", "dee"),
    ],
)
def test_v13_final2_letter_name_spelling_cue_after(text, leak):
    assert leak not in _b1_masked(text)


@pytest.mark.parametrize(
    "text",
    ["you are oh, that's my name", "Is that you, are you ok, that's my name", "Jan, you are ok", "Thanks, you are ee", "jay ay en ee is not a word"],
)
def test_v13_final2_letter_name_lookalikes(text):
    assert _b1_masked(text) == text
