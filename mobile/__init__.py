"""WORK-035: the Android/mobile participation agent.

A mobile device participates in ADCOS through this layer: it owns
exactly one WORK-033 ``AgentRuntime`` (composed, never re-implemented)
and adds what a mobile node needs ON TOP of it -- OS lifecycle
adaptation (foreground/background/stopped as explicit platform
inputs), user-controlled resource sharing (consent grants as user
INPUT, not authority), session continuity across access changes and
offline periods (the sacred access-independent ``session_id`` is
preserved; handover re-binds through the ordinary WORK-033 binding
path over the WORK-016 adapter and WORK-018 IP surfaces), a
continuity view over the frozen WORK-013 path-status vocabulary, and
local discovery behind the host-provided port.  It runs headless:
driven entirely by data (configuration + command batches + platform
observations), with injected time.

Platform/vendor APIs stay behind the ``mobile.platform`` and
``mobile.discovery`` seams; no second identity, session, routing,
multipath, or policy authority exists in this family.
"""

from .errors import MobileError, MobileReasonCode
from .model import (
    AccessPathView,
    DeferReason,
    GrantScope,
    MobileEvent,
    MobileEventType,
    MobileOutcome,
    MobilePhase,
    MobileRunResult,
    MobileSnapshot,
    MobileVerdict,
    NetworkKind,
    ParticipationDecision,
    PlatformSnapshot,
    PowerState,
    ShedReason,
    UserGrant,
    derive_mobile_event_id,
    mobile_event_list_digest,
    mobile_events_canonical_bytes,
)
from .platform import (
    MOBILE_EVIDENCE_STATUS,
    FailingPlatformSource,
    MobilePlatformSource,
    ScriptedPlatformSource,
    StaticPlatformSource,
)
from .lifecycle import (
    PHASE_TRANSITIONS,
    grant_active,
    participation_gate,
    transition_is_legal,
)
from .discovery import (
    DiscoveryCycle,
    LocalDiscoveryPort,
    NullDiscovery,
    PeerObservation,
)
from .participation import (
    MobileAgent,
    MobileBudget,
    MobileCommand,
    MobileCommandKind,
    derive_mobile_command_id,
    run_mobile_headless,
    verify_mobile_replay,
)

__all__ = [
    # errors
    "MobileError",
    "MobileReasonCode",
    # vocabularies and value records
    "AccessPathView",
    "DeferReason",
    "GrantScope",
    "MobileEvent",
    "MobileEventType",
    "MobileOutcome",
    "MobilePhase",
    "MobileRunResult",
    "MobileSnapshot",
    "MobileVerdict",
    "NetworkKind",
    "ParticipationDecision",
    "PlatformSnapshot",
    "PowerState",
    "ShedReason",
    "UserGrant",
    "derive_mobile_event_id",
    "mobile_event_list_digest",
    "mobile_events_canonical_bytes",
    # platform boundary
    "MOBILE_EVIDENCE_STATUS",
    "FailingPlatformSource",
    "MobilePlatformSource",
    "ScriptedPlatformSource",
    "StaticPlatformSource",
    # lifecycle
    "PHASE_TRANSITIONS",
    "grant_active",
    "participation_gate",
    "transition_is_legal",
    # local discovery boundary
    "DiscoveryCycle",
    "LocalDiscoveryPort",
    "NullDiscovery",
    "PeerObservation",
    # the composition
    "MobileAgent",
    "MobileBudget",
    "MobileCommand",
    "MobileCommandKind",
    "derive_mobile_command_id",
    "run_mobile_headless",
    "verify_mobile_replay",
]
