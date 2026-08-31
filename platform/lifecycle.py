"""WORK-042 platform integrator: the public production surface.

:class:`PlatformIntegrator` composes the whole ACR-006 flow over
existing authorities' PUBLIC seams only:

- the platform-event ingestion boundary (``platform.boundary``,
  which itself composes the accepted WORK-033 ``InterfaceSource``
  and WORK-035 ``MobilePlatformSource`` seams);
- the deterministic event/snapshot reconciliation
  (``platform.state``);
- the append-only journal and the injectable durable store
  (``platform.journal``);
- compact checkpoints bound to the journal tail
  (``platform.checkpoint``);
- journal-first recovery (``platform.recovery``).

What it OWNS: exactly the platform-integration journal, its
checkpoints, and the reconciled platform-state representation.
What it NEVER does:

- mint identity, session, route, transport, policy, or federation
  state (there is no authority object here at all -- the
  constructor takes a store and a clock, and recovery takes only
  read-only platform seams);
- mutate another authority's internals;
- treat a platform observation as protocol truth (observations
  become DATA + evidence; decisions stay decisions).

Construction discipline (fail closed): a fresh integrator requires
an EMPTY durable store -- continuing from durable state is only
possible through :meth:`recover`, which reconciles with a fresh
authoritative platform observation and records session loss
honestly.  There is no silent adoption of stale durable state.

Determinism: the injected WORK-033 clock seam is the only time
source (one clock read per checkpoint and one per recovery);
observation instants are host-injected; all ids/digests are
content-derived; iteration is sorted; no randomness, no UUIDs, no
wall clock, no network access.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from agent.clock import AgentClock
from agent.interfaces import InterfaceSource
from agent.model import InterfaceSnapshot

from mobile.model import PlatformSnapshot
from mobile.platform import MobilePlatformSource

from .boundary import (
    events_from_sources,
    interface_event,
    interface_removal_event,
    platform_state_event,
)
from .checkpoint import PlatformCheckpoint, build_checkpoint
from .errors import PlatformError, PlatformReasonCode
from .journal import (
    AppendOnlyJournal,
    JournalRecord,
    JournalRecordKind,
    PlatformStore,
)
from .model import (
    DEFAULT_INTERFACE_SOURCE,
    DEFAULT_PLATFORM_SOURCE,
    EventKind,
    IngestionOutcome,
    IngestionStatus,
    PlatformEvent,
    SessionBindingRef,
)
from .recovery import RecoveryReport, perform_recovery
from .state import ReconciledState, apply_record, fold_state


# ---------------------------------------------------------------------------
# Reconciled-state views over the EXISTING seams (composition, never
# replacement: these implement the frozen WORK-033/W035 seam
# interfaces on top of event-reconstructed state so the accepted
# authorities consume the recovered platform state unchanged).
# ---------------------------------------------------------------------------


class ReconciledInterfaceSource(InterfaceSource):
    """The WORK-033 interface-discovery seam over the reconciled
    state (a LIVE view: each ``discover()`` reads the integrator's
    current reconciled interfaces)."""

    def __init__(self, state_provider: Callable[[], ReconciledState]) -> None:
        if not callable(state_provider):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "state_provider must be callable (the live reconciled "
                "state view)",
            )
        self._state_provider = state_provider

    def discover(self) -> Tuple[InterfaceSnapshot, ...]:
        state = self._state_provider()
        if not isinstance(state, ReconciledState):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "state provider returned a non-ReconciledState value",
            )
        snapshots: List[InterfaceSnapshot] = []
        for record in state.interface_records:
            if record.kind != EventKind.INTERFACE_OBSERVATION:
                continue
            try:
                snapshots.append(
                    InterfaceSnapshot.from_dict(record.payload)
                )
            except Exception as error:  # typed re-wrap (fail closed)
                raise PlatformError(
                    PlatformReasonCode.STATE_INVALID,
                    "reconciled interface payload rejected by the "
                    "accepted model: %s" % type(error).__name__,
                ) from error
        return tuple(
            sorted(snapshots, key=lambda snapshot: snapshot.name)
        )


class ReconciledPlatformSource(MobilePlatformSource):
    """The WORK-035 platform-state seam over the reconciled state
    (a LIVE view of the latest platform-state observation)."""

    def __init__(self, state_provider: Callable[[], ReconciledState]) -> None:
        if not callable(state_provider):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "state_provider must be callable (the live reconciled "
                "state view)",
            )
        self._state_provider = state_provider

    def read(self) -> PlatformSnapshot:
        state = self._state_provider()
        if not isinstance(state, ReconciledState):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "state provider returned a non-ReconciledState value",
            )
        record = state.platform_record
        if record is None:
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "no platform-state observation has been reconciled yet "
                "(fail closed -- the mobile layer requires a genuine "
                "PlatformSnapshot)",
            )
        try:
            return PlatformSnapshot.from_dict(record.payload)
        except Exception as error:  # typed re-wrap (fail closed)
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "reconciled platform-state payload rejected by the "
                "accepted model: %s" % type(error).__name__,
            ) from error


# ---------------------------------------------------------------------------
# The public production surface
# ---------------------------------------------------------------------------


class PlatformIntegrator:
    """The W042 public surface: event boundary + journal +
    checkpoints + journal-first recovery."""

    def __init__(self, *, store: PlatformStore, clock: AgentClock) -> None:
        if not isinstance(store, PlatformStore):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "store must be a PlatformStore (the injectable durable "
                "seam)",
            )
        if not isinstance(clock, AgentClock):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 "
                "seam)",
            )
        # Construction discipline: a fresh integrator requires an
        # EMPTY durable store; continuing from durable state is only
        # possible through recover() (fresh observation + honest
        # session loss).  Never silently adopt stale state.
        if store.journal_bytes() != b"" or store.read_checkpoint() != b"":
            raise PlatformError(
                PlatformReasonCode.RECOVERY_REJECTED,
                "the durable store is not empty; continuing from durable "
                "state requires PlatformIntegrator.recover (journal-first "
                "recovery with a fresh platform observation -- never a "
                "silent adoption of stale state)",
            )
        self._store = store
        self._clock = clock
        self._journal = AppendOnlyJournal(store=store)
        self._state = ReconciledState()
        self._last_checkpoint: Optional[PlatformCheckpoint] = None

    # ------------------------------------------------------------------
    # The event-first ingestion boundary (primary path)
    # ------------------------------------------------------------------

    def ingest_interface_observation(
        self,
        snapshot: InterfaceSnapshot,
        *,
        observed_at: str,
        source: str = DEFAULT_INTERFACE_SOURCE,
    ) -> IngestionOutcome:
        """Ingest one host-pushed interface observation (event-first)."""
        return self._ingest_event(
            interface_event(
                snapshot, observed_at=observed_at, source=source
            )
        )

    def ingest_interface_removal(
        self,
        interface_name: str,
        *,
        observed_at: str,
        source: str = DEFAULT_INTERFACE_SOURCE,
    ) -> IngestionOutcome:
        """Ingest one host-pushed interface-removal notification."""
        return self._ingest_event(
            interface_removal_event(
                interface_name, observed_at=observed_at, source=source
            )
        )

    def ingest_platform_state(
        self,
        snapshot: PlatformSnapshot,
        *,
        observed_at: str,
        source: str = DEFAULT_PLATFORM_SOURCE,
    ) -> IngestionOutcome:
        """Ingest one host-pushed OS platform-state observation."""
        return self._ingest_event(
            platform_state_event(
                snapshot, observed_at=observed_at, source=source
            )
        )

    def ingest_event(self, event: PlatformEvent) -> IngestionOutcome:
        """Ingest one already-built event (redelivery / replay path)."""
        if not isinstance(event, PlatformEvent):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "event must be a PlatformEvent",
            )
        return self._ingest_event(event)

    def ingest_from_sources(
        self,
        *,
        interface_source: Optional[InterfaceSource] = None,
        platform_source: Optional[MobilePlatformSource] = None,
        observed_at: str,
    ) -> Tuple[IngestionOutcome, ...]:
        """The polling FALLBACK (ACR-006 section 1: polling may
        remain available as a fallback, never the normative primary
        mechanism).

        Reads the current observation sets ONCE through the
        accepted seams and ingests the change-detected events (one
        event per actual change; unchanged observations produce
        nothing).
        """
        events = events_from_sources(
            state=self._state,
            interface_source=interface_source,
            platform_source=platform_source,
            observed_at=observed_at,
        )
        return tuple(self._ingest_event(event) for event in events)

    def _ingest_event(self, event: PlatformEvent) -> IngestionOutcome:
        """The ingest pipeline: admission gate -> stale
        determination -> persist-then-ack append -> incremental
        fold."""
        admission = self._journal.check_admissible(event)
        if admission == "duplicate":
            sequence = self._journal.event_sequence(event.event_id)
            return IngestionOutcome(
                status=IngestionStatus.DUPLICATE,
                event_id=event.event_id,
                record_id="",
                sequence=0,
                detail="already journaled at sequence %d (idempotent "
                "no-op)" % sequence,
            )
        stale = self._is_stale(event)
        record = self._journal.append_event(event)  # persist-then-ack
        self._state = apply_record(self._state, record)
        return IngestionOutcome(
            status=(
                IngestionStatus.STALE
                if stale
                else IngestionStatus.APPENDED
            ),
            event_id=event.event_id,
            record_id=record.record_id,
            sequence=record.sequence,
            detail=(
                "older observation for reference %r (deterministically "
                "inert: no state transition)" % event.platform_ref
                if stale
                else "observation journaled and reconciled"
            ),
        )

    def _ingest_for_recovery(
        self, event: PlatformEvent, state: ReconciledState
    ) -> ReconciledState:
        """The ingest closure used by recovery (ordinary gates +
        persist-then-ack + fold)."""
        admission = self._journal.check_admissible(event)
        if admission == "duplicate":
            return state  # the fresh sweep rediscovered a journaled event
        record = self._journal.append_event(event)
        self._state = apply_record(state, record)
        return self._state

    def _is_stale(self, event: PlatformEvent) -> bool:
        """An observation older than the reconciled record for its
        reference is deterministically inert (ACR-006 section 2)."""
        if event.kind == EventKind.PLATFORM_STATE_OBSERVATION:
            current = self._state.platform_record
        else:
            current = self._state.interface_map().get(event.platform_ref)
        if current is None:
            return False
        return event.observed_at < current.observed_at

    # ------------------------------------------------------------------
    # Reconciled state and journal views
    # ------------------------------------------------------------------

    def state(self) -> ReconciledState:
        """The current reconciled state (state REPRESENTATION)."""
        return self._state

    def journal_records(self) -> Tuple[JournalRecord, ...]:
        """The immutable journal record view."""
        return self._journal.records()

    def journal_digest(self) -> str:
        """The deterministic digest over the full journal."""
        return self._journal.journal_digest()

    def tail_sequence(self) -> int:
        """The journal tail position (0 for an empty journal)."""
        return self._journal.tail_sequence()

    def lost_session_refs(self) -> Tuple[str, ...]:
        """Session-id REFERENCES recorded lost in the journal
        (honest evidence DATA)."""
        return self._journal.lost_session_refs()

    def verify_integrity(self) -> None:
        """Independent integrity verification (fail closed).

        Recomputes every record fingerprint, the chain links, the
        contiguous sequence, the duplicate/contradiction indexes,
        and the fold equality (state == fold of all records), plus
        the durable-medium equality (the store's journal bytes are
        the canonical serialization of the in-memory records).
        """
        records = list(self._journal.records())
        previous: Optional[JournalRecord] = None
        seen_events: set = set()
        collisions: dict = {}
        for index, record in enumerate(records, start=1):
            if record.sequence != index:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "sequence gap at position %d" % index,
                )
            if previous is None:
                if record.prev_record_id != "":
                    raise PlatformError(
                        PlatformReasonCode.JOURNAL_CORRUPT,
                        "first record must have an empty prev link",
                    )
            elif record.prev_record_id != previous.record_id:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "chain break at sequence %d" % record.sequence,
                )
            if record.record_kind == JournalRecordKind.PLATFORM_EVENT:
                event = record.event
                if event is None or event.event_id in seen_events:
                    raise PlatformError(
                        PlatformReasonCode.JOURNAL_CORRUPT,
                        "duplicate or eventless platform-event record at "
                        "sequence %d" % record.sequence,
                    )
                seen_events.add(event.event_id)
                key = (event.kind, event.platform_ref, event.observed_at)
                existing = collisions.get(key)
                if existing is not None and existing != event.event_id:
                    raise PlatformError(
                        PlatformReasonCode.JOURNAL_CORRUPT,
                        "contradictory events at sequence %d"
                        % record.sequence,
                    )
                collisions[key] = event.event_id
            previous = record
        folded = fold_state(records)
        if not folded.state_equal(self._state):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "reconciled state is not the fold of the journal "
                "(state drift -- fail closed)",
            )
        # the durable medium IS the journal: the store's bytes are
        # the canonical serialization of the in-memory records
        from .journal import journal_bytes_for

        if self._store.journal_bytes() != journal_bytes_for(records):
            raise PlatformError(
                PlatformReasonCode.JOURNAL_CORRUPT,
                "the durable medium diverges from the in-memory journal "
                "(persist-then-ack violated or store tampered -- fail "
                "closed)",
            )

    # ------------------------------------------------------------------
    # Durable checkpoints (persist-before-suspend)
    # ------------------------------------------------------------------

    def checkpoint(
        self, *, session_bindings: Sequence[SessionBindingRef] = ()
    ) -> PlatformCheckpoint:
        """Cut one compact checkpoint at the CURRENT journal tail and
        persist it through the store (persist-before-suspend, ACR-006
        section 4).

        ``session_bindings`` are REFERENCES the caller's process
        currently holds (e.g. built from the NetworkPathManager's
        public binding facts); they are recorded as DATA so that a
        future process death is reported honestly.  Consumes exactly
        one injected clock read.
        """
        instant = self._clock.now()
        checkpoint = build_checkpoint(
            state=self._state,
            records=list(self._journal.records()),
            session_bindings=tuple(session_bindings),
            produced_at=instant,
        )
        self._store.write_checkpoint(checkpoint.to_bytes())
        self._last_checkpoint = checkpoint
        return checkpoint

    def stored_checkpoint(self) -> Optional[PlatformCheckpoint]:
        """The persisted checkpoint, if one exists (loaded and
        content-verified, fail closed on corruption)."""
        payload = self._store.read_checkpoint()
        if payload == b"":
            return None
        return PlatformCheckpoint.from_bytes(payload)

    @property
    def last_checkpoint(self) -> Optional[PlatformCheckpoint]:
        """The most recent checkpoint cut by THIS instance (None
        until the first :meth:`checkpoint` call)."""
        return self._last_checkpoint

    # ------------------------------------------------------------------
    # Journal-first recovery (the successor-process factory)
    # ------------------------------------------------------------------

    @classmethod
    def recover(
        cls,
        *,
        store: PlatformStore,
        clock: AgentClock,
        interface_source: Optional[InterfaceSource] = None,
        platform_source: Optional[MobilePlatformSource] = None,
    ) -> Tuple["PlatformIntegrator", RecoveryReport]:
        """Recover the successor process from durable state.

        The flow (ACR-006 section 3): load + verify the durable
        journal; load + verify the checkpoint and its journal
        binding; replay the tail deterministically; take ONE fresh
        authoritative platform observation through the accepted
        seams; reconcile (ingest the change-detected events through
        the ordinary boundary); record session loss honestly for
        every checkpoint binding (transport state cannot survive
        process death); return the successor integrator and the
        durable recovery report.

        Deliberately NO authority parameters: recovery cannot touch
        session/routing/identity state by construction.  Consumes
        exactly one injected clock read (the recovery instant).
        """
        if not isinstance(store, PlatformStore):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "store must be a PlatformStore (the injectable durable "
                "seam)",
            )
        if not isinstance(clock, AgentClock):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 "
                "seam)",
            )
        journal = AppendOnlyJournal.load(store)  # fail closed (corrupt/tamper)
        recovery_instant = clock.now()  # the ONE clock read
        payload = store.read_checkpoint()

        # Bypass the empty-store construction rule deliberately: the
        # successor is BUILT from durable state through recovery (the
        # rule exists to prevent silent adoption; recovery is the
        # loud, verified path).
        integrator = cls.__new__(cls)
        integrator._store = store
        integrator._clock = clock
        integrator._journal = journal
        integrator._state = ReconciledState()
        integrator._last_checkpoint = None

        report, state, checkpoint = perform_recovery(
            journal=journal,
            checkpoint_payload=payload,
            recovery_instant=recovery_instant,
            interface_source=interface_source,
            platform_source=platform_source,
            ingest=integrator._ingest_for_recovery,
        )
        integrator._state = state
        integrator._last_checkpoint = checkpoint
        return integrator, report

    # ------------------------------------------------------------------
    # Composition seams over the reconciled state
    # ------------------------------------------------------------------

    def reconciled_interface_source(self) -> InterfaceSource:
        """The WORK-033 interface-discovery seam backed by the
        reconciled platform state (composition: the accepted
        authorities consume event-reconstructed state
        unchanged)."""
        return ReconciledInterfaceSource(lambda: self._state)

    def reconciled_platform_source(self) -> MobilePlatformSource:
        """The WORK-035 platform-state seam backed by the reconciled
        platform state."""
        return ReconciledPlatformSource(lambda: self._state)

    def content_digest(self) -> str:
        """Deterministic digest over the integrator's durable
        content (journal + reconciled state)."""
        from protocol.canonicalization import canonical_json_bytes
        import hashlib

        payload = {
            "journal_digest": self._journal.journal_digest(),
            "state": self._state.to_dict(),
        }
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(payload)
        ).hexdigest()


__all__ = [
    "PlatformIntegrator",
    "ReconciledInterfaceSource",
    "ReconciledPlatformSource",
]
