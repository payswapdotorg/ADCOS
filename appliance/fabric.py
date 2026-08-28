"""WORK-036 local fabric view: the complete-fabric projection.

:class:`FabricView` joins the appliance's public read surfaces into
one deterministic, secret-free snapshot of the LOCAL fabric: the
agent's live access adapters (WORK-016 through WORK-033), the edge
posture (WORK-034), the provisioned breakout gateways (WORK-024),
and the registered local services (WORK-025).

:func:`fabric_complete` is the deterministic completeness predicate
for the acceptance target ``operators can provision a complete local
fabric``: a provisioned site with at least one live access adapter,
one registered breakout gateway, and one registered local service.

The view is a PROJECTION only -- it reads state, never mutates it,
and it never re-derives authority facts (counts and refs come from
the appliance's own tracked provisioning outcomes and the registries'
public surfaces).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import ApplianceError, ApplianceReasonCode
from .model import ProvisionState, UpstreamMode


@dataclass(frozen=True)
class FabricView:
    """One deterministic snapshot of the local fabric's posture."""

    site_label: str
    upstream_mode: str
    provision_state: str
    adapter_ids: Tuple[str, ...]
    access_posture: str
    gateway_refs: Tuple[str, ...]
    path_count: int
    service_refs: Tuple[str, ...]
    complete: bool

    def __post_init__(self) -> None:
        if self.upstream_mode not in UpstreamMode.values():
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "fabric view upstream mode %r not in the frozen "
                "vocabulary" % (self.upstream_mode,),
            )
        if self.provision_state not in ProvisionState.values():
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "fabric view provision state %r not in the frozen "
                "vocabulary" % (self.provision_state,),
            )
        for name in ("adapter_ids", "gateway_refs", "service_refs"):
            if not isinstance(getattr(self, name), tuple):
                raise ApplianceError(
                    ApplianceReasonCode.INVALID_INPUT,
                    "fabric view %s must be a tuple" % (name,),
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_label": self.site_label,
            "upstream_mode": self.upstream_mode,
            "provision_state": self.provision_state,
            "adapter_ids": list(self.adapter_ids),
            "access_posture": self.access_posture,
            "gateway_refs": list(self.gateway_refs),
            "path_count": self.path_count,
            "service_refs": list(self.service_refs),
            "complete": self.complete,
        }


def fabric_complete(
    *,
    provision_state: str,
    adapter_ids: Tuple[str, ...],
    gateway_refs: Tuple[str, ...],
    service_refs: Tuple[str, ...],
) -> bool:
    """The deterministic completeness predicate (pure).

    A COMPLETE local fabric is: a provisioned site exposing at least
    one live access adapter, at least one registered breakout
    gateway, and at least one registered local service.  Everything
    is judged from explicit facts -- no defaults, no guesses.
    """
    return (
        provision_state == ProvisionState.PROVISIONED
        and len(adapter_ids) >= 1
        and len(gateway_refs) >= 1
        and len(service_refs) >= 1
    )


def build_fabric_view(
    *,
    site_label: str,
    upstream_mode: str,
    provision_state: str,
    adapter_ids: Tuple[str, ...],
    access_posture: str,
    gateway_refs: Tuple[str, ...],
    path_count: int,
    service_refs: Tuple[str, ...],
) -> FabricView:
    """Join the public facts into one :class:`FabricView`."""
    complete = fabric_complete(
        provision_state=provision_state,
        adapter_ids=adapter_ids,
        gateway_refs=gateway_refs,
        service_refs=service_refs,
    )
    return FabricView(
        site_label=site_label,
        upstream_mode=upstream_mode,
        provision_state=provision_state,
        adapter_ids=tuple(adapter_ids),
        access_posture=access_posture,
        gateway_refs=tuple(sorted(gateway_refs)),
        path_count=path_count,
        service_refs=tuple(sorted(service_refs)),
        complete=complete,
    )


def fabric_view_digest(view: FabricView) -> str:
    """The canonical digest of one fabric view (replayable)."""
    import hashlib

    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(view.to_dict()),
    ).hexdigest()


__all__ = [
    "FabricView",
    "fabric_complete",
    "build_fabric_view",
    "fabric_view_digest",
]
