"""The disclosed M005 harvest seam: telemetry observations become
observation-type evidence records (LOCK-106).

Migration classification (``spec/migration/classification-matrix.md``,
FROZEN): the WORK-026-era ``telemetry`` package is **RETAIN** with
target authority **Assurance evidence** — telemetry stays the owner of
raw operational measurement (its privacy fence, its policy-gated
topology-promotion semantics, and its authority boundaries are
governed by their own frozen specs and are NOT rewritten here); the
``evidence`` package owns the TYPED evidence record.  This module is
the single, explicit, disclosed translation point between the two:

    telemetry.TelemetryObservation (raw operational measurement)
        -> evidence.ObservationEvidence (typed evidence record)

The seam is one-directional and DATA-only:

- it CONSUMES ``telemetry.model.TelemetryObservation`` through the
  public, frozen surface (subject, source, metric, value, confidence,
  observed_at, freshness_until, observation id);
- it PRODUCES a typed ``ObservationEvidence`` whose provenance is
  complete and honest: the observing node is the producer, the
  telemetry observation id rides ``source_refs`` (lineage — LOCK-118),
  and the contract reference is INJECTED BY THE CALLER (a raw
  operational measurement never knows which contract it serves; the
  caller binds the evidence to the canonical contract — LOCK-101);
- it never mutates the telemetry record, never writes telemetry state,
  and never constructs telemetry records (there is no reverse
  translation: evidence is not a measurement authority);
- it is fail-closed and typed: non-observation input, an untranslatable
  metric, or a malformed contract reference raise ``EvidenceError``
  with stable reason codes (never raw exception text).

Determinism: the translation is a pure function of (observation,
contract_ref) — the same inputs always produce the byte-identical
evidence record (same content-derived id); no wall clock, no
randomness, no network, no secrets (LOCK-119 — the source record was
already secret-scanned by the telemetry authority; the seam re-scans
the translated fields through the record constructors).
"""

from __future__ import annotations

from typing import Any

from .errors import EvidenceError, EvidenceReasonCode
from .model import OBSERVATION_METRICS, ObservationEvidence

#: The disclosed seam identity (battery-introspectable).
TELEMETRY_HARVEST_SEAM = "telemetry:observation->evidence:observation"

#: The seam's contract binding note: the caller injects the contract
#: reference; raw operational measurements never carry contract
#: identity (LOCK-101 discipline).
SEAM_DISCLOSURE = (
    "harvest (classification-matrix: Telemetry RETAIN -> Assurance "
    "evidence): telemetry stays the owner of raw operational "
    "measurement; evidence/ owns the typed evidence record; this seam "
    "is the explicit, disclosed, one-directional translation point"
)


def telemetry_observation_to_evidence(
    observation: Any, contract_ref: str
) -> ObservationEvidence:
    """Translate one ``telemetry.TelemetryObservation`` into one typed
    ``ObservationEvidence`` record (fail closed on anything else).

    Field mapping (complete and disclosed):

    =========================  =======================================
    telemetry member           evidence member
    =========================  =======================================
    ``subject_ref``            ``subject_ref`` (verbatim)
    ``metric``                 ``metric`` (must be in the frozen
                               evidence observation-metric vocabulary)
    ``value``                  ``value`` (integer discipline preserved)
    ``confidence_basis_points`` ``confidence_basis_points``
    ``observed_at``            ``instant`` (the production instant)
    ``freshness_until``        ``freshness_until`` (the explicit
                               validity window rides verbatim —
                               staleness is derived, never stored fresh)
    ``source_node_id``         ``producer`` (the observing node is the
                               producer — LOCK-118)
    ``observation_id``         ``source_refs[0]`` (lineage: the exact
                               upstream record id)
    (caller-injected)          ``contract_ref`` (the canonical contract
                               the evidence serves)
    =========================  =======================================
    """
    # import here so the seam module is the ONLY evidence/ module that
    # touches the telemetry surface (the harvest direction is explicit)
    from telemetry.model import TelemetryObservation

    if not isinstance(observation, TelemetryObservation):
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "the seam translates telemetry.TelemetryObservation records "
            "only (got %s) — it is a disclosed harvest seam, not a "
            "generic converter" % type(observation).__name__,
        )
    if observation.metric not in OBSERVATION_METRICS:
        raise EvidenceError(
            EvidenceReasonCode.VOCABULARY,
            "telemetry metric %r is outside the frozen evidence "
            "observation-metric vocabulary — the seam translates only "
            "standardized registry metrics" % observation.metric,
        )
    if not isinstance(contract_ref, str) or not contract_ref:
        raise EvidenceError(
            EvidenceReasonCode.INVALID_INPUT,
            "contract_ref must be a non-empty canonical contract id "
            "(the caller binds the evidence to the contract; raw "
            "operational measurements never carry contract identity)",
        )
    return ObservationEvidence(
        subject_ref=observation.subject_ref,
        contract_ref=contract_ref,
        instant=observation.observed_at,
        producer=observation.source_node_id,
        metric=observation.metric,
        value=observation.value,
        confidence_basis_points=observation.confidence_basis_points,
        freshness_until=observation.freshness_until,
        source_refs=(observation.observation_id,),
    )


__all__ = [
    "TELEMETRY_HARVEST_SEAM",
    "SEAM_DISCLOSURE",
    "telemetry_observation_to_evidence",
]
