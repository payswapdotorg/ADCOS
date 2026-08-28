"""Management-plane wire-form serialization (WORK-030).

Fail-closed round-trips for the management plane's own persisted
artifacts (audit records and role-assignment events) using the shared
WORK-003 canonicalization machinery (``canonical_json_bytes`` -- the
same primitive every family consumes).  Strict schemas: unknown keys,
wrong types, and malformed values fail closed; a truncated or
tampered DATA mapping never reconstructs a domain object.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import ManagementError, ManagementReasonCode
from .model import (
    AuditRecord,
    RoleAssignmentEvent,
    derive_audit_record_id,
    derive_role_event_id,
)


def audit_record_to_mapping(record: AuditRecord) -> Dict[str, Any]:
    """Wire form of an audit record (the content dict + its derived
    id; JSON-safe)."""
    out = record.content_dict()
    out["record_id"] = record.record_id
    return out


def audit_record_from_mapping(data: Mapping[str, Any]) -> AuditRecord:
    """Reconstruct an audit record from its wire form (fail closed:
    exact key set, strict types, and the chained content-derived id
    must recompute)."""
    required = {
        "record_id",
        "sequence",
        "recorded_instant",
        "operation",
        "operator_node_id",
        "outcome",
        "detail",
        "evidence_refs",
        "prev_digest",
    }
    if not isinstance(data, Mapping):
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "audit record wire form must be a mapping",
        )
    keys = set(data.keys())
    unknown = keys - required
    if unknown:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "audit record wire form carries unknown keys %s" % sorted(unknown),
        )
    missing = required - keys
    if missing:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "audit record wire form is missing keys %s" % sorted(missing),
        )
    refs = data["evidence_refs"]
    if not isinstance(refs, list) or not all(
        isinstance(r, str) and r for r in refs
    ):
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "audit record evidence_refs must be a list of non-empty strings",
        )
    sequence = data["sequence"]
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "audit record sequence must be an int",
        )
    record = AuditRecord(
        record_id=data["record_id"],
        sequence=sequence,
        recorded_instant=data["recorded_instant"],
        operation=data["operation"],
        operator_node_id=data["operator_node_id"],
        outcome=data["outcome"],
        detail=data["detail"],
        evidence_refs=tuple(refs),
        prev_digest=data["prev_digest"],
    )
    if derive_audit_record_id(record.prev_digest, record) != record.record_id:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "audit record id %r does not recompute from its content "
            "(tamper-evidence failed)" % record.record_id,
        )
    return record


def role_event_to_mapping(event: RoleAssignmentEvent) -> Dict[str, Any]:
    """Wire form of a role-assignment event."""
    out = event.content_dict()
    out["event_id"] = event.event_id
    return out


def role_event_from_mapping(data: Mapping[str, Any]) -> RoleAssignmentEvent:
    """Reconstruct a role-assignment event from its wire form (fail
    closed: exact key set, strict types, content-derived id must
    recompute)."""
    required = {
        "event_id",
        "kind",
        "operator_node_id",
        "role_id",
        "instant",
        "actor_node_id",
        "reason",
        "valid_from",
        "valid_until",
    }
    if not isinstance(data, Mapping):
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role event wire form must be a mapping",
        )
    keys = set(data.keys())
    unknown = keys - required
    if unknown:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role event wire form carries unknown keys %s" % sorted(unknown),
        )
    missing = required - keys
    if missing:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role event wire form is missing keys %s" % sorted(missing),
        )
    event = RoleAssignmentEvent(
        event_id=data["event_id"],
        kind=data["kind"],
        operator_node_id=data["operator_node_id"],
        role_id=data["role_id"],
        instant=data["instant"],
        actor_node_id=data["actor_node_id"],
        reason=data["reason"],
        valid_from=data["valid_from"],
        valid_until=data["valid_until"],
    )
    if derive_role_event_id(event) != event.event_id:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role event id %r does not recompute from its content "
            "(tamper-evidence failed)" % event.event_id,
        )
    return event


def audit_record_canonical_bytes(record: AuditRecord) -> bytes:
    """Canonical bytes of an audit record (the chain-verification
    input material)."""
    return canonical_json_bytes(record.content_dict())


def role_event_canonical_bytes(event: RoleAssignmentEvent) -> bytes:
    """Canonical bytes of a role-assignment event."""
    return canonical_json_bytes(event.content_dict())


__all__ = [
    "audit_record_canonical_bytes",
    "audit_record_from_mapping",
    "audit_record_to_mapping",
    "role_event_canonical_bytes",
    "role_event_from_mapping",
    "role_event_to_mapping",
]
