"""The M006 contract-to-execution-plan translation (LOCK-109).

``translate_contract`` is the canonical bridge: it consumes an ACCEPTED
canonical ``ConnectivityContract`` (the M002 authority — by reference,
never modified, never duplicated) together with the optimizer's
proposed ``SegmentInput`` records and produces a typed, deterministic,
provenance-carrying ``ExecutionPlan``.

LOCK-108 enforcement points (no silent contract weakening — every
attempt fails closed with a typed error):

1. **No override surface.** The translation carries NO constraint
   input: the plan's hard-constraint set is copied VERBATIM from the
   contract and the plan's LOCK-108 fingerprint is the contract's OWN
   ``hard_constraint_fingerprint()`` output (the M002 evidence API,
   consumed by reference). There is no input path that can weaken,
   drop, relax or re-interpret a constraint.
2. **Tamper evidence at the boundary.** Plan construction and
   deserialization verify that the carried constraint set matches the
   carried fingerprint and the content-derived plan identity
   (``plan-constraint-mismatch`` / ``plan-id-mismatch``).
3. **Cross-authority verification.** ``verify_plan_preserves_contract``
   is the pure LOCK-108 gate: a plan presented against a contract
   fails closed unless the constraint set is preserved VERBATIM (set
   equality by canonical content, both directions), the fingerprints
   agree, the attribution agrees, every segment's offer reference is a
   verbatim accepted-offer reference, and the plan window lies within
   the contract validity.

LOCK-111 (optimizer replaceability): the optimizer is replaceable —
its proposal arrives as data (``SegmentInput`` records) and can never
override hard contract constraints, identity/trust authorization,
evidence obligations or policy prohibitions. The plan SHAPE (contract
attribution, verbatim constraints, validity containment, offer
realization) is authority-true — derived from the contract, not from
the optimizer. Tie-breaking is deterministic, DECLARED and INJECTED
(the ``tie_break`` rule), never wall-clock: same input snapshot and
declared rule produce the byte-identical plan regardless of the
proposal's input order.

LOCK-117: ``plan_reference`` is the sole bridge back toward the
contract — the plan rides as an opaque ``execution-artifact``
reference (data, never authority), bindable through the contract's own
frozen ``BindExecutionArtifact`` command vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import parse_instant

from contracts import (
    ConnectivityContract,
    OpaqueReference,
    Provenance,
    ValidityInterval,
)

from .errors import ExecutionPlanError, ExecutionPlanReason
from .model import (
    ADAPTER_OPERATIONS,
    DEFAULT_TIE_BREAK,
    PLANNABLE_CONTRACT_STATES,
    SEGMENT_ROLES,
    ExecutionPlan,
    ExecutionSegment,
    _derive_plan_id_from_core,
    _derive_segment_id_from_core,
    _normalize_operations,
    _normalize_tie_break,
    _segment_sort_key,
    _require_in,
    _require_tuple,
    _wrap_contract_error,
)

__all__ = [
    "SegmentInput",
    "plan_reference",
    "translate_contract",
    "verify_plan_preserves_contract",
]


# ----------------------------------------------------------------------
# The optimizer's proposal record (replaceable strategy, data only)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentInput:
    """One optimizer-proposed segment, as DATA (LOCK-111: the strategy
    is replaceable; its proposal can never override the authority-true
    plan shape).

    ``offer_reference`` must be a VERBATIM member of the owning
    contract's ``accepted_offers`` (value and provenance — a lookalike
    reference fails closed). ``operations`` may arrive in any order;
    the translator normalizes them into the frozen canonical §6
    realization order. There is deliberately NO constraint member: the
    plan's hard-constraint set is the contract's own (LOCK-108).
    """

    offer_reference: OpaqueReference
    role: str
    operations: Tuple[str, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        with _wrap_contract_error("segment_input.offer_reference"):
            if not isinstance(self.offer_reference, OpaqueReference):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "segment_input.offer_reference must be an OpaqueReference",
                )
            if self.offer_reference.ref_kind != "offer":
                raise ExecutionPlanError(
                    ExecutionPlanReason.VOCABULARY,
                    "segment_input.offer_reference must use the offer reference "
                    "kind (found %s)" % self.offer_reference.ref_kind,
                )
        _require_in(self.role, SEGMENT_ROLES, "segment_input.role")
        with _wrap_contract_error("segment_input.operations"):
            object.__setattr__(
                self,
                "operations",
                _require_tuple(self.operations, "segment_input.operations", min_len=1),
            )
            for i, item in enumerate(self.operations):
                _require_in(
                    item, ADAPTER_OPERATIONS, "segment_input.operations[%d]" % i
                )
            if len(set(self.operations)) != len(self.operations):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "segment_input.operations must not repeat an operation",
                )
        with _wrap_contract_error("segment_input.provenance"):
            if not isinstance(self.provenance, Provenance):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "segment_input.provenance must be a Provenance record",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_reference": self.offer_reference.to_dict(),
            "role": self.role,
            "operations": list(self.operations),
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "SegmentInput":
        if not isinstance(data, Mapping):
            raise ExecutionPlanError(
                ExecutionPlanReason.INVALID_INPUT, "segment input must be a mapping"
            )
        with _wrap_contract_error("segment input deserialization"):
            return SegmentInput(
                offer_reference=OpaqueReference.from_dict(data.get("offer_reference")),
                role=data.get("role"),
                operations=tuple(data.get("operations") or ()),
                provenance=Provenance.from_dict(data.get("provenance")),
            )


# ----------------------------------------------------------------------
# The canonical bridge (LOCK-109)
# ----------------------------------------------------------------------


def translate_contract(
    contract: ConnectivityContract,
    segments: Sequence[SegmentInput],
    *,
    provenance: Provenance,
    plan_window: Optional[ValidityInterval] = None,
    tie_break: Sequence[str] = DEFAULT_TIE_BREAK,
) -> ExecutionPlan:
    """Translate one accepted canonical contract into one typed
    execution plan (the LOCK-109 bridge; deterministic and offline).

    Fail-closed gates, in order:

    - the input must be a ``contracts.ConnectivityContract`` in a
      plannable lifecycle state (accepted offers bound, pre-settlement,
      non-terminal — ``plan-contract-not-plannable``);
    - at least one ``SegmentInput`` (``plan-invalid-input``);
    - every proposed offer reference must be a VERBATIM member of the
      contract's accepted offers (``plan-offer-not-accepted``);
    - the declared tie-break rule must be valid (``plan-tie-break-invalid``)
      and is normalized to end with the ``segment-id`` total order;
    - the plan window (default: the contract validity) must lie within
      the contract validity (``plan-temporal-invalid``);
    - segment cores must be distinct (``plan-duplicate-segment``) and
      at least one primary realization must exist
      (``plan-no-primary-segment``).

    The plan's hard-constraint set and LOCK-108 fingerprint are taken
    from the CONTRACT (never from the inputs); segments are normalized
    (canonical §6 operation order) and deterministically ordered by the
    declared tie-break rule; the plan identity is content-derived over
    the state-independent core. Same inputs and declared rule produce
    the byte-identical plan regardless of input order (LOCK-111).
    """
    if not isinstance(contract, ConnectivityContract):
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "translate_contract requires a contracts.ConnectivityContract",
        )
    if not isinstance(segments, (tuple, list)) or isinstance(segments, (str, bytes)):
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "translate_contract requires a sequence of SegmentInput records",
        )
    if not segments:
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "translate_contract requires at least one SegmentInput",
        )
    for i, item in enumerate(segments):
        if not isinstance(item, SegmentInput):
            raise ExecutionPlanError(
                ExecutionPlanReason.INVALID_INPUT,
                "segments[%d] must be a SegmentInput record" % i,
            )
    with _wrap_contract_error("translate.provenance"):
        if not isinstance(provenance, Provenance):
            raise ExecutionPlanError(
                ExecutionPlanReason.INVALID_INPUT,
                "translate_contract requires planning provenance (LOCK-118)",
            )

    # the plannable-state gate (LOCK-109: the bridge consumes ACCEPTED
    # contracts with bound offers; terminal/post-execution states fail)
    if contract.state not in PLANNABLE_CONTRACT_STATES:
        raise ExecutionPlanError(
            ExecutionPlanReason.NOT_PLANNABLE,
            "a contract in %s is not plan-translatable (plannable: %s; INTENT "
            "has no accepted offers; terminal and post-execution states never "
            "plan)" % (contract.state, ", ".join(PLANNABLE_CONTRACT_STATES)),
        )
    if not contract.accepted_offers:
        raise ExecutionPlanError(
            ExecutionPlanReason.NOT_PLANNABLE,
            "the contract carries no accepted offer references to realize",
        )

    # the declared tie-breaking rule (LOCK-111): validated and
    # completed with the segment-id total order when omitted
    normalized_tie_break = _normalize_tie_break(
        tie_break, "translate.tie_break", complete=True
    )

    # the plan window: default the contract validity; always contained
    if plan_window is None:
        window = contract.validity
    else:
        with _wrap_contract_error("translate.plan_window"):
            if not isinstance(plan_window, ValidityInterval):
                raise ExecutionPlanError(
                    ExecutionPlanReason.INVALID_INPUT,
                    "plan_window must be a contracts.ValidityInterval",
                )
        window = plan_window
        if parse_instant(window.not_before) < parse_instant(contract.validity.not_before):
            raise ExecutionPlanError(
                ExecutionPlanReason.TEMPORAL_INVALID,
                "plan window not_before %s precedes the contract validity "
                "not_before %s (the plan realizes only within the contract "
                "window)" % (window.not_before, contract.validity.not_before),
            )
        if parse_instant(window.not_after) > parse_instant(contract.validity.not_after):
            raise ExecutionPlanError(
                ExecutionPlanReason.TEMPORAL_INVALID,
                "plan window not_after %s exceeds the contract validity "
                "not_after %s" % (window.not_after, contract.validity.not_after),
            )

    # LOCK-108 (point 1): the constraint set and fingerprint come from
    # the CONTRACT — there is no input path that can weaken them
    hard_constraints = tuple(contract.hard_constraints)
    constraint_fingerprint = contract.hard_constraint_fingerprint()

    # realize segments over VERBATIM accepted offer references only
    built: list = []
    for i, item in enumerate(segments):
        if item.offer_reference not in contract.accepted_offers:
            raise ExecutionPlanError(
                ExecutionPlanReason.OFFER_NOT_ACCEPTED,
                "segments[%d] proposes offer reference %s which is not a "
                "verbatim member of the contract's accepted offers "
                "(segments realize exactly the accepted offers)"
                % (i, item.offer_reference.value[:24]),
            )
        operations = _normalize_operations(item.operations, "segments[%d].operations" % i)
        segment_id = _derive_segment_id_from_core(
            contract.contract_id,
            item.offer_reference,
            item.role,
            operations,
            item.provenance,
        )
        built.append(
            ExecutionSegment(
                segment_id=segment_id,
                contract_id=contract.contract_id,
                offer_reference=item.offer_reference,
                role=item.role,
                operations=operations,
                state="PLANNED",
                provenance=item.provenance,
            )
        )

    # distinct segment cores (identical cores are duplicates)
    segment_ids = [segment.segment_id for segment in built]
    if len(set(segment_ids)) != len(segment_ids):
        raise ExecutionPlanError(
            ExecutionPlanReason.DUPLICATE_SEGMENT,
            "the proposal carries duplicate segments (identical "
            "content-derived cores); segments must be distinct",
        )
    if not any(segment.role == "primary" for segment in built):
        raise ExecutionPlanError(
            ExecutionPlanReason.NO_PRIMARY,
            "the plan requires at least one primary realization segment",
        )

    # deterministic declared ordering (LOCK-111)
    ordered = tuple(sorted(built, key=_segment_sort_key(normalized_tie_break)))

    plan_id = _derive_plan_id_from_core(
        contract.contract_id,
        hard_constraints,
        constraint_fingerprint,
        window,
        ordered,
        normalized_tie_break,
        provenance,
    )
    return ExecutionPlan(
        plan_id=plan_id,
        contract_id=contract.contract_id,
        hard_constraints=hard_constraints,
        constraint_fingerprint=constraint_fingerprint,
        validity=window,
        segments=ordered,
        tie_break=normalized_tie_break,
        provenance=provenance,
    )


# ----------------------------------------------------------------------
# The LOCK-108 verification gate (pure, fail-closed)
# ----------------------------------------------------------------------


def _constraint_digest_map(
    constraints: Sequence[Any],
) -> Dict[str, Any]:
    """The canonical-content view of a constraint set: digest -> record
    (order-independent set equality — a reorder is not a weakening; the
    fingerprint gate below still catches reorders)."""
    return {
        canonical_json_bytes(constraint.to_dict()).decode("utf-8"): constraint
        for constraint in constraints
    }


def verify_plan_preserves_contract(
    plan: ExecutionPlan, contract: ConnectivityContract
) -> None:
    """Fail closed unless the plan preserves the contract's hard
    constraints VERBATIM and stays within the contract authority.

    Checks (ordered so the LOCK-108 verdict cites the specific
    constraint kinds):

    1. constraint-set equality by canonical content, both directions
       (dropped, relaxed, re-interpreted or invented constraints all
       fail with ``plan-constraint-weakened``);
    2. LOCK-108 fingerprint agreement (``plan-constraint-mismatch`` —
       a reorder or tamper outside the digest-stable set);
    3. attribution: the plan and every segment reference exactly this
       contract (``plan-id-mismatch``);
    4. every segment's offer reference is a verbatim accepted-offer
       reference of THIS contract (``plan-offer-not-accepted``);
    5. the plan validity lies within the contract validity
       (``plan-temporal-invalid``).
    """
    if not isinstance(plan, ExecutionPlan):
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "verify_plan_preserves_contract requires an ExecutionPlan",
        )
    if not isinstance(contract, ConnectivityContract):
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "verify_plan_preserves_contract requires a contracts.ConnectivityContract",
        )

    # 1. verbatim set equality (LOCK-108 — the kind-citing gate)
    plan_map = _constraint_digest_map(plan.hard_constraints)
    contract_map = _constraint_digest_map(contract.hard_constraints)
    if set(plan_map) != set(contract_map):
        missing = sorted(
            {contract_map[text].kind for text in contract_map if text not in plan_map}
        )
        added = sorted({plan_map[text].kind for text in plan_map if text not in contract_map})
        detail = "the plan does not preserve the contract hard constraints "
        if missing:
            detail += (
                "verbatim — contract constraint(s) of kind %s dropped, "
                "relaxed or re-interpreted on the plan; " % ", ".join(missing)
            )
        if added:
            detail += (
                "constraint(s) of kind %s carried on the plan are not on "
                "the contract; " % ", ".join(added)
            )
        raise ExecutionPlanError(
            ExecutionPlanReason.CONSTRAINT_WEAKENED,
            detail + "(LOCK-108: no silent contract weakening — the "
            "translation fails closed)",
        )

    # 2. fingerprint agreement (the M002 LOCK-108 evidence convention)
    if plan.constraint_fingerprint != contract.hard_constraint_fingerprint():
        raise ExecutionPlanError(
            ExecutionPlanReason.CONSTRAINT_MISMATCH,
            "the plan's LOCK-108 constraint fingerprint does not match the "
            "contract's (reordered or tampered constraint material fails "
            "closed)",
        )

    # 3. attribution
    if plan.contract_id != contract.contract_id:
        raise ExecutionPlanError(
            ExecutionPlanReason.ID_MISMATCH,
            "the plan is attributable to contract %s, not %s"
            % (plan.contract_id[:24], contract.contract_id[:24]),
        )
    for i, segment in enumerate(plan.segments):
        if segment.contract_id != contract.contract_id:
            raise ExecutionPlanError(
                ExecutionPlanReason.ID_MISMATCH,
                "segments[%d] is attributable to contract %s, not %s"
                % (i, segment.contract_id[:24], contract.contract_id[:24]),
            )

    # 4. verbatim accepted-offer realization
    for i, segment in enumerate(plan.segments):
        if segment.offer_reference not in contract.accepted_offers:
            raise ExecutionPlanError(
                ExecutionPlanReason.OFFER_NOT_ACCEPTED,
                "segments[%d] carries offer reference %s which is not a "
                "verbatim member of the contract's accepted offers"
                % (i, segment.offer_reference.value[:24]),
            )

    # 5. validity containment
    if parse_instant(plan.validity.not_before) < parse_instant(
        contract.validity.not_before
    ) or parse_instant(plan.validity.not_after) > parse_instant(
        contract.validity.not_after
    ):
        raise ExecutionPlanError(
            ExecutionPlanReason.TEMPORAL_INVALID,
            "plan window [%s, %s] escapes the contract validity [%s, %s]"
            % (
                plan.validity.not_before,
                plan.validity.not_after,
                contract.validity.not_before,
                contract.validity.not_after,
            ),
        )


# ----------------------------------------------------------------------
# The LOCK-117 bridge back toward the contract
# ----------------------------------------------------------------------


def plan_reference(plan: ExecutionPlan) -> OpaqueReference:
    """The opaque ``execution-artifact`` reference a plan produces for
    the canonical ``BindExecutionArtifact`` command (LOCK-117: the plan
    rides as DATA on the contract — never an authority; binding never
    changes contract identity or state)."""
    if not isinstance(plan, ExecutionPlan):
        raise ExecutionPlanError(
            ExecutionPlanReason.INVALID_INPUT,
            "plan_reference requires an ExecutionPlan",
        )
    return OpaqueReference(
        ref_kind="execution-artifact",
        value=plan.plan_id,
        provenance=Provenance(
            issuer=plan.provenance.issuer,
            decision_refs=tuple(plan.provenance.decision_refs),
        ),
    )
