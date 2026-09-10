"""ADCOS typed evidence-record canonical model (M005 — Evidence and
Assurance; LOCK-106).

The four DISTINCT evidence record types of the frozen Architecture 1.1
mandate — **claim**, **observation**, **commitment**, **attestation** —
as typed, canonical-JSON-serializable frozen records carrying provenance
(the frozen 1.1 §9 closed-loop assurance evidence base):

- **claim** — an assertion a producer makes about a subject without
  measuring it (LOCK-008 discipline: a remote statement is a claim BY
  the reporting producer; the frozen 1.0-era §6.11 source classes live
  on the raw telemetry records, not here).  Carries a required integer
  confidence (basis points, 0..10000).
- **observation** — a measured value with an explicit validity window
  (``freshness_until`` strictly after ``instant``); staleness is
  DERIVED at evaluation time from that window, never stored as fresh.
  Carries a required integer confidence.
- **commitment** — a forward-looking promise over an explicit window
  (``valid_from`` .. ``valid_until``, non-empty); a commitment is DATA
  about a promise, never an authority (LOCK-117: the contract stays
  the authority; commitments ride as evidence).
- **attestation** — a third-party certification with its own validity
  boundary (``valid_until`` strictly after ``instant``).

Type distinction is STRUCTURAL (LOCK-106: no type confusion, no
untyped evidence): the four record classes carry different payload
fields, the ``record_type`` member is fixed per class, and each
``from_dict`` rejects a payload whose ``record_type`` does not match
the class — a serialized observation can never be reconstructed as a
claim, commitment or attestation.

Every record carries the LOCK-118 provenance envelope: the subject
reference (what the evidence is about), the contract reference (the
canonical ``ConnectivityContract`` id the evidence serves), the
production instant (injected RFC 3339 UTC — never wall clock), the
producer identity, and confidence where applicable.  Lineage
references (``source_refs``) point at the upstream records the
evidence was derived from (e.g. the telemetry observation id for the
M005 harvest seam) — opaque DATA, never authority.

Identity is content-derived over the COMPLETE canonical DATA
(the repo-wide discipline): ``record_id`` equals
``derive_<type>_id(...)`` — SHA-256 over the canonical JSON of the
record minus the id itself — so any field mutation under a retained
id is rejected at construction (tamper evidence).  Deterministic,
offline, no randomness, no UUIDs, no network, no secrets (LOCK-119:
secret-shaped producer/reference text is rejected at construction and
deserialization time; integer values only — no binary floating point).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from .errors import EvidenceError, EvidenceReasonCode

# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------

#: The frozen LOCK-106 evidence-type vocabulary: claim, observation,
#: commitment and attestation are DISTINCT types (never untyped).
EVIDENCE_TYPES: Tuple[str, ...] = (
    "claim",
    "observation",
    "commitment",
    "attestation",
)

#: Frozen claim-kind vocabulary (what a claim asserts).
CLAIM_KINDS: Tuple[str, ...] = (
    "capability-statement",
    "coverage-statement",
    "capacity-statement",
    "status-statement",
)

#: Frozen commitment-kind vocabulary (what a commitment promises).
COMMITMENT_KINDS: Tuple[str, ...] = (
    "service-level",
    "availability",
    "latency",
    "repair-window",
)

#: Frozen attestation-kind vocabulary (what an attestation certifies).
ATTESTATION_KINDS: Tuple[str, ...] = (
    "external-audit",
    "controller-verified",
    "remotely-attested",
    "compliance-certificate",
)

#: Frozen observation-metric vocabulary: EXACTLY the standardized
#: telemetry metric-registry names (the M005 harvest seam translates
#: ``TelemetryObservation`` records whose (subject kind, metric) pair
#: is drawn from ``telemetry.TELEMETRY_METRIC_REGISTRY``; the M005
#: battery cross-checks this vocabulary against that registry — the
#: frozen primitive is reused, never reinvented).
OBSERVATION_METRICS: Tuple[str, ...] = (
    # link metrics (frozen WORK-016 LinkMetricName set)
    "link-up",
    "rx-bytes-total",
    "tx-bytes-total",
    "rx-error-count",
    "tx-error-count",
    "retransmit-count",
    # path metrics (WORK-011 integer discipline)
    "latency-ms",
    "loss-bp",
    "capacity-bps",
    "energy-cost-millijoules",
    # resource metrics
    "utilization-bp",
    "available-base",
    # energy metrics (WORK-008 ENERGY base units)
    "energy-level-millijoules",
    "energy-capacity-millijoules",
    "power-draw-milliwatts",
    "reserve-bp",
    # adapter-health metrics (WORK-016 HealthState ladder)
    "health-state",
    "consecutive-failures",
)

#: The repository-wide confidence scale (WORK-011 standard): integer
#: basis points, 10000 bp == 100.00%.
MAX_BASIS_POINTS = 10_000

#: Maximum measurement magnitude (integers only; the bound keeps
#: canonical determinism trivially auditable — the telemetry
#: house rule).
MAX_EVIDENCE_VALUE = 1 << 53

#: Record-id prefixes (the M005 family namespaces).
_ID_PREFIXES: Dict[str, str] = {
    "claim": "evidence:claim:",
    "observation": "evidence:observation:",
    "commitment": "evidence:commitment:",
    "attestation": "evidence:attestation:",
}

_REF_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,256}$")
_SECRET_VALUE_PATTERN = re.compile(
    r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$"
)
_SECRET_TOKEN_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "%s must be a non-empty str (got %s)"
            % (label, type(value).__name__),
        )
    return value


def _require_ref_text(value: object, label: str) -> str:
    """A reference-grammar string that is also not secret-shaped
    (LOCK-119)."""
    text = _require_str(value, label)
    if not _REF_PATTERN.match(text):
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "%s must match the reference grammar [A-Za-z0-9._:+/-]{1,256}"
            % label,
        )
    if _SECRET_VALUE_PATTERN.match(text) or _SECRET_TOKEN_PATTERN.search(text):
        raise EvidenceError(
            EvidenceReasonCode.SECRET_REJECTED,
            "%s is secret-shaped material; secrets never become evidence "
            "DATA (LOCK-119)" % label,
        )
    return text


def _require_instant(value: object, label: str) -> str:
    """An explicit RFC 3339 UTC instant (injected, never wall clock)."""
    if not isinstance(value, str) or not value:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INSTANT,
            "%s must be an explicit RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INSTANT,
            "%s must be an explicit RFC 3339 UTC instant: %s"
            % (label, str(error)[:120]),
        ) from None
    return value


def _require_int(value: object, label: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "%s must be an int (got %s)" % (label, type(value).__name__),
        )
    if value < 0 or value > maximum:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "%s must be within 0..%d (got %d)" % (label, maximum, value),
        )
    return value


def _require_confidence(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceError(
            EvidenceReasonCode.INVALID_CONFIDENCE,
            "%s must be an integer basis-point value (got %s)"
            % (label, type(value).__name__),
        )
    if value < 0 or value > MAX_BASIS_POINTS:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_CONFIDENCE,
            "%s must be within 0..%d basis points (got %d)"
            % (label, MAX_BASIS_POINTS, value),
        )
    return value


def _require_tuple(value: object, label: str) -> Tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "%s must be a tuple or list (got %s)"
            % (label, type(value).__name__),
        )
    return tuple(value)


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    text = _require_str(value, label)
    if text not in vocabulary:
        raise EvidenceError(
            EvidenceReasonCode.VOCABULARY,
            "%s must be one of the frozen vocabulary %s (got %r)"
            % (label, list(vocabulary), text),
        )
    return text


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "%s is not canonicalizable: %s" % (label, str(error)[:120]),
        ) from None


def _derive_record_id(record_type: str, document: Mapping[str, Any]) -> str:
    """The tamper-evident, content-derived record id over the COMPLETE
    canonical DATA (the record dict minus ``record_id`` itself)."""
    material = dict(document)
    material.pop("record_id", None)
    digest = hashlib.sha256(_canonical_bytes(material, "record identity")).hexdigest()
    return _ID_PREFIXES[record_type] + digest


def _check_record_id(record_type: str, record_id: object, expected: str) -> str:
    prefix = _ID_PREFIXES[record_type]
    if not isinstance(record_id, str) or not record_id:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "record_id must be a non-empty %s-prefixed string" % prefix,
        )
    if record_id != expected:
        raise EvidenceError(
            EvidenceReasonCode.ID_MISMATCH,
            "record_id must equal the content-derived derivation — a "
            "tampered or miscomputed id is rejected (the record is "
            "attributable DATA)",
        )
    return record_id


def _check_record_type(data: object, record_type: str) -> None:
    """LOCK-106 no-type-confusion guard: a payload whose record_type
    does not match the reconstructing class fails closed."""
    if not isinstance(data, Mapping):
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "%s DATA must be a mapping (got %s)"
            % (record_type, type(data).__name__),
        )
    actual = data.get("record_type")
    if actual != record_type:
        raise EvidenceError(
            EvidenceReasonCode.VOCABULARY,
            "record_type mismatch: %s.from_dict requires record_type=%r "
            "(got %r) — the four evidence types are distinct and never "
            "convertible (LOCK-106)" % (record_type.capitalize(), record_type, actual),
        )


def _common_from_dict_members(data: Mapping[str, Any], record_type: str) -> Dict[str, Any]:
    """Extract + validate the shared provenance envelope members."""
    return {
        "subject_ref": data.get("subject_ref"),
        "contract_ref": data.get("contract_ref"),
        "instant": data.get("instant"),
        "producer": data.get("producer"),
        "source_refs": tuple(data.get("source_refs") or ()),
        "record_id": data.get("record_id"),
    }


def _validate_common(
    record: Any,
) -> None:
    """Validate the shared provenance envelope on a constructed record."""
    object.__setattr__(
        record, "subject_ref", _require_ref_text(record.subject_ref, "subject_ref")
    )
    object.__setattr__(
        record, "contract_ref", _require_ref_text(record.contract_ref, "contract_ref")
    )
    object.__setattr__(record, "instant", _require_instant(record.instant, "instant"))
    object.__setattr__(
        record, "producer", _require_ref_text(record.producer, "producer")
    )
    refs = _require_tuple(record.source_refs, "source_refs")
    object.__setattr__(
        record,
        "source_refs",
        tuple(
            _require_ref_text(ref, "source_refs[%d]" % i)
            for i, ref in enumerate(refs)
        ),
    )


def _derive_and_check(record: Any) -> None:
    """Derive the content id for the record and enforce the retained-id
    tamper guard (construction AND deserialization)."""
    expected = _derive_record_id(record.record_type, record.to_id_material())
    record_id = getattr(record, "record_id", "")
    if not record_id:
        object.__setattr__(record, "record_id", expected)
    else:
        _check_record_id(record.record_type, record_id, expected)


# ----------------------------------------------------------------------
# Canonical records (LOCK-106: four DISTINCT typed records)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimEvidence:
    """A claim: an assertion a producer makes about a subject WITHOUT
    measuring it (LOCK-008: the claim belongs to the producer).  Typed
    DATA with immutable provenance — never a verdict.

    Distinct payload: ``claim_kind`` + ``asserted_value`` + REQUIRED
    integer confidence (a claim without a producer-stated confidence
    is unattributable opinion, not typed evidence).
    """

    subject_ref: str
    contract_ref: str
    instant: str
    producer: str
    claim_kind: str
    asserted_value: int
    confidence_basis_points: int
    source_refs: Tuple[str, ...] = ()
    record_id: str = ""

    record_type: str = "claim"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "claim_kind", _require_in(self.claim_kind, CLAIM_KINDS, "claim_kind")
        )
        object.__setattr__(
            self,
            "asserted_value",
            _require_int(self.asserted_value, "asserted_value", maximum=MAX_EVIDENCE_VALUE),
        )
        object.__setattr__(
            self,
            "confidence_basis_points",
            _require_confidence(self.confidence_basis_points, "confidence_basis_points"),
        )
        _validate_common(self)
        _derive_and_check(self)

    def to_id_material(self) -> Dict[str, Any]:
        return {
            "record_type": self.record_type,
            "subject_ref": self.subject_ref,
            "contract_ref": self.contract_ref,
            "instant": self.instant,
            "producer": self.producer,
            "claim_kind": self.claim_kind,
            "asserted_value": self.asserted_value,
            "confidence_basis_points": self.confidence_basis_points,
            "source_refs": list(self.source_refs),
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.to_id_material(), record_id=self.record_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ClaimEvidence":
        _check_record_type(data, "claim")
        members = _common_from_dict_members(data, "claim")
        return cls(
            subject_ref=members["subject_ref"],
            contract_ref=members["contract_ref"],
            instant=members["instant"],
            producer=members["producer"],
            source_refs=members["source_refs"],
            claim_kind=data.get("claim_kind"),
            asserted_value=data.get("asserted_value"),
            confidence_basis_points=data.get("confidence_basis_points"),
            record_id=members["record_id"] or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "claim record")


@dataclass(frozen=True)
class ObservationEvidence:
    """An observation: a measured value with an explicit validity
    window (``freshness_until`` STRICTLY after ``instant`` — the
    telemetry temporal discipline).  Staleness is DERIVED at
    evaluation time from the window, never stored as fresh.

    Distinct payload: ``metric`` (the frozen standardized metric
    vocabulary — the telemetry registry names) + ``value`` + REQUIRED
    integer confidence + the freshness boundary.
    """

    subject_ref: str
    contract_ref: str
    instant: str
    producer: str
    metric: str
    value: int
    confidence_basis_points: int
    freshness_until: str
    source_refs: Tuple[str, ...] = ()
    record_id: str = ""

    record_type: str = "observation"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "metric", _require_in(self.metric, OBSERVATION_METRICS, "metric")
        )
        object.__setattr__(
            self, "value", _require_int(self.value, "value", maximum=MAX_EVIDENCE_VALUE)
        )
        object.__setattr__(
            self,
            "confidence_basis_points",
            _require_confidence(self.confidence_basis_points, "confidence_basis_points"),
        )
        _validate_common(self)
        object.__setattr__(
            self, "freshness_until", _require_instant(self.freshness_until, "freshness_until")
        )
        if not parse_instant(self.freshness_until) > parse_instant(self.instant):
            raise EvidenceError(
                EvidenceReasonCode.INVALID_WINDOW,
                "validity window must be non-empty (freshness_until %s must "
                "be strictly after instant %s)" % (self.freshness_until, self.instant),
            )
        _derive_and_check(self)

    def is_fresh_at(self, at_instant: str) -> bool:
        """True iff the explicit validity window covers ``at_instant``
        (fresh iff strictly before freshness_until — the derived
        staleness discipline; the query instant must be a valid RFC
        3339 UTC instant)."""
        at = parse_instant(_require_instant(at_instant, "at_instant"))
        return parse_instant(self.freshness_until) > at

    def to_id_material(self) -> Dict[str, Any]:
        return {
            "record_type": self.record_type,
            "subject_ref": self.subject_ref,
            "contract_ref": self.contract_ref,
            "instant": self.instant,
            "producer": self.producer,
            "metric": self.metric,
            "value": self.value,
            "confidence_basis_points": self.confidence_basis_points,
            "freshness_until": self.freshness_until,
            "source_refs": list(self.source_refs),
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.to_id_material(), record_id=self.record_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObservationEvidence":
        _check_record_type(data, "observation")
        members = _common_from_dict_members(data, "observation")
        return cls(
            subject_ref=members["subject_ref"],
            contract_ref=members["contract_ref"],
            instant=members["instant"],
            producer=members["producer"],
            source_refs=members["source_refs"],
            metric=data.get("metric"),
            value=data.get("value"),
            confidence_basis_points=data.get("confidence_basis_points"),
            freshness_until=data.get("freshness_until"),
            record_id=members["record_id"] or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "observation record")


@dataclass(frozen=True)
class CommitmentEvidence:
    """A commitment: a forward-looking promise over an explicit,
    non-empty window (``valid_from`` .. ``valid_until``).  A commitment
    is DATA about a promise — the CONTRACT stays the authority
    (LOCK-117); commitments never bind execution artifacts and never
    confer rights by themselves.

    Distinct payload: ``commitment_kind`` + ``committed_value`` + the
    two-sided window (no confidence member: a promise is not a
    measurement — LOCK-106 type distinction is structural).
    """

    subject_ref: str
    contract_ref: str
    instant: str
    producer: str
    commitment_kind: str
    committed_value: int
    valid_from: str
    valid_until: str
    source_refs: Tuple[str, ...] = ()
    record_id: str = ""

    record_type: str = "commitment"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "commitment_kind",
            _require_in(self.commitment_kind, COMMITMENT_KINDS, "commitment_kind"),
        )
        object.__setattr__(
            self,
            "committed_value",
            _require_int(self.committed_value, "committed_value", maximum=MAX_EVIDENCE_VALUE),
        )
        _validate_common(self)
        object.__setattr__(
            self, "valid_from", _require_instant(self.valid_from, "valid_from")
        )
        object.__setattr__(
            self, "valid_until", _require_instant(self.valid_until, "valid_until")
        )
        if not parse_instant(self.valid_until) > parse_instant(self.valid_from):
            raise EvidenceError(
                EvidenceReasonCode.INVALID_WINDOW,
                "commitment window must be non-empty (valid_until %s must "
                "be strictly after valid_from %s)" % (self.valid_until, self.valid_from),
            )
        _derive_and_check(self)

    def covers(self, at_instant: str) -> bool:
        """True iff the commitment window covers ``at_instant``
        (valid_from <= at < valid_until)."""
        at = parse_instant(_require_instant(at_instant, "at_instant"))
        return parse_instant(self.valid_from) <= at < parse_instant(self.valid_until)

    def to_id_material(self) -> Dict[str, Any]:
        return {
            "record_type": self.record_type,
            "subject_ref": self.subject_ref,
            "contract_ref": self.contract_ref,
            "instant": self.instant,
            "producer": self.producer,
            "commitment_kind": self.commitment_kind,
            "committed_value": self.committed_value,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "source_refs": list(self.source_refs),
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.to_id_material(), record_id=self.record_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CommitmentEvidence":
        _check_record_type(data, "commitment")
        members = _common_from_dict_members(data, "commitment")
        return cls(
            subject_ref=members["subject_ref"],
            contract_ref=members["contract_ref"],
            instant=members["instant"],
            producer=members["producer"],
            source_refs=members["source_refs"],
            commitment_kind=data.get("commitment_kind"),
            committed_value=data.get("committed_value"),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until"),
            record_id=members["record_id"] or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "commitment record")


@dataclass(frozen=True)
class AttestationEvidence:
    """An attestation: a third-party certification of a subject over
    an explicit validity window (``valid_until`` strictly after
    ``instant``).  The attestor IS the producer (LOCK-118: issuer and
    provenance first-class).

    Distinct payload: ``attestation_kind`` + ``attested_value`` + the
    validity boundary (no confidence member: a certification is not a
    probabilistic measurement — LOCK-106 type distinction is
    structural).
    """

    subject_ref: str
    contract_ref: str
    instant: str
    producer: str
    attestation_kind: str
    attested_value: int
    valid_until: str
    source_refs: Tuple[str, ...] = ()
    record_id: str = ""

    record_type: str = "attestation"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attestation_kind",
            _require_in(self.attestation_kind, ATTESTATION_KINDS, "attestation_kind"),
        )
        object.__setattr__(
            self,
            "attested_value",
            _require_int(self.attested_value, "attested_value", maximum=MAX_EVIDENCE_VALUE),
        )
        _validate_common(self)
        object.__setattr__(
            self, "valid_until", _require_instant(self.valid_until, "valid_until")
        )
        if not parse_instant(self.valid_until) > parse_instant(self.instant):
            raise EvidenceError(
                EvidenceReasonCode.INVALID_WINDOW,
                "attestation validity must be non-empty (valid_until %s must "
                "be strictly after instant %s)" % (self.valid_until, self.instant),
            )
        _derive_and_check(self)

    def is_valid_at(self, at_instant: str) -> bool:
        """True iff the attestation is still valid at ``at_instant``
        (strictly before valid_until)."""
        at = parse_instant(_require_instant(at_instant, "at_instant"))
        return parse_instant(self.valid_until) > at

    def to_id_material(self) -> Dict[str, Any]:
        return {
            "record_type": self.record_type,
            "subject_ref": self.subject_ref,
            "contract_ref": self.contract_ref,
            "instant": self.instant,
            "producer": self.producer,
            "attestation_kind": self.attestation_kind,
            "attested_value": self.attested_value,
            "valid_until": self.valid_until,
            "source_refs": list(self.source_refs),
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.to_id_material(), record_id=self.record_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AttestationEvidence":
        _check_record_type(data, "attestation")
        members = _common_from_dict_members(data, "attestation")
        return cls(
            subject_ref=members["subject_ref"],
            contract_ref=members["contract_ref"],
            instant=members["instant"],
            producer=members["producer"],
            source_refs=members["source_refs"],
            attestation_kind=data.get("attestation_kind"),
            attested_value=data.get("attested_value"),
            valid_until=data.get("valid_until"),
            record_id=members["record_id"] or "",
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "attestation record")


# ----------------------------------------------------------------------
# Type dispatch helpers (typed, never untyped)
# ----------------------------------------------------------------------

#: The typed record classes, keyed by the frozen LOCK-106 vocabulary.
EVIDENCE_RECORD_CLASSES: Dict[str, type] = {
    "claim": ClaimEvidence,
    "observation": ObservationEvidence,
    "commitment": CommitmentEvidence,
    "attestation": AttestationEvidence,
}


def record_from_dict(data: object) -> Any:
    """Reconstruct a typed evidence record from canonical DATA, with
    the ``record_type`` member selecting the class (fail closed on
    unknown types — LOCK-106: no untyped evidence, no type
    confusion)."""
    if not isinstance(data, Mapping):
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "evidence DATA must be a mapping (got %s)" % type(data).__name__,
        )
    record_type = data.get("record_type")
    if record_type not in EVIDENCE_RECORD_CLASSES:
        raise EvidenceError(
            EvidenceReasonCode.VOCABULARY,
            "record_type must be one of the frozen LOCK-106 evidence types "
            "%s (got %r) — there is no untyped evidence" % (list(EVIDENCE_TYPES), record_type),
        )
    return EVIDENCE_RECORD_CLASSES[record_type].from_dict(data)


def derive_record_id(record: Any) -> str:
    """The content-derived id of an already-constructed typed record
    (re-derivation for verification callers)."""
    return _derive_record_id(record.record_type, record.to_id_material())


__all__ = [
    "EVIDENCE_TYPES",
    "CLAIM_KINDS",
    "COMMITMENT_KINDS",
    "ATTESTATION_KINDS",
    "OBSERVATION_METRICS",
    "MAX_BASIS_POINTS",
    "MAX_EVIDENCE_VALUE",
    "EVIDENCE_RECORD_CLASSES",
    "ClaimEvidence",
    "ObservationEvidence",
    "CommitmentEvidence",
    "AttestationEvidence",
    "record_from_dict",
    "derive_record_id",
]
