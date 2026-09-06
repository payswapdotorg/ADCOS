"""ADCOS adapter certification records (WORK-057).

Provider onboarding consumes the WORK-016 adapter boundary through
this module ONLY as data: an operator's declared access/provider
adapter is bound to certification evidence without importing any
provider implementation semantics into core authorities.

Authority boundaries (the layering contract):

- **The adapter contract stays WORK-016.** ``AdapterDescriptor``
  validation (id grammar, registry-known access technology, profile
  versions, capability reference classification, security state,
  LOCK-023 secret rejection) is the existing
  ``adapters.model``/``adapters.validation`` surface; certification
  re-uses it and never re-implements it.
- **Certification is evidence, not trust.** A certified adapter is
  NOT a healthy adapter and NOT node-level trust: the verdict only
  records that an explicit declaration was bound to explicit
  evidence. ``AdapterRuntime.health`` remains the only health
  authority and federation membership remains the only inter-domain
  trust authority.
- **Vendor isolation (LOCK-017).** The certification record carries
  adapter ids, digests, and opaque evidence references only. No
  vendor SDK type, no implementation object, and no access-technology
  branch ever enters this module. Family packages
  (``adapters.ran``, ``adapters.wifi``, ...) are never imported here.
- **No new authority.** This module creates no identity, capability,
  resource, session, routing, transport, usage, payment, settlement,
  or policy authority.

Determinism: content-derived ids over canonical JSON (WORK-003 house
style: empty at construction means "derive it"; a supplied non-empty
id MUST match the derived fingerprint -- tamper evidence at
construction AND deserialization); injected RFC 3339 UTC instants
only; no wall-clock, no randomness, no UUIDs, no network; sorted
iteration everywhere (PYTHONHASHSEED-safe); floats rejected by the
canonical serializer.

Secrets: LOCK-023-style recursive key scan at construction; values
are never echoed in errors.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from .model import AdapterDescriptor
from .validation import validate_adapter_id, validate_access_technology_id

# ----------------------------------------------------------------------
# Reason vocabulary (certification-local; adding a value is a
# deliberate vocabulary change on this WORK-057 surface)
# ----------------------------------------------------------------------


class CertificationCode:
    CERTIFIED = "certified"
    NOT_ATTESTED = "not-attested"
    EVIDENCE_MISSING = "evidence-missing"
    INVALID_INPUT = "invalid-input"
    SECRET_MATERIAL = "secret-material"
    ACCESS_TECHNOLOGY_LEAKAGE = "access-technology-leakage"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.CERTIFIED,
            cls.NOT_ATTESTED,
            cls.EVIDENCE_MISSING,
            cls.INVALID_INPUT,
            cls.SECRET_MATERIAL,
            cls.ACCESS_TECHNOLOGY_LEAKAGE,
        )


class AdapterCertificationError(ValueError):
    """Fail-closed certification error with a stable machine-readable
    ``code`` and deterministic ``detail`` (no secret material is ever
    echoed)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# ----------------------------------------------------------------------
# Leakage guards (repo-convention local copies; free text only --
# validated adapter ids and access-technology ids legitimately carry
# their own grammar and are never scanned here)
# ----------------------------------------------------------------------

_SECRET_HINTS = (
    "private_key",
    "secret_key",
    "priv_key",
    "password",
    "token",
    "credential_secret",
    "subscriber_secret",
    "modem_secret",
)

_FORBIDDEN_TOKENS = (
    "5g",
    "6g",
    "nr",
    "lte",
    "wifi",
    "wi-fi",
    "3g",
    "4g",
    "cellular",
    "satellite",
    "mesh",
    "fiber",
    "ethernet",
    "vendor",
    "ran",
    "cn",
    "bearer",
    "apn",
    "imsi",
    "imei",
    "ssid",
    "gnb",
    "enb",
    "n3iwf",
    "quic",
    "tls",
    "chipset",
)

_FORBIDDEN_PATTERNS = tuple(
    re.compile(r"(?:^|[^a-z0-9])%s(?:$|[^a-z0-9])" % re.escape(token))
    for token in _FORBIDDEN_TOKENS
)


def _reject_secret_material(document: object, label: str) -> None:
    if isinstance(document, Mapping):
        for key, value in document.items():
            key_text = key if isinstance(key, str) else str(key)
            if any(hint in key_text.lower() for hint in _SECRET_HINTS):
                raise AdapterCertificationError(
                    CertificationCode.SECRET_MATERIAL,
                    "%s: mapping key %r looks like secret material" % (label, key_text),
                )
            _reject_secret_material(value, label)
    elif isinstance(document, (list, tuple)):
        for item in document:
            _reject_secret_material(item, label)


def _reject_forbidden_tokens(value: str, label: str) -> None:
    lowered = value.lower()
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(lowered) is not None:
            raise AdapterCertificationError(
                CertificationCode.ACCESS_TECHNOLOGY_LEAKAGE,
                "%s: forbidden access-technology/vendor token in free text" % label,
            )


def _validate_free_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT, "%s must be a string" % label
        )
    if not value:
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT, "%s must be non-empty" % label
        )
    if len(value) > 256:
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT, "%s exceeds 256 characters" % label
        )
    _reject_forbidden_tokens(value, label)
    return value


def _validate_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT, "%s: %s" % (label, error)
        ) from None
    return value


def _validate_string_refs(refs: object, label: str) -> Tuple[str, ...]:
    if not isinstance(refs, tuple):
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT, "%s must be a tuple" % label
        )
    seen = set()
    for item in refs:
        if not isinstance(item, str) or not item:
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT, "%s entries must be non-empty strings" % label
            )
        if len(item) > 256:
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT, "%s entries exceed 256 characters" % label
            )
        seen.add(item)
    return tuple(sorted(seen))


# ----------------------------------------------------------------------
# Descriptor digest (canonical over the public declaration surface)
# ----------------------------------------------------------------------


def descriptor_document(descriptor: AdapterDescriptor) -> Dict[str, Any]:
    """Canonical JSON-safe document of the descriptor's public
    declaration surface (the frozen section 6.3 MUST-expose list).
    The digest of this document is what a certification binds -- the
    certification never holds the descriptor object itself (vendor
    isolation: the record survives even if implementation objects do
    not)."""
    if not isinstance(descriptor, AdapterDescriptor):
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT,
            "descriptor must be an AdapterDescriptor (the WORK-016 declaration object)",
        )
    security_state = descriptor.security_state
    document: Dict[str, Any] = {
        "adapter_id": descriptor.adapter_id,
        "access_technology_id": descriptor.access_technology_id,
        "supported_profile_versions": sorted(descriptor.supported_profile_versions),
        "capabilities": sorted(descriptor.capabilities),
        "security_state": {
            "profile": security_state.profile,
            "credential_slots": sorted(security_state.credential_slots),
            "attested": bool(security_state.attested),
        },
        "resource_mapping": [
            {
                "technology_resource": entry.technology_resource,
                "kind": entry.kind,
                "unit": entry.unit,
                "quantity": entry.quantity,
                "availability": entry.availability,
            }
            for entry in sorted(
                descriptor.resource_mapping,
                key=lambda entry: (
                    entry.technology_resource,
                    entry.kind,
                    entry.unit,
                    entry.quantity,
                    entry.availability,
                ),
            )
        ],
    }
    _reject_secret_material(document, "descriptor document")
    return document


def descriptor_digest(descriptor: AdapterDescriptor) -> str:
    """Content-derived digest (``sha256:<hex>``) over the descriptor's
    canonical public declaration document."""
    document = descriptor_document(descriptor)
    try:
        digest = hashlib.sha256(canonical_json_bytes(document)).hexdigest()
    except CanonicalizationError as error:
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT,
            "descriptor document is not canonicalizable: %s" % (error,),
        ) from None
    return "sha256:" + digest


# ----------------------------------------------------------------------
# AdapterCertification
# ----------------------------------------------------------------------

_CERTIFICATION_KIND = "adcos:adapter-certification"


@dataclass(frozen=True)
class AdapterCertification:
    """One immutable adapter declaration certification record.

    The record binds (operator, adapter declaration, evidence) into a
    tamper-evident artifact for the onboarding lifecycle. It creates
    no authority: a certified adapter is a declared adapter with
    evidence, nothing more (LOCK-008 discipline -- evidence is a
    claim about a declaration, never topology truth; health and
    inter-domain trust remain with their owning authorities).
    """

    certification_id: str
    adapter_id: str
    access_technology_id: str
    descriptor_digest: str
    provider_node_id: str
    provider_operator_reference: str
    supported_profile_versions: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    attested: bool
    evidence_refs: Tuple[str, ...]
    certified_at: str
    valid_from: str
    valid_until: str
    verdict: str
    reason_code: str
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.certification_id, str):
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT, "certification_id must be a string"
            )
        expected = _derive_certification_id(self._content_document())
        if self.certification_id == "":
            object.__setattr__(self, "certification_id", expected)
        elif self.certification_id != expected:
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT,
                "certification id %r does not match the content-derived identity %r"
                % (self.certification_id, expected),
            )
        if self.verdict not in ("certified", "rejected"):
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT,
                "verdict %r must be 'certified' or 'rejected'" % (self.verdict,),
            )
        if self.reason_code not in CertificationCode.values():
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT,
                "reason code %r is not a certification reason" % (self.reason_code,),
            )
        _validate_free_text(self.provider_operator_reference, "provider_operator_reference")
        _validate_free_text(self.detail, "detail")
        validate_adapter_id(self.adapter_id)
        validate_access_technology_id(self.access_technology_id)
        for instant_label, instant_value in (
            ("certified_at", self.certified_at),
            ("valid_from", self.valid_from),
            ("valid_until", self.valid_until),
        ):
            _validate_instant(instant_value, instant_label)
        if self.valid_until < self.valid_from:
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT,
                "valid_until must not precede valid_from",
            )
        # provider_node_id is an OPERATOR REFERENCE consumed by the
        # onboarding layer (which binds it against the application's
        # canonical WORK-004 operator NodeID by equality); the adapters
        # package validates only its shape here (the adapters import
        # boundary is protocol/capabilities/sessions/resources only).
        _validate_free_text(self.provider_node_id, "provider_node_id")
        for string_field in (
            "supported_profile_versions",
            "capabilities",
            "evidence_refs",
        ):
            value = getattr(self, string_field)
            if not isinstance(value, tuple):
                raise AdapterCertificationError(
                    CertificationCode.INVALID_INPUT, "%s must be a tuple" % string_field
                )
            for item in value:
                if not isinstance(item, str) or not item:
                    raise AdapterCertificationError(
                        CertificationCode.INVALID_INPUT,
                        "%s entries must be non-empty strings" % string_field,
                    )
        object.__setattr__(
            self, "evidence_refs", _validate_string_refs(self.evidence_refs, "evidence_refs")
        )

    # -- identity -----------------------------------------------------

    def _content_document(self) -> Dict[str, Any]:
        return {
            "certification_kind": _CERTIFICATION_KIND,
            "adapter_id": self.adapter_id,
            "access_technology_id": self.access_technology_id,
            "descriptor_digest": self.descriptor_digest,
            "provider_node_id": self.provider_node_id,
            "provider_operator_reference": self.provider_operator_reference,
            "supported_profile_versions": sorted(self.supported_profile_versions),
            "capabilities": sorted(self.capabilities),
            "attested": self.attested,
            "evidence_refs": list(self.evidence_refs),
            "certified_at": self.certified_at,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }

    def to_dict(self) -> Dict[str, Any]:
        document = self._content_document()
        document["certification_id"] = self.certification_id
        return document

    @classmethod
    def from_mapping(cls, data: object) -> "AdapterCertification":
        if not isinstance(data, Mapping):
            raise AdapterCertificationError(
                CertificationCode.INVALID_INPUT, "certification record must be a mapping"
            )
        required = (
            "adapter_id",
            "access_technology_id",
            "descriptor_digest",
            "provider_node_id",
            "provider_operator_reference",
            "certified_at",
            "valid_from",
            "valid_until",
            "verdict",
            "reason_code",
            "detail",
        )
        for member in required:
            if member not in data:
                raise AdapterCertificationError(
                    CertificationCode.INVALID_INPUT,
                    "certification record member %r is required" % (member,),
                )
        _reject_secret_material(dict(data), "certification record")
        return cls(
            certification_id=data.get("certification_id", ""),
            adapter_id=data["adapter_id"],
            access_technology_id=data["access_technology_id"],
            descriptor_digest=data["descriptor_digest"],
            provider_node_id=data["provider_node_id"],
            provider_operator_reference=data["provider_operator_reference"],
            supported_profile_versions=tuple(data.get("supported_profile_versions", ())),
            capabilities=tuple(data.get("capabilities", ())),
            attested=bool(data.get("attested", False)),
            evidence_refs=tuple(data.get("evidence_refs", ())),
            certified_at=data["certified_at"],
            valid_from=data["valid_from"],
            valid_until=data["valid_until"],
            verdict=data["verdict"],
            reason_code=data["reason_code"],
            detail=data["detail"],
        )

    # -- validity -----------------------------------------------------

    def is_certified(self) -> bool:
        return self.verdict == "certified"

    def validity_at(self, evaluation_instant: str) -> bool:
        """Evaluated (never observed) validity window at an injected
        instant -- inclusive at both ends, exactly like the resource
        and federation validity discipline."""
        instant = _validate_instant(evaluation_instant, "evaluation_instant")
        return self.valid_from <= instant <= self.valid_until


def _derive_certification_id(document: Mapping[str, Any]) -> str:
    try:
        digest = hashlib.sha256(canonical_json_bytes(dict(document))).hexdigest()
    except CanonicalizationError as error:
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT,
            "certification content is not canonicalizable: %s" % (error,),
        ) from None
    return "sha256:" + digest


# ----------------------------------------------------------------------
# Certification evaluation (fail closed)
# ----------------------------------------------------------------------


def certify_adapter_descriptor(
    *,
    descriptor: AdapterDescriptor,
    provider_node_id: str,
    evidence_refs: Tuple[str, ...],
    certified_at: str,
    valid_from: str,
    valid_until: str,
    provider_operator_reference: str,
) -> AdapterCertification:
    """Bind one declared adapter to certification evidence.

    Fail-closed certification requirements (the smallest coherent
    set):

    - the declaration is a genuinely validated WORK-016
      ``AdapterDescriptor`` (grammar + registry + classification +
      security state enforced by the existing authority);
    - the declaring operator is a canonical NodeID holder (the
      certification binds the operator, never a node-trust claim);
    - the security state is attested (``attested`` is the declared
      attestation fact carried as data);
    - the evidence reference list is non-empty (a certification
      without evidence is not a certification);
    - free text carries no access-technology/vendor tokens and no
      secret-shaped material (LOCK-023 house discipline).

    The verdict is deterministic over the inputs; a rejected
    declaration still produces a tamper-evident record (auditability:
    adversarial attempts are recorded, never silently dropped).
    """
    if not isinstance(descriptor, AdapterDescriptor):
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT,
            "descriptor must be an AdapterDescriptor (the WORK-016 declaration object)",
        )
    validate_adapter_id(descriptor.adapter_id)
    validate_access_technology_id(descriptor.access_technology_id)

    operator_reference = _validate_free_text(
        provider_operator_reference, "provider_operator_reference"
    )
    operator_reference_id = _validate_free_text(provider_node_id, "provider_node_id")
    evidence = _validate_string_refs(evidence_refs, "evidence_refs")

    digest = descriptor_digest(descriptor)
    security_state = descriptor.security_state
    attested = bool(security_state.attested)

    for instant_label, instant_value in (
        ("certified_at", certified_at),
        ("valid_from", valid_from),
        ("valid_until", valid_until),
    ):
        _validate_instant(instant_value, instant_label)
    if valid_until < valid_from:
        raise AdapterCertificationError(
            CertificationCode.INVALID_INPUT, "valid_until must not precede valid_from"
        )

    if not attested:
        verdict = "rejected"
        reason = CertificationCode.NOT_ATTESTED
        detail = (
            "adapter declaration is not attested (declared attestation is "
            "required for certification)"
        )
    elif not evidence:
        verdict = "rejected"
        reason = CertificationCode.EVIDENCE_MISSING
        detail = (
            "adapter declaration carries no evidence references "
            "(certification requires explicit evidence)"
        )
    else:
        verdict = "certified"
        reason = CertificationCode.CERTIFIED
        detail = (
            "adapter declaration bound to %d evidence reference(s) by the "
            "declaring operator (evidence is a claim about a declaration, never "
            "topology truth)"
            % (len(evidence),)
        )

    return AdapterCertification(
        certification_id="",
        adapter_id=descriptor.adapter_id,
        access_technology_id=descriptor.access_technology_id,
        descriptor_digest=digest,
        provider_node_id=operator_reference_id,
        provider_operator_reference=operator_reference,
        supported_profile_versions=tuple(sorted(descriptor.supported_profile_versions)),
        capabilities=tuple(sorted(descriptor.capabilities)),
        attested=attested,
        evidence_refs=evidence,
        certified_at=certified_at,
        valid_from=valid_from,
        valid_until=valid_until,
        verdict=verdict,
        reason_code=reason,
        detail=detail,
    )


def certification_from_mapping(data: object) -> AdapterCertification:
    """Fail-closed wire construction (alias of
    ``AdapterCertification.from_mapping``)."""
    return AdapterCertification.from_mapping(data)


__all__ = [
    "AdapterCertificationError",
    "AdapterCertification",
    "CertificationCode",
    "certification_from_mapping",
    "certify_adapter_descriptor",
    "descriptor_digest",
    "descriptor_document",
]
