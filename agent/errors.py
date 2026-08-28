"""WORK-033 agent error model.

The Linux reference agent is a composition root over accepted authority
implementations; it owns no protocol semantics of its own.  Errors here
describe agent-side composition faults (configuration, lifecycle,
interface discovery, command dispatch) with frozen reason codes and
deterministic, secret-free detail text.
"""

from __future__ import annotations

from typing import Tuple


class AgentReasonCode:
    """Frozen reason-code vocabulary for agent-side failures."""

    INVALID_INPUT = "invalid-input"
    NOT_BOOTED = "not-booted"
    ALREADY_BOOTED = "already-booted"
    ALREADY_SHUTDOWN = "already-shutdown"
    INTERFACE_INVALID = "interface-invalid"
    INTERFACE_SOURCE_FAILED = "interface-source-failed"
    ADAPTER_CONFLICT = "adapter-conflict"
    PEER_INVALID = "peer-invalid"
    POLICY_REJECTED = "policy-rejected"
    ROUTE_UNAVAILABLE = "route-unavailable"
    SESSION_REJECTED = "session-rejected"
    TRANSPORT_REJECTED = "transport-rejected"
    BINDING_REJECTED = "binding-rejected"
    COMMAND_REJECTED = "command-rejected"
    COMMAND_FAILED = "command-failed"
    MONITORING_FAILED = "monitoring-failed"
    NEGOTIATION_FAILED = "negotiation-failed"
    CONFORMANCE_FAILED = "conformance-failed"
    SERIALIZATION_INVALID = "serialization-invalid"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.NOT_BOOTED,
            cls.ALREADY_BOOTED,
            cls.ALREADY_SHUTDOWN,
            cls.INTERFACE_INVALID,
            cls.INTERFACE_SOURCE_FAILED,
            cls.ADAPTER_CONFLICT,
            cls.PEER_INVALID,
            cls.POLICY_REJECTED,
            cls.ROUTE_UNAVAILABLE,
            cls.SESSION_REJECTED,
            cls.TRANSPORT_REJECTED,
            cls.BINDING_REJECTED,
            cls.COMMAND_REJECTED,
            cls.COMMAND_FAILED,
            cls.MONITORING_FAILED,
            cls.NEGOTIATION_FAILED,
            cls.CONFORMANCE_FAILED,
            cls.SERIALIZATION_INVALID,
        )


class AgentError(ValueError):
    """Caller-side agent error with a frozen reason code.

    Adapter/transport/IP-integration side faults surface through their
    own typed failure values; ``AgentError`` is raised only for
    agent-side input and lifecycle violations, mirroring the
    ``AdapterError`` convention.
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail
