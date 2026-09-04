"""WORK-052 UsageLedger lifecycle manager (the public surface).

The control-plane authority for USAGE/ECONOMIC LEDGER STATE
ONLY (ACR-009 "Usage integrity", W052 contract):

- It owns exactly one thing: the usage/economic ledger -- usage
  observations derived from authoritative delivered-traffic
  evidence, the explicit billable-final transition, deterministic
  reconciliation from observed delivery to billable
  quantity/amount, and append-only compensating
  refunds/reversals/disputes -- journaled append-only,
  deterministically, and idempotently, with every fact
  attributable.
- It REFERENCES commercial transaction ids (WORK-051
  authority-owned), logical session ids (WORK-012), NetworkPath
  ids (WORK-041), and delivery-plane evidence ids through an
  INJECTED immutable :class:`~usage.evidence.UsageEvidenceIndex`
  snapshot built by the caller from the authorities' PUBLIC
  interfaces.  It never queries, instantiates, or mutates a
  session, path, routing, transport, identity, policy, payment,
  or delivery authority (no authority object ever crosses this
  boundary; the battery AST-audits it).
- Payment capture NEVER creates usage (payment-observation
  evidence is rejected by the kind table); reservation/lease
  state NEVER creates usage (delivery eligibility gate +
  reserved/attempted quantity classes are DATA only); provider
  observations are DATA, never proof of delivery.

Determinism: the ONLY time source is the injected WORK-033
``AgentClock`` seam.  Duplicate redeliveries (command-level and
evidence-window-level) consume NO clock read (idempotent
no-ops); every other command submission consumes exactly ONE
clock read (the deterministic event instant, whether the
command is then appended or rejected by a state gate -- the
read count is a pure function of the command sequence).  All
ids and digests are content-derived over WORK-003 canonical
JSON.  The fold (:func:`apply_record`, :func:`fold_state`) is
the SINGLE state-derivation AND causal-verification function
used by both the live manager and journal replay, so live state
and replayed state are byte-identical by construction, and
replay re-derives and verifies the COMPLETE causal identity web
-- every content-derived fact identity (observation, sealed
statement, compensation), the event identity, the
command/fact/attribution bindings, the walk linkage, the sealed
statement's tariff binding to the injected W051 transaction
snapshot, and the DELIVERED observations' evidence re-binding
-- so a fact mutated together with a fully recomputed outer
hash chain still fails closed ``JOURNAL_CORRUPT``.  The
per-transaction projection is sorted by observation id, so the
ECONOMIC projection (class quantities, amount, the contributing
evidence multiset, observation count, net) is arrival-order
independent for the same admitted observation set
(delayed/out-of-order observations reconcile deterministically);
the observation identities themselves are admission-attributed
(they bind the causal command and the admission instant), so
different arrival orders honestly produce different observation
ids, audit lists, and statement ids.

Fresh construction requires an EMPTY store (the W042/W051
precedent); :meth:`UsageLedger.load` is the only continuation
path (journal-first recovery: load, verify the full hash chain,
fold with full causal re-verification, resume).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from agent.clock import AgentClock

from .errors import UsageError, UsageReasonCode
from .evidence import (
    CommercialTransactionSnapshot,
    DeliveryEvidence,
    QuantityClass,
    UsageEvidenceIndex,
)
from .journal import (
    AppendOnlyUsageJournal,
    GENESIS_RECORD_ID,
    UsageJournalRecord,
    UsageStore,
)
from .model import (
    CompensationRecord,
    SealedBillableStatement,
    UsageAction,
    UsageCommand,
    UsageEvent,
    UsageObservationRecord,
    UsageTransaction,
    UsageTransactionState,
    derive_compensation_id,
    derive_event_id,
    derive_observation_id,
    derive_statement_id,
    transition_target,
    usage_transaction_digest,
)
from .validation import (
    find_duplicate_observation,
    resolve_observation_evidence,
    validate_command_against_transaction,
    validate_delivery_eligibility,
    validate_observation_instant,
    validate_observation_quantity_cap,
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

    ``APPENDED``: the command was admitted and its usage fact
    journaled (persist-then-ack).  ``DUPLICATE``: the exact
    command (same id AND same content digest) was already
    admitted -- OR a DELIVERED observation whose evidence-window
    identity was already recorded with the same derived content
    (the no-double-charge idempotency layer) -- an idempotent
    no-op; NO new journal record, NO clock read, NO state
    change; the recorded event id / observation id and the
    CURRENT projected state are returned.  Conflicting
    redeliveries (same command id, different content; or the
    same evidence-window with a different quantity) raise
    ``COMMAND_CONFLICT`` / ``EVIDENCE_MISMATCH``.  Rejected
    commands raise typed UsageError (fail closed, no journal
    growth).
    """

    status: str
    command_id: str
    transaction_id: str
    event_id: str
    fact_id: str
    from_state: str
    to_state: str
    instant: str

    def __post_init__(self) -> None:
        if self.status not in CommandStatus.values():
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "status %r must be one of %s"
                % (self.status, list(CommandStatus.values())),
            )
        if self.status == CommandStatus.APPENDED:
            if not self.event_id:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "an appended outcome carries its event id",
                )
            if not self.fact_id:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "an appended outcome carries its fact id",
                )
            if not self.instant:
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "an appended outcome carries its event instant",
                )
        for label in ("from_state", "to_state"):
            value = getattr(self, label)
            if value != "" and value not in UsageTransactionState.values():
                raise UsageError(
                    UsageReasonCode.INVALID_INPUT,
                    "%s %r is not a usage transaction state" % (label, value),
                )


# ---------------------------------------------------------------------------
# The single state-derivation fold (live manager AND journal replay)
# ---------------------------------------------------------------------------

#: The fact kind each action must carry (the action/fact table;
#: frozen with the action vocabulary).
_ACTION_FACT_KIND: Dict[str, str] = {
    UsageAction.OBSERVE_USAGE: "usage-observation-record",
    UsageAction.SEAL_BILLABLE: "sealed-billable-statement-record",
    UsageAction.RECORD_REFUND: "usage-compensation-record",
    UsageAction.RECORD_REVERSAL: "usage-compensation-record",
    UsageAction.RECORD_DISPUTE: "usage-compensation-record",
}

#: The compensation kind each compensation action produces (the
#: action/kind table; frozen with the compensation vocabulary).
_COMPENSATION_KIND_BY_ACTION: Dict[str, str] = {
    UsageAction.RECORD_REFUND: "refund",
    UsageAction.RECORD_REVERSAL: "reversal",
    UsageAction.RECORD_DISPUTE: "dispute",
}


def _corrupt(record: UsageJournalRecord, message: str) -> UsageError:
    """A fail-closed ``JOURNAL_CORRUPT`` error located at one
    journal record (the replay integrity boundary)."""
    return UsageError(
        UsageReasonCode.JOURNAL_CORRUPT,
        "journal record %d: %s" % (record.sequence, message),
    )


def _parse_fact(record: UsageJournalRecord, event: UsageEvent) -> Any:
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
        if expected_kind == "usage-observation-record":
            fact: Any = event.observation()
        elif expected_kind == "sealed-billable-statement-record":
            fact = event.statement()
        else:
            fact = event.compensation()
    except UsageError as error:
        raise _corrupt(
            record,
            "the stored %s fact is invalid: %s" % (expected_kind, error.detail),
        ) from error
    if fact is None:  # pragma: no cover - the kind gate ran above
        raise _corrupt(record, "missing %s fact" % expected_kind)
    return fact


def _verify_fact_identity(
    record: UsageJournalRecord, event: UsageEvent, fact: Any
) -> str:
    """Re-derive the content-derived fact identity from the fact's
    OWN content (the identity <-> content binding).

    ``observation_id`` / ``statement_id`` / ``compensation_id``
    are documented as content-derived fingerprints; this gate
    mechanically re-derives each one from the fact it claims to
    identify, so a fact whose content was edited without a
    fully-consistent identity cascade fails closed here.
    Returns the fact id (the event identity's fact member).
    """
    action = event.action
    if action == UsageAction.OBSERVE_USAGE:
        observation: UsageObservationRecord = fact
        expected = derive_observation_id(
            observation.command_id,
            observation.transaction_id,
            observation.quantity_class,
            observation.quantity,
            observation.evidence_id,
            observation.window_start,
            observation.window_end,
            observation.recorded_at,
        )
        if observation.observation_id != expected:
            raise _corrupt(
                record,
                "observation id %s does not match the id re-derived from "
                "its own content %s (tampered observation fact)"
                % (observation.observation_id, expected),
            )
        return observation.observation_id
    if action == UsageAction.SEAL_BILLABLE:
        statement: SealedBillableStatement = fact
        expected = derive_statement_id(
            statement.transaction_id,
            statement.contributing_observations,
            statement.sealed_at,
        )
        if statement.statement_id != expected:
            raise _corrupt(
                record,
                "statement id %s does not match the id re-derived from "
                "its own content %s (tampered sealed statement)"
                % (statement.statement_id, expected),
            )
        return statement.statement_id
    compensation: CompensationRecord = fact
    expected = derive_compensation_id(
        compensation.transaction_id,
        compensation.compensation_kind,
        compensation.amount_micros,
        compensation.reason,
        compensation.statement_id,
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
    record: UsageJournalRecord, event: UsageEvent, fact_id: str
) -> None:
    """Re-derive the event id from the event's own content + the
    fact's identity (the event identity <-> content binding).

    The event id binds the full attribution + walk edge + the
    causal command + the fact identity + the instant; a fact or
    event edited with a recomputed outer record chain but an
    un-cascaded event id fails closed here.
    """
    expected = derive_event_id(
        event.transaction_id,
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


def _verify_observation_causality(
    record: UsageJournalRecord,
    transaction: Optional[UsageTransaction],
    observation: UsageObservationRecord,
    evidence_index: UsageEvidenceIndex,
) -> None:
    """The command -> observation causal binding + the
    authoritative evidence re-binding (replay integrity).

    The observation fact must be EXACTLY the deterministic
    derivation of its causal command (payload members, event
    instant, attribution); and a DELIVERED observation's evidence
    citation must re-resolve against the injected index (kind
    table, correlation, window, static and cumulative quantity
    bounds) exactly as admission required -- the journal cannot
    contain an observation admission would have rejected or
    de-duplicated.
    """
    command = record.command
    event = record.event
    payload = command.payload
    expected_observation_id = derive_observation_id(
        command.command_id,
        command.transaction_id,
        payload.get("quantity_class"),
        payload.get("quantity"),
        payload.get("evidence_id"),
        payload.get("window_start"),
        payload.get("window_end"),
        event.instant,
    )
    expected: Dict[str, Any] = {
        "kind": "usage-observation-record",
        "observation_id": expected_observation_id,
        "command_id": command.command_id,
        "transaction_id": command.transaction_id,
        "quantity_class": payload.get("quantity_class"),
        "quantity": payload.get("quantity"),
        "recorded_at": event.instant,
        "actor": command.actor,
        "source": command.source,
    }
    if payload.get("evidence_id") is not None:
        expected["evidence_id"] = payload.get("evidence_id")
        expected["window_start"] = payload.get("window_start")
        expected["window_end"] = payload.get("window_end")
    if observation.to_dict() != expected:
        raise _corrupt(
            record,
            "the observation fact is not the deterministic derivation of "
            "its causal command (fact/content or attribution divergence; "
            "a mutated fact with recomputed identities but an untouched "
            "command fails here)",
        )
    if observation.quantity_class == QuantityClass.DELIVERED:
        try:
            evidence = resolve_observation_evidence(command, evidence_index)
        except UsageError as error:
            raise _corrupt(
                record,
                "the DELIVERED observation's evidence citation does not "
                "resolve against the injected index at replay: %s"
                % error.detail,
            ) from error
        try:
            validate_observation_quantity_cap(command, evidence, transaction)
        except UsageError as error:
            raise _corrupt(
                record,
                "the DELIVERED observation exceeds the authoritative "
                "evidence quantity at replay: %s" % error.detail,
            ) from error
        if transaction is not None:
            for existing in transaction.observations:
                if (
                    existing.evidence_id == observation.evidence_id
                    and (
                        existing.window_start,
                        existing.window_end,
                    )
                    == (observation.window_start, observation.window_end)
                ):
                    raise _corrupt(
                        record,
                        "duplicate evidence-window identity %s in the "
                        "journal (admission de-duplicates evidence-window "
                        "redelivery; the journal cannot carry both)"
                        % observation.evidence_id,
                    )


def _expected_statement(
    record: UsageJournalRecord,
    event: UsageEvent,
    transaction: Optional[UsageTransaction],
    evidence_index: UsageEvidenceIndex,
) -> SealedBillableStatement:
    """Re-derive the ENTIRE sealed statement from the folded
    observation history, the event instant, and the injected W051
    transaction snapshot (the tariff re-binding).

    The sealed billable fact must be exactly: the folded
    class-distinguished quantities, the sorted contributing
    observation/evidence audit lists, and the authoritative tariff
    (unit price, billable unit, provenance) with the exact integer
    amount ``billable_quantity * unit_price_micros`` -- so a
    tampered statement that is internally arithmetic-consistent
    but carries a different price, unit, provenance, audit list,
    or quantity still fails closed at replay (an outer hash chain
    cannot reprice the billable fact).
    """
    try:
        snapshot = evidence_index.transaction(event.transaction_id)
    except UsageError as error:
        raise _corrupt(
            record,
            "the sealed statement cites a transaction unresolvable in the "
            "injected W051 authority at replay: %s" % error.detail,
        ) from error
    observations = (
        transaction.observations if transaction is not None else ()
    )
    if transaction is None:
        quantities = {
            QuantityClass.RESERVED: 0,
            QuantityClass.ATTEMPTED: 0,
            QuantityClass.DELIVERED: 0,
        }
    else:
        quantities = transaction.quantities()
    delivered_ids = tuple(
        sorted(
            observation.observation_id
            for observation in observations
            if observation.is_billable()
        )
    )
    evidence_ids = tuple(
        sorted(
            observation.evidence_id
            for observation in observations
            if observation.evidence_id is not None
        )
    )
    billable_quantity = quantities[QuantityClass.DELIVERED]
    return SealedBillableStatement(
        statement_id=derive_statement_id(
            event.transaction_id, delivered_ids, event.instant
        ),
        transaction_id=event.transaction_id,
        reserved_quantity=quantities[QuantityClass.RESERVED],
        attempted_quantity=quantities[QuantityClass.ATTEMPTED],
        delivered_quantity=billable_quantity,
        billable_quantity=billable_quantity,
        unit_price_micros=snapshot.unit_price_micros,
        amount_micros=billable_quantity * snapshot.unit_price_micros,
        billable_unit=snapshot.billable_unit,
        tariff_provenance=snapshot.tariff_provenance,
        contributing_observations=delivered_ids,
        contributing_evidence=evidence_ids,
        sealed_at=event.instant,
    )


def _expected_compensation_dict(
    record: UsageJournalRecord,
    event: UsageEvent,
    statement_id: str,
) -> Dict[str, Any]:
    """Re-derive the compensation fact from its causal command,
    the folded sealed statement, and the event instant (the
    command -> compensation binding)."""
    command = record.command
    compensation_kind = _COMPENSATION_KIND_BY_ACTION[command.action]
    amount_micros = (
        command.payload.get("amount_micros")
        if compensation_kind != "dispute"
        else 0
    )
    return {
        "kind": "usage-compensation-record",
        "compensation_id": derive_compensation_id(
            command.transaction_id,
            compensation_kind,
            amount_micros,
            command.payload.get("reason"),
            statement_id,
            command.command_id,
            event.instant,
        ),
        "transaction_id": command.transaction_id,
        "compensation_kind": compensation_kind,
        "amount_micros": amount_micros,
        "reason": command.payload.get("reason"),
        "statement_id": statement_id,
        "command_id": command.command_id,
        "recorded_at": event.instant,
    }


def apply_record(
    transaction: Optional[UsageTransaction],
    record: UsageJournalRecord,
    *,
    evidence_index: UsageEvidenceIndex,
) -> UsageTransaction:
    """Apply ONE journal record to a transaction projection.

    THE single state-derivation function: the live manager calls
    it after append; journal replay calls it in order.  It is also
    THE single causal-verification function (the replay
    integrity boundary).  Before folding, every record is
    verified against its COMPLETE causal identity web:

    - the event attribution must equal the admitted command's
      attribution (actor/source);
    - the fact kind must match the action (the action/fact
      table);
    - the content-derived fact identity
      (``observation_id`` / ``statement_id`` /
      ``compensation_id``) must re-derive from the fact's OWN
      content;
    - the event id must re-derive from the event's content and
      the fact's identity;
    - the walk linkage (the event's declared predecessor state
      MUST be the folded current state -- the replay verifies
      the WALK, not merely the chain and each edge) and the
      frozen transition table;
    - the fact must be EXACTLY the deterministic derivation of
      its causal command, the folded state, and the event
      instant -- and, for the sealed statement, of the injected
      W051 transaction snapshot (tariff price/unit/provenance
      and the exact amount), and, for DELIVERED observations, of
      the authoritative evidence citation re-resolved against
      the injected index (kind, correlation, window, quantity
      bounds); compensations must cite the folded sealed
      statement and stay bounded (net never negative; one open
      dispute).

    A modified fact therefore cannot be made chain-valid merely
    by recomputing the outer record id/hash chain: every
    mismatch fails closed ``JOURNAL_CORRUPT``.  The projection
    is returned as a NEW frozen record (no in-place mutation;
    the observations are re-sorted by observation id so the
    economic fold is arrival-order independent).
    """
    event = record.event
    command = record.command
    action = event.action

    # --- attribution binding (event == admitted command) ---
    if event.actor != command.actor or event.source != command.source:
        raise _corrupt(
            record,
            "event attribution (actor %r, source %r) does not match the "
            "admitted command's attribution (actor %r, source %r)"
            % (event.actor, event.source, command.actor, command.source),
        )

    # --- fact extraction + identity <-> content bindings ---
    fact = _parse_fact(record, event)
    fact_id = _verify_fact_identity(record, event, fact)
    _verify_event_identity(record, event, fact_id)

    if transaction is None:
        if action == UsageAction.OBSERVE_USAGE:
            observation: UsageObservationRecord = fact
            _verify_observation_causality(
                record, transaction, observation, evidence_index
            )
            if (
                event.from_state != UsageTransactionState.OBSERVING
                or event.to_state != UsageTransactionState.OBSERVING
            ):
                raise _corrupt(
                    record,
                    "the creation record must be the OBSERVING self-edge "
                    "(found %s -> %s)" % (event.from_state, event.to_state),
                )
            observations = tuple(
                sorted((observation,), key=lambda obs: obs.observation_id)
            )
            return UsageTransaction(
                transaction_id=event.transaction_id,
                state=event.to_state,
                observations=observations,
            )
        if action == UsageAction.SEAL_BILLABLE:
            # the explicit zero-observation seal (an honest zero bill:
            # a delivery-eligible transaction with no recorded usage
            # seals to quantity 0 / amount 0, priced by the snapshot
            # tariff like every other seal)
            statement: SealedBillableStatement = fact
            expected_statement = _expected_statement(
                record, event, None, evidence_index
            )
            if statement.to_dict() != expected_statement.to_dict():
                raise _corrupt(
                    record,
                    "the zero-observation creation seal is not the "
                    "deterministic derivation of an empty observation "
                    "history and the injected W051 tariff snapshot "
                    "(quantities, audit lists, tariff, or amount diverge)",
                )
            if (
                event.from_state != UsageTransactionState.OBSERVING
                or event.to_state != UsageTransactionState.BILLABLE_FINAL
            ):
                raise _corrupt(
                    record,
                    "the zero-observation creation seal must be the "
                    "OBSERVING -> BILLABLE_FINAL edge (found %s -> %s)"
                    % (event.from_state, event.to_state),
                )
            return UsageTransaction(
                transaction_id=event.transaction_id,
                state=event.to_state,
                observations=(),
                statement=statement,
            )
        raise _corrupt(
            record,
            "journal record for transaction %s has no usage history before "
            "action %r (usage transactions are created by observations or "
            "the zero-observation seal only)" % (event.transaction_id, action),
        )

    if event.transaction_id != transaction.transaction_id:
        raise _corrupt(
            record,
            "record applied to transaction %s belongs to %s"
            % (transaction.transaction_id, event.transaction_id),
        )

    # Walk-linkage verification (fail closed): the event's declared
    # predecessor state MUST be the folded current state.  Honest
    # journals are contiguous walks by construction (admission emits
    # from_state = the live transaction state), so this rejects only
    # out-of-order, inserted, or forged records whose event declares a
    # table-legal edge that does not connect to the actual walk.
    if event.from_state != transaction.state:
        raise _corrupt(
            record,
            "journal record for transaction %s declares from_state %s but "
            "the folded state is %s (out-of-order or inserted record; the "
            "replay walk must be contiguous)"
            % (event.transaction_id, event.from_state, transaction.state),
        )
    if transition_target(event.from_state, action) != event.to_state:
        raise _corrupt(
            record,
            "journal record for transaction %s declares %s -> %s via %s "
            "which is not a frozen-table transition"
            % (
                event.transaction_id,
                event.from_state,
                event.to_state,
                action,
            ),
        )

    if action == UsageAction.OBSERVE_USAGE:
        observation = fact
        _verify_observation_causality(
            record, transaction, observation, evidence_index
        )
        observations = tuple(
            sorted(
                transaction.observations + (observation,),
                key=lambda obs: obs.observation_id,
            )
        )
        return UsageTransaction(
            transaction_id=transaction.transaction_id,
            state=event.to_state,
            observations=observations,
            compensations=transaction.compensations,
        )

    if action == UsageAction.SEAL_BILLABLE:
        statement = fact
        expected_statement = _expected_statement(
            record, event, transaction, evidence_index
        )
        if statement.to_dict() != expected_statement.to_dict():
            raise _corrupt(
                record,
                "the sealed statement is not the deterministic derivation "
                "of the folded observation history and the injected W051 "
                "tariff snapshot (quantities, audit lists, tariff "
                "price/unit/provenance, or the exact amount diverge; a "
                "recomputed outer chain cannot reprice the billable fact)",
            )
        return UsageTransaction(
            transaction_id=transaction.transaction_id,
            state=event.to_state,
            observations=transaction.observations,
            statement=statement,
            compensations=transaction.compensations,
        )

    # the compensation family
    compensation: CompensationRecord = fact
    if transaction.statement is None:
        raise _corrupt(
            record,
            "%s journal record arrives with no folded sealed statement "
            "(compensations append against finality)" % action,
        )
    expected_compensation = _expected_compensation_dict(
        record, event, transaction.statement.statement_id
    )
    if compensation.to_dict() != expected_compensation:
        raise _corrupt(
            record,
            "the compensation fact is not the deterministic derivation of "
            "its causal command and the folded sealed statement (amount, "
            "reason, kind, citation, or attribution divergence)",
        )
    compensation_kind = expected_compensation["compensation_kind"]
    if compensation_kind in ("refund", "reversal"):
        cumulative = (
            transaction.refunded_amount_micros()
            + transaction.reversed_amount_micros()
        )
        if (
            cumulative + expected_compensation["amount_micros"]
            > transaction.statement.amount_micros
        ):
            raise _corrupt(
                record,
                "the journaled compensation exceeds the sealed amount at "
                "replay (the journal cannot contain an over-compensation "
                "admission would have rejected; the net never goes "
                "negative)",
            )
    if compensation_kind == "dispute" and transaction.disputed():
        raise _corrupt(
            record,
            "a second dispute record in the journal (admission would have "
            "rejected it; one open dispute per transaction)",
        )
    compensations = tuple(
        sorted(
            transaction.compensations + (compensation,),
            key=lambda record_: record_.compensation_id,
        )
    )
    return UsageTransaction(
        transaction_id=transaction.transaction_id,
        state=event.to_state,
        observations=transaction.observations,
        statement=transaction.statement,
        compensations=compensations,
    )


def fold_state(
    records: Tuple[UsageJournalRecord, ...],
    *,
    evidence_index: UsageEvidenceIndex,
) -> Dict[str, UsageTransaction]:
    """Fold a verified journal into the usage state.

    Deterministic: records in journal order, one apply per
    record, projections keyed by transaction id.  The live
    manager's state and this fold are byte-identical by
    construction (the same :func:`apply_record`), and the fold is
    where replay re-derives and verifies the complete causal
    identity web of every record (fact identities, event
    identities, command/fact/attribution bindings, walk
    linkage, the W051 tariff/evidence re-binding) -- all
    fail-closed ``JOURNAL_CORRUPT``.
    """
    state: Dict[str, UsageTransaction] = {}
    for record in records:
        transaction = state.get(record.event.transaction_id)
        projection = apply_record(
            transaction, record, evidence_index=evidence_index
        )
        state[projection.transaction_id] = projection
    return state


# ---------------------------------------------------------------------------
# The UsageLedger public surface
# ---------------------------------------------------------------------------


class UsageLedger:
    """The usage/economic ledger (frozen public surface).

    Construct fresh over an EMPTY store; recover a persisted
    store with :meth:`load`.  Every command submission: dedup
    (command id, then evidence-window identity) -> shape/index
    validation -> ONE clock read -> state gates -> atomic
    journal append (persist-then-ack) -> fold.
    """

    def __init__(
        self,
        *,
        store: UsageStore,
        clock: AgentClock,
        evidence_index: UsageEvidenceIndex,
    ) -> None:
        if not isinstance(store, UsageStore):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "store must be a UsageStore",
            )
        if not isinstance(clock, AgentClock):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 seam)",
            )
        if not isinstance(evidence_index, UsageEvidenceIndex):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "evidence_index must be a UsageEvidenceIndex (built from "
                "the authorities' public surfaces by the caller)",
            )
        self._journal = AppendOnlyUsageJournal(store=store)
        if len(self._journal) != 0:
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "fresh construction requires an EMPTY store (recover a "
                "persisted ledger with UsageLedger.load)",
            )
        self._clock = clock
        self._evidence_index = evidence_index
        self._state: Dict[str, UsageTransaction] = {}

    @classmethod
    def load(
        cls,
        *,
        store: UsageStore,
        clock: AgentClock,
        evidence_index: UsageEvidenceIndex,
    ) -> "UsageLedger":
        """Journal-first recovery: load, verify the full hash
        chain, fold, resume (the only continuation path)."""
        if not isinstance(store, UsageStore):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "store must be a UsageStore",
            )
        if not isinstance(clock, AgentClock):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 seam)",
            )
        if not isinstance(evidence_index, UsageEvidenceIndex):
            raise UsageError(
                UsageReasonCode.INVALID_INPUT,
                "evidence_index must be a UsageEvidenceIndex",
            )
        ledger = cls.__new__(cls)
        ledger._journal = AppendOnlyUsageJournal(store=store)
        ledger._clock = clock
        ledger._evidence_index = evidence_index
        ledger._state = fold_state(
            ledger._journal.records(), evidence_index=evidence_index
        )
        return ledger

    # ------------------------------------------------------------------
    # Reads (deterministic, no clock consumption)
    # ------------------------------------------------------------------

    def evidence_index(self) -> UsageEvidenceIndex:
        return self._evidence_index

    def transaction(self, transaction_id: str) -> UsageTransaction:
        projection = self._state.get(transaction_id)
        if projection is None:
            raise UsageError(
                UsageReasonCode.TRANSACTION_UNKNOWN,
                "usage transaction %r has no journaled observations"
                % transaction_id,
            )
        return projection

    def transactions(self) -> Tuple[UsageTransaction, ...]:
        return tuple(self._state[key] for key in sorted(self._state))

    def usage_record_ids(self) -> Tuple[str, ...]:
        """Every admitted DELIVERED usage observation id (sorted)."""
        ids: List[str] = []
        for projection in self._state.values():
            ids.extend(projection.delivered_observation_ids())
        return tuple(sorted(ids))

    def command_ledger(self) -> Dict[str, Dict[str, str]]:
        return self._journal.command_ledger()

    def journal_records(self) -> Tuple[UsageJournalRecord, ...]:
        return self._journal.records()

    def journal_digest(self) -> str:
        return self._journal.journal_digest()

    def digest_stream(self) -> str:
        """The canonical deterministic evidence document (journal,
        state, command ledger, event list, evidence index digests
        in one canonical JSON document; the two-run and hash-seed
        determinism proofs bind to this)."""
        from .digest import assemble_digest_stream

        return assemble_digest_stream(
            journal=self._journal,
            transactions=self._state.values(),
            index=self._evidence_index,
        )

    def state_digest(self) -> str:
        from .digest import state_digest

        return state_digest(self._state.values())

    def reconciliation_statement(self, transaction_id: str) -> Dict[str, Any]:
        """The deterministic reconciliation statement: observed
        delivery -> billable quantity/amount -> compensations ->
        net, with the full audit trail (contributing observation
        ids, evidence ids, compensation ids, and digests).

        A pure deterministic READ (no journal growth, no clock
        consumption): byte-identical across re-reads, restarts,
        and replay.  Distinguishes the ACR-009 quantity classes:
        reserved, attempted, delivered, billable, disputed,
        refunded, reversed.
        """
        projection = self.transaction(transaction_id)
        quantities = projection.quantities()
        statement: Dict[str, Any] = {
            "kind": "usage-reconciliation-statement",
            "transaction_id": transaction_id,
            "usage_state": projection.state,
            "reserved_quantity": quantities[QuantityClass.RESERVED],
            "attempted_quantity": quantities[QuantityClass.ATTEMPTED],
            "delivered_quantity": quantities[QuantityClass.DELIVERED],
            "observation_count": len(projection.observations),
        }
        if projection.statement is not None:
            sealed = projection.statement
            statement.update(
                {
                    "billable_quantity": sealed.billable_quantity,
                    "unit_price_micros": sealed.unit_price_micros,
                    "billable_unit": sealed.billable_unit,
                    "gross_amount_micros": sealed.amount_micros,
                    "statement_id": sealed.statement_id,
                    "tariff_provenance": sealed.tariff_provenance,
                    "contributing_observations": list(
                        sealed.contributing_observations
                    ),
                    "contributing_evidence": list(sealed.contributing_evidence),
                    "sealed_at": sealed.sealed_at,
                }
            )
        else:
            statement.update(
                {
                    "billable_quantity": 0,
                    "unit_price_micros": (
                        self._evidence_index.transaction(transaction_id).unit_price_micros
                        if self._evidence_index.contains_transaction(transaction_id)
                        else -1
                    ),
                    "gross_amount_micros": 0,
                    "statement_id": "",
                }
            )
        statement.update(
            {
                "refunded_amount_micros": projection.refunded_amount_micros(),
                "reversed_amount_micros": projection.reversed_amount_micros(),
                "refunded_quantity": projection.refunded_quantity(),
                "reversed_quantity": projection.reversed_quantity(),
                "disputed": projection.disputed(),
                "net_amount_micros": projection.net_amount_micros(),
                "compensation_ids": [
                    compensation.compensation_id
                    for compensation in projection.compensations
                ],
                "projection_digest": usage_transaction_digest(projection),
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
        if sorted(folded) != sorted(self._state):
            raise UsageError(
                UsageReasonCode.JOURNAL_CORRUPT,
                "live state transaction set diverges from the journal fold",
            )
        for key in sorted(self._state):
            live = self._state[key].to_dict()
            replayed = folded[key].to_dict()
            if live != replayed:
                raise UsageError(
                    UsageReasonCode.JOURNAL_CORRUPT,
                    "live state for %s diverges from the journal fold" % key,
                )

    # ------------------------------------------------------------------
    # Command execution (dedup -> validate -> clock -> append -> fold)
    # ------------------------------------------------------------------

    def _execute(self, command: UsageCommand) -> CommandOutcome:
        """The single admission path (every typed method lands
        here; the generic path is deliberately NOT public -- the
        frozen typed surface is the whole API)."""
        # 1. durable idempotency: exact duplicate = no-op (no
        #    clock read, no journal growth); conflicting
        #    redelivery = fail closed.
        known = self._journal.known_command(command.command_id)
        if known is not None:
            if known["command_digest"] != command.digest():
                raise UsageError(
                    UsageReasonCode.COMMAND_CONFLICT,
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
                fact_id="",
                from_state=current_state,
                to_state=current_state,
                instant="",
            )

        # 2. shape validation (fail closed, no journal growth)
        validate_payload_shape(command)

        # 3. transaction snapshot resolution against the injected
        #    index (fabricated citations fail closed here)
        snapshot = self._evidence_index.transaction(command.transaction_id)

        # 4. evidence resolution + kind gates (the
        #    payment/provider/delivery separation) + static
        #    window/quantity bounds (no clock consumption)
        evidence = resolve_observation_evidence(command, self._evidence_index)

        # 5. delivery eligibility (usage requires an
        #    already-authorized delivery path; reservation/lease
        #    never creates usage) -- static, index-derived
        validate_delivery_eligibility(command, snapshot)

        # 6. evidence-level duplicate detection (the
        #    no-double-charge idempotency layer; a duplicate is
        #    a no-op with NO clock read; a conflicting
        #    evidence-window reuse fails closed).  The duplicate
        #    observation is recorded in an EARLIER command's
        #    event; its event id is recovered deterministically.
        transaction = self._state.get(command.transaction_id)
        duplicate_observation_id = find_duplicate_observation(command, transaction)
        if duplicate_observation_id is not None:
            current_state = transaction.state if transaction else ""
            event_id = ""
            for record in self._journal.records():
                observation = record.event.observation()
                if (
                    observation is not None
                    and observation.observation_id == duplicate_observation_id
                ):
                    event_id = record.event.event_id
                    break
            return CommandOutcome(
                status=CommandStatus.DUPLICATE,
                command_id=command.command_id,
                transaction_id=command.transaction_id,
                event_id=event_id,
                fact_id=duplicate_observation_id,
                from_state=current_state,
                to_state=current_state,
                instant="",
            )

        # 7. the cumulative per-evidence cap (no double charge
        #    from windowed sub-metering; no clock consumption)
        validate_observation_quantity_cap(command, evidence, transaction)

        # 8. the deterministic event instant: exactly ONE clock
        #    read per non-duplicate submission (appended or
        #    rejected by a state gate; the read count is a pure
        #    function of the command sequence).
        instant = self._clock.now()
        validate_observation_instant(command, evidence, instant)

        # 9. the state gates (with the real instant)
        validate_command_against_transaction(command, transaction)

        # 10. derive the fact + identities (content-derived)
        from_state = (
            transaction.state if transaction else UsageTransactionState.OBSERVING
        )
        to_state = transition_target(from_state, command.action)
        fact: Mapping[str, Any]
        fact_id: str
        if command.action == UsageAction.OBSERVE_USAGE:
            quantity_class = command.payload["quantity_class"]
            if quantity_class == QuantityClass.DELIVERED:
                assert evidence is not None
                observation_id = derive_observation_id(
                    command.command_id,
                    command.transaction_id,
                    quantity_class,
                    command.payload["quantity"],
                    command.payload["evidence_id"],
                    command.payload["window_start"],
                    command.payload["window_end"],
                    instant,
                )
                observation = UsageObservationRecord(
                    observation_id=observation_id,
                    command_id=command.command_id,
                    transaction_id=command.transaction_id,
                    quantity_class=quantity_class,
                    quantity=command.payload["quantity"],
                    recorded_at=instant,
                    evidence_id=command.payload["evidence_id"],
                    window_start=command.payload["window_start"],
                    window_end=command.payload["window_end"],
                    actor=command.actor,
                    source=command.source,
                )
            else:
                observation_id = derive_observation_id(
                    command.command_id,
                    command.transaction_id,
                    quantity_class,
                    command.payload["quantity"],
                    None,
                    None,
                    None,
                    instant,
                )
                observation = UsageObservationRecord(
                    observation_id=observation_id,
                    command_id=command.command_id,
                    transaction_id=command.transaction_id,
                    quantity_class=quantity_class,
                    quantity=command.payload["quantity"],
                    recorded_at=instant,
                    actor=command.actor,
                    source=command.source,
                )
            fact = observation.to_dict()
            fact_id = observation_id
        elif command.action == UsageAction.SEAL_BILLABLE:
            quantities = transaction.quantities() if transaction else {
                QuantityClass.RESERVED: 0,
                QuantityClass.ATTEMPTED: 0,
                QuantityClass.DELIVERED: 0,
            }
            delivered_ids = tuple(
                sorted(
                    transaction.delivered_observation_ids()
                    if transaction
                    else ()
                )
            )
            evidence_ids = tuple(
                sorted(
                    observation.evidence_id
                    for observation in (
                        transaction.observations if transaction else ()
                    )
                    if observation.evidence_id is not None
                )
            )
            statement_id = derive_statement_id(
                command.transaction_id, delivered_ids, instant
            )
            billable_quantity = quantities[QuantityClass.DELIVERED]
            statement = SealedBillableStatement(
                statement_id=statement_id,
                transaction_id=command.transaction_id,
                reserved_quantity=quantities[QuantityClass.RESERVED],
                attempted_quantity=quantities[QuantityClass.ATTEMPTED],
                delivered_quantity=billable_quantity,
                billable_quantity=billable_quantity,
                unit_price_micros=snapshot.unit_price_micros,
                amount_micros=billable_quantity * snapshot.unit_price_micros,
                billable_unit=snapshot.billable_unit,
                tariff_provenance=snapshot.tariff_provenance,
                contributing_observations=delivered_ids,
                contributing_evidence=evidence_ids,
                sealed_at=instant,
            )
            fact = statement.to_dict()
            fact_id = statement_id
        else:
            compensation_kind = {
                UsageAction.RECORD_REFUND: "refund",
                UsageAction.RECORD_REVERSAL: "reversal",
                UsageAction.RECORD_DISPUTE: "dispute",
            }[command.action]
            amount_micros = (
                command.payload.get("amount_micros", 0)
                if compensation_kind != "dispute"
                else 0
            )
            assert transaction is not None and transaction.statement is not None
            compensation_id = derive_compensation_id(
                command.transaction_id,
                compensation_kind,
                amount_micros,
                command.payload["reason"],
                transaction.statement.statement_id,
                command.command_id,
                instant,
            )
            compensation = CompensationRecord(
                compensation_id=compensation_id,
                transaction_id=command.transaction_id,
                compensation_kind=compensation_kind,
                amount_micros=amount_micros,
                reason=command.payload["reason"],
                statement_id=transaction.statement.statement_id,
                command_id=command.command_id,
                recorded_at=instant,
            )
            fact = compensation.to_dict()
            fact_id = compensation_id

        event_id = derive_event_id(
            command.transaction_id,
            command.action,
            from_state,
            to_state,
            command.command_id,
            fact_id,
            instant,
        )
        event = UsageEvent(
            event_id=event_id,
            transaction_id=command.transaction_id,
            action=command.action,
            from_state=from_state,
            to_state=to_state,
            command_id=command.command_id,
            fact=fact,
            actor=command.actor,
            source=command.source,
            instant=instant,
        )

        # 11. atomic journal append (persist-then-ack)
        prev_record_id = (
            self._journal.records()[-1].record_id
            if len(self._journal)
            else GENESIS_RECORD_ID
        )
        record = UsageJournalRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=prev_record_id,
            command=command,
            command_digest=command.digest(),
            event=event,
        )
        self._journal.append(record)

        # 12. fold the state with the SINGLE derivation function
        #     (which also re-verifies the complete causal identity
        #     web of the record it just appended)
        projection = apply_record(
            self._state.get(command.transaction_id),
            record,
            evidence_index=self._evidence_index,
        )
        self._state[projection.transaction_id] = projection

        return CommandOutcome(
            status=CommandStatus.APPENDED,
            command_id=command.command_id,
            transaction_id=command.transaction_id,
            event_id=event_id,
            fact_id=fact_id,
            from_state=from_state,
            to_state=to_state,
            instant=instant,
        )

    # ------------------------------------------------------------------
    # The frozen typed command surface
    # ------------------------------------------------------------------

    def observe_usage(
        self,
        *,
        command_id: str,
        transaction_id: str,
        quantity_class: str,
        quantity: int,
        evidence_id: Optional[str] = None,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Ingest one usage observation.

        DELIVERED-class observations require the authoritative
        delivery-evidence citation (evidence_id + window) and
        create billable usage; RESERVED/ATTEMPTED-class
        observations are DATA for reconciliation only (they must
        NOT cite delivery evidence and never create usage).
        """
        payload: Dict[str, Any] = {
            "quantity_class": quantity_class,
            "quantity": quantity,
        }
        if evidence_id is not None:
            payload["evidence_id"] = evidence_id
        if window_start is not None:
            payload["window_start"] = window_start
        if window_end is not None:
            payload["window_end"] = window_end
        return self._execute(
            UsageCommand(
                command_id=command_id,
                action=UsageAction.OBSERVE_USAGE,
                transaction_id=transaction_id,
                payload=payload,
                actor=actor,
                source=source,
            )
        )

    def seal_billable(
        self,
        *,
        command_id: str,
        transaction_id: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """The explicit billable-final transition: derive the
        sealed statement (billable quantity, amount, audit trail)
        from the recorded delivered observations and the cited
        tariff, and freeze the transaction against further
        observations (corrections are append-only compensating
        records)."""
        return self._execute(
            UsageCommand(
                command_id=command_id,
                action=UsageAction.SEAL_BILLABLE,
                transaction_id=transaction_id,
                payload={},
                actor=actor,
                source=source,
            )
        )

    def record_refund(
        self,
        *,
        command_id: str,
        transaction_id: str,
        amount_micros: int,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one refund compensation against the sealed
        statement (monetary; bounded by the sealed amount)."""
        return self._execute(
            UsageCommand(
                command_id=command_id,
                action=UsageAction.RECORD_REFUND,
                transaction_id=transaction_id,
                payload={"amount_micros": amount_micros, "reason": reason},
                actor=actor,
                source=source,
            )
        )

    def record_reversal(
        self,
        *,
        command_id: str,
        transaction_id: str,
        amount_micros: int,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one reversal compensation against the sealed
        statement (monetary; bounded by the sealed amount)."""
        return self._execute(
            UsageCommand(
                command_id=command_id,
                action=UsageAction.RECORD_REVERSAL,
                transaction_id=transaction_id,
                payload={"amount_micros": amount_micros, "reason": reason},
                actor=actor,
                source=source,
            )
        )

    def record_dispute(
        self,
        *,
        command_id: str,
        transaction_id: str,
        reason: str,
        actor: str,
        source: str,
    ) -> CommandOutcome:
        """Append one dispute record against the sealed
        statement (non-monetary; one open dispute at a time;
        dispute resolution is a settlement-layer concern)."""
        return self._execute(
            UsageCommand(
                command_id=command_id,
                action=UsageAction.RECORD_DISPUTE,
                transaction_id=transaction_id,
                payload={"reason": reason},
                actor=actor,
                source=source,
            )
        )
