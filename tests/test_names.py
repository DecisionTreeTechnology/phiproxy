"""Names found from context by the pattern detector (no model, no patient record)."""

import pytest

from phiproxy import EntityType as T
from phiproxy import RegexDetector


def names(text):
    return {e.text for e in RegexDetector().detect(text) if e.type is T.NAME}


@pytest.mark.parametrize(
    "text,name",
    [
        # Self-introductions, any case.
        ("hey its jess again, can u move my day 3", "jess"),
        ("caller: hi um yeah this is jessica okafor i have a question", "jessica okafor"),
        ("caller: no uh my name is chen wei and my cell is", "chen wei"),
        ("caller: c'est mathieu je suis le conjoint de sandrine", "mathieu"),
        ("caller: hi i'm marcus henry i can't log in", "marcus henry"),
        ("Hi, Anna Kowalski here, I live in Sudbury", "Anna Kowalski"),
        ("Je m'appelle Catherine Dubois-Tremblay, mon courriel", "Catherine Dubois-Tremblay"),
        ("Me llamo Yolanda Pérez, mi correo es", "Yolanda Pérez"),
        ("hola soy Paty, no puedo llegar a las 9", "Paty"),
        ("Nazywam się Małgorzata Wiśniewska, e-mail", "Małgorzata Wiśniewska"),
        ("cześć tu Kasia, spóźnię się 10 min", "Kasia"),
        ("שלום, אני רוצה לקבוע ייעוץ. קוראים לי ענת שפירא, המייל שלי", "ענת שפירא"),
        ("היי זאת שירה, אפשר להזיז את הבדיקה", "שירה"),
        ("My partner's name is spelled Nikhil with a K", "Nikhil"),
        # Relatives and contacts, with or without "my".
        ("Husband Imran supportive.", "Imran"),
        ("Partner: Kevin Nguyen", "Kevin Nguyen"),
        ("surrogate is Tiffany Rhodes, IPs are Mario and Luca Bianchi", "Tiffany Rhodes"),
        ("surrogate is Tiffany Rhodes, IPs are Mario and Luca Bianchi", "Mario and Luca Bianchi"),
        ("Son mari Olivier l'accompagne.", "Olivier"),
        ("Hola, mi esposo Jorge va a llevar la muestra", "Jorge"),
        ("Mój mąż Piotr przyniesie próbkę", "Piotr"),
        ("teść Henryk kontakt awaryjny", "Henryk"),
        ("my wife hope she had her retrieval", "hope"),
        ("c'est Mathieu, le chum de Sandrine. Elle a mal", "Sandrine"),
        ("זה יוסי אברהם, בעלה של מיכל. היא מדממת", "מיכל"),
        # Chart labels and forms.
        ("PATIENT: PARK, Soo-jin", "PARK, Soo-jin"),
        ("Patiente : DUPUIS, Marie-Claude   Naissance : 1989-04-30", "DUPUIS, Marie-Claude"),
        ("Pacjent: Wiśniewski, Aleksander   Data: 2026-11-03", "Wiśniewski, Aleksander"),
        ("Pt Kimberly D. reports", "Kimberly D."),
        ("Re: Samantha J. Reyes, DOB 1/12/1993", "Samantha J. Reyes"),
        ("REFERENCIA: Adriana Mejía, FDN 1987-03-12", "Adriana Mejía"),
        ("מטופלת: כהן, מיכל   תאריך לידה: 30/04/1989", "כהן, מיכל"),
        # Sign-offs and email headers.
        ("Thanks so much,\nJess\n\n--\nJessica Okafor - Senior Analyst", "Jess"),
        ("Thanks so much,\nJess\n\n--\nJessica Okafor - Senior Analyst", "Jessica Okafor"),
        ("hi can we reschedule? ive got a cold. -N. Al-Rashid", "N. Al-Rashid"),
        ("Gracias doctora Lal. Los quiere, Ana y Beto", "Ana y Beto"),
        ("Please advise.\n\nBen Okafor\n(905) 555-0114", "Ben Okafor"),
        ("From: Jessica Okafor <jess.okafor@example.com>", "Jessica Okafor"),
        ("> On Nov 2, 2026, Karen Whitfield wrote:", "Karen Whitfield"),
        # A full name before an identifier or after "for".
        ("Lab requisition: Amelia Frost, DOB 1986-01-05", "Amelia Frost"),
        ("Can you look up my appointment? Teresa Nguyen, born June 3, 1988", "Teresa Nguyen"),
        ("about a prescription for Alina Petrova", "Alina Petrova"),
        ("Phone note: C. Wu states she will pay", "C. Wu"),
        # Courtesy titles keep the title, mask the name.
        ("Mrs. Okafor called", "Okafor"),
        ("Mère porteuse : Mme Whitney Bray.", "Whitney Bray"),
    ],
)
def test_finds_names(text, name):
    assert name in names(text)


@pytest.mark.parametrize(
    "text",
    [
        "my husband picks up the other one",  # verb after a relation
        "my donor sperm order is late",
        "ma femme dort encore après la ponction",
        "Hi, I'd like to book a new consult",
        "Subject: Re: Day 3 bloodwork",
        "Bonjour,\n\nVeuillez trouver ci-joint la référence",
        "progesterone in oil 50 mg IM daily from CD16",
        "Sincerely,\nDr. A. Kaur\nRiverside Family Health",
        "Gracias, Beth Alvarado, RN",
        "Boardroom B. Minutes were circulated",
        "Na, K. Cabergoline 0.5 mg daily",
        "Relationship: spouse\nMember ID: MOH-5520-9981",
        "DONOR MATCH",
        "NOTE TO FILE: patient is 91",
        "my wife is Canadian and I'm Jewish",
        "can I switch from Gonal-f to Puregon?",
        "closed on Monday for Remembrance Day",
        "Thank you,\nPatient Services",
        "תודה ד״ר לוי!! הבטא יצאה 214",
        "PACJENT: Chcę zapłacić kartą.",
        "Agent : Merci. Vos résultats sont dans le portail",
        "Hi, I'm stuck in traffic",
    ],
)
def test_no_name_in(text):
    assert names(text) == set()
