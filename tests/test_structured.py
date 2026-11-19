from phiproxy import EntityType as T
from phiproxy import RegexDetector


def found(text):
    return {(e.type, e.text) for e in RegexDetector().detect(text)}


def test_json_fields():
    text = '{"fields":{"first_name":"Dmitri","last_name":"Volkov","zip":"80206","topic":"semen_analysis"}}'
    got = found(text)
    assert {(T.NAME, "Dmitri"), (T.NAME, "Volkov"), (T.ZIP, "80206")} <= got
    assert not any(e[1] == "semen_analysis" for e in got)


def test_key_value_dump():
    got = found("legal_name: Aiyana Redcrow\npreferred_name: Ana\npronouns: they/them\nvisit_type: consult")
    assert {(T.NAME, "Aiyana Redcrow"), (T.NAME, "Ana")} <= got
    assert not any(e[1] in ("they/them", "consult") for e in got)


def test_csv_columns():
    got = found("last,first,dob,member_id\nTran,Hoa,1990-02-14,VN4412903\nLe,Bao,1988-11-02,VN4412977")
    assert {(T.NAME, "Le"), (T.NAME, "Bao"), (T.NAME, "Tran"), (T.NAME, "Hoa")} <= got
    got = found("id,first,last,tz,phone\n1,נועם,פרידמן,301245678,+972-50-555-0520\n3,,,,")
    assert {(T.NAME, "נועם"), (T.ID, "301245678")} <= got
    got = found("Nom;Date de naissance;Carte santé;Téléphone\nBeaulieu Maude;1989-06-21;AB 112 553 084;403-555-0123")
    assert (T.HEALTH_CARD, "AB 112 553 084") in got


def test_csv_needs_a_header():
    # Prose with commas is not a table, and a list of field words alone has no rows.
    assert not found("Please send name, phone, email and DOB.\nThanks, see you soon, bye")
    assert not found("drug,dose,lot\nMenopur,75 IU,A4471")


def test_hl7_pid_segment():
    text = (
        "MSH|^~\\&|LRM|LARKSPUR|20261117081244||ADT^A04|MSG00918|P|2.5\n"
        "PID|1||LRM-0091177^^^LRM||Penhallow^Marianne^L||19870922|F|||77 Lark Lane^^Arvada^CO^80002||(720)555-0178^PRN^PH\n"
        "PV1|1|O|FERT^^^LRM"
    )
    got = found(text)
    for item in [(T.NAME, "Penhallow"), (T.NAME, "Marianne"), (T.NAME, "L"), (T.ADDRESS, "Arvada"), (T.ZIP, "80002"),
                 (T.PHONE, "(720)555-0178")]:
        assert item in got
    assert "19870922" in {e[1] for e in got}  # the birth date (found as a long number first)
    assert not any(e[1] in ("CO", "F", "FERT", "PRN") for e in got)


def test_values_must_look_like_their_key():
    for text in [
        '{"first":"Menopur","dose":"75 IU"}', "Nom: Clinique Fertilité", "Preferred: morning", "First name: TBD",
        "Phone: press 1", "Tel: 24/7 line", "Policy: 24 hours cancellation", "Chart: Estradiol 245", "DOB: 2 weeks",
        "Patient ID: 5 of 10", "Username: required field", "city: Toronto and then Ottawa", "sin: 3 times a day",
        '{"phone":"ext 4412"}', "zip: 12 boxes",
    ]:
        assert not found(text), text


def test_key_value_keeps_to_the_identifier():
    got = found("Phone: 416-555-0123 (cell) or 416-555-0199 (home), leave a voicemail\n")
    assert {e[1] for e in got} == {"416-555-0123", "416-555-0199"}


def test_crlf_quotes_escapes_and_weak_keys():
    got = found("legal_name: Aiyana Redcrow\r\npreferred_name: Ana\r\n")
    assert {(T.NAME, "Aiyana Redcrow"), (T.NAME, "Ana")} <= got
    got = found('"first_name","last_name","dob"\n"Maria","Lopez, Jr","1990-02-14"')
    assert {(T.NAME, "Maria"), (T.NAME, "Lopez, Jr")} <= got
    assert (T.NAME, "Mar\\u00eda") in found('{"first_name":"Mar\\u00eda","dob":"1990-02-14"}')
    # A bare "name" counts beside a personal field, not alone.
    assert (T.NAME, "Dmitri Volkov") in found('{"name":"Dmitri Volkov","dob":"1990-02-14"}')
    assert not found('{"name":"Menopur 75 IU kit"}')
    assert (T.NAME, "Maria Lopez") in found("Patient Name,Notes\nMaria Lopez,ok")


def test_round2_review():
    # Ragged rows and a blank line do not end the table.
    got = found("first_name,last_name,dob\nMaria,Lopez\nAna,Ruiz,1991-01-01")
    assert {(T.NAME, "Maria"), (T.NAME, "Ruiz")} <= got
    assert (T.NAME, "Ana") in found("first_name,last_name,dob\nMaria,Lopez,1990-02-14\n\nAna,Ruiz,1991-01-01")
    # Weak keys confirm each other or a sure key; long and lower-case names on sure keys.
    assert {(T.NAME, "Lopez"), (T.NAME, "Maria")} <= found("Last: Lopez\nFirst: Maria")
    assert (T.NAME, "Tremblay") in found("Nom: Tremblay\nPrénom: Marie")
    assert (T.NAME, "Maria Lopez Garcia de la Cruz") in found("full_name: Maria Lopez Garcia de la Cruz")
    assert (T.NAME, "maria") in found('{"first_name":"maria","last_name":"lopez"}')
    assert (T.NAME, "John Smith") in found("emergency_contact: John Smith, 416-555-0123")
    assert (T.NAME, "Maria") in found('first_name: "Maria",\nlast_name: "Lopez",')
    # camelCase keys, Python dicts, XML elements.
    assert (T.NAME, "Maria Lopez") in found('{"patientName":"Maria Lopez"}')
    assert (T.NAME, "Lopez") in found("{'first_name': 'Maria', 'last_name': 'Lopez'}")
    assert (T.NAME, "Lopez") in found("<first_name>Maria</first_name><last_name>Lopez</last_name>")
    assert not found("<dose>75</dose><drug>Menopur</drug>")


def test_structured_value_not_cut_short_by_a_street_match():
    from phiproxy import Masker

    assert Masker().mask("Address: 12 King St W, Toronto", "s").text == "Address: [ADDRESS_1]"
    assert Masker().mask("כתובת: הרצל 12 תל אביב", "s").text == "כתובת: [ADDRESS_1]"


def test_round3_review():
    # Tables: a second header, prose rows and chat lines are not data; blank lines and placeholders do not end it.
    assert {e[1] for e in found("first_name,last_name\nMaria,Lopez\n\nphone,email\n416-555-0123,m@x.com")} == {
        "Maria", "Lopez", "416-555-0123", "m@x.com"}
    assert "thanks" not in {e[1] for e in found("first_name,last_name\nMaria,Lopez\nthanks, bye\nfirst_name,last_name\nAna,Ruiz")}
    assert "Tue" not in {e[1] for e in found("first_name,last_name,dob\nMaria,Lopez,1990-02-14\n\nOur hours are Mon, Tue, Wed.")}
    assert (T.NAME, "Ruiz") in found("first_name,last_name\nMaria,Lopez\n\n\nAna,Ruiz")
    assert (T.NAME, "Ana") in found("first_name,last_name,dob\nMaria,Lopez,unknown\nAna,Ruiz,1990-01-01")
    assert (T.NAME, "Maria Lopez") in found("ID,Name\n1,Maria Lopez")
    assert not found("drug,name\nX,Gonal F")
    # Direction marks, French spacing, smart quotes, "Last, First", name fields holding word-like names.
    assert (T.NAME, "שרה") in found("שם פרטי: ‏שרה‏\nשם משפחה: כהן")
    assert (T.NAME, "Tremblay") in found("Nom : Tremblay\r\nPrénom : Marie\r\n")
    assert (T.NAME, "Maria Lopez") in found("full_name: “Maria Lopez”")
    assert (T.NAME, "Lopez, Maria Jose Elena") in found("full_name: Lopez, Maria Jose Elena")
    assert {(T.NAME, "Sunday"), (T.NAME, "Adeyemi")} <= found('{"first_name":"Sunday","last_name":"Adeyemi"}')
    assert (T.NAME, "Nombre y apellidos".split()[0]) not in found("Nombre y apellidos: María López García")
    assert (T.NAME, "María López García") in found("Nombre y apellidos: María López García")
