"""M013 explicit, versioned API contract (the W046-era model
harvested onto the Architecture 1.1 surface).

The retained versioned-API-schema machinery with backward-
compatibility guarantees:

- **API versioning**: the version namespace is the route prefix
  ``/api/{version}/...``; every request must ALSO carry the
  ``X-ADCOS-API-Version`` header, and a disagreement between
  the route version and the header version is rejected
  deterministically (``version-unsupported``) so a client
  request is UNAMBIGUOUSLY attributable to exactly one API
  version.  The compatibility policy is the frozen table in
  :data:`VERSION_STATUS_POLICY`:

  ====================  ==========================================
  status                behavior
  ====================  ==========================================
  ``supported``         admitted normally
  ``deprecated``        admitted; every response carries a
                        deprecation notice (the sunset hint is
                        DATA for developers, never a silent
                        behavior change)
  ``retired``           rejected ``version-unsupported``
  anything else         rejected ``version-unsupported``
  ====================  ==========================================

- **Additive-change rules**: a resource schema may gain an
  OPTIONAL field within a compatible version lineage
  (classified ``ADDITIVE`` by :func:`classify_change`); clients
  of the older version keep validating (their payloads are a
  subset), and responses simply omit absent optional members.
  A field may be marked ``deprecated`` (classified
  ``DEPRECATION``): requests carrying it are still admitted and
  the response carries the deprecation notice, until removal --
  and removal itself is a BREAKING change requiring a new major
  version.

- **Breaking-change rules** (:func:`classify_change``): removing
  a field, renaming a field, changing its declared type, adding
  a REQUIRED field, or narrowing an optional field to required
  are all classified ``BREAKING`` and are FORBIDDEN within a
  compatible lineage -- :func:`assert_backward_compatible` is
  the mechanical gate the compatibility battery exercises (a
  breaking change fails closed; the checker is data, so the
  battery pins its verdicts on constructed schema pairs).

- **Strict request validation**: request payloads are validated
  against the request's OWN version schema set: unknown fields
  are rejected (fail closed, like every ADCOS boundary), types
  are checked exactly, and required members must be present.
  A v1.0-shaped payload therefore validates against the v1.1
  (additively evolved) schema set -- the live backward-
  compatibility proof.

- **Canonical serialization**: every response body serializes
  through the WORK-003 canonical JSON profile
  (:func:`protocol.canonicalization.canonical_json_bytes`), so
  identical logical responses produce byte-identical bodies
  (the determinism battery's substrate).

Resource schemas are DATA (field tables), not code paths: the
developer-facing resource shapes below cover the canonical
contract surface the Architecture 1.1 §12 developer-API
semantics name -- connectivity intents, accepted-offer
typed references, contract activation, termination, contract
leases, application credentials, and webhook endpoints.  The
ADAPTED resources (contract/lease projections) serialize from
the canonical contracts-domain records unchanged in meaning:
the boundary adds only the resource envelope (``kind``,
``environment``) -- it never re-shapes, renames, or re-semantics
canonical state (no second domain model).

M013 version policy (disclosed in docs/M013-evidence.md): the
2.0 major version carries the canonical Architecture 1.1
surface; the 1.x line is RETIRED (the schema module's own
gate classifies the 1.x -> 2.0 resource change as BREAKING --
removal of the commercial-plane members -- which requires a
new major version, and the 1.x backing bindings are superseded
by the accepted contracts domain); 0.9 stays deprecated with
its historical schema set (the retained machinery surfaces --
credentials, webhook endpoints -- remain admitted with the
deprecation notice); 0.8 stays retired.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, FrozenSet, List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import DeveloperApiError, DeveloperApiReasonCode

#: The current major API version line (the Architecture 1.1
#: canonical contract surface; see the module docstring for the
#: 1.x retirement disclosure).
API_VERSION_CURRENT = "2.0"

#: The header carrying the client-requested API version.
API_VERSION_HEADER = "X-ADCOS-API-Version"

#: The frozen version-status behavior policy (single site).
VERSION_STATUS_POLICY = {
    "supported": "admitted normally",
    "deprecated": "admitted with a deprecation notice on every response",
    "retired": "rejected deterministically (version-unsupported)",
}


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


# ---------------------------------------------------------------------------
# Resource schemas
# ---------------------------------------------------------------------------

#: The frozen field-type vocabulary (structural types only).
FIELD_TYPES = ("text", "integer", "boolean", "mapping", "list")


@dataclass(frozen=True)
class FieldSpec:
    """One declared resource field (structural contract member)."""

    name: str
    ftype: str
    required: bool = True
    deprecated: bool = False
    deprecation_note: str = ""

    def __post_init__(self) -> None:
        _require_text(self.name, "field name")
        if self.ftype not in FIELD_TYPES:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "field %r type %r must be one of %s"
                % (self.name, self.ftype, list(FIELD_TYPES)),
            )
        if self.deprecated and not self.deprecation_note:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "deprecated field %r must carry a deprecation note"
                % self.name,
            )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "name": self.name,
            "type": self.ftype,
            "required": self.required,
        }
        if self.deprecated:
            out["deprecated"] = True
            out["deprecation_note"] = self.deprecation_note
        return out


@dataclass(frozen=True)
class ResourceSchema:
    """One versioned resource contract (kind + field table)."""

    kind: str
    schema_version: str
    fields: Tuple[FieldSpec, ...]

    def __post_init__(self) -> None:
        _require_text(self.kind, "resource kind")
        _require_text(self.schema_version, "schema version")
        seen: Dict[str, FieldSpec] = {}
        for spec in self.fields:
            if not isinstance(spec, FieldSpec):
                raise DeveloperApiError(
                    DeveloperApiReasonCode.INVALID_INPUT,
                    "schema %r fields must be FieldSpec values" % self.kind,
                )
            if spec.name in seen:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.INVALID_INPUT,
                    "schema %r declares field %r twice" % (self.kind, spec.name),
                )
            seen[spec.name] = spec

    def field(self, name: str) -> FieldSpec:
        for spec in self.fields:
            if spec.name == name:
                return spec
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "schema %r has no field %r" % (self.kind, name),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
            "fields": [spec.to_dict() for spec in self.fields],
        }

    # -- request validation (strict, fail closed) ---------------------

    def validate(self, value: object, label: str) -> None:
        """Validate a request-side payload subset against this
        schema: unknown members rejected, declared types checked,
        required members present.  Optional members may be absent
        (additive lineages stay compatible)."""
        if not isinstance(value, Mapping):
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "%s must be a mapping" % label,
            )
        declared = {spec.name: spec for spec in self.fields}
        for key in sorted(value):
            if key not in declared:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.INVALID_INPUT,
                    "%s carries undeclared member %r (strict validation: "
                    "this API version's %s schema declares %s)"
                    % (label, key, self.kind, sorted(declared)),
                )
        for name in sorted(declared):
            spec = declared[name]
            if name not in value:
                if spec.required:
                    raise DeveloperApiError(
                        DeveloperApiReasonCode.INVALID_INPUT,
                        "%s is missing required member %r" % (label, name),
                    )
                continue
            member = value[name]
            if spec.ftype == "text":
                if not isinstance(member, str) or not member:
                    raise DeveloperApiError(
                        DeveloperApiReasonCode.INVALID_INPUT,
                        "%s member %r must be a non-empty string"
                        % (label, name),
                    )
            elif spec.ftype == "integer":
                if not isinstance(member, int) or isinstance(member, bool):
                    raise DeveloperApiError(
                        DeveloperApiReasonCode.INVALID_INPUT,
                        "%s member %r must be an integer" % (label, name),
                    )
            elif spec.ftype == "boolean":
                if not isinstance(member, bool):
                    raise DeveloperApiError(
                        DeveloperApiReasonCode.INVALID_INPUT,
                        "%s member %r must be a boolean" % (label, name),
                    )
            elif spec.ftype == "mapping":
                if not isinstance(member, Mapping):
                    raise DeveloperApiError(
                        DeveloperApiReasonCode.INVALID_INPUT,
                        "%s member %r must be a mapping" % (label, name),
                    )
            elif spec.ftype == "list":
                if not isinstance(member, (list, tuple)):
                    raise DeveloperApiError(
                        DeveloperApiReasonCode.INVALID_INPUT,
                        "%s member %r must be a list" % (label, name),
                    )

    def deprecations_in(self, value: Mapping[str, Any]) -> Tuple[str, ...]:
        """The deprecated members a payload carries (DATA for the
        response deprecation notice)."""
        return tuple(
            sorted(
                spec.name
                for spec in self.fields
                if spec.deprecated and spec.name in value
            )
        )


# ---------------------------------------------------------------------------
# The historical version-1.0 / 1.1 resource schema sets (the
# W046-era commercial-plane contract).  RETAINED AS DATA for the
# deprecated 0.9 line (the last pre-2.0 admitted version); the
# 1.0/1.1 versions themselves are RETIRED at the M013
# translation (their resource semantics -- offer publication,
# commercial intents/reservations, usage/billing reads,
# economic policies -- are demoted to the M003/M009 child
# domains per the migration matrix; the canonical surface is
# 2.0).  Disclosed in docs/M013-evidence.md.
# ---------------------------------------------------------------------------

_OFFER_FIELDS_V1 = (
    FieldSpec("name", "text"),
    FieldSpec("description", "text", required=False),
    FieldSpec("capacity_bps", "integer"),
    FieldSpec("pricing_currency", "text"),
    FieldSpec("pricing_amount", "integer"),
    FieldSpec("pricing_unit", "text"),
    FieldSpec("effective_from", "text"),
    FieldSpec("effective_until", "text"),
)

_WEBHOOK_ENDPOINT_FIELDS_V1 = (
    FieldSpec("url", "text"),
    FieldSpec("event_types", "list"),
)

#: The request-shape of the economic-policy registration: the
#: FROZEN WORK-046 1.x contract, byte-for-byte in members and
#: required-ness (policy_id + the integer version coordinate,
#: currency, exponent, rounding, the effective window with
#: effective_until OPTIONAL -- absent = the open-ended window --
#: adc_os_share_bps, tax_bps, and the developer-split bounds).
#:
#: WORK-056 re-binds the boundary's INTERNALS to the CURRENT
#: canonical W053 terms-derived immutable policy version, but
#: the developer-facing 1.0/1.1 request contract is PRESERVED
#: exactly: the gateway translates the 1.x members onto the
#: canonical register_policy terms (adc_os_share_bps ->
#: adcos_share_bps, developer_share_*_bps -> provider_*_bps,
#: rounding -> rounding_mode, exponent -> minor_unit_digits)
#: and carries the 1.x-only members (the (policy_id, version)
#: coordinates, tax_bps, the open-ended flag) inside the
#: canonical policy LABEL term (the label participates in the
#: canonical policy-id derivation, so distinct 1.x coordinates
#: remain distinct immutable versions and identical 1.x bodies
#: deduplicate canonically).  The 1.x member set is accepted,
#: validated, and projected back verbatim -- no silently
#: redefined 1.0/1.1 semantics.
_ECONOMIC_POLICY_FIELDS_V1 = (
    FieldSpec("policy_id", "text"),
    FieldSpec("version", "integer"),
    FieldSpec("currency", "text"),
    FieldSpec("exponent", "integer"),
    FieldSpec("rounding", "text"),
    FieldSpec("effective_from", "text"),
    FieldSpec("effective_until", "text", required=False),
    FieldSpec("adc_os_share_bps", "integer"),
    FieldSpec("tax_bps", "integer"),
    FieldSpec("developer_share_min_bps", "integer"),
    FieldSpec("developer_share_max_bps", "integer"),
)

_INTENT_REQUEST_FIELDS_V1 = (
    FieldSpec("intent", "mapping"),
    FieldSpec("offer_id", "text", required=False),
)

_RESERVATION_REQUEST_FIELDS_V1 = (
    FieldSpec("expires_at", "text"),
    FieldSpec("payment_refs", "list", required=False),
)

RESOURCE_SCHEMAS_V1: Dict[str, ResourceSchema] = {
    "offer": ResourceSchema("offer", "1.0", _OFFER_FIELDS_V1),
    "webhook_endpoint": ResourceSchema(
        "webhook_endpoint", "1.0", _WEBHOOK_ENDPOINT_FIELDS_V1
    ),
    "economic_policy": ResourceSchema(
        "economic_policy", "1.0", _ECONOMIC_POLICY_FIELDS_V1
    ),
    "intent_request": ResourceSchema(
        "intent_request", "1.0", _INTENT_REQUEST_FIELDS_V1
    ),
    "reservation_request": ResourceSchema(
        "reservation_request", "1.0", _RESERVATION_REQUEST_FIELDS_V1
    ),
}

#: The request-schema roles of the CURRENT canonical surface
#: (which schema validates which mutation body; the roles are
#: looked up per the request's OWN version schema set).
REQUEST_SCHEMA_ROLES = {
    "POST /intents": "intent_request",
    "POST /intents/{}/offers": "offer_selection",
    "POST /intents/{}/activation": "activation_request",
    "POST /contracts/{}/termination": "termination_request",
    "POST /contracts/{}/leases": "lease_request",
    "POST /leases/{}/renewal": "lease_renewal",
    "POST /leases/{}/revocation": "lease_revocation",
    "POST /webhook-endpoints": "webhook_endpoint",
}

#: The retained W046-era 1.x roles (historical data; the demoted
#: routes no longer dispatch, so these roles are unreachable on
#: the canonical route table).
REQUEST_SCHEMA_ROLES_V1 = {
    "POST /offers": "offer",
    "POST /webhook-endpoints": "webhook_endpoint",
    "POST /economic-policies": "economic_policy",
    "POST /intents": "intent_request",
    "POST /intents/{}/reservations": "reservation_request",
}

# ---------------------------------------------------------------------------
# The version-1.1 schema set: the historical ADDITIVE evolution
# of 1.0 (one optional field gained on the offer resource, one
# v1.0 field marked deprecated).  Retained as the compatibility
# machinery's demonstration lineage (the battery exercises the
# classification gate on these constructed pairs); the 1.1
# version itself is RETIRED at the M013 translation.
# ---------------------------------------------------------------------------

_OFFER_FIELDS_V1_1 = _OFFER_FIELDS_V1 + (
    FieldSpec(
        "region", "text", required=False
    ),
)
# mark pricing_unit deprecated in the 1.1 lineage
_OFFER_FIELDS_V1_1 = tuple(
    FieldSpec(
        "pricing_unit",
        "text",
        required=True,
        deprecated=True,
        deprecation_note=(
            "pricing_unit is deprecated in API version 1.1; express the "
            "unit inside pricing terms instead (removal requires a new "
            "major version)"
        ),
    )
    if spec.name == "pricing_unit"
    else spec
    for spec in _OFFER_FIELDS_V1_1
)

RESOURCE_SCHEMAS_V1_1: Dict[str, ResourceSchema] = dict(RESOURCE_SCHEMAS_V1)
RESOURCE_SCHEMAS_V1_1["offer"] = ResourceSchema("offer", "1.1", _OFFER_FIELDS_V1_1)


# ---------------------------------------------------------------------------
# The version-2.0 resource schema set: the canonical
# Architecture 1.1 contract surface (technology-neutral,
# LOCK-114).  Every request member is either structural
# metadata (the request-declared command instant, which makes
# the canonical command identity stable across idempotent
# retries) or canonical contract material delivered as OPAQUE
# TYPED REFERENCES (requirements, accepted offers, usage terms,
# assurance obligations, execution scope, signatures, the
# supersession link) -- the boundary never interprets another
# child domain's semantics (LOCK-102/LOCK-114: no network
# implementation objects, no second domain model).
# ---------------------------------------------------------------------------

#: The canonical intent-creation request: the technology-
#: neutral creation core of a connectivity contract (frozen
#: Architecture 1.1 §3).  ``recorded_at`` is the request-
#: declared command instant (retry-stable canonical identity);
#: every semantics-bearing member is canonical contract material
#: validated by the contracts domain itself.
_INTENT_REQUEST_FIELDS_V2 = (
    FieldSpec("requirements", "list"),
    FieldSpec("validity", "mapping"),
    FieldSpec("termination", "mapping"),
    FieldSpec("recorded_at", "text"),
    FieldSpec("hard_constraints", "list", required=False),
    FieldSpec("beneficiaries", "list", required=False),
    FieldSpec("service_properties", "list", required=False),
    FieldSpec("usage_pricing_terms", "mapping", required=False),
    FieldSpec("assurance_obligations", "list", required=False),
    FieldSpec("execution_scope", "list", required=False),
    FieldSpec("superseded_contract", "mapping", required=False),
)

#: The accepted-offer selection request: OFFERS SEMANTICS STAY
#: THE M003 AUTHORITY'S -- the request carries the accepted
#: offer references as opaque TYPED REFERENCES only
#: (``ref_kind: "offer"``); the boundary validates the reference
#: shape and passes it through; it never interprets, prices, or
#: re-models an offer.
_OFFER_SELECTION_FIELDS_V2 = (
    FieldSpec("offers", "list"),
    FieldSpec("recorded_at", "text"),
)

#: The contract activation request: the request-declared
#: activation instant (canonically validated against the
#: contract's validity interval) and the signature typed
#: references.
_ACTIVATION_REQUEST_FIELDS_V2 = (
    FieldSpec("activated_at", "text"),
    FieldSpec("signature_refs", "list"),
)

#: The contract termination request: the declared termination
#: condition (must be declared in the contract's termination
#: rules), the recorded reason, and the request-declared command
#: instant.
_TERMINATION_REQUEST_FIELDS_V2 = (
    FieldSpec("condition", "text"),
    FieldSpec("reason", "text"),
    FieldSpec("recorded_at", "text"),
)

#: The contract-scoped lease grant request: the request-declared
#: lease window (all three members canonically validated: the
#: window must lie inside the contract validity).
_LEASE_REQUEST_FIELDS_V2 = (
    FieldSpec("granted_at", "text"),
    FieldSpec("not_before", "text"),
    FieldSpec("not_after", "text"),
)

#: The lease renewal request: the successor lease window
#: (renewal creates a NEW lease record; the predecessor flips to
#: ``renewed`` -- the audit trail).
_LEASE_RENEWAL_FIELDS_V2 = (
    FieldSpec("granted_at", "text"),
    FieldSpec("not_before", "text"),
    FieldSpec("not_after", "text"),
)

#: The lease revocation request: the recorded reason and the
#: request-declared command instant.
_LEASE_REVOCATION_FIELDS_V2 = (
    FieldSpec("reason", "text"),
    FieldSpec("recorded_at", "text"),
)

#: The webhook-endpoint registration request (RETAINED VERBATIM
#: from the W046 1.x contract: url + event_types).
_WEBHOOK_ENDPOINT_FIELDS_V2 = (
    FieldSpec("url", "text"),
    FieldSpec("event_types", "list"),
)

RESOURCE_SCHEMAS_V2: Dict[str, ResourceSchema] = {
    "intent_request": ResourceSchema(
        "intent_request", "2.0", _INTENT_REQUEST_FIELDS_V2
    ),
    "offer_selection": ResourceSchema(
        "offer_selection", "2.0", _OFFER_SELECTION_FIELDS_V2
    ),
    "activation_request": ResourceSchema(
        "activation_request", "2.0", _ACTIVATION_REQUEST_FIELDS_V2
    ),
    "termination_request": ResourceSchema(
        "termination_request", "2.0", _TERMINATION_REQUEST_FIELDS_V2
    ),
    "lease_request": ResourceSchema(
        "lease_request", "2.0", _LEASE_REQUEST_FIELDS_V2
    ),
    "lease_renewal": ResourceSchema(
        "lease_renewal", "2.0", _LEASE_RENEWAL_FIELDS_V2
    ),
    "lease_revocation": ResourceSchema(
        "lease_revocation", "2.0", _LEASE_REVOCATION_FIELDS_V2
    ),
    "webhook_endpoint": ResourceSchema(
        "webhook_endpoint", "2.0", _WEBHOOK_ENDPOINT_FIELDS_V2
    ),
}


# ---------------------------------------------------------------------------
# API version registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApiVersionSpec:
    """One registered API version: status, notice, and the
    resource-schema set that version's requests validate
    against."""

    version: str
    status: str
    notice: str
    schemas: Mapping[str, ResourceSchema]

    def __post_init__(self) -> None:
        _require_text(self.version, "api version")
        if self.status not in VERSION_STATUS_POLICY:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "api version %r status %r must be one of %s"
                % (self.version, self.status, sorted(VERSION_STATUS_POLICY)),
            )
        if self.status == "deprecated" and not self.notice:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "deprecated api version %r must carry a notice"
                % self.version,
            )


#: The frozen registered API versions (single site; the M013
#: re-targeting disclosed in docs/M013-evidence.md: 2.0 is the
#: canonical Architecture 1.1 surface; the 1.x line is retired
#: with the honest migration notices; 0.9 remains deprecated
#: with its historical schema set; 0.8 remains retired).
API_VERSIONS: Dict[str, ApiVersionSpec] = {
    "2.0": ApiVersionSpec(
        version="2.0",
        status="supported",
        notice="",
        schemas=RESOURCE_SCHEMAS_V2,
    ),
    "1.1": ApiVersionSpec(
        version="1.1",
        status="retired",
        notice=(
            "API version 1.1 is retired at the M013 translation: the 1.x "
            "commercial-plane resource surface (offer publication, "
            "commercial intent/reservation projections, usage/billing "
            "reads, economic policies) is superseded by the Architecture "
            "1.1 canonical contract surface; migrate to 2.0"
        ),
        schemas=RESOURCE_SCHEMAS_V1_1,
    ),
    "1.0": ApiVersionSpec(
        version="1.0",
        status="retired",
        notice=(
            "API version 1.0 is retired at the M013 translation: the 1.x "
            "commercial-plane resource surface is superseded by the "
            "Architecture 1.1 canonical contract surface; migrate to 2.0"
        ),
        schemas=RESOURCE_SCHEMAS_V1,
    ),
    "0.9": ApiVersionSpec(
        version="0.9",
        status="deprecated",
        notice=(
            "API version 0.9 is deprecated: migrate to 2.0; 0.9 requests "
            "remain admitted with this notice until retirement (the "
            "retained machinery surfaces -- the application self read "
            "and webhook endpoints -- are shared; the 1.x-era commercial "
            "resource routes no longer dispatch)"
        ),
        schemas=RESOURCE_SCHEMAS_V1,
    ),
    "0.8": ApiVersionSpec(
        version="0.8",
        status="retired",
        notice="API version 0.8 is retired and rejected deterministically",
        schemas=RESOURCE_SCHEMAS_V1,
    ),
}


def resolve_version(version: object) -> ApiVersionSpec:
    """Resolve a requested API version (fail closed).

    Unknown versions are rejected deterministically with the
    frozen supported-version list in the detail (developer-
    actionable, never a guess)."""
    if not isinstance(version, str) or not version:
        raise DeveloperApiError(
            DeveloperApiReasonCode.VERSION_UNSUPPORTED,
            "api version must be a non-empty string (header %s or the "
            "/api/{version}/ route prefix); supported: %s"
            % (API_VERSION_HEADER, sorted(API_VERSIONS)),
        )
    spec = API_VERSIONS.get(version)
    if spec is None:
        raise DeveloperApiError(
            DeveloperApiReasonCode.VERSION_UNSUPPORTED,
            "api version %r is not registered; supported: %s"
            % (version, sorted(API_VERSIONS)),
        )
    if spec.status == "retired":
        raise DeveloperApiError(
            DeveloperApiReasonCode.VERSION_UNSUPPORTED,
            "api version %r is retired: %s" % (version, spec.notice),
        )
    return spec


# ---------------------------------------------------------------------------
# Backward-compatibility classification (the mechanical gate)
# ---------------------------------------------------------------------------

#: The classification vocabulary.
CHANGE_CLASSES = ("ADDITIVE", "DEPRECATION", "BREAKING")


def _field_map(schema: ResourceSchema) -> Dict[str, FieldSpec]:
    return {spec.name: spec for spec in schema.fields}


def classify_change(
    old: ResourceSchema, new: ResourceSchema
) -> Tuple[Tuple[str, str, str], ...]:
    """Classify every field difference between two versions of
    one resource schema.

    Returns the sorted list of (field, class, note) triples:

    - ``ADDITIVE``: an OPTIONAL field gained by ``new``;
    - ``DEPRECATION``: a field present in both, marked deprecated
      by ``new`` (structure otherwise unchanged);
    - ``BREAKING``: a field removed, renamed (i.e. a required
      member gone), retyped, gained as REQUIRED, or narrowed
      from optional to required.
    """
    if old.kind != new.kind:
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "cannot classify change across kinds %r and %r"
            % (old.kind, new.kind),
        )
    old_fields = _field_map(old)
    new_fields = _field_map(new)
    out: List[Tuple[str, str, str]] = []

    for name in sorted(set(old_fields) | set(new_fields)):
        before = old_fields.get(name)
        after = new_fields.get(name)
        if before is None and after is not None:
            if after.required:
                out.append(
                    (name, "BREAKING", "required member added")
                )
            else:
                out.append((name, "ADDITIVE", "optional member added"))
        elif before is not None and after is None:
            out.append((name, "BREAKING", "member removed"))
        else:
            assert before is not None and after is not None
            if before.ftype != after.ftype:
                out.append(
                    (name, "BREAKING", "type changed %s -> %s"
                     % (before.ftype, after.ftype))
                )
            elif before.required and not after.required:
                out.append((name, "ADDITIVE", "member relaxed to optional"))
            elif not before.required and after.required:
                out.append(
                    (name, "BREAKING", "member narrowed to required")
                )
            elif not before.deprecated and after.deprecated:
                out.append((name, "DEPRECATION", after.deprecation_note))
            else:
                continue
    out.sort()
    return tuple(out)


def assert_backward_compatible(
    old: ResourceSchema, new: ResourceSchema
) -> Tuple[Tuple[str, str, str], ...]:
    """Fail closed if any classified change is BREAKING.

    Returns the full classification (the compatibility evidence);
    raises ``invalid-input`` naming every breaking member (the
    gate the battery exercises with constructed breaking pairs).
    """
    classified = classify_change(old, new)
    breaking = [entry for entry in classified if entry[1] == "BREAKING"]
    if breaking:
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "schema change %s %s -> %s is BREAKING (requires a new major "
            "version): %s"
            % (
                old.kind,
                old.schema_version,
                new.schema_version,
                "; ".join("%s: %s" % (f, note) for f, _c, note in breaking),
            ),
        )
    return classified


# ---------------------------------------------------------------------------
# The response envelope (canonical serialization)
# ---------------------------------------------------------------------------

def canonical_response_bytes(body: Mapping[str, Any]) -> bytes:
    """Deterministic response serialization (WORK-003 profile).

    Identical logical responses produce byte-identical bodies --
    the substrate the idempotent-replay byte-equivalence and the
    hash-seed determinism proofs rely on."""
    return canonical_json_bytes(dict(body))
