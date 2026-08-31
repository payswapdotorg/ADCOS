"""WORK-041 authority-mediated binding and traffic probe.

Binding drives the EXISTING production seams -- never a parallel one:

- :func:`bind_candidate` calls the ordinary WORK-033
  ``AgentRuntime.bind_session`` path (adapter binding + WORK-018 IP
  integration binding), which is exactly the mechanism the WORK-040
  correction exercised for dynamic interface exposure and handover.
  The NetworkPath family therefore creates NO
  second binding authority: the adapter runtime owns the bearer, the
  IP integration owns the flow binding, and this module only RECORDS
  the resulting facts.
- :func:`probe_candidate` sends one deterministic datagram through the
  ordinary WORK-017 transport path (``AgentRuntime.send_datagram``).
  The payload is content-derived from public identity DATA (session
  id + path id + probe sequence): no randomness, no wall clock, no
  secrets.

Both functions wrap ``AgentError`` into the typed NetworkPath
vocabulary (fail-closed isolation: an agent-family failure never
crosses the composition boundary untyped), and neither mutates any
authority state beyond what the ordinary runtime path itself does.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from protocol.canonicalization import canonical_json_bytes

from agent.errors import AgentError
from agent.runtime import AgentRuntime

from .errors import NetworkPathError, NetworkPathReasonCode
from .model import NetworkPath
from .state import NetworkPathState


@dataclass(frozen=True)
class BindingFacts:
    """The recorded outputs of one legitimate session binding.

    Facts only: the adapter runtime and IP integration remain the
    owners of this state.  Serialized as DATA for evidence records.
    """

    adapter_id: str
    binding_id: str
    bearer_ref: str
    ip_binding_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "binding_id": self.binding_id,
            "bearer_ref": self.bearer_ref,
            "ip_binding_id": self.ip_binding_id,
        }


@dataclass(frozen=True)
class ProbeFacts:
    """The recorded outputs of one traffic probe (traffic proof)."""

    probe_sequence: int
    payload_digest: str
    frame_digest: str
    transport_id: str
    artifact_session_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_sequence": self.probe_sequence,
            "payload_digest": self.payload_digest,
            "frame_digest": self.frame_digest,
            "transport_id": self.transport_id,
            "artifact_session_id": self.artifact_session_id,
        }


def bind_candidate(
    runtime: AgentRuntime, session_id: str, path: NetworkPath
) -> BindingFacts:
    """Bind an established session to the candidate's interface.

    Delegates to ``AgentRuntime.bind_session(session_id,
    interface_name=...)`` -- the ordinary WORK-033 binding path
    (adapter + IP integration).  Any rejection surfaces as the typed
    ``BIND_REJECTED`` NetworkPath error with the agent family's
    deterministic detail.
    """
    _require_runtime(runtime)
    if not isinstance(session_id, str) or not session_id:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "session_id must be a non-empty string (the existing session "
            "authority owns it)",
        )
    if not isinstance(path, NetworkPath):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT, "path must be a NetworkPath"
        )
    try:
        result = runtime.bind_session(session_id, interface_name=path.interface_name)
    except AgentError as error:
        raise NetworkPathError(
            NetworkPathReasonCode.BIND_REJECTED,
            "runtime binding rejected for interface %r: %s"
            % (path.interface_name, error.detail or error.reason),
        ) from error
    return BindingFacts(
        adapter_id=str(result.get("adapter_id", "")),
        binding_id=str(result.get("binding_id", "")),
        bearer_ref=str(result.get("bearer_ref", "")),
        ip_binding_id=str(result.get("ip_binding_id", "")),
    )


def probe_payload(session_id: str, network_path_id: str, probe_sequence: int) -> bytes:
    """The deterministic probe payload (content-derived, no secrets).

    Derived from public identity DATA only: the session id, the path
    fingerprint, and the probe sequence number.  Identical logical
    inputs produce identical payload bytes (replay determinism).
    """
    content = {
        "probe": "networkpath",
        "session_id": session_id,
        "network_path_id": network_path_id,
        "probe_sequence": probe_sequence,
    }
    digest = hashlib.sha256(canonical_json_bytes(content)).hexdigest()
    return digest.encode("ascii")


def probe_candidate(
    runtime: AgentRuntime,
    session_id: str,
    network_path_id: str,
    probe_sequence: int,
) -> ProbeFacts:
    """Send one deterministic probe datagram through the real transport.

    The probe proves traffic can flow for the bound session at the
    moment of probing (the protected frame + its transport id are
    recorded as digests).  Rejections surface as the typed
    ``PROBE_REJECTED`` error.
    """
    _require_runtime(runtime)
    if probe_sequence < 1:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "probe_sequence must be a positive integer (deterministic "
            "sequence, no randomness)",
        )
    payload = probe_payload(session_id, network_path_id, probe_sequence)
    try:
        artifact = runtime.send_datagram(session_id, payload)
    except AgentError as error:
        raise NetworkPathError(
            NetworkPathReasonCode.PROBE_REJECTED,
            "probe datagram rejected: %s" % (error.detail or error.reason),
        ) from error
    frame_digest = "sha256:" + hashlib.sha256(
        canonical_json_bytes(dict(artifact.frame))
    ).hexdigest()
    payload_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return ProbeFacts(
        probe_sequence=probe_sequence,
        payload_digest=payload_digest,
        frame_digest=frame_digest,
        transport_id=artifact.transport_id,
        artifact_session_id=artifact.session_id,
    )


def _require_runtime(runtime: AgentRuntime) -> None:
    if not isinstance(runtime, AgentRuntime):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "runtime must be an AgentRuntime (the existing WORK-033 "
            "composition owner)",
        )


#: The state a candidate must be in when binding runs, and the state
#: probing requires (contract data; the lifecycle manager enforces).
BIND_REQUIRED_STATE = NetworkPathState.VALIDATED
PROBE_REQUIRED_STATE = NetworkPathState.BOUND
