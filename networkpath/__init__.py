"""ADCOS NetworkPath package (WORK-041): first-class network path
and platform integration.

Implements the accepted ACR-005 boundary (DEC-0047) under the active
authorization ``WORK-041-CORE-001`` (DEC-0052): a technology-neutral
NetworkPath representation over existing authority-owned state, with
platform observation kept separate from ADCOS protocol state and path
detection / validation / binding / activation / retirement kept as
explicitly separated lifecycle steps.

Frozen authority boundary (mirrors the mobile-family discipline):

- NetworkPath is NOT an identity authority (WORK-004 owns identity);
  its ``network_path_id`` is a content-derived fingerprint, never a
  NodeID and never trust.
- NetworkPath is NOT a session authority (WORK-012 owns logical
  session lifecycle); a physical path change is never a logical
  session replacement (``session_id`` is stable across validated
  handover).
- NetworkPath is NOT a routing engine (WORK-011 owns route
  decisions); it exposes path facts only.
- NetworkPath is NOT a transport manager (WORK-017) and NOT an
  adapter authority (WORK-016); binding drives the ordinary
  ``AgentRuntime.bind_session`` path (the W040-corrected mechanism)
  and records the resulting facts.
- NetworkPath is NOT a policy authority (WORK-010), NOT a federation
  authority, and NOT a discovery authority (WORK-006/W033): interface
  discovery reuses the existing ``InterfaceSource`` seam.
- NetworkPath owns exactly one journal: the candidate-path lifecycle
  (discover/validate/bind/probe/activate/retire) with deterministic,
  replay-safe, independently verifiable evidence.

Determinism: injected WORK-033 clock seam only; content-derived ids
and digests (WORK-003 canonical JSON); sorted iteration; no
randomness, no UUIDs, no wall clock, no network access, no
platform/vendor API.
"""

from __future__ import annotations

from .errors import NetworkPathError, NetworkPathReasonCode
from .state import (
    ACTION_REQUIRED_STATE,
    LIFECYCLE_TRANSITIONS,
    NetworkPathAction,
    NetworkPathState,
    transition_is_legal,
)
from .model import (
    ACTION_PRECONDITIONS,
    ACTION_VALUES,
    LifecycleEvent,
    NetworkPath,
    PlatformObservation,
    STATE_VALUES,
    TRANSITION_TABLE,
    derive_network_path_event_id,
    derive_network_path_id,
    lifecycle_event_list_digest,
    network_path_identity_content,
)
from .observation import (
    candidate_from_observation,
    observation_for,
    read_observations,
)
from .validation import (
    FAILED_ADAPTER_HEALTH,
    REQUIRED_ADAPTER_LIFECYCLE,
    VALIDATION_REQUIRED_STATE,
    ValidationVerdict,
    validate_candidate,
)
from .binding import (
    BIND_REQUIRED_STATE,
    BindingFacts,
    ProbeFacts,
    PROBE_REQUIRED_STATE,
    bind_candidate,
    probe_candidate,
    probe_payload,
)
from .lifecycle import HandoverResult, NetworkPathManager
from .evidence import (
    NETWORKPATH_EVIDENCE_STATUS,
    PathEvidenceRecord,
    assemble_path_evidence,
    evidence_digest,
    event_journal_digest,
    verify_path_evidence,
)
from .integration import (
    SESSION_CREATED_EVENT_TYPE,
    SessionContinuityFacts,
    assert_session_continuity,
    session_continuity_facts,
)

__all__ = [
    # error model
    "NetworkPathError",
    "NetworkPathReasonCode",
    # lifecycle vocabulary
    "NetworkPathState",
    "NetworkPathAction",
    "LIFECYCLE_TRANSITIONS",
    "TRANSITION_TABLE",
    "ACTION_REQUIRED_STATE",
    "ACTION_PRECONDITIONS",
    "ACTION_VALUES",
    "STATE_VALUES",
    "transition_is_legal",
    # value model
    "NetworkPath",
    "PlatformObservation",
    "LifecycleEvent",
    "derive_network_path_id",
    "derive_network_path_event_id",
    "network_path_identity_content",
    "lifecycle_event_list_digest",
    # observation boundary
    "read_observations",
    "observation_for",
    "candidate_from_observation",
    # validation
    "ValidationVerdict",
    "validate_candidate",
    "VALIDATION_REQUIRED_STATE",
    "REQUIRED_ADAPTER_LIFECYCLE",
    "FAILED_ADAPTER_HEALTH",
    # binding + probe
    "BindingFacts",
    "ProbeFacts",
    "bind_candidate",
    "probe_candidate",
    "probe_payload",
    "BIND_REQUIRED_STATE",
    "PROBE_REQUIRED_STATE",
    # lifecycle manager (the public production surface)
    "NetworkPathManager",
    "HandoverResult",
    # evidence chain
    "NETWORKPATH_EVIDENCE_STATUS",
    "PathEvidenceRecord",
    "assemble_path_evidence",
    "evidence_digest",
    "event_journal_digest",
    "verify_path_evidence",
    # session continuity
    "SessionContinuityFacts",
    "session_continuity_facts",
    "assert_session_continuity",
    "SESSION_CREATED_EVENT_TYPE",
]
