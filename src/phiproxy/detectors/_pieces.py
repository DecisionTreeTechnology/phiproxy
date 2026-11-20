"""A phone number given in pieces over several turns of a conversation.

"the area code is 404" / "then 555" / "0182" / "sorry, 0128" is a phone number said a
group at a time and then corrected, in any language. A group of three or four digits is
masked only when the text near it talks about a phone number AND the groups that follow
make a North American sequence (area code, exchange, line). A group of three or four
digits anywhere else (a time like 0930, a dose, a room, an extension) is left alone.
"""

from __future__ import annotations

import re

_CUE = re.compile(
    r"phone|\bnumbers?\b|area\s+code|\bcell(?![a-z])(?![ \t]+(?:count|counts|culture|cultures|line|lines|free|division|mass|survival|therapy|analysis|biology|salvage))|mobile|t[ée]l[ée]phone|tel[ée]fono|\bn[uú]mer\w*|\bnum[ée]ro|"
    r"indicatif|c[oó]digo\s+de\s+[aá]rea|telefon|kierunkow|טלפון|נייד|קידומת|전화|번호|điện\s+thoại|\bcall\s*back\b",
    re.IGNORECASE,
)
# A cue that really says "phone": only these let several groups on the cue's own line count
# ("Estradiol numbers: 350, 420, 1100" is a list of values, not a phone number).
_STRONG_CUE = re.compile(
    r"phone|area\s+code|\bcell(?![a-z])(?![ \t]+(?:count|counts|culture|cultures|line|lines|free|division|mass|survival|therapy|analysis|biology|salvage))|mobile|t[ée]l[ée]phone|tel[ée]fono|\btel\b|\bcall\s*(?:me|back)|\breach\s+me|"
    r"\b(?:my|mi|mon|ma|m[oó]j|moja)\s+(?:\w+\s+)?(?:number|n[uú]mero|num[ée]ro|numer)\b|number\s+to\s+(?:reach|call)|"
    r"indicatif|c[oó]digo\s+de\s+[aá]rea|telefon|kierunkow|טלפון|נייד|קידומת|전화|번호|điện\s+thoại",
    re.IGNORECASE,
)
# A group of 3-4 digits standing alone: not part of a longer number, time, date or amount.
_FRAG = re.compile(r"(?<![\w.:/\-+$#])(?<!\d,)(\d{3,4})(?![\w:/%$]|-(?![ \t]*$)|[.,]\d)")
# A number that follows a non-phone label ("Room 204", "Ext 4521", "Suite 300"): not a phone piece.
_NONPHONE_LABEL = re.compile(
    r"(?i)\b(?:room|rm|ext|extension|suite|ste|unit|apt|apartment|bed|bay|lot|order|ref|reference|invoice|box|floor|gate|door|"
    r"page|step|day|dose|cycle|chambre|salle|poste|bureau|appartement|lit|porte|[ée]tage|commande|facture|jour|"
    r"habitaci[óo]n|sala|oficina|cama|piso|puerta|pedido|factura|d[íi]a|dosis|ciclo|pok[óo]j|sala|gabinet|pi[ęe]tro|"
    r"wewn[ęe]trzny|dzie[ńn]|dawka|cykl|zam[óo]wienie|חדר|שלוחה|קומה|מיטה|יום|מנה|מחזור|הזמנה)[ \t.:#\-]*$"
)
# "lot number", "room number": the word "number" there is not about a phone.
_NONPHONE_NUMBER = re.compile(
    r"(?i)\b(?:room|rm|ext|extension|suite|unit|apt|bed|bay|lot|order|ref|reference|invoice|box|floor|gate|door|page|step|"
    r"batch|serial|model|item|case|ticket|claim|policy|account|file|chart)[ \t]+(?:number|numbers|no\.?|#)"
)
_DIGITS = re.compile(r"\d+")
# Dose, unit, time or money right after the group: not a phone fragment.
_UNIT_AFTER = re.compile(r"\s{0,2}(?:a\.?m\b|p\.?m\b|mg|mcg|iu|ml|ng|pg|units?|hours?|hrs?|h\b|dollars?|euros?)", re.IGNORECASE)
_WINDOW = 10  # lines, counting the line that talks about the number
_MAX_WORDS = 12  # a line that carries a piece is short


# Other national shapes, one group per line right under a line that says "phone": Polish mobile 3-3-3, Mexican 2-4-4,
# Polish landline 2-3-2-2. Each group stands alone on its line, so a list of values is not taken for a phone.
_EXTRA_SHAPES = ((3, 3, 3), (2, 4, 4), (2, 3, 2, 2))
_PHONE_WORD = re.compile(
    r"phone|\bcell(?![a-z])(?![ \t]+(?:count|counts|culture|cultures|line|lines|free|division|mass|survival|therapy|analysis|biology|salvage))|mobile|t[ée]l[ée]phone|tel[ée]fono|celular|\btel\b|telefon|kom[óo]rk|טלפון|נייד|điện\s+thoại", re.IGNORECASE
)
_ALONE = re.compile(r"\s*(\d{2,4})\s*[.,;]?\s*$")


# Another numeric topic named on the cue line or on a line before the pieces: the pieces are values, not a phone.
_OTHER_TOPIC = re.compile(
    r"(?i)\b(?:doses?|dosage|counts?|levels?|results?|mg|mcg|iu|ml|units?|follicles?|values?|readings?|measurements?|labs?|"
    r"dosis|niveles?|resultados?|r[ée]sultats?|niveaux|wyniki|dawk\w*|poziom\w*)\b"
)


def _cue_directly_above(cue_line: str) -> bool:
    """The phone word is in the last sentence of the cue line, and no other numeric topic is named there."""
    if _OTHER_TOPIC.search(cue_line):
        return False
    last = re.split(r"[.!?]+[ \t]+", cue_line.strip())[-1]
    return bool(_PHONE_WORD.search(last))


def _extra_shape_spans(lines: list[tuple[int, str]], i: int) -> list[tuple[int, int]]:
    cue_line = lines[i][1]
    if not _PHONE_WORD.search(cue_line) or re.search(r"\d", cue_line) or not _cue_directly_above(cue_line):
        return []
    for shape in _EXTRA_SHAPES:
        spans = []
        for j, want in enumerate(shape):
            k = i + 1 + j
            if k >= len(lines):
                break
            m = _ALONE.fullmatch(lines[k][1])
            if not m or len(m.group(1)) != want or (j == 0 and shape == (3, 3, 3) and m.group(1)[0] == "1"):
                break
            spans.append((lines[k][0] + m.start(1), lines[k][0] + m.end(1)))
        else:
            nxt = i + 1 + len(shape)
            # The run must end here: one more bare group is a list of values.
            if nxt < len(lines) and _ALONE.fullmatch(lines[nxt][1]):
                continue
            return spans
    return []


def _hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


_CLINIC_SIDE = re.compile(
    r"(?i)\b(?:call[ \t]+us|reach[ \t]+us|our[ \t]+(?:number|line|phone|office)|main[ \t]+line|front[ \t]+desk|reception|"
    r"clinic(?:['’]s)?[ \t]+(?:number|line|phone)|\(clinic\b|appelez[ \t]+-?nous|ll[aá]menos|zadzwo[ńn][ \t]+do[ \t]+nas)"
)
_FIRST_PERSON = re.compile(r"(?i)\b(?:my|me|mine|i|i['’]m|mon|ma|mi|m[óo]j|moja|moje)\b")


def detect(text: str) -> list[tuple[int, int]]:
    """Spans of the pieces of phone numbers given group by group."""
    lines = [(m.start(), m.group(0)) for m in re.finditer(r"[^\n]+", text)]
    cue_at = [bool(_CUE.search(line)) for _, line in lines]
    found: set[tuple[int, int]] = set()
    for i, has_cue in enumerate(cue_at):
        if not has_cue:
            found.update(_extra_shape_spans(lines, i))
            continue
        cue_line = lines[i][1]
        if _NONPHONE_NUMBER.search(cue_line) and not _CUE.search(_NONPHONE_NUMBER.sub(" ", cue_line)):
            continue  # "lot number?": the cue is not about a phone
        if _CLINIC_SIDE.search(cue_line) and not _FIRST_PERSON.search(cue_line):
            continue  # "Call us: area code 416, then 555 ... (clinic main line)": the clinic's own number
        pieces: list[tuple[int, int, str]] = []  # (start, end, digits) in order
        stage = 0  # 0 want area, 1 want exchange, 2 want line, 3 corrections
        last = ""
        committed = False
        for k in range(i, min(i + _WINDOW, len(lines))):
            base, line = lines[k]
            frags = list(_FRAG.finditer(line))
            if k > i and not frags and _OTHER_TOPIC.search(line):
                break  # another numeric topic comes before the pieces
            if k == i and len(frags) >= 2 and not _STRONG_CUE.search(line):
                continue
            if not frags or len(_DIGITS.findall(line)) != len(frags) or len(line.split()) > _MAX_WORDS + 1:
                continue
            for f in frags:
                d = f.group(1)
                if _UNIT_AFTER.match(line, f.end()) or _NONPHONE_LABEL.search(line[: f.start()]):
                    continue
                span = (base + f.start(1), base + f.end(1), d)
                if stage == 0 and len(d) == 3 and d[0] in "23456789":
                    pieces.append(span)
                    stage = 1
                elif stage == 1 and len(d) == 3 and d[0] in "23456789":
                    pieces.append(span)
                    stage = 2
                elif stage == 2 and len(d) == 4:
                    pieces.append(span)
                    stage, last, committed = 3, d, True
                elif stage == 3 and len(d) == 4 and _hamming(d, last) <= 2:
                    pieces.append(span)  # the line number said again, corrected
                    last = d
        if committed:
            found.update((a, b) for a, b, _ in pieces)
        else:
            found.update(_extra_shape_spans(lines, i))
    return sorted(found)
