"""ADCOS resilience domain model (M015 — Execution Resilience Runtime).

The execution-runtime resilience records of the R8 charter M015 scope:
the session-runtime lifecycle with EXPLICIT reconnect transitions (the
WORK-012 discipline re-expressed on the Architecture 1.1 authority —
every route/realization change is an explicit recorded reconnect
naming BOTH the old AND the new references, never a silent
replacement), the journaled runtime events (deterministic, replayable,
typed provenance — the LOCK-106/LOCK-118 evidence-typing conventions
consumed from the accepted ``evidence/`` vocabulary), and the frozen
projection onto the M008-owned realization-state vocabulary (consumed
BY REFERENCE from ``replan/`` — never redefined, never duplicated).

The central boundary (enforced throughout):

    RUNTIME SESSION
        = an EXECUTION-RUNTIME artifact riding the canonical
          ``ConnectivityContract`` as an opaque reference (LOCK-117:
          the contract is the sole authority; the runtime session
          cites the contract id, never re-derives contract identity,
          never carries a second constraint model)
        != CONTRACT AUTHORITY (contracts/ stays the sole authority —
          the runtime session carries NO constraint set at all; every
          constraint check is delegated to the consumed replan gates)
        != THE M008 REPLAN KERNEL (replan/ owns the realization-state
          vocabulary and the decision engine; this domain PROJECTS
          onto that vocabulary and DRIVES that engine — never
          redefines, never duplicates)
        != THE M006 PLAN DOMAIN (executionplans/ owns plans/segments;
          failover alternatives are read from an accepted plan BY
          REFERENCE)
        != A LEGACY PACKAGE (the WORK-012/014/013 reservoir is source
          material only — their disciplines are re-expressed here on
          the 1.1 authority, and the legacy packages are not imported)

LOCK-108 discipline (the core rule): every handover/failover
transition preserves the contract's hard-constraint set VERBATIM.  The
model enforces it structurally — the runtime session and its events
carry NO constraint material at all — and the engines
(:mod:`resilience.handover`, :mod:`resilience.failover`) validate
every candidate against the contract's full hard-constraint set
through the accepted ``replan/`` gates, consumed BY REFERENCE.  An
impossible realization enters an EXPLICIT degraded/failed state or
triggers EXPLICIT renegotiation — never a silent downgrade.

Determinism (LOCK-111/LOCK-119): content-derived ids over canonical
JSON (namespaced); injected instants only (no wall clock); no
randomness, no UUIDs, no network, no secrets; canonical-JSON
round-trips with tamper-evident ids re-verified at deserialization;
sorted and order-normalized iteration; PYTHONHASHSEED-safe.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import (
    CONSTRAINT_KINDS,
    OpaqueReference,
    Provenance,
)

from evidence import EVIDENCE_TYPES

from replan import (
    REALIZATION_STATES,
    RealizationSnapshot,
    TIE_BREAK_KEYS,
)

from .errors import ResilienceError, ResilienceReason


# ----------------------------------------------------------------------
# The consumed-boundary error wrap (exception isolation)
# ----------------------------------------------------------------------

_CONSUMED_CODE_MAP = {
    "secret-rejected": ResilienceReason.SECRET_REJECTED,
    "vocabulary": ResilienceReason.VOCABULARY,
    "temporal-invalid": ResilienceReason.TEMPORAL_INVALID,
    "invalid-input": ResilienceReason.INVALID_INPUT,
    "id-mismatch": ResilienceReason.ID_MISMATCH,
}


def _wrap_consumed_error(label: str) -> Iterator[None]:
    """Exception isolation at the consumed-domain boundary: a
    ``ContractError``/``ReplanError``/``ExecutionPlanError`` (all
    ValueError subclasses carrying ``code``/``detail``) surfaces as a
    typed ResilienceError with its deterministic text preserved — never
    a foreign exception type, never raw exception text into stored
    state.  The consumed domain's LOCK-119 secret rejection maps onto
    this surface's own ``resilience-secret-rejected``."""

    @contextlib.contextmanager
    def _ctx() -> Iterator[None]:
        try:
            yield
        except ResilienceError:
            raise
        except ValueError as error:  # consumed typed errors are ValueError
            code = getattr(error, "code", "")
            mapped = _CONSUMED_CODE_MAP.get(code, ResilienceReason.INVALID_INPUT)
            raise ResilienceError(
                mapped,
                "%s was rejected by a consumed domain: %s"
                % (label, getattr(error, "detail", error)),
            ) from None

    return _ctx()


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The M015-owned session-runtime lifecycle states (the deterministic
#: execution-runtime vocabulary, re-expressing the WORK-012 session
#: lifecycle discipline on the 1.1 authority — deliberately NOT the
#: M008 realization-state vocabulary, which stays owned by ``replan/``
#: and is consumed through the frozen projection below):
#:
#: - ``PENDING`` — created, not yet realizing (no realization
#:   references exist; activation names them explicitly);
#: - ``ACTIVE`` — realizing on the current route/realization
#:   references;
#: - ``RECONNECTING`` — the EXPLICIT transitional state of an
#:   in-progress route change (a reconnect was initiated; the OLD
#:   references and the CANDIDATE new references are both recorded on
#:   the initiating event — the session is still the same realization
#:   holder, never a silent replacement);
#: - ``DEGRADED`` — the EXPLICIT degraded runtime state (entry and
#:   exit are journaled runtime events with typed provenance — never a
#:   silent downgrade);
#: - ``FAILED`` — terminal failure;
#: - ``TERMINATED`` — terminal deliberate termination.
RUNTIME_STATES: Tuple[str, ...] = (
    "PENDING",
    "ACTIVE",
    "RECONNECTING",
    "DEGRADED",
    "FAILED",
    "TERMINATED",
)

#: Terminal runtime states (never transition out).
RUNTIME_TERMINAL_STATES: Tuple[str, ...] = ("FAILED", "TERMINATED")

#: Legal runtime-state transitions (fail-closed elsewhere).
#: ``ACTIVE -> RECONNECTING -> ACTIVE`` is the explicit reconnect
#: arc (the WORK-012 discipline); ``DEGRADED -> RECONNECTING`` is the
#: degraded runtime attempting an explicit reconnect to restore a
#: satisfying realization; ``DEGRADED -> ACTIVE`` is the explicit
#: degraded-exit (recovery) edge; ``PENDING -> ACTIVE`` is activation
#: (the initial realization references are named on the activating
#: event); every non-terminal state carries the explicit FAILED and
#: TERMINATED edges.
RUNTIME_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "PENDING": ("ACTIVE", "FAILED", "TERMINATED"),
    "ACTIVE": ("RECONNECTING", "DEGRADED", "FAILED", "TERMINATED"),
    "RECONNECTING": ("ACTIVE", "DEGRADED", "FAILED", "TERMINATED"),
    "DEGRADED": ("RECONNECTING", "ACTIVE", "FAILED", "TERMINATED"),
    "FAILED": (),
    "TERMINATED": (),
}

#: The runtime states a reconnect may be initiated from (the
#: realization-holder states; a PENDING session has no realization
#: references to leave, and terminal sessions never transition).
RUNTIME_RECONNECTABLE_STATES: Tuple[str, ...] = ("ACTIVE", "DEGRADED")

#: The frozen projection of the runtime lifecycle onto the M008-owned
#: realization-state vocabulary (consumed BY REFERENCE from
#: ``replan/`` — one-way and additive: the M008 vocabulary is NEVER
#: redefined or extended here; the runtime states PROJECT onto the
#: existing states exactly):
#:
#: - ``ACTIVE`` / ``RECONNECTING`` -> ``REALIZING`` (the runtime is
#:   the active realization holder; RECONNECTING is the explicit
#:   in-progress route change — still the same realization);
#: - ``DEGRADED`` -> ``DEGRADED`` (the explicit degraded runtime state
#:   IS the explicit degraded realization — frozen 1.1 §9);
#: - ``FAILED`` -> ``FAILED`` (terminal);
#: - ``PENDING`` / ``TERMINATED`` -> NOT a replan surface (a pending
#:   runtime has no established realization; a deliberately terminated
#:   runtime is a lifecycle decision, not a failure — both fail
#:   closed with typed reasons, never a silent downgrade).
RUNTIME_REALIZATION_MAP: Dict[str, str] = {
    "ACTIVE": "REALIZING",
    "RECONNECTING": "REALIZING",
    "DEGRADED": "DEGRADED",
    "FAILED": "FAILED",
}

#: The journaled runtime event kinds (the deterministic, replayable
#: runtime journal vocabulary):
#:
#: - ``session-created`` — the runtime session is created (PENDING);
#: - ``session-activated`` — PENDING -> ACTIVE, carrying the INITIAL
#:   realization references (both members required — activating
#:   without naming the realization fails closed);
#: - ``reconnect-initiated`` — ACTIVE/DEGRADED -> RECONNECTING,
#:   carrying the OLD references (must equal the session's current
#:   ones) AND the CANDIDATE new references;
#: - ``reconnect-completed`` — RECONNECTING -> ACTIVE, carrying BOTH
#:   the OLD AND the NEW references (the new ones MUST equal the
#:   pending candidates recorded on the initiating event — the
#:   WORK-012 discipline mechanically enforced; a completion without
#:   a matching initiation, or with different new references, is a
#:   SILENT REPLACEMENT and fails closed);
#: - ``reconnect-failed`` — RECONNECTING -> DEGRADED/FAILED, carrying
#:   the typed reason (the attempted reconnect did not complete; the
#:   session keeps its pre-change references);
#: - ``degraded-entered`` — ACTIVE -> DEGRADED, the EXPLICIT
#:   degraded-mode entry (journaled, typed provenance, evidence kind
#:   drawn from the accepted ``evidence/`` LOCK-106 vocabulary and
#:   evidence references as opaque ``decision``-kinded data);
#: - ``degraded-recovered`` — DEGRADED -> ACTIVE, the EXPLICIT
#:   degraded-mode exit (journaled, typed provenance);
#: - ``session-failed`` — -> FAILED, the explicit terminal failure
#:   with its typed reason;
#: - ``session-terminated`` — -> TERMINATED, the explicit deliberate
#:   termination.
RUNTIME_EVENT_KINDS: Tuple[str, ...] = (
    "session-created",
    "session-activated",
    "reconnect-initiated",
    "reconnect-completed",
    "reconnect-failed",
    "degraded-entered",
    "degraded-recovered",
    "session-failed",
    "session-terminated",
)

#: The realization-reference member names (the WORK-012 member shape —
#: a realization is named by its route decision id AND its path id).
ROUTE_MEMBER_NAMES: Tuple[str, ...] = (
    "route_decision_id",
    "path_id",
)


def _normalize_tie_break(
    tie_break: object, label: str, *, complete: bool = False
) -> Tuple[str, ...]:
    """Validate a declared tie-breaking rule (LOCK-111), against the
    CONSUMED ``replan.TIE_BREAK_KEYS`` vocabulary (never a second
    vocabulary — the M008-owned key set, by reference).

    With ``complete=True`` (engine input) a rule that omits the
    ``candidate-id`` key is completed with it (the total-order
    guarantee); with ``complete=False`` the stored rule must already
    end with ``candidate-id``.  Content keys only — a temporal key does
    not exist in the consumed vocabulary (never wall-clock).
    """
    if not isinstance(tie_break, (tuple, list)) or isinstance(tie_break, (str, bytes)):
        raise ResilienceError(ResilienceReason.TIE_BREAK_INVALID, "%s must be a sequence" % label)
    items = tuple(tie_break)
    if not items:
        raise ResilienceError(
            ResilienceReason.TIE_BREAK_INVALID, "%s requires at least one entry" % label
        )
    for i, item in enumerate(items):
        if item not in TIE_BREAK_KEYS:
            raise ResilienceError(
                ResilienceReason.TIE_BREAK_INVALID,
                "%s[%d] must be one of %s (found %r) — the consumed M008 content-key "
                "vocabulary only, never temporal (LOCK-111 deterministic ordering)"
                % (label, i, ", ".join(TIE_BREAK_KEYS), item),
            )
    if len(set(items)) != len(items):
        raise ResilienceError(
            ResilienceReason.TIE_BREAK_INVALID,
            "%s must not repeat a tie-break key" % label,
        )
    if complete and "candidate-id" not in items:
        items = items + ("candidate-id",)
    if items[-1] != "candidate-id":
        raise ResilienceError(
            ResilienceReason.TIE_BREAK_INVALID,
            "%s must end with the candidate-id key (the total-order guarantee; "
            "LOCK-111 deterministic ordering)" % label,
        )
    return items


_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")

_RUNTIME_NAMESPACE = "adc-os-resilience-runtime"
_EVENT_NAMESPACE = "adc-os-resilience-event"
_RECONNECT_NAMESPACE = "adc-os-resilience-reconnect"

#: The default issuer recorded on runtime-session provenance (LOCK-118:
#: the runtime asserts its own records; the contract stays the sole
#: authority).
RUNTIME_ISSUER = "resilience:runtime"


# ----------------------------------------------------------------------
# Internal helpers (the consumed-domain conventions, re-used)
# ----------------------------------------------------------------------


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, label)
    ).hexdigest()


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-shaped material never enters runtime data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise ResilienceError(
            ResilienceReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter resilience "
            "runtime data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise ResilienceError(
            ResilienceReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter resilience "
            "runtime data" % label,
        )


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "%s must be the content-derived identity (sha256:...)" % label,
        )
    _reject_secret(value, label)
    return value


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "%s must be a non-empty instant string" % label
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise ResilienceError(
            ResilienceReason.TEMPORAL_INVALID,
            "%s %r is not RFC 3339 UTC: %s" % (label, value, error),
        ) from None
    _reject_secret(value, label)
    return value


def _require_provenance(value: object, label: str) -> Provenance:
    if not isinstance(value, Provenance):
        raise ResilienceError(ResilienceReason.INVALID_INPUT, "%s must be a Provenance record" % label)
    return value


def _require_sequence(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "%s must be a positive integer journal position (found %r)" % (label, value),
        )
    return value


def _normalize_evidence_refs(
    value: object, label: str
) -> Tuple[OpaqueReference, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ResilienceError(ResilienceReason.INVALID_INPUT, "%s must be a sequence" % label)
    normalized = []
    for i, item in enumerate(value):
        with _wrap_consumed_error("%s[%d]" % (label, i)):
            if not isinstance(item, OpaqueReference):
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "%s[%d] must be an OpaqueReference record" % (label, i),
                )
            if item.ref_kind != "decision":
                raise ResilienceError(
                    ResilienceReason.VOCABULARY,
                    "%s[%d] must use the decision reference kind (the M002 "
                    "record-assurance evidence discipline — found %s)"
                    % (label, i, item.ref_kind),
                )
        normalized.append(item)
    return tuple(normalized)


# ----------------------------------------------------------------------
# The pure runtime-state kernel
# ----------------------------------------------------------------------


def check_runtime_transition(current: str, target: str) -> None:
    """Fail closed unless current -> target is a legal runtime
    lifecycle transition (the M015-owned deterministic state machine)."""
    if current in RUNTIME_TERMINAL_STATES:
        raise ResilienceError(
            ResilienceReason.SESSION_TERMINAL,
            "runtime session is terminal in %s; terminal runtime sessions never "
            "transition" % current,
        )
    legal = RUNTIME_TRANSITIONS.get(current, ())
    if target not in legal:
        raise ResilienceError(
            ResilienceReason.TRANSITION_ILLEGAL,
            "runtime transition %s -> %s is not legal (legal: %s)"
            % (current, target, ", ".join(legal) or "none"),
        )


def check_realization_surface(state: str) -> str:
    """Fail closed unless the runtime state is a replan surface, and
    return the projected M008 realization state (the frozen
    :data:`RUNTIME_REALIZATION_MAP` — consumed vocabulary, never a
    re-definition)."""
    if state == "PENDING":
        raise ResilienceError(
            ResilienceReason.REALIZATION_NOT_ESTABLISHED,
            "runtime session is PENDING — no established realization exists to "
            "replan yet (activate the runtime session first)",
        )
    if state in RUNTIME_TERMINAL_STATES:
        raise ResilienceError(
            ResilienceReason.SESSION_TERMINAL,
            "runtime session is terminal in %s — a deliberately terminated or "
            "failed runtime is not a replan surface" % state,
        )
    mapped = RUNTIME_REALIZATION_MAP.get(state)
    if mapped is None:
        # unreachable post-construction (the frozen runtime vocabulary
        # is fully covered above); kept as a closed guard
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "runtime state %r has no frozen realization mapping" % state,
        )
    if mapped not in REALIZATION_STATES:
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "the projected realization state %r is outside the consumed M008 "
            "vocabulary (drift guard — the frozen vocabularies have drifted)" % mapped,
        )
    return mapped


# ----------------------------------------------------------------------
# The runtime session (the fold result — an execution artifact, never
# an authority; LOCK-117)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeSession:
    """The typed session-runtime record (the deterministic fold result
    of the runtime journal).

    ``runtime_id`` is content-derived over the STATE-INDEPENDENT
    creation core (the owning contract id, the creation instant, the
    creation provenance): lifecycle evolution (activation, reconnects,
    degraded episodes, failure, termination) never changes the runtime
    identity — the execution artifact evolves while the contract stays
    stable (LOCK-117).  ``contract_id`` cites the OWNING canonical
    contract (attribution; the contract is the sole authority — this
    record carries no constraint material at all).  ``route_decision_
    id`` / ``path_id`` name the CURRENT realization (the WORK-012
    member shape; empty exactly while PENDING); they change ONLY
    through the explicit reconnect discipline enforced by the journal
    fold.  ``sequence`` is the journal position of the last applied
    event (the deterministic replay watermark).
    """

    runtime_id: str
    contract_id: str
    state: str
    created_at: str
    sequence: int
    provenance: Provenance
    route_decision_id: str = ""
    path_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_id", _require_id(self.runtime_id, "runtime.runtime_id"))
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "runtime.contract_id")
        )
        object.__setattr__(self, "state", _require_in(self.state, RUNTIME_STATES, "runtime.state"))
        object.__setattr__(
            self, "created_at", _require_instant(self.created_at, "runtime.created_at")
        )
        object.__setattr__(
            self, "sequence", _require_sequence(self.sequence, "runtime.sequence")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "runtime.provenance")
        )
        for member in ROUTE_MEMBER_NAMES:
            value = getattr(self, member)
            if value:
                object.__setattr__(
                    self,
                    member,
                    _require_str(value, "runtime.%s" % member, pattern=_REF_VALUE_PATTERN),
                )
        # a realization exists exactly in the realization-holder states
        has_refs = bool(self.route_decision_id) and bool(self.path_id)
        if self.state in ("ACTIVE", "RECONNECTING", "DEGRADED") and not has_refs:
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "a runtime session in %s must carry its current realization "
                "references (route_decision_id AND path_id) — a realization "
                "holder without named references is a silent replacement "
                "shape (the WORK-012 discipline)" % self.state,
            )
        if self.state in ("PENDING", "FAILED", "TERMINATED") and has_refs:
            # FAILED/TERMINATED keep their last-named references as
            # historical evidence; PENDING never carries any
            if self.state == "PENDING":
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "a PENDING runtime session carries no realization references "
                    "(activation names them explicitly)",
                )

    @property
    def is_terminal(self) -> bool:
        return self.state in RUNTIME_TERMINAL_STATES

    def realization_refs(self) -> Tuple[str, str]:
        """The current realization references (both members; fail
        closed unless the runtime holds a named realization)."""
        if not self.route_decision_id or not self.path_id:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "runtime session %s carries no named realization in %s"
                % (self.runtime_id[:23], self.state),
            )
        return (self.route_decision_id, self.path_id)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "runtime_id": self.runtime_id,
            "contract_id": self.contract_id,
            "state": self.state,
            "created_at": self.created_at,
            "sequence": self.sequence,
            "provenance": self.provenance.to_dict(),
        }
        if self.route_decision_id:
            data["route_decision_id"] = self.route_decision_id
        if self.path_id:
            data["path_id"] = self.path_id
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RuntimeSession":
        if not isinstance(data, Mapping):
            raise ResilienceError(ResilienceReason.INVALID_INPUT, "runtime must be a mapping")
        with _wrap_consumed_error("runtime deserialization"):
            return RuntimeSession(
                runtime_id=data.get("runtime_id"),
                contract_id=data.get("contract_id"),
                state=data.get("state"),
                created_at=data.get("created_at"),
                sequence=data.get("sequence"),
                provenance=Provenance.from_dict(data.get("provenance")),
                route_decision_id=data.get("route_decision_id") or "",
                path_id=data.get("path_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "runtime record")


def derive_runtime_id(
    contract_id: str, created_at: str, provenance: Provenance
) -> str:
    """The content-derived runtime identity over the state-independent
    creation core (the owning contract, the creation instant, the
    creation provenance)."""
    document = {
        "contract_id": contract_id,
        "created_at": created_at,
        "provenance": provenance.to_dict(),
    }
    return _derive_id(_RUNTIME_NAMESPACE, document, "runtime id document")


# ----------------------------------------------------------------------
# The journaled runtime event (deterministic, replayable, typed)
# ----------------------------------------------------------------------

#: The route-member groups (the WORK-012 member shape, one group per
#: reconnect role; the plain group names the CURRENT realization and
#: exists exactly on the activating event).
_ROUTE_PLAIN_MEMBERS: Tuple[str, ...] = ("route_decision_id", "path_id")
_ROUTE_OLD_MEMBERS: Tuple[str, ...] = ("old_route_decision_id", "old_path_id")
_ROUTE_CANDIDATE_MEMBERS: Tuple[str, ...] = (
    "candidate_route_decision_id",
    "candidate_path_id",
)
_ROUTE_NEW_MEMBERS: Tuple[str, ...] = ("new_route_decision_id", "new_path_id")
_ALL_ROUTE_MEMBERS: Tuple[str, ...] = (
    _ROUTE_PLAIN_MEMBERS + _ROUTE_OLD_MEMBERS + _ROUTE_CANDIDATE_MEMBERS + _ROUTE_NEW_MEMBERS
)

#: The per-kind member discipline: kind -> (required members, members
#: that must be ABSENT).  Every route member outside its kind's shape
#: is a silent-replacement shape and fails closed; ``reason`` and the
#: evidence members are typed per kind.
_KIND_MEMBER_RULES: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "session-created": ((), _ALL_ROUTE_MEMBERS + ("reason", "evidence_kind")),
    "session-activated": (
        _ROUTE_PLAIN_MEMBERS,
        _ROUTE_OLD_MEMBERS + _ROUTE_CANDIDATE_MEMBERS + _ROUTE_NEW_MEMBERS
        + ("reason", "evidence_kind"),
    ),
    "reconnect-initiated": (
        _ROUTE_OLD_MEMBERS + _ROUTE_CANDIDATE_MEMBERS,
        _ROUTE_PLAIN_MEMBERS + _ROUTE_NEW_MEMBERS + ("reason", "evidence_kind"),
    ),
    "reconnect-completed": (
        _ROUTE_OLD_MEMBERS + _ROUTE_NEW_MEMBERS,
        _ROUTE_PLAIN_MEMBERS + _ROUTE_CANDIDATE_MEMBERS + ("reason", "evidence_kind"),
    ),
    "reconnect-failed": (
        ("reason",),
        _ALL_ROUTE_MEMBERS + ("evidence_kind",),
    ),
    "degraded-entered": (
        ("evidence_kind",),
        _ALL_ROUTE_MEMBERS + ("reason",),
    ),
    "degraded-recovered": ((), _ALL_ROUTE_MEMBERS + ("reason", "evidence_kind")),
    "session-failed": (("reason",), _ALL_ROUTE_MEMBERS + ("evidence_kind",)),
    "session-terminated": ((), _ALL_ROUTE_MEMBERS + ("reason", "evidence_kind")),
}


@dataclass(frozen=True)
class RuntimeEvent:
    """One typed runtime journal event (the deterministic, replayable
    evidence unit of the execution-runtime lifecycle).

    Every event carries: the content-derived event identity
    (``event_id``, tamper-evident over the full event core); the owning
    runtime session (``runtime_id``) and the owning canonical contract
    (``contract_id`` — attribution on every record); the deterministic
    journal position (``sequence``, a positive integer — gaps and
    conflicts fail closed at replay); the event kind (the frozen
    :data:`RUNTIME_EVENT_KINDS` vocabulary); the injected instant; the
    state AFTER the event (``state_after`` — the fold chains states
    through these); and the typed provenance (LOCK-118).

    Kind-specific members (fail-closed by kind — the full
    :data:`_KIND_MEMBER_RULES` discipline, so no event shape can carry
    realization-reference members outside the reconnect discipline):

    - ``session-activated`` — ``route_decision_id`` / ``path_id`` (the
      INITIAL realization references; both required);
    - ``reconnect-initiated`` — ``old_route_decision_id`` /
      ``old_path_id`` (the references being left) AND
      ``candidate_route_decision_id`` / ``candidate_path_id`` (the
      proposed new ones; all four required);
    - ``reconnect-completed`` — ``old_route_decision_id`` /
      ``old_path_id`` AND ``new_route_decision_id`` / ``new_path_id``
      (all four required — the completed reconnect is the WORK-012
      single-event evidence shape carrying BOTH sides);
    - ``reconnect-failed`` / ``session-failed`` — ``reason`` (a typed
      non-empty reason string);
    - ``degraded-entered`` — ``evidence_kind`` (drawn from the
      accepted ``evidence/`` LOCK-106 type vocabulary, consumed BY
      REFERENCE) and optional ``evidence_refs`` (opaque
      ``decision``-kinded references, the M002 record-assurance
      discipline).
    """

    runtime_id: str
    contract_id: str
    sequence: int
    kind: str
    recorded_at: str
    state_after: str
    provenance: Provenance
    event_id: str = ""
    route_decision_id: str = ""
    path_id: str = ""
    old_route_decision_id: str = ""
    old_path_id: str = ""
    candidate_route_decision_id: str = ""
    candidate_path_id: str = ""
    new_route_decision_id: str = ""
    new_path_id: str = ""
    reason: str = ""
    evidence_kind: str = ""
    evidence_refs: Tuple[OpaqueReference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_id", _require_id(self.runtime_id, "event.runtime_id"))
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "event.contract_id")
        )
        object.__setattr__(
            self, "sequence", _require_sequence(self.sequence, "event.sequence")
        )
        object.__setattr__(self, "kind", _require_in(self.kind, RUNTIME_EVENT_KINDS, "event.kind"))
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "event.recorded_at")
        )
        object.__setattr__(
            self,
            "state_after",
            _require_in(self.state_after, RUNTIME_STATES, "event.state_after"),
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "event.provenance")
        )
        # the kind-member discipline (fail-closed per kind): required
        # members present, foreign members absent — a route member on
        # the wrong kind is a silent-replacement shape
        required, forbidden = _KIND_MEMBER_RULES[self.kind]
        missing = [name for name in required if not getattr(self, name)]
        if missing:
            if any(name in _ALL_ROUTE_MEMBERS for name in missing):
                raise ResilienceError(
                    ResilienceReason.SILENT_REPLACEMENT,
                    "the %s event is missing the route-change members %s (the "
                    "WORK-012 discipline requires BOTH the old AND the new "
                    "route references on every reconnect — a route change is "
                    "never a silent replacement)"
                    % (self.kind, ", ".join(missing)),
                )
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the %s event is missing the members %s" % (self.kind, ", ".join(missing)),
            )
        foreign = [name for name in forbidden if getattr(self, name)]
        if foreign:
            if any(name in _ALL_ROUTE_MEMBERS for name in foreign):
                raise ResilienceError(
                    ResilienceReason.SILENT_REPLACEMENT,
                    "the %s event carries the realization-reference members %s "
                    "outside the reconnect discipline (a route change happens "
                    "ONLY through the explicit reconnect events — never a "
                    "silent replacement)" % (self.kind, ", ".join(foreign)),
                )
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the %s event carries the members %s outside its frozen shape"
                % (self.kind, ", ".join(foreign)),
            )
        # the route members, when present, must be well-formed opaque
        # reference values (LOCK-117: references, never authority)
        for member in _ALL_ROUTE_MEMBERS:
            value = getattr(self, member)
            if value:
                object.__setattr__(
                    self,
                    member,
                    _require_str(value, "event.%s" % member, pattern=_REF_VALUE_PATTERN),
                )
        if self.reason:
            object.__setattr__(
                self,
                "reason",
                _require_str(self.reason, "event.reason", pattern=_REF_VALUE_PATTERN),
            )
        if self.evidence_kind:
            object.__setattr__(
                self,
                "evidence_kind",
                _require_in(self.evidence_kind, EVIDENCE_TYPES, "event.evidence_kind"),
            )
        object.__setattr__(
            self,
            "evidence_refs",
            _normalize_evidence_refs(self.evidence_refs, "event.evidence_refs"),
        )
        expected = _derive_event_id_from_core(self)
        if not self.event_id:
            object.__setattr__(self, "event_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.event_id) is None:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "event.event_id must be the content-derived identity (sha256:...)",
                )
            if self.event_id != expected:
                raise ResilienceError(
                    ResilienceReason.ID_MISMATCH,
                    "event_id does not match the derived identity (tamper evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "runtime_id": self.runtime_id,
            "contract_id": self.contract_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "recorded_at": self.recorded_at,
            "state_after": self.state_after,
            "provenance": self.provenance.to_dict(),
        }
        for member in (
            "route_decision_id",
            "path_id",
            "old_route_decision_id",
            "old_path_id",
            "candidate_route_decision_id",
            "candidate_path_id",
            "new_route_decision_id",
            "new_path_id",
            "reason",
            "evidence_kind",
        ):
            value = getattr(self, member)
            if value:
                data[member] = value
        if self.evidence_refs:
            data["evidence_refs"] = [r.to_dict() for r in self.evidence_refs]
        data["event_id"] = self.event_id
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RuntimeEvent":
        if not isinstance(data, Mapping):
            raise ResilienceError(ResilienceReason.INVALID_INPUT, "event must be a mapping")
        with _wrap_consumed_error("event deserialization"):
            return RuntimeEvent(
                runtime_id=data.get("runtime_id"),
                contract_id=data.get("contract_id"),
                sequence=data.get("sequence"),
                kind=data.get("kind"),
                recorded_at=data.get("recorded_at"),
                state_after=data.get("state_after"),
                provenance=Provenance.from_dict(data.get("provenance")),
                event_id=data.get("event_id") or "",
                route_decision_id=data.get("route_decision_id") or "",
                path_id=data.get("path_id") or "",
                old_route_decision_id=data.get("old_route_decision_id") or "",
                old_path_id=data.get("old_path_id") or "",
                candidate_route_decision_id=data.get("candidate_route_decision_id") or "",
                candidate_path_id=data.get("candidate_path_id") or "",
                new_route_decision_id=data.get("new_route_decision_id") or "",
                new_path_id=data.get("new_path_id") or "",
                reason=data.get("reason") or "",
                evidence_kind=data.get("evidence_kind") or "",
                evidence_refs=tuple(
                    OpaqueReference.from_dict(r) for r in data.get("evidence_refs") or ()
                ),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "event record")


def _derive_event_id_from_core(event: RuntimeEvent) -> str:
    document = {
        "runtime_id": event.runtime_id,
        "contract_id": event.contract_id,
        "sequence": event.sequence,
        "kind": event.kind,
        "recorded_at": event.recorded_at,
        "state_after": event.state_after,
        "provenance": event.provenance.to_dict(),
        "route_decision_id": event.route_decision_id,
        "path_id": event.path_id,
        "old_route_decision_id": event.old_route_decision_id,
        "old_path_id": event.old_path_id,
        "candidate_route_decision_id": event.candidate_route_decision_id,
        "candidate_path_id": event.candidate_path_id,
        "new_route_decision_id": event.new_route_decision_id,
        "new_path_id": event.new_path_id,
        "reason": event.reason,
        "evidence_kind": event.evidence_kind,
        "evidence_refs": [r.to_dict() for r in event.evidence_refs],
    }
    return _derive_id(_EVENT_NAMESPACE, document, "event id document")


# ----------------------------------------------------------------------
# The typed reconnect evidence record (the WORK-012 discipline,
# re-expressed on the 1.1 authority)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeReconnect:
    """One explicit runtime reconnect as typed evidence (the
    re-expressed WORK-012 discipline: a route change is ALWAYS an
    explicit lifecycle event recording the old AND the new route
    references — never a silent replacement).

    Constructed from the runtime journal's initiating/completing event
    pair by :func:`resilience.journal.reconnect_evidence`; fail-closed
    on any reconnect missing either side of the route change
    (``resilience-silent-replacement``).  ``reconnect_id`` is
    content-derived over the full pair (tamper-evident).
    """

    runtime_id: str
    initiated_event_id: str
    completed_event_id: str
    reconnect_instant: str
    old_route_decision_id: str
    new_route_decision_id: str
    old_path_id: str
    new_path_id: str
    reconnect_id: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("runtime_id", self.runtime_id),
            ("initiated_event_id", self.initiated_event_id),
            ("completed_event_id", self.completed_event_id),
        ):
            object.__setattr__(
                self, label, _require_id(value, "reconnect.%s" % label)
            )
        object.__setattr__(
            self,
            "reconnect_instant",
            _require_instant(self.reconnect_instant, "reconnect.reconnect_instant"),
        )
        # the WORK-012 discipline, enforced: a reconnect record missing
        # EITHER side of the route change is a silent replacement and
        # fails closed (never a generic validation error — the reason
        # cites the discipline itself)
        route_members = (
            ("old_route_decision_id", self.old_route_decision_id),
            ("new_route_decision_id", self.new_route_decision_id),
            ("old_path_id", self.old_path_id),
            ("new_path_id", self.new_path_id),
        )
        missing = [label for label, value in route_members if not isinstance(value, str) or not value]
        if missing:
            raise ResilienceError(
                ResilienceReason.SILENT_REPLACEMENT,
                "the reconnect record is missing the route-change members %s "
                "(the WORK-012 discipline requires BOTH the old AND the new "
                "route references on every reconnect — a route change is "
                "never a silent replacement)" % ", ".join(sorted(missing)),
            )
        for label, value in route_members:
            object.__setattr__(
                self,
                label,
                _require_str(value, "reconnect.%s" % label, pattern=_REF_VALUE_PATTERN),
            )
        expected = _derive_reconnect_id_from_core(self)
        if not self.reconnect_id:
            object.__setattr__(self, "reconnect_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.reconnect_id) is None:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "reconnect.reconnect_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.reconnect_id != expected:
                raise ResilienceError(
                    ResilienceReason.ID_MISMATCH,
                    "reconnect_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "initiated_event_id": self.initiated_event_id,
            "completed_event_id": self.completed_event_id,
            "reconnect_instant": self.reconnect_instant,
            "old_route_decision_id": self.old_route_decision_id,
            "new_route_decision_id": self.new_route_decision_id,
            "old_path_id": self.old_path_id,
            "new_path_id": self.new_path_id,
            "reconnect_id": self.reconnect_id,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RuntimeReconnect":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "reconnect must be a mapping"
            )
        return RuntimeReconnect(
            runtime_id=data.get("runtime_id"),
            initiated_event_id=data.get("initiated_event_id"),
            completed_event_id=data.get("completed_event_id"),
            reconnect_instant=data.get("reconnect_instant"),
            old_route_decision_id=data.get("old_route_decision_id"),
            new_route_decision_id=data.get("new_route_decision_id"),
            old_path_id=data.get("old_path_id"),
            new_path_id=data.get("new_path_id"),
            reconnect_id=data.get("reconnect_id") or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "reconnect record")


def _derive_reconnect_id_from_core(record: RuntimeReconnect) -> str:
    document = {
        "runtime_id": record.runtime_id,
        "initiated_event_id": record.initiated_event_id,
        "completed_event_id": record.completed_event_id,
        "reconnect_instant": record.reconnect_instant,
        "old_route_decision_id": record.old_route_decision_id,
        "new_route_decision_id": record.new_route_decision_id,
        "old_path_id": record.old_path_id,
        "new_path_id": record.new_path_id,
    }
    return _derive_id(_RECONNECT_NAMESPACE, document, "reconnect id document")


# ----------------------------------------------------------------------
# The realization projection (the M008 vocabulary consumed BY
# REFERENCE — projected onto, never redefined)
# ----------------------------------------------------------------------


def runtime_realization_snapshot(
    session: RuntimeSession,
    *,
    observed_at: str,
    provenance: Optional[Provenance] = None,
) -> RealizationSnapshot:
    """Project one runtime session onto the M008 realization view (the
    accepted ``replan.RealizationSnapshot`` record, consumed BY
    REFERENCE — the resilience runtime NEVER redefines the realization
    vocabulary; it projects onto the frozen M008 states through
    :data:`RUNTIME_REALIZATION_MAP`).

    Fail-closed gates: the input must be a :class:`RuntimeSession`; the
    runtime state must be a replan surface (PENDING fails closed as
    not-established; FAILED/TERMINATED fail closed as terminal — never
    a silent downgrade).  The snapshot cites the runtime id as the
    session reference, the CURRENT route references (only the explicit
    reconnect discipline ever changes them) and the current path as an
    opaque ``execution-artifact`` reference (LOCK-117: DATA, never
    authority).
    """
    if not isinstance(session, RuntimeSession):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "runtime_realization_snapshot requires a resilience RuntimeSession "
            "(got %s)" % type(session).__name__,
        )
    projected = check_realization_surface(session.state)
    route_decision_id, path_id = session.realization_refs()
    view_provenance = (
        provenance
        if provenance is not None
        else Provenance(
            issuer=RUNTIME_ISSUER,
            decision_refs=(session.runtime_id, session.contract_id),
        )
    )
    if not isinstance(view_provenance, Provenance):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    with _wrap_consumed_error("the realization snapshot projection"):
        return RealizationSnapshot(
            contract_id=session.contract_id,
            surface="session",
            state=projected,
            observed_at=observed_at,
            session_ref=session.runtime_id,
            route_refs=(route_decision_id,),
            artifact_refs=(
                OpaqueReference(
                    ref_kind="execution-artifact",
                    value=path_id,
                    provenance=Provenance(
                        issuer=RUNTIME_ISSUER,
                        decision_refs=(session.runtime_id,),
                    ),
                ),
            ),
            provenance=view_provenance,
        )


# ----------------------------------------------------------------------
# Import-time vocabulary consistency (fail loud on drift)
# ----------------------------------------------------------------------


def _check_vocabularies() -> None:
    """The consumed vocabularies must be exactly the frozen sets this
    domain was built against (fail loud on drift — never silently
    mis-project)."""
    if REALIZATION_STATES != ("REALIZING", "DEGRADED", "FAILED", "SUPERSEDED"):
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "the consumed M008 realization-state vocabulary has drifted from "
            "the frozen four-state set this domain projects onto",
        )
    if set(EVIDENCE_TYPES) != {"claim", "observation", "commitment", "attestation"}:
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "the consumed evidence LOCK-106 type vocabulary has drifted from "
            "the frozen four-type set",
        )
    if set(CONSTRAINT_KINDS) != {
        "latency-bound",
        "throughput-floor",
        "availability-floor",
        "loss-bound",
        "jitter-bound",
        "isolation",
        "jurisdiction",
        "security-level",
        "provider-trust",
        "evidence-obligation",
        "geography",
        "priority",
    }:
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "the consumed contracts constraint-kind vocabulary has drifted "
            "from the frozen 12-kind set",
        )
    if set(RUNTIME_REALIZATION_MAP.values()) - set(REALIZATION_STATES):
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "the runtime realization projection escapes the consumed M008 "
            "vocabulary (drift guard)",
        )
    if RUNTIME_STATES != (
        "PENDING",
        "ACTIVE",
        "RECONNECTING",
        "DEGRADED",
        "FAILED",
        "TERMINATED",
    ):
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "the M015 runtime-state vocabulary has drifted",
        )
    for kind in RUNTIME_EVENT_KINDS:
        required, _ = _KIND_MEMBER_RULES[kind]
        if any(name not in _ALL_ROUTE_MEMBERS + ("reason", "evidence_kind") for name in required):
            raise ResilienceError(
                ResilienceReason.VOCABULARY,
                "the event kind %r carries an unknown required member (drift "
                "guard)" % kind,
            )


_check_vocabularies()
