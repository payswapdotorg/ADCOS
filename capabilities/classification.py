"""Capability identifier classification (open-world, no coercion).

The single identifier authority is the WORK-002 capability registry
(spec/schemas/registries/capability-registry.json) — loaded here, never
duplicated in code. Classification mirrors the registry's
unknown_id_policy: KNOWN, UNKNOWN_BUT_WELL_FORMED (preserved verbatim,
safely ignorable when optional, explicit failure when required), or
INVALID (malformed; fails closed).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Mapping, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = (
    REPO_ROOT / "spec" / "schemas" / "registries" / "capability-registry.json"
)


class CapabilityIdClass:
    """Open-world identifier classification (never coerced)."""

    KNOWN = "known"
    UNKNOWN_BUT_WELL_FORMED = "unknown_but_well_formed"
    INVALID = "invalid"


def _load_registry() -> Mapping[str, object]:
    import json

    def hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key %r in capability registry" % key)
            result[key] = value
        return result

    if not REGISTRY_PATH.is_file():
        raise ValueError("missing capability registry: %s" % REGISTRY_PATH)
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"), object_pairs_hook=hook)
    if not isinstance(data, dict):
        raise ValueError("capability registry must be a JSON object")
    return data


@lru_cache(maxsize=1)
def _cached_registry() -> Mapping[str, object]:
    return _load_registry()


@lru_cache(maxsize=1024)
def classify_capability_id(capability_id: object) -> str:
    """Classify a capability identifier against the WORK-002 registry.

    Non-strings are INVALID. Malformed strings (failing the registry
    id_grammar) are INVALID. Registered entries are KNOWN. Well-formed
    unregistered identifiers are UNKNOWN_BUT_WELL_FORMED.
    """
    if not isinstance(capability_id, str):
        return CapabilityIdClass.INVALID
    registry = _cached_registry()
    entries = cast(Dict[str, object], registry.get("entries", {}))
    if isinstance(entries, Mapping) and capability_id in entries:
        return CapabilityIdClass.KNOWN
    grammar = cast(str, registry.get("id_grammar", ""))
    if grammar:
        import re

        if re.fullmatch(grammar, capability_id) is not None:
            return CapabilityIdClass.UNKNOWN_BUT_WELL_FORMED
    return CapabilityIdClass.INVALID


def known_capability_ids() -> FrozenSet[str]:
    """Registered capability identifiers (introspection/tests)."""
    registry = _cached_registry()
    entries = cast(Dict[str, object], registry.get("entries", {}))
    if isinstance(entries, Mapping):
        return frozenset(entries)
    return frozenset()
