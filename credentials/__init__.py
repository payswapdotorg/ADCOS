"""ADCOS credentials package (M018 — Credential and Key Lifecycle
Operations).

The operational credential-lifecycle domain of the R8 charter M018
scope (R8-CORE-001, DEC-0114; chain-independent: composed from the
accepted R7 state — the M014 identity/federation/client convergence
surfaces are the composition substrate, imported and driven BY
REFERENCE; never reimplemented, weakened, forked, or bypassed):

- **Rotation drills with zero coverage gaps** (:mod:`credentials.
  rotation`): no operation window in which a superseded (or revoked)
  credential is still admitted — the admitted-set transition is
  ATOMIC (riding the identity authority's own all-or-nothing
  ``StoreBatch`` rotation) and JOURNALED with the before/after sets
  fully recorded; a rotation is a deterministic, replayable
  operation sequence; the mechanical zero-coverage-gap kernel
  (:func:`check_rotation_flip_is_atomic`,
  :func:`check_removal_is_atomic`, :func:`check_zero_coverage_gap`)
  rejects any intermediate window at construction AND at replay.
- **Revocation propagation as deterministic rounds with declared
  convergence bounds** (:mod:`credentials.propagation`): the
  convergence bound is a declared ROUND COUNT (never wall clock);
  every round is journaled and replayable; the round sequence is a
  pure function of the declared plan (same inputs -> identical
  rounds); an unconvergeable plan fails closed.
- **Emergency revocation paths that are explicit and evidence-
  visible** (:mod:`credentials.emergency`): the distinct typed
  ``emergency-revocation`` journal kind carrying the three frozen
  steps (the identity revocation, the M014 authorization revocation,
  the accepted emergency stop driven through the frozen W049
  client's own control), each step carrying LOCK-106 evidence
  references that resolve in the real evidence store.
- **Credential inventory verification** (:mod:`credentials.
  inventory`): every admitted credential traces to a valid lifecycle
  record; an incomplete chain is the typed
  ``credential-inventory-incomplete`` FAILURE citing the break kind
  (never a warning).
- **Key material never stored, logged, or echoed (LOCK-119)**:
  public records carry references and public metadata only — every
  public type is structurally secret-free (no bytes-carrying member
  anywhere); secret material lives only behind the accepted
  ``CredentialStore`` interface, which this package never opens (the
  ``new_secret`` argument of the rotation drill transits verbatim to
  the accepted ``IdentityService.rotate`` and never enters any
  record; the battery's fixtures are assembled at runtime from
  fragments so the full shape never appears in source).
- **The admission gate consumed BY REFERENCE from the accepted
  ``client/``/``federation/`` surfaces** (:mod:`credentials.gate`):
  NO second authorization runtime (LOCK-117) — the composed probe
  drives the accepted M014 identity gates and the converged
  traffic-admission point through their public APIs and records
  their verdicts verbatim; it never re-decides trust.

Authority boundaries (the layering contract, frozen 1.1):

- **LOCK-101/LOCK-117**: the identity authority stays the sole
  credential authority and the converged admission gate stays the
  sole authorization runtime; the M018 records are operational
  evidence riding credential REFERENCES (content-derived ids, sorted
  reference sets — opaque, never authority).  Imports flow one way:
  ``credentials/`` imports the accepted authorities (identity,
  federation, client — and through them contracts, evidence,
  offers); NO accepted authority imports ``credentials/``.
- **LOCK-106**: the emergency path's evidence references resolve to
  REAL typed evidence records inside the real evidence store
  (consumed by reference from the accepted evidence/ typing).
- **LOCK-118**: every record carries typed provenance (issuer +
  content-derived ids).
- **LOCK-119**: no wall clock, no randomness, no network, no
  secrets; content-derived ids over canonical JSON; canonical-JSON
  round-trips with tamper-evident ids re-verified at
  deserialization.

Harvest disclosure (R8 charter M018 scope): the legacy 1.0 reservoir
is source material only — the credential-drill disciplines are
re-expressed on the accepted 1.1 authorities inside this package;
the legacy packages are NOT imported, NOT modified.
"""

from __future__ import annotations

from .errors import CredentialLifecycleError, CredentialLifecycleReason
from .model import (
    ADMITTING_AUTHORIZATION_VERDICTS,
    ADMITTING_LIFECYCLE_VERDICTS,
    CREDENTIALS_ISSUER,
    CREDENTIALS_PREFIX,
    EMERGENCY_STEP_KINDS,
    INVENTORY_BREAK_KINDS,
    OPERATION_KINDS,
    PROPAGATION_ISSUER,
    AdmissionProbe,
    EmergencyStep,
    InventoryAuditRecord,
    InventoryTrace,
    LifecycleFold,
    LifecycleOperationRecord,
    PropagationPlan,
    admitted_set_from_records,
    check_removal_is_atomic,
    check_rotation_flip_is_atomic,
    check_zero_coverage_gap,
    consumer_observed_revocation,
    derive_operation_id,
    derive_probe_id,
    plan_propagation,
    probe_from_mapping,
    record_from_mapping,
    round_deliveries,
)
from .journal import LifecycleJournal, fold_operations
from .rotation import admitted_set, run_revocation_drill, run_rotation_drill
from .propagation import propagation_verdict, run_revocation_propagation
from .emergency import run_emergency_revocation, verify_emergency_evidence
from .inventory import journal_inventory_audit, run_inventory_audit
from .gate import (
    admission_gate_world,
    check_credential_admission,
    probe_credential_admission,
)

__all__ = [
    # typed errors
    "CredentialLifecycleError",
    "CredentialLifecycleReason",
    # frozen vocabularies
    "OPERATION_KINDS",
    "EMERGENCY_STEP_KINDS",
    "INVENTORY_BREAK_KINDS",
    "ADMITTING_LIFECYCLE_VERDICTS",
    "ADMITTING_AUTHORIZATION_VERDICTS",
    "CREDENTIALS_PREFIX",
    "CREDENTIALS_ISSUER",
    "PROPAGATION_ISSUER",
    # typed records
    "LifecycleOperationRecord",
    "EmergencyStep",
    "PropagationPlan",
    "AdmissionProbe",
    "InventoryTrace",
    "InventoryAuditRecord",
    "LifecycleFold",
    # the journal (the fold is the sole writer of the replayed view)
    "LifecycleJournal",
    "fold_operations",
    # the pure kernels
    "admitted_set_from_records",
    "check_rotation_flip_is_atomic",
    "check_removal_is_atomic",
    "check_zero_coverage_gap",
    "derive_operation_id",
    "derive_probe_id",
    "plan_propagation",
    "round_deliveries",
    "consumer_observed_revocation",
    "record_from_mapping",
    "probe_from_mapping",
    # the drills (the accepted authorities driven by reference)
    "admitted_set",
    "run_rotation_drill",
    "run_revocation_drill",
    # revocation propagation (deterministic rounds, declared bounds)
    "run_revocation_propagation",
    "propagation_verdict",
    # the emergency path (distinct, typed, journaled, evidence-visible)
    "run_emergency_revocation",
    "verify_emergency_evidence",
    # the inventory audit (fail closed)
    "run_inventory_audit",
    "journal_inventory_audit",
    # the admission gate (composed from the accepted surfaces)
    "admission_gate_world",
    "probe_credential_admission",
    "check_credential_admission",
]
