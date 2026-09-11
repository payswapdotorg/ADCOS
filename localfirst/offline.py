"""ADCOS local-first offline composition (M016 — Local-First and
Offline Operation).

The M015 composition substrate: the local-first offline transitions
DRIVE the accepted ``resilience/`` runtime (``RuntimeStore``, the
lifecycle states, the reconnect discipline) BY REFERENCE — the runtime
session is never duplicated, never forked:

- :func:`attach_runtime_session` — create and activate the accepted
  M015 runtime session whose REALIZATION is the base authority view
  (the WORK-012 member shape: ``route_decision_id`` = the snapshot id,
  ``path_id`` = the state digest — the local-first node's runtime
  realizes the authority snapshot it operates on).
- :func:`open_partition` — the journaled offline/degraded-mode ENTRY
  (the M015 degraded-mode discipline extended across the offline
  boundary): the accepted ``RuntimeStore.enter_degraded`` is driven
  with an accepted LOCK-106 evidence kind and the episode id as the
  decision-kinded evidence reference, and the offline journal opens
  with its ``partition-entered`` record carrying the M015 degraded-
  entry EVENT id — the evidence-visible composition link.
- :func:`local_admit` — one partition-tolerant local admission onto
  the open episode's journal (the admission gates + the IDEMPOTENT
  append: a retried admission derives the same position-independent
  content identity and never double-applies).
- :func:`close_partition` — the explicit reconnect AND
  resynchronization (fail-closed ORDER: the pure deterministic
  convergence is computed and gated FIRST — on a typed rejection the
  runtime stays DEGRADED and the partition stays open, honest; only
  then the accepted M015 reconnect pair is driven —
  ``initiate_reconnect`` naming the OLD authority-view references
  verbatim (the episode's base view) and the CANDIDATE fresh view,
  ``complete_reconnect`` landing ACTIVE on the fresh view — and the
  offline journal closes with its ``partition-exited`` record carrying
  the resync result id and the M015 reconnect EVIDENCE id).
- :class:`CloseResult` — the typed close envelope (the resync result,
  the runtime session after the reconnect, the WORK-012 reconnect
  evidence naming BOTH the old and the new authority views, and the
  folded local state after the exit).

The offline transitions never write contract state and never carry
constraint material as authority: the claimed constraint sets riding
the journal records are DATA re-validated by the consumed M008 gates
(LOCK-108 across the offline boundary — see
:mod:`localfirst.admission` / :mod:`localfirst.resync`).

Determinism (LOCK-111/LOCK-119): same inputs -> the byte-identical
transitions; injected instants only; no wall clock, no randomness, no
network, no secrets.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from contracts import (
    ConnectivityContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
)

from replan import DEFAULT_TIE_BREAK

from resilience import (
    RuntimeReconnect,
    RuntimeSession,
    RuntimeStore,
)

from .admission import admit_operation
from .errors import LocalFirstError, LocalFirstReason
from .journal import OfflineJournal
from .model import (
    AuthoritySnapshot,
    LOCALFRESH_ISSUER,
    LocalState,
    OfflineOperation,
    RESYNC_DRIVEN_ISSUER,
    ResyncResult,
    _wrap_consumed_error,
    derive_episode_id,
)
from .resync import resynchronize

__all__ = [
    "attach_runtime_session",
    "sync_authority_view",
    "open_partition",
    "local_admit",
    "close_partition",
    "CloseResult",
]


def attach_runtime_session(
    store: RuntimeStore,
    contract: ConnectivityContract,
    base_snapshot: AuthoritySnapshot,
    *,
    created_at: str,
    activated_at: str,
    provenance: Optional[Provenance] = None,
) -> RuntimeSession:
    """Create and activate the accepted M015 runtime session whose
    realization is the base authority view (the WORK-012 member shape:
    the snapshot id and the state digest — the local-first node's
    runtime realizes the authority snapshot it operates on)."""
    if not isinstance(store, RuntimeStore):
        raise LocalFirstError(
            LocalFirstReason.COMPOSITION,
            "attach_runtime_session requires a resilience RuntimeStore (got %s) "
            "— the accepted M015 runtime is the composition substrate, "
            "consumed BY REFERENCE" % type(store).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "attach_runtime_session requires a contracts.ConnectivityContract "
            "(got %s)" % type(contract).__name__,
        )
    if not isinstance(base_snapshot, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "attach_runtime_session requires a localfirst AuthoritySnapshot "
            "(got %s)" % type(base_snapshot).__name__,
        )
    if base_snapshot.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the base authority view is attributable to contract %s, not %s — "
            "the runtime session rides exactly its owning contract"
            % (base_snapshot.contract_id[:23], contract.contract_id[:23]),
        )
    if provenance is None:
        provenance = Provenance(
            issuer=LOCALFRESH_ISSUER,
            decision_refs=(contract.contract_id, base_snapshot.snapshot_id),
        )
    elif not isinstance(provenance, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    snapshot_id, state_digest = base_snapshot.realization_refs()
    with _wrap_consumed_error("the M015 runtime-session attachment"):
        created = store.create(
            contract_id=contract.contract_id,
            created_at=created_at,
            provenance=provenance,
        )
        store.activate(
            created.runtime_id,
            route_decision_id=snapshot_id,
            path_id=state_digest,
            recorded_at=activated_at,
            provenance=provenance,
        )
    return store.session(created.runtime_id)


def sync_authority_view(
    store: RuntimeStore,
    runtime_id: object,
    contract: ConnectivityContract,
    view: AuthoritySnapshot,
    *,
    recorded_at: str,
    provenance: Optional[Provenance] = None,
) -> Optional[RuntimeReconnect]:
    """Sync the runtime session onto an authority view WHILE CONNECTED
    (the explicit reconnect pair of the accepted M015 runtime — the
    WORK-012 discipline: the view change is ALWAYS an explicit
    recorded reconnect naming the OLD and the NEW references, never a
    silent replacement).

    IDEMPOTENT: when the session already realizes exactly the view,
    nothing is driven and None is returned (no fabricated events —
    the accepted runtime never journals a no-op reconnect)."""
    if not isinstance(store, RuntimeStore):
        raise LocalFirstError(
            LocalFirstReason.COMPOSITION,
            "sync_authority_view requires a resilience RuntimeStore (got %s) — "
            "the accepted M015 runtime is the composition substrate, consumed "
            "BY REFERENCE" % type(store).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "sync_authority_view requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(view, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "sync_authority_view requires a localfirst AuthoritySnapshot (got %s)"
            % type(view).__name__,
        )
    session = store.session(runtime_id)
    if session.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "runtime session %s rides contract %s, not %s"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    if view.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the authority view is attributable to contract %s, not %s"
            % (view.contract_id[:23], contract.contract_id[:23]),
        )
    if session.realization_refs() == view.realization_refs():
        return None  # idempotent: already synced, no fabricated events
    if provenance is None:
        provenance = Provenance(
            issuer=LOCALFRESH_ISSUER,
            decision_refs=(session.runtime_id, view.snapshot_id),
        )
    elif not isinstance(provenance, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    snapshot_id, state_digest = view.realization_refs()
    with _wrap_consumed_error("the M015 reconnect pair"):
        store.initiate_reconnect(
            session.runtime_id,
            candidate_route_decision_id=snapshot_id,
            candidate_path_id=state_digest,
            recorded_at=recorded_at,
            provenance=provenance,
        )
        store.complete_reconnect(
            session.runtime_id,
            recorded_at=recorded_at,
            provenance=provenance,
        )
    evidence = store.reconnect_evidence(session.runtime_id)
    return evidence[-1] if evidence else None


def open_partition(
    store: RuntimeStore,
    runtime_id: object,
    contract: ConnectivityContract,
    base_snapshot: AuthoritySnapshot,
    *,
    recorded_at: str,
    provenance: Optional[Provenance] = None,
) -> Tuple[OfflineJournal, OfflineOperation]:
    """Open one partition episode (the journaled offline/degraded-mode
    ENTRY — the M015 degraded-mode discipline extended across the
    offline boundary).

    Fail-closed gates: the runtime session must ride exactly the
    owning contract and must currently realize EXACTLY the base
    authority view (the WORK-012 discipline — the episode operates on
    the view the session holds).  The accepted
    ``RuntimeStore.enter_degraded`` is then driven with the accepted
    LOCK-106 ``observation`` evidence kind and the episode id as the
    decision-kinded evidence reference (never a silent downgrade), and
    the offline journal opens with its ``partition-entered`` record
    carrying the M015 degraded-entry EVENT id (the evidence-visible
    composition link)."""
    if not isinstance(store, RuntimeStore):
        raise LocalFirstError(
            LocalFirstReason.COMPOSITION,
            "open_partition requires a resilience RuntimeStore (got %s) — the "
            "accepted M015 runtime is the composition substrate, consumed BY "
            "REFERENCE" % type(store).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "open_partition requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(base_snapshot, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "open_partition requires a localfirst AuthoritySnapshot (got %s)"
            % type(base_snapshot).__name__,
        )
    session = store.session(runtime_id)
    if session.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "runtime session %s rides contract %s, not %s — a partition "
            "episode opens on exactly the owning contract"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    if base_snapshot.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the base authority view is attributable to contract %s, not %s"
            % (base_snapshot.contract_id[:23], contract.contract_id[:23]),
        )
    if session.realization_refs() != base_snapshot.realization_refs():
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the runtime session realizes %s/%s, not the base authority view "
            "%s/%s — a partition episode operates on exactly the view the "
            "session holds (the WORK-012 discipline)"
            % (
                session.route_decision_id[:23],
                session.path_id[:23],
                base_snapshot.snapshot_id[:23],
                base_snapshot.state_digest[:23],
            ),
        )
    if provenance is None:
        provenance = Provenance(
            issuer=LOCALFRESH_ISSUER,
            decision_refs=(session.runtime_id, base_snapshot.snapshot_id),
        )
    elif not isinstance(provenance, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    episode_id = derive_episode_id(
        contract.contract_id, base_snapshot.snapshot_id, recorded_at, provenance
    )

    # the M015 degraded-mode entry, driven BY REFERENCE (the accepted
    # store validates the ACTIVE -> DEGRADED transition; the evidence
    # kind is drawn from the accepted LOCK-106 vocabulary; the episode
    # id rides as the decision-kinded evidence reference).  A consumed
    # typed rejection surfaces as this surface's own typed error with
    # its deterministic text preserved (exception isolation).
    with _wrap_consumed_error("the M015 degraded entry"):
        store.enter_degraded(
            session.runtime_id,
            evidence_kind="observation",
            evidence_refs=(
                OpaqueReference(
                    ref_kind="decision",
                    value=episode_id,
                    provenance=Provenance(
                        issuer=LOCALFRESH_ISSUER,
                        decision_refs=(session.runtime_id, contract.contract_id),
                    ),
                ),
            ),
            recorded_at=recorded_at,
            provenance=provenance,
        )
    # the evidence-visible composition link: the journaled offline
    # entry names the M015 degraded-entry EVENT id
    degraded_event = store.events(session.runtime_id)[-1]
    if degraded_event.kind != "degraded-entered":
        raise LocalFirstError(
            LocalFirstReason.COMPOSITION,
            "the accepted M015 runtime did not journal the degraded entry (the "
            "offline entry requires its evidence link)",
        )
    journal, record = OfflineJournal.open_episode(
        contract_id=contract.contract_id,
        base_snapshot_id=base_snapshot.snapshot_id,
        base_state_digest=base_snapshot.state_digest,
        runtime_event_id=degraded_event.event_id,
        recorded_at=recorded_at,
        provenance=provenance,
    )
    if record.episode_id != episode_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the journaled episode identity does not match the evidenced one "
            "(tamper evidence)",
        )
    return journal, record


def local_admit(
    journal: OfflineJournal,
    contract: ConnectivityContract,
    snapshot: AuthoritySnapshot,
    *,
    subject: OpaqueReference,
    claimed_constraints: Sequence[HardConstraint],
    decided_at: str,
    provenance: Optional[Provenance] = None,
) -> OfflineOperation:
    """Decide and journal ONE partition-tolerant local admission onto
    the open episode's journal (the admission gates + the IDEMPOTENT
    append: a retried admission derives the same position-independent
    content identity and never double-applies).

    The authority snapshot the admission is decided against must be
    the episode's base view (a local admission rides exactly the view
    the partitioned node operates on)."""
    if not isinstance(journal, OfflineJournal):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "local_admit requires a localfirst OfflineJournal (got %s)"
            % type(journal).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "local_admit requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(snapshot, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "local_admit requires a localfirst AuthoritySnapshot (got %s)"
            % type(snapshot).__name__,
        )
    state = journal.state()
    if state.state != "OPEN":
        raise LocalFirstError(
            LocalFirstReason.EPISODE_CLOSED,
            "the partition episode %s is CLOSED; closed episodes never accept "
            "operations (a new partition opens a new episode)"
            % state.episode_id[:23],
        )
    if snapshot.snapshot_id != state.base_snapshot_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the authority snapshot %s is not the episode's base view %s — a "
            "local admission is decided against exactly the view the "
            "partitioned node operates on"
            % (snapshot.snapshot_id[:23], state.base_snapshot_id[:23]),
        )
    record = admit_operation(
        contract,
        snapshot,
        episode_id=state.episode_id,
        sequence=state.sequence + 1,
        subject=subject,
        claimed_constraints=claimed_constraints,
        decided_at=decided_at,
        provenance=provenance,
    )
    return journal.append(record)


class CloseResult:
    """The typed close envelope: the resynchronization result, the
    runtime session AFTER the explicit reconnect, the WORK-012
    reconnect evidence naming BOTH the old and the new authority
    views, and the folded local state after the journaled exit."""

    __slots__ = ("resync", "session", "reconnect", "state")

    def __init__(
        self,
        resync: ResyncResult,
        session: RuntimeSession,
        reconnect: RuntimeReconnect,
        state: LocalState,
    ) -> None:
        self.resync = resync
        self.session = session
        self.reconnect = reconnect
        self.state = state

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "CloseResult(episode=%s, divergences=%d, applied=%d)" % (
            self.resync.episode_id[:23],
            len(self.resync.divergences),
            len(self.resync.applied_operations),
        )


def close_partition(
    store: RuntimeStore,
    runtime_id: object,
    contract: ConnectivityContract,
    journal: OfflineJournal,
    fresh: AuthoritySnapshot,
    *,
    resolution_rule: Sequence[str] = DEFAULT_TIE_BREAK,
    recorded_at: str,
    provenance: Optional[Provenance] = None,
) -> CloseResult:
    """Close one partition episode: the explicit reconnect AND
    resynchronization (fail-closed ORDER — the pure convergence is
    computed and gated FIRST; on a typed rejection the runtime stays
    DEGRADED and the partition stays open, honest).

    1. :func:`localfirst.resync.resynchronize` — the pure
       deterministic convergence (divergence detection, the DECLARED
       RECORDED resolution, the per-operation LOCK-108 re-verification
       against the LIVE contract; fail-closed typed rejections leave
       every journal byte-identical and the runtime untouched).
    2. The accepted M015 reconnect pair, driven BY REFERENCE:
       ``initiate_reconnect`` naming the OLD authority-view references
       verbatim (the episode's base view — the WORK-012 discipline,
       enforced mechanically by the accepted fold) and the CANDIDATE
       fresh view; ``complete_reconnect`` landing ACTIVE on the fresh
       view, the evidence naming BOTH sides.
    3. The offline journal's ``partition-exited`` record — the
       journaled offline-mode EXIT, carrying the fresh view, the resync
       result id and the M015 reconnect evidence id (the
       evidence-visible composition links)."""
    if not isinstance(store, RuntimeStore):
        raise LocalFirstError(
            LocalFirstReason.COMPOSITION,
            "close_partition requires a resilience RuntimeStore (got %s) — the "
            "accepted M015 runtime is the composition substrate, consumed BY "
            "REFERENCE" % type(store).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "close_partition requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(journal, OfflineJournal):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "close_partition requires a localfirst OfflineJournal (got %s)"
            % type(journal).__name__,
        )
    if not isinstance(fresh, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "close_partition requires a localfirst AuthoritySnapshot (got %s)"
            % type(fresh).__name__,
        )

    # 1. the pure convergence FIRST (fail-closed: a typed rejection
    #    leaves the runtime DEGRADED and the partition open)
    result = resynchronize(
        contract,
        journal,
        fresh,
        resolution_rule=resolution_rule,
        recorded_at=recorded_at,
    )

    # 2. the accepted M015 reconnect pair (the explicit reconnect
    #    naming the OLD view verbatim and the CANDIDATE fresh view)
    session = store.session(runtime_id)
    if session.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "runtime session %s rides contract %s, not %s"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    local_state = journal.state()
    if local_state.base_snapshot_id != session.route_decision_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the runtime session realizes %s, not the episode's base view %s — "
            "the reconnect must name the references being left verbatim (the "
            "WORK-012 discipline)"
            % (session.route_decision_id[:23], local_state.base_snapshot_id[:23]),
        )
    if provenance is None:
        provenance = Provenance(
            issuer=RESYNC_DRIVEN_ISSUER,
            decision_refs=(local_state.episode_id, fresh.snapshot_id),
        )
    elif not isinstance(provenance, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    fresh_snapshot_id, fresh_state_digest = fresh.realization_refs()
    with _wrap_consumed_error("the M015 reconnect pair"):
        store.initiate_reconnect(
            session.runtime_id,
            candidate_route_decision_id=fresh_snapshot_id,
            candidate_path_id=fresh_state_digest,
            recorded_at=recorded_at,
            provenance=provenance,
        )
        after = store.complete_reconnect(
            session.runtime_id,
            recorded_at=recorded_at,
            provenance=provenance,
        )
    evidence = store.reconnect_evidence(session.runtime_id)
    reconnect = evidence[-1] if evidence else None
    if reconnect is None:
        raise LocalFirstError(
            LocalFirstReason.COMPOSITION,
            "the accepted M015 runtime did not journal the reconnect evidence "
            "(the offline exit requires its evidence link)",
        )

    # 3. the journaled offline-mode EXIT (the evidence-visible links:
    #    the resync result id and the M015 reconnect evidence id)
    journal.exit(
        fresh_snapshot_id=fresh_snapshot_id,
        fresh_state_digest=fresh_state_digest,
        resync_id=result.resync_id,
        reconnect_id=reconnect.reconnect_id,
        recorded_at=recorded_at,
        provenance=provenance,
    )
    return CloseResult(
        resync=result,
        session=after,
        reconnect=reconnect,
        state=journal.state(),
    )
