"""WORK-033: the Linux reference agent.

A general-purpose computer participates in ADCOS through this runtime:
it owns isolated instances of the accepted authorities, exposes the
host's network interfaces as WORK-016 adapters, establishes and
monitors WORK-012 sessions over WORK-017 secure transport with WORK-018
IP integration, records logs and metrics through the WORK-026 store,
negotiates versions through WORK-029, exposes privileged operations
through the WORK-030 API, and self-verifies against the WORK-032
conformance suite.  It runs headless: driven entirely by data
(configuration + command batches), with injected time.
"""

from .errors import AgentError, AgentReasonCode
from .model import (
    AgentCommand,
    AgentConfig,
    AgentEvent,
    AgentEventType,
    AgentIdentitySpec,
    AgentRunResult,
    AgentStatus,
    CommandKind,
    CommandOutcome,
    CommandVerdict,
    DatagramArtifact,
    InterfaceSnapshot,
    LinkMetricSpec,
    MigrationSpec,
    MonitoringReport,
    MutationRecord,
    SessionAcceptArtifact,
    SessionConfirmArtifact,
    SessionRequestArtifact,
    agent_events_canonical_bytes,
    derive_agent_event_id,
    derive_command_id,
)
from .clock import AgentClock, FixedClock, StepClock, SystemClock, add_seconds, format_instant, parse_utc
from .interfaces import (
    FailingInterfaceSource,
    InterfaceSource,
    LinuxInterfaceSource,
    StaticInterfaceSource,
)
from .bridge import (
    INTERFACE_CAPABILITIES,
    InterfaceTechnologyAdapter,
    STEP_CHARGES,
    TECHNOLOGY_FOR_KIND,
    interface_descriptor,
    technology_for_snapshot,
)
from .runtime import (
    AgentRuntime,
    IP_INTEGRATION_ID,
    run_headless,
    verify_agent_replay,
)

__all__ = [
    "AgentError",
    "AgentReasonCode",
    "AgentCommand",
    "AgentConfig",
    "AgentEvent",
    "AgentEventType",
    "AgentIdentitySpec",
    "AgentRunResult",
    "AgentStatus",
    "CommandKind",
    "CommandOutcome",
    "CommandVerdict",
    "DatagramArtifact",
    "InterfaceSnapshot",
    "LinkMetricSpec",
    "MigrationSpec",
    "MonitoringReport",
    "MutationRecord",
    "SessionAcceptArtifact",
    "SessionConfirmArtifact",
    "SessionRequestArtifact",
    "agent_events_canonical_bytes",
    "derive_agent_event_id",
    "derive_command_id",
    "AgentClock",
    "FixedClock",
    "StepClock",
    "SystemClock",
    "add_seconds",
    "format_instant",
    "parse_utc",
    "FailingInterfaceSource",
    "InterfaceSource",
    "LinuxInterfaceSource",
    "StaticInterfaceSource",
    "INTERFACE_CAPABILITIES",
    "InterfaceTechnologyAdapter",
    "STEP_CHARGES",
    "TECHNOLOGY_FOR_KIND",
    "interface_descriptor",
    "technology_for_snapshot",
    "AgentRuntime",
    "IP_INTEGRATION_ID",
    "run_headless",
    "verify_agent_replay",
]
