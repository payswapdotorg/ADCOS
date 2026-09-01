"""WORK-051 CommercialCore external reference boundary.

The authority-reference model of the commercial core (ACR-009
authority boundaries 1-2, W051 contract invariant 6):

- The commercial core may REFERENCE logical session IDs (WORK-012
  authority-owned), NetworkPath IDs (WORK-041 authority-owned),
  delivery evidence ids (delivery/transport plane), usage record
  ids (WORK-052 future), settlement confirmation ids, and payment
  observation ids (external payment providers, DATA only).
- It must NEVER own, mutate, query, or instantiate those
  authorities: there is no authority object, client, manager, or
  private accessor anywhere in the commercial package.  A
  :class:`ReferenceIndex` is an immutable snapshot mapping
  reference ids to family descriptors, BUILT BY THE CALLER from
  the authorities' PUBLIC interfaces (the W042
  ``session_bindings_from_manager`` composition precedent) and
  INJECTED into the core.
- Fail-closed reference integrity: a command citing a reference
  the index does not carry is rejected ``REFERENCE_UNKNOWN`` (a
  fabricated session or NetworkPath reference can never enter
  commercial state); a reference of the wrong family for the
  command's causal requirement is rejected
  ``REFERENCE_FAMILY_INVALID``; a payment-family reference can
  never satisfy a delivery or settlement requirement
  (``PAYMENT_NOT_DELIVERY`` / ``PAYMENT_NOT_SETTLEMENT`` -- the
  payment/delivery separation is family-table-driven, not
  caller-honor-driven).

References are DATA (id + family + provenance label): they carry
no authority semantics, no trust, and no mutation surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Tuple

from .errors import CommercialError, CommercialReasonCode


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CommercialError(
            CommercialReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


class ReferenceFamily:
    """The frozen external-reference family vocabulary.

    Session, NetworkPath, delivery-evidence, usage, and
    settlement families are the reference families the W051
    contract names (logical session IDs, NetworkPath IDs, delivery
    evidence, usage references) plus the settlement confirmation
    DATA that justifies ``SETTLED``.  The payment family is
    explicitly separate: payment observations are recorded DATA
    and can never justify delivery or settlement events.
    """

    SESSION = "session"
    NETWORK_PATH = "network-path"
    DELIVERY_EVIDENCE = "delivery-evidence"
    USAGE = "usage"
    SETTLEMENT = "settlement"
    PAYMENT = "payment"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.SESSION,
            cls.NETWORK_PATH,
            cls.DELIVERY_EVIDENCE,
            cls.USAGE,
            cls.SETTLEMENT,
            cls.PAYMENT,
        )

    @classmethod
    def authority_families(cls) -> Tuple[str, ...]:
        """The connectivity-authority-owned families the core may
        cite but never own."""
        return (cls.SESSION, cls.NETWORK_PATH, cls.DELIVERY_EVIDENCE, cls.USAGE)

    @classmethod
    def external_families(cls) -> Tuple[str, ...]:
        """The external-plane families (settlement/payment DATA)."""
        return (cls.SETTLEMENT, cls.PAYMENT)


@dataclass(frozen=True)
class Reference:
    """One external reference (id + family + provenance, DATA only).

    ``reference_id`` is the authority-owned identity string (e.g.
    a WORK-012 ``session_id`` fingerprint, a W041
    ``network_path_id`` fingerprint, a delivery-plane evidence
    id).  ``provenance`` records which authority surface produced
    it (a label, never a live object).  A Reference is a citation,
    not a capability: holding one grants no authority access.
    """

    reference_id: str
    family: str
    provenance: str

    def __post_init__(self) -> None:
        _require_text(self.reference_id, "reference_id")
        if self.family not in ReferenceFamily.values():
            raise CommercialError(
                CommercialReasonCode.REFERENCE_FAMILY_INVALID,
                "family %r must be one of %s"
                % (self.family, list(ReferenceFamily.values())),
            )
        _require_text(self.provenance, "provenance")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "family": self.family,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: object) -> "Reference":
        if not isinstance(data, Mapping):
            raise CommercialError(
                CommercialReasonCode.REFERENCE_FAMILY_INVALID,
                "reference must be a mapping",
            )
        for key in ("reference_id", "family", "provenance"):
            if key not in data:
                raise CommercialError(
                    CommercialReasonCode.REFERENCE_FAMILY_INVALID,
                    "reference is missing required member %r" % key,
                )
        return cls(
            reference_id=data["reference_id"],
            family=data["family"],
            provenance=data["provenance"],
        )


class ReferenceIndex:
    """An immutable snapshot of resolvable external references.

    Built by the CALLER from the accepted authorities' PUBLIC
    interfaces (e.g. the session store's established session ids,
    the NetworkPathManager's active paths, the platform journal's
    delivery-plane evidence ids) and INJECTED into the commercial
    core.  The core resolves command references against the index
    and never against a live authority: commercial state can cite
    an authority identity only if the caller has already read it
    through that authority's public surface.

    The index is frozen at construction (a snapshot, not a live
    view): reference sets change only by building a new index,
    which keeps command admission deterministic and replay-safe.
    """

    def __init__(self, references: Iterable[Reference]) -> None:
        table: Dict[str, Reference] = {}
        for reference in references:
            if not isinstance(reference, Reference):
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "index entries must be Reference values",
                )
            existing = table.get(reference.reference_id)
            if existing is not None:
                if (
                    existing.family != reference.family
                    or existing.provenance != reference.provenance
                ):
                    raise CommercialError(
                        CommercialReasonCode.REFERENCE_FAMILY_INVALID,
                        "conflicting index entries for reference %s"
                        % reference.reference_id,
                    )
                continue
            table[reference.reference_id] = reference
        self._table: Dict[str, Reference] = dict(table)

    def __len__(self) -> int:
        return len(self._table)

    def contains(self, reference_id: str) -> bool:
        return reference_id in self._table

    def get(self, reference_id: str) -> Reference:
        reference = self._table.get(reference_id)
        if reference is None:
            raise CommercialError(
                CommercialReasonCode.REFERENCE_UNKNOWN,
                "external reference %r is not resolvable in the reference "
                "index (fabricated or evicted reference)" % reference_id,
            )
        return reference

    def families(self) -> FrozenSet[str]:
        return frozenset(ref.family for ref in self._table.values())

    def by_family(self, family: str) -> Tuple[Reference, ...]:
        if family not in ReferenceFamily.values():
            raise CommercialError(
                CommercialReasonCode.REFERENCE_FAMILY_INVALID,
                "family %r must be one of %s"
                % (family, list(ReferenceFamily.values())),
            )
        return tuple(
            self._table[key] for key in sorted(self._table)
            if self._table[key].family == family
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "references": [
                self._table[key].to_dict() for key in sorted(self._table)
            ]
        }


def resolve_references(
    index: ReferenceIndex,
    references: Tuple[Reference, ...],
) -> Tuple[Reference, ...]:
    """Resolve every cited reference against the index.

    Fail-closed: an unknown reference id (fabricated session /
    NetworkPath / delivery-evidence citation) raises
    ``REFERENCE_UNKNOWN`` BEFORE any commercial state changes.
    Resolution returns the INDEX-AUTHORITATIVE records (the
    index is the family authority): a citation claiming one
    family while the index records another is judged by the
    index family in command admission (the payment/delivery
    separation in :mod:`commercial.validation` -- a payment id
    cited in a delivery-evidence slot resolves as payment-family
    and fails closed ``PAYMENT_NOT_DELIVERY``).  Duplicate ids in
    one citation collapse deterministically (sorted, unique).
    """
    resolved: Dict[str, Reference] = {}
    for reference in references:
        known = index.get(reference.reference_id)
        resolved[reference.reference_id] = known
    return tuple(resolved[key] for key in sorted(resolved))


def reference_family_counts(references: Tuple[Reference, ...]) -> Dict[str, int]:
    """Deterministic family histogram of a resolved reference tuple."""
    counts: Dict[str, int] = {}
    for reference in references:
        counts[reference.family] = counts.get(reference.family, 0) + 1
    return counts
