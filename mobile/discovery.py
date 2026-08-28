"""WORK-035 local discovery participation port.

Local discovery is a HOST-PROVIDED capability behind the mobile
boundary -- exactly like the platform source.  The work order's rule
("mobile/OS-specific APIs remain behind the mobile adapter boundary")
applies in both directions:

- the mobile layer OWNS the participation gate (when local discovery
  may run: consent + phase + connectivity) and the journaling of what
  it learned;
- the actual announce/receive substrate is the accepted WORK-006
  discovery machinery, WIRED BY THE HOST.  A real device build
  constructs the WORK-006 ``DiscoveryService`` with the app's identity
  wiring and adapts it to this port; the reference battery wires a
  genuine signed WORK-006 exchange over the in-memory transport bus.

The mobile family therefore imports NO discovery module and NO
identity machinery: no second identity authority can be constructed
from inside the mobile layer, structurally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .errors import MobileError, MobileReasonCode


@dataclass(frozen=True)
class PeerObservation:
    """What the mobile node learned from one local discovery cycle:
    an authenticated observation that a peer saw THIS node.  Pure
    DATA (never identity, never trust, never topology authority --
    the WORK-006 observation discipline)."""

    observed_by: str
    endpoints: Tuple[str, ...] = ()
    observed_at: str = ""
    freshness_until: str = ""
    source: str = "local"

    def __post_init__(self) -> None:
        if not isinstance(self.observed_by, str) or not self.observed_by:
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "peer observation observed_by must be a non-empty node id",
            )
        if not isinstance(self.endpoints, tuple):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "peer observation endpoints must be a tuple of strings",
            )

    def to_dict(self) -> dict:
        return {
            "observed_by": self.observed_by,
            "endpoints": list(self.endpoints),
            "observed_at": self.observed_at,
            "freshness_until": self.freshness_until,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PeerObservation":
        if not isinstance(data, dict):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "peer observation must be a mapping",
            )
        endpoints = data.get("endpoints", ())
        if not isinstance(endpoints, (list, tuple)):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "peer observation endpoints must be a sequence",
            )
        return cls(
            observed_by=str(data.get("observed_by", "")),
            endpoints=tuple(str(entry) for entry in endpoints),
            observed_at=str(data.get("observed_at", "")),
            freshness_until=str(data.get("freshness_until", "")),
            source=str(data.get("source", "local")),
        )


@dataclass(frozen=True)
class DiscoveryCycle:
    """The result of one local discovery cycle through the port."""

    announced: bool
    announcement_id: str = ""
    observations: Tuple[PeerObservation, ...] = ()

    def to_dict(self) -> dict:
        return {
            "announced": self.announced,
            "announcement_id": self.announcement_id,
            "observations": [entry.to_dict() for entry in self.observations],
        }


class LocalDiscoveryPort:
    """The host-provided local discovery capability seam.

    ``cycle`` performs one announce/receive round at the injected
    instant and returns what was announced and what was learned.
    Implementations must be deterministic for a fixed scenario; they
    never mutate mobile-layer state and never touch agent
    authorities.
    """

    def cycle(self, *, now: str) -> DiscoveryCycle:
        raise NotImplementedError


class NullDiscovery(LocalDiscoveryPort):
    """The honest no-discovery default: announces nothing, observes
    nothing.  Wiring no port means the node does not participate in
    local discovery -- it never fabricates observations."""

    def cycle(self, *, now: str) -> DiscoveryCycle:
        return DiscoveryCycle(announced=False)
