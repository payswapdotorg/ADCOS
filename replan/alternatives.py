"""ADCOS replan alternative constructors (M008 — Replan and Failover).

The typed candidate-realization constructors that consume the
accepted sibling domains BY REFERENCE (LOCK-101 discipline — the
consumed domains are never modified, never duplicated):

- :func:`plan_candidate` — wraps a new ``ExecutionPlan`` translated
  from the SAME contract (the accepted M006 ``executionplans/``
  domain; the plan's own hard-constraint set IS the contract's —
  preserved verbatim by the M006 translation, so the candidate's
  claimed set re-validates trivially against the contract);
- :func:`route_candidate` — wraps a WORK-011 accepted route decision
  as a mobility-handover or multipath-path alternative (the harvested
  WORK-014/WORK-013 alternative models);
- :func:`capability_candidate` — wraps an M007 ``OfferView`` (an
  available alternative from the adapter capability surface —
  provider-neutral DATA, LOCK-110) as a provider-alternative
  candidate.

Every constructor is fail-closed and typed: attribution is checked
against the owning contract, artifact references ride as opaque
``execution-artifact`` data (LOCK-117), provenance is carried
verbatim (LOCK-118), and the claimed constraint set is INPUT DATA
(LOCK-111: optimizer-supplied, re-validated by the engine against the
contract's full hard-constraint set — LOCK-108).

Determinism (LOCK-119): injected instants only; content-derived ids;
no wall clock, no randomness, no network, no secrets.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from contracts import ConnectivityContract, HardConstraint, OpaqueReference, Provenance

from executionplans import ExecutionPlan, plan_reference
from routing.model import RouteDecision

from .errors import ReplanError, ReplanReason
from .model import ReplanCandidate


def _require_contract(contract: ConnectivityContract) -> ConnectivityContract:
    if not isinstance(contract, ConnectivityContract):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "the alternative constructors require a contracts.ConnectivityContract "
            "(got %s)" % type(contract).__name__,
        )
    return contract


def plan_candidate(
    contract: ConnectivityContract, plan: ExecutionPlan
) -> ReplanCandidate:
    """Wrap a new M006 ``ExecutionPlan`` (translated from the SAME
    contract) as an execution-plan candidate.

    Attribution is checked (the plan must be attributable to exactly
    this contract — ``replan-id-mismatch`` otherwise); the candidate's
    claimed constraint set is the PLAN's own (which the M006
    translation took verbatim from the contract); the artifact
    reference is the plan's opaque ``execution-artifact`` reference
    (LOCK-117: the plan rides as data, never authority).

    The caller may re-validate the whole shape with the M006 gate
    ``executionplans.verify_plan_preserves_contract`` — the engine
    re-validates the constraint set regardless (LOCK-108 twice).
    """
    _require_contract(contract)
    if not isinstance(plan, ExecutionPlan):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "plan_candidate requires an executionplans.ExecutionPlan (got %s)"
            % type(plan).__name__,
        )
    if plan.contract_id != contract.contract_id:
        raise ReplanError(
            ReplanReason.ID_MISMATCH,
            "the plan is attributable to contract %s, not %s — an execution-plan "
            "candidate realizes exactly its owning contract"
            % (plan.contract_id[:23], contract.contract_id[:23]),
        )
    return ReplanCandidate(
        kind="execution-plan",
        contract_id=contract.contract_id,
        hard_constraints=tuple(plan.hard_constraints),
        artifact_refs=(plan_reference(plan),),
        provenance=Provenance(
            issuer="replan:alternatives",
            decision_refs=(plan.plan_id, contract.contract_id),
        ),
    )


def route_candidate(
    contract: ConnectivityContract,
    kind: str,
    route_decision: RouteDecision,
    hard_constraints: Sequence[HardConstraint],
    provenance: Optional[Provenance] = None,
) -> ReplanCandidate:
    """Wrap an accepted WORK-011 route decision as a harvested
    alternative-model candidate (``mobility-handover`` or
    ``multipath-path`` — the WORK-014/WORK-013 alternative shapes).

    The route decision is consumed BY REFERENCE (its content-derived
    identities ride as opaque ``execution-artifact`` data, LOCK-117);
    ``hard_constraints`` is the constraint set the alternative CLAIMS
    to satisfy — optimizer-supplied DATA re-validated by the engine
    against the contract's full hard-constraint set (LOCK-108: a
    weakening claim is rejected, never silently adopted).
    """
    _require_contract(contract)
    if kind not in ("mobility-handover", "multipath-path"):
        raise ReplanError(
            ReplanReason.VOCABULARY,
            "route_candidate kind must be mobility-handover or multipath-path "
            "(found %r)" % (kind,),
        )
    if not isinstance(route_decision, RouteDecision):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "route_candidate requires a WORK-011 RouteDecision (got %s)"
            % type(route_decision).__name__,
        )
    if route_decision.selected is None:
        raise ReplanError(
            ReplanReason.CANDIDATE_INVALID,
            "route_candidate requires a SELECTED route decision (an "
            "alternative realization carries its selected path)",
        )
    selected_path = route_decision.selected
    if provenance is None:
        provenance = Provenance(
            issuer="replan:alternatives",
            decision_refs=(route_decision.decision_id, contract.contract_id),
        )
    elif not isinstance(provenance, Provenance):
        raise ReplanError(
            ReplanReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    return ReplanCandidate(
        kind=kind,
        contract_id=contract.contract_id,
        hard_constraints=tuple(hard_constraints),
        artifact_refs=(
            OpaqueReference(
                ref_kind="execution-artifact",
                value=route_decision.decision_id,
                provenance=Provenance(
                    issuer="routing:WORK-011",
                    decision_refs=(selected_path.path_id,),
                ),
            ),
            OpaqueReference(
                ref_kind="execution-artifact",
                value=selected_path.path_id,
                provenance=Provenance(
                    issuer="routing:WORK-011",
                    decision_refs=(route_decision.decision_id,),
                ),
            ),
        ),
        provenance=provenance,
    )


def capability_candidate(
    contract: ConnectivityContract,
    offer_view: object,
    hard_constraints: Sequence[HardConstraint],
    provenance: Optional[Provenance] = None,
) -> ReplanCandidate:
    """Wrap an M007 ``OfferView`` (an available alternative from the
    adapter capability surface — ``inspect_offers`` output) as a
    provider-alternative candidate.

    The offer view is consumed BY REFERENCE as provider-neutral DATA
    (LOCK-110: never a provider SDK type, never topology — the view's
    declared resource mapping and mediated capability references only);
    the artifact reference cites the adapter and its declared
    technology resource.  ``hard_constraints`` is the claimed set —
    optimizer-supplied DATA re-validated by the engine (LOCK-108).
    """
    _require_contract(contract)
    # BY-REFERENCE type check: the M007 surface is imported here and
    # nowhere re-implemented (LOCK-101/LOCK-110)
    from adapters.capability import OfferView

    if not isinstance(offer_view, OfferView):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "capability_candidate requires an adapters.capability.OfferView "
            "(got %s)" % type(offer_view).__name__,
        )
    if not offer_view.adapter_id or not offer_view.technology_resource:
        raise ReplanError(
            ReplanReason.CANDIDATE_INVALID,
            "the offer view must carry its adapter id and technology resource "
            "(the declared provider-local inventory slice)",
        )
    if provenance is None:
        provenance = Provenance(
            issuer="replan:alternatives",
            decision_refs=(offer_view.adapter_id, contract.contract_id),
        )
    elif not isinstance(provenance, Provenance):
        raise ReplanError(
            ReplanReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    artifact_value = "%s/%s" % (
        offer_view.adapter_id,
        offer_view.technology_resource,
    )
    if len(artifact_value) > 128:
        artifact_value = artifact_value[:128]
    return ReplanCandidate(
        kind="provider-alternative",
        contract_id=contract.contract_id,
        hard_constraints=tuple(hard_constraints),
        artifact_refs=(
            OpaqueReference(
                ref_kind="execution-artifact",
                value=artifact_value,
                provenance=Provenance(
                    issuer="adapters:WORK-016",
                    decision_refs=(offer_view.adapter_id,),
                ),
            ),
        ),
        provenance=provenance,
    )
