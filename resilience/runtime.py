"""ADCOS resilience runtime store (M015 — Execution Resilience Runtime).

The deterministic, atomic session-runtime lifecycle persistence — the
WORK-012 store discipline re-expressed on the Architecture 1.1
authority:

- **ATOMICITY**: every mutation is validated in full BEFORE any state
  changes (the new event is appended only after every gate passes); a
  rejected operation leaves the journal byte-identical.
- **REPLAY**: the runtime state is ALWAYS the deterministic fold of
  the append-only journal (construction-is-recovery —
  :func:`resilience.journal.fold_events`); ``RuntimeStore.from_events``
  rebuilds a store from a journal with no other state.
- **ROUTE BINDING**: the realization references change ONLY through
  the explicit reconnect pair (initiate + complete), each side
  recorded, the new references equal to the declared candidates —
  nothing silently replaces a route (the WORK-012 discipline,
  mechanically enforced by the fold).
- **EXPLICIT DEGRADED MODE**: entering/leaving degraded operation is a
  journaled runtime event with typed provenance and an evidence kind
  drawn from the accepted ``evidence/`` LOCK-106 vocabulary — never a
  silent downgrade.
- **THE REPLAN-KERNEL COMPOSITION**: :func:`drive_replan_decision`
  applies an accepted ``replan.ReplanDecision`` (computed by the
  M008 kernel, consumed BY REFERENCE — never duplicated here) to the
  runtime journal: adopt-alternative -> the explicit reconnect pair;
  degraded -> the journaled degraded entry; failed/renegotiate -> the
  explicit terminal failure.  Every path is journaled with the
  decision's identity in the event provenance (LOCK-118).

The store never writes contract state: adopted realizations ride back
toward the contract only through the contract's own frozen command
vocabulary (the M008 ``replan.bridge``, consumed by the caller); the
runtime session is an execution artifact riding the contract as an
opaque reference (LOCK-117).

Determinism (LOCK-119): injected instants only; content-derived ids;
no wall clock, no randomness, no network, no secrets.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from contracts import ConnectivityContract, OpaqueReference, Provenance

from replan import ReplanDecision

from resilience.errors import ResilienceError, ResilienceReason
from resilience.journal import fold_events, reconnect_evidence
from resilience.model import (
    RUNTIME_RECONNECTABLE_STATES,
    RUNTIME_TERMINAL_STATES,
    RuntimeEvent,
    RuntimeReconnect,
    RuntimeSession,
    check_runtime_transition,
    check_realization_surface,
    derive_runtime_id,
)

__all__ = [
    "RUNTIME_DRIVEN_ISSUER",
    "RuntimeStore",
    "DriveResult",
    "drive_replan_decision",
]


#: The issuer recorded on runtime events produced by the replan-kernel
#: composition (LOCK-118: the drive cites the decision it applies).
RUNTIME_DRIVEN_ISSUER = "resilience:runtime-replan-drive"


def _require_not_terminal(session: RuntimeSession, operation: str) -> None:
    """Fail closed with the SPECIFIC typed terminal reason BEFORE any
    operation-specific state gate: a terminal runtime session never
    transitions, and ``resilience-session-terminal`` (the vocabulary's
    own terminal reason — "FAILED/TERMINATED sessions never
    transition") must surface uniformly across every lifecycle
    operation, never masked by a generic transition error."""
    if session.state in RUNTIME_TERMINAL_STATES:
        raise ResilienceError(
            ResilienceReason.SESSION_TERMINAL,
            "runtime session is terminal in %s; terminal runtime sessions never "
            "transition (the %s operation is rejected)" % (session.state, operation),
        )


class RuntimeStore:
    """The deterministic session-runtime store (append-only journal +
    pure fold; the sole writer of runtime state is the fold)."""

    def __init__(self) -> None:
        self._events: Dict[str, List[RuntimeEvent]] = {}

    # -- read surface --------------------------------------------------

    def get(self, runtime_id: object) -> Optional[RuntimeSession]:
        """The folded runtime session (None when unknown)."""
        if not isinstance(runtime_id, str) or not runtime_id:
            return None
        events = self._events.get(runtime_id)
        if not events:
            return None
        return fold_events(events, label="the runtime journal")

    def session(self, runtime_id: object) -> RuntimeSession:
        """The folded runtime session (fail-closed on unknown)."""
        if not isinstance(runtime_id, str) or not runtime_id:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "runtime_id must be a non-empty string"
            )
        events = self._events.get(runtime_id)
        if not events:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "runtime session %s is unknown to the runtime store (fail-closed: "
                "the runtime surface never invents a session)" % runtime_id[:32],
            )
        return fold_events(events, label="the runtime journal")

    def events(self, runtime_id: object) -> Tuple[RuntimeEvent, ...]:
        """The append-only journal of one runtime session (its own
        deterministic order)."""
        if not isinstance(runtime_id, str) or not runtime_id:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "runtime_id must be a non-empty string"
            )
        events = self._events.get(runtime_id)
        if not events:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "runtime session %s is unknown to the runtime store" % runtime_id[:32],
            )
        return tuple(events)

    def reconnect_evidence(self, runtime_id: object) -> Tuple[RuntimeReconnect, ...]:
        """The typed reconnect evidence records of one runtime session
        (the WORK-012 discipline as evidence)."""
        return reconnect_evidence(
            self.events(runtime_id), label="the runtime journal"
        )

    def sessions(self) -> Tuple[RuntimeSession, ...]:
        """All folded runtime sessions (deterministic id order)."""
        return tuple(
            fold_events(self._events[runtime_id], label="the runtime journal")
            for runtime_id in sorted(self._events)
        )

    def verify_integrity(self, runtime_id: object) -> None:
        """Fail closed unless the journal re-folds byte-identically
        (the deterministic replay check — construction-is-recovery)."""
        current = self.session(runtime_id)
        replayed = fold_events(
            self.events(runtime_id), label="the integrity replay"
        )
        if current.canonical_bytes() != replayed.canonical_bytes():
            raise ResilienceError(
                ResilienceReason.JOURNAL_DIVERGENCE,
                "the journal of runtime %s does not re-fold byte-identically "
                "(construction-is-recovery violated)" % current.runtime_id[:23],
            )

    # -- construction-is-recovery ---------------------------------------

    @classmethod
    def from_events(cls, events: object) -> "RuntimeStore":
        """Rebuild a store from an event journal (construction-is-
        recovery: no state exists outside the fold)."""
        store = cls()
        sequence = tuple(events)
        folded = fold_events(sequence, label="the recovery journal")
        store._events[folded.runtime_id] = list(sequence)
        store.verify_integrity(folded.runtime_id)
        return store

    # -- lifecycle operations (atomic: validate fully, then append) ----

    def create(
        self,
        *,
        contract_id: object,
        created_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """Create one runtime session riding the owning contract
        (PENDING; the runtime identity is content-derived over the
        creation core).  Idempotent for a byte-identical re-creation;
        a conflicting re-use of the identity fails closed."""
        if not isinstance(provenance, Provenance):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "create requires a contracts.Provenance record (LOCK-118)",
            )
        if not isinstance(contract_id, str) or not contract_id:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "contract_id must be a non-empty string"
            )
        runtime_id = derive_runtime_id(contract_id, created_at, provenance)
        existing = self._events.get(runtime_id)
        if existing:
            replay = fold_events(existing, label="the runtime journal")
            if replay.contract_id == contract_id and replay.created_at == created_at:
                return replay
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "runtime identity %s already exists with different creation "
                "material (create is once; conflicting re-use fails closed)"
                % runtime_id[:23],
            )
        event = RuntimeEvent(
            runtime_id=runtime_id,
            contract_id=contract_id,
            sequence=1,
            kind="session-created",
            recorded_at=created_at,
            state_after="PENDING",
            provenance=provenance,
        )
        self._events[runtime_id] = [event]
        return fold_events(self._events[runtime_id], label="the runtime journal")

    def activate(
        self,
        runtime_id: object,
        *,
        route_decision_id: object,
        path_id: object,
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """PENDING -> ACTIVE, naming the INITIAL realization references
        (both required — activating without naming the realization is a
        silent-replacement shape)."""
        session = self.session(runtime_id)
        _require_not_terminal(session, "activation")
        if session.state != "PENDING":
            raise ResilienceError(
                ResilienceReason.TRANSITION_ILLEGAL,
                "activation requires the PENDING runtime state (found %s; the "
                "runtime is already realizing or terminal)"
                % session.state,
            )
        check_runtime_transition(session.state, "ACTIVE")
        if not isinstance(route_decision_id, str) or not route_decision_id:
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "activation must name the initial realization references "
                "(route_decision_id AND path_id) — an unnamed realization is "
                "a silent replacement shape",
            )
        if not isinstance(path_id, str) or not path_id:
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "activation must name the initial realization references "
                "(route_decision_id AND path_id) — an unnamed realization is "
                "a silent replacement shape",
            )
        event = self._append(
            session,
            kind="session-activated",
            state_after="ACTIVE",
            recorded_at=recorded_at,
            provenance=provenance,
            route_decision_id=route_decision_id,
            path_id=path_id,
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    def initiate_reconnect(
        self,
        runtime_id: object,
        *,
        candidate_route_decision_id: object,
        candidate_path_id: object,
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """ACTIVE/DEGRADED -> RECONNECTING: the EXPLICIT initiation of a
        route change, naming the OLD references verbatim (they must
        equal the session's current ones — enforced by the fold) and
        the CANDIDATE new references."""
        session = self.session(runtime_id)
        _require_not_terminal(session, "reconnect initiation")
        if session.state not in RUNTIME_RECONNECTABLE_STATES:
            raise ResilienceError(
                ResilienceReason.TRANSITION_ILLEGAL,
                "a reconnect initiation requires a realization-holder state "
                "(ACTIVE or DEGRADED; found %s — a PENDING runtime has no "
                "realization to leave and terminal runtimes never transition)"
                % session.state,
            )
        if not isinstance(candidate_route_decision_id, str) or not candidate_route_decision_id:
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "a reconnect initiation must declare the candidate new "
                "references (candidate_route_decision_id AND "
                "candidate_path_id) — an undeclared candidate is a silent "
                "replacement shape",
            )
        if not isinstance(candidate_path_id, str) or not candidate_path_id:
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "a reconnect initiation must declare the candidate new "
                "references (candidate_route_decision_id AND "
                "candidate_path_id) — an undeclared candidate is a silent "
                "replacement shape",
            )
        old_route, old_path = session.realization_refs()
        event = self._append(
            session,
            kind="reconnect-initiated",
            state_after="RECONNECTING",
            recorded_at=recorded_at,
            provenance=provenance,
            old_route_decision_id=old_route,
            old_path_id=old_path,
            candidate_route_decision_id=candidate_route_decision_id,
            candidate_path_id=candidate_path_id,
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    def complete_reconnect(
        self,
        runtime_id: object,
        *,
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """RECONNECTING -> ACTIVE: the EXPLICIT completion of the pending
        reconnect.  The new references are the initiation's declared
        candidates (enforced verbatim by the fold — a completion naming
        anything else, or without a matching initiation, is a SILENT
        REPLACEMENT and fails closed).  The completed event records
        BOTH the old AND the new references (the WORK-012 evidence
        shape)."""
        session = self.session(runtime_id)
        _require_not_terminal(session, "reconnect completion")
        if session.state != "RECONNECTING":
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "a reconnect completion requires an in-progress initiation "
                "(the runtime is %s, not RECONNECTING) — a route change "
                "without the explicit initiated+completed pair naming old "
                "AND new references is never a silent replacement"
                % session.state,
            )
        initiation = self._events[session.runtime_id][-1]
        if initiation.kind != "reconnect-initiated":
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "the pending journal entry is not a reconnect initiation — "
                "the completion cannot take its declared candidates",
            )
        old_route, old_path = session.realization_refs()
        event = self._append(
            session,
            kind="reconnect-completed",
            state_after="ACTIVE",
            recorded_at=recorded_at,
            provenance=provenance,
            old_route_decision_id=old_route,
            old_path_id=old_path,
            new_route_decision_id=initiation.candidate_route_decision_id,
            new_path_id=initiation.candidate_path_id,
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    def fail_reconnect(
        self,
        runtime_id: object,
        *,
        target: object,
        reason: object,
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """RECONNECTING -> DEGRADED/FAILED: the attempted reconnect did
        not complete; the session keeps its pre-change references and
        carries the typed reason."""
        session = self.session(runtime_id)
        _require_not_terminal(session, "reconnect failure")
        if session.state != "RECONNECTING":
            raise ResilienceError(
                ResilienceReason.TRANSITION_ILLEGAL,
                "a reconnect failure requires an in-progress initiation "
                "(found %s)" % session.state,
            )
        if target not in ("DEGRADED", "FAILED"):
            raise ResilienceError(
                ResilienceReason.VOCABULARY,
                "a reconnect failure lands the runtime in DEGRADED or FAILED "
                "(found %r)" % (target,),
            )
        if not isinstance(reason, str) or not reason:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "reason must be a non-empty string"
            )
        self._append(
            session,
            kind="reconnect-failed",
            state_after=target,
            recorded_at=recorded_at,
            provenance=provenance,
            reason=reason,
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    def enter_degraded(
        self,
        runtime_id: object,
        *,
        evidence_kind: object,
        evidence_refs: object = (),
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """ACTIVE/RECONNECTING -> DEGRADED: the EXPLICIT degraded-mode
        entry — a journaled runtime event with typed provenance and an
        evidence kind drawn from the accepted ``evidence/`` LOCK-106
        vocabulary (never a silent downgrade)."""
        session = self.session(runtime_id)
        check_runtime_transition(session.state, "DEGRADED")
        if not isinstance(evidence_kind, str) or not evidence_kind:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the degraded entry must cite its evidence kind (the accepted "
                "evidence/ LOCK-106 type vocabulary)",
            )
        self._append(
            session,
            kind="degraded-entered",
            state_after="DEGRADED",
            recorded_at=recorded_at,
            provenance=provenance,
            evidence_kind=evidence_kind,
            evidence_refs=tuple(evidence_refs or ()),
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    def recover_degraded(
        self,
        runtime_id: object,
        *,
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """DEGRADED -> ACTIVE: the EXPLICIT degraded-mode exit —
        journaled, typed provenance, never silent."""
        session = self.session(runtime_id)
        _require_not_terminal(session, "degraded recovery")
        if session.state != "DEGRADED":
            raise ResilienceError(
                ResilienceReason.TRANSITION_ILLEGAL,
                "a degraded recovery requires the DEGRADED runtime state "
                "(found %s)" % session.state,
            )
        check_runtime_transition(session.state, "ACTIVE")
        self._append(
            session,
            kind="degraded-recovered",
            state_after="ACTIVE",
            recorded_at=recorded_at,
            provenance=provenance,
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    def fail(
        self,
        runtime_id: object,
        *,
        reason: object,
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """-> FAILED: the explicit terminal failure with its typed
        reason."""
        session = self.session(runtime_id)
        if not isinstance(reason, str) or not reason:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "reason must be a non-empty string"
            )
        check_runtime_transition(session.state, "FAILED")
        self._append(
            session,
            kind="session-failed",
            state_after="FAILED",
            recorded_at=recorded_at,
            provenance=provenance,
            reason=reason,
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    def terminate(
        self,
        runtime_id: object,
        *,
        recorded_at: object,
        provenance: object,
    ) -> RuntimeSession:
        """-> TERMINATED: the explicit deliberate termination."""
        session = self.session(runtime_id)
        check_runtime_transition(session.state, "TERMINATED")
        self._append(
            session,
            kind="session-terminated",
            state_after="TERMINATED",
            recorded_at=recorded_at,
            provenance=provenance,
        )
        return fold_events(self._events[session.runtime_id], label="the runtime journal")

    # -- internals ------------------------------------------------------

    def _append(
        self,
        session: RuntimeSession,
        *,
        kind: str,
        state_after: str,
        recorded_at: object,
        provenance: object,
        **members: object,
    ) -> RuntimeEvent:
        """Validate and append one event (atomic: the event constructor
        and the fold validate in full BEFORE the append is visible)."""
        if not isinstance(provenance, Provenance):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the %s event requires a contracts.Provenance record (LOCK-118)"
                % kind,
            )
        event = RuntimeEvent(
            runtime_id=session.runtime_id,
            contract_id=session.contract_id,
            sequence=session.sequence + 1,
            kind=kind,
            recorded_at=recorded_at,
            state_after=state_after,
            provenance=provenance,
            **members,
        )
        candidate_journal = self._events[session.runtime_id] + [event]
        # the fold is the sole writer of state: the appended journal
        # must fold cleanly or nothing is appended (atomicity)
        fold_events(candidate_journal, label="the candidate journal")
        self._events[session.runtime_id].append(event)
        return event


# ----------------------------------------------------------------------
# The replan-kernel composition core (the runtime DRIVES the accepted
# M008 engine's decision — never duplicates it)
# ----------------------------------------------------------------------


#: The frozen mapping of the consumed M008 decision kinds onto the
#: runtime drive outcome kinds (never a second decision model — the
#: consumed decision record rides verbatim on every result).
DRIVE_OUTCOME_KINDS: Tuple[str, ...] = (
    "adopted",
    "degraded",
    "failed",
    "renegotiate",
)


class DriveResult:
    """The typed outcome envelope of driving the accepted M008 replan
    kernel through the runtime journal (shared by the handover engine
    and the failover orchestrator — both drive the SAME consumed
    kernel through the SAME composition core): the applied M008
    decision record (consumed, verbatim), the runtime session AFTER
    the drive, the reconnect evidence when the drive adopted (old AND
    new references — the WORK-012 discipline), and the appended
    journal event ids (evidence-visible)."""

    __slots__ = ("decision", "session", "reconnect", "event_ids")

    def __init__(
        self,
        decision: ReplanDecision,
        session: RuntimeSession,
        reconnect: Optional[RuntimeReconnect],
        event_ids: Tuple[str, ...],
    ) -> None:
        self.decision = decision
        self.session = session
        self.reconnect = reconnect
        self.event_ids = event_ids

    @property
    def outcome(self) -> str:
        """The drive outcome kind (the frozen :data:`DRIVE_OUTCOME_KINDS`
        mapping of the consumed decision kind)."""
        if self.decision.decision == "adopt-alternative":
            return "adopted"
        return self.decision.decision

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "DriveResult(outcome=%s, decision=%s)" % (
            self.outcome,
            self.decision.decision_id[:23],
        )


def drive_replan_decision(
    store: RuntimeStore,
    runtime_id: object,
    contract: ConnectivityContract,
    decision: ReplanDecision,
    *,
    recorded_at: object,
    new_route_decision_id: object = None,
    new_path_id: object = None,
    provenance: Optional[Provenance] = None,
) -> Tuple[RuntimeSession, Optional[RuntimeReconnect]]:
    """Apply one accepted ``replan.ReplanDecision`` to the runtime
    journal (the composition core: the resilience runtime drives the
    M008 kernel's decision — every effect is journaled, never silent).

    Mapping (deterministic, closed against the CONSUMED decision
    vocabulary — there is no second decision model):

    - ``adopt-alternative`` -> the EXPLICIT reconnect pair
      (initiation naming the old references verbatim + completion
      naming BOTH sides with the adopted candidate's declared new
      references); the runtime lands ACTIVE on the adopted
      realization;
    - ``degraded`` -> the journaled EXPLICIT degraded-mode entry (the
      decision id rides the evidence references and the provenance);
    - ``failed`` / ``renegotiate`` -> the EXPLICIT terminal failure
      (the decision id rides the provenance; the typed renegotiation
      notice stays on the decision record for the caller's
      principal-side renegotiation flow — never a silent downgrade).

    Fail-closed gates: the decision must be an accepted
    ``replan.ReplanDecision`` attributable to exactly the owning
    contract of exactly this runtime session; an adopt-alternative
    decision must carry EXACTLY two adopted artifact references whose
    values equal the supplied new realization references (the decision
    record is the truth — a mismatch fails closed
    ``resilience-id-mismatch``).
    """
    if not isinstance(store, RuntimeStore):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "drive_replan_decision requires a resilience RuntimeStore (got %s)"
            % type(store).__name__,
        )
    if not isinstance(decision, ReplanDecision):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "drive_replan_decision requires a replan.ReplanDecision (got %s) — "
            "the accepted M008 kernel computes the decision; the runtime only "
            "applies it" % type(decision).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "drive_replan_decision requires a contracts.ConnectivityContract "
            "(got %s)" % type(contract).__name__,
        )
    session = store.session(runtime_id)
    if decision.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the decision is attributable to contract %s, not %s"
            % (decision.contract_id[:23], contract.contract_id[:23]),
        )
    if session.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "runtime session %s rides contract %s, not %s"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    # the runtime must be a replan surface (PENDING fails closed as
    # not-established; terminal runtimes never transition)
    check_realization_surface(session.state)

    drive_provenance = (
        provenance
        if provenance is not None
        else Provenance(
            issuer=RUNTIME_DRIVEN_ISSUER,
            decision_refs=(decision.decision_id, decision.trigger_id),
        )
    )
    if not isinstance(drive_provenance, Provenance):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    if decision.decision == "adopt-alternative":
        if len(decision.adopted_artifacts) != 2:
            raise ResilienceError(
                ResilienceReason.ID_MISMATCH,
                "an adopted alternative realization names exactly its two "
                "realization references (route decision id and path id — the "
                "WORK-012 member shape); the decision carries %d artifact "
                "references" % len(decision.adopted_artifacts),
            )
        adopted_route = decision.adopted_artifacts[0].value
        adopted_path = decision.adopted_artifacts[1].value
        if (new_route_decision_id, new_path_id) != (adopted_route, adopted_path):
            raise ResilienceError(
                ResilienceReason.ID_MISMATCH,
                "the supplied new realization references %r/%r do not equal "
                "the decision's adopted artifact references %r/%r — the "
                "decision record is the truth (never a silent divergence)"
                % (new_route_decision_id, new_path_id, adopted_route, adopted_path),
            )
        store.initiate_reconnect(
            session.runtime_id,
            candidate_route_decision_id=adopted_route,
            candidate_path_id=adopted_path,
            recorded_at=recorded_at,
            provenance=drive_provenance,
        )
        after = store.complete_reconnect(
            session.runtime_id,
            recorded_at=recorded_at,
            provenance=drive_provenance,
        )
        evidence = store.reconnect_evidence(session.runtime_id)
        return after, (evidence[-1] if evidence else None)

    if decision.decision == "degraded":
        after = store.enter_degraded(
            session.runtime_id,
            evidence_kind="observation",
            evidence_refs=(
                OpaqueReference(
                    ref_kind="decision",
                    value=decision.decision_id,
                    provenance=Provenance(
                        issuer=RUNTIME_DRIVEN_ISSUER,
                        decision_refs=(decision.trigger_id, decision.contract_id),
                    ),
                ),
            ),
            recorded_at=recorded_at,
            provenance=drive_provenance,
        )
        return after, None

    # failed / renegotiate: the explicit terminal failure
    after = store.fail(
        session.runtime_id,
        reason=decision.decision,
        recorded_at=recorded_at,
        provenance=drive_provenance,
    )
    return after, None
