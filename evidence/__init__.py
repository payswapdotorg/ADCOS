"""ADCOS typed evidence-record package (M005 — Evidence and Assurance).

Public surface:

- the frozen LOCK-106 evidence-type vocabulary ``EVIDENCE_TYPES``
  (claim, observation, commitment, attestation — DISTINCT types, no
  untyped evidence) and the per-type frozen vocabularies
  ``CLAIM_KINDS`` / ``OBSERVATION_METRICS`` / ``COMMITMENT_KINDS`` /
  ``ATTESTATION_KINDS``;
- the four typed, canonical-JSON-serializable frozen records:
  :class:`ClaimEvidence`, :class:`ObservationEvidence`,
  :class:`CommitmentEvidence`, :class:`AttestationEvidence` — each
  carrying the LOCK-118 provenance envelope (subject reference,
  contract reference, injected instant, producer identity, confidence
  where applicable) and a content-derived tamper-evident id;
- the typed reconstruction dispatch :func:`record_from_dict`
  (record_type-selected, fail-closed on type confusion);
- the append-only, idempotent :class:`EvidenceStore` (immutable
  records; construction-is-recovery JSONL persistence; LOCK-119
  secret scanning on every persisted line);
- the disclosed M005 harvest seam :func:`telemetry_observation_to_evidence`
  (telemetry ``TelemetryObservation`` records become observation-type
  evidence records; telemetry stays the owner of raw operational
  measurement — classification matrix: Telemetry RETAIN -> Assurance
  evidence).

Authority boundaries (the layering contract):

- ``/evidence`` owns the TYPED EVIDENCE RECORDS — nothing else.  It
  never interprets contracts (LOCK-101: ``contracts/`` is the sole
  contract authority, consumed by reference), never evaluates
  assurance obligations (the ``assurance/`` domain owns evaluation),
  never becomes a measurement authority (telemetry owns raw
  operational measurement; the seam is one-directional DATA
  translation), and never hosts secrets (LOCK-119).
- Evidence records are immutable DATA with provenance (LOCK-118).
  A record asserts; it never authorizes.  No evidence record is a
  second authority for anything (LOCK-117).

Determinism: content-derived ids over canonical JSON; injected
RFC 3339 UTC instants only (no wall clock, no randomness, no UUIDs,
no network); integer values and confidence only (no binary floating
point); sorted iteration; fail-closed typed errors with stable codes.
"""

from __future__ import annotations

from .errors import (
    EVIDENCE_PREFIX,
    EvidenceError,
    EvidenceReasonCode,
)
from .model import (
    ATTESTATION_KINDS,
    CLAIM_KINDS,
    COMMITMENT_KINDS,
    EVIDENCE_RECORD_CLASSES,
    EVIDENCE_TYPES,
    MAX_BASIS_POINTS,
    MAX_EVIDENCE_VALUE,
    OBSERVATION_METRICS,
    AttestationEvidence,
    ClaimEvidence,
    CommitmentEvidence,
    ObservationEvidence,
    derive_record_id,
    record_from_dict,
)
from .store import EvidenceStore, IngestResult
from .telemetry_seam import (
    SEAM_DISCLOSURE,
    TELEMETRY_HARVEST_SEAM,
    telemetry_observation_to_evidence,
)

__all__ = [
    # family prefix
    "EVIDENCE_PREFIX",
    # error model
    "EvidenceError",
    "EvidenceReasonCode",
    # frozen vocabularies (LOCK-106)
    "EVIDENCE_TYPES",
    "CLAIM_KINDS",
    "COMMITMENT_KINDS",
    "ATTESTATION_KINDS",
    "OBSERVATION_METRICS",
    "MAX_BASIS_POINTS",
    "MAX_EVIDENCE_VALUE",
    # the four DISTINCT typed records
    "ClaimEvidence",
    "ObservationEvidence",
    "CommitmentEvidence",
    "AttestationEvidence",
    "EVIDENCE_RECORD_CLASSES",
    # typed dispatch
    "record_from_dict",
    "derive_record_id",
    # the append-only store
    "EvidenceStore",
    "IngestResult",
    # the disclosed harvest seam
    "TELEMETRY_HARVEST_SEAM",
    "SEAM_DISCLOSURE",
    "telemetry_observation_to_evidence",
]
