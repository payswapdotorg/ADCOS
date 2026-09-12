"""ADCOS recovery domain model (M017 — Disaster Recovery and State
Reconciliation).

The disaster-recovery and state-reconciliation typed records of the R8
charter M017 scope, composing the accepted journal-bearing state planes
BY REFERENCE (the M015 runtime journals — ``resilience/`` — and the
M016 offline journals — ``localfirst/``; imported and driven, never
reimplemented, weakened, forked, or bypassed):

- **Typed recovery points** (:class:`RecoveryPoint`): the snapshot of
  one journal-bearing plane — the plane's journal carried as canonical
  JSON record lines (immutable bytes — the byte-exact restore
  material), with the content-derived identity (the LOCK-106 class:
  identity derived from CONTENT, never from journal position or time),
  the content-derived state digest, the journal watermark, and the
  full provenance envelope (LOCK-118).
- **The deterministic drill plan** (:class:`DrillPlan` /
  :class:`DrillStep`): a drill is ITSELF a deterministic, replayable
  operation sequence — the frozen step vocabulary (snapshot, induced
  loss, restore, verify, reconcile) with injected instants and typed
  provenance, never wall-clock dependent.
- **The recovery-time bound as DECLARED deterministic operation
  counts** (:class:`OperationBudget`): the RTO-style bound is expressed
  as declared operation counts — journal appends, folds, verifications
  — NEVER wall clock, never sleeps, never timing measurements
  (LOCK-119).  :class:`OperationCounts` is the measured accounting
  record (the drill engine's deterministic counters).
- **Typed restore verification** (:class:`RestoreVerification` /
  :class:`RestoreDivergence`): the recovered state equals the
  pre-failure state BYTE-EXACTLY (``byte-exact``), or the divergence
  is explicitly disclosed and reconciled (``divergence-reconciled`` —
  one typed record per lost record, full provenance, the recovery
  point as the authoritative reconciliation base) — never silently
  absorbed.
- **Typed cross-plane reconciliation** (:class:`PlaneReconciliation` /
  :class:`CrossPlaneDivergence`): the contracts/journal/evidence
  planes converge after a drill with typed divergence records; the
  accepted ``localfirst/`` divergence vocabulary is consumed BY
  REFERENCE where it fits (the accepted ``ResyncResult`` preserved
  verbatim when the reconciliation drives the accepted
  resynchronization); the LOCK-106 evidence records produced by the
  drill are cited and preserved.

The central boundary (enforced throughout — the M015/M016 layering,
extended to the recovery surface):

    RECOVERY POINT / DRILL RESULT
        = an EXECUTION-RECOVERY artifact riding the canonical
          ``ConnectivityContract`` and the accepted journal-bearing
          planes as opaque references (LOCK-117: the contract is the
          sole authority; recovery never writes contract state, never
          re-derives contract identity, never becomes a second
          authority)
        != A JOURNAL AUTHORITY (the accepted folds stay the sole
          writers of plane state — construction-is-recovery: the
          restore REBUILDS through the accepted constructors, never
          around them)
        != A HISTORY REWRITER (LOCK-106: recovered records preserve
          their original content-derived identities; no historical
          record is rewritten; no gapless sequence is silently
          renumbered; a restored plane is byte-identical or the
          difference is a typed, disclosed, reconciled divergence)

Determinism (LOCK-119): content-derived ids over canonical JSON;
injected RFC 3339 UTC instants only; no wall clock, no randomness, no
UUIDs, no network, no secrets; canonical-JSON round-trips with
tamper-evident ids.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import Provenance

from .errors import RecoveryError, RecoveryReason

__all__ = [
    "PLANE_KINDS",
    "CROSS_PLANE_NAMES",
    "DRILL_STEP_KINDS",
    "RESTORE_OUTCOMES",
    "RESTORE_DIVERGENCE_CODES",
    "RESTORE_DIVERGENCE_RESOLUTIONS",
    "CROSS_PLANE_DIVERGENCE_CODES",
    "CROSS_PLANE_RESOLUTIONS",
    "RECONCILIATION_OUTCOMES",
    "RECOVERY_ISSUER",
    "DRILL_ISSUER",
    "OperationBudget",
    "OperationCounts",
    "DrillStep",
    "DrillPlan",
    "RecoveryPoint",
    "RestoreDivergence",
    "RestoreVerification",
    "CrossPlaneDivergence",
    "PlaneReconciliation",
    "DrillResult",
    "journal_state_digest",
]


# ----------------------------------------------------------------------
# The consumed-boundary error wrap (exception isolation)
# ----------------------------------------------------------------------

_CONSUMED_CODE_MAP = {
    "secret-rejected": RecoveryReason.SECRET_REJECTED,
    "recovery-secret-rejected": RecoveryReason.SECRET_REJECTED,
    "resilience-secret-rejected": RecoveryReason.SECRET_REJECTED,
    "localfirst-secret-rejected": RecoveryReason.SECRET_REJECTED,
    "evidence-secret-rejected": RecoveryReason.SECRET_REJECTED,
    "vocabulary": RecoveryReason.VOCABULARY,
    "resilience-vocabulary": RecoveryReason.VOCABULARY,
    "localfirst-vocabulary": RecoveryReason.VOCABULARY,
    "temporal-invalid": RecoveryReason.TEMPORAL_INVALID,
    "resilience-temporal-invalid": RecoveryReason.TEMPORAL_INVALID,
    "localfirst-temporal-invalid": RecoveryReason.TEMPORAL_INVALID,
    "invalid-instant": RecoveryReason.TEMPORAL_INVALID,
    "invalid-input": RecoveryReason.INVALID_INPUT,
    "resilience-invalid-input": RecoveryReason.INVALID_INPUT,
    "localfirst-invalid-input": RecoveryReason.INVALID_INPUT,
    "id-mismatch": RecoveryReason.ID_MISMATCH,
    "resilience-id-mismatch": RecoveryReason.ID_MISMATCH,
    "localfirst-id-mismatch": RecoveryReason.ID_MISMATCH,
    "evidence-record-tamper": RecoveryReason.SNAPSHOT_UNVERIFIABLE,
}


def _wrap_consumed_error(label: str) -> Iterator[None]:
    """Exception isolation at the consumed-domain boundary: a
    ``ResilienceError``/``LocalFirstError``/``ContractError``/
    ``EvidenceError``/``ReplanError`` (all ValueError subclasses
    carrying ``code``/``detail``) surfaces as a typed RecoveryError
    with its deterministic text preserved — never a foreign exception
    type, never raw exception text into stored state.  A
    ``RecoveryError`` passes through untouched (this surface's own
    typed rejections are never double-wrapped)."""

    @contextlib.contextmanager
    def _ctx() -> Iterator[None]:
        try:
            yield
        except RecoveryError:
            raise
        except ValueError as error:  # consumed typed errors are ValueError
            code = getattr(error, "code", "")
            mapped = _CONSUMED_CODE_MAP.get(code, RecoveryReason.COMPOSITION)
            raise RecoveryError(
                mapped,
                "%s was rejected by a consumed domain: %s"
                % (label, getattr(error, "detail", error)),
            ) from None

    return _ctx()


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The journal-bearing state planes the M017 drills operate over (the
#: accepted M015 runtime journal and the accepted M016 offline journal
#: — consumed BY REFERENCE; this vocabulary NAMES them, never
#: re-implements them):
#:
#: - ``runtime-journal`` — one M015 runtime session's append-only event
#:   journal (the accepted ``resilience.RuntimeStore`` journal; the
#:   subject is the runtime session identity);
#: - ``offline-journal`` — one M016 partition episode's append-only
#:   record journal (the accepted ``localfirst.OfflineJournal``; the
#:   subject is the episode identity).
PLANE_KINDS: Tuple[str, ...] = ("runtime-journal", "offline-journal")

#: The plane names of the cross-plane reconciliation (the charter's
#: contracts/journal/evidence planes; the journal plane splits into
#: its two accepted journal-bearing planes):
CROSS_PLANE_NAMES: Tuple[str, ...] = (
    "contracts-plane",
    "runtime-journal",
    "offline-journal",
    "evidence-plane",
)

#: The frozen drill step vocabulary (a drill is itself a deterministic,
#: replayable operation sequence — never wall-clock dependent):
#:
#: - ``snapshot-plane`` — construct the typed recovery point over the
#:   step's plane (the plane journal captured at its head);
#: - ``induce-plane-loss`` — the deterministic simulated plane loss
#:   (the pre-failure content is captured for the restore
#:   verification; the in-memory holder is dropped);
#: - ``restore-plane`` — rebuild the plane from its recovery point
#:   through the ACCEPTED construction-is-recovery constructors (the
#:   fail-closed point verification happens here — an unverifiable
#:   snapshot is rejected whole);
#: - ``verify-restore`` — the restore verification (byte-exact or the
#:   typed disclosed-and-reconciled divergence) plus the LOCK-106
#:   attestation evidence record;
#: - ``reconcile-planes`` — the cross-plane reconciliation (the
#:   contracts/journal/evidence planes converge; the accepted M016
#:   resynchronization driven BY REFERENCE when the episode is open).
DRILL_STEP_KINDS: Tuple[str, ...] = (
    "snapshot-plane",
    "induce-plane-loss",
    "restore-plane",
    "verify-restore",
    "reconcile-planes",
)

#: The plane-scoped step kinds (they carry the ``plane`` member).
_PLANE_SCOPED_STEPS: Tuple[str, ...] = (
    "snapshot-plane",
    "induce-plane-loss",
    "restore-plane",
    "verify-restore",
)

#: The restore-verification outcomes: the recovered state equals the
#: pre-failure state BYTE-EXACTLY, or the divergence is explicitly
#: disclosed and reconciled (never silently absorbed).
RESTORE_OUTCOMES: Tuple[str, ...] = (
    "byte-exact",
    "divergence-reconciled",
)

#: The typed restore-divergence codes: records the pre-failure plane
#: carried BEYOND the recovery point's watermark are lost with the
#: failure — disclosed one typed record each, cited by their ORIGINAL
#: content-derived identities (never renumbered, never rewritten —
#: restoring them would FABRICATE history).
RESTORE_DIVERGENCE_CODES: Tuple[str, ...] = (
    "record-lost-beyond-recovery-point",
)

#: The restore-divergence resolutions: the recovery point is the
#: authoritative reconciliation base (the only legal resolution — a
#: divergence never reconciles onto partially-trusted material).
RESTORE_DIVERGENCE_RESOLUTIONS: Tuple[str, ...] = (
    "reconciled-to-recovery-point",
)

#: The typed cross-plane divergence codes (the cross-plane
#: reconciliation's disclosed records):
#:
#: - ``composition-link-unresolved`` — a journal-plane cross reference
#:   (the offline journal's M015 event/evidence citations) does not
#:   resolve in the peer journal after the drill;
#: - ``evidence-record-missing`` — a drill-produced LOCK-106 evidence
#:   record is absent from the evidence plane (lost with the failure —
#:   disclosed, never silently dropped).
CROSS_PLANE_DIVERGENCE_CODES: Tuple[str, ...] = (
    "composition-link-unresolved",
    "evidence-record-missing",
)

#: The cross-plane divergence resolutions (the disclosure IS the
#: resolution — the M016 convention: the loser stays cited, only
#: explicitly superseded IN THE REPLICA).
CROSS_PLANE_RESOLUTIONS: Tuple[str, ...] = ("disclosed",)

#: The cross-plane reconciliation outcomes.
RECONCILIATION_OUTCOMES: Tuple[str, ...] = (
    "converged",
    "divergence-disclosed",
)

#: The default issuer recorded on recovery-point provenance (LOCK-118:
#: the recovery surface asserts its own records; the contract stays
#: the sole authority).
RECOVERY_ISSUER = "recovery:point"

#: The default issuer recorded on drill provenance.
DRILL_ISSUER = "recovery:drill"


# ----------------------------------------------------------------------
# Internal helpers (the consumed-domain conventions, re-used)
# ----------------------------------------------------------------------

_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")
_SECRET_VALUE_PATTERN_LINE = re.compile(
    r"(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+"
)

_POINT_NAMESPACE = "adc-os-recovery-point"
_DRILL_NAMESPACE = "adc-os-recovery-drill"
_RESTORE_DIVERGENCE_NAMESPACE = "adc-os-recovery-restore-divergence"
_RESTORE_VERIFICATION_NAMESPACE = "adc-os-recovery-restore-verification"
_CROSS_PLANE_DIVERGENCE_NAMESPACE = "adc-os-recovery-cross-plane-divergence"
_RECONCILIATION_NAMESPACE = "adc-os-recovery-reconciliation"
_DRILL_RUN_NAMESPACE = "adc-os-recovery-drill-run"


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, label)
    ).hexdigest()


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-shaped material never enters recovery data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise RecoveryError(
            RecoveryReason.SECRET_REJECTED,
            "%s looks like secret material; secrets never enter recovery "
            "data" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise RecoveryError(
            RecoveryReason.SECRET_REJECTED,
            "%s carries a secret-shaped value; secrets never enter recovery "
            "data" % label,
        )


def _require_str(value: object, label: str, *, pattern: Optional[re.Pattern] = None) -> str:
    if not isinstance(value, str) or not value:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "%s must be the content-derived identity (sha256:...)" % label,
        )
    _reject_secret(value, label)
    return value


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise RecoveryError(
            RecoveryReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "%s must be a non-empty instant string" % label
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise RecoveryError(
            RecoveryReason.TEMPORAL_INVALID,
            "%s %r is not RFC 3339 UTC: %s" % (label, value, error),
        ) from None
    _reject_secret(value, label)
    return value


def _require_provenance(value: object, label: str) -> Provenance:
    if not isinstance(value, Provenance):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "%s must be a Provenance record" % label
        )
    return value


def _require_count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "%s must be a non-negative integer operation count (found %r)"
            % (label, value),
        )
    return value


def _require_sequence(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "%s must be a positive integer journal position (found %r)" % (label, value),
        )
    return value


def journal_state_digest(record_lines: Sequence[str]) -> str:
    """The content-derived plane state digest: the sha256 identity over
    the plane's journal record lines (the concatenated canonical JSON
    bytes, in journal order — the byte-exact restore-verification
    target)."""
    if isinstance(record_lines, (str, bytes)) or not isinstance(
        record_lines, (tuple, list)
    ):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the journal record lines must be a sequence of strings",
        )
    digest = hashlib.sha256()
    for i, line in enumerate(record_lines):
        if not isinstance(line, str) or not line:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "the journal record line %d must be a non-empty canonical JSON "
                "string" % i,
            )
        digest.update(line.encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def _normalize_record_lines(value: object, label: str) -> Tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "%s must be a sequence of record lines" % label
        )
    normalized = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s[%d] must be a non-empty canonical JSON record line" % (label, i),
            )
        _reject_secret(item, "%s[%d]" % (label, i))
        if _SECRET_VALUE_PATTERN_LINE.search(item):
            raise RecoveryError(
                RecoveryReason.SECRET_REJECTED,
                "%s[%d] carries secret-shaped material inside its record line "
                "(LOCK-119: secrets never enter recovery data — the snapshot "
                "is rejected whole)" % (label, i),
            )
        normalized.append(item)
    return tuple(normalized)


def _normalize_digest_pairs(value: object, label: str) -> Tuple[Tuple[str, str], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "%s must be a sequence of pairs" % label
        )
    normalized = []
    for i, item in enumerate(value):
        if isinstance(item, (str, bytes)) or not isinstance(item, (tuple, list)) or len(item) != 2:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s[%d] must be a (plane, digest) pair" % (label, i),
            )
        plane = _require_in(item[0], CROSS_PLANE_NAMES, "%s[%d][0]" % (label, i))
        digest = _require_id(item[1], "%s[%d][1]" % (label, i))
        normalized.append((plane, digest))
    seen = set()
    for plane, _ in normalized:
        if plane in seen:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s carries the plane %s twice" % (label, plane),
            )
        seen.add(plane)
    return tuple(normalized)


# ----------------------------------------------------------------------
# The recovery-time bound: declared and measured operation counts
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OperationBudget:
    """The DECLARED recovery-time bound: the RTO-style bound expressed
    as declared deterministic OPERATION COUNTS — journal appends,
    folds, verifications (LOCK-119: never wall clock, never sleeps,
    never timing measurements).  The drill engine counts the
    operations it drives and fails closed with
    ``recovery-rto-exceeded`` the moment a counter exceeds its
    declared bound; the measured counts are recorded on the drill
    result (byte-identical across re-runs of the same inputs).
    """

    journal_appends: int
    folds: int
    verifications: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "journal_appends", _require_count(self.journal_appends, "budget.journal_appends")
        )
        object.__setattr__(self, "folds", _require_count(self.folds, "budget.folds"))
        object.__setattr__(
            self,
            "verifications",
            _require_count(self.verifications, "budget.verifications"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journal_appends": self.journal_appends,
            "folds": self.folds,
            "verifications": self.verifications,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OperationBudget":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the budget must be a mapping"
            )
        return OperationBudget(
            journal_appends=data.get("journal_appends"),
            folds=data.get("folds"),
            verifications=data.get("verifications"),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the operation budget")


@dataclass(frozen=True)
class OperationCounts:
    """The MEASURED deterministic operation counts (the drill engine's
    accounting record — the RTO verification material: same drill
    inputs, the byte-identical counts; never a timing measurement)."""

    journal_appends: int
    folds: int
    verifications: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "journal_appends", _require_count(self.journal_appends, "counts.journal_appends")
        )
        object.__setattr__(self, "folds", _require_count(self.folds, "counts.folds"))
        object.__setattr__(
            self,
            "verifications",
            _require_count(self.verifications, "counts.verifications"),
        )

    def exceeds(self, budget: OperationBudget) -> Optional[str]:
        """The first exceeded budget member (None when within the
        declared bound) — the deterministic RTO check."""
        if not isinstance(budget, OperationBudget):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "exceeds requires an OperationBudget record",
            )
        for member in ("journal_appends", "folds", "verifications"):
            if getattr(self, member) > getattr(budget, member):
                return member
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journal_appends": self.journal_appends,
            "folds": self.folds,
            "verifications": self.verifications,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "OperationCounts":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the counts must be a mapping"
            )
        return OperationCounts(
            journal_appends=data.get("journal_appends"),
            folds=data.get("folds"),
            verifications=data.get("verifications"),
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the operation counts")


# ----------------------------------------------------------------------
# The drill plan (the deterministic, replayable operation sequence)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class DrillStep:
    """One typed drill operation (the deterministic, replayable
    sequence element).  The plane-scoped kinds carry the ``plane``
    member (one of the journal-bearing planes); ``reconcile-planes``
    carries none (it is the cross-plane step).  Every step carries its
    injected instant and typed provenance (LOCK-118)."""

    kind: str
    recorded_at: str
    provenance: Provenance
    plane: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _require_in(self.kind, DRILL_STEP_KINDS, "step.kind"))
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "step.recorded_at")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "step.provenance")
        )
        if self.kind in _PLANE_SCOPED_STEPS:
            object.__setattr__(
                self, "plane", _require_in(self.plane, PLANE_KINDS, "step.plane")
            )
        elif self.plane:
            raise RecoveryError(
                RecoveryReason.VOCABULARY,
                "the %s step carries the plane member %r outside its frozen "
                "shape (only the plane-scoped steps name a plane)"
                % (self.kind, self.plane),
            )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "kind": self.kind,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }
        if self.plane:
            data["plane"] = self.plane
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "DrillStep":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the drill step must be a mapping"
            )
        return DrillStep(
            kind=data.get("kind"),
            recorded_at=data.get("recorded_at"),
            provenance=Provenance.from_dict(data.get("provenance")),
            plane=data.get("plane") or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the drill step")


@dataclass(frozen=True)
class DrillPlan:
    """The deterministic, replayable drill operation sequence (the
    drill INPUT — never wall-clock dependent): the owning contract, the
    step sequence (strictly increasing injected instants — the
    deterministic operation order), the declared recovery-time bound
    (the RTO-style operation counts) and the typed provenance.
    ``drill_id`` is content-derived over the full plan core (the
    LOCK-106 class: identity from content, never position or time).
    """

    contract_id: str
    steps: Tuple[DrillStep, ...]
    budget: OperationBudget
    provenance: Provenance
    drill_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "plan.contract_id")
        )
        if isinstance(self.steps, (str, bytes)) or not isinstance(self.steps, (tuple, list)):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "plan.steps must be a sequence of steps"
            )
        steps = []
        for i, item in enumerate(self.steps):
            if not isinstance(item, DrillStep):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "plan.steps[%d] must be a DrillStep record (got %s)"
                    % (i, type(item).__name__),
                )
            steps.append(item)
        object.__setattr__(self, "steps", tuple(steps))
        if not self.steps:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "plan.steps carries no steps (a drill is a non-empty operation "
                "sequence)",
            )
        # the deterministic operation order: strictly increasing
        # injected instants (a drill never depends on wall clock — the
        # step order IS the time order, injected)
        for index in range(1, len(self.steps)):
            if (
                parse_instant(self.steps[index].recorded_at)
                <= parse_instant(self.steps[index - 1].recorded_at)
            ):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "plan.steps[%d].recorded_at %s does not strictly follow "
                    "%s (a drill's injected instants are strictly increasing — "
                    "the deterministic operation order)"
                    % (
                        index,
                        self.steps[index].recorded_at,
                        self.steps[index - 1].recorded_at,
                    ),
                )
        if not isinstance(self.budget, OperationBudget):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "plan.budget must be an OperationBudget record (the declared "
                "RTO-style operation counts)",
            )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "plan.provenance")
        )
        expected = self._derive_drill_id()
        if not self.drill_id:
            object.__setattr__(self, "drill_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.drill_id) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "plan.drill_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.drill_id != expected:
                raise RecoveryError(
                    RecoveryReason.ID_MISMATCH,
                    "drill_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_drill_id(self) -> str:
        document = {
            "contract_id": self.contract_id,
            "steps": [step.to_dict() for step in self.steps],
            "budget": self.budget.to_dict(),
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(_DRILL_NAMESPACE, document, "the drill id document")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "steps": [step.to_dict() for step in self.steps],
            "budget": self.budget.to_dict(),
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "DrillPlan":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the drill plan must be a mapping"
            )
        with _wrap_consumed_error("the drill-plan deserialization"):
            return DrillPlan(
                contract_id=data.get("contract_id"),
                steps=tuple(DrillStep.from_dict(s) for s in data.get("steps") or ()),
                budget=OperationBudget.from_dict(data.get("budget")),
                provenance=Provenance.from_dict(data.get("provenance")),
                drill_id=data.get("drill_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the drill plan")


# ----------------------------------------------------------------------
# The typed recovery point (the snapshot of one journal-bearing plane)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveryPoint:
    """The typed recovery point over one journal-bearing state plane
    (the snapshot/recovery-point construction surface).

    ``recovery_point_id`` is content-derived over the full point core
    (the LOCK-106 class: identity derived from CONTENT — the plane
    journal carried as canonical JSON record lines — never from
    journal position or time alone).  ``plane`` names the accepted
    journal-bearing plane (the M015 runtime journal or the M016
    offline journal — consumed by reference).  ``contract_id`` cites
    the OWNING canonical contract (attribution; the contract is the
    sole authority — this record carries no contract semantics beyond
    the citation).  ``subject_id`` is the plane's journal-bearing
    subject (the runtime session identity or the partition-episode
    identity).  ``record_lines`` carries the plane's journal as
    immutable canonical JSON record lines (the byte-exact restore
    material — each line is an accepted record's canonical
    serialization, with its own content-derived identity and
    provenance envelope).  ``state_digest`` (derived) is the
    content-derived plane state digest (the byte-exact
    restore-verification target).  ``sequence`` is the journal
    watermark at snapshot time (the deterministic replay watermark —
    carried as content, never as identity).  ``provenance`` is the
    full provenance envelope (LOCK-118).

    Fail-closed at deserialization (:func:`RecoveryPoint.from_dict` —
    the snapshot verification): unparseable material, a missing
    provenance envelope, a state digest that does not re-derive, or an
    identity that does not re-derive is REJECTED WHOLE
    (``recovery-snapshot-unverifiable``) — never partially trusted,
    never best-effort loaded.
    """

    plane: str
    contract_id: str
    subject_id: str
    record_lines: Tuple[str, ...]
    sequence: int
    recorded_at: str
    provenance: Provenance
    recovery_point_id: str = ""
    state_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plane", _require_in(self.plane, PLANE_KINDS, "point.plane"))
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "point.contract_id")
        )
        object.__setattr__(
            self, "subject_id", _require_id(self.subject_id, "point.subject_id")
        )
        object.__setattr__(
            self,
            "record_lines",
            _normalize_record_lines(self.record_lines, "point.record_lines"),
        )
        object.__setattr__(
            self, "sequence", _require_sequence(self.sequence, "point.sequence")
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "point.recorded_at")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "point.provenance")
        )
        expected_digest = journal_state_digest(self.record_lines)
        if not self.state_digest:
            object.__setattr__(self, "state_digest", expected_digest)
        else:
            if _ID_PATTERN.fullmatch(self.state_digest) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "point.state_digest must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.state_digest != expected_digest:
                raise RecoveryError(
                    RecoveryReason.SNAPSHOT_UNVERIFIABLE,
                    "the recovery point's state digest does not re-derive from "
                    "its journal record lines (bad integrity — the snapshot is "
                    "rejected whole, never partially trusted)",
                )
        expected_id = self._derive_point_id()
        if not self.recovery_point_id:
            object.__setattr__(self, "recovery_point_id", expected_id)
        else:
            if _ID_PATTERN.fullmatch(self.recovery_point_id) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "point.recovery_point_id must be the content-derived "
                    "identity (sha256:...)",
                )
            if self.recovery_point_id != expected_id:
                raise RecoveryError(
                    RecoveryReason.SNAPSHOT_UNVERIFIABLE,
                    "recovery_point_id does not match the derived identity "
                    "(tamper evidence — the snapshot is rejected whole, never "
                    "partially trusted)",
                )

    def _derive_point_id(self) -> str:
        document = {
            "plane": self.plane,
            "contract_id": self.contract_id,
            "subject_id": self.subject_id,
            "record_lines": list(self.record_lines),
            "sequence": self.sequence,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(_POINT_NAMESPACE, document, "the recovery point id document")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_point_id": self.recovery_point_id,
            "plane": self.plane,
            "contract_id": self.contract_id,
            "subject_id": self.subject_id,
            "record_lines": list(self.record_lines),
            "state_digest": self.state_digest,
            "sequence": self.sequence,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RecoveryPoint":
        """The fail-closed snapshot load: unparseable material, a
        missing provenance envelope, a digest or identity that does
        not re-derive — REJECTED WHOLE (never partially trusted, never
        best-effort loaded)."""
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.SNAPSHOT_UNVERIFIABLE,
                "the recovery point must be a mapping (unparseable snapshot "
                "material is rejected whole)",
            )
        with _wrap_consumed_error("the recovery-point deserialization"):
            missing = [
                member
                for member in (
                    "plane",
                    "contract_id",
                    "subject_id",
                    "record_lines",
                    "sequence",
                    "recorded_at",
                    "provenance",
                )
                if data.get(member) is None
            ]
            if missing:
                raise RecoveryError(
                    RecoveryReason.SNAPSHOT_UNVERIFIABLE,
                    "the recovery point is missing the members %s (provenance-"
                    "missing or malformed snapshots are rejected whole, never "
                    "best-effort loaded)" % ", ".join(missing),
                )
            return RecoveryPoint(
                plane=data.get("plane"),
                contract_id=data.get("contract_id"),
                subject_id=data.get("subject_id"),
                record_lines=tuple(data.get("record_lines") or ()),
                sequence=data.get("sequence"),
                recorded_at=data.get("recorded_at"),
                provenance=Provenance.from_dict(data.get("provenance")),
                recovery_point_id=data.get("recovery_point_id") or "",
                state_digest=data.get("state_digest") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the recovery point")


# ----------------------------------------------------------------------
# The typed restore verification (byte-exact or disclosed+reconciled)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RestoreDivergence:
    """One typed restore-divergence record (the disclosed and
    reconciled difference between the pre-failure plane and the
    recovered plane).

    ``divergence_id`` is content-derived over the full record.
    ``code`` is the frozen divergence class; ``expected_record_id``
    cites the LOST record's ORIGINAL content-derived identity (never
    renumbered, never rewritten — restoring it would FABRICATE
    history); ``resolution`` names the reconciliation base (the
    recovery point — the authoritative recovery material).  Full
    provenance on the record (LOCK-118).
    """

    divergence_id: str
    recovery_point_id: str
    plane: str
    subject_id: str
    code: str
    expected_record_id: str
    resolution: str
    provenance: Provenance
    actual_record_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "recovery_point_id", _require_id(self.recovery_point_id, "divergence.recovery_point_id")
        )
        object.__setattr__(self, "plane", _require_in(self.plane, PLANE_KINDS, "divergence.plane"))
        object.__setattr__(
            self, "subject_id", _require_id(self.subject_id, "divergence.subject_id")
        )
        object.__setattr__(
            self, "code", _require_in(self.code, RESTORE_DIVERGENCE_CODES, "divergence.code")
        )
        object.__setattr__(
            self,
            "expected_record_id",
            _require_id(self.expected_record_id, "divergence.expected_record_id"),
        )
        object.__setattr__(
            self,
            "resolution",
            _require_in(
                self.resolution, RESTORE_DIVERGENCE_RESOLUTIONS, "divergence.resolution"
            ),
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "divergence.provenance")
        )
        if self.actual_record_id:
            object.__setattr__(
                self,
                "actual_record_id",
                _require_id(self.actual_record_id, "divergence.actual_record_id"),
            )
        expected = self._derive_divergence_id()
        if not self.divergence_id:
            object.__setattr__(self, "divergence_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.divergence_id) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "divergence.divergence_id must be the content-derived "
                    "identity (sha256:...)",
                )
            if self.divergence_id != expected:
                raise RecoveryError(
                    RecoveryReason.ID_MISMATCH,
                    "divergence_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_divergence_id(self) -> str:
        document = {
            "recovery_point_id": self.recovery_point_id,
            "plane": self.plane,
            "subject_id": self.subject_id,
            "code": self.code,
            "expected_record_id": self.expected_record_id,
            "actual_record_id": self.actual_record_id,
            "resolution": self.resolution,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(
            _RESTORE_DIVERGENCE_NAMESPACE, document, "the restore-divergence id document"
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "divergence_id": self.divergence_id,
            "recovery_point_id": self.recovery_point_id,
            "plane": self.plane,
            "subject_id": self.subject_id,
            "code": self.code,
            "expected_record_id": self.expected_record_id,
            "resolution": self.resolution,
            "provenance": self.provenance.to_dict(),
        }
        if self.actual_record_id:
            data["actual_record_id"] = self.actual_record_id
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RestoreDivergence":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the restore divergence must be a mapping"
            )
        with _wrap_consumed_error("the restore-divergence deserialization"):
            return RestoreDivergence(
                divergence_id=data.get("divergence_id") or "",
                recovery_point_id=data.get("recovery_point_id"),
                plane=data.get("plane"),
                subject_id=data.get("subject_id"),
                code=data.get("code"),
                expected_record_id=data.get("expected_record_id"),
                resolution=data.get("resolution"),
                provenance=Provenance.from_dict(data.get("provenance")),
                actual_record_id=data.get("actual_record_id") or "",
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the restore divergence")


@dataclass(frozen=True)
class RestoreVerification:
    """The typed restore-verification record: the recovered plane
    equals the pre-failure plane BYTE-EXACTLY (``byte-exact``:
    ``actual_digest == expected_digest``, zero divergences), or the
    divergence is explicitly disclosed and reconciled
    (``divergence-reconciled``: one typed
    :class:`RestoreDivergence` per lost record, every resolution
    naming the recovery point as the authoritative base — never
    silently absorbed).

    ``expected_digest`` is the PRE-FAILURE plane state digest (the
    plane content at loss time); ``actual_digest`` is the RECOVERED
    plane state digest (which MUST equal the recovery point's — the
    restore rebuilds exactly its source; anything else fails closed).
    ``verified_records`` counts the recovered records whose
    content-derived identities were re-verified against the recovery
    point (the no-history-fabrication check count).
    """

    verification_id: str
    recovery_point_id: str
    plane: str
    subject_id: str
    expected_digest: str
    actual_digest: str
    outcome: str
    divergences: Tuple[RestoreDivergence, ...]
    verified_records: int
    recorded_at: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recovery_point_id",
            _require_id(self.recovery_point_id, "verification.recovery_point_id"),
        )
        object.__setattr__(self, "plane", _require_in(self.plane, PLANE_KINDS, "verification.plane"))
        object.__setattr__(
            self, "subject_id", _require_id(self.subject_id, "verification.subject_id")
        )
        object.__setattr__(
            self, "expected_digest", _require_id(self.expected_digest, "verification.expected_digest")
        )
        object.__setattr__(
            self, "actual_digest", _require_id(self.actual_digest, "verification.actual_digest")
        )
        object.__setattr__(
            self, "outcome", _require_in(self.outcome, RESTORE_OUTCOMES, "verification.outcome")
        )
        if isinstance(self.divergences, (str, bytes)) or not isinstance(
            self.divergences, (tuple, list)
        ):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "verification.divergences must be a sequence"
            )
        for i, item in enumerate(self.divergences):
            if not isinstance(item, RestoreDivergence):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "verification.divergences[%d] must be a RestoreDivergence "
                    "record" % i,
                )
        object.__setattr__(self, "divergences", tuple(self.divergences))
        object.__setattr__(
            self,
            "verified_records",
            _require_count(self.verified_records, "verification.verified_records"),
        )
        object.__setattr__(
            self, "recorded_at", _require_instant(self.recorded_at, "verification.recorded_at")
        )
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "verification.provenance"),
        )
        # the mechanically enforced outcome discipline: byte-exact
        # requires zero divergences AND equal digests; a divergence
        # outcome requires the disclosed records — a divergence
        # silently absorbed fails closed
        if self.outcome == "byte-exact":
            if self.divergences:
                raise RecoveryError(
                    RecoveryReason.RESTORE_DIVERGED,
                    "a byte-exact verification carries no divergence records "
                    "(the outcome and the disclosed records diverge)",
                )
            if self.expected_digest != self.actual_digest:
                raise RecoveryError(
                    RecoveryReason.RESTORE_DIVERGED,
                    "a byte-exact verification requires equal digests (the "
                    "pre-failure digest and the recovered digest differ)",
                )
        else:
            if not self.divergences:
                raise RecoveryError(
                    RecoveryReason.RESTORE_DIVERGED,
                    "a divergence-reconciled verification discloses its "
                    "divergence records (never a silently absorbed divergence)",
                )
            if self.expected_digest == self.actual_digest:
                raise RecoveryError(
                    RecoveryReason.RESTORE_DIVERGED,
                    "a divergence-reconciled verification requires the digests "
                    "to differ (equal digests with a divergence outcome is a "
                    "contradiction)",
                )
        expected = self._derive_verification_id()
        if not self.verification_id:
            object.__setattr__(self, "verification_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.verification_id) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "verification.verification_id must be the content-derived "
                    "identity (sha256:...)",
                )
            if self.verification_id != expected:
                raise RecoveryError(
                    RecoveryReason.ID_MISMATCH,
                    "verification_id does not match the derived identity "
                    "(tamper evidence)",
                )

    def _derive_verification_id(self) -> str:
        document = {
            "recovery_point_id": self.recovery_point_id,
            "plane": self.plane,
            "subject_id": self.subject_id,
            "expected_digest": self.expected_digest,
            "actual_digest": self.actual_digest,
            "outcome": self.outcome,
            "divergences": [d.to_dict() for d in self.divergences],
            "verified_records": self.verified_records,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(
            _RESTORE_VERIFICATION_NAMESPACE, document, "the restore-verification id document"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "recovery_point_id": self.recovery_point_id,
            "plane": self.plane,
            "subject_id": self.subject_id,
            "expected_digest": self.expected_digest,
            "actual_digest": self.actual_digest,
            "outcome": self.outcome,
            "divergences": [d.to_dict() for d in self.divergences],
            "verified_records": self.verified_records,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RestoreVerification":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the restore verification must be a mapping"
            )
        with _wrap_consumed_error("the restore-verification deserialization"):
            return RestoreVerification(
                verification_id=data.get("verification_id") or "",
                recovery_point_id=data.get("recovery_point_id"),
                plane=data.get("plane"),
                subject_id=data.get("subject_id"),
                expected_digest=data.get("expected_digest"),
                actual_digest=data.get("actual_digest"),
                outcome=data.get("outcome"),
                divergences=tuple(
                    RestoreDivergence.from_dict(d)
                    for d in data.get("divergences") or ()
                ),
                verified_records=data.get("verified_records"),
                recorded_at=data.get("recorded_at"),
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the restore verification")


# ----------------------------------------------------------------------
# The typed cross-plane reconciliation
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class CrossPlaneDivergence:
    """One typed cross-plane divergence record (the disclosed
    difference between two planes of the reconciliation — the M016
    divergence-record conventions re-expressed on this surface: full
    provenance, the loser stays cited, the disclosure IS the
    resolution).

    ``plane_a``/``plane_b`` name the divergent plane pair; ``code``
    is the frozen cross-plane divergence class; ``expected``/``actual``
    carry the divergent references (opaque values or digests); the
    resolution is ``disclosed`` (the M016 convention — only explicitly
    superseded IN THE REPLICA, never silently dropped).
    """

    divergence_id: str
    drill_id: str
    contract_id: str
    code: str
    plane_a: str
    plane_b: str
    expected: str
    actual: str
    resolution: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "drill_id", _require_id(self.drill_id, "cross.drill_id")
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "cross.contract_id")
        )
        object.__setattr__(
            self, "code", _require_in(self.code, CROSS_PLANE_DIVERGENCE_CODES, "cross.code")
        )
        object.__setattr__(
            self, "plane_a", _require_in(self.plane_a, CROSS_PLANE_NAMES, "cross.plane_a")
        )
        object.__setattr__(
            self, "plane_b", _require_in(self.plane_b, CROSS_PLANE_NAMES, "cross.plane_b")
        )
        if self.plane_a == self.plane_b:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "a cross-plane divergence names two DIFFERENT planes (found "
                "%s twice)" % self.plane_a,
            )
        object.__setattr__(
            self, "expected", _require_str(self.expected, "cross.expected", pattern=_REF_VALUE_PATTERN)
        )
        object.__setattr__(
            self, "actual", _require_str(self.actual, "cross.actual", pattern=_REF_VALUE_PATTERN)
        )
        object.__setattr__(
            self,
            "resolution",
            _require_in(self.resolution, CROSS_PLANE_RESOLUTIONS, "cross.resolution"),
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "cross.provenance")
        )
        expected = self._derive_cross_divergence_id()
        if not self.divergence_id:
            object.__setattr__(self, "divergence_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.divergence_id) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "cross.divergence_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.divergence_id != expected:
                raise RecoveryError(
                    RecoveryReason.ID_MISMATCH,
                    "divergence_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_cross_divergence_id(self) -> str:
        document = {
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "code": self.code,
            "plane_a": self.plane_a,
            "plane_b": self.plane_b,
            "expected": self.expected,
            "actual": self.actual,
            "resolution": self.resolution,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(
            _CROSS_PLANE_DIVERGENCE_NAMESPACE, document, "the cross-plane divergence id document"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "divergence_id": self.divergence_id,
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "code": self.code,
            "plane_a": self.plane_a,
            "plane_b": self.plane_b,
            "expected": self.expected,
            "actual": self.actual,
            "resolution": self.resolution,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "CrossPlaneDivergence":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the cross-plane divergence must be a mapping"
            )
        with _wrap_consumed_error("the cross-plane-divergence deserialization"):
            return CrossPlaneDivergence(
                divergence_id=data.get("divergence_id") or "",
                drill_id=data.get("drill_id"),
                contract_id=data.get("contract_id"),
                code=data.get("code"),
                plane_a=data.get("plane_a"),
                plane_b=data.get("plane_b"),
                expected=data.get("expected"),
                actual=data.get("actual"),
                resolution=data.get("resolution"),
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the cross-plane divergence")


@dataclass(frozen=True)
class PlaneReconciliation:
    """The typed cross-plane reconciliation record: the
    contracts/journal/evidence planes converge after a drill (with
    typed divergence records for every disclosed difference).

    ``constraint_fingerprint`` is the CONTRACT's own LOCK-108
    fingerprint (consumed BY REFERENCE from the live contract — the
    contracts-plane convergence material; never recomputed).  ``plane_
    digests`` carries the post-drill journal-plane state digests.
    ``evidence_record_ids`` cites the drill-produced LOCK-106 evidence
    records (preserved — the reconciliation verifies each is present
    on the evidence plane with its identity intact).
    ``divergences`` carries the typed cross-plane divergence records
    (empty iff ``converged``).  ``accepted_resync`` preserves the
    accepted M016 :class:`~localfirst.model.ResyncResult` serialization
    VERBATIM (consumed BY REFERENCE where it fits — never
    re-interpreted, never re-derived) when the reconciliation drove
    the accepted resynchronization; None otherwise.
    """

    reconciliation_id: str
    drill_id: str
    contract_id: str
    constraint_fingerprint: str
    plane_digests: Tuple[Tuple[str, str], ...]
    evidence_record_ids: Tuple[str, ...]
    divergences: Tuple[CrossPlaneDivergence, ...]
    accepted_resync: Optional[Mapping[str, Any]]
    outcome: str
    recorded_at: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "drill_id", _require_id(self.drill_id, "reconciliation.drill_id")
        )
        object.__setattr__(
            self,
            "contract_id",
            _require_id(self.contract_id, "reconciliation.contract_id"),
        )
        object.__setattr__(
            self,
            "constraint_fingerprint",
            _require_id(
                self.constraint_fingerprint, "reconciliation.constraint_fingerprint"
            ),
        )
        object.__setattr__(
            self,
            "plane_digests",
            _normalize_digest_pairs(self.plane_digests, "reconciliation.plane_digests"),
        )
        if isinstance(self.evidence_record_ids, (str, bytes)) or not isinstance(
            self.evidence_record_ids, (tuple, list)
        ):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "reconciliation.evidence_record_ids must be a sequence",
            )
        ids = []
        for i, value in enumerate(self.evidence_record_ids):
            ids.append(_require_str(value, "reconciliation.evidence_record_ids[%d]" % i))
        object.__setattr__(self, "evidence_record_ids", tuple(ids))
        if isinstance(self.divergences, (str, bytes)) or not isinstance(
            self.divergences, (tuple, list)
        ):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "reconciliation.divergences must be a sequence",
            )
        for i, item in enumerate(self.divergences):
            if not isinstance(item, CrossPlaneDivergence):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "reconciliation.divergences[%d] must be a "
                    "CrossPlaneDivergence record" % i,
                )
        object.__setattr__(self, "divergences", tuple(self.divergences))
        if self.accepted_resync is not None and not isinstance(
            self.accepted_resync, Mapping
        ):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "reconciliation.accepted_resync must be the accepted "
                "ResyncResult serialization (a mapping) or None",
            )
        object.__setattr__(
            self,
            "outcome",
            _require_in(self.outcome, RECONCILIATION_OUTCOMES, "reconciliation.outcome"),
        )
        object.__setattr__(
            self,
            "recorded_at",
            _require_instant(self.recorded_at, "reconciliation.recorded_at"),
        )
        object.__setattr__(
            self,
            "provenance",
            _require_provenance(self.provenance, "reconciliation.provenance"),
        )
        # the mechanically enforced outcome discipline: converged
        # carries zero divergence records; a divergence-disclosed
        # outcome carries them (never a silently absorbed divergence)
        if self.outcome == "converged" and self.divergences:
            raise RecoveryError(
                RecoveryReason.PLANE_MISMATCH,
                "a converged reconciliation carries no divergence records "
                "(the outcome and the disclosed records diverge)",
            )
        if self.outcome == "divergence-disclosed" and not self.divergences:
            raise RecoveryError(
                RecoveryReason.PLANE_MISMATCH,
                "a divergence-disclosed reconciliation discloses its "
                "divergence records (never a silently absorbed divergence)",
            )
        expected = self._derive_reconciliation_id()
        if not self.reconciliation_id:
            object.__setattr__(self, "reconciliation_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.reconciliation_id) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "reconciliation.reconciliation_id must be the "
                    "content-derived identity (sha256:...)",
                )
            if self.reconciliation_id != expected:
                raise RecoveryError(
                    RecoveryReason.ID_MISMATCH,
                    "reconciliation_id does not match the derived identity "
                    "(tamper evidence)",
                )

    def _derive_reconciliation_id(self) -> str:
        document = {
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "constraint_fingerprint": self.constraint_fingerprint,
            "plane_digests": [
                [plane, digest] for plane, digest in self.plane_digests
            ],
            "evidence_record_ids": list(self.evidence_record_ids),
            "divergences": [d.to_dict() for d in self.divergences],
            "accepted_resync": dict(self.accepted_resync)
            if self.accepted_resync is not None
            else None,
            "outcome": self.outcome,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(
            _RECONCILIATION_NAMESPACE, document, "the reconciliation id document"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reconciliation_id": self.reconciliation_id,
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "constraint_fingerprint": self.constraint_fingerprint,
            "plane_digests": [
                [plane, digest] for plane, digest in self.plane_digests
            ],
            "evidence_record_ids": list(self.evidence_record_ids),
            "divergences": [d.to_dict() for d in self.divergences],
            "accepted_resync": dict(self.accepted_resync)
            if self.accepted_resync is not None
            else None,
            "outcome": self.outcome,
            "recorded_at": self.recorded_at,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "PlaneReconciliation":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the reconciliation must be a mapping"
            )
        with _wrap_consumed_error("the reconciliation deserialization"):
            return PlaneReconciliation(
                reconciliation_id=data.get("reconciliation_id") or "",
                drill_id=data.get("drill_id"),
                contract_id=data.get("contract_id"),
                constraint_fingerprint=data.get("constraint_fingerprint"),
                plane_digests=tuple(
                    (pair[0], pair[1]) for pair in data.get("plane_digests") or ()
                ),
                evidence_record_ids=tuple(data.get("evidence_record_ids") or ()),
                divergences=tuple(
                    CrossPlaneDivergence.from_dict(d)
                    for d in data.get("divergences") or ()
                ),
                accepted_resync=data.get("accepted_resync"),
                outcome=data.get("outcome"),
                recorded_at=data.get("recorded_at"),
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the plane reconciliation")


# ----------------------------------------------------------------------
# The drill result (the typed drill outcome)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class DrillResult:
    """The typed drill outcome: the recovery points constructed (plane
    by plane), the restore verifications (byte-exact or
    divergence-reconciled), the cross-plane reconciliation, and the
    MEASURED operation counts against the DECLARED budget (the
    deterministic RTO accounting — never a timing measurement).

    ``drill_run_id`` is content-derived over the full outcome (same
    drill inputs -> the byte-identical run).  ``recovery_points``
    carries (plane, recovery_point_id) pairs in step order;
    ``restorations`` carries the restore verifications in step order;
    ``reconciliation`` is None when the plan carries no reconcile
    step.  ``completed_at`` is the last executed step's injected
    instant (deterministic — never wall clock).
    """

    drill_run_id: str
    drill_id: str
    contract_id: str
    recovery_points: Tuple[Tuple[str, str], ...]
    restorations: Tuple[RestoreVerification, ...]
    reconciliation: Optional[PlaneReconciliation]
    measured_counts: OperationCounts
    declared_budget: OperationBudget
    completed_at: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "drill_id", _require_id(self.drill_id, "run.drill_id")
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "run.contract_id")
        )
        if isinstance(self.recovery_points, (str, bytes)) or not isinstance(
            self.recovery_points, (tuple, list)
        ):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "run.recovery_points must be a sequence"
            )
        points = []
        for i, item in enumerate(self.recovery_points):
            if isinstance(item, (str, bytes)) or not isinstance(item, (tuple, list)) or len(item) != 2:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "run.recovery_points[%d] must be a (plane, point id) pair" % i,
                )
            plane = _require_in(item[0], PLANE_KINDS, "run.recovery_points[%d][0]" % i)
            point_id = _require_id(item[1], "run.recovery_points[%d][1]" % i)
            points.append((plane, point_id))
        object.__setattr__(self, "recovery_points", tuple(points))
        if isinstance(self.restorations, (str, bytes)) or not isinstance(
            self.restorations, (tuple, list)
        ):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "run.restorations must be a sequence"
            )
        for i, item in enumerate(self.restorations):
            if not isinstance(item, RestoreVerification):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "run.restorations[%d] must be a RestoreVerification record" % i,
                )
        object.__setattr__(self, "restorations", tuple(self.restorations))
        if self.reconciliation is not None and not isinstance(
            self.reconciliation, PlaneReconciliation
        ):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "run.reconciliation must be a PlaneReconciliation record or None",
            )
        if not isinstance(self.measured_counts, OperationCounts):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "run.measured_counts must be an OperationCounts record",
            )
        if not isinstance(self.declared_budget, OperationBudget):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "run.declared_budget must be an OperationBudget record",
            )
        # defense in depth: a finished run whose measured counts exceed
        # the declared budget fails closed (the engine already fails at
        # the increment point; a hand-built record cannot claim an
        # over-budget run as green)
        exceeded = self.measured_counts.exceeds(self.declared_budget)
        if exceeded is not None:
            raise RecoveryError(
                RecoveryReason.RTO_EXCEEDED,
                "the drill run's measured %s exceeds the declared budget "
                "(%d > %d — the recovery-time bound is a declared operation "
                "count, never wall clock)"
                % (
                    exceeded,
                    getattr(self.measured_counts, exceeded),
                    getattr(self.declared_budget, exceeded),
                ),
            )
        object.__setattr__(
            self, "completed_at", _require_instant(self.completed_at, "run.completed_at")
        )
        object.__setattr__(
            self, "provenance", _require_provenance(self.provenance, "run.provenance")
        )
        expected = self._derive_run_id()
        if not self.drill_run_id:
            object.__setattr__(self, "drill_run_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.drill_run_id) is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "run.drill_run_id must be the content-derived identity "
                    "(sha256:...)",
                )
            if self.drill_run_id != expected:
                raise RecoveryError(
                    RecoveryReason.ID_MISMATCH,
                    "drill_run_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_run_id(self) -> str:
        document = {
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "recovery_points": [
                [plane, point_id] for plane, point_id in self.recovery_points
            ],
            "restorations": [v.to_dict() for v in self.restorations],
            "reconciliation": self.reconciliation.to_dict()
            if self.reconciliation is not None
            else None,
            "measured_counts": self.measured_counts.to_dict(),
            "declared_budget": self.declared_budget.to_dict(),
            "completed_at": self.completed_at,
            "provenance": self.provenance.to_dict(),
        }
        return _derive_id(_DRILL_RUN_NAMESPACE, document, "the drill-run id document")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drill_run_id": self.drill_run_id,
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "recovery_points": [
                [plane, point_id] for plane, point_id in self.recovery_points
            ],
            "restorations": [v.to_dict() for v in self.restorations],
            "reconciliation": self.reconciliation.to_dict()
            if self.reconciliation is not None
            else None,
            "measured_counts": self.measured_counts.to_dict(),
            "declared_budget": self.declared_budget.to_dict(),
            "completed_at": self.completed_at,
            "provenance": self.provenance.to_dict(),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "DrillResult":
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT, "the drill result must be a mapping"
            )
        with _wrap_consumed_error("the drill-result deserialization"):
            return DrillResult(
                drill_run_id=data.get("drill_run_id") or "",
                drill_id=data.get("drill_id"),
                contract_id=data.get("contract_id"),
                recovery_points=tuple(
                    (pair[0], pair[1]) for pair in data.get("recovery_points") or ()
                ),
                restorations=tuple(
                    RestoreVerification.from_dict(v)
                    for v in data.get("restorations") or ()
                ),
                reconciliation=PlaneReconciliation.from_dict(data["reconciliation"])
                if data.get("reconciliation") is not None
                else None,
                measured_counts=OperationCounts.from_dict(data.get("measured_counts")),
                declared_budget=OperationBudget.from_dict(data.get("declared_budget")),
                completed_at=data.get("completed_at"),
                provenance=Provenance.from_dict(data.get("provenance")),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the drill result")
