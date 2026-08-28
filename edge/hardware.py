"""WORK-034 Pi-class hardware abstraction.

Board profiles are DATA: the public product specifications of the
Raspberry Pi boards the frozen contract names (and one generic ARM64
edge profile), carried as frozen constants in the repository's
DATA-not-behavior discipline (the WORK-020 TR 38.901 constant
precedent).  They classify a deployment's capacity envelope; they are
never parsed into protocol behavior.

``LinuxHardwareSource`` reads the real ``/proc`` filesystem and the
filesystem statistics of a deployment-declared board through
``pathlib``/``shutil`` -- read-only, no privileges, the ONLY
filesystem-access site in the edge family (battery-audited, the
WORK-033 ``LinuxInterfaceSource`` precedent).  The board identity
itself is deployment configuration, not sniffing.

Anti-faking rule (the WORK-020 physical-SDR discipline applied to
hardware): ``HARDWARE_EVIDENCE_STATUS`` is frozen DATA recording that
software/constrained-environment evidence is SUPPORTED by this
repository's deterministic battery, while PHYSICAL Raspberry Pi
hardware evidence remains OPEN.  No code path in this family may
report a physical-hardware PASS; the battery asserts the OPEN status
byte-for-byte.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from shutil import disk_usage
from typing import Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import EdgeError, EdgeReasonCode

DEFAULT_PROC_MEMINFO = "/proc/meminfo"
DEFAULT_PROC_CPUINFO = "/proc/cpuinfo"

#: The frozen hardware-evidence disclosure (anti-faking; the WORK-020
#: physical-SDR precedent).  ``software-constrained`` evidence is the
#: deterministic, emulated constrained-environment verification this
#: battery produces; ``physical-hardware`` evidence requires a real
#: board and remains OPEN until one is available.  Flipping the second
#: value to anything other than "open" fails the battery.
HARDWARE_EVIDENCE_STATUS = {
    "software-constrained": "supported",
    "physical-hardware": "open",
}


@dataclass(frozen=True)
class BoardProfile:
    """One Pi-class board capacity profile (public product DATA)."""

    board_id: str
    arch: str
    cpu_cores: int
    memory_mib: int
    storage_mib: int
    description: str = ""

    def __post_init__(self) -> None:
        if not self.board_id or not isinstance(self.board_id, str):
            raise EdgeError(
                EdgeReasonCode.HARDWARE_INVALID,
                "board id must be a non-empty string",
            )
        if not self.arch or not isinstance(self.arch, str):
            raise EdgeError(
                EdgeReasonCode.HARDWARE_INVALID,
                "board arch must be a non-empty string",
            )
        for name in ("cpu_cores", "memory_mib", "storage_mib"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise EdgeError(
                    EdgeReasonCode.HARDWARE_INVALID,
                    "%s must be an integer (got %s)"
                    % (name, type(value).__name__),
                )
            if value < 1:
                raise EdgeError(
                    EdgeReasonCode.HARDWARE_INVALID,
                    "%s must be >= 1 (got %d)" % (name, value),
                )

    def to_dict(self) -> dict:
        return {
            "board_id": self.board_id,
            "arch": self.arch,
            "cpu_cores": self.cpu_cores,
            "memory_mib": self.memory_mib,
            "storage_mib": self.storage_mib,
            "description": self.description,
        }

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


#: The frozen board-profile registry (public product specifications as
#: DATA; raspberry-pi product briefs, carried without importing any
#: vendor tooling -- names only, per the vendor-token discipline).
EDGE_BOARD_PROFILES: Tuple[BoardProfile, ...] = (
    BoardProfile(
        board_id="raspberry-pi-5",
        arch="aarch64",
        cpu_cores=4,
        memory_mib=8192,
        storage_mib=65536,
        description="4x Cortex-A76 @ 2.4 GHz, 4/8 GiB LPDDR4X, SD storage",
    ),
    BoardProfile(
        board_id="raspberry-pi-4b",
        arch="aarch64",
        cpu_cores=4,
        memory_mib=4096,
        storage_mib=32768,
        description="4x Cortex-A72 @ 1.5 GHz, 2/4/8 GiB LPDDR4, SD storage",
    ),
    BoardProfile(
        board_id="raspberry-pi-3b",
        arch="aarch64",
        cpu_cores=4,
        memory_mib=1024,
        storage_mib=32768,
        description="4x Cortex-A53 @ 1.2 GHz, 1 GiB LPDDR2, SD storage",
    ),
    BoardProfile(
        board_id="raspberry-pi-zero-2w",
        arch="aarch64",
        cpu_cores=4,
        memory_mib=512,
        storage_mib=32768,
        description="4x Cortex-A53 @ 1 GHz, 512 MiB LPDDR2, SD storage",
    ),
    BoardProfile(
        board_id="generic-edge-arm64",
        arch="aarch64",
        cpu_cores=2,
        memory_mib=1024,
        storage_mib=16384,
        description="generic 64-bit ARM edge board (reference envelope)",
    ),
)


def board_for(board_id: str) -> BoardProfile:
    """Look up a frozen board profile by id (fail closed)."""
    for profile in EDGE_BOARD_PROFILES:
        if profile.board_id == board_id:
            return profile
    raise EdgeError(
        EdgeReasonCode.HARDWARE_INVALID,
        "unknown board id %r (known: %s)"
        % (board_id, [profile.board_id for profile in EDGE_BOARD_PROFILES]),
    )


@dataclass(frozen=True)
class HardwareInventory:
    """One hardware-capacity reading: the board identity plus the
    DYNAMIC quantities (cores, available memory, available storage).
    Capacities only -- interface inventory stays with the WORK-033
    interface source; there is no second discovery authority."""

    board_id: str
    arch: str
    cpu_cores: int
    memory_total_mib: int
    memory_available_mib: int
    storage_total_mib: int
    storage_available_mib: int

    def __post_init__(self) -> None:
        if not self.board_id or not isinstance(self.board_id, str):
            raise EdgeError(
                EdgeReasonCode.HARDWARE_INVALID,
                "inventory board id must be a non-empty string",
            )
        if not self.arch or not isinstance(self.arch, str):
            raise EdgeError(
                EdgeReasonCode.HARDWARE_INVALID,
                "inventory arch must be a non-empty string",
            )
        for name in (
            "cpu_cores", "memory_total_mib", "memory_available_mib",
            "storage_total_mib", "storage_available_mib",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise EdgeError(
                    EdgeReasonCode.HARDWARE_INVALID,
                    "%s must be an integer (got %s)"
                    % (name, type(value).__name__),
                )
            if value < 0:
                raise EdgeError(
                    EdgeReasonCode.HARDWARE_INVALID,
                    "%s must be non-negative (got %d)" % (name, value),
                )
        if self.cpu_cores < 1:
            raise EdgeError(
                EdgeReasonCode.HARDWARE_INVALID,
                "cpu_cores must be >= 1",
            )
        if self.memory_available_mib > self.memory_total_mib:
            raise EdgeError(
                EdgeReasonCode.HARDWARE_INVALID,
                "memory available (%d MiB) exceeds total (%d MiB)"
                % (self.memory_available_mib, self.memory_total_mib),
            )
        if self.storage_available_mib > self.storage_total_mib:
            raise EdgeError(
                EdgeReasonCode.HARDWARE_INVALID,
                "storage available (%d MiB) exceeds total (%d MiB)"
                % (self.storage_available_mib, self.storage_total_mib),
            )

    def to_dict(self) -> dict:
        return {
            "board_id": self.board_id,
            "arch": self.arch,
            "cpu_cores": self.cpu_cores,
            "memory_total_mib": self.memory_total_mib,
            "memory_available_mib": self.memory_available_mib,
            "storage_total_mib": self.storage_total_mib,
            "storage_available_mib": self.storage_available_mib,
        }

    @classmethod
    def from_dict(cls, data: object) -> "HardwareInventory":
        if not isinstance(data, Mapping):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "hardware inventory must be a mapping",
            )
        return cls(
            board_id=data.get("board_id", ""),
            arch=data.get("arch", ""),
            cpu_cores=data.get("cpu_cores", 0),
            memory_total_mib=data.get("memory_total_mib", 0),
            memory_available_mib=data.get("memory_available_mib", 0),
            storage_total_mib=data.get("storage_total_mib", 0),
            storage_available_mib=data.get("storage_available_mib", 0),
        )

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


class HardwareInventorySource:
    """The read-only hardware-capacity discovery seam (the WORK-033
    ``InterfaceSource`` discipline)."""

    def read(self) -> HardwareInventory:
        raise NotImplementedError


class StaticHardwareSource(HardwareInventorySource):
    """Deterministic in-memory hardware source (verification seam)."""

    def __init__(self, inventory: HardwareInventory) -> None:
        if not isinstance(inventory, HardwareInventory):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "static hardware source requires a genuine "
                "HardwareInventory (got %s)" % (type(inventory).__name__,),
            )
        self._inventory = inventory

    def read(self) -> HardwareInventory:
        return self._inventory


class LinuxHardwareSource(HardwareInventorySource):
    """Read the real hardware capacities of a deployment-declared
    board.

    The board identity and its advertised totals come from the frozen
    profile (deployment configuration -- honest by construction: the
    source never guesses which board it runs on); the DYNAMIC
    quantities are read from ``/proc/meminfo``, ``/proc/cpuinfo`` and
    the storage statistics of ``storage_root``.  Unreadable sources
    fail closed with ``hardware-source-failed``.
    """

    def __init__(
        self,
        board: BoardProfile,
        *,
        proc_meminfo: str = DEFAULT_PROC_MEMINFO,
        proc_cpuinfo: str = DEFAULT_PROC_CPUINFO,
        storage_root: str = ".",
    ) -> None:
        if not isinstance(board, BoardProfile):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "linux hardware source requires a genuine BoardProfile",
            )
        self._board = board
        self._proc_meminfo = Path(proc_meminfo)
        self._proc_cpuinfo = Path(proc_cpuinfo)
        self._storage_root = Path(storage_root)

    def _read_meminfo_kib(self, key: str) -> int:
        try:
            text = self._proc_meminfo.read_text(encoding="utf-8")
        except OSError as error:
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "unreadable %s: %s" % (self._proc_meminfo, type(error).__name__),
            ) from error
        for line in text.splitlines():
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip() == key:
                try:
                    return int(parts[1].strip().split()[0])
                except (ValueError, IndexError):
                    return 0
        return 0

    def _read_cpu_cores(self) -> int:
        try:
            text = self._proc_cpuinfo.read_text(encoding="utf-8")
        except OSError as error:
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "unreadable %s: %s" % (self._proc_cpuinfo, type(error).__name__),
            ) from error
        cores = 0
        for line in text.splitlines():
            if line.startswith("processor"):
                cores += 1
        if cores < 1:
            return self._board.cpu_cores
        return cores

    def _read_storage_mib(self) -> Tuple[int, int]:
        try:
            usage = disk_usage(str(self._storage_root))
        except OSError as error:
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "unreadable storage statistics for %s: %s"
                % (self._storage_root, type(error).__name__),
            ) from error
        total_mib = usage.total // (1024 * 1024)
        free_mib = usage.free // (1024 * 1024)
        return total_mib, free_mib

    def read(self) -> HardwareInventory:
        memory_total_kib = self._read_meminfo_kib("MemTotal")
        memory_available_kib = self._read_meminfo_kib("MemAvailable")
        if memory_total_kib <= 0:
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "MemTotal missing from %s" % (self._proc_meminfo,),
            )
        memory_total_mib = max(1, memory_total_kib // 1024)
        memory_available_mib = memory_available_kib // 1024
        if memory_available_mib > memory_total_mib:
            memory_available_mib = memory_total_mib
        cpu_cores = self._read_cpu_cores()
        storage_total_mib, storage_free_mib = self._read_storage_mib()
        storage_available_mib = min(storage_free_mib, storage_total_mib)
        return HardwareInventory(
            board_id=self._board.board_id,
            arch=self._board.arch,
            cpu_cores=cpu_cores,
            # The declared board profile CAPS the reported totals: an
            # emulation host larger than the board reports the board's
            # envelope (honest constrained-environment emulation, the
            # cgroup/QEMU equivalent inside the model).
            memory_total_mib=min(memory_total_mib, self._board.memory_mib),
            memory_available_mib=min(
                memory_available_mib, self._board.memory_mib
            ),
            storage_total_mib=storage_total_mib,
            storage_available_mib=storage_available_mib,
        )


class FailingHardwareSource(HardwareInventorySource):
    """Fault-injection hardware source (fail-closed verification)."""

    def __init__(
        self, error: object = None
    ) -> None:
        if error is None:
            self._error: Exception = EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "injected hardware-source failure",
            )
        elif isinstance(error, Exception):
            self._error = error
        else:
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "failing hardware source error must be an Exception",
            )

    def read(self) -> HardwareInventory:
        raise self._error


__all__ = [
    "HARDWARE_EVIDENCE_STATUS",
    "BoardProfile",
    "EDGE_BOARD_PROFILES",
    "board_for",
    "HardwareInventory",
    "HardwareInventorySource",
    "StaticHardwareSource",
    "LinuxHardwareSource",
    "FailingHardwareSource",
    "DEFAULT_PROC_MEMINFO",
    "DEFAULT_PROC_CPUINFO",
]
