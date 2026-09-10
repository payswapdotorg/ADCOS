"""M009 usage contract binding — the canonical re-bind of the
usage evidence boundary (LOCK-113).

Architecture 1.1 (accepted M002, DEC-0102) makes the canonical
``ConnectivityContract`` the sole durable authority for acquired
connectivity: usage records and settlement references carry
canonical contract references, NEVER a second contract model.
This module implements that binding for the W052 UsageLedger
surface:

- :class:`ContractCommercialSnapshot` — the contract-cited
  commercial snapshot.  Its ``transaction_id`` IS the canonical
  contract id (validated against the M002 content-derived
  grammar) and its ``commercial_state`` cites the canonical
  contract state (validated against the frozen
  ``contracts.CONTRACT_STATES`` vocabulary, imported from the
  canonical domain — LOCK-101: the vocabulary is consumed,
  never duplicated).  It subclasses the W052
  :class:`~usage.evidence.CommercialTransactionSnapshot`, so
  the typed admission surface (the evidence index, the ledger
  fold, the journals, the digests) carries contract-cited
  snapshots unchanged — every usage record admitted against the
  index is bound to the canonical contract by construction
  (the account key is the contract citation).
- The canonical-state eligibility constants
  (:data:`CONTRACT_DELIVERY_ELIGIBLE_STATES` /
  :data:`CONTRACT_RESERVATION_PHASE_STATES`) — the canonical
  contract states under which usage metering is legitimate
  (delivery begun) versus explicitly rejected (the
  pre-execution reservation phase: reservation/lease state
  never creates usage — the frozen W052 separation carried onto
  the canonical vocabulary).

The contract binding is validated AT CONSTRUCTION (fail
closed): a snapshot whose citation is not a canonical contract
id, or whose state is not a canonical contract state, can never
enter the evidence index, so no usage record can ever be
admitted against a fabricated or non-contract commercial
authority.

Determinism: immutable records, sorted iteration,
canonical-JSON round-trips, injected instants only, no wall
clock, no randomness, no network.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from contracts import CONTRACT_STATES

from .errors import UsageError, UsageReasonCode
from .evidence import CommercialTransactionSnapshot
from .families import validate_contract_id

#: The canonical contract states in which usage metering is
#: legitimate (delivery has begun on the contract: execution
#: active, delivery recorded, assurance states, usage finality,
#: and the settlement walk — all post-delivery).  These cite the
#: frozen M002 ``CONTRACT_STATES`` vocabulary; they are a
#: SUBSET, not a second vocabulary.
CONTRACT_DELIVERY_ELIGIBLE_STATES: Tuple[str, ...] = (
    "EXECUTION_ACTIVE",
    "DELIVERY",
    "ASSURED",
    "DEGRADED",
    "USAGE_FINAL",
    "SETTLEMENT_PENDING",
    "SETTLED",
)

#: The canonical contract states where usage metering is
#: explicitly rejected: the pre-execution phase (intent, offer
#: selection, contract activation without execution).
#: ``CONTRACT_ACTIVE`` is the canonical reservation/lease state
#: (the W051 RESERVATION_HELD counterpart — the explicit
#: ``RESERVATION_NOT_USAGE`` fork); INTENT / OFFER_SELECTED are
#: the generic pre-delivery phases (``TRANSACTION_NOT_DELIVERING``).
CONTRACT_RESERVATION_PHASE_STATES: Tuple[str, ...] = (
    "INTENT",
    "OFFER_SELECTED",
    "CONTRACT_ACTIVE",
)


class ContractCommercialSnapshot(CommercialTransactionSnapshot):
    """The contract-cited commercial snapshot (the M009 re-bind).

    ``transaction_id`` IS the canonical contract id (the M002
    content-derived ``sha256:`` grammar, validated at
    construction); ``commercial_state`` IS the canonical
    contract state (read through the
    :class:`contracts.ContractStore` public surface by the
    CALLER at snapshot-build time, validated against the frozen
    canonical vocabulary here).  ``unit_price_micros`` /
    ``billable_unit`` / ``tariff_provenance`` carry the tariff
    DATA the caller resolved from the contract's opaque
    ``usage-pricing-terms`` reference (LOCK-113: commercial
    terms ride the contract as an opaque reference; the usage
    ledger consumes the resolved integer tariff as DATA).

    Every usage record admitted against an index carrying this
    snapshot cites the canonical contract as its commercial
    authority: the account key (``transaction_id``) is the
    contract citation — LOCK-113 bound, never a second contract
    model.
    """

    def __post_init__(self) -> None:
        # the canonical binding FIRST (fail closed before the
        # base members): the account key is the contract id and
        # the commercial state is the canonical contract state.
        validate_contract_id(self.transaction_id, "contract citation")
        if self.commercial_state not in CONTRACT_STATES:
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "commercial_state %r must be a canonical contract state "
                "(contracts.CONTRACT_STATES, read through the "
                "ContractStore public surface)"
                % (self.commercial_state,),
            )
        # then the frozen base-member discipline
        super().__post_init__()

    def is_delivery_eligible(self) -> bool:
        """Usage metering is legitimate only once delivery has
        begun on the cited CONTRACT (the canonical state gate).

        The canonical pre-delivery states (INTENT,
        OFFER_SELECTED, CONTRACT_ACTIVE) reject metering;
        execution-active and every post-delivery state admit it.
        """
        return self.commercial_state in CONTRACT_DELIVERY_ELIGIBLE_STATES

    def is_reservation_phase(self) -> bool:
        """The canonical reservation/lease state: the contract is
        ACTIVE but execution has not begun -- the canonical
        counterpart of the W051 RESERVATION_HELD fork (reservation
        state never creates usage).  INTENT / OFFER_SELECTED are
        generic pre-delivery phases (TRANSACTION_NOT_DELIVERING),
        exactly like their W051 counterparts."""
        return self.commercial_state == "CONTRACT_ACTIVE"

    def contract_id(self) -> str:
        """The canonical contract citation (the account key)."""
        return self.transaction_id

    def content(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["binding"] = "contract"
        return data

    def to_dict(self) -> Dict[str, Any]:
        return self.content()


def contract_commercial_snapshot(
    *,
    contract_id: str,
    contract_state: str,
    unit_price_micros: int,
    billable_unit: str,
    tariff_provenance: str,
    session_reference: Optional[str] = None,
    path_reference: Optional[str] = None,
) -> ContractCommercialSnapshot:
    """Build one contract-cited commercial snapshot.

    The caller supplies the canonical contract id and the
    canonical contract state (both read through the
    ``contracts.ContractStore`` public surface), plus the
    resolved tariff DATA (integer unit price, billable unit
    label, tariff provenance label).  The construction itself
    validates the canonical binding (fail closed).
    """
    return ContractCommercialSnapshot(
        transaction_id=contract_id,
        commercial_state=contract_state,
        unit_price_micros=unit_price_micros,
        billable_unit=billable_unit,
        tariff_provenance=tariff_provenance,
        session_reference=session_reference,
        path_reference=path_reference,
    )


__all__ = [
    "CONTRACT_DELIVERY_ELIGIBLE_STATES",
    "CONTRACT_RESERVATION_PHASE_STATES",
    "ContractCommercialSnapshot",
    "contract_commercial_snapshot",
]
