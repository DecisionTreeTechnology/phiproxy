"""Mask text and LLM payloads before they leave; restore them when replies come back."""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Optional, Sequence

from .dates import shift_date_text
from .detectors.base import Detector, fill_text, merge_entities
from .detectors.known import KnownEntities, KnownEntityDetector
from .detectors.regex import RegexDetector
from .entities import Entity, EntityType
from .vault import InMemoryVault, Vault


class PhiproxyError(Exception):
    """Masking failed. Callers must not send the original content (fail closed)."""


class UnsupportedContentError(PhiproxyError):
    """The payload holds content phiproxy cannot mask (images, audio, files)."""


# Detectors whose spans are statistical guesses rather than record or rule matches.
MODEL_SOURCES = frozenset({"presidio", "gliner"})


def _within(inner: Entity, outer: Entity) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end


@dataclass
class Policy:
    # Clinician names are not patient identifiers under Safe Harbor and masking
    # them hurts answers ("Dr. [PROVIDER_1] said..."), so they pass by default.
    disabled_types: set[EntityType] = field(default_factory=lambda: {EntityType.PROVIDER})
    # "token": dates become [DATE_n]. "shift": dates move by a per-session offset,
    # keeping intervals intact; the reply is shifted back.
    date_mode: Literal["token", "shift"] = "token"
    day_first: bool = False  # how to read 03/04/2026 (False = US month first)
    allow_images: bool = False
    allow_audio: bool = False
    allow_files: bool = False


@dataclass
class MaskResult:
    text: str
    entities: list[Entity]  # contains the original PHI - never log this

    def summary(self) -> dict[str, int]:
        """Counts per entity type; safe to log."""
        return dict(Counter(e.type.value for e in self.entities))


_TYPE_ALTERNATION = "|".join(
    sorted((t.value.replace("_", "[ _]?") for t in EntityType), key=len, reverse=True)
)
# Tolerant token matcher: [NAME_1], [name 1], [ NAME-1 ], NAME_1
_TOKEN_RE = re.compile(
    rf"\[\s*(?P<t1>{_TYPE_ALTERNATION})[ _\-]?(?P<n1>\d+)\s*\]|\b(?P<t2>{_TYPE_ALTERNATION})_(?P<n2>\d+)\b",
    re.IGNORECASE,
)

# Keys whose string values are structure, not content.
_STRUCTURAL_KEYS = {
    "role", "type", "id", "tool_call_id", "tool_use_id", "model", "cache_control",
    "media_type", "detail", "format", "index", "finish_reason", "object", "signature",
    "stop_reason", "call_id", "status",
}
_STREAM_HOLD = 48  # chars held back while streaming so tokens/dates are never split


class Masker:
    """Detects identifiers, swaps them for tokens, and swaps them back.

    >>> m = Masker()
    >>> r = m.mask("Call me at 416-555-0142", session_id="s1")
    >>> r.text
    'Call me at [PHONE_1]'
    >>> m.unmask("I will call [PHONE_1] today.", session_id="s1")
    'I will call 416-555-0142 today.'
    """

    def __init__(
        self,
        vault: Optional[Vault] = None,
        detectors: Optional[Sequence[Detector]] = None,
        policy: Optional[Policy] = None,
    ):
        self.vault: Vault = vault if vault is not None else InMemoryVault()
        self.detectors: list[Detector] = list(detectors) if detectors is not None else [RegexDetector()]
        self.policy = policy or Policy()
        self._date_detector = RegexDetector(enabled={EntityType.DATE})

    # ------------------------------------------------------------------ detect
    def detect(self, text: str, known: Optional[KnownEntities] = None) -> list[Entity]:
        detectors: list[Detector] = list(self.detectors)
        if known is not None and not known.is_empty():
            detectors.insert(0, KnownEntityDetector(known))
        found: list[Entity] = []
        for d in detectors:
            found.extend(d.detect(text))
        # A disabled span (by default a clinician name) also shields model
        # guesses inside it: a NER model tags "Dr. Patel" as a person too, and
        # that guess must not mask what the policy lets through. Matches from
        # records or rules inside it are still masked.
        disabled = [e for e in found if e.type in self.policy.disabled_types]
        found = [
            e
            for e in found
            if e.type not in self.policy.disabled_types
            and not (e.source in MODEL_SOURCES and any(_within(e, d) for d in disabled))
        ]
        return fill_text(text, merge_entities(found))

    # -------------------------------------------------------------------- mask
    def mask(self, text: str, session_id: str, known: Optional[KnownEntities] = None) -> MaskResult:
        try:
            entities = self.detect(text, known)
            out: list[str] = []
            pos = 0
            offset = None
            for e in entities:
                out.append(text[pos : e.start])
                replacement = None
                if e.type is EntityType.DATE and self.policy.date_mode == "shift":
                    if offset is None:
                        offset = self.vault.date_offset(session_id)
                    replacement = shift_date_text(e.text, offset, self.policy.day_first)
                if replacement is None:
                    replacement = self.vault.token_for(session_id, e.type, e.value)
                out.append(replacement)
                pos = e.end
            out.append(text[pos:])
            return MaskResult("".join(out), entities)
        except PhiproxyError:
            raise
        except Exception as exc:  # fail closed
            raise PhiproxyError(f"masking failed: {type(exc).__name__}") from exc

    # ------------------------------------------------------------------ unmask
    def unmask(self, text: str, session_id: str) -> str:
        if not text:
            return text
        mapping = self.vault.mapping(session_id)

        def repl(m: re.Match[str]) -> str:
            t = (m.group("t1") or m.group("t2")).upper().replace(" ", "_")
            if "_" not in t:  # "HEALTHCARD" -> "HEALTH_CARD"
                t = next((et.value for et in EntityType if et.value.replace("_", "") == t), t)
            n = m.group("n1") or m.group("n2")
            value = mapping.get(f"[{t}_{n}]")
            return value if value is not None else m.group(0)

        out = _TOKEN_RE.sub(repl, text) if mapping else text
        if self.policy.date_mode == "shift":
            out = self._shift_all_dates(out, session_id, direction=-1)
        return out

    def remask(self, text: str, session_id: str) -> str:
        """Put tokens back over real values (e.g. before writing a reply to logs)."""
        if not text:
            return text
        mapping = self.vault.mapping(session_id)
        for token, value in sorted(mapping.items(), key=lambda kv: len(kv[1]), reverse=True):
            if len(value) < 2:
                continue
            text = re.sub(r"(?<!\w)" + re.escape(value) + r"(?!\w)", token, text, flags=re.IGNORECASE)
        if self.policy.date_mode == "shift":
            text = self._shift_all_dates(text, session_id, direction=+1)
        return text

    def _shift_all_dates(self, text: str, session_id: str, direction: int) -> str:
        dates = self._date_detector.detect(text)
        if not dates:
            return text
        days = direction * self.vault.date_offset(session_id)
        out, pos = [], 0
        for e in merge_entities(dates):
            shifted = shift_date_text(text[e.start : e.end], days, self.policy.day_first)
            out.append(text[pos : e.start])
            out.append(shifted if shifted is not None else text[e.start : e.end])
            pos = e.end
        out.append(text[pos:])
        return "".join(out)

    # ---------------------------------------------------------------- payloads
    def mask_payload(self, obj: Any, session_id: str, known: Optional[KnownEntities] = None) -> Any:
        """Mask every content string in a JSON-like payload (messages, content blocks,
        tool calls, tool results). Returns a copy; raises on images/audio/files
        unless the policy allows them (they then pass through *unmasked*)."""
        return _walk(copy.deepcopy(obj), lambda s: self.mask(s, session_id, known).text, self.policy, masking=True)

    def unmask_payload(self, obj: Any, session_id: str) -> Any:
        return _walk(copy.deepcopy(obj), lambda s: self.unmask(s, session_id), self.policy, masking=False)

    def stream_unmasker(self, session_id: str) -> "StreamUnmasker":
        return StreamUnmasker(self, session_id)


def _walk(obj: Any, fn: Callable[[str], str], policy: Policy, masking: bool, key: Optional[str] = None,
          parent: Optional[dict] = None) -> Any:
    if isinstance(obj, str):
        if key in _STRUCTURAL_KEYS:
            return obj
        if key == "name" and not (parent and "role" in parent):
            return obj  # tool/function name, not a participant name
        if key == "arguments":  # tool-call arguments are a JSON string
            try:
                parsed = json.loads(obj)
            except ValueError:
                return fn(obj)
            return json.dumps(_walk(parsed, fn, policy, masking), ensure_ascii=False)
        return fn(obj)
    if isinstance(obj, dict):
        kind = _media_kind(obj)
        if kind is not None:
            if not masking:
                return obj
            if kind == "text_document":
                obj["source"] = _walk(obj["source"], fn, policy, masking, "source", obj)
                return obj
            allowed = {"image": policy.allow_images, "audio": policy.allow_audio, "file": policy.allow_files}[kind]
            if not allowed:
                raise UnsupportedContentError(f"payload contains {kind} content; blocked by policy")
            return obj  # allowed media passes through UNMASKED
        for k in list(obj.keys()):
            obj[k] = _walk(obj[k], fn, policy, masking, k, obj)
        return obj
    if isinstance(obj, list):
        return [_walk(v, fn, policy, masking, key, parent) for v in obj]
    return obj


_MEDIA_TYPES = {
    "image_url": "image", "image": "image", "input_image": "image",
    "input_audio": "audio", "audio": "audio",
    "file": "file", "input_file": "file", "document": "file",
}


def _media_kind(part: dict) -> Optional[str]:
    """Classify a content part by its declared type (OpenAI, Anthropic, Responses API)."""
    t = part.get("type")
    if not isinstance(t, str) or t not in _MEDIA_TYPES:
        return None
    src = part.get("source")
    if t == "document" and isinstance(src, dict) and src.get("type") == "text" and isinstance(src.get("data"), str):
        return "text_document"  # Anthropic plain-text document: maskable
    return _MEDIA_TYPES[t]


class StreamUnmasker:
    """Unmask a streamed reply chunk by chunk without splitting a token or date.

    Holds back the last few dozen characters until it is sure they do not
    start a token. Call ``flush()`` when the stream ends.
    """

    def __init__(self, masker: Masker, session_id: str):
        self.masker = masker
        self.session_id = session_id
        self._buf = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buf += chunk
        cut = len(self._buf) - _STREAM_HOLD
        if cut <= 0:
            return ""
        cut = self._safe_cut(cut)
        out, self._buf = self._buf[:cut], self._buf[cut:]
        return self.masker.unmask(out, self.session_id)

    def flush(self) -> str:
        out, self._buf = self._buf, ""
        return self.masker.unmask(out, self.session_id)

    def _safe_cut(self, cut: int) -> int:
        spans: list[tuple[int, int]] = [m.span() for m in _TOKEN_RE.finditer(self._buf)]
        lb = self._buf.rfind("[", 0, cut)
        if lb != -1 and "]" not in self._buf[lb:cut]:
            spans.append((lb, len(self._buf)))
        if self.masker.policy.date_mode == "shift":
            spans += [(e.start, e.end) for e in self.masker._date_detector.detect(self._buf)]
        for s, e in sorted(spans):
            if s < cut < e:
                cut = s
        return cut


def mask_texts(masker: Masker, texts: Iterable[str], session_id: str,
               known: Optional[KnownEntities] = None) -> list[MaskResult]:
    return [masker.mask(t, session_id, known) for t in texts]
