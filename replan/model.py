"""ADCOS replan domain model (M008 — Replan and Failover).

The closed-loop replan records of Architecture 1.1 §9: when an active
contract's realization becomes unsatisfiable (adapter failure, segment
loss, assurance degradation/violation, route expiry, or the constraint
set itself becoming unsatisfiable with the available alternatives),
the replan engine computes an ALTERNATIVE realization that still
satisfies the SAME contract.

The central boundary (enforced throughout):

    REPLAN DECISION
        = the typed, deterministic failover record over the canonical
          contract's IMMUTABLE hard-constraint set (LOCK-108)
        != CONTRACT AUTHORITY (contracts/ stays the sole authority —
          the decision cites the contract and rides back through the
          contract's own command vocabulary, never around it)
        != EXECUTION PLAN AUTHORITY (M006 owns the plan/segment
          vocabulary; a plan candidate is consumed BY REFERENCE)
        != ADAPTER / PROVIDER SURFACE (M007 owns the capability
          surface; offer views are consumed as DATA, LOCK-110)
        != SESSION / MOBILITY / MULTIPATH AUTHORITY (the WORK-012/014/
          013 packages stay their own authorities — the disclosed
          harvest seam in ``replan.execution_state`` reads their
          public surfaces by reference, one-way, and their
          explicit-reconnect discipline is PRESERVED, never bypassed)
        != OPTIMIZER AUTHORITY (LOCK-111: the engine is a deterministic
          strategy over DATA inputs; tie-breaking rules are injected,
          never wall-clock)

LOCK-108 discipline (the core rule of this domain): replanning MUST
NOT silently weaken hard contract constraints.  Every candidate
realization is validated against the contract's full hard-constraint
set; a candidate that weakens or drops ANY hard constraint is
REJECTED with the typed ``replan-constraint-weakened`` reason citing
the specific kinds.  A realization that cannot satisfy the hard
constraints enters an EXPLICIT ``DEGRADED``/``FAILED`` state or
triggers EXPLICIT contract renegotiation (a typed renegotiation
notice referencing the contract to supersede) — never a silent
downgrade.  There is NO constraint input on any decision path: the
constraint set a ``ReplanDecision`` carries is the CONTRACT's own,
taken verbatim with the contract's own LOCK-108 fingerprint.

Determinism (LOCK-111/LOCK-119): content-derived ids over WORK-003
canonical JSON (namespaced); injected instants only (no wall clock);
no randomness, no UUIDs, no network, no secrets; canonical-JSON
round-trips with tamper-evident ids re-verified at deserialization.
"""

from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import (
    CONSTRAINT_KINDS,
    ContractError,
    HardConstraint,
    OpaqueReference,
    Provenance,
)

from .errors import ReplanError, ReplanReason


@contextmanager
def _wrap_contract_error(label: str) -> Iterator[None]:
    """Exception isolation at the consumed-domain boundary: contract
    validation errors surface as typed replan errors with their
    deterministic text preserved — never a foreign exception type, never
    raw exception text into stored state.  The consumed domain's
    LOCK-119 secret rejection maps onto this surface's own
    ``replan-secret-rejected`` reason."""
    try:
        yield
    except ContractError as error:
        code = ReplanReason.INVALID_INPUT
        if getattr(error, "code", "") == "secret-rejected":
            code = ReplanReason.SECRET_REJECTED
        raise ReplanError(
            code,
            "%s: %s" % (label, error.detail if hasattr(error, "detail") else error),
        ) from None

# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: What failed — the typed replan trigger kinds.  ``adapter-failure``
#: and ``segment-loss`` are execution-surface failures; ``assurance-
#: degraded`` / ``assurance-violated`` carry the M005 closed-loop
#: verdicts; ``route-expiry`` is the WORK-012 path-expiry shape;
#: ``constraint-unsatisfiable`` is the impossible-realization case
#: (the hard constraints cannot be satisfied by ANY available
#: alternative — the explicit renegotiation trigger class).
TRIGGER_KINDS: Tuple[str, ...] = (
    "adapter-failure",
    "segment-loss",
    "assurance-degraded",
    "assurance-violated",
    "route-expiry",
    "constraint-unsatisfiable",
)

#: The M008-owned realization states (the frozen 1.1 §9 explicit
#: degraded/failed realization vocabulary — deliberately NOT the M006
#: segment vocabulary, which stops at PLANNED/RESERVED/ACTIVATED/
#: MEASURED/RELEASED, and NOT the contract lifecycle, which the
#: contracts/ domain owns):
#:
#: - ``REALIZING`` — the realization is satisfying the contract;
#: - ``DEGRADED`` — the EXPLICIT degraded realization state (frozen
#:   §9: never a silent downgrade);
#: - ``FAILED`` — the realization cannot satisfy the hard constraints
#:   (terminal);
#: - ``SUPERSEDED`` — the realization was replaced by an adopted
#:   failover alternative (terminal).
REALIZATION_STATES: Tuple[str, ...] = (
    "REALIZING",
    "DEGRADED",
    "FAILED",
    "SUPERSEDED",
)

#: Terminal realization states (never transition out).
REALIZATION_TERMINAL_STATES: Tuple[str, ...] = ("FAILED", "SUPERSEDED")

#: Legal realization-state transitions (fail-closed elsewhere).
#: ``DEGRADED -> REALIZING`` is the recovery edge (an adopted
#: failover alternative restores a satisfying realization);
#: ``REALIZING -> SUPERSEDED`` is the make-before-break failover of a
#: still-satisfying realization (LOCK-116 proactive handover shape).
REALIZATION_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "REALIZING": ("DEGRADED", "FAILED", "SUPERSEDED"),
    "DEGRADED": ("REALIZING", "FAILED", "SUPERSEDED"),
    "FAILED": (),
    "SUPERSEDED": (),
}

#: Which surface a realization snapshot rides on (the harvested
#: WORK-era execution surfaces plus the accepted M006 plan surface —
#: each consumed by reference, never re-owned here).
REALIZATION_SURFACES: Tuple[str, ...] = (
    "execution-plan",
    "session",
    "mobility-handover",
    "multipath-plan",
)

#: The alternative-realization candidate kinds.  ``execution-plan`` —
#: a new ``ExecutionPlan`` translated from the SAME contract (M006,
#: by reference); ``mobility-handover`` / ``multipath-path`` — the
#: harvested handover/multi-path alternative models (WORK-014/WORK-
#: 013); ``provider-alternative`` — an available alternative from
#: the M007 adapter capability surface (an ``OfferView`` as DATA).
CANDIDATE_KINDS: Tuple[str, ...] = (
    "execution-plan",
    "mobility-handover",
    "multipath-path",
    "provider-alternative",
)

#: The replan decision vocabulary (the frozen §9 outcomes):
#:
#: - ``adopt-alternative`` — an alternative realization satisfying
#:   the SAME hard constraints is adopted;
#: - ``degraded`` — no acceptable alternative and a soft trigger:
#:   the realization enters the EXPLICIT degraded state (the
#:   contract records ``degraded`` assurance through its own
#:   command vocabulary);
#: - ``failed`` — no acceptable alternative and a hard trigger: the
#:   realization enters the EXPLICIT failed state (the contract
#:   records ``violated`` assurance), carrying the explicit
#:   renegotiation notice;
#: - ``renegotiate`` — the impossible-realization decision class
#:   (``constraint-unsatisfiable``): the realization fails AND an
#:   explicit contract renegotiation is triggered (the successor
#:   contract is created through the M002 ``superseded-contract``
#:   reference path by the principal-side flow; the notice is the
#:   typed trigger record).
DECISION_KINDS: Tuple[str, ...] = (
    "adopt-alternative",
    "degraded",
    "failed",
    "renegotiate",
)

#: The soft trigger kinds (a no-alternative evaluation degrades the
#: realization explicitly instead of failing it: the closed loop keeps
#: observing — frozen §9 degraded is an evaluated, recorded state).
SOFT_TRIGGER_KINDS: Tuple[str, ...] = ("assurance-degraded",)

#: The impossible-realization trigger class (explicit renegotiation).
RENEGOTIATION_TRIGGER_KINDS: Tuple[str, ...] = ("constraint-unsatisfiable",)

#: The declared tie-break key vocabulary (LOCK-111: deterministic,
#: injected and declared — every key is a CONTENT key, never a
#: temporal one).  ``candidate-id`` is the total order guarantee and
#: must be the final component of every declared rule.
TIE_BREAK_KEYS: Tuple[str, ...] = ("candidate-kind", "candidate-id")

#: The default injected tie-breaking rule.
DEFAULT_TIE_BREAK: Tuple[str, ...] = ("candidate-kind", "candidate-id")


def _normalize_tie_break(
    tie_break: object, label: str = "tie_break", *, complete: bool = False
) -> Tuple[str, ...]:
    """Validate a declared tie-breaking rule (LOCK-111).

    With ``complete=True`` (the engine input) a rule that omits the
    ``candidate-id`` key is completed with it (the total-order
    guarantee); with ``complete=False`` (decision-record construction)
    the stored rule must already end with ``candidate-id`` (tamper
    evidence — a record never invents the rule it declares).  Content
    keys only — a temporal key does not exist in the vocabulary (never
    wall-clock).
    """
    items = _require_tuple(tie_break, label, min_len=1)
    for i, item in enumerate(items):
        if item not in TIE_BREAK_KEYS:
            raise ReplanError(
                ReplanReason.TIE_BREAK_INVALID,
                "%s[%d] must be one of %s (found %r) — content keys only, "
                "never temporal (LOCK-111 deterministic ordering)"
                % (label, i, ", ".join(TIE_BREAK_KEYS), item),
            )
    if len(set(items)) != len(items):
        raise ReplanError(
            ReplanReason.TIE_BREAK_INVALID,
            "%s must not repeat a tie-break key" % label,
        )
    if complete and "candidate-id" not in items:
        items = tuple(items) + ("candidate-id",)
    if items[-1] != "candidate-id":
        raise ReplanError(
            ReplanReason.TIE_BREAK_INVALID,
            "%s must end with the candidate-id key (the total-order "
            "guarantee; LOCK-111 deterministic ordering)" % label,
        )
    return tuple(items)

_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")

_TRIGGER_NAMESPACE = "adc-os-replan-trigger"
_CANDIDATE_NAMESPACE = "adc-os-replan-candidate"
_SNAPSHOT_NAMESPACE = "adc-os-replan-realization"
_DECISION_NAMESPACE = "adc-os-replan-decision"
_RECONNECT_NAMESPACE = "adc-os-replan-reconnect"
_NOTICE_NAMESPACE = "adc-os-replan-renegotiation-notice"


# ----------------------------------------------------------------------
# Internal helpers (the consumed-domain conventions, re-used)
# ----------------------------------------------------------------------


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload, label)).hexdigest()


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise ReplanError(ReplanReason.INVALID_INPUT, "%s must be a non-empty string" % label)
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ReplanError(ReplanReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value))
    _reject_secret(value, label)
    return value


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-looking material never enters replan data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise ReplanError(
            ReplanReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter replan data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise ReplanError(
            ReplanReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter replan data" % label,
        )


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "%s must be the content-derived identity (sha256:...)" % label,
        )
    _reject_secret(value, label)
    return value


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise ReplanError(
            ReplanReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _require_tuple(value: object, label: str, *, min_len: int = 0) -> Tuple[Any, ...]:
    if not isinstance(value, (tuple, list)) or isinstance(value, (str, bytes)):
        raise ReplanError(ReplanReason.INVALID_INPUT, "%s must be a sequence" % label)
    if len(value) < min_len:
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "%s requires at least %d entr%s" % (label, min_len, "y" if min_len == 1 else "ies"),
        )
    return tuple(value)


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReplanError(ReplanReason.INVALID_INPUT, "%s must be a non-empty instant string" % label)
    try:
        parse_instant(value)
    except TemporalError as error:
        raise ReplanError(
            ReplanReason.TEMPORAL_INVALID,
            "%s %r is not RFC 3339 UTC: %s" % (label, value, error),
        ) from None
    _reject_secret(value, label)
    return value


def _require_provenance(value: object, label: str) -> Provenance:
    if not isinstance(value, Provenance):
        raise ReplanError(ReplanReason.INVALID_INPUT, "%s must be a Provenance record" % label)
    return value


def _normalize_constraints(value: object, label: str) -> Tuple[HardConstraint, ...]:
    constraints = _require_tuple(value, label)
    normalized = []
    for i, item in enumerate(constraints):
        if not isinstance(item, HardConstraint):
            raise ReplanError(
                ReplanReason.INVALID_INPUT,
                "%s[%d] must be a contracts.HardConstraint record" % (label, i),
            )
        normalized.append(item)
    return tuple(normalized)


def _normalize_refs(value: object, label: str, ref_kind: str) -> Tuple[OpaqueReference, ...]:
    refs = _require_tuple(value, label)
    normalized = []
    for i, item in enumerate(refs):
        if not isinstance(item, OpaqueReference):
            raise ReplanError(
                ReplanReason.INVALID_INPUT,
                "%s[%d] must be an OpaqueReference record" % (label, i),
            )
        if item.ref_kind != ref_kind:
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "%s[%d] must use the %s reference kind (found %s)"
                % (label, i, ref_kind, item.ref_kind),
            )
        normalized.append(item)
    return tuple(normalized)


def _constraints_fingerprint(constraints: Sequence[HardConstraint]) -> str:
    """The LOCK-108 constraint-set digest — the exact M002 convention
    (``ConnectivityContract.hard_constraint_fingerprint``), consumed by
    reference so a decision's fingerprint is byte-comparable with the
    owning contract's own fingerprint."""
    document = [constraint.to_dict() for constraint in constraints]
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes({"constraints": document})
    ).hexdigest()


# ----------------------------------------------------------------------
# The typed replan trigger (what failed)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ReplanTrigger:
    """The typed record of WHAT failed on an active realization.

    ``evidence_refs`` are typed ``decision``-kinded opaque references
    (the M002 ``record-assurance`` evidence discipline: assurance and
    failure verdicts enter as opaque decision references with
    provenance — LOCK-117/LOCK-118).  ``realization_ref`` cites the
    realization record being replaced (the M008 snapshot id, or the
    M006 plan id, or the WORK-012 session id — a reference, never an
    authority).  ``recorded_at`` is an INJECTED instant.
    """

    kind: str
    contract_id: str
    recorded_at: str
    evidence_refs: Tuple[OpaqueReference, ...] = ()
    realization_ref: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(issuer="replan:trigger"))
    trigger_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _require_in(self.kind, TRIGGER_KINDS, "trigger.kind"))
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "trigger.contract_id")
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "trigger.recorded_at")
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _normalize_refs(self.evidence_refs, "trigger.evidence_refs", "decision"),
        )
        if self.realization_ref:
            object.__setattr__(
                self,
                "realization_ref",
                _require_str(
                    self.realization_ref, "trigger.realization_ref", pattern=_REF_VALUE_PATTERN
                ),
            )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "trigger.provenance")
        )
        expected = _derive_trigger_id_from_core(self)
        if not self.trigger_id:
            object.__setattr__(self, "trigger_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.trigger_id) is None:
                raise ReplanError(
                    ReplanReason.INVALID_INPUT,
                    "trigger.trigger_id must be the content-derived identity (sha256:...)",
                )
            if self.trigger_id != expected:
                raise ReplanError(
                    ReplanReason.ID_MISMATCH,
                    "trigger_id does not match the derived identity (tamper evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "kind": self.kind,
            "contract_id": self.contract_id,
            "recorded_at": self.recorded_at,
            "evidence_refs": [r.to_dict() for r in self.evidence_refs],
            "provenance": self.provenance.to_dict(),
        }
        if self.realization_ref:
            data["realization_ref"] = self.realization_ref
        data["trigger_id"] = self.trigger_id
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ReplanTrigger":
        if not isinstance(data, Mapping):
            raise ReplanError(ReplanReason.INVALID_INPUT, "trigger must be a mapping")
        with _wrap_contract_error("trigger deserialization"):
            return ReplanTrigger(
                kind=data.get("kind"),
                contract_id=data.get("contract_id"),
                recorded_at=data.get("recorded_at"),
                evidence_refs=tuple(
                    OpaqueReference.from_dict(r) for r in data.get("evidence_refs") or ()
                ),
                realization_ref=data.get("realization_ref") or "",
                provenance=Provenance.from_dict(data.get("provenance")),
                trigger_id=data.get("trigger_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "trigger record")


def _derive_trigger_id_from_core(trigger: ReplanTrigger) -> str:
    document = {
        "kind": trigger.kind,
        "contract_id": trigger.contract_id,
        "recorded_at": trigger.recorded_at,
        "evidence_refs": [r.to_dict() for r in trigger.evidence_refs],
        "realization_ref": trigger.realization_ref,
        "provenance": trigger.provenance.to_dict(),
    }
    return _derive_id(_TRIGGER_NAMESPACE, document, "trigger id document")


# ----------------------------------------------------------------------
# The realization snapshot (the execution state replan operates over)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RealizationSnapshot:
    """The typed, contract-attributable snapshot of ONE realization
    being replanned (the M008 execution-state view).

    The snapshot is a VIEW over a harvested or accepted execution
    surface (``surface`` names which one); it is DATA, never an
    authority (LOCK-117): the contract stays the sole authority, and
    the realization id is a content-derived reference.  ``state`` is
    the M008-owned explicit realization state vocabulary (frozen §9:
    REALIZING / DEGRADED / FAILED / SUPERSEDED — never a silent
    downgrade).  ``route_refs`` / ``artifact_refs`` cite the current
    route decision ids and execution-artifact references (plan ids,
    path ids — opaque data).
    """

    contract_id: str
    surface: str
    state: str
    observed_at: str
    session_ref: str = ""
    route_refs: Tuple[str, ...] = ()
    artifact_refs: Tuple[OpaqueReference, ...] = ()
    provenance: Provenance = field(
        default_factory=lambda: Provenance(issuer="replan:execution-state")
    )
    realization_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "snapshot.contract_id")
        )
        object.__setattr__(
            self, "surface", _require_in(self.surface, REALIZATION_SURFACES, "snapshot.surface")
        )
        object.__setattr__(
            self, "state", _require_in(self.state, REALIZATION_STATES, "snapshot.state")
        )
        object.__setattr__(
            self, "observed_at", _require_instant(self.observed_at, "snapshot.observed_at")
        )
        if self.session_ref:
            object.__setattr__(
                self,
                "session_ref",
                _require_str(
                    self.session_ref, "snapshot.session_ref", pattern=_REF_VALUE_PATTERN
                ),
            )
        route_refs = _require_tuple(self.route_refs, "snapshot.route_refs")
        normalized_routes = tuple(
            _require_str(ref, "snapshot.route_refs[%d]" % i, pattern=_REF_VALUE_PATTERN)
            for i, ref in enumerate(route_refs)
        )
        object.__setattr__(self, "route_refs", normalized_routes)
        object.__setattr__(
            self,
            "artifact_refs",
            _normalize_refs(self.artifact_refs, "snapshot.artifact_refs", "execution-artifact"),
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "snapshot.provenance")
        )
        expected = _derive_realization_id_from_core(self)
        if not self.realization_id:
            object.__setattr__(self, "realization_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.realization_id) is None:
                raise ReplanError(
                    ReplanReason.INVALID_INPUT,
                    "snapshot.realization_id must be the content-derived identity (sha256:...)",
                )
            if self.realization_id != expected:
                raise ReplanError(
                    ReplanReason.ID_MISMATCH,
                    "realization_id does not match the derived identity (tamper evidence)",
                )

    def is_terminal(self) -> bool:
        return self.state in REALIZATION_TERMINAL_STATES

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "contract_id": self.contract_id,
            "surface": self.surface,
            "state": self.state,
            "observed_at": self.observed_at,
            "route_refs": list(self.route_refs),
            "artifact_refs": [r.to_dict() for r in self.artifact_refs],
            "provenance": self.provenance.to_dict(),
            "realization_id": self.realization_id,
        }
        if self.session_ref:
            data["session_ref"] = self.session_ref
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RealizationSnapshot":
        if not isinstance(data, Mapping):
            raise ReplanError(ReplanReason.INVALID_INPUT, "snapshot must be a mapping")
        with _wrap_contract_error("snapshot deserialization"):
            return RealizationSnapshot(
                contract_id=data.get("contract_id"),
                surface=data.get("surface"),
                state=data.get("state"),
                observed_at=data.get("observed_at"),
                session_ref=data.get("session_ref") or "",
                route_refs=tuple(data.get("route_refs") or ()),
                artifact_refs=tuple(
                    OpaqueReference.from_dict(r) for r in data.get("artifact_refs") or ()
                ),
                provenance=Provenance.from_dict(data.get("provenance")),
                realization_id=data.get("realization_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "snapshot record")


def _derive_realization_id_from_core(snapshot: RealizationSnapshot) -> str:
    document = {
        "contract_id": snapshot.contract_id,
        "surface": snapshot.surface,
        "state": snapshot.state,
        "observed_at": snapshot.observed_at,
        "session_ref": snapshot.session_ref,
        "route_refs": list(snapshot.route_refs),
        "artifact_refs": [r.to_dict() for r in snapshot.artifact_refs],
        "provenance": snapshot.provenance.to_dict(),
    }
    return _derive_id(_SNAPSHOT_NAMESPACE, document, "realization id document")


# ----------------------------------------------------------------------
# The candidate realization (the alternative, as DATA)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ReplanCandidate:
    """One alternative realization considered by the engine, as DATA
    (LOCK-111: the strategy is replaceable; its proposal can never
    override the authority-true constraint set).

    ``hard_constraints`` is the constraint set the alternative CLAIMS
    to satisfy — optimizer-supplied DATA, re-validated against the
    contract's full hard-constraint set by the engine (LOCK-108: a
    candidate that weakens/drops ANY hard constraint is REJECTED with
    the typed ``replan-constraint-weakened`` reason).  There is no
    constraint-MUTATION power anywhere on this surface.  ``artifact_
    refs`` cite what the candidate proposes (an M006 plan reference, a
    WORK-011 path reference, an M007 offer-view resource reference —
    opaque ``execution-artifact`` data, LOCK-117).
    """

    kind: str
    contract_id: str
    hard_constraints: Tuple[HardConstraint, ...]
    artifact_refs: Tuple[OpaqueReference, ...]
    provenance: Provenance
    candidate_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _require_in(self.kind, CANDIDATE_KINDS, "candidate.kind"))
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "candidate.contract_id")
        )
        object.__setattr__(
            self,
            "hard_constraints",
            _normalize_constraints(self.hard_constraints, "candidate.hard_constraints"),
        )
        object.__setattr__(
            self,
            "artifact_refs",
            _normalize_refs(self.artifact_refs, "candidate.artifact_refs", "execution-artifact"),
        )
        if not self.artifact_refs:
            raise ReplanError(
                ReplanReason.CANDIDATE_INVALID,
                "candidate.artifact_refs requires at least one execution-artifact "
                "reference (what the alternative proposes)",
            )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "candidate.provenance")
        )
        expected = _derive_candidate_id_from_core(self)
        if not self.candidate_id:
            object.__setattr__(self, "candidate_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.candidate_id) is None:
                raise ReplanError(
                    ReplanReason.INVALID_INPUT,
                    "candidate.candidate_id must be the content-derived identity (sha256:...)",
                )
            if self.candidate_id != expected:
                raise ReplanError(
                    ReplanReason.ID_MISMATCH,
                    "candidate_id does not match the derived identity (tamper evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "contract_id": self.contract_id,
            "hard_constraints": [c.to_dict() for c in self.hard_constraints],
            "artifact_refs": [r.to_dict() for r in self.artifact_refs],
            "provenance": self.provenance.to_dict(),
            "candidate_id": self.candidate_id,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ReplanCandidate":
        if not isinstance(data, Mapping):
            raise ReplanError(ReplanReason.INVALID_INPUT, "candidate must be a mapping")
        with _wrap_contract_error("candidate deserialization"):
            return ReplanCandidate(
                kind=data.get("kind"),
                contract_id=data.get("contract_id"),
                hard_constraints=tuple(
                    HardConstraint.from_dict(c) for c in data.get("hard_constraints") or ()
                ),
                artifact_refs=tuple(
                    OpaqueReference.from_dict(r) for r in data.get("artifact_refs") or ()
                ),
                provenance=Provenance.from_dict(data.get("provenance")),
                candidate_id=data.get("candidate_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "candidate record")


def _derive_candidate_id_from_core(candidate: ReplanCandidate) -> str:
    document = {
        "kind": candidate.kind,
        "contract_id": candidate.contract_id,
        "hard_constraints": [c.to_dict() for c in candidate.hard_constraints],
        "artifact_refs": [r.to_dict() for r in candidate.artifact_refs],
        "provenance": candidate.provenance.to_dict(),
    }
    return _derive_id(_CANDIDATE_NAMESPACE, document, "candidate id document")


# ----------------------------------------------------------------------
# Per-candidate verdicts (typed, deterministic)
# ----------------------------------------------------------------------


#: The verdict recorded for an ACCEPTED candidate (the only non-error
#: code on a verdict; every rejection carries a frozen
#: ``ReplanReason`` code).
VERDICT_ACCEPTED = "replan-candidate-accepted"


@dataclass(frozen=True)
class CandidateVerdict:
    """The typed verdict for ONE considered candidate: accepted (the
    alternative satisfies the contract's full hard-constraint set
    verbatim) or rejected with a frozen reason code and a
    deterministic detail (LOCK-108 rejections cite the specific
    constraint kinds)."""

    candidate_id: str
    accepted: bool
    code: str
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_id", _require_id(self.candidate_id, "verdict.candidate_id")
        )
        if not isinstance(self.accepted, bool):
            raise ReplanError(
                ReplanReason.INVALID_INPUT, "verdict.accepted must be a boolean"
            )
        object.__setattr__(self, "code", _require_str(self.code, "verdict.code"))
        object.__setattr__(self, "detail", _require_str(self.detail, "verdict.detail"))
        if self.accepted and self.code != VERDICT_ACCEPTED:
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "an accepted verdict must carry the %s code (found %s)"
                % (VERDICT_ACCEPTED, self.code),
            )
        if not self.accepted and self.code not in ReplanReason.values():
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "a rejected verdict must carry a frozen replan reason code (found %s)"
                % self.code,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "accepted": self.accepted,
            "code": self.code,
            "detail": self.detail,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "verdict record")

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "CandidateVerdict":
        if not isinstance(data, Mapping):
            raise ReplanError(ReplanReason.INVALID_INPUT, "verdict must be a mapping")
        return CandidateVerdict(
            candidate_id=data.get("candidate_id"),
            accepted=data.get("accepted"),
            code=data.get("code"),
            detail=data.get("detail"),
        )


# ----------------------------------------------------------------------
# The renegotiation notice (the explicit renegotiation trigger)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RenegotiationNotice:
    """The typed EXPLICIT contract-renegotiation trigger (frozen 1.1
    §9: a realization that cannot satisfy the hard constraints either
    enters an explicit degraded/failed state or triggers explicit
    contract renegotiation — never a silent downgrade).

    The notice cites the contract to supersede; the successor contract
    is created through the accepted M002 ``superseded-contract``
    reference path by the principal-side flow (the replan domain never
    creates contracts — contracts/ stays the sole authority,
    LOCK-101).  The notice itself is DATA: a deterministic,
    content-derived record the renegotiation flow consumes.
    """

    superseded_contract_id: str
    trigger_id: str
    recorded_at: str
    reason: str
    notice_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "superseded_contract_id",
            _require_id(self.superseded_contract_id, "notice.superseded_contract_id"),
        )
        object.__setattr__(
            self, "trigger_id", _require_id(self.trigger_id, "notice.trigger_id")
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "notice.recorded_at")
        )
        object.__setattr__(
            self, "reason", _require_str(self.reason, "notice.reason", pattern=_REF_VALUE_PATTERN)
        )
        expected = _derive_notice_id_from_core(self)
        if not self.notice_id:
            object.__setattr__(self, "notice_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.notice_id) is None:
                raise ReplanError(
                    ReplanReason.INVALID_INPUT,
                    "notice.notice_id must be the content-derived identity (sha256:...)",
                )
            if self.notice_id != expected:
                raise ReplanError(
                    ReplanReason.ID_MISMATCH,
                    "notice_id does not match the derived identity (tamper evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "superseded_contract_id": self.superseded_contract_id,
            "trigger_id": self.trigger_id,
            "recorded_at": self.recorded_at,
            "reason": self.reason,
            "notice_id": self.notice_id,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RenegotiationNotice":
        if not isinstance(data, Mapping):
            raise ReplanError(ReplanReason.INVALID_INPUT, "notice must be a mapping")
        return RenegotiationNotice(
            superseded_contract_id=data.get("superseded_contract_id"),
            trigger_id=data.get("trigger_id"),
            recorded_at=data.get("recorded_at"),
            reason=data.get("reason"),
            notice_id=data.get("notice_id") or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "notice record")


def _derive_notice_id_from_core(notice: RenegotiationNotice) -> str:
    document = {
        "superseded_contract_id": notice.superseded_contract_id,
        "trigger_id": notice.trigger_id,
        "recorded_at": notice.recorded_at,
        "reason": notice.reason,
    }
    return _derive_id(_NOTICE_NAMESPACE, document, "notice id document")


# ----------------------------------------------------------------------
# The replan decision (the typed closed-loop record)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ReplanDecision:
    """The typed, deterministic replan decision record.

    Field set: the content-derived decision identity; the trigger id
    (what failed); the owning contract identity (attribution); the
    decision kind (adopt-alternative / degraded / failed /
    renegotiate); the resulting realization state (the M008-owned
    explicit vocabulary — the state the REPLACED realization enters);
    the contract's hard-constraint set RE-VALIDATED (preserved
    verbatim, with the contract's own LOCK-108 fingerprint — same
    inputs always produce the byte-identical record); every candidate
    considered with its typed verdict (deterministic order); the
    adopted candidate (when the decision adopts); the provenance
    referencing the contract + the realization being replaced; and
    the explicit renegotiation notice (when the realization cannot
    satisfy the hard constraints and renegotiation is triggered).

    The decision is an EXECUTION-SIDE record, never a contract
    authority (LOCK-101/LOCK-117): its effects enter the contract
    only through the contract's own frozen command vocabulary (the
    ``replan.bridge`` recording path — BindExecutionArtifact /
    RecordAssurance, consumed, never extended).
    """

    trigger_id: str
    contract_id: str
    decision: str
    realization_state: str
    recorded_at: str
    hard_constraints: Tuple[HardConstraint, ...]
    constraint_fingerprint: str
    verdicts: Tuple[CandidateVerdict, ...]
    provenance: Provenance
    tie_break: Tuple[str, ...] = DEFAULT_TIE_BREAK
    adopted_candidate_id: str = ""
    adopted_artifacts: Tuple[OpaqueReference, ...] = ()
    replaces: Tuple[str, ...] = ()
    renegotiation: Optional[RenegotiationNotice] = None
    decision_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger_id", _require_id(self.trigger_id, "decision.trigger_id"))
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "decision.contract_id")
        )
        object.__setattr__(
            self, "decision", _require_in(self.decision, DECISION_KINDS, "decision.decision")
        )
        object.__setattr__(
            self,
            "realization_state",
            _require_in(self.realization_state, REALIZATION_STATES, "decision.realization_state"),
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "decision.recorded_at")
        )
        object.__setattr__(
            self,
            "hard_constraints",
            _normalize_constraints(self.hard_constraints, "decision.hard_constraints"),
        )
        object.__setattr__(
            self, "constraint_fingerprint", _require_id(self.constraint_fingerprint, "decision.constraint_fingerprint")
        )
        # tamper evidence: the carried constraint set must match the
        # carried LOCK-108 fingerprint (dropped, relaxed, re-interpreted
        # or reordered material fails closed)
        if _constraints_fingerprint(self.hard_constraints) != self.constraint_fingerprint:
            raise ReplanError(
                ReplanReason.CONSTRAINT_MISMATCH,
                "the decision's LOCK-108 constraint fingerprint does not match the "
                "constraint set it carries (dropped, relaxed, re-interpreted or "
                "reordered constraints fail closed)",
            )
        verdicts = _require_tuple(self.verdicts, "decision.verdicts")
        normalized_verdicts = tuple(
            item if isinstance(item, CandidateVerdict) else CandidateVerdict.from_dict(item)
            for item in verdicts
        )
        object.__setattr__(self, "verdicts", normalized_verdicts)
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "decision.provenance")
        )
        object.__setattr__(
            self,
            "tie_break",
            _normalize_tie_break(self.tie_break, "decision.tie_break"),
        )
        if self.adopted_candidate_id:
            object.__setattr__(
                self,
                "adopted_candidate_id",
                _require_id(self.adopted_candidate_id, "decision.adopted_candidate_id"),
            )
        object.__setattr__(
            self,
            "adopted_artifacts",
            _normalize_refs(
                self.adopted_artifacts, "decision.adopted_artifacts", "execution-artifact"
            ),
        )
        replaces = _require_tuple(self.replaces, "decision.replaces")
        object.__setattr__(
            self,
            "replaces",
            tuple(
                _require_str(ref, "decision.replaces[%d]" % i, pattern=_REF_VALUE_PATTERN)
                for i, ref in enumerate(replaces)
            ),
        )
        if self.renegotiation is not None and not isinstance(self.renegotiation, RenegotiationNotice):
            raise ReplanError(
                ReplanReason.INVALID_INPUT,
                "decision.renegotiation must be a RenegotiationNotice record",
            )
        # decision-kind consistency (fail closed):
        if self.decision == "adopt-alternative":
            if not self.adopted_candidate_id:
                raise ReplanError(
                    ReplanReason.INVALID_INPUT,
                    "an adopt-alternative decision must carry the adopted candidate id",
                )
            if not any(
                v.candidate_id == self.adopted_candidate_id and v.accepted
                for v in self.verdicts
            ):
                raise ReplanError(
                    ReplanReason.VOCABULARY,
                    "the adopted candidate must be an accepted verdict on this decision",
                )
            if self.realization_state != "SUPERSEDED":
                raise ReplanError(
                    ReplanReason.VOCABULARY,
                    "an adopt-alternative decision supersedes the replaced realization",
                )
        else:
            if self.adopted_candidate_id or self.adopted_artifacts:
                raise ReplanError(
                    ReplanReason.VOCABULARY,
                    "only an adopt-alternative decision may carry an adopted candidate",
                )
            if self.decision == "degraded" and self.realization_state != "DEGRADED":
                raise ReplanError(
                    ReplanReason.VOCABULARY,
                    "a degraded decision enters the explicit DEGRADED realization state",
                )
            if self.decision in ("failed", "renegotiate") and self.realization_state != "FAILED":
                raise ReplanError(
                    ReplanReason.VOCABULARY,
                    "a %s decision enters the explicit FAILED realization state" % self.decision,
                )
        if self.decision in ("failed", "renegotiate") and self.renegotiation is None:
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "a %s decision carries the explicit renegotiation notice "
                "(the renegotiation trigger path — never a silent downgrade)" % self.decision,
            )
        if self.decision in ("adopt-alternative", "degraded") and self.renegotiation is not None:
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "a %s decision does not trigger renegotiation" % self.decision,
            )
        expected = _derive_decision_id_from_core(self)
        if not self.decision_id:
            object.__setattr__(self, "decision_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.decision_id) is None:
                raise ReplanError(
                    ReplanReason.INVALID_INPUT,
                    "decision.decision_id must be the content-derived identity (sha256:...)",
                )
            if self.decision_id != expected:
                raise ReplanError(
                    ReplanReason.ID_MISMATCH,
                    "decision_id does not match the derived identity (tamper evidence)",
                )

    def is_terminal(self) -> bool:
        """A decision record is terminal (immutable evidence) once
        made — replan decisions are never re-decided in place; a
        later trigger produces a NEW decision record."""
        return True

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "trigger_id": self.trigger_id,
            "contract_id": self.contract_id,
            "decision": self.decision,
            "realization_state": self.realization_state,
            "recorded_at": self.recorded_at,
            "hard_constraints": [c.to_dict() for c in self.hard_constraints],
            "constraint_fingerprint": self.constraint_fingerprint,
            "verdicts": [v.to_dict() for v in self.verdicts],
            "provenance": self.provenance.to_dict(),
            "tie_break": list(self.tie_break),
            "replaces": list(self.replaces),
            "decision_id": self.decision_id,
        }
        if self.adopted_candidate_id:
            data["adopted_candidate_id"] = self.adopted_candidate_id
        if self.adopted_artifacts:
            data["adopted_artifacts"] = [r.to_dict() for r in self.adopted_artifacts]
        if self.renegotiation is not None:
            data["renegotiation"] = self.renegotiation.to_dict()
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ReplanDecision":
        if not isinstance(data, Mapping):
            raise ReplanError(ReplanReason.INVALID_INPUT, "decision must be a mapping")
        renegotiation = data.get("renegotiation")
        with _wrap_contract_error("decision deserialization"):
            return ReplanDecision(
                trigger_id=data.get("trigger_id"),
                contract_id=data.get("contract_id"),
                decision=data.get("decision"),
                realization_state=data.get("realization_state"),
                recorded_at=data.get("recorded_at"),
                hard_constraints=tuple(
                    HardConstraint.from_dict(c) for c in data.get("hard_constraints") or ()
                ),
                constraint_fingerprint=data.get("constraint_fingerprint"),
                verdicts=tuple(
                    CandidateVerdict.from_dict(v) for v in data.get("verdicts") or ()
                ),
                provenance=Provenance.from_dict(data.get("provenance")),
                tie_break=tuple(data.get("tie_break") or DEFAULT_TIE_BREAK),
                adopted_candidate_id=data.get("adopted_candidate_id") or "",
                adopted_artifacts=tuple(
                    OpaqueReference.from_dict(r) for r in data.get("adopted_artifacts") or ()
                ),
                replaces=tuple(data.get("replaces") or ()),
                renegotiation=(
                    RenegotiationNotice.from_dict(renegotiation)
                    if renegotiation is not None
                    else None
                ),
                decision_id=data.get("decision_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "decision record")


def _derive_decision_id_from_core(decision: ReplanDecision) -> str:
    document = {
        "trigger_id": decision.trigger_id,
        "contract_id": decision.contract_id,
        "decision": decision.decision,
        "realization_state": decision.realization_state,
        "recorded_at": decision.recorded_at,
        "hard_constraints": [c.to_dict() for c in decision.hard_constraints],
        "constraint_fingerprint": decision.constraint_fingerprint,
        "verdicts": [v.to_dict() for v in decision.verdicts],
        "provenance": decision.provenance.to_dict(),
        "tie_break": list(decision.tie_break),
        "adopted_candidate_id": decision.adopted_candidate_id,
        "adopted_artifacts": [r.to_dict() for r in decision.adopted_artifacts],
        "replaces": list(decision.replaces),
        "renegotiation": (
            decision.renegotiation.to_dict() if decision.renegotiation is not None else None
        ),
    }
    return _derive_id(_DECISION_NAMESPACE, document, "decision id document")


# ----------------------------------------------------------------------
# The typed reconnect record (the WORK-012 discipline, preserved)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ReconnectRecord:
    """One explicit session reconnect event as typed replan evidence
    (the harvested WORK-012 discipline: a route change is ALWAYS an
    explicit lifecycle event recording the old AND the new route
    references — never a silent replacement).

    Constructed from the session store's own event history by
    ``replan.execution_state.reconnect_history``; fail-closed on any
    reconnect event missing either side of the route change
    (``replan-silent-replacement``).
    """

    session_id: str
    event_id: str
    reconnect_instant: str
    old_route_decision_id: str
    new_route_decision_id: str
    old_path_id: str
    new_path_id: str
    new_path_expires_at: str = ""
    reconnect_id: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("session_id", self.session_id),
            ("event_id", self.event_id),
        ):
            object.__setattr__(
                self, label, _require_str(value, "reconnect.%s" % label, pattern=_REF_VALUE_PATTERN)
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
            ("new_path_expires_at", self.new_path_expires_at),
        )
        missing = [label for label, value in route_members if not isinstance(value, str) or not value]
        if missing:
            raise ReplanError(
                ReplanReason.SILENT_REPLACEMENT,
                "the reconnect record is missing the route-change members %s "
                "(the WORK-012 discipline requires BOTH the old AND the new "
                "route references on every reconnect — a route change is "
                "never a silent replacement)" % ", ".join(sorted(missing)),
            )
        for label, value in route_members[:4]:
            object.__setattr__(
                self,
                label,
                _require_str(value, "reconnect.%s" % label, pattern=_REF_VALUE_PATTERN),
            )
        object.__setattr__(
            self,
            "new_path_expires_at",
            _require_instant(self.new_path_expires_at, "reconnect.new_path_expires_at"),
        )
        expected = _derive_reconnect_id_from_core(self)
        if not self.reconnect_id:
            object.__setattr__(self, "reconnect_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.reconnect_id) is None:
                raise ReplanError(
                    ReplanReason.INVALID_INPUT,
                    "reconnect.reconnect_id must be the content-derived identity (sha256:...)",
                )
            if self.reconnect_id != expected:
                raise ReplanError(
                    ReplanReason.ID_MISMATCH,
                    "reconnect_id does not match the derived identity (tamper evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "event_id": self.event_id,
            "reconnect_instant": self.reconnect_instant,
            "old_route_decision_id": self.old_route_decision_id,
            "new_route_decision_id": self.new_route_decision_id,
            "old_path_id": self.old_path_id,
            "new_path_id": self.new_path_id,
            "new_path_expires_at": self.new_path_expires_at,
            "reconnect_id": self.reconnect_id,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ReconnectRecord":
        if not isinstance(data, Mapping):
            raise ReplanError(ReplanReason.INVALID_INPUT, "reconnect must be a mapping")
        return ReconnectRecord(
            session_id=data.get("session_id"),
            event_id=data.get("event_id"),
            reconnect_instant=data.get("reconnect_instant"),
            old_route_decision_id=data.get("old_route_decision_id"),
            new_route_decision_id=data.get("new_route_decision_id"),
            old_path_id=data.get("old_path_id"),
            new_path_id=data.get("new_path_id"),
            new_path_expires_at=data.get("new_path_expires_at") or "",
            reconnect_id=data.get("reconnect_id") or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "reconnect record")


def _derive_reconnect_id_from_core(record: ReconnectRecord) -> str:
    document = {
        "session_id": record.session_id,
        "event_id": record.event_id,
        "reconnect_instant": record.reconnect_instant,
        "old_route_decision_id": record.old_route_decision_id,
        "new_route_decision_id": record.new_route_decision_id,
        "old_path_id": record.old_path_id,
        "new_path_id": record.new_path_id,
        "new_path_expires_at": record.new_path_expires_at,
    }
    return _derive_id(_RECONNECT_NAMESPACE, document, "reconnect id document")


# ----------------------------------------------------------------------
# The pure realization-state kernel (identity- and constraint-
# preserving by construction)
# ----------------------------------------------------------------------


def check_realization_transition(current: str, target: str) -> None:
    """Fail closed unless current -> target is a legal realization
    transition (the M008-owned explicit-state vocabulary)."""
    if current in REALIZATION_TERMINAL_STATES:
        raise ReplanError(
            ReplanReason.REALIZATION_TERMINAL,
            "realization is terminal in %s; terminal realizations never transition" % current,
        )
    legal = REALIZATION_TRANSITIONS.get(current, ())
    if target not in legal:
        raise ReplanError(
            ReplanReason.VOCABULARY,
            "transition %s -> %s is not legal (legal: %s)"
            % (current, target, ", ".join(legal) or "none"),
        )


def apply_realization_transition(
    snapshot: RealizationSnapshot, target: str
) -> RealizationSnapshot:
    """Pure transition kernel: apply one realization-state transition.

    Returns the successor snapshot (identity material, attribution,
    routes and artifacts preserved; only the state and the
    content-derived snapshot id evolve — a snapshot id is an
    observation, not an identity).  Raises ReplanError on any illegal
    transition.  Constraint sets never ride on snapshots (LOCK-108
    lives on the contract and the decision records, not on
    execution-state views).
    """
    if not isinstance(snapshot, RealizationSnapshot):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "apply_realization_transition requires a RealizationSnapshot",
        )
    check_realization_transition(snapshot.state, target)
    return RealizationSnapshot(
        contract_id=snapshot.contract_id,
        surface=snapshot.surface,
        state=target,
        observed_at=snapshot.observed_at,
        session_ref=snapshot.session_ref,
        route_refs=snapshot.route_refs,
        artifact_refs=snapshot.artifact_refs,
        provenance=snapshot.provenance,
    )


# ----------------------------------------------------------------------
# Import-time vocabulary consistency (fail loud on drift)
# ----------------------------------------------------------------------


def _check_vocabularies() -> None:
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
        raise ReplanError(
            ReplanReason.VOCABULARY,
            "the consumed contracts constraint-kind vocabulary has drifted from "
            "the frozen 12-kind set this domain was built against",
        )
    if REALIZATION_STATES != ("REALIZING", "DEGRADED", "FAILED", "SUPERSEDED"):
        raise ReplanError(
            ReplanReason.VOCABULARY,
            "the M008 realization-state vocabulary has drifted",
        )
    if TIE_BREAK_KEYS[-1] != "candidate-id":
        raise ReplanError(
            ReplanReason.TIE_BREAK_INVALID,
            "the tie-break key vocabulary must guarantee the candidate-id total order",
        )


_check_vocabularies()
