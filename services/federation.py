"""ADCOS service registry federation-scoped DATA translation
(WORK-025).

Federation-scoped translation ONLY (WORK-025 invariant 4): this
module carries federation references, scopes, and exposure policy as
DATA and translates local service records into peer claims for the
WORK-015 federation exchange.  It NEVER imports or recreates
federation trust state -- the ``services`` layer reads no federation
module; the frozen scope strings below are the frozen WORK-015
``federation.model.Scope`` values, cross-checked byte-for-byte by the
WORK-025 selftest (the WORK-023 lazy-vocabulary discipline inverted:
a local constant, verified against the authority instead of
importing it).

Membership in a federation never implies unrestricted service trust
or access: exposure is per (service, relationship, scope), and
removing an exposure never deletes the local service record.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from .errors import ServiceError, ServiceReasonCode
from .model import FederationExposure, ServiceCandidate
from .validation import validate_federation_ref, validate_label

#: The frozen WORK-015 federation scope governing service discovery
#: exposure (DATA; cross-checked against
#: ``federation.model.Scope.SERVICE_DISCOVER`` by the selftest).
SERVICE_DISCOVER_SCOPE = "service.discover"

#: The frozen WORK-015 federation scope governing service invocation
#: (DATA; cross-checked against ``federation.model.Scope.SERVICE_INVOKE``
#: by the selftest).
SERVICE_INVOKE_SCOPE = "service.invoke"

#: The frozen scope set the service layer may carry as DATA.
SERVICE_FEDERATION_SCOPES: Tuple[str, ...] = (
    SERVICE_DISCOVER_SCOPE, SERVICE_INVOKE_SCOPE,
)


def validate_federation_scope(value: object) -> str:
    """Validate a federation scope carried as service-layer DATA
    (must be one of the frozen WORK-015 service scopes)."""
    if not isinstance(value, str) or value not in SERVICE_FEDERATION_SCOPES:
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "federation scope %r is not one of the frozen WORK-015 "
            "service scopes carried by the service layer (%s)"
            % (value, SERVICE_FEDERATION_SCOPES),
        )
    return value


def export_service_exposures(
    records: Iterable[ServiceCandidate],
    exposures: Iterable[FederationExposure],
    *,
    relationship_id: str,
) -> Tuple[Mapping[str, Any], ...]:
    """Translate the local records that carry an ACTIVE exposure for
    one federation relationship into secret-free peer claims (the
    ``service-exposure`` exchange payload).

    The claim carries the service identity, semantic DATA, and
    location reference the peer side needs to re-register the claim --
    and nothing else: no secrets, no policy internals, no provider
    state (LOCK-023).  Records without an active exposure for the
    relationship are never exported: local tenant state does not leak
    into the federation exchange.
    """
    validate_federation_ref(relationship_id, label="relationship id")
    active = {
        exposure.service_ref
        for exposure in exposures
        if exposure.relationship_id == relationship_id
        and exposure.scope == SERVICE_DISCOVER_SCOPE
    }
    claims = []
    for record in records:
        if record.service_ref not in active:
            continue
        if record.source_class != "direct-observation":
            continue
        claims.append(
            {
                "service_ref": record.service_ref,
                "name": record.name,
                "service_kind": record.service_kind,
                "tenant_domain": record.tenant_domain,
                "host_node_id": record.host_node_id,
                "capability_refs": list(record.capability_refs),
                "service_labels": list(record.service_labels),
                "locality_labels": list(record.locality_labels),
                "privacy_labels": list(record.privacy_labels),
                "registered_at": record.registered_at,
                "expires_at": record.expires_at,
                "endpoint_ref": record.endpoint_ref,
                "policy_controlled": record.policy_controlled,
            }
        )
    return tuple(claims)


def peer_claim_fingerprint(claim: Mapping[str, Any]) -> str:
    """A deterministic fingerprint over one exported peer claim (the
    composition root may use it as provenance DATA)."""
    for field_name in ("service_ref", "name", "service_kind", "tenant_domain"):
        if not isinstance(claim.get(field_name), str):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "peer claim field %r must be a str" % (field_name,),
            )
    validate_label(claim["name"], label="peer claim name")
    return "|".join(
        (
            claim["service_ref"],
            claim["name"],
            claim["service_kind"],
            claim["tenant_domain"],
        )
    )


__all__ = [
    "SERVICE_DISCOVER_SCOPE",
    "SERVICE_INVOKE_SCOPE",
    "SERVICE_FEDERATION_SCOPES",
    "validate_federation_scope",
    "export_service_exposures",
    "peer_claim_fingerprint",
]
