"""WORK-053 EconomicAllocation value model.

The canonical economic-allocation value vocabulary and the
content-derived identity/digest conventions (mirroring the
accepted W051/W052 model discipline):

- the frozen subject-state vocabularies (policy subjects:
  ``REGISTERED``; allocation subjects: ``PLANNED`` /
  ``SETTLED``) with the frozen action vocabulary and transition
  table;
- the frozen rounding-mode vocabulary (``floor`` / ``half-up`` /
  ``half-even``) and the exact integer split arithmetic
  (``compute_split``): adcos share = round(distributable *
  adcos_bps / 10^4), the post-ADCOS residual is split by the
  developer-selected provider share, and the developer share is
  the exact residual remainder -- so provider + developer +
  ADCOS allocations sum EXACTLY to the distributable amount by
  construction, and distributable + fees + taxes + adjustments
  sums exactly to the gross billable amount;
- :class:`AllocationCommand` (the caller-issued input with the
  idempotency key and content-derived digest),
  :class:`AllocationEvent` (the resulting derived fact with full
  attribution), :class:`PolicyVersion` (an immutable economic
  policy version), :class:`AllocationSnapshot` (the immutable
  three-way allocation fact), :class:`SettlementAcknowledgement`
  (the settlement-acknowledgement fact citing an external
  settlement reference), :class:`PaymentReferenceRecord` (an
  external payment reference recorded as DATA), and
  :class:`AllocationCompensationRecord` (an append-only
  refund/reversal/chargeback/payout-failure/dispute fact), plus
  :class:`AllocationTransaction` (the deterministic fold
  projection of one allocation subject);
- content-derived identities: every id is a ``sha256:``
  fingerprint over WORK-003 canonical JSON (identity DATA only:
  never a NodeID, never trust, never a session identity, never
  an authorization).

No floats anywhere: all amounts are integers in micro currency
units and every basis point is an integer (the canonical JSON
subset forbids floats), so all allocation arithmetic is exact
and deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import AllocationError, AllocationReasonCode
from .evidence import BillableUsageSnapshot


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_instant(value: object, label: str) -> str:
    """RFC 3339 UTC second-precision instant (WORK-003 style)."""
    text = _require_text(value, label)
    if len(text) != 20 or text[4] != "-" or text[7] != "-" or text[10] != "T":
        raise AllocationError(
            AllocationReasonCode.INSTANT_INVALID,
            "%s must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)" % label,
        )
    if text[-1] != "Z" or text[13] != ":" or text[16] != ":":
        raise AllocationError(
            AllocationReasonCode.INSTANT_INVALID,
            "%s must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)" % label,
        )
    return text


def _require_mapping(value: object, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "%s must be a mapping" % label,
        )
    return dict(value)


# ---------------------------------------------------------------------------
# The frozen state / action vocabularies and transition table
# ---------------------------------------------------------------------------


class PolicySubjectState:
    """The frozen policy-subject state vocabulary.

    A policy version is registered exactly once and is immutable
    thereafter: ``REGISTERED`` is the single state and the single
    self-edge (re-registration of identical terms is the
    idempotent no-op path; different terms derive a different
    policy version id and are a genuinely new version).
    """

    REGISTERED = "REGISTERED"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.REGISTERED,)


class AllocationSubjectState:
    """The frozen allocation-subject state vocabulary (one usage
    transaction's allocation walk).

    ``PLANNED``: the immutable allocation snapshot exists (the
    three-way plan over the billable-final usage fact); external
    payment references may already be recorded as DATA.
    ``SETTLED``: the settlement acknowledgement exists -- the
    allocation history is settled and immutable (no rewrite path
    exists); later corrections are append-only compensating
    allocation events, and late/delayed payment callbacks remain
    recordable DATA.
    """

    PLANNED = "PLANNED"
    SETTLED = "SETTLED"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.PLANNED, cls.SETTLED)


class AllocationAction:
    """The frozen EconomicAllocation action vocabulary.

    REGISTER_POLICY registers one immutable economic policy
    version.  ALLOCATE consumes one billable-final usage fact
    (the ONLY allocation-creating action, and it requires the
    BILLABLE_FINAL usage state).  ACKNOWLEDGE_SETTLEMENT records
    the settlement acknowledgement citing an external settlement
    reference.  RECORD_PAYMENT_REFERENCE records one external
    payment-provider callback as DATA (never state-transitioning,
    never allocation-creating).  RECORD_REFUND /
    RECORD_REVERSAL / RECORD_CHARGEBACK / RECORD_PAYOUT_FAILURE /
    RECORD_DISPUTE append compensating allocation events against
    a settled allocation (never history rewrites).
    """

    REGISTER_POLICY = "register-policy"
    ALLOCATE = "allocate"
    ACKNOWLEDGE_SETTLEMENT = "acknowledge-settlement"
    RECORD_PAYMENT_REFERENCE = "record-payment-reference"
    RECORD_REFUND = "record-refund"
    RECORD_REVERSAL = "record-reversal"
    RECORD_CHARGEBACK = "record-chargeback"
    RECORD_PAYOUT_FAILURE = "record-payout-failure"
    RECORD_DISPUTE = "record-dispute"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.REGISTER_POLICY,
            cls.ALLOCATE,
            cls.ACKNOWLEDGE_SETTLEMENT,
            cls.RECORD_PAYMENT_REFERENCE,
            cls.RECORD_REFUND,
            cls.RECORD_REVERSAL,
            cls.RECORD_CHARGEBACK,
            cls.RECORD_PAYOUT_FAILURE,
            cls.RECORD_DISPUTE,
        )

    @classmethod
    def compensation_actions(cls) -> Tuple[str, ...]:
        return (
            cls.RECORD_REFUND,
            cls.RECORD_REVERSAL,
            cls.RECORD_CHARGEBACK,
            cls.RECORD_PAYOUT_FAILURE,
            cls.RECORD_DISPUTE,
        )


#: The frozen allocation transition table.  Policy subjects walk
#: the single REGISTERED self-edge; allocation subjects are
#: created by ALLOCATE at PLANNED (the creation self-edge),
#: settlement acknowledgement moves PLANNED -> SETTLED exactly
#: once (re-ack fails closed SETTLEMENT_IMMUTABLE), payment
#: references are state-preserving DATA at either state, and
#: compensations append only after settlement (SETTLED ->
#: SETTLED: state unchanged, fact appended, attribution
#: preserved).
ALLOCATION_TRANSITIONS: Dict[Tuple[str, str], str] = {
    (PolicySubjectState.REGISTERED, AllocationAction.REGISTER_POLICY): (
        PolicySubjectState.REGISTERED
    ),
    (AllocationSubjectState.PLANNED, AllocationAction.ALLOCATE): (
        AllocationSubjectState.PLANNED
    ),
    (AllocationSubjectState.PLANNED, AllocationAction.RECORD_PAYMENT_REFERENCE): (  # noqa: E501
        AllocationSubjectState.PLANNED
    ),
    (AllocationSubjectState.PLANNED, AllocationAction.ACKNOWLEDGE_SETTLEMENT): (  # noqa: E501
        AllocationSubjectState.SETTLED
    ),
    (AllocationSubjectState.SETTLED, AllocationAction.RECORD_PAYMENT_REFERENCE): (  # noqa: E501
        AllocationSubjectState.SETTLED
    ),
    (AllocationSubjectState.SETTLED, AllocationAction.RECORD_REFUND): (
        AllocationSubjectState.SETTLED
    ),
    (AllocationSubjectState.SETTLED, AllocationAction.RECORD_REVERSAL): (
        AllocationSubjectState.SETTLED
    ),
    (AllocationSubjectState.SETTLED, AllocationAction.RECORD_CHARGEBACK): (
        AllocationSubjectState.SETTLED
    ),
    (AllocationSubjectState.SETTLED, AllocationAction.RECORD_PAYOUT_FAILURE): (  # noqa: E501
        AllocationSubjectState.SETTLED
    ),
    (AllocationSubjectState.SETTLED, AllocationAction.RECORD_DISPUTE): (
        AllocationSubjectState.SETTLED
    ),
}


def transition_target(from_state: str, action: str) -> str:
    """The frozen-table target state (KeyError = illegal pair).

    Fail closed: the admission layer translates an illegal
    (state, action) pair into the typed state-gate error; this
    function itself is table-only (the model gate).
    """
    return ALLOCATION_TRANSITIONS[(from_state, action)]


def transition_is_legal(from_state: str, action: str) -> bool:
    return (from_state, action) in ALLOCATION_TRANSITIONS


#: The complete frozen subject-state vocabulary (events validate
#: their from/to members against this union; the subject-kind
#: routing in the fold keeps the two families disjoint).
SUBJECT_STATE_VALUES: Tuple[str, ...] = (
    PolicySubjectState.REGISTERED,
    AllocationSubjectState.PLANNED,
    AllocationSubjectState.SETTLED,
)


# ---------------------------------------------------------------------------
# The frozen rounding vocabulary and the exact split arithmetic
# ---------------------------------------------------------------------------


class RoundingMode:
    """The frozen allocation rounding-mode vocabulary.

    Every share division is an exact integer operation with a
    DECLARED tie/remainder behavior; the declared mode is carried
    immutably by the policy version and re-cited by the
    allocation snapshot, so the same (distributable, bps, mode)
    triple always derives byte-identical shares.
    """

    FLOOR = "floor"
    HALF_UP = "half-up"
    HALF_EVEN = "half-even"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.FLOOR, cls.HALF_UP, cls.HALF_EVEN)


#: The canonical basis-point denominator (shares are declared in
#: hundredths of a percent, exactly as the policy model requires).
BPS_DENOMINATOR = 10_000


def apply_rounding(numerator: int, denominator: int, mode: str) -> int:
    """Exact integer division with the declared rounding mode.

    Deterministic pure integer arithmetic (no floats): ``floor``
    truncates; ``half-up`` rounds remainders >= half up; ``half-even``
    (banker's rounding) resolves exact halves to the even
    quotient.  Requires a positive denominator and a non-negative
    numerator (the allocation domain guarantees both: amounts are
    non-negative integers and basis points are non-negative).
    """
    if not isinstance(numerator, int) or isinstance(numerator, bool):
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "rounding numerator must be an integer",
        )
    if not isinstance(denominator, int) or isinstance(denominator, bool):
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "rounding denominator must be an integer",
        )
    if denominator <= 0:
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "rounding denominator must be positive",
        )
    if numerator < 0:
        raise AllocationError(
            AllocationReasonCode.INVALID_INPUT,
            "rounding numerator must be non-negative",
        )
    if mode == RoundingMode.FLOOR:
        return numerator // denominator
    quotient, remainder = divmod(numerator, denominator)
    if mode == RoundingMode.HALF_UP:
        if 2 * remainder >= denominator:
            return quotient + 1
        return quotient
    if mode == RoundingMode.HALF_EVEN:
        if 2 * remainder > denominator:
            return quotient + 1
        if 2 * remainder == denominator and quotient % 2 == 1:
            return quotient + 1
        return quotient
    raise AllocationError(
        AllocationReasonCode.INVALID_INPUT,
        "rounding mode %r must be one of %s"
        % (mode, list(RoundingMode.values())),
    )


def compute_split(
    distributable_micros: int,
    adcos_share_bps: int,
    provider_share_bps: int,
    rounding_mode: str,
) -> Tuple[int, int, int]:
    """The exact three-way split (adcos, provider, developer).

    Deterministic and exactly conservative by construction:
    the ADCOS platform share is the declared-bps share of the
    distributable amount under the policy's rounding mode; the
    post-ADCOS residual is split by the developer-selected
    provider share under the SAME mode; the developer share is
    the exact remainder.  adcos + provider + developer ==
    distributable ALWAYS, for every rounding mode and every bps
    pair -- no rounding residue leaks and no cent is minted or
    destroyed.
    """
    adcos_share_micros = apply_rounding(
        distributable_micros * adcos_share_bps,
        BPS_DENOMINATOR,
        rounding_mode,
    )
    residual_micros = distributable_micros - adcos_share_micros
    provider_share_micros = apply_rounding(
        residual_micros * provider_share_bps,
        BPS_DENOMINATOR,
        rounding_mode,
    )
    developer_share_micros = residual_micros - provider_share_micros
    return (adcos_share_micros, provider_share_micros, developer_share_micros)


# ---------------------------------------------------------------------------
# Content-derived identities
# ---------------------------------------------------------------------------


def command_content(
    command_id: str,
    action: str,
    subject_id: str,
    payload: Mapping[str, Any],
    actor: str,
    source: str,
) -> Dict[str, Any]:
    """The canonical command content (digest basis + journal DATA)."""
    return {
        "command_id": command_id,
        "action": action,
        "subject_id": subject_id,
        "payload": dict(payload),
        "actor": actor,
        "source": source,
    }


def derive_command_digest(
    command_id: str,
    action: str,
    subject_id: str,
    payload: Mapping[str, Any],
    actor: str,
    source: str,
) -> str:
    """The content-derived command digest (idempotency ledger).

    Same command id + same content -> same digest (idempotent
    no-op on redelivery); same command id + different content ->
    ``COMMAND_CONFLICT`` (fail closed).
    """
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            command_content(
                command_id, action, subject_id, payload, actor, source
            )
        )
    ).hexdigest()


def derive_policy_id(
    label: str,
    adcos_share_bps: int,
    provider_min_bps: int,
    provider_max_bps: int,
    rounding_mode: str,
    currency: str,
    minor_unit_digits: int,
    effective_from: str,
    effective_until: str,
) -> str:
    """The content-derived policy-version id.

    Binds the version to its TERMS ONLY (never the registering
    command id, never the registration instant): identical terms
    derive the identical version id -- the immutable-policy-
    version identity -- while any term change derives a genuinely
    new version.
    """
    content = {
        "kind": "economic-policy-version",
        "label": label,
        "adcos_share_bps": adcos_share_bps,
        "provider_min_bps": provider_min_bps,
        "provider_max_bps": provider_max_bps,
        "rounding_mode": rounding_mode,
        "currency": currency,
        "minor_unit_digits": minor_unit_digits,
        "effective_from": effective_from,
        "effective_until": effective_until,
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def derive_allocation_id(
    usage_transaction_id: str,
    usage_statement_id: str,
    policy_id: str,
    provider_share_bps: int,
    fee_micros: int,
    tax_micros: int,
    adjustment_micros: int,
    created_at: str,
) -> str:
    """The content-derived allocation-snapshot fact id.

    Binds the allocation to its consumed billable-final usage
    record, its immutable policy version, the developer-selected
    split, the declared fees/taxes/adjustments, and the
    deterministic creation instant.
    """
    content = {
        "kind": "allocation-snapshot",
        "usage_transaction_id": usage_transaction_id,
        "usage_statement_id": usage_statement_id,
        "policy_id": policy_id,
        "provider_share_bps": provider_share_bps,
        "fee_micros": fee_micros,
        "tax_micros": tax_micros,
        "adjustment_micros": adjustment_micros,
        "created_at": created_at,
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def derive_settlement_ack_id(
    usage_transaction_id: str,
    allocation_id: str,
    settlement_reference: str,
    command_id: str,
    acknowledged_at: str,
) -> str:
    """The content-derived settlement-acknowledgement fact id."""
    content = {
        "kind": "settlement-acknowledgement",
        "usage_transaction_id": usage_transaction_id,
        "allocation_id": allocation_id,
        "settlement_reference": settlement_reference,
        "command_id": command_id,
        "acknowledged_at": acknowledged_at,
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def derive_payment_reference_id(
    usage_transaction_id: str,
    allocation_id: str,
    payment_reference: str,
    command_id: str,
    recorded_at: str,
) -> str:
    """The content-derived payment-reference record id.

    Binds the DATA record to the external reference identity it
    cites, the allocation it correlates to, its causal command,
    and the deterministic recording instant -- the
    callback-level idempotency identity.
    """
    content = {
        "kind": "payment-reference-record",
        "usage_transaction_id": usage_transaction_id,
        "allocation_id": allocation_id,
        "payment_reference": payment_reference,
        "command_id": command_id,
        "recorded_at": recorded_at,
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def derive_compensation_id(
    usage_transaction_id: str,
    compensation_kind: str,
    amount_micros: int,
    reason: str,
    allocation_id: str,
    command_id: str,
    recorded_at: str,
) -> str:
    """The content-derived compensating-allocation-event id."""
    content = {
        "kind": "allocation-compensation",
        "usage_transaction_id": usage_transaction_id,
        "compensation_kind": compensation_kind,
        "amount_micros": amount_micros,
        "reason": reason,
        "allocation_id": allocation_id,
        "command_id": command_id,
        "recorded_at": recorded_at,
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def derive_event_id(
    subject_id: str,
    action: str,
    from_state: str,
    to_state: str,
    command_id: str,
    fact_id: str,
    instant: str,
) -> str:
    """Content-derived allocation event id (journal identity
    DATA)."""
    content = {
        "subject_id": subject_id,
        "action": action,
        "from_state": from_state,
        "to_state": to_state,
        "command_id": command_id,
        "fact_id": fact_id,
        "instant": instant,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


# ---------------------------------------------------------------------------
# Allocation command (the input record)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllocationCommand:
    """One caller-issued economic-allocation command.

    ``command_id`` is the caller's idempotency key (redelivery
    with the same id and content is a no-op, redelivery with
    different content fails closed COMMAND_CONFLICT).
    ``subject_id`` is the command's subject citation: the policy
    LABEL for REGISTER_POLICY, and the cited WORK-052 usage
    transaction id for every allocation-subject action (the
    allocation projection is keyed by the usage transaction --
    exactly one allocation per billable-final usage record).
    ``payload`` carries the action-specific members
    (shape-validated at admission).  ``actor`` / ``source``
    attribute the command.
    """

    command_id: str
    action: str
    subject_id: str
    payload: Mapping[str, Any]
    actor: str
    source: str

    def __post_init__(self) -> None:
        _require_text(self.command_id, "command_id")
        if self.action not in AllocationAction.values():
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "action %r must be one of %s"
                % (self.action, list(AllocationAction.values())),
            )
        _require_text(self.subject_id, "subject_id")
        _require_mapping(self.payload, "payload")
        _require_text(self.actor, "actor")
        _require_text(self.source, "source")

    def digest(self) -> str:
        return derive_command_digest(
            self.command_id,
            self.action,
            self.subject_id,
            self.payload,
            self.actor,
            self.source,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "action": self.action,
            "subject_id": self.subject_id,
            "payload": dict(self.payload),
            "actor": self.actor,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: object) -> "AllocationCommand":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.INVALID_INPUT,
                "allocation command must be a mapping",
            )
        for key in (
            "command_id",
            "action",
            "subject_id",
            "payload",
            "actor",
            "source",
        ):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.INVALID_INPUT,
                    "allocation command is missing required member %r"
                    % key,
                )
        return cls(
            command_id=data["command_id"],
            action=data["action"],
            subject_id=data["subject_id"],
            payload=data["payload"],
            actor=data["actor"],
            source=data["source"],
        )


# ---------------------------------------------------------------------------
# The derived fact records (journal event payloads)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyVersion:
    """One immutable economic policy version (REGISTER_POLICY).

    The versioned revenue-share contract: the ADCOS platform
    share, the platform constraint bounds on the developer-
    selectable provider share (of the post-ADCOS residual), the
    declared rounding mode, the currency and its minor-unit
    precision, and the effective window.  ``policy_id`` derives
    from the TERMS ONLY (never the command or instant), so
    identical terms always mean the identical version.
    """

    policy_id: str
    label: str
    adcos_share_bps: int
    provider_min_bps: int
    provider_max_bps: int
    rounding_mode: str
    currency: str
    minor_unit_digits: int
    effective_from: str
    effective_until: str
    command_id: str
    registered_at: str

    def __post_init__(self) -> None:
        _require_text(self.policy_id, "policy_id")
        _require_text(self.label, "label")
        for label in (
            "adcos_share_bps",
            "provider_min_bps",
            "provider_max_bps",
            "minor_unit_digits",
        ):
            value = getattr(self, label)
            if not isinstance(value, int) or isinstance(value, bool):
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "%s must be an integer" % label,
                )
        if not 0 <= self.adcos_share_bps <= BPS_DENOMINATOR:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "adcos_share_bps %d must be within [0, %d]"
                % (self.adcos_share_bps, BPS_DENOMINATOR),
            )
        if not 0 <= self.provider_min_bps <= BPS_DENOMINATOR:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "provider_min_bps %d must be within [0, %d]"
                % (self.provider_min_bps, BPS_DENOMINATOR),
            )
        if not 0 <= self.provider_max_bps <= BPS_DENOMINATOR:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "provider_max_bps %d must be within [0, %d]"
                % (self.provider_max_bps, BPS_DENOMINATOR),
            )
        if self.provider_min_bps > self.provider_max_bps:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "provider_min_bps %d must not exceed provider_max_bps %d"
                % (self.provider_min_bps, self.provider_max_bps),
            )
        if self.rounding_mode not in RoundingMode.values():
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "rounding_mode %r must be one of %s"
                % (self.rounding_mode, list(RoundingMode.values())),
            )
        _require_text(self.currency, "currency")
        if not 0 <= self.minor_unit_digits <= 6:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "minor_unit_digits %d must be within [0, 6] (the "
                "canonical micro-integer precision range)"
                % self.minor_unit_digits,
            )
        _require_instant(self.effective_from, "effective_from")
        _require_instant(self.effective_until, "effective_until")
        if self.effective_until < self.effective_from:
            raise AllocationError(
                AllocationReasonCode.POLICY_INVALID,
                "effective_until %s must not precede effective_from %s"
                % (self.effective_until, self.effective_from),
            )
        _require_text(self.command_id, "command_id")
        _require_instant(self.registered_at, "registered_at")

    def is_effective(self, instant: str) -> bool:
        """The declared effective window contains the instant
        (inclusive both ends; the window is deterministic policy
        DATA, never a wall-clock read)."""
        return self.effective_from <= instant <= self.effective_until

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "policy-version-record",
            "policy_id": self.policy_id,
            "label": self.label,
            "adcos_share_bps": self.adcos_share_bps,
            "provider_min_bps": self.provider_min_bps,
            "provider_max_bps": self.provider_max_bps,
            "rounding_mode": self.rounding_mode,
            "currency": self.currency,
            "minor_unit_digits": self.minor_unit_digits,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "command_id": self.command_id,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PolicyVersion":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "policy version record must be a mapping",
            )
        for key in (
            "policy_id",
            "label",
            "adcos_share_bps",
            "provider_min_bps",
            "provider_max_bps",
            "rounding_mode",
            "currency",
            "minor_unit_digits",
            "effective_from",
            "effective_until",
            "command_id",
            "registered_at",
        ):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "policy version record is missing member %r" % key,
                )
        return cls(
            policy_id=data["policy_id"],
            label=data["label"],
            adcos_share_bps=data["adcos_share_bps"],
            provider_min_bps=data["provider_min_bps"],
            provider_max_bps=data["provider_max_bps"],
            rounding_mode=data["rounding_mode"],
            currency=data["currency"],
            minor_unit_digits=data["minor_unit_digits"],
            effective_from=data["effective_from"],
            effective_until=data["effective_until"],
            command_id=data["command_id"],
            registered_at=data["registered_at"],
        )


@dataclass(frozen=True)
class AllocationSnapshot:
    """The immutable three-way allocation fact (ALLOCATE).

    The exact economic plan over ONE billable-final usage record
    under ONE immutable policy version: the gross billable amount
    (re-bound at replay to the injected W052 usage snapshot), the
    explicitly declared fees/taxes/adjustments, the distributable
    amount, and the exactly conservative three-way
    provider/developer/ADCOS split computed by
    :func:`compute_split` under the policy's declared rounding
    mode.  Conservation is a MECHANICAL invariant of this record:
    ``adcos + provider + developer == distributable`` and
    ``distributable + fee + tax + adjustment == gross`` always,
    verified at construction and re-verified by re-derivation at
    replay -- an arithmetic-consistent forgery still fails the
    full re-derivation, and an arithmetic-inconsistent fact fails
    immediately.  There is no mutation path: corrections are
    append-only compensating allocation events.
    """

    allocation_id: str
    usage_transaction_id: str
    usage_statement_id: str
    policy_id: str
    gross_micros: int
    fee_micros: int
    tax_micros: int
    adjustment_micros: int
    distributable_micros: int
    adcos_share_micros: int
    provider_share_micros: int
    developer_share_micros: int
    provider_share_bps: int
    adcos_share_bps: int
    rounding_mode: str
    currency: str
    minor_unit_digits: int
    created_at: str

    def __post_init__(self) -> None:
        _require_text(self.allocation_id, "allocation_id")
        _require_text(self.usage_transaction_id, "usage_transaction_id")
        _require_text(self.usage_statement_id, "usage_statement_id")
        _require_text(self.policy_id, "policy_id")
        for label in (
            "gross_micros",
            "fee_micros",
            "tax_micros",
            "adjustment_micros",
            "distributable_micros",
            "adcos_share_micros",
            "provider_share_micros",
            "developer_share_micros",
            "provider_share_bps",
            "adcos_share_bps",
        ):
            value = getattr(self, label)
            if not isinstance(value, int) or isinstance(value, bool):
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "%s must be an integer" % label,
                )
        if self.gross_micros < 0:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "gross_micros must be >= 0",
            )
        if self.fee_micros < 0 or self.tax_micros < 0:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "fee/tax amounts must be >= 0 (explicitly modeled "
                "charges are never negative; an adjustment carries "
                "the credit direction)",
            )
        if (
            self.distributable_micros < 0
            or self.distributable_micros > self.gross_micros
        ):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "distributable_micros must be within [0, gross_micros]",
            )
        if (
            self.distributable_micros
            != self.gross_micros
            - self.fee_micros
            - self.tax_micros
            - self.adjustment_micros
        ):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "conservation violated: distributable %d != gross %d "
                "- fee %d - tax %d - adjustment %d (the exact "
                "post-fee/tax/adjustment derivation)"
                % (
                    self.distributable_micros,
                    self.gross_micros,
                    self.fee_micros,
                    self.tax_micros,
                    self.adjustment_micros,
                ),
            )
        if (
            self.adcos_share_micros
            + self.provider_share_micros
            + self.developer_share_micros
            != self.distributable_micros
        ):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "conservation violated: adcos %d + provider %d + "
                "developer %d != distributable %d (the three-way "
                "sum is exact, always)"
                % (
                    self.adcos_share_micros,
                    self.provider_share_micros,
                    self.developer_share_micros,
                    self.distributable_micros,
                ),
            )
        if self.rounding_mode not in RoundingMode.values():
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "rounding_mode %r is not in the frozen vocabulary"
                % self.rounding_mode,
            )
        if not 0 <= self.provider_share_bps <= BPS_DENOMINATOR:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "provider_share_bps %d must be within [0, %d]"
                % (self.provider_share_bps, BPS_DENOMINATOR),
            )
        if not 0 <= self.adcos_share_bps <= BPS_DENOMINATOR:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "adcos_share_bps %d must be within [0, %d]"
                % (self.adcos_share_bps, BPS_DENOMINATOR),
            )
        expected_split = compute_split(
            self.distributable_micros,
            self.adcos_share_bps,
            self.provider_share_bps,
            self.rounding_mode,
        )
        if (
            self.adcos_share_micros,
            self.provider_share_micros,
            self.developer_share_micros,
        ) != expected_split:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "the recorded split (%d, %d, %d) is not the exact "
                "deterministic derivation over (distributable %d, "
                "adcos bps %d, provider bps %d, mode %s) = %r (a "
                "self-consistent-but-repriced fact is still a "
                "tampered fact)"
                % (
                    self.adcos_share_micros,
                    self.provider_share_micros,
                    self.developer_share_micros,
                    self.distributable_micros,
                    self.adcos_share_bps,
                    self.provider_share_bps,
                    self.rounding_mode,
                    expected_split,
                ),
            )
        _require_text(self.currency, "currency")
        if not 0 <= self.minor_unit_digits <= 6:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "minor_unit_digits %d must be within [0, 6]"
                % self.minor_unit_digits,
            )
        _require_instant(self.created_at, "created_at")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "allocation-snapshot-record",
            "allocation_id": self.allocation_id,
            "usage_transaction_id": self.usage_transaction_id,
            "usage_statement_id": self.usage_statement_id,
            "policy_id": self.policy_id,
            "gross_micros": self.gross_micros,
            "fee_micros": self.fee_micros,
            "tax_micros": self.tax_micros,
            "adjustment_micros": self.adjustment_micros,
            "distributable_micros": self.distributable_micros,
            "adcos_share_micros": self.adcos_share_micros,
            "provider_share_micros": self.provider_share_micros,
            "developer_share_micros": self.developer_share_micros,
            "provider_share_bps": self.provider_share_bps,
            "adcos_share_bps": self.adcos_share_bps,
            "rounding_mode": self.rounding_mode,
            "currency": self.currency,
            "minor_unit_digits": self.minor_unit_digits,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "AllocationSnapshot":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "allocation snapshot must be a mapping",
            )
        for key in (
            "allocation_id",
            "usage_transaction_id",
            "usage_statement_id",
            "policy_id",
            "gross_micros",
            "fee_micros",
            "tax_micros",
            "adjustment_micros",
            "distributable_micros",
            "adcos_share_micros",
            "provider_share_micros",
            "developer_share_micros",
            "provider_share_bps",
            "adcos_share_bps",
            "rounding_mode",
            "currency",
            "minor_unit_digits",
            "created_at",
        ):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "allocation snapshot is missing member %r" % key,
                )
        return cls(
            allocation_id=data["allocation_id"],
            usage_transaction_id=data["usage_transaction_id"],
            usage_statement_id=data["usage_statement_id"],
            policy_id=data["policy_id"],
            gross_micros=data["gross_micros"],
            fee_micros=data["fee_micros"],
            tax_micros=data["tax_micros"],
            adjustment_micros=data["adjustment_micros"],
            distributable_micros=data["distributable_micros"],
            adcos_share_micros=data["adcos_share_micros"],
            provider_share_micros=data["provider_share_micros"],
            developer_share_micros=data["developer_share_micros"],
            provider_share_bps=data["provider_share_bps"],
            adcos_share_bps=data["adcos_share_bps"],
            rounding_mode=data["rounding_mode"],
            currency=data["currency"],
            minor_unit_digits=data["minor_unit_digits"],
            created_at=data["created_at"],
        )


@dataclass(frozen=True)
class SettlementAcknowledgement:
    """The settlement-acknowledgement fact
    (ACKNOWLEDGE_SETTLEMENT).

    Records that the external settlement plane confirmed the
    settlement of ONE allocation, citing the external settlement
    reference (DATA: the reference identifies external movement;
    it is never commercial truth and never reprices or rewrites
    the allocation).  The acknowledgement is the explicit
    PLANNED -> SETTLED transition; it happens exactly once
    (re-ack fails closed).
    """

    acknowledgement_id: str
    usage_transaction_id: str
    allocation_id: str
    settlement_reference: str
    command_id: str
    acknowledged_at: str

    def __post_init__(self) -> None:
        _require_text(self.acknowledgement_id, "acknowledgement_id")
        _require_text(self.usage_transaction_id, "usage_transaction_id")
        _require_text(self.allocation_id, "allocation_id")
        _require_text(
            self.settlement_reference, "settlement_reference"
        )
        _require_text(self.command_id, "command_id")
        _require_instant(self.acknowledged_at, "acknowledged_at")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "settlement-acknowledgement-record",
            "acknowledgement_id": self.acknowledgement_id,
            "usage_transaction_id": self.usage_transaction_id,
            "allocation_id": self.allocation_id,
            "settlement_reference": self.settlement_reference,
            "command_id": self.command_id,
            "acknowledged_at": self.acknowledged_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "SettlementAcknowledgement":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "settlement acknowledgement must be a mapping",
            )
        for key in (
            "acknowledgement_id",
            "usage_transaction_id",
            "allocation_id",
            "settlement_reference",
            "command_id",
            "acknowledged_at",
        ):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "settlement acknowledgement is missing member %r"
                    % key,
                )
        return cls(
            acknowledgement_id=data["acknowledgement_id"],
            usage_transaction_id=data["usage_transaction_id"],
            allocation_id=data["allocation_id"],
            settlement_reference=data["settlement_reference"],
            command_id=data["command_id"],
            acknowledged_at=data["acknowledged_at"],
        )


@dataclass(frozen=True)
class PaymentReferenceRecord:
    """One external payment-provider reference recorded as DATA
    (RECORD_PAYMENT_REFERENCE).

    The provider-callback boundary record: it cites the external
    reference identity, correlates it to one allocation, and
    carries the full command attribution.  It NEVER transitions
    allocation state (the walk edge is a self-loop at PLANNED or
    SETTLED), NEVER creates or reprices allocation, and NEVER
    carries an amount, counterparty, or provider semantic --
    failed, duplicate, delayed, or out-of-order callbacks are
    idempotent or append-only DATA and cannot corrupt canonical
    allocation state.
    """

    payment_reference_id: str
    usage_transaction_id: str
    allocation_id: str
    payment_reference: str
    command_id: str
    recorded_at: str

    def __post_init__(self) -> None:
        _require_text(
            self.payment_reference_id, "payment_reference_id"
        )
        _require_text(self.usage_transaction_id, "usage_transaction_id")
        _require_text(self.allocation_id, "allocation_id")
        _require_text(self.payment_reference, "payment_reference")
        _require_text(self.command_id, "command_id")
        _require_instant(self.recorded_at, "recorded_at")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "payment-reference-record",
            "payment_reference_id": self.payment_reference_id,
            "usage_transaction_id": self.usage_transaction_id,
            "allocation_id": self.allocation_id,
            "payment_reference": self.payment_reference,
            "command_id": self.command_id,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PaymentReferenceRecord":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "payment reference record must be a mapping",
            )
        for key in (
            "payment_reference_id",
            "usage_transaction_id",
            "allocation_id",
            "payment_reference",
            "command_id",
            "recorded_at",
        ):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "payment reference record is missing member %r"
                    % key,
                )
        return cls(
            payment_reference_id=data["payment_reference_id"],
            usage_transaction_id=data["usage_transaction_id"],
            allocation_id=data["allocation_id"],
            payment_reference=data["payment_reference"],
            command_id=data["command_id"],
            recorded_at=data["recorded_at"],
        )


@dataclass(frozen=True)
class AllocationCompensationRecord:
    """One append-only compensating allocation event.

    Kinds: ``refund`` / ``reversal`` / ``chargeback`` /
    ``payout-failure`` (monetary: the amount adjusts the net
    allocation) and ``dispute`` (non-monetary: the amount is
    pinned to 0; a dispute may be followed by monetary
    compensation records, but the dispute itself never rewrites
    history).  Every compensation cites the immutable allocation
    snapshot it compensates.  There is no mutation, removal, or
    rewrite path for a compensation record.
    """

    compensation_id: str
    usage_transaction_id: str
    compensation_kind: str
    amount_micros: int
    reason: str
    allocation_id: str
    command_id: str
    recorded_at: str

    def __post_init__(self) -> None:
        _require_text(self.compensation_id, "compensation_id")
        _require_text(self.usage_transaction_id, "usage_transaction_id")
        if self.compensation_kind not in (
            "refund",
            "reversal",
            "chargeback",
            "payout-failure",
            "dispute",
        ):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "compensation_kind %r must be refund/reversal/"
                "chargeback/payout-failure/dispute"
                % self.compensation_kind,
            )
        if not isinstance(self.amount_micros, int) or isinstance(
            self.amount_micros, bool
        ):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "amount_micros must be an integer",
            )
        if self.compensation_kind == "dispute" and self.amount_micros != 0:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "a dispute record is non-monetary (amount pinned to 0; "
                "the monetary compensation is a separate "
                "refund/reversal/chargeback/payout-failure record)",
            )
        if (
            self.compensation_kind
            in ("refund", "reversal", "chargeback", "payout-failure")
            and self.amount_micros < 1
        ):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "a refund/reversal/chargeback/payout-failure record "
                "must carry amount >= 1",
            )
        _require_text(self.reason, "reason")
        _require_text(self.allocation_id, "allocation_id")
        _require_text(self.command_id, "command_id")
        _require_instant(self.recorded_at, "recorded_at")

    def is_monetary(self) -> bool:
        return self.compensation_kind != "dispute"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "allocation-compensation-record",
            "compensation_id": self.compensation_id,
            "usage_transaction_id": self.usage_transaction_id,
            "compensation_kind": self.compensation_kind,
            "amount_micros": self.amount_micros,
            "reason": self.reason,
            "allocation_id": self.allocation_id,
            "command_id": self.command_id,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "AllocationCompensationRecord":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "allocation compensation record must be a mapping",
            )
        for key in (
            "compensation_id",
            "usage_transaction_id",
            "compensation_kind",
            "amount_micros",
            "reason",
            "allocation_id",
            "command_id",
            "recorded_at",
        ):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "allocation compensation record is missing member "
                    "%r" % key,
                )
        return cls(
            compensation_id=data["compensation_id"],
            usage_transaction_id=data["usage_transaction_id"],
            compensation_kind=data["compensation_kind"],
            amount_micros=data["amount_micros"],
            reason=data["reason"],
            allocation_id=data["allocation_id"],
            command_id=data["command_id"],
            recorded_at=data["recorded_at"],
        )


#: The frozen compensation-kind table keyed by action.
COMPENSATION_KIND_BY_ACTION: Dict[str, str] = {
    AllocationAction.RECORD_REFUND: "refund",
    AllocationAction.RECORD_REVERSAL: "reversal",
    AllocationAction.RECORD_CHARGEBACK: "chargeback",
    AllocationAction.RECORD_PAYOUT_FAILURE: "payout-failure",
    AllocationAction.RECORD_DISPUTE: "dispute",
}


#: The monetary compensation kinds (the net-adjusting family).
MONETARY_COMPENSATION_KINDS = (
    "refund",
    "reversal",
    "chargeback",
    "payout-failure",
)


# ---------------------------------------------------------------------------
# Allocation event (the journal event record)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllocationEvent:
    """One derived allocation fact with full attribution.

    Carries the subject citation (the policy label for policy
    subjects; the cited usage transaction id for allocation
    subjects -- identical to the causal command's subject), the
    action, the from/to state attribution (the allocation walk),
    the causal command id, the derived fact record (policy
    version / allocation snapshot / settlement acknowledgement /
    payment reference / compensation -- a tagged mapping), the
    actor, the source, and the deterministic event instant (an
    injected WORK-033 clock read).  ``event_id`` is the
    content-derived fingerprint over the full attribution + fact.
    """

    event_id: str
    subject_id: str
    action: str
    from_state: str
    to_state: str
    command_id: str
    fact: Mapping[str, Any]
    actor: str
    source: str
    instant: str

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.subject_id, "subject_id")
        if self.action not in AllocationAction.values():
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "event action %r is not in the frozen vocabulary"
                % self.action,
            )
        if self.from_state not in SUBJECT_STATE_VALUES:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "event from_state %r is not in the frozen vocabulary"
                % self.from_state,
            )
        if self.to_state not in SUBJECT_STATE_VALUES:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "event to_state %r is not in the frozen vocabulary"
                % self.to_state,
            )
        _require_text(self.command_id, "command_id")
        _require_mapping(self.fact, "fact")
        _require_text(self.actor, "actor")
        _require_text(self.source, "source")
        _require_instant(self.instant, "instant")

    def policy_version(self) -> Optional[PolicyVersion]:
        if self.fact.get("kind") == "policy-version-record":
            return PolicyVersion.from_dict(self.fact)
        return None

    def allocation_snapshot(self) -> Optional[AllocationSnapshot]:
        if self.fact.get("kind") == "allocation-snapshot-record":
            return AllocationSnapshot.from_dict(self.fact)
        return None

    def settlement_acknowledgement(
        self,
    ) -> Optional[SettlementAcknowledgement]:
        if self.fact.get("kind") == "settlement-acknowledgement-record":
            return SettlementAcknowledgement.from_dict(self.fact)
        return None

    def payment_reference(self) -> Optional[PaymentReferenceRecord]:
        if self.fact.get("kind") == "payment-reference-record":
            return PaymentReferenceRecord.from_dict(self.fact)
        return None

    def compensation(self) -> Optional[AllocationCompensationRecord]:
        if self.fact.get("kind") == "allocation-compensation-record":
            return AllocationCompensationRecord.from_dict(self.fact)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "subject_id": self.subject_id,
            "action": self.action,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "command_id": self.command_id,
            "fact": dict(self.fact),
            "actor": self.actor,
            "source": self.source,
            "instant": self.instant,
        }

    @classmethod
    def from_dict(cls, data: object) -> "AllocationEvent":
        if not isinstance(data, Mapping):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "allocation event must be a mapping",
            )
        for key in (
            "event_id",
            "subject_id",
            "action",
            "from_state",
            "to_state",
            "command_id",
            "fact",
            "actor",
            "source",
            "instant",
        ):
            if key not in data:
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "allocation event is missing member %r" % key,
                )
        return cls(
            event_id=data["event_id"],
            subject_id=data["subject_id"],
            action=data["action"],
            from_state=data["from_state"],
            to_state=data["to_state"],
            command_id=data["command_id"],
            fact=data["fact"],
            actor=data["actor"],
            source=data["source"],
            instant=data["instant"],
        )


def event_list_digest(events: Tuple[AllocationEvent, ...]) -> str:
    """Deterministic digest over the ordered event list."""
    content = {
        "kind": "allocation-event-list",
        "events": [event.event_id for event in events],
        "count": len(events),
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


# ---------------------------------------------------------------------------
# The single allocation-snapshot derivation (admission AND replay)
# ---------------------------------------------------------------------------


def build_allocation_snapshot(
    *,
    usage_transaction_id: str,
    usage_snapshot: BillableUsageSnapshot,
    policy: PolicyVersion,
    provider_share_bps: int,
    fee_micros: int,
    tax_micros: int,
    adjustment_micros: int,
    created_at: str,
) -> AllocationSnapshot:
    """THE single deterministic allocation-snapshot derivation.

    Called by the admission path AND by the replay fold, so the
    journaled fact is by construction exactly the derivation of
    (the resolved billable-final usage snapshot, the resolved
    immutable policy version, the declared split and
    fees/taxes/adjustments, the deterministic creation instant) --
    a mutated or repriced fact with a fully recomputed outer hash
    chain still fails closed at replay.
    """
    if usage_snapshot.statement_id is None:
        raise AllocationError(
            AllocationReasonCode.USAGE_NOT_FINAL,
            "usage transaction %s is %s (allocation consumes only "
            "BILLABLE_FINAL usage facts)"
            % (usage_transaction_id, usage_snapshot.usage_state),
        )
    gross_micros = usage_snapshot.gross_amount_micros
    distributable_micros = (
        gross_micros - fee_micros - tax_micros - adjustment_micros
    )
    if distributable_micros < 0 or distributable_micros > gross_micros:
        raise AllocationError(
            AllocationReasonCode.DISTRIBUTION_INVALID,
            "distributable %d (gross %d - fee %d - tax %d - adjustment "
            "%d) must be within [0, gross] (the declared charges can "
            "never make the distributable amount negative or exceed "
            "the billable amount)"
            % (
                distributable_micros,
                gross_micros,
                fee_micros,
                tax_micros,
                adjustment_micros,
            ),
        )
    (
        adcos_share_micros,
        provider_share_micros,
        developer_share_micros,
    ) = compute_split(
        distributable_micros,
        policy.adcos_share_bps,
        provider_share_bps,
        policy.rounding_mode,
    )
    return AllocationSnapshot(
        allocation_id=derive_allocation_id(
            usage_transaction_id,
            usage_snapshot.statement_id,
            policy.policy_id,
            provider_share_bps,
            fee_micros,
            tax_micros,
            adjustment_micros,
            created_at,
        ),
        usage_transaction_id=usage_transaction_id,
        usage_statement_id=usage_snapshot.statement_id,
        policy_id=policy.policy_id,
        gross_micros=gross_micros,
        fee_micros=fee_micros,
        tax_micros=tax_micros,
        adjustment_micros=adjustment_micros,
        distributable_micros=distributable_micros,
        adcos_share_micros=adcos_share_micros,
        provider_share_micros=provider_share_micros,
        developer_share_micros=developer_share_micros,
        provider_share_bps=provider_share_bps,
        adcos_share_bps=policy.adcos_share_bps,
        rounding_mode=policy.rounding_mode,
        currency=policy.currency,
        minor_unit_digits=policy.minor_unit_digits,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Allocation transaction (the fold projection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllocationTransaction:
    """The deterministic economic-allocation projection of ONE
    cited usage transaction (allocation state ONLY -- never a
    usage-lifecycle or commercial-lifecycle shadow).

    ``state`` is PLANNED / SETTLED.  ``snapshot`` is the
    immutable three-way allocation fact (created by ALLOCATE).
    ``settlement`` is the settlement acknowledgement once
    acknowledged.  ``payment_references`` carries the recorded
    external payment callbacks (sorted by record id -- a
    canonical audit order; the records' identities are
    admission-attributed, so the same logical callback set
    arriving in a different order carries different ids while
    the reference-id multiset and the state stay identical).
    ``compensations`` carries the append-only compensating
    records (sorted by compensation id).  Monetary compensations
    adjust ``net_distributable_micros`` = distributable - the
    monetary compensation sum; a dispute sets ``disputed``
    without touching amounts.
    """

    usage_transaction_id: str
    state: str
    snapshot: Optional[AllocationSnapshot] = None
    settlement: Optional[SettlementAcknowledgement] = None
    payment_references: Tuple[PaymentReferenceRecord, ...] = ()
    compensations: Tuple[AllocationCompensationRecord, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.usage_transaction_id, "usage_transaction_id")
        if self.state not in AllocationSubjectState.values():
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "allocation transaction state %r is not in the frozen "
                "vocabulary" % self.state,
            )
        if self.snapshot is None:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "an allocation projection requires the immutable "
                "allocation snapshot (created by ALLOCATE)",
            )
        if not isinstance(self.snapshot, AllocationSnapshot):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "snapshot must be an AllocationSnapshot value",
            )
        if self.state == AllocationSubjectState.SETTLED:
            if self.settlement is None:
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "SETTLED requires the settlement acknowledgement",
                )
        elif self.settlement is not None:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "PLANNED must not carry a settlement acknowledgement",
            )
        if self.snapshot.usage_transaction_id != self.usage_transaction_id:
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "the allocation snapshot cites usage transaction %s, "
                "not the projection's %s"
                % (
                    self.snapshot.usage_transaction_id,
                    self.usage_transaction_id,
                ),
            )
        for reference in self.payment_references:
            if not isinstance(reference, PaymentReferenceRecord):
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "payment_references must be "
                    "PaymentReferenceRecord values",
                )
        reference_ids = [
            record.payment_reference_id
            for record in self.payment_references
        ]
        if reference_ids != sorted(reference_ids):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "payment_references must be sorted by record id",
            )
        if len(set(reference_ids)) != len(reference_ids):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "duplicate payment reference record ids in the "
                "projection",
            )
        cited_reference_ids = [
            record.payment_reference
            for record in self.payment_references
        ]
        if len(set(cited_reference_ids)) != len(cited_reference_ids):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "duplicate external payment reference identities in "
                "the projection (admission de-duplicates callback "
                "redelivery; the projection cannot carry both)",
            )
        for compensation in self.compensations:
            if not isinstance(
                compensation, AllocationCompensationRecord
            ):
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "compensations must be "
                    "AllocationCompensationRecord values",
                )
        compensation_ids = [
            compensation.compensation_id
            for compensation in self.compensations
        ]
        if compensation_ids != sorted(compensation_ids):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "compensations must be sorted by compensation id",
            )
        if len(set(compensation_ids)) != len(compensation_ids):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "duplicate compensation ids in the projection",
            )
        for compensation in self.compensations:
            if (
                compensation.allocation_id
                != self.snapshot.allocation_id
            ):
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "compensation %s cites allocation %s, not the "
                    "projection's allocation %s"
                    % (
                        compensation.compensation_id,
                        compensation.allocation_id,
                        self.snapshot.allocation_id,
                    ),
                )
        for reference in self.payment_references:
            if (
                reference.allocation_id
                != self.snapshot.allocation_id
            ):
                raise AllocationError(
                    AllocationReasonCode.EVENT_INVALID,
                    "payment reference %s cites allocation %s, not "
                    "the projection's allocation %s"
                    % (
                        reference.payment_reference_id,
                        reference.allocation_id,
                        self.snapshot.allocation_id,
                    ),
                )
        if self.settlement is not None and (
            self.settlement.allocation_id != self.snapshot.allocation_id
        ):
            raise AllocationError(
                AllocationReasonCode.EVENT_INVALID,
                "the settlement acknowledgement cites allocation %s, "
                "not the projection's allocation %s"
                % (
                    self.settlement.allocation_id,
                    self.snapshot.allocation_id,
                ),
            )

    # ------------------------------------------------------------------
    # deterministic reads (the class-distinguishing reconciliation
    # quantities)
    # ------------------------------------------------------------------

    def monetary_compensation_micros(self) -> int:
        """The summed monetary compensation (refund + reversal +
        chargeback + payout-failure)."""
        return sum(
            compensation.amount_micros
            for compensation in self.compensations
            if compensation.is_monetary()
        )

    def compensation_amount_by_kind(self, kind: str) -> int:
        return sum(
            compensation.amount_micros
            for compensation in self.compensations
            if compensation.compensation_kind == kind
        )

    def refunded_amount_micros(self) -> int:
        return self.compensation_amount_by_kind("refund")

    def reversed_amount_micros(self) -> int:
        return self.compensation_amount_by_kind("reversal")

    def chargeback_amount_micros(self) -> int:
        return self.compensation_amount_by_kind("chargeback")

    def payout_failure_amount_micros(self) -> int:
        return self.compensation_amount_by_kind("payout-failure")

    def disputed(self) -> bool:
        return any(
            compensation.compensation_kind == "dispute"
            for compensation in self.compensations
        )

    def net_distributable_micros(self) -> int:
        """distributable - monetary compensations (disputes are
        flags)."""
        return (
            self.snapshot.distributable_micros
            - self.monetary_compensation_micros()
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "usage_transaction_id": self.usage_transaction_id,
            "state": self.state,
            "snapshot": self.snapshot.to_dict(),
        }
        if self.settlement is not None:
            data["settlement"] = self.settlement.to_dict()
        if self.payment_references:
            data["payment_references"] = [
                reference.to_dict()
                for reference in self.payment_references
            ]
        if self.compensations:
            data["compensations"] = [
                compensation.to_dict()
                for compensation in self.compensations
            ]
        return data


def allocation_transaction_digest(
    transaction: AllocationTransaction,
) -> str:
    """Deterministic digest of one allocation projection."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            {
                "kind": "allocation-transaction-projection",
                "transaction": transaction.to_dict(),
            }
        )
    ).hexdigest()


def policy_registry_digest(
    policies: Mapping[str, PolicyVersion],
) -> str:
    """Deterministic digest over the policy-version registry
    (sorted by policy id)."""
    content = {
        "kind": "policy-registry",
        "policies": [
            {"policy_id": key, "policy": policies[key].to_dict()}
            for key in sorted(policies)
        ],
        "count": len(policies),
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()
