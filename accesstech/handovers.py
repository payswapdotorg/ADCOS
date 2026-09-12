"""ADCOS access-technology handover characteristic declarations
(M020 — Access Technology Capability Envelope, R9-CORE-001, DEC-0120).

The per-handover-kind characteristic declarations of the R9 charter
M020 scope: typed declarations of what every handover of a declared
kind preserves — consumed BY REFERENCE from the accepted
``resilience/`` handover machinery, never duplicated and never
weakened.

The consumed machinery (imported, LOCK-108 by reference):

* the accepted handover machinery (:mod:`resilience.handover`)
  validates every handover candidate against the contract's FULL
  hard-constraint set through the accepted M008 gates
  (``replan.validate_constraints_preserved`` /
  ``replan.candidate_verdict``): a candidate that weakens, drops or
  re-interprets ANY hard constraint is REJECTED with the typed
  kind-citing reason — the constraint-set semantics this module
  declares per kind is the machinery's OWN frozen semantics, never a
  second definition;
* the typed constraint vocabulary is the accepted
  :data:`contracts.CONSTRAINT_KINDS` (the 12-kind frozen set the
  machinery's gates check ``HardConstraint`` records against — the
  same object the accepted ``resilience.model`` freeze-checks on
  import).  It is imported and declared here verbatim; a declaration
  carrying anything other than the FULL set fails closed as a
  LOCK-108 weakening (a subset declares some constraint kinds
  optional across the handover — the machinery never permits that),
  and an unknown kind fails closed as vocabulary drift.

Declared kinds (:data:`HANDOVER_KINDS`) — the handover shapes the R9
gate itself names: ``intra-technology`` (a handover within one
technology class — the M021/M022 access-internal shape), ``cross-
technology`` (the M024 interchange drill: wireline ↔ radio-family ↔
non-terrestrial), ``pass`` (the M022 NGSO pass-handover geometry),
``replacement`` (the M024 technology-REPLACEMENT drill — the "or
replace" half of the gate objective).  The kinds are declared DATA;
the machinery drives the actual handovers.

Per-kind declared characteristics (each fail-closed typed):

* **``preserved_constraint_kinds``** — EXACTLY the imported frozen
  12-kind set, sorted deterministically: the LOCK-108 verbatim
  constraint-set equality across every handover of the kind (the
  accepted machinery enforces it; the declaration states it — never
  weakens it);
* **``explicit_reconnect``** — True, mandatory: every handover of the
  kind is an explicit recorded reconnect event naming BOTH the old
  AND the new references (the WORK-012 discipline the accepted
  runtime journal enforces).  A kind declaring a silent reference
  swap fails closed as HANDOVER_ILLEGAL (never a silent replacement);
* **``contract_continuity``** — True, mandatory: the handover realizes
  the SAME contract (LOCK-101/LOCK-117 — a handover never becomes a
  second contract authority; the successor-contract path is explicit
  renegotiation through the M002 ``superseded-contract`` reference,
  a different mechanism the accepted machinery keeps distinct).  A
  kind declaring contract-breaking semantics fails closed.

Determinism (LOCK-119): content-derived characteristic identities over
canonical JSON (LOCK-106 discipline); canonical-JSON round-trips with
tamper-evident re-verification at reconstruction; no wall clock, no
randomness, no network, no secrets.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes

# BY REFERENCE: the typed constraint vocabulary the accepted handover
# machinery validates candidates against (the same frozen object
# resilience.model imports and freeze-checks).
from contracts import CONSTRAINT_KINDS

from .errors import AccessTechError, AccessTechReason

__all__ = [
    "HANDOVER_KINDS",
    "HandoverCharacteristics",
    "declare_handover_kind",
    "derive_characteristics_id",
    "handover_characteristics_from_mapping",
    "preserved_constraint_kinds",
]


#: The declared handover-kind vocabulary (M020 declared DATA — the
#: handover shapes the R9 charter itself names: the intra-technology
#: access-internal handover, the M024 cross-technology interchange,
#: the M022 NGSO pass handover, the M024 technology replacement).
HANDOVER_KINDS: Tuple[str, ...] = (
    "intra-technology",
    "cross-technology",
    "pass",
    "replacement",
)

#: The per-kind declared preserved-constraint set: the imported frozen
#: vocabulary, sorted deterministically (the LOCK-108 full-set
#: semantics — every handover preserves the contract's hard
#: constraints VERBATIM; the declaration never weakens it).
_PRESERVED_KINDS: Tuple[str, ...] = tuple(sorted(CONSTRAINT_KINDS))

#: Identity namespace (WORK-003 canonical-JSON SHA-256 convention).
_CHARACTERISTICS_NAMESPACE = "adcos.accesstech.handover"

_KIND_NAME_PATTERN_MAX = 64


def _check_consumed_vocabulary() -> None:
    """Fail loud on drift: the imported constraint vocabulary must be
    exactly the frozen 12-kind set the accepted handover machinery
    gates against (never silently mis-declared)."""
    if set(CONSTRAINT_KINDS) != {
        "latency-bound",
        "throughput-floor",
        "availability-floor",
        "loss-bound",
        "jitter-bound",
        "isolation",
        "jurisdiction",
        "security-level",
        "provider-trust",
        "evidence-obligation",
        "geography",
        "priority",
    }:
        raise AccessTechError(
            AccessTechReason.VOCABULARY,
            "the consumed contracts constraint-kind vocabulary has drifted "
            "from the frozen 12-kind set the accepted handover machinery "
            "validates against (fail loud, never silently mis-declared)",
        )


_check_consumed_vocabulary()


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def preserved_constraint_kinds() -> Tuple[str, ...]:
    """The declared per-kind preserved-constraint set (the imported
    frozen vocabulary, sorted deterministically — BY REFERENCE, never
    a duplicated list)."""
    return _PRESERVED_KINDS


def derive_characteristics_id(
    kind: str,
    preserved_kinds: Sequence[str],
    *,
    explicit_reconnect: bool,
    contract_continuity: bool,
) -> str:
    """The content-derived handover-characteristics identity (LOCK-106
    discipline: sha256 over the canonical JSON of the declared
    content)."""
    document = {
        "kind": "adcos.accesstech.handover",
        "handover_kind": kind,
        "preserved_constraint_kinds": list(preserved_kinds),
        "explicit_reconnect": bool(explicit_reconnect),
        "contract_continuity": bool(contract_continuity),
    }
    payload = dict(document)
    payload["namespace"] = _CHARACTERISTICS_NAMESPACE
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, "the handover characteristics")
    ).hexdigest()


@dataclass(frozen=True)
class HandoverCharacteristics:
    """The declared handover characteristics of ONE handover kind:
    the LOCK-108 constraint-preservation declaration (the FULL
    imported frozen constraint-kind set — verbatim equality across
    every handover of the kind), the WORK-012 explicit-reconnect
    discipline (old AND new references recorded — mandatory True),
    and the contract-continuity discipline (the handover realizes the
    SAME contract — mandatory True; LOCK-101/LOCK-117).

    The declaration states the accepted machinery's OWN semantics BY
    REFERENCE: the preserved set is the imported vocabulary (never a
    re-typed list), and any attempt to declare weaker semantics (a
    subset of the kinds, a silent swap, a contract-breaking handover)
    is a typed HANDOVER_ILLEGAL rejection — the declaration layer
    never weakens what the machinery enforces.
    """

    kind: str
    preserved_constraint_kinds: Tuple[str, ...]
    explicit_reconnect: bool
    contract_continuity: bool
    characteristics_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "handover kind must be a string",
            )
        if len(self.kind) > _KIND_NAME_PATTERN_MAX:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "handover kind exceeds %d characters" % _KIND_NAME_PATTERN_MAX,
            )
        if self.kind not in HANDOVER_KINDS:
            raise AccessTechError(
                AccessTechReason.VOCABULARY,
                "handover kind %r is not in the declared kind vocabulary %s"
                % (self.kind, ", ".join(HANDOVER_KINDS)),
            )
        if isinstance(self.preserved_constraint_kinds, (str, bytes)) or not isinstance(
            self.preserved_constraint_kinds, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "preserved_constraint_kinds must be a sequence of strings",
            )
        declared = tuple(self.preserved_constraint_kinds)
        for item in declared:
            if not isinstance(item, str):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "preserved constraint kinds must be strings (found %r)"
                    % (item,),
                )
        if set(declared) - set(CONSTRAINT_KINDS):
            unknown = sorted(set(declared) - set(CONSTRAINT_KINDS))
            raise AccessTechError(
                AccessTechReason.VOCABULARY,
                "preserved constraint kinds %s are outside the accepted "
                "machinery's typed constraint vocabulary (drift — never "
                "declared)" % ", ".join(unknown),
            )
        if set(declared) != set(CONSTRAINT_KINDS):
            missing = sorted(set(CONSTRAINT_KINDS) - set(declared))
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the %s handover kind declares a weakened constraint-"
                "preservation set — LOCK-108: every handover preserves "
                "the contract's hard constraints VERBATIM (missing kinds: "
                "%s; a subset declaration is never accepted)" % (self.kind, ", ".join(missing)),
            )
        if len(declared) != len(set(declared)):
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "the declared preserved-constraint set carries duplicates "
                "(contradictory declaration)",
            )
        object.__setattr__(
            self, "preserved_constraint_kinds", tuple(sorted(declared))
        )
        if self.explicit_reconnect is not True:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the %s handover kind declares a silent reference swap — "
                "the WORK-012 discipline the accepted machinery enforces "
                "is mandatory: every handover is an explicit recorded "
                "reconnect naming BOTH the old AND the new references"
                % self.kind,
            )
        if self.contract_continuity is not True:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the %s handover kind declares contract-breaking semantics "
                "— LOCK-101/LOCK-117: a handover realizes the SAME "
                "contract and never becomes a second contract authority "
                "(the successor-contract path is explicit renegotiation, "
                "a distinct mechanism)" % self.kind,
            )
        derived = derive_characteristics_id(
            self.kind,
            self.preserved_constraint_kinds,
            explicit_reconnect=self.explicit_reconnect,
            contract_continuity=self.contract_continuity,
        )
        if not isinstance(self.characteristics_id, str) or not self.characteristics_id:
            object.__setattr__(self, "characteristics_id", derived)
        elif self.characteristics_id != derived:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "characteristics_id does not match the content-derived "
                "identity (tamper evidence): declared %s, derived %s"
                % (self.characteristics_id, derived),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "preserved_constraint_kinds": list(self.preserved_constraint_kinds),
            "explicit_reconnect": self.explicit_reconnect,
            "contract_continuity": self.contract_continuity,
            "characteristics_id": self.characteristics_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(
            self.content_dict(), "the handover characteristics"
        )


def declare_handover_kind(kind: str) -> HandoverCharacteristics:
    """Declare the characteristics of one handover kind with the
    consumed machinery's OWN frozen semantics: the FULL imported
    constraint-kind preservation set (LOCK-108 verbatim equality), the
    mandatory explicit-reconnect discipline (WORK-012: old AND new
    references recorded) and the mandatory contract-continuity
    discipline (LOCK-101/LOCK-117).  The kind itself is the declared
    DATA; the semantics are imported, never re-typed."""
    return HandoverCharacteristics(
        kind=kind,
        preserved_constraint_kinds=_PRESERVED_KINDS,
        explicit_reconnect=True,
        contract_continuity=True,
    )


def handover_characteristics_from_mapping(
    value: object,
) -> HandoverCharacteristics:
    """Reconstruct :class:`HandoverCharacteristics` from its canonical
    mapping (fail-closed on grammar drift, on every characteristic-
    discipline violation, and on identity tampering — the
    content-derived id is recomputed and compared at load)."""
    if not isinstance(value, Mapping):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the handover characteristics must be a mapping",
        )
    data = dict(value)
    characteristics_id = data.get("characteristics_id")
    if not isinstance(characteristics_id, str) or not characteristics_id:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the handover characteristics lack their content-derived "
            "characteristics_id",
        )
    for member in (
        "kind",
        "preserved_constraint_kinds",
        "explicit_reconnect",
        "contract_continuity",
    ):
        if member not in data:
            raise AccessTechError(
                AccessTechReason.SERIALIZATION_INVALID,
                "the handover characteristics lack the %r member" % member,
            )
    preserved_raw = data["preserved_constraint_kinds"]
    if isinstance(preserved_raw, (str, bytes)) or not isinstance(
        preserved_raw, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "preserved_constraint_kinds must be a sequence of strings",
        )
    return HandoverCharacteristics(
        kind=data["kind"],
        preserved_constraint_kinds=tuple(preserved_raw),
        explicit_reconnect=data["explicit_reconnect"],
        contract_continuity=data["contract_continuity"],
        characteristics_id=characteristics_id,
    )
