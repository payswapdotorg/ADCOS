"""WORK-033 Linux network-interface discovery.

The interface source is the agent's read-only view of the host's
network interfaces.  ``LinuxInterfaceSource`` reads the real
``/sys/class/net`` tree (and ``/proc/net/if_inet6`` for global IPv6
addresses) through ``pathlib`` -- read-only, no privileges required,
the only filesystem-access site in the agent family (battery-audited).
``StaticInterfaceSource`` is the deterministic seam used by
verification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from .errors import AgentError, AgentReasonCode
from .model import InterfaceSnapshot

DEFAULT_SYS_CLASS_NET = "/sys/class/net"
DEFAULT_PROC_IF_INET6 = "/proc/net/if_inet6"

# Linux arp_hw type identifiers (include/linux/if_arp.h) for the kinds
# the reference agent classifies; anything else is "other".
_HW_KINDS: Dict[str, str] = {
    "1": "ethernet",
    "772": "loopback",
    "801": "wireless",
    "802": "wireless",
    "803": "wireless",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_int(path: Path) -> int:
    text = _read_text(path)
    try:
        return int(text)
    except ValueError:
        return 0


class InterfaceSource:
    """The read-only interface discovery seam."""

    def discover(self) -> Tuple[InterfaceSnapshot, ...]:
        raise NotImplementedError


class StaticInterfaceSource(InterfaceSource):
    """Deterministic in-memory interface source (verification seam)."""

    def __init__(self, snapshots: Tuple[InterfaceSnapshot, ...] = ()) -> None:
        seen: Set[str] = set()
        for snapshot in snapshots:
            if snapshot.name in seen:
                raise AgentError(
                    AgentReasonCode.INTERFACE_INVALID,
                    "duplicate interface name %r" % snapshot.name,
                )
            seen.add(snapshot.name)
        self._snapshots = tuple(snapshots)

    def discover(self) -> Tuple[InterfaceSnapshot, ...]:
        return self._snapshots


class LinuxInterfaceSource(InterfaceSource):
    """The real Linux ``/sys/class/net`` discovery source.

    Reads only kernel-exported pseudo-files.  Interface classification
    uses the kernel's hardware type (``/sys/class/net/<if>/type``):
    1 = ethernet, 772 = loopback, 801..803 = wireless; anything else
    maps to ``other``.  Missing or unreadable attributes degrade to
    honest defaults (state down, speed/mtu 0) rather than raising.
    """

    def __init__(
        self,
        sys_class_net: str = DEFAULT_SYS_CLASS_NET,
        proc_if_inet6: str = DEFAULT_PROC_IF_INET6,
        *,
        max_interfaces: int = 64,
    ) -> None:
        self._root = Path(sys_class_net)
        self._inet6 = Path(proc_if_inet6)
        self._max_interfaces = max_interfaces

    def discover(self) -> Tuple[InterfaceSnapshot, ...]:
        if not self._root.is_dir():
            raise AgentError(
                AgentReasonCode.INTERFACE_SOURCE_FAILED,
                "%s is not a directory (this source requires Linux)" % str(self._root),
            )
        names = sorted(entry.name for entry in self._root.iterdir() if entry.is_dir())
        snapshots: List[InterfaceSnapshot] = []
        for name in names[: self._max_interfaces]:
            snapshot = self._snapshot(name)
            if snapshot is not None:
                snapshots.append(snapshot)
        return tuple(snapshots)

    def _snapshot(self, name: str) -> Optional[InterfaceSnapshot]:
        if not name or "/" in name or name in (".", ".."):
            return None
        base = self._root / name
        if not base.is_dir():
            return None
        kind = _HW_KINDS.get(_read_text(base / "type"), "other")
        flags = _read_int(base / "flags")
        state_up = bool(flags & 0x1) or _read_text(base / "operstate") == "up"
        mtu = _read_int(base / "mtu")
        speed = _read_int(base / "speed")
        if speed < 0:
            speed = 0
        stats = base / "statistics"
        addresses = self._inet6_addresses(name)
        try:
            return InterfaceSnapshot(
                name=name,
                link_kind=kind,
                state_up=state_up,
                mtu=mtu,
                speed_mbps=speed,
                rx_bytes=_read_int(stats / "rx_bytes"),
                tx_bytes=_read_int(stats / "tx_bytes"),
                rx_errors=_read_int(stats / "rx_errors"),
                tx_errors=_read_int(stats / "tx_errors"),
                addresses=addresses,
            )
        except AgentError:
            return None

    def _inet6_addresses(self, interface: str) -> Tuple[str, ...]:
        """Global-scope IPv6 addresses from /proc/net/if_inet6 (if present)."""
        text = _read_text(self._inet6)
        if not text:
            return ()
        found: List[str] = []
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 6 and parts[5] == interface:
                hex_address = parts[0]
                scope = parts[3]
                if scope == "00":  # global scope
                    compressed = _compress_ipv6(hex_address)
                    if compressed is not None and compressed not in found:
                        found.append(compressed)
        return tuple(found)


def _compress_ipv6(hex_address: str) -> Optional[str]:
    """Canonical RFC 4291 compressed text for a 32-hex-digit address."""
    import ipaddress

    if len(hex_address) != 32:
        return None
    try:
        return str(ipaddress.IPv6Address(hex_address))
    except ValueError:
        return None


# Battery hook: deterministic fault injection into discovery.  The
# runtime treats a raising source as an isolated discovery failure
# (typed value, never an exception crossing the composition boundary).
class FailingInterfaceSource(InterfaceSource):
    """A source whose discover() always raises (isolation fixture)."""

    def __init__(self, error: Optional[Callable[[], Exception]] = None) -> None:
        self._error = error or (lambda: RuntimeError("interface discovery failed"))

    def discover(self) -> Tuple[InterfaceSnapshot, ...]:
        raise self._error()
