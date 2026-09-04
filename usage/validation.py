"""WORK-052 UsageLedger command admission rules.

Fail-closed admission gates, mirroring the accepted W051
validation discipline (the family-rules-table pattern):

- **strict payload shape**: each action carries an exact member
  set; unknown members or wrong types reject ``COMMAND_INVALID``
  with zero journal drift.
- **the kind table** (the payment/provider/delivery separation,
  table-driven, not caller-honor-driven): a DELIVERED-class
  observation must cite evidence of kind ``delivered`` -- a
  payment observation cited as delivery evidence fails closed
  ``PAYMENT_NOT_DELIVERY``; a provider observation fails closed
  ``PROVIDER_NOT_DELIVERY``.  Provider/payment observations are
  DATA and never proof of delivery.
- **evidence correlation**: the cited evidence must resolve in
  the injected index (``EVIDENCE_UNKNOWN``), must correlate to
  the command's transaction (``EVIDENCE_MISMATCH``), must bound
  the observed window (``WINDOW_INVALID``), and must bound the
  observed quantity (``QUANTITY_EXCEEDED`` -- usage can never
  overstate the authoritative delivered fact).
- **delivery eligibility**: usage requires an
  already-authorized delivery path -- a DELIVERED observation
  against a transaction whose W051 snapshot state is
  pre-delivery (intent/offer/reservation/lease/session/path)
  fails closed ``TRANSACTION_NOT_DELIVERING`` (reservation or
  lease state never creates usage).
- **finality gates**: observations after the seal fail closed
  ``USAGE_SEALED`` (delayed observations after finality never
  rewrite the billable fact); re-seal fails closed
  ``FINAL_IMMUTABLE``; compensations before the seal fail
  closed ``COMPENSATION_REQUIRES_FINAL``; monetary compensation
  beyond the sealed amount fails closed ``COMPENSATION_EXCEEDED``
  (append-only corrections, never negative nets); a second open
  dispute fails closed ``DISPUTE_ALREADY_OPEN``.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from .errors import UsageError, UsageReasonCode
from .evidence import (
    CommercialTransactionSnapshot,
    DeliveryEvidence,
    EvidenceKind,
    QuantityClass,
    UsageEvidenceIndex,
)
from .model import (
    UsageAction,
    UsageCommand,
    UsageTransaction,
    UsageTransactionState,
    transition_is_legal,
    transition_target,
)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise UsageError(
            UsageReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_int(value: object, label: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise UsageError(
            UsageReasonCode.COMMAND_INVALID,
            "%s must be an integer" % label,
        )
    if value < minimum:
        raise UsageError(
            UsageReasonCode.COMMAND_INVALID,
            "%s must be >= %d" % (label, minimum),
        )
    return value


#: The strict per-action payload member sets (exact membership;
#: unknown members reject COMMAND_INVALID).
PAYLOAD_MEMBER_RULES: Dict[str, Tuple[str, ...]] = {
    UsageAction.OBSERVE_USAGE: (
        "quantity_class",
        "quantity",
    ),
    UsageAction.SEAL_BILLABLE: (),
    UsageAction.RECORD_REFUND: ("amount_micros", "reason"),
    UsageAction.RECORD_REVERSAL: (
        "amount_micros",
        "reason",
    ),
    UsageAction.RECORD_DISPUTE: ("reason",),
}

#: The optional evidence members an OBSERVE_USAGE payload may
#: carry (required for the DELIVERED class, forbidden
#: else).
OBSERVATION_EVIDENCE_MEMBERS = ("evidence_id", "window_start", "window_end")


def validate_payload_shape(command: UsageCommand) -> None:
    """Strict per-action payload shape (fail closed, zero drift)."""
    action = command.action
    payload = command.payload
    required = PAYLOAD_MEMBER_RULES.get(action)
    if required is None:
        raise UsageError(
            UsageReasonCode.COMMAND_INVALID,
            "action %r has no payload rule (frozen vocabulary violation)"
            % action,
        )
    extra = sorted(set(payload) - set(required) - set(OBSERVATION_EVIDENCE_MEMBERS))
    if extra:
        raise UsageError(
            UsageReasonCode.COMMAND_INVALID,
            "payload for %s carries unknown member(s) %r"
            % (action, extra),
        )
    missing = sorted(set(required) - set(payload))
    if missing:
        raise UsageError(
            UsageReasonCode.COMMAND_INVALID,
            "payload for %s is missing required member(s) %r"
            % (action, missing),
        )
    if action == UsageAction.OBSERVE_USAGE:
        quantity_class = payload.get("quantity_class")
        if quantity_class not in QuantityClass.values():
            raise UsageError(
                UsageReasonCode.OBSERVATION_CLASS_INVALID,
                "quantity_class %r must be one of %s"
                % (quantity_class, list(QuantityClass.values())),
            )
        _require_int(payload.get("quantity"), "quantity", 1)
        evidence_members = sorted(
            set(OBSERVATION_EVIDENCE_MEMBERS) & set(payload)
        )
        if quantity_class == QuantityClass.DELIVERED:
            if set(evidence_members) != set(OBSERVATION_EVIDENCE_MEMBERS):
                raise UsageError(
                    UsageReasonCode.OBSERVATION_REJECTED,
                    "a DELIVERED-class observation must cite "
                    "evidence_id, window_start, and window_end",
                )
            _require_text(payload.get("evidence_id"), "evidence_id")
            for member in ("window_start", "window_end"):
                text = payload.get(member)
                if not isinstance(text, str) or len(text) != 20 or text[-1] != "Z":
                    raise UsageError(
                        UsageReasonCode.WINDOW_INVALID,
                        "%s must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)"
                        % member,
                    )
            if payload["window_end"] < payload["window_start"]:
                raise UsageError(
                    UsageReasonCode.WINDOW_INVALID,
                    "observation window_end must not precede window_start",
                )
        else:
            if evidence_members:
                raise UsageError(
                    UsageReasonCode.OBSERVATION_CLASS_INVALID,
                    "a %s-class observation must not cite delivery "
                    "evidence (reserved/attempted quantities are DATA, "
                    "never delivered-traffic facts)" % quantity_class,
                )
    elif action in (UsageAction.RECORD_REFUND, UsageAction.RECORD_REVERSAL):
        _require_int(payload.get("amount_micros"), "amount_micros", 1)
        _require_text(payload.get("reason"), "reason")
    elif action == UsageAction.RECORD_DISPUTE:
        _require_text(payload.get("reason"), "reason")


def resolve_observation_evidence(
    command: UsageCommand, index: UsageEvidenceIndex
) -> Optional[DeliveryEvidence]:
    """Resolve and gate the delivery-evidence citation of a
    DELIVERED-class observation against the injected index.

    The kind table (payment/provider/delivery separation):
    fail closed PAYMENT_NOT_DELIVERY / PROVIDER_NOT_DELIVERY for
    DATA-kind citations; fail closed EVIDENCE_UNKNOWN for
    fabricated ids; fail closed EVIDENCE_MISMATCH when the
    evidence does not correlate to the command's transaction.
    Returns None for non-DELIVERED classes (no evidence
    citation exists to resolve).
    """
    if command.payload.get("quantity_class") != QuantityClass.DELIVERED:
        return None
    evidence_id = command.payload["evidence_id"]
    record = index.evidence(evidence_id)
    # the kind gate: the payment/provider/delivery separation is
    # table-driven (an observation can never satisfy the
    # delivered-evidence requirement with DATA)
    if record.evidence_kind == EvidenceKind.PAYMENT_OBSERVED:
        raise UsageError(
            UsageReasonCode.PAYMENT_NOT_DELIVERY,
            "evidence %s is a PAYMENT observation (DATA, never proof of "
            "delivery; payment capture never creates usage)"
            % evidence_id,
        )
    if record.evidence_kind == EvidenceKind.PROVIDER_OBSERVED:
        raise UsageError(
            UsageReasonCode.PROVIDER_NOT_DELIVERY,
            "evidence %s is a PROVIDER observation (DATA, never proof of "
            "delivery; provider observations never create usage)"
            % evidence_id,
        )
    # correlation: the evidence must belong to the cited
    # transaction (the usage record correlates delivered quantity
    # to an authorized delivery evidence record)
    if record.transaction_id != command.transaction_id:
        raise UsageError(
            UsageReasonCode.EVIDENCE_MISMATCH,
            "evidence %s correlates to transaction %s, not the command's "
            "transaction %s"
            % (evidence_id, record.transaction_id, command.transaction_id),
        )
    # window containment: the observed window must sit inside the
    # authoritative delivery window
    window_start = command.payload["window_start"]
    window_end = command.payload["window_end"]
    if window_start < record.window_start or window_end > record.window_end:
        raise UsageError(
            UsageReasonCode.WINDOW_INVALID,
            "observation window [%s, %s] is not contained in the evidence "
            "window [%s, %s]"
            % (window_start, window_end, record.window_start, record.window_end),
        )
    # static quantity bound: a single observation can never
    # overstate the authoritative delivered fact
    if command.payload["quantity"] > record.delivered_quantity:
        raise UsageError(
            UsageReasonCode.QUANTITY_EXCEEDED,
            "observed quantity %d exceeds the delivered evidence quantity "
            "%d for evidence %s"
            % (command.payload["quantity"], record.delivered_quantity, evidence_id),
        )
    return record


def validate_delivery_eligibility(
    command: UsageCommand, snapshot: CommercialTransactionSnapshot
) -> None:
    """Usage requires an already-authorized delivery path.

    A DELIVERED-class observation against a transaction whose
    cited W051 state is pre-delivery fails closed: the explicit
    reservation/lease-phase citation fails closed
    RESERVATION_NOT_USAGE (reservation or lease state NEVER
    creates usage -- the named separation), and any other
    pre-delivery phase fails closed TRANSACTION_NOT_DELIVERING.
    """
    if command.payload.get("quantity_class") != QuantityClass.DELIVERED:
        return
    if snapshot.is_delivery_eligible():
        return
    if snapshot.commercial_state == "RESERVATION_HELD":
        raise UsageError(
            UsageReasonCode.RESERVATION_NOT_USAGE,
            "transaction %s is RESERVATION_HELD (reservation/lease state "
            "never creates usage; only authoritative delivered-traffic "
            "evidence does)"
            % command.transaction_id,
        )
    raise UsageError(
        UsageReasonCode.TRANSACTION_NOT_DELIVERING,
        "transaction %s is in state %s (delivery not yet authorized on "
        "the cited path; usage requires an already-authorized delivery "
        "path)"
        % (command.transaction_id, snapshot.commercial_state),
    )


def find_duplicate_observation(
    command: UsageCommand, transaction: Optional[UsageTransaction]
) -> Optional[str]:
    """Evidence-level duplicate detection (no double charge).

    A DELIVERED-class observation whose (evidence_id, window)
    key is already recorded is a duplicate report of the same
    delivered fact: if the quantity matches the recorded
    observation it is an idempotent no-op (the DUPLICATE outcome
    returns the recorded observation id and NO new record, NO
    clock read, NO state change); if the quantity differs the
    same evidence-window cannot carry two different quantities
    -- conflicting reuse fails closed EVIDENCE_MISMATCH.
    """
    if command.payload.get("quantity_class") != QuantityClass.DELIVERED:
        return None
    if transaction is None:
        return None
    evidence_id = command.payload["evidence_id"]
    window_key = (command.payload["window_start"], command.payload["window_end"])
    for observation in transaction.observations:
        if (
            observation.evidence_id == evidence_id
            and (observation.window_start, observation.window_end) == window_key
        ):
            if observation.quantity != command.payload["quantity"]:
                raise UsageError(
                    UsageReasonCode.EVIDENCE_MISMATCH,
                    "evidence %s window %r already recorded with quantity "
                    "%d (conflicting reuse of the evidence-window identity "
                    "fails closed; quantity %d conflicts)"
                    % (
                        evidence_id,
                        window_key,
                        observation.quantity,
                        command.payload["quantity"],
                    ),
                )
            return observation.observation_id
    return None


def validate_observation_quantity_cap(
    command: UsageCommand,
    record: Optional[DeliveryEvidence],
    transaction: Optional[UsageTransaction],
) -> None:
    """The cumulative per-evidence cap: the summed DELIVERED
    quantity recorded against one evidence record can never
    exceed the authoritative delivered quantity (no double
    charge from windowed sub-metering either)."""
    if record is None or transaction is None:
        return
    evidence_id = record.evidence_id
    already = sum(
        observation.quantity
        for observation in transaction.observations
        if observation.evidence_id == evidence_id
    )
    if already + command.payload["quantity"] > record.delivered_quantity:
        raise UsageError(
            UsageReasonCode.QUANTITY_EXCEEDED,
            "cumulative observed quantity %d + %d exceeds the delivered "
            "evidence quantity %d for evidence %s (no double charge)"
            % (
                already,
                command.payload["quantity"],
                record.delivered_quantity,
                evidence_id,
            ),
        )


def validate_command_against_transaction(
    command: UsageCommand,
    transaction: Optional[UsageTransaction],
) -> None:
    """The state gates (fail closed; a rejection here may follow
    the single deterministic clock read, exactly like the W051
    state-gate layer)."""
    current_state = (
        transaction.state if transaction is not None
        else UsageTransactionState.OBSERVING
    )
    if not transition_is_legal(current_state, command.action):
        # map the illegal pair to the typed finality reasons
        if (
            current_state == UsageTransactionState.BILLABLE_FINAL
            and command.action == UsageAction.OBSERVE_USAGE
        ):
            raise UsageError(
                UsageReasonCode.USAGE_SEALED,
                "transaction %s is BILLABLE_FINAL: delayed observations "
                "after the seal fail closed (the sealed billable fact is "
                "immutable; corrections are append-only compensations)"
                % command.transaction_id,
            )
        if (
            current_state == UsageTransactionState.BILLABLE_FINAL
            and command.action == UsageAction.SEAL_BILLABLE
        ):
            raise UsageError(
                UsageReasonCode.FINAL_IMMUTABLE,
                "transaction %s is already sealed (re-seal rejected; "
                "billable finality is explicit and immutable)"
                % command.transaction_id,
            )
        if command.action in UsageAction.compensation_actions():
            raise UsageError(
                UsageReasonCode.COMPENSATION_REQUIRES_FINAL,
                "%s requires a sealed billable statement (compensations "
                "append against finality; they never rewrite history)"
                % command.action,
            )
        raise UsageError(
            UsageReasonCode.OBSERVATION_REJECTED,
            "%s from %s is not in the frozen usage transition table"
            % (command.action, current_state),
        )
    # the compensation family gates (only reachable in
    # BILLABLE_FINAL, where the statement exists by the
    # UsageTransaction invariant)
    if command.action in UsageAction.compensation_actions():
        if transaction is None or transaction.statement is None:
            raise UsageError(
                UsageReasonCode.COMPENSATION_REQUIRES_FINAL,
                "%s requires a sealed billable statement (compensations "
                "append against finality; they never rewrite history)"
                % command.action,
            )
        statement = transaction.statement
        if command.action in (
            UsageAction.RECORD_REFUND,
            UsageAction.RECORD_REVERSAL,
        ):
            new_amount = command.payload["amount_micros"]
            cumulative = (
                transaction.refunded_amount_micros()
                + transaction.reversed_amount_micros()
            )
            if cumulative + new_amount > statement.amount_micros:
                raise UsageError(
                    UsageReasonCode.COMPENSATION_EXCEEDED,
                    "cumulative compensation %d + %d exceeds the sealed "
                    "amount %d (the net never goes negative; corrections "
                    "are bounded compensating records)"
                    % (cumulative, new_amount, statement.amount_micros),
                )
        elif command.action == UsageAction.RECORD_DISPUTE:
            if transaction.disputed():
                raise UsageError(
                    UsageReasonCode.DISPUTE_ALREADY_OPEN,
                    "transaction %s already carries an open dispute "
                    "(a second dispute record is rejected; dispute "
                    "resolution is a settlement-layer concern)"
                    % command.transaction_id,
                )


def validate_observation_instant(
    command: UsageCommand, record: Optional[DeliveryEvidence], instant: str
) -> None:
    """The deterministic recorded instant must be a well-formed
    RFC 3339 UTC instant (the injected clock seam read)."""
    if not isinstance(instant, str) or len(instant) != 20 or instant[-1] != "Z":
        raise UsageError(
            UsageReasonCode.INSTANT_INVALID,
            "the usage event instant must be RFC 3339 UTC "
            "(YYYY-MM-DDTHH:MM:SSZ)",
        )
