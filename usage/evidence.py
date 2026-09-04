"""WORK-052 UsageLedger external evidence boundary.

The authority-reference model of the usage ledger (ACR-009
"Usage integrity" + authority boundaries 1-4):

- The usage ledger may REFERENCE commercial transaction ids
  (WORK-051 authority-owned), logical session ids (WORK-012
  authority-owned), NetworkPath ids (WORK-041 authority-owned),
  and delivery-plane evidence ids.  It must NEVER own, mutate,
  query, or instantiate those authorities: there is no authority
  object, client, manager, or private accessor anywhere in the
  usage package.  A :class:`UsageEvidenceIndex` is an immutable
  snapshot BUILT BY THE CALLER from the authorities' PUBLIC
  interfaces (the W042/W051 composition precedent) and INJECTED
  into the ledger.
- Fail-closed evidence integrity: an observation citing an
  evidence id the index does not carry is rejected
  ``EVIDENCE_UNKNOWN`` (a fabricated delivery citation can never
  create usage); an evidence record of a non-delivered kind
  (provider observation / payment observation) can never satisfy
  the delivered-evidence requirement
  (``PROVIDER_NOT_DELIVERY`` / ``PAYMENT_NOT_DELIVERY`` -- the
  payment/provider/delivery separation is kind-table-driven,
  not caller-honor-driven).
- Provider observations and payment observations are DATA: the
  index may carry them (so the ledger's audit trail can show
  they were seen), but they are structurally ineligible as
  usage evidence.

Usage originates ONLY from an already-authorized delivery path
plus accepted traffic evidence: a
:class:`CommercialTransactionSnapshot` carries the W051 public
state citation at snapshot-build time, and a transaction that is
not in a delivery-eligible state (delivery not yet started)
rejects observations ``TRANSACTION_NOT_DELIVERING`` -- a
reservation or lease alone can never create usage
(``RESERVATION_NOT_USAGE`` is the explicit lease/quantity-class
separation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .errors import UsageError, UsageReasonCode

# The W051 delivery-eligible commercial states (a citation of the
# accepted WORK-051 lifecycle vocabulary, read through the W051
# public surface by the CALLER when building the snapshot; the
# usage ledger never owns or computes the commercial lifecycle).
# Delivery has begun or completed: usage metering is legitimate.
DELIVERY_ELIGIBLE_STATES = (
    "DELIVERY_STARTED",
    "USAGE_ACCRUING",
    "DELIVERY_COMPLETED",
    "BILLABLE_FINAL",
    "SETTLEMENT_PENDING",
    "SETTLED",
)

#: The states where usage metering is explicitly rejected: the
#: transaction is still pre-delivery (intent/offer/reservation/
#: lease/session/path phases -- reservation and lease can never
#: create usage).
RESERVATION_PHASE_STATES = (
    "CONNECTIVITY_INTENT",
    "OFFER_SELECTED",
    "RESERVATION_HELD",
    "SESSION_AUTHORIZED",
    "PATH_ACTIVE",
)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise UsageError(
            UsageReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


class EvidenceKind:
    """The frozen delivery-evidence kind vocabulary.

    ``DELIVERED`` is the authoritative delivery-plane evidence
    kind (usage-eligible).  ``PROVIDER_OBSERVED`` and
    ``PAYMENT_OBSERVED`` are DATA-only kinds: provider-side and
    payment-side observations may be recorded in the index and in
    the ledger's audit trail, but they are structurally
    ineligible as usage evidence -- they never prove delivery.
    """

    DELIVERED = "delivered"
    PROVIDER_OBSERVED = "provider-observed"
    PAYMENT_OBSERVED = "payment-observed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.DELIVERED, cls.PROVIDER_OBSERVED, cls.PAYMENT_OBSERVED)

    @classmethod
    def usage_eligible(cls) -> Tuple[str, ...]:
        """The kinds that can justify usage: exactly one."""
        return (cls.DELIVERED,)


class QuantityClass:
    """The frozen usage quantity-class vocabulary (ACR-009:
    "usage records distinguish reserved, attempted, delivered,
    billable, disputed, refunded, and reversed quantities").

    Only the ``DELIVERED`` class creates billable usage.
    ``RESERVED`` and ``ATTEMPTED`` observations are recorded as
    DATA for reconciliation (the statement distinguishes the
    classes) but never contribute to billable quantity.
    """

    RESERVED = "reserved"
    ATTEMPTED = "attempted"
    DELIVERED = "delivered"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.RESERVED, cls.ATTEMPTED, cls.DELIVERED)

    @classmethod
    def billable_classes(cls) -> Tuple[str, ...]:
        return (cls.DELIVERED,)


@dataclass(frozen=True)
class DeliveryEvidence:
    """One external delivery-plane evidence record (DATA + the
    delivered-quantity fact the usage ledger derives from).

    ``evidence_id`` is the delivery-plane authority-owned
    identity string (e.g. a platform-journal delivery-plane event
    id).  ``transaction_id`` is the WORK-051 commercial
    transaction the evidence correlates to (a citation, never
    owned).  ``session_reference`` / ``path_reference`` are
    optional WORK-012 / WORK-041 citations carried as
    correlation DATA.  ``delivered_quantity`` is the integer
    delivered-traffic quantity (canonical units, e.g. bytes; the
    canonical JSON subset forbids floats, so all quantities are
    integers).  ``window_start`` / ``window_end`` are RFC 3339
    UTC instants bounding the delivery window.
    ``evidence_kind`` separates authoritative delivered evidence
    from provider/payment observations (DATA, never proof of
    delivery).  ``provenance`` records which authority surface
    produced the record (a label, never a live object).
    """

    evidence_id: str
    transaction_id: str
    delivered_quantity: int
    window_start: str
    window_end: str
    evidence_kind: str
    provenance: str
    session_reference: Optional[str] = None
    path_reference: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "evidence_id")
        _require_text(self.transaction_id, "transaction_id")
        if not isinstance(self.delivered_quantity, int) or isinstance(
            self.delivered_quantity, bool
        ):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "delivered_quantity must be an integer",
            )
        if self.evidence_kind != EvidenceKind.DELIVERED:
            # a DATA-only observation kind never carries a delivered
            # quantity fact: provider/payment observations record
            # observed amounts in their own payloads, not delivery
            # quantities.  The delivered_quantity member is the
            # DELIVERED-plane fact; for DATA kinds it is pinned to 0
            # so the record can never be misread as delivered traffic.
            if self.delivered_quantity != 0:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "evidence_kind %r must carry delivered_quantity 0 "
                    "(provider/payment observations are DATA, never "
                    "delivered-quantity facts)"
                    % self.evidence_kind,
                )
        elif self.delivered_quantity < 1:
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "delivered_quantity must be >= 1 for delivered evidence "
                "(evidence records a non-empty delivered quantity)",
            )
        _require_text(self.window_start, "window_start")
        _require_text(self.window_end, "window_end")
        if self.window_end < self.window_start:
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "window_end must not precede window_start",
            )
        if self.evidence_kind not in EvidenceKind.values():
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "evidence_kind %r must be one of %s"
                % (self.evidence_kind, list(EvidenceKind.values())),
            )
        _require_text(self.provenance, "provenance")
        for label, value in (
            ("session_reference", self.session_reference),
            ("path_reference", self.path_reference),
        ):
            if value is not None:
                _require_text(value, label)

    def is_usage_eligible(self) -> bool:
        """Only authoritative delivered evidence creates usage."""
        return self.evidence_kind == EvidenceKind.DELIVERED

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "transaction_id": self.transaction_id,
            "delivered_quantity": self.delivered_quantity,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "evidence_kind": self.evidence_kind,
            "provenance": self.provenance,
        }
        if self.session_reference is not None:
            data["session_reference"] = self.session_reference
        if self.path_reference is not None:
            data["path_reference"] = self.path_reference
        return data

    @classmethod
    def from_dict(cls, data: object) -> "DeliveryEvidence":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "delivery evidence must be a mapping",
            )
        for key in (
            "evidence_id",
            "transaction_id",
            "delivered_quantity",
            "window_start",
            "window_end",
            "evidence_kind",
            "provenance",
        ):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "delivery evidence is missing required member %r" % key,
                )
        return cls(
            evidence_id=data["evidence_id"],
            transaction_id=data["transaction_id"],
            delivered_quantity=data["delivered_quantity"],
            window_start=data["window_start"],
            window_end=data["window_end"],
            evidence_kind=data["evidence_kind"],
            provenance=data["provenance"],
            session_reference=data.get("session_reference"),
            path_reference=data.get("path_reference"),
        )


@dataclass(frozen=True)
class CommercialTransactionSnapshot:
    """One WORK-051 commercial transaction citation (public-read
    DATA, never owned).

    ``commercial_state`` is the W051 lifecycle state at
    snapshot-build time (the caller read it through the
    CommercialCore public surface).  ``unit_price_micros`` is the
    integer unit price (micro currency units per canonical
    quantity unit) read from the W051 offer/public surface by
    the caller; the usage ledger multiplies exactly (integer
    arithmetic, deterministic, no floats, no rounding).
    ``billable_unit`` labels the canonical quantity unit.
    ``tariff_provenance`` records where the tariff was read.
    """

    transaction_id: str
    commercial_state: str
    unit_price_micros: int
    billable_unit: str
    tariff_provenance: str
    session_reference: Optional[str] = None
    path_reference: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.transaction_id, "transaction_id")
        _require_text(self.commercial_state, "commercial_state")
        if not isinstance(self.unit_price_micros, int) or isinstance(
            self.unit_price_micros, bool
        ):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "unit_price_micros must be an integer",
            )
        if self.unit_price_micros < 0:
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "unit_price_micros must be >= 0",
            )
        _require_text(self.billable_unit, "billable_unit")
        _require_text(self.tariff_provenance, "tariff_provenance")
        for label, value in (
            ("session_reference", self.session_reference),
            ("path_reference", self.path_reference),
        ):
            if value is not None:
                _require_text(value, label)

    def is_delivery_eligible(self) -> bool:
        """Usage metering is legitimate only once delivery has
        begun on the cited transaction (reservation/lease alone
        never creates usage)."""
        return self.commercial_state in DELIVERY_ELIGIBLE_STATES

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "transaction_id": self.transaction_id,
            "commercial_state": self.commercial_state,
            "unit_price_micros": self.unit_price_micros,
            "billable_unit": self.billable_unit,
            "tariff_provenance": self.tariff_provenance,
        }
        if self.session_reference is not None:
            data["session_reference"] = self.session_reference
        if self.path_reference is not None:
            data["path_reference"] = self.path_reference
        return data

    @classmethod
    def from_dict(cls, data: object) -> "CommercialTransactionSnapshot":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "transaction snapshot must be a mapping",
            )
        for key in (
            "transaction_id",
            "commercial_state",
            "unit_price_micros",
            "billable_unit",
            "tariff_provenance",
        ):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "transaction snapshot is missing required member %r"
                    % key,
                )
        return cls(
            transaction_id=data["transaction_id"],
            commercial_state=data["commercial_state"],
            unit_price_micros=data["unit_price_micros"],
            billable_unit=data["billable_unit"],
            tariff_provenance=data["tariff_provenance"],
            session_reference=data.get("session_reference"),
            path_reference=data.get("path_reference"),
        )


class UsageEvidenceIndex:
    """An immutable snapshot of resolvable usage-evidence inputs.

    Built by the CALLER from the accepted authorities' PUBLIC
    interfaces (the W051 CommercialCore public reads for
    transaction citations and tariffs, the delivery plane's
    public evidence records for delivered-traffic facts) and
    INJECTED into the usage ledger.  The ledger resolves
    observation citations against the index and never against a
    live authority: usage can cite an authority identity only if
    the caller has already read it through that authority's
    public surface.

    The index is frozen at construction (a snapshot, not a live
    view): evidence sets change only by building a new index,
    which keeps observation admission deterministic and
    replay-safe.
    """

    def __init__(
        self,
        evidence: Iterable[DeliveryEvidence],
        transactions: Iterable[CommercialTransactionSnapshot],
    ) -> None:
        evidence_table: Dict[str, DeliveryEvidence] = {}
        for record in evidence:
            if not isinstance(record, DeliveryEvidence):
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "index evidence entries must be DeliveryEvidence values",
                )
            existing = evidence_table.get(record.evidence_id)
            if existing is not None:
                if existing.to_dict() != record.to_dict():
                    raise UsageError(
                        UsageReasonCode.EVIDENCE_MISMATCH,
                        "conflicting index entries for evidence %s"
                        % record.evidence_id,
                    )
                continue
            evidence_table[record.evidence_id] = record
        transaction_table: Dict[str, CommercialTransactionSnapshot] = {}
        for snapshot in transactions:
            if not isinstance(snapshot, CommercialTransactionSnapshot):
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "index transactions must be "
                    "CommercialTransactionSnapshot values",
                )
            existing = transaction_table.get(snapshot.transaction_id)
            if existing is not None:
                if existing.to_dict() != snapshot.to_dict():
                    raise UsageError(
                        UsageReasonCode.EVIDENCE_MISMATCH,
                        "conflicting index entries for transaction %s"
                        % snapshot.transaction_id,
                    )
                continue
            transaction_table[snapshot.transaction_id] = snapshot
        self._evidence: Dict[str, DeliveryEvidence] = dict(evidence_table)
        self._transactions: Dict[str, CommercialTransactionSnapshot] = dict(
            transaction_table
        )

    def __len__(self) -> int:
        return len(self._evidence) + len(self._transactions)

    # ------------------------------------------------------------------
    # fail-closed resolution
    # ------------------------------------------------------------------

    def transaction(self, transaction_id: str) -> CommercialTransactionSnapshot:
        snapshot = self._transactions.get(transaction_id)
        if snapshot is None:
            raise UsageError(
                UsageReasonCode.TRANSACTION_UNKNOWN,
                "commercial transaction %r is not resolvable in the "
                "evidence index (fabricated or unregistered citation)"
                % transaction_id,
            )
        return snapshot

    def evidence(self, evidence_id: str) -> DeliveryEvidence:
        record = self._evidence.get(evidence_id)
        if record is None:
            raise UsageError(
                UsageReasonCode.EVIDENCE_UNKNOWN,
                "delivery evidence %r is not resolvable in the evidence "
                "index (fabricated, stale, or unauthorized citation)"
                % evidence_id,
            )
        return record

    def contains_evidence(self, evidence_id: str) -> bool:
        return evidence_id in self._evidence

    def contains_transaction(self, transaction_id: str) -> bool:
        return transaction_id in self._transactions

    # ------------------------------------------------------------------
    # deterministic reads
    # ------------------------------------------------------------------

    def evidence_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._evidence))

    def transaction_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._transactions))

    def evidence_by_transaction(
        self, transaction_id: str
    ) -> Tuple[DeliveryEvidence, ...]:
        return tuple(
            self._evidence[key]
            for key in sorted(self._evidence)
            if self._evidence[key].transaction_id == transaction_id
        )

    def evidence_counts(self) -> Dict[str, int]:
        """Deterministic kind histogram of the evidence set."""
        counts: Dict[str, int] = {}
        for record in self._evidence.values():
            counts[record.evidence_kind] = (
                counts.get(record.evidence_kind, 0) + 1
            )
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transactions": [
                self._transactions[key].to_dict()
                for key in sorted(self._transactions)
            ],
            "evidence": [
                self._evidence[key].to_dict() for key in sorted(self._evidence)
            ],
        }

    @classmethod
    def from_dict(cls, data: object) -> "UsageEvidenceIndex":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "evidence index must be a mapping",
            )
        for key in ("transactions", "evidence"):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "evidence index is missing required member %r" % key,
                )
        return cls(
            evidence=[
                DeliveryEvidence.from_dict(entry)
                for entry in data["evidence"]
            ],
            transactions=[
                CommercialTransactionSnapshot.from_dict(entry)
                for entry in data["transactions"]
            ],
        )
