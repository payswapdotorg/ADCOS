"""WORK-034: the Raspberry Pi / low-power edge gateway layer.

A Pi-class node participates in ADCOS as infrastructure through this
layer: the accepted WORK-033 Linux Agent runs UNCHANGED underneath,
and the edge layer adds what constrained edge hardware needs --

- **hardware abstraction** -- frozen Pi-class board profiles plus a
  read-only Linux hardware-capability source (``edge.hardware``);
- **resource-aware operation** -- the deterministic CPU / memory /
  storage pressure model and the protected/essential/bulk command
  scheduler with typed deferral and shedding (``edge.pressure``,
  ``edge.scheduler``);
- **Ethernet/Wi-Fi/cellular coexistence** -- access classification,
  deterministic selection, and the connected/degraded/offline
  posture over the agent's own live adapters (``edge.coexistence``);
- **gateway/relay behavior** -- the evidence-scoped gateway-claim
  table and forwarding through ordinary sessions, reusing the
  WORK-023 evidence and relay vocabularies as DATA
  (``edge.gateway``);
- **offline/degraded operation** -- bounded, TTL'd deferred relay
  that drains when an access path returns.

Composition, not re-implementation: no protocol semantic changes, no
second authority, no access-technology duplication, and the
physical-hardware evidence track stays explicitly OPEN (the
``HARDWARE_EVIDENCE_STATUS`` disclosure).
"""

from .errors import EdgeError, EdgeReasonCode
from .model import (
    CommandPriority,
    ConnectivityPosture,
    EdgeEvent,
    EdgeEventType,
    EdgeOutcome,
    EdgeRunResult,
    ForwardRecord,
    PRESSURE_LEVEL_ORDINALS,
    PressureDomain,
    PressureLevel,
    PressureReading,
    SchedulerDecision,
    SchedulingVerdict,
    derive_edge_event_id,
    edge_event_list_digest,
    edge_events_canonical_bytes,
    worse_pressure_level,
)
from .hardware import (
    BoardProfile,
    EDGE_BOARD_PROFILES,
    FailingHardwareSource,
    HARDWARE_EVIDENCE_STATUS,
    HardwareInventory,
    HardwareInventorySource,
    LinuxHardwareSource,
    StaticHardwareSource,
    board_for,
)
from .pressure import (
    COMMAND_CPU_CHARGES,
    COMMAND_MEMORY_ESTIMATE_BYTES,
    COMMAND_STORAGE_ESTIMATE_BYTES,
    PRESSURE_THRESHOLDS_BASIS_POINTS,
    PressureLedger,
    ResourceBudget,
    command_cpu_charge,
    command_memory_estimate,
    command_storage_estimate,
    compute_pressure,
    pressure_level,
)
from .scheduler import (
    ADMISSION_BY_LEVEL,
    OFFLINE_DEFERRED_KINDS,
    PRIORITY_FOR_KIND,
    decide_command,
    priority_for_kind,
)
from .coexistence import (
    COEXISTENCE_PREFERENCE,
    TECHNOLOGY_ACCESS_CLASS,
    AccessClass,
    AccessView,
    build_access_views,
    classify_access,
    connectivity_posture,
    select_access,
    validate_access_plan,
)
from .gateway import (
    FORWARD_EVIDENCE_REQUIREMENT,
    PRESSURE_PROVENANCE,
    ClaimLookup,
    EdgeGateway,
    GatewayClaim,
    GatewayTable,
    run_edge_headless,
    verify_edge_replay,
)

__all__ = [
    # errors
    "EdgeError",
    "EdgeReasonCode",
    # model
    "CommandPriority",
    "ConnectivityPosture",
    "EdgeEvent",
    "EdgeEventType",
    "EdgeOutcome",
    "EdgeRunResult",
    "ForwardRecord",
    "PRESSURE_LEVEL_ORDINALS",
    "PressureDomain",
    "PressureLevel",
    "PressureReading",
    "SchedulerDecision",
    "SchedulingVerdict",
    "derive_edge_event_id",
    "edge_event_list_digest",
    "edge_events_canonical_bytes",
    "worse_pressure_level",
    # hardware
    "BoardProfile",
    "EDGE_BOARD_PROFILES",
    "FailingHardwareSource",
    "HARDWARE_EVIDENCE_STATUS",
    "HardwareInventory",
    "HardwareInventorySource",
    "LinuxHardwareSource",
    "StaticHardwareSource",
    "board_for",
    # pressure
    "COMMAND_CPU_CHARGES",
    "COMMAND_MEMORY_ESTIMATE_BYTES",
    "COMMAND_STORAGE_ESTIMATE_BYTES",
    "PRESSURE_THRESHOLDS_BASIS_POINTS",
    "PressureLedger",
    "ResourceBudget",
    "command_cpu_charge",
    "command_memory_estimate",
    "command_storage_estimate",
    "compute_pressure",
    "pressure_level",
    # scheduler
    "ADMISSION_BY_LEVEL",
    "OFFLINE_DEFERRED_KINDS",
    "PRIORITY_FOR_KIND",
    "decide_command",
    "priority_for_kind",
    # coexistence
    "COEXISTENCE_PREFERENCE",
    "TECHNOLOGY_ACCESS_CLASS",
    "AccessClass",
    "AccessView",
    "build_access_views",
    "classify_access",
    "connectivity_posture",
    "select_access",
    "validate_access_plan",
    # gateway
    "FORWARD_EVIDENCE_REQUIREMENT",
    "PRESSURE_PROVENANCE",
    "ClaimLookup",
    "EdgeGateway",
    "GatewayClaim",
    "GatewayTable",
    "run_edge_headless",
    "verify_edge_replay",
]
