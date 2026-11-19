"""Date shifting that keeps the original writing style.

Shifting every date in a session by the same random offset hides the real dates
but keeps intervals intact (cycle day 3 -> retrieval -> transfer 5 days later),
which clinical reasoning depends on. The reply is shifted back by the same offset.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

_MONTHS_FULL = [
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
]
_MONTH_LOOKUP = {}
for _i, _m in enumerate(_MONTHS_FULL, start=1):
    _MONTH_LOOKUP[_m] = _i
    _MONTH_LOOKUP[_m[:3]] = _i
_MONTH_LOOKUP["sept"] = 9

_NO_YEAR_REF = 2024  # leap year, so "Feb 29" without a year still parses

_ISO = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})$")
_NUMERIC = re.compile(r"^(?P<a>\d{1,2})(?P<sep>[/\-.])(?P<b>\d{1,2})(?:(?P=sep)(?P<y>\d{4}|\d{2}))?$")
_MONTH_FIRST = re.compile(
    r"^(?P<mon>[A-Za-z]+)(?P<dot>\.?)(?P<sp>\s+)(?P<d>\d{1,2})(?P<suf>st|nd|rd|th)?"
    r"(?:(?P<comma>,?)(?P<sp2>\s+)(?P<y>\d{4}))?$",
    re.IGNORECASE,
)
_DAY_FIRST = re.compile(
    r"^(?P<d>\d{1,2})(?P<suf>st|nd|rd|th)?(?P<sp>\s+)(?P<of>of\s+)?(?P<mon>[A-Za-z]+)(?P<dot>\.?)"
    r"(?:(?P<comma>,?)(?P<sp2>\s+)(?P<y>\d{4}))?$",
    re.IGNORECASE,
)


def _suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _month_word(month: int, like: str) -> str:
    full = _MONTHS_FULL[month - 1]
    if len(like.rstrip(".")) <= 3 or (len(like) == 4 and like.lower() == "sept"):
        word = full[:3]
    else:
        word = full
    if like.isupper():
        return word.upper()
    if like[0].isupper():
        return word.capitalize()
    return word


def _pad(n: int, like: str, other: str = "") -> str:
    """Zero-pad when the original date shows a padded style ("03/14" or "11/03")."""
    padded = (len(like) == 2 and like.startswith("0")) or (len(other) == 2 and other.startswith("0"))
    return f"{n:02d}" if padded else str(n)


def _year(y: int, like: str) -> str:
    return f"{y % 100:02d}" if len(like) == 2 else str(y)


def _full_year(two_or_four: str) -> int:
    y = int(two_or_four)
    if len(two_or_four) == 2:
        y += 2000 if y < 70 else 1900
    return y


def shift_date_text(text: str, days: int, day_first: bool = False) -> Optional[str]:
    """Shift a date written as text by ``days``, keeping its format.

    Returns None if the text is not a date this module understands; callers
    should then fall back to replacing it with a token.
    """
    s = text.strip()
    try:
        m = _ISO.match(s)
        if m:
            d = date(int(m["y"]), int(m["m"]), int(m["d"])) + timedelta(days=days)
            return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"

        m = _NUMERIC.match(s)
        if m:
            a, b = int(m["a"]), int(m["b"])
            month_first = not day_first
            if a > 12 and b <= 12:
                month_first = False
            elif b > 12 and a <= 12:
                month_first = True
            mo, dy = (a, b) if month_first else (b, a)
            mo_like, dy_like = (m["a"], m["b"]) if month_first else (m["b"], m["a"])
            year = _full_year(m["y"]) if m["y"] else _NO_YEAR_REF
            d = date(year, mo, dy) + timedelta(days=days)
            mo_s, dy_s = _pad(d.month, mo_like, dy_like), _pad(d.day, dy_like, mo_like)
            first, second = (mo_s, dy_s) if month_first else (dy_s, mo_s)
            out = f"{first}{m['sep']}{second}"
            if m["y"]:
                out += f"{m['sep']}{_year(d.year, m['y'])}"
            return out

        for pat, month_first in ((_MONTH_FIRST, True), (_DAY_FIRST, False)):
            m = pat.match(s)
            if not m:
                continue
            month = _MONTH_LOOKUP.get(m["mon"].lower())
            if month is None:
                return None
            year = int(m["y"]) if m["y"] else _NO_YEAR_REF
            d = date(year, month, int(m["d"])) + timedelta(days=days)
            mon = _month_word(d.month, m["mon"]) + m["dot"]
            day = str(d.day) + (_suffix(d.day) if m["suf"] else "")
            if month_first:
                out = f"{mon}{m['sp']}{day}"
            else:
                out = f"{day}{m['sp']}{m['of'] or ''}{mon}"
            if m["y"]:
                out += f"{m['comma']}{m['sp2']}{d.year}"
            return out
    except ValueError:  # e.g. 2/30
        return None
    return None


# A numeric pair after a card-expiry or a pain-score word is not a calendar date ("exp 03/25",
# "pain 5/10"). Such a span is still masked, but as a token: shifting it would rewrite a
# month/year or a score into an invented day.
_NOT_A_DATE_BEFORE = re.compile(
    r"(?i:\b(?:exp(?:iry|ires|ired|iration|\.)?|valid\s+(?:thru|until|through)|pain|score|scale|rating|rated|severity|intensity)\b)"
    r"[^\n\d]{0,20}$"
)


def is_non_date_context(text: str, start: int, end: int) -> bool:
    """True if ``text[start:end]`` is a bare numeric pair that follows an expiry or score word."""
    span = text[start:end]
    m = _NUMERIC.match(span)
    if m is None or (m["y"] and len(m["y"]) == 4):
        return False
    return bool(_NOT_A_DATE_BEFORE.search(text[max(0, start - 40) : start]))
