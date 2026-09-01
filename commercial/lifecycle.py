"""WORK-051 CommercialCore lifecycle manager (the public surface).

The control-plane authority for COMMERCIAL STATE ONLY (ACR-009
authority boundaries, W051 contract):

- It owns exactly one thing: the canonical commercial lifecycle
  (ConnectivityIntent .. Settled with the four compensating
  families), journaled append-only, deterministically, and
  idempotently, with every transition attributable.
- It REFERENCES logical session ids, NetworkPath ids, delivery
  evidence, usage references, settlement confirmations, and
  payment observations through an INJECTED immutable
  :class:`~commercial.references.ReferenceIndex` snapshot built
  by the caller from the authorities' PUBLIC interfaces.  It
  never queries, instantiates, or mutates a session, path,
  routing, transport, identity, policy, or payment authority
  (no authority object ever crosses this boundary; the battery
  AST-audits it).
- Payment movement is outside ADCOS/W051: payment-family
  references are recorded DATA and can never justify a delivery
  or settlement event (the family-rules table enforces it).

Determinism: the ONLY time source is the injected WORK-033
``AgentClock`` seam.  Duplicate redeliveries consume NO clock
read (an idempotent no-op); every other command submission
consumes exactly ONE clock read (the deterministic event
instant, whether the command is then appended or rejected --
the read count is a pure function of the command sequence).
All ids and digests are content-derived over WORK-003 canonical
JSON.  The fold (:func:`apply_record`, :func:`fold_state`) is
the SINGLE state-derivation function used by both the live
manager and journal replay, so live state and replayed state are
byte-identical by construction.

Fresh construction requires an EMPTY store (the W042
PlatformIntegrator precedent); :meth:`CommercialCore.load` is the
only continuation path (journal-first recovery: load, verify the
full hash chain, fold, resume).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from agent.clock import AgentClock

from .errors import CommercialError, CommercialReasonCode
from .journal import (
    AppendOnlyCommercialJournal,
    CommercialStore,
    GENESIS_RECORD_ID,
    JournalRecord,
)
from .model import (
    ACTION_TARGET_STATE,
    CommercialAction,
    CommercialCommand,
    CommercialEvent,
    CommercialState,
    CommercialTransaction,
    derive_event_id,
    derive_transaction_id,
    transition_is_legal,
)
from .references import (
    Reference,
    ReferenceFamily,
    ReferenceIndex,
    resolve_references,
)
from .validation import (
    validate_cancel_state,
    validate_command_against_transaction,
    validate_expire_due,
    validate_family_rules,
    validate_non_delivery_state,
    validate_path_failure_state,
    validate_payload_shape,
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

    ``APPENDED``: the command was admitted and its commercial
    event journaled (persist-then-ack).  ``DUPLICATE``: the exact
    command (same id AND same content digest) was already
    admitted -- an idempotent no-op; NO new journal record, NO
    clock read, NO state change; the recorded event id and the
    CURRENT projected state are returned.  Conflicting
    redeliveries (same id, different content) raise
    ``COMMAND_CONFLICT``.  Rejected commands raise typed
    CommercialError (fail closed, no journal growth).
    """

    status: str
    command_id: str
    transaction_id: str
    event_id: str
    from_state: str
    to_state: str
    instant: str

    def __post_init__(self) -> None:
        if self.status not in CommandStatus.values():
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "status %r must be one of %s"
                % (self.status, list(CommandStatus.values())),
            )
        for label in ("command_id", "transaction_id"):
            value = getattr(self, label)
            if not isinstance(value, str):
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "%s must be a string" % label,
                )
        if self.status == CommandStatus.APPENDED:
            if not self.event_id:
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "an appended outcome carries its event id",
                )
            if self.instant == "":
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "an appended outcome carries its event instant",
                )
        for label in ("from_state", "to_state"):
            value = getattr(self, label)
            if value != "" and value not in CommercialState.values():
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "%s %r is not a commercial state" % (label, value),
                )


# ---------------------------------------------------------------------------
# The single state-derivation fold (live manager AND journal replay)
# ---------------------------------------------------------------------------


def _project_initial_transaction(record: JournalRecord) -> CommercialTransaction:
    event = record.event
    command = record.command
    intent = command.payload.get("intent")
    if not isinstance(intent, Mapping):
        raise CommercialError(
            CommercialReasonCode.JOURNAL_CORRUPT,
            "submit_intent journal record carries no intent payload",
        )
    return CommercialTransaction(
        transaction_id=event.transaction_id,
        state=event.to_state,
        actor=event.actor,
        source=event.source,
        created_at=event.instant,
        intent=dict(intent),
        offer={},
        expires_at="",
        session_ref="",
        path_ref="",
        delivery_evidence_refs=(),
        usage_refs=(),
        settlement_refs=(),
        payment_refs=(),
        last_action=event.action,
        last_instant=event.instant,
        event_count=1,
    )


def apply_record(
    transaction: Optional[CommercialTransaction], record: JournalRecord
) -> CommercialTransaction:
    """Apply ONE journal record to a transaction projection.

    THE single state-derivation function: the live manager calls
    it after append; journal replay calls it in order.  It
    derives the new projection from the record's event (state,
    attribution) and the event's RESOLVED causal references
    (family-partitioned into the transaction's reference fields).
    There is no in-place mutation: a new frozen record is
    returned; terminal projections have no successor records by
    construction (the lifecycle table has no outgoing terminal
    edges, and admission never appends one).
    """
    event = record.event
    action = event.action

    if transaction is None:
        if action != CommercialAction.SUBMIT_INTENT:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "journal record for transaction %s has no creation record "
                "before action %r" % (event.transaction_id, action),
            )
        return _project_initial_transaction(record)

    if event.transaction_id != transaction.transaction_id:
        raise CommercialError(
            CommercialReasonCode.JOURNAL_CORRUPT,
            "record applied to transaction %s belongs to %s"
            % (transaction.transaction_id, event.transaction_id),
        )

    refs = event.causal_references

    def ids_of(family: str) -> Tuple[str, ...]:
        return tuple(ref.reference_id for ref in refs if ref.family == family)

    offer = transaction.offer
    expires_at = transaction.expires_at
    session_ref = transaction.session_ref
    path_ref = transaction.path_ref
    delivery_refs = transaction.delivery_evidence_refs
    usage_refs = transaction.usage_refs
    settlement_refs = transaction.settlement_refs
    payment_refs = transaction.payment_refs

    if action == CommercialAction.SELECT_OFFER:
        offer_payload = record.command.payload.get("offer")
        if not isinstance(offer_payload, Mapping):
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "select_offer journal record carries no offer payload",
            )
        offer = dict(offer_payload)
    elif action == CommercialAction.HOLD_RESERVATION:
        deadline = record.command.payload.get("expires_at")
        if not isinstance(deadline, str) or not deadline:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "hold_reservation journal record carries no deadline",
            )
        expires_at = deadline
        payment_refs = payment_refs + ids_of(ReferenceFamily.PAYMENT)
    elif action == CommercialAction.AUTHORIZE_SESSION:
        session_ids = ids_of(ReferenceFamily.SESSION)
        if len(session_ids) != 1:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "authorize_session journal record must carry exactly one "
                "session-family causal reference",
            )
        session_ref = session_ids[0]
    elif action == CommercialAction.ACTIVATE_PATH:
        path_ids = ids_of(ReferenceFamily.NETWORK_PATH)
        if len(path_ids) != 1:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "activate_path journal record must carry exactly one "
                "network-path-family causal reference",
            )
        path_ref = path_ids[0]
    elif action == CommercialAction.START_DELIVERY:
        delivery_refs = delivery_refs + ids_of(ReferenceFamily.DELIVERY_EVIDENCE)
    elif action == CommercialAction.ACCRUE_USAGE:
        usage_refs = usage_refs + ids_of(ReferenceFamily.USAGE)
    elif action == CommercialAction.COMPLETE_DELIVERY:
        delivery_refs = delivery_refs + ids_of(ReferenceFamily.DELIVERY_EVIDENCE)
    elif action == CommercialAction.INITIATE_SETTLEMENT:
        payment_refs = payment_refs + ids_of(ReferenceFamily.PAYMENT)
    elif action == CommercialAction.SETTLE:
        settlement_refs = settlement_refs + ids_of(ReferenceFamily.SETTLEMENT)
    # compensating and finalize actions carry no reference updates

    return CommercialTransaction(
        transaction_id=transaction.transaction_id,
        state=event.to_state,
        actor=transaction.actor,
        source=transaction.source,
        created_at=transaction.created_at,
        intent=transaction.intent,
        offer=offer,
        expires_at=expires_at,
        session_ref=session_ref,
        path_ref=path_ref,
        delivery_evidence_refs=delivery_refs,
        usage_refs=usage_refs,
        settlement_refs=settlement_refs,
        payment_refs=payment_refs,
        last_action=event.action,
        last_instant=event.instant,
        event_count=transaction.event_count + 1,
    )


def fold_state(
    records: Tuple[JournalRecord, ...]
) -> Dict[str, CommercialTransaction]:
    """Fold a verified journal into the commercial state.

    Deterministic: records in journal order, one apply per
    record, projections keyed by transaction id.  The live
    manager's state and this fold are byte-identical by
    construction (the same :func:`apply_record`).
    """
    state: Dict[str, CommercialTransaction] = {}
    for record in records:
        transaction = state.get(record.event.transaction_id)
        projection = apply_record(transaction, record)
        state[projection.transaction_id] = projection
    return state


# ---------------------------------------------------------------------------
# The CommercialCore public surface
# ---------------------------------------------------------------------------


class CommercialCore:
    """The commercial control-plane core (frozen public surface).

    Construct fresh over an EMPTY store; recover a persisted
    store with :meth:`load`.  Every command submission: dedup ->
    validate (fail closed) -> one clock read -> atomic journal
    append (persist-then-ack) -> fold update -> outcome.
    """

    def __init__(
        self,
        *,
        store: CommercialStore,
        clock: AgentClock,
        references: ReferenceIndex,
    ) -> None:
        if not isinstance(clock, AgentClock):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 seam)",
            )
        if not isinstance(references, ReferenceIndex):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "references must be a ReferenceIndex",
            )
        self._journal = AppendOnlyCommercialJournal(store=store)
        if len(self._journal) != 0:
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "fresh construction requires an EMPTY store; use "
                "CommercialCore.load for journal-first recovery",
            )
        self._clock = clock
        self._references = references
        self._state: Dict[str, CommercialTransaction] = {}

    @classmethod
    def load(
        cls,
        *,
        store: CommercialStore,
        clock: AgentClock,
        references: ReferenceIndex,
    ) -> "CommercialCore":
        """Journal-first recovery: load, verify the full hash
        chain, fold, resume.

        The reference index is injected fresh (the caller reads
        the CURRENT public authority state); recorded commercial
        facts are immutable, but future commands re-validate
        their references against the current index (an evicted
        delivery citation fails settlement, never silently).
        """
        core = cls.__new__(cls)
        if not isinstance(clock, AgentClock):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 seam)",
            )
        if not isinstance(references, ReferenceIndex):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "references must be a ReferenceIndex",
            )
        core._journal = AppendOnlyCommercialJournal(store=store)
        core._clock = clock
        core._references = references
        core._state = fold_state(core._journal.records())
        return core

    # -----------------------------------------------------------------
    # Reads (deterministic, no clock consumption)
    # -----------------------------------------------------------------

    def transaction(self, transaction_id: str) -> CommercialTransaction:
        transaction = self._state.get(transaction_id)
        if transaction is None:
            raise CommercialError(
                CommercialReasonCode.TRANSACTION_UNKNOWN,
                "transaction %r is not journaled" % transaction_id,
            )
        return transaction

    def transactions(self) -> Tuple[CommercialTransaction, ...]:
        return tuple(self._state[key] for key in sorted(self._state))

    def journal_records(self) -> Tuple[JournalRecord, ...]:
        return self._journal.records()

    def journal_digest(self) -> str:
        return self._journal.journal_digest()

    def tail_sequence(self) -> int:
        return self._journal.tail_sequence()

    def command_ledger(self) -> Dict[str, Dict[str, str]]:
        return self._journal.command_ledger()

    def digest_stream(self) -> str:
        """The canonical deterministic evidence document (public
        read; see :func:`commercial.digest.assemble_digest_stream`)."""
        from .digest import assemble_digest_stream

        return assemble_digest_stream(
            journal=self._journal,
            transactions=self.transactions(),
            index=self._references,
        )

    def reference_index(self) -> ReferenceIndex:
        return self._references

    def verify_integrity(self) -> None:
        """Re-verify the whole journal (chain, digests) and that
        the live state is exactly the journal fold (byte-identical
        by construction; re-derived here as tamper evidence)."""
        folded = fold_state(self._journal.records())
        if sorted(folded) != sorted(self._state):
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "live state transaction set diverges from the journal fold",
            )
        for key in sorted(folded):
            live = self._state[key]
            replayed = folded[key]
            if live.to_dict() != replayed.to_dict():
                raise CommercialError(
                    CommercialReasonCode.JOURNAL_CORRUPT,
                    "live state for %s diverges from the journal fold" % key,
                )

    # -----------------------------------------------------------------
    # Command execution (dedup -> validate -> clock -> append -> fold)
    # -----------------------------------------------------------------

    def _execute(self, command: CommercialCommand) -> CommandOutcome:
        """The single admission path (every typed method lands
        here; the generic path is deliberately NOT public -- the
        frozen typed surface is the whole API)."""
        # 1. durable idempotency: exact duplicate = no-op (no
        #    clock read, no journal growth); conflicting
        #    redelivery = fail closed.
        known = self._journal.known_command(command.command_id)
        if known is not None:
            if known["command_digest"] != command.digest():
                raise CommercialError(
                    CommercialReasonCode.COMMAND_CONFLICT,
                    "command id %r was already admitted with different "
                    "content (conflicting duplicate rejected)"
                    % command.command_id,
                )
            transaction = self._state.get(command.transaction_id)
            current_state = transaction.state if transaction else ""
            return CommandOutcome(
                status=CommandStatus.DUPLICATE,
                command_id=command.command_id,
                transaction_id=command.transaction_id,
                event_id=known["event_id"],
                from_state=current_state,
                to_state=current_state,
                instant="",
            )

        # 2. shape validation (fail closed, no journal growth)
        validate_payload_shape(command)

        # 3. resolve causal references against the injected index
        #    (fabricated citations fail closed here)
        resolved = resolve_references(self._references, command.references)

        # 4. family rules (the payment/delivery separation table)
        validate_family_rules(command.action, resolved)

        # 5. transaction existence
        if command.action == CommercialAction.SUBMIT_INTENT:
            transaction = None
            from_state = ""
        else:
            transaction = self._state.get(command.transaction_id)
            if transaction is None:
                raise CommercialError(
                    CommercialReasonCode.TRANSACTION_UNKNOWN,
                    "transaction %r is not journaled" % command.transaction_id,
                )
            from_state = transaction.state

        # 6. the deterministic event instant: exactly ONE clock
        #    read per non-duplicate submission (appended or
        #    rejected; the read count is a pure function of the
        #    command sequence).
        instant = self._clock.now()

        # 7. the state gates (with the real instant)
        if transaction is not None:
            validate_command_against_transaction(
                command, transaction, self._references, resolved, instant
            )
            if command.action == CommercialAction.CANCEL:
                validate_cancel_state(transaction)
            elif command.action == CommercialAction.EXPIRE:
                validate_expire_due(transaction, instant)
            elif command.action == CommercialAction.RECORD_PATH_FAILURE:
                validate_path_failure_state(transaction)
            elif command.action == CommercialAction.RECORD_NON_DELIVERY:
                validate_non_delivery_state(transaction)

        # 8. identities (content-derived)
        if command.action == CommercialAction.SUBMIT_INTENT:
            transaction_id = derive_transaction_id(
                command.payload["intent"], command.actor, command.source, instant
            )
            from_state = CommercialState.CONNECTIVITY_INTENT
        else:
            transaction_id = command.transaction_id

        target = ACTION_TARGET_STATE[command.action]
        if not transition_is_legal(from_state, target):
            raise CommercialError(
                CommercialReasonCode.LIFECYCLE_ILLEGAL,
                "%s from %s to %s is not in the frozen lifecycle table"
                % (command.action, from_state, target),
            )

        event_id = derive_event_id(
            transaction_id,
            command.action,
            from_state,
            target,
            command.command_id,
            instant,
        )
        event = CommercialEvent(
            event_id=event_id,
            transaction_id=transaction_id,
            action=command.action,
            from_state=from_state,
            to_state=target,
            command_id=command.command_id,
            causal_references=resolved,
            actor=command.actor,
            source=command.source,
            instant=instant,
        )

        # 9. atomic journal append (persist-then-ack)
        prev_record_id = (
            self._journal.records()[-1].record_id
            if len(self._journal)
            else GENESIS_RECORD_ID
        )
        record = JournalRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=prev_record_id,
            command=command,
            command_digest=command.digest(),
            event=event,
        )
        self._journal.append(record)

        # 10. fold the state with the SINGLE derivation function
        projection = apply_record(self._state.get(transaction_id), record)
        self._state[projection.transaction_id] = projection

        return CommandOutcome(
            status=CommandStatus.APPENDED,
            command_id=command.command_id,
            transaction_id=transaction_id,
            event_id=event_id,
            from_state=from_state,
            to_state=target,
            instant=instant,
        )

    # -----------------------------------------------------------------
    # The frozen typed command surface
    # -----------------------------------------------------------------

    def submit_intent(
        self,
        *,
        command_id: str,
        actor: str,
        source: str,
        intent: Mapping[str, Any],
    ) -> CommandOutcome:
        """Record a ConnectivityIntent (the transaction-creation
        record; the transaction identity is content-derived)."""
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.SUBMIT_INTENT,
            transaction_id="",
            references=(),
            payload={"intent": dict(intent)},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def select_offer(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        offer: Mapping[str, Any],
    ) -> CommandOutcome:
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.SELECT_OFFER,
            transaction_id=transaction_id,
            references=(),
            payload={"offer": dict(offer)},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def hold_reservation(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        expires_at: str,
        payment_refs: Tuple[str, ...] = (),
    ) -> CommandOutcome:
        """Hold the reservation, recording the deadline (DATA) and
        any payment observations as attached DATA (payment never
        implies delivery)."""
        references = tuple(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.PAYMENT,
                provenance="command-citation",
            )
            for ref in payment_refs
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.HOLD_RESERVATION,
            transaction_id=transaction_id,
            references=references,
            payload={"expires_at": expires_at},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def authorize_session(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        session_ref: str,
    ) -> CommandOutcome:
        """Authorize the commercial session against a REAL logical
        session id (WORK-012 authority-owned; referenced, never
        owned)."""
        references = (
            Reference(
                reference_id=session_ref,
                family=ReferenceFamily.SESSION,
                provenance="command-citation",
            ),
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.AUTHORIZE_SESSION,
            transaction_id=transaction_id,
            references=references,
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def activate_path(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        path_ref: str,
    ) -> CommandOutcome:
        """Activate the commercial path against a REAL NetworkPath
        id (WORK-041 authority-owned; referenced, never owned)."""
        references = (
            Reference(
                reference_id=path_ref,
                family=ReferenceFamily.NETWORK_PATH,
                provenance="command-citation",
            ),
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.ACTIVATE_PATH,
            transaction_id=transaction_id,
            references=references,
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def start_delivery(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        evidence_refs: Tuple[str, ...],
    ) -> CommandOutcome:
        """Start delivery -- ONLY real delivery-evidence citations
        may justify this (payment success never implies delivery;
        reservation never implies delivery)."""
        references = tuple(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.DELIVERY_EVIDENCE,
                provenance="command-citation",
            )
            for ref in evidence_refs
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.START_DELIVERY,
            transaction_id=transaction_id,
            references=references,
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def accrue_usage(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        usage_refs: Tuple[str, ...],
    ) -> CommandOutcome:
        """Accrue usage REFERENCES (usage metering is WORK-052;
        the core records the citations, never usage facts)."""
        references = tuple(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.USAGE,
                provenance="command-citation",
            )
            for ref in usage_refs
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.ACCRUE_USAGE,
            transaction_id=transaction_id,
            references=references,
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def complete_delivery(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        evidence_refs: Tuple[str, ...],
    ) -> CommandOutcome:
        """Complete delivery -- only real delivery-evidence
        citations (delivery facts cannot be rewritten by later
        commercial events; the core records, never manufactures)."""
        references = tuple(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.DELIVERY_EVIDENCE,
                provenance="command-citation",
            )
            for ref in evidence_refs
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.COMPLETE_DELIVERY,
            transaction_id=transaction_id,
            references=references,
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def finalize_billable(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Mark billable finality (delivery completed; usage rules
        satisfied is a commercial judgment, never a delivery
        fact)."""
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.FINALIZE_BILLABLE,
            transaction_id=transaction_id,
            references=(),
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def initiate_settlement(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        payment_refs: Tuple[str, ...] = (),
    ) -> CommandOutcome:
        """Initiate settlement (a commercial decision; attached
        payment observations are DATA and never settlement
        confirmations)."""
        references = tuple(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.PAYMENT,
                provenance="command-citation",
            )
            for ref in payment_refs
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.INITIATE_SETTLEMENT,
            transaction_id=transaction_id,
            references=references,
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def settle(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
        settlement_refs: Tuple[str, ...],
    ) -> CommandOutcome:
        """Settle -- requires a REAL settlement confirmation
        citation and the intact recorded delivery-evidence chain
        (settlement without delivery evidence fails closed;
        settlement never confuses itself with delivery)."""
        references = tuple(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.SETTLEMENT,
                provenance="command-citation",
            )
            for ref in settlement_refs
        )
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.SETTLE,
            transaction_id=transaction_id,
            references=references,
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def cancel(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Record the cancellation compensating event (pre-delivery
        states only; the historical record stays immutable)."""
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.CANCEL,
            transaction_id=transaction_id,
            references=(),
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def expire(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Record the expiry compensating event (reservation-window
        states only, deadline honestly passed; premature expiry is
        rejected)."""
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.EXPIRE,
            transaction_id=transaction_id,
            references=(),
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def record_path_failure(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Record the path-failure compensating event (path/
        delivery states only; the NetworkPath authority owns the
        failure fact -- the core records the commercial
        consequence)."""
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.RECORD_PATH_FAILURE,
            transaction_id=transaction_id,
            references=(),
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)

    def record_non_delivery(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Record the non-delivery compensating event (path/
        delivery states only; delivery facts cannot be
        manufactured -- non-delivery is their honest absence)."""
        command = CommercialCommand(
            command_id=command_id,
            action=CommercialAction.RECORD_NON_DELIVERY,
            transaction_id=transaction_id,
            references=(),
            payload={},
            actor=actor,
            source=source,
        )
        return self._execute(command)
