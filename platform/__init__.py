"""ADCOS platform-integration package (WORK-042): event-driven
platform integration and journal-first recovery.

Implements the accepted ACR-006 model (DEC-0048) under the active
authorization ``WORK-042-CORE-001`` (DEC-0055): a platform-event
ingestion boundary carrying authoritative observations, deterministic
event/snapshot reconciliation (events are change notifications;
snapshots remain state representation), a secret-free append-only
journal with content-derived ids and a tamper-evident hash chain,
compact journal-bound checkpoints, and durable restart/suspension
recovery that reconciles reconstructed state with a fresh
authoritative platform observation and records session loss
honestly.

Frozen authority boundary (mirrors the WORK-041 discipline):

- platform integration is NOT an identity authority (WORK-004
  owns identity); no id minted here is a NodeID or trust;
- it is NOT a session authority (WORK-012 owns logical session
  lifecycle): recovery records session-loss REFERENCES and never
  recreates, resurrects, or mutates a session; re-establishment
  is the successor's ordinary business through the existing
  authority paths;
- it is NOT a routing engine (WORK-011), NOT a transport manager
  (WORK-017), NOT an adapter authority (WORK-016), and NOT a
  policy authority (WORK-010);
- it is NOT a second platform/discovery authority: the boundary
  composes the accepted WORK-033 ``InterfaceSource`` and WORK-035
  ``MobilePlatformSource`` seams, and the reconciled-state views
  implement those same frozen seam interfaces so existing
  authorities consume event-reconstructed state unchanged;
- it owns exactly one journal: the platform-integration event
  journal (observations + honest recovery outcomes), with
  deterministic, replay-safe, independently verifiable evidence.

Determinism: injected WORK-033 clock seam only (one read per
checkpoint, one per recovery); host-injected observation instants;
content-derived ids and digests (WORK-003 canonical JSON); sorted
iteration; no randomness, no UUIDs, no wall clock, no network
access, no platform/vendor API (the stdlib ``platform`` module is
never imported; this package deliberately owns the repository-local
``platform`` namespace).
"""

from __future__ import annotations

from .errors import PlatformError, PlatformReasonCode
from .model import (
    DEFAULT_INTERFACE_SOURCE,
    DEFAULT_PLATFORM_SOURCE,
    PLATFORM_STATE_REF,
    EventKind,
    IngestionOutcome,
    IngestionStatus,
    PlatformEvent,
    SessionBindingRef,
    derive_platform_event_id,
    event_list_digest,
    platform_event_content,
)
from .boundary import (
    event_from_redelivery,
    events_from_sources,
    interface_event,
    interface_removal_event,
    platform_state_event,
)
from .state import (
    ObservationRecord,
    ReconciledState,
    apply_record,
    fold_state,
    fold_state_from,
)
from .journal import (
    SESSION_LOSS_CAUSE,
    AppendOnlyJournal,
    FilePlatformStore,
    JournalRecord,
    JournalRecordKind,
    MemoryPlatformStore,
    PlatformStore,
    derive_record_id,
    journal_bytes_for,
    record_list_digest,
)
from .checkpoint import (
    CHECKPOINT_SCHEMA,
    PlatformCheckpoint,
    build_checkpoint,
    derive_checkpoint_id,
)
from .recovery import (
    DIVERGENCE_APPEARED,
    DIVERGENCE_CHANGED,
    DIVERGENCE_REMOVED,
    Divergence,
    RecoveryReport,
    divergences_from_fresh_events,
    load_verified_checkpoint,
    perform_recovery,
)
from .lifecycle import (
    PlatformIntegrator,
    ReconciledInterfaceSource,
    ReconciledPlatformSource,
)
from .evidence import (
    PLATFORM_EVIDENCE_STATUS,
    RecoveryEvidenceRecord,
    assemble_recovery_evidence,
    evidence_digest,
    verify_recovery_evidence,
)
from .integration import (
    path_supports_state,
    session_bindings_from_manager,
)

__all__ = [
    # error model
    "PlatformError",
    "PlatformReasonCode",
    # value model
    "DEFAULT_INTERFACE_SOURCE",
    "DEFAULT_PLATFORM_SOURCE",
    "PLATFORM_STATE_REF",
    "EventKind",
    "IngestionOutcome",
    "IngestionStatus",
    "PlatformEvent",
    "SessionBindingRef",
    "derive_platform_event_id",
    "event_list_digest",
    "platform_event_content",
    # ingestion boundary
    "event_from_redelivery",
    "events_from_sources",
    "interface_event",
    "interface_removal_event",
    "platform_state_event",
    # deterministic reconciliation
    "ObservationRecord",
    "ReconciledState",
    "apply_record",
    "fold_state",
    "fold_state_from",
    # append-only journal + durable store
    "SESSION_LOSS_CAUSE",
    "AppendOnlyJournal",
    "FilePlatformStore",
    "JournalRecord",
    "JournalRecordKind",
    "MemoryPlatformStore",
    "PlatformStore",
    "derive_record_id",
    "journal_bytes_for",
    "record_list_digest",
    # checkpoints
    "CHECKPOINT_SCHEMA",
    "PlatformCheckpoint",
    "build_checkpoint",
    "derive_checkpoint_id",
    # recovery
    "DIVERGENCE_APPEARED",
    "DIVERGENCE_CHANGED",
    "DIVERGENCE_REMOVED",
    "Divergence",
    "RecoveryReport",
    "divergences_from_fresh_events",
    "load_verified_checkpoint",
    "perform_recovery",
    # public production surface
    "PlatformIntegrator",
    "ReconciledInterfaceSource",
    "ReconciledPlatformSource",
    # evidence chain
    "PLATFORM_EVIDENCE_STATUS",
    "RecoveryEvidenceRecord",
    "assemble_recovery_evidence",
    "evidence_digest",
    "verify_recovery_evidence",
    # authority composition helpers
    "path_supports_state",
    "session_bindings_from_manager",
]
