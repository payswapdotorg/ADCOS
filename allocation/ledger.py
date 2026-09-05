"""WORK-053 EconomicAllocation lifecycle manager (the public
surface).

The control-plane authority for ALLOCATION/ECONOMIC-POLICY STATE
ONLY (ACR-009 "Economic allocation", W053 contract):

- It owns exactly one thing: the economic-allocation ledger --
  immutable versioned revenue-share policy versions, immutable
  three-way allocation snapshots derived from billable-final
  usage facts, external payment references recorded as DATA,
  settlement acknowledgements, and append-only compensating
  allocation events -- journaled append-only, deterministically,
  and idempotently, with every fact attributable.
- It REFERENCES billable-final UsageLedger projections (WORK-052
  authority-owned), W051 commercial citations, and EXTERNAL
  payment/settlement-plane reference identities through an
  INJECTED immutable
  :class:`~allocation.evidence.AllocationEvidenceIndex` snapshot
  built by the caller from the authorities' PUBLIC interfaces.
  It never queries, instantiates, or mutates a usage, commercial,
  session, path, routing, transport, identity, policy, or
  payment authority (no authority object ever crosses this
  boundary; the battery AST-audits it).
- Payment success NEVER creates allocation (payment references
  are DATA and the kind table rejects them as usage citations
  ``PAYMENT_NOT_USAGE``); reservation/offer state NEVER creates
  allocation (allocation consumes ONLY BILLABLE_FINAL usage
  facts -- ``USAGE_NOT_FINAL``; reservation and offer states
  have no usage statement to allocate at all); provider
  callbacks NEVER transition or reprice allocation (they are
  idempotent/append-only DATA records); payment-provider
  references identify external movement but are never commercial
  truth; ADCOS does not custody, mint, or move regulated funds
  here (the boundary records identity citations only).

Determinism: the ONLY time source is the injected WORK-033
``AgentClock`` seam.  Duplicate redeliveries (command-level,
policy-version-level, and provider-callback-level) consume NO
clock read (idempotent no-ops); every other command submission
consumes exactly ONE clock read (the deterministic event
instant, whether the command is then appended or rejected by a
gate -- the read count is a pure function of the command
sequence).  All ids and digests are content-derived over WORK-003
canonical JSON.  The fold (:func:`apply_record`,
:func:`fold_state`) is the SINGLE state-derivation AND
causal-verification function used by both the live manager and
journal replay, so live state and replayed state are
byte-identical by construction, and replay re-derives and
verifies the COMPLETE causal identity web of every record -- every
content-derived fact identity (policy version, allocation
snapshot, settlement acknowledgement, payment reference,
compensation), the event identities, the command/fact/attribution
bindings, the walk linkage, the allocation's re-binding to the
injected W052 usage snapshot (gross, statement, finality) and to
the folded immutable policy version (terms, bounds, rounding,
effective window), the external-reference kind/correlation
re-resolution, and the FULL allocation arithmetic re-derivation
(compute_split under the declared rounding mode) -- so a fact
mutated together with a fully recomputed outer hash chain still
fails closed ``JOURNAL_CORRUPT``.  The per-allocation projection
carries sorted reference/compensation audit lists, so the
ECONOMIC projection (shares, state, the reference-id multiset,
the compensation multiset) is arrival-order independent for the
same admitted set; the record identities themselves are
admission-attributed (they bind the causal command and the
admission instant).

Fresh construction requires an EMPTY store (the W042/W051/W052
precedent); :meth:`AllocationLedger.load` is the only
continuation path (journal-first recovery: load, verify the full
hash chain, fold with full causal re-verification, resume).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from agent.clock import AgentClock

from .errors import AllocationError, AllocationReasonCode
from .evidence import AllocationEvidenceIndex
from .journal import (
    AppendOnlyAllocationJournal,
    GENESIS_RECORD_ID,
    AllocationJournalRecord,
    AllocationStore,
)
from .model import (
    AllocationAction,
    AllocationCommand,
    AllocationCompensationRecord,
    AllocationEvent,
    AllocationSnapshot,
    AllocationTransaction,
    AllocationSubjectState,
    COMPENSATION_KIND_BY_ACTION,
    PaymentReferenceRecord,
    PolicySubjectState,
    PolicyVersion,
    SettlementAcknowledgement,
    build_allocation_snapshot,
    derive_allocation_id,
    derive_command_digest,
    derive_compensation_id,
    derive_event_id,
    derive_payment_reference_id,
    derive_policy_id,
    derive_settlement_ack_id,
    allocation_transaction_digest,
    policy_registry_digest,
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


class CommandStatus:
    """The frozen command-outcome vocabulary."""

    APPENDED = "appended"
    DUPLICATE = "duplicate"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.APPENDED, cls.DUPLICATE)


@dataclass(frozen=True)
class CommandOutcome:
    """The deterministic result of one command submission.

    ``APPENDED``: the command was admitted and its allocation
    fact journaled (persist-then-ack).  ``DUPLICATE``: the exact
    command (same id AND same content digest) was already
    admitted -- OR the identical immutable policy version
    (content-derived id over identical terms) was already
    registered -- OR a payment callback whose external reference
    identity was already recorded on the allocation -- an
    idempotent no-op; NO new journal record, NO clock read, NO
    state change; the recorded event id / fact id and the
    CURRENT projected state are returned.  Conflicting
    redeliveries (same command id, different content) raise
    ``COMMAND_CONFLICT``; conflicting reuse of a billable-final
    usage record or a mismatched external correlation raises the
    typed fail-closed reason.  Rejected commands raise typed
    AllocationError (fail closed, no journal growth).
    """

    status: str
    command_id: str
    subject_id: str
    event_id: str
    fact_id: str
    from_state: str
    to_state: str
    instant: str

    def __post_init__(self) -> None:
        if self.status not in CommandStatus.values():
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "status %r must be one of %s"
                % (self.status, list(CommandStatus.values())),
            )
        if self.status == CommandStatus.APPENDED:
            if not self.event_id:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "an appended outcome carries its event id",
                )
            if not self.fact_id:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "an appended outcome carries its fact id",
                )
            if not self.instant:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "an appended outcome carries its event instant",
                )


# ---------------------------------------------------------------------------
# The folded projection state (policies + allocations)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllocationFoldState:
    """The complete deterministic allocation fold state: the
    immutable policy-version registry (keyed by the
    content-derived policy id) and the allocation projections
    (keyed by the cited usage transaction id -- exactly one
    allocation per billable-final usage record)."""

    policies: Mapping[str, PolicyVersion] = field(default_factory=dict)
    allocations: Mapping[str, AllocationTransaction] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# The single state-derivation fold (live manager AND journal replay)
# ---------------------------------------------------------------------------

#: The fact kind each action must carry (the action/fact table;
#: frozen with the action vocabulary).
_ACTION_FACT_KIND: Dict[str, str] = {
    AllocationAction.REGISTER_POLICY: "policy-version-record",
    AllocationAction.ALLOCATE: "allocation-snapshot-record",
    AllocationAction.ACKNOWLEDGE_SETTLEMENT: (
        "settlement-acknowledgement-record"
    ),
    AllocationAction.RECORD_PAYMENT_REFERENCE: (
        "payment-reference-record"
    ),
    AllocationAction.RECORD_REFUND: "allocation-compensation-record",
    AllocationAction.RECORD_REVERSAL: "allocation-compensation-record",
    AllocationAction.RECORD_CHARGEBACK: (
        "allocation-compensation-record"
    ),
    AllocationAction.RECORD_PAYOUT_FAILURE: (
        "allocation-compensation-record"
    ),
    AllocationAction.RECORD_DISPUTE: "allocation-compensation-record",
}


def _corrupt(record: AllocationJournalRecord, message: str) -> AllocationError:
    """A fail-closed ``JOURNAL_CORRUPT`` error located at one
    journal record (the replay integrity boundary)."""
    return AllocationError(
        AllocationReasonCode.JOURNAL_CORRUPT,
        "journal record %d: %s" % (record.sequence, message),
    )


def _corrupt_from(
    record: AllocationJournalRecord, prefix: str, error: AllocationError
) -> AllocationError:
    """Map an admission-shaped gate failure re-applied at replay
    to fail-closed ``JOURNAL_CORRUPT`` (the admission/replay
    symmetry: the journal cannot contain a record admission would
    have rejected, walk-valid or not)."""
    return _corrupt(
        record, "%s: %s" % (prefix, error.detail)
    )


def _derive_or_corrupt(record, builder):
    """Run one replay-side fact derivation, mapping every typed
    model failure to fail-closed ``JOURNAL_CORRUPT`` (a stored
    record whose expected fact cannot even be constructed is a
    corrupted record, never an admission error)."""
    try:
        return builder()
    except AllocationError as error:
        raise _corrupt(
            record,
            "the stored fact is not derivable from its causal "
            "command: %s" % error.detail,
        ) from error


def _parse_fact(
    record: AllocationJournalRecord, event: AllocationEvent
) -> Any:
    """Extract the event's fact record through the action/fact
    kind table, mapping every parse/validation failure to
    ``JOURNAL_CORRUPT`` (a malformed stored fact is corruption,
    not an admission error)."""
    action = event.action
    expected_kind = _ACTION_FACT_KIND[action]
    found_kind = event.fact.get("kind")
    if found_kind != expected_kind:
        raise _corrupt(
            record,
            "a %s event must carry a %s fact (found %r)"
            % (action, expected_kind, found_kind),
        )
    try:
        if expected_kind == "policy-version-record":
            fact: Any = event.policy_version()
        elif expected_kind == "allocation-snapshot-record":
            fact = event.allocation_snapshot()
        elif expected_kind == "settlement-acknowledgement-record":
            fact = event.settlement_acknowledgement()
        elif expected_kind == "payment-reference-record":
            fact = event.payment_reference()
        else:
            fact = event.compensation()
    except AllocationError as error:
        raise _corrupt(
            record,
            "the stored %s fact is invalid: %s"
            % (expected_kind, error.detail),
        ) from error
    if fact is None:  # pragma: no cover - the kind gate ran above
        raise _corrupt(record, "missing %s fact" % expected_kind)
    return fact


def _verify_fact_identity(
    record: AllocationJournalRecord, event: AllocationEvent, fact: Any
) -> str:
    """Re-derive the content-derived fact identity from the fact's
    OWN content (the identity <-> content binding).

    ``policy_id`` / ``allocation_id`` / ``acknowledgement_id`` /
    ``payment_reference_id`` / ``compensation_id`` are documented
    as content-derived fingerprints; this gate mechanically
    re-derives each one from the fact it claims to identify, so a
    fact whose content was edited without a fully-consistent
    identity cascade fails closed here.  Returns the fact id (the
    event identity's fact member).
    """
    action = event.action
    if action == AllocationAction.REGISTER_POLICY:
        policy: PolicyVersion = fact
        expected = derive_policy_id(
            policy.label,
            policy.adcos_share_bps,
            policy.provider_min_bps,
            policy.provider_max_bps,
            policy.rounding_mode,
            policy.currency,
            policy.minor_unit_digits,
            policy.effective_from,
            policy.effective_until,
        )
        if policy.policy_id != expected:
            raise _corrupt(
                record,
                "policy id %s does not match the id re-derived from "
                "its own terms %s (tampered policy version)"
                % (policy.policy_id, expected),
            )
        return policy.policy_id
    if action == AllocationAction.ALLOCATE:
        snapshot: AllocationSnapshot = fact
        expected = derive_allocation_id(
            snapshot.usage_transaction_id,
            snapshot.usage_statement_id,
            snapshot.policy_id,
            snapshot.provider_share_bps,
            snapshot.fee_micros,
            snapshot.tax_micros,
            snapshot.adjustment_micros,
            snapshot.created_at,
        )
        if snapshot.allocation_id != expected:
            raise _corrupt(
                record,
                "allocation id %s does not match the id re-derived "
                "from its own content %s (tampered allocation "
                "snapshot)" % (snapshot.allocation_id, expected),
            )
        return snapshot.allocation_id
    if action == AllocationAction.ACKNOWLEDGE_SETTLEMENT:
        acknowledgement: SettlementAcknowledgement = fact
        expected = derive_settlement_ack_id(
            acknowledgement.usage_transaction_id,
            acknowledgement.allocation_id,
            acknowledgement.settlement_reference,
            acknowledgement.command_id,
            acknowledgement.acknowledged_at,
        )
        if acknowledgement.acknowledgement_id != expected:
            raise _corrupt(
                record,
                "acknowledgement id %s does not match the id "
                "re-derived from its own content %s (tampered "
                "settlement acknowledgement)"
                % (acknowledgement.acknowledgement_id, expected),
            )
        return acknowledgement.acknowledgement_id
    if action == AllocationAction.RECORD_PAYMENT_REFERENCE:
        reference: PaymentReferenceRecord = fact
        expected = derive_payment_reference_id(
            reference.usage_transaction_id,
            reference.allocation_id,
            reference.payment_reference,
            reference.command_id,
            reference.recorded_at,
        )
        if reference.payment_reference_id != expected:
            raise _corrupt(
                record,
                "payment reference record id %s does not match the id "
                "re-derived from its own content %s (tampered payment "
                "reference record)"
                % (reference.payment_reference_id, expected),
            )
        return reference.payment_reference_id
    compensation: AllocationCompensationRecord = fact
    expected = derive_compensation_id(
        compensation.usage_transaction_id,
        compensation.compensation_kind,
        compensation.amount_micros,
        compensation.reason,
        compensation.allocation_id,
        compensation.command_id,
        compensation.recorded_at,
    )
    if compensation.compensation_id != expected:
        raise _corrupt(
            record,
            "compensation id %s does not match the id re-derived from "
            "its own content %s (tampered compensation fact)"
            % (compensation.compensation_id, expected),
        )
    return compensation.compensation_id


def _verify_event_identity(
    record: AllocationJournalRecord,
    event: AllocationEvent,
    fact_id: str,
) -> None:
    """Re-derive the event id from the event's own content + the
    fact's identity (the event identity <-> content binding).

    The event id binds the full attribution + walk edge + the
    causal command + the fact identity + the instant; a fact or
    event edited with a recomputed outer record chain but an
    un-cascaded event id fails closed here.
    """
    expected = derive_event_id(
        event.subject_id,
        event.action,
        event.from_state,
        event.to_state,
        event.command_id,
        fact_id,
        event.instant,
    )
    if event.event_id != expected:
        raise _corrupt(
            record,
            "event id %s does not match the id re-derived from its "
            "content and fact identity %s (tampered event)"
            % (event.event_id, expected),
        )


def _expected_policy(
    record: AllocationJournalRecord, event: AllocationEvent
) -> PolicyVersion:
    """Re-derive the policy-version fact from its causal command
    and the event instant (the command -> policy binding)."""
    command = record.command
    payload = command.payload
    policy_id = derive_policy_id(
        command.subject_id,
        payload["adcos_share_bps"],
        payload["provider_min_bps"],
        payload["provider_max_bps"],
        payload["rounding_mode"],
        payload["currency"],
        payload["minor_unit_digits"],
        payload["effective_from"],
        payload["effective_until"],
    )
    return PolicyVersion(
        policy_id=policy_id,
        label=command.subject_id,
        adcos_share_bps=payload["adcos_share_bps"],
        provider_min_bps=payload["provider_min_bps"],
        provider_max_bps=payload["provider_max_bps"],
        rounding_mode=payload["rounding_mode"],
        currency=payload["currency"],
        minor_unit_digits=payload["minor_unit_digits"],
        effective_from=payload["effective_from"],
        effective_until=payload["effective_until"],
        command_id=command.command_id,
        registered_at=event.instant,
    )


def _expected_settlement_ack(
    record: AllocationJournalRecord,
    event: AllocationEvent,
    allocation_id: str,
) -> SettlementAcknowledgement:
    """Re-derive the settlement-acknowledgement fact from its
    causal command, the folded allocation, and the event
    instant."""
    command = record.command
    return SettlementAcknowledgement(
        acknowledgement_id=derive_settlement_ack_id(
            command.subject_id,
            allocation_id,
            command.payload["settlement_reference"],
            command.command_id,
            event.instant,
        ),
        usage_transaction_id=command.subject_id,
        allocation_id=allocation_id,
        settlement_reference=command.payload["settlement_reference"],
        command_id=command.command_id,
        acknowledged_at=event.instant,
    )


def _expected_payment_reference(
    record: AllocationJournalRecord,
    event: AllocationEvent,
    allocation_id: str,
) -> PaymentReferenceRecord:
    """Re-derive the payment-reference DATA fact from its causal
    command, the folded allocation, and the event instant."""
    command = record.command
    return PaymentReferenceRecord(
        payment_reference_id=derive_payment_reference_id(
            command.subject_id,
            allocation_id,
            command.payload["payment_reference"],
            command.command_id,
            event.instant,
        ),
        usage_transaction_id=command.subject_id,
        allocation_id=allocation_id,
        payment_reference=command.payload["payment_reference"],
        command_id=command.command_id,
        recorded_at=event.instant,
    )


def _expected_compensation(
    record: AllocationJournalRecord,
    event: AllocationEvent,
    allocation_id: str,
) -> AllocationCompensationRecord:
    """Re-derive the compensation fact from its causal command,
    the folded allocation, and the event instant."""
    command = record.command
    compensation_kind = COMPENSATION_KIND_BY_ACTION[command.action]
    amount_micros = (
        command.payload.get("amount_micros")
        if compensation_kind != "dispute"
        else 0
    )
    return AllocationCompensationRecord(
        compensation_id=derive_compensation_id(
            command.subject_id,
            compensation_kind,
            amount_micros,
            command.payload.get("reason"),
            allocation_id,
            command.command_id,
            event.instant,
        ),
        usage_transaction_id=command.subject_id,
        compensation_kind=compensation_kind,
        amount_micros=amount_micros,
        reason=command.payload.get("reason"),
        allocation_id=allocation_id,
        command_id=command.command_id,
        recorded_at=event.instant,
    )


def apply_record(
    state: AllocationFoldState,
    record: AllocationJournalRecord,
    *,
    evidence_index: AllocationEvidenceIndex,
) -> AllocationFoldState:
    """Apply ONE journal record to the fold state.

    THE single state-derivation function: the live manager calls
    it after append; journal replay calls it in order.  It is also
    THE single causal-verification function (the replay
    integrity boundary).  Before folding, every record is
    verified against its COMPLETE causal identity web:

    - the event attribution must equal the admitted command's
      attribution (actor/source) and the command/event subjects
      must match (the record invariant);
    - the fact kind must match the action (the action/fact
      table);
    - the content-derived fact identity must re-derive from the
      fact's OWN content;
    - the event id must re-derive from the event's content and
      the fact's identity;
    - the fact must be EXACTLY the deterministic derivation of
      its causal command, the folded state, and the event
      instant -- and, for ALLOCATE, of the injected W052 usage
      snapshot (the payment/settlement kind table, the usage
      statement binding, the BILLABLE_FINAL finality gate -- the
      SAME gates admission applies) and the folded immutable
      policy version (resolution, bounds, effective window) with
      the FULL allocation arithmetic re-derivation (the exact
      three-way split under the declared rounding mode); for
      ACKNOWLEDGE_SETTLEMENT and RECORD_PAYMENT_REFERENCE, of
      the external-reference kind/correlation re-resolution
      (admission/replay symmetry); compensations must cite the
      folded allocation, require the SETTLED state, and stay
      bounded (the net never goes negative; one open dispute);
      payment references must not duplicate a recorded callback
      identity; ALLOCATE must be the one allocation for its
      subject; REGISTER_POLICY must be the one registration for
      its version id;
    - the walk linkage (the event's declared predecessor state
      MUST be the folded current state -- the replay verifies the
      WALK, not merely the chain and each edge) and the frozen
      transition table.

    A modified fact therefore cannot be made chain-valid merely
    by recomputing the outer record id/hash chain: every
    mismatch fails closed ``JOURNAL_CORRUPT``.  The projection is
    returned as a NEW frozen state (no in-place mutation; the
    reference/compensation lists are re-sorted so the economic
    fold is arrival-order independent).
    """
    event = record.event
    command = record.command
    action = event.action

    # --- attribution binding (event == admitted command) ---
    if event.actor != command.actor or event.source != command.source:
        raise _corrupt(
            record,
            "event attribution (actor %r, source %r) does not match "
            "the admitted command's attribution (actor %r, source %r)"
            % (event.actor, event.source, command.actor, command.source),
        )

    # --- fact extraction + identity <-> content bindings ---
    fact = _parse_fact(record, event)
    fact_id = _verify_fact_identity(record, event, fact)
    _verify_event_identity(record, event, fact_id)

    if action == AllocationAction.REGISTER_POLICY:
        policy: PolicyVersion = fact
        expected_policy = _derive_or_corrupt(
            record, lambda: _expected_policy(record, event)
        )
        if policy.to_dict() != expected_policy.to_dict():
            raise _corrupt(
                record,
                "the policy version fact is not the deterministic "
                "derivation of its causal command (terms, label, or "
                "attribution divergence)",
            )
        if (
            event.from_state != PolicySubjectState.REGISTERED
            or event.to_state != PolicySubjectState.REGISTERED
        ):
            raise _corrupt(
                record,
                "the policy registration record must be the REGISTERED "
                "self-edge (found %s -> %s)"
                % (event.from_state, event.to_state),
            )
        if policy.policy_id in state.policies:
            raise _corrupt(
                record,
                "duplicate policy version id %s in the journal "
                "(admission de-duplicates identical terms; the "
                "journal cannot carry both)"
                % policy.policy_id,
            )
        policies = dict(state.policies)
        policies[policy.policy_id] = policy
        return AllocationFoldState(
            policies=policies, allocations=dict(state.allocations)
        )

    if action == AllocationAction.ALLOCATE:
        snapshot: AllocationSnapshot = fact
        # The SAME usage-citation gates admission applies, re-applied
        # against the injected W052 snapshot at replay (the
        # payment/settlement/usage kind table, the statement
        # binding, and the BILLABLE_FINAL finality gate: payment,
        # reservation, or offer state never creates allocation --
        # at admission OR at replay).
        try:
            usage_snapshot = resolve_usage_projection(
                command, evidence_index
            )
        except AllocationError as error:
            raise _corrupt_from(
                record,
                "the ALLOCATE usage citation is not admissible against "
                "the injected W052 usage snapshot at replay",
                error,
            ) from error
        # The policy must resolve from the FOLDED registry exactly as
        # admission required (journal order: registered before cited).
        try:
            policy = resolve_policy(command, state.policies)
        except AllocationError as error:
            raise _corrupt_from(
                record,
                "the ALLOCATE policy citation does not resolve in the "
                "folded policy registry at replay",
                error,
            ) from error
        try:
            validate_split_bounds(
                policy, command.payload["provider_share_bps"]
            )
        except AllocationError as error:
            raise _corrupt_from(
                record,
                "the ALLOCATE developer-selected split violates the "
                "cited policy bounds at replay",
                error,
            ) from error
        try:
            validate_policy_effective(policy, event.instant)
        except AllocationError as error:
            raise _corrupt_from(
                record,
                "the cited policy version is not effective at the "
                "ALLOCATE instant at replay",
                error,
            ) from error
        # The FULL arithmetic re-derivation (the single derivation
        # function admission itself uses: gross re-bound to the
        # injected usage snapshot, policy terms, split, and fees).
        try:
            expected_snapshot = build_allocation_snapshot(
                usage_transaction_id=command.subject_id,
                usage_snapshot=usage_snapshot,
                policy=policy,
                provider_share_bps=command.payload[
                    "provider_share_bps"
                ],
                fee_micros=command.payload["fee_micros"],
                tax_micros=command.payload["tax_micros"],
                adjustment_micros=command.payload["adjustment_micros"],
                created_at=event.instant,
            )
        except AllocationError as error:
            raise _corrupt_from(
                record,
                "the ALLOCATE arithmetic is not admissible at replay "
                "(distribution/derivation divergence)",
                error,
            ) from error
        if snapshot.to_dict() != expected_snapshot.to_dict():
            raise _corrupt(
                record,
                "the allocation snapshot is not the deterministic "
                "derivation of the injected W052 usage snapshot, the "
                "folded policy version, and the declared split and "
                "charges (gross, statement, shares, rounding, or "
                "conservation diverge; a recomputed outer chain cannot "
                "reprice the allocation fact)",
            )
        if event.subject_id in state.allocations:
            raise _corrupt(
                record,
                "duplicate allocation for usage transaction %s in the "
                "journal (exactly one allocation per billable-final "
                "usage record; admission would have rejected the "
                "second)" % event.subject_id,
            )
        if (
            event.from_state != AllocationSubjectState.PLANNED
            or event.to_state != AllocationSubjectState.PLANNED
        ):
            raise _corrupt(
                record,
                "the allocation creation record must be the PLANNED "
                "self-edge (found %s -> %s)"
                % (event.from_state, event.to_state),
            )
        allocations = dict(state.allocations)
        allocations[event.subject_id] = AllocationTransaction(
            usage_transaction_id=event.subject_id,
            state=event.to_state,
            snapshot=snapshot,
        )
        return AllocationFoldState(
            policies=dict(state.policies), allocations=allocations
        )

    # --- every remaining action operates on an existing
    # --- allocation subject (walk-linkage verified)
    transaction = state.allocations.get(event.subject_id)
    if transaction is None:
        raise _corrupt(
            record,
            "journal record for usage transaction %s has no folded "
            "allocation before action %r (allocations are created by "
            "ALLOCATE only)" % (event.subject_id, action),
        )
    if event.from_state != transaction.state:
        raise _corrupt(
            record,
            "journal record for usage transaction %s declares "
            "from_state %s but the folded state is %s (out-of-order "
            "or inserted record; the replay walk must be contiguous)"
            % (event.subject_id, event.from_state, transaction.state),
        )
    if transition_target(event.from_state, action) != event.to_state:
        raise _corrupt(
            record,
            "journal record for usage transaction %s declares %s -> "
            "%s via %s which is not a frozen-table transition"
            % (
                event.subject_id,
                event.from_state,
                event.to_state,
                action,
            ),
        )

    if action == AllocationAction.ACKNOWLEDGE_SETTLEMENT:
        acknowledgement: SettlementAcknowledgement = fact
        # the SAME external-reference kind/correlation gates
        # admission applies, re-applied at replay
        try:
            resolve_settlement_reference(command, evidence_index)
        except AllocationError as error:
            raise _corrupt_from(
                record,
                "the settlement acknowledgement citation is not "
                "admissible against the injected reference index at "
                "replay",
                error,
            ) from error
        expected_ack = _derive_or_corrupt(
            record,
            lambda: _expected_settlement_ack(
                record, event, transaction.snapshot.allocation_id
            ),
        )
        if acknowledgement.to_dict() != expected_ack.to_dict():
            raise _corrupt(
                record,
                "the settlement acknowledgement fact is not the "
                "deterministic derivation of its causal command and "
                "the folded allocation (reference, citation, or "
                "attribution divergence)",
            )
        allocations = dict(state.allocations)
        allocations[event.subject_id] = AllocationTransaction(
            usage_transaction_id=transaction.usage_transaction_id,
            state=event.to_state,
            snapshot=transaction.snapshot,
            settlement=acknowledgement,
            payment_references=transaction.payment_references,
            compensations=transaction.compensations,
        )
        return AllocationFoldState(
            policies=dict(state.policies), allocations=allocations
        )

    if action == AllocationAction.RECORD_PAYMENT_REFERENCE:
        reference_record: PaymentReferenceRecord = fact
        try:
            resolve_payment_reference(command, evidence_index)
        except AllocationError as error:
            raise _corrupt_from(
                record,
                "the payment callback citation is not admissible "
                "against the injected reference index at replay",
                error,
            ) from error
        expected_reference = _derive_or_corrupt(
            record,
            lambda: _expected_payment_reference(
                record, event, transaction.snapshot.allocation_id
            ),
        )
        if reference_record.to_dict() != expected_reference.to_dict():
            raise _corrupt(
                record,
                "the payment reference record is not the deterministic "
                "derivation of its causal command and the folded "
                "allocation (citation or attribution divergence)",
            )
        for existing in transaction.payment_references:
            if (
                existing.payment_reference
                == reference_record.payment_reference
            ):
                raise _corrupt(
                    record,
                    "duplicate external payment reference identity %s "
                    "in the journal (admission de-duplicates callback "
                    "redelivery; the journal cannot carry both)"
                    % reference_record.payment_reference,
                )
        references = tuple(
            sorted(
                transaction.payment_references + (reference_record,),
                key=lambda item: item.payment_reference_id,
            )
        )
        allocations = dict(state.allocations)
        allocations[event.subject_id] = AllocationTransaction(
            usage_transaction_id=transaction.usage_transaction_id,
            state=event.to_state,
            snapshot=transaction.snapshot,
            settlement=transaction.settlement,
            payment_references=references,
            compensations=transaction.compensations,
        )
        return AllocationFoldState(
            policies=dict(state.policies), allocations=allocations
        )

    # the compensation family
    compensation: AllocationCompensationRecord = fact
    if transaction.state != AllocationSubjectState.SETTLED:
        raise _corrupt(
            record,
            "%s journal record arrives with the allocation not "
            "settled (compensations append against settled history)"
            % action,
        )
    if transaction.settlement is None:  # pragma: no cover - SETTLED invariant
        raise _corrupt(
            record,
            "SETTLED allocation carries no settlement acknowledgement "
            "(projection invariant violation)",
        )
    expected_compensation = _derive_or_corrupt(
        record,
        lambda: _expected_compensation(
            record, event, transaction.snapshot.allocation_id
        ),
    )
    if compensation.to_dict() != expected_compensation.to_dict():
        raise _corrupt(
            record,
            "the compensation fact is not the deterministic derivation "
            "of its causal command and the folded allocation (amount, "
            "reason, kind, citation, or attribution divergence)",
        )
    compensation_kind = expected_compensation.compensation_kind
    if compensation_kind != "dispute":
        cumulative = transaction.monetary_compensation_micros()
        if (
            cumulative + expected_compensation.amount_micros
            > transaction.snapshot.distributable_micros
        ):
            raise _corrupt(
                record,
                "the journaled compensation exceeds the distributable "
                "allocation at replay (the journal cannot contain an "
                "over-compensation admission would have rejected; the "
                "net never goes negative)",
            )
    if compensation_kind == "dispute" and transaction.disputed():
        raise _corrupt(
            record,
            "a second dispute record in the journal (admission would "
            "have rejected it; one open dispute per allocation)",
        )
    compensations = tuple(
        sorted(
            transaction.compensations + (compensation,),
            key=lambda item: item.compensation_id,
        )
    )
    allocations = dict(state.allocations)
    allocations[event.subject_id] = AllocationTransaction(
        usage_transaction_id=transaction.usage_transaction_id,
        state=event.to_state,
        snapshot=transaction.snapshot,
        settlement=transaction.settlement,
        payment_references=transaction.payment_references,
        compensations=compensations,
    )
    return AllocationFoldState(
        policies=dict(state.policies), allocations=allocations
    )


def fold_state(
    records: Tuple[AllocationJournalRecord, ...],
    *,
    evidence_index: AllocationEvidenceIndex,
) -> AllocationFoldState:
    """Fold a verified journal into the allocation state.

    Deterministic: records in journal order, one apply per
    record.  The live manager's state and this fold are
    byte-identical by construction (the same
    :func:`apply_record`), and the fold is where replay
    re-derives and verifies the complete causal identity web of
    every record -- all fail-closed ``JOURNAL_CORRUPT``.
    """
    state = AllocationFoldState()
    for record in records:
        state = apply_record(
            state, record, evidence_index=evidence_index
        )
    return state


# ---------------------------------------------------------------------------
# The AllocationLedger public surface
# ---------------------------------------------------------------------------


class AllocationLedger:
    """The economic-allocation ledger (frozen public surface).

    Construct fresh over an EMPTY store; recover a persisted
    store with :meth:`load`.  Every command submission: dedup
    (command id, then policy-version identity, then
    provider-callback identity) -> shape/index validation -> ONE
    clock read -> state gates -> atomic journal append
    (persist-then-ack) -> fold.
    """

    def __init__(
        self,
        *,
        store: AllocationStore,
        clock: AgentClock,
        evidence_index: AllocationEvidenceIndex,
    ) -> None:
        if not isinstance(store, AllocationStore):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "store must be an AllocationStore",
            )
        if not isinstance(clock, AgentClock):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 "
                "seam)",
            )
        if not isinstance(evidence_index, AllocationEvidenceIndex):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "evidence_index must be an AllocationEvidenceIndex "
                "(built from the authorities' public surfaces by the "
                "caller)",
            )
        self._journal = AppendOnlyAllocationJournal(store=store)
        if len(self._journal) != 0:
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "fresh construction requires an EMPTY store (recover "
                "a persisted ledger with AllocationLedger.load)",
            )
        self._clock = clock
        self._evidence_index = evidence_index
        self._fold = AllocationFoldState()

    @classmethod
    def load(
        cls,
        *,
        store: AllocationStore,
        clock: AgentClock,
        evidence_index: AllocationEvidenceIndex,
    ) -> "AllocationLedger":
        """Journal-first recovery: load, verify the full hash
        chain, fold, resume (the only continuation path)."""
        if not isinstance(store, AllocationStore):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "store must be an AllocationStore",
            )
        if not isinstance(clock, AgentClock):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 "
                "seam)",
            )
        if not isinstance(evidence_index, AllocationEvidenceIndex):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "evidence_index must be an AllocationEvidenceIndex",
            )
        ledger = cls.__new__(cls)
        ledger._journal = AppendOnlyAllocationJournal(store=store)
        ledger._clock = clock
        ledger._evidence_index = evidence_index
        ledger._fold = fold_state(
            ledger._journal.records(), evidence_index=evidence_index
        )
        return ledger

    # ------------------------------------------------------------------
    # Reads (deterministic, no clock consumption)
    # ------------------------------------------------------------------

    def evidence_index(self) -> AllocationEvidenceIndex:
        return self._evidence_index

    def policy(self, policy_id: str) -> PolicyVersion:
        policy = self._fold.policies.get(policy_id)
        if policy is None:
            raise AllocationError(
                AllocationReasonCode.POLICY_UNKNOWN,
                "policy version %r is not registered in the folded "
                "policy registry" % policy_id,
            )
        return policy

    def policies(self) -> Tuple[PolicyVersion, ...]:
        return tuple(
            self._fold.policies[key]
            for key in sorted(self._fold.policies)
        )

    def allocation(self, usage_transaction_id: str) -> AllocationTransaction:
        projection = self._fold.allocations.get(usage_transaction_id)
        if projection is None:
            raise AllocationError(
                AllocationReasonCode.ALLOCATION_UNKNOWN,
                "usage transaction %r has no allocation in the "
                "economic ledger" % usage_transaction_id,
            )
        return projection

    def allocations(self) -> Tuple[AllocationTransaction, ...]:
        return tuple(
            self._fold.allocations[key]
            for key in sorted(self._fold.allocations)
        )

    def command_ledger(self) -> Dict[str, Dict[str, str]]:
        return self._journal.command_ledger()

    def journal_records(self) -> Tuple[AllocationJournalRecord, ...]:
        return self._journal.records()

    def journal_digest(self) -> str:
        return self._journal.journal_digest()

    def state_digest(self) -> str:
        from .digest import state_digest

        return state_digest(self._fold)

    def digest_stream(self) -> str:
        """The canonical deterministic evidence document (journal,
        state, command ledger, event list, evidence index digests
        in one canonical JSON document; the two-run and hash-seed
        determinism proofs bind to this)."""
        from .digest import assemble_digest_stream

        return assemble_digest_stream(
            journal=self._journal,
            fold=self._fold,
            index=self._evidence_index,
        )

    def allocation_statement(self, usage_transaction_id: str) -> Dict[str, Any]:
        """The deterministic allocation reconciliation statement:
        the billable-final usage citation, the immutable policy
        version citation, the exact three-way split and its
        conservation proof, the external payment references, the
        settlement acknowledgement, the compensating events, and
        the net -- with the full audit trail (ids + digests).

        A pure deterministic READ (no journal growth, no clock
        consumption): byte-identical across re-reads, restarts,
        and replay.
        """
        projection = self.allocation(usage_transaction_id)
        snapshot = projection.snapshot
        statement: Dict[str, Any] = {
            "kind": "allocation-reconciliation-statement",
            "usage_transaction_id": usage_transaction_id,
            "allocation_state": projection.state,
            "allocation_id": snapshot.allocation_id,
            "usage_statement_id": snapshot.usage_statement_id,
            "policy_id": snapshot.policy_id,
            "gross_micros": snapshot.gross_micros,
            "fee_micros": snapshot.fee_micros,
            "tax_micros": snapshot.tax_micros,
            "adjustment_micros": snapshot.adjustment_micros,
            "distributable_micros": snapshot.distributable_micros,
            "adcos_share_micros": snapshot.adcos_share_micros,
            "provider_share_micros": snapshot.provider_share_micros,
            "developer_share_micros": snapshot.developer_share_micros,
            "three_way_sum_micros": (
                snapshot.adcos_share_micros
                + snapshot.provider_share_micros
                + snapshot.developer_share_micros
            ),
            "provider_share_bps": snapshot.provider_share_bps,
            "adcos_share_bps": snapshot.adcos_share_bps,
            "rounding_mode": snapshot.rounding_mode,
            "currency": snapshot.currency,
            "minor_unit_digits": snapshot.minor_unit_digits,
            "created_at": snapshot.created_at,
        }
        if projection.settlement is not None:
            settlement = projection.settlement
            statement.update(
                {
                    "settlement_acknowledged": True,
                    "settlement_reference": (
                        settlement.settlement_reference
                    ),
                    "acknowledgement_id": settlement.acknowledgement_id,
                    "acknowledged_at": settlement.acknowledged_at,
                }
            )
        else:
            statement["settlement_acknowledged"] = False
        statement.update(
            {
                "payment_reference_ids": [
                    record.payment_reference
                    for record in projection.payment_references
                ],
                "payment_reference_record_ids": [
                    record.payment_reference_id
                    for record in projection.payment_references
                ],
                "refunded_amount_micros": (
                    projection.refunded_amount_micros()
                ),
                "reversed_amount_micros": (
                    projection.reversed_amount_micros()
                ),
                "chargeback_amount_micros": (
                    projection.chargeback_amount_micros()
                ),
                "payout_failure_amount_micros": (
                    projection.payout_failure_amount_micros()
                ),
                "disputed": projection.disputed(),
                "net_distributable_micros": (
                    projection.net_distributable_micros()
                ),
                "compensation_ids": [
                    compensation.compensation_id
                    for compensation in projection.compensations
                ],
                "projection_digest": allocation_transaction_digest(
                    projection
                ),
            }
        )
        return statement

    def verify_replay(self) -> None:
        """Fold the journal from scratch -- re-deriving and
        verifying the complete causal identity web of every
        record -- and compare against the live state
        (byte-identical by construction; any drift is
        JOURNAL_CORRUPT fail-closed)."""
        folded = fold_state(
            self._journal.records(), evidence_index=self._evidence_index
        )
        if sorted(folded.policies) != sorted(self._fold.policies):
            raise AllocationError(
                AllocationReasonCode.JOURNAL_CORRUPT,
                "live policy registry diverges from the journal fold",
            )
        if sorted(folded.allocations) != sorted(self._fold.allocations):
            raise AllocationError(
                AllocationReasonCode.JOURNAL_CORRUPT,
                "live allocation set diverges from the journal fold",
            )
        for key in sorted(self._fold.policies):
            if (
                self._fold.policies[key].to_dict()
                != folded.policies[key].to_dict()
            ):
                raise AllocationError(
                    AllocationReasonCode.JOURNAL_CORRUPT,
                    "live policy %s diverges from the journal fold"
                    % key,
                )
        for key in sorted(self._fold.allocations):
            if (
                self._fold.allocations[key].to_dict()
                != folded.allocations[key].to_dict()
            ):
                raise AllocationError(
                    AllocationReasonCode.JOURNAL_CORRUPT,
                    "live allocation for %s diverges from the journal "
                    "fold" % key,
                )

    # ------------------------------------------------------------------
    # Command execution (dedup -> validate -> clock -> append -> fold)
    # ------------------------------------------------------------------

    def _duplicate_outcome(
        self, command: AllocationCommand, fact_id: str, event_id: str
    ) -> CommandOutcome:
        transaction = self._fold.allocations.get(command.subject_id)
        current_state = (
            transaction.state if transaction is not None else ""
        )
        return CommandOutcome(
            status=CommandStatus.DUPLICATE,
            command_id=command.command_id,
            subject_id=command.subject_id,
            event_id=event_id,
            fact_id=fact_id,
            from_state=current_state,
            to_state=current_state,
            instant="",
        )

    def _find_fact_event_id(self, fact_id: str) -> str:
        """Recover the event id of the journal record that carries
        the given fact id (deterministic scan of the journal)."""
        for record in self._journal.records():
            event = record.event
            if event.fact.get("kind") == "policy-version-record":
                if event.fact.get("policy_id") == fact_id:
                    return event.event_id
            elif event.fact.get("kind") == "payment-reference-record":
                if event.fact.get("payment_reference_id") == fact_id:
                    return event.event_id
        return ""

    def _execute(self, command: AllocationCommand) -> CommandOutcome:
        """The single admission path (every typed method lands
        here; the generic path is deliberately NOT public -- the
        frozen typed surface is the whole API)."""
        # 1. durable idempotency: exact duplicate = no-op (no
        #    clock read, no journal growth); conflicting
        #    redelivery = fail closed.
        known = self._journal.known_command(command.command_id)
        if known is not None:
            if known["command_digest"] != command.digest():
                raise AllocationError(
                    AllocationReasonCode.COMMAND_CONFLICT,
                    "command id %r was already admitted with different "
                    "content (conflicting duplicate rejected)"
                    % command.command_id,
                )
            return self._duplicate_outcome(
                command, fact_id="", event_id=known["event_id"]
            )

        # 2. shape validation (fail closed, no journal growth)
        validate_payload_shape(command)

        action = command.action

        # 3. per-action pre-resolution (static, index/registry
        #    derived, no clock consumption)
        if action == AllocationAction.REGISTER_POLICY:
            policy_id = derive_policy_id(
                command.subject_id,
                command.payload["adcos_share_bps"],
                command.payload["provider_min_bps"],
                command.payload["provider_max_bps"],
                command.payload["rounding_mode"],
                command.payload["currency"],
                command.payload["minor_unit_digits"],
                command.payload["effective_from"],
                command.payload["effective_until"],
            )
            registered = self._fold.policies.get(policy_id)
            if registered is not None:
                # policy-version-level duplicate: identical TERMS
                # derive the identical immutable version id -- an
                # idempotent no-op (no clock read, no journal
                # growth; the version is already registered).
                return self._duplicate_outcome(
                    command,
                    fact_id=policy_id,
                    event_id=self._find_fact_event_id(policy_id),
                )
        elif action == AllocationAction.ALLOCATE:
            # the payment/settlement/usage kind table, the usage
            # statement binding, and the BILLABLE_FINAL gate
            usage_snapshot = resolve_usage_projection(
                command, self._evidence_index
            )
            validate_usage_finality(command, usage_snapshot)
            # the policy resolves from the folded registry (never
            # a live authority)
            policy = resolve_policy(command, self._fold.policies)
            # the developer-selected split within platform bounds
            validate_split_bounds(
                policy, command.payload["provider_share_bps"]
            )
            # the distribution discipline (static: no instant
            # needed) -- distributable must stay within [0, gross]
            gross = usage_snapshot.gross_amount_micros
            distributable = (
                gross
                - command.payload["fee_micros"]
                - command.payload["tax_micros"]
                - command.payload["adjustment_micros"]
            )
            if distributable < 0 or distributable > gross:
                raise AllocationError(
                    AllocationReasonCode.DISTRIBUTION_INVALID,
                    "distributable %d (gross %d - fee %d - tax %d - "
                    "adjustment %d) must be within [0, gross] (the "
                    "declared charges can never make the distributable "
                    "amount negative or exceed the billable amount)"
                    % (
                        distributable,
                        gross,
                        command.payload["fee_micros"],
                        command.payload["tax_micros"],
                        command.payload["adjustment_micros"],
                    ),
                )
            # exactly one allocation per billable-final usage
            # record (pre-clock: the walk gate)
            transaction = self._fold.allocations.get(command.subject_id)
            if transaction is not None:
                raise AllocationError(
                    AllocationReasonCode.ALLOCATION_ALREADY_EXISTS,
                    "usage transaction %s already carries allocation %s "
                    "(exactly one allocation per billable-final usage "
                    "record; re-allocation is a closed conflict, never "
                    "a second allocation)"
                    % (
                        command.subject_id,
                        transaction.snapshot.allocation_id,
                    ),
                )
        else:
            # the allocation-subject family: the subject must
            # already carry an allocation
            transaction = self._fold.allocations.get(command.subject_id)
            if transaction is None:
                raise AllocationError(
                    AllocationReasonCode.ALLOCATION_UNKNOWN,
                    "usage transaction %r has no allocation yet "
                    "(payment references, settlement acknowledgements, "
                    "and compensations cite an existing allocation; "
                    "only ALLOCATE creates one)" % command.subject_id,
                )
            if action == AllocationAction.ACKNOWLEDGE_SETTLEMENT:
                resolve_settlement_reference(
                    command, self._evidence_index
                )
            elif action == AllocationAction.RECORD_PAYMENT_REFERENCE:
                resolve_payment_reference(
                    command, self._evidence_index
                )
                # callback-level duplicate: the external reference
                # identity already recorded = idempotent no-op (no
                # clock read, no journal growth)
                duplicate_record_id = find_duplicate_payment_reference(
                    command, transaction
                )
                if duplicate_record_id is not None:
                    return self._duplicate_outcome(
                        command,
                        fact_id=duplicate_record_id,
                        event_id=self._find_fact_event_id(
                            duplicate_record_id
                        ),
                    )

        # 4. the deterministic event instant: exactly ONE clock
        #    read per non-duplicate submission (appended or
        #    rejected by a state gate; the read count is a pure
        #    function of the command sequence).
        instant = self._clock.now()
        validate_event_instant(instant)

        # 5. the instant-dependent gates + state gates (with the
        #    real instant)
        if action == AllocationAction.ALLOCATE:
            policy = resolve_policy(command, self._fold.policies)
            validate_policy_effective(policy, instant)
        validate_command_against_state(
            command, self._fold.allocations.get(command.subject_id)
        )

        # 6. derive the fact + identities (content-derived)
        if action == AllocationAction.REGISTER_POLICY:
            from_state = PolicySubjectState.REGISTERED
            to_state = transition_target(from_state, action)
            policy_id = derive_policy_id(
                command.subject_id,
                command.payload["adcos_share_bps"],
                command.payload["provider_min_bps"],
                command.payload["provider_max_bps"],
                command.payload["rounding_mode"],
                command.payload["currency"],
                command.payload["minor_unit_digits"],
                command.payload["effective_from"],
                command.payload["effective_until"],
            )
            policy = PolicyVersion(
                policy_id=policy_id,
                label=command.subject_id,
                adcos_share_bps=command.payload["adcos_share_bps"],
                provider_min_bps=command.payload["provider_min_bps"],
                provider_max_bps=command.payload["provider_max_bps"],
                rounding_mode=command.payload["rounding_mode"],
                currency=command.payload["currency"],
                minor_unit_digits=command.payload[
                    "minor_unit_digits"
                ],
                effective_from=command.payload["effective_from"],
                effective_until=command.payload["effective_until"],
                command_id=command.command_id,
                registered_at=instant,
            )
            fact: Mapping[str, Any] = policy.to_dict()
            fact_id: str = policy_id
        elif action == AllocationAction.ALLOCATE:
            usage_snapshot = resolve_usage_projection(
                command, self._evidence_index
            )
            policy = resolve_policy(command, self._fold.policies)
            snapshot = build_allocation_snapshot(
                usage_transaction_id=command.subject_id,
                usage_snapshot=usage_snapshot,
                policy=policy,
                provider_share_bps=command.payload[
                    "provider_share_bps"
                ],
                fee_micros=command.payload["fee_micros"],
                tax_micros=command.payload["tax_micros"],
                adjustment_micros=command.payload[
                    "adjustment_micros"
                ],
                created_at=instant,
            )
            from_state = AllocationSubjectState.PLANNED
            to_state = transition_target(from_state, action)
            fact = snapshot.to_dict()
            fact_id = snapshot.allocation_id
        elif action == AllocationAction.ACKNOWLEDGE_SETTLEMENT:
            transaction = self._fold.allocations[command.subject_id]
            from_state = transaction.state
            to_state = transition_target(from_state, action)
            acknowledgement = SettlementAcknowledgement(
                acknowledgement_id=derive_settlement_ack_id(
                    command.subject_id,
                    transaction.snapshot.allocation_id,
                    command.payload["settlement_reference"],
                    command.command_id,
                    instant,
                ),
                usage_transaction_id=command.subject_id,
                allocation_id=transaction.snapshot.allocation_id,
                settlement_reference=command.payload[
                    "settlement_reference"
                ],
                command_id=command.command_id,
                acknowledged_at=instant,
            )
            fact = acknowledgement.to_dict()
            fact_id = acknowledgement.acknowledgement_id
        elif action == AllocationAction.RECORD_PAYMENT_REFERENCE:
            transaction = self._fold.allocations[command.subject_id]
            from_state = transaction.state
            to_state = transition_target(from_state, action)
            reference_record = PaymentReferenceRecord(
                payment_reference_id=derive_payment_reference_id(
                    command.subject_id,
                    transaction.snapshot.allocation_id,
                    command.payload["payment_reference"],
                    command.command_id,
                    instant,
                ),
                usage_transaction_id=command.subject_id,
                allocation_id=transaction.snapshot.allocation_id,
                payment_reference=command.payload["payment_reference"],
                command_id=command.command_id,
                recorded_at=instant,
            )
            fact = reference_record.to_dict()
            fact_id = reference_record.payment_reference_id
        else:
            transaction = self._fold.allocations[command.subject_id]
            compensation_kind = COMPENSATION_KIND_BY_ACTION[action]
            amount_micros = (
                command.payload.get("amount_micros")
                if compensation_kind != "dispute"
                else 0
            )
            from_state = transaction.state
            to_state = transition_target(from_state, action)
            compensation = AllocationCompensationRecord(
                compensation_id=derive_compensation_id(
                    command.subject_id,
                    compensation_kind,
                    amount_micros,
                    command.payload["reason"],
                    transaction.snapshot.allocation_id,
                    command.command_id,
                    instant,
                ),
                usage_transaction_id=command.subject_id,
                compensation_kind=compensation_kind,
                amount_micros=amount_micros,
                reason=command.payload["reason"],
                allocation_id=transaction.snapshot.allocation_id,
                command_id=command.command_id,
                recorded_at=instant,
            )
            fact = compensation.to_dict()
            fact_id = compensation.compensation_id

        event_id = derive_event_id(
            command.subject_id,
            command.action,
            from_state,
            to_state,
            command.command_id,
            fact_id,
            instant,
        )
        event = AllocationEvent(
            event_id=event_id,
            subject_id=command.subject_id,
            action=command.action,
            from_state=from_state,
            to_state=to_state,
            command_id=command.command_id,
            fact=fact,
            actor=command.actor,
            source=command.source,
            instant=instant,
        )

        # 7. atomic journal append (persist-then-ack)
        prev_record_id = (
            self._journal.records()[-1].record_id
            if len(self._journal)
            else GENESIS_RECORD_ID
        )
        record = AllocationJournalRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=prev_record_id,
            command=command,
            command_digest=command.digest(),
            event=event,
        )
        self._journal.append(record)

        # 8. fold the state with the SINGLE derivation function
        #    (which also re-verifies the complete causal identity
        #    web of the record it just appended)
        self._fold = apply_record(
            self._fold, record, evidence_index=self._evidence_index
        )

        return CommandOutcome(
            status=CommandStatus.APPENDED,
            command_id=command.command_id,
            subject_id=command.subject_id,
            event_id=event_id,
            fact_id=fact_id,
            from_state=from_state,
            to_state=to_state,
            instant=instant,
        )

    # ------------------------------------------------------------------
    # The frozen typed command surface
    # ------------------------------------------------------------------

    def register_policy(
        self,
        *,
        command_id: str,
        label: str,
        adcos_share_bps: int,
        provider_min_bps: int,
        provider_max_bps: int,
        rounding_mode: str,
        currency: str,
        minor_unit_digits: int,
        effective_from: str,
        effective_until: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Register one immutable economic policy version.

        The version id is content-derived over the TERMS (the
        platform share, the developer-split constraint bounds,
        the declared rounding mode, the currency and precision,
        and the effective window): identical terms always mean
        the identical version (re-registration is the idempotent
        no-op); any term change is a genuinely new version.
        """
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.REGISTER_POLICY,
                subject_id=label,
                payload={
                    "adcos_share_bps": adcos_share_bps,
                    "provider_min_bps": provider_min_bps,
                    "provider_max_bps": provider_max_bps,
                    "rounding_mode": rounding_mode,
                    "currency": currency,
                    "minor_unit_digits": minor_unit_digits,
                    "effective_from": effective_from,
                    "effective_until": effective_until,
                },
                actor=actor,
                source=source,
            )
        )

    def allocate(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        usage_statement_id: str,
        policy_id: str,
        provider_share_bps: int,
        fee_micros: int = 0,
        tax_micros: int = 0,
        adjustment_micros: int = 0,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Consume ONE billable-final usage fact and derive the
        immutable three-way allocation snapshot.

        The ONLY allocation-creating action: it requires the
        cited usage transaction to be BILLABLE_FINAL in the
        injected W052 snapshot (payment, reservation, offer, or
        provider-callback state never creates allocation), the
        cited sealed statement to match, the cited policy version
        to be folded and effective at the deterministic instant,
        and the developer-selected provider share to lie within
        the policy's platform bounds.  The three-way split is the
        exact deterministic derivation under the policy's
        rounding mode (conservation is mechanical).
        """
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.ALLOCATE,
                subject_id=usage_transaction_id,
                payload={
                    "usage_statement_id": usage_statement_id,
                    "policy_id": policy_id,
                    "provider_share_bps": provider_share_bps,
                    "fee_micros": fee_micros,
                    "tax_micros": tax_micros,
                    "adjustment_micros": adjustment_micros,
                },
                actor=actor,
                source=source,
            )
        )

    def acknowledge_settlement(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        settlement_reference: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Record the settlement acknowledgement citing an
        external settlement reference (DATA: the reference
        identifies external movement; it is never commercial
        truth and never reprices the allocation).  The explicit
        PLANNED -> SETTLED transition; exactly once."""
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.ACKNOWLEDGE_SETTLEMENT,
                subject_id=usage_transaction_id,
                payload={
                    "settlement_reference": settlement_reference,
                },
                actor=actor,
                source=source,
            )
        )

    def record_payment_reference(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        payment_reference: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Record ONE external payment-provider callback as DATA.

        Never transitions allocation state, never creates or
        reprices allocation, never carries amounts or provider
        semantics: failed, duplicate, delayed, or out-of-order
        callbacks are idempotent or append-only DATA and cannot
        corrupt canonical allocation state."""
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.RECORD_PAYMENT_REFERENCE,
                subject_id=usage_transaction_id,
                payload={"payment_reference": payment_reference},
                actor=actor,
                source=source,
            )
        )

    def record_refund(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        amount_micros: int,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one refund compensation against the settled
        allocation (monetary; bounded by the distributable
        amount)."""
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.RECORD_REFUND,
                subject_id=usage_transaction_id,
                payload={"amount_micros": amount_micros, "reason": reason},
                actor=actor,
                source=source,
            )
        )

    def record_reversal(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        amount_micros: int,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one reversal compensation against the settled
        allocation (monetary; bounded by the distributable
        amount)."""
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.RECORD_REVERSAL,
                subject_id=usage_transaction_id,
                payload={"amount_micros": amount_micros, "reason": reason},
                actor=actor,
                source=source,
            )
        )

    def record_chargeback(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        amount_micros: int,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one chargeback compensation against the settled
        allocation (monetary; bounded by the distributable
        amount)."""
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.RECORD_CHARGEBACK,
                subject_id=usage_transaction_id,
                payload={"amount_micros": amount_micros, "reason": reason},
                actor=actor,
                source=source,
            )
        )

    def record_payout_failure(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        amount_micros: int,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one payout-failure compensation against the
        settled allocation (monetary; bounded by the distributable
        amount)."""
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.RECORD_PAYOUT_FAILURE,
                subject_id=usage_transaction_id,
                payload={"amount_micros": amount_micros, "reason": reason},
                actor=actor,
                source=source,
            )
        )

    def record_dispute(
        self,
        *,
        command_id: str,
        usage_transaction_id: str,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one dispute record against the settled
        allocation (non-monetary; one open dispute at a time;
        dispute resolution is an external settlement concern)."""
        return self._execute(
            AllocationCommand(
                command_id=command_id,
                action=AllocationAction.RECORD_DISPUTE,
                subject_id=usage_transaction_id,
                payload={"reason": reason},
                actor=actor,
                source=source,
            )
        )
