"""ADCOS closed-loop assurance package (M005 — Evidence and Assurance).

Public surface:

- the FROZEN assurance state vocabulary ``ASSURANCE_STATES``
  (Architecture 1.1 §9: compliant, degraded, violated, unknown
  (stale/absent evidence), failed, deliberately_terminated — no
  state outside the vocabulary) and the frozen obligation
  vocabularies ``OBLIGATION_KINDS`` / ``OBLIGATION_SEVERITIES`` /
  ``BOUND_KINDS`` / ``REASON_KINDS``;
- :class:`AssuranceObligation` — the typed obligation record whose
  content-derived id is the value the canonical contract's opaque
  ``assurance-obligation`` references carry
  (:func:`to_contract_references` binds them into a CreateContract;
  :func:`resolve_obligations` enforces the fail-closed 1:1
  resolution — the contract alone decides WHICH obligations apply,
  this authority alone owns their semantics; no second contract
  model);
- :func:`evaluate_contract` — the deterministic, pure closed-loop
  evaluation of an ACTIVE canonical contract against its obligations
  using the typed ``evidence/`` records (same inputs -> same state,
  same typed reasons, same content-derived evaluation id;
  stale-evidence detection is instant-threshold-based on injected
  instants, never wall clock);
- :class:`AssuranceJournal` — the append-only, idempotent evaluation
  history (construction-is-recovery persistence; LOCK-119 secret
  scanning);
- the contract bridge :func:`bridge_command` /
  :func:`record_into_contract` — the sole, explicit recording path
  back into the accepted ``contracts/`` domain via its own
  ``RecordAssurance`` command vocabulary (consumed, never modified).

Authority boundaries (the layering contract):

- ``/assurance`` owns the CONTRACT-LEVEL EVALUATION — nothing else.
  It consumes ``contracts/`` by reference (LOCK-101/LOCK-117: the
  contract stays the sole authority; the bridge is the only write
  path, through the contract's own command vocabulary); it consumes
  the typed ``evidence/`` records (LOCK-106); it never owns raw
  operational measurement (telemetry owns that — the disclosed
  harvest seam lives in ``evidence/telemetry_seam.py``); it never
  becomes an execution/replan authority (M006/M008 own those) and
  never hosts secrets (LOCK-119).
"""

from __future__ import annotations

from .errors import (
    ASSURANCE_PREFIX,
    AssuranceError,
    AssuranceReasonCode,
)
from .model import (
    ASSURANCE_STATES,
    BOUND_KINDS,
    EVALUABLE_CONTRACT_STATES,
    OBLIGATION_KINDS,
    OBLIGATION_SEVERITIES,
    REASON_KINDS,
    SHORT_CIRCUIT_CONTRACT_STATES,
    AssuranceEvaluation,
    AssuranceObligation,
    AssuranceReason,
    evaluate_contract,
    resolve_obligations,
    to_contract_references,
)
from .journal import AssuranceJournal, AppendResult
from .bridge import (
    CONTRACT_RECORDABLE_STATES,
    DEFAULT_BRIDGE_ISSUER,
    EVALUATION_TO_RECORDED_STATE,
    bridge_command,
    record_into_contract,
)

__all__ = [
    # family prefix
    "ASSURANCE_PREFIX",
    # error model
    "AssuranceError",
    "AssuranceReasonCode",
    # frozen vocabularies (the §9 state vocabulary is frozen)
    "ASSURANCE_STATES",
    "OBLIGATION_KINDS",
    "OBLIGATION_SEVERITIES",
    "BOUND_KINDS",
    "REASON_KINDS",
    "EVALUABLE_CONTRACT_STATES",
    "SHORT_CIRCUIT_CONTRACT_STATES",
    # the typed obligation record + resolution
    "AssuranceObligation",
    "to_contract_references",
    "resolve_obligations",
    # the typed evaluation outcome + the pure kernel
    "AssuranceReason",
    "AssuranceEvaluation",
    "evaluate_contract",
    # the append-only evaluation history
    "AssuranceJournal",
    "AppendResult",
    # the contract bridge (the closed loop)
    "EVALUATION_TO_RECORDED_STATE",
    "CONTRACT_RECORDABLE_STATES",
    "DEFAULT_BRIDGE_ISSUER",
    "bridge_command",
    "record_into_contract",
]
