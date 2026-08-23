"""Capability registry view (WORK-002 authority, consumed read-only)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Mapping, cast

from .classification import CapabilityIdClass, _cached_registry, classify_capability_id

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = (
    REPO_ROOT / "spec" / "schemas" / "registries" / "capability-registry.json"
)


@dataclass(frozen=True)
class CapabilityRegistry:
    """Read-only view over the WORK-002 capability registry."""

    entries: FrozenSet[str]
    grammar: str

    def classify(self, capability_id: str) -> str:
        if capability_id in self.entries:
            return CapabilityIdClass.KNOWN
        if self.grammar:
            import re

            if re.fullmatch(self.grammar, capability_id) is not None:
                return CapabilityIdClass.UNKNOWN_BUT_WELL_FORMED
        return CapabilityIdClass.INVALID

    def is_known(self, capability_id: str) -> bool:
        return self.classify(capability_id) == CapabilityIdClass.KNOWN


@lru_cache(maxsize=1)
def default_registry() -> CapabilityRegistry:
    registry = _cached_registry()
    entries = cast(Mapping[str, object], registry.get("entries", {}))
    grammar = cast(str, registry.get("id_grammar", ""))
    return CapabilityRegistry(
        entries=frozenset(entries) if isinstance(entries, Mapping) else frozenset(),
        grammar=grammar,
    )
