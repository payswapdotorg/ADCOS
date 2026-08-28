"""ADCOS service registry / edge compute input validation (WORK-025).

Pure stdlib shape checks (mirrors the WORK-022/023/024 validation
discipline): every validator is fail-closed, performs an explicit
``isinstance`` check first (no duck typing), and normalizes nothing
silently.  Identity-carrying grammars are validated as DATA only --
this module never derives, stores, or reinterprets a NodeID
(WORK-004), a session id (WORK-012), a path fingerprint (WORK-011),
or a federation id (WORK-015).

Central identity-separation guarantees enforced here:

- a :class:`services.model.ServiceRef` never collides with any
  NodeID / session / path / resource / federation grammar (distinct
  root namespace, plus explicit separation asserts);
- external identifiers (endpoint references, provenance text) are
  DATA and are rejected outright when they masquerade as ADCOS
  identity grammars (ACCESS_SESSION_COLLAPSE);
- credential-like text is rejected in every free-text field
  (LOCK-023: no secret leakage).

NOTE: this module is the enforcement-vocabulary file; the selftest's
credential scan deliberately excludes it from its own scan (the
forbidden tokens below are rejection vocabulary, not secrets).
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from .errors import ServiceError, ServiceReasonCode

# ---- # Frozen grammar patterns --------------------------------------- #

#: Opaque service-layer reference kinds.  Every service-layer ref has
#: the shape ``services:<kind>:<32 lowercase hex>`` (leading 128 bits
#: of a SHA-256 digest over canonical identity material).
_OPAQUE_REF_KINDS = (
    "service", "decision", "admission", "allocation", "execution",
    "exposure",
)
_OPAQUE_REF_PATTERN = re.compile(
    r"^services:(service|decision|admission|allocation|execution|exposure):[0-9a-f]{32}$"
)

#: WORK-012 session ids and WORK-011 path fingerprints (DATA).
_SESSION_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

#: WORK-015 federation domain/relationship/grant ids (DATA).
_FEDERATION_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

#: WORK-004 NodeID grammar (DATA; never derived or reinterpreted here).
_NODE_ID_PATTERN = re.compile(
    r"^adcos:node:((?:[a-z0-9][a-z0-9-]*\.)+[a-z0-9][a-z0-9-]*):([0-9a-f]{64})$"
)

#: WORK-002 capability id grammar (open world: ``capability.core.*`` /
#: ``capability.profile.*``; unknown-but-well-formed ids are preserved).
_CAPABILITY_REF_PATTERN = re.compile(
    r"^capability\.(core|profile)(\.[a-z0-9][a-z0-9-]*)+$"
)

#: Free-text service name (printable ASCII, 1..64).
_SERVICE_NAME_PATTERN = re.compile(r"^[\x21-\x7e][\x20-\x7e]{0,63}$")

#: Tenant / authority domain label (printable ASCII, 1..64).
_TENANT_DOMAIN_PATTERN = re.compile(r"^[\x21-\x7e][\x20-\x7e]{0,63}$")

#: External endpoint reference (printable ASCII, 1..127) -- DATA.
_ENDPOINT_REF_PATTERN = re.compile(r"^[\x21-\x7e][\x20-\x7e]{0,127}$")

#: Locality / privacy / service label (printable ASCII, 1..64).
_LABEL_PATTERN = re.compile(r"^[\x21-\x7e][\x20-\x7e]{0,63}$")

#: RFC 3339 UTC instant (injected; no wall clock exists in this layer).
_INSTANT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
)

#: Separator runs collapsed for credential-like normalization.
_SEPARATOR_RUN = re.compile(r"[-_.\s]+")

# ---- # DATA-discipline rejection vocabularies ------------------------- #

#: Identifier prefixes that belong to other ADCOS grammars.  An
#: external identifier matching any of these raises
#: ACCESS_SESSION_COLLAPSE: external identifiers are DATA, never
#: identity (the WORK-021/022/023/024 discipline).
_EXTERNAL_ID_FORBIDDEN_PREFIXES = (
    "adcos:", "services:", "sha256:", "distcore:", "mesh:", "backhaul:",
    "wifi:", "fivegc:", "transport:", "ipint:", "capability:",
)

#: Credential-like tokens rejected in every free-text field.  Matched
#: against both the lowered text and a separator-normalized form so
#: ``shared_secret`` / ``shared-secret`` / ``shared.secret`` /
#: ``shared secret`` all fail closed (LOCK-023).
_CREDENTIAL_LIKE_FORBIDDEN = (
    "private_key", "secret_key", "password", "passphrase", "token",
    "api_key", "shared_secret", "community_string", "psk",
    "pre_shared_key", "preshared", "sim_pin", "session_key",
    "credential_value", "client_secret", "access_key", "signing_key",
    "hmac_key", "master_key", "root_password", "mgmt_secret",
    "service_password", "edge_secret", "runtime_secret",
)

#: WORK-008 consumable resource kinds the service layer may carry as
#: capacity DATA (cross-checked byte-for-byte against
#: ``resources.model.ResourceKind`` by the WORK-025 selftest; the
#: service layer reads the frozen vocabulary, never mints a second
#: one).
SERVICE_CAPACITY_KINDS: Tuple[str, ...] = (
    "compute", "storage", "bandwidth", "energy", "edge-service-capacity",
)


# ---- # Credential-like rejection -------------------------------------- #

def _normalized(text: str) -> str:
    return _SEPARATOR_RUN.sub("-", text.strip().lower())


def reject_credential_like_text(value: object, *, label: str = "text") -> str:
    """Validate free text and reject credential-like content.

    Both the lowered text and its separator-normalized form are
    matched against the frozen forbidden-token vocabulary, so
    ``shared_secret``, ``shared-secret``, ``shared.secret`` and
    ``shared secret`` all fail closed with INVALID_INPUT.
    """
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be a str (got %s)" % (label, type(value).__name__),
        )
    lowered = value.strip().lower()
    normalized = _normalized(value)
    for token in _CREDENTIAL_LIKE_FORBIDDEN:
        if token in lowered or _normalized(token) in normalized:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "%s must not carry credential-like content (LOCK-023: "
                "secrets never become service-registry DATA)" % (label,),
            )
    return value


# ---- # Identity / reference validators -------------------------------- #

def validate_opaque_ref(value: object, expected_kind: Optional[str] = None) -> str:
    """Validate a ``services:<kind>:<hex32>`` opaque reference."""
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "opaque ref must be a str (got %s)" % (type(value).__name__,),
        )
    if not _OPAQUE_REF_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "opaque ref %r does not match the frozen services grammar "
            "services:(%s):<32 lowercase hex>" % (value, "|".join(_OPAQUE_REF_KINDS)),
        )
    if expected_kind is not None:
        kind = value.split(":", 2)[1]
        if kind != expected_kind:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "opaque ref %r is of kind %r, expected %r"
                % (value, kind, expected_kind),
            )
    return value


def validate_session_ref(value: object) -> str:
    """Validate a WORK-012 session id (DATA; never reinterpreted)."""
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "session id must be a str (got %s)" % (type(value).__name__,),
        )
    if not _SESSION_REF_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "session id %r is not a canonical sha256 session reference "
            "(WORK-012 DATA)" % (value,),
        )
    return value


def validate_federation_ref(value: object, *, label: str = "federation id") -> str:
    """Validate a WORK-015 federation id (DATA; never reinterpreted)."""
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be a str (got %s)" % (label, type(value).__name__),
        )
    if not _FEDERATION_REF_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s %r is not a canonical sha256 federation reference "
            "(WORK-015 DATA)" % (label, value),
        )
    return value


def validate_node_id(value: object, *, label: str = "node id") -> str:
    """Validate a WORK-004 NodeID text form (DATA; never derived from
    or collapsed onto a service identity)."""
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be a str (got %s)" % (label, type(value).__name__),
        )
    if not _NODE_ID_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s %r is not a canonical adcos:node:<profile>:<64 hex> "
            "NodeID (WORK-004 DATA)" % (label, value),
        )
    return value


def validate_capability_ref(value: object) -> str:
    """Validate a WORK-002 capability id (open-world grammar)."""
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "capability ref must be a str (got %s)" % (type(value).__name__,),
        )
    if not _CAPABILITY_REF_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "capability ref %r does not match the frozen WORK-002 "
            "capability.(core|profile).* grammar" % (value,),
        )
    return value


# ---- # Free-text validators (DATA discipline) -------------------------- #

def validate_service_name(value: object) -> str:
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "service name must be a str (got %s)" % (type(value).__name__,),
        )
    if not _SERVICE_NAME_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "service name %r must be 1..64 printable ASCII characters" % (value,),
        )
    return reject_credential_like_text(value, label="service name")


def validate_tenant_domain(value: object) -> str:
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "tenant domain must be a str (got %s)" % (type(value).__name__,),
        )
    if not _TENANT_DOMAIN_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "tenant domain %r must be 1..64 printable ASCII characters" % (value,),
        )
    return reject_credential_like_text(value, label="tenant domain")


def validate_endpoint_ref(value: object) -> str:
    """Validate an external endpoint reference (optional: the empty
    string means the advertisement carries no endpoint reference
    yet).  Endpoint references are external DATA: any ADCOS identity
    grammar embedded in them is rejected outright (external
    identifiers are DATA, never identity)."""
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "endpoint ref must be a str (got %s)" % (type(value).__name__,),
        )
    if value == "":
        return value
    if not _ENDPOINT_REF_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "endpoint ref %r must be 1..127 printable ASCII characters" % (value,),
        )
    lowered = value.lower()
    for prefix in _EXTERNAL_ID_FORBIDDEN_PREFIXES:
        if lowered.startswith(prefix):
            raise ServiceError(
                ServiceReasonCode.ACCESS_SESSION_COLLAPSE,
                "endpoint ref %r embeds the ADCOS identity grammar %r -- "
                "external identifiers are DATA, never identity"
                % (value, prefix),
            )
    return reject_credential_like_text(value, label="endpoint ref")


def validate_label(value: object, *, label: str = "label") -> str:
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be a str (got %s)" % (label, type(value).__name__),
        )
    if not _LABEL_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s %r must be 1..64 printable ASCII characters" % (label, value),
        )
    return reject_credential_like_text(value, label=label)


# ---- # Vocabulary validators ------------------------------------------- #

def validate_service_kind(value: object) -> str:
    from .model import ServiceKind

    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "service kind must be a str (got %s)" % (type(value).__name__,),
        )
    if value not in ServiceKind.values():
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "service kind %r is not in the frozen service-kind "
            "vocabulary %s" % (value, ServiceKind.values()),
        )
    return value


def validate_visibility(value: object) -> str:
    from .model import VisibilityScope

    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "visibility must be a str (got %s)" % (type(value).__name__,),
        )
    if value not in VisibilityScope.values():
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "visibility %r is not in the frozen visibility vocabulary %s"
            % (value, VisibilityScope.values()),
        )
    return value


def validate_evidence_source(value: object) -> str:
    from .model import EvidenceSourceClass

    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "evidence source must be a str (got %s)" % (type(value).__name__,),
        )
    if value not in EvidenceSourceClass.values():
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "evidence source %r is not in the frozen evidence-source "
            "vocabulary %s" % (value, EvidenceSourceClass.values()),
        )
    return value


def validate_capacity_kind(value: object) -> str:
    """Validate a service-capacity kind against the frozen
    WORK-008-consumable kind set (DATA; the resource vocabulary
    remains WORK-008 -- no second registry is minted)."""
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "capacity kind must be a str (got %s)" % (type(value).__name__,),
        )
    if value not in SERVICE_CAPACITY_KINDS:
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "capacity kind %r is not a WORK-008 consumable resource kind "
            "carried by the service layer (known: %s)"
            % (value, SERVICE_CAPACITY_KINDS),
        )
    return value


def validate_capacity_quantity(value: object, *, label: str = "quantity_base") -> int:
    """Validate a base-unit capacity quantity.  Zero is a VALID
    declaration that contributes NO allocatable capacity (the WORK-022
    lesson: existence of a service record is not evidence that its
    resource reservation exists)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be an int (got %s)" % (label, type(value).__name__),
        )
    if value < 0 or value > 2 ** 40:
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be within 0..2^40 base units (got %d)" % (label, value),
        )
    return value


# ---- # Digest / instant validators ------------------------------------- #

def validate_claim_digest(value: object) -> str:
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "claim digest must be a str (got %s)" % (type(value).__name__,),
        )
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "claim digest %r must be 64 lowercase hex characters" % (value,),
        )
    return value


def validate_policy_decision_id(value: object) -> str:
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "policy decision id must be a str (got %s)" % (type(value).__name__,),
        )
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "policy decision id %r must be 64 lowercase hex characters"
            % (value,),
        )
    return value


def validate_instant(value: object, *, label: str = "instant") -> str:
    if not isinstance(value, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be a str (got %s)" % (label, type(value).__name__),
        )
    if not _INSTANT_PATTERN.fullmatch(value):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s %r must be an RFC 3339 UTC instant (injected; no wall "
            "clock exists in this layer)" % (label, value),
        )
    return value


# ---- # Identity-separation asserts ------------------------------------- #

def _hex_fragments(value: str, *, size: int) -> Tuple[str, ...]:
    text = value.lower()
    digest = text.rsplit(":", 1)[-1]
    return tuple(
        digest[i: i + size] for i in range(0, max(0, len(digest) - size + 1))
    )


def assert_ref_session_separation(ref: str, session_id: str) -> None:
    """Assert that an opaque service-layer ref and a session id share
    no hex fragment (16+ characters): a service-layer ref must never
    be derived from or collapsed onto session identity (the WORK-025
    central identity rule)."""
    if not session_id:
        return
    ref_frags = _hex_fragments(ref, size=16)
    session_frags = set(_hex_fragments(session_id, size=16))
    for frag in ref_frags:
        if frag and frag in session_frags:
            raise ServiceError(
                ServiceReasonCode.ACCESS_SESSION_COLLAPSE,
                "service-layer ref %r shares identity material with "
                "session id -- service identity is distinct from session "
                "identity (WORK-025 invariant 1)" % (ref,),
            )


def assert_service_node_separation(service_ref: str, node_id: str) -> None:
    """Assert that a service ref and a NodeID share no hex fragment
    (16+ characters): a service reference must never be derived from
    or collapsed onto a node identity (WORK-025 invariant 1; the
    service may move between edge nodes without becoming a different
    service identity)."""
    if not node_id:
        return
    ref_frags = _hex_fragments(service_ref, size=16)
    node_frags = set(_hex_fragments(node_id, size=16))
    for frag in ref_frags:
        if frag and frag in node_frags:
            raise ServiceError(
                ServiceReasonCode.ACCESS_SESSION_COLLAPSE,
                "service ref %r shares identity material with node id "
                "-- service identity is distinct from node identity "
                "(WORK-025 invariant 1)" % (service_ref,),
            )


__all__ = [
    "SERVICE_CAPACITY_KINDS",
    "reject_credential_like_text",
    "validate_opaque_ref",
    "validate_session_ref",
    "validate_federation_ref",
    "validate_node_id",
    "validate_capability_ref",
    "validate_service_name",
    "validate_tenant_domain",
    "validate_endpoint_ref",
    "validate_label",
    "validate_service_kind",
    "validate_visibility",
    "validate_evidence_source",
    "validate_capacity_kind",
    "validate_capacity_quantity",
    "validate_claim_digest",
    "validate_policy_decision_id",
    "validate_instant",
    "assert_ref_session_separation",
    "assert_service_node_separation",
]
