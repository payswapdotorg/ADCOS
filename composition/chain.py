"""WORK-054 composition chain model.

The frozen ordered chain of the R2 System Composition Conformance
gate, reconciled verbatim with the WORK-054 contract and the
DEC-0085 activation record:

    intent -> offer -> eligibility -> reservation/lease ->
    candidate selection -> NetworkPath validation -> containment ->
    session -> delivered traffic -> usage -> BILLABLE_FINAL ->
    allocation -> external payment reference -> reconciliation

Every edge identifies its OWNING authority and its evidence
class.  An unavailable authority produces an explicit fail-closed
edge outcome; every edge downstream of a fail-closed edge is
recorded ``NOT_ENTERED`` (the orchestrator never skips, guesses,
or fabricates a stage).  The trace never converts a blocked
composition into a passing production composition: while any
required authority is absent, the verdict is
``BLOCKED_MISSING_AUTHORITY`` and ``production_composition`` is
``False``.

The chain model is pure DATA: the orchestrator (composition.
orchestrator) drives the real authorities and emits
``EdgeOutcome`` records; this module defines the frozen
vocabulary, the ordered edges, and the deterministic trace
document (WORK-003 canonical JSON digest).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from protocol.canonicalization import canonical_json_bytes

import hashlib


#: The ordered stage names of the canonical chain (14 stages,
#: 13 edges).
CHAIN_STAGE_NAMES: Tuple[str, ...] = (
    "intent",
    "offer",
    "eligibility",
    "reservation/lease",
    "candidate-selection",
    "networkpath-validation",
    "containment",
    "session",
    "delivered-traffic",
    "usage",
    "billable-final",
    "allocation",
    "external-payment-reference",
    "reconciliation",
)


@dataclass(frozen=True)
class EdgeSpec:
    """One frozen chain edge: the transition between two stages,
    the Work Item that OWNS the decision at that edge, and the
    authority surface the orchestrator composes."""

    edge_id: str
    from_stage: str
    to_stage: str
    owning_work_item: str
    authority_surface: str
    evidence_class: str = "SOFTWARE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "owning_work_item": self.owning_work_item,
            "authority_surface": self.authority_surface,
            "evidence_class": self.evidence_class,
        }


#: The frozen 13-edge chain (the WORK-054 contract order).
CHAIN_EDGES: Tuple[EdgeSpec, ...] = (
    EdgeSpec(
        edge_id="edge-01-intent-offer",
        from_stage="intent",
        to_stage="offer",
        owning_work_item="WORK-009/WORK-047",
        authority_surface="intent.normalize_intent -> marketplace.discover",
    ),
    EdgeSpec(
        edge_id="edge-02-offer-eligibility",
        from_stage="offer",
        to_stage="eligibility",
        owning_work_item="WORK-045",
        authority_surface="eligibility.EligibilityAuthority.evaluate",
    ),
    EdgeSpec(
        edge_id="edge-03-eligibility-reservation",
        from_stage="eligibility",
        to_stage="reservation/lease",
        owning_work_item="WORK-051",
        authority_surface=(
            "marketplace.coordinate_reservation -> CommercialCore "
            "submit_intent/select_offer/hold_reservation"
        ),
    ),
    EdgeSpec(
        edge_id="edge-04-reservation-candidate-selection",
        from_stage="reservation/lease",
        to_stage="candidate-selection",
        owning_work_item="WORK-047",
        authority_surface="marketplace.propose -> SelectionProposal",
    ),
    EdgeSpec(
        edge_id="edge-05-candidate-selection-networkpath-validation",
        from_stage="candidate-selection",
        to_stage="networkpath-validation",
        owning_work_item="WORK-041",
        authority_surface=(
            "marketplace.handoff_to_networkpath -> NetworkPathManager "
            "discover/validate/bind/probe/activate"
        ),
    ),
    EdgeSpec(
        edge_id="edge-06-networkpath-validation-containment",
        from_stage="networkpath-validation",
        to_stage="containment",
        owning_work_item="WORK-048",
        authority_surface="sharing runtime / containment authority (ABSENT)",
    ),
    EdgeSpec(
        edge_id="edge-07-containment-session",
        from_stage="containment",
        to_stage="session",
        owning_work_item="WORK-012/WORK-051",
        authority_surface=(
            "sessions.SessionStore.create + CommercialCore.authorize_session"
        ),
    ),
    EdgeSpec(
        edge_id="edge-08-session-delivered-traffic",
        from_stage="session",
        to_stage="delivered-traffic",
        owning_work_item="WORK-042",
        authority_surface=(
            "platform journal delivery-plane evidence-window records "
            "(DeliveryEvidence, caller-derived from public reads)"
        ),
    ),
    EdgeSpec(
        edge_id="edge-09-delivered-traffic-usage",
        from_stage="delivered-traffic",
        to_stage="usage",
        owning_work_item="WORK-052",
        authority_surface="usage.UsageLedger.observe_usage",
    ),
    EdgeSpec(
        edge_id="edge-10-usage-billable-final",
        from_stage="usage",
        to_stage="billable-final",
        owning_work_item="WORK-052/WORK-051",
        authority_surface=(
            "usage.UsageLedger.seal_billable + CommercialCore.finalize_billable"
        ),
    ),
    EdgeSpec(
        edge_id="edge-11-billable-final-allocation",
        from_stage="billable-final",
        to_stage="allocation",
        owning_work_item="WORK-053",
        authority_surface="allocation.AllocationLedger.allocate",
    ),
    EdgeSpec(
        edge_id="edge-12-allocation-external-payment-reference",
        from_stage="allocation",
        to_stage="external-payment-reference",
        owning_work_item="WORK-044",
        authority_surface=(
            "payment.SettlementGateway create_intent/authorize/capture/"
            "emit_payout (citing W051/W052/W053 public snapshots)"
        ),
    ),
    EdgeSpec(
        edge_id="edge-13-external-payment-reference-reconciliation",
        from_stage="external-payment-reference",
        to_stage="reconciliation",
        owning_work_item="WORK-044",
        authority_surface=(
            "payment.SettlementGateway ingest_callback/apply_observation/"
            "reconcile (divergence classification, never a rewrite)"
        ),
    ),
)


class OutcomeReason:
    """The frozen edge-outcome reason vocabulary."""

    ADVANCED = "advanced"
    W048_RUNTIME_ABSENT = "w048-runtime-absent-fail-closed"
    ELIGIBILITY_DENIED = "eligibility-denied-fail-closed"
    SELECTION_EMPTY = "selection-empty-fail-closed"
    VALIDATION_REJECTED = "networkpath-validation-rejected-fail-closed"
    RESERVATION_FAILED = "reservation-failed-fail-closed"
    UPSTREAM_BLOCKED = "upstream-blocked-not-entered"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.ADVANCED,
            cls.W048_RUNTIME_ABSENT,
            cls.ELIGIBILITY_DENIED,
            cls.SELECTION_EMPTY,
            cls.VALIDATION_REJECTED,
            cls.RESERVATION_FAILED,
            cls.UPSTREAM_BLOCKED,
        )


class StageOutcome:
    """The frozen edge outcome vocabulary."""

    ADVANCED = "ADVANCED"
    FAIL_CLOSED = "FAIL_CLOSED"
    NOT_ENTERED = "NOT_ENTERED"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ADVANCED, cls.FAIL_CLOSED, cls.NOT_ENTERED)


class ChainVerdict:
    """The frozen whole-chain verdict vocabulary.

    There is deliberately NO verdict that reports a passing
    production composition while a required authority is absent:
    ``BLOCKED_MISSING_AUTHORITY`` is the only reachable verdict on
    the current mainline (W048 accepted-not-restored), and it
    always pairs with ``production_composition=False``.
    """

    BLOCKED_MISSING_AUTHORITY = "BLOCKED_MISSING_AUTHORITY"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.BLOCKED_MISSING_AUTHORITY,)


#: The seven mandatory negative proofs of the R2 gate (the frozen
#: roadmap wording; each is proven mechanically by the battery).
NEGATIVE_PROOF_STATEMENTS: Tuple[str, ...] = (
    "payment success cannot create connectivity",
    "reservation success cannot imply reachability",
    "marketplace discovery cannot activate a path",
    "W050 capability declaration cannot enforce containment",
    "W049 client state cannot become canonical state",
    "API/webhook observation cannot become a second source of truth",
    "software evidence cannot close physical evidence",
)


@dataclass(frozen=True)
class EdgeOutcome:
    """One recorded chain-edge execution over the real authorities.

    ``correlation`` carries ONLY authority-sourced identities and
    digests (content-derived ids, journal digests, statement ids)
    -- never a composition-minted authority identity.  ``detail``
    is the deterministic human-readable evidence line.
    """

    edge_id: str
    owning_work_item: str
    authority_surface: str
    evidence_class: str
    outcome: str
    reason: str
    detail: str
    correlation: Dict[str, Any] = field(default_factory=dict)
    instant: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "edge_id": self.edge_id,
            "owning_work_item": self.owning_work_item,
            "authority_surface": self.authority_surface,
            "evidence_class": self.evidence_class,
            "outcome": self.outcome,
            "reason": self.reason,
            "detail": self.detail,
            "correlation": self.correlation,
        }
        if self.instant:
            data["instant"] = self.instant
        return data


def chain_edge(edge_id: str) -> EdgeSpec:
    """Resolve one frozen edge by id (fail closed on unknown)."""
    for edge in CHAIN_EDGES:
        if edge.edge_id == edge_id:
            return edge
    raise KeyError("unknown chain edge %r" % edge_id)


@dataclass(frozen=True)
class CompositionTrace:
    """The deterministic evidence document of one chain run.

    Derived data only: every member is a projection of the
    composed authorities' own public outputs.  The trace is never
    a state store, never journaled, and never authoritative for
    anything -- it is conformance evidence.
    """

    edges: Tuple[EdgeOutcome, ...]
    verdict: str
    verdict_detail: str
    blocked_at: str
    missing_authority: str
    production_composition: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "work-054-composition-trace",
            "verdict": self.verdict,
            "verdict_detail": self.verdict_detail,
            "blocked_at": self.blocked_at,
            "missing_authority": self.missing_authority,
            "production_composition": self.production_composition,
            "edges": [edge.to_dict() for edge in self.edges],
        }

    def content_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    def digest(self) -> str:
        """The WORK-003-convention content digest of the trace."""
        return "sha256:" + hashlib.sha256(self.content_bytes()).hexdigest()

    def outcomes_by_edge(self) -> Dict[str, str]:
        return {edge.edge_id: edge.outcome for edge in self.edges}

    def reasons_by_edge(self) -> Dict[str, str]:
        return {edge.edge_id: edge.reason for edge in self.edges}

    def fail_closed_edges(self) -> Tuple[EdgeOutcome, ...]:
        return tuple(
            edge for edge in self.edges if edge.outcome == StageOutcome.FAIL_CLOSED
        )
