"""M009 commercial contract binding — the canonical re-bind of
the CommercialCore commercial track (LOCK-113).

Architecture 1.1 (accepted M002, DEC-0102) makes the canonical
``ConnectivityContract`` the sole durable authority for acquired
connectivity.  The W051 commercial lifecycle (the eleven-state
acquisition walk) is therefore REFACTORED per the frozen
migration matrix row "Commercial: REFACTOR -> Contract/usage/
settlement reference": commercial transactions remain the
commercial RECONCILIATION accounts of the commercial track, but
every account is BOUND to the canonical contract —

- :class:`ContractCitation` — the canonical contract citation
  DATA (contract id + contract state + provenance), validated
  against the M002 content-derived id grammar and the frozen
  ``contracts.CONTRACT_STATES`` vocabulary (imported from the
  canonical domain: LOCK-101 — the vocabulary is consumed,
  never duplicated; the commercial domain runs no second
  contract model).
- :class:`ContractReferenceIndex` — the immutable injected index
  of canonical contract citations, built by the CALLER from the
  ``contracts.ContractStore`` public surface and injected into
  the CommercialCore alongside the W051 reference index.
- :data:`CONTRACT_STATE_FLOOR_BY_ACTION` — the canonical-state
  floor each commercial action requires BEFORE it may run.  The
  commercial reconciliation walk may NEVER run ahead of the
  canonical contract: the contract selects its offers first,
  activates first, records execution/delivery first, reaches
  usage finality first, and settles first.  A forward commercial
  action whose cited contract has not reached the floor fails
  closed ``CONTRACT_STATE_INVALID``; a citation that does not
  resolve fails closed ``CONTRACT_UNKNOWN``.

The bound mode is the M009 normative surface for the commercial
track (the usage, settlement, allocation, and payment batteries
all run bound).  The unbound legacy mode (no injected contract
index) remains constructible for the accepted M003 marketplace
composition and the M006 composition track consumers; their own
tracks own the later re-bases (disclosed in
``docs/M009-evidence.md``).

Determinism: immutable records, sorted iteration,
canonical-JSON round-trips, injected instants only, no wall
clock, no randomness, no network, fail-closed everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple

from contracts import CONTRACT_STATES

from .errors import CommercialError, CommercialReasonCode
from .model import CommercialAction

#: The canonical contract-id grammar citation (the M002
#: content-derived identity form: ``sha256:`` + 64 lowercase hex
#: digits).  Commercial transactions and settlement references
#: that carry a canonical contract binding MUST match it
#: (LOCK-113).  The check is a pure string predicate (no regex
#: dependency: the family import discipline stays stdlib-value-
#: types + the accepted seams + the canonical contracts domain).
_HEX_DIGITS = frozenset("0123456789abcdef")


def _is_canonical_contract_id(value: str) -> bool:
    if not value.startswith("sha256:"):
        return False
    tail = value[len("sha256:"):]
    return len(tail) == 64 and all(ch in _HEX_DIGITS for ch in tail)


def validate_contract_id(value: object, label: str) -> str:
    """Fail-closed validation of a canonical contract citation."""
    if not (isinstance(value, str) and _is_canonical_contract_id(value)):
        raise CommercialError(
            CommercialReasonCode.INVALID_INPUT,
            "%s must be a canonical contract id "
            "(sha256:<64 lowercase hex>, the M002 content-derived "
            "grammar): %r" % (label, value),
        )
    return value


#: The canonical contract-state rank map: the forward §11 walk
#: (INTENT -> OFFER_SELECTED -> CONTRACT_ACTIVE -> EXECUTION_ACTIVE
#: -> DELIVERY -> ASSURED -> USAGE_FINAL -> SETTLEMENT_PENDING ->
#: SETTLED) is linear, with DEGRADED parallel to ASSURED (§9).  A
#: citation at rank >= the action's floor is admitted; terminal
#: states fail every floor (fail closed: a terminal contract
#: admits no forward commercial action).
CONTRACT_STATE_RANK: Dict[str, int] = {
    "INTENT": 0,
    "OFFER_SELECTED": 1,
    "CONTRACT_ACTIVE": 2,
    "EXECUTION_ACTIVE": 3,
    "DELIVERY": 4,
    "ASSURED": 5,
    "DEGRADED": 5,
    "USAGE_FINAL": 6,
    "SETTLEMENT_PENDING": 7,
    "SETTLED": 8,
}


def contract_state_rank(state: str) -> int:
    """The forward-walk rank of a canonical contract state.

    Terminal states (TERMINATED / EXPIRED / FAILED) have no
    forward rank: they fail closed (``None``).
    """
    return CONTRACT_STATE_RANK.get(state, -1)


#: The canonical-state floor per commercial action: the contract
#: must have ALREADY reached this rank before the commercial
#: reconciliation account may record the mirroring fact.  The
#: canonical contract is the authority; the commercial walk
#: mirrors it and never runs ahead (LOCK-113 + LOCK-101).
#: Compensating commercial actions (cancel / expire / path
#: failure / non-delivery) carry no floor: they are
#: commercial-domain compensations gated by their own W051
#: state families; they require only a RESOLVABLE contract
#: citation.
CONTRACT_STATE_FLOOR_BY_ACTION: Dict[str, int] = {
    CommercialAction.SUBMIT_INTENT: CONTRACT_STATE_RANK["INTENT"],
    CommercialAction.SELECT_OFFER: CONTRACT_STATE_RANK["OFFER_SELECTED"],
    CommercialAction.HOLD_RESERVATION: CONTRACT_STATE_RANK["CONTRACT_ACTIVE"],
    CommercialAction.AUTHORIZE_SESSION: CONTRACT_STATE_RANK["CONTRACT_ACTIVE"],
    CommercialAction.ACTIVATE_PATH: CONTRACT_STATE_RANK["CONTRACT_ACTIVE"],
    CommercialAction.START_DELIVERY: CONTRACT_STATE_RANK["EXECUTION_ACTIVE"],
    CommercialAction.ACCRUE_USAGE: CONTRACT_STATE_RANK["EXECUTION_ACTIVE"],
    CommercialAction.COMPLETE_DELIVERY: CONTRACT_STATE_RANK["DELIVERY"],
    CommercialAction.FINALIZE_BILLABLE: CONTRACT_STATE_RANK["USAGE_FINAL"],
    CommercialAction.INITIATE_SETTLEMENT: CONTRACT_STATE_RANK["SETTLEMENT_PENDING"],
    CommercialAction.SETTLE: CONTRACT_STATE_RANK["SETTLED"],
    CommercialAction.CANCEL: -2,  # compensating: citation must resolve
    CommercialAction.EXPIRE: -2,  # compensating: citation must resolve
    CommercialAction.RECORD_PATH_FAILURE: -2,  # compensating
    CommercialAction.RECORD_NON_DELIVERY: -2,  # compensating
}


@dataclass(frozen=True)
class ContractCitation:
    """One canonical contract citation (DATA, never authority).

    ``contract_id`` is the canonical content-derived identity;
    ``contract_state`` is the canonical contract state read
    through the ``contracts.ContractStore`` public surface by
    the CALLER at snapshot-build time; ``provenance`` records
    the public surface it was read from.  A citation is a
    reference, never a capability: the commercial domain
    consumes the canonical state as DATA and never mutates the
    contract, never re-derives its lifecycle, and never hosts a
    second contract model.
    """

    contract_id: str
    contract_state: str
    provenance: str

    def __post_init__(self) -> None:
        validate_contract_id(self.contract_id, "contract_id")
        if self.contract_state not in CONTRACT_STATES:
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "contract_state %r must be a canonical contract state "
                "(contracts.CONTRACT_STATES, read through the "
                "ContractStore public surface)" % (self.contract_state,),
            )
        if not isinstance(self.provenance, str) or not self.provenance:
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "provenance must be a non-empty string",
            )

    def rank(self) -> int:
        """The forward-walk rank (terminal states fail closed)."""
        return contract_state_rank(self.contract_state)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_state": self.contract_state,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ContractCitation":
        if not isinstance(data, Mapping):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "contract citation must be a mapping",
            )
        for key in ("contract_id", "contract_state", "provenance"):
            if key not in data:
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "contract citation is missing required member %r" % key,
                )
        return cls(
            contract_id=data["contract_id"],
            contract_state=data["contract_state"],
            provenance=data["provenance"],
        )


class ContractReferenceIndex:
    """An immutable snapshot of resolvable canonical contract
    citations (fail-closed).

    Built by the CALLER from the ``contracts.ContractStore``
    PUBLIC surface (the contract identity and the CURRENT
    contract state) and INJECTED into the CommercialCore.  The
    core resolves the transaction's contract binding against the
    index and never against the live contract authority: a
    commercial command may cite a contract only if the caller
    has already read it through the contract authority's public
    surface.  The index is frozen at construction (a snapshot,
    not a live view) — reference sets change only by building a
    new index, which keeps command admission deterministic and
    replay-safe.  Duplicate ids with conflicting content fail
    closed at construction; exact duplicates collapse
    deterministically.
    """

    def __init__(self, citations: Iterable[ContractCitation]) -> None:
        table: Dict[str, ContractCitation] = {}
        for citation in citations:
            if not isinstance(citation, ContractCitation):
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "index entries must be ContractCitation values",
                )
            existing = table.get(citation.contract_id)
            if existing is not None:
                if existing.to_dict() != citation.to_dict():
                    raise CommercialError(
                        CommercialReasonCode.INVALID_INPUT,
                        "conflicting index entries for contract %s"
                        % citation.contract_id,
                    )
                continue
            table[citation.contract_id] = citation
        self._table: Dict[str, ContractCitation] = dict(table)

    def __len__(self) -> int:
        return len(self._table)

    def contains(self, contract_id: str) -> bool:
        return contract_id in self._table

    def citation(self, contract_id: str) -> ContractCitation:
        entry = self._table.get(contract_id)
        if entry is None:
            raise CommercialError(
                CommercialReasonCode.CONTRACT_UNKNOWN,
                "canonical contract %r is not resolvable in the injected "
                "contract reference index (fabricated, unregistered, or "
                "not read through the contracts public surface)"
                % contract_id,
            )
        return entry

    def contract_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._table))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citations": [
                self._table[key].to_dict() for key in sorted(self._table)
            ]
        }

    @classmethod
    def from_dict(cls, data: object) -> "ContractReferenceIndex":
        if not isinstance(data, Mapping):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "contract reference index must be a mapping",
            )
        if "citations" not in data:
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "contract reference index is missing required member "
                "'citations'",
            )
        return cls(
            citations=[
                ContractCitation.from_dict(entry)
                for entry in data["citations"]
            ]
        )


def validate_contract_binding(
    action: str, citation: ContractCitation
) -> None:
    """The canonical-state floor gate (fail closed).

    A forward commercial action requires the cited canonical
    contract to have ALREADY reached the action's floor rank:
    the commercial reconciliation walk never runs ahead of the
    canonical contract (LOCK-113).  Terminal contract states
    fail every floor (``CONTRACT_STATE_INVALID``).  Compensating
    actions carry no floor (their W051 state families gate
    them); only citation resolution is required.
    """
    if action not in CONTRACT_STATE_FLOOR_BY_ACTION:
        raise CommercialError(
            CommercialReasonCode.COMMAND_INVALID,
            "action %r is not a commercial action" % (action,),
        )
    floor = CONTRACT_STATE_FLOOR_BY_ACTION[action]
    if floor < 0:
        # compensating action: citation resolved is enough
        return
    rank = citation.rank()
    if rank < 0:
        raise CommercialError(
            CommercialReasonCode.CONTRACT_STATE_INVALID,
            "contract %s is in the terminal state %s (a terminal "
            "contract admits no forward commercial action)"
            % (citation.contract_id, citation.contract_state),
        )
    if rank < floor:
        raise CommercialError(
            CommercialReasonCode.CONTRACT_STATE_INVALID,
            "action %r requires contract %s to have reached the "
            "canonical floor rank %d (found state %s at rank %d); the "
            "commercial walk never runs ahead of the canonical contract"
            % (
                action,
                citation.contract_id,
                floor,
                citation.contract_state,
                rank,
            ),
        )


__all__ = [
    "CONTRACT_STATE_FLOOR_BY_ACTION",
    "CONTRACT_STATE_RANK",
    "ContractCitation",
    "ContractReferenceIndex",
    "contract_state_rank",
    "validate_contract_binding",
    "validate_contract_id",
]
