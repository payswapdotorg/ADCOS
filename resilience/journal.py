"""ADCOS resilience journal (M015 — Execution Resilience Runtime).

The deterministic, replayable runtime journal and its fold
(construction-is-recovery — the accepted ``contracts/store.py``
discipline, re-expressed for the execution runtime):

- :func:`fold_events` — the pure deterministic fold of one runtime
  session's append-only event sequence onto its
  :class:`~resilience.model.RuntimeSession` snapshot.  The fold is the
  SOLE writer of runtime state (the store appends validated events;
  the state is always the fold of the journal).  Fail-closed gates:
  the sequence must start with ``session-created`` at position 1 (and
  the runtime identity must re-derive from the creation core — tamper
  evidence); journal positions must be gapless and conflict-free
  (``resilience-journal-divergence``); every event must attribute to
  the same runtime session and the same owning contract; the
  kind/state chain must be legal (the frozen transition table, wrapped
  as journal divergence); and — the WORK-012 discipline mechanically
  enforced — the realization references change ONLY through the
  explicit reconnect pair, with the initiation naming the OLD
  references verbatim and the completion naming BOTH sides with its
  NEW references equal to the initiation's declared candidates
  (``resilience-silent-replacement`` otherwise, never a silent
  replacement).
- :func:`reconnect_evidence` — the derivation of the typed
  :class:`~resilience.model.RuntimeReconnect` evidence records from
  the journal's initiating/completing event pairs (fail-closed on an
  orphaned completion — a completion without a matching initiation is
  a silent replacement, never evidence).

Determinism (LOCK-119): the fold is pure and order-driven (no wall
clock, no randomness, no network, no secrets); the same event sequence
always folds to the byte-identical runtime snapshot; canonical-JSON
round-trips with tamper-evident ids.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from resilience.errors import ResilienceError, ResilienceReason
from resilience.model import (
    RuntimeEvent,
    RuntimeReconnect,
    RuntimeSession,
    RUNTIME_RECONNECTABLE_STATES,
    derive_runtime_id,
)

__all__ = [
    "EVENT_TARGET_STATES",
    "fold_events",
    "reconnect_evidence",
]


#: The frozen kind -> allowed ``state_after`` map (the kind/state
#: consistency of the journal chain: an event of kind K may only land
#: the runtime in one of these states — a ``degraded-entered`` event
#: landing the runtime in RECONNECTING is journal divergence).
EVENT_TARGET_STATES: Dict[str, Tuple[str, ...]] = {
    "session-created": ("PENDING",),
    "session-activated": ("ACTIVE",),
    "reconnect-initiated": ("RECONNECTING",),
    "reconnect-completed": ("ACTIVE",),
    "reconnect-failed": ("DEGRADED", "FAILED"),
    "degraded-entered": ("DEGRADED",),
    "degraded-recovered": ("ACTIVE",),
    "session-failed": ("FAILED",),
    "session-terminated": ("TERMINATED",),
}


def _require_event_sequence(events: object, label: str) -> Tuple[RuntimeEvent, ...]:
    if isinstance(events, (str, bytes)) or not isinstance(events, (tuple, list)):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "%s must be a sequence of events" % label
        )
    for i, item in enumerate(events):
        if not isinstance(item, RuntimeEvent):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "%s[%d] must be a RuntimeEvent record (got %s)"
                % (label, i, type(item).__name__),
            )
    return tuple(events)


def fold_events(events: object, *, label: str = "the runtime journal") -> RuntimeSession:
    """Fold one runtime session's append-only event sequence onto its
    :class:`RuntimeSession` snapshot (the pure deterministic fold —
    construction-is-recovery).

    Fail-closed gates, in fold order:

    1. the sequence is non-empty and starts with ``session-created``
       at journal position 1, landing PENDING, with the runtime
       identity re-derived from the creation core (tamper evidence);
    2. journal positions are gapless and conflict-free
       (``resilience-journal-divergence``); every event attributes to
       the same runtime session and the same owning contract;
    3. every event's ``state_after`` is a legal successor of the prior
       state AND consistent with its kind (the frozen
       :data:`EVENT_TARGET_STATES` map) — except the reconnect
       completion, whose orphaned shape (no matching initiation) fails
       as the WORK-012 ``resilience-silent-replacement`` discipline;
    4. the realization references change ONLY through the explicit
       reconnect pair — the initiation names the OLD references
       verbatim; the completion names BOTH sides with its NEW
       references equal to the initiation's declared candidates
       (``resilience-silent-replacement`` otherwise).
    """
    sequence = _require_event_sequence(events, label)
    if not sequence:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "%s carries no events" % label
        )

    first = sequence[0]
    if first.kind != "session-created":
        raise ResilienceError(
            ResilienceReason.JOURNAL_DIVERGENCE,
            "%s does not start with session-created (found %r at position 1)"
            % (label, first.kind),
        )
    if first.sequence != 1:
        raise ResilienceError(
            ResilienceReason.JOURNAL_DIVERGENCE,
            "the session-created event must hold journal position 1 (found %d)"
            % first.sequence,
        )
    expected_runtime_id = derive_runtime_id(
        first.contract_id, first.recorded_at, first.provenance
    )
    if first.runtime_id != expected_runtime_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the runtime identity does not re-derive from the creation core "
            "(tamper evidence): expected %s, the journal carries %s"
            % (expected_runtime_id[:23], first.runtime_id[:23]),
        )

    state = "PENDING"
    route_decision_id = ""
    path_id = ""
    pending_route = None  # the initiation's declared candidates

    for index, event in enumerate(sequence):
        position = index + 1
        if event.sequence != position:
            raise ResilienceError(
                ResilienceReason.JOURNAL_DIVERGENCE,
                "event at fold position %d carries journal position %d "
                "(gap or conflict — the journal is not replayable)"
                % (position, event.sequence),
            )
        if event.runtime_id != first.runtime_id or event.contract_id != first.contract_id:
            raise ResilienceError(
                ResilienceReason.JOURNAL_DIVERGENCE,
                "event at position %d attributes to runtime %s / contract %s, "
                "not the journal's %s / %s"
                % (
                    position,
                    event.runtime_id[:23],
                    event.contract_id[:23],
                    first.runtime_id[:23],
                    first.contract_id[:23],
                ),
            )
        allowed_targets = EVENT_TARGET_STATES.get(event.kind, ())
        if event.state_after not in allowed_targets:
            raise ResilienceError(
                ResilienceReason.JOURNAL_DIVERGENCE,
                "the %s event lands the runtime in %s (allowed: %s) — the "
                "kind/state chain diverged"
                % (event.kind, event.state_after, ", ".join(allowed_targets) or "none"),
            )
        if event.kind == "reconnect-completed" and state != "RECONNECTING":
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "a reconnect completion at position %d has no matching "
                "initiation (the runtime is %s, not RECONNECTING) — a route "
                "change is ALWAYS the explicit initiated+completed pair "
                "naming old AND new references, never a silent replacement"
                % (position, state),
            )
        if event.kind != "session-created":
            # the generic state-chain legality (terminal states never
            # exit; illegal edges diverge)
            if state in ("FAILED", "TERMINATED"):
                raise ResilienceError(
                    ResilienceReason.JOURNAL_DIVERGENCE,
                    "event at position %d follows the terminal %s state — "
                    "terminal runtimes never transition" % (position, state),
                )
            legal = {
                "PENDING": ("ACTIVE", "FAILED", "TERMINATED"),
                "ACTIVE": ("RECONNECTING", "DEGRADED", "FAILED", "TERMINATED"),
                "RECONNECTING": ("ACTIVE", "DEGRADED", "FAILED", "TERMINATED"),
                "DEGRADED": ("RECONNECTING", "ACTIVE", "FAILED", "TERMINATED"),
            }.get(state, ())
            if event.state_after not in legal:
                raise ResilienceError(
                    ResilienceReason.JOURNAL_DIVERGENCE,
                    "the %s event transitions %s -> %s (legal: %s) — the "
                    "state chain diverged"
                    % (event.kind, state, event.state_after, ", ".join(legal) or "none"),
                )
        if event.kind == "reconnect-initiated":
            if state not in RUNTIME_RECONNECTABLE_STATES:
                raise ResilienceError(
                    ResilienceReason.JOURNAL_DIVERGENCE,
                    "a reconnect initiation at position %d from the %s state "
                    "has no realization references to leave" % (position, state),
                )
            if (event.old_route_decision_id, event.old_path_id) != (
                route_decision_id,
                path_id,
            ):
                raise ResilienceError(
                    ResilienceReason.SILENT_REPLACEMENT,
                    "the initiating reconnect at position %d names the old "
                    "references %s/%s, not the session's current %s/%s — the "
                    "initiation must name the references being left verbatim "
                    "(the WORK-012 discipline)"
                    % (
                        position,
                        event.old_route_decision_id,
                        event.old_path_id,
                        route_decision_id,
                        path_id,
                    ),
                )
            pending_route = (
                event.candidate_route_decision_id,
                event.candidate_path_id,
            )
        elif event.kind == "reconnect-completed":
            if (event.old_route_decision_id, event.old_path_id) != (
                route_decision_id,
                path_id,
            ):
                raise ResilienceError(
                    ResilienceReason.SILENT_REPLACEMENT,
                    "the completed reconnect at position %d names the old "
                    "references %s/%s, not the session's pre-change %s/%s "
                    "(the WORK-012 discipline requires BOTH the old AND the "
                    "new references, verbatim)"
                    % (
                        position,
                        event.old_route_decision_id,
                        event.old_path_id,
                        route_decision_id,
                        path_id,
                    ),
                )
            if pending_route is None or (
                event.new_route_decision_id,
                event.new_path_id,
            ) != pending_route:
                raise ResilienceError(
                    ResilienceReason.SILENT_REPLACEMENT,
                    "the completed reconnect at position %d names the new "
                    "references %s/%s, not the initiation's declared "
                    "candidates %s — a realization change to anything other "
                    "than the explicitly declared candidate is a silent "
                    "replacement (the WORK-012 discipline)"
                    % (
                        position,
                        event.new_route_decision_id,
                        event.new_path_id,
                        "/".join(pending_route) if pending_route else "(none declared)",
                    ),
                )
            route_decision_id, path_id = event.new_route_decision_id, event.new_path_id
            pending_route = None
        elif event.kind == "session-activated":
            route_decision_id = event.route_decision_id
            path_id = event.path_id
        elif event.kind == "reconnect-failed":
            # the attempted reconnect did not complete: the session
            # keeps its pre-change references
            pending_route = None
        # degraded-entered / degraded-recovered / session-failed /
        # session-terminated leave the references unchanged
        state = event.state_after

    if state == "PENDING":
        route_decision_id, path_id = "", ""

    return RuntimeSession(
        runtime_id=first.runtime_id,
        contract_id=first.contract_id,
        state=state,
        created_at=first.recorded_at,
        sequence=sequence[-1].sequence,
        provenance=first.provenance,
        route_decision_id=route_decision_id,
        path_id=path_id,
    )


def reconnect_evidence(
    events: object, *, label: str = "the runtime journal"
) -> Tuple[RuntimeReconnect, ...]:
    """Derive the typed reconnect evidence records from the journal's
    initiating/completing event pairs (the WORK-012 discipline as
    evidence: old AND new, both sides, fail-closed).

    Every ``reconnect-completed`` event MUST be paired with its
    preceding ``reconnect-initiated`` event (an orphaned completion is
    a silent replacement, never evidence).  The returned records cite
    the initiating/completing event ids, the reconnect instant (the
    completion's), and all four route-change members.
    """
    sequence = _require_event_sequence(events, label)
    records: list = []
    initiated: RuntimeEvent | None = None
    for position, event in enumerate(sequence, start=1):
        if event.kind == "reconnect-initiated":
            initiated = event
        elif event.kind == "reconnect-completed":
            if initiated is None:
                raise ResilienceError(
                    ResilienceReason.SILENT_REPLACEMENT,
                    "a reconnect completion at position %d has no matching "
                    "initiation — never evidence (the WORK-012 discipline "
                    "requires the explicit initiated+completed pair naming "
                    "old AND new references)" % position,
                )
            records.append(
                RuntimeReconnect(
                    runtime_id=event.runtime_id,
                    initiated_event_id=initiated.event_id,
                    completed_event_id=event.event_id,
                    reconnect_instant=event.recorded_at,
                    old_route_decision_id=event.old_route_decision_id,
                    new_route_decision_id=event.new_route_decision_id,
                    old_path_id=event.old_path_id,
                    new_path_id=event.new_path_id,
                )
            )
            initiated = None
        elif event.kind == "reconnect-failed":
            initiated = None
    return tuple(records)
