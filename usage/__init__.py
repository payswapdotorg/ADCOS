"""ADCOS UsageLedger package (WORK-052): the canonical
usage/economic ledger of the commercial connectivity control
plane.

Implements the accepted ACR-009 "Usage integrity" boundary
(DEC-0050) under the active authorization ``WORK-052-CORE-001``
(DEC-0059, baseline reconciled by DEC-0060): billable usage
derived ONLY from authoritative delivered-traffic evidence --

    delivered evidence citation -> usage observation ->
    deterministic reconciliation -> explicit BILLABLE_FINAL ->
    append-only compensating refunds / reversals / disputes

as an append-only, deterministic, idempotent, attributable
ledger that references -- never owns or mutates -- the WORK-051
commercial transaction identities, WORK-012 logical session
ids, WORK-041 NetworkPath ids, and the delivery plane's
evidence records.

Frozen authority boundary (mirrors the W041/W042/W051
discipline):

- The UsageLedger is NOT an identity authority (WORK-004);
  observation/event/fact ids are content-derived fingerprints,
  never NodeIDs and never trust.
- The UsageLedger is NOT a session authority (WORK-012), NOT a
  NetworkPath authority (WORK-041), NOT a routing engine
  (WORK-011), NOT a transport manager (WORK-017), NOT a policy
  authority (WORK-010), NOT a federation authority, and NOT a
  payment provider: payment movement (rails, custody, payout,
  KYC/KYB, jurisdiction) stays behind the external boundary.
- Payment capture NEVER creates usage (payment-observation
  evidence is rejected by the kind table
  ``PAYMENT_NOT_DELIVERY``); reservation/lease state NEVER
  creates usage (the delivery-eligibility gate
  ``TRANSACTION_NOT_DELIVERING`` plus the reserved/attempted
  DATA-only quantity classes); provider observations are DATA,
  never proof of delivery (``PROVIDER_NOT_DELIVERY``).
- The UsageLedger owns exactly one journal: the append-only,
  hash-chained usage history (commands + fact events, atomic
  per-record, persist-then-ack, tamper-evident, replayable).

Determinism: injected WORK-033 clock seam only (duplicates
consume no read; each other submission consumes exactly one);
content-derived ids and digests (WORK-003 canonical JSON);
sorted iteration; integer-only money math (no floats, no
rounding); no randomness, no UUIDs, no wall clock, no network
access, no platform/vendor API, no filesystem writes outside
the injectable store seam.
"""

from __future__ import annotations

from .errors import UsageError, UsageReasonCode
from .evidence import (
    CommercialTransactionSnapshot,
    DeliveryEvidence,
    EvidenceKind,
    QuantityClass,
    UsageEvidenceIndex,
    DELIVERY_ELIGIBLE_STATES,
    RESERVATION_PHASE_STATES,
)
from .model import (
    USAGE_TRANSITIONS,
    CompensationRecord,
    SealedBillableStatement,
    UsageAction,
    UsageCommand,
    UsageEvent,
    UsageObservationRecord,
    UsageTransaction,
    UsageTransactionState,
    command_content,
    derive_command_digest,
    derive_compensation_id,
    derive_event_id,
    derive_observation_id,
    derive_statement_id,
    event_list_digest,
    transition_is_legal,
    transition_target,
    usage_transaction_digest,
)
from .validation import (
    OBSERVATION_EVIDENCE_MEMBERS,
    PAYLOAD_MEMBER_RULES,
    find_duplicate_observation,
    resolve_observation_evidence,
    validate_command_against_transaction,
    validate_delivery_eligibility,
    validate_observation_instant,
    validate_observation_quantity_cap,
    validate_payload_shape,
)
from .journal import (
    GENESIS_RECORD_ID,
    JOURNAL_RECORD_KIND,
    AppendOnlyUsageJournal,
    FileUsageStore,
    MemoryUsageStore,
    UsageJournalRecord,
    UsageStore,
    derive_record_id,
    journal_bytes_for,
    record_list_digest,
)
from .ledger import (
    CommandOutcome,
    CommandStatus,
    UsageLedger,
    apply_record,
    fold_state,
)
from .digest import (
    assemble_digest_stream,
    command_ledger_digest,
    digest_of,
    evidence_index_digest,
    state_digest,
)

__all__ = [
    # error model
    "UsageError",
    "UsageReasonCode",
    # external evidence boundary
    "CommercialTransactionSnapshot",
    "DeliveryEvidence",
    "EvidenceKind",
    "QuantityClass",
    "UsageEvidenceIndex",
    "DELIVERY_ELIGIBLE_STATES",
    "RESERVATION_PHASE_STATES",
    # value model
    "USAGE_TRANSITIONS",
    "CompensationRecord",
    "SealedBillableStatement",
    "UsageAction",
    "UsageCommand",
    "UsageEvent",
    "UsageObservationRecord",
    "UsageTransaction",
    "UsageTransactionState",
    "command_content",
    "derive_command_digest",
    "derive_compensation_id",
    "derive_event_id",
    "derive_observation_id",
    "derive_statement_id",
    "event_list_digest",
    "transition_is_legal",
    "transition_target",
    "usage_transaction_digest",
    # command admission rules
    "OBSERVATION_EVIDENCE_MEMBERS",
    "PAYLOAD_MEMBER_RULES",
    "find_duplicate_observation",
    "resolve_observation_evidence",
    "validate_command_against_transaction",
    "validate_delivery_eligibility",
    "validate_observation_instant",
    "validate_observation_quantity_cap",
    "validate_payload_shape",
    # append-only journal + durable store
    "GENESIS_RECORD_ID",
    "JOURNAL_RECORD_KIND",
    "AppendOnlyUsageJournal",
    "FileUsageStore",
    "MemoryUsageStore",
    "UsageJournalRecord",
    "UsageStore",
    "derive_record_id",
    "journal_bytes_for",
    "record_list_digest",
    # public production surface
    "CommandOutcome",
    "CommandStatus",
    "UsageLedger",
    "apply_record",
    "fold_state",
    # deterministic evidence digests
    "assemble_digest_stream",
    "command_ledger_digest",
    "digest_of",
    "evidence_index_digest",
    "state_digest",
]
