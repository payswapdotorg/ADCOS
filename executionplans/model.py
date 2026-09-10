"""ADCOS execution-plan domain model (M006 — Execution Plan).

``ExecutionPlan`` is THE bridge from the canonical ``ConnectivityContract``
to concrete provider mechanisms (LOCK-109): a typed, deterministic,
provenance-carrying translation target composed of typed
``ExecutionSegment`` records. It is an EXECUTION ARTIFACT (LOCK-117):
a plan rides as an opaque ``execution-artifact`` reference on the
contract and NEVER becomes a contract authority — a ``Path``,
``Session``, ``Tunnel``, ``Bearer``, ``eSIM``, adapter or provider
record is never an authority, and neither is a plan or a segment.

Authority boundaries (the layering contract):

- **Contracts stay M002 (LOCK-101).** The plan consumes the accepted
  ``contracts/`` public surface by reference; it never mutates
  contract state, never re-derives contract identity, and never
  duplicates the contract model. The hard-constraint set on a plan is
  the contract's own set, preserved VERBATIM (LOCK-108 — see
  ``translation.py`` for the enforcement points).
- **Offers stay M003.** Segments reference accepted offers as the
  contract-shaped ``OpaqueReference`` records the contract itself
  stores; the plan never resolves or evaluates offers.
- **Adapters stay M007 (LOCK-110).** Segments reference
  capability-oriented adapter OPERATIONS by name only, from the frozen
  1.1 §6 vocabulary; provider-native SDK types never enter this model.
- **Replan/failover stays M008.** The M006 segment state vocabulary is
  exactly PLANNED/RESERVED/ACTIVATED/MEASURED/RELEASED; degraded and
  failed realization states belong to the M008 replan surface and are
  deliberately NOT invented here.
- **Provenance is first-class (LOCK-118).** Plans and segments carry
  issuer + decision references.

Determinism discipline (LOCK-119): content-derived ids over canonical
JSON, injected RFC 3339 UTC instants only (no wall clock), sorted and
order-normalized segment iteration, no randomness, no UUIDs, no
network, secret-shaped material rejected at construction and
deserialization time. Segment and plan identities are derived over
STATE-INDEPENDENT cores: segment state evolution (PLANNED → … →
RELEASED) never changes a segment id or the plan id — the execution
artifacts evolve while the contract authority stays stable.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import (
    HardConstraint,
    OpaqueReference,
    Provenance,
    ValidityInterval,
)

from .errors import ExecutionPlanError, ExecutionPlanReason

__all__ = [
    "ADAPTER_OPERATIONS",
    "DEFAULT_TIE_BREAK",
    "PLANNABLE_CONTRACT_STATES",
    "SEGMENT_ROLES",
    "SEGMENT_STATES",
    "SEGMENT_TERMINAL_STATES",
    "SEGMENT_TRANSITIONS",
    "TIE_BREAK_KEYS",
    "ExecutionPlan",
    "ExecutionSegment",
    "apply_segment_transition",
    "check_segment_transition",
    "derive_plan_id",
    "derive_segment_id",
]


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The capability-oriented adapter operation vocabulary (frozen 1.1 §6;
#: LOCK-110 — names only, never provider SDK types; M007 owns the
#: adapters that expose them). The order below is the canonical
#: realization order used to normalize a segment's operation sequence.
ADAPTER_OPERATIONS: Tuple[str, ...] = (
    "inspect-capabilities",
    "inspect-offers",
    "reserve",
    "activate",
    "measure",
    "reconfigure",
    "release",
    "health",
)

_OPERATION_ORDER: Dict[str, int] = {
    operation: index for index, operation in enumerate(ADAPTER_OPERATIONS)
}

#: The segment roles (frozen 1.1 §10 deployment shape): ``primary`` is
#: a main realization segment (multiple primaries compose — LOCK-116);
#: ``alternative`` is a failover alternative under the same contract;
#: ``access`` is an access-mechanism segment.
SEGMENT_ROLES: Tuple[str, ...] = ("primary", "alternative", "access")

#: The frozen segment state vocabulary (M006 scope, exactly these
#: five; the M008 replan surface owns degraded/failed realization
#: states and is NOT invented here).
SEGMENT_STATES: Tuple[str, ...] = (
    "PLANNED",
    "RESERVED",
    "ACTIVATED",
    "MEASURED",
    "RELEASED",
)

#: Terminal segment states (never transition out).
SEGMENT_TERMINAL_STATES: Tuple[str, ...] = ("RELEASED",)

#: Legal segment-state transitions (every transition validated,
#: fail-closed). ``MEASURED -> MEASURED`` is the explicit idempotent
#: re-measurement transition (closed-loop assurance re-observes an
#: active segment); ``PLANNED/RESERVED/ACTIVATED -> RELEASED`` are the
#: cancellation/reservation-release/execution-release edges.
SEGMENT_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "PLANNED": ("RESERVED", "RELEASED"),
    "RESERVED": ("ACTIVATED", "RELEASED"),
    "ACTIVATED": ("MEASURED", "RELEASED"),
    "MEASURED": ("RELEASED", "MEASURED"),
    "RELEASED": (),
}

#: The contract lifecycle states from which a plan may be translated
#: (post-offer-binding, pre-settlement). INTENT has no accepted offers
#: to realize; DELIVERY/ASSURED/USAGE_FINAL/SETTLEMENT_PENDING are
#: post-execution evaluation/settlement states; terminal states never
#: plan. DEGRADED is included: engaging failover alternatives for a
#: degraded realization is the LOCK-116 complex-composition shape
#: (replan semantics themselves stay M008).
PLANNABLE_CONTRACT_STATES: Tuple[str, ...] = (
    "OFFER_SELECTED",
    "CONTRACT_ACTIVE",
    "EXECUTION_ACTIVE",
    "DEGRADED",
)

#: The declared tie-break key vocabulary (LOCK-111: the plan's segment
#: ordering rule is deterministic, injected and declared — every key is
#: a CONTENT key, never a temporal one). ``segment-id`` is the total
#: order guarantee and must be the final component of every declared
#: rule.
TIE_BREAK_KEYS: Tuple[str, ...] = ("role", "operation", "offer", "segment-id")

#: The default injected tie-breaking rule.
DEFAULT_TIE_BREAK: Tuple[str, ...] = ("role", "offer", "segment-id")


_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

_PLAN_NAMESPACE = "adc-os-execution-plan"
_SEGMENT_NAMESPACE = "adc-os-execution-segment"


# ----------------------------------------------------------------------
# Internal helpers (the consumed contracts conventions, by reference)
# ----------------------------------------------------------------------


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, label)
    ).hexdigest()


def _constraints_fingerprint(constraints: Sequence[HardConstraint]) -> str:
    """The LOCK-108 constraint-set digest — the exact M002 convention
    (``ConnectivityContract.hard_constraint_fingerprint``), consumed by
    reference so a plan's fingerprint is byte-comparable with the
    owning contract's own fingerprint."""
    document = [constraint.to_dict() for constraint in constraints]
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes({"constraints": document})
    ).hexdigest()


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "%s must be the content-derived identity (sha256:...)" % label,
        )
    return value


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise ExecutionPlanError(
            ExecutionPlanReason.VOCABULARY,
            "%s must be one of %s (found %r)"
            % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _require_tuple(value: object, label: str, *, min_len: int = 0) -> Tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT, "%s must be a sequence" % label
        )
    if len(value) < min_len:
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "%s requires at least %d member(s)" % (label, min_len),
        )
    return tuple(value)


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT, "%s must be an instant string" % label
        )
    try:
        parse_instant(value)
    except (TemporalError, ValueError) as error:
        raise ExecutionPlanError(
            ExecutionPlanReason.TEMPORAL_INVALID,
            "%s is not a valid instant: %s" % (label, error),
        ) from None
    return value


#: Wrapping a consumed-domain validation error (typed, deterministic;
#: no raw exception text leaks into stored state).
_CONTRACT_CODE_MAP = {
    "secret-rejected": ExecutionPlanReason.SECRET_REJECTED,
    "vocabulary": ExecutionPlanReason.VOCABULARY,
    "temporal-invalid": ExecutionPlanReason.TEMPORAL_INVALID,
    "invalid-input": ExecutionPlanReason.INVALID_INPUT,
}


def _wrap_contract_error(label: str) -> Any:
    """Context manager: a contracts-domain validation error surfaces as
    a typed ExecutionPlanError (exception isolation discipline)."""

    @contextlib.contextmanager
    def _ctx():
        try:
            yield
        except ExecutionPlanError:
            raise
        except ValueError as error:  # ContractError is a ValueError
            code = getattr(error, "code", "")
            mapped = _CONTRACT_CODE_MAP.get(code, ExecutionPlanReason.INVALID_INPUT)
            raise ExecutionPlanError(
                mapped,
                "%s was rejected by the consumed contracts domain: %s"
                % (label, getattr(error, "detail", error)),
            ) from None

    return _ctx()


def _normalize_operations(operations: object, label: str) -> Tuple[str, ...]:
    items = _require_tuple(operations, label, min_len=1)
    seen: Dict[str, int] = {}
    for i, item in enumerate(items):
        _require_in(item, ADAPTER_OPERATIONS, "%s[%d]" % (label, i))
        if item in seen:
            raise ExecutionPlanError(
                ExecutionPlanReason.INVALID_INPUT,
                "%s must not repeat an operation (%s appears twice)" % (label, item),
            )
    # deterministic canonical realization order (frozen 1.1 §6)
    return tuple(sorted(items, key=lambda op: _OPERATION_ORDER[op]))


def _normalize_tie_break(
    tie_break: object, label: str, *, complete: bool = False
) -> Tuple[str, ...]:
    """Validate a declared tie-breaking rule (LOCK-111).

    With ``complete=True`` (the translator) a rule that omits the
    ``segment-id`` key is completed with it (the total-order
    guarantee); with ``complete=False`` (plan construction) the
    stored rule must already end with ``segment-id``.
    """
    items = _require_tuple(tie_break, label, min_len=1)
    for i, item in enumerate(items):
        _require_in(item, TIE_BREAK_KEYS, "%s[%d]" % (label, i))
    if len(set(items)) != len(items):
        raise ExecutionPlanError(
            ExecutionPlanReason.TIE_BREAK_INVALID,
            "%s must not repeat a tie-break key" % label,
        )
    if complete and "segment-id" not in items:
        items = tuple(items) + ("segment-id",)
    if items[-1] != "segment-id":
        raise ExecutionPlanError(
            ExecutionPlanReason.TIE_BREAK_INVALID,
            "%s must end with the segment-id key (the total-order "
            "guarantee; LOCK-111 deterministic ordering)" % label,
        )
    return tuple(items)


def _segment_sort_key(tie_break: Sequence[str]) -> Any:
    """The deterministic sort key for one declared tie-break rule."""

    def key(segment: "ExecutionSegment") -> Tuple:
        components = []
        for tie_key in tie_break:
            if tie_key == "role":
                components.append(segment.role)
            elif tie_key == "operation":
                components.append(segment.operations)
            elif tie_key == "offer":
                components.append(segment.offer_reference.value)
            else:  # segment-id (validated by _normalize_tie_break)
                components.append(segment.segment_id)
        return tuple(components)

    return key


# ----------------------------------------------------------------------
# The execution segment
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionSegment:
    """One typed realization segment of exactly one contract.

    A segment is attributable to its contract (``contract_id`` is the
    content-derived identity of the OWNING canonical contract), carries
    the verbatim accepted-offer reference it realizes (LOCK-117: a
    reference, never an authority; LOCK-118: provenance), a frozen
    role, and the capability-oriented adapter operations it engages
    (LOCK-110: names only — M007 owns the adapters).

    ``segment_id`` is derived over the STATE-INDEPENDENT core
    (contract, offer reference, role, operations, provenance): state
    evolution never changes a segment's identity.
    """

    segment_id: str
    contract_id: str
    offer_reference: OpaqueReference
    role: str
    operations: Tuple[str, ...]
    state: str
    provenance: Provenance

    def __post_init__(self) -> None:
        _require_id(self.segment_id, "segment.segment_id")
        _require_id(self.contract_id, "segment.contract_id")
        with _wrap_contract_error("segment.offer_reference"):
            if not isinstance(self.offer_reference, OpaqueReference):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "segment.offer_reference must be an OpaqueReference",
                )
            if self.offer_reference.ref_kind != "offer":
                raise ExecutionPlanError(
                    ExecutionPlanReason.VOCABULARY,
                    "segment.offer_reference must use the offer reference kind "
                    "(found %s)" % self.offer_reference.ref_kind,
                )
        _require_in(self.role, SEGMENT_ROLES, "segment.role")
        with _wrap_contract_error("segment.operations"):
            object.__setattr__(
                self, "operations", _normalize_operations(self.operations, "segment.operations")
            )
        _require_in(self.state, SEGMENT_STATES, "segment.state")
        with _wrap_contract_error("segment.provenance"):
            if not isinstance(self.provenance, Provenance):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "segment.provenance must be a Provenance record",
                )
        # tamper evidence: the id must equal the content-derived identity
        # over the state-independent core
        expected = _derive_segment_id_from_core(
            self.contract_id, self.offer_reference, self.role, self.operations, self.provenance
        )
        if self.segment_id != expected:
            raise ExecutionPlanError(
                ExecutionPlanReason.ID_MISMATCH,
                "segment_id does not match the derived identity (tamper evidence)",
            )

    def is_terminal(self) -> bool:
        return self.state in SEGMENT_TERMINAL_STATES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "contract_id": self.contract_id,
            "offer_reference": self.offer_reference.to_dict(),
            "role": self.role,
            "operations": list(self.operations),
            "state": self.state,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ExecutionSegment":
        if not isinstance(data, Mapping):
            raise ExecutionPlanError(
                ExecutionPlanReason.INVALID_INPUT, "segment must be a mapping"
            )
        with _wrap_contract_error("segment deserialization"):
            return ExecutionSegment(
                segment_id=data.get("segment_id"),
                contract_id=data.get("contract_id"),
                offer_reference=OpaqueReference.from_dict(data.get("offer_reference")),
                role=data.get("role"),
                operations=tuple(data.get("operations") or ()),
                state=data.get("state") if data.get("state") is not None else "PLANNED",
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "segment record")


def _derive_segment_id_from_core(
    contract_id: str,
    offer_reference: OpaqueReference,
    role: str,
    operations: Sequence[str],
    provenance: Provenance,
) -> str:
    document = {
        "contract_id": contract_id,
        "offer_reference": offer_reference.to_dict(),
        "role": role,
        "operations": list(operations),
        "provenance": provenance.to_dict(),
    }
    return _derive_id(_SEGMENT_NAMESPACE, document, "segment id document")


def derive_segment_id(segment: ExecutionSegment) -> str:
    """Re-derive the identity of a constructed segment (tamper check)."""
    return _derive_segment_id_from_core(
        segment.contract_id,
        segment.offer_reference,
        segment.role,
        segment.operations,
        segment.provenance,
    )


# ----------------------------------------------------------------------
# The execution plan
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionPlan:
    """The contract-to-execution-plan translation target (LOCK-109).

    Field set: the content-derived plan identity; the owning contract
    identity (attribution); the contract's hard-constraint set
    preserved VERBATIM plus its LOCK-108 fingerprint; the plan validity
    window (contained in the contract validity); the typed segments
    (at least one, at least one primary, deterministic declared
    tie-break order); the declared tie-breaking rule; and the planning
    provenance (LOCK-118).

    ``plan_id`` is derived over the STATE-INDEPENDENT core: segment
    state evolution never changes the plan identity (execution
    artifacts evolve while the contract stays stable — LOCK-117).

    The plan is an execution artifact, never an authority: bind it to
    a contract as an opaque ``execution-artifact`` reference via
    ``translation.plan_reference``.
    """

    plan_id: str
    contract_id: str
    hard_constraints: Tuple[HardConstraint, ...]
    constraint_fingerprint: str
    validity: ValidityInterval
    segments: Tuple[ExecutionSegment, ...]
    tie_break: Tuple[str, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        _require_id(self.plan_id, "plan.plan_id")
        _require_id(self.contract_id, "plan.contract_id")
        with _wrap_contract_error("plan.hard_constraints"):
            constraints = _require_tuple(
                self.hard_constraints, "plan.hard_constraints"
            )
            normalized = tuple(
                item if isinstance(item, HardConstraint) else HardConstraint.from_dict(item)
                for item in constraints
            )
            object.__setattr__(self, "hard_constraints", normalized)
        _require_id(self.constraint_fingerprint, "plan.constraint_fingerprint")
        # the carried constraint set must match the carried fingerprint
        # (tamper evidence at the construction boundary)
        if _constraints_fingerprint(self.hard_constraints) != self.constraint_fingerprint:
            raise ExecutionPlanError(
                ExecutionPlanReason.CONSTRAINT_MISMATCH,
                "the plan's LOCK-108 constraint fingerprint does not match the "
                "constraint set it carries (dropped, relaxed, re-interpreted or "
                "reordered constraints fail closed)",
            )
        with _wrap_contract_error("plan.validity"):
            if not isinstance(self.validity, ValidityInterval):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "plan.validity must be a contracts.ValidityInterval",
                )
        with _wrap_contract_error("plan.segments"):
            segments = _require_tuple(self.segments, "plan.segments", min_len=1)
            normalized_segments = tuple(
                item if isinstance(item, ExecutionSegment) else ExecutionSegment.from_dict(item)
                for item in segments
            )
            object.__setattr__(self, "segments", normalized_segments)
        # attribution: every segment belongs to exactly this contract
        for i, segment in enumerate(self.segments):
            if segment.contract_id != self.contract_id:
                raise ExecutionPlanError(
                    ExecutionPlanReason.ID_MISMATCH,
                    "segments[%d] is attributable to contract %s, not %s "
                    "(segments belong to exactly one contract)"
                    % (i, segment.contract_id[:24], self.contract_id[:24]),
                )
        # no duplicate segments (identical content-derived cores)
        segment_ids = [segment.segment_id for segment in self.segments]
        if len(set(segment_ids)) != len(segment_ids):
            raise ExecutionPlanError(
                ExecutionPlanReason.DUPLICATE_SEGMENT,
                "the plan carries duplicate segments (identical content-derived "
                "cores); segments must be distinct",
            )
        # at least one primary realization segment
        if not any(segment.role == "primary" for segment in self.segments):
            raise ExecutionPlanError(
                ExecutionPlanReason.NO_PRIMARY,
                "the plan requires at least one primary realization segment",
            )
        with _wrap_contract_error("plan.tie_break"):
            object.__setattr__(
                self, "tie_break", _normalize_tie_break(self.tie_break, "plan.tie_break")
            )
        # the stored segment order must equal the declared tie-break
        # order (internal consistency; the translator normalizes)
        expected_order = sorted(
            self.segments, key=_segment_sort_key(self.tie_break)
        )
        if tuple(expected_order) != self.segments:
            raise ExecutionPlanError(
                ExecutionPlanReason.INVALID_INPUT,
                "the plan's segment order does not match its declared tie-break "
                "rule %s (deterministic ordering discipline, LOCK-111)"
                % list(self.tie_break),
            )
        with _wrap_contract_error("plan.provenance"):
            if not isinstance(self.provenance, Provenance):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "plan.provenance must be a Provenance record",
                )
        # tamper evidence: the id must equal the content-derived identity
        # over the state-independent core
        expected = _derive_plan_id_from_core(
            self.contract_id,
            self.hard_constraints,
            self.constraint_fingerprint,
            self.validity,
            self.segments,
            self.tie_break,
            self.provenance,
        )
        if self.plan_id != expected:
            raise ExecutionPlanError(
                ExecutionPlanReason.ID_MISMATCH,
                "plan_id does not match the derived identity (tamper evidence)",
            )

    def segment(self, segment_id: str) -> ExecutionSegment:
        """Fail-closed read of one segment by id."""
        for candidate in self.segments:
            if candidate.segment_id == segment_id:
                return candidate
        raise ExecutionPlanError(
            ExecutionPlanReason.SEGMENT_UNKNOWN,
            "segment %s is not carried by plan %s" % (segment_id[:24], self.plan_id[:24]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "contract_id": self.contract_id,
            "hard_constraints": [c.to_dict() for c in self.hard_constraints],
            "constraint_fingerprint": self.constraint_fingerprint,
            "validity": self.validity.to_dict(),
            "segments": [s.to_dict() for s in self.segments],
            "tie_break": list(self.tie_break),
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ExecutionPlan":
        if not isinstance(data, Mapping):
            raise ExecutionPlanError(
                ExecutionPlanReason.INVALID_INPUT, "plan must be a mapping"
            )
        with _wrap_contract_error("plan deserialization"):
            return ExecutionPlan(
                plan_id=data.get("plan_id"),
                contract_id=data.get("contract_id"),
                hard_constraints=tuple(
                    HardConstraint.from_dict(c) for c in data.get("hard_constraints") or ()
                ),
                constraint_fingerprint=data.get("constraint_fingerprint"),
                validity=ValidityInterval.from_dict(data.get("validity")),
                segments=tuple(
                    ExecutionSegment.from_dict(s) for s in data.get("segments") or ()
                ),
                tie_break=tuple(data.get("tie_break") or ()),
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "plan record")


def _derive_plan_id_from_core(
    contract_id: str,
    hard_constraints: Sequence[HardConstraint],
    constraint_fingerprint: str,
    validity: ValidityInterval,
    segments: Sequence[ExecutionSegment],
    tie_break: Sequence[str],
    provenance: Provenance,
) -> str:
    """Content-derived plan identity over the STATE-INDEPENDENT core:
    attribution, the verbatim constraint set and its fingerprint, the
    validity window, the ordered segment identities, the declared
    tie-break rule and the planning provenance. Segment states are
    deliberately absent (identity is stable across execution)."""
    document = {
        "contract_id": contract_id,
        "hard_constraints": [c.to_dict() for c in hard_constraints],
        "constraint_fingerprint": constraint_fingerprint,
        "validity": validity.to_dict(),
        "segment_ids": [s.segment_id for s in segments],
        "tie_break": list(tie_break),
        "provenance": provenance.to_dict(),
    }
    return _derive_id(_PLAN_NAMESPACE, document, "plan id document")


def derive_plan_id(plan: ExecutionPlan) -> str:
    """Re-derive the identity of a constructed plan (tamper check)."""
    return _derive_plan_id_from_core(
        plan.contract_id,
        plan.hard_constraints,
        plan.constraint_fingerprint,
        plan.validity,
        plan.segments,
        plan.tie_break,
        plan.provenance,
    )


# ----------------------------------------------------------------------
# The segment state machine (pure transition kernel)
# ----------------------------------------------------------------------


def check_segment_transition(current: str, target: str) -> None:
    """Fail closed unless current -> target is a legal segment
    transition (every transition validated, fail-closed)."""
    if current in SEGMENT_TERMINAL_STATES:
        raise ExecutionPlanError(
            ExecutionPlanReason.SEGMENT_TERMINAL,
            "segment is terminal in %s; terminal states never transition" % current,
        )
    legal = SEGMENT_TRANSITIONS.get(current, ())
    if target not in legal:
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_TRANSITION,
            "transition %s -> %s is not legal (legal: %s)"
            % (current, target, ", ".join(legal) or "none"),
        )


def apply_segment_transition(
    plan: ExecutionPlan,
    segment_id: str,
    target_state: str,
    *,
    at_instant: str,
) -> ExecutionPlan:
    """Pure transition kernel: advance ONE segment of ONE plan.

    Deterministic and fail-closed:

    - the addressed segment must exist (``plan-segment-unknown``);
    - the transition must be legal (``plan-invalid-transition`` /
      ``plan-segment-terminal``);
    - ``at_instant`` is an injected instant (no wall clock); engaging
      execution mechanisms (RESERVED / ACTIVATED / MEASURED) past the
      plan validity fails closed, while RELEASE remains legal at any
      valid instant (release is cleanup, never an engagement);
    - the successor plan carries the SAME plan identity, the SAME
      segment identity, and the SAME verbatim constraint set (LOCK-108
      is structural: this kernel touches segment state only).
    """
    if not isinstance(plan, ExecutionPlan):
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "apply_segment_transition requires an ExecutionPlan",
        )
    _require_str(segment_id, "transition.segment_id")
    _require_instant(at_instant, "transition.at_instant")
    _require_in(target_state, SEGMENT_STATES, "transition.target_state")
    segment = plan.segment(segment_id)
    check_segment_transition(segment.state, target_state)
    if target_state in ("RESERVED", "ACTIVATED", "MEASURED"):
        if parse_instant(at_instant) > parse_instant(plan.validity.not_after):
            raise ExecutionPlanError(
                ExecutionPlanReason.TEMPORAL_INVALID,
                "engaging %s at %s is past the plan validity not_after %s "
                "(execution engagement fails closed past expiry)"
                % (target_state, at_instant, plan.validity.not_after),
            )
        if parse_instant(at_instant) < parse_instant(plan.validity.not_before):
            raise ExecutionPlanError(
                ExecutionPlanReason.TEMPORAL_INVALID,
                "engaging %s at %s precedes the plan validity not_before %s"
                % (target_state, at_instant, plan.validity.not_before),
            )
    successor_segment = replace(segment, state=target_state)
    successors = tuple(
        successor_segment if item.segment_id == segment_id else item
        for item in plan.segments
    )
    return replace(plan, segments=successors)
