"""WORK-036 isolated-site boundary: the upstream posture model.

The appliance's design center is the ISOLATED site (community /
emergency deployment): the box and its local fabric operate with NO
upstream Internet.  This module is the pure posture model:

- :data:`APPLIANCE_EVIDENCE_STATUS` -- the anti-faking two-track
  disclosure (the W020/W034/W035 discipline): a software/simulated
  isolated-site integration run is engineering verification and is
  NEVER a physical-deployment PASS.  The physical appliance track
  stays explicitly OPEN until genuinely demonstrated on real
  hardware at a real site.

- :func:`upstream_mode_for` -- the bool-to-posture vocabulary map;

- :func:`check_service_query` -- the local-fabric query policy: the
  appliance NEVER issues a federated service query.  A federated
  request is refused with a typed, journaled reason under BOTH
  postures (the appliance hosts a LOCAL fabric; federation exchange
  is a later-work-item surface, never silently downgraded into a
  local query here).

Everything is a pure function of explicit inputs -- no clock, no OS
state, no network.
"""

from __future__ import annotations

from .errors import ApplianceError, ApplianceReasonCode
from .model import UpstreamMode

#: The frozen two-track evidence disclosure for WORK-036.
#:
#: Track 1 (software/simulated isolated-site integration) is closed by
#: the deterministic battery.  Track 2 (a physical Network-in-a-Box
#: appliance operating at a real isolated site) remains OPEN until a
#: genuine field deployment is demonstrated -- a simulated site is
#: engineering verification, NEVER a physical-deployment PASS.
APPLIANCE_EVIDENCE_STATUS = {
    "isolated_site_software_integration": "supported-verified",
    "physical_appliance_deployment": "open",
}


def upstream_mode_for(available: bool) -> str:
    """Map an upstream-availability fact to the posture vocabulary."""
    if not isinstance(available, bool):
        raise ApplianceError(
            ApplianceReasonCode.INVALID_INPUT,
            "upstream availability must be a bool (got %s)"
            % (type(available).__name__,),
        )
    if available:
        return UpstreamMode.CONNECTED
    return UpstreamMode.ISOLATED


def check_service_query(*, include_federated: bool) -> None:
    """The local-fabric query policy (pure, fail-closed).

    The appliance's service surface is LOCAL by construction.  A
    federated query is refused with a typed reason under both
    postures: the operator's request is never silently downgraded
    into a local query, and the appliance never wires federation
    trust state (that surface belongs to later work items, out of
    scope here).
    """
    if include_federated is True:
        raise ApplianceError(
            ApplianceReasonCode.FEDERATION_OUT_OF_SCOPE,
            "the appliance service surface is LOCAL: federated "
            "discovery belongs to the federation surface of later "
            "work items (refused, never silently downgraded)",
        )
    if not isinstance(include_federated, bool):
        raise ApplianceError(
            ApplianceReasonCode.PARAMS_INVALID,
            "include_federated must be a bool",
        )


def isolated_site_ready(
    *, provision_state: str, upstream_mode: str,
) -> bool:
    """The pure isolated-site readiness predicate: a provisioned
    fabric operating in the ISOLATED posture (the acceptance target
    ``local services operate without upstream Internet``)."""
    return (
        provision_state == "provisioned"
        and upstream_mode == UpstreamMode.ISOLATED
    )


__all__ = [
    "APPLIANCE_EVIDENCE_STATUS",
    "upstream_mode_for",
    "check_service_query",
    "isolated_site_ready",
]
