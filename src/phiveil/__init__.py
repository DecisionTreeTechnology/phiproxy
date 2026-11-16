"""phiveil: reversible PHI masking for LLM traffic.

Mask patient identifiers before a prompt leaves your network, restore them in the
reply. phiveil reduces how much PHI reaches an LLM provider; it does not make an
unapproved provider compliant. See README for the full disclaimer.
"""

from .detectors import KnownEntities, KnownEntityDetector, RegexDetector
from .entities import Entity, EntityType
from .masker import Masker, MaskResult, PhiveilError, Policy, StreamUnmasker, UnsupportedContentError
from .vault import InMemoryVault, RedisVault, Vault

__version__ = "0.1.0.dev0"

__all__ = [
    "Entity",
    "EntityType",
    "InMemoryVault",
    "KnownEntities",
    "KnownEntityDetector",
    "MaskResult",
    "Masker",
    "PhiveilError",
    "Policy",
    "RedisVault",
    "RegexDetector",
    "StreamUnmasker",
    "UnsupportedContentError",
    "Vault",
]
