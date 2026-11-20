import json

import pytest

from phiproxy import KnownEntities, Masker, PhiproxyError, Policy, UnsupportedContentError
from phiproxy.detectors.regex import RegexDetector

KNOWN = KnownEntities(names=["Sarah Chen"], phones=["416-555-0142"], dates_of_birth=["1990-03-05"])


def test_round_trip_and_consistency():
    m = Masker()
    a = m.mask("Hi, this is Sarah Chen, call 416-555-0142", "s", KNOWN)
    b = m.mask("Sarah Chen again; same number 416 555 0142", "s", KNOWN)
    assert "Sarah" not in a.text and "416" not in a.text
    assert "[NAME_1]" in a.text and "[NAME_1]" in b.text  # same value, same token
    assert "[PHONE_1]" in b.text  # formatting differences normalize to the same token
    assert m.unmask("Thanks [NAME_1], we'll call [PHONE_1].", "s") == "Thanks Sarah Chen, we'll call 416-555-0142."


def test_sessions_are_isolated():
    m = Masker()
    m.mask("call 416-555-0142", "s1")
    assert m.unmask("[PHONE_1]", "s2") == "[PHONE_1]"


def test_tolerant_unmask_and_unknown_tokens():
    m = Masker()
    m.mask("email jane@example.com", "s")
    for variant in ["[EMAIL_1]", "[email_1]", "[ EMAIL 1 ]", "EMAIL_1", "[EMAIL-1]"]:
        assert m.unmask(f"to {variant}.", "s") == "to jane@example.com."
    assert m.unmask("[EMAIL_9] and [NAME_1]", "s") == "[EMAIL_9] and [NAME_1]"


def test_token_is_not_derived_from_value():
    m = Masker()
    t1 = m.mask("call 416-555-0142", "a").text
    t2 = m.mask("call 647-555-0199", "b").text
    assert t1 == t2 == "call [PHONE_1]"


def test_remask_for_logs():
    m = Masker()
    m.mask("this is Sarah Chen", "s", KNOWN)
    assert m.remask("Hello sarah chen!", "s") == "Hello [NAME_1]!"


def test_provider_names_pass_by_default():
    assert Masker().mask("Dr. Patel said so", "s").text == "Dr. Patel said so"
    m = Masker(policy=Policy(disabled_types=set()))
    assert m.mask("Dr. Patel said so", "s").text == "Dr. [PROVIDER_1] said so"


def test_date_shift_round_trip():
    m = Masker(policy=Policy(date_mode="shift"))
    text = "retrieval 2026-11-03, transfer Nov 8th"
    masked = m.mask(text, "s").text
    assert "2026-11-03" not in masked and "[DATE" not in masked
    assert m.unmask(masked, "s") == text


def test_fail_closed_on_detector_error():
    class Boom:
        name = "boom"

        def detect(self, text):
            raise RuntimeError("model crashed")

    with pytest.raises(PhiproxyError):
        Masker(detectors=[RegexDetector(), Boom()]).mask("call 416-555-0142", "s")


def test_openai_messages_payload():
    m = Masker()
    messages = [
        {"role": "system", "content": "You are a clinic assistant."},
        {"role": "user", "content": [{"type": "text", "text": "I'm Sarah Chen, 416-555-0142"}]},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "lookup_patient",
                                         "arguments": json.dumps({"phone": "416-555-0142"})}}],
        },
        {"role": "tool", "tool_call_id": "c1", "content": '{"dob": "1990-03-05", "name": "Sarah Chen"}'},
    ]
    out = m.mask_payload(messages, "s", KNOWN)
    dumped = json.dumps(out)
    assert "Sarah" not in dumped and "416-555" not in dumped and "1990-03-05" not in dumped
    assert out[2]["tool_calls"][0]["function"]["name"] == "lookup_patient"
    assert json.loads(out[2]["tool_calls"][0]["function"]["arguments"]) == {"phone": "[PHONE_1]"}
    assert messages[1]["content"][0]["text"].startswith("I'm Sarah")  # input untouched
    back = m.unmask_payload(out, "s")
    assert json.loads(back[2]["tool_calls"][0]["function"]["arguments"]) == {"phone": "416-555-0142"}


def test_anthropic_blocks_payload():
    m = Masker()
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "My email is sarah@example.com"},
        {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "MRN: 00482913"}]},
        {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": "SSN 123-45-6789"}},
    ]}]
    dumped = json.dumps(m.mask_payload(msgs, "s"))
    assert "sarah@" not in dumped and "00482913" not in dumped and "123-45-6789" not in dumped
    assert '"tool_use_id": "t1"' in dumped


def test_images_blocked_unless_allowed():
    msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}]}]
    with pytest.raises(UnsupportedContentError):
        Masker().mask_payload(msg, "s")
    assert Masker(policy=Policy(allow_images=True)).mask_payload(msg, "s") == msg


def test_stream_unmasker_never_splits_tokens():
    m = Masker()
    m.mask("Hi this is Sarah Chen at 416-555-0142", "s", KNOWN)
    reply = "Thanks [NAME_1]! We will call you at [PHONE_1] tomorrow. " * 3
    expected = m.unmask(reply, "s")
    for size in (1, 2, 3, 5, 7, 13):
        u = m.stream_unmasker("s")
        out = "".join(u.feed(reply[i : i + size]) for i in range(0, len(reply), size)) + u.flush()
        assert out == expected, size


def test_stream_unmasker_shift_mode_dates():
    m = Masker(policy=Policy(date_mode="shift"))
    masked = m.mask("transfer on 2026-11-08 and check 11/20/2026", "s").text
    u = m.stream_unmasker("s")
    out = "".join(u.feed(ch) for ch in masked) + u.flush()
    assert out == "transfer on 2026-11-08 and check 11/20/2026"


def test_allow_list_passes_clinic_details_but_not_the_patient():
    from phiproxy import KnownEntities

    m = Masker(policy=Policy(allow=["Harborview Reproductive Centre", "613-555-0100", "Beth Alvarado"]))
    text = "Call Harborview Reproductive Centre at (613) 555 0100. Thanks, Beth Alvarado. Patient: Maria Lopez, 613-555-0199"
    out = m.mask(text, "s").text
    assert "Harborview Reproductive Centre" in out and "(613) 555 0100" in out
    assert "Maria Lopez" not in out and "613-555-0199" not in out
    # A patient who shares an allowed name is still masked when it comes from the record.
    out = m.mask("Hi, this is Beth Alvarado", "s2", known=KnownEntities(names=["Beth Alvarado"])).text
    assert "Beth Alvarado" not in out


def test_allow_email_domain():
    m = Masker(policy=Policy(allow=["@clinic.example.org"]))
    out = m.mask("write to nurses@clinic.example.org or me at jo@example.com", "s").text
    assert "nurses@clinic.example.org" in out and "jo@example.com" not in out


def test_cross_script_name_unmasks_in_the_text_script():
    from phiproxy import KnownEntities, Masker

    m = Masker()
    t = "אני נועה, ואני מתקשרת לגבי התור"
    r = m.mask(t, session_id="s-he", known=KnownEntities(names=["Noa Ben-Ami"]))
    assert "נועה" not in r.text
    assert m.unmask(r.text, session_id="s-he") == t


def test_cross_script_name_unmasks_latin_text_from_hebrew_record():
    from phiproxy import KnownEntities, Masker

    m = Masker()
    t = "Hi, Noa here, calling about my appointment"
    r = m.mask(t, session_id="s-lat", known=KnownEntities(names=["נועה רוזנברג"]))
    assert "Noa" not in r.text
    assert m.unmask(r.text, session_id="s-lat") == t


def test_allowed_address_with_state_code_and_extension():
    m = Masker(policy=Policy(allow=["4410 East Camelback Road, Suite 300", "Phoenix", "85018", "(602) 555-0700"]))
    text = "Visit 4410 East Camelback Road, Suite 300, Phoenix AZ 85018 or call (602) 555-0700 ext 224."
    assert m.mask(text, "s").text == text
    # A patient's street in the same city is still masked.
    out = m.mask("I live at 12 Elm Street, Phoenix AZ 85018", "s2").text
    assert "12 Elm Street" not in out


def test_allowed_city_alone_does_not_cover_a_state():
    from phiproxy.entities import Entity, EntityType
    from phiproxy.masker import _covered

    text = "I'm in Vancouver WA not BC, the clinic is 1450 West Georgia Street, Vancouver BC"
    allowed = [(7, 16), (42, 66), (68, 77)]  # "Vancouver", "1450 West Georgia Street", "Vancouver"
    city = Entity(EntityType.ADDRESS, 7, 19, text[7:19], "model")
    clinic = Entity(EntityType.ADDRESS, 42, 80, text[42:80], "model")
    assert text[7:16] == "Vancouver" and text[42:66] == "1450 West Georgia Street" and text[68:77] == "Vancouver"
    assert not _covered(city, allowed)
    assert _covered(clinic, allowed)


def test_clinic_name_forms_and_spoken_clinic_number():
    m = Masker(policy=Policy(allow=["Bluebonnet", "Montréal", "(713) 555-0820"]))
    for text in ["Agent: Clinique Bluebonnet, bonjour.", "Équipe Bluebonnet Montréal"]:
        assert m.mask(text, "s").text == text
    out = m.mask("Please call us back at seven one three, five five five, zero eight two zero.", "s2").text
    assert "seven one three" in out
    out = m.mask("My number is seven one three, five five five, zero one two six.", "s3").text
    assert "seven one three" not in out


def test_v10_allowed_address_written_another_way():
    m = Masker(policy=Policy(allow=["1420 Nicollet Ave Suite 310", "812 8th Avenue SW"]))
    for ok in [
        "1420 Nicollet Ave, Suite 310",
        "1420 Nicollet Avenue, Ste 310.",
        "1420 Nicollet Ave #310",
        "812 Eighth Avenue SW, Suite 900",
    ]:
        assert m.mask(f"Visit {ok} today", "s").text == f"Visit {ok} today", ok
    # a patient on the same street, another number or another street word is still masked
    for bad in ["1422 Nicollet Ave, Suite 310", "1420 Nicollet St Suite 310", "1420 Nicollet Ave Apt 5B", "813 Eighth Avenue SW"]:
        assert "[ADDRESS_" in m.mask(f"I live at {bad}", "s").text, bad


def test_v10_patient_city_and_zip_next_to_own_street():
    m = Masker(policy=Policy(allow=["Minneapolis", "55403"]))
    out = m.mask("addr1: 1807 Stevens Ave\ncity: Minneapolis\nzip: 55403", "s").text
    assert "Minneapolis" not in out and "55403" not in out
    assert m.mask("We are in Minneapolis 55403", "s").text == "We are in Minneapolis 55403"


def test_v10_review1_echo_facility_and_holiday_phrases_stay():
    for text, kept in [
        ("My name is Peter Ross. Ross Memorial Hospital referred me.", "Ross Memorial Hospital"),
        ("My name is Ryan Scott. Scott Laboratories did the test.", "Scott Laboratories"),
        ("I'm Mark Davis. Davis Clinic in Ottawa; the Davis Report.", "the Davis Report"),
        ("My name is Julie Martin. Martin Luther King Jr Day closes the clinic.", "Martin Luther King Jr Day"),
    ]:
        out = Masker().mask(text, "s").text
        assert kept in out and "[NAME_1]" in out


def test_v10_review1_echo_ordinary_word_at_sentence_start():
    out = Masker().mask("My name is Grant Lee. Grant access to my chart. Grant me an appointment.", "s").text
    assert "Grant access" in out and "Grant me" in out
    out = Masker().mask("My name is Ken Wood. Wood lamp; Jack up the dose.", "s").text
    assert "Wood lamp" in out
    # a subject verb after it keeps it a name
    out = Masker().mask("My name is Grant Lee. Grant said hi. Grant prefers email.", "s").text
    assert "Grant said" not in out


def test_v10_review1_echo_possessive_and_joined_forms():
    m = Masker()
    out = m.mask("my name is Sarah Cohen. Sarah's chart and Cohen’s chart. Sarah-Jane, Sarah_Cohen", "s").text
    assert "Sarah" not in out.split(".", 1)[1] and "Cohen" not in out.split(".", 1)[1]
    assert "'s chart" in out and "’s chart" in out
    assert m.unmask(out, "s") == "my name is Sarah Cohen. Sarah's chart and Cohen’s chart. Sarah-Jane, Sarah_Cohen"


def test_v10_review1_echo_same_surface_same_token():
    out = Masker().mask("my name is Sarah Cohen. Later Cohen said hi. Cohen again.", "s").text
    assert out.count("[NAME_2]") == 2


def _v10r1_masked(text, **kw):
    from phiproxy import Masker

    return Masker().mask(text, "s", **kw).text


def test_v10_review1_handle_needs_cue_or_shape():
    for t in ["I'll be @home after 3, call me then.", "The @clinic team will reach out.", "Reply to the @nurses channel."]:
        assert _v10r1_masked(t) == t
    assert "@thao_ttc" not in _v10r1_masked("my insta is @thao_ttc")
    assert "@lenaruiz" not in _v10r1_masked("find me on instagram @lenaruiz")
    assert "@MiaKowalski" not in _v10r1_masked("Follow @MiaKowalski")


def test_v10_review1_bare_site_only_when_personal():
    assert _v10r1_masked("Visit mayoclinic.org for general info about IVF.") == "Visit mayoclinic.org for general info about IVF."
    assert "janedoe.example.com" not in _v10r1_masked("my blog is janedoe.example.com")
    assert "jane-doe.org" not in _v10r1_masked("visit jane-doe.org")
    assert "helpjane.org" not in _v10r1_masked("our fundraiser is helpjane.org")


def test_v10_review1_known_lone_name_parts():
    from phiproxy.detectors.known import KnownEntities

    for rec, text in [("Sunil Das", "Das is calling"), ("Van Nguyen", "Van is my daughter"), ("Tran Le", "Hi, it's Le"), ("Wei Du", "Du called")]:
        out = _v10r1_masked(text, known=KnownEntities(names=[rec]))
        assert "[NAME_1]" in out, (rec, out)


def test_v10_review1_mrn_after_order_like_words():
    for t, v in [
        ("po prostu mój MRN 00123456", "00123456"),
        ("I'll quote my MRN: 556677", "556677"),
        ("per the quote my member ID: ABC1234567", "ABC1234567"),
        ("my model of care ID 55667788", "55667788"),
        ("Work order: my MRN 556677", "556677"),
        ("the PO said my account number 12345678", "12345678"),
    ]:
        assert v not in _v10r1_masked(t), t
    assert "445566" in _v10r1_masked("PO 445566 for gloves")


def test_v10_review1_name_filters_do_not_hide_self_introductions():
    for t, n in [
        ("in the chat my name is Anna Wu", "Anna"),
        ("Via chat, I'm Anna Wu", "Anna"),
        ("for my dog, I'm Sarah Lee", "Sarah"),
        ("Hello, this is Maria: I'd like to book", "Maria"),
        ("Hi I'm Anna: need a callback", "Anna"),
        ("Patient: Priya Sharma Medical History: PCOS", "Priya"),
        ("Name: Rahul Patel Services", "Rahul"),
        ("Contact: Ana Ruiz Specialist", "Ana"),
        ("my name is Dakota Reyes", "Dakota"),
        ("My name is Lo Wei", "Lo Wei"),
        ("Me llamo Ya Xiong", "Ya"),
        ("mam na imię andrzej", "andrzej"),
        ("my name is andrzej", "andrzej"),
    ]:
        assert n not in _v10r1_masked(t), t
    assert "Pierogi" in _v10r1_masked("the dog's name is Pierogi")


def test_v10_review1_shift_skips_expiry_and_pain_score():
    from phiproxy import Policy

    m = Masker(policy=Policy(date_mode="shift"))
    out = m.mask("exp 03/25 and pain started 5/10", "s").text
    assert "03/25" not in out and "5/10" not in out
    assert "04/02" not in out
    shifted = m.mask("seen on 03/14/1990", "s").text
    assert shifted != "seen on 03/14/1990" and "[DATE" not in shifted


def test_v10_review2_echo_ordinary_words_stay():
    for text, kept in [
        ("My name is Jack Lemon. Lemon juice. Lemon tea", "Lemon juice. Lemon tea"),
        ("My name is Ben Lake. Lake Ontario. Lake Shore Blvd", "Lake Ontario. Lake Shore Blvd"),
        ("My name is Ann Day. Summer vacation. Day 3 of stimulation", "Day 3 of stimulation"),
        ("My name is Tom Hall. Hall of Fame. City Hall", "City Hall"),
    ]:
        out = Masker(policy=Policy(staff=["Dr. Smith"])).mask(text, "s").text
        assert kept in out
        assert out.startswith("My name is [NAME_1].")


def test_v10_review2_echo_ordinary_word_names_in_person_context():
    out = Masker(policy=Policy(staff=["Dr. Smith"])).mask(
        "My name is Priya Hall. Mr Hall called. Hall is coming. Hall's chart. Priya Hall again", "s"
    ).text
    assert "Hall" not in out and "Priya" not in out
    out = Masker(policy=Policy(staff=["Dr. Smith"])).mask("My name is Halina Kowalczyk. Is Halina able to come?", "s").text
    assert "Halina" not in out


def test_v10_review2_social_handle_clinic_and_staff():
    m = Masker(policy=Policy(staff=["Jen Alvarez"], allow=["Fertiligent Fertility Clinic"]))
    out = m.mask("Follow @fertiligent on Instagram, @fertiligentai too, thanks @dr_jen_alvarez and @jen_alvarez88", "s").text
    assert "@fertiligent on" in out and "@fertiligentai" in out and "@dr_jen_alvarez" in out and "@jen_alvarez88" in out
    # Not the clinic's and not staff: stays masked, and so does everything without a configured list.
    assert "@thaolee_ttc" not in m.mask("dm me @thaolee_ttc", "s2").text
    assert "@fertiligent_mom" not in m.mask("dm me @fertiligent_mom", "s3").text
    assert "@nurse_jen" not in Masker().mask("thanks @nurse_jen", "s4").text
    assert "@nurse_jen" not in m.mask("thanks @nurse_jen", "s5").text  # one name word is not the whole name


def test_v10_review2_allow_address_variants():
    cases = [
        ("123 King Street West, Toronto", ["clinic at 123 King St. W., Toronto", "Clinic is 123 King Street W., Toronto",
                                           "at 123 King St W Toronto", "at 123 King Street West Toronto"]),
        ("123 King St W, Toronto", ["at 123 King Street West, Toronto", "at 123 King St. West, Toronto"]),
        ("123 Main Ave, Suite 4", ["Come to 123 Main Avenue Ste. 4, Toronto.", "Come to 123 Main Avenue\\r\\nSuite 4.",
                                   "Come to 123 Main Avenue\\nSuite 4."]),
    ]
    for allow, texts in cases:
        for t in texts:
            t = t.replace("\\r", "\r").replace("\\n", "\n")
            out = Masker(policy=Policy(staff=["Dr. Smith"], allow=[allow])).mask(t, "s").text
            assert out == t, (allow, t, out)
    # The house number and the street name must still match.
    out = Masker(policy=Policy(staff=["Dr. Smith"], allow=["123 King Street West, Toronto"])).mask(
        "at 124 King St. W., Toronto and 123 Queen St W Toronto", "s"
    ).text
    assert "124 King" not in out and "123 Queen" not in out


def test_v10_review3_card_and_document_expiry_masked_product_expiry_kept():
    from phiproxy import Masker

    for t in ("card 4111-1111-1111-1112 exp 03/28 cvv 123", "my card 4111 1111 1111 1111 exp 05/29",
              "card 4111 1111 1111 1111 exp 5/29 and my DOB 5/29", "passport expires 03/2028",
              "driver licence exp 2028-05", "health card valid thru 06/27", "exp 03/2028"):
        out = Masker().mask(t, "s").text
        assert "[DATE_" in out and not any(x in out for x in ("03/28", "05/29", "5/29", "03/2028", "2028-05", "06/27")), (t, out)
    for t in ("Product expires 03/2027", "Gonal-f pen expires 03/2027", "Use by 03/2027", "Best before 2027-03",
              "Expiry: 03/2027 on the vial", "The Menopur box says exp 04/2028", "lot 5512 exp 08/28"):
        assert "[DATE_" not in Masker().mask(t, "s").text, t


def test_v10_review3_born_in_month_masks_only_the_month():
    from phiproxy import Masker

    assert Masker().mask("Born in May", "s").text == "Born in [DATE_1]"
    assert Masker().mask("She was born in March", "s").text == "She was born in [DATE_1]"
    assert Masker().mask("Les règles arrivent en mai", "s").text == "Les règles arrivent en [DATE_1]"


def test_v10_review3_lowercase_month_with_birth_cue():
    from phiproxy import Masker

    for t, keep in (("my dob is may 3rd 1990", "my dob is "), ("im sarah cohen born march 3 1990", "born "),
                    ("dob: may 3", "dob: "), ("the baby was born june 12th", "born ")):
        out = Masker().mask(t, "s").text
        assert "[DATE_1]" in out and out.count(keep) == 1 and "1990" not in out and "12th" not in out, (t, out)
    for t in ("we may 3 times", "I march 3 miles"):
        assert Masker().mask(t, "s").text == t


def test_v10_review3_clinic_owned_handle_and_site():
    from phiproxy import Masker, Policy

    for t in ("Follow the clinic on Twitter: @XYZfertility", "Instagram: @xyz_fertility is our page",
              "follow us on ig: clinic_official", "See our website at example.com",
              "Visit healthcanada.gc.ca for details", "Visit ontario.ca for details"):
        assert Masker().mask(t, "s").text == t, t
    for t in ("my instagram is jane_88", "Follow @jane_doe88 please", "my blog is jane-doe.com",
              "her fundraiser at gofundme.com/amy"):
        out = Masker().mask(t, "s").text
        assert "[ID_1]" in out or "[URL_1]" in out, t
    p = Policy(allow=["info@xyz.ca"])
    assert Masker(policy=p).mask("Visit portal.xyz.ca for the patient portal", "s").text == "Visit portal.xyz.ca for the patient portal"
    assert "[URL_1]" in Masker().mask("Visit portal.xyz.ca for the patient portal", "s").text


def test_v10_review4_clinic_address_after_patient_street():
    m = Masker(policy=Policy(allow=["123 Kingfisher Row West, Springdale"]))
    out = m.mask("My address is 12 Elm Street. The clinic is at 123 Kingfisher Row West, Springdale.", "s").text
    assert "123 Kingfisher Row West, Springdale" in out and "12 Elm" not in out
    out = m.mask("I'm coming from 55 Oak Ave, Springdale to 123 Kingfisher Row West, Springdale", "s2").text
    assert out.endswith("123 Kingfisher Row West, Springdale") and "55 Oak" not in out


def test_v10_review4_clinic_address_with_extra_unit_masked():
    m = Masker(policy=Policy(allow=["500 Oak Street, Suite 4"]))
    for t, leak in [("Home: 500 Oak Street Suite 4, apt 12", "500 Oak"), ("Home: 500 Oak Street, #4 floor 12", "500 Oak"),
                    ("Please send to 500 Oak Street Suite 4 Apt 3", "500 Oak"), ("500 Oak Street Suite 4\nApt 7 is mine", "500 Oak")]:
        assert leak not in m.mask(t, "s").text, t
    assert m.mask("Come to 500 Oak Street #4", "s").text == "Come to 500 Oak Street #4"
    assert m.mask("Come to 500 Oak Street Suite 4.", "s").text == "Come to 500 Oak Street Suite 4."


def test_v10_review4_handle_needs_whole_staff_name():
    m = Masker(policy=Policy(staff=["Dr. Sarah Lee", "Nurse Jen Alvarez"], allow=["Bluebonnet Fertility Clinic"]))
    for t in ("my instagram is @sarah_k", "find me on instagram @sarah", "my instagram is @alvarez_k"):
        assert "[ID_" in m.mask(t, "s").text, t
    for t in ("follow @sarah_lee", "follow @dr_jen_alvarez", "follow @bluebonnet", "follow @bluebonnetclinic"):
        assert m.mask(t, "s").text == t, t


def test_v10_review4_echo_homonym_surnames():
    m = Masker(policy=Policy(staff=["Dr. Smith"]))
    out = m.mask("My name is Mary Early. Early pregnancy test. Early.", "s").text
    assert "Early pregnancy test" in out and out.endswith("[NAME_2].")
    assert "Pink discharge" in m.mask("My name is Amy Pink. Pink discharge.", "s").text


def test_v10_review4_shift_roundtrip_with_restored_address():
    for t in ("born 3 May 1990 123 King Street West, Toronto", "DOB 1990-05-03 123 King Street West, Toronto"):
        m = Masker(policy=Policy(date_mode="shift"))
        assert m.unmask(m.mask(t, "s").text, "s") == t


def test_v10_review4_known_middle_particle_given_name():
    for t, n in [("Van called", "Nguyen Van Anh"), ("Bin called", "Zhang Bin Li"), ("Do called", "Kim Do Hyun"),
                 ("Le called", "Tran Le Mai"), ("Ter called", "Ana Ter Haar")]:
        assert Masker().mask(t, "s", known=KnownEntities(names=[n])).text == "[NAME_1] called", t
    assert Masker().mask("the de la plaza", "s", known=KnownEntities(names=["Lucia de la Cruz"])).text == "the de la plaza"


def _r5(text, **kw):
    return Masker(policy=Policy(**kw)).mask(text, "s").text


def test_v10_review5_plain_at_needs_real_local_part():
    for t in ["Please look at hotmail.com", "Look at yahoo.ca for more.", "Come at gmail.com", "Tell me at yahoo.com."]:
        assert _r5(t) == t
    assert "[EMAIL_1]" in _r5("email jane at gmail com")
    assert _r5("jane.doe at gmail.com") == "[EMAIL_1]"


def test_v10_review5_plural_family_rejects_group_words():
    for t in ["We are the Hospitals", "we're the Doctors", "from the Mothers group", "This is the Williams Syndrome clinic",
              "the Pre-Ops", "the Mid-Atlantics", "the Co-Ops"]:
        assert _r5(t) == t
    assert "Smiths" not in _r5("we are the Smiths")
    assert "Vang-Lees" not in _r5("the Vang-Lees")


def test_v10_review5_contact_is_skips_payers():
    assert _r5("Billing contact is Sun Life.") == "Billing contact is Sun Life."
    assert _r5("Insurance contact is Blue Cross.") == "Insurance contact is Blue Cross."
    assert "Karen" not in _r5("My manager is Karen Lee.")


def test_v10_review5_bare_site_institutions_and_platforms():
    for t in ["Visit mountsinai.on.ca", "Visit wix.com"]:
        assert _r5(t) == t
    assert "wixsite" not in _r5("Visit jane.wixsite.com/x")


def test_v10_review5_month_alone_in_scheduling_sentence():
    # A patient's appointment month is tied to that person, so it stays masked (privacy over precision).
    for t in ["Mi cita es en mayo.", "Appointment in March", "wizyta w maju"]:
        assert "[DATE_1]" in _r5(t), t
    assert _r5("The baby is due in May.") == "The baby is due in [DATE_1]."


def test_v10_review5_dr_street_still_masked():
    for t in ["I live at 42 Dr. Penfield Ave", "9 Dr. Jones Street", "I live at 2501 Dr. Martin Luther King Jr Dr",
              "I live at 15 Dr. Penfield, Montreal"]:
        assert "[ADDRESS_1]" in _r5(t, staff=["Dr. Smith"])
    assert "[ADDRESS" not in _r5("I have 30 with Dr. Lal")


def test_v10_review5_blocked_first_word_keeps_surname_masked():
    for t, last in [("My name is Se Park", "Park"), ("je m'appelle Se Ri", "Ri"), ("my name is Hindi Patel", "Patel"),
                    ("Hi I'm Cell Rivera", "Rivera"), ("I'm Zoom Lee", "Lee"), ("my name is Zawsze Kowalski", "Kowalski")]:
        out = _r5(t, staff=["Dr. Smith"])
        assert last not in out and "[NAME_1]" in out


def test_v11_staff_initials_stay_patient_initials_masked():
    m = Masker(policy=Policy(staff=["Anjali Deshmukh", "Min-jun Park", "Paris Jean-Baptiste"]))
    out = m.mask("AD: pt KJ 34yo. MJP on call, PJB too. re: QX's FET, M.R. G3P0", "s").text
    assert "AD:" in out and "MJP on call" in out and "PJB too" in out
    assert "KJ" not in out and "QX" not in out and "M.R." not in out
    # Without a staff list the same letters are masked wherever a patient cue gives them a slot.
    plain = Masker().mask("pt MJP 34yo", "s").text
    assert "MJP" not in plain


def test_v11_name_echo_handle_and_polish_forms():
    m = Masker()
    out = m.mask("paid from @ztester-1985\nfile IMG_20261114_ztester.jpg", "s").text
    assert "ztester" not in out
    out = m.mask("Czesc, tu Marek, maz Oli Szymanskiej. Ola jest po punkcji", "s").text
    assert "Ola" not in out
    out = Masker().mask("Pacjent: Roman Gil, ur. 1980.\nProszę poprosić pana Gila o datę", "s").text
    assert "Gila" not in out
    # a lowercase word that merely resembles nothing in the record stays
    assert "pana" in out


def _m(text, **kw):
    from phiproxy import Masker, Policy

    return Masker(policy=Policy(**kw)).mask(text, "s").text


def test_v11_review1_card_last4_not_lot_or_kit_noun():
    for t in [
        "Thanks a lot! Please charge the card ending in 4417",
        "I paid a lot for the cycle, my card ending in 4417",
        "I paid for the medication kit with my visa ending in 4417",
        "It's a lot to take in, but the credit card ending 4417 is the right one",
    ]:
        assert "4417" not in _m(t), t
    # product shapes keep the old behaviour
    assert "0457" in _m("the lot number on the box ends in 0457")
    assert "0457" in _m("lot 5512 ends in 0457")
    assert "0457" in _m("batch is stamped, serial ends in 0457")


def test_v11_review1_lowercase_miss_title_after_to_and():
    for t in [
        "i spoke to miss chen yesterday about the results",
        "please give this to miss garcia",
        "yes and miss rivera too",
        "thanks so much miss patel",
    ]:
        out = _m(t)
        assert not any(n in out for n in ("chen", "garcia", "rivera", "patel")), out
    for t in ["to miss work", "to miss the appointment", "i miss texts", "we'll miss you"]:
        assert _m(t) == t


def test_v11_review1_dona_first_name_echoed():
    assert "Dona" not in _m("Hi, I'm Dona Ramirez. Dona again.")
    assert "Dona" not in _m("Please add my wife, Dona Smith, to the file. Dona's DOB is 1/2/1990")


def test_v11_review1_closure_word_with_personal_date():
    assert "Nov 4" not in _m("Clinic closed Friday so I rescheduled the HSG, now Nov 4")
    assert "November 4" not in _m("Since the clinic closed early, I'm booking the IUI for November 4 instead")
    assert "Nov 4" not in _m("It was closed, Tuesday Nov 4 is when I had the HSG")
    assert "February 3" not in _m("Office closed for lunch - Sarah Kim, February 3 1990")
    assert "Nov 4" not in _m("Closed on Nov 4 for my appointment")
    # notices stay readable


def test_v11_review1_upkeep_not_embryo_dates():
    assert "11/12" not in _m("The lab said my embryos were replaced 11/12")
    assert "11/12" not in _m("Lab: embryo replaced 11/12, beta 11/24")
    assert "11/12" not in _m("The lab validated 11/12 as the day of the retrieval")
    assert _m("The freezer was serviced 11/12") == "The freezer was serviced 11/12"
    assert _m("Lab incubator replaced 11/12") == "Lab incubator replaced 11/12"


def test_v11_review1_patient_cue_initials_not_staff():
    import re

    from phiproxy import Masker, Policy
    from phiproxy.detectors.regex import RegexDetector
    from phiproxy.entities import Entity, EntityType

    class Stub:
        def detect(self, text):
            return [Entity(EntityType.NAME, m.start(), m.end(), m.group(), 0.9, "gliner") for m in re.finditer(r"\b(?:DM|MA|PA)\b", text)]

    def run(t):
        return Masker(detectors=[RegexDetector(), Stub()], policy=Policy(staff=["Maria Jensen"])).mask(t, "s").text

    assert "DM" not in run("Patient DM called, DOB 03/14/1988")
    assert "MA," not in run("Hi this is MA, I need to move my transfer")
    assert "PA" not in run("Please call pt PA at 416-555-0192")
    assert "MJ" not in _m("pt MJ, 34yo, G2P0, here for FET", staff=["Maria Jensen"])
    for t in ["MJ: called pt", "-MJ", "per MJ", "pt called, MJ RN"]:
        assert _m(t, staff=["Maria Jensen"]) == t


@pytest.mark.parametrize(
    "text",
    ["call the clinic at 613-555-0100 or plus 1 613 555 0100", "Clinic line plus 1 613 555 0100", "más 1 613 555 0100 ok", "+1 613 555 0100 ok"],
)
def test_v11_review1_allowed_clinic_phone_with_plus_word(text):
    out = Masker(policy=Policy(allow=["613-555-0100"])).mask(text, "s").text
    assert out == text


@pytest.mark.parametrize("text", ["plus 1 613 555 0199", "más 1 416 555 0100", "my number is plus 1 416 555 0100"])
def test_v11_review1_patient_phone_with_plus_word_masked(text):
    out = Masker(policy=Policy(allow=["613-555-0100"])).mask(text, "s").text
    assert "[PHONE_" in out and "555" not in out


def test_v11_review1_spanish_y_stays_outside_spelled_name():
    out = Masker().mask("mi apellido es p, e, eñe, a, y mi nombre es Ana", "s").text
    assert " y mi nombre" in out and "p, e" not in out and "Ana" not in out


def test_v11_review1_polish_surname_case_forms_echoed():
    m = Masker()
    out = m.mask("Moje nazwisko Kowalski. Zadzwoń do pana Kowalskiego. Z panem Kowalskim, panią Kowalską, Kowalskiemu", "pl1").text
    for form in ("Kowalskiego", "Kowalskim", "Kowalską", "Kowalskiemu"):
        assert form not in out
    out = m.mask("Moje nazwisko Kowalska. Pani Kowalskiej wynik", "pl2").text
    assert "Kowalskiej" not in out


def test_v11_review1_polish_case_forms_lookalikes_stay():
    m = Masker()
    # no base surname was found: a lone form after "pana" is not guessed, and unrelated words stay
    assert "Kowalskie" in m.mask("Moje nazwisko Kowalski. Kowalskie jest daleko.", "pl3").text
    assert "Kowalewo" in m.mask("Moje nazwisko Kowalski. Kowalewo jest daleko.", "pl4").text


def test_v11_review1_personal_handle_repeat_masked():
    m = Masker()
    r = m.mask("pay me at @kellison88. kellison88 said. Kellison hi", "h1").text
    assert "kellison88" not in r.lower().replace("@kellison88", "")
    assert r.count("[ID_") == 2  # the bare repeat has its own placeholder (round-trips exactly)
    r = m.mask("my username is luna_cycle_88 and Luna is me. luna_cycle_88 again", "h2").text
    assert "luna" not in r.lower()


def test_v11_review1_handle_repeat_lookalikes_stay():
    m = Masker()
    r = m.mask("pay me at @kellison88. kellison88x is a different word and kellison8 too", "h3").text
    assert "kellison88x" in r and "kellison8 " in r
    # a word that merely starts like the handle's first token is not masked when it is lower case and ordinary
    r = m.mask("my username is luna_cycle_88. the lunar cycle is 28 days", "h4").text
    assert "lunar cycle" in r


_STREET_ALLOW = ["100 Main Street, Suite 200, Toronto, ON M5V 1A1"]


@pytest.mark.parametrize(
    "text",
    [
        "I live at 100 Main Street, Ottawa",
        "I live at 100 Main St, Mississauga",
        "my address is 100 Main Street",
        "mi dirección es 100 Main Street",
        "j'habite au 100 Main Street",
    ],
)
def test_v11_review2_street_head_is_masked_for_patient_address(text):
    out = Masker(policy=Policy(allow=_STREET_ALLOW)).mask(text, "s").text
    assert "100 Main" not in out and "[ADDRESS_1]" in out


def test_v11_review2_street_head_other_state_masked():
    m = Masker(policy=Policy(allow=["1180 Peachtree Park Drive, Atlanta, GA 30309"]))
    out = m.mask("I live at 1180 Peachtree Park Drive, Smyrna, GA 30080", "s").text
    assert "1180" not in out and "Peachtree" not in out


def test_v11_review2_handle_echo_round_trip():
    for text in [
        "pay me at @kellison88. kellison88 said. Kellison hi",
        "send to @kellison88 then kellison88 again",
        "my handle luna_cycle_88, luna_cycle_88 again and @luna_cycle_88",
        "Oli Szymanskiej was seen. Ola came with pana Gila. Roman Gil and pana Gila",
    ]:
        m = Masker()
        r = m.mask(text, "s")
        assert m.unmask(r.text, "s") == text
    r = Masker().mask("send to @kellison88 then kellison88 again", "s")
    assert "kellison88" not in r.text


@pytest.mark.parametrize(
    "text,hidden",
    [
        ("Mrs. Hard called", "Hard"),
        ("My last name is Hard", "Hard"),
        ("this is Mr Ready", "Ready"),
        ("Mme Fait", "Fait"),
        ("Sra. Hecho", "Hecho"),
        ("Mi apellido es Hecho", "Hecho"),
        ("Nazwisko Czyli", "Czyli"),
        ("Ms. Easy", "Easy"),
        ("Mr. Possible", "Possible"),
    ],
)
def test_v11_review2_late_stop_words_masked_after_title_or_cue(text, hidden):
    out = Masker(policy=Policy(allow=["Cedar Clinic"], staff=["Jon Smith"])).mask(text, "s").text
    assert hidden not in out and "[NAME_1]" in out


@pytest.mark.parametrize("text", ["it is hard to say", "I am ready", "that was easy for me", "Is that possible?"])
def test_v11_review2_late_stop_words_lookalikes_stay(text):
    assert Masker().mask(text, "s").text == text


@pytest.mark.parametrize(
    "text,out",
    [
        ("số điện thoại 604 555 0182 năm nay em 30 tuổi", "số điện thoại [PHONE_1] năm nay em 30 tuổi"),
        ("ref 55512345 hai and x", "ref [ID_1] hai and x"),
        ("phone 604 555 0182 hai", "phone [PHONE_1] hai"),
        ("số điện thoại của tôi là không một hai ba bốn năm sáu bảy tám chín", "số điện thoại của tôi là [PHONE_1]"),
        ("năm nay em 30 tuổi", "năm nay em 30 tuổi"),
    ],
)
def test_v11_review2_vietnamese_digit_words_do_not_extend_digit_runs(text, out):
    assert Masker().mask(text, "s").text == out


@pytest.mark.parametrize(
    "text,out",
    [
        ("Phone number mismatch? Room 204\nRoom 305\nExt 4521", "Phone number mismatch? Room 204\nRoom 305\nExt 4521"),
        ("Agent: lot number?\nPatient: 300\nPatient: 400\nPatient: 5000", None),
        ("my phone number\n604\n555\n0182", "my phone number\n[PHONE_1]"),
        ("the area code is 604\nthen 555\n0182", "the area code is [PHONE_1]\nthen [PHONE_2]\n[PHONE_3]"),
    ],
)
def test_v11_review2_phone_pieces_after_non_phone_labels(text, out):
    got = Masker().mask(text, "s").text
    assert got == (out if out is not None else text)


@pytest.mark.parametrize(
    "text,allow,out",
    [
        ("Patient EF at 12 weeks", [], "Patient EF at 12 weeks"),
        ("Patient LV function, patient TSH", [], "Patient LV function, patient TSH"),
        ("patient HRC referral", ["HRC"], "patient HRC referral"),
        ("patient HRC referral", [], "patient [NAME_1] referral"),
        ("Patient KJ, 34 y/o, called", [], "Patient [NAME_1], 34 y/o, called"),
    ],
)
def test_v11_review2_initials_after_patient_cue(text, allow, out):
    assert Masker(policy=Policy(allow=allow)).mask(text, "s").text == out


@pytest.mark.parametrize(
    "text,out",
    [
        ("Visit Cobb County office", "Visit Cobb County office"),
        ("Take Mission Road Reserve exit", "Take Mission Road Reserve exit"),
        ("Colonia Roma Norte clinic has an office", "Colonia Roma Norte clinic has an office"),
        ("Unit 5, Fort Street clinic", "Unit 5, Fort Street clinic"),
        ("I live in Cobb County", "I live in [ADDRESS_1]"),
        ("We live in Cobb County near the office", "We live in [ADDRESS_1] near the office"),
        ("We drive from Cobb County to you", "We drive from [ADDRESS_1] to you"),
    ],
)
def test_v11_review2_public_place_cues_not_addresses(text, out):
    assert Masker().mask(text, "s").text == out


@pytest.mark.parametrize(
    "text,out",
    [
        ("my venmo is jane-doe-12", "my venmo is [ID_1]"),
        ("my paypal is janedoe", "my paypal is [ID_1]"),
        ("venmo: jane-doe-12", "venmo: [ID_1]"),
        ("my paypal is down", "my paypal is down"),
        ("paypal is working", "paypal is working"),
    ],
)
def test_v11_review2_bare_payment_handles(text, out):
    assert Masker().mask(text, "s").text == out


def test_v11_review2_possessive_abbreviation_is_a_person():
    import re

    from phiproxy.entities import Entity, EntityType

    class Stub:
        def detect(self, text):
            return [Entity(EntityType.NAME, m.start(), m.end(), m.group(), 0.9, "gliner") for m in re.finditer(r"\bTB\b", text)]

    def run(t):
        return Masker(detectors=[RegexDetector(), Stub()], policy=Policy(staff=["Maria Jensen"])).mask(t, "s").text

    assert "TB" not in run("Also re: TB's IUI, trigger 2130h")


def test_v11_review2_closed_needs_clinic_subject():
    assert "Dec 5" not in Masker().mask("Case closed Dec 5 2019", "s").text
    assert "March 3" not in Masker().mask("Account closed March 3 2024", "s").text


def test_v11_review2_late_stop_surname_echoed():
    assert Masker().mask("Mrs. Hard called. Hard again", "s").text == "Mrs. [NAME_1] called. [NAME_1] again"
    assert Masker().mask("it is hard to say", "s").text == "it is hard to say"


def _stub_initials_masker(staff):
    import re as _re

    from phiproxy.detectors.regex import RegexDetector
    from phiproxy.entities import Entity, EntityType

    class Stub:
        def detect(self, text):
            return [Entity(EntityType.NAME, m.start(), m.end(), m.group(), 0.9, "gliner") for m in _re.finditer(r"\b[A-Z]{2,3}\b", text)]

    return Masker(detectors=[RegexDetector(), Stub()], policy=Policy(staff=staff))


@pytest.mark.parametrize(
    "text",
    [
        "Patient name: MJ", "Nombre: MJ", "Apellido: MJ", "Imię i nazwisko: MJ", "Nazwisko: MJ", "Last name: MJ",
        "Surname: MJ", "Full name: MJ", "Emergency contact: MJ", "Cardholder name: MJ", "Patient name: AD",
        "for MJ", "re: MJ, 34yo", "MJ is pregnant", "MJ, 34yo", "Please call MJ about the results",
    ],
)
def test_v11_review3_staff_initials_masked_outside_signatures(text):
    staff = ["Maria Jones", "Dr. Alan Smith", "Anna Dawson"]
    out = _stub_initials_masker(staff).mask(text, "s").text
    assert "MJ" not in out and "AD" not in out


def test_v11_review3_spoken_answer_after_long_chatter():
    from phiproxy.detectors.regex import RegexDetector

    filler = "Sorry, my kids are being loud, and the nurse said last week the results would be back soon, " * 5
    t = f"Agent: What is your chart number? {filler} Ok here it is: four five six seven"
    assert [(e.type.name, e.text) for e in RegexDetector().detect(t)] == [("ID", "four five six seven")]
    t = f"Agent: What's the best phone number to reach you? {filler} Ok here it is: six one three five five five"
    assert [(e.type.name, e.text) for e in RegexDetector().detect(t)] == [("PHONE", "six one three five five five")]
    # no question: nothing to type the digits with
    assert RegexDetector().detect(f"Ok {filler} here it is: four five six seven") == []


@pytest.mark.parametrize(
    "text,masked",
    [
        ("Wound closure Nov 14", True),
        ("Incision closure Nov 14, staples out Nov 28", True),
        ("Cervical closure Dec 5", True),
        ("Our adoption closure Nov 14", True),
        ("Clinic closed Nov 14 (Emma's birth)", True),
        ("Clinic closure Nov 14", True),
        ("Office closure Dec 24", True),
        ("Closure: Nov 11", True),
        ("Holiday closure Dec 24", True),
        ("Policy for Sarah effective Jan 1", True),
        ("Insurance policy effective Jan 1 2027", True),
        ("Policy effective Nov 14 2026 for Sarah Mitchell, DOB Nov 14 1990", True),
        ("Schedule effective Dec 5", True),
        ("Updates effective Nov 14 — IVF cycle begins", True),
        ("Fee schedule effective Jan 1", True),
        ("Updated prices effective March 1, 2027", True),
        ("Version 7, effective January 1", True),
    ],
)
def test_v11_review3_closure_and_effective_dates(text, masked):
    out = Masker().mask(text, "s").text
    assert ("[DATE_" in out) is masked


_R3_STREET_ALLOW = ["1180 Peachtree Park Drive NE, Suite 400, Atlanta, GA 30309"]


@pytest.mark.parametrize(
    "text",
    [
        "Pt lives on Peachtree Park Drive NE #1204",
        "Peachtree Park Drive NE #1204, Atlanta",
        "It's Peachtree Park Drive NE apt 1204, near the clinic",
        "Lives on Peachtree Park Drive NE",
        "She lives on Peachtree Park Drive NE",
        "Home: Peachtree Park Drive NE",
        "Pt's address: Peachtree Park Drive NE apt 12",
        "Patient address: Peachtree Park Drive NE",
        "ship to Peachtree Park Drive NE apt 12 Atlanta GA 30309",
    ],
)
def test_v11_review3_bare_clinic_street_of_a_patient_masked(text):
    out = Masker(policy=Policy(allow=_R3_STREET_ALLOW)).mask(text, "s").text
    assert "Peachtree" not in out


def test_v11_review3_clinic_street_before_other_town_masked():
    p = Policy(allow=["100 Park Drive, Suite 210, Halifax, NS B3J 1H2"])
    assert "100 Park Drive" not in Masker(policy=p).mask("I live at 100 Park Drive Springfield", "s").text
    assert "Park Drive" not in Masker(policy=p).mask("at 100 Park Drive, Toronto", "s").text


@pytest.mark.parametrize(
    "text",
    ["Dona Garcia. garcia", "señora Garcia\ngarcia", "madame tremblay. Madame Tremblay", "Dona Garcia. Garcia",
     "email estradiol88@gmail.com Estradiol 350 pg/mL, estradiol", "Venmo @eggs-2026. Eggs retrieved: 12, eggs",
     "Venmo @jtran-1985, jtran, Jtran", "Jtran, hello. Venmo @jtran-1985. My handle jtran-1985 again",
     "Venmo @jtran-1985, jtran-1985", "email kellison88@example.com then Kellison wrote, kellison88@example.com"],
)
def test_v11_review3_echo_round_trips(text):
    m = Masker()
    r = m.mask(text, "s")
    back = m.unmask(r.text, "s")
    assert (back if isinstance(back, str) else back.text) == text


def test_v11_review3_handle_echo_details():
    out = Masker().mask("Venmo @jtran-1985, jtran-1985", "s").text
    assert "1985" not in out and out.count("[ID_") == 2
    out = Masker().mask("email estradiol88@gmail.com Estradiol 350 pg/mL, estradiol", "s").text
    assert out == "email [EMAIL_1] Estradiol 350 pg/mL, estradiol"
    out = Masker().mask("Venmo @eggs-2026. Eggs retrieved: 12, eggs", "s").text
    assert "Eggs retrieved: 12, eggs" in out
    # a name-built handle still echoes its stem
    assert "jtran" not in Masker().mask("Venmo @jtran-1985 and jtran", "s").text


def test_v11_review3_clinic_street_with_name_prefix_patient_address_masked():
    m = Masker(policy=Policy(allow=["Toronto Fertility, 123 Main Street, Suite 400, Toronto ON M5V 1A1"]))
    for text in ["I live at 123 Main Street", "my address is 123 Main Street, Ottawa", "I live at 123 Main Street, Toronto"]:
        out = m.mask(text, "s").text
        assert "123 Main" not in out, text


def test_v11_review3_lists_of_values_pass():
    for text in ["Scores 7/10, 8/10", "BMI 24.5, 26.1"]:
        assert Masker().mask(text, "s").text == text
    assert "[DATE_" in Masker().mask("Embryos 4/6", "s").text  # kept as before
    assert "[DATE_" in Masker().mask("visit 24.5, 26.1", "s").text


def test_v11_review3_new_spans_round_trip():
    for text in [
        "my email is kelli dash smith at gmail dot com",
        "email k, e, l, l, i, 8, 8 at gmail dot com",
        "I live in Ste. Anne Reserve No. 4",
        "Where do you live?\nSudbury",
        "Unit 2050 Box 4190, APO AP 96278",
        "90210 Beverly Hills CA and my phone",
    ]:
        m = Masker()
        r = m.mask(text, "s")
        assert r.text != text
        assert m.unmask(r.text, "s") == text


@pytest.mark.parametrize(
    "text",
    [
        "Sa mère habite au 1180 Peachtree Park Drive NE",
        "Ella vive en 1180 Peachtree Park Drive NE",
        "Ona mieszka przy 1180 Peachtree Park Drive NE",
        "Mailing address: 1180 Peachtree Park Drive NE",
        "Billing: 1180 Peachtree Park Drive NE, Atlanta",
    ],
)
def test_v11_review3_other_language_residence_cue_masks_clinic_street(text):
    out = Masker(policy=Policy(allow=["1180 Peachtree Park Drive NE, Suite 400, Atlanta, GA 30309"])).mask(text, "s").text
    assert "Peachtree" not in out


def test_v11_review3_full_name_label_initials_not_staff():
    m = Masker(policy=Policy(staff=["Maria Jones"]))
    assert "MJ" not in m.mask("Nombre completo: MJ", "s").text
    assert m.mask("MJ: called pt", "s").text == "MJ: called pt"


def test_v11_review3_clinical_handle_head_not_echoed():
    assert Masker().mask("login: embryo_2026 embryo", "s").text == "login: [ID_1] embryo"


_R4_ALLOW = ["1180 Peachtree Park Drive NE, Suite 400, Atlanta, GA 30309"]


@pytest.mark.parametrize(
    "text",
    [
        "Je demeure au 1182, Peachtree Park Drive NE",
        "Estoy en Peachtree Park Drive NE número 1182",
        "My street is Peachtree Park Drive NE, house number 1182",
        "Street: Peachtree Park Drive NE\nHouse no: 1182\nCity: Marietta",
        "Address on file: Peachtree Park Drive NE",
        "Come to 1182 Peachtree Park Drive NE",
    ],
)
def test_v11_review4_patient_street_on_clinic_street_masked(text):
    out = Masker(policy=Policy(staff=["Maria Jones"], allow=_R4_ALLOW)).mask(text, "s").text
    assert "Peachtree" not in out, out


def test_v11_review4_patient_initials_beat_staff_initials():
    m = Masker(policy=Policy(staff=["Maria Jones", "Dr. Kevin Lee"]))
    assert "MJ" not in m.mask("Pt initials MJ", "s").text
    assert "MJ" not in m.mask("patient initials MJ", "s").text
    assert m.mask("MJ: called pt", "s").text == "MJ: called pt"
    assert m.mask("Thanks, MJ", "s").text == "Thanks, MJ"


def test_v11_review4_geo_spans_complete():
    class _M:
        @staticmethod
        def mask(t, sid):
            return Masker().mask(t, sid)

    m = _M()
    assert m.mask("We live past the Circle K on Hwy 20", "s").text == "We live past the [ADDRESS_1]"
    assert m.mask("I live on County Road 12 near Truro", "s").text.startswith("I live on [ADDRESS_1] near")
    assert m.mask("the house past the Circle K Hwy 20", "s").text == "[ADDRESS_1]"
    assert m.mask("the blue house past the Circle K on Highway 20 East", "s").text == "[ADDRESS_1]"
    assert m.mask("Lac La Biche County Alberta", "s").text == "[ADDRESS_1] Alberta"
    assert m.mask("I live in Cobb County Georgia", "s").text == "I live in [ADDRESS_1] Georgia"
    assert m.mask("We moved to Wake County North Carolina last year", "s").text == "We moved to [ADDRESS_1] North Carolina last year"
    assert "גרה" in m.mask("גרה באלפרטה, GA", "s").text
    # lookalikes keep their old behaviour
    assert m.mask("I live on Main Road 5 minutes from here", "s").text.endswith("5 minutes from here")
    assert "Main" not in m.mask("I live on Main Road 5 minutes from here", "s").text


def test_v11_review4_spoken_digits_stop_at_count():
    class _M:
        @staticmethod
        def mask(t, sid):
            return Masker().mask(t, sid)

    m = _M()
    assert m.mask("plus 1 4 1 6 5 5 5 0 1 8 2 and then 3 vials", "s").text in ("plus [PHONE_1] and then 3 vials", "[PHONE_1] and then 3 vials")
    assert m.mask("my phone is 4 1 6 5 5 5 0 1 8 2 and I take 5 mg", "s").text == "my phone is [PHONE_1] and I take 5 mg"
    assert m.mask("plus 1 4 1 6 5 5 5 0 1 8 2\n5 vials", "s").text in ("plus [PHONE_1]\n5 vials", "[PHONE_1]\n5 vials")
    assert m.mask("four one six five five five and then oh one one seven", "s").text == "[PHONE_1]"


def test_v11_review4_county_institutions_and_sin_not_names():
    for t in ["Hennepin County Medical Center", "Fulton County Airport", "patient SIN"]:
        assert Masker().mask(t, "s").text == t
    assert "Cobb" not in Masker().mask("I live in Cobb County", "s").text


# ---- v11 final round (r5 #8-#12). The clinic street with no house number is no longer allowed (it is
# masked as in the frozen code); the earlier tests that kept it visible were narrowed to numbered forms:
# test_v11_review3_bare_clinic_street_still_allowed (4 bare cases dropped), test_v11_review3_clinic_street_with_name_prefix
# ("Come to Main Street, Suite 400" dropped), test_v11_review4_clinic_street_still_allowed (4 bare cases dropped).
_FINAL_ALLOW = ["1180 Peachtree Park Drive NE, Suite 400, Atlanta, GA 30309"]


@pytest.mark.parametrize(
    "text",
    [
        "Peachtree Park Drive NE, Atlanta",
        "Jane Roe\nPeachtree Park Drive NE\nAtlanta",
        "We bought a house on Peachtree Park Drive NE, close to your clinic",
        "Jane Roe, Peachtree Park Drive NE, see you at the office",
        "We're renting on Peachtree Park Drive NE",
        "I'm coming from Peachtree Park Drive NE so I'll need parking",
        "We are on Peachtree Park Drive NE",
    ],
)
def test_v11_final_bare_clinic_street_masked(text):
    out = Masker(policy=Policy(allow=_FINAL_ALLOW)).mask(text, "s").text
    assert "Peachtree" not in out, out
    assert "1184" not in out and " 12" not in out and "1182" not in out, out


def test_v11_final_other_number_on_clinic_street_masked():
    out = Masker(policy=Policy(allow=_FINAL_ALLOW)).mask("I live at 1184 Peachtree Park Drive NE", "s").text
    assert "1184" not in out and "Peachtree" not in out


@pytest.mark.parametrize(
    "text",
    [
        "Call 416-555-0199. Two embryos transferred, Three more frozen.",
        "My number is 416 555 0199. One embryo was transferred.",
        "Phone: (416) 555-0199. Five days after transfer I had spotting",
        "Call 416-555-0199.\nTrois jours",
    ],
)
def test_v11_final_number_word_after_sentence_not_swallowed(text):
    out = Masker().mask(text, "s").text
    assert "embryo" in out or "days" in out or "jours" in out
    for w in ("Two", "One", "Five", "Trois"):
        if w in text:
            assert w in out, out


def test_v11_final_spoken_digit_runs_still_join():
    for t in ["call me at four one six five five five zero one nine nine", "four one six five five five zero one one nine. two embryos"]:
        assert "four one six" not in Masker().mask(t, "s").text
    assert "five five five" not in Masker().mask("four one six. Five five five. One two three four", "s").text


def test_v11_final_plus_phone_round_trip():
    m = Masker(policy=Policy())
    for t in [
        "Call plus 44 7700 900123. Six Nations Reserve, Main Street. plus 44 7700 900123 ok",
        "Call plus 44 7700 900123. Six weeks ago I had a transfer. plus 44 7700 900123 ok",
        "I live on Six Nations Reserve. My phone is plus 44 7700 900123. Six Nations Reserve again. plus 44 7700 900123",
    ]:
        r = m.mask(t, "c")
        assert m.unmask(r.text, "c") == t, r.text


_ROUND_TRIP_MESSAGES = [
    "Hi, this is Jane Roe, my email is jane.roe@example.com and my phone is 416-555-0142.",
    "Please call 416-555-0142 or email jane.roe@example.com. Thanks, jane.roe@example.com",
    "My DOB is 03/14/1988.\r\nMy health card is 1234-567-890-AB.\r\nCall 416-555-0142.",
    "I live at 25 Elm Street, Toronto ON M5V 1A1. Same address: 25 Elm Street, Toronto ON M5V 1A1.",
    "Call 416-555-0199. Two embryos transferred, Three more frozen. Call 416-555-0199.",
    "Phone: (416) 555-0199. Five days after transfer I had spotting. (416) 555-0199",
    "Call plus 44 7700 900123. Six Nations Reserve, Main Street. plus 44 7700 900123 ok",
    "four one six five five five zero one nine nine, again four one six five five five zero one nine nine",
    "Email a@example.org,b@example.org;c@example.org\nd@example.net",
    "Visit www.example.org/portal or www.example.org/portal today.",
    "SSN 123-45-6789 and again 123-45-6789.",
    "Appointment on March 3, 2027 at 9:30. Then March 3, 2027 again.",
    "Dr. Lee said Maria Gomez should call 613-555-0100.\r\n\r\nMaria Gomez agrees. 613-555-0100",
    "Card 4111 1111 1111 1111 expires 12/28; 4111 1111 1111 1111.",
    "I'm Anna Kowalska, mieszkam przy Kwiatowa 5, Warszawa. Anna Kowalska",
    "Mi teléfono es 416-555-0101 y mi correo ana@example.com.",
    "Mon numéro: 514-555-0123. Trois embryons. 514-555-0123",
    "416-555-0142416-555-0142",
    "a@example.com\nb@example.com\r\na@example.com",
    "Zip 90210 and 90210-1234 and 90210.",
    "Order #AB-12345, Order #AB-12345.",
    "My MRN is 77412 (MRN 77412).",
    "From 416-555-0142 to 416-555-0143 to 416-555-0142.",
    "Call me at 416 555 0142, 416 555 0142!",
    "Jane Roe (jane.roe@example.com)/416-555-0142",
    "\n\n416-555-0142\n\n",
    "Her number is plus 1 416 555 0142. plus 1 416 555 0142.",
    "Text 647-555-0177 or call 647-555-0177. One more thing.",
    "My name is Priya Shah. Priya Shah, born 1990-05-04, 1990-05-04.",
    "Send to 25 Elm Street, Apt 4\r\nToronto ON M5V 1A1\r\n25 Elm Street, Apt 4",
]


def test_v11_final_mask_unmask_round_trip_property():
    for i, t in enumerate(_ROUND_TRIP_MESSAGES):
        for policy in (Policy(), Policy(date_mode="mask") if "date_mode" in Policy.__dataclass_fields__ else Policy()):
            m = Masker(policy=policy)
            r = m.mask(t, f"rt{i}")
            assert m.unmask(r.text, f"rt{i}") == t, (t, r.text)


@pytest.mark.parametrize(
    "text",
    [
        "I have MS. I am tired.",
        "She has MS. A neurologist referred her.",
        "Re: LDN. Please advise.",
        "Patient SOB noted at follow-up visit.",
        "Pochodzę z Europy.",
        "Directions to the clinic: the white house past the Esso on Highway 7.",
    ],
)
def test_v11_final2_ordinary_text_not_masked(text):
    assert Masker().mask(text, "s").text == text


@pytest.mark.parametrize(
    "text, gone",
    [
        ("Sra. A llamó", "Sra. A "),
        ("Mrs. O in rm 5", "Mrs. O "),
        ("Pochodzę z Krakowa.", "Krakowa"),
        ("My place is the blue house past the Circle K on Hwy 20.", "Circle K"),
        ("call 601 234 567. Two embryos", "601 234 567"),
        ("Zadzwoń 48 601 234 567. Dwa zarodki", "601 234 567"),
        ("my phone is 52 55 1234 5678. Three days ago", "1234 5678"),
    ],
)
def test_v11_final2_identifiers_still_masked(text, gone):
    assert gone not in Masker().mask(text, "s").text


def test_v11_final2_nanp_number_stops_at_sentence():
    assert Masker().mask("Call 416-555-0199. Two embryos.", "s").text == "Call [PHONE_1]. Two embryos."


@pytest.mark.parametrize(
    "text, gone",
    [
        ("Surname Easy", "Easy"),
        ("Patient Ready, Anna", "Ready"),
        ("My surname is Hard, spelled H, A, R, D", "Hard"),
        ("my phone, area code 416, then 555, then 0182", "0182"),
        ("What is your home address?\nMarkham Road", "Markham"),
    ],
)
def test_v11_final3_identifiers_masked(text, gone):
    assert gone not in Masker().mask(text, "s").text


@pytest.mark.parametrize(
    "text",
    [
        "it is hard to say",
        "Patient UC flare",
        "patient RA on methotrexate",
        "patient OCD",
        "patient LAH",
        "Which address is closest for you?\nMarkham Road",
        "Which address works for pickup?\nQueen Street",
        "Call-back: area code 416, then 555, then 0100 (clinic main line)",
        "Call us: area code\n416\nthen 555\nthen 0100",
    ],
)
def test_v11_final3_ordinary_text_not_masked(text):
    assert Masker().mask(text, "s").text == text


@pytest.mark.parametrize(
    "text, gone",
    [
        ("yes this is she i spoke to miss day yesterday", "miss day"),
        ("and miss chance called back", "chance"),
        ("Vivo en Toronto", "Toronto"),
        ("Mieszkam w Krakowie", "Krakowie"),
        ("Where do you live?\nSudbury", "Sudbury"),
        ("Patient KM, 34yo", "KM"),
    ],
)
def test_v11_final5_identifiers_masked(text, gone):
    assert gone not in Masker().mask(text, "s").text


@pytest.mark.parametrize(
    "text",
    [
        "i will miss work tomorrow",
        "Hola, estoy en Fase 3 y tengo dolor",
        "Soy de Tipo O positivo",
        "Mieszkam w Pobliżu kliniki",
        "Jestem z Mężem na wizycie",
        "Patient ALT 45 and AST 30, both normal",
        "Pt VM full, could not leave message",
        "Re: PET scan results",
        "Dónde vive?\nCentro",
        "Where do you live?\nDowntown",
    ],
)
def test_v11_final5_ordinary_text_not_masked(text):
    assert Masker().mask(text, "s").text == text


def _stub_masker(staff):
    import re

    from phiproxy.entities import Entity, EntityType

    class Stub:
        def detect(self, text):
            return [Entity(EntityType.NAME, m.start(), m.end(), m.group(), 0.9, "gliner") for m in re.finditer(r"\b(?:TB|MJ|TN)\b", text)]

    return Masker(detectors=[RegexDetector(), Stub()], policy=Policy(staff=staff))


@pytest.mark.parametrize(
    "text, gone",
    [
        ("Husband: TB", "TB"),
        ("my husband MJ", "MJ"),
        ("Please call MJ", "MJ"),
        ("Husband MJ NP", "MJ"),
        ("MJ and TN", "MJ"),
    ],
)
def test_v11_final6_patient_initials_not_staff(text, gone):
    assert gone not in _stub_masker(["Maria Jones", "Tina Nguyen"]).mask(text, "s").text


@pytest.mark.parametrize(
    "text, gone",
    [
        ("Are you closed Nov 14? I have a retrieval that day.", "Nov 14"),
        ("We are closed Nov 14. I have my transfer then", "Nov 14"),
        ("We are closed Nov 14 and Nov 15. Sarah's retrieval is Nov 14.", "Nov 14"),
    ],
)
def test_v11_final6_personal_date_after_closure_masked(text, gone):
    assert gone not in Masker().mask(text, "s").text


@pytest.mark.parametrize(
    "text",
    [
        "@pcos_mom1 PCOS is common.",
        "Follow @endo_warrior1 on IG. Endo pain is bad",
        "Señora Doctora Lee la atenderá.",
        "pt GA 8w",
        "pt ANA neg",
        "Cash App $northside accepted.",
    ],
)
def test_v11_final6_ordinary_text_kept(text):
    out = Masker(policy=Policy(staff=["Dr. Sarah Lee"])).mask(text, "s").text
    for w in ("PCOS", "Endo", "Doctora Lee", "GA", "ANA", "$northside", "December 24"):
        if w in text:
            assert w in out, (text, out)
