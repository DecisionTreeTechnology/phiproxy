"""Entity types and the detected-span record."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EntityType(str, Enum):
    """What kind of identifier a span is.

    The label is what appears inside a token, e.g. ``[NAME_1]``. Types map to the
    HIPAA Safe Harbor identifier list (45 CFR 164.514(b)(2)) plus Canadian and
    fertility-clinic identifiers.
    """

    NAME = "NAME"
    PROVIDER = "PROVIDER"  # clinician name ("Dr. Smith"); off by default, see Policy
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    DATE = "DATE"
    AGE = "AGE"  # ages over 89 only (Safe Harbor)
    ADDRESS = "ADDRESS"
    POSTAL_CODE = "POSTAL_CODE"
    ZIP = "ZIP"
    SSN = "SSN"
    SIN = "SIN"  # Canadian Social Insurance Number
    HEALTH_CARD = "HEALTH_CARD"  # OHIP, RAMQ and other provincial health numbers
    MRN = "MRN"
    DONOR_ID = "DONOR_ID"  # gamete donor / embryo identifiers
    ACCOUNT = "ACCOUNT"
    ID = "ID"  # any other identifying number
    EMPLOYER = "EMPLOYER"  # a named workplace, which can identify a person
    URL = "URL"
    IP_ADDRESS = "IP_ADDRESS"


@dataclass(frozen=True)
class Entity:
    """A detected identifier inside a piece of text."""

    type: EntityType
    start: int
    end: int
    text: str
    source: str  # which detector found it: "known", "regex", "presidio", ...
    score: float = 1.0
    # Normalized value used for token assignment, e.g. the spelling from the
    # patient record when the text had a typo. Defaults to the span text.
    canonical: Optional[str] = None

    def __post_init__(self) -> None:
        if not (0 <= self.start < self.end):
            raise ValueError(f"invalid span {self.start}:{self.end}")

    def overlaps(self, other: "Entity") -> bool:
        return self.start < other.end and other.start < self.end

    @property
    def value(self) -> str:
        return self.canonical if self.canonical is not None else self.text

    @property
    def length(self) -> int:
        return self.end - self.start
