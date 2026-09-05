"""WORK-053 EconomicAllocation command admission rules.

Fail-closed admission gates, mirroring the accepted W052
validation discipline (the family-rules-table pattern):

- **strict payload shape**: each action carries an exact member
  set; unknown members or wrong types reject ``COMMAND_INVALID``
  with zero journal drift;
- **the kind table** (the payment/settlement/usage separation,
  table-driven, not caller-honor-driven): an ALLOCATE subject
  citation resolving to a payment reference fails closed
  ``PAYMENT_NOT_USAGE``; one resolving to a settlement reference
  fails closed ``SETTLEMENT_NOT_USAGE`` (payment success,
  reservation state, offer state, or provider callbacks never
  create allocation -- they are external references and never
  usage facts); a settlement acknowledgement citing a payment
  reference fails closed ``PAYMENT_NOT_SETTLEMENT``; a payment
  callback citing a settlement reference fails closed
  ``SETTLEMENT_NOT_PAYMENT``;
- **billable-usage finality**: allocation consumes only
  BILLABLE_FINAL usage facts -- a cited usage transaction whose
  W052 public snapshot is not final (still OBSERVING) fails
  closed ``USAGE_NOT_FINAL``; a cited statement id that does not
  match the snapshot's sealed statement fails closed
  ``USAGE_MISMATCH``;
- **policy discipline**: the cited policy version must resolve
  in the folded registry (``POLICY_UNKNOWN`` -- never a live
  authority), must be effective at the deterministic event
  instant (``POLICY_NOT_EFFECTIVE`` -- the declared effective
  window is the version-selection gate), and the
  developer-selected provider share must lie within the
  platform-declared bounds (``SPLIT_OUT_OF_BOUNDS``);
- **distribution discipline**: declared fees/taxes are
  non-negative integers and the derived distributable amount
  must stay within [0, gross] (``DISTRIBUTION_INVALID``);
- **external-reference correlation**: a cited reference must
  resolve in the injected index (``REFERENCE_UNKNOWN``), must be
  of the required kind (the table above), and must not conflict
  with its declared usage-transaction correlation
  (``REFERENCE_MISMATCH``);
- **finality gates**: settlement acknowledgement happens exactly
  once (re-ack fails closed ``SETTLEMENT_IMMUTABLE``);
  compensations append only after settlement
  (``COMPENSATION_REQUIRES_SETTLED``); monetary compensation
  beyond the distributable amount fails closed
  ``COMPENSATION_EXCEEDED`` (append-only corrections, never
  negative nets); a second open dispute fails closed
  ``DISPUTE_ALREADY_OPEN``; a second allocation for one
  billable-final usage record fails closed
  ``ALLOCATION_ALREADY_EXISTS`` (exactly one allocation per
  usage record).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from .errors import AllocationError, AllocationReasonCode
from .evidence import (
    AllocationEvidenceIndex,
    BillableUsageSnapshot,
    ExternalReferenceSnapshot,
    ReferenceKind,
    USAGE_STATE_FINAL,
)
from .model import (
    AllocationAction,
    AllocationCommand,
    AllocationSubjectState,
    AllocationTransaction,
    BPS_DENOMINATOR,
    PolicyVersion,
    RoundingMode,
    transition_is_legal,
)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_int(value: object, label: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise AllocationError(
            AllocationReasonCode.COMMAND_INVALID,
            "%s must be an integer" % label,
        )
    if value < minimum:
        raise AllocationError(
            AllocationReasonCode.COMMAND_INVALID,
            "%s must be >= %d" % (label, minimum),
        )
    return value


#: The strict per-action payload member sets (exact membership;
#: unknown members reject COMMAND_INVALID).
PAYLOAD_MEMBER_RULES: Dict[str, Tuple[str, ...]] = {
    AllocationAction.REGISTER_POLICY: (
        "adcos_share_bps",
        "provider_min_bps",
        "provider_max_bps",
        "rounding_mode",
        "currency",
        "minor_unit_digits",
        "effective_from",
        "effective_until",
    ),
    AllocationAction.ALLOCATE: (
        "usage_statement_id",
        "policy_id",
        "provider_share_bps",
        "fee_micros",
        "tax_micros",
        "adjustment_micros",
    ),
    AllocationAction.ACKNOWLEDGE_SETTLEMENT: (
        "settlement_reference",
    ),
    AllocationAction.RECORD_PAYMENT_REFERENCE: (
        "payment_reference",
    ),
    AllocationAction.RECORD_REFUND: ("amount_micros", "reason"),
    AllocationAction.RECORD_REVERSAL: ("amount_micros", "reason"),
    AllocationAction.RECORD_CHARGEBACK: ("amount_micros", "reason"),
    AllocationAction.RECORD_PAYOUT_FAILURE: (
        "amount_micros",
        "reason",
    ),
    AllocationAction.RECORD_DISPUTE: ("reason",),
}


def _require_instant_payload(value: object, label: str) -> None:
    """RFC 3339 UTC instant member (payload-shape level)."""
    if not isinstance(value, str) or len(value) != 20 or value[-1] != "Z":
        raise AllocationError(
            AllocationReasonCode.COMMAND_INVALID,
            "%s must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)" % label,
        )


def validate_payload_shape(command: AllocationCommand) -> None:
    """Strict per-action payload shape (fail closed, zero
    drift)."""
    action = command.action
    payload = command.payload
    required = PAYLOAD_MEMBER_RULES.get(action)
    if required is None:
        raise AllocationError(
            AllocationReasonCode.COMMAND_INVALID,
            "action %r has no payload rule (frozen vocabulary "
            "violation)" % action,
        )
    extra = sorted(set(payload) - set(required))
    if extra:
        raise AllocationError(
            AllocationReasonCode.COMMAND_INVALID,
            "payload for %s carries unknown member(s) %r"
            % (action, extra),
        )
    missing = sorted(set(required) - set(payload))
    if missing:
        raise AllocationError(
            AllocationReasonCode.COMMAND_INVALID,
            "payload for %s is missing required member(s) %r"
            % (action, missing),
        )
    if action == AllocationAction.REGISTER_POLICY:
        for member in (
            "adcos_share_bps",
            "provider_min_bps",
            "provider_max_bps",
            "minor_unit_digits",
        ):
            value = payload.get(member)
            if not isinstance(value, int) or isinstance(value, bool):
                raise AllocationError(
                    AllocationReasonCode.COMMAND_INVALID,
                    "%s must be an integer" % member,
                )
            if not 0 <= value <= BPS_DENOMINATOR:
                raise AllocationError(
                    AllocationReasonCode.POLICY_INVALID,
                    "%s %d must be within [0, %d] (basis points)"
                    % (member, value, BPS_DENOMINATOR),
                )
        if payload["minor_unit_digits"] > 6:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "minor_unit_digits must be within [0, 6]",
            )
        if payload["provider_min_bps"] > payload["provider_max_bps"]:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "provider_min_bps must not exceed provider_max_bps",
            )
        if payload["rounding_mode"] not in RoundingMode.values():
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "rounding_mode %r must be one of %s"
                % (
                    payload["rounding_mode"],
                    list(RoundingMode.values()),
                ),
            )
        _require_text(payload.get("currency"), "currency")
        for member in ("effective_from", "effective_until"):
            _require_instant_payload(payload.get(member), member)
        if payload["effective_until"] < payload["effective_from"]:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "effective_until must not precede effective_from",
            )
    elif action == AllocationAction.ALLOCATE:
        _require_text(
            payload.get("usage_statement_id"), "usage_statement_id"
        )
        _require_text(payload.get("policy_id"), "policy_id")
        _require_int(
            payload.get("provider_share_bps"),
            "provider_share_bps",
            0,
        )
        if payload["provider_share_bps"] > BPS_DENOMINATOR:
            raise AllocationError(
                AllocationReasonCode.COMMAND_INVALID,
                "provider_share_bps must be within [0, %d]"
                % BPS_DENOMINATOR,
            )
        for member in ("fee_micros", "tax_micros"):
            _require_int(payload.get(member), member, 0)
        if not isinstance(payload.get("adjustment_micros"), int) or isinstance(  # noqa: E501
            payload.get("adjustment_micros"), bool
        ):
            raise AllocationError(
                AllocationReasonCode.COMMAND_INVALID,
                "adjustment_micros must be an integer",
            )
    elif action == AllocationAction.ACKNOWLEDGE_SETTLEMENT:
        _require_text(
            payload.get("settlement_reference"), "settlement_reference"
        )
    elif action == AllocationAction.RECORD_PAYMENT_REFERENCE:
        _require_text(
            payload.get("payment_reference"), "payment_reference"
        )
    elif action in AllocationAction.compensation_actions():
        if action != AllocationAction.RECORD_DISPUTE:
            _require_int(payload.get("amount_micros"), "amount_micros", 1)
        _require_text(payload.get("reason"), "reason")


# ---------------------------------------------------------------------------
# The usage-citation resolution (the payment/settlement/usage
# separation + finality + statement binding)
# ---------------------------------------------------------------------------


def resolve_usage_projection(
    command: AllocationCommand, index: AllocationEvidenceIndex
) -> BillableUsageSnapshot:
    """Resolve and gate the ALLOCATE usage citation against the
    injected index (the payment/settlement/usage kind table).

    The kind gate first: a subject citation that resolves to an
    EXTERNAL reference (payment or settlement) is structurally
    ineligible as a usage fact -- payment success, reservation
    state, offer state, or provider callbacks never create
    allocation (``PAYMENT_NOT_USAGE`` / ``SETTLEMENT_NOT_USAGE``).
    Then the usage-table resolution (``USAGE_UNKNOWN`` for
    fabricated citations) and the two bindings: the sealed
    statement must match the cited statement id
    (``USAGE_MISMATCH``) and the usage state must be
    BILLABLE_FINAL (``USAGE_NOT_FINAL``).
    """
    usage_transaction_id = command.subject_id
    if index.contains_reference(usage_transaction_id):
        reference = index.reference(usage_transaction_id)
        if reference.reference_kind == ReferenceKind.PAYMENT:
            raise AllocationError(
                AllocationReasonCode.PAYMENT_NOT_USAGE,
                "the cited subject %s is a PAYMENT reference (DATA, "
                "never a usage fact; payment success never creates "
                "allocation)" % usage_transaction_id,
            )
        raise AllocationError(
            AllocationReasonCode.SETTLEMENT_NOT_USAGE,
            "the cited subject %s is a SETTLEMENT reference (DATA, "
            "never a usage fact; settlement confirmation never "
            "creates allocation)" % usage_transaction_id,
        )
    snapshot = index.usage(usage_transaction_id)
    if snapshot.usage_state != USAGE_STATE_FINAL:
        raise AllocationError(
            AllocationReasonCode.USAGE_NOT_FINAL,
            "usage transaction %s is %s (allocation consumes only "
            "BILLABLE_FINAL usage facts; OBSERVING usage has no "
            "sealed billable record to allocate)"
            % (usage_transaction_id, snapshot.usage_state),
        )
    cited_statement = command.payload.get("usage_statement_id")
    if snapshot.statement_id != cited_statement:
        raise AllocationError(
            AllocationReasonCode.USAGE_MISMATCH,
            "the cited usage statement %s does not match the snapshot's "
            "sealed statement %s for usage transaction %s"
            % (cited_statement, snapshot.statement_id, usage_transaction_id),
        )
    return snapshot


def validate_usage_finality(
    command: AllocationCommand, snapshot: BillableUsageSnapshot
) -> None:
    """Allocation requires the BILLABLE_FINAL usage state (the
    explicit gate, separable for the replay symmetry)."""
    if snapshot.usage_state != USAGE_STATE_FINAL:
        raise AllocationError(
            AllocationReasonCode.USAGE_NOT_FINAL,
            "usage transaction %s is %s (allocation consumes only "
            "BILLABLE_FINAL usage facts)"
            % (command.subject_id, snapshot.usage_state),
        )


# ---------------------------------------------------------------------------
# The policy discipline
# ---------------------------------------------------------------------------


def resolve_policy(
    command: AllocationCommand,
    policies: Mapping[str, PolicyVersion],
) -> PolicyVersion:
    """Resolve the cited policy version against the FOLDED
    registry (never a live authority: the allocation ledger owns
    its policy-version projection; a fabricated citation fails
    closed here, at admission AND at replay)."""
    policy_id = command.payload.get("policy_id")
    policy = policies.get(policy_id)
    if policy is None:
        raise AllocationError(
            AllocationReasonCode.POLICY_UNKNOWN,
            "policy version %r is not registered in the folded policy "
            "registry (fabricated, stale, or not-yet-registered "
            "citation)" % policy_id,
        )
    return policy


def validate_policy_effective(
    policy: PolicyVersion, instant: str
) -> None:
    """The declared effective window must contain the
    deterministic event instant (the immutable-policy version
    selection gate)."""
    if not policy.is_effective(instant):
        raise AllocationError(
            AllocationReasonCode.POLICY_NOT_EFFECTIVE,
            "policy version %s is not effective at %s (declared "
            "window [%s, %s]; versioned policy selection is exact)"
            % (
                policy.policy_id,
                instant,
                policy.effective_from,
                policy.effective_until,
            ),
        )


def validate_split_bounds(
    policy: PolicyVersion, provider_share_bps: int
) -> None:
    """The developer-selected provider share must lie within the
    platform-declared constraint bounds of the cited immutable
    policy version."""
    if not (
        policy.provider_min_bps
        <= provider_share_bps
        <= policy.provider_max_bps
    ):
        raise AllocationError(
            AllocationReasonCode.SPLIT_OUT_OF_BOUNDS,
            "developer-selected provider share %d bps is outside the "
            "policy %s platform bounds [%d, %d] bps"
            % (
                provider_share_bps,
                policy.policy_id,
                policy.provider_min_bps,
                policy.provider_max_bps,
            ),
        )


# ---------------------------------------------------------------------------
# The external-reference resolution (the payment/settlement
# correlation discipline)
# ---------------------------------------------------------------------------


def _resolve_reference(
    command: AllocationCommand,
    index: AllocationEvidenceIndex,
    member: str,
) -> ExternalReferenceSnapshot:
    reference_id = command.payload.get(member)
    if not index.contains_reference(reference_id):
        raise AllocationError(
            AllocationReasonCode.REFERENCE_UNKNOWN,
            "external reference %r is not resolvable in the evidence "
            "index (fabricated, stale, or unauthorized citation)"
            % reference_id,
        )
    return index.reference(reference_id)


def _validate_reference_correlation(
    command: AllocationCommand,
    reference: ExternalReferenceSnapshot,
    *,
    member: str,
) -> None:
    correlated = reference.correlated_usage_transaction_id
    if correlated is not None and correlated != command.subject_id:
        raise AllocationError(
            AllocationReasonCode.REFERENCE_MISMATCH,
            "external reference %s correlates to usage transaction "
            "%s, not the command's subject %s (the external plane "
            "declared its own correlation; a mismatched citation "
            "fails closed)"
            % (
                command.payload.get(member),
                correlated,
                command.subject_id,
            ),
        )


def resolve_settlement_reference(
    command: AllocationCommand, index: AllocationEvidenceIndex
) -> ExternalReferenceSnapshot:
    """Resolve and gate the settlement-acknowledgement citation
    (the payment/settlement kind table + correlation)."""
    reference = _resolve_reference(
        command, index, "settlement_reference"
    )
    if reference.reference_kind != ReferenceKind.SETTLEMENT:
        raise AllocationError(
            AllocationReasonCode.PAYMENT_NOT_SETTLEMENT,
            "reference %s is a PAYMENT reference (DATA, never a "
            "settlement confirmation; a settlement acknowledgement "
            "cites the settlement plane only)"
            % command.payload.get("settlement_reference"),
        )
    _validate_reference_correlation(
        command, reference, member="settlement_reference"
    )
    return reference


def resolve_payment_reference(
    command: AllocationCommand, index: AllocationEvidenceIndex
) -> ExternalReferenceSnapshot:
    """Resolve and gate the provider-callback citation (the
    payment/settlement kind table + correlation)."""
    reference = _resolve_reference(command, index, "payment_reference")
    if reference.reference_kind != ReferenceKind.PAYMENT:
        raise AllocationError(
            AllocationReasonCode.SETTLEMENT_NOT_PAYMENT,
            "reference %s is a SETTLEMENT reference (never a payment "
            "callback; the payment-reference record cites the payment "
            "plane only)"
            % command.payload.get("payment_reference"),
        )
    _validate_reference_correlation(
        command, reference, member="payment_reference"
    )
    return reference


# ---------------------------------------------------------------------------
# Duplicate detection (idempotency layers)
# ---------------------------------------------------------------------------


def find_duplicate_payment_reference(
    command: AllocationCommand,
    transaction: Optional[AllocationTransaction],
) -> Optional[str]:
    """Callback-level duplicate detection (DATA idempotency).

    A payment callback whose external reference identity is
    already recorded on the allocation is a duplicate delivery of
    the same external event: an idempotent no-op (the DUPLICATE
    outcome returns the recorded payment-reference record id and
    NO new journal record, NO clock read, NO state change).  The
    external reference identity is the idempotency key; conflicting
    external correlations fail closed earlier at resolution
    (REFERENCE_MISMATCH), so a recorded duplicate is always the
    same external fact.
    """
    if transaction is None:
        return None
    payment_reference = command.payload.get("payment_reference")
    for record in transaction.payment_references:
        if record.payment_reference == payment_reference:
            return record.payment_reference_id
    return None


# ---------------------------------------------------------------------------
# The state gates
# ---------------------------------------------------------------------------


def validate_command_against_state(
    command: AllocationCommand,
    transaction: Optional[AllocationTransaction],
) -> None:
    """The state gates (fail closed; a rejection here may follow
    the single deterministic clock read, exactly like the W051/
    W052 state-gate layers)."""
    action = command.action
    if action == AllocationAction.REGISTER_POLICY:
        return  # the policy registry is stateless-by-version
    if action == AllocationAction.ALLOCATE:
        if transaction is not None:
            raise AllocationError(
                AllocationReasonCode.ALLOCATION_ALREADY_EXISTS,
                "usage transaction %s already carries allocation %s "
                "(exactly one allocation per billable-final usage "
                "record; re-allocation is a closed conflict, never a "
                "second allocation)"
                % (
                    command.subject_id,
                    transaction.snapshot.allocation_id,
                ),
            )
        return
    if transaction is None:
        raise AllocationError(
            AllocationReasonCode.ALLOCATION_UNKNOWN,
            "usage transaction %r has no allocation yet (payment "
            "references, settlement acknowledgements, and "
            "compensations cite an existing allocation; only ALLOCATE "
            "creates one)" % command.subject_id,
        )
    current_state = transaction.state
    if not transition_is_legal(current_state, action):
        if (
            current_state == AllocationSubjectState.SETTLED
            and action == AllocationAction.ACKNOWLEDGE_SETTLEMENT
        ):
            raise AllocationError(
                AllocationReasonCode.SETTLEMENT_IMMUTABLE,
                "allocation for %s is already settled (re-acknowledgement "
                "rejected; settled allocation history is immutable)"
                % command.subject_id,
            )
        if action in AllocationAction.compensation_actions():
            raise AllocationError(
                AllocationReasonCode.COMPENSATION_REQUIRES_SETTLED,
                "%s requires a settled allocation (compensations "
                "append against settled history; they never rewrite "
                "it)" % action,
            )
        raise AllocationError(
            AllocationReasonCode.EVENT_INVALID,
            "%s from %s is not in the frozen allocation transition "
            "table" % (action, current_state),
        )
    if action in AllocationAction.compensation_actions():
        kind = {
            AllocationAction.RECORD_REFUND: "refund",
            AllocationAction.RECORD_REVERSAL: "reversal",
            AllocationAction.RECORD_CHARGEBACK: "chargeback",
            AllocationAction.RECORD_PAYOUT_FAILURE: "payout-failure",
            AllocationAction.RECORD_DISPUTE: "dispute",
        }[action]
        if kind != "dispute":
            new_amount = command.payload["amount_micros"]
            cumulative = transaction.monetary_compensation_micros()
            if (
                cumulative + new_amount
                > transaction.snapshot.distributable_micros
            ):
                raise AllocationError(
                    AllocationReasonCode.COMPENSATION_EXCEEDED,
                    "cumulative monetary compensation %d + %d exceeds "
                    "the distributable allocation %d (the net never "
                    "goes negative; corrections are bounded "
                    "compensating records)"
                    % (
                        cumulative,
                        new_amount,
                        transaction.snapshot.distributable_micros,
                    ),
                )
        elif transaction.disputed():
            raise AllocationError(
                AllocationReasonCode.DISPUTE_ALREADY_OPEN,
                "allocation for %s already carries an open dispute (a "
                "second dispute record is rejected; dispute resolution "
                "is an external settlement concern)"
                % command.subject_id,
            )


def validate_event_instant(instant: object) -> None:
    """The deterministic event instant must be a well-formed RFC
    3339 UTC instant (the injected clock seam read)."""
    if (
        not isinstance(instant, str)
        or len(instant) != 20
        or instant[-1] != "Z"
    ):
        raise AllocationError(
            AllocationReasonCode.INSTANT_INVALID,
            "the allocation event instant must be RFC 3339 UTC "
            "(YYYY-MM-DDTHH:MM:SSZ)",
        )
