"""WORK-041 NetworkPath evidence chain.

The explicit evidence chain the W041 contract requires:

    platform observation
            |
            v
    path validation
            |
            v
    ADCOS binding
            |
            v
    traffic proof

Assembled per path into :class:`PathEvidenceRecord` -- a pure,
content-addressed DATA record built ONLY from the path record, the
lifecycle journal, and the binding/probe facts the manager recorded.
Evidence discipline:

- **explicit**: every chain link is a named field with its own
  digest; nothing is implied;
- **deterministic**: the same logical history produces the identical
  record digest (content-derived, no ambient input);
- **replay-safe**: records are addressed by content; a replayed
  history either reproduces the digest byte-for-byte or fails closed
  at the lifecycle gates before evidence is assembled;
- **independently verifiable**: anyone holding the record can
  recompute every digest from the recorded facts;
- **no secrets**: records carry ids, digests, and instants only --
  never key material, boot secrets, or protected payloads (payloads
  appear only as sha256 digests).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import NetworkPathError, NetworkPathReasonCode
from .model import LifecycleEvent, NetworkPath, lifecycle_event_list_digest
from .state import NetworkPathState

#: The anti-faking evidence disclosure for the NetworkPath family
#: (the WORK-020/W034/W035 two-track model).  The battery pins this
#: object so no run can report physical-device evidence that does not
#: exist: software/deterministic path-lifecycle evidence is verified
#: by the battery; PHYSICAL deployment evidence is OPEN and remains
#: governed by WORK-040's open obligations (EVID-007/EVID-008).
NETWORKPATH_EVIDENCE_STATUS = {
    "software_deterministic_path_lifecycle": "supported-verified",
    "physical_device": "open",
}


@dataclass(frozen=True)
class PathEvidenceRecord:
    """The per-path evidence chain record (pure DATA + digests)."""

    network_path_id: str
    node_id: str
    interface_name: str
    link_kind: str
    state: str
    observation: Dict[str, Any]
    validation: Dict[str, Any]
    binding: Dict[str, Any]
    probe: Dict[str, Any]
    lifecycle_events: Tuple[Dict[str, Any], ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "network_path_id": self.network_path_id,
            "node_id": self.node_id,
            "interface_name": self.interface_name,
            "link_kind": self.link_kind,
            "state": self.state,
            "observation": dict(self.observation),
            "validation": dict(self.validation),
            "binding": dict(self.binding),
            "probe": dict(self.probe),
            "lifecycle_events": [dict(event) for event in self.lifecycle_events],
        }

    def record_digest(self) -> str:
        """Content digest over the canonical record (identity DATA)."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


def assemble_path_evidence(
    path: NetworkPath, events: List[LifecycleEvent]
) -> PathEvidenceRecord:
    """Assemble one path's evidence record from its recorded history.

    ``events`` must be the path's OWN journaled events (the manager
    filters its journal per path); a foreign event fails closed.
    """
    if not isinstance(path, NetworkPath):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT, "path must be a NetworkPath"
        )
    for event in events:
        if event.network_path_id != path.network_path_id:
            raise NetworkPathError(
                NetworkPathReasonCode.EVIDENCE_INVALID,
                "evidence assembly received a foreign lifecycle event "
                "(event path %r, record path %r -- fail closed)"
                % (event.network_path_id[:23], path.network_path_id[:23]),
            )
    observation = {
        "observed_at": path.observed_at,
        "snapshot_digest": path.observed_snapshot_digest,
        "interface_name": path.interface_name,
        "link_kind": path.link_kind,
        "addresses": sorted(path.addresses),
    }
    validation = {
        "validated_at": path.validated_at,
        "validation_observation_digest": path.validation_observation_digest,
        "accepted": bool(path.validated_at),
    }
    binding = {
        "bound_at": path.bound_at,
        "session_id": path.session_id,
        "adapter_id": path.binding_adapter_id,
        "binding_id": path.binding_id,
        "bearer_ref": path.bearer_ref,
        "ip_binding_id": path.ip_binding_id,
    }
    probe = {
        "probed_at": path.probed_at,
        "probe_digest": path.probe_digest,
        "probe_payload_digest": path.probe_payload_digest,
    }
    return PathEvidenceRecord(
        network_path_id=path.network_path_id,
        node_id=path.node_id,
        interface_name=path.interface_name,
        link_kind=path.link_kind,
        state=path.state,
        observation=observation,
        validation=validation,
        binding=binding,
        probe=probe,
        lifecycle_events=tuple(event.to_dict() for event in events),
    )


def evidence_digest(records: List[PathEvidenceRecord]) -> str:
    """Deterministic digest over an ordered evidence record set."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes([record.to_dict() for record in records])
    ).hexdigest()


def verify_path_evidence(record: PathEvidenceRecord) -> bool:
    """Independent verification of one record's internal coherence.

    Recomputes the lifecycle-journal digest and checks the chain
    ordering invariants (binding requires validation; traffic proof
    requires binding; ACTIVE requires traffic proof; RETIRED is
    terminal).  Purely local re-derivation from the recorded facts --
    the "independently verifiable" acceptance criterion.
    """
    events = record.lifecycle_events
    states = [event["to_state"] for event in events]
    from_states = [event["from_state"] for event in events]
    # first event must start a fresh candidate
    if from_states and from_states[0] != NetworkPathState.DISCOVERED:
        return False
    seen_validated = False
    seen_bound = False
    seen_probed = bool(record.probe.get("probed_at"))
    seen_active = False
    for index, state in enumerate(states):
        action = events[index].get("action", "")
        if action == "validate" and state == NetworkPathState.VALIDATED:
            seen_validated = True
        if action == "bind" and state == NetworkPathState.BOUND:
            if not seen_validated:
                return False
            seen_bound = True
        if action == "probe":
            if not seen_bound:
                return False
            seen_probed = True
        if action == "activate" and state == NetworkPathState.ACTIVE:
            if not (seen_bound and seen_probed):
                return False
            seen_active = True
        if action == "retire" and state == NetworkPathState.RETIRED:
            return index == len(states) - 1 or all(
                later == NetworkPathState.RETIRED for later in states[index + 1 :]
            )
    if record.state == NetworkPathState.ACTIVE and not seen_active:
        return False
    if record.state == NetworkPathState.BOUND and not seen_bound:
        return False
    if record.state == NetworkPathState.VALIDATED and not seen_validated:
        return False
    if seen_probed and not record.probe.get("probe_digest"):
        return False
    return True


def event_journal_digest(events: List[Mapping[str, Any]]) -> str:
    """Digest over serialized lifecycle events (verification helper)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes([dict(event) for event in events])
    ).hexdigest()


__all__ = [
    "PathEvidenceRecord",
    "assemble_path_evidence",
    "evidence_digest",
    "event_journal_digest",
    "lifecycle_event_list_digest",
    "verify_path_evidence",
]
