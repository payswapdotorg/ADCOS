"""WORK-032 conformance vectors -- per-area vector modules.

Each module exposes ``vectors() -> Tuple[ConformanceVector, ...]``.
Registration order is irrelevant: the registry canonicalizes by
vector id (see conformance/registry.py).

WORK-055 added the wire module (R3 production-conformance coverage
for the envelope area: canonicalization profile rules, golden corpus,
signature coverage, unknown-field hardening, replay/idempotency, and
evidence separation).  The WORK-029 surfaces are covered from
tools/conformance_selftest.py, the sanctioned composition root.
"""

from __future__ import annotations

from typing import Tuple

from conformance.model import ConformanceVector

from conformance.vectors import (
    adapter,
    capabilities,
    envelope,
    federation,
    identity,
    routing,
    sessions,
    structure,
    topology,
    transport,
    wire,
)

__all__ = ["all_vectors"]


def all_vectors() -> Tuple[ConformanceVector, ...]:
    """Aggregate every area's vectors (order here is not canonical)."""
    aggregated: Tuple[ConformanceVector, ...] = ()
    for module in (
        envelope,
        identity,
        capabilities,
        topology,
        routing,
        sessions,
        federation,
        adapter,
        transport,
        structure,
        wire,
    ):
        aggregated = aggregated + module.vectors()
    return aggregated
