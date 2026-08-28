"""ADCOS service registry / edge compute canonical serialization
(WORK-025).

Canonical DATA reduction (mirrors the WORK-022/023/024 families):
model objects reduce via their ``to_dict``, tuples serialize as
arrays, and the final bytes come from the frozen
``protocol.canonicalization.canonical_json_bytes`` profile (RFC
8785-like key ordering, no whitespace, floats rejected).  Two
conformant implementations reproduce identical canonical bytes for
the same authoritative service facts.
"""

from __future__ import annotations

from typing import Any

from protocol.canonicalization import canonical_json_bytes


def to_canonical_dict(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return to_canonical_dict(value.to_dict())
    if isinstance(value, dict):
        return {key: to_canonical_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_canonical_dict(item) for item in value]
    return value


def to_canonical_bytes(value: Any) -> bytes:
    return canonical_json_bytes(to_canonical_dict(value))


__all__ = [
    "to_canonical_dict",
    "to_canonical_bytes",
]
