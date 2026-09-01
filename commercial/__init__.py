"""ADCOS CommercialCore package (WORK-051): the canonical
commercial connectivity control-plane core.

Implements the accepted ACR-009 boundary (DEC-0050) under the
active authorization ``WORK-051-CORE-001`` (DEC-0058): the
canonical commercial state lifecycle

    CONNECTIVITY_INTENT -> OFFER_SELECTED -> RESERVATION_HELD ->
    SESSION_AUTHORIZED -> PATH_ACTIVE -> DELIVERY_STARTED ->
    USAGE_ACCRUING -> DELIVERY_COMPLETED -> BILLABLE_FINAL ->
    SETTLEMENT_PENDING -> SETTLED

with the four compensating families (cancellation, expiry, path
failure, non-delivery), as an append-only, deterministic,
idempotent, attributable state machine that references -- never
owns or mutates -- logical session ids (WORK-012), NetworkPath
ids (WORK-041), delivery evidence, usage references, settlement
confirmations, and payment observations (external DATA).

Frozen authority boundary (mirrors the W041/W042 discipline):

- CommercialCore is NOT an identity authority (WORK-004);
  transaction/event/reference ids are content-derived
  fingerprints, never NodeIDs and never trust.
- CommercialCore is NOT a session authority (WORK-012); it cites
  logical session ids resolved against an injected
  ReferenceIndex built from the session authority's PUBLIC
  surface.
- CommercialCore is NOT a NetworkPath authority (WORK-041); it
  cites NetworkPath ids the same way.
- CommercialCore is NOT a routing engine (WORK-011), NOT a
  transport manager (WORK-017), NOT a policy authority
  (WORK-010), NOT a federation authority, and NOT a payment
  provider: payment movement (rails, custody, payout, KYC/KYB,
  jurisdiction) stays behind the external boundary; payment
  observations are recorded DATA and never imply delivery or
  settlement.
- CommercialCore owns exactly one journal: the append-only,
  hash-chained commercial history (commands + events, atomic
  per-record, persist-then-ack, tamper-evident, replayable).

Determinism: injected WORK-033 clock seam only (duplicates
consume no read; each other submission consumes exactly one);
content-derived ids and digests (WORK-003 canonical JSON);
sorted iteration; no randomness, no UUIDs, no wall clock, no
network access, no platform/vendor API, no filesystem writes
outside the injectable store seam.
"""

from __future__ import annotations

from .errors import CommercialError, CommercialReasonCode
from .references import (
    Reference,
    ReferenceFamily,
    ReferenceIndex,
    reference_family_counts,
    resolve_references,
)
from .model import (
    ACTION_REQUIRED_STATE,
    ACTION_TARGET_STATE,
    CommercialAction,
    CommercialCommand,
    CommercialEvent,
    CommercialState,
    CommercialTransaction,
    LIFECYCLE_TRANSITIONS,
    command_content,
    derive_command_digest,
    derive_event_id,
    derive_transaction_id,
    event_list_digest,
    transaction_digest,
    transition_is_legal,
)
from .validation import (
    ACTION_FAMILY_RULES,
    validate_cancel_state,
    validate_command_against_transaction,
    validate_expire_due,
    validate_family_rules,
    validate_non_delivery_state,
    validate_path_failure_state,
    validate_payload_shape,
    validate_reservation_deadline,
    validate_settlement_integrity,
)
from .journal import (
    GENESIS_RECORD_ID,
    JOURNAL_RECORD_KIND,
    AppendOnlyCommercialJournal,
    CommercialStore,
    FileCommercialStore,
    JournalRecord,
    MemoryCommercialStore,
    derive_record_id,
    journal_bytes_for,
    record_list_digest,
)
from .lifecycle import (
    CommandOutcome,
    CommandStatus,
    CommercialCore,
    apply_record,
    fold_state,
)
from .digest import (
    assemble_digest_stream,
    command_ledger_digest,
    digest_of,
    reference_index_digest,
    state_digest,
)

__all__ = [
    # error model
    "CommercialError",
    "CommercialReasonCode",
    # external reference boundary
    "Reference",
    "ReferenceFamily",
    "ReferenceIndex",
    "reference_family_counts",
    "resolve_references",
    # value model
    "ACTION_REQUIRED_STATE",
    "ACTION_TARGET_STATE",
    "CommercialAction",
    "CommercialCommand",
    "CommercialEvent",
    "CommercialState",
    "CommercialTransaction",
    "LIFECYCLE_TRANSITIONS",
    "command_content",
    "derive_command_digest",
    "derive_event_id",
    "derive_transaction_id",
    "event_list_digest",
    "transaction_digest",
    "transition_is_legal",
    # command admission rules
    "ACTION_FAMILY_RULES",
    "validate_cancel_state",
    "validate_command_against_transaction",
    "validate_expire_due",
    "validate_family_rules",
    "validate_non_delivery_state",
    "validate_path_failure_state",
    "validate_payload_shape",
    "validate_reservation_deadline",
    "validate_settlement_integrity",
    # append-only journal + durable store
    "GENESIS_RECORD_ID",
    "JOURNAL_RECORD_KIND",
    "AppendOnlyCommercialJournal",
    "CommercialStore",
    "FileCommercialStore",
    "JournalRecord",
    "MemoryCommercialStore",
    "derive_record_id",
    "journal_bytes_for",
    "record_list_digest",
    # public production surface
    "CommandOutcome",
    "CommandStatus",
    "CommercialCore",
    "apply_record",
    "fold_state",
    # deterministic evidence digests
    "assemble_digest_stream",
    "command_ledger_digest",
    "digest_of",
    "reference_index_digest",
    "state_digest",
]
