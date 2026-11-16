import pytest

from phiveil.dates import shift_date_text


@pytest.mark.parametrize(
    "text,days,expected",
    [
        ("2026-11-03", 10, "2026-11-13"),
        ("11/3/2026", 30, "12/3/2026"),
        ("11/03/2026", -3, "10/31/2026"),
        ("12/30/26", 5, "1/4/27"),
        ("3/14", 1, "3/15"),
        ("March 5, 1990", 1, "March 6, 1990"),
        ("Mar 5", 30, "Apr 4"),
        ("Nov 8th", 1, "Nov 9th"),
        ("5 March 2026", 1, "6 March 2026"),
        ("3rd of May", 19, "22nd of May"),
        ("MARCH 5", 0, "MARCH 5"),
        ("Feb 28", 1, "Feb 29"),  # no year: leap-year reference
    ],
)
def test_shift_keeps_format(text, days, expected):
    assert shift_date_text(text, days) == expected


@pytest.mark.parametrize("text", ["2/30/2026", "Foo 5", "hello"])
def test_unparseable_returns_none(text):
    assert shift_date_text(text, 3) is None


def test_day_first():
    assert shift_date_text("03/04/2026", 1, day_first=True) == "04/04/2026"
    assert shift_date_text("25/12/2026", 1) == "26/12/2026"  # 25 can only be a day
