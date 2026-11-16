"""Token vaults: the private mapping between tokens and real values.

Tokens are assigned sequentially per session (``[NAME_1]``, ``[NAME_2]``...).
They are *not* derived from the value (no hashing), so a token on its own carries
no information about the person - see 45 CFR 164.514(c) on re-identification codes.
The same value always gets the same token within a session, which keeps
multi-turn conversations coherent and keeps provider prompt caching working.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

from .entities import EntityType


def normalize_value(entity_type: EntityType, value: str) -> str:
    """Key used to decide whether two spans are 'the same value'."""
    if entity_type in (EntityType.PHONE, EntityType.SSN, EntityType.SIN):
        digits = re.sub(r"\D", "", value)
        if entity_type is EntityType.PHONE and len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        return digits
    if entity_type in (EntityType.HEALTH_CARD, EntityType.MRN, EntityType.ID,
                       EntityType.DONOR_ID, EntityType.ACCOUNT, EntityType.POSTAL_CODE):
        return re.sub(r"[\s\-.]", "", value).upper()
    return " ".join(value.split()).casefold()


def format_token(entity_type: EntityType, n: int) -> str:
    return f"[{entity_type.value}_{n}]"


def random_date_offset(min_days: int = 7, max_days: int = 60) -> int:
    """A non-zero day offset in [-max, -min] U [min, max]."""
    days = min_days + secrets.randbelow(max_days - min_days + 1)
    return days if secrets.randbelow(2) else -days


class Vault(Protocol):
    def token_for(self, session_id: str, entity_type: EntityType, value: str) -> str:
        """Return the session's token for this value, creating one if needed."""

    def value_for(self, session_id: str, token: str) -> Optional[str]:
        """Return the original value for a token, or None if unknown."""

    def mapping(self, session_id: str) -> dict[str, str]:
        """All token -> value pairs for a session."""

    def date_offset(self, session_id: str) -> int:
        """The session's date-shift offset in days (created on first use)."""

    def forget(self, session_id: str) -> None:
        """Delete a session's mapping."""


@dataclass
class _Session:
    touched: float
    value_to_token: dict[tuple[str, str], str] = field(default_factory=dict)
    token_to_value: dict[str, str] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    date_offset: Optional[int] = None


class InMemoryVault:
    """Process-local vault. Fine for a single process; use RedisVault behind replicas."""

    def __init__(self, ttl_seconds: float = 24 * 3600, date_shift_days: tuple[int, int] = (7, 60)):
        self.ttl = ttl_seconds
        self.date_shift_days = date_shift_days
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def _get(self, session_id: str) -> _Session:
        now = time.monotonic()
        # Cheap eviction on access.
        expired = [k for k, s in self._sessions.items() if now - s.touched > self.ttl]
        for k in expired:
            del self._sessions[k]
        s = self._sessions.get(session_id)
        if s is None:
            s = self._sessions[session_id] = _Session(touched=now)
        s.touched = now
        return s

    def token_for(self, session_id: str, entity_type: EntityType, value: str) -> str:
        key = (entity_type.value, normalize_value(entity_type, value))
        with self._lock:
            s = self._get(session_id)
            tok = s.value_to_token.get(key)
            if tok is None:
                n = s.counters.get(entity_type.value, 0) + 1
                s.counters[entity_type.value] = n
                tok = format_token(entity_type, n)
                s.value_to_token[key] = tok
                s.token_to_value[tok] = value
            return tok

    def value_for(self, session_id: str, token: str) -> Optional[str]:
        with self._lock:
            return self._get(session_id).token_to_value.get(token)

    def mapping(self, session_id: str) -> dict[str, str]:
        with self._lock:
            return dict(self._get(session_id).token_to_value)

    def date_offset(self, session_id: str) -> int:
        with self._lock:
            s = self._get(session_id)
            if s.date_offset is None:
                s.date_offset = random_date_offset(*self.date_shift_days)
            return s.date_offset

    def forget(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


class RedisVault:
    """Vault shared across processes/replicas. Requires ``pip install phiveil[redis]``.

    Keys (all expire after ``ttl_seconds`` of inactivity):
      {prefix}:{session}:v2t   hash  "<TYPE>|<normalized>" -> token
      {prefix}:{session}:t2v   hash  token -> original value
      {prefix}:{session}:n     hash  TYPE -> counter
      {prefix}:{session}:shift string day offset
    Values are stored in plain text: protect Redis like the PHI store it is
    (private network, TLS, auth, encryption at rest).
    """

    def __init__(self, client=None, url: Optional[str] = None, prefix: str = "phiveil",
                 ttl_seconds: int = 24 * 3600, date_shift_days: tuple[int, int] = (7, 60)):
        if client is None:
            import redis  # type: ignore[import-not-found]

            client = redis.Redis.from_url(url or "redis://localhost:6379/0", decode_responses=True)
        self.r = client
        self.prefix = prefix
        self.ttl = ttl_seconds
        self.date_shift_days = date_shift_days

    def _k(self, session_id: str, part: str) -> str:
        return f"{self.prefix}:{session_id}:{part}"

    def _touch(self, session_id: str) -> None:
        for part in ("v2t", "t2v", "n", "shift"):
            self.r.expire(self._k(session_id, part), self.ttl)

    def token_for(self, session_id: str, entity_type: EntityType, value: str) -> str:
        field_ = f"{entity_type.value}|{normalize_value(entity_type, value)}"
        v2t = self._k(session_id, "v2t")
        tok = self.r.hget(v2t, field_)
        if tok is None:
            n = self.r.hincrby(self._k(session_id, "n"), entity_type.value, 1)
            candidate = format_token(entity_type, int(n))
            if self.r.hsetnx(v2t, field_, candidate):
                self.r.hset(self._k(session_id, "t2v"), candidate, value)
                tok = candidate
            else:  # another replica assigned it first
                tok = self.r.hget(v2t, field_)
        self._touch(session_id)
        return str(tok)

    def value_for(self, session_id: str, token: str) -> Optional[str]:
        return self.r.hget(self._k(session_id, "t2v"), token)

    def mapping(self, session_id: str) -> dict[str, str]:
        return dict(self.r.hgetall(self._k(session_id, "t2v")) or {})

    def date_offset(self, session_id: str) -> int:
        key = self._k(session_id, "shift")
        self.r.set(key, random_date_offset(*self.date_shift_days), nx=True, ex=self.ttl)
        return int(self.r.get(key))

    def forget(self, session_id: str) -> None:
        self.r.delete(*(self._k(session_id, p) for p in ("v2t", "t2v", "n", "shift")))
