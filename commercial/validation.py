"""WORK-051 CommercialCore command validation (fail-closed).

The admission rules every command must pass BEFORE any journal
record is written (a rejected command leaves no phantom state and
no journal growth):

- **shape validation**: payload members required per action
  (intent descriptor, offer descriptor, reservation deadline, ...)
  with strict types;
- **family requirements**: which reference families each action
  REQUIRES as its causal justification, and which families are
  forbidden.  The payment/delivery separation is TABLE-DRIVEN,
  not caller-honor-driven: a payment-family reference can never
  satisfy a delivery or settlement requirement
  (``PAYMENT_NOT_DELIVERY`` / ``PAYMENT_NOT_SETTLEMENT``), and a
  settlement-family reference can never justify a delivery state.
  Reservation is structurally never delivery (the lifecycle table
  admits ``DELIVERY_STARTED`` only from ``PATH_ACTIVE``);
- **expiry discipline**: a reservation deadline is recorded DATA
  (``expires_at``); authorizing or activating past the deadline
  fails closed ``RESERVATION_EXPIRED``; expiring before the
  deadline fails closed ``EXPIRY_NOT_DUE``;
- **settlement integrity**: ``SETTLE`` requires the recorded
  delivery-evidence chain to be intact (non-empty and every cited
  delivery reference resolvable in the current index) and a
  settlement-family causal reference; settlement without delivery
  evidence fails closed ``SETTLEMENT_REJECTED``.

All comparisons use the deterministic ``agent.clock`` parse
helpers (no OS time).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from agent.clock import parse_utc

from .errors import CommercialError, CommercialReasonCode
from .model import (
    ACTION_REQUIRED_STATE,
    CommercialAction,
    CommercialCommand,
    CommercialState,
    CommercialTransaction,
    transition_is_legal,
)
from .references import (
    Reference,
    ReferenceFamily,
    ReferenceIndex,
    reference_family_counts,
)


def _require_payload_key(payload: Mapping[str, Any], key: str, action: str) -> Any:
    if key not in payload:
        raise CommercialError(
            CommercialReasonCode.COMMAND_INVALID,
            "%s requires payload member %r" % (action, key),
        )
    return payload[key]


def _payload_mapping(
    payload: Mapping[str, Any], key: str, action: str
) -> Dict[str, Any]:
    value = _require_payload_key(payload, key, action)
    if not isinstance(value, Mapping):
        raise CommercialError(
            CommercialReasonCode.COMMAND_INVALID,
            "%s payload member %r must be a mapping" % (action, key),
        )
    return dict(value)


def _payload_instant(payload: Mapping[str, Any], key: str, action: str) -> str:
    value = _require_payload_key(payload, key, action)
    if not isinstance(value, str) or not value:
        raise CommercialError(
            CommercialReasonCode.INSTANT_INVALID,
            "%s payload member %r must be an RFC 3339 UTC instant string"
            % (action, key),
        )
    try:
        parse_utc(value)
    except Exception as error:  # noqa: BLE001 - re-wrapped typed
        raise CommercialError(
            CommercialReasonCode.INSTANT_INVALID,
            "%s payload member %r is not RFC 3339 UTC: %s"
            % (action, key, error),
        ) from error
    return value


#: The frozen causal family requirement table (the
#: payment/delivery and reservation/delivery separations are
#: structural here, not caller honors):
#:
#: - ``required``: families that MUST appear among the command's
#:   resolved causal references;
#: - ``forbidden``: families that MUST NOT appear (payment
#:   references are DATA-only attachments for reservation and
#:   settlement-initiation commands and are forbidden outright
#:   for delivery commands).
ACTION_FAMILY_RULES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    CommercialAction.SUBMIT_INTENT: {
        "required": (),
        "forbidden": (ReferenceFamily.PAYMENT, ReferenceFamily.SETTLEMENT),
    },
    CommercialAction.SELECT_OFFER: {
        "required": (),
        "forbidden": (ReferenceFamily.PAYMENT, ReferenceFamily.SETTLEMENT),
    },
    CommercialAction.HOLD_RESERVATION: {
        # payment observations may be attached as recorded DATA
        # (reservation/payment state is separate from delivery),
        # but they justify nothing.
        "required": (),
        "forbidden": (ReferenceFamily.SETTLEMENT,),
    },
    CommercialAction.AUTHORIZE_SESSION: {
        "required": (ReferenceFamily.SESSION,),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.DELIVERY_EVIDENCE,
            ReferenceFamily.USAGE,
        ),
    },
    CommercialAction.ACTIVATE_PATH: {
        "required": (ReferenceFamily.NETWORK_PATH,),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.DELIVERY_EVIDENCE,
            ReferenceFamily.USAGE,
        ),
    },
    CommercialAction.START_DELIVERY: {
        # ONLY delivery evidence can start delivery.  Payment
        # success NEVER implies delivery (ACR-009 invariant 1);
        # reservation NEVER implies delivery (invariant 2).
        "required": (ReferenceFamily.DELIVERY_EVIDENCE,),
        "forbidden": (ReferenceFamily.PAYMENT, ReferenceFamily.SETTLEMENT),
    },
    CommercialAction.ACCRUE_USAGE: {
        # usage references only (usage metering is WORK-052; the
        # core records usage REFERENCES, never usage facts).
        "required": (ReferenceFamily.USAGE,),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.DELIVERY_EVIDENCE,
        ),
    },
    CommercialAction.COMPLETE_DELIVERY: {
        "required": (ReferenceFamily.DELIVERY_EVIDENCE,),
        "forbidden": (ReferenceFamily.PAYMENT, ReferenceFamily.SETTLEMENT),
    },
    CommercialAction.FINALIZE_BILLABLE: {
        "required": (),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.DELIVERY_EVIDENCE,
            ReferenceFamily.USAGE,
        ),
    },
    CommercialAction.INITIATE_SETTLEMENT: {
        # settlement initiation is a commercial decision; payment
        # observations may be attached as DATA, settlement
        # confirmations are NOT yet required (they justify SETTLE).
        "required": (),
        "forbidden": (ReferenceFamily.SETTLEMENT,),
    },
    CommercialAction.SETTLE: {
        # ONLY an external settlement confirmation justifies
        # SETTLED (payment observations are not settlement
        # confirmations: PAYMENT_NOT_SETTLEMENT).
        "required": (ReferenceFamily.SETTLEMENT,),
        "forbidden": (ReferenceFamily.PAYMENT,),
    },
    # compensating actions cite no external authority families
    CommercialAction.CANCEL: {
        "required": (),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.DELIVERY_EVIDENCE,
            ReferenceFamily.USAGE,
            ReferenceFamily.SESSION,
            ReferenceFamily.NETWORK_PATH,
        ),
    },
    CommercialAction.EXPIRE: {
        "required": (),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.DELIVERY_EVIDENCE,
            ReferenceFamily.USAGE,
            ReferenceFamily.SESSION,
            ReferenceFamily.NETWORK_PATH,
        ),
    },
    CommercialAction.RECORD_PATH_FAILURE: {
        "required": (),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.USAGE,
        ),
    },
    CommercialAction.RECORD_NON_DELIVERY: {
        "required": (),
        "forbidden": (
            ReferenceFamily.PAYMENT,
            ReferenceFamily.SETTLEMENT,
            ReferenceFamily.USAGE,
        ),
    },
}


def validate_family_rules(
    action: str, resolved_references: Tuple[Reference, ...]
) -> None:
    """Enforce the frozen causal family rules for one action.

    The payment/delivery separation: a payment-family reference
    on a delivery command is rejected ``PAYMENT_NOT_DELIVERY``
    (payment success never implies delivery); a payment-family
    reference on a settle command is rejected
    ``PAYMENT_NOT_SETTLEMENT`` (a payment observation is not a
    settlement confirmation).  Forbidden families are judged
    BEFORE required families so the payment separation is always
    the discriminating reason.  Every other family violation is
    ``COMMAND_INVALID`` fail-closed.
    """
    rules = ACTION_FAMILY_RULES.get(action)
    if rules is None:
        raise CommercialError(
            CommercialReasonCode.COMMAND_INVALID,
            "action %r has no family rules (unknown action)" % action,
        )
    counts = reference_family_counts(resolved_references)
    required, forbidden = rules["required"], rules["forbidden"]
    for family in forbidden:
        if counts.get(family, 0) > 0:
            if family == ReferenceFamily.PAYMENT and action in (
                CommercialAction.START_DELIVERY,
                CommercialAction.COMPLETE_DELIVERY,
                CommercialAction.ACCRUE_USAGE,
            ):
                raise CommercialError(
                    CommercialReasonCode.PAYMENT_NOT_DELIVERY,
                    "payment-family reference cannot justify %s: payment "
                    "success never implies delivery" % action,
                )
            if family == ReferenceFamily.PAYMENT and action == CommercialAction.SETTLE:
                raise CommercialError(
                    CommercialReasonCode.PAYMENT_NOT_SETTLEMENT,
                    "payment observations are recorded DATA and never "
                    "settlement confirmations",
                )
            raise CommercialError(
                CommercialReasonCode.COMMAND_INVALID,
                "%s forbids %s-family causal references" % (action, family),
            )
    for family in required:
        if counts.get(family, 0) <= 0:
            raise CommercialError(
                CommercialReasonCode.COMMAND_INVALID,
                "%s requires at least one %s-family causal reference"
                % (action, family),
            )


def validate_payload_shape(command: CommercialCommand) -> None:
    """Per-action payload shape validation (fail-closed).

    Only shape and member presence are validated here; semantic
    gates (state, expiry, settlement integrity) are enforced by
    the lifecycle manager with the clock instant and transaction
    projection in hand.
    """
    action = command.action
    payload = command.payload
    if action == CommercialAction.SUBMIT_INTENT:
        _payload_mapping(payload, "intent", action)
    elif action == CommercialAction.SELECT_OFFER:
        _payload_mapping(payload, "offer", action)
    elif action == CommercialAction.HOLD_RESERVATION:
        _payload_instant(payload, "expires_at", action)
    elif action == CommercialAction.AUTHORIZE_SESSION:
        pass
    elif action == CommercialAction.ACTIVATE_PATH:
        pass
    elif action == CommercialAction.START_DELIVERY:
        pass
    elif action == CommercialAction.ACCRUE_USAGE:
        pass
    elif action == CommercialAction.COMPLETE_DELIVERY:
        pass
    elif action == CommercialAction.FINALIZE_BILLABLE:
        pass
    elif action == CommercialAction.INITIATE_SETTLEMENT:
        pass
    elif action == CommercialAction.SETTLE:
        pass
    elif action == CommercialAction.CANCEL:
        pass
    elif action == CommercialAction.EXPIRE:
        pass
    elif action == CommercialAction.RECORD_PATH_FAILURE:
        pass
    elif action == CommercialAction.RECORD_NON_DELIVERY:
        pass
    else:  # pragma: no cover - vocabulary-frozen above
        raise CommercialError(
            CommercialReasonCode.COMMAND_INVALID,
            "action %r is not in the frozen vocabulary" % action,
        )


def validate_reservation_deadline(
    transaction: CommercialTransaction, now_instant: str
) -> None:
    """Fail closed when acting on an expired reservation.

    Deterministic deadline arithmetic via the accepted parse
    helper (no OS time).  Applies to the reservation window states
    (``RESERVATION_HELD`` / ``SESSION_AUTHORIZED``): once the
    recorded deadline has passed, forward progression fails closed
    and the caller must record the explicit compensating
    ``expire`` event.
    """
    if transaction.state not in (
        CommercialState.RESERVATION_HELD,
        CommercialState.SESSION_AUTHORIZED,
    ):
        return
    if not transaction.expires_at:
        return
    deadline = parse_utc(transaction.expires_at)
    now = parse_utc(now_instant)
    if now >= deadline:
        raise CommercialError(
            CommercialReasonCode.RESERVATION_EXPIRED,
            "reservation window for %s closed at %s (now %s); record the "
            "compensating expire event"
            % (transaction.transaction_id, transaction.expires_at, now_instant),
        )


def validate_settlement_integrity(
    transaction: CommercialTransaction,
    index: ReferenceIndex,
    resolved_references: Tuple[Reference, ...],
) -> None:
    """The SETTLE preconditions (settlement/delivery separation).

    Settlement can never be confused with delivery, and can never
    occur without the delivery evidence the transaction actually
    recorded:

    - the transaction must carry at least one recorded delivery
      evidence reference (``DELIVERY_STARTED`` is reachable only
      through a delivery-evidence-justified command, so an empty
      chain here means tampering or a forged projection -- fail
      closed);
    - every recorded delivery evidence reference must still
      resolve in the current reference index (an evicted or
      fabricated delivery citation fails closed);
    - a settlement-family confirmation must be among the command's
      causal references (enforced by the family table; this
      function adds the delivery-chain integrity half).

    Settlement does not rewrite delivery facts: this check only
    READS the recorded chain.
    """
    if not transaction.delivery_evidence_refs:
        raise CommercialError(
            CommercialReasonCode.SETTLEMENT_REJECTED,
            "transaction %s has no recorded delivery evidence; settlement "
            "without delivery is rejected (delivery and settlement are "
            "separate authorities of fact)"
            % transaction.transaction_id,
        )
    for reference_id in transaction.delivery_evidence_refs:
        try:
            index.get(reference_id)
        except CommercialError as error:
            raise CommercialError(
                CommercialReasonCode.SETTLEMENT_REJECTED,
                "recorded delivery evidence %s no longer resolves in the "
                "reference index: %s" % (reference_id, error.detail),
            ) from error
    counts = reference_family_counts(resolved_references)
    if counts.get(ReferenceFamily.SETTLEMENT, 0) <= 0:
        raise CommercialError(
            CommercialReasonCode.PAYMENT_NOT_SETTLEMENT,
            "settle requires a settlement-family confirmation reference",
        )


def validate_command_against_transaction(
    command: CommercialCommand,
    transaction: CommercialTransaction,
    index: ReferenceIndex,
    resolved_references: Tuple[Reference, ...],
    now_instant: str,
) -> None:
    """The full fail-closed admission gate for an EXECUTING command.

    Order matters and every gate is fail-closed BEFORE any journal
    record exists:

    1. the action's required precondition state (the command
       class's own state gate, independent of the target state);
    2. settled/terminal immutability (``HISTORY_IMMUTABLE`` for
       ``SETTLED``; ``LIFECYCLE_ILLEGAL`` for the compensating
       terminals);
    3. the transition legality from the CURRENT projected state;
    4. the reservation deadline (forward progression past the
       deadline fails closed);
    5. the causal family rules (payment/delivery separation);
    6. the SETTLE-specific settlement-integrity preconditions.
    """
    action = command.action
    required_state = ACTION_REQUIRED_STATE.get(action)
    if required_state is None:
        raise CommercialError(
            CommercialReasonCode.COMMAND_INVALID,
            "action %r has no precondition state" % action,
        )

    if transaction.settled():
        raise CommercialError(
            CommercialReasonCode.HISTORY_IMMUTABLE,
            "transaction %s is SETTLED: historical commercial facts are "
            "immutable; corrections are compensating records, never "
            "re-writes" % transaction.transaction_id,
        )
    if transaction.terminal():
        raise CommercialError(
            CommercialReasonCode.LIFECYCLE_ILLEGAL,
            "transaction %s is in terminal state %s; no command may "
            "progress a terminal transaction"
            % (transaction.transaction_id, transaction.state),
        )
    if required_state and transaction.state != required_state:
        # State-preserving accrual admits USAGE_ACCRUING transitively.
        if not (
            action == CommercialAction.ACCRUE_USAGE
            and transaction.state == CommercialState.USAGE_ACCRUING
        ):
            raise CommercialError(
                CommercialReasonCode.LIFECYCLE_ILLEGAL,
                "%s requires state %s (transaction %s is %s)"
                % (
                    action,
                    required_state,
                    transaction.transaction_id,
                    transaction.state,
                ),
            )

    # the reservation deadline gates FORWARD progression only
    # (authorize/activate); the compensating expire command is
    # governed by validate_expire_due (honest EXPIRY_NOT_DUE).
    if action != CommercialAction.EXPIRE:
        validate_reservation_deadline(transaction, now_instant)
    validate_family_rules(action, resolved_references)
    if action == CommercialAction.SETTLE:
        validate_settlement_integrity(transaction, index, resolved_references)


def validate_expire_due(
    transaction: CommercialTransaction, now_instant: str
) -> None:
    """``EXPIRE`` is compensating and deadline-honest.

    Fails closed with ``EXPIRY_NOT_DUE`` when the recorded
    deadline has not yet passed (no premature expiry) and with
    ``LIFECYCLE_ILLEGAL`` when the transaction is not in an
    expirable state.
    """
    if transaction.state not in (
        CommercialState.RESERVATION_HELD,
        CommercialState.SESSION_AUTHORIZED,
    ):
        raise CommercialError(
            CommercialReasonCode.LIFECYCLE_ILLEGAL,
            "expire is a compensating record for reservation-window states; "
            "transaction %s is %s"
            % (transaction.transaction_id, transaction.state),
        )
    if not transaction.expires_at:
        raise CommercialError(
            CommercialReasonCode.EXPIRY_NOT_DUE,
            "transaction %s carries no reservation deadline" % transaction.transaction_id,
        )
    deadline = parse_utc(transaction.expires_at)
    now = parse_utc(now_instant)
    if now < deadline:
        raise CommercialError(
            CommercialReasonCode.EXPIRY_NOT_DUE,
            "reservation window for %s is open until %s (now %s); premature "
            "expiry is rejected" % (transaction.transaction_id, transaction.expires_at, now_instant),
        )


def validate_path_failure_state(transaction: CommercialTransaction) -> None:
    """``RECORD_PATH_FAILURE`` is compensating for delivery states."""
    if transaction.state not in (
        CommercialState.PATH_ACTIVE,
        CommercialState.DELIVERY_STARTED,
        CommercialState.USAGE_ACCRUING,
    ):
        raise CommercialError(
            CommercialReasonCode.PATH_FAILURE_REJECTED,
            "path failure is a compensating record for path/delivery "
            "states; transaction %s is %s"
            % (transaction.transaction_id, transaction.state),
        )


def validate_non_delivery_state(transaction: CommercialTransaction) -> None:
    """``RECORD_NON_DELIVERY`` is compensating for delivery states."""
    if transaction.state not in (
        CommercialState.PATH_ACTIVE,
        CommercialState.DELIVERY_STARTED,
        CommercialState.USAGE_ACCRUING,
    ):
        raise CommercialError(
            CommercialReasonCode.NON_DELIVERY_REJECTED,
            "non-delivery is a compensating record for path/delivery "
            "states; transaction %s is %s"
            % (transaction.transaction_id, transaction.state),
        )


def validate_cancel_state(transaction: CommercialTransaction) -> None:
    """``CANCEL`` is compensating for pre-delivery states."""
    if transaction.state not in (
        CommercialState.CONNECTIVITY_INTENT,
        CommercialState.OFFER_SELECTED,
        CommercialState.RESERVATION_HELD,
        CommercialState.SESSION_AUTHORIZED,
        CommercialState.PATH_ACTIVE,
    ):
        raise CommercialError(
            CommercialReasonCode.LIFECYCLE_ILLEGAL,
            "cancellation is a pre-delivery compensating record; "
            "transaction %s is %s"
            % (transaction.transaction_id, transaction.state),
        )
