"""WORK-032 conformance suite -- the deterministic vector registry.

Vectors register from the per-area modules; the registry enforces
unique vector ids, a frozen tag vocabulary, and a canonical ordering
that is independent of insertion order (spec/prompts/WORK-032.md,
Determinism: "vector ordering independent of insertion order").
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

from conformance.model import (
    AREA_AUTHORITY,
    ConformanceVector,
    KNOWN_TAGS,
    Polarity,
    RegistryError,
    REQUIRED_AREAS,
)

__all__ = ["VectorRegistry", "build_default_registry"]


class VectorRegistry:
    """Deterministic registry of conformance vectors (fail closed)."""

    def __init__(self) -> None:
        self._vectors: Dict[str, ConformanceVector] = {}

    # -- registration ------------------------------------------------------

    def register(self, vector: ConformanceVector) -> None:
        """Register one vector; duplicates and unknown tags fail closed."""
        if not isinstance(vector, ConformanceVector):
            raise RegistryError("registry accepts ConformanceVector instances only")
        if vector.vector_id in self._vectors:
            raise RegistryError("duplicate vector id: %s" % vector.vector_id)
        if vector.area not in REQUIRED_AREAS:
            raise RegistryError(
                "vector %s has unknown area %r" % (vector.vector_id, vector.area)
            )
        if vector.authority != AREA_AUTHORITY.get(vector.area, vector.authority):
            # structure-area vectors may cite WORK-032 itself; every other
            # area must attribute its outcome to the owning authority.
            if vector.area != "structure" or vector.authority != "WORK-032":
                raise RegistryError(
                    "vector %s authority %r does not own area %r"
                    % (vector.vector_id, vector.authority, vector.area)
                )
        if vector.polarity not in (Polarity.POSITIVE.value, Polarity.NEGATIVE.value):
            raise RegistryError(
                "vector %s has unknown polarity %r"
                % (vector.vector_id, vector.polarity)
            )
        unknown_tags = set(vector.tags) - KNOWN_TAGS
        if unknown_tags:
            raise RegistryError(
                "vector %s uses tags outside the frozen vocabulary: %s"
                % (vector.vector_id, sorted(unknown_tags))
            )
        self._vectors[vector.vector_id] = vector

    def register_all(self, vectors: Iterable[ConformanceVector]) -> None:
        for vector in vectors:
            self.register(vector)

    # -- queries -----------------------------------------------------------

    def canonical_vectors(self) -> Tuple[ConformanceVector, ...]:
        """All vectors in canonical (vector-id sorted) order.

        The order is total (unique ids) and independent of the order in
        which vectors were registered.
        """
        return tuple(self._vectors[k] for k in sorted(self._vectors))

    def vector_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._vectors))

    def __len__(self) -> int:
        return len(self._vectors)

    def areas(self) -> Tuple[str, ...]:
        seen: Set[str] = {v.area for v in self._vectors.values()}
        return tuple(a for a in REQUIRED_AREAS if a in seen)

    def counts_by_area(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for vector in self._vectors.values():
            counts[vector.area] = counts.get(vector.area, 0) + 1
        return {area: counts[area] for area in sorted(counts)}

    def counts_by_polarity(self) -> Dict[str, int]:
        counts = {"positive": 0, "negative": 0}
        for vector in self._vectors.values():
            counts[vector.polarity] += 1
        return counts

    def tags(self) -> List[str]:
        seen: Set[str] = set()
        for vector in self._vectors.values():
            seen.update(vector.tags)
        return sorted(seen)


def build_default_registry() -> VectorRegistry:
    """Build the default registry from all area modules (fixed order).

    Registration order is deliberately documented as irrelevant: the
    canonical order is the sorted vector-id order.
    """
    from conformance.vectors import all_vectors

    registry = VectorRegistry()
    registry.register_all(all_vectors())
    return registry
