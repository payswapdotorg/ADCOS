"""ADCOS EconomicAllocation package (WORK-053): the canonical
economic-allocation layer of the commercial connectivity
control plane.

Implements the accepted ACR-009 "Economic allocation" boundary
under the active authorization ``WORK-053-CORE-001``
(DEC-0061, baseline ``bcaf0d0``): billable-final usage facts
converted into immutable developer/provider/ADCOS allocation
records under versioned economic policy --

    billable-final usage citation (W052 public snapshot)
        + immutable policy version (terms-derived identity)
        -> ALLOCATE (the exact three-way split: conservation is
           mechanical)
        -> external payment references (DATA only) ->
        ACKNOWLEDGE_SETTLEMENT (exactly once)
        -> append-only compensating allocation events (refund /
           reversal / chargeback / payout-failure / dispute)

as an append-only, deterministic, idempotent, attributable
ledger that references -- never owns or mutates -- the WORK-052
usage ledger identities, the WORK-051 commercial citations, and
the external payment/settlement planes.

Frozen authority boundary (mirrors the W041/W042/W051/W052
discipline):

- The EconomicAllocation layer is NOT an identity authority
  (WORK-004); policy/allocation/fact ids are content-derived
  fingerprints, never NodeIDs and never trust.
- It is NOT a session authority (WORK-012), NOT a NetworkPath
  authority (WORK-041), NOT a routing engine (WORK-011), NOT a
  transport manager (WORK-017), NOT a policy authority
  (WORK-010), NOT a federation authority, NOT a usage/commercial
  authority (W052/W051 -- those are consumed as injected public
  snapshots only), and NOT a payment provider: payment movement
  (rails, custody, payout execution, KYC/KYB, jurisdiction)
  stays behind the external boundary; external references are
  identity citations only and ADCOS does not custody, mint, or
  move regulated funds here.
- Payment success NEVER creates allocation (payment references
  fail the usage kind table ``PAYMENT_NOT_USAGE``; settlement
  references fail ``SETTLEMENT_NOT_USAGE``); reservation/offer
  state NEVER creates allocation (allocation consumes ONLY
  BILLABLE_FINAL usage facts -- ``USAGE_NOT_FINAL``); provider
  callbacks NEVER transition or reprice allocation (they are
  idempotent/append-only DATA records).
- No payment-provider-specific concepts exist in the canonical
  allocation model (provider-neutral, technology-neutral; the
  battery audits vendor tokens).
- The EconomicAllocation layer owns exactly one journal: the
  append-only, hash-chained allocation history (commands + fact
  events, atomic per-record, persist-then-ack,
  tamper-evident, replayable).

Determinism: injected WORK-033 clock seam only (duplicates
consume no read; each other submission consumes exactly one);
content-derived ids and digests (WORK-003 canonical JSON);
sorted iteration; integer-only money math with explicit
declared rounding (no floats, no hidden rounding); no
randomness, no UUIDs, no wall clock, no network access, no
platform/vendor API, no filesystem writes outside the injectable
store seam.
"""

from __future__ import annotations

from .errors import AllocationError, AllocationReasonCode
from .evidence import (
    AllocationEvidenceIndex,
    BillableUsageSnapshot,
    ExternalReferenceSnapshot,
    ReferenceKind,
    KNOWN_USAGE_STATES,
    USAGE_STATE_FINAL,
    USAGE_STATE_OBSERVING,
)
from .model import (
    ALLOCATION_TRANSITIONS,
    AllocationAction,
    AllocationCommand,
    AllocationCompensationRecord,
    AllocationEvent,
    AllocationSnapshot,
    AllocationSubjectState,
    AllocationTransaction,
    BPS_DENOMINATOR,
    COMPENSATION_KIND_BY_ACTION,
    MONETARY_COMPENSATION_KINDS,
    PaymentReferenceRecord,
    PolicySubjectState,
    PolicyVersion,
    RoundingMode,
    SettlementAcknowledgement,
    SUBJECT_STATE_VALUES,
    allocation_transaction_digest,
    apply_rounding,
    build_allocation_snapshot,
    command_content,
    compute_split,
    derive_allocation_id,
    derive_command_digest,
    derive_compensation_id,
    derive_event_id,
    derive_payment_reference_id,
    derive_policy_id,
    derive_settlement_ack_id,
    event_list_digest,
    policy_registry_digest,
    transition_is_legal,
    transition_target,
)
from .validation import (
    PAYLOAD_MEMBER_RULES,
    find_duplicate_payment_reference,
    resolve_payment_reference,
    resolve_policy,
    resolve_settlement_reference,
    resolve_usage_projection,
    validate_command_against_state,
    validate_event_instant,
    validate_payload_shape,
    validate_policy_effective,
    validate_split_bounds,
    validate_usage_finality,
)
from .journal import (
    GENESIS_RECORD_ID,
    JOURNAL_RECORD_KIND,
    AllocationJournalRecord,
    AllocationStore,
    AppendOnlyAllocationJournal,
    FileAllocationStore,
    MemoryAllocationStore,
    derive_record_id,
    journal_bytes_for,
    record_list_digest,
)
from .ledger import (
    AllocationFoldState,
    AllocationLedger,
    CommandOutcome,
    CommandStatus,
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
    "AllocationError",
    "AllocationReasonCode",
    # external evidence boundary
    "AllocationEvidenceIndex",
    "BillableUsageSnapshot",
    "ExternalReferenceSnapshot",
    "ReferenceKind",
    "KNOWN_USAGE_STATES",
    "USAGE_STATE_FINAL",
    "USAGE_STATE_OBSERVING",
    # value model
    "ALLOCATION_TRANSITIONS",
    "AllocationAction",
    "AllocationCommand",
    "AllocationCompensationRecord",
    "AllocationEvent",
    "AllocationSnapshot",
    "AllocationSubjectState",
    "AllocationTransaction",
    "BPS_DENOMINATOR",
    "COMPENSATION_KIND_BY_ACTION",
    "MONETARY_COMPENSATION_KINDS",
    "PaymentReferenceRecord",
    "PolicySubjectState",
    "PolicyVersion",
    "RoundingMode",
    "SettlementAcknowledgement",
    "SUBJECT_STATE_VALUES",
    "allocation_transaction_digest",
    "apply_rounding",
    "build_allocation_snapshot",
    "command_content",
    "compute_split",
    "derive_allocation_id",
    "derive_command_digest",
    "derive_compensation_id",
    "derive_event_id",
    "derive_payment_reference_id",
    "derive_policy_id",
    "derive_settlement_ack_id",
    "event_list_digest",
    "policy_registry_digest",
    "transition_is_legal",
    "transition_target",
    # command admission rules
    "PAYLOAD_MEMBER_RULES",
    "find_duplicate_payment_reference",
    "resolve_payment_reference",
    "resolve_policy",
    "resolve_settlement_reference",
    "resolve_usage_projection",
    "validate_command_against_state",
    "validate_event_instant",
    "validate_payload_shape",
    "validate_policy_effective",
    "validate_split_bounds",
    "validate_usage_finality",
    # append-only journal + durable store
    "GENESIS_RECORD_ID",
    "JOURNAL_RECORD_KIND",
    "AllocationJournalRecord",
    "AllocationStore",
    "AppendOnlyAllocationJournal",
    "FileAllocationStore",
    "MemoryAllocationStore",
    "derive_record_id",
    "journal_bytes_for",
    "record_list_digest",
    # public production surface
    "AllocationFoldState",
    "AllocationLedger",
    "CommandOutcome",
    "CommandStatus",
    "apply_record",
    "fold_state",
    # deterministic evidence digests
    "assemble_digest_stream",
    "command_ledger_digest",
    "digest_of",
    "evidence_index_digest",
    "state_digest",
]
