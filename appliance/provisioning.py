"""WORK-036 provisioning: pure manifest validation and step planning.

``validate_manifest`` is a PURE, fail-closed check of the operator's
declarative :class:`~appliance.model.FabricManifest` BEFORE anything
is applied: genuine ACCEPTED domain objects only (no duck typing),
evidence claim digests must bind the whole claims, vocabularies must
be the frozen WORK-024/W025 values, entries must be unique, and the
fabric must be internally coherent (every declared path terminates
at a declared gateway).  The output is the frozen, deterministic
application plan (gateways, then paths, then services).

Nothing here mutates any authority: the plan is DATA; the appliance
applies it through the accepted public manager/registry surfaces.
"""

from __future__ import annotations

from typing import List, Tuple

from adapters.distcore import (
    GatewayRoleClass,
    derive_gateway_claim_digest,
    derive_gateway_ref,
)
from services import (
    EvidenceSourceClass,
    VisibilityScope,
    derive_advertisement_claim_digest,
)
from services.model import ServiceKind

from .errors import ApplianceError, ApplianceReasonCode
from .model import (
    FabricManifest,
    GatewayEntry,
    ProvisionStep,
    ProvisionStepKind,
    ServiceEntry,
)


def validate_manifest(manifest: FabricManifest) -> Tuple[ProvisionStep, ...]:
    """Validate one fabric manifest and derive its application plan.

    Raises :class:`ApplianceError` (typed, fail-closed) on any
    violation; returns the ordered :class:`ProvisionStep` plan on
    success.  The check order is frozen: types -> per-entry evidence
    binding -> vocabularies -> duplicates -> path coherence.
    """
    if not isinstance(manifest, FabricManifest):
        raise ApplianceError(
            ApplianceReasonCode.INVALID_INPUT,
            "provisioning requires a genuine FabricManifest (got %s)"
            % (type(manifest).__name__,),
        )

    steps: List[ProvisionStep] = []

    # -- gateways ----------------------------------------------------
    seen_gateway_refs = set()
    gateway_nodes = set()
    for gateway_index, gateway_entry in enumerate(manifest.gateways):
        descriptor = gateway_entry.descriptor
        evidence = gateway_entry.evidence
        expected = derive_gateway_claim_digest(descriptor)
        if evidence.claim_digest != expected:
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "gateway entry %d: evidence claim digest does not "
                "bind the descriptor claim (unevidenced or tampered)"
                % (gateway_index,),
            )
        if descriptor.role_class not in GatewayRoleClass.values():
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "gateway entry %d: role class %r not in the frozen "
                "WORK-024 vocabulary"
                % (gateway_index, descriptor.role_class),
            )
        gateway_ref = derive_gateway_ref(
            descriptor.name, descriptor.gateway_id,
            descriptor.node_id, descriptor.role_class,
        )
        if gateway_ref in seen_gateway_refs:
            raise ApplianceError(
                ApplianceReasonCode.DUPLICATE_ENTRY,
                "gateway entry %d duplicates an earlier gateway "
                "identity (%s)" % (gateway_index, gateway_ref),
            )
        seen_gateway_refs.add(gateway_ref)
        if descriptor.node_id in gateway_nodes:
            raise ApplianceError(
                ApplianceReasonCode.DUPLICATE_ENTRY,
                "gateway entry %d: node %s already hosts a declared "
                "gateway (the appliance registers one gateway per "
                "node role -- two gateways on one node would be "
                "ambiguous at breakout resolution)"
                % (gateway_index, descriptor.node_id[:24]),
            )
        gateway_nodes.add(descriptor.node_id)
        steps.append(
            ProvisionStep(
                kind=ProvisionStepKind.REGISTER_GATEWAY,
                ref=gateway_ref,
                detail="role=%s" % (descriptor.role_class,),
            )
        )

    # -- paths --------------------------------------------------------
    seen_path_ids = set()
    for path_index, path in enumerate(manifest.paths):
        if path.path_id in seen_path_ids:
            raise ApplianceError(
                ApplianceReasonCode.DUPLICATE_ENTRY,
                "path entry %d duplicates an earlier path identity "
                "(%s)" % (path_index, path.path_id),
            )
        seen_path_ids.add(path.path_id)
        if path.destination_node_id not in gateway_nodes:
            raise ApplianceError(
                ApplianceReasonCode.PATH_INCOHERENT,
                "path entry %d does not terminate at a declared "
                "fabric gateway (destination %s)"
                % (path_index, path.destination_node_id),
            )
        steps.append(
            ProvisionStep(
                kind=ProvisionStepKind.REGISTER_PATH,
                ref=path.path_id,
                detail="feasible=%s" % (path.feasible,),
            )
        )

    # -- services ------------------------------------------------------
    seen_service_refs = set()
    for service_index, service_entry in enumerate(manifest.services):
        advertisement = service_entry.advertisement
        evidence = service_entry.evidence
        expected = derive_advertisement_claim_digest(advertisement)
        if evidence.claim_digest != expected:
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "service entry %d: evidence claim digest does not "
                "bind the advertisement claim (unevidenced or "
                "tampered)" % (service_index,),
            )
        if advertisement.descriptor.service_kind not in ServiceKind.values():
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "service entry %d: service kind %r not in the frozen "
                "WORK-025 vocabulary"
                % (service_index, advertisement.descriptor.service_kind),
            )
        if advertisement.visibility not in VisibilityScope.values():
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "service entry %d: visibility %r not in the frozen "
                "WORK-025 vocabulary"
                % (service_index, advertisement.visibility),
            )
        if (
            evidence.source_class == EvidenceSourceClass.REMOTE_CLAIM
            and not advertisement.federation_relationship_id
        ):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "service entry %d: a peer-imported claim must carry "
                "the federation relationship it arrived on"
                % (service_index,),
            )
        service_ref = advertisement.service_ref
        if service_ref in seen_service_refs:
            raise ApplianceError(
                ApplianceReasonCode.DUPLICATE_ENTRY,
                "service entry %d duplicates an earlier service "
                "identity (%s)" % (service_index, service_ref),
            )
        seen_service_refs.add(service_ref)
        steps.append(
            ProvisionStep(
                kind=ProvisionStepKind.REGISTER_SERVICE,
                ref=service_ref,
                detail="kind=%s" % (advertisement.descriptor.service_kind,),
            )
        )

    if not steps:
        raise ApplianceError(
            ApplianceReasonCode.MANIFEST_INVALID,
            "manifest declares no gateways, paths, or services "
            "(an empty fabric is not provisionable)",
        )
    return tuple(steps)


def planned_refs(
    steps: Tuple[ProvisionStep, ...],
    kind: str,
) -> Tuple[str, ...]:
    """The planned references of one step kind (deterministic order)."""
    return tuple(step.ref for step in steps if step.kind == kind)


__all__ = [
    "validate_manifest",
    "planned_refs",
]
