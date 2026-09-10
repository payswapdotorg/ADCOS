"""M009 allocation fact families — the family-classified
citation surface of the economic-allocation track (LOCK-113
re-bind).

Architecture 1.1 (accepted M002, DEC-0102) makes the canonical
``ConnectivityContract`` the sole durable authority for acquired
connectivity.  The M009 re-bind classifies every public read the
caller collects while composing the allocation evidence
boundary by FAMILY, with the canonical contract citation as the
binding member of the usage and commercial facts:

- ``USAGE_FINAL`` — the W052 billable-final usage fact (the
  sealed statement identity + the billable amount the three-way
  split conserves against); under the M009 re-bind the usage
  account key IS the canonical contract id, so every usage-final
  fact citation carries the contract binding
  (``contract_id``).
- ``COMMERCIAL`` — the commercial reconciliation account
  citation (the contract-bound commercial transaction); carries
  the canonical ``contract_id`` binding member.
- ``SETTLEMENT`` — the external settlement-plane confirmation
  reference (DATA only: the reference identifies external
  movement; ADCOS never custodies or moves funds).
- ``PAYMENT_PROVIDER`` — the external payment-provider
  observation (DATA only: payment callbacks never transition or
  reprice allocation).

This module re-establishes the W044-era symbol names
(``FactFamily`` / ``FactReference`` / ``FactIndex`` /
``AllocationState`` / ``EconomicPolicy``) on the M009 surface —
the DEC-0099 disclosure assigned the era-superseded
payment/eligibility battery re-baselines to the M009 commercial
track, and this is the honest re-establishment: the names carry
the M009 family-classified semantics above, not the superseded
W044 allocation lifecycle.  The typed admission surface stays
:class:`~allocation.evidence.AllocationEvidenceIndex`
(billable-usage snapshots + external references); the family
index is the caller-side composition seam that feeds it.
``AllocationState`` and ``EconomicPolicy`` are concept aliases
of the current :class:`~allocation.model.AllocationSubjectState`
and :class:`~allocation.model.PolicyVersion` — the era names
for the same frozen concepts, never a second state machine or
policy model.

Determinism: immutable records, content-validated at
construction, sorted iteration, canonical-JSON round-trips, no
wall clock, no randomness, no network, fail-closed everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple

from .errors import AllocationError, AllocationReasonCode
from .model import AllocationSubjectState, PolicyVersion

_HEX_DIGITS = frozenset("0123456789abcdef")


def matches_contract_id_grammar(value: object) -> bool:
    """True iff ``value`` matches the canonical contract-id
    grammar (``sha256:`` + 64 lowercase hex digits, the M002
    content-derived identity form — a grammar citation, not a
    second vocabulary)."""
    if not isinstance(value, str):
        return False
    if not value.startswith("sha256:"):
        return False
    tail = value[len("sha256:"):]
    return len(tail) == 64 and all(ch in _HEX_DIGITS for ch in tail)


def validate_contract_id(value: object, label: str) -> str:
    """Fail-closed validation of a canonical contract citation
    (LOCK-113): fact references that carry a canonical contract
    binding MUST match the canonical id grammar."""
    if not matches_contract_id_grammar(value):
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be a canonical contract id "
            "(sha256:<64 lowercase hex>, the M002 content-derived "
            "grammar): %r" % (label, value),
        )
    return value


class FactFamily:
    """The frozen allocation fact-family vocabulary (M009).

    ``USAGE_FINAL`` is the allocation-creating fact family (the
    sealed billable statement read through the UsageLedger
    public surface); ``COMMERCIAL`` is the contract-bound
    commercial account citation; ``SETTLEMENT`` and
    ``PAYMENT_PROVIDER`` are external-plane DATA (never
    allocation-creating, never repricing).
    """

    USAGE_FINAL = "usage-final"
    COMMERCIAL = "commercial"
    SETTLEMENT = "settlement"
    PAYMENT_PROVIDER = "payment-provider"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.USAGE_FINAL,
            cls.COMMERCIAL,
            cls.SETTLEMENT,
            cls.PAYMENT_PROVIDER,
        )

    @classmethod
    def allocation_creating_families(cls) -> Tuple[str, ...]:
        """The families that can create allocation: exactly one."""
        return (cls.USAGE_FINAL,)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _optional_text(value: object, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be a string" % label,
        )
    return value


def _optional_int(value: object, label: str) -> int:
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool):
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be an integer" % label,
        )
    return value


@dataclass(frozen=True)
class FactReference:
    """One family-classified allocation fact citation (DATA).

    ``reference_id`` is the authority-owned identity string
    (the sealed billable-statement record id, the commercial
    transaction id, or an external reference id).  ``family``
    classifies it; ``provenance`` records the public surface it
    was read from.  The DATA members carry only what the family
    legitimately consumes: the usage-final projection
    (``usage_state`` / ``transaction_id`` / ``amount`` /
    ``quantity`` / ``unit`` / ``finalized_at``), the commercial
    projection (``commercial_state`` / ``session_ref`` /
    ``path_ref``), and — for the contract-bound M009 citations —
    the canonical ``contract_id`` (LOCK-113 binding, validated
    when non-empty).

    A fact reference is a citation, never a capability; a
    SETTLEMENT or PAYMENT_PROVIDER reference is structurally
    ineligible as an allocation-creating fact.
    """

    reference_id: str
    family: str
    provenance: str
    usage_state: str = ""
    transaction_id: str = ""
    amount: int = 0
    quantity: int = 0
    unit: str = ""
    finalized_at: str = ""
    commercial_state: str = ""
    contract_id: str = ""
    session_ref: str = ""
    path_ref: str = ""

    def __post_init__(self) -> None:
        _require_text(self.reference_id, "reference_id")
        if self.family not in FactFamily.values():
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "family %r must be one of %s"
                % (self.family, list(FactFamily.values())),
            )
        _require_text(self.provenance, "provenance")
        for label, value in (
            ("usage_state", self.usage_state),
            ("transaction_id", self.transaction_id),
            ("unit", self.unit),
            ("finalized_at", self.finalized_at),
            ("commercial_state", self.commercial_state),
            ("contract_id", self.contract_id),
            ("session_ref", self.session_ref),
            ("path_ref", self.path_ref),
        ):
            if not isinstance(value, str):
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "%s must be a string" % label,
                )
        for label, value in (
            ("amount", self.amount),
            ("quantity", self.quantity),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "%s must be an integer" % label,
                )
            if value < 0:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "%s must be non-negative" % label,
                )
        if self.contract_id:
            validate_contract_id(self.contract_id, "contract_id")

    def is_allocation_creating(self) -> bool:
        """Only usage-final family entries create allocation."""
        return self.family == FactFamily.USAGE_FINAL

    def content(self) -> Dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "family": self.family,
            "provenance": self.provenance,
            "usage_state": self.usage_state,
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "quantity": self.quantity,
            "unit": self.unit,
            "finalized_at": self.finalized_at,
            "commercial_state": self.commercial_state,
            "contract_id": self.contract_id,
            "session_ref": self.session_ref,
            "path_ref": self.path_ref,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content()

    @classmethod
    def from_dict(cls, data: object) -> "FactReference":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "fact reference must be a mapping",
            )
        for key in ("reference_id", "family", "provenance"):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "fact reference is missing required member %r" % key,
                )
        return cls(
            reference_id=data["reference_id"],
            family=data["family"],
            provenance=data["provenance"],
            usage_state=data.get("usage_state", ""),
            transaction_id=data.get("transaction_id", ""),
            amount=data.get("amount", 0),
            quantity=data.get("quantity", 0),
            unit=data.get("unit", ""),
            finalized_at=data.get("finalized_at", ""),
            commercial_state=data.get("commercial_state", ""),
            contract_id=data.get("contract_id", ""),
            session_ref=data.get("session_ref", ""),
            path_ref=data.get("path_ref", ""),
        )


class FactIndex:
    """An immutable family-classified index of allocation fact
    citations (the M009 composition seam).

    Built by the CALLER from the authorities' PUBLIC interfaces
    and used to compose the typed admission surface
    (:class:`~allocation.evidence.AllocationEvidenceIndex`).
    Fail-closed construction: duplicate ids with conflicting
    content fail closed; exact duplicates collapse
    deterministically.  Resolution is by exact id (fail closed
    for fabricated citations); the family view ``by_family`` is
    the deterministic read the composition helpers consume.
    """

    def __init__(self, entries: Iterable[FactReference]) -> None:
        table: Dict[str, FactReference] = {}
        for entry in entries:
            if not isinstance(entry, FactReference):
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "index entries must be FactReference values",
                )
            existing = table.get(entry.reference_id)
            if existing is not None:
                if existing.to_dict() != entry.to_dict():
                    raise AllocationError(
                        AllocationReasonCode.INVALID_INPUT,
                        "conflicting index entries for fact %s"
                        % entry.reference_id,
                    )
                continue
            table[entry.reference_id] = entry
        self._table: Dict[str, FactReference] = dict(table)

    def __len__(self) -> int:
        return len(self._table)

    def families(self) -> Tuple[str, ...]:
        return tuple(sorted({ref.family for ref in self._table.values()}))

    def by_family(self, family: str) -> Tuple[FactReference, ...]:
        """Deterministic family view (sorted by reference id)."""
        if family not in FactFamily.values():
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "family %r must be one of %s"
                % (family, list(FactFamily.values())),
            )
        return tuple(
            self._table[key]
            for key in sorted(self._table)
            if self._table[key].family == family
        )

    def fact(self, reference_id: str) -> FactReference:
        entry = self._table.get(reference_id)
        if entry is None:
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "fact citation %r is not resolvable in the family index "
                "(fabricated or unregistered reference)" % reference_id,
            )
        return entry

    def contains(self, reference_id: str) -> bool:
        return reference_id in self._table

    def reference_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._table))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "references": [
                self._table[key].to_dict() for key in sorted(self._table)
            ]
        }

    @classmethod
    def from_dict(cls, data: object) -> "FactIndex":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "fact index must be a mapping",
            )
        if "references" not in data:
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "fact index is missing required member 'references'",
            )
        return cls(
            entries=[
                FactReference.from_dict(entry)
                for entry in data["references"]
            ]
        )


#: The M009 name for the allocation account state vocabulary: the
#: W053/M009 two-state walk (``PLANNED`` -> ``SETTLED``,
#: compensations append-only after the snapshot).  A concept
#: alias of :class:`~allocation.model.AllocationSubjectState` —
#: the era name for the same frozen concept, never a second
#: state machine.
AllocationState = AllocationSubjectState

#: The M009 name for the immutable economic-policy version: a
#: concept alias of :class:`~allocation.model.PolicyVersion` —
#: the era name for the same frozen concept (terms-derived
#: identity, immutable after registration), never a second
#: policy model.
EconomicPolicy = PolicyVersion

__all__ = [
    "AllocationState",
    "EconomicPolicy",
    "FactFamily",
    "FactIndex",
    "FactReference",
    "matches_contract_id_grammar",
    "validate_contract_id",
]
