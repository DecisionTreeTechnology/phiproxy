"""phiproxy: reversible PHI masking for LLM traffic.

Mask patient identifiers before a prompt leaves your network, restore them in the
reply. phiproxy reduces how much PHI reaches an LLM provider; it does not make an
unapproved provider compliant. See README for the full disclaimer.
"""

from .detectors import KnownEntities, KnownEntityDetector, RegexDetector
from .entities import Entity, EntityType
from .masker import Masker, MaskResult, PhiproxyError, Policy, StreamUnmasker, UnsupportedContentError
from .vault import InMemoryVault, RedisVault, Vault

__version__ = "0.1.0a6"

__all__ = [
    "Entity",
    "EntityType",
    "InMemoryVault",
    "KnownEntities",
    "KnownEntityDetector",
    "MaskResult",
    "Masker",
    "PhiproxyError",
    "Policy",
    "RedisVault",
    "RegexDetector",
    "StreamUnmasker",
    "UnsupportedContentError",
    "Vault",
]
