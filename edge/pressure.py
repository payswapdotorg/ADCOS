"""WORK-034 deterministic resource-pressure model.

CPU / memory / storage pressure on a Pi-class node, modeled the way
the repository models every resource: deterministic integer
accounting over injected data, never wall-clock measurement (the
WORK-016 ``STEP_CHARGES`` hang-model precedent, applied at the agent
command layer).

Three domains, one ladder:

- **cpu** -- a per-epoch step budget (``cpu_steps_per_epoch``); every
  executed command is charged its frozen ``COMMAND_CPU_CHARGES``
  cost.  Epochs are explicit (one ``run_edge`` batch); the budget
  replenishes at each epoch boundary, so pressure is a scheduling
  input, not a leak.
- **memory** -- a cumulative modeled-usage ledger.  Every executed
  command charges its frozen ``COMMAND_MEMORY_ESTIMATE_BYTES``
  estimate (a MODEL, labeled as one everywhere it surfaces);
  deployment-level reclamation is an explicit ``reclaim_memory``
  operation.
- **storage** -- a cumulative journal-growth ledger charged per
  executed command; compaction is an explicit
  ``compact_storage`` operation.

The charge tables are frozen DATA keyed by the WORK-033 command-kind
VALUES (strings; the battery cross-checks completeness against
``agent.CommandKind``).  Utilization is integer basis points
(``used * 10000 // capacity``), classified on the frozen
nominal/pressured/critical ladder by the classic 70/90 operational
watermarks (DATA).
"""

from __future__ import annotations

from typing import Dict, Tuple

from .errors import EdgeError, EdgeReasonCode
from .hardware import HardwareInventory
from .model import PressureDomain, PressureLevel, PressureReading

#: The frozen pressure watermarks in basis points (the classic 70/90
#: operational-watermark convention, carried as DATA).
PRESSURE_THRESHOLDS_BASIS_POINTS = {
    "pressured_min_bp": 7000,
    "critical_min_bp": 9000,
}

#: Frozen CPU step charges per WORK-033 command kind (the WORK-016
#: ``STEP_CHARGES`` discipline at the agent command layer: units are
#: deterministic accounting steps, never wall-clock milliseconds).
COMMAND_CPU_CHARGES: Dict[str, int] = {
    "boot": 8,
    "expose-interfaces": 6,
    "register-peer": 1,
    "monitor": 4,
    "send-datagram": 3,
    "receive-datagram": 3,
    "suspend-session": 4,
    "terminate-session": 5,
    "negotiate-peer": 6,
    "self-test": 20,
    "shutdown": 4,
}

#: Frozen MODELED memory-allocation estimates per command kind, in
#: bytes.  These are engineering models of the dominant allocations
#: (authority construction, batch bookkeeping, conformance matrix),
#: labeled MODELED wherever they surface -- they are not
#: measurements, and they never masquerade as telemetry observations
#: of the host process.
COMMAND_MEMORY_ESTIMATE_BYTES: Dict[str, int] = {
    "boot": 32768,
    "expose-interfaces": 16384,
    "register-peer": 4096,
    "monitor": 8192,
    "send-datagram": 4096,
    "receive-datagram": 4096,
    "suspend-session": 2048,
    "terminate-session": 2048,
    "negotiate-peer": 8192,
    "self-test": 131072,
    "shutdown": 2048,
}

#: Frozen MODELED journal-growth estimates per executed command, in
#: bytes (the agent event log + mutation records the command
#: appends).
COMMAND_STORAGE_ESTIMATE_BYTES: Dict[str, int] = {
    "boot": 1024,
    "expose-interfaces": 1024,
    "register-peer": 512,
    "monitor": 512,
    "send-datagram": 256,
    "receive-datagram": 256,
    "suspend-session": 256,
    "terminate-session": 256,
    "negotiate-peer": 512,
    "self-test": 2048,
    "shutdown": 256,
}

_MIB = 1024 * 1024


def command_cpu_charge(kind: str) -> int:
    """The frozen CPU step charge for a command kind (unknown kinds
    fail closed to the maximum observed charge -- a new command kind
    without a table entry is a pressure hazard, never a free
    ride)."""
    return COMMAND_CPU_CHARGES.get(kind, 20)


def command_memory_estimate(kind: str) -> int:
    """The frozen MODELED memory estimate for a command kind."""
    return COMMAND_MEMORY_ESTIMATE_BYTES.get(kind, 32768)


def command_storage_estimate(kind: str) -> int:
    """The frozen MODELED journal-growth estimate for a command
    kind."""
    return COMMAND_STORAGE_ESTIMATE_BYTES.get(kind, 1024)


def pressure_level(
    utilization_bp: int,
    thresholds: Dict[str, int] = PRESSURE_THRESHOLDS_BASIS_POINTS,
) -> str:
    """Classify utilization (basis points) on the frozen ladder."""
    if isinstance(utilization_bp, bool) or not isinstance(utilization_bp, int):
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "utilization must be an integer (got %s)"
            % (type(utilization_bp).__name__,),
        )
    if utilization_bp < 0:
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "utilization must be non-negative (got %d)" % (utilization_bp,),
        )
    if utilization_bp >= thresholds["critical_min_bp"]:
        return PressureLevel.CRITICAL
    if utilization_bp >= thresholds["pressured_min_bp"]:
        return PressureLevel.PRESSURED
    return PressureLevel.NOMINAL


class ResourceBudget:
    """The frozen scheduling-budget envelope (deployment DATA)."""

    __slots__ = (
        "cpu_steps_per_epoch", "max_deferred_depth", "deferred_ttl_seconds",
    )

    def __init__(
        self,
        *,
        cpu_steps_per_epoch: int = 10000,
        max_deferred_depth: int = 32,
        deferred_ttl_seconds: int = 3600,
    ) -> None:
        for name, value in (
            ("cpu_steps_per_epoch", cpu_steps_per_epoch),
            ("max_deferred_depth", max_deferred_depth),
            ("deferred_ttl_seconds", deferred_ttl_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise EdgeError(
                    EdgeReasonCode.BUDGET_INVALID,
                    "%s must be an integer (got %s)"
                    % (name, type(value).__name__),
                )
            if value < 1:
                raise EdgeError(
                    EdgeReasonCode.BUDGET_INVALID,
                    "%s must be >= 1 (got %d)" % (name, value),
                )
        self.cpu_steps_per_epoch = cpu_steps_per_epoch
        self.max_deferred_depth = max_deferred_depth
        self.deferred_ttl_seconds = deferred_ttl_seconds

    def to_dict(self) -> dict:
        return {
            "cpu_steps_per_epoch": self.cpu_steps_per_epoch,
            "max_deferred_depth": self.max_deferred_depth,
            "deferred_ttl_seconds": self.deferred_ttl_seconds,
        }


class PressureLedger:
    """The deterministic pressure accounting ledger (mutable,
    data-driven; integer math only).

    The ledger holds MODELED counts.  CPU usage resets at each
    scheduling epoch (an explicit ``replenish_epoch``); memory and
    storage are cumulative with explicit reclamation/compaction.
    """

    __slots__ = ("cpu_steps_used", "memory_used_bytes", "storage_used_bytes")

    def __init__(self) -> None:
        self.cpu_steps_used = 0
        self.memory_used_bytes = 0
        self.storage_used_bytes = 0

    def charge_cpu(self, steps: int) -> None:
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
            raise EdgeError(
                EdgeReasonCode.BUDGET_INVALID,
                "cpu charge must be a non-negative integer",
            )
        self.cpu_steps_used += steps

    def charge_memory(self, size_bytes: int) -> None:
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) \
                or size_bytes < 0:
            raise EdgeError(
                EdgeReasonCode.BUDGET_INVALID,
                "memory charge must be a non-negative integer",
            )
        self.memory_used_bytes += size_bytes

    def charge_storage(self, size_bytes: int) -> None:
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) \
                or size_bytes < 0:
            raise EdgeError(
                EdgeReasonCode.BUDGET_INVALID,
                "storage charge must be a non-negative integer",
            )
        self.storage_used_bytes += size_bytes

    def reclaim_memory(self, size_bytes: int) -> int:
        """Reclaim modeled memory (deployment-level release); returns
        the amount actually reclaimed (clamped at zero floor)."""
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) \
                or size_bytes < 0:
            raise EdgeError(
                EdgeReasonCode.BUDGET_INVALID,
                "memory reclaim must be a non-negative integer",
            )
        reclaimed = min(size_bytes, self.memory_used_bytes)
        self.memory_used_bytes -= reclaimed
        return reclaimed

    def compact_storage(self, size_bytes: int) -> int:
        """Compact modeled journal growth; returns the bytes actually
        released."""
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) \
                or size_bytes < 0:
            raise EdgeError(
                EdgeReasonCode.BUDGET_INVALID,
                "storage compaction must be a non-negative integer",
            )
        released = min(size_bytes, self.storage_used_bytes)
        self.storage_used_bytes -= released
        return released

    def replenish_epoch(self) -> None:
        """Start a new scheduling epoch: the CPU step counter resets
        (memory/storage stay cumulative)."""
        self.cpu_steps_used = 0

    def to_dict(self) -> dict:
        return {
            "cpu_steps_used": self.cpu_steps_used,
            "memory_used_bytes": self.memory_used_bytes,
            "storage_used_bytes": self.storage_used_bytes,
        }


def _utilization_bp(used: int, capacity: int) -> int:
    """Integer basis-point utilization, clamped at the ceiling (the
    ledger keeps raw counts; readings never exceed 10000 bp)."""
    if capacity <= 0:
        return 10000 if used > 0 else 0
    value = (used * 10000) // capacity
    if value > 10000:
        return 10000
    return value


def compute_pressure(
    inventory: HardwareInventory, ledger: PressureLedger,
    budget: ResourceBudget,
) -> Tuple[PressureReading, ...]:
    """Compute the three-domain pressure readings from the current
    inventory, ledger, and epoch budget (pure, deterministic).

    CPU capacity is the deployment's epoch envelope
    (``budget.cpu_steps_per_epoch``): a smaller board is provisioned
    with a smaller epoch budget -- the constrained-envelope choice
    is deployment DATA, not hidden scaling.  Memory and storage
    capacities come from the hardware inventory."""
    if not isinstance(inventory, HardwareInventory):
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "pressure computation requires a genuine HardwareInventory",
        )
    if not isinstance(ledger, PressureLedger):
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "pressure computation requires a genuine PressureLedger",
        )
    if not isinstance(budget, ResourceBudget):
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "pressure computation requires a genuine ResourceBudget",
        )
    cpu_capacity = budget.cpu_steps_per_epoch
    cpu_bp = _utilization_bp(ledger.cpu_steps_used, cpu_capacity)
    memory_capacity = inventory.memory_available_mib * _MIB
    memory_bp = _utilization_bp(ledger.memory_used_bytes, memory_capacity)
    storage_capacity = inventory.storage_available_mib * _MIB
    storage_bp = _utilization_bp(ledger.storage_used_bytes, storage_capacity)
    readings: Tuple[PressureReading, ...] = (
        PressureReading(
            domain=PressureDomain.CPU,
            used=ledger.cpu_steps_used,
            capacity=cpu_capacity,
            utilization_bp=cpu_bp,
            level=pressure_level(cpu_bp),
        ),
        PressureReading(
            domain=PressureDomain.MEMORY,
            used=ledger.memory_used_bytes,
            capacity=memory_capacity,
            utilization_bp=memory_bp,
            level=pressure_level(memory_bp),
        ),
        PressureReading(
            domain=PressureDomain.STORAGE,
            used=ledger.storage_used_bytes,
            capacity=storage_capacity,
            utilization_bp=storage_bp,
            level=pressure_level(storage_bp),
        ),
    )
    return readings


__all__ = [
    "PRESSURE_THRESHOLDS_BASIS_POINTS",
    "COMMAND_CPU_CHARGES",
    "COMMAND_MEMORY_ESTIMATE_BYTES",
    "COMMAND_STORAGE_ESTIMATE_BYTES",
    "command_cpu_charge",
    "command_memory_estimate",
    "command_storage_estimate",
    "pressure_level",
    "ResourceBudget",
    "PressureLedger",
    "compute_pressure",
]
