"""WORK-042 journal-first recovery.

The exact ACR-006 section 3 flow, as one deterministic procedure:

    load durable snapshot (checkpoint)
        -> verify the checkpoint <-> journal binding
        -> replay the journal tail deterministically
        -> obtain a FRESH authoritative platform observation
        -> reconcile reconstructed state with the fresh observation
        -> record session loss HONESTLY where transport state
           cannot survive process death

Honesty rules (battery-pinned):

- transport liveness is NEVER faked: the killed process's runtime
  (adapters, transport bindings, in-memory session state) is gone;
  every session-binding REFERENCE recorded in the checkpoint is
  reported lost and journaled as a session-loss record, whatever
  the fresh platform observation says about the underlying
  interfaces.  A still-present interface does NOT resurrect a
  session (that would be fabricating continuity);
- no session is ever RECREATED by recovery: the recovery procedure
  has NO authority parameters at all (no runtime, no session
  store, no manager) -- it reconstructs platform DATA only.
  Re-establishment is the successor's ordinary business through
  the existing authority paths, never a recovery side effect;
- divergence between the reconstructed state and the fresh
  observation is REPORTED (interface changed / appeared / removed
  during downtime), then reconciled by ingesting fresh events
  through the ordinary boundary (the same event-first path with
  its duplicate/contradiction gates);
- stale/corrupt checkpoint, journal/checkpoint mismatch, corrupt
  journal, or invalid fresh observations all fail closed with
  typed errors -- never a silent fallback, never an invented
  PASS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes
import hashlib

from agent.interfaces import InterfaceSource

from mobile.platform import MobilePlatformSource

from .boundary import events_from_sources
from .checkpoint import PlatformCheckpoint
from .errors import PlatformError, PlatformReasonCode
from .journal import AppendOnlyJournal, JournalRecord, SESSION_LOSS_CAUSE
from .model import EventKind, SessionBindingRef
from .state import ReconciledState, apply_record, fold_state, fold_state_from


#: The frozen recovery divergence vocabulary (pure DATA for the
# honest report; never semantics).
DIVERGENCE_CHANGED = "changed-during-downtime"
DIVERGENCE_APPEARED = "appeared-during-downtime"
DIVERGENCE_REMOVED = "removed-during-downtime"


@dataclass(frozen=True)
class Divergence:
    """One honest difference between the reconstructed state and
    the fresh platform observation (DATA only)."""

    kind: str
    platform_ref: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "platform_ref": self.platform_ref,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RecoveryReport:
    """The durable outcome of one recovery run (pure DATA).

    Everything a reviewer needs to verify recovery honesty:
    checkpoint provenance, replay counts, the fresh-observation
    events ingested, the divergences found, and the lost-session
    references recorded.
    """

    checkpoint_id: str
    journal_tail_sequence: int
    journal_records_replayed: int
    fresh_event_ids: Tuple[str, ...]
    divergences: Tuple[Divergence, ...]
    lost_sessions: Tuple[str, ...]
    session_loss_record_ids: Tuple[str, ...]
    recovery_instant: str
    state_digest: str
    journal_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "journal_tail_sequence": self.journal_tail_sequence,
            "journal_records_replayed": self.journal_records_replayed,
            "fresh_event_ids": list(self.fresh_event_ids),
            "divergences": [item.to_dict() for item in self.divergences],
            "lost_sessions": list(self.lost_sessions),
            "session_loss_record_ids": list(self.session_loss_record_ids),
            "recovery_instant": self.recovery_instant,
            "state_digest": self.state_digest,
            "journal_digest": self.journal_digest,
        }

    def recovery_digest(self) -> str:
        """Content digest over the canonical report (identity
        DATA)."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


def load_verified_checkpoint(
    journal: AppendOnlyJournal, payload: bytes
) -> PlatformCheckpoint:
    """Load a checkpoint payload and verify its journal binding.

    Fail-closed families: malformed payload bytes, tampered content
    binding, incompatible schema, a checkpoint positioned beyond
    the journal tail, a prefix-digest mismatch (truncated or
    rewritten journal), and a recorded state that is not the true
    fold of its own prefix (a fabricated or stale checkpoint).
    """
    checkpoint = PlatformCheckpoint.from_bytes(payload)
    position = checkpoint.journal_tail_sequence
    records = list(journal.records())
    if position > len(records):
        raise PlatformError(
            PlatformReasonCode.CHECKPOINT_MISMATCH,
            "checkpoint claims journal position %d but the journal holds "
            "%d records (a checkpoint ahead of its journal -- corrupt or "
            "incompatible durable state, fail closed)"
            % (position, len(records)),
        )
    prefix = journal.prefix_digest(position)
    if prefix != checkpoint.journal_tail_digest:
        raise PlatformError(
            PlatformReasonCode.CHECKPOINT_MISMATCH,
            "checkpoint journal binding mismatch: prefix digest at %d "
            "is %r, checkpoint records %r (truncated, rewritten, or "
            "tampered journal -- fail closed)"
            % (position, prefix[:23], checkpoint.journal_tail_digest[:23]),
        )
    true_state = fold_state(records[:position])
    if not true_state.state_equal(checkpoint.reconciled_state):
        raise PlatformError(
            PlatformReasonCode.CHECKPOINT_MISMATCH,
            "checkpoint state is not the fold of its journal prefix "
            "(fabricated or stale checkpoint state -- fail closed)",
        )
    return checkpoint


def divergences_from_fresh_events(
    reconstructed: ReconciledState,
    fresh_events: Tuple[Any, ...],
) -> Tuple[Divergence, ...]:
    """The honest divergence report, derived from the
    change-detected fresh events.

    The polling fallback emits an event ONLY where the fresh
    observation actually differs from the reconstructed state, so
    the emitted change set IS the divergence set -- reported
    verbatim, never re-inferred from a concurrent re-read (ACR-006
    section 2).
    """
    present = set(reconstructed.present_interface_names())
    out: List[Divergence] = []
    for event in fresh_events:
        if event.kind == EventKind.INTERFACE_OBSERVATION:
            if event.platform_ref in present:
                out.append(
                    Divergence(
                        kind=DIVERGENCE_CHANGED,
                        platform_ref=event.platform_ref,
                        detail="interface observation differs from the "
                        "reconstructed state (platform changed during "
                        "downtime)",
                    )
                )
            else:
                out.append(
                    Divergence(
                        kind=DIVERGENCE_APPEARED,
                        platform_ref=event.platform_ref,
                        detail="interface newly observed by the fresh "
                        "platform observation",
                    )
                )
        elif event.kind == EventKind.INTERFACE_REMOVAL:
            out.append(
                Divergence(
                    kind=DIVERGENCE_REMOVED,
                    platform_ref=event.platform_ref,
                    detail="interface no longer observed by the fresh "
                    "platform observation",
                )
            )
        else:
            if reconstructed.platform_record is None:
                out.append(
                    Divergence(
                        kind=DIVERGENCE_APPEARED,
                        platform_ref=event.platform_ref,
                        detail="platform-state observation available in "
                        "the fresh read",
                    )
                )
            else:
                out.append(
                    Divergence(
                        kind=DIVERGENCE_CHANGED,
                        platform_ref=event.platform_ref,
                        detail="platform state differs from the "
                        "reconstructed observation (platform changed "
                        "during downtime)",
                    )
                )
    return tuple(out)


def perform_recovery(
    *,
    journal: AppendOnlyJournal,
    checkpoint_payload: bytes,
    recovery_instant: str,
    interface_source: Optional[InterfaceSource] = None,
    platform_source: Optional[MobilePlatformSource] = None,
    ingest: Optional[
        Callable[[Any, ReconciledState], ReconciledState]
    ] = None,
) -> Tuple[RecoveryReport, ReconciledState, Optional[PlatformCheckpoint]]:
    """Run the journal-first recovery procedure (deterministic).

    ``ingest`` (the lifecycle's ordinary ingest closure) receives
    each fresh-observation event and the running state and returns
    the folded state; recovery itself never bypasses the boundary
    gates (duplicate / contradiction / persist-then-ack).  When
    ``ingest`` is None the fresh events are only REPORTED (pure
    verification use).

    A missing checkpoint payload (a crash before the first
    checkpoint) is handled honestly: the state is reconstructed
    from the FULL journal, no session bindings exist to lose, and
    the report records the absent checkpoint with id ``''``.

    Returns ``(report, final_state, checkpoint_or_None)``; the
    successor lifecycle continues from the final state and the
    extended journal.
    """
    if not isinstance(recovery_instant, str) or not recovery_instant:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "recovery_instant must be a non-empty instant string",
        )
    records = list(journal.records())

    # 1. load + verify the durable snapshot (or its honest absence)
    checkpoint: Optional[PlatformCheckpoint] = None
    if isinstance(checkpoint_payload, bytes) and checkpoint_payload != b"":
        checkpoint = load_verified_checkpoint(journal, checkpoint_payload)
        position = checkpoint.journal_tail_sequence
        reconstructed = fold_state_from(
            checkpoint.reconciled_state, records[position:]
        )
        checkpoint_id = checkpoint.checkpoint_id
        bindings = checkpoint.session_bindings
    else:
        position = 0
        reconstructed = fold_state(records)
        checkpoint_id = ""
        bindings = ()

    # 2. ONE fresh authoritative platform observation through the
    #    accepted seams (change-detected; a stateful scripted source
    #    is read exactly once)
    fresh_events = events_from_sources(
        state=reconstructed,
        interface_source=interface_source,
        platform_source=platform_source,
        observed_at=recovery_instant,
    )
    divergences = divergences_from_fresh_events(reconstructed, fresh_events)

    # 3. ingest the fresh observations through the ordinary boundary
    state = reconstructed
    fresh_event_ids: List[str] = []
    for event in fresh_events:
        if ingest is not None:
            state = ingest(event, state)
        fresh_event_ids.append(event.event_id)

    # 4. session-loss honesty: the transport state of the killed
    #    process is gone.  EVERY checkpoint binding reference is
    #    reported lost and durably journaled (idempotently keyed on
    #    (session_id, checkpoint_id)); a still-present interface
    #    never resurrects a session, and no session is ever
    #    recreated here.
    lost_sessions: List[str] = []
    loss_record_ids: List[str] = []
    for binding in bindings:
        session_id = binding.session_id
        if session_id in lost_sessions:
            continue
        lost_sessions.append(session_id)
        if not journal.has_session_loss(session_id, checkpoint_id):
            record = journal.append_session_loss(
                session_id=session_id,
                network_path_id=binding.network_path_id,
                interface_name=binding.interface_name,
                cause=SESSION_LOSS_CAUSE,
                checkpoint_id=checkpoint_id,
                instant=recovery_instant,
            )
            loss_record_ids.append(record.record_id)
            state = apply_record(state, record)

    report = RecoveryReport(
        checkpoint_id=checkpoint_id,
        journal_tail_sequence=position,
        journal_records_replayed=len(records) - position,
        fresh_event_ids=tuple(sorted(fresh_event_ids)),
        divergences=divergences,
        lost_sessions=tuple(sorted(lost_sessions)),
        session_loss_record_ids=tuple(sorted(loss_record_ids)),
        recovery_instant=recovery_instant,
        state_digest=state.state_digest(),
        journal_digest=journal.journal_digest(),
    )
    return report, state, checkpoint


__all__ = [
    "DIVERGENCE_APPEARED",
    "DIVERGENCE_CHANGED",
    "DIVERGENCE_REMOVED",
    "Divergence",
    "RecoveryReport",
    "divergences_from_fresh_events",
    "load_verified_checkpoint",
    "perform_recovery",
]
