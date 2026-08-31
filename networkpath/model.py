"""WORK-041 NetworkPath value model.

The frozen value records of the NetworkPath family:

- **PlatformObservation** -- what one read of the platform's interface
  source reported (the WORK-033 ``InterfaceSnapshot`` DATA, wrapped
  with its observation instant and content digest).  Observation is
  EVIDENCE, never protocol truth: nothing in this module converts an
  observation into session, route, or policy state.
- **NetworkPath** -- a technology-neutral representation of one
  observed connectivity path from THIS node, carrying its lifecycle
  state (``networkpath.state``), its binding facts (recorded, never
  owned), and its probe evidence digest.
- **LifecycleEvent** -- one append-only journaled lifecycle action
  with its deterministic, content-derived event id.

Identity discipline (the routing ``Path`` precedent): ``network_path_id``
is a CONTENT-DERIVED fingerprint --
``"sha256:" + sha256(canonical_json_bytes(content))`` over
(node id, interface name, link kind, sorted addresses).  It is a
fingerprint ONLY: not a NodeID, not a trust authority, never an
authorization, and never a session identity.  Volatile facts (link
counters, observed instants, binding references, lifecycle state) are
deliberately OUTSIDE the identity content: a path's identity is its
observed endpoint facts, not its volatile measurements.  The
constructor mechanically verifies the content binding, so a tampered
or deserialized NetworkPath can never carry an attacker-chosen id.

Temporal discipline: every instant is an injected RFC 3339 UTC string
(WORK-003 / WORK-033 clock seam).  No wall-clock reads, no UUIDs, no
randomness, no environment-dependent identity anywhere in this
family.  Iteration over path/observation sets is sorted, so identical
logical inputs produce identical canonical bytes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from agent.model import LINK_KINDS, InterfaceSnapshot

from .errors import NetworkPathError, NetworkPathReasonCode
from .state import (
    ACTION_REQUIRED_STATE,
    LIFECYCLE_TRANSITIONS,
    NetworkPathAction,
    NetworkPathState,
    transition_is_legal,
)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_instant(value: object, label: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if not isinstance(value, str) or not value:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "%s must be an RFC 3339 UTC instant string" % label,
        )
    return value


# ---------------------------------------------------------------------------
# Platform observation (evidence, never protocol truth)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlatformObservation:
    """One platform interface observation, projected as DATA.

    Wraps the WORK-033 ``InterfaceSnapshot`` with the observation
    instant and the snapshot's content digest.  The observation
    records platform facts (interface present, link kind, state,
    address information); it is INPUT to candidate discovery and
    validation -- it is never silently converted into ADCOS protocol
    state.
    """

    snapshot: InterfaceSnapshot
    observed_at: str
    origin: str = "interface-source"

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, InterfaceSnapshot):
            raise NetworkPathError(
                NetworkPathReasonCode.OBSERVATION_INVALID,
                "platform observation requires a genuine InterfaceSnapshot",
            )
        _require_instant(self.observed_at, "observed_at")
        _require_text(self.origin, "origin")

    @property
    def interface_name(self) -> str:
        return self.snapshot.name

    @property
    def link_kind(self) -> str:
        return self.snapshot.link_kind

    @property
    def state_up(self) -> bool:
        return self.snapshot.state_up

    @property
    def snapshot_digest(self) -> str:
        return self.snapshot.digest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "observed_at": self.observed_at,
            "origin": self.origin,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PlatformObservation":
        if not isinstance(data, Mapping):
            raise NetworkPathError(
                NetworkPathReasonCode.OBSERVATION_INVALID,
                "platform observation must be a mapping",
            )
        snapshot_data = data.get("snapshot")
        if not isinstance(snapshot_data, Mapping):
            raise NetworkPathError(
                NetworkPathReasonCode.OBSERVATION_INVALID,
                "platform observation snapshot must be a mapping",
            )
        try:
            snapshot = InterfaceSnapshot.from_dict(snapshot_data)
        except Exception as error:  # typed re-wrap (fail closed)
            raise NetworkPathError(
                NetworkPathReasonCode.OBSERVATION_INVALID,
                "interface snapshot round-trip failed: %s"
                % type(error).__name__,
            ) from error
        return cls(
            snapshot=snapshot,
            observed_at=str(data.get("observed_at", "")),
            origin=str(data.get("origin", "interface-source")),
        )

    def observation_digest(self) -> str:
        """Content digest over the canonical observation record."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


# ---------------------------------------------------------------------------
# NetworkPath (the technology-neutral path representation)
# ---------------------------------------------------------------------------


def network_path_identity_content(
    node_id: str,
    interface_name: str,
    link_kind: str,
    addresses: Tuple[str, ...],
) -> Dict[str, Any]:
    """The canonical identity content of a NetworkPath.

    Addresses are sorted (insertion-order independent); volatile
    measurements (counters, speed, observed instants, binding
    references) are deliberately excluded.
    """
    return {
        "node_id": node_id,
        "interface_name": interface_name,
        "link_kind": link_kind,
        "addresses": sorted(addresses),
    }


def derive_network_path_id(
    node_id: str,
    interface_name: str,
    link_kind: str,
    addresses: Tuple[str, ...],
) -> str:
    """The content-derived NetworkPath fingerprint (identity DATA only)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            network_path_identity_content(node_id, interface_name, link_kind, addresses)
        )
    ).hexdigest()


@dataclass(frozen=True)
class NetworkPath:
    """A technology-neutral observed connectivity path, with lifecycle.

    Content binding: ``network_path_id`` MUST equal the fingerprint
    recomputed from (node_id, interface_name, link_kind, addresses) --
    enforced at construction, so every NetworkPath (built by discovery,
    rebuilt via ``dataclasses.replace`` by the lifecycle manager, or
    deserialized) passes through the same tamper-evident gate.

    ``session_id`` is set when the path is BOUND (a binding is
    session-scoped); binding facts are RECORDED OUTPUTS of the
    authority-mediated binding (adapter + IP integration), never
    owned state.  ``probe_digest`` records the traffic-proof payload
    digest that activation requires.
    """

    network_path_id: str
    node_id: str
    interface_name: str
    link_kind: str
    addresses: Tuple[str, ...]
    state: str = NetworkPathState.DISCOVERED
    session_id: str = ""
    observed_at: str = ""
    observed_snapshot_digest: str = ""
    validation_observation_digest: str = ""
    validated_at: str = ""
    binding_adapter_id: str = ""
    binding_id: str = ""
    bearer_ref: str = ""
    ip_binding_id: str = ""
    bound_at: str = ""
    probe_digest: str = ""
    probed_at: str = ""
    probe_payload_digest: str = ""
    activated_at: str = ""
    retired_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.network_path_id, str):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "network_path_id must be a string",
            )
        _require_text(self.node_id, "node_id")
        _require_text(self.interface_name, "interface_name")
        _require_text(self.link_kind, "link_kind")
        if self.link_kind not in LINK_KINDS:
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "link_kind %r must be one of %s (the accepted OS "
                "classification vocabulary)" % (self.link_kind, list(LINK_KINDS)),
            )
        if not isinstance(self.addresses, tuple) or any(
            not isinstance(item, str) for item in self.addresses
        ):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "addresses must be a tuple of strings",
            )
        if self.state not in NetworkPathState.values():
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "state %r must be one of %s"
                % (self.state, list(NetworkPathState.values())),
            )
        # Tamper-evident content binding (the routing Path discipline):
        # an EMPTY id at construction means "derive it" (the WORK-007
        # claim_id convention); a non-empty id MUST equal the
        # fingerprint recomputed from the content, so a tampered or
        # deserialized record can never carry an attacker-chosen id.
        expected = derive_network_path_id(
            self.node_id, self.interface_name, self.link_kind, self.addresses
        )
        if self.network_path_id == "":
            object.__setattr__(self, "network_path_id", expected)
        elif self.network_path_id != expected:
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "network_path_id %r does not match the derived fingerprint %r "
                "(content binding: node + interface + link kind + sorted "
                "addresses -- tampered or misbound path id rejected)"
                % (self.network_path_id[:80], expected[:80]),
            )

    def identity_content(self) -> Dict[str, Any]:
        return network_path_identity_content(
            self.node_id, self.interface_name, self.link_kind, self.addresses
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "network_path_id": self.network_path_id,
            "node_id": self.node_id,
            "interface_name": self.interface_name,
            "link_kind": self.link_kind,
            "addresses": sorted(self.addresses),
            "state": self.state,
            "session_id": self.session_id,
            "observed_at": self.observed_at,
            "observed_snapshot_digest": self.observed_snapshot_digest,
            "validation_observation_digest": self.validation_observation_digest,
            "validated_at": self.validated_at,
            "binding_adapter_id": self.binding_adapter_id,
            "binding_id": self.binding_id,
            "bearer_ref": self.bearer_ref,
            "ip_binding_id": self.ip_binding_id,
            "bound_at": self.bound_at,
            "probe_digest": self.probe_digest,
            "probed_at": self.probed_at,
            "probe_payload_digest": self.probe_payload_digest,
            "activated_at": self.activated_at,
            "retired_at": self.retired_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "NetworkPath":
        if not isinstance(data, Mapping):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "network path must be a mapping",
            )
        addresses = data.get("addresses", ())
        if not isinstance(addresses, (list, tuple)):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "network path addresses must be a sequence",
            )
        return cls(
            network_path_id=str(data.get("network_path_id", "")),
            node_id=str(data.get("node_id", "")),
            interface_name=str(data.get("interface_name", "")),
            link_kind=str(data.get("link_kind", "")),
            addresses=tuple(str(item) for item in addresses),
            state=str(data.get("state", NetworkPathState.DISCOVERED)),
            session_id=str(data.get("session_id", "")),
            observed_at=str(data.get("observed_at", "")),
            observed_snapshot_digest=str(data.get("observed_snapshot_digest", "")),
            validation_observation_digest=str(
                data.get("validation_observation_digest", "")
            ),
            validated_at=str(data.get("validated_at", "")),
            binding_adapter_id=str(data.get("binding_adapter_id", "")),
            binding_id=str(data.get("binding_id", "")),
            bearer_ref=str(data.get("bearer_ref", "")),
            ip_binding_id=str(data.get("ip_binding_id", "")),
            bound_at=str(data.get("bound_at", "")),
            probe_digest=str(data.get("probe_digest", "")),
            probed_at=str(data.get("probed_at", "")),
            probe_payload_digest=str(data.get("probe_payload_digest", "")),
            activated_at=str(data.get("activated_at", "")),
            retired_at=str(data.get("retired_at", "")),
        )

    def content_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


# ---------------------------------------------------------------------------
# Lifecycle event (append-only journal record)
# ---------------------------------------------------------------------------


def derive_network_path_event_id(
    network_path_id: str,
    action: str,
    from_state: str,
    to_state: str,
    instant: str,
) -> str:
    """Content-derived lifecycle event id (journal identity DATA)."""
    content = {
        "network_path_id": network_path_id,
        "action": action,
        "from_state": from_state,
        "to_state": to_state,
        "instant": instant,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


@dataclass(frozen=True)
class LifecycleEvent:
    """One journaled NetworkPath lifecycle action.

    ``from_state == to_state`` marks a state-preserving journaled
    action (``PROBE``): evidence is recorded, lifecycle state is not
    changed.  ``event_id`` is content-derived over (path, action,
    from, to, instant) -- an exact replay of the same transition
    yields the same id and is rejected as a duplicate.
    """

    event_id: str
    network_path_id: str
    action: str
    from_state: str
    to_state: str
    instant: str
    detail: str = ""

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.network_path_id, "network_path_id")
        if self.action not in NetworkPathAction.values():
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "action %r must be one of %s"
                % (self.action, list(NetworkPathAction.values())),
            )
        for label, value in (("from_state", self.from_state), ("to_state", self.to_state)):
            if value not in NetworkPathState.values():
                raise NetworkPathError(
                    NetworkPathReasonCode.INVALID_INPUT,
                    "%s %r must be one of %s"
                    % (label, value, list(NetworkPathState.values())),
                )
        _require_instant(self.instant, "instant")
        expected = derive_network_path_event_id(
            self.network_path_id,
            self.action,
            self.from_state,
            self.to_state,
            self.instant,
        )
        if self.event_id != expected:
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "event_id %r does not match the derived fingerprint (content "
                "binding -- tampered or misbound event id rejected)"
                % (self.event_id[:80],),
            )
        if self.from_state != self.to_state and not transition_is_legal(
            self.from_state, self.to_state
        ):
            raise NetworkPathError(
                NetworkPathReasonCode.LIFECYCLE_ILLEGAL,
                "lifecycle event records an illegal transition %s -> %s "
                "(fail closed: the frozen table rejects it)"
                % (self.from_state, self.to_state),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "network_path_id": self.network_path_id,
            "action": self.action,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "instant": self.instant,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: object) -> "LifecycleEvent":
        if not isinstance(data, Mapping):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "lifecycle event must be a mapping",
            )
        return cls(
            event_id=str(data.get("event_id", "")),
            network_path_id=str(data.get("network_path_id", "")),
            action=str(data.get("action", "")),
            from_state=str(data.get("from_state", "")),
            to_state=str(data.get("to_state", "")),
            instant=str(data.get("instant", "")),
            detail=str(data.get("detail", "")),
        )


def lifecycle_event_list_digest(events: List[LifecycleEvent]) -> str:
    """Deterministic digest over the ordered lifecycle journal."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes([event.to_dict() for event in events])
    ).hexdigest()


#: Re-exported for callers that need the frozen vocabulary alongside
#: the value model (single import site).
STATE_VALUES = NetworkPathState.values()
TRANSITION_TABLE: Dict[str, FrozenSet[str]] = dict(LIFECYCLE_TRANSITIONS)
ACTION_VALUES = NetworkPathAction.values()
ACTION_PRECONDITIONS: Dict[str, str] = dict(ACTION_REQUIRED_STATE)
