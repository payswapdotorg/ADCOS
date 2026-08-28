"""ADCOS upgrade / rollback / compatibility error model (WORK-029).

Leaf module: imported by every other ``upgrade`` submodule, imports
nothing from the package (no import cycles).  :class:`UpgradeError` is
the fail-closed caller-input/state error raised for every rejected
operation.  Every rejection carries a frozen reason code and a
human-readable detail; there is no silent fallback anywhere in the
family.

The upgrade family is a COMPATIBILITY-ORCHESTRATION layer, not a new
authority (architecture-lock section 3/5): protocol version semantics
stay WORK-003 (``protocol/`` + ``spec/schemas/protocol.json`` are the
single source of truth, consumed read-only), capability negotiation
semantics stay WORK-005 (``capabilities/`` -- the family DELEGATES to
its ``negotiate()``, never re-implements it), adapter health and
observations stay WORK-016/W026 (``telemetry/`` -- gate evidence is
real telemetry DATA, consumed read-only), and upgrade state is
node-local lifecycle state (spec/architecture.md 5.6 "upgrade state"),
never topology, session, routing, or policy state.

The reason-code vocabulary is frozen: adding a code is a deliberate
vocabulary change, never a silent extension.
"""

from __future__ import annotations

#: Canonical upgrade family prefix.  Uses its own ``upgrade`` root
#: namespace (WORK-029 family convention), structurally disjoint from
#: the WORK-004 NodeID prefix ``adcos:node:``, the WORK-026 telemetry
#: prefixes ``telemetry:...``, the WORK-027 ``energy`` namespace, and
#: the sibling family prefixes by construction.
UPGRADE_PREFIX = "upgrade"


class UpgradeReasonCode:
    """Frozen reason-code vocabulary (upgrade / rollback / compatibility).

    Adding a code is a deliberate vocabulary change, never a silent
    extension.
    """

    INVALID_INPUT = "invalid-input"
    VERSION_MALFORMED = "version-malformed"
    VERSION_KIND_CONFLATED = "version-kind-conflated"
    MAJOR_UNKNOWN = "major-unknown"
    MAJOR_MISMATCH = "major-mismatch"
    NO_COMMON_PROFILE = "no-common-profile"
    MIGRATION_PATH_UNKNOWN = "migration-path-unknown"
    MIGRATION_NOT_REVERSIBLE = "migration-not-reversible"
    MIGRATION_INVALID_STEP = "migration-invalid-step"
    MIGRATION_DUPLICATE_EDGE = "migration-duplicate-edge"
    PLAN_INVALID = "plan-invalid"
    PLAN_VERSION_MISMATCH = "plan-version-mismatch"
    NOT_AN_UPGRADE = "not-an-upgrade"
    FLOOR_VIOLATION = "floor-violation"
    DOWNGRADE_BLOCKED = "downgrade-blocked"
    WRONG_STAGE = "wrong-stage"
    GATE_NOT_PASSED = "gate-not-passed"
    GATE_INSUFFICIENT_EVIDENCE = "gate-insufficient-evidence"
    ROLLBACK_WINDOW_CLOSED = "rollback-window-closed"
    POPULATION_MISMATCH = "population-mismatch"
    ACTIVE_PLAN_EXISTS = "active-plan-exists"

    ALL_VALUES = frozenset(
        {
            INVALID_INPUT,
            VERSION_MALFORMED,
            VERSION_KIND_CONFLATED,
            MAJOR_UNKNOWN,
            MAJOR_MISMATCH,
            NO_COMMON_PROFILE,
            MIGRATION_PATH_UNKNOWN,
            MIGRATION_NOT_REVERSIBLE,
            MIGRATION_INVALID_STEP,
            MIGRATION_DUPLICATE_EDGE,
            PLAN_INVALID,
            PLAN_VERSION_MISMATCH,
            NOT_AN_UPGRADE,
            FLOOR_VIOLATION,
            DOWNGRADE_BLOCKED,
            WRONG_STAGE,
            GATE_NOT_PASSED,
            GATE_INSUFFICIENT_EVIDENCE,
            ROLLBACK_WINDOW_CLOSED,
            POPULATION_MISMATCH,
            ACTIVE_PLAN_EXISTS,
        }
    )


class UpgradeError(ValueError):
    """Fail-closed error for rejected upgrade/compatibility operations.

    Attributes:
        reason: One frozen :class:`UpgradeReasonCode` value.
        detail: Human-readable, deterministic detail text.
    """

    def __init__(self, reason: str, detail: str) -> None:
        if reason not in UpgradeReasonCode.ALL_VALUES:
            raise AssertionError("unknown upgrade reason code: %r" % (reason,))
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail
