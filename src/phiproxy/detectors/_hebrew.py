"""Hebrew helpers: one-letter prefixes, common names across scripts, places.

Israeli patients often appear in Latin script in the clinic record ("Noa Ben-Ami")
and in Hebrew in their messages ("נועה"), or the other way round.
"""

from __future__ import annotations

import re

# One-letter prefixes glued to a word: ו (and), ב (in), ל (to), מ (from), ה (the),
# ש (that), כ (as). "ולנועה" has two.
_PREFIX_LETTERS = "ובלמהשכ"


def unprefixed(word: str) -> list[str]:
    """``word`` without one, then two, leading prefix letters ("ומיכל" -> "מיכל", "יכל")."""
    out = []
    for k in (1, 2):
        if len(word) - k >= 2 and all(c in _PREFIX_LETTERS for c in word[:k]):
            out.append(word[k:])
    return out

# Common Israeli names: Latin spellings -> Hebrew. Short names that are also words
# (טל dew, גל wave, אור light) are left out.
_NAMES = """
noa:נועה michal:מיכל yael:יעל shira:שירה tamar:תמר maya,maia:מאיה noam:נועם itai,itay:איתי
eitan,etan,ethan:איתן yoav:יואב avi:אבי dana:דנה rachel,rahel:רחל sarah,sara:שרה rivka:רבקה
leah,lea:לאה ruth,rut:רות hila:הילה inbal:ענבל liat:ליאת keren:קרן orly,orli:אורלי galit:גלית
sigal:סיגל efrat:אפרת hadas:הדס talia,talya:טליה adi:עדי lior:ליאור omer:עומר amit:עמית
daniel:דניאל david:דוד moshe:משה yosef,yossi:יוסף,יוסי ariel:אריאל eyal:אייל ido:עידו nir:ניר
ronit:רונית rina:רינה avital:אביטל naama:נעמה yaara:יערה ayelet:איילת osnat:אסנת merav:מירב
limor:לימור anat:ענת dalia:דליה esther:אסתר miriam:מרים hannah,hana,chana:חנה
yonatan,jonathan:יונתן binyamin,benjamin:בנימין elad:אלעד gil:גיל roni:רוני shai,shay:שי
yehuda:יהודה avraham,abraham:אברהם yitzhak,itzik:יצחק yaakov,yakov:יעקב shlomo:שלמה
reut:רעות shani:שני tali:טלי hagit:חגית orit:אורית irit:עירית nurit:נורית tova:טובה
cohen,kohen:כהן levi,levy:לוי mizrahi:מזרחי peretz,perez:פרץ biton:ביטון dahan:דהן
friedman,fridman:פרידמן katz:כץ rosenberg:רוזנברג avraham:אברהם shapiro,shapira:שפירא
goldberg:גולדברג azulay,azoulay:אזולאי ben-david:בן-דוד ben-ami:בן-עמי
nadav:נדב omri:עמרי uri:אורי ofir:אופיר tomer:תומר guy:גיא ron:רון noga:נוגה sivan:סיון
rotem:רותם ayala:איילה yuval:יובל itamar:איתמר eden:עדן liron:לירון gali:גלי moran:מורן
boaz:בועז inbar:ענבר dafna:דפנה nitzan:ניצן hadar:הדר raz:רז shachar,shahar:שחר oren:אורן
erez:ארז matan:מתן ilan:אילן ehud:אהוד yigal:יגאל tzipi,tsipi:ציפי batya:בתיה ofra:עפרה
"""
LATIN_TO_HEBREW: dict[str, set[str]] = {}
HEBREW_TO_LATIN: dict[str, set[str]] = {}
for _pair in _NAMES.split():
    _lat, _heb = _pair.split(":")
    for _l in _lat.split(","):
        for _h in _heb.split(","):
            LATIN_TO_HEBREW.setdefault(_l, set()).add(_h)
            HEBREW_TO_LATIN.setdefault(_h, set()).add(_l)

# Places written in Hebrew: Israeli cities and the cities patients move between.
# Names that are also ordinary words (רחובות "streets") are left out.
PLACES = """
ירושלים|תל אביב|תל-אביב|תל אביב-יפו|חיפה|ראשון לציון|פתח תקווה|פתח תקוה|פתח-תקווה|אשדוד|נתניה|
באר שבע|באר-שבע|בני ברק|חולון|רמת גן|רמת-גן|אשקלון|בת ים|בית שמש|כפר סבא|הרצליה|חדרה|מודיעין|
נצרת|לוד|רמלה|רעננה|הוד השרון|גבעתיים|קריית גת|קרית גת|נהריה|אילת|עכו|כרמיאל|טבריה|צפת|
קריית שמונה|קרית שמונה|זכרון יעקב|יבנה|ראש העין|קריית אתא|קריית ביאליק|קריית מוצקין|נס ציונה|
עפולה|דימונה|ערד|אריאל|מעלה אדומים|אלעד|ביתר עילית|אום אל-פחם|רמת השרון|קיסריה|יקנעם|
טורונטו|ונקובר|מונטריאול|אוטווה|קלגרי|אדמונטון|ויניפג|ריצ׳מונד|ריצ'מונד|ברנבי|מיסיסוגה|
ניו יורק|לוס אנג׳לס|לוס אנג'לס|שיקגו|בוסטון|מיאמי|סיאטל|פורטלנד|סן פרנסיסקו|
לונדון|פריז|ברלין|ורשה|קרקוב|מוסקבה|קייב|מדריד|ברצלונה|מקסיקו סיטי|בואנוס איירס
"""
PLACE_RE = re.compile(
    r"(?<![א-ת])(?:[ובלמה]-?)?(?P<place>"
    + "|".join(sorted((p.strip() for p in PLACES.replace("\n", "").split("|") if p.strip()), key=len, reverse=True))
    + r")(?![א-ת])"
)
