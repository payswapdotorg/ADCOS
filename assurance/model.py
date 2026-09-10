"""ADCOS closed-loop assurance model (M005 — Evidence and Assurance;
LOCK-107).

The contract-level closed-loop assurance evaluation domain:

- the FROZEN assurance state vocabulary of Architecture 1.1 §9 —
  ``compliant``, ``degraded``, ``violated``, ``unknown`` (stale/absent
  evidence), ``failed``, ``deliberately_terminated`` — exactly the
  §9 list, no state outside it (:data:`ASSURANCE_STATES`);
- :class:`AssuranceObligation` — the TYPED obligation record the
  M005 authority owns.  The canonical ``ConnectivityContract``
  carries assurance obligations as OPAQUE references
  (``ref_kind="assurance-obligation"``); this module resolves those
  reference values to typed obligation records whose content-derived
  ids equal them (1:1, fail-closed both directions — the CONTRACT
  alone decides WHICH obligations apply; the assurance authority
  alone owns their SEMANTICS; there is no second contract model).
  The obligation record is CONTRACT-AGNOSTIC by design (LOCK-117:
  the contract's opaque reference is the binding — an obligation's
  identity is its semantics, so two contracts may reference the
  same obligation record); evaluation scopes evidence to the
  evaluated contract through the evidence records' own contract
  references.
- :class:`AssuranceReason` / :class:`AssuranceEvaluation` — the
  typed, deterministic evaluation outcome.  Evaluation is a PURE
  function of (contract, obligation set, evidence set, injected
  instant): same inputs -> same state, same reasons, same
  content-derived evaluation id.  Violations/degradations carry typed
  reason records referencing the specific obligation and the evidence
  (or evidence absence) that triggered them.

Semantics (frozen, disclosed in ``docs/M005-evidence.md``):

- **Contract-state dispatch.** ``TERMINATED`` short-circuits to
  ``deliberately_terminated`` and ``FAILED`` to ``failed`` — no
  obligation re-evaluation, no side effects (terminal contracts
  reject commands).  The §9 assurance-evaluable lifecycle states
  (``CONTRACT_ACTIVE``, ``EXECUTION_ACTIVE``, ``DELIVERY``,
  ``ASSURED``, ``DEGRADED``) evaluate their obligations; every other
  contract state (pre-activation or the post-assurance commercial
  tail — LOCK-113 territory) fails closed NOT_EVALUABLE.
- **Per-obligation evidence matching** is by (typed evidence record
  class, contract id, subject ref, evidence name) with NO time
  travel: records produced after the evaluation instant are ignored.
- **Eligibility** (validity at the evaluation instant): observations
  must be fresh (instant window); commitments must cover the instant;
  attestations must be unexpired; claims carry no expiry (a claim is
  an assertion, not a measurement — the LOCK-106 type distinction is
  structural).
- **Latest-evidence-wins**: the obligation evaluates against the most
  recent eligible record (max by (instant, record_id)) — the current
  evidence is the current truth; an older satisfying record never
  masks a newer breaching one.
- **Breach classes**: a valid record whose value is outside the
  obligation bound (floor: value >= bound; ceiling: value <= bound)
  breaches at the obligation severity; the total absence of VALID
  evidence after the obligation's explicit ``evidence_deadline``
  breaches at the severity (triggered by the evidence ABSENCE).
  Stale/absent evidence WITHOUT a fired deadline yields ``unknown``
  — evidence-class honesty: unknown is never treated as compliant.
- **Aggregation** is worst-of, deterministic:
  violated > degraded > unknown > compliant.

Determinism: content-derived ids over canonical JSON; injected
RFC 3339 UTC instants only (staleness is instant-threshold-based on
injected instants, never wall clock); no randomness, no UUIDs, no
network; sorted iteration; fail-closed typed errors with stable
codes; PYTHONHASHSEED-safe.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from contracts import (
    CONTRACT_STATES,
    ConnectivityContract,
)
from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from evidence.errors import EvidenceError  # noqa: F401  (re-exported seam)
from evidence.model import (
    ATTESTATION_KINDS,
    CLAIM_KINDS,
    COMMITMENT_KINDS,
    MAX_EVIDENCE_VALUE,
    OBSERVATION_METRICS,
    AttestationEvidence,
    ClaimEvidence,
    CommitmentEvidence,
    ObservationEvidence,
)

from .errors import AssuranceError, AssuranceReasonCode

# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The FROZEN assurance state vocabulary (Architecture 1.1 §9):
#: compliant, degraded, violated, unknown (stale/absent evidence),
#: failed, deliberately terminated.  EXACTLY the §9 list — no state
#: outside the vocabulary ever leaves the evaluation.
ASSURANCE_STATES: Tuple[str, ...] = (
    "compliant",
    "degraded",
    "violated",
    "unknown",
    "failed",
    "deliberately_terminated",
)

#: The frozen obligation-kind vocabulary — one kind per LOCK-106
#: evidence type (every typed evidence class backs exactly one
#: obligation semantics).
OBLIGATION_KINDS: Tuple[str, ...] = (
    "observation-bound",
    "claim-level",
    "commitment-window",
    "attestation-required",
)

#: The frozen breach-severity vocabulary: ``hard`` breaches aggregate
#: to ``violated``; ``degradable`` breaches aggregate to ``degraded``
#: (the explicit, recoverable §9 degraded state).
OBLIGATION_SEVERITIES: Tuple[str, ...] = (
    "hard",
    "degradable",
)

#: The frozen bound vocabulary: ``floor`` (value >= bound satisfies)
#: and ``ceiling`` (value <= bound satisfies).
BOUND_KINDS: Tuple[str, ...] = (
    "floor",
    "ceiling",
)

#: The frozen reason-kind vocabulary of evaluation reason records.
REASON_KINDS: Tuple[str, ...] = (
    "satisfied",
    "value-breach",
    "absence-breach",
    "stale-evidence",
    "absent-evidence",
    "contract-failed",
    "contract-terminated",
)

#: The contract lifecycle states the assurance loop evaluates (the
#: active delivery/assurance segment of the frozen §11 lifecycle).
EVALUABLE_CONTRACT_STATES: Tuple[str, ...] = (
    "CONTRACT_ACTIVE",
    "EXECUTION_ACTIVE",
    "DELIVERY",
    "ASSURED",
    "DEGRADED",
)

#: The contract lifecycle states that short-circuit the evaluation
#: with an honest terminal verdict (no re-evaluation, no side
#: effects): TERMINATED -> deliberately_terminated; FAILED -> failed.
SHORT_CIRCUIT_CONTRACT_STATES: Tuple[str, ...] = (
    "TERMINATED",
    "FAILED",
)


def _check_state_vocabularies() -> None:
    """Import-time consistency guard against contract-vocabulary
    drift: every state the assurance dispatch references must exist
    in the CONSUMED contracts vocabulary (fail loud, never silently
    mis-dispatch)."""
    known = set(CONTRACT_STATES)
    for state in EVALUABLE_CONTRACT_STATES + SHORT_CIRCUIT_CONTRACT_STATES:
        if state not in known:
            raise AssuranceError(
                AssuranceReasonCode.VOCABULARY,
                "assurance dispatch references contract state %r outside "
                "the consumed contracts vocabulary — the frozen "
                "vocabularies have drifted" % state,
            )


_check_state_vocabularies()


#: The evidence record class backing each obligation kind (LOCK-106:
#: one typed evidence class per obligation semantics).
_KIND_TO_RECORD_CLASS: Dict[str, type] = {
    "observation-bound": ObservationEvidence,
    "claim-level": ClaimEvidence,
    "commitment-window": CommitmentEvidence,
    "attestation-required": AttestationEvidence,
}

#: The per-kind evidence-name vocabulary (the obligation's watched
#: metric / claim kind / commitment kind / attestation kind).
_KIND_TO_NAME_VOCABULARY: Dict[str, Tuple[str, ...]] = {
    "observation-bound": OBSERVATION_METRICS,
    "claim-level": CLAIM_KINDS,
    "commitment-window": COMMITMENT_KINDS,
    "attestation-required": ATTESTATION_KINDS,
}

_OBLIGATION_ID_PREFIX = "assurance:obligation:"
_EVALUATION_ID_PREFIX = "assurance:evaluation:"

_REF_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,256}$")
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")
_SECRET_TOKEN_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "%s must be a non-empty str (got %s)" % (label, type(value).__name__),
        )
    return value


def _require_ref_text(value: object, label: str) -> str:
    text = _require_str(value, label)
    if not _REF_PATTERN.match(text):
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "%s must match the reference grammar [A-Za-z0-9._:+/-]{1,256}" % label,
        )
    if _SECRET_VALUE_PATTERN.match(text) or _SECRET_TOKEN_PATTERN.search(text):
        raise AssuranceError(
            AssuranceReasonCode.SECRET_REJECTED,
            "%s is secret-shaped material; secrets never enter assurance "
            "records (LOCK-119)" % label,
        )
    return text


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INSTANT,
            "%s must be an explicit RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INSTANT,
            "%s must be an explicit RFC 3339 UTC instant: %s"
            % (label, str(error)[:120]),
        ) from None
    return value


def _require_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "%s must be an int (got %s)" % (label, type(value).__name__),
        )
    if value < 0 or value > MAX_EVIDENCE_VALUE:
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "%s must be within 0..%d (got %d)" % (label, MAX_EVIDENCE_VALUE, value),
        )
    return value


def _require_tuple(value: object, label: str) -> Tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "%s must be a tuple or list (got %s)" % (label, type(value).__name__),
        )
    return tuple(value)


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    text = _require_str(value, label)
    if text not in vocabulary:
        raise AssuranceError(
            AssuranceReasonCode.VOCABULARY,
            "%s must be one of the frozen vocabulary %s (got %r)"
            % (label, list(vocabulary), text),
        )
    return text


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, str(error)[:120]),
        ) from None


def _derive_over(document: Mapping[str, Any]) -> str:
    material = dict(document)
    material.pop("id", None)
    return hashlib.sha256(
        _canonical_bytes(material, "assurance identity")
    ).hexdigest()


# ----------------------------------------------------------------------
# The typed obligation record
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AssuranceObligation:
    """One typed assurance obligation the M005 authority owns.

    The canonical contract carries this obligation as an OPAQUE
    reference whose value equals :attr:`obligation_id` (the
    content-derived identity — LOCK-117: the contract stores the
    reference, the assurance authority owns the semantics).  The
    obligation record is CONTRACT-AGNOSTIC: its identity is its
    semantics (kind, subject, name, bound, severity, deadline,
    producer), so the SAME obligation record may be referenced by
    more than one contract — the contract's reference is the
    binding, and evaluation scopes the evidence by the evidence
    records' own contract references.

    Fields:

    - ``obligation_kind`` — the evaluation semantics (one per LOCK-106
      evidence type);
    - ``subject_ref`` — what the obligation watches (the subject
      reference the matching evidence must carry);
    - ``evidence_name`` — the watched metric / claim kind / commitment
      kind / attestation kind (per-kind frozen vocabulary);
    - ``bound_kind`` + ``bound_value`` — the optional value bound
      (floor: value >= bound satisfies; ceiling: value <= bound
      satisfies; absent: valid-evidence existence satisfies);
    - ``severity`` — ``hard`` (breach aggregates to ``violated``) or
      ``degradable`` (breach aggregates to ``degraded``);
    - ``evidence_deadline`` — the optional instant by which valid
      evidence must exist (absence after the deadline breaches at the
      severity — triggered by the evidence ABSENCE);
    - ``producer`` + ``provenance_refs`` — the obligation issuer and
      decision lineage (LOCK-118).
    """

    obligation_kind: str
    subject_ref: str
    evidence_name: str
    severity: str
    producer: str
    bound_kind: Optional[str] = None
    bound_value: Optional[int] = None
    evidence_deadline: Optional[str] = None
    provenance_refs: Tuple[str, ...] = ()
    obligation_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "obligation_kind",
            _require_in(self.obligation_kind, OBLIGATION_KINDS, "obligation_kind"),
        )
        object.__setattr__(
            self, "subject_ref", _require_ref_text(self.subject_ref, "subject_ref")
        )
        object.__setattr__(
            self,
            "evidence_name",
            _require_in(
                self.evidence_name,
                _KIND_TO_NAME_VOCABULARY[self.obligation_kind],
                "evidence_name",
            ),
        )
        object.__setattr__(
            self, "severity", _require_in(self.severity, OBLIGATION_SEVERITIES, "severity")
        )
        object.__setattr__(
            self, "producer", _require_ref_text(self.producer, "producer")
        )
        # the bound pair: both members or neither
        if (self.bound_kind is None) != (self.bound_value is None):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "bound_kind and bound_value must be provided together "
                "(got kind=%r, value=%r)" % (self.bound_kind, self.bound_value),
            )
        if self.bound_kind is not None:
            object.__setattr__(
                self, "bound_kind", _require_in(self.bound_kind, BOUND_KINDS, "bound_kind")
            )
        if self.bound_value is not None:
            object.__setattr__(
                self, "bound_value", _require_int(self.bound_value, "bound_value")
            )
        if self.evidence_deadline is not None:
            object.__setattr__(
                self,
                "evidence_deadline",
                _require_instant(self.evidence_deadline, "evidence_deadline"),
            )
        refs = _require_tuple(self.provenance_refs, "provenance_refs")
        object.__setattr__(
            self,
            "provenance_refs",
            tuple(
                _require_ref_text(ref, "provenance_refs[%d]" % i)
                for i, ref in enumerate(refs)
            ),
        )
        expected = _OBLIGATION_ID_PREFIX + _derive_over(self.to_id_material())
        if not self.obligation_id:
            object.__setattr__(self, "obligation_id", expected)
        elif self.obligation_id != expected:
            raise AssuranceError(
                AssuranceReasonCode.ID_MISMATCH,
                "obligation_id must equal the content-derived derivation — "
                "a tampered or miscomputed id is rejected",
            )

    def to_id_material(self) -> Dict[str, Any]:
        return {
            "obligation_kind": self.obligation_kind,
            "subject_ref": self.subject_ref,
            "evidence_name": self.evidence_name,
            "severity": self.severity,
            "producer": self.producer,
            "bound_kind": self.bound_kind,
            "bound_value": self.bound_value,
            "evidence_deadline": self.evidence_deadline,
            "provenance_refs": list(self.provenance_refs),
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.to_id_material(), obligation_id=self.obligation_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssuranceObligation":
        if not isinstance(data, Mapping):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "obligation DATA must be a mapping (got %s)" % type(data).__name__,
            )
        return cls(
            obligation_kind=data.get("obligation_kind"),
            subject_ref=data.get("subject_ref"),
            evidence_name=data.get("evidence_name"),
            severity=data.get("severity"),
            producer=data.get("producer"),
            bound_kind=data.get("bound_kind"),
            bound_value=data.get("bound_value"),
            evidence_deadline=data.get("evidence_deadline"),
            provenance_refs=tuple(data.get("provenance_refs") or ()),
            obligation_id=data.get("obligation_id") or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "obligation record")


# ----------------------------------------------------------------------
# Typed reason records + the evaluation record
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AssuranceReason:
    """One typed evaluation reason.  Breach reasons reference the
    specific obligation and the evidence (or evidence absence) that
    triggered them; satisfied/stale/absent reasons give the honest
    per-obligation evidence state.  The detail text is stable,
    machine-readable, and never carries raw exception text."""

    reason_kind: str
    obligation_id: str
    evidence_id: str
    severity: str
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reason_kind", _require_in(self.reason_kind, REASON_KINDS, "reason_kind")
        )
        # obligation_id may be empty ONLY for contract-level short-circuit
        # reasons; evidence_id may be empty ONLY for absence/stale-free
        # reasons (the absence IS the trigger — no evidence to cite).
        for label, value in (
            ("reason.obligation_id", self.obligation_id),
            ("reason.evidence_id", self.evidence_id),
        ):
            if not isinstance(value, str):
                raise AssuranceError(
                    AssuranceReasonCode.INVALID_INPUT,
                    "%s must be a str (got %s)" % (label, type(value).__name__),
                )
        if self.severity:
            object.__setattr__(
                self, "severity", _require_in(self.severity, OBLIGATION_SEVERITIES, "reason.severity")
            )
        else:
            object.__setattr__(self, "severity", "")
        object.__setattr__(
            self, "detail", _require_str(self.detail, "reason.detail")
        )
        if _SECRET_VALUE_PATTERN.match(self.detail) or _SECRET_TOKEN_PATTERN.search(self.detail):
            raise AssuranceError(
                AssuranceReasonCode.SECRET_REJECTED,
                "reason.detail is secret-shaped material (LOCK-119)",
            )
        # cross-field discipline: only contract-level short-circuit
        # reasons (contract-failed / contract-terminated) may leave the
        # obligation reference empty.
        if not self.obligation_id and self.reason_kind not in (
            "contract-failed",
            "contract-terminated",
        ):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "reason.obligation_id is required for %s reasons (only "
                "contract-level short-circuit reasons carry none)"
                % self.reason_kind,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason_kind": self.reason_kind,
            "obligation_id": self.obligation_id,
            "evidence_id": self.evidence_id,
            "severity": self.severity,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssuranceReason":
        if not isinstance(data, Mapping):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "reason DATA must be a mapping (got %s)" % type(data).__name__,
            )
        return cls(
            reason_kind=data.get("reason_kind"),
            obligation_id=data.get("obligation_id"),
            evidence_id=data.get("evidence_id"),
            severity=data.get("severity") or "",
            detail=data.get("detail"),
        )


@dataclass(frozen=True)
class AssuranceEvaluation:
    """The typed, deterministic outcome of one closed-loop evaluation.

    ``evaluation_id`` is content-derived over the canonical result
    (contract, instant, state, reasons) — the same inputs always
    produce the byte-identical evaluation (tamper-evident, replayable
    as the assurance decision reference the contract's
    ``record-assurance`` command cites)."""

    contract_ref: str
    evaluated_at: str
    state: str
    reasons: Tuple[AssuranceReason, ...]
    evaluation_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_ref", _require_ref_text(self.contract_ref, "evaluation.contract_ref")
        )
        object.__setattr__(
            self, "evaluated_at", _require_instant(self.evaluated_at, "evaluation.evaluated_at")
        )
        object.__setattr__(
            self, "state", _require_in(self.state, ASSURANCE_STATES, "evaluation.state")
        )
        reasons = _require_tuple(self.reasons, "evaluation.reasons")
        normalized = tuple(
            r if isinstance(r, AssuranceReason) else AssuranceReason.from_dict(r)
            for r in reasons
        )
        object.__setattr__(self, "reasons", normalized)
        expected = _EVALUATION_ID_PREFIX + _derive_over(self.to_id_material())
        if not self.evaluation_id:
            object.__setattr__(self, "evaluation_id", expected)
        elif self.evaluation_id != expected:
            raise AssuranceError(
                AssuranceReasonCode.ID_MISMATCH,
                "evaluation_id must equal the content-derived derivation — "
                "a tampered or miscomputed id is rejected",
            )

    def to_id_material(self) -> Dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "evaluated_at": self.evaluated_at,
            "state": self.state,
            "reasons": [r.to_dict() for r in self.reasons],
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.to_id_material(), evaluation_id=self.evaluation_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssuranceEvaluation":
        if not isinstance(data, Mapping):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "evaluation DATA must be a mapping (got %s)" % type(data).__name__,
            )
        return cls(
            contract_ref=data.get("contract_ref"),
            evaluated_at=data.get("evaluated_at"),
            state=data.get("state"),
            reasons=tuple(data.get("reasons") or ()),
            evaluation_id=data.get("evaluation_id") or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "evaluation record")


# ----------------------------------------------------------------------
# Obligation resolution (contract references <-> typed obligations)
# ----------------------------------------------------------------------


def to_contract_references(
    obligations: Sequence[AssuranceObligation],
    issuer: str = "assurance:m005",
) -> Tuple[Any, ...]:
    """Build the canonical contract-domain opaque references for a
    set of typed obligations (``ref_kind="assurance-obligation"``,
    value = the content-derived obligation id).  This is the ONE
    disclosed point where assurance-domain obligations bind into a
    ``CreateContract`` — the contract stores the references; it never
    interprets them (LOCK-117)."""
    from contracts import OpaqueReference, Provenance  # by-reference consumption

    refs = []
    for obligation in obligations:
        if not isinstance(obligation, AssuranceObligation):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "to_contract_references requires AssuranceObligation records "
                "(got %s)" % type(obligation).__name__,
            )
        refs.append(
            OpaqueReference(
                ref_kind="assurance-obligation",
                value=obligation.obligation_id,
                provenance=Provenance(issuer=issuer),
            )
        )
    return tuple(refs)


def resolve_obligations(
    contract: ConnectivityContract, obligations: Sequence[AssuranceObligation]
) -> Tuple[AssuranceObligation, ...]:
    """Resolve the contract's opaque assurance-obligation references
    against the typed obligations (fail-closed 1:1):

    - every reference value the contract carries must resolve to a
      typed obligation (OBLIGATION_UNRESOLVED — the contract demands
      an obligation the assurance authority does not carry);
    - every typed obligation must be referenced by the contract
      (OBLIGATION_NOT_REFERENCED — no second obligation model: the
      contract alone decides which obligations apply).

    The contract's opaque reference IS the binding (LOCK-117: the
    obligation record is contract-agnostic semantics; the reference
    binds it into this contract's scope).  Returns the obligations
    in deterministic obligation-id order.
    """
    if not isinstance(contract, ConnectivityContract):
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "resolve_obligations requires a canonical ConnectivityContract "
            "(got %s) — the contract domain is consumed by reference, "
            "never duplicated" % type(contract).__name__,
        )
    records = _require_tuple(obligations, "obligations")
    for record in records:
        if not isinstance(record, AssuranceObligation):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "obligations must be AssuranceObligation records (got %s)"
                % type(record).__name__,
            )
    reference_values = {
        reference.value
        for reference in contract.assurance_obligations
        if reference.ref_kind == "assurance-obligation"
    }
    obligation_ids = {record.obligation_id for record in records}
    unresolved = sorted(reference_values - obligation_ids)
    if unresolved:
        raise AssuranceError(
            AssuranceReasonCode.OBLIGATION_UNRESOLVED,
            "the contract references %d assurance obligation(s) the "
            "assurance authority does not carry (first: %s)" % (len(unresolved), unresolved[0][:48]),
        )
    not_referenced = sorted(obligation_ids - reference_values)
    if not_referenced:
        raise AssuranceError(
            AssuranceReasonCode.OBLIGATION_NOT_REFERENCED,
            "%d typed obligation(s) are not referenced by this contract "
            "(first: %s) — the contract alone decides which obligations "
            "apply" % (len(not_referenced), not_referenced[0][:48]),
        )
    return tuple(sorted(records, key=lambda record: record.obligation_id))


# ----------------------------------------------------------------------
# The evaluation kernel (LOCK-107)
# ----------------------------------------------------------------------


def _matches_obligation(record: Any, obligation: AssuranceObligation) -> bool:
    """Typed matching: the record class, subject, and name must all
    match the obligation (LOCK-106: the evidence type is part of the
    match — no cross-type satisfaction).  Contract scoping happens
    BEFORE matching (the evidence records' own contract references
    scope them to the evaluated contract)."""
    expected_class = _KIND_TO_RECORD_CLASS[obligation.obligation_kind]
    if type(record) is not expected_class:
        return False
    if record.subject_ref != obligation.subject_ref:
        return False
    name_member = {
        "observation-bound": "metric",
        "claim-level": "claim_kind",
        "commitment-window": "commitment_kind",
        "attestation-required": "attestation_kind",
    }[obligation.obligation_kind]
    return getattr(record, name_member) == obligation.evidence_name


def _is_eligible(record: Any, obligation: AssuranceObligation, at: Any) -> bool:
    """Validity at the evaluation instant (the derived-staleness
    discipline): observations must be fresh, commitments must cover
    the instant, attestations must be unexpired; claims carry no
    expiry (an assertion, not a measurement)."""
    if obligation.obligation_kind == "observation-bound":
        return parse_instant(record.freshness_until) > at
    if obligation.obligation_kind == "commitment-window":
        return parse_instant(record.valid_from) <= at < parse_instant(record.valid_until)
    if obligation.obligation_kind == "attestation-required":
        return parse_instant(record.valid_until) > at
    return True  # claim-level


def _value_of(record: Any, obligation: AssuranceObligation) -> int:
    if obligation.obligation_kind == "observation-bound":
        return record.value
    if obligation.obligation_kind == "claim-level":
        return record.asserted_value
    if obligation.obligation_kind == "commitment-window":
        return record.committed_value
    return record.attested_value  # attestation-required


def _satisfies_bound(record: Any, obligation: AssuranceObligation) -> bool:
    if obligation.bound_kind is None:
        return True  # valid-evidence existence satisfies
    value = _value_of(record, obligation)
    if obligation.bound_kind == "floor":
        return value >= obligation.bound_value
    return value <= obligation.bound_value  # ceiling


def _latest(records: List[Any]) -> Any:
    """The most recent record (max by (instant, record_id)) — the
    current evidence is the current truth (latest-evidence-wins)."""
    return max(records, key=lambda record: (record.instant, record.record_id))


def _evaluate_one(
    obligation: AssuranceObligation,
    evidence: List[Any],
    at: Any,
    at_text: str,
) -> AssuranceReason:
    """Evaluate one obligation against the evidence set at the
    injected instant (pure; returns the typed reason record)."""
    # no time travel: records produced after the evaluation instant
    # are ignored entirely
    candidates = [
        record
        for record in evidence
        if _matches_obligation(record, obligation)
        and parse_instant(record.instant) <= at
    ]
    eligible = [record for record in candidates if _is_eligible(record, obligation, at)]
    if eligible:
        chosen = _latest(eligible)
        if _satisfies_bound(chosen, obligation):
            if obligation.bound_kind is None:
                detail = "valid %s evidence present (%s)" % (
                    obligation.obligation_kind, chosen.record_id[:32],
                )
            else:
                detail = "value %d within %s bound %d (%s)" % (
                    _value_of(chosen, obligation), obligation.bound_kind,
                    obligation.bound_value, chosen.record_id[:32],
                )
            return AssuranceReason(
                reason_kind="satisfied",
                obligation_id=obligation.obligation_id,
                evidence_id=chosen.record_id,
                severity="",
                detail=detail,
            )
        detail = "value %d outside %s bound %d at %s (%s)" % (
            _value_of(chosen, obligation), obligation.bound_kind,
            obligation.bound_value, at_text, chosen.record_id[:32],
        )
        return AssuranceReason(
            reason_kind="value-breach",
            obligation_id=obligation.obligation_id,
            evidence_id=chosen.record_id,
            severity=obligation.severity,
            detail=detail,
        )
    # no VALID evidence at the instant
    deadline_fired = (
        obligation.evidence_deadline is not None
        and at >= parse_instant(obligation.evidence_deadline)
    )
    if deadline_fired:
        state_text = "stale" if candidates else "absent"
        detail = "no valid %s evidence by deadline %s (evidence state: %s)" % (
            obligation.obligation_kind, obligation.evidence_deadline, state_text,
        )
        return AssuranceReason(
            reason_kind="absence-breach",
            obligation_id=obligation.obligation_id,
            evidence_id="",
            severity=obligation.severity,
            detail=detail,
        )
    if candidates:
        latest_stale = _latest(candidates)
        detail = "evidence exists but its validity window does not cover %s" % at_text
        return AssuranceReason(
            reason_kind="stale-evidence",
            obligation_id=obligation.obligation_id,
            evidence_id=latest_stale.record_id,
            severity="",
            detail=detail,
        )
    detail = "no %s evidence for subject %s at %s" % (
        obligation.obligation_kind, obligation.subject_ref[:32], at_text,
    )
    return AssuranceReason(
        reason_kind="absent-evidence",
        obligation_id=obligation.obligation_id,
        evidence_id="",
        severity="",
        detail=detail,
    )


_AGGREGATION_ORDER = {"violated": 3, "degraded": 2, "unknown": 1, "compliant": 0}


def _breach_state(reason: AssuranceReason) -> str:
    """The state a reason contributes to the worst-of aggregation
    (severity-driven)."""
    if reason.reason_kind in ("value-breach", "absence-breach"):
        if reason.severity == "hard":
            return "violated"
        return "degraded"
    if reason.reason_kind in ("stale-evidence", "absent-evidence"):
        return "unknown"
    return "compliant"  # satisfied reasons contribute the best state


def evaluate_contract(
    contract: ConnectivityContract,
    obligations: Sequence[AssuranceObligation],
    evidence: Sequence[Any],
    at_instant: str,
) -> AssuranceEvaluation:
    """Evaluate one ACTIVE canonical contract against its assurance
    obligations using the typed evidence records (LOCK-107).

    Deterministic and pure: the same (contract, obligations, evidence,
    instant) always produces the byte-identical evaluation — same
    state, same reasons, same content-derived id.  No wall clock (the
    evaluation instant is INJECTED; staleness is instant-threshold
    based), no contract mutation, no store writes, no network.

    Contract-state dispatch (frozen §9 honesty):

    - ``TERMINATED`` -> ``deliberately_terminated`` (no obligation
      re-evaluation, no side effects);
    - ``FAILED`` -> ``failed``;
    - the §9 assurance-evaluable states -> full evaluation;
    - everything else -> typed NOT_EVALUABLE (fail closed).
    """
    if not isinstance(contract, ConnectivityContract):
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "evaluate_contract requires a canonical ConnectivityContract "
            "(got %s) — the accepted contracts/ domain is consumed by "
            "reference, never duplicated" % type(contract).__name__,
        )
    at_text = _require_instant(at_instant, "at_instant")
    at = parse_instant(at_text)
    records = _require_tuple(evidence, "evidence")
    for record in records:
        if not isinstance(record, (ClaimEvidence, ObservationEvidence, CommitmentEvidence, AttestationEvidence)):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "evidence must be typed evidence records (LOCK-106: no "
                "untyped evidence); got %s" % type(record).__name__,
            )
    resolved = resolve_obligations(contract, obligations)

    state = contract.state
    if state == "TERMINATED":
        return AssuranceEvaluation(
            contract_ref=contract.contract_id,
            evaluated_at=at_text,
            state="deliberately_terminated",
            reasons=(
                AssuranceReason(
                    reason_kind="contract-terminated",
                    obligation_id="",
                    evidence_id="",
                    severity="",
                    detail="contract is TERMINATED (deliberate); no obligation "
                    "re-evaluation, no side effects",
                ),
            ),
        )
    if state == "FAILED":
        return AssuranceEvaluation(
            contract_ref=contract.contract_id,
            evaluated_at=at_text,
            state="failed",
            reasons=(
                AssuranceReason(
                    reason_kind="contract-failed",
                    obligation_id="",
                    evidence_id="",
                    severity="",
                    detail="contract is FAILED; no obligation re-evaluation, "
                    "no side effects",
                ),
            ),
        )
    if state not in EVALUABLE_CONTRACT_STATES:
        raise AssuranceError(
            AssuranceReasonCode.NOT_EVALUABLE,
            "contract state %r is outside the assurance evaluation surface "
            "(pre-activation or the post-assurance commercial tail); only "
            "the active delivery/assurance states evaluate" % state,
        )

    evidence_list = [
        record for record in records if record.contract_ref == contract.contract_id
    ]
    reasons = tuple(
        _evaluate_one(obligation, evidence_list, at, at_text)
        for obligation in resolved
    )
    aggregate = "compliant"
    for reason in reasons:
        contributed = _breach_state(reason)
        if _AGGREGATION_ORDER[contributed] > _AGGREGATION_ORDER[aggregate]:
            aggregate = contributed
    return AssuranceEvaluation(
        contract_ref=contract.contract_id,
        evaluated_at=at_text,
        state=aggregate,
        reasons=reasons,
    )


__all__ = [
    "ASSURANCE_STATES",
    "OBLIGATION_KINDS",
    "OBLIGATION_SEVERITIES",
    "BOUND_KINDS",
    "REASON_KINDS",
    "EVALUABLE_CONTRACT_STATES",
    "SHORT_CIRCUIT_CONTRACT_STATES",
    "AssuranceObligation",
    "AssuranceReason",
    "AssuranceEvaluation",
    "to_contract_references",
    "resolve_obligations",
    "evaluate_contract",
]
