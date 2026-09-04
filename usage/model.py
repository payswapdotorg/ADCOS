"""WORK-052 UsageLedger value model.

The canonical usage value vocabulary and the content-derived
identity/digest conventions (mirroring the accepted W051 model
discipline):

- the frozen usage transaction state vocabulary
  (``OBSERVING`` / ``BILLABLE_FINAL``) with the frozen action
  vocabulary and transition table;
- the frozen quantity-class vocabulary (ACR-009: usage records
  distinguish reserved, attempted, delivered, billable,
  disputed, refunded, and reversed quantities);
- :class:`UsageCommand` (the caller-issued input with the
  idempotency key and content-derived digest),
  :class:`UsageEvent` (the resulting derived fact with full
  attribution), :class:`UsageObservationRecord` (an ingested
  observation), :class:`SealedBillableStatement` (the explicit
  immutable billable-final fact), :class:`CompensationRecord`
  (an append-only refund/reversal/dispute fact), and
  :class:`UsageTransaction` (the deterministic fold projection);
- content-derived identities: every id is a ``sha256:``
  fingerprint over WORK-003 canonical JSON (identity DATA only:
  never a NodeID, never trust, never a session identity, never
  an authorization).

No floats anywhere: quantities, prices, and amounts are
integers (the canonical JSON subset forbids floats), so all
ledger arithmetic is exact and deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import UsageError, UsageReasonCode
from .evidence import QuantityClass


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise UsageError(
            UsageReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_instant(value: object, label: str) -> str:
    """RFC 3339 UTC second-precision instant (WORK-003 style)."""
    text = _require_text(value, label)
    if len(text) != 20 or text[4] != "-" or text[7] != "-" or text[10] != "T":
        raise UsageError(
            UsageReasonCode.INSTANT_INVALID,
            "%s must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)" % label,
        )
    if text[-1] != "Z" or text[13] != ":" or text[16] != ":":
        raise UsageError(
            UsageReasonCode.INSTANT_INVALID,
            "%s must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)" % label,
        )
    return text


def _require_mapping(value: object, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UsageError(
            UsageReasonCode.INVALID_INPUT,
            "%s must be a mapping" % label,
        )
    return dict(value)


# ---------------------------------------------------------------------------
# The frozen state / action vocabularies and transition table
# ---------------------------------------------------------------------------


class UsageTransactionState:
    """The frozen usage-transaction state vocabulary.

    ``OBSERVING``: usage observations are being admitted for the
    transaction (delivered usage plus reserved/attempted DATA
    observations).  ``BILLABLE_FINAL``: the explicit sealed
    billable-final statement exists -- immutable, no further
    observations, only append-only compensations.
    """

    OBSERVING = "OBSERVING"
    BILLABLE_FINAL = "BILLABLE_FINAL"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.OBSERVING, cls.BILLABLE_FINAL)


class UsageAction:
    """The frozen UsageLedger action vocabulary.

    OBSERVE_USAGE ingests one usage observation (the ONLY
    usage-creating action, and it requires authoritative
    delivered-traffic evidence for the DELIVERED class).
    SEAL_BILLABLE performs the explicit billable-final
    transition.  RECORD_REFUND / RECORD_REVERSAL /
    RECORD_DISPUTE append compensating records against a sealed
    statement (never history rewrites).
    """

    OBSERVE_USAGE = "observe-usage"
    SEAL_BILLABLE = "seal-billable"
    RECORD_REFUND = "record-refund"
    RECORD_REVERSAL = "record-reversal"
    RECORD_DISPUTE = "record-dispute"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.OBSERVE_USAGE,
            cls.SEAL_BILLABLE,
            cls.RECORD_REFUND,
            cls.RECORD_REVERSAL,
            cls.RECORD_DISPUTE,
        )

    @classmethod
    def compensation_actions(cls) -> Tuple[str, ...]:
        return (cls.RECORD_REFUND, cls.RECORD_REVERSAL, cls.RECORD_DISPUTE)


#: The frozen usage transition table.  Observations are admitted
#: only while OBSERVING (a late/delayed observation after the
#: seal fails closed USAGE_SEALED); the seal moves OBSERVING ->
#: BILLABLE_FINAL exactly once (re-seal fails closed
#: FINAL_IMMUTABLE); compensations append only after the seal
#: (BILLABLE_FINAL -> BILLABLE_FINAL: state unchanged, record
#: appended, attribution preserved).
USAGE_TRANSITIONS: Dict[Tuple[str, str], str] = {
    (UsageTransactionState.OBSERVING, UsageAction.OBSERVE_USAGE): (
        UsageTransactionState.OBSERVING
    ),
    (UsageTransactionState.OBSERVING, UsageAction.SEAL_BILLABLE): (
        UsageTransactionState.BILLABLE_FINAL
    ),
    (UsageTransactionState.BILLABLE_FINAL, UsageAction.RECORD_REFUND): (
        UsageTransactionState.BILLABLE_FINAL
    ),
    (UsageTransactionState.BILLABLE_FINAL, UsageAction.RECORD_REVERSAL): (
        UsageTransactionState.BILLABLE_FINAL
    ),
    (UsageTransactionState.BILLABLE_FINAL, UsageAction.RECORD_DISPUTE): (
        UsageTransactionState.BILLABLE_FINAL
    ),
}


def transition_target(from_state: str, action: str) -> str:
    """The frozen-table target state (KeyError = illegal pair).

    Fail closed: the admission layer translates an illegal
    (state, action) pair into the typed LIFECYCLE-class error;
    this function itself is table-only (the model gate).
    """
    return USAGE_TRANSITIONS[(from_state, action)]


def transition_is_legal(from_state: str, action: str) -> bool:
    return (from_state, action) in USAGE_TRANSITIONS


# ---------------------------------------------------------------------------
# Content-derived identities
# ---------------------------------------------------------------------------


def command_content(
    command_id: str,
    action: str,
    transaction_id: str,
    payload: Mapping[str, Any],
    actor: str,
    source: str,
) -> Dict[str, Any]:
    """The canonical command content (digest basis + journal DATA)."""
    return {
        "command_id": command_id,
        "action": action,
        "transaction_id": transaction_id,
        "payload": dict(payload),
        "actor": actor,
        "source": source,
    }


def derive_command_digest(
    command_id: str,
    action: str,
    transaction_id: str,
    payload: Mapping[str, Any],
    actor: str,
    source: str,
) -> str:
    """The content-derived command digest (idempotency ledger).

    Same command id + same content -> same digest (idempotent
    no-op on redelivery); same command id + different content ->
    ``COMMAND_CONFLICT`` (fail closed).
    """
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            command_content(
                command_id, action, transaction_id, payload, actor, source
            )
        )
    ).hexdigest()


def derive_event_id(
    transaction_id: str,
    action: str,
    from_state: str,
    to_state: str,
    command_id: str,
    fact_id: str,
    instant: str,
) -> str:
    """Content-derived usage event id (journal identity DATA)."""
    content = {
        "transaction_id": transaction_id,
        "action": action,
        "from_state": from_state,
        "to_state": to_state,
        "command_id": command_id,
        "fact_id": fact_id,
        "instant": instant,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def derive_observation_id(
    command_id: str,
    transaction_id: str,
    quantity_class: str,
    quantity: int,
    evidence_id: Optional[str],
    window_start: Optional[str],
    window_end: Optional[str],
    recorded_at: str,
) -> str:
    """The content-derived usage-observation fact id.

    Binds the observation to its causal command, its
    transaction, its class/quantity, its delivery evidence
    citation, its window, and the deterministic recorded
    instant.  Two observations of the SAME evidence with the
    SAME derived content derive the SAME fact id -- the
    evidence-level no-double-charge identity.
    """
    content: Dict[str, Any] = {
        "kind": "usage-observation",
        "command_id": command_id,
        "transaction_id": transaction_id,
        "quantity_class": quantity_class,
        "quantity": quantity,
        "recorded_at": recorded_at,
    }
    if evidence_id is not None:
        content["evidence_id"] = evidence_id
    if window_start is not None:
        content["window_start"] = window_start
    if window_end is not None:
        content["window_end"] = window_end
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def derive_statement_id(
    transaction_id: str,
    contributing_observation_ids: Tuple[str, ...],
    sealed_at: str,
) -> str:
    """The content-derived sealed billable statement id."""
    content = {
        "kind": "sealed-billable-statement",
        "transaction_id": transaction_id,
        "contributing_observations": list(contributing_observation_ids),
        "sealed_at": sealed_at,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def derive_compensation_id(
    transaction_id: str,
    compensation_kind: str,
    amount_micros: int,
    reason: str,
    statement_id: str,
    command_id: str,
    recorded_at: str,
) -> str:
    """The content-derived compensating-record id."""
    content = {
        "kind": "usage-compensation",
        "transaction_id": transaction_id,
        "compensation_kind": compensation_kind,
        "amount_micros": amount_micros,
        "reason": reason,
        "statement_id": statement_id,
        "command_id": command_id,
        "recorded_at": recorded_at,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


# ---------------------------------------------------------------------------
# Usage command (the input record)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageCommand:
    """One caller-issued usage command.

    ``command_id`` is the caller's idempotency key (the
    observation-delivery identity; redelivery with the same id
    and content is a no-op, redelivery with different content
    fails closed COMMAND_CONFLICT).  ``transaction_id`` is the
    WORK-051 commercial transaction citation (correlation key;
    resolved against the injected evidence index).  ``payload``
    carries the action-specific members (shape-validated at
    admission).  ``actor`` / ``source`` attribute the command.
    """

    command_id: str
    action: str
    transaction_id: str
    payload: Mapping[str, Any]
    actor: str
    source: str

    def __post_init__(self) -> None:
        _require_text(self.command_id, "command_id")
        if self.action not in UsageAction.values():
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "action %r must be one of %s"
                % (self.action, list(UsageAction.values())),
            )
        _require_text(self.transaction_id, "transaction_id")
        _require_mapping(self.payload, "payload")
        _require_text(self.actor, "actor")
        _require_text(self.source, "source")

    def digest(self) -> str:
        return derive_command_digest(
            self.command_id,
            self.action,
            self.transaction_id,
            self.payload,
            self.actor,
            self.source,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "action": self.action,
            "transaction_id": self.transaction_id,
            "payload": dict(self.payload),
            "actor": self.actor,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: object) -> "UsageCommand":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "usage command must be a mapping",
            )
        for key in (
            "command_id",
            "action",
            "transaction_id",
            "payload",
            "actor",
            "source",
        ):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "usage command is missing required member %r" % key,
                )
        return cls(
            command_id=data["command_id"],
            action=data["action"],
            transaction_id=data["transaction_id"],
            payload=data["payload"],
            actor=data["actor"],
            source=data["source"],
        )


# ---------------------------------------------------------------------------
# The derived fact records (journal event payloads)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageObservationRecord:
    """One ingested usage observation (the OBSERVE_USAGE fact).

    DELIVERED-class observations carry the delivery-evidence
    citation (evidence_id + window, validated at admission
    against the index: quantity <= evidence quantity, window
    within the evidence window) and contribute to billable
    usage.  RESERVED/ATTEMPTED-class observations are DATA for
    reconciliation only: they carry NO delivery-evidence
    citation (reservations and attempts never create usage) and
    never contribute to billable quantity.
    """

    observation_id: str
    command_id: str
    transaction_id: str
    quantity_class: str
    quantity: int
    recorded_at: str
    evidence_id: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    actor: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        _require_text(self.observation_id, "observation_id")
        _require_text(self.command_id, "command_id")
        _require_text(self.transaction_id, "transaction_id")
        if self.quantity_class not in QuantityClass.values():
            raise UsageError(
                UsageReasonCode.OBSERVATION_CLASS_INVALID,
                "quantity_class %r must be one of %s"
                % (self.quantity_class, list(QuantityClass.values())),
            )
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "quantity must be an integer",
            )
        if self.quantity < 1:
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "quantity must be >= 1 (an empty observation is not a fact)",
            )
        _require_instant(self.recorded_at, "recorded_at")
        if self.quantity_class == QuantityClass.DELIVERED:
            _require_text(self.evidence_id, "evidence_id")
            _require_instant(self.window_start, "window_start")
            _require_instant(self.window_end, "window_end")
        elif self.evidence_id is not None:
            raise UsageError(
                UsageReasonCode.OBSERVATION_CLASS_INVALID,
                "a %s-class observation must not cite delivery evidence "
                "(reserved/attempted quantities are DATA and never "
                "delivered-traffic facts)" % self.quantity_class,
            )

    def is_billable(self) -> bool:
        return self.quantity_class == QuantityClass.DELIVERED

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "kind": "usage-observation-record",
            "observation_id": self.observation_id,
            "command_id": self.command_id,
            "transaction_id": self.transaction_id,
            "quantity_class": self.quantity_class,
            "quantity": self.quantity,
            "recorded_at": self.recorded_at,
            "actor": self.actor,
            "source": self.source,
        }
        if self.evidence_id is not None:
            data["evidence_id"] = self.evidence_id
        if self.window_start is not None:
            data["window_start"] = self.window_start
        if self.window_end is not None:
            data["window_end"] = self.window_end
        return data

    @classmethod
    def from_dict(cls, data: object) -> "UsageObservationRecord":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "usage observation record must be a mapping",
            )
        for key in (
            "observation_id",
            "command_id",
            "transaction_id",
            "quantity_class",
            "quantity",
            "recorded_at",
        ):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "usage observation record is missing member %r" % key,
                )
        return cls(
            observation_id=data["observation_id"],
            command_id=data["command_id"],
            transaction_id=data["transaction_id"],
            quantity_class=data["quantity_class"],
            quantity=data["quantity"],
            recorded_at=data["recorded_at"],
            evidence_id=data.get("evidence_id"),
            window_start=data.get("window_start"),
            window_end=data.get("window_end"),
            actor=str(data.get("actor", "")),
            source=str(data.get("source", "")),
        )


@dataclass(frozen=True)
class SealedBillableStatement:
    """The explicit, immutable billable-final fact (SEAL_BILLABLE).

    Distinguishes the quantity classes exactly as ACR-009
    requires: reserved, attempted, delivered, and billable
    quantities are separate members (billable == delivered; the
    distinction is the sealed, final, chargeable derivation).
    The amount is exact integer arithmetic
    ``billable_quantity * unit_price_micros`` (no floats, no
    rounding, deterministic).  ``contributing_observations`` is
    the sorted id list of every admitted DELIVERED observation
    sealed by this statement (the audit trail); once sealed,
    the statement is immutable (no rewrite path exists) and any
    later correction is an append-only compensating record.
    """

    statement_id: str
    transaction_id: str
    reserved_quantity: int
    attempted_quantity: int
    delivered_quantity: int
    billable_quantity: int
    unit_price_micros: int
    amount_micros: int
    billable_unit: str
    tariff_provenance: str
    contributing_observations: Tuple[str, ...]
    contributing_evidence: Tuple[str, ...]
    sealed_at: str

    def __post_init__(self) -> None:
        _require_text(self.statement_id, "statement_id")
        _require_text(self.transaction_id, "transaction_id")
        for label in (
            "reserved_quantity",
            "attempted_quantity",
            "delivered_quantity",
            "billable_quantity",
            "unit_price_micros",
            "amount_micros",
        ):
            value = getattr(self, label)
            if not isinstance(value, int) or isinstance(value, bool):
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "%s must be an integer" % label,
                )
        for label in ("reserved_quantity", "attempted_quantity"):
            if getattr(self, label) < 0:
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "%s must be >= 0" % label,
                )
        if self.delivered_quantity < 0 or self.billable_quantity < 0:
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "delivered/billable quantities must be >= 0",
            )
        if self.billable_quantity != self.delivered_quantity:
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "billable_quantity must equal delivered_quantity (the "
                "billable derivation is exactly the delivered evidence; "
                "no silent write-down or write-up)",
            )
        if self.unit_price_micros < 0 or self.amount_micros < 0:
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "price/amount must be >= 0",
            )
        if self.amount_micros != self.billable_quantity * self.unit_price_micros:
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "amount_micros must be exactly "
                "billable_quantity * unit_price_micros",
            )
        _require_text(self.billable_unit, "billable_unit")
        _require_text(self.tariff_provenance, "tariff_provenance")
        _require_instant(self.sealed_at, "sealed_at")
        for observation_id in self.contributing_observations:
            _require_text(observation_id, "contributing observation id")
        for evidence_id in self.contributing_evidence:
            _require_text(evidence_id, "contributing evidence id")
        if (
            sorted(self.contributing_observations)
            != list(self.contributing_observations)
        ):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "contributing_observations must be sorted (deterministic "
                "audit order)",
            )
        if sorted(self.contributing_evidence) != list(self.contributing_evidence):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "contributing_evidence must be sorted (deterministic "
                "audit order)",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "sealed-billable-statement-record",
            "statement_id": self.statement_id,
            "transaction_id": self.transaction_id,
            "reserved_quantity": self.reserved_quantity,
            "attempted_quantity": self.attempted_quantity,
            "delivered_quantity": self.delivered_quantity,
            "billable_quantity": self.billable_quantity,
            "unit_price_micros": self.unit_price_micros,
            "amount_micros": self.amount_micros,
            "billable_unit": self.billable_unit,
            "tariff_provenance": self.tariff_provenance,
            "contributing_observations": list(self.contributing_observations),
            "contributing_evidence": list(self.contributing_evidence),
            "sealed_at": self.sealed_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "SealedBillableStatement":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "sealed statement must be a mapping",
            )
        for key in (
            "statement_id",
            "transaction_id",
            "reserved_quantity",
            "attempted_quantity",
            "delivered_quantity",
            "billable_quantity",
            "unit_price_micros",
            "amount_micros",
            "billable_unit",
            "tariff_provenance",
            "contributing_observations",
            "contributing_evidence",
            "sealed_at",
        ):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "sealed statement is missing member %r" % key,
                )
        return cls(
            statement_id=data["statement_id"],
            transaction_id=data["transaction_id"],
            reserved_quantity=data["reserved_quantity"],
            attempted_quantity=data["attempted_quantity"],
            delivered_quantity=data["delivered_quantity"],
            billable_quantity=data["billable_quantity"],
            unit_price_micros=data["unit_price_micros"],
            amount_micros=data["amount_micros"],
            billable_unit=data["billable_unit"],
            tariff_provenance=data["tariff_provenance"],
            contributing_observations=tuple(data["contributing_observations"]),
            contributing_evidence=tuple(data["contributing_evidence"]),
            sealed_at=data["sealed_at"],
        )


@dataclass(frozen=True)
class CompensationRecord:
    """One append-only compensating economic fact.

    Kinds: ``refund`` / ``reversal`` (monetary: amount adjusts
    the net) and ``dispute`` (non-monetary flag: amount pinned
    to 0; a dispute may be followed by monetary compensation
    records, but the dispute itself never rewrites history).
    Every compensation cites the immutable sealed statement it
    compensates.  There is no mutation, removal, or rewrite path
    for a compensation record.
    """

    compensation_id: str
    transaction_id: str
    compensation_kind: str
    amount_micros: int
    reason: str
    statement_id: str
    command_id: str
    recorded_at: str

    def __post_init__(self) -> None:
        _require_text(self.compensation_id, "compensation_id")
        _require_text(self.transaction_id, "transaction_id")
        if self.compensation_kind not in ("refund", "reversal", "dispute"):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "compensation_kind %r must be refund/reversal/dispute"
                % self.compensation_kind,
            )
        if not isinstance(self.amount_micros, int) or isinstance(
            self.amount_micros, bool
        ):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "amount_micros must be an integer",
            )
        if self.compensation_kind == "dispute" and self.amount_micros != 0:
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "a dispute record is non-monetary (amount pinned to 0; "
                "the monetary compensation is a separate refund/reversal "
                "record)",
            )
        if self.compensation_kind in ("refund", "reversal") and self.amount_micros < 1:
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "a refund/reversal record must carry amount >= 1",
            )
        _require_text(self.reason, "reason")
        _require_text(self.statement_id, "statement_id")
        _require_text(self.command_id, "command_id")
        _require_instant(self.recorded_at, "recorded_at")

    def is_monetary(self) -> bool:
        return self.compensation_kind in ("refund", "reversal")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "usage-compensation-record",
            "compensation_id": self.compensation_id,
            "transaction_id": self.transaction_id,
            "compensation_kind": self.compensation_kind,
            "amount_micros": self.amount_micros,
            "reason": self.reason,
            "statement_id": self.statement_id,
            "command_id": self.command_id,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "CompensationRecord":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "compensation record must be a mapping",
            )
        for key in (
            "compensation_id",
            "transaction_id",
            "compensation_kind",
            "amount_micros",
            "reason",
            "statement_id",
            "command_id",
            "recorded_at",
        ):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "compensation record is missing member %r" % key,
                )
        return cls(
            compensation_id=data["compensation_id"],
            transaction_id=data["transaction_id"],
            compensation_kind=data["compensation_kind"],
            amount_micros=data["amount_micros"],
            reason=data["reason"],
            statement_id=data["statement_id"],
            command_id=data["command_id"],
            recorded_at=data["recorded_at"],
        )


# ---------------------------------------------------------------------------
# Usage event (the journal event record)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageEvent:
    """One derived usage fact with full attribution.

    Carries the transaction id, the action, the from/to state
    attribution (the usage walk), the causal command id, the
    derived fact record (observation / sealed statement /
    compensation -- a tagged mapping), the actor, the source,
    and the deterministic event instant (an injected WORK-033
    clock read).  ``event_id`` is the content-derived fingerprint
    over the full attribution + fact.
    """

    event_id: str
    transaction_id: str
    action: str
    from_state: str
    to_state: str
    command_id: str
    fact: Mapping[str, Any]
    actor: str
    source: str
    instant: str

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.transaction_id, "transaction_id")
        if self.action not in UsageAction.values():
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "event action %r is not in the frozen vocabulary"
                % self.action,
            )
        if self.from_state not in UsageTransactionState.values():
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "event from_state %r is not in the frozen vocabulary"
                % self.from_state,
            )
        if self.to_state not in UsageTransactionState.values():
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "event to_state %r is not in the frozen vocabulary"
                % self.to_state,
            )
        _require_text(self.command_id, "command_id")
        _require_mapping(self.fact, "fact")
        _require_text(self.actor, "actor")
        _require_text(self.source, "source")
        _require_instant(self.instant, "instant")

    def observation(self) -> Optional[UsageObservationRecord]:
        if self.fact.get("kind") == "usage-observation-record":
            return UsageObservationRecord.from_dict(self.fact)
        return None

    def statement(self) -> Optional[SealedBillableStatement]:
        if self.fact.get("kind") == "sealed-billable-statement-record":
            return SealedBillableStatement.from_dict(self.fact)
        return None

    def compensation(self) -> Optional[CompensationRecord]:
        if self.fact.get("kind") == "usage-compensation-record":
            return CompensationRecord.from_dict(self.fact)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "transaction_id": self.transaction_id,
            "action": self.action,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "command_id": self.command_id,
            "fact": dict(self.fact),
            "actor": self.actor,
            "source": self.source,
            "instant": self.instant,
        }

    @classmethod
    def from_dict(cls, data: object) -> "UsageEvent":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "usage event must be a mapping",
            )
        for key in (
            "event_id",
            "transaction_id",
            "action",
            "from_state",
            "to_state",
            "command_id",
            "fact",
            "actor",
            "source",
            "instant",
        ):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "usage event is missing member %r" % key,
                )
        return cls(
            event_id=data["event_id"],
            transaction_id=data["transaction_id"],
            action=data["action"],
            from_state=data["from_state"],
            to_state=data["to_state"],
            command_id=data["command_id"],
            fact=data["fact"],
            actor=data["actor"],
            source=data["source"],
            instant=data["instant"],
        )


def event_list_digest(events: Tuple[UsageEvent, ...]) -> str:
    """Deterministic digest over the ordered event list."""
    content = {
        "kind": "usage-event-list",
        "events": [event.event_id for event in events],
        "count": len(events),
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


# ---------------------------------------------------------------------------
# Usage transaction (the fold projection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageTransaction:
    """The deterministic usage-economy projection of ONE cited
    commercial transaction (usage/economic ledger state ONLY --
    never a commercial lifecycle shadow).

    ``state`` is OBSERVING / BILLABLE_FINAL.  ``observations``
    carries the admitted observation records (sorted by
    observation id -- a canonical audit order; the observation
    ids themselves are admission-attributed: they bind the
    causal command and the admission instant, so the SAME
    logical observation set admitted in a different arrival
    order carries different ids and audit lists while the
    economic fold -- quantities, amount, contributing evidence
    multiset -- remains identical).  ``statement``
    is the sealed billable-final fact once sealed (else absent).
    ``compensations`` carries the append-only compensating
    records (sorted).  Monetary compensations adjust
    ``net_amount_micros`` = amount - refunds - reversals; a
    dispute sets ``disputed`` without touching amounts.
    """

    transaction_id: str
    state: str
    observations: Tuple[UsageObservationRecord, ...] = ()
    statement: Optional[SealedBillableStatement] = None
    compensations: Tuple[CompensationRecord, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.transaction_id, "transaction_id")
        if self.state not in UsageTransactionState.values():
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "usage transaction state %r is not in the frozen "
                "vocabulary" % self.state,
            )
        if self.state == UsageTransactionState.BILLABLE_FINAL:
            if self.statement is None:
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "BILLABLE_FINAL requires the sealed statement",
                )
        elif self.statement is not None:
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "OBSERVING must not carry a sealed statement",
            )
        for observation in self.observations:
            if not isinstance(observation, UsageObservationRecord):
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "observations must be UsageObservationRecord values",
                )
        for compensation in self.compensations:
            if not isinstance(compensation, CompensationRecord):
                raise UsageError(
                    UsageReasonCode.EVENT_INVALID,
                    "compensations must be CompensationRecord values",
                )
        ids = [observation.observation_id for observation in self.observations]
        if ids != sorted(ids):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "observations must be sorted by observation id",
            )
        if len(set(ids)) != len(ids):
            raise UsageError(
                UsageReasonCode.EVENT_INVALID,
                "duplicate observation ids in the projection",
            )
        if self.statement is not None and self.compensations:
            for compensation in self.compensations:
                if compensation.statement_id != self.statement.statement_id:
                    raise UsageError(
                        UsageReasonCode.EVENT_INVALID,
                        "compensation %s cites statement %s, not the "
                        "transaction's sealed statement %s"
                        % (
                            compensation.compensation_id,
                            compensation.statement_id,
                            self.statement.statement_id,
                        ),
                    )

    # ------------------------------------------------------------------
    # deterministic reads (the class-distinguishing reconciliation
    # quantities -- ACR-009: reserved/attempted/delivered/billable/
    # disputed/refunded/reversed are separate)
    # ------------------------------------------------------------------

    def quantities(self) -> Dict[str, int]:
        """The class-distinguished observation quantities."""
        totals: Dict[str, int] = {
            QuantityClass.RESERVED: 0,
            QuantityClass.ATTEMPTED: 0,
            QuantityClass.DELIVERED: 0,
        }
        for observation in self.observations:
            totals[observation.quantity_class] = (
                totals.get(observation.quantity_class, 0) + observation.quantity
            )
        return totals

    def delivered_observation_ids(self) -> Tuple[str, ...]:
        return tuple(
            observation.observation_id
            for observation in self.observations
            if observation.is_billable()
        )

    def compensated_amount_micros(self) -> int:
        """The summed monetary compensation (refunds+reversals)."""
        return sum(
            compensation.amount_micros
            for compensation in self.compensations
            if compensation.is_monetary()
        )

    def refunded_quantity(self) -> int:
        """The REFUND compensation expressed in quantity units
        (floor division of the refund amount by the unit price;
        0 when unsealed or the unit price is 0).  DATA for the
        reconciliation statement; the canonical money fact is
        the refund amount, not this derived view.  Derived from
        the refund amounts ONLY (independent of reversals;
        floor divisions do not re-add across kinds)."""
        if self.statement is None or self.statement.unit_price_micros == 0:
            return 0
        return self.refunded_amount_micros() // self.statement.unit_price_micros

    def reversed_quantity(self) -> int:
        """The REVERSAL compensation expressed in quantity units
        (floor division of the reversal amount by the unit
        price; 0 when unsealed or the unit price is 0).  DATA
        for the reconciliation statement; the canonical money
        fact is the reversal amount, not this derived view.
        Derived from the reversal amounts ONLY (independent of
        refunds; floor divisions do not re-add across kinds)."""
        if self.statement is None or self.statement.unit_price_micros == 0:
            return 0
        return self.reversed_amount_micros() // self.statement.unit_price_micros

    def refunded_amount_micros(self) -> int:
        return sum(
            compensation.amount_micros
            for compensation in self.compensations
            if compensation.compensation_kind == "refund"
        )

    def reversed_amount_micros(self) -> int:
        return sum(
            compensation.amount_micros
            for compensation in self.compensations
            if compensation.compensation_kind == "reversal"
        )

    def disputed(self) -> bool:
        return any(
            compensation.compensation_kind == "dispute"
            for compensation in self.compensations
        )

    def net_amount_micros(self) -> int:
        """amount - refunds - reversals (disputes are flags)."""
        if self.statement is None:
            return 0
        return (
            self.statement.amount_micros
            - self.refunded_amount_micros()
            - self.reversed_amount_micros()
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "transaction_id": self.transaction_id,
            "state": self.state,
            "observations": [obs.to_dict() for obs in self.observations],
        }
        if self.statement is not None:
            data["statement"] = self.statement.to_dict()
        if self.compensations:
            data["compensations"] = [
                compensation.to_dict() for compensation in self.compensations
            ]
        return data


def usage_transaction_digest(transaction: UsageTransaction) -> str:
    """Deterministic digest of one transaction projection."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            {
                "kind": "usage-transaction-projection",
                "transaction": transaction.to_dict(),
            }
        )
    ).hexdigest()
