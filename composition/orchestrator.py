"""WORK-054 composition orchestrator.

Drives the canonical chain over the composed world's REAL
authorities and produces deterministic conformance evidence.

Two evidence layers, both derived (never canonical state):

- :func:`run_full_chain` -- the STRICT production-composition
  run: every edge in the frozen contract order, each edge driven
  by its OWNING authority through its public surface.  The
  containment edge probes the W048 sharing runtime; on the
  current mainline the runtime is accepted-not-restored, so the
  edge records a typed FAIL_CLOSED outcome, every downstream edge
  is recorded NOT_ENTERED (never skipped, never guessed), and the
  verdict is ``BLOCKED_MISSING_AUTHORITY`` with
  ``production_composition=False``.  The absence is never counted
  as a passing production composition.
- :func:`run_available_segments` -- the SEGMENT-CONFORMANCE run:
  every AVAILABLE composition link downstream of the blocked edge
  is exercised end to end through the existing authorities' public
  boundaries (the commercial session authorization and path
  activation, the delivery-plane evidence-window records, the usage
  observations and the explicit BILLABLE_FINAL seal, the economic
  allocation and settlement acknowledgement, the external payment
  reference lifecycle, and the provider/ADCOS reconciliation).
  Segment conformance is explicitly NOT a claim of a completed
  production composition; the disclaimer travels with every
  segment report.

- :func:`compose_scenario_stream` -- the deterministic digest
  stream (the byte-stable fingerprint of one full composed run;
  the battery's PYTHONHASHSEED and repeat-run proofs compare
  these streams byte for byte).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from intent.model import (
    ConnectivityIntent,
    Constraint,
    IntentDimension,
    Operator,
    Hardness,
)
from intent.normalization import normalize_intent

from marketplace import DiscoveryQuery, UserConstraints
from marketplace.handoff import (
    HandoffOutcome,
    ReservationCoordination,
    handoff_to_networkpath,
    record_path_activation,
)

from commercial import ReferenceFamily
from usage import QuantityClass, UsageLedger
from allocation import AllocationLedger
from payment import SettlementGateway

from .chain import (
    CHAIN_EDGES,
    EdgeOutcome,
    OutcomeReason,
    StageOutcome,
    CompositionTrace,
    ChainVerdict,
)

from .authority import w048_runtime_absent

from .evidence import SoftwareEvidenceRecord

from .world import (
    CompositionWorld,
    _ALLOC_T0,
    _PAY_T0,
    _USAGE_T0,
    _OFFER_CURRENCY,
    _POLICY_ADCOS_BPS,
    _POLICY_CURRENCY,
    _POLICY_DIGITS,
    _POLICY_FROM,
    _POLICY_LABEL,
    _POLICY_MAX_BPS,
    _POLICY_MIN_BPS,
    _POLICY_PROVIDER_BPS,
    _POLICY_ROUNDING,
    _POLICY_UNTIL,
    _PROVIDER_ID,
    StepClock,
    build_allocation_evidence_index,
    build_delivery_evidence,
    build_payment_snapshot,
    build_usage_evidence_index,
    allocation_store,
    payment_store,
    sandbox_provider,
    usage_store,
)

#: The disclaimer that travels with every segment-conformance
#: report (the honest boundary between exercising available links
#: and claiming a completed production composition).
SEGMENT_CONFORMANCE_DISCLAIMER = (
    "Segment conformance exercises every AVAILABLE composition link "
    "end-to-end through the existing authorities' public boundaries.  It "
    "is NOT a claim of a completed production composition: the strict "
    "production chain remains BLOCKED_MISSING_AUTHORITY at the containment "
    "edge (WORK-048 accepted-not-restored on the current mainline), and "
    "segment evidence never promotes itself into a production composition "
    "claim."
)


@dataclass
class ChainRunArtifacts:
    """The authority artifacts of one strict chain run (all
    authority-owned objects; the orchestrator owns none of them)."""

    trace: CompositionTrace
    intent_digest: str = ""
    query_digest: str = ""
    index_digest: str = ""
    proposal: Optional[Any] = None
    decision_id: str = ""
    decision_result: str = ""
    transaction_id: str = ""
    reservation_commands: Tuple[str, ...] = ()
    reservation_expires_at: str = ""
    handoff: Optional[HandoffOutcome] = None


@dataclass
class SegmentArtifacts:
    """The authority artifacts of one segment-conformance run (the
    battery reuses the live authorities for the recovery,
    idempotency, and replay proofs)."""

    report: Dict[str, Any]
    world: CompositionWorld
    chain: ChainRunArtifacts
    coordination: Optional[ReservationCoordination] = None
    usage_ledger: Optional[UsageLedger] = None
    usage_store: Optional[Any] = None
    allocation_ledger: Optional[AllocationLedger] = None
    allocation_store: Optional[Any] = None
    gateway: Optional[SettlementGateway] = None
    payment_store: Optional[Any] = None
    provider: Optional[Any] = None
    statement_id: str = ""
    usage_transaction_id: str = ""
    policy_id: str = ""
    payment_intent_ids: Tuple[str, ...] = ()


#: The type of the deterministic scenario stream (a plain
#: name -> digest mapping).
ScenarioStream = Dict[str, str]


def segment_conformance_allowed() -> bool:
    """Segment conformance is always ALLOWED to run (it exercises
    available links) but is never allowed to promote itself into
    a production composition claim while the strict chain is
    blocked: the disclaimer travels with every report."""
    return True


def _chain_query() -> DiscoveryQuery:
    return DiscoveryQuery(
        buyer_id="w054-buyer-1",
        jurisdiction="gh",
        payment_reference="w054-payauth-1",
        constraints=UserConstraints(currency=_OFFER_CURRENCY, max_price_minor=500),
    )


def _chain_intent() -> ConnectivityIntent:
    return ConnectivityIntent(
        intent_id="w054-intent-1",
        requirements=(
            Constraint(
                constraint_id="w054-bw",
                dimension=IntentDimension.BANDWIDTH,
                operator=Operator.GE,
                value=10,
                unit="Mbps",
                hardness=Hardness.HARD,
            ),
        ),
    )


def _listing_terms(world: CompositionWorld) -> Dict[str, Any]:
    """The selected listing's commercial terms (public read of the
    listing index -- the same offer payload shape the W047
    coordination seam writes)."""
    offer = world.listing_index.offer(_PROVIDER_ID, "wifi-basic")
    return {
        "provider_id": offer.provider_id,
        "offer_id": offer.offer_id,
        "currency": offer.currency,
        "price_minor": offer.price_minor,
        "price_exponent": offer.price_exponent,
        "billing_mode": offer.billing_mode,
        "jurisdiction": offer.jurisdiction,
    }


def run_full_chain(world: CompositionWorld) -> ChainRunArtifacts:
    """Drive the STRICT production-composition chain (the frozen
    contract order) over the world's real authorities.

    The chain stops at the first fail-closed edge: on the current
    mainline the W048 sharing runtime is accepted-not-restored,
    so the containment edge fails closed with the typed reason
    ``w048-runtime-absent-fail-closed`` and every downstream edge
    is recorded NOT_ENTERED.  The verdict is
    ``BLOCKED_MISSING_AUTHORITY`` (production_composition=False).
    """
    artifacts = ChainRunArtifacts(trace=None)
    edges: List[EdgeOutcome] = []

    # ------------------------------------------------------------------
    # edge-01: intent -> offer (WORK-009 normalization feeds the
    # W047 discovery; the offer edge is owned by W009/W047)
    # ------------------------------------------------------------------
    normalized = normalize_intent(_chain_intent())
    if not normalized.ok or normalized.intent is None:
        edges.append(
            EdgeOutcome(
                edge_id="edge-01-intent-offer",
                owning_work_item="WORK-009/WORK-047",
                authority_surface="intent.normalize_intent -> marketplace.discover",
                evidence_class="SOFTWARE",
                outcome=StageOutcome.FAIL_CLOSED,
                reason=OutcomeReason.RESERVATION_FAILED,
                detail="intent normalization failed: %s (%s)"
                % (normalized.code, normalized.detail),
            )
        )
        return _finish_chain(artifacts, edges, blocked_at="intent")

    artifacts.intent_digest = normalized.intent.digest
    query = _chain_query()
    discovery = world.marketplace.discover(query=query)
    artifacts.query_digest = discovery.query_digest
    artifacts.index_digest = discovery.index_digest
    if not discovery.ranked:
        edges.append(
            EdgeOutcome(
                edge_id="edge-01-intent-offer",
                owning_work_item="WORK-009/WORK-047",
                authority_surface="intent.normalize_intent -> marketplace.discover",
                evidence_class="SOFTWARE",
                outcome=StageOutcome.FAIL_CLOSED,
                reason=OutcomeReason.SELECTION_EMPTY,
                detail=(
                    "no eligible candidate survived the discovery filters "
                    "(%d excluded)" % len(discovery.excluded)
                ),
                correlation={"query_digest": discovery.query_digest},
            )
        )
        return _finish_chain(artifacts, edges, blocked_at="offer")

    edges.append(
        EdgeOutcome(
            edge_id="edge-01-intent-offer",
            owning_work_item="WORK-009/WORK-047",
            authority_surface="intent.normalize_intent -> marketplace.discover",
            evidence_class="SOFTWARE",
            outcome=StageOutcome.ADVANCED,
            reason=OutcomeReason.ADVANCED,
            detail=(
                "normalized intent (digest %s) discovered %d ranked "
                "candidate(s) through the marketplace public filters"
                % (normalized.intent.digest[:16], len(discovery.ranked))
            ),
            correlation={
                "intent_digest": normalized.intent.digest,
                "query_digest": discovery.query_digest,
                "index_digest": discovery.index_digest,
            },
        )
    )

    # ------------------------------------------------------------------
    # edge-02: offer -> eligibility (WORK-045 owns the decision)
    # ------------------------------------------------------------------
    decision = world.eligibility.evaluate(
        command_id="w054-elg-evaluate-1",
        actor="platform",
        source="composition-conformance",
        jurisdiction="gh",
        provider_id=_PROVIDER_ID,
        offer_id="wifi-basic",
        valid_until="2027-01-01T00:00:00Z",
    )
    record = world.eligibility.decision(decision.decision_id)
    artifacts.decision_id = decision.decision_id
    artifacts.decision_result = record.result
    if record.result != "eligible":
        edges.append(
            EdgeOutcome(
                edge_id="edge-02-offer-eligibility",
                owning_work_item="WORK-045",
                authority_surface="eligibility.EligibilityAuthority.evaluate",
                evidence_class="SOFTWARE",
                outcome=StageOutcome.FAIL_CLOSED,
                reason=OutcomeReason.ELIGIBILITY_DENIED,
                detail=(
                    "the eligibility authority denied the configuration "
                    "(reasons: %s)"
                    % ",".join(sorted(record.reason_codes))
                ),
                correlation={"decision_id": decision.decision_id},
            )
        )
        return _finish_chain(artifacts, edges, blocked_at="eligibility")

    edges.append(
        EdgeOutcome(
            edge_id="edge-02-offer-eligibility",
            owning_work_item="WORK-045",
            authority_surface="eligibility.EligibilityAuthority.evaluate",
            evidence_class="SOFTWARE",
            outcome=StageOutcome.ADVANCED,
            reason=OutcomeReason.ADVANCED,
            detail=(
                "the eligibility authority recorded decision %s: eligible "
                "(zero denial reason codes)" % decision.decision_id[:16]
            ),
            correlation={"decision_id": decision.decision_id},
        )
    )

    # ------------------------------------------------------------------
    # edge-03: eligibility -> reservation/lease (WORK-051 owns the
    # commercial state; driven through its public typed surface)
    # ------------------------------------------------------------------
    step_intent = "w054-chain-01"
    step_select = "w054-chain-02"
    step_hold = "w054-chain-03"
    core = world.core
    out_intent = core.submit_intent(
        command_id=step_intent,
        actor="w054-buyer-1",
        source="composition-conformance",
        intent={
            "buyer": "w054-buyer-1",
            "want": "connectivity",
            "region": "gh",
            "provider": _PROVIDER_ID,
            "offer": "wifi-basic",
        },
    )
    transaction_id = out_intent.transaction_id
    artifacts.transaction_id = transaction_id
    artifacts.reservation_commands = (step_intent, step_select, step_hold)
    core.select_offer(
        command_id=step_select,
        transaction_id=transaction_id,
        actor="w054-buyer-1",
        source="composition-conformance",
        offer=_listing_terms(world),
    )
    expires_at = "2026-09-01T12:15:00Z"
    core.hold_reservation(
        command_id=step_hold,
        transaction_id=transaction_id,
        actor="w054-buyer-1",
        source="composition-conformance",
        expires_at=expires_at,
    )
    artifacts.reservation_expires_at = expires_at
    transaction = core.transaction(transaction_id)
    if transaction.state != "RESERVATION_HELD":
        edges.append(
            EdgeOutcome(
                edge_id="edge-03-eligibility-reservation",
                owning_work_item="WORK-051",
                authority_surface="CommercialCore.submit_intent/select_offer/hold_reservation",
                evidence_class="SOFTWARE",
                outcome=StageOutcome.FAIL_CLOSED,
                reason=OutcomeReason.RESERVATION_FAILED,
                detail=(
                    "the commercial authority did not hold the reservation "
                    "(state %s)" % transaction.state
                ),
                correlation={"transaction_id": transaction_id},
            )
        )
        return _finish_chain(artifacts, edges, blocked_at="reservation/lease")

    edges.append(
        EdgeOutcome(
            edge_id="edge-03-eligibility-reservation",
            owning_work_item="WORK-051",
            authority_surface="CommercialCore.submit_intent/select_offer/hold_reservation",
            evidence_class="SOFTWARE",
            outcome=StageOutcome.ADVANCED,
            reason=OutcomeReason.ADVANCED,
            detail=(
                "the commercial authority holds reservation on transaction "
                "%s (deadline %s; journal digest %s)"
                % (
                    transaction_id[:16],
                    expires_at,
                    core.journal_digest()[:16],
                )
            ),
            correlation={
                "transaction_id": transaction_id,
                "commercial_state": "RESERVATION_HELD",
                "commercial_journal_digest": core.journal_digest(),
            },
        )
    )

    # ------------------------------------------------------------------
    # edge-04: reservation/lease -> candidate selection (WORK-047
    # owns the selection proposal)
    # ------------------------------------------------------------------
    proposal = world.marketplace.propose(query=query, count=1)
    artifacts.proposal = proposal
    edges.append(
        EdgeOutcome(
            edge_id="edge-04-reservation-candidate-selection",
            owning_work_item="WORK-047",
            authority_surface="marketplace.propose -> SelectionProposal",
            evidence_class="SOFTWARE",
            outcome=StageOutcome.ADVANCED,
            reason=OutcomeReason.ADVANCED,
            detail=(
                "the marketplace selected candidate %s/%s (proposal %s; a "
                "PROPOSAL -- nothing is validated, bound, or activated here)"
                % (
                    proposal.primary[0],
                    proposal.primary[1],
                    proposal.proposal_id[:16],
                )
            ),
            correlation={
                "proposal_id": proposal.proposal_id,
                "selected": ["%s/%s" % key for key in proposal.selected],
            },
        )
    )

    # ------------------------------------------------------------------
    # edge-05: candidate selection -> NetworkPath validation
    # (WORK-041 owns the path lifecycle; driven through the
    # sanctioned W047 handoff seam)
    # ------------------------------------------------------------------
    try:
        outcome = handoff_to_networkpath(
            proposal=proposal,
            index=world.listing_index,
            manager=world.manager,
            session_id=world.transport_session_id,
        )
    except Exception as error:  # MarketplaceError (fail closed)
        edges.append(
            EdgeOutcome(
                edge_id="edge-05-candidate-selection-networkpath-validation",
                owning_work_item="WORK-041",
                authority_surface=(
                    "marketplace.handoff_to_networkpath -> NetworkPathManager "
                    "discover/validate/bind/probe/activate"
                ),
                evidence_class="SOFTWARE",
                outcome=StageOutcome.FAIL_CLOSED,
                reason=OutcomeReason.VALIDATION_REJECTED,
                detail=(
                    "the NetworkPath machinery rejected every candidate "
                    "(%s: %s)" % (type(error).__name__, error)
                ),
                correlation={"proposal_id": proposal.proposal_id},
            )
        )
        return _finish_chain(artifacts, edges, blocked_at="networkpath-validation")

    artifacts.handoff = outcome
    path = world.manager.path(outcome.network_path_id)
    edges.append(
        EdgeOutcome(
            edge_id="edge-05-candidate-selection-networkpath-validation",
            owning_work_item="WORK-041",
            authority_surface=(
                "marketplace.handoff_to_networkpath -> NetworkPathManager "
                "discover/validate/bind/probe/activate"
            ),
            evidence_class="SOFTWARE",
            outcome=StageOutcome.ADVANCED,
            reason=OutcomeReason.ADVANCED,
            detail=(
                "the W041 machinery validated, bound, probed, and activated "
                "path %s for session %s (state %s; content digest %s)"
                % (
                    outcome.network_path_id[:16],
                    world.transport_session_id[:16],
                    path.state,
                    world.manager.content_digest()[:16],
                )
            ),
            correlation={
                "network_path_id": outcome.network_path_id,
                "network_path_state": path.state,
                "networkpath_content_digest": world.manager.content_digest(),
            },
        )
    )

    # ------------------------------------------------------------------
    # edge-06: NetworkPath validation -> containment (WORK-048
    # owns the boundary; the runtime is ABSENT on this mainline)
    # ------------------------------------------------------------------
    edges.append(
        EdgeOutcome(
            edge_id="edge-06-networkpath-validation-containment",
            owning_work_item="WORK-048",
            authority_surface="sharing runtime / containment authority (ABSENT)",
            evidence_class="SOFTWARE",
            outcome=StageOutcome.FAIL_CLOSED,
            reason=OutcomeReason.W048_RUNTIME_ABSENT,
            detail=(
                "the W048 sharing runtime is accepted-not-restored on this "
                "mainline: no authority exists to establish, verify, or "
                "activate a containment boundary, so buyer-traffic "
                "admission fails closed (detected explicitly; never "
                "restored, recreated, mocked, or substituted)"
            ),
            correlation={
                "sharing_package": "absent",
                "containment_runtime": "absent",
                "containment_vocabulary": "restored (containment/state.py, ACR-012)",
            },
        )
    )

    # every downstream edge: NOT ENTERED (never skipped)
    for edge in CHAIN_EDGES[6:]:
        edges.append(
            EdgeOutcome(
                edge_id=edge.edge_id,
                owning_work_item=edge.owning_work_item,
                authority_surface=edge.authority_surface,
                evidence_class="SOFTWARE",
                outcome=StageOutcome.NOT_ENTERED,
                reason=OutcomeReason.UPSTREAM_BLOCKED,
                detail=(
                    "not entered: the upstream containment edge failed "
                    "closed (W048 runtime absent); the orchestrator never "
                    "skips, guesses, or fabricates a stage"
                ),
            )
        )
    return _finish_chain(
        artifacts, edges, blocked_at="containment", missing="WORK-048"
    )


def _finish_chain(
    artifacts: ChainRunArtifacts,
    edges: List[EdgeOutcome],
    *,
    blocked_at: str,
    missing: str = "",
) -> ChainRunArtifacts:
    trace = CompositionTrace(
        edges=tuple(edges),
        verdict=ChainVerdict.BLOCKED_MISSING_AUTHORITY,
        verdict_detail=(
            "the strict production composition is blocked at the %s edge "
            "and is NOT reported as a passing production composition"
            % blocked_at
        ),
        blocked_at=blocked_at,
        missing_authority=missing,
        production_composition=False,
    )
    artifacts.trace = trace
    return artifacts


# ---------------------------------------------------------------------------
# Segment conformance (the available links, end to end)
# ---------------------------------------------------------------------------


def run_available_segments(
    world: CompositionWorld, chain: ChainRunArtifacts
) -> SegmentArtifacts:
    """Exercise every AVAILABLE composition link downstream of the
    blocked containment edge, through the existing authorities'
    public boundaries.

    The run continues the SAME commercial transaction the strict
    chain left at RESERVATION_HELD.  Every segment records its
    owning authority, its evidence class (SOFTWARE), and the
    authority-sourced correlation identities.  The disclaimer is
    part of the report: segment conformance never claims a
    completed production composition.
    """
    artifacts = SegmentArtifacts(
        report={}, world=world, chain=chain
    )
    segments: List[Dict[str, Any]] = []

    def segment(
        edge_id: str,
        owning: str,
        detail: str,
        correlation: Dict[str, Any],
    ) -> None:
        segments.append(
            {
                "edge_id": edge_id,
                "owning_work_item": owning,
                "evidence_class": "SOFTWARE",
                "outcome": "ADVANCED",
                "reason": "advanced-segment-conformance",
                "detail": detail,
                "correlation": correlation,
            }
        )

    core = world.core
    transaction_id = chain.transaction_id

    # ------------------------------------------------------------------
    # segment: containment -> session (the commercial session
    # authorization + path activation through the sanctioned W047
    # record seam, which PROVES W041 ACTIVE first; plus the W012
    # logical session created through the genuine W011/W010
    # decisions in the world fixture)
    # ------------------------------------------------------------------
    coordination = ReservationCoordination(
        proposal_id=chain.proposal.proposal_id,
        transaction_id=transaction_id,
        commands=chain.reservation_commands,
        commercial_state=core.transaction(transaction_id).state,
        expires_at=chain.reservation_expires_at,
    )
    artifacts.coordination = coordination
    record_path_activation(
        coordination=coordination,
        core=core,
        manager=world.manager,
        outcome=chain.handoff,
        session_id=world.transport_session_id,
        actor="w054-buyer-1",
    )
    transaction = core.transaction(transaction_id)
    if transaction.state != "PATH_ACTIVE":
        raise AssertionError(
            "the commercial session/path authorization did not reach "
            "PATH_ACTIVE (state %s)" % transaction.state
        )
    segment(
        "edge-07-containment-session",
        "WORK-012/WORK-051",
        "the commercial session was authorized and the path activated "
        "against a PROVEN W041 ACTIVE path (the W047 record seam), and "
        "the W012 logical session %s was created through the genuine "
        "W011 route decision and W010 policy decision"
        % world.logical_session_id[:16],
        {
            "transaction_id": transaction_id,
            "commercial_state": transaction.state,
            "logical_session_id": world.logical_session_id,
            "transport_session_id": world.transport_session_id,
            "network_path_id": chain.handoff.network_path_id,
        },
    )

    # ------------------------------------------------------------------
    # segment: session -> delivered traffic (the platform journal
    # metering window records, caller-derived from public reads) and the
    # commercial DELIVERY_STARTED -> DELIVERY_COMPLETED chain
    # ------------------------------------------------------------------
    # the commercial core cites the DELIVERY-PLANE journal event ids
    # (the W051 injection contract: the reference index carries the
    # platform journal's delivery-evidence identities)
    journal_evidence_ids = tuple(
        ref.reference_id
        for ref in world.reference_index.by_family(ReferenceFamily.DELIVERY_EVIDENCE)
    )
    # the usage ledger's evidence-window records are derived per transaction
    delivery_evidence = build_usage_evidence_index(
        core, world.integrator, (transaction_id,)
    ).evidence_by_transaction(transaction_id)
    evidence_ids = tuple(
        record.evidence_id for record in delivery_evidence
    )
    core.start_delivery(
        command_id="w054-seg-01",
        transaction_id=transaction_id,
        actor="platform",
        source="composition-conformance",
        evidence_refs=journal_evidence_ids[:1],
    )
    usage_plane = (
        world.reference_index.by_family(ReferenceFamily.USAGE)[0].reference_id
    )
    core.accrue_usage(
        command_id="w054-seg-02",
        transaction_id=transaction_id,
        actor="platform",
        source="composition-conformance",
        usage_refs=(usage_plane,),
    )
    core.complete_delivery(
        command_id="w054-seg-03",
        transaction_id=transaction_id,
        actor="platform",
        source="composition-conformance",
        evidence_refs=(journal_evidence_ids[-1],),
    )
    transaction = core.transaction(transaction_id)
    if transaction.state != "DELIVERY_COMPLETED":
        raise AssertionError(
            "the delivery segment did not reach DELIVERY_COMPLETED "
            "(state %s)" % transaction.state
        )
    segment(
        "edge-08-session-delivered-traffic",
        "WORK-042",
        "the delivery-plane evidence-window records were derived from the "
        "platform journal's public reads (consecutive cumulative counter "
        "deltas on the ACTIVE path interface) and the commercial core "
        "recorded delivery against them",
        {
            "delivery_evidence_ids": list(evidence_ids),
            "platform_journal_digest": world.integrator.journal_digest(),
            "commercial_state": transaction.state,
        },
    )

    # ------------------------------------------------------------------
    # segment: delivered traffic -> usage (the W052 observations
    # citing the authoritative delivery evidence)
    # ------------------------------------------------------------------
    usage_index = build_usage_evidence_index(
        core, world.integrator, (transaction_id,)
    )
    store = usage_store()
    ledger = _usage_ledger(store, usage_index)
    artifacts.usage_ledger = ledger
    artifacts.usage_store = store
    artifacts.usage_transaction_id = transaction_id
    window_bounds = tuple(
        (record.evidence_id, record.window_start, record.window_end)
        for record in delivery_evidence
    )
    command_id = 1
    for evidence_id, window_start, window_end in window_bounds:
        ledger.observe_usage(
            command_id="w054-use-%02d" % command_id,
            transaction_id=transaction_id,
            quantity_class=QuantityClass.DELIVERED,
            quantity=_window_quantity(world, transaction_id, evidence_id),
            evidence_id=evidence_id,
            window_start=window_start,
            window_end=window_end,
            actor="meter",
            source="usage-collector",
        )
        command_id += 1
    # one DATA-only reserved observation (reconciliation DATA; never
    # billable) exercises the non-billable class inside the same run
    ledger.observe_usage(
        command_id="w054-use-%02d" % command_id,
        transaction_id=transaction_id,
        quantity_class=QuantityClass.RESERVED,
        quantity=500,
        actor="meter",
        source="reservation-service",
    )
    segment(
        "edge-09-delivered-traffic-usage",
        "WORK-052",
        "the usage ledger admitted the delivered observations (each "
        "citing the authoritative delivery evidence) plus one "
        "DATA-only reserved observation",
        {
            "usage_state": ledger.transaction(transaction_id).state,
            "usage_journal_digest": ledger.journal_digest(),
        },
    )

    # ------------------------------------------------------------------
    # segment: usage -> BILLABLE_FINAL (the explicit seal; then the
    # commercial billable finality)
    # ------------------------------------------------------------------
    ledger.seal_billable(
        command_id="w054-seal-01",
        transaction_id=transaction_id,
        actor="billing",
        source="usage-ledger",
    )
    projection = ledger.transaction(transaction_id)
    statement = projection.statement
    artifacts.statement_id = statement.statement_id
    core.finalize_billable(
        command_id="w054-seg-04",
        transaction_id=transaction_id,
        actor="billing",
        source="composition-conformance",
    )
    segment(
        "edge-10-usage-billable-final",
        "WORK-052/WORK-051",
        "the usage ledger sealed the billable statement (quantity %d, "
        "amount %d micros) and the commercial core recorded billable "
        "finality"
        % (statement.billable_quantity, statement.amount_micros),
        {
            "statement_id": statement.statement_id,
            "billable_quantity": statement.billable_quantity,
            "amount_micros": statement.amount_micros,
            "sealed_at": statement.sealed_at,
            "commercial_state": core.transaction(transaction_id).state,
        },
    )

    # ------------------------------------------------------------------
    # segment: BILLABLE_FINAL -> allocation (the W053 three-way
    # split + the settlement acknowledgement)
    # ------------------------------------------------------------------
    alloc_store = allocation_store()
    alloc_index = build_allocation_evidence_index(ledger, (transaction_id,))
    alloc_ledger = _allocation_ledger(alloc_store, alloc_index)
    artifacts.allocation_ledger = alloc_ledger
    artifacts.allocation_store = alloc_store
    policy_outcome = alloc_ledger.register_policy(
        command_id="w054-alloc-01",
        label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING,
        currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM,
        effective_until=_POLICY_UNTIL,
        actor="platform",
        source="economic-policy-service",
    )
    artifacts.policy_id = policy_outcome.fact_id
    alloc_ledger.allocate(
        command_id="w054-alloc-02",
        usage_transaction_id=transaction_id,
        usage_statement_id=statement.statement_id,
        policy_id=policy_outcome.fact_id,
        provider_share_bps=_POLICY_PROVIDER_BPS,
        actor="billing",
        source="allocation-service",
    )
    settlement_reference = ""
    for reference_id in alloc_index.reference_ids():
        if (
            alloc_index.reference(reference_id).reference_kind
            == "settlement"
        ):
            settlement_reference = reference_id
            break
    if not settlement_reference:
        raise AssertionError(
            "the allocation evidence index carries no settlement reference"
        )
    alloc_ledger.acknowledge_settlement(
        command_id="w054-alloc-03",
        usage_transaction_id=transaction_id,
        settlement_reference=settlement_reference,
        actor="settlement",
        source="settlement-service",
    )
    account = alloc_ledger.allocation(transaction_id)
    snapshot = account.snapshot
    segment(
        "edge-11-billable-final-allocation",
        "WORK-053",
        "the allocation ledger derived the immutable three-way split "
        "(adcos %d, provider %d, developer %d micros; conservation exact) "
        "and acknowledged the external settlement reference"
        % (
            snapshot.adcos_share_micros,
            snapshot.provider_share_micros,
            snapshot.developer_share_micros,
        ),
        {
            "allocation_id": snapshot.allocation_id,
            "allocation_state": account.state,
            "policy_id": policy_outcome.fact_id,
            "allocation_journal_digest": alloc_ledger.journal_digest(),
        },
    )

    # ------------------------------------------------------------------
    # segment: allocation -> external payment reference (the W044
    # intent lifecycle citing the W051/W052/W053 public snapshots)
    # ------------------------------------------------------------------
    pay_store = payment_store()
    pay_snapshot = build_payment_snapshot(
        core, ledger, alloc_ledger, (transaction_id,)
    )
    provider = sandbox_provider()
    gateway = _payment_gateway(pay_store, pay_snapshot, provider)
    artifacts.gateway = gateway
    artifacts.payment_store = pay_store
    artifacts.provider = provider
    gateway.record_capabilities(
        command_id="w054-pay-00", actor="platform", source="payment-boundary"
    )
    intent_id = "w054-pi-01"
    gateway.create_intent(
        command_id="w054-pay-01",
        intent_id=intent_id,
        transaction_id=transaction_id,
        amount=statement.amount_micros,
        currency=_OFFER_CURRENCY,
        exponent=_POLICY_DIGITS,
        usage_record_id=statement.statement_id,
        description="w054 composed settlement",
        actor="billing",
        source="composition-conformance",
    )
    gateway.authorize(
        command_id="w054-pay-02",
        intent_id=intent_id,
        actor="billing",
        source="composition-conformance",
    )
    gateway.capture(
        command_id="w054-pay-03",
        intent_id=intent_id,
        amount=statement.amount_micros,
        actor="billing",
        source="composition-conformance",
    )
    payout_outcome = gateway.emit_payout(
        command_id="w054-pay-04",
        usage_record_id=transaction_id,
        actor="billing",
        source="composition-conformance",
    )
    payout = gateway.payout(transaction_id)
    segment(
        "edge-12-allocation-external-payment-reference",
        "WORK-044",
        "the payment boundary created, authorized, and captured the "
        "intent citing the commercial transaction and the sealed usage "
        "statement, and emitted the payout instruction from the "
        "finalized allocation citation (state %s -> %s)"
        % (payout_outcome.from_state, payout_outcome.to_state),
        {
            "intent_id": intent_id,
            "intent_state": gateway.intent(intent_id).state,
            "payout_state": payout.state,
            "payment_journal_digest": gateway.journal_digest(),
        },
    )

    # ------------------------------------------------------------------
    # segment: external payment reference -> reconciliation (the
    # provider callbacks as OBSERVATIONS, the explicit exactly-once
    # fold, and the divergence classification)
    # ------------------------------------------------------------------
    # the intent lifecycle callbacks are ingested as OBSERVATIONS
    # only (never auto-applied: the recorded canonical state already
    # covers them; a fold is explicit, monotonic, and exactly-once)
    observation_count = 0
    for envelope in provider.pending_callbacks():
        out = gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
        if out.status == "appended":
            observation_count += 1
    # the provider advances the transfer asynchronously and emits
    # the transfer callback: a genuine provider-ahead observation
    provider.async_advance_transfer(
        payout.transfer_ref, "TRF_DONE"
    )
    for envelope in provider.pending_callbacks():
        out = gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
        if out.status == "appended":
            observation_count += 1
    for observation in gateway.observations():
        if observation.applied or observation.orphan:
            continue
        if observation.kind != "transfer-status":
            continue
        if observation.canonical_status != "TRANSFERRED":
            # the transfer-emission callback (EMITTED) is already
            # covered by the recorded canonical state; only the
            # provider-ahead TRANSFERRED observation is foldable
            continue
        # the EXPLICIT reconciled fold of the one provider-ahead
        # observation (monotonic, validated, journaled exactly once)
        gateway.apply_observation(
            command_id="w054-apply-%s" % observation.event_id[7:19],
            event_id=observation.event_id,
            actor="settlement",
            source="composition-conformance",
        )
    reconcile_outcome = gateway.reconcile(
        command_id="w054-reconcile-01",
        actor="settlement",
        source="composition-conformance",
    )
    report = (
        gateway.reports()[-1] if gateway.reports() else None
    )
    report_entries = (
        tuple(report.entries) if report is not None else ()
    )
    classifications = sorted(
        str(entry.get("classification", ""))
        for entry in report_entries
    )
    segment(
        "edge-13-external-payment-reference-reconciliation",
        "WORK-044",
        "%d provider callbacks were ingested as OBSERVATIONS (no state "
        "fold), the one provider-ahead transfer observation was folded "
        "explicitly exactly once, and the reconciliation report "
        "classified every subject (%s) without rewriting any canonical "
        "state" % (observation_count, ",".join(classifications)),
        {
            "reconciliation_report_id": (
                str(report.report_id) if report is not None else ""
            ),
            "classifications": classifications,
            "payout_state": gateway.payout(transaction_id).state,
            "payment_journal_digest": gateway.journal_digest(),
        },
    )

    artifacts.report = {
        "kind": "work-054-segment-conformance",
        "disclaimer": SEGMENT_CONFORMANCE_DISCLAIMER,
        "production_composition": False,
        "segments": segments,
    }
    artifacts.report["digest"] = _report_digest(artifacts.report)
    return artifacts


def _report_digest(report: Dict[str, Any]) -> str:
    payload = {
        key: value for key, value in report.items() if key != "digest"
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()


def _window_quantity(
    world: CompositionWorld, transaction_id: str, evidence_id: str
) -> int:
    for record in build_delivery_evidence(world.integrator, transaction_id):
        if record.evidence_id == evidence_id:
            return record.delivered_quantity
    raise AssertionError(
        "evidence %s is not derived for the transaction" % evidence_id
    )


def _usage_ledger(store: Any, index: Any) -> UsageLedger:
    return UsageLedger(
        store=store, clock=StepClock(_USAGE_T0, 60), evidence_index=index
    )


def _allocation_ledger(store: Any, index: Any) -> AllocationLedger:
    return AllocationLedger(
        store=store, clock=StepClock(_ALLOC_T0, 60), evidence_index=index
    )


def _payment_gateway(
    store: Any, snapshot: Any, provider: Any
) -> SettlementGateway:
    return SettlementGateway(
        store=store,
        clock=StepClock(_PAY_T0, 60),
        snapshot=snapshot,
        adapter=provider,
    )


# ---------------------------------------------------------------------------
# The deterministic scenario stream
# ---------------------------------------------------------------------------


def compose_scenario_stream() -> ScenarioStream:
    """One fully composed deterministic run: the world, the strict
    chain, and every available segment -- reduced to the
    byte-stable digest stream (identical across processes and
    hash seeds)."""
    world = CompositionWorld()
    world_digests = world.public_digests()
    chain = run_full_chain(world)
    segments = run_available_segments(world, chain)
    stream: Dict[str, str] = {}
    for key, value in world_digests.items():
        stream["world_%s" % key] = value
    stream["chain_trace_digest"] = chain.trace.digest()
    for edge_id, outcome in chain.trace.outcomes_by_edge().items():
        stream["chain_%s" % edge_id] = outcome
    stream["segment_report_digest"] = segments.report["digest"]
    stream["segment_count"] = "%d" % len(segments.report["segments"])
    stream["usage_statement_id"] = segments.statement_id
    stream["usage_journal_digest"] = segments.usage_ledger.journal_digest()
    stream[
        "allocation_journal_digest"
    ] = segments.allocation_ledger.journal_digest()
    stream["payment_journal_digest"] = segments.gateway.journal_digest()
    stream["intent_state"] = segments.gateway.intent(
        "w054-pi-01"
    ).state
    stream["payout_state"] = segments.gateway.payout(
        segments.usage_transaction_id
    ).state
    stream["commercial_state"] = segments.world.core.transaction(
        segments.usage_transaction_id
    ).state
    stream["networkpath_state"] = segments.world.manager.path(
        segments.chain.handoff.network_path_id
    ).state
    return stream
