"""ADCOS resilience multipath failover orchestrator (M015 — Execution
Resilience Runtime).

The multipath failover orchestration with deterministic declared
recorded tie-breaking (the R8 charter M015 scope; the WORK-013
multipath failover model harvested as SOURCE MATERIAL and re-expressed
on the Architecture 1.1 authority — the legacy ``multipath/`` package
is not imported and not modified):

When the active path fails (``path-failed``) or degrades below a
declared bound (``path-degraded`` — the contract's own hard-constraint
bounds are the declared bounds), the orchestrator:

1. **Reads the failover alternatives from the accepted M006 execution
   plan BY REFERENCE** (:func:`failover_alternatives`): the plan's
   ``alternative``-role segments — the frozen 1.1 §10 complex-
   deployment shape of failover alternatives under ONE contract
   (LOCK-116).  The plan itself is gate-checked with the consumed M006
   LOCK-108 gate ``executionplans.verify_plan_preserves_contract``
   (double verification: the alternatives inherit a verbatim
   constraint set);
2. **Drives the accepted M008 replan kernel**
   (:func:`orchestrate_failover` -> ``replan.decide_replan``): the
   alternatives become M008 ``ReplanCandidate`` records (the
   execution-plan candidate kind), validated against the contract's
   full hard-constraint set (LOCK-108 — a weakening alternative is
   REJECTED with the typed reason), and ordered by the DECLARED
   INJECTED tie-break rule (LOCK-111: content keys only, never
   wall-clock, never random; same inputs -> same decision, same
   reasons — the byte-identical decision record IS the recorded
   tie-break evidence);
3. **Applies the decision through the runtime journal** (the
   composition core): an adopted alternative lands through the
   EXPLICIT reconnect pair (old AND new references recorded — the
   WORK-012 discipline); an impossible failover enters the EXPLICIT
   degraded/failed state or triggers the EXPLICIT renegotiation path —
   never a silent downgrade.

LOCK-115 (simple-system validity): a plan with no alternative-role
segments carries no failover alternatives, and the orchestrator says
so with the typed ``resilience-no-candidates`` outcome — a simple
deployment does not require alternatives, and the runtime never
invents them.

LOCK-117: the plan, its segments and the adopted artifacts ride as
opaque ``execution-artifact`` data; the contract stays the sole
authority.

Determinism (LOCK-111/LOCK-119): same inputs -> the byte-identical
decision record (run twice, byte-identical); tie-breaking declared and
injected; injected instants only; no randomness, no network, no
secrets.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from contracts import ConnectivityContract, OpaqueReference, Provenance

from executionplans import (
    ExecutionPlan,
    verify_plan_preserves_contract as _consumed_verify_plan,
)

from replan import (
    DEFAULT_TIE_BREAK,
    ReplanCandidate,
    ReplanError,
    ReplanTrigger,
    decide_replan as _consumed_decide_replan,
)

from resilience.errors import ResilienceError, ResilienceReason
from resilience.model import (
    RUNTIME_ISSUER,
    _normalize_tie_break,
    check_realization_surface,
    runtime_realization_snapshot,
)
from resilience.runtime import DriveResult, RuntimeStore, drive_replan_decision

__all__ = [
    "FAILOVER_TRIGGER_KINDS",
    "FAILOVER_TRIGGER_MAP",
    "FAILOVER_CANDIDATE_KIND",
    "failover_alternatives",
    "orchestrate_failover",
]


#: The failover trigger kinds (the runtime-side vocabulary): the active
#: path FAILED, or it DEGRADED below a declared bound (the contract's
#: own hard-constraint bounds are the declared bounds — a degradation
#: trigger maps onto the closed-loop assurance-degraded evaluation).
FAILOVER_TRIGGER_KINDS: Tuple[str, ...] = ("path-failed", "path-degraded")

#: The frozen mapping of the failover trigger kinds onto the CONSUMED
#: M008 trigger vocabulary (never a second trigger model — the
#: runtime-side kinds project onto the accepted kernel's kinds):
#: ``path-failed`` -> ``segment-loss`` (the active path's segment was
#: lost); ``path-degraded`` -> ``assurance-degraded`` (the closed loop
#: evaluated the active path below a declared bound).
FAILOVER_TRIGGER_MAP: dict = {
    "path-failed": "segment-loss",
    "path-degraded": "assurance-degraded",
}

#: The failover alternative candidate kind (the M008-owned frozen
#: candidate-kind vocabulary, consumed BY REFERENCE — the M006
#: execution-plan alternative shape).
FAILOVER_CANDIDATE_KIND = "execution-plan"


def failover_alternatives(plan: ExecutionPlan) -> Tuple[ReplanCandidate, ...]:
    """Read the failover alternatives from an accepted M006 execution
    plan BY REFERENCE: every ``alternative``-role segment becomes one
    M008 ``ReplanCandidate`` (the execution-plan candidate kind) whose
    claimed constraint set is the PLAN's own (which the M006
    translation took VERBATIM from the contract — the kernel
    re-validates it regardless, LOCK-108 twice).

    Each alternative's realization references are the plan id (the
    realization decision artifact) and the segment id (the concrete
    realization member) — both content-derived ids of the accepted M006
    domain, cited as opaque strings (LOCK-117).  Deterministic order:
    the plan's own declared tie-break segment order, preserved
    verbatim.
    """
    if not isinstance(plan, ExecutionPlan):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "failover_alternatives requires an executionplans.ExecutionPlan "
            "(got %s) — the accepted M006 domain owns the failover "
            "alternative segments" % type(plan).__name__,
        )
    candidates = []
    for segment in plan.segments:
        if segment.role != "alternative":
            continue
        try:
            candidates.append(
                ReplanCandidate(
                    kind=FAILOVER_CANDIDATE_KIND,
                    contract_id=plan.contract_id,
                    hard_constraints=tuple(plan.hard_constraints),
                    artifact_refs=(
                        OpaqueReference(
                            ref_kind="execution-artifact",
                            value=plan.plan_id,
                            provenance=Provenance(
                                issuer="resilience:failover",
                                decision_refs=(segment.segment_id, plan.contract_id),
                            ),
                        ),
                        OpaqueReference(
                            ref_kind="execution-artifact",
                            value=segment.segment_id,
                            provenance=Provenance(
                                issuer="resilience:failover",
                                decision_refs=(plan.plan_id, plan.contract_id),
                            ),
                        ),
                    ),
                    provenance=Provenance(
                        issuer="resilience:failover",
                        decision_refs=(plan.plan_id, segment.segment_id),
                    ),
                )
            )
        except ReplanError as error:
            raise ResilienceError(
                ResilienceReason.REPLAN_COMPOSITION,
                "the failover alternative was rejected by the consumed M008 "
                "candidate model: %s" % error.detail,
            ) from None
    return tuple(candidates)


def orchestrate_failover(
    store: RuntimeStore,
    runtime_id: object,
    contract: ConnectivityContract,
    plan: ExecutionPlan,
    *,
    trigger_kind: str,
    recorded_at: str,
    tie_break: Sequence[str] = DEFAULT_TIE_BREAK,
    provenance: Optional[Provenance] = None,
) -> DriveResult:
    """Orchestrate one multipath failover: read the alternatives from
    the accepted plan, validate every candidate against the contract's
    full hard-constraint set through the consumed kernel (LOCK-108),
    select deterministically by the DECLARED injected tie-break rule
    (LOCK-111), and apply the outcome through the runtime journal (the
    explicit reconnect pair on adoption; the EXPLICIT degraded/failed
    state or the renegotiation trigger otherwise — never a silent
    downgrade).

    Fail-closed gates: the store/session/contract/plan inputs (typed,
    attributed — the plan must be attributable to exactly the owning
    contract and must PASS the consumed M006 LOCK-108 gate
    ``verify_plan_preserves_contract``); the runtime session must be a
    replan surface; the trigger kind must be in
    :data:`FAILOVER_TRIGGER_KINDS`; the plan must carry at least one
    alternative-role segment (LOCK-115: a simple deployment carries no
    alternatives, and the typed ``resilience-no-candidates`` outcome
    says so — never an invented alternative, never a silent no-op).
    """
    if not isinstance(store, RuntimeStore):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "orchestrate_failover requires a resilience RuntimeStore (got %s)"
            % type(store).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "orchestrate_failover requires a contracts.ConnectivityContract "
            "(got %s)" % type(contract).__name__,
        )
    if not isinstance(plan, ExecutionPlan):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "orchestrate_failover requires an executionplans.ExecutionPlan "
            "(got %s)" % type(plan).__name__,
        )
    if trigger_kind not in FAILOVER_TRIGGER_KINDS:
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "trigger_kind must be one of %s (found %r) — the failover trigger "
            "kinds map onto the consumed M008 vocabulary through "
            "FAILOVER_TRIGGER_MAP" % (", ".join(FAILOVER_TRIGGER_KINDS), trigger_kind),
        )
    session = store.session(runtime_id)
    if session.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "runtime session %s rides contract %s, not %s — a failover "
            "realizes exactly its owning contract"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    if plan.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the plan is attributable to contract %s, not %s — failover "
            "alternatives realize exactly their owning contract"
            % (plan.contract_id[:23], contract.contract_id[:23]),
        )
    check_realization_surface(session.state)
    # the consumed M006 LOCK-108 gate (BY REFERENCE): the plan must
    # preserve the contract's hard constraints verbatim before any of
    # its alternatives may be read (double verification — the kernel
    # re-validates the candidates regardless)
    try:
        _consumed_verify_plan(plan, contract)
    except Exception as error:  # ExecutionPlanError (ValueError subclass)
        raise ResilienceError(
            ResilienceReason.CONSTRAINT_MISMATCH,
            "the execution plan failed the consumed M006 LOCK-108 gate: %s"
            % getattr(error, "detail", error),
        ) from None

    candidates = failover_alternatives(plan)
    if not candidates:
        raise ResilienceError(
            ResilienceReason.NO_CANDIDATES,
            "the plan carries no alternative-role segments — there are no "
            "failover alternatives under this contract (LOCK-115: a simple "
            "deployment does not require failover alternatives; the runtime "
            "never invents them and never silently no-ops)",
        )
    normalized_tie_break = _normalize_tie_break(
        tie_break, "orchestrate_failover.tie_break", complete=True
    )

    snapshot = runtime_realization_snapshot(
        session, observed_at=recorded_at, provenance=provenance
    )
    kernel_trigger_kind = FAILOVER_TRIGGER_MAP[trigger_kind]
    try:
        trigger = ReplanTrigger(
            kind=kernel_trigger_kind,
            contract_id=contract.contract_id,
            recorded_at=recorded_at,
            realization_ref=session.runtime_id,
        )
        decision = _consumed_decide_replan(
            contract,
            trigger,
            snapshot,
            candidates,
            tie_break=normalized_tie_break,
        )
    except ReplanError as error:
        raise ResilienceError(
            ResilienceReason.REPLAN_COMPOSITION,
            "the consumed M008 replan kernel rejected the failover drive: %s"
            % error.detail,
        ) from None

    sequence_before = session.sequence
    new_route = None
    new_path = None
    if decision.decision == "adopt-alternative":
        for candidate in candidates:
            if candidate.candidate_id == decision.adopted_candidate_id:
                new_route = candidate.artifact_refs[0].value
                new_path = candidate.artifact_refs[1].value
                break
    after, reconnect = drive_replan_decision(
        store,
        session.runtime_id,
        contract,
        decision,
        recorded_at=recorded_at,
        new_route_decision_id=new_route,
        new_path_id=new_path,
        provenance=Provenance(
            issuer=RUNTIME_ISSUER,
            decision_refs=(decision.decision_id, session.runtime_id),
        ),
    )
    appended = store.events(session.runtime_id)[sequence_before:]
    return DriveResult(
        decision=decision,
        session=after,
        reconnect=reconnect,
        event_ids=tuple(event.event_id for event in appended),
    )
