"""Optional local-model layer using GLiNER, run in-process (nothing leaves).

Pattern rules cannot find a lowercase name that is not in the patient's record
("my husband ravi"), a city ("I live in Sudbury") or a workplace. A small
named-entity model can. GLiNER models are zero-shot: they take the entity
labels as plain text, so the same model covers several languages and types.

Install with ``pip install phiproxy[gliner]``. The default model is
``urchade/gliner_multi_pii-v1`` (Apache-2.0, about 1.2 GB, English, French,
Spanish, German, Italian, Portuguese). It is downloaded from Hugging Face on
first use; in production, download it once and point ``model`` at the local
directory, or set ``HF_HUB_OFFLINE=1``. Text is never sent anywhere to detect
PHI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..entities import Entity, EntityType

DEFAULT_MODEL = "urchade/gliner_multi_pii-v1"

# Label shown to the model -> phiproxy type. The model sees only the keys.
DEFAULT_LABELS: dict[str, EntityType] = {
    "person": EntityType.NAME,
    "doctor or nurse": EntityType.PROVIDER,
    "city": EntityType.ADDRESS,
    "street address": EntityType.ADDRESS,
    "employer": EntityType.EMPLOYER,
}

_WORD = re.compile(r"\S+")

# NER models sometimes tag pronouns and role words as people ("we", "you",
# "Patient"). These closed-class words are never names on their own.
_NOT_NAMES = frozenset(
    """
    i me my mine you your yours we us our ours he him his she her hers they them
    their it someone somebody everyone anyone patient patients caller agent
    partner husband wife spouse mom mum mother dad father baby doctor nurse
    je moi tu toi vous nous il elle ils elles on yo tú tu usted ustedes nosotros
    nosotras él ella ellos ellas ja ty wy oni ona on pan pani
    """.split()
)


@dataclass
class GlinerDetector:
    """Local NER detector for names, places and workplaces.

    ``threshold`` is deliberately low: a missed name is a disclosure, while an
    extra mask only costs the model a little context.
    """

    name: str = "gliner"
    model: Any = DEFAULT_MODEL  # model id, local path, or a loaded GLiNER instance
    labels: dict[str, EntityType] = field(default_factory=lambda: dict(DEFAULT_LABELS))
    threshold: float = 0.4
    # GLiNER reads at most a few hundred words at once; longer text is cut into
    # overlapping windows so an entity on a boundary is still seen whole.
    window_words: int = 200
    overlap_words: int = 40
    device: Optional[str] = None  # e.g. "cuda", "mps"; default CPU

    def __post_init__(self) -> None:
        if isinstance(self.model, str):
            from gliner import GLiNER  # type: ignore[import-not-found]

            self.model = GLiNER.from_pretrained(self.model)
            if self.device:
                self.model = self.model.to(self.device)
        if self.overlap_words >= self.window_words:
            raise ValueError("overlap_words must be smaller than window_words")

    def detect(self, text: str) -> list[Entity]:
        out: list[Entity] = []
        seen: set[tuple[int, int, EntityType]] = set()
        label_names = list(self.labels)
        for offset, chunk in _windows(text, self.window_words, self.overlap_words):
            for p in self.model.predict_entities(chunk, label_names, threshold=self.threshold):
                t = self.labels.get(p["label"])
                if t is None:
                    continue
                start, end = offset + p["start"], offset + p["end"]
                span = text[start:end]
                if (start, end, t) in seen or len(span.strip()) < 2:
                    continue
                if t is EntityType.NAME and span.strip().lower() in _NOT_NAMES:
                    continue
                seen.add((start, end, t))
                out.append(Entity(t, start, end, span, self.name, float(p["score"])))
        return out


def _windows(text: str, size: int, overlap: int) -> list[tuple[int, str]]:
    """Split text into (char offset, chunk) windows of ``size`` words."""
    words = list(_WORD.finditer(text))
    if len(words) <= size:
        return [(0, text)]
    out = []
    step = size - overlap
    for i in range(0, len(words), step):
        group = words[i : i + size]
        start, end = group[0].start(), group[-1].end()
        out.append((start, text[start:end]))
        if i + size >= len(words):
            break
    return out
