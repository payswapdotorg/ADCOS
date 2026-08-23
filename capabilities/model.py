"""Capability statement model (frozen architecture section 6.4).

A CapabilityStatement is a signed, versioned CLAIM about what a node or
adapter may provide. Field set per frozen section 6.4: capability_id,
schema_version, provider_identity, validity interval, parameters,
constraints, evidence references, signature. Withdrawal state is carried
explicitly (withdrawn_at) and is covered by the signature.

Parameters and constraints are open-world typed data (any JSON object);
they never carry technology-specific core semantics. Evidence references
are opaque strings — references, never topology authority (LOCK-008).
The signature is opaque metadata; signing/verification flows through the
WORK-004 provider seam and WORK-003 canonical input machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional, Tuple

from protocol.temporal import TemporalError, parse_instant

from .classification import CapabilityIdClass, classify_capability_id
from .validity import validate_validity


class CapabilityError(ValueError):
    """Raised when a capability statement violates its contract (fail
    closed). ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


SCHEMA_VERSION_PATTERN = "^[0-9]+\\.[0-9]+$"


@dataclass(frozen=True)
class CapabilityStatement:
    """A capability advertisement claim (frozen section 6.4 field set)."""

    capability_id: str
    schema_version: str
    provider_identity: str
    valid_from: str
    expires_at: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    constraints: Mapping[str, Any] = field(default_factory=dict)
    evidence_references: Tuple[str, ...] = ()
    signature: str = ""
    withdrawn_at: Optional[str] = None

    def __post_init__(self) -> None:
        classification = classify_capability_id(self.capability_id)
        if classification == CapabilityIdClass.INVALID:
            raise CapabilityError(
                "capability-id",
                "capability_id %r is malformed (fails the registry grammar) "
                "— malformed identifiers fail closed" % self.capability_id,
            )
        if not isinstance(self.schema_version, str):
            raise CapabilityError("schema-version", "schema_version must be a string")
        import re

        if re.fullmatch(SCHEMA_VERSION_PATTERN, self.schema_version) is None:
            raise CapabilityError(
                "schema-version",
                "schema_version %r must be MAJOR.MINOR" % self.schema_version,
            )
        if not isinstance(self.provider_identity, str) or not self.provider_identity:
            raise CapabilityError("provider-identity", "provider_identity must be a non-empty string")
        try:
            validate_validity(self.valid_from, self.expires_at)
        except Exception as error:
            raise CapabilityError("validity", str(error)) from error
        if not isinstance(self.parameters, Mapping):
            raise CapabilityError("parameters", "parameters must be an object")
        if not isinstance(self.constraints, Mapping):
            raise CapabilityError("constraints", "constraints must be an object")
        for reference in self.evidence_references:
            if not isinstance(reference, str) or not reference:
                raise CapabilityError(
                    "evidence", "evidence references must be non-empty strings"
                )
        if not isinstance(self.signature, str):
            raise CapabilityError("signature", "signature must be an opaque string")
        if self.withdrawn_at is not None:
            try:
                parse_instant(self.withdrawn_at)
            except TemporalError as error:
                raise CapabilityError("withdrawn-at", str(error)) from error

    @property
    def id_classification(self) -> str:
        return classify_capability_id(self.capability_id)

    def withdraw(self, withdrawn_at: str) -> "CapabilityStatement":
        """Return a withdrawn copy (explicit act; timestamp covered by
        re-signing through the provider seam)."""
        try:
            parse_instant(withdrawn_at)
        except TemporalError as error:
            raise CapabilityError("withdrawn-at", str(error)) from error
        return replace(self, withdrawn_at=withdrawn_at)

    def to_dict(self) -> dict:
        """Serialize to the WORK-002 capability.schema.json field shape:
        the validity interval nests under ``validity`` (frozen section 6.4
        semantics; schema compatibility is asserted by the self-test)."""
        validity: dict = {
            "valid_from": self.valid_from,
            "expires_at": self.expires_at,
        }
        if self.withdrawn_at is not None:
            validity["withdrawn_at"] = self.withdrawn_at
        return {
            "capability_id": self.capability_id,
            "schema_version": self.schema_version,
            "provider_identity": self.provider_identity,
            "validity": validity,
            "parameters": dict(self.parameters),
            "constraints": dict(self.constraints),
            "evidence_references": list(self.evidence_references),
            "signature": self.signature,
        }

    def __repr__(self) -> str:
        return (
            "CapabilityStatement(capability_id=%r, schema_version=%r, "
            "provider_identity=%r, classification=%s)"
            % (
                self.capability_id,
                self.schema_version,
                self.provider_identity[:24] + ("…" if len(self.provider_identity) > 24 else ""),
                self.id_classification,
            )
        )


def statement_from_mapping(data: object) -> CapabilityStatement:
    """Build a statement from a mapping, failing closed on every
    contract violation (missing members, wrong types, malformed IDs,
    impossible validity)."""
    if not isinstance(data, Mapping):
        raise CapabilityError("statement", "capability statement must be a JSON object")
    required = (
        "capability_id",
        "schema_version",
        "provider_identity",
        "validity",
        "parameters",
        "constraints",
        "evidence_references",
        "signature",
    )
    for member in required:
        if member not in data:
            raise CapabilityError("missing", "required member %r is absent" % member)
    evidence = data["evidence_references"]
    if not isinstance(evidence, list):
        raise CapabilityError("evidence", "evidence_references must be an array")
    validity = data.get("validity")
    if not isinstance(validity, Mapping):
        raise CapabilityError("validity", "validity must be an object with valid_from/expires_at")
    valid_from = validity.get("valid_from")
    expires_at = validity.get("expires_at")
    if not isinstance(valid_from, str) or not isinstance(expires_at, str):
        raise CapabilityError("validity", "validity requires string valid_from and expires_at")
    withdrawn_at = validity.get("withdrawn_at")
    if withdrawn_at is not None and not isinstance(withdrawn_at, str):
        raise CapabilityError("validity", "withdrawn_at must be a string when present")
    return CapabilityStatement(
        capability_id=data["capability_id"],
        schema_version=data["schema_version"],
        provider_identity=data["provider_identity"],
        valid_from=valid_from,
        expires_at=expires_at,
        parameters=dict(data["parameters"]),
        constraints=dict(data["constraints"]),
        evidence_references=tuple(evidence),
        signature=data["signature"],
        withdrawn_at=withdrawn_at,
    )
