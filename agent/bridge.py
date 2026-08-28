"""WORK-033 interface-to-adapter bridge.

Bridges discovered network interfaces into the WORK-016 Adapter SDK:
each interface becomes one adapter (descriptor + contract
implementation) registered on the node's ``AdapterRuntime``.  The
bridge follows the sanctioned SDK-bridge pattern (the wifi family
precedent): it holds only its owner references, all adapter-side faults
surface through the sandbox as typed failure values, and every
operation charges the deterministic step budget.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from adapters import (
    AdapterContract,
    AdapterContext,
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
)

from .interfaces import InterfaceSource
from .model import InterfaceSnapshot

# Technology map: the agent's local link-kind classification -> a
# registered access-technology id (registry DATA behind the adapter
# boundary; no core semantic ever branches on these).
TECHNOLOGY_FOR_KIND: Dict[str, str] = {
    "ethernet": "access.ieee.8023",
    "loopback": "access.generic.experimental",
    "wireless": "access.ieee.80211",
    "other": "access.generic.experimental",
}

INTERFACE_CAPABILITIES: Tuple[str, ...] = (
    "capability.profile.ip.data-transfer",
)

# Deterministic step charges (the hang model; no wall-clock timeouts).
STEP_CHARGES: Dict[str, int] = {
    "open": 4,
    "observe": 3,
    "allocate": 8,
    "release": 4,
    "bind_session": 6,
    "unbind_session": 4,
    "close": 4,
}

# Fallback declared bandwidth when the OS reports no link speed
# (loopback, virtual interfaces): an honest, conservative floor.
FALLBACK_SPEED_MBPS = 10


def technology_for_snapshot(snapshot: InterfaceSnapshot) -> str:
    technology = TECHNOLOGY_FOR_KIND.get(snapshot.link_kind, "access.generic.experimental")
    return technology


def interface_descriptor(
    snapshot: InterfaceSnapshot, adapter_id: str
) -> AdapterDescriptor:
    """Build the WORK-016 descriptor for one discovered interface."""
    speed = snapshot.speed_mbps if snapshot.speed_mbps > 0 else FALLBACK_SPEED_MBPS
    return AdapterDescriptor(
        adapter_id=adapter_id,
        access_technology_id=technology_for_snapshot(snapshot),
        supported_profile_versions=("v1-0-0",),
        capabilities=INTERFACE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="%s:bandwidth" % snapshot.name,
                kind="bandwidth",
                unit="mbps",
                quantity=speed,
                availability="continuous",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("interface-credential",),
            attested=False,
        ),
    )


class InterfaceTechnologyAdapter(AdapterContract):
    """The WORK-016 adapter implementation backed by one interface.

    Holds only its owner references (the interface source and the
    interface name) plus a deterministic local ledger; the runtime
    performs session-state verification and capacity enforcement --
    the bridge never touches authority state.
    """

    label = "agent-interface"

    def __init__(self, source: InterfaceSource, name: str) -> None:
        self._source = source
        self._name = name
        self._allocations: Dict[str, str] = {}  # ref -> purpose
        self._bearers: Dict[str, str] = {}  # bearer -> session_id
        self._sequence = 0
        self._open = False

    # -- helpers -----------------------------------------------------------

    def _snapshot(self, context: AdapterContext) -> Optional[InterfaceSnapshot]:
        for snapshot in self._source.discover():
            if snapshot.name == self._name:
                return snapshot
        return None

    def _next_ref(self, prefix: str) -> str:
        self._sequence += 1
        return "agent-if:%s:%06d" % (prefix, self._sequence)

    # -- the nine contract operations --------------------------------------

    def open(self, context: AdapterContext) -> None:
        context.charge(STEP_CHARGES["open"])
        snapshot = self._snapshot(context)
        if snapshot is None:
            raise RuntimeError("interface %s disappeared from the source" % self._name)
        self._open = True

    def capabilities(self) -> Sequence[str]:
        return INTERFACE_CAPABILITIES

    def observe(self, context: AdapterContext) -> Mapping[str, int]:
        context.charge(STEP_CHARGES["observe"])
        snapshot = self._snapshot(context)
        if snapshot is None:
            raise RuntimeError("interface %s disappeared from the source" % self._name)
        return {
            "link-up": 1 if snapshot.state_up else 0,
            "rx-bytes-total": snapshot.rx_bytes,
            "tx-bytes-total": snapshot.tx_bytes,
            "rx-error-count": snapshot.rx_errors,
            "tx-error-count": snapshot.tx_errors,
            # The kernel interface statistics this source reads expose
            # no retransmit counter; the honest reported value is 0.
            "retransmit-count": 0,
        }

    def allocate(
        self, context: AdapterContext, *, kind: str, quantity_base: int, purpose: str
    ) -> str:
        context.charge(STEP_CHARGES["allocate"])
        if kind != "bandwidth":
            raise ValueError("interface adapter maps only bandwidth, got %r" % kind)
        if quantity_base <= 0:
            raise ValueError("quantity must be positive")
        reference = self._next_ref("alloc")
        self._allocations[reference] = purpose
        return reference

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        context.charge(STEP_CHARGES["release"])
        if technology_ref not in self._allocations:
            raise KeyError("unknown technology reference")
        del self._allocations[technology_ref]

    def bind_session(
        self,
        context: AdapterContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> str:
        context.charge(STEP_CHARGES["bind_session"])
        if not session_id:
            raise ValueError("session_id is required")
        bearer = self._next_ref("bearer")
        self._bearers[bearer] = session_id
        return bearer

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        context.charge(STEP_CHARGES["unbind_session"])
        if bearer_ref not in self._bearers:
            raise KeyError("unknown bearer reference")
        del self._bearers[bearer_ref]

    def health(self) -> str:
        # Health derives from a fresh source observation of this
        # interface: link down -> FAILED, errors -> DEGRADED, else
        # HEALTHY (the WORK-016 worse-of ladder applies on top).
        snapshot: Optional[InterfaceSnapshot] = None
        for candidate in self._source.discover():
            if candidate.name == self._name:
                snapshot = candidate
                break
        if snapshot is None:
            return "FAILED"
        if not snapshot.state_up:
            return "FAILED"
        if snapshot.rx_errors > 0 or snapshot.tx_errors > 0:
            return "DEGRADED"
        return "HEALTHY"

    def close(self, context: AdapterContext) -> None:
        context.charge(STEP_CHARGES["close"])
        self._open = False
        self._allocations.clear()
        self._bearers.clear()
