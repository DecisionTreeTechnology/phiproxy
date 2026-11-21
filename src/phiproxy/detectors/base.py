"""Detector interface and span merging."""

from __future__ import annotations

import bisect
from typing import Iterable, Protocol, Sequence

from ..entities import Entity

# When two detections overlap, the one from the higher-priority source wins.
# Known-entity matches come from the clinic's own records, so they are the most
# trustworthy; NER guesses are the least.
SOURCE_PRIORITY = {"known": 3, "regex": 2, "presidio": 1, "gliner": 1}


class Detector(Protocol):
    """Finds identifier spans in text. Must not call any external service."""

    name: str

    def detect(self, text: str) -> list[Entity]: ...


def merge_entities(entities: Iterable[Entity]) -> list[Entity]:
    """Resolve overlapping spans into a non-overlapping, start-ordered list.

    Overlaps are resolved by (span length, source priority, score): the longer
    span wins (an email beats a first name found inside it); on equal length the
    more trustworthy source wins; on a tie of both, any specific type beats the
    generic ACCOUNT (an "SSN ends in 1234" span stays SSN). If a loser extends past the winner, the winner
    is widened to the union so no character of the loser leaks.
    """
    ordered = sorted(
        entities,
        key=lambda e: (e.length, SOURCE_PRIORITY.get(e.source, 0), e.type.value != "ACCOUNT", e.score),
        reverse=True,
    )
    # Kept spans never overlap each other, so they are held sorted by start and the spans that clash
    # with a candidate are found by bisection (linear-ish instead of comparing every pair). ``rank``
    # keeps the priority order of the original list-based version: a widened winner goes first.
    starts: list[int] = []
    items: list[tuple[Entity, int]] = []
    next_rank = 0
    front_rank = -1
    empty: list[Entity] = []  # zero-width spans overlap nothing
    for cand in ordered:
        if cand.start >= cand.end:
            empty.append(cand)
            continue
        i = bisect.bisect_left(starts, cand.end)
        j = i - 1
        while j >= 0 and items[j][0].overlaps(cand):
            j -= 1
        lo, hi = j + 1, i
        if lo == hi:
            pos = bisect.bisect_right(starts, cand.start)
            starts.insert(pos, cand.start)
            items.insert(pos, (cand, next_rank))
            next_rank += 1
            continue
        clash = items[lo:hi]
        winner = min(clash, key=lambda t: t[1])[0]
        start = min([cand.start] + [c.start for c, _ in clash])
        end = max([cand.end] + [c.end for c, _ in clash])
        if len(clash) == 1 and (start, end) == (winner.start, winner.end):
            continue
        del starts[lo:hi]
        del items[lo:hi]
        widened = Entity(
            type=winner.type,
            start=start,
            end=end,
            text="?",  # placeholder; fill_text() re-attaches real text
            source=winner.source,
            score=winner.score,
        )
        pos = bisect.bisect_right(starts, start)
        starts.insert(pos, start)
        items.insert(pos, (widened, front_rank))
        front_rank -= 1
    kept = [e for e, _ in items] + empty
    return sorted(kept, key=lambda e: e.start)


def fill_text(text: str, entities: Sequence[Entity]) -> list[Entity]:
    """Re-attach span text after merging (merge may widen spans)."""
    out = []
    for e in entities:
        span = text[e.start : e.end]
        # A widened span no longer matches its canonical form; fall back to the text.
        canonical = e.canonical if span == e.text else None
        out.append(Entity(e.type, e.start, e.end, span, e.source, e.score, canonical))
    return out
