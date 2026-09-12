"""ADCOS credential revocation propagation (M018 — Credential and
Key Lifecycle Operations).

Revocation propagation as DETERMINISTIC ROUNDS with DECLARED
CONVERGENCE BOUNDS:

- the convergence bound is a declared ROUND COUNT (never a wall
  clock — the plan carries integers only, and the AST audit in the
  battery confirms no time construct reaches this surface);
- every round is JOURNALED and REPLAYABLE (each round appends one
  ``propagation-round`` operation record to the lifecycle journal:
  the round index, the delivered consumer slice, the pending
  remainder, the converged flag);
- the round sequence is a PURE FUNCTION of the declared plan (the
  sorted consumer order + the declared fanout): same inputs ->
  identical rounds (verified in-process twice, across full re-runs,
  and across PYTHONHASHSEED subprocesses by the battery);
- the declared bound is ENFORCED: propagation that cannot reach
  every declared consumer within the declared round count FAILS
  CLOSED (typed ``credential-propagation-unconverged`` citing the
  bound and the pending consumers — never a silent partial
  propagation, never a wall-clock excuse);
- the authoritative admitted set is UNCHANGED by propagation (the
  revocation already flipped it; the rounds model the DISTRIBUTION
  of that revocation to the declared admission consumers — each
  round record carries the unchanged before/after sets, mechanically
  enforced).

The consumer-observation model is replayable: a consumer holds the
revoked credential in its local admitted view until the round that
delivers the revocation to it (:func:`consumer_observed_revocation`
— the pure lookup over the journaled rounds).
"""

from __future__ import annotations

from typing import Optional, Tuple

from .errors import CredentialLifecycleError, CredentialLifecycleReason
from .journal import LifecycleJournal
from .model import (
    PROPAGATION_ISSUER,
    LifecycleOperationRecord,
    PropagationPlan,
    check_zero_coverage_gap,
    consumer_observed_revocation,
    plan_propagation,
    round_deliveries,
)

__all__ = [
    "run_revocation_propagation",
    "propagation_verdict",
    "consumer_observed_revocation",
    "plan_propagation",
    "round_deliveries",
]


def run_revocation_propagation(
    *,
    journal: LifecycleJournal,
    revocation_operation_id: str,
    revoked_ref: str,
    plan: PropagationPlan,
    round_instants: Tuple[str, ...],
    provenance: Optional[str] = None,
) -> Tuple[LifecycleOperationRecord, ...]:
    """Run the declared deterministic propagation of one journaled
    revocation (or emergency revocation) to the declared consumers.

    ``round_instants`` carries one injected instant per DECLARED
    round (exactly ``plan.max_rounds`` — the round-count budget;
    deterministic instants, never a wall clock).  At most
    ``plan.max_rounds`` rounds execute (the declared bound, capped);
    every executed round is journaled; a plan that cannot converge
    within the declared round count fails closed AFTER the bounded
    rounds are journaled (the evidence of the bounded failure stays
    visible — the typed error cites the declared bound and the
    pending consumers).
    """
    if not isinstance(journal, LifecycleJournal):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_revocation_propagation requires a LifecycleJournal",
        )
    if not isinstance(plan, PropagationPlan):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_revocation_propagation requires a declared "
            "PropagationPlan (the round-count convergence bound)",
        )
    if not isinstance(round_instants, tuple):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "round_instants must be a tuple of injected RFC 3339 instants "
            "(one per declared round — never a wall clock)",
        )
    # the propagated revocation must exist on this journal and must
    # have flipped the credential out of the admitted set (the
    # propagation distributes a REAL journaled revocation)
    revocation = journal.operation(revocation_operation_id)
    if revocation.kind not in ("revocation", "emergency-revocation"):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
            "operation %r is a %r — only a journaled revocation (or the "
            "distinct emergency revocation) is propagated"
            % (revocation_operation_id, revocation.kind),
        )
    if revocation.subject_ref != revoked_ref:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ID_MISMATCH,
            "operation %r revoked %r, not %r (attribution fails closed)"
            % (revocation_operation_id, revocation.subject_ref, revoked_ref),
        )
    check_zero_coverage_gap(journal.fold(), revoked_ref)
    deliveries = round_deliveries(plan)
    if len(round_instants) != plan.max_rounds:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the declared round-count bound is %d but %d round instant(s) "
            "were injected (one deterministic instant per DECLARED round "
            "— the budget; never a wall clock)"
            % (plan.max_rounds, len(round_instants)),
        )
    # the authoritative admitted set is UNCHANGED by propagation (the
    # revocation already flipped it; the rounds distribute it)
    authoritative = journal.fold().current_admitted()
    if revoked_ref in authoritative:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
            "the revoked credential %r is still in the authoritative "
            "admitted set — propagation distributes a completed revocation"
            % (revoked_ref,),
        )
    issuer = provenance or PROPAGATION_ISSUER
    journaled: list = []
    pending = list(plan.consumers)
    # the DECLARED round-count bound caps the executed rounds (the
    # convergence bound is the budget — a plan needing more rounds
    # than declared fails closed below)
    executed = min(len(deliveries), plan.max_rounds)
    for index in range(executed):
        delivery = deliveries[index]
        instant = round_instants[index]
        pending = [consumer for consumer in pending if consumer not in delivery]
        converged = not pending
        record = LifecycleOperationRecord(
            operation_id="",
            kind="propagation-round",
            sequence=len(journal) + 1,
            node_id=journal.node_id,
            recorded_at=instant,
            subject_ref=revoked_ref,
            before_admitted=authoritative,
            after_admitted=authoritative,
            propagates_operation=revocation_operation_id,
            round_index=index + 1,
            delivered_to=delivery,
            pending_after=tuple(pending),
            converged=converged,
            provenance=issuer,
        )
        journaled.append(journal.append(record))
        if converged:
            break
    if pending:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.PROPAGATION_UNCONVERGED,
            "revocation propagation did not converge within the declared "
            "ROUND-COUNT bound %d (fanout %d over %d consumer(s)): %d "
            "consumer(s) still pending (%s) — fail closed, never a silent "
            "partial propagation and never a wall-clock bound"
            % (
                plan.max_rounds,
                plan.fanout_per_round,
                len(plan.consumers),
                len(pending),
                ", ".join(pending[:4]),
            ),
        )
    return tuple(journaled)


def propagation_verdict(
    journal: LifecycleJournal, revocation_operation_id: str
) -> str:
    """The typed convergence verdict over the journaled rounds of one
    propagated revocation: ``converged`` (every declared consumer
    received the revocation within the journaled rounds) or the
    pending-consumer citation (fail-closed disclosure, never a silent
    pass)."""
    rounds = [
        record
        for record in journal.operations()
        if record.kind == "propagation-round"
        and record.propagates_operation == revocation_operation_id
    ]
    if not rounds:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
            "operation %r carries no journaled propagation rounds"
            % (revocation_operation_id,),
        )
    pending = rounds[-1].pending_after
    if pending:
        return "unconverged:%s" % ",".join(pending)
    return "converged"
