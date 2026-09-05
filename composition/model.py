"""W054 immutable composition value model."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Dict, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes


COMPOSITION_STAGES: Tuple[str, ...] = (
    "DEVELOPER_API",
    "POLICY_ELIGIBILITY",
    "OFFER_RESERVATION_LEASE",
    "MARKETPLACE_SELECTION",
    "NETWORK_PATH_VALIDATION",
    "CONTAINMENT",
    "SESSION",
    "DELIVERY",
    "USAGE",
    "BILLABLE_FINAL",
    "ALLOCATION",
    "PAYMENT_RECONCILIATION",
    "CANONICAL_OBSERVATION",
)

STAGE_AUTHORITIES = MappingProxyType({
    "DEVELOPER_API": "WORK-046",
    "POLICY_ELIGIBILITY": "WORK-045",
    "OFFER_RESERVATION_LEASE": "WORK-051",
    "MARKETPLACE_SELECTION": "WORK-047",
    "NETWORK_PATH_VALIDATION": "WORK-041",
    "CONTAINMENT": "WORK-048",
    "SESSION": "WORK-012",
    "DELIVERY": "WORK-048",
    "USAGE": "WORK-052",
    "BILLABLE_FINAL": "WORK-051",
    "ALLOCATION": "WORK-053",
    "PAYMENT_RECONCILIATION": "WORK-044",
    "CANONICAL_OBSERVATION": "WORK-046",
})


class CompositionReasonCode:
    INVALID_INPUT = "invalid-input"
    REQUEST_CONFLICT = "request-conflict"
    STORE_CORRUPT = "store-corrupt"
    STAGE_ORDER = "stage-order"
    AUTHORITY_INVALID = "authority-invalid"
    RECEIPT_INVALID = "receipt-invalid"
    PHYSICAL_CLAIM = "physical-claim"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.REQUEST_CONFLICT,
            cls.STORE_CORRUPT,
            cls.STAGE_ORDER,
            cls.AUTHORITY_INVALID,
            cls.RECEIPT_INVALID,
            cls.PHYSICAL_CLAIM,
        )


class CompositionError(ValueError):
    """Typed fail-closed composition error."""

    def __init__(self, reason: str, message: str) -> None:
        if reason not in CompositionReasonCode.values():
            raise ValueError("unknown composition reason code %r" % reason)
        super().__init__(message)
        self.reason = reason


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CompositionError(CompositionReasonCode.INVALID_INPUT, "%s must be non-empty text" % label)
    return value


def _freeze_mapping(value: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    try:
        payload = dict(value)
        canonical_json_bytes(payload)
    except Exception as exc:
        raise CompositionError(CompositionReasonCode.INVALID_INPUT, "%s is outside canonical JSON" % label) from exc
    return MappingProxyType(payload)


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + sha256(canonical_json_bytes(dict(value))).hexdigest()


@dataclass(frozen=True)
class CompositionRequest:
    request_id: str
    actor: str
    source: str
    intent: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.actor, "actor")
        _text(self.source, "source")
        if not isinstance(self.intent, Mapping):
            raise CompositionError(CompositionReasonCode.INVALID_INPUT, "intent must be a mapping")
        object.__setattr__(self, "intent", _freeze_mapping(self.intent, "intent"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "actor": self.actor,
            "source": self.source,
            "intent": dict(self.intent),
        }

    def digest(self) -> str:
        return _canonical_digest(self.to_dict())


@dataclass(frozen=True)
class StageReceipt:
    stage: str
    authority: str
    operation: str
    status: str
    reference: str
    evidence_refs: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        expected = STAGE_AUTHORITIES.get(self.stage)
        if expected is None:
            raise CompositionError(CompositionReasonCode.RECEIPT_INVALID, "unknown stage %r" % self.stage)
        if self.authority != expected:
            raise CompositionError(
                CompositionReasonCode.AUTHORITY_INVALID,
                "stage %s must be owned by %s, not %s" % (self.stage, expected, self.authority),
            )
        _text(self.operation, "operation")
        _text(self.status, "status")
        _text(self.reference, "reference")
        if not isinstance(self.evidence_refs, tuple) or not all(isinstance(v, str) and v for v in self.evidence_refs):
            raise CompositionError(CompositionReasonCode.RECEIPT_INVALID, "evidence_refs must be a tuple of non-empty strings")
        if self.metadata is None:
            metadata = {}
        elif isinstance(self.metadata, Mapping):
            metadata = dict(self.metadata)
        else:
            raise CompositionError(CompositionReasonCode.RECEIPT_INVALID, "metadata must be a mapping")
        try:
            flattened = canonical_json_bytes(metadata).decode("utf-8")
        except Exception as exc:
            raise CompositionError(CompositionReasonCode.RECEIPT_INVALID, "metadata is outside canonical JSON") from exc
        if "PHYSICAL_PASS" in flattened or "physical_pass" in flattened:
            raise CompositionError(CompositionReasonCode.PHYSICAL_CLAIM, "composition receipts cannot claim physical PASS")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "metadata", MappingProxyType(metadata))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "authority": self.authority,
            "operation": self.operation,
            "status": self.status,
            "reference": self.reference,
            "evidence_refs": list(self.evidence_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CompositionResult:
    request: CompositionRequest
    receipts: Tuple[StageReceipt, ...]
    final_status: str
    digest: str

    def __post_init__(self) -> None:
        if len(self.receipts) != len(COMPOSITION_STAGES):
            raise CompositionError(CompositionReasonCode.STORE_CORRUPT, "complete result must contain every composition stage")
        for index, receipt in enumerate(self.receipts):
            if receipt.stage != COMPOSITION_STAGES[index]:
                raise CompositionError(CompositionReasonCode.STAGE_ORDER, "receipt order is not the frozen composition order")
        _text(self.final_status, "final_status")
        expected = _canonical_digest(self.payload_for_digest())
        if self.digest != expected:
            raise CompositionError(CompositionReasonCode.STORE_CORRUPT, "composition digest does not match content")
        object.__setattr__(self, "receipts", tuple(self.receipts))

    def payload_for_digest(self) -> Dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "final_status": self.final_status,
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.payload_for_digest(), digest=self.digest)
