"""M009 usage evidence families — the family-classified citation
surface of the commercial track (LOCK-113 re-bind).

Architecture 1.1 (accepted M002, DEC-0102) makes the canonical
``ConnectivityContract`` the sole durable authority for acquired
connectivity.  The M009 usage re-bind therefore classifies every
public read the caller collects while composing the usage
evidence boundary by FAMILY, with the canonical contract citation
as the commercial family's binding member:

- ``DELIVERY_EVIDENCE`` — delivery-plane evidence identities
  (platform-journal delivery events / intervals) read through the
  delivery plane's public surface.
- ``COMMERCIAL`` — the commercial-authority citation: under the
  M009 re-bind this is the CANONICAL CONTRACT citation (the
  ``contract_id`` member carries it; ``commercial_state`` cites
  the canonical contract state read through the
  ``contracts.ContractStore`` public surface).  The commercial
  family never carries a second contract model — the contract
  reference IS the authority citation (LOCK-101/LOCK-113).
- ``SESSION`` / ``NETWORK_PATH`` — correlation DATA (the W012
  logical-session and W041 NetworkPath identities cited, never
  owned).
- ``PAYMENT`` — external payment observations: DATA only, never
  proof of delivery (the W052 kind-table separation carried
  faithfully onto the family vocabulary).

This module re-establishes the W044-era symbol names
(``EvidenceFamily`` / ``EvidenceReference`` / ``EvidenceIndex`` /
``UsageState``) on the M009 surface — the DEC-0099 disclosure
assigned the era-superseded payment/eligibility battery
re-baselines to the M009 commercial track, and this is the
honest re-establishment: the names carry the M009 semantics
above (family-classified citations for commercial-track
composition), not the superseded W044 usage lifecycle.  The
typed admission surface stays
:class:`~usage.evidence.UsageEvidenceIndex`
(delivery-evidence records + contract-cited commercial
snapshots); the family index is the caller-side composition seam
that feeds it.

Determinism: immutable records, content-validated at
construction, sorted iteration, canonical-JSON round-trips, no
wall clock, no randomness, no network, fail-closed everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple

from .errors import UsageError, UsageReasonCode
from .evidence import CommercialTransactionSnapshot
from .model import UsageTransactionState

#: The canonical contract-id grammar citation (the M002
#: content-derived identity form: ``sha256:`` + 64 lowercase hex
#: digits).  Usage records and settlement references that carry
#: a canonical contract binding MUST match it (LOCK-113).  The
#: check is a pure string predicate (no regex dependency: the
#: family import discipline stays stdlib-value-types + the
#: accepted seams + the canonical contracts domain).
_HEX_DIGITS = frozenset("0123456789abcdef")


def _is_canonical_contract_id(value: str) -> bool:
    if not value.startswith("sha256:"):
        return False
    tail = value[len("sha256:"):]
    return len(tail) == 64 and all(ch in _HEX_DIGITS for ch in tail)


def matches_contract_id_grammar(value: object) -> bool:
    """True iff ``value`` matches the canonical contract-id grammar."""
    return isinstance(value, str) and _is_canonical_contract_id(value)


def validate_contract_id(value: object, label: str) -> str:
    """Fail-closed validation of a canonical contract citation.

    The canonical contract identity is content-derived over the
    contract core (LOCK-101); a usage record or settlement
    reference that claims a canonical binding must carry the
    exact canonical id grammar.  Anything else fails closed
    ``INVALID_INPUT`` — a fabricated or malformed contract
    citation never enters usage state.
    """
    if not (isinstance(value, str) and _is_canonical_contract_id(value)):
        raise UsageError(
            UsageReasonCode.INVALID_INPUT,
            "%s must be a canonical contract id "
            "(sha256:<64 lowercase hex>, the M002 content-derived "
            "grammar): %r" % (label, value),
        )
    return value


class EvidenceFamily:
    """The frozen usage-evidence family vocabulary (M009).

    The families classify the public reads the caller collects
    while composing the usage evidence boundary.  ``COMMERCIAL``
    is the canonical-contract citation family under the M009
    re-bind: its entries carry the ``contract_id`` binding member
    (the canonical authority citation, LOCK-113) and the
    canonical contract state in ``commercial_state``.
    ``PAYMENT`` entries are DATA only: a payment observation can
    never justify usage (the frozen kind-table separation).
    """

    DELIVERY_EVIDENCE = "delivery-evidence"
    COMMERCIAL = "commercial"
    SESSION = "session"
    NETWORK_PATH = "network-path"
    PAYMENT = "payment"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.DELIVERY_EVIDENCE,
            cls.COMMERCIAL,
            cls.SESSION,
            cls.NETWORK_PATH,
            cls.PAYMENT,
        )

    @classmethod
    def usage_eligible_families(cls) -> Tuple[str, ...]:
        """The families that can justify usage: exactly one.

        Only authoritative delivery evidence creates usage; the
        commercial (contract) family carries the authority
        citation that the admission gate consults, and the
        session/network-path families are correlation DATA, but
        the delivered-traffic fact itself always rides the
        ``DELIVERY_EVIDENCE`` family.
        """
        return (cls.DELIVERY_EVIDENCE,)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise UsageError(
            UsageReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _optional_text(value: object, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise UsageError(
            UsageReasonCode.INVALID_INPUT,
            "%s must be a string" % label,
        )
    return value


@dataclass(frozen=True)
class EvidenceReference:
    """One family-classified usage-evidence citation (DATA).

    ``reference_id`` is the authority-owned identity string (a
    delivery-plane evidence id, the canonical contract id, a
    logical session id, a NetworkPath id, or an external payment
    observation id).  ``family`` classifies it;
    ``provenance`` records the public surface it was read from.
    The DATA members carry only what the family legitimately
    consumes: ``instant`` (delivery evidence observation
    instant), ``commercial_state`` + ``contract_id`` (the
    canonical contract citation — the M009 LOCK-113 binding),
    ``session_ref`` / ``path_ref`` (correlation DATA).

    A reference is a citation, never a capability: holding one
    grants no authority access, and a PAYMENT-family reference
    is structurally ineligible as usage evidence.
    """

    reference_id: str
    family: str
    provenance: str
    instant: str = ""
    commercial_state: str = ""
    contract_id: str = ""
    session_ref: str = ""
    path_ref: str = ""

    def __post_init__(self) -> None:
        _require_text(self.reference_id, "reference_id")
        if self.family not in EvidenceFamily.values():
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "family %r must be one of %s"
                % (self.family, list(EvidenceFamily.values())),
            )
        _require_text(self.provenance, "provenance")
        for label, value in (
            ("instant", self.instant),
            ("commercial_state", self.commercial_state),
            ("contract_id", self.contract_id),
            ("session_ref", self.session_ref),
            ("path_ref", self.path_ref),
        ):
            if not isinstance(value, str):
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "%s must be a string" % label,
                )
        if self.contract_id:
            validate_contract_id(self.contract_id, "contract_id")

    def is_usage_eligible(self) -> bool:
        """Only delivery-evidence family entries justify usage."""
        return self.family == EvidenceFamily.DELIVERY_EVIDENCE

    def content(self) -> Dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "family": self.family,
            "provenance": self.provenance,
            "instant": self.instant,
            "commercial_state": self.commercial_state,
            "contract_id": self.contract_id,
            "session_ref": self.session_ref,
            "path_ref": self.path_ref,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content()

    @classmethod
    def from_dict(cls, data: object) -> "EvidenceReference":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "evidence reference must be a mapping",
            )
        for key in ("reference_id", "family", "provenance"):
            if key not in data:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "evidence reference is missing required member %r" % key,
                )
        return cls(
            reference_id=data["reference_id"],
            family=data["family"],
            provenance=data["provenance"],
            instant=data.get("instant", ""),
            commercial_state=data.get("commercial_state", ""),
            contract_id=data.get("contract_id", ""),
            session_ref=data.get("session_ref", ""),
            path_ref=data.get("path_ref", ""),
        )


class EvidenceIndex:
    """An immutable family-classified index of evidence
    citations (the M009 composition seam).

    Built by the CALLER from the authorities' PUBLIC interfaces
    and used to compose the typed admission surface
    (:class:`~usage.evidence.UsageEvidenceIndex`): the
    family-classified reads classify WHAT was read and from
    WHERE, before the caller assembles the typed records the
    usage ledger actually admits.  Fail-closed construction:
    duplicate ids with conflicting content fail closed
    ``EVIDENCE_MISMATCH``; exact duplicates collapse
    deterministically.  Resolution is by exact id (fail closed
    ``EVIDENCE_UNKNOWN`` for fabricated citations), and the
    family view ``by_family`` is the deterministic read the
    composition helpers consume.
    """

    def __init__(self, entries: Iterable[EvidenceReference]) -> None:
        table: Dict[str, EvidenceReference] = {}
        for entry in entries:
            if not isinstance(entry, EvidenceReference):
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "index entries must be EvidenceReference values",
                )
            existing = table.get(entry.reference_id)
            if existing is not None:
                if existing.to_dict() != entry.to_dict():
                    raise UsageError(
                        UsageReasonCode.EVIDENCE_MISMATCH,
                        "conflicting index entries for evidence %s"
                        % entry.reference_id,
                    )
                continue
            table[entry.reference_id] = entry
        self._table: Dict[str, EvidenceReference] = dict(table)

    def __len__(self) -> int:
        return len(self._table)

    def families(self) -> Tuple[str, ...]:
        return tuple(sorted({ref.family for ref in self._table.values()}))

    def by_family(self, family: str) -> Tuple[EvidenceReference, ...]:
        """Deterministic family view (sorted by reference id)."""
        if family not in EvidenceFamily.values():
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "family %r must be one of %s"
                % (family, list(EvidenceFamily.values())),
            )
        return tuple(
            self._table[key]
            for key in sorted(self._table)
            if self._table[key].family == family
        )

    def reference(self, reference_id: str) -> EvidenceReference:
        entry = self._table.get(reference_id)
        if entry is None:
            raise UsageError(
                UsageReasonCode.EVIDENCE_UNKNOWN,
                "evidence citation %r is not resolvable in the family "
                "index (fabricated or unregistered reference)"
                % reference_id,
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
    def from_dict(cls, data: object) -> "EvidenceIndex":
        if not isinstance(data, Mapping):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "evidence index must be a mapping",
            )
        if "references" not in data:
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "evidence index is missing required member 'references'",
            )
        return cls(
            entries=[
                EvidenceReference.from_dict(entry)
                for entry in data["references"]
            ]
        )


#: The M009 name for the usage account state vocabulary: the
#: W052/M009 two-state walk (``OBSERVING`` -> ``BILLABLE_FINAL``,
#: compensations append-only after the seal).  The era name maps
#: exactly onto the current concept — an honest re-establishment
#: of the import surface, not a second state machine.
UsageState = UsageTransactionState

__all__ = [
    "EvidenceFamily",
    "EvidenceIndex",
    "EvidenceReference",
    "UsageState",
    "matches_contract_id_grammar",
    "validate_contract_id",
]
