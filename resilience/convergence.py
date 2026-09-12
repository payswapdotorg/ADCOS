"""ADCOS resilience convergence (M019 — Resilience Convergence and
Scale Hardening).

The R8 convergence surface of the R8 charter M019 scope (R8-CORE-001,
DEC-0114; the convergence child — every accepted R8 child authority is
the composition substrate), living in the M015-owned shared prefix
``resilience/``:

- **The end-to-end resilience drill** (:func:`run_fault_phase` +
  :func:`assemble_convergence_drill`): the deterministic fault
  injection across the full accepted surface — fault -> detect ->
  replan/failover -> recover -> reconcile — with EVERY hard constraint
  preserved at each step (LOCK-108: the contract's own
  ``hard_constraint_fingerprint`` re-verified at every phase boundary;
  the constraint validation itself happens inside the CONSUMED M008
  kernel, never here) and every transition evidence-visible (LOCK-106
  records consumed by reference from the accepted ``evidence/``
  typing).  The drill is a deterministic, replayable operation
  sequence: injected instants only, no wall clock, no randomness.

- **The converged-domain compatibility matrix over the R8 domains**
  (:class:`ConvergenceDomainVersion`, :func:`classify_convergence_domain`,
  :func:`negotiate_r8_matrix`, :func:`compose_convergence_matrix`): the
  accepted ``upgrade/`` matrix discipline (the ``upgrade.convergence``
  surface) extended onto the R8 domain labels — the additive-evolution
  ``MAJOR.MINOR`` grammar, the frozen verdict vocabulary, sorted
  domain iteration, input-order independence and byte-stable digests.
  The R7-substrate rows ride on the COMPOSED matrix as the accepted
  engine's own serialized verdicts (DATA, consumed by reference at
  runtime); the battery pins the vocabulary equality with the accepted
  ``DOMAIN_COMPATIBILITY_VERDICTS`` (the drift guard).

- **Federation-scale convergence over the R8 domains**
  (:class:`FederationScaleBounds`,
  :func:`verify_federation_scale_convergence`): the accepted
  ``scale/`` harness discipline extended — the R8 convergence
  scenarios (driven by the battery, the composition root, through the
  accepted ``scale.convergence`` harness and the accepted
  ``federation.convergence`` citation constructors over the REAL R8
  drill material) verified against DECLARED deterministic bounds: the
  planned citation admissions, the topology-predicted propagation
  round counts, and the byte-identical replay.

The composition boundary (the M014 discipline, mechanically adapted to
this prefix's frozen import boundary — the accepted batteries audit
every file under ``resilience/`` to the sanctioned import set):

    THIS MODULE
        imports DIRECTLY (by reference): the accepted authorities at
        or below this package in the one-way dependency DAG —
        ``contracts/`` (the canonical authority), ``replan/`` (the
        M008 kernel records), ``executionplans/`` (the M006 plans),
        ``evidence/`` (the LOCK-106 typed records + store) — plus
        ``protocol/`` and this package's own M015 runtime.
        composes AT RUNTIME (duck-typed, the accepted records' OWN
        public surfaces — exactly the ``federation.convergence``
        cite_* discipline for the child authorities it cannot import
        without cycles): ``localfirst/`` (the M016 authority views and
        the offline journal state), ``recovery/`` (the M017 drill
        result and its reconciliation), ``upgrade/`` (the accepted
        matrix's serialized verdicts) and ``scale/`` (the accepted
        harness run result).  The accepted objects' own code runs and
        their own gates fire on every consumed value — nothing is
        reimplemented, weakened, forked, or bypassed; the battery (the
        M019-owned ``tools/scale_selftest.py`` evolution, where the
        import audit does not apply) is the composition root that
        wires the accepted M016/M017/upgrade/scale engines into this
        surface.

LOCK-117: nothing here becomes a second contract authority — the
runtime session, the drill records, the matrix rows and the scale
reports ride the contract and the accepted planes as opaque
references.  LOCK-119: injected instants only; content-derived ids
over canonical JSON; no wall clock, no randomness, no network, no
secrets (secret-shaped material is rejected typed at every
construction boundary).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import ConnectivityContract, Provenance

from replan import TIE_BREAK_KEYS

from executionplans import ExecutionPlan

from evidence import AttestationEvidence, EvidenceStore, ObservationEvidence

from resilience.errors import ResilienceError, ResilienceReason
from resilience.runtime import DriveResult, RuntimeStore
from resilience.failover import orchestrate_failover

__all__ = [
    # frozen vocabularies
    "CONVERGENCE_ISSUER",
    "R8_CONVERGENCE_DOMAINS",
    "MATRIX_VERDICTS",
    "FAULT_KINDS",
    "DRILL_PHASES",
    "DRILL_OUTCOMES",
    "FAULT_OBSERVATION_VALUE",
    "FAILOVER_ATTESTATION_ADOPTED",
    "FAILOVER_ATTESTATION_NOT_ADOPTED",
    # typed records — the drill
    "ConvergenceDrillPlan",
    "FaultRecord",
    "FaultPhaseResult",
    "OfflinePhaseRecord",
    "RecoveryPhaseRecord",
    "ConvergenceDrillResult",
    # typed records — the matrix
    "ConvergenceDomainVersion",
    "ConvergenceDomainVerdict",
    "R8MatrixReport",
    "ConvergenceMatrixReport",
    # typed records — the federation-scale surface
    "FederationScaleBounds",
    "FederationScaleConvergence",
    # the drill engines
    "run_fault_phase",
    "assemble_convergence_drill",
    # the duck-typed composition helpers (the accepted surfaces' own values)
    "offline_phase_record",
    "recovery_phase_record",
    # the matrix engines
    "classify_convergence_domain",
    "negotiate_r8_matrix",
    "compose_convergence_matrix",
    # the federation-scale verifier
    "verify_federation_scale_convergence",
]


#: The issuer recorded on convergence-surface provenance (LOCK-118: the
#: convergence surface asserts its own records; the contract stays the
#: sole authority).
CONVERGENCE_ISSUER = "resilience:convergence"

#: The accepted R8 chain-child domain labels entering the converged
#: compatibility matrix (the M019 extension set — sorted; the accepted
#: M015/M016/M017 domains).  ``credentials`` (M018) is deliberately
#: NOT a member: it is chain-independent and IN FLIGHT at this head —
#: the convergence surface never claims an unaccepted child, and the
#: R7-substrate labels stay owned by the accepted ``upgrade/`` matrix
#: (they enter the composed matrix as that engine's own verdict DATA,
#: never re-declared here).
R8_CONVERGENCE_DOMAINS: Tuple[str, ...] = (
    "localfirst",
    "recovery",
    "resilience",
)

#: The frozen domain-compatibility verdict vocabulary — the accepted
#: ``upgrade.convergence.DOMAIN_COMPATIBILITY_VERDICTS`` discipline's
#: values, extended onto the R8 labels (the battery pins the equality
#: with the accepted set; the fail-closed drift guard lives there
#: because this prefix's frozen import boundary forbids importing the
#: ``upgrade/`` package — the vocabulary values are identical by
#: construction and verified by reference in the battery).
MATRIX_VERDICTS: Tuple[str, ...] = (
    "additive-gap",
    "compatible",
    "local-missing",
    "major-mismatch",
    "peer-missing",
    "unknown-domain",
)

#: The deterministic fault-injection vocabulary of the end-to-end
#: drill (each fault kind projects onto an accepted
#: :data:`resilience.failover.FAILOVER_TRIGGER_KINDS` trigger through
#: the accepted frozen map — never a second trigger model).
FAULT_KINDS: Tuple[str, ...] = ("path-failure",)

#: The end-to-end drill's phase vocabulary (the deterministic
#: replayable operation sequence — every phase's instant is injected
#: on the drill plan):
#:
#: - ``fault`` — the deterministic fault injection (the realization is
#:   lost; the fault record names the realization being lost);
#: - ``detect`` — the LOCK-106 observation of the fault (the evidence
#:   plane sees the failure);
#: - ``replan-failover`` — the accepted M015 failover drive (the
#:   consumed M008 kernel validates every alternative against the
#:   contract's full hard-constraint set — LOCK-108; the adopted
#:   realization lands through the explicit reconnect pair);
#: - ``offline-operation`` — the accepted M016 offline boundary (the
#:   authority-view sync, the journaled partition, the local
#:   admissions — driven by the composition root);
#: - ``recover`` — the accepted M017 disaster cycle (the recovery
#:   points, the induced losses, the restores, the verifications);
#: - ``reconcile`` — the accepted M017 cross-plane reconciliation
#:   (the M016 resynchronization drive + the converged planes).
DRILL_PHASES: Tuple[str, ...] = (
    "fault",
    "detect",
    "replan-failover",
    "offline-operation",
    "recover",
    "reconcile",
)

#: The end-to-end drill's outcome vocabulary: the drill outcome mirrors
#: the consumed M017 reconciliation outcome verbatim (``converged``, or
#: ``divergence-disclosed`` — the disclosed divergences ride on the
#: consumed reconciliation record; this surface never absorbs them).
DRILL_OUTCOMES: Tuple[str, ...] = ("converged", "divergence-disclosed")

#: The drill's LOCK-106 observation value for the injected fault (the
#: frozen WORK-016 health-state ordinal: 3 = NOT_RUNNING — the
#: realization is lost, the same frozen metric/value class the accepted
#: M017 drill uses for its plane-loss observations).
FAULT_OBSERVATION_VALUE = 3

#: The drill's LOCK-106 attestation value for an adopted failover (the
#: runtime landed ACTIVE on the adopted alternative through the
#: explicit reconnect pair).
FAILOVER_ATTESTATION_ADOPTED = 1

#: The drill's LOCK-106 attestation value for a non-adopted failover
#: outcome (degraded / failed / renegotiate — the honest disclosed
#: outcome, never a silent downgrade).
FAILOVER_ATTESTATION_NOT_ADOPTED = 0


# ----------------------------------------------------------------------
# Internal helpers (the accepted-domain conventions, re-used)
# ----------------------------------------------------------------------

_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CITATION_ID_PATTERN = re.compile(r"^m014:cite:sha256:[0-9a-f]{64}$")
_RUN_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")

_DRILL_NAMESPACE = "adc-os-resilience-convergence-drill"
_FAULT_NAMESPACE = "adc-os-resilience-convergence-fault"
_MATRIX_NAMESPACE = "adc-os-resilience-convergence-matrix"
_SCALE_NAMESPACE = "adc-os-resilience-convergence-scale"


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
    """LOCK-119 guard: secret-shaped material never enters convergence data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise ResilienceError(
            ResilienceReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter convergence "
            "data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise ResilienceError(
            ResilienceReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter convergence "
            "data" % label,
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


def _require_int(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "%s must be an integer >= %d (found %r)" % (label, minimum, value),
        )
    return value


def _require_provenance(value: object, label: str) -> Provenance:
    if not isinstance(value, Provenance):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "%s must be a Provenance record" % label
        )
    return value


def _duck_surface(record: object, names: Sequence[str], label: str) -> None:
    """The duck-typed composition gate (the M014
    ``federation.convergence`` cite-* discipline): a consumed accepted
    record must expose its OWN public surface (every named member,
    readable) — the accepted record's own code produced these values;
    this surface only reads them.  A record missing the surface fails
    closed typed (never a silent partial consumption)."""
    if record is None:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "%s requires the accepted record (got None) — the convergence "
            "surface composes the accepted surfaces by reference" % label,
        )
    for name in names:
        if not hasattr(record, name):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "%s does not expose %r — the convergence surface composes "
                "only the accepted record's own public surface (the "
                "duck-typed by-reference discipline; got %s)"
                % (label, name, type(record).__name__),
            )


# ----------------------------------------------------------------------
# The convergence drill plan (the deterministic operation sequence)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ConvergenceDrillPlan:
    """The deterministic, replayable end-to-end convergence drill plan
    (the M019-owned phase material; the offline and recovery phases'
    own accepted plans carry their instants — the composition root
    sequences them after this plan's phases).

    ``fault_kind`` is the deterministic fault injected at ``fault_at``
    (projects onto the accepted failover trigger vocabulary).
    ``detect_at`` / ``failover_at`` / ``offline_at`` are the injected
    phase instants, NON-DECREASING in phase order (the deterministic
    sequence; the evidence windows use the next phase's instant as
    their horizon — the accepted M017 drill's deterministic-window
    discipline, never wall clock).  ``resolution_rule`` is the DECLARED
    conflict-resolution rule for the reconciliation drive (the LOCK-111
    class, over the consumed M008 key vocabulary).  ``drill_id`` is
    content-derived over the full core (tamper-evident).
    """

    contract_id: str
    runtime_id: str
    fault_kind: str
    fault_at: str
    detect_at: str
    failover_at: str
    offline_at: str
    resolution_rule: Tuple[str, ...]
    provenance: Provenance
    drill_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "drill.contract_id")
        )
        object.__setattr__(
            self, "runtime_id", _require_id(self.runtime_id, "drill.runtime_id")
        )
        object.__setattr__(
            self, "fault_kind", _require_in(self.fault_kind, FAULT_KINDS, "drill.fault_kind")
        )
        for label, value in (
            ("fault_at", self.fault_at),
            ("detect_at", self.detect_at),
            ("failover_at", self.failover_at),
            ("offline_at", self.offline_at),
        ):
            object.__setattr__(self, label, _require_instant(value, "drill.%s" % label))
        if not (
            parse_instant(self.fault_at)
            <= parse_instant(self.detect_at)
            <= parse_instant(self.failover_at)
            <= parse_instant(self.offline_at)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the convergence drill's phase instants must be non-decreasing "
                "in phase order (fault %s -> detect %s -> failover %s -> "
                "offline %s) — the drill is a deterministic replayable "
                "operation sequence" % (
                    self.fault_at, self.detect_at, self.failover_at, self.offline_at,
                ),
            )
        object.__setattr__(
            self,
            "resolution_rule",
            _normalize_resolution_rule(self.resolution_rule),
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "drill.provenance")
        )
        expected = _derive_drill_id_from_core(self)
        if not self.drill_id:
            object.__setattr__(self, "drill_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.drill_id) is None:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "drill.drill_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.drill_id != expected:
                raise ResilienceError(
                    ResilienceReason.ID_MISMATCH,
                    "drill_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "fault_kind": self.fault_kind,
            "fault_at": self.fault_at,
            "detect_at": self.detect_at,
            "failover_at": self.failover_at,
            "offline_at": self.offline_at,
            "resolution_rule": list(self.resolution_rule),
            "provenance": self.provenance.to_dict(),
            "drill_id": self.drill_id,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ConvergenceDrillPlan":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "the drill plan must be a mapping"
            )
        return ConvergenceDrillPlan(
            contract_id=data.get("contract_id"),
            runtime_id=data.get("runtime_id"),
            fault_kind=data.get("fault_kind"),
            fault_at=data.get("fault_at"),
            detect_at=data.get("detect_at"),
            failover_at=data.get("failover_at"),
            offline_at=data.get("offline_at"),
            resolution_rule=tuple(data.get("resolution_rule") or ()),
            provenance=Provenance.from_dict(data.get("provenance")),
            drill_id=data.get("drill_id") or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the drill plan record")


def _derive_drill_id_from_core(plan: ConvergenceDrillPlan) -> str:
    document = {
        "contract_id": plan.contract_id,
        "runtime_id": plan.runtime_id,
        "fault_kind": plan.fault_kind,
        "fault_at": plan.fault_at,
        "detect_at": plan.detect_at,
        "failover_at": plan.failover_at,
        "offline_at": plan.offline_at,
        "resolution_rule": list(plan.resolution_rule),
        "provenance": plan.provenance.to_dict(),
    }
    return _derive_id(_DRILL_NAMESPACE, document, "the drill id document")


def _normalize_resolution_rule(rule: object) -> Tuple[str, ...]:
    """Validate the DECLARED conflict-resolution rule (the LOCK-111
    class) against the CONSUMED M008 key vocabulary (the same
    convention as :func:`resilience.model._normalize_tie_break` — the
    rule must end with the ``candidate-id`` total-order key)."""
    if isinstance(rule, (str, bytes)) or not isinstance(rule, (tuple, list)):
        raise ResilienceError(
            ResilienceReason.TIE_BREAK_INVALID,
            "the resolution rule must be a sequence of content keys",
        )
    items = tuple(rule)
    if not items:
        raise ResilienceError(
            ResilienceReason.TIE_BREAK_INVALID,
            "the resolution rule requires at least one entry",
        )
    for i, item in enumerate(items):
        if item not in TIE_BREAK_KEYS:
            raise ResilienceError(
                ResilienceReason.TIE_BREAK_INVALID,
                "the resolution rule[%d] must be one of %s (found %r) — the "
                "consumed M008 content-key vocabulary only, never temporal "
                "(the LOCK-111 class)" % (i, ", ".join(TIE_BREAK_KEYS), item),
            )
    if len(set(items)) != len(items):
        raise ResilienceError(
            ResilienceReason.TIE_BREAK_INVALID,
            "the resolution rule must not repeat a key",
        )
    if items[-1] != "candidate-id":
        raise ResilienceError(
            ResilienceReason.TIE_BREAK_INVALID,
            "the resolution rule must end with the candidate-id key (the "
            "total-order guarantee; the LOCK-111 class)",
        )
    return items


# ----------------------------------------------------------------------
# The fault record (the deterministic fault injection, typed)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class FaultRecord:
    """One deterministic fault injection (the drill's ``fault`` phase):
    the runtime session's CURRENT realization is lost.

    The fault record names the realization being lost VERBATIM (the
    current route decision id and path id — the WORK-012 member shape;
    the loss is explicit, never a silent replacement) and carries the
    fault kind (the frozen :data:`FAULT_KINDS` vocabulary).  The
    record carries NO constraint material (LOCK-108 is structural
    here: the fault never interprets the contract's constraints); the
    contract's own LOCK-108 fingerprint rides the drill result's
    verification trail instead.  ``fault_id`` is content-derived over
    the full core (tamper-evident).
    """

    fault_id: str
    contract_id: str
    runtime_id: str
    fault_kind: str
    fault_at: str
    lost_route_decision_id: str
    lost_path_id: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "fault.contract_id")
        )
        object.__setattr__(
            self, "runtime_id", _require_id(self.runtime_id, "fault.runtime_id")
        )
        object.__setattr__(
            self, "fault_kind", _require_in(self.fault_kind, FAULT_KINDS, "fault.fault_kind")
        )
        object.__setattr__(
            self, "fault_at", _require_instant(self.fault_at, "fault.fault_at")
        )
        for label, value in (
            ("lost_route_decision_id", self.lost_route_decision_id),
            ("lost_path_id", self.lost_path_id),
        ):
            object.__setattr__(
                self,
                label,
                _require_str(value, "fault.%s" % label, pattern=_REF_VALUE_PATTERN),
            )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "fault.provenance")
        )
        expected = _derive_fault_id_from_core(self)
        if not self.fault_id:
            object.__setattr__(self, "fault_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.fault_id) is None:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "fault.fault_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.fault_id != expected:
                raise ResilienceError(
                    ResilienceReason.ID_MISMATCH,
                    "fault_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fault_id": self.fault_id,
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "fault_kind": self.fault_kind,
            "fault_at": self.fault_at,
            "lost_route_decision_id": self.lost_route_decision_id,
            "lost_path_id": self.lost_path_id,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "FaultRecord":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT, "the fault record must be a mapping"
            )
        return FaultRecord(
            fault_id=data.get("fault_id") or "",
            contract_id=data.get("contract_id"),
            runtime_id=data.get("runtime_id"),
            fault_kind=data.get("fault_kind"),
            fault_at=data.get("fault_at"),
            lost_route_decision_id=data.get("lost_route_decision_id"),
            lost_path_id=data.get("lost_path_id"),
            provenance=Provenance.from_dict(data.get("provenance")),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the fault record")


def _derive_fault_id_from_core(record: FaultRecord) -> str:
    document = {
        "contract_id": record.contract_id,
        "runtime_id": record.runtime_id,
        "fault_kind": record.fault_kind,
        "fault_at": record.fault_at,
        "lost_route_decision_id": record.lost_route_decision_id,
        "lost_path_id": record.lost_path_id,
        "provenance": record.provenance.to_dict(),
    }
    return _derive_id(_FAULT_NAMESPACE, document, "the fault id document")


# ----------------------------------------------------------------------
# The fault phase (fault -> detect -> replan/failover)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class FaultPhaseResult:
    """The typed outcome of the drill's first three phases (fault ->
    detect -> replan/failover), all driven through THIS package's own
    accepted engines plus the accepted ``evidence/`` plane:

    - ``fault`` — the typed :class:`FaultRecord` (the deterministic
      fault injection naming the lost realization);
    - ``detection_evidence_id`` — the accepted LOCK-106
      ``ObservationEvidence`` record id (the fault is OBSERVED on the
      evidence plane — health-state, NOT_RUNNING);
    - ``drive`` — the accepted :class:`resilience.runtime.DriveResult`
      of the failover (the consumed M008 ``ReplanDecision`` verbatim,
      the runtime session after the drive, the WORK-012 reconnect
      evidence when adopted, the appended journal event ids);
    - ``failover_evidence_id`` — the accepted LOCK-106
      ``AttestationEvidence`` record id attesting the failover outcome
      (controller-verified: adopted, or the honest disclosed
      non-adoption);
    - ``constraint_fingerprint`` — the contract's OWN LOCK-108
      fingerprint, consumed from the contract at the phase boundary
      (never recomputed here; the trail entry).
    """

    fault: FaultRecord
    detection_evidence_id: str
    drive: DriveResult
    failover_evidence_id: str
    constraint_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.fault, FaultRecord):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the fault phase requires a FaultRecord",
            )
        object.__setattr__(
            self,
            "detection_evidence_id",
            _require_str(
                self.detection_evidence_id,
                "the detection evidence id",
                pattern=_REF_VALUE_PATTERN,
            ),
        )
        if not isinstance(self.drive, DriveResult):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the fault phase requires a resilience DriveResult (the "
                "accepted failover drive)",
            )
        object.__setattr__(
            self,
            "failover_evidence_id",
            _require_str(
                self.failover_evidence_id,
                "the failover attestation id",
                pattern=_REF_VALUE_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "constraint_fingerprint",
            _require_id(self.constraint_fingerprint, "the phase fingerprint"),
        )


def run_fault_phase(
    plan: ConvergenceDrillPlan,
    *,
    contract: ConnectivityContract,
    execution_plan: ExecutionPlan,
    runtime_store: RuntimeStore,
    runtime_id: object,
    evidence_store: EvidenceStore,
    provenance: Optional[Provenance] = None,
) -> FaultPhaseResult:
    """Execute the drill's fault -> detect -> replan/failover phases
    (deterministic; injected instants only).

    1. **FAULT** — the typed fault record: the runtime session's
       CURRENT realization is lost (named verbatim — the fault kind
       projects onto the accepted failover trigger vocabulary through
       the accepted frozen map).
    2. **DETECT** — the LOCK-106 observation of the fault, ingested
       into the caller's accepted ``EvidenceStore`` (the frozen
       ``health-state`` metric, the NOT_RUNNING ordinal — the evidence
       plane sees the failure; the freshness horizon is the failover
       phase's injected instant, the deterministic-window discipline).
    3. **REPLAN/FAILOVER** — the accepted
       :func:`resilience.failover.orchestrate_failover` over the
       accepted M006 plan: the consumed M008 kernel validates every
       alternative against the contract's FULL hard-constraint set
       (LOCK-108 — a weakening candidate is rejected with the typed
       reason, never silently adopted), selects deterministically by
       the DECLARED tie-break (LOCK-111), and the adopted realization
       lands through the EXPLICIT reconnect pair (the WORK-012
       discipline).  The outcome is attested on the evidence plane
       (controller-verified: adopted, or the honest disclosed
       non-adoption — never a silent downgrade).

    Fail-closed gates: the plan/contract/runtime attribution must
    agree exactly (the drill rides one contract and one runtime
    session); the runtime must be a replan surface (the accepted
    engine's own gate); the evidence records must be accepted by the
    evidence plane.
    """
    if not isinstance(plan, ConvergenceDrillPlan):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "run_fault_phase requires a ConvergenceDrillPlan (got %s)"
            % type(plan).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "run_fault_phase requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(execution_plan, ExecutionPlan):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "run_fault_phase requires an executionplans.ExecutionPlan (got %s)"
            % type(execution_plan).__name__,
        )
    if not isinstance(runtime_store, RuntimeStore):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "run_fault_phase requires a resilience RuntimeStore (got %s)"
            % type(runtime_store).__name__,
        )
    if not isinstance(evidence_store, EvidenceStore):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "run_fault_phase requires an evidence EvidenceStore (got %s)"
            % type(evidence_store).__name__,
        )
    if plan.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the convergence drill plan rides contract %s, not %s — the "
            "drill runs on exactly its owning contract"
            % (plan.contract_id[:23], contract.contract_id[:23]),
        )
    session = runtime_store.session(runtime_id)
    if session.runtime_id != plan.runtime_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the convergence drill plan rides runtime %s, not %s"
            % (plan.runtime_id[:23], session.runtime_id[:23]),
        )
    if session.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "runtime session %s rides contract %s, not %s — the drill "
            "realizes exactly its owning contract"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    phase_provenance = (
        provenance
        if provenance is not None
        else Provenance(
            issuer=CONVERGENCE_ISSUER,
            decision_refs=(plan.drill_id, contract.contract_id, session.runtime_id),
        )
    )
    if not isinstance(phase_provenance, Provenance):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    # -- phase 1: FAULT (the deterministic fault injection) ----------
    old_route, old_path = session.realization_refs()
    fault = FaultRecord(
        fault_id="",
        contract_id=contract.contract_id,
        runtime_id=session.runtime_id,
        fault_kind=plan.fault_kind,
        fault_at=plan.fault_at,
        lost_route_decision_id=old_route,
        lost_path_id=old_path,
        provenance=phase_provenance,
    )

    # -- phase 2: DETECT (the LOCK-106 observation, evidence-visible) -
    observation = ObservationEvidence(
        subject_ref=session.runtime_id,
        contract_ref=contract.contract_id,
        instant=plan.detect_at,
        producer=CONVERGENCE_ISSUER,
        metric="health-state",
        value=FAULT_OBSERVATION_VALUE,
        confidence_basis_points=10_000,
        freshness_until=plan.failover_at,
        source_refs=(contract.contract_id, fault.fault_id),
    )
    observation_result = evidence_store.ingest(observation)
    if not observation_result.accepted:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "the fault-detection observation was not accepted by the "
            "evidence plane: %s" % observation_result.detail[:90],
        )

    # -- phase 3: REPLAN/FAILOVER (the accepted M015 failover drive) -
    drive = orchestrate_failover(
        runtime_store,
        session.runtime_id,
        contract,
        execution_plan,
        trigger_kind="path-failed",
        recorded_at=plan.failover_at,
        provenance=phase_provenance,
    )
    adopted = drive.outcome == "adopted"
    reconnect_ref = (
        drive.reconnect.reconnect_id if drive.reconnect is not None else ""
    )
    attestation = AttestationEvidence(
        subject_ref=session.runtime_id,
        contract_ref=contract.contract_id,
        instant=plan.failover_at,
        producer=CONVERGENCE_ISSUER,
        attestation_kind="controller-verified",
        attested_value=(
            FAILOVER_ATTESTATION_ADOPTED
            if adopted
            else FAILOVER_ATTESTATION_NOT_ADOPTED
        ),
        valid_until=plan.offline_at,
        source_refs=(
            drive.decision.decision_id,
            reconnect_ref or drive.decision.decision,
        ),
    )
    attestation_result = evidence_store.ingest(attestation)
    if not attestation_result.accepted:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "the failover-outcome attestation was not accepted by the "
            "evidence plane: %s" % attestation_result.detail[:90],
        )

    return FaultPhaseResult(
        fault=fault,
        detection_evidence_id=observation_result.record_id,
        drive=drive,
        failover_evidence_id=attestation_result.record_id,
        constraint_fingerprint=contract.hard_constraint_fingerprint(),
    )


# ----------------------------------------------------------------------
# The duck-typed phase records (the accepted surfaces' own values)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OfflinePhaseRecord:
    """The composed citations of the drill's ``offline-operation``
    phase — the accepted M016 offline boundary as DATA (the
    composition root drives the accepted ``localfirst`` surface; this
    record carries the accepted records' OWN public values, read
    through the duck-typed by-reference discipline).

    ``episode_id`` / ``base_snapshot_id`` / ``base_state_digest`` cite
    the partition episode and the base authority view it operated on;
    ``admitted_operation_ids`` cite the journaled local admissions in
    journal order; ``base_constraint_fingerprint`` is the base view's
    OWN LOCK-108 fingerprint (the accepted ``AuthoritySnapshot``'s
    member, consumed at runtime — the assembler re-verifies it equals
    the contract's own).
    """

    episode_id: str
    base_snapshot_id: str
    base_state_digest: str
    admitted_operation_ids: Tuple[str, ...]
    base_constraint_fingerprint: str

    def __post_init__(self) -> None:
        for label, value in (
            ("episode_id", self.episode_id),
            ("base_snapshot_id", self.base_snapshot_id),
            ("base_state_digest", self.base_state_digest),
        ):
            object.__setattr__(
                self,
                label,
                _require_str(value, "offline.%s" % label, pattern=_REF_VALUE_PATTERN),
            )
        if isinstance(self.admitted_operation_ids, (str, bytes)) or not isinstance(
            self.admitted_operation_ids, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "offline.admitted_operation_ids must be a sequence",
            )
        normalized = tuple(
            _require_str(value, "offline.admitted_operation_ids[%d]" % i,
                         pattern=_REF_VALUE_PATTERN)
            for i, value in enumerate(self.admitted_operation_ids)
        )
        object.__setattr__(self, "admitted_operation_ids", normalized)
        object.__setattr__(
            self,
            "base_constraint_fingerprint",
            _require_id(self.base_constraint_fingerprint, "offline.base_constraint_fingerprint"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "base_snapshot_id": self.base_snapshot_id,
            "base_state_digest": self.base_state_digest,
            "admitted_operation_ids": list(self.admitted_operation_ids),
            "base_constraint_fingerprint": self.base_constraint_fingerprint,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OfflinePhaseRecord":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the offline phase record must be a mapping",
            )
        return OfflinePhaseRecord(
            episode_id=data.get("episode_id"),
            base_snapshot_id=data.get("base_snapshot_id"),
            base_state_digest=data.get("base_state_digest"),
            admitted_operation_ids=tuple(data.get("admitted_operation_ids") or ()),
            base_constraint_fingerprint=data.get("base_constraint_fingerprint"),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the offline phase record")


def offline_phase_record(journal: object, base_view: object) -> OfflinePhaseRecord:
    """Read the accepted M016 offline-boundary citations from the
    accepted records' OWN public surfaces (the duck-typed by-reference
    discipline — the ``localfirst`` package is above this prefix in
    the frozen one-way import DAG, so its records are consumed at
    runtime exactly the way ``federation.convergence`` consumes the
    accepted child authorities it cannot import: the accepted
    objects' own methods produce every value).

    ``journal`` is the accepted ``localfirst.OfflineJournal`` (its
    folded ``state()`` carries the episode id, the base view
    references and the admitted operation ids); ``base_view`` is the
    accepted ``localfirst.AuthoritySnapshot`` (its ``realization_
    refs()`` and ``constraint_fingerprint`` members carry the view
    citations).  A record that does not expose the accepted surface
    fails closed typed (never a silent partial consumption).
    """
    _duck_surface(
        journal,
        ("state",),
        "the accepted M016 offline journal",
    )
    state = journal.state()
    _duck_surface(
        state,
        ("episode_id", "base_snapshot_id", "base_state_digest", "admitted"),
        "the accepted M016 folded local state",
    )
    _duck_surface(
        base_view,
        ("realization_refs", "constraint_fingerprint"),
        "the accepted M016 base authority view",
    )
    snapshot_id, state_digest = base_view.realization_refs()
    if state.base_snapshot_id != snapshot_id or state.base_state_digest != state_digest:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the offline episode's base view references %s/%s do not equal "
            "the supplied base authority view's %s/%s — the drill composes "
            "exactly the view the partitioned node operated on"
            % (
                state.base_snapshot_id[:23],
                state.base_state_digest[:23],
                snapshot_id[:23],
                state_digest[:23],
            ),
        )
    return OfflinePhaseRecord(
        episode_id=state.episode_id,
        base_snapshot_id=snapshot_id,
        base_state_digest=state_digest,
        admitted_operation_ids=tuple(state.admitted),
        base_constraint_fingerprint=base_view.constraint_fingerprint,
    )


@dataclass(frozen=True)
class RecoveryPhaseRecord:
    """The composed citations of the drill's ``recover`` and
    ``reconcile`` phases — the accepted M017 disaster-recovery drill
    as DATA (the composition root drives the accepted ``recovery``
    engine; this record carries the accepted ``DrillResult``'s OWN
    public values, read through the duck-typed by-reference
    discipline).

    ``drill_run_id`` cites the accepted drill run; ``recovery_points``
    carries the (plane, recovery_point_id) pairs; ``restoration_
    outcomes`` carries the per-plane restore-verification outcomes
    (``byte-exact`` or ``divergence-reconciled`` — the honest M017
    vocabulary, never re-interpreted); ``reconciliation_outcome`` is
    the accepted cross-plane reconciliation outcome (``converged`` or
    ``divergence-disclosed``); ``reconciliation_fingerprint`` is the
    accepted reconciliation's OWN LOCK-108 fingerprint; ``evidence_
    record_ids`` are the drill's LOCK-106 evidence records (the
    plane-loss observations and the restore attestations — the
    evidence-visible recover phase); ``measured_counts`` are the
    deterministic operation counts (the RTO accounting, verbatim);
    ``completed_at`` is the accepted drill's completion instant.
    """

    drill_run_id: str
    contract_id: str
    recovery_points: Tuple[Tuple[str, str], ...]
    restoration_outcomes: Tuple[str, ...]
    reconciliation_outcome: str
    reconciliation_fingerprint: str
    reconciliation_evidence_ids: Tuple[str, ...]
    measured_journal_appends: int
    measured_folds: int
    measured_verifications: int
    completed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "drill_run_id",
            _require_str(self.drill_run_id, "recovery.drill_run_id",
                         pattern=_REF_VALUE_PATTERN),
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "recovery.contract_id")
        )
        if isinstance(self.recovery_points, (str, bytes)) or not isinstance(
            self.recovery_points, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "recovery.recovery_points must be a sequence of (plane, id) pairs",
            )
        points = []
        for i, pair in enumerate(self.recovery_points):
            if isinstance(pair, (str, bytes)) or not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "recovery.recovery_points[%d] must be a (plane, id) pair" % i,
                )
            plane, point_id = pair[0], pair[1]
            _require_str(plane, "recovery.recovery_points[%d].plane" % i,
                         pattern=_REF_VALUE_PATTERN)
            _require_str(point_id, "recovery.recovery_points[%d].id" % i,
                         pattern=_REF_VALUE_PATTERN)
            points.append((plane, point_id))
        object.__setattr__(self, "recovery_points", tuple(points))
        if isinstance(self.restoration_outcomes, (str, bytes)) or not isinstance(
            self.restoration_outcomes, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "recovery.restoration_outcomes must be a sequence",
            )
        outcomes = tuple(
            _require_str(value, "recovery.restoration_outcomes[%d]" % i,
                         pattern=_REF_VALUE_PATTERN)
            for i, value in enumerate(self.restoration_outcomes)
        )
        unknown = [o for o in outcomes if o not in ("byte-exact", "divergence-reconciled")]
        if unknown:
            raise ResilienceError(
                ResilienceReason.VOCABULARY,
                "recovery.restoration_outcomes carries values outside the "
                "accepted M017 vocabulary %r (the convergence surface never "
                "re-interprets the accepted restore outcomes)" % unknown,
            )
        object.__setattr__(self, "restoration_outcomes", outcomes)
        object.__setattr__(
            self,
            "reconciliation_outcome",
            _require_in(
                self.reconciliation_outcome,
                ("converged", "divergence-disclosed"),
                "recovery.reconciliation_outcome",
            ),
        )
        object.__setattr__(
            self,
            "reconciliation_fingerprint",
            _require_id(
                self.reconciliation_fingerprint,
                "recovery.reconciliation_fingerprint",
            ),
        )
        if isinstance(self.reconciliation_evidence_ids, (str, bytes)) or not isinstance(
            self.reconciliation_evidence_ids, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "recovery.reconciliation_evidence_ids must be a sequence",
            )
        evidence_ids = tuple(
            _require_str(value, "recovery.reconciliation_evidence_ids[%d]" % i,
                         pattern=_REF_VALUE_PATTERN)
            for i, value in enumerate(self.reconciliation_evidence_ids)
        )
        object.__setattr__(self, "reconciliation_evidence_ids", evidence_ids)
        for label, value in (
            ("measured_journal_appends", self.measured_journal_appends),
            ("measured_folds", self.measured_folds),
            ("measured_verifications", self.measured_verifications),
        ):
            object.__setattr__(
                self, label, _require_int(value, "recovery.%s" % label)
            )
        object.__setattr__(
            self,
            "completed_at",
            _require_instant(self.completed_at, "recovery.completed_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drill_run_id": self.drill_run_id,
            "contract_id": self.contract_id,
            "recovery_points": [
                {"plane": plane, "recovery_point_id": point_id}
                for plane, point_id in self.recovery_points
            ],
            "restoration_outcomes": list(self.restoration_outcomes),
            "reconciliation_outcome": self.reconciliation_outcome,
            "reconciliation_fingerprint": self.reconciliation_fingerprint,
            "reconciliation_evidence_ids": list(self.reconciliation_evidence_ids),
            "measured_counts": {
                "journal_appends": self.measured_journal_appends,
                "folds": self.measured_folds,
                "verifications": self.measured_verifications,
            },
            "completed_at": self.completed_at,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RecoveryPhaseRecord":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the recovery phase record must be a mapping",
            )
        counts = data.get("measured_counts") or {}
        return RecoveryPhaseRecord(
            drill_run_id=data.get("drill_run_id"),
            contract_id=data.get("contract_id"),
            recovery_points=tuple(
                (item.get("plane"), item.get("recovery_point_id"))
                for item in data.get("recovery_points") or ()
            ),
            restoration_outcomes=tuple(data.get("restoration_outcomes") or ()),
            reconciliation_outcome=data.get("reconciliation_outcome"),
            reconciliation_fingerprint=data.get("reconciliation_fingerprint"),
            reconciliation_evidence_ids=tuple(
                data.get("reconciliation_evidence_ids") or ()
            ),
            measured_journal_appends=counts.get("journal_appends"),
            measured_folds=counts.get("folds"),
            measured_verifications=counts.get("verifications"),
            completed_at=data.get("completed_at"),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the recovery phase record")


def recovery_phase_record(drill_result: object) -> RecoveryPhaseRecord:
    """Read the accepted M017 drill citations from the accepted
    ``recovery.DrillResult``'s OWN public surface (the duck-typed
    by-reference discipline — see :func:`offline_phase_record`).

    Fail-closed gates: the result must expose the accepted surface
    (the run id, the recovery points, the restorations, the
    reconciliation with its fingerprint and evidence ids, the measured
    counts, the completion instant); the reconciliation must exist
    (the drill's reconcile step ran — the end-to-end sequence requires
    it); every restoration outcome must be the accepted M017
    vocabulary.
    """
    _duck_surface(
        drill_result,
        (
            "drill_run_id",
            "contract_id",
            "recovery_points",
            "restorations",
            "reconciliation",
            "measured_counts",
            "completed_at",
        ),
        "the accepted M017 drill result",
    )
    reconciliation = drill_result.reconciliation
    if reconciliation is None:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "the accepted M017 drill result carries no reconciliation — the "
            "end-to-end convergence drill requires the reconcile phase (the "
            "cross-plane reconciliation is the drill's convergence verdict)",
        )
    _duck_surface(
        reconciliation,
        ("outcome", "constraint_fingerprint", "evidence_record_ids"),
        "the accepted M017 plane reconciliation",
    )
    _duck_surface(
        drill_result.measured_counts,
        ("journal_appends", "folds", "verifications"),
        "the accepted M017 measured operation counts",
    )
    restorations = tuple(drill_result.restorations)
    outcomes = []
    for i, verification in enumerate(restorations):
        _duck_surface(
            verification,
            ("outcome",),
            "the accepted M017 restore verification %d" % i,
        )
        outcomes.append(verification.outcome)
    return RecoveryPhaseRecord(
        drill_run_id=drill_result.drill_run_id,
        contract_id=drill_result.contract_id,
        recovery_points=tuple(
            (plane, point_id) for plane, point_id in drill_result.recovery_points
        ),
        restoration_outcomes=tuple(outcomes),
        reconciliation_outcome=reconciliation.outcome,
        reconciliation_fingerprint=reconciliation.constraint_fingerprint,
        reconciliation_evidence_ids=tuple(
            reconciliation.evidence_record_ids
        ),
        measured_journal_appends=drill_result.measured_counts.journal_appends,
        measured_folds=drill_result.measured_counts.folds,
        measured_verifications=drill_result.measured_counts.verifications,
        completed_at=drill_result.completed_at,
    )


# ----------------------------------------------------------------------
# The end-to-end drill result (the composed convergence verdict)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ConvergenceDrillResult:
    """The composed end-to-end convergence drill outcome: the fault
    phase citations, the offline-phase citations, the recovery-phase
    citations, the LOCK-108 verification trail (one entry per phase —
    the contract's OWN fingerprint, re-verified equal at every phase
    boundary), the LOCK-106 evidence citations (every evidence-visible
    transition), and the drill outcome (the accepted M017
    reconciliation outcome, consumed verbatim).

    ``convergence_run_id`` is content-derived over the full composed
    core (tamper-evident; same drill inputs -> the byte-identical run
    id).
    """

    convergence_run_id: str
    drill_id: str
    contract_id: str
    runtime_id: str
    fault_id: str
    detection_evidence_id: str
    failover_outcome: str
    failover_decision_id: str
    failover_reconnect_id: str
    failover_evidence_id: str
    offline: OfflinePhaseRecord
    recovery: RecoveryPhaseRecord
    lock108_trail: Tuple[Tuple[str, str], ...]
    lock106_citations: Tuple[str, ...]
    outcome: str
    completed_at: str
    provenance: Provenance

    def __post_init__(self) -> None:
        for label, value in (
            ("drill_id", self.drill_id),
            ("contract_id", self.contract_id),
            ("runtime_id", self.runtime_id),
            ("fault_id", self.fault_id),
        ):
            object.__setattr__(self, label, _require_id(value, "result.%s" % label))
        for label, value in (
            ("detection_evidence_id", self.detection_evidence_id),
            ("failover_evidence_id", self.failover_evidence_id),
            ("failover_decision_id", self.failover_decision_id),
        ):
            object.__setattr__(
                self,
                label,
                _require_str(value, "result.%s" % label, pattern=_REF_VALUE_PATTERN),
            )
        object.__setattr__(
            self,
            "failover_reconnect_id",
            _require_str(
                self.failover_reconnect_id,
                "result.failover_reconnect_id",
                pattern=_REF_VALUE_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "failover_outcome",
            _require_in(
                self.failover_outcome,
                ("adopted", "degraded", "failed", "renegotiate"),
                "result.failover_outcome",
            ),
        )
        if not isinstance(self.offline, OfflinePhaseRecord):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "result.offline must be an OfflinePhaseRecord",
            )
        if not isinstance(self.recovery, RecoveryPhaseRecord):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "result.recovery must be a RecoveryPhaseRecord",
            )
        if isinstance(self.lock108_trail, (str, bytes)) or not isinstance(
            self.lock108_trail, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "result.lock108_trail must be a sequence of (phase, fingerprint) pairs",
            )
        trail = []
        for i, pair in enumerate(self.lock108_trail):
            if isinstance(pair, (str, bytes)) or not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "result.lock108_trail[%d] must be a (phase, fingerprint) pair" % i,
                )
            phase, fingerprint = pair[0], pair[1]
            _require_in(phase, DRILL_PHASES, "result.lock108_trail[%d].phase" % i)
            _require_id(fingerprint, "result.lock108_trail[%d].fingerprint" % i)
            trail.append((phase, fingerprint))
        object.__setattr__(self, "lock108_trail", tuple(trail))
        if isinstance(self.lock106_citations, (str, bytes)) or not isinstance(
            self.lock106_citations, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "result.lock106_citations must be a sequence",
            )
        citations = tuple(
            _require_str(value, "result.lock106_citations[%d]" % i,
                         pattern=_REF_VALUE_PATTERN)
            for i, value in enumerate(self.lock106_citations)
        )
        object.__setattr__(self, "lock106_citations", citations)
        object.__setattr__(
            self, "outcome", _require_in(self.outcome, DRILL_OUTCOMES, "result.outcome")
        )
        object.__setattr__(
            self,
            "completed_at",
            _require_instant(self.completed_at, "result.completed_at"),
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "result.provenance")
        )
        expected = _derive_convergence_run_id(self)
        if not self.convergence_run_id:
            object.__setattr__(self, "convergence_run_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.convergence_run_id) is None:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "result.convergence_run_id must be the content-derived "
                    "identity (sha256:...)",
                )
            if self.convergence_run_id != expected:
                raise ResilienceError(
                    ResilienceReason.ID_MISMATCH,
                    "convergence_run_id does not match the derived identity "
                    "(tamper evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "convergence_run_id": self.convergence_run_id,
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "fault_id": self.fault_id,
            "detection_evidence_id": self.detection_evidence_id,
            "failover_outcome": self.failover_outcome,
            "failover_decision_id": self.failover_decision_id,
            "failover_reconnect_id": self.failover_reconnect_id,
            "failover_evidence_id": self.failover_evidence_id,
            "offline": self.offline.to_dict(),
            "recovery": self.recovery.to_dict(),
            "lock108_trail": [
                {"phase": phase, "constraint_fingerprint": fingerprint}
                for phase, fingerprint in self.lock108_trail
            ],
            "lock106_citations": list(self.lock106_citations),
            "outcome": self.outcome,
            "completed_at": self.completed_at,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ConvergenceDrillResult":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the convergence drill result must be a mapping",
            )
        return ConvergenceDrillResult(
            convergence_run_id=data.get("convergence_run_id") or "",
            drill_id=data.get("drill_id"),
            contract_id=data.get("contract_id"),
            runtime_id=data.get("runtime_id"),
            fault_id=data.get("fault_id"),
            detection_evidence_id=data.get("detection_evidence_id"),
            failover_outcome=data.get("failover_outcome"),
            failover_decision_id=data.get("failover_decision_id"),
            failover_reconnect_id=data.get("failover_reconnect_id"),
            failover_evidence_id=data.get("failover_evidence_id"),
            offline=OfflinePhaseRecord.from_dict(data.get("offline") or {}),
            recovery=RecoveryPhaseRecord.from_dict(data.get("recovery") or {}),
            lock108_trail=tuple(
                (item.get("phase"), item.get("constraint_fingerprint"))
                for item in data.get("lock108_trail") or ()
            ),
            lock106_citations=tuple(data.get("lock106_citations") or ()),
            outcome=data.get("outcome"),
            completed_at=data.get("completed_at"),
            provenance=Provenance.from_dict(data.get("provenance")),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the convergence drill result")


def _derive_convergence_run_id(result: ConvergenceDrillResult) -> str:
    document = {
        "drill_id": result.drill_id,
        "contract_id": result.contract_id,
        "runtime_id": result.runtime_id,
        "fault_id": result.fault_id,
        "detection_evidence_id": result.detection_evidence_id,
        "failover_outcome": result.failover_outcome,
        "failover_decision_id": result.failover_decision_id,
        "failover_reconnect_id": result.failover_reconnect_id,
        "failover_evidence_id": result.failover_evidence_id,
        "offline": result.offline.to_dict(),
        "recovery": result.recovery.to_dict(),
        "lock108_trail": [
            {"phase": phase, "constraint_fingerprint": fingerprint}
            for phase, fingerprint in result.lock108_trail
        ],
        "lock106_citations": list(result.lock106_citations),
        "outcome": result.outcome,
        "completed_at": result.completed_at,
    }
    return _derive_id(_DRILL_NAMESPACE, document, "the convergence run id document")


def assemble_convergence_drill(
    plan: ConvergenceDrillPlan,
    *,
    contract: ConnectivityContract,
    fault_phase: FaultPhaseResult,
    offline_phase: OfflinePhaseRecord,
    recovery_phase: RecoveryPhaseRecord,
    evidence_store: EvidenceStore,
    provenance: Optional[Provenance] = None,
) -> ConvergenceDrillResult:
    """Assemble and VERIFY the composed end-to-end convergence drill
    (the deterministic convergence verdict over the composed phases).

    The LOCK-108 verification trail (every hard constraint preserved
    at each step — the contract's OWN fingerprint, consumed from the
    contract and re-verified equal at every phase boundary):

    1. ``fault`` / ``detect`` / ``replan-failover`` — the fault
       phase's recorded fingerprint (the contract's own, read at the
       phase boundary; the constraint validation itself happened
       inside the consumed M008 kernel — a weakening alternative was
       rejected there with the typed reason, never adopted);
    2. ``offline-operation`` — the base authority view's OWN
       fingerprint (duck-typed, the accepted ``AuthoritySnapshot``
       member) must equal the contract's — a forged or stale authority
       view fails closed HERE as well as inside the accepted M016
       resynchronization gate;
    3. ``recover`` — the recovery phase's contract attribution (the
       accepted drill result rode exactly the owning contract);
    4. ``reconcile`` — the accepted M017 reconciliation's OWN
       fingerprint must equal the contract's (the accepted record
       carries the contract's fingerprint; a mismatch is a forged
       reconciliation and fails closed).

    The LOCK-106 citation verification (every transition
    evidence-visible): the fault-detection observation, the
    failover-outcome attestation and every accepted M017 drill
    evidence record (the plane-loss observations and the restore
    attestations) must RESOLVE on the evidence plane (the accepted
    ``EvidenceStore.has`` gate — an evidence record that never landed
    is a broken evidence chain, never a silent pass).

    The drill outcome: the accepted M017 reconciliation outcome,
    consumed VERBATIM (``converged`` or ``divergence-disclosed`` —
    this surface never absorbs a disclosed divergence and never
    upgrades one).
    """
    if not isinstance(plan, ConvergenceDrillPlan):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "assemble_convergence_drill requires a ConvergenceDrillPlan",
        )
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "assemble_convergence_drill requires a contracts.ConnectivityContract",
        )
    if not isinstance(fault_phase, FaultPhaseResult):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "assemble_convergence_drill requires a FaultPhaseResult",
        )
    if not isinstance(offline_phase, OfflinePhaseRecord):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "assemble_convergence_drill requires an OfflinePhaseRecord",
        )
    if not isinstance(recovery_phase, RecoveryPhaseRecord):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "assemble_convergence_drill requires a RecoveryPhaseRecord",
        )
    if not isinstance(evidence_store, EvidenceStore):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "assemble_convergence_drill requires an evidence EvidenceStore",
        )
    if plan.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the convergence drill plan rides contract %s, not %s"
            % (plan.contract_id[:23], contract.contract_id[:23]),
        )
    if fault_phase.fault.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the fault phase rode contract %s, not %s — the drill composes "
            "phases of exactly one owning contract"
            % (fault_phase.fault.contract_id[:23], contract.contract_id[:23]),
        )
    if fault_phase.fault.runtime_id != plan.runtime_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the fault phase rode runtime %s, not the drill plan's %s"
            % (fault_phase.fault.runtime_id[:23], plan.runtime_id[:23]),
        )
    if fault_phase.drive.decision.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the failover decision is attributable to contract %s, not %s — "
            "the consumed M008 decision must ride exactly the drill's "
            "owning contract"
            % (
                fault_phase.drive.decision.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    if recovery_phase.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the accepted M017 drill result rode contract %s, not %s — the "
            "composed phases must ride exactly one owning contract"
            % (recovery_phase.contract_id[:23], contract.contract_id[:23]),
        )

    contract_fingerprint = contract.hard_constraint_fingerprint()

    # -- the LOCK-108 trail: the contract's own fingerprint, equal at
    #    every phase boundary (fail closed on any divergence) --------
    if fault_phase.constraint_fingerprint != contract_fingerprint:
        raise ResilienceError(
            ResilienceReason.CONSTRAINT_MISMATCH,
            "the fault phase's recorded LOCK-108 fingerprint does not "
            "reproduce the contract's own — the drill's hard-constraint "
            "preservation trail is broken at the fault/detect/failover "
            "boundary (LOCK-108)",
        )
    if offline_phase.base_constraint_fingerprint != contract_fingerprint:
        raise ResilienceError(
            ResilienceReason.CONSTRAINT_MISMATCH,
            "the base authority view's LOCK-108 fingerprint does not "
            "reproduce the contract's own — a forged or stale authority "
            "view is rejected whole across the offline boundary (LOCK-108)",
        )
    if recovery_phase.reconciliation_fingerprint != contract_fingerprint:
        raise ResilienceError(
            ResilienceReason.CONSTRAINT_MISMATCH,
            "the accepted M017 reconciliation's LOCK-108 fingerprint does "
            "not reproduce the contract's own — the cross-plane "
            "reconciliation did not preserve the contract's hard "
            "constraints (LOCK-108)",
        )
    lock108_trail: Tuple[Tuple[str, str], ...] = (
        ("fault", contract_fingerprint),
        ("detect", contract_fingerprint),
        ("replan-failover", contract_fingerprint),
        ("offline-operation", contract_fingerprint),
        ("recover", contract_fingerprint),
        ("reconcile", contract_fingerprint),
    )

    # -- the LOCK-106 citations: every evidence-visible transition
    #    resolves on the evidence plane (fail closed on a broken chain) --
    citations = (
        fault_phase.detection_evidence_id,
        fault_phase.failover_evidence_id,
    ) + recovery_phase.reconciliation_evidence_ids
    for citation in citations:
        if not evidence_store.has(citation):
            raise ResilienceError(
                ResilienceReason.ID_MISMATCH,
                "the LOCK-106 evidence record %s does not resolve on the "
                "evidence plane — an evidence-visible transition that never "
                "landed is a broken evidence chain (the drill never passes "
                "silently)" % citation[:48],
            )

    assembly_provenance = (
        provenance
        if provenance is not None
        else Provenance(
            issuer=CONVERGENCE_ISSUER,
            decision_refs=(
                plan.drill_id,
                contract.contract_id,
                recovery_phase.drill_run_id,
            ),
        )
    )
    if not isinstance(assembly_provenance, Provenance):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    drive = fault_phase.drive
    return ConvergenceDrillResult(
        convergence_run_id="",
        drill_id=plan.drill_id,
        contract_id=contract.contract_id,
        runtime_id=plan.runtime_id,
        fault_id=fault_phase.fault.fault_id,
        detection_evidence_id=fault_phase.detection_evidence_id,
        failover_outcome=drive.outcome,
        failover_decision_id=drive.decision.decision_id,
        failover_reconnect_id=(
            drive.reconnect.reconnect_id if drive.reconnect is not None else ""
        ),
        failover_evidence_id=fault_phase.failover_evidence_id,
        offline=offline_phase,
        recovery=recovery_phase,
        lock108_trail=lock108_trail,
        lock106_citations=citations,
        outcome=recovery_phase.reconciliation_outcome,
        completed_at=recovery_phase.completed_at,
        provenance=assembly_provenance,
    )


# ----------------------------------------------------------------------
# The converged-domain compatibility matrix over the R8 domains
# (the accepted upgrade/ matrix discipline, extended)
# ----------------------------------------------------------------------


def _require_r8_domain(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "%s must be a non-empty domain label" % label,
        )
    _reject_secret(value, label)
    if value not in R8_CONVERGENCE_DOMAINS:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "%s %r is outside the R8 convergence domain set %s (fail "
            "closed — the R7-substrate labels enter the composed matrix as "
            "the accepted upgrade engine's own verdict DATA, never "
            "re-declared here)" % (label, value, list(R8_CONVERGENCE_DOMAINS)),
        )
    return value


@dataclass(frozen=True)
class ConvergenceDomainVersion:
    """One R8 convergence domain's implementation version point (the
    accepted ``upgrade.convergence.DomainVersion`` grammar extended
    onto the R8 labels: the frozen additive-evolution ``MAJOR.MINOR``
    — each side speaks every minor up to its head).

    An R7-substrate domain version is constructed through the ACCEPTED
    ``upgrade.convergence.DomainVersion`` record by the composition
    root (its own construction gates apply verbatim); this record
    covers the R8 extension labels only.
    """

    domain: str
    major: int
    minor: int

    def __post_init__(self) -> None:
        _require_r8_domain(self.domain, "the domain version domain")
        for label, value in (("major", self.major), ("minor", self.minor)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "the domain version %s must be an int >= 0 (found %r)"
                    % (label, value),
                )

    def to_dict(self) -> Dict[str, object]:
        return {"domain": self.domain, "major": self.major, "minor": self.minor}

    @staticmethod
    def from_dict(data: object) -> "ConvergenceDomainVersion":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the domain version material must be a mapping",
            )
        return ConvergenceDomainVersion(
            domain=data.get("domain"),
            major=data.get("major"),
            minor=data.get("minor"),
        )


@dataclass(frozen=True)
class ConvergenceDomainVerdict:
    """One typed per-domain coexistence verdict on the R8 matrix (the
    accepted ``upgrade.convergence.DomainCompatibilityVerdict`` shape —
    the same serialized members — so the composed matrix digests
    uniformly over the accepted R7 rows and the R8 extension rows)."""

    domain: str
    verdict: str
    local_major: int
    local_minor: int
    peer_major: int
    peer_minor: int
    detail: str = ""

    def __post_init__(self) -> None:
        _require_r8_domain(self.domain, "the verdict domain")
        _require_in(self.verdict, MATRIX_VERDICTS, "the verdict")
        for label, value in (
            ("local_major", self.local_major),
            ("local_minor", self.local_minor),
            ("peer_major", self.peer_major),
            ("peer_minor", self.peer_minor),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < -1:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "the verdict %s must be an int >= -1 (the -1 marks a "
                    "missing side; found %r)" % (label, value),
                )
        if isinstance(self.detail, str) and len(self.detail) > 240:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the verdict detail is bounded (240 characters maximum)",
            )

    def to_dict(self) -> Dict[str, object]:
        return {
            "domain": self.domain,
            "verdict": self.verdict,
            "local_major": self.local_major,
            "local_minor": self.local_minor,
            "peer_major": self.peer_major,
            "peer_minor": self.peer_minor,
            "detail": self.detail,
        }

    @staticmethod
    def from_dict(data: object) -> "ConvergenceDomainVerdict":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the verdict material must be a mapping",
            )
        return ConvergenceDomainVerdict(
            domain=data.get("domain"),
            verdict=data.get("verdict"),
            local_major=data.get("local_major"),
            local_minor=data.get("local_minor"),
            peer_major=data.get("peer_major"),
            peer_minor=data.get("peer_minor"),
            detail=data.get("detail") or "",
        )


def classify_convergence_domain(
    local: ConvergenceDomainVersion, peer: ConvergenceDomainVersion
) -> ConvergenceDomainVerdict:
    """The deterministic mixed-version coexistence verdict for ONE R8
    convergence domain (the accepted upgrade matrix discipline,
    extended onto the R8 labels — the family's frozen fail-closed
    semantics): incompatible majors have NO fallback, no clamping, no
    best-effort guess; additive minors are disclosed, never silently
    ignored; same-major peers at or below the local additive head are
    compatible."""
    if not isinstance(local, ConvergenceDomainVersion) or not isinstance(
        peer, ConvergenceDomainVersion
    ):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "classify_convergence_domain requires two "
            "ConvergenceDomainVersion records",
        )
    if local.domain != peer.domain:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "domain mismatch: %r vs %r (one verdict per domain)"
            % (local.domain, peer.domain),
        )
    if local.major != peer.major:
        return ConvergenceDomainVerdict(
            domain=local.domain,
            verdict="major-mismatch",
            local_major=local.major,
            local_minor=local.minor,
            peer_major=peer.major,
            peer_minor=peer.minor,
            detail="majors differ (%d vs %d): there is NO fallback to a "
                   "lower common major (fail closed)" % (local.major, peer.major),
        )
    if peer.minor > local.minor:
        return ConvergenceDomainVerdict(
            domain=local.domain,
            verdict="additive-gap",
            local_major=local.major,
            local_minor=local.minor,
            peer_major=peer.major,
            peer_minor=peer.minor,
            detail="the peer carries additive minors %d..%d the local side "
                   "does not speak (disclosed; interoperate on the shared "
                   "minor %d)" % (local.minor + 1, peer.minor, local.minor),
        )
    return ConvergenceDomainVerdict(
        domain=local.domain,
        verdict="compatible",
        local_major=local.major,
        local_minor=local.minor,
        peer_major=peer.major,
        peer_minor=peer.minor,
        detail="the shared major %d with the peer minor %d at or below the "
               "local additive head %d" % (local.major, peer.minor, local.minor),
    )


def _matrix_digest(local_id: str, peer_id: str, rows: Sequence[Mapping[str, object]]) -> str:
    """The byte-stable matrix digest (canonical JSON over the sorted
    row sequence — input order never matters; hash-seed independent)."""
    document = {
        "local_id": local_id,
        "peer_id": peer_id,
        "verdicts": [dict(row) for row in rows],
    }
    return _derive_id(_MATRIX_NAMESPACE, document, "the matrix digest document")


@dataclass(frozen=True)
class R8MatrixReport:
    """The deterministic compatibility report over two peers' R8
    domain version sets (sorted domain iteration; input-order
    independent; byte-stable digest).  A domain present on one side
    only fails closed (``local-missing`` / ``peer-missing`` — never
    silently skipped)."""

    local_id: str
    peer_id: str
    verdicts: Tuple[ConvergenceDomainVerdict, ...]

    def __post_init__(self) -> None:
        for label, value in (("local_id", self.local_id), ("peer_id", self.peer_id)):
            object.__setattr__(
                self,
                label,
                _require_str(value, "the matrix report %s" % label),
            )
        if isinstance(self.verdicts, (str, bytes)) or not isinstance(
            self.verdicts, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the matrix report verdicts must be a sequence",
            )
        verdicts = tuple(self.verdicts)
        for i, verdict in enumerate(verdicts):
            if not isinstance(verdict, ConvergenceDomainVerdict):
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "the matrix report verdicts[%d] must be a "
                    "ConvergenceDomainVerdict record" % i,
                )
        object.__setattr__(self, "verdicts", verdicts)

    def digest(self) -> str:
        """The canonical report digest (byte-stable across runs and
        hash seeds; the same discipline as the accepted
        ``ConvergedCompatibilityReport.digest``)."""
        return _matrix_digest(
            self.local_id,
            self.peer_id,
            [verdict.to_dict() for verdict in sorted(
                self.verdicts, key=lambda v: v.domain
            )],
        )

    def by_domain(self) -> Dict[str, ConvergenceDomainVerdict]:
        return {verdict.domain: verdict for verdict in self.verdicts}

    def compatible(self) -> bool:
        """True iff NO R8 domain pair fails closed (major mismatches
        and missing sides refuse; additive gaps are disclosed but
        interoperate)."""
        return all(
            verdict.verdict in ("compatible", "additive-gap")
            for verdict in self.verdicts
        )


def negotiate_r8_matrix(
    *,
    local_id: str,
    peer_id: str,
    local_versions: Sequence[ConvergenceDomainVersion],
    peer_versions: Sequence[ConvergenceDomainVersion],
) -> R8MatrixReport:
    """The deterministic R8-domain compatibility negotiation (the
    accepted ``negotiate_converged_compatibility`` discipline extended
    onto the R8 labels): both sides' version sets are consulted by
    SORTED domain label (input order never matters); a domain present
    on one side only fails closed; every present pair classifies
    through :func:`classify_convergence_domain`."""
    if isinstance(local_versions, (str, bytes)) or not isinstance(
        local_versions, (tuple, list)
    ):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "negotiate_r8_matrix requires version sequences",
        )
    if isinstance(peer_versions, (str, bytes)) or not isinstance(
        peer_versions, (tuple, list)
    ):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "negotiate_r8_matrix requires version sequences",
        )
    local_map: Dict[str, ConvergenceDomainVersion] = {}
    for version in local_versions:
        if not isinstance(version, ConvergenceDomainVersion):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the local version entries must be ConvergenceDomainVersion "
                "records",
            )
        if version.domain in local_map:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "duplicate local domain version for %r" % version.domain,
            )
        local_map[version.domain] = version
    peer_map: Dict[str, ConvergenceDomainVersion] = {}
    for version in peer_versions:
        if not isinstance(version, ConvergenceDomainVersion):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the peer version entries must be ConvergenceDomainVersion "
                "records",
            )
        if version.domain in peer_map:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "duplicate peer domain version for %r" % version.domain,
            )
        peer_map[version.domain] = version
    records = []
    for domain in sorted(set(local_map) | set(peer_map)):
        local = local_map.get(domain)
        peer = peer_map.get(domain)
        if local is None:
            records.append(ConvergenceDomainVerdict(
                domain=domain,
                verdict="local-missing",
                local_major=-1,
                local_minor=-1,
                peer_major=peer.major,
                peer_minor=peer.minor,
                detail="the local peer does not carry the R8 convergence "
                       "domain (fail closed; never silently skipped)",
            ))
            continue
        if peer is None:
            records.append(ConvergenceDomainVerdict(
                domain=domain,
                verdict="peer-missing",
                local_major=local.major,
                local_minor=local.minor,
                peer_major=-1,
                peer_minor=-1,
                detail="the remote peer does not carry the R8 convergence "
                       "domain (fail closed; never silently skipped)",
            ))
            continue
        records.append(classify_convergence_domain(local, peer))
    return R8MatrixReport(
        local_id=local_id,
        peer_id=peer_id,
        verdicts=tuple(records),
    )


#: The accepted R7-substrate verdict dict members (the
# ``upgrade.convergence.DomainCompatibilityVerdict.to_dict`` shape —
# the composed matrix validates every substrate row against this
# exact member set, so the accepted engine's own serialized verdicts
# ride verbatim and nothing else does).
_SUBSTRATE_ROW_MEMBERS: Tuple[str, ...] = (
    "domain",
    "verdict",
    "local_major",
    "local_minor",
    "peer_major",
    "peer_minor",
    "detail",
)


@dataclass(frozen=True)
class ConvergenceMatrixReport:
    """The COMPOSED converged-domain compatibility matrix: the
    accepted upgrade engine's R7-substrate rows (its own serialized
    verdicts — DATA consumed by reference at runtime) plus the R8
    extension rows, iterated by SORTED domain label with a
    byte-stable digest over the composed row sequence (input order
    never matters)."""

    local_id: str
    peer_id: str
    rows: Tuple[Tuple[str, str, str], ...]

    def __post_init__(self) -> None:
        for label, value in (("local_id", self.local_id), ("peer_id", self.peer_id)):
            object.__setattr__(
                self,
                label,
                _require_str(value, "the composed matrix %s" % label),
            )
        if isinstance(self.rows, (str, bytes)) or not isinstance(
            self.rows, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the composed matrix rows must be a sequence of "
                "(domain, verdict, detail) triples",
            )
        rows = []
        seen = set()
        for i, triple in enumerate(self.rows):
            if (
                isinstance(triple, (str, bytes))
                or not isinstance(triple, (tuple, list))
                or len(triple) != 3
            ):
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "the composed matrix rows[%d] must be a (domain, verdict, "
                    "detail) triple" % i,
                )
            domain, verdict, detail = triple[0], triple[1], triple[2]
            _require_str(domain, "the composed matrix rows[%d].domain" % i)
            _require_in(verdict, MATRIX_VERDICTS, "the composed matrix rows[%d].verdict" % i)
            _require_str(detail, "the composed matrix rows[%d].detail" % i)
            if domain in seen:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "the composed matrix carries the domain %r twice — one "
                    "row per domain" % domain,
                )
            seen.add(domain)
            rows.append((domain, verdict, detail))
        object.__setattr__(self, "rows", tuple(rows))

    def digest(self) -> str:
        """The canonical composed-matrix digest (byte-stable; sorted by
        domain label — the accepted discipline)."""
        document = {
            "local_id": self.local_id,
            "peer_id": self.peer_id,
            "rows": [
                {"domain": domain, "verdict": verdict, "detail": detail}
                for domain, verdict, detail in sorted(self.rows)
            ],
        }
        return _derive_id(_MATRIX_NAMESPACE, document, "the composed matrix digest")

    def by_domain(self) -> Dict[str, str]:
        return {domain: verdict for domain, verdict, _ in self.rows}

    def compatible(self) -> bool:
        """True iff NO composed row fails closed (major mismatches and
        missing sides refuse; additive gaps interoperate)."""
        return all(
            verdict in ("compatible", "additive-gap") for _, verdict, _ in self.rows
        )


def compose_convergence_matrix(
    substrate_verdicts: Sequence[Mapping[str, object]],
    r8_report: R8MatrixReport,
    *,
    local_id: str,
    peer_id: str,
) -> ConvergenceMatrixReport:
    """Compose the full converged-domain compatibility matrix: the
    accepted upgrade engine's R7-substrate rows (the caller passes
    that engine's OWN serialized verdicts — ``[verdict.to_dict() for
    verdict in report.verdicts]`` — consumed by reference at runtime)
    plus the R8 extension rows from :func:`negotiate_r8_matrix`.

    Fail-closed gates: every substrate row must carry EXACTLY the
    accepted verdict member set (the ``upgrade.convergence`` shape —
    anything else is not the accepted engine's output); every verdict
    value must be inside the frozen :data:`MATRIX_VERDICTS`; the
    substrate rows must cover exactly the R7-substrate labels (no R8
    label may ride the substrate rows — the accepted engine cannot
    classify them); the R8 rows must cover exactly the R8 labels.  The
    composed iteration is by SORTED domain label (input order never
    matters) and the digest is byte-stable.
    """
    if isinstance(substrate_verdicts, (str, bytes)) or not isinstance(
        substrate_verdicts, (tuple, list)
    ):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "compose_convergence_matrix requires the accepted engine's "
            "serialized substrate verdict sequence",
        )
    if not isinstance(r8_report, R8MatrixReport):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "compose_convergence_matrix requires an R8MatrixReport",
        )
    composed: list = []
    substrate_domains = set()
    for i, row in enumerate(substrate_verdicts):
        if not isinstance(row, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the substrate verdicts[%d] must be a mapping (the accepted "
                "engine's serialized verdict rows)" % i,
            )
        if set(row.keys()) != set(_SUBSTRATE_ROW_MEMBERS):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the substrate verdicts[%d] does not carry exactly the "
                "accepted upgrade verdict member set %s — only that "
                "engine's own serialized verdicts ride the composed matrix"
                % (i, list(_SUBSTRATE_ROW_MEMBERS)),
            )
        domain = row.get("domain")
        verdict = row.get("verdict")
        detail = row.get("detail")
        if not isinstance(domain, str) or not domain:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the substrate verdicts[%d].domain must be a non-empty "
                "string" % i,
            )
        if domain in R8_CONVERGENCE_DOMAINS:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the substrate verdicts[%d] carries the R8 domain %r — the "
                "accepted upgrade engine classifies exactly the R7-substrate "
                "labels (an R8 label on the substrate rows is not that "
                "engine's output)" % (i, domain),
            )
        if domain in substrate_domains:
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the substrate verdicts carry the domain %r twice" % domain,
            )
        substrate_domains.add(domain)
        _require_in(verdict, MATRIX_VERDICTS, "the substrate verdicts[%d].verdict" % i)
        if not isinstance(detail, str):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the substrate verdicts[%d].detail must be a string" % i,
            )
        composed.append((domain, verdict, detail))
    r8_domains = {verdict.domain for verdict in r8_report.verdicts}
    if r8_domains & substrate_domains:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "the R8 rows and the substrate rows overlap (%s) — one row per "
            "domain" % sorted(r8_domains & substrate_domains),
        )
    for verdict in r8_report.verdicts:
        composed.append((verdict.domain, verdict.verdict, verdict.detail))
    if r8_domains != set(R8_CONVERGENCE_DOMAINS):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "the R8 rows must cover exactly the R8 convergence domain set "
            "%s (found %s) — a converged peer that does not carry an R8 "
            "domain is incompatible on that line, never silently skipped"
            % (list(R8_CONVERGENCE_DOMAINS), sorted(r8_domains)),
        )
    return ConvergenceMatrixReport(
        local_id=local_id,
        peer_id=peer_id,
        rows=tuple(composed),
    )


# ----------------------------------------------------------------------
# The federation-scale convergence over the R8 domains (the accepted
# scale/ harness discipline, extended)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class FederationScaleBounds:
    """The DECLARED deterministic bounds of one R8 federation-scale
    convergence scenario (the accepted ``scale.convergence`` harness
    envelope — the W039 reproducibility contract — declared up front
    and VERIFIED against the accepted harness run by
    :func:`verify_federation_scale_convergence`):

    - the world envelope: ``domain_count``, ``shape`` (the accepted
      topology vocabulary), ``tick_seconds``, ``horizon_ticks``;
    - the citation envelope: ``citation_rate_limit`` (the per-domain
      per-tick admission bound) and ``planned_citations`` (the declared
      admission count);
    - the revocation envelope: ``revoked_citation_count`` (the declared
      revoked-holder count) and ``propagation_round_bounds`` — one
      DECLARED predicted-round count per revoked citation id (the
      topology-predicted convergence bound, LOCK-111-class: observed
      must equal predicted, fail closed on divergence).
    """

    domain_count: int
    shape: str
    tick_seconds: int
    horizon_ticks: int
    citation_rate_limit: int
    planned_citations: int
    revoked_citation_count: int
    propagation_round_bounds: Tuple[Tuple[str, int], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_count", _require_int(self.domain_count, "bounds.domain_count", minimum=1)
        )
        object.__setattr__(
            self, "shape", _require_str(self.shape, "bounds.shape")
        )
        object.__setattr__(
            self, "tick_seconds", _require_int(self.tick_seconds, "bounds.tick_seconds", minimum=1)
        )
        object.__setattr__(
            self, "horizon_ticks", _require_int(self.horizon_ticks, "bounds.horizon_ticks")
        )
        object.__setattr__(
            self,
            "citation_rate_limit",
            _require_int(self.citation_rate_limit, "bounds.citation_rate_limit", minimum=1),
        )
        object.__setattr__(
            self,
            "planned_citations",
            _require_int(self.planned_citations, "bounds.planned_citations"),
        )
        object.__setattr__(
            self,
            "revoked_citation_count",
            _require_int(self.revoked_citation_count, "bounds.revoked_citation_count"),
        )
        if isinstance(self.propagation_round_bounds, (str, bytes)) or not isinstance(
            self.propagation_round_bounds, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "bounds.propagation_round_bounds must be a sequence of "
                "(citation id, predicted rounds) pairs",
            )
        bounds = []
        seen = set()
        for i, pair in enumerate(self.propagation_round_bounds):
            if (
                isinstance(pair, (str, bytes))
                or not isinstance(pair, (tuple, list))
                or len(pair) != 2
            ):
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "bounds.propagation_round_bounds[%d] must be a (citation "
                    "id, predicted rounds) pair" % i,
                )
            citation_id, rounds = pair[0], pair[1]
            _require_str(
                citation_id,
                "bounds.propagation_round_bounds[%d].citation_id" % i,
                pattern=_CITATION_ID_PATTERN,
            )
            _require_int(
                rounds,
                "bounds.propagation_round_bounds[%d].rounds" % i,
                minimum=1,
            )
            if citation_id in seen:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "bounds.propagation_round_bounds carries the citation "
                    "%r twice" % citation_id[:40],
                )
            seen.add(citation_id)
            bounds.append((citation_id, rounds))
        object.__setattr__(self, "propagation_round_bounds", tuple(bounds))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_count": self.domain_count,
            "shape": self.shape,
            "tick_seconds": self.tick_seconds,
            "horizon_ticks": self.horizon_ticks,
            "citation_rate_limit": self.citation_rate_limit,
            "planned_citations": self.planned_citations,
            "revoked_citation_count": self.revoked_citation_count,
            "propagation_round_bounds": [
                {"citation_id": citation_id, "predicted_rounds": rounds}
                for citation_id, rounds in self.propagation_round_bounds
            ],
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "FederationScaleBounds":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the scale bounds must be a mapping",
            )
        return FederationScaleBounds(
            domain_count=data.get("domain_count"),
            shape=data.get("shape"),
            tick_seconds=data.get("tick_seconds"),
            horizon_ticks=data.get("horizon_ticks"),
            citation_rate_limit=data.get("citation_rate_limit"),
            planned_citations=data.get("planned_citations"),
            revoked_citation_count=data.get("revoked_citation_count"),
            propagation_round_bounds=tuple(
                (item.get("citation_id"), item.get("predicted_rounds"))
                for item in data.get("propagation_round_bounds") or ()
            ),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the scale bounds record")


@dataclass(frozen=True)
class FederationScaleConvergence:
    """The composed R8 federation-scale convergence report: the
    accepted scale harness run consumed by reference at runtime (its
    OWN digests and counts carried verbatim — never recomputed here)
    together with the declared bounds and the VERIFIED convergence
    properties (the replay identity, the topology-predicted round
    counts, the declared envelopes).  ``report_id`` is content-derived
    over the composed core (tamper-evident)."""

    report_id: str
    run_digest: str
    spec_digest: str
    citation_ids: Tuple[str, ...]
    domain_count: int
    relationship_count: int
    citation_count: int
    revoked_citation_count: int
    propagation: Tuple[Tuple[str, int, int], ...]
    declared_bounds: FederationScaleBounds
    replay_verified: bool
    provenance: Provenance

    def __post_init__(self) -> None:
        for label, value in (
            ("run_digest", self.run_digest),
            ("spec_digest", self.spec_digest),
        ):
            object.__setattr__(
                self,
                label,
                _require_str(value, "the scale convergence %s" % label,
                             pattern=_RUN_DIGEST_PATTERN),
            )
        if isinstance(self.citation_ids, (str, bytes)) or not isinstance(
            self.citation_ids, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the scale convergence citation_ids must be a sequence",
            )
        citation_ids = tuple(
            _require_str(value, "the scale convergence citation_ids[%d]" % i,
                         pattern=_CITATION_ID_PATTERN)
            for i, value in enumerate(self.citation_ids)
        )
        if len(set(citation_ids)) != len(citation_ids):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the scale convergence citation_ids carry duplicates",
            )
        object.__setattr__(self, "citation_ids", citation_ids)
        for label, value in (
            ("domain_count", self.domain_count),
            ("relationship_count", self.relationship_count),
            ("citation_count", self.citation_count),
            ("revoked_citation_count", self.revoked_citation_count),
        ):
            object.__setattr__(
                self, label, _require_int(value, "the scale convergence %s" % label)
            )
        if isinstance(self.propagation, (str, bytes)) or not isinstance(
            self.propagation, (tuple, list)
        ):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the scale convergence propagation must be a sequence of "
                "(citation id, predicted rounds, observed rounds) triples",
            )
        propagation = []
        for i, triple in enumerate(self.propagation):
            if (
                isinstance(triple, (str, bytes))
                or not isinstance(triple, (tuple, list))
                or len(triple) != 3
            ):
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "the scale convergence propagation[%d] must be a "
                    "(citation id, predicted, observed) triple" % i,
                )
            citation_id, predicted, observed = triple[0], triple[1], triple[2]
            _require_str(
                citation_id,
                "the scale convergence propagation[%d].citation_id" % i,
                pattern=_CITATION_ID_PATTERN,
            )
            _require_int(predicted, "the propagation[%d].predicted" % i, minimum=1)
            _require_int(observed, "the propagation[%d].observed" % i, minimum=1)
            propagation.append((citation_id, predicted, observed))
        object.__setattr__(self, "propagation", tuple(propagation))
        if not isinstance(self.declared_bounds, FederationScaleBounds):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the scale convergence requires the declared bounds record",
            )
        if not isinstance(self.replay_verified, bool):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the scale convergence replay_verified must be a boolean",
            )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "the scale convergence provenance")
        )
        expected = _derive_scale_report_id(self)
        if not self.report_id:
            object.__setattr__(self, "report_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.report_id) is None:
                raise ResilienceError(
                    ResilienceReason.INVALID_INPUT,
                    "the scale convergence report_id must be the "
                    "content-derived identity (sha256:...)",
                )
            if self.report_id != expected:
                raise ResilienceError(
                    ResilienceReason.ID_MISMATCH,
                    "report_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_digest": self.run_digest,
            "spec_digest": self.spec_digest,
            "citation_ids": list(self.citation_ids),
            "domain_count": self.domain_count,
            "relationship_count": self.relationship_count,
            "citation_count": self.citation_count,
            "revoked_citation_count": self.revoked_citation_count,
            "propagation": [
                {
                    "citation_id": citation_id,
                    "predicted_rounds": predicted,
                    "observed_rounds": observed,
                }
                for citation_id, predicted, observed in self.propagation
            ],
            "declared_bounds": self.declared_bounds.to_dict(),
            "replay_verified": self.replay_verified,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "FederationScaleConvergence":
        if not isinstance(data, Mapping):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "the scale convergence report must be a mapping",
            )
        return FederationScaleConvergence(
            report_id=data.get("report_id") or "",
            run_digest=data.get("run_digest"),
            spec_digest=data.get("spec_digest"),
            citation_ids=tuple(data.get("citation_ids") or ()),
            domain_count=data.get("domain_count"),
            relationship_count=data.get("relationship_count"),
            citation_count=data.get("citation_count"),
            revoked_citation_count=data.get("revoked_citation_count"),
            propagation=tuple(
                (
                    item.get("citation_id"),
                    item.get("predicted_rounds"),
                    item.get("observed_rounds"),
                )
                for item in data.get("propagation") or ()
            ),
            declared_bounds=FederationScaleBounds.from_dict(
                data.get("declared_bounds") or {}
            ),
            replay_verified=data.get("replay_verified"),
            provenance=Provenance.from_dict(data.get("provenance")),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the scale convergence report")


def _derive_scale_report_id(report: FederationScaleConvergence) -> str:
    document = {
        "run_digest": report.run_digest,
        "spec_digest": report.spec_digest,
        "citation_ids": list(report.citation_ids),
        "domain_count": report.domain_count,
        "relationship_count": report.relationship_count,
        "citation_count": report.citation_count,
        "revoked_citation_count": report.revoked_citation_count,
        "propagation": [
            {
                "citation_id": citation_id,
                "predicted_rounds": predicted,
                "observed_rounds": observed,
            }
            for citation_id, predicted, observed in report.propagation
        ],
        "declared_bounds": report.declared_bounds.to_dict(),
        "replay_verified": report.replay_verified,
    }
    return _derive_id(_SCALE_NAMESPACE, document, "the scale report id document")


def verify_federation_scale_convergence(
    bounds: FederationScaleBounds,
    run_result: object,
    replay_result: object,
    *,
    citation_ids: Sequence[str],
    provenance: Optional[Provenance] = None,
) -> FederationScaleConvergence:
    """Verify the accepted scale-harness run against the DECLARED
    deterministic bounds and compose the R8 federation-scale
    convergence report (the accepted ``scale.convergence`` run result
    consumed by reference at runtime — its OWN digests and counts
    carried verbatim, never recomputed here).

    The verified properties (every one fails closed typed on
    divergence):

    1. the run and the re-run (the replay) carry the IDENTICAL run
       digest — the byte-identical replay, the accepted harness's own
       reproducibility contract;
    2. the world envelope matches the declared bounds (the domain
       count);
    3. the citation envelope matches (the citation admissions count
       and every R8 material citation id present in the run's
       propagation/journal material — the declared R8 citations);
    4. the revocation envelope matches (the revoked-citation count);
    5. every observed propagation round count equals its DECLARED
       predicted bound (the topology-predicted convergence bound —
       LOCK-111-class: fail closed on divergence, never a silent
       pass).

    ``citation_ids`` are the R8 drill-material citation ids the
    scenario planned across the federation domains (constructed by
    the composition root through the ACCEPTED
    ``federation.convergence`` cite-* constructors over the REAL R8
    records — the replan decision and the LOCK-106 evidence records).
    """
    if not isinstance(bounds, FederationScaleBounds):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "verify_federation_scale_convergence requires "
            "FederationScaleBounds (the declared deterministic envelope)",
        )
    _duck_surface(
        run_result,
        (
            "run_digest",
            "spec_digest",
            "domain_count",
            "relationship_count",
            "citation_count",
            "revoked_citation_count",
            "propagation",
            "ledger_digests",
        ),
        "the accepted scale harness run result",
    )
    _duck_surface(
        replay_result,
        ("run_digest",),
        "the accepted scale harness replay result",
    )
    if isinstance(citation_ids, (str, bytes)) or not isinstance(
        citation_ids, (tuple, list)
    ):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "citation_ids must be a sequence of citation ids",
        )
    r8_citations = tuple(
        _require_str(value, "citation_ids[%d]" % i, pattern=_CITATION_ID_PATTERN)
        for i, value in enumerate(citation_ids)
    )
    if len(set(r8_citations)) != len(r8_citations):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "citation_ids carry duplicates",
        )

    # 1. the byte-identical replay (the accepted harness's own
    #    reproducibility contract, verified on the consumed digests)
    replay_verified = replay_result.run_digest == run_result.run_digest
    if not replay_verified:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the accepted scale harness replay diverged (run digest %s vs "
            "%s) — the convergence scenarios are replay-verified, never "
            "silently accepted" % (
                run_result.run_digest[:23], replay_result.run_digest[:23],
            ),
        )

    # 2. the world envelope
    if run_result.domain_count != bounds.domain_count:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the accepted harness ran %d domains, not the declared %d — the "
            "declared deterministic bounds are the contract"
            % (run_result.domain_count, bounds.domain_count),
        )
    ledger_digests = tuple(run_result.ledger_digests)
    if len(ledger_digests) != bounds.domain_count:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the accepted harness carries %d per-domain ledger digests, "
            "not one per declared domain (%d)"
            % (len(ledger_digests), bounds.domain_count),
        )

    # 3. the citation envelope
    if run_result.citation_count != bounds.planned_citations:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the accepted harness admitted %d citations, not the declared "
            "%d — the declared deterministic bounds are the contract"
            % (run_result.citation_count, bounds.planned_citations),
        )

    # 4. the revocation envelope
    if run_result.revoked_citation_count != bounds.revoked_citation_count:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "the accepted harness revoked %d citations, not the declared %d"
            % (
                run_result.revoked_citation_count,
                bounds.revoked_citation_count,
            ),
        )

    # 5. the topology-predicted propagation bounds (observed ==
    #    declared predicted, fail closed).  Every declared bound rides
    #    an R8 material citation (the revocation envelope cites the R8
    #    drill material — a bound naming a foreign citation fails
    #    closed: the composed report's citations stay the R8 set).
    r8_citation_set = set(r8_citations)
    for citation_id, _ in bounds.propagation_round_bounds:
        if citation_id not in r8_citation_set:
            raise ResilienceError(
                ResilienceReason.ID_MISMATCH,
                "the declared propagation bound cites %s — not one of the "
                "R8 drill-material citations (the revocation envelope "
                "rides the R8 material; fail closed)" % citation_id[:40],
            )
    propagation_records = tuple(run_result.propagation)
    observed_by_citation = {}
    for record in propagation_records:
        _duck_surface(
            record,
            ("citation_id", "predicted_rounds", "observed_rounds"),
            "the accepted propagation record",
        )
        observed_by_citation[record.citation_id] = (
            record.predicted_rounds,
            record.observed_rounds,
        )
    propagation = []
    for citation_id, declared_rounds in bounds.propagation_round_bounds:
        pair = observed_by_citation.get(citation_id)
        if pair is None:
            raise ResilienceError(
                ResilienceReason.ID_MISMATCH,
                "the declared revoked citation %s never propagated in the "
                "accepted harness run — the declared bounds are the "
                "contract (fail closed)" % citation_id[:40],
            )
        predicted, observed = pair
        if predicted != declared_rounds or observed != declared_rounds:
            raise ResilienceError(
                ResilienceReason.ID_MISMATCH,
                "the propagation of %s diverged from the declared "
                "topology-predicted bound (declared %d, the harness "
                "predicted %d, observed %d) — the convergence bound fails "
                "closed (LOCK-111-class)" % (
                    citation_id[:40], declared_rounds, predicted, observed,
                ),
            )
        propagation.append((citation_id, declared_rounds, observed))

    verify_provenance = (
        provenance
        if provenance is not None
        else Provenance(
            issuer=CONVERGENCE_ISSUER,
            decision_refs=(run_result.run_digest, bounds.shape),
        )
    )
    if not isinstance(verify_provenance, Provenance):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    return FederationScaleConvergence(
        report_id="",
        run_digest=run_result.run_digest,
        spec_digest=run_result.spec_digest,
        citation_ids=r8_citations,
        domain_count=run_result.domain_count,
        relationship_count=run_result.relationship_count,
        citation_count=run_result.citation_count,
        revoked_citation_count=run_result.revoked_citation_count,
        propagation=tuple(propagation),
        declared_bounds=bounds,
        replay_verified=True,
        provenance=verify_provenance,
    )
