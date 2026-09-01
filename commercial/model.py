"""WORK-051 CommercialCore value model.

The frozen value records of the commercial control-plane core
(ACR-009, authorization WORK-051-CORE-001 / DEC-0058):

- **CommercialState / CommercialAction / LIFECYCLE_TRANSITIONS** --
  the canonical commercial lifecycle the W051 contract requires:

      CONNECTIVITY_INTENT -> OFFER_SELECTED -> RESERVATION_HELD ->
      SESSION_AUTHORIZED -> PATH_ACTIVE -> DELIVERY_STARTED ->
      USAGE_ACCRUING -> DELIVERY_COMPLETED -> BILLABLE_FINAL ->
      SETTLEMENT_PENDING -> SETTLED

  with the four compensating terminal states CANCELLED, EXPIRED,
  PATH_FAILED, and NON_DELIVERED (cancellation, expiry, path
  failure, non-delivery).  ``SETTLED`` and every compensating
  state is terminal: historical commercial facts are immutable.
  Two state-preserving self-edges exist for journaled actions
  that record facts without advancing the lifecycle: the
  transaction-creation record (``CONNECTIVITY_INTENT ->
  CONNECTIVITY_INTENT``) and subsequent usage accruals
  (``USAGE_ACCRUING -> USAGE_ACCRUING``) -- the W041 ``PROBE``
  precedent (evidence without transition).

- **CommercialCommand** -- one caller-issued command with an
  external ``command_id`` (idempotency key) and a content-derived
  digest; repeated delivery of the identical command is an
  idempotent no-op, a conflicting redelivery fails closed.

- **CommercialEvent** -- one append-only journaled commercial fact
  with its deterministic, content-derived ``event_id``.  Every
  event identifies the previous state, the new state, the
  action, the causal command, the resolved causal references,
  and the authoritative actor/source (attribution).

- **CommercialTransaction** -- the fold projection of one
  transaction's journaled history (its current commercial state
  plus the recorded reference DATA).  It is a frozen value
  record: "mutation" is always replacement by a new projected
  record derived from an appended journal record, never an
  in-place edit, and a transaction in a terminal state can never
  be re-projected (the lifecycle table has no outgoing terminal
  edges).

Identity discipline (the W041/W042 precedent): ``transaction_id``
and ``event_id`` are CONTENT-DERIVED fingerprints --
``"sha256:" + sha256(canonical_json_bytes(content))`` (WORK-003
canonical JSON).  They are fingerprints ONLY: not NodeIDs, not
trust, never an authorization, and never a session or path
identity.  The constructors mechanically verify content
bindings, so a tampered or deserialized record can never carry
an attacker-chosen id.

Temporal discipline: every instant is an injected RFC 3339 UTC
string (the WORK-033 ``AgentClock`` seam read by the lifecycle
manager -- one clock read per executed command).  No wall-clock
reads, no UUIDs, no randomness, no environment-dependent
identity anywhere in this family.  Deadline arithmetic uses the
accepted ``agent.clock`` parse helpers (deterministic, no OS
time).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import CommercialError, CommercialReasonCode
from .references import Reference


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CommercialError(
            CommercialReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_instant(value: object, label: str) -> str:
    """A required RFC 3339 UTC instant string (shape-validated)."""
    from agent.clock import parse_utc

    if not isinstance(value, str) or not value:
        raise CommercialError(
            CommercialReasonCode.INSTANT_INVALID,
            "%s must be an RFC 3339 UTC instant string" % label,
        )
    try:
        parse_utc(value)
    except Exception as error:  # noqa: BLE001 - re-wrapped typed
        raise CommercialError(
            CommercialReasonCode.INSTANT_INVALID,
            "%s %r is not RFC 3339 UTC: %s" % (label, value, error),
        ) from error
    return value


def _require_mapping(value: object, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CommercialError(
            CommercialReasonCode.INVALID_INPUT,
            "%s must be a mapping" % label,
        )
    return dict(value)


# ---------------------------------------------------------------------------
# The frozen commercial lifecycle vocabulary (W051 contract / ACR-009)
# ---------------------------------------------------------------------------


class CommercialState:
    """The frozen canonical commercial lifecycle states.

    The eleven canonical states are the W051 contract's own words
    (ConnectivityIntent .. Settled, upper-case snake form).  The
    four compensating states are the contract's compensating
    families (cancellation, expiry, path failure, non-delivery).
    ``SETTLED`` plus the four compensating states are TERMINAL:
    historical commercial facts are immutable and corrections are
    compensating records, never rewrites.
    """

    CONNECTIVITY_INTENT = "CONNECTIVITY_INTENT"
    OFFER_SELECTED = "OFFER_SELECTED"
    RESERVATION_HELD = "RESERVATION_HELD"
    SESSION_AUTHORIZED = "SESSION_AUTHORIZED"
    PATH_ACTIVE = "PATH_ACTIVE"
    DELIVERY_STARTED = "DELIVERY_STARTED"
    USAGE_ACCRUING = "USAGE_ACCRUING"
    DELIVERY_COMPLETED = "DELIVERY_COMPLETED"
    BILLABLE_FINAL = "BILLABLE_FINAL"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    SETTLED = "SETTLED"
    # compensating (terminal)
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    PATH_FAILED = "PATH_FAILED"
    NON_DELIVERED = "NON_DELIVERED"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.CONNECTIVITY_INTENT,
            cls.OFFER_SELECTED,
            cls.RESERVATION_HELD,
            cls.SESSION_AUTHORIZED,
            cls.PATH_ACTIVE,
            cls.DELIVERY_STARTED,
            cls.USAGE_ACCRUING,
            cls.DELIVERY_COMPLETED,
            cls.BILLABLE_FINAL,
            cls.SETTLEMENT_PENDING,
            cls.SETTLED,
            cls.CANCELLED,
            cls.EXPIRED,
            cls.PATH_FAILED,
            cls.NON_DELIVERED,
        )

    @classmethod
    def canonical_values(cls) -> Tuple[str, ...]:
        return (
            cls.CONNECTIVITY_INTENT,
            cls.OFFER_SELECTED,
            cls.RESERVATION_HELD,
            cls.SESSION_AUTHORIZED,
            cls.PATH_ACTIVE,
            cls.DELIVERY_STARTED,
            cls.USAGE_ACCRUING,
            cls.DELIVERY_COMPLETED,
            cls.BILLABLE_FINAL,
            cls.SETTLEMENT_PENDING,
            cls.SETTLED,
        )

    @classmethod
    def compensating_values(cls) -> Tuple[str, ...]:
        return (cls.CANCELLED, cls.EXPIRED, cls.PATH_FAILED, cls.NON_DELIVERED)

    @classmethod
    def terminal_values(cls) -> Tuple[str, ...]:
        return (
            cls.SETTLED,
            cls.CANCELLED,
            cls.EXPIRED,
            cls.PATH_FAILED,
            cls.NON_DELIVERED,
        )


#: The frozen lifecycle transition table.  The canonical forward
#: chain is strictly linear; every compensating family is reachable
#: only from the states where its cause exists; terminal states have
#: NO outgoing edges (settled history and compensating outcomes are
#: immutable).  Payment/reservation/settlement states can NEVER jump
#: to a delivery state: delivery is reachable only through the
#: session-authorized + path-active chain.  Two state-preserving
#: self-edges exist for journaled facts without lifecycle advance
#: (transaction creation, subsequent usage accruals).
LIFECYCLE_TRANSITIONS: Dict[str, frozenset] = {
    CommercialState.CONNECTIVITY_INTENT: frozenset(
        {
            CommercialState.CONNECTIVITY_INTENT,
            CommercialState.OFFER_SELECTED,
            CommercialState.CANCELLED,
        }
    ),
    CommercialState.OFFER_SELECTED: frozenset(
        {CommercialState.RESERVATION_HELD, CommercialState.CANCELLED}
    ),
    CommercialState.RESERVATION_HELD: frozenset(
        {
            CommercialState.SESSION_AUTHORIZED,
            CommercialState.CANCELLED,
            CommercialState.EXPIRED,
        }
    ),
    CommercialState.SESSION_AUTHORIZED: frozenset(
        {CommercialState.PATH_ACTIVE, CommercialState.CANCELLED, CommercialState.EXPIRED}
    ),
    CommercialState.PATH_ACTIVE: frozenset(
        {
            CommercialState.DELIVERY_STARTED,
            CommercialState.CANCELLED,
            CommercialState.PATH_FAILED,
            CommercialState.NON_DELIVERED,
        }
    ),
    CommercialState.DELIVERY_STARTED: frozenset(
        {
            CommercialState.USAGE_ACCRUING,
            CommercialState.PATH_FAILED,
            CommercialState.NON_DELIVERED,
        }
    ),
    CommercialState.USAGE_ACCRUING: frozenset(
        {
            CommercialState.USAGE_ACCRUING,
            CommercialState.DELIVERY_COMPLETED,
            CommercialState.PATH_FAILED,
            CommercialState.NON_DELIVERED,
        }
    ),
    CommercialState.DELIVERY_COMPLETED: frozenset({CommercialState.BILLABLE_FINAL}),
    CommercialState.BILLABLE_FINAL: frozenset({CommercialState.SETTLEMENT_PENDING}),
    CommercialState.SETTLEMENT_PENDING: frozenset({CommercialState.SETTLED}),
    CommercialState.SETTLED: frozenset(),
    CommercialState.CANCELLED: frozenset(),
    CommercialState.EXPIRED: frozenset(),
    CommercialState.PATH_FAILED: frozenset(),
    CommercialState.NON_DELIVERED: frozenset(),
}


def transition_is_legal(from_state: str, to_state: str) -> bool:
    """True iff the lifecycle table allows ``from_state -> to_state``.

    Unknown states fail closed (``False``): an out-of-vocabulary
    state can never transition anywhere, least of all into
    ``SETTLED`` or a delivery state.
    """
    if from_state not in LIFECYCLE_TRANSITIONS:
        return False
    return to_state in LIFECYCLE_TRANSITIONS[from_state]


class CommercialAction:
    """The frozen journaled command/action vocabulary.

    Each canonical state has exactly one forward action; the four
    compensating actions (cancel / expire / record_path_failure /
    record_non_delivery) are the contract's compensating families.
    ``ACCRUE_USAGE`` is additionally a state-preserving journaled
    action (``USAGE_ACCRUING -> USAGE_ACCRUING``): subsequent usage
    references append evidence without changing lifecycle state
    (usage metering itself is WORK-052, out of scope here -- the
    core only records usage REFERENCES).  ``SUBMIT_INTENT`` is the
    state-preserving transaction-creation record.
    """

    SUBMIT_INTENT = "submit_intent"
    SELECT_OFFER = "select_offer"
    HOLD_RESERVATION = "hold_reservation"
    AUTHORIZE_SESSION = "authorize_session"
    ACTIVATE_PATH = "activate_path"
    START_DELIVERY = "start_delivery"
    ACCRUE_USAGE = "accrue_usage"
    COMPLETE_DELIVERY = "complete_delivery"
    FINALIZE_BILLABLE = "finalize_billable"
    INITIATE_SETTLEMENT = "initiate_settlement"
    SETTLE = "settle"
    # compensating
    CANCEL = "cancel"
    EXPIRE = "expire"
    RECORD_PATH_FAILURE = "record_path_failure"
    RECORD_NON_DELIVERY = "record_non_delivery"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.SUBMIT_INTENT,
            cls.SELECT_OFFER,
            cls.HOLD_RESERVATION,
            cls.AUTHORIZE_SESSION,
            cls.ACTIVATE_PATH,
            cls.START_DELIVERY,
            cls.ACCRUE_USAGE,
            cls.COMPLETE_DELIVERY,
            cls.FINALIZE_BILLABLE,
            cls.INITIATE_SETTLEMENT,
            cls.SETTLE,
            cls.CANCEL,
            cls.EXPIRE,
            cls.RECORD_PATH_FAILURE,
            cls.RECORD_NON_DELIVERY,
        )

    @classmethod
    def compensating_values(cls) -> Tuple[str, ...]:
        return (
            cls.CANCEL,
            cls.EXPIRE,
            cls.RECORD_PATH_FAILURE,
            cls.RECORD_NON_DELIVERY,
        )


#: Which lifecycle state each action requires BEFORE it may run
#: (the fail-closed precondition gate; the manager enforces this in
#: addition to the transition table so duplicate, stale, and
#: out-of-order commands never silently succeed).  ``SUBMIT_INTENT``
#: creates a new transaction (no precondition state); the
#: compensating actions run from their family-specific state sets
#: (validated in :mod:`commercial.validation`).
ACTION_REQUIRED_STATE: Dict[str, str] = {
    CommercialAction.SUBMIT_INTENT: "",
    CommercialAction.SELECT_OFFER: CommercialState.CONNECTIVITY_INTENT,
    CommercialAction.HOLD_RESERVATION: CommercialState.OFFER_SELECTED,
    CommercialAction.AUTHORIZE_SESSION: CommercialState.RESERVATION_HELD,
    CommercialAction.ACTIVATE_PATH: CommercialState.SESSION_AUTHORIZED,
    CommercialAction.START_DELIVERY: CommercialState.PATH_ACTIVE,
    CommercialAction.ACCRUE_USAGE: CommercialState.DELIVERY_STARTED,
    CommercialAction.COMPLETE_DELIVERY: CommercialState.USAGE_ACCRUING,
    CommercialAction.FINALIZE_BILLABLE: CommercialState.DELIVERY_COMPLETED,
    CommercialAction.INITIATE_SETTLEMENT: CommercialState.BILLABLE_FINAL,
    CommercialAction.SETTLE: CommercialState.SETTLEMENT_PENDING,
    CommercialAction.CANCEL: "",
    CommercialAction.EXPIRE: "",
    CommercialAction.RECORD_PATH_FAILURE: "",
    CommercialAction.RECORD_NON_DELIVERY: "",
}


#: The target lifecycle state of each action (the table's to-state).
ACTION_TARGET_STATE: Dict[str, str] = {
    CommercialAction.SUBMIT_INTENT: CommercialState.CONNECTIVITY_INTENT,
    CommercialAction.SELECT_OFFER: CommercialState.OFFER_SELECTED,
    CommercialAction.HOLD_RESERVATION: CommercialState.RESERVATION_HELD,
    CommercialAction.AUTHORIZE_SESSION: CommercialState.SESSION_AUTHORIZED,
    CommercialAction.ACTIVATE_PATH: CommercialState.PATH_ACTIVE,
    CommercialAction.START_DELIVERY: CommercialState.DELIVERY_STARTED,
    CommercialAction.ACCRUE_USAGE: CommercialState.USAGE_ACCRUING,
    CommercialAction.COMPLETE_DELIVERY: CommercialState.DELIVERY_COMPLETED,
    CommercialAction.FINALIZE_BILLABLE: CommercialState.BILLABLE_FINAL,
    CommercialAction.INITIATE_SETTLEMENT: CommercialState.SETTLEMENT_PENDING,
    CommercialAction.SETTLE: CommercialState.SETTLED,
    CommercialAction.CANCEL: CommercialState.CANCELLED,
    CommercialAction.EXPIRE: CommercialState.EXPIRED,
    CommercialAction.RECORD_PATH_FAILURE: CommercialState.PATH_FAILED,
    CommercialAction.RECORD_NON_DELIVERY: CommercialState.NON_DELIVERED,
}


# ---------------------------------------------------------------------------
# Content-derived identities (fingerprints, never trust)
# ---------------------------------------------------------------------------


def derive_transaction_id(
    intent_payload: Mapping[str, Any],
    actor: str,
    source: str,
    submitted_at: str,
) -> str:
    """The content-derived CommercialTransaction fingerprint.

    Binds the intent content, the submitting actor, the command
    source, and the deterministic submitted instant (an injected
    clock read).  Identity DATA only: not a NodeID, not trust,
    never a session identity, never an authorization.
    """
    content = {
        "kind": "commercial-transaction",
        "intent": dict(intent_payload),
        "actor": actor,
        "source": source,
        "submitted_at": submitted_at,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def command_content(
    command_id: str,
    action: str,
    transaction_id: str,
    references: Tuple[Reference, ...],
    payload: Mapping[str, Any],
    actor: str,
    source: str,
) -> Dict[str, Any]:
    """The canonical command content (digest basis + journal DATA)."""
    return {
        "command_id": command_id,
        "action": action,
        "transaction_id": transaction_id,
        "references": [reference.to_dict() for reference in references],
        "payload": dict(payload),
        "actor": actor,
        "source": source,
    }


def derive_command_digest(
    command_id: str,
    action: str,
    transaction_id: str,
    references: Tuple[Reference, ...],
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
                command_id, action, transaction_id, references, payload, actor, source
            )
        )
    ).hexdigest()


def derive_event_id(
    transaction_id: str,
    action: str,
    from_state: str,
    to_state: str,
    command_id: str,
    instant: str,
) -> str:
    """Content-derived commercial event id (journal identity DATA)."""
    content = {
        "transaction_id": transaction_id,
        "action": action,
        "from_state": from_state,
        "to_state": to_state,
        "command_id": command_id,
        "instant": instant,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


# ---------------------------------------------------------------------------
# Commercial command (the input record)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommercialCommand:
    """One caller-issued commercial command.

    ``command_id`` is the caller's idempotency key (an external
    command identity, e.g. a platform message id): repeated
    delivery of the identical command (same content digest) is an
    idempotent no-op; a redelivery with different content fails
    closed as ``COMMAND_CONFLICT``.  ``transaction_id`` may be
    empty ONLY for ``submit_intent`` (the transaction identity is
    derived at execution from the intent content + the clock
    read).  ``references`` are the causal external references,
    resolved against the injected :class:`ReferenceIndex` -- the
    core never queries authorities live.  ``payload`` is
    command-specific DATA (intent descriptor, offer descriptor,
    reservation deadline, ...).  ``actor`` and ``source`` carry
    attribution.
    """

    command_id: str
    action: str
    transaction_id: str
    references: Tuple[Reference, ...]
    payload: Dict[str, Any]
    actor: str
    source: str

    def __post_init__(self) -> None:
        _require_text(self.command_id, "command_id")
        if self.action not in CommercialAction.values():
            raise CommercialError(
                CommercialReasonCode.COMMAND_INVALID,
                "action %r must be one of %s"
                % (self.action, list(CommercialAction.values())),
            )
        if self.action == CommercialAction.SUBMIT_INTENT:
            if self.transaction_id != "":
                raise CommercialError(
                    CommercialReasonCode.COMMAND_INVALID,
                    "submit_intent derives its transaction_id at execution; "
                    "the citation must be empty",
                )
        else:
            _require_text(self.transaction_id, "transaction_id")
        if not isinstance(self.references, tuple):
            raise CommercialError(
                CommercialReasonCode.COMMAND_INVALID,
                "references must be a tuple of Reference",
            )
        for reference in self.references:
            if not isinstance(reference, Reference):
                raise CommercialError(
                    CommercialReasonCode.COMMAND_INVALID,
                    "references must contain Reference values",
                )
        payload = _require_mapping(self.payload, "payload")
        object.__setattr__(self, "payload", payload)
        for key in payload:
            if not isinstance(key, str) or not key:
                raise CommercialError(
                    CommercialReasonCode.INVALID_INPUT,
                    "payload keys must be non-empty strings",
                )
        _require_text(self.actor, "actor")
        _require_text(self.source, "source")
        # the command content must be canonical-JSON representable
        # (fail closed on floats and other out-of-subset values --
        # commercial quantities are DATA, never floating-point
        # money)
        try:
            canonical_json_bytes(
                command_content(
                    self.command_id,
                    self.action,
                    self.transaction_id,
                    self.references,
                    self.payload,
                    self.actor,
                    self.source,
                )
            )
        except CommercialError:
            raise
        except ValueError as error:
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "command payload is not canonical-JSON representable "
                "(floats and unsupported value kinds are rejected): %s" % error,
            ) from error

    def content(self) -> Dict[str, Any]:
        return command_content(
            self.command_id,
            self.action,
            self.transaction_id,
            self.references,
            self.payload,
            self.actor,
            self.source,
        )

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.content())
        ).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return self.content()

    @classmethod
    def from_dict(cls, data: object) -> "CommercialCommand":
        if not isinstance(data, Mapping):
            raise CommercialError(
                CommercialReasonCode.COMMAND_INVALID,
                "command must be a mapping",
            )
        required = (
            "command_id",
            "action",
            "transaction_id",
            "references",
            "payload",
            "actor",
            "source",
        )
        for key in required:
            if key not in data:
                raise CommercialError(
                    CommercialReasonCode.COMMAND_INVALID,
                    "command is missing required member %r" % key,
                )
        raw_refs = data["references"]
        if not isinstance(raw_refs, list):
            raise CommercialError(
                CommercialReasonCode.COMMAND_INVALID,
                "references must be a list",
            )
        references = tuple(Reference.from_dict(item) for item in raw_refs)
        return cls(
            command_id=data["command_id"],
            action=data["action"],
            transaction_id=data["transaction_id"],
            references=references,
            payload=data["payload"],
            actor=data["actor"],
            source=data["source"],
        )


# ---------------------------------------------------------------------------
# Commercial event (the append-only journaled fact)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommercialEvent:
    """One append-only journaled commercial fact.

    Attribution (the W051 contract): every event identifies the
    PREVIOUS state, the NEW state, the ACTION, the causal COMMAND
    (``command_id``), the resolved causal REFERENCES (external
    reference ids with their index-authoritative families), and
    the authoritative ACTOR/SOURCE.  ``event_id`` is
    content-derived over (transaction, action, from, to, command,
    instant) and is mechanically verified at construction and
    deserialization, so a tampered event can never carry an
    attacker-chosen id.

    ``from_state == to_state`` marks a state-preserving journaled
    action (the transaction-creation record, subsequent usage
    accruals).  Settlement/delivery separation is structural: an
    event IS the commercial fact; it may REFERENCE delivery
    evidence but can never BE delivery evidence, and no
    payment-family reference can appear among the causal
    references of a delivery-state or settlement-state event
    (family validation happens at command admission).
    """

    event_id: str
    transaction_id: str
    action: str
    from_state: str
    to_state: str
    command_id: str
    causal_references: Tuple[Reference, ...]
    actor: str
    source: str
    instant: str

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.transaction_id, "transaction_id")
        if self.action not in CommercialAction.values():
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "action %r must be one of %s"
                % (self.action, list(CommercialAction.values())),
            )
        for label, value in (
            ("from_state", self.from_state),
            ("to_state", self.to_state),
        ):
            if value not in CommercialState.values():
                raise CommercialError(
                    CommercialReasonCode.EVENT_INVALID,
                    "%s %r must be one of %s"
                    % (label, value, list(CommercialState.values())),
                )
        if not transition_is_legal(self.from_state, self.to_state):
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "event transition %s -> %s is not in the frozen lifecycle "
                "table" % (self.from_state, self.to_state),
            )
        _require_text(self.command_id, "command_id")
        if not isinstance(self.causal_references, tuple):
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "causal_references must be a tuple of Reference",
            )
        for reference in self.causal_references:
            if not isinstance(reference, Reference):
                raise CommercialError(
                    CommercialReasonCode.EVENT_INVALID,
                    "causal_references must contain Reference values",
                )
        _require_text(self.actor, "actor")
        _require_text(self.source, "source")
        _require_instant(self.instant, "instant")
        expected = derive_event_id(
            self.transaction_id,
            self.action,
            self.from_state,
            self.to_state,
            self.command_id,
            self.instant,
        )
        if self.event_id != expected:
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "event_id %s does not match the content-derived id %s "
                "(tampered or malformed event)" % (self.event_id, expected),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "transaction_id": self.transaction_id,
            "action": self.action,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "command_id": self.command_id,
            "causal_references": [
                reference.to_dict() for reference in self.causal_references
            ],
            "actor": self.actor,
            "source": self.source,
            "instant": self.instant,
        }

    @classmethod
    def from_dict(cls, data: object) -> "CommercialEvent":
        if not isinstance(data, Mapping):
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "event must be a mapping",
            )
        required = (
            "event_id",
            "transaction_id",
            "action",
            "from_state",
            "to_state",
            "command_id",
            "causal_references",
            "actor",
            "source",
            "instant",
        )
        for key in required:
            if key not in data:
                raise CommercialError(
                    CommercialReasonCode.EVENT_INVALID,
                    "event is missing required member %r" % key,
                )
        raw_refs = data["causal_references"]
        if not isinstance(raw_refs, list):
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "causal_references must be a list",
            )
        references = tuple(Reference.from_dict(item) for item in raw_refs)
        return cls(
            event_id=data["event_id"],
            transaction_id=data["transaction_id"],
            action=data["action"],
            from_state=data["from_state"],
            to_state=data["to_state"],
            command_id=data["command_id"],
            causal_references=references,
            actor=data["actor"],
            source=data["source"],
            instant=data["instant"],
        )


def event_list_digest(events: Tuple[CommercialEvent, ...]) -> str:
    """Deterministic digest over the ordered journal event list."""
    content = {
        "kind": "commercial-event-list",
        "events": [event.to_dict() for event in events],
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


# ---------------------------------------------------------------------------
# Commercial transaction (the fold projection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommercialTransaction:
    """The current projected state of one commercial transaction.

    This is a FOLD PROJECTION of the journaled history, not an
    independently mutable record: every field is derived from the
    appended journal records, replacement happens only through
    the journal (apply_record -> new projection), and a
    transaction in a terminal state (``SETTLED`` or a compensating
    state) can never be re-projected because the lifecycle table
    has no outgoing terminal edges.  Delivery and payment DATA
    stay separated by construction: delivery facts live in
    ``delivery_evidence_refs`` (populated ONLY by
    delivery-evidence-family causal references), payment
    observations in ``payment_refs`` (DATA only -- they can never
    justify a delivery or settlement event).

    Reference fields record the EXTERNAL authority identities the
    transaction cites (session, NetworkPath, delivery evidence,
    usage, settlement confirmations, payment observations).  The
    core references them; it never owns or mutates them.
    """

    transaction_id: str
    state: str
    actor: str
    source: str
    created_at: str
    intent: Dict[str, Any]
    offer: Dict[str, Any]
    expires_at: str
    session_ref: str
    path_ref: str
    delivery_evidence_refs: Tuple[str, ...]
    usage_refs: Tuple[str, ...]
    settlement_refs: Tuple[str, ...]
    payment_refs: Tuple[str, ...]
    last_action: str
    last_instant: str
    event_count: int

    def __post_init__(self) -> None:
        _require_text(self.transaction_id, "transaction_id")
        if self.state not in CommercialState.values():
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "transaction state %r must be one of %s"
                % (self.state, list(CommercialState.values())),
            )
        _require_text(self.actor, "actor")
        _require_text(self.source, "source")
        _require_instant(self.created_at, "created_at")
        if not isinstance(self.intent, Mapping):
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "intent must be a mapping",
            )
        if not isinstance(self.offer, Mapping):
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "offer must be a mapping",
            )
        if self.expires_at != "":
            _require_instant(self.expires_at, "expires_at")
        for label, value in (
            ("session_ref", self.session_ref),
            ("path_ref", self.path_ref),
        ):
            if value != "" and not isinstance(value, str):
                raise CommercialError(
                    CommercialReasonCode.EVENT_INVALID,
                    "%s must be a string" % label,
                )
        for label, value in (
            ("delivery_evidence_refs", self.delivery_evidence_refs),
            ("usage_refs", self.usage_refs),
            ("settlement_refs", self.settlement_refs),
            ("payment_refs", self.payment_refs),
        ):
            if not isinstance(value, tuple):
                raise CommercialError(
                    CommercialReasonCode.EVENT_INVALID,
                    "%s must be a tuple" % label,
                )
            for item in value:
                if not isinstance(item, str) or not item:
                    raise CommercialError(
                        CommercialReasonCode.EVENT_INVALID,
                        "%s must contain non-empty strings" % label,
                    )
        if self.last_action not in CommercialAction.values():
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "last_action %r must be one of %s"
                % (self.last_action, list(CommercialAction.values())),
            )
        _require_instant(self.last_instant, "last_instant")
        if not isinstance(self.event_count, int) or isinstance(self.event_count, bool):
            raise CommercialError(
                CommercialReasonCode.EVENT_INVALID,
                "event_count must be an integer",
            )

    def terminal(self) -> bool:
        return self.state in CommercialState.terminal_values()

    def settled(self) -> bool:
        return self.state == CommercialState.SETTLED

    def content(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "state": self.state,
            "actor": self.actor,
            "source": self.source,
            "created_at": self.created_at,
            "intent": dict(self.intent),
            "offer": dict(self.offer),
            "expires_at": self.expires_at,
            "session_ref": self.session_ref,
            "path_ref": self.path_ref,
            "delivery_evidence_refs": list(self.delivery_evidence_refs),
            "usage_refs": list(self.usage_refs),
            "settlement_refs": list(self.settlement_refs),
            "payment_refs": list(self.payment_refs),
            "last_action": self.last_action,
            "last_instant": self.last_instant,
            "event_count": self.event_count,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content()


def transaction_digest(transaction: CommercialTransaction) -> str:
    """Deterministic digest of one transaction projection."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(transaction.content())
    ).hexdigest()
