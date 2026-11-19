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
