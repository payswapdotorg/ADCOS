"""ADCOS local-first partition-tolerant admission (M016 — Local-First
and Offline Operation).

The partition-tolerant admission gates — the charter's core M016
discipline, in the accepted raising-gate + typed-twin convention (the
``replan/validation.py`` pattern: :func:`replan.validate_constraints_
preserved` raises, :func:`replan.candidate_verdict` is the non-raising
twin the engine consumes):

- :func:`check_authority_fresh` — the RAISING freshness gate: a local
  authority snapshot past its declared freshness bound at the decision
  instant fails closed ``localfirst-authority-stale`` (NEVER a silent
  allow); an instant before the window opens fails closed
  ``localfirst-authority-not-yet-valid``.  Inclusive bounds,
  deterministic, injected instants only.
- :func:`check_admission_preserves_contract` — the RAISING LOCK-108
  gate across the offline boundary: the claimed constraint set through
  the CONSUMED M008 gate (``replan.validate_constraints_preserved``,
  BY REFERENCE — never duplicated); a set that drops, relaxes or
  re-interprets ANY hard contract constraint fails closed
  ``localfirst-constraint-weakened`` citing the specific kinds (the
  consumed gate's deterministic text preserved; the
  ``resilience/failover.py`` wrap precedent); a reordered/tampered set
  fails closed ``localfirst-constraint-mismatch``.
- :func:`admit_operation` — the typed TWIN: the partition-tolerant
  admission decision as a journaled
  :class:`~localfirst.model.OfflineOperation` record — ``admitted``, or
  the fail-closed rejection classes (``stale-rejected`` /
  ``not-yet-valid-rejected`` / ``weakened-rejected``).  Every decision
  CARRIES the authority's declared freshness window (the journal fold
  MECHANICALLY rejects a forged admitted record outside its carried
  window).  A rejected admission is JOURNALED — fail-closed is
  evidence, never a silent allow and never a silent drop.
- :func:`authority_snapshot` — the snapshot constructor helper: builds
  the :class:`~localfirst.model.AuthoritySnapshot` FROM the accepted
  ``ConnectivityContract`` (the contract's own LOCK-108 fingerprint
  consumed — never recomputed), with the declared freshness window and
  the authority's opaque records.

Determinism (LOCK-111/LOCK-119): same inputs -> the same decision
record byte-identically; injected instants only; no wall clock, no
randomness, no network, no secrets.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from contracts import (
    ConnectivityContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
)

from replan import (
    ReplanError,
    validate_constraints_preserved as _consumed_validate_constraints,
)

from .errors import LocalFirstError, LocalFirstReason
from .model import (
    AuthoritySnapshot,
    LOCALFRESH_ISSUER,
    OfflineOperation,
    derive_snapshot_id,
)

__all__ = [
    "check_authority_fresh",
    "check_admission_preserves_contract",
    "admit_operation",
    "authority_snapshot",
]


def authority_snapshot(
    contract: ConnectivityContract,
    authority_records: Sequence[OpaqueReference],
    *,
    fresh_from: str,
    fresh_until: str,
    recorded_at: str,
    provenance: Optional[Provenance] = None,
) -> AuthoritySnapshot:
    """Build one authority snapshot FROM the accepted contract (the
    local replica's typed view of the authority material).

    The snapshot's ``contract_id`` cites the OWNING canonical contract
    and its ``constraint_fingerprint`` is the CONTRACT's own LOCK-108
    fingerprint (``hard_constraint_fingerprint()`` — consumed, never
    recomputed here); the resynchronization re-verifies the equality
    against the live contract, so a forged or stale authority view
    fails closed there.  ``authority_records`` are the authority's
    current records as opaque ``execution-artifact`` references
    (LOCK-117: DATA, never authority; unique values).
    """
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "authority_snapshot requires a contracts.ConnectivityContract "
            "(got %s) — the contract is the sole authority (LOCK-101)"
            % type(contract).__name__,
        )
    if provenance is None:
        provenance = Provenance(
            issuer=LOCALFRESH_ISSUER,
            decision_refs=(contract.contract_id,),
        )
    elif not isinstance(provenance, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    # the constructor derives the content identities over the full core
    # (snapshot_id "" -> derived; tamper-evident)
    return AuthoritySnapshot(
        snapshot_id="",
        contract_id=contract.contract_id,
        authority_records=tuple(authority_records),
        fresh_from=fresh_from,
        fresh_until=fresh_until,
        constraint_fingerprint=contract.hard_constraint_fingerprint(),
        recorded_at=recorded_at,
        provenance=provenance,
    )


def check_authority_fresh(snapshot: AuthoritySnapshot, decided_at: str) -> str:
    """The RAISING freshness gate (fail-closed, never a silent allow):
    fail closed ``localfirst-authority-stale`` when ``decided_at`` is
    PAST the snapshot's declared freshness bound, or
    ``localfirst-authority-not-yet-valid`` when it PRECEDES the
    window's opening; return ``fresh`` otherwise (inclusive bounds)."""
    if not isinstance(snapshot, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "check_authority_fresh requires a localfirst AuthoritySnapshot "
            "(got %s)" % type(snapshot).__name__,
        )
    outcome = snapshot.freshness_outcome(decided_at)
    if outcome == "stale":
        raise LocalFirstError(
            LocalFirstReason.AUTHORITY_STALE,
            "the local authority snapshot is PAST its declared freshness "
            "bound at %s (the window %s..%s has expired) — a local state "
            "past its declared freshness bound NEVER silently authorizes "
            "(the admission is rejected, fail-closed)"
            % (decided_at, snapshot.fresh_from, snapshot.fresh_until),
        )
    if outcome == "not-yet-valid":
        raise LocalFirstError(
            LocalFirstReason.AUTHORITY_NOT_YET_VALID,
            "the decision instant %s PRECEDES the authority's declared "
            "freshness window (%s..%s) — the snapshot is not yet the "
            "authority's declaration (the admission is rejected, "
            "fail-closed)" % (decided_at, snapshot.fresh_from, snapshot.fresh_until),
        )
    return outcome


def check_admission_preserves_contract(
    contract: ConnectivityContract,
    claimed_constraints: Sequence[HardConstraint],
    *,
    subject_value: str,
) -> None:
    """The RAISING LOCK-108 gate across the offline boundary: the
    claimed constraint set through the CONSUMED M008 gate
    (:func:`replan.validate_constraints_preserved`, BY REFERENCE —
    never duplicated).  A claimed set that drops, relaxes or
    re-interprets ANY hard contract constraint fails closed
    ``localfirst-constraint-weakened`` citing the specific kinds; a
    reordered/tampered set fails closed
    ``localfirst-constraint-mismatch``."""
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "check_admission_preserves_contract requires a "
            "contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(claimed_constraints, (tuple, list)) or isinstance(
        claimed_constraints, (str, bytes)
    ):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "claimed_constraints must be a sequence of HardConstraint records",
        )
    try:
        _consumed_validate_constraints(
            tuple(claimed_constraints),
            contract.hard_constraints,
            contract.hard_constraint_fingerprint(),
            label="the local admission of %s" % subject_value[:32],
        )
    except ReplanError as error:
        if error.code == "replan-constraint-weakened":
            raise LocalFirstError(
                LocalFirstReason.CONSTRAINT_WEAKENED,
                "%s (LOCK-108 across the offline boundary: a local admission "
                "that would weaken ANY hard contract constraint is REJECTED, "
                "never a silent weakening)" % error.detail,
            ) from None
        raise LocalFirstError(
            LocalFirstReason.CONSTRAINT_MISMATCH,
            "the claimed constraint set failed the consumed M008 LOCK-108 "
            "gate: %s" % error.detail,
        ) from None


def admit_operation(
    contract: ConnectivityContract,
    snapshot: AuthoritySnapshot,
    *,
    episode_id: str,
    sequence: int,
    subject: OpaqueReference,
    claimed_constraints: Sequence[HardConstraint],
    decided_at: str,
    provenance: Optional[Provenance] = None,
) -> OfflineOperation:
    """Decide ONE partition-tolerant local admission against the
    freshness-bounded authority snapshot — the typed TWIN of the two
    raising gates (the journaled outcome record; a rejected admission
    is JOURNALED: fail-closed is evidence, never a silent allow and
    never a silent drop).

    Gates (ordered, fail-closed):

    1. **Attribution** — the snapshot must be attributable to exactly
       the owning contract (``localfirst-id-mismatch`` otherwise — a
       raised typed rejection, not an outcome).
    2. **The declared freshness window** — ``decided_at`` inside the
       window (inclusive bounds) -> the admission may proceed; PAST
       ``fresh_until`` -> the ``stale-rejected`` outcome (a local
       state past its declared freshness bound NEVER silently
       authorizes); BEFORE ``fresh_from`` -> the
       ``not-yet-valid-rejected`` outcome.
    3. **LOCK-108 across the offline boundary** — the claimed
       constraint set through the CONSUMED M008 gate: a set that
       drops, relaxes or re-interprets ANY hard constraint -> the
       ``weakened-rejected`` outcome; a reordered/tampered set ->
       ``localfirst-constraint-mismatch`` (raised — the fingerprint
       discipline is tamper evidence, not an admission outcome).

    The returned :class:`~localfirst.model.OfflineOperation` carries
    the outcome, the freshness window, the claimed constraints
    verbatim (DATA — the ``ReplanCandidate`` precedent) and the
    subject; the position-independent content identity is the
    idempotency key (a retried admission never double-applies).
    """
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "admit_operation requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(snapshot, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "admit_operation requires a localfirst AuthoritySnapshot (got %s)"
            % type(snapshot).__name__,
        )
    if not isinstance(subject, OpaqueReference):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "admit_operation requires its subject as an OpaqueReference record",
        )
    if not isinstance(claimed_constraints, (tuple, list)) or isinstance(
        claimed_constraints, (str, bytes)
    ):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "claimed_constraints must be a sequence of HardConstraint records",
        )
    if provenance is None:
        provenance = Provenance(
            issuer=LOCALFRESH_ISSUER,
            decision_refs=(episode_id, snapshot.snapshot_id, subject.value),
        )
    elif not isinstance(provenance, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    # gate 1: attribution (the snapshot rides exactly the contract)
    if snapshot.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the authority snapshot is attributable to contract %s, not %s — "
            "a local admission rides exactly its owning contract"
            % (snapshot.contract_id[:23], contract.contract_id[:23]),
        )

    # gate 2: the declared freshness window (fail-closed stale-authority
    # rejection — never a silent allow)
    freshness = snapshot.freshness_outcome(decided_at)
    if freshness == "stale":
        return _build_operation(
            episode_id=episode_id,
            contract_id=contract.contract_id,
            sequence=sequence,
            subject=subject,
            claimed_constraints=tuple(claimed_constraints),
            decided_at=decided_at,
            fresh_from=snapshot.fresh_from,
            fresh_until=snapshot.fresh_until,
            outcome="stale-rejected",
            provenance=provenance,
        )
    if freshness == "not-yet-valid":
        return _build_operation(
            episode_id=episode_id,
            contract_id=contract.contract_id,
            sequence=sequence,
            subject=subject,
            claimed_constraints=tuple(claimed_constraints),
            decided_at=decided_at,
            fresh_from=snapshot.fresh_from,
            fresh_until=snapshot.fresh_until,
            outcome="not-yet-valid-rejected",
            provenance=provenance,
        )

    # gate 3: LOCK-108 across the offline boundary — the CONSUMED M008
    # gate (BY REFERENCE, never duplicated)
    try:
        _consumed_validate_constraints(
            tuple(claimed_constraints),
            contract.hard_constraints,
            contract.hard_constraint_fingerprint(),
            label="the local admission of %s" % subject.value[:32],
        )
    except ReplanError as error:
        if error.code == "replan-constraint-weakened":
            return _build_operation(
                episode_id=episode_id,
                contract_id=contract.contract_id,
                sequence=sequence,
                subject=subject,
                claimed_constraints=tuple(claimed_constraints),
                decided_at=decided_at,
                fresh_from=snapshot.fresh_from,
                fresh_until=snapshot.fresh_until,
                outcome="weakened-rejected",
                provenance=provenance,
            )
        raise LocalFirstError(
            LocalFirstReason.CONSTRAINT_MISMATCH,
            "the claimed constraint set failed the consumed M008 LOCK-108 "
            "gate: %s" % error.detail,
        ) from None

    return _build_operation(
        episode_id=episode_id,
        contract_id=contract.contract_id,
        sequence=sequence,
        subject=subject,
        claimed_constraints=tuple(claimed_constraints),
        decided_at=decided_at,
        fresh_from=snapshot.fresh_from,
        fresh_until=snapshot.fresh_until,
        outcome="admitted",
        provenance=provenance,
    )


def _build_operation(
    *,
    episode_id: str,
    contract_id: str,
    sequence: int,
    subject: OpaqueReference,
    claimed_constraints: Tuple[HardConstraint, ...],
    decided_at: str,
    fresh_from: str,
    fresh_until: str,
    outcome: str,
    provenance: Provenance,
) -> OfflineOperation:
    """Construct one typed admission record (the position-independent
    content identity is the idempotency key)."""
    return OfflineOperation(
        operation_id="",
        episode_id=episode_id,
        contract_id=contract_id,
        sequence=sequence,
        kind="connectivity-admission",
        recorded_at=decided_at,
        provenance=provenance,
        subject=subject,
        hard_constraints=claimed_constraints,
        fresh_from=fresh_from,
        fresh_until=fresh_until,
        outcome=outcome,
    )
