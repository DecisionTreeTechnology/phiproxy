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
    out = m.mask("exp 03/25 and pain 5/10", "s").text
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

    for t in ("Follow the clinic on Twitter: @MFCfertility", "Instagram: @mfc_fertility is our page",
              "follow us on ig: clinic_official", "See our website at example.com",
              "Visit healthcanada.gc.ca for details", "Visit ontario.ca for details"):
        assert Masker().mask(t, "s").text == t, t
    for t in ("my instagram is jane_88", "Follow @jane_doe88 please", "my blog is jane-doe.com",
              "her fundraiser at gofundme.com/amy"):
        out = Masker().mask(t, "s").text
        assert "[ID_1]" in out or "[URL_1]" in out, t
    p = Policy(allow=["info@mfc.ca"])
    assert Masker(policy=p).mask("Visit portal.mfc.ca for the patient portal", "s").text == "Visit portal.mfc.ca for the patient portal"
    assert "[URL_1]" in Masker().mask("Visit portal.mfc.ca for the patient portal", "s").text


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
