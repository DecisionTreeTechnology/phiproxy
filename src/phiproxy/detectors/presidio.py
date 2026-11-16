"""Optional NER layer using Microsoft Presidio, run in-process (nothing leaves).

Install with ``pip install phiproxy[presidio]`` plus a spaCy model, e.g.
``python -m spacy download en_core_web_lg``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..entities import Entity, EntityType

# Presidio entity -> phiproxy type. Unlisted Presidio entities are ignored.
DEFAULT_MAP: dict[str, EntityType] = {
    "PERSON": EntityType.NAME,
    "PHONE_NUMBER": EntityType.PHONE,
    "EMAIL_ADDRESS": EntityType.EMAIL,
    "DATE_TIME": EntityType.DATE,
    "LOCATION": EntityType.ADDRESS,
    "US_SSN": EntityType.SSN,
    "IP_ADDRESS": EntityType.IP_ADDRESS,
    "URL": EntityType.URL,
    "MEDICAL_LICENSE": EntityType.ID,
    "US_DRIVER_LICENSE": EntityType.ID,
    "US_PASSPORT": EntityType.ID,
    "US_BANK_NUMBER": EntityType.ACCOUNT,
    "CREDIT_CARD": EntityType.ACCOUNT,
    "IBAN_CODE": EntityType.ACCOUNT,
}


@dataclass
class PresidioDetector:
    name: str = "presidio"
    language: str = "en"
    score_threshold: float = 0.35  # low on purpose: recall over precision
    entity_map: dict[str, EntityType] = field(default_factory=lambda: dict(DEFAULT_MAP))
    analyzer: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.analyzer is None:
            from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]

            self.analyzer = AnalyzerEngine()

    def detect(self, text: str) -> list[Entity]:
        results = self.analyzer.analyze(
            text=text,
            language=self.language,
            entities=list(self.entity_map.keys()),
            score_threshold=self.score_threshold,
        )
        out = []
        for r in results:
            t = self.entity_map.get(r.entity_type)
            if t is None or r.end <= r.start:
                continue
            # Presidio tags times ("3pm") and durations ("5 days") as DATE_TIME too;
            # those are not identifiers. Calendar dates are left to the regex layer.
            if t is EntityType.DATE:
                continue
            out.append(Entity(t, r.start, r.end, text[r.start : r.end], self.name, float(r.score)))
        return out
