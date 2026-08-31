"""WORK-041 platform observation boundary.

The seam through which platform observations become candidate
NetworkPath records -- and NOTHING else:

    platform observation  (InterfaceSource.discover, the accepted
                           WORK-033/W040 interface discovery seam)
            |
            v
    PlatformObservation    (DATA + evidence: facts, digest, instant)
            |
            v
    candidate NetworkPath  (state DISCOVERED -- detection only)

The observation boundary reuses the EXISTING interface-discovery
machinery (``agent.interfaces.InterfaceSource`` -- the seam the
WORK-040 correction exercised for dynamic interface exposure and
interface-class handover).  It creates no competing discovery authority,
imports no platform/vendor API, and hard-codes no technology names.

Fail-closed discipline:

- a source that raises surfaces as a typed
  ``OBSERVATION_SOURCE_FAILED`` error (an OS exception never crosses
  the composition boundary);
- an ambiguous observation set (duplicate interface names) is
  rejected whole (``OBSERVATION_INVALID``);
- malformed observations (not genuine ``InterfaceSnapshot`` values)
  are rejected at construction;
- a candidate is created in ``DISCOVERED`` state ONLY -- discovery
  never validates, binds, activates, or mutates any other authority.
"""

from __future__ import annotations

from typing import Tuple

from agent.errors import AgentError
from agent.interfaces import InterfaceSource
from agent.model import InterfaceSnapshot

from .errors import NetworkPathError, NetworkPathReasonCode
from .model import NetworkPath, PlatformObservation
from .state import NetworkPathState


def read_observations(
    source: InterfaceSource, *, now: str
) -> Tuple[PlatformObservation, ...]:
    """Read one interface-discovery cycle through the existing seam.

    ``now`` is the injected observation instant (the WORK-033 clock
    seam; never a wall clock).  Source failures are isolated into the
    typed NetworkPath error vocabulary.  The returned tuple is sorted
    by interface name (deterministic order).
    """
    if not isinstance(source, InterfaceSource):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "source must be an InterfaceSource (the existing WORK-033 seam)",
        )
    if not isinstance(now, str) or not now:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "now must be an RFC 3339 UTC instant string",
        )
    try:
        snapshots = source.discover()
    except Exception as error:  # isolation: typed value, never an OS exception
        raise NetworkPathError(
            NetworkPathReasonCode.OBSERVATION_SOURCE_FAILED,
            "interface discovery failed (%s)"
            % type(error).__name__,
        ) from error
    if not isinstance(snapshots, tuple):
        raise NetworkPathError(
            NetworkPathReasonCode.OBSERVATION_SOURCE_FAILED,
            "interface source returned a non-tuple result (%s)"
            % type(snapshots).__name__,
        )
    observations: Tuple[PlatformObservation, ...] = tuple(
        PlatformObservation(snapshot=snapshot, observed_at=now)
        for snapshot in snapshots
    )
    _reject_ambiguous(observations)
    return tuple(sorted(observations, key=lambda item: item.interface_name))


def _reject_ambiguous(observations: Tuple[PlatformObservation, ...]) -> None:
    """Duplicate interface names make the observation set ambiguous."""
    seen = set()
    for observation in observations:
        name = observation.interface_name
        if name in seen:
            raise NetworkPathError(
                NetworkPathReasonCode.OBSERVATION_INVALID,
                "ambiguous observation set: interface %r reported more than "
                "once in one discovery cycle (fail closed)" % name,
            )
        seen.add(name)


def observation_for(
    observations: Tuple[PlatformObservation, ...], interface_name: str
) -> PlatformObservation:
    """The observation of one interface; absent means fail closed."""
    for observation in observations:
        if observation.interface_name == interface_name:
            return observation
    raise NetworkPathError(
        NetworkPathReasonCode.OBSERVATION_INVALID,
        "no platform observation for interface %r (the path is not "
        "currently observed -- fail closed)" % interface_name,
    )


def candidate_from_observation(
    observation: PlatformObservation, *, node_id: str, now: str
) -> NetworkPath:
    """Project one platform observation into a DISCOVERED candidate.

    The candidate records the observation evidence (instant + snapshot
    digest) and NOTHING else: no validation verdict, no binding facts,
    no activation.  ``AgentError`` raised by the content-bound record
    constructor is re-wrapped into the typed NetworkPath vocabulary.
    """
    if not isinstance(observation, PlatformObservation):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "observation must be a PlatformObservation",
        )
    if not isinstance(node_id, str) or not node_id:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "node_id must be a non-empty string (the existing node identity)",
        )
    snapshot = observation.snapshot
    if not isinstance(snapshot, InterfaceSnapshot):
        raise NetworkPathError(
            NetworkPathReasonCode.OBSERVATION_INVALID,
            "observation carries a malformed interface snapshot",
        )
    try:
        return NetworkPath(
            network_path_id="",
            node_id=node_id,
            interface_name=snapshot.name,
            link_kind=snapshot.link_kind,
            addresses=tuple(sorted(snapshot.addresses)),
            state=NetworkPathState.DISCOVERED,
            observed_at=now,
            observed_snapshot_digest=observation.snapshot_digest,
        )
    except NetworkPathError as error:
        raise NetworkPathError(
            NetworkPathReasonCode.OBSERVATION_INVALID,
            "candidate projection rejected: %s" % error.detail,
        ) from error
    except AgentError as error:
        raise NetworkPathError(
            NetworkPathReasonCode.OBSERVATION_INVALID,
            "candidate projection rejected: %s" % error.detail,
        ) from error
