"""ADCOS upgrade / rollback / compatibility family (WORK-029).

Upgrade, rollback, and compatibility management: protocol-profile
negotiation for mixed-version coexistence (fail closed on
incompatible majors, per the WORK-003 artifact), reversible schema
migrations over versioned persisted state, the node-local staged
upgrade ladder (PLANNED -> PREPARED -> CANARY -> ROLLING ->
COMMITTED with honest terminal exits), health gates over REAL
WORK-026 telemetry evidence, downgrade protection (the
minimum-version floor ratchet), and deterministic rolling upgrades
across a node population with canary discipline.

The family is a COMPATIBILITY-ORCHESTRATION layer, not a new
authority:

- protocol version semantics stay WORK-003 (``protocol/`` and
  ``spec/schemas/protocol.json`` are the single source of truth,
  consumed read-only);
- capability negotiation stays WORK-005 (mixed-version capability
  interop is DELEGATED to ``capabilities.negotiation``);
- adapter health and observations stay WORK-016/W026 (gate evidence
  is real telemetry DATA, consumed read-only);
- upgrade state is node-local lifecycle state (spec/architecture.md
  5.6), never topology, session, routing, policy, or identity state;
- the four governance version kinds (Architecture, Protocol, Schema,
  Implementation) are never conflated: the model enforces the
  separation structurally, and the Architecture Version is not a
  dimension of this family at all.
"""

from .errors import UpgradeError, UpgradeReasonCode
from .model import (
    EventKind,
    GateVerdict,
    HealthGateResult,
    HealthGateSpec,
    MigrationDescriptor,
    ProtocolProfile,
    SoftwareVersion,
    UpgradeEvent,
    UpgradePlan,
    UpgradeStage,
    VersionInventory,
    VersionKind,
    derive_event_id,
    derive_inventory_id,
    derive_migration_id,
    derive_plan_id,
    event_ledger_digest,
)

__all__ = [
    "UpgradeError",
    "UpgradeReasonCode",
    "EventKind",
    "GateVerdict",
    "HealthGateResult",
    "HealthGateSpec",
    "MigrationDescriptor",
    "ProtocolProfile",
    "SoftwareVersion",
    "UpgradeEvent",
    "UpgradePlan",
    "UpgradeStage",
    "VersionInventory",
    "VersionKind",
    "derive_event_id",
    "derive_inventory_id",
    "derive_migration_id",
    "derive_plan_id",
    "event_ledger_digest",
]
