"""Detector interface and span merging."""

from __future__ import annotations

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
    more trustworthy source wins. If a loser extends past the winner, the winner
    is widened to the union so no character of the loser leaks.
    """
    ordered = sorted(
        entities,
        key=lambda e: (e.length, SOURCE_PRIORITY.get(e.source, 0), e.score),
        reverse=True,
    )
    kept: list[Entity] = []
    for cand in ordered:
        clash = [k for k in kept if k.overlaps(cand)]
        if not clash:
            kept.append(cand)
            continue
        # Widen the strongest overlapping winner to the union so no character
        # of the loser (or of other winners it bridges) leaks.
        winner = clash[0]  # kept is in priority order, so the first clash is strongest
        start = min([cand.start] + [k.start for k in clash])
        end = max([cand.end] + [k.end for k in clash])
        if len(clash) == 1 and (start, end) == (winner.start, winner.end):
            continue
        for k in clash:
            kept.remove(k)
        kept.insert(
            0,
            Entity(
                type=winner.type,
                start=start,
                end=end,
                text="?",  # placeholder; fill_text() re-attaches real text
                source=winner.source,
                score=winner.score,
            ),
        )
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
