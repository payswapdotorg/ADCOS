"""WORK-053 EconomicAllocation external evidence boundary.

The authority-reference model of the economic-allocation layer
(ACR-009 "Economic allocation", W053 contract, authority
boundaries):

- The allocation ledger may REFERENCE billable-final UsageLedger
  projections (WORK-052 authority-owned), W051 commercial
  transaction citations, and EXTERNAL payment-provider /
  settlement-plane reference ids.  It must NEVER own, mutate,
  query, or instantiate those authorities: there is no UsageLedger
  object, CommercialCore object, payment-provider client, or any
  other authority object anywhere in the allocation package.  An
  :class:`AllocationEvidenceIndex` is an immutable snapshot BUILT
  BY THE CALLER from the accepted authorities' PUBLIC interfaces
  (the W051/W052 composition precedent) and INJECTED into the
  allocation ledger.
- **Allocation consumes only billable-final usage facts**: a
  :class:`BillableUsageSnapshot` carries the W052 public usage
  projection state at snapshot-build time.  A usage transaction
  that is not ``BILLABLE_FINAL`` (still ``OBSERVING``) never
  creates allocation (``USAGE_NOT_FINAL``) -- payment success,
  reservation state, offer state, or provider callbacks have no
  path into allocation at all: they are external references,
  structurally ineligible as usage citations
  (``PAYMENT_NOT_USAGE`` / ``SETTLEMENT_NOT_USAGE``).
- **External references are DATA, never commercial truth**: the
  index may carry payment-provider and settlement-plane reference
  snapshots so the ledger's audit trail can show they were seen
  and correlated, but they never feed allocation arithmetic, and
  they never transition allocation state.  A settlement
  acknowledgement may cite a SETTLEMENT reference
  (``PAYMENT_NOT_SETTLEMENT`` guards the kind table); a payment
  callback may cite a PAYMENT reference
  (``SETTLEMENT_NOT_PAYMENT``); neither may impersonate the
  other, and neither may impersonate a usage fact.
- ADCOS does not custody, mint, or move regulated funds here:
  the external reference model records that movement HAPPENED
  outside ADCOS (an identity citation only) and never how much
  moved, for whom, or on what rail -- no amounts, no provider
  names, no provider-specific concepts exist in this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .errors import AllocationError, AllocationReasonCode

#: The W052 usage-transaction states the boundary cites (a
#: citation of the accepted WORK-052 lifecycle vocabulary, read
#: through the UsageLedger public surface by the CALLER when
#: building the snapshot; the allocation ledger never owns or
#: computes the usage lifecycle).  Allocation requires the
#: billable-final state.
USAGE_STATE_FINAL = "BILLABLE_FINAL"
USAGE_STATE_OBSERVING = "OBSERVING"

#: The usage-transaction states a caller may snapshot: the W052
#: frozen two-state vocabulary, cited exactly.
KNOWN_USAGE_STATES = (USAGE_STATE_FINAL, USAGE_STATE_OBSERVING)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


class ReferenceKind:
    """The frozen external-reference kind vocabulary.

    ``SETTLEMENT``: an external settlement-plane confirmation
    (the only kind a settlement acknowledgement may cite).
    ``PAYMENT``: an external payment-provider reference (intent /
    transfer / callback DATA -- the only kind a payment-reference
    record may cite).  Payment references are DATA and never
    transition allocation state; settlement references
    acknowledge external settlement, they never create or reprice
    allocation.
    """

    SETTLEMENT = "settlement"
    PAYMENT = "payment"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.SETTLEMENT, cls.PAYMENT)


@dataclass(frozen=True)
class BillableUsageSnapshot:
    """One WORK-052 public usage-transaction citation (public-read
    DATA, never owned).

    ``usage_state`` is the W052 usage transaction state at
    snapshot-build time (the caller read it through the
    UsageLedger public surface).  ``statement_id`` / ``sealed_at``
    exist only for the ``BILLABLE_FINAL`` state (the sealed
    billable statement identity); ``gross_amount_micros`` is the
    sealed statement's exact integer amount (the allocation input
    -- the billable amount the three-way share must conserve
    against).  ``billable_quantity`` / ``unit_price_micros`` /
    ``billable_unit`` / ``tariff_provenance`` are the sealed
    tariff DATA re-cited for the audit trail.
    ``refunded_amount_micros`` / ``reversed_amount_micros`` /
    ``disputed`` are the W052-side compensation DATA at snapshot
    time (recorded for reconciliation; allocation arithmetic
    consumes the gross billable amount, and W053-level
    compensations are separate append-only facts).
    """

    usage_transaction_id: str
    usage_state: str
    gross_amount_micros: int = 0
    statement_id: Optional[str] = None
    billable_quantity: int = 0
    unit_price_micros: int = 0
    billable_unit: str = ""
    tariff_provenance: str = ""
    refunded_amount_micros: int = 0
    reversed_amount_micros: int = 0
    disputed: bool = False
    sealed_at: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(
            self.usage_transaction_id, "usage_transaction_id"
        )
        if self.usage_state not in KNOWN_USAGE_STATES:
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "usage_state %r must be one of %s (the cited W052 "
                "vocabulary)" % (self.usage_state, list(KNOWN_USAGE_STATES)),
            )
        if not isinstance(self.gross_amount_micros, int) or isinstance(
            self.gross_amount_micros, bool
        ):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "gross_amount_micros must be an integer",
            )
        if self.gross_amount_micros < 0:
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "gross_amount_micros must be >= 0",
            )
        for label in (
            "refunded_amount_micros",
            "reversed_amount_micros",
        ):
            value = getattr(self, label)
            if not isinstance(value, int) or isinstance(value, bool):
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "%s must be an integer" % label,
                )
            if value < 0:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "%s must be >= 0" % label,
                )
        if not isinstance(self.disputed, bool):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "disputed must be a boolean",
            )
        if self.usage_state == USAGE_STATE_FINAL:
            if not self.statement_id:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "a BILLABLE_FINAL snapshot must carry the sealed "
                    "usage statement id",
                )
            if not self.sealed_at:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "a BILLABLE_FINAL snapshot must carry the sealed-at "
                    "instant",
                )
        else:
            if self.statement_id is not None or self.sealed_at is not None:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "a non-final usage snapshot must not carry a sealed "
                    "statement (billable finality has not happened)",
                )
            if self.gross_amount_micros != 0:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "a non-final usage snapshot must carry gross amount 0 "
                    "(there is no sealed billable amount yet)",
                )
        if self.statement_id is not None:
            _require_text(self.statement_id, "statement_id")
        if self.sealed_at is not None:
            _require_text(self.sealed_at, "sealed_at")

    def is_billable_final(self) -> bool:
        return self.usage_state == USAGE_STATE_FINAL

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "usage_transaction_id": self.usage_transaction_id,
            "usage_state": self.usage_state,
            "gross_amount_micros": self.gross_amount_micros,
            "refunded_amount_micros": self.refunded_amount_micros,
            "reversed_amount_micros": self.reversed_amount_micros,
            "disputed": self.disputed,
        }
        if self.statement_id is not None:
            data["statement_id"] = self.statement_id
            data["sealed_at"] = self.sealed_at
            data["billable_quantity"] = self.billable_quantity
            data["unit_price_micros"] = self.unit_price_micros
            data["billable_unit"] = self.billable_unit
            data["tariff_provenance"] = self.tariff_provenance
        return data

    @classmethod
    def from_dict(cls, data: object) -> "BillableUsageSnapshot":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "usage snapshot must be a mapping",
            )
        for key in ("usage_transaction_id", "usage_state"):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "usage snapshot is missing required member %r" % key,
                )
        return cls(
            usage_transaction_id=data["usage_transaction_id"],
            usage_state=data["usage_state"],
            gross_amount_micros=data.get("gross_amount_micros", 0),
            statement_id=data.get("statement_id"),
            billable_quantity=data.get("billable_quantity", 0),
            unit_price_micros=data.get("unit_price_micros", 0),
            billable_unit=str(data.get("billable_unit", "")),
            tariff_provenance=str(data.get("tariff_provenance", "")),
            refunded_amount_micros=data.get("refunded_amount_micros", 0),
            reversed_amount_micros=data.get("reversed_amount_micros", 0),
            disputed=bool(data.get("disputed", False)),
            sealed_at=data.get("sealed_at"),
        )


@dataclass(frozen=True)
class ExternalReferenceSnapshot:
    """One external payment/settlement-plane reference citation
    (DATA only, never commercial truth).

    ``reference_id`` is the EXTERNAL-plane identity string
    (genuinely outside ADCOS; the caller cites deterministic
    external ids with explicit provenance labels).
    ``reference_kind`` separates settlement confirmations from
    payment references (the kind table).  ``provenance`` records
    which external surface produced the reference (a label, never
    a live object, never a provider name).
    ``correlated_usage_transaction_id`` is optional correlation
    DATA: when the external plane recorded which usage
    transaction the reference settles/pays, the caller may carry
    it, and the allocation ledger fail-closes on mismatch
    (``REFERENCE_MISMATCH``).  The snapshot deliberately carries
    NO amount, currency, counterparty, or provider semantics:
    external movement is identified, never quantified or
    interpreted here.
    """

    reference_id: str
    reference_kind: str
    provenance: str
    correlated_usage_transaction_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_text(self.reference_id, "reference_id")
        if self.reference_kind not in ReferenceKind.values():
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "reference_kind %r must be one of %s"
                % (self.reference_kind, list(ReferenceKind.values())),
            )
        _require_text(self.provenance, "provenance")
        if self.correlated_usage_transaction_id is not None:
            _require_text(
                self.correlated_usage_transaction_id,
                "correlated_usage_transaction_id",
            )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "reference_id": self.reference_id,
            "reference_kind": self.reference_kind,
            "provenance": self.provenance,
        }
        if self.correlated_usage_transaction_id is not None:
            data["correlated_usage_transaction_id"] = (
                self.correlated_usage_transaction_id
            )
        return data

    @classmethod
    def from_dict(cls, data: object) -> "ExternalReferenceSnapshot":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "external reference must be a mapping",
            )
        for key in ("reference_id", "reference_kind", "provenance"):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "external reference is missing required member %r"
                    % key,
                )
        return cls(
            reference_id=data["reference_id"],
            reference_kind=data["reference_kind"],
            provenance=data["provenance"],
            correlated_usage_transaction_id=data.get(
                "correlated_usage_transaction_id"
            ),
        )


class AllocationEvidenceIndex:
    """An immutable snapshot of resolvable allocation-evidence
    inputs.

    Built by the CALLER from the accepted authorities' PUBLIC
    interfaces (the WORK-052 UsageLedger public reads for the
    billable-final usage projections; the W051 reference/public
    surface and the external payment/settlement planes for
    reference citations) and INJECTED into the allocation
    ledger.  The ledger resolves citations against the index and
    never against a live authority: allocation can cite a usage
    statement or an external reference only if the caller has
    already read it through that authority's public surface.

    The index is frozen at construction (a snapshot, not a live
    view): evidence sets change only by building a new index,
    which keeps allocation admission deterministic and
    replay-safe.
    """

    def __init__(
        self,
        usage: Iterable[BillableUsageSnapshot],
        references: Iterable[ExternalReferenceSnapshot],
    ) -> None:
        usage_table: Dict[str, BillableUsageSnapshot] = {}
        for snapshot in usage:
            if not isinstance(snapshot, BillableUsageSnapshot):
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "index usage entries must be "
                    "BillableUsageSnapshot values",
                )
            existing = usage_table.get(snapshot.usage_transaction_id)
            if existing is not None:
                if existing.to_dict() != snapshot.to_dict():
                    raise AllocationError(
                        AllocationReasonCode.USAGE_MISMATCH,
                        "conflicting index entries for usage "
                        "transaction %s"
                        % snapshot.usage_transaction_id,
                    )
                continue
            usage_table[snapshot.usage_transaction_id] = snapshot
        reference_table: Dict[str, ExternalReferenceSnapshot] = {}
        for snapshot in references:
            if not isinstance(snapshot, ExternalReferenceSnapshot):
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "index references must be "
                    "ExternalReferenceSnapshot values",
                )
            existing = reference_table.get(snapshot.reference_id)
            if existing is not None:
                if existing.to_dict() != snapshot.to_dict():
                    raise AllocationError(
                        AllocationReasonCode.REFERENCE_MISMATCH,
                        "conflicting index entries for reference %s"
                        % snapshot.reference_id,
                    )
                continue
            reference_table[snapshot.reference_id] = snapshot
        self._usage: Dict[str, BillableUsageSnapshot] = dict(usage_table)
        self._references: Dict[str, ExternalReferenceSnapshot] = dict(
            reference_table
        )

    def __len__(self) -> int:
        return len(self._usage) + len(self._references)

    # ------------------------------------------------------------------
    # fail-closed resolution
    # ------------------------------------------------------------------

    def usage(self, usage_transaction_id: str) -> BillableUsageSnapshot:
        snapshot = self._usage.get(usage_transaction_id)
        if snapshot is None:
            raise AllocationError(
                AllocationReasonCode.USAGE_UNKNOWN,
                "usage transaction %r is not resolvable in the "
                "evidence index (fabricated or unregistered citation)"
                % usage_transaction_id,
            )
        return snapshot

    def reference(self, reference_id: str) -> ExternalReferenceSnapshot:
        snapshot = self._references.get(reference_id)
        if snapshot is None:
            raise AllocationError(
                AllocationReasonCode.REFERENCE_UNKNOWN,
                "external reference %r is not resolvable in the "
                "evidence index (fabricated, stale, or unauthorized "
                "citation)" % reference_id,
            )
        return snapshot

    def contains_usage(self, usage_transaction_id: str) -> bool:
        return usage_transaction_id in self._usage

    def contains_reference(self, reference_id: str) -> bool:
        return reference_id in self._references

    # ------------------------------------------------------------------
    # deterministic reads
    # ------------------------------------------------------------------

    def usage_transaction_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._usage))

    def reference_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._references))

    def usage_states(self) -> Dict[str, int]:
        """Deterministic state histogram of the usage set."""
        counts: Dict[str, int] = {}
        for snapshot in self._usage.values():
            counts[snapshot.usage_state] = (
                counts.get(snapshot.usage_state, 0) + 1
            )
        return counts

    def reference_counts(self) -> Dict[str, int]:
        """Deterministic kind histogram of the reference set."""
        counts: Dict[str, int] = {}
        for snapshot in self._references.values():
            counts[snapshot.reference_kind] = (
                counts.get(snapshot.reference_kind, 0) + 1
            )
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "usage": [
                self._usage[key].to_dict() for key in sorted(self._usage)
            ],
            "references": [
                self._references[key].to_dict()
                for key in sorted(self._references)
            ],
        }

    @classmethod
    def from_dict(cls, data: object) -> "AllocationEvidenceIndex":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "evidence index must be a mapping",
            )
        for key in ("usage", "references"):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "evidence index is missing required member %r" % key,
                )
        return cls(
            usage=[
                BillableUsageSnapshot.from_dict(entry)
                for entry in data["usage"]
            ],
            references=[
                ExternalReferenceSnapshot.from_dict(entry)
                for entry in data["references"]
            ],
        )
