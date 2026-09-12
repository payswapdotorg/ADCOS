"""ADCOS local-first resynchronization (M016 — Local-First and Offline
Operation).

The explicit reconnect-and-resynchronize core: divergence detection
and DETERMINISTIC CONVERGENCE by the DECLARED RECORDED resolution rule
(the LOCK-111 class), with LOCK-108 enforced across the offline
boundary — never a silent drop, never a silent duplicate.

:func:`resynchronize` — the pure, deterministic convergence of one
OPEN partition episode onto the fresh authority view:

1. **Fail-closed pre-gates** (nothing converges on a rejected input):
   the episode must be OPEN (a closed episode never resynchronizes —
   ``localfirst-episode-closed``); the fresh snapshot must be
   attributable to exactly the owning contract and its LOCK-108
   fingerprint must equal the CONTRACT's own
   (``localfirst-constraint-mismatch`` — a forged or stale authority
   view is rejected whole, never partially trusted); the declared
   resolution rule must be valid (``localfirst-resolution-invalid`` —
   content keys only, never temporal, the consumed M008 key
   vocabulary).
2. **Per-operation re-verification (LOCK-108 across the offline
   boundary)**: every local ADMITTED operation's claimed constraint
   set is re-validated against the LIVE contract through the CONSUMED
   M008 gate (BY REFERENCE): a set that drops, relaxes or
   re-interprets ANY hard constraint is REJECTED with the typed
   :class:`~localfirst.model.ConvergenceRejection` citing the specific
   kinds — never silently converged, never silently dropped.
3. **Divergence detection**: a local admitted subject that also
   appears in the fresh authority view's records is a CONFLICT — typed
   :class:`~localfirst.model.DivergenceRecord` with FULL PROVENANCE
   (the local operation id, the authority record verbatim, the
   declared rule, the resolution outcome).
4. **Deterministic convergence**: each conflict resolves by the
   DECLARED RECORDED rule (both sides projected onto the orderable
   candidate shape over the consumed M008 key vocabulary — the
   projected candidate-kind/candidate-id pair; the default rule lets
   the authority side win, LOCK-101).  Same inputs -> the
   byte-identical resolution, always.
5. **The no-silent-loss invariant** (mechanically enforced on the
   finished result by :class:`~localfirst.model.ResyncResult`): every
   local admitted operation is accounted EXACTLY ONCE across the
   applied set, the divergence citations and the typed rejections —
   never a silent drop, never a silent duplicate.

The admission-time rejections (stale / not-yet-valid / weakened,
journaled at decision time) authorized nothing and converge nothing —
they stay typed evidence in the journal; the resynchronization
accounts the ADMITTED operations.

Determinism (LOCK-111/LOCK-119): pure and order-driven; injected
instants only; no wall clock, no randomness, no network, no secrets;
canonical-JSON round-trips with tamper-evident ids.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from contracts import (
    ConnectivityContract,
    OpaqueReference,
    Provenance,
)

from replan import (
    ReplanError,
    validate_constraints_preserved as _consumed_validate_constraints,
)

from .errors import LocalFirstError, LocalFirstReason
from .journal import OfflineJournal
from .model import (
    AuthoritySnapshot,
    ConvergenceRejection,
    DEFAULT_RESOLUTION_RULE,
    DivergenceRecord,
    LocalState,
    OfflineOperation,
    RESYNC_DRIVEN_ISSUER,
    ResyncResult,
    normalize_resolution_rule,
    resolve_conflict,
)

__all__ = [
    "resynchronize",
]


def resynchronize(
    contract: ConnectivityContract,
    journal: OfflineJournal,
    fresh: AuthoritySnapshot,
    *,
    resolution_rule: Sequence[str] = DEFAULT_RESOLUTION_RULE,
    recorded_at: str,
    provenance: Optional[Provenance] = None,
) -> ResyncResult:
    """Resynchronize one OPEN partition episode onto the fresh
    authority view (the pure deterministic convergence — see the
    module docstring for the full gate order).  Returns the typed
    :class:`~localfirst.model.ResyncResult`; the CALLER drives the
    accepted M015 runtime reconnect and journals the partition exit
    (:mod:`localfirst.offline` — the composition)."""
    if not isinstance(contract, ConnectivityContract):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "resynchronize requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(journal, OfflineJournal):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "resynchronize requires a localfirst OfflineJournal (got %s)"
            % type(journal).__name__,
        )
    if not isinstance(fresh, AuthoritySnapshot):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT,
            "resynchronize requires a localfirst AuthoritySnapshot (got %s)"
            % type(fresh).__name__,
        )

    # gate 1a: the episode must be OPEN (an unopened journal has no
    # state; a closed episode never resynchronizes)
    state: LocalState = journal.state()
    if state.state != "OPEN":
        raise LocalFirstError(
            LocalFirstReason.EPISODE_CLOSED,
            "the partition episode %s is CLOSED; a closed episode never "
            "resynchronizes (a new partition opens a new episode)"
            % state.episode_id[:23],
        )

    # gate 1b: attribution — the fresh view and the episode ride
    # exactly the owning contract
    if fresh.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the fresh authority view is attributable to contract %s, not %s "
            "— a resynchronization converges exactly its owning contract"
            % (fresh.contract_id[:23], contract.contract_id[:23]),
        )
    if state.contract_id != contract.contract_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the partition episode %s rides contract %s, not %s"
            % (
                state.episode_id[:23],
                state.contract_id[:23],
                contract.contract_id[:23],
            ),
        )

    # gate 1c: LOCK-108 on the FRESH VIEW — the snapshot's fingerprint
    # must be the CONTRACT's own (a forged or stale authority view is
    # rejected whole: converging onto weakened authority material is a
    # silent contract weakening across the offline boundary, and it
    # fails closed)
    if fresh.constraint_fingerprint != contract.hard_constraint_fingerprint():
        raise LocalFirstError(
            LocalFirstReason.CONSTRAINT_MISMATCH,
            "the fresh authority view's LOCK-108 fingerprint does not "
            "reproduce the contract's (a forged or stale authority view is "
            "rejected whole — never partially trusted)",
        )

    # gate 1d: the declared resolution rule (the LOCK-111 class)
    rule = normalize_resolution_rule(resolution_rule, "resynchronize.resolution_rule")

    if provenance is None:
        provenance = Provenance(
            issuer=RESYNC_DRIVEN_ISSUER,
            decision_refs=(state.episode_id, fresh.snapshot_id),
        )
    elif not isinstance(provenance, Provenance):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    # the authority record index (unique values — constructor-enforced)
    authority_index: dict = {}
    for record in fresh.authority_records:
        authority_index[record.value] = record

    records = journal.records()
    admitted_records = {
        record.operation_id: record
        for record in records
        if record.kind == "connectivity-admission" and record.outcome == "admitted"
    }

    divergences: list = []
    applied: list = []
    rejected: list = []
    local_winners: set = set()  # authority record values the locals superseded

    # deterministic journal order — the fold's own order
    for operation_id in state.admitted:
        record = admitted_records[operation_id]

        # gate 2: the LOCK-108 re-verification against the LIVE contract
        # (the CONSUMED M008 gate, BY REFERENCE — never duplicated)
        try:
            _consumed_validate_constraints(
                record.hard_constraints,
                contract.hard_constraints,
                contract.hard_constraint_fingerprint(),
                label="the offline operation %s" % record.operation_id[:23],
            )
        except ReplanError as error:
            if error.code == "replan-constraint-weakened":
                # REJECTED with the typed reason citing the kinds —
                # never silently converged, never silently dropped
                rejected.append(
                    ConvergenceRejection(
                        operation_id=record.operation_id,
                        code=LocalFirstReason.CONSTRAINT_WEAKENED,
                        detail=error.detail,
                    )
                )
                continue
            rejected.append(
                ConvergenceRejection(
                    operation_id=record.operation_id,
                    code=LocalFirstReason.CONSTRAINT_MISMATCH,
                    detail=error.detail,
                )
            )
            continue

        # gate 3: divergence detection — the subject on both sides
        subject_value = record.subject.value
        authority_record = authority_index.get(subject_value)
        if authority_record is None:
            # clean convergence: no conflict, the operation applies
            applied.append(operation_id)
            continue

        # gate 4: the deterministic DECLARED RECORDED resolution
        winner = resolve_conflict(
            "local-offline-operation",
            record.operation_id,
            "authority-record",
            authority_record.value,
            rule,
        )
        if winner == "local-offline-operation":
            applied.append(operation_id)
            local_winners.add(authority_record.value)
            resolution = "local-offline-operation"
        else:
            resolution = "authority-record"
        divergences.append(
            DivergenceRecord(
                divergence_id="",
                episode_id=state.episode_id,
                contract_id=state.contract_id,
                subject_value=subject_value,
                local_operation_id=record.operation_id,
                authority_record=authority_record,
                resolution_rule=rule,
                resolution=resolution,
                provenance=Provenance(
                    issuer=RESYNC_DRIVEN_ISSUER,
                    decision_refs=(
                        state.episode_id,
                        record.operation_id,
                        authority_record.value,
                    ),
                ),
            )
        )

    # the converged replica record set: the fresh authority records
    # (snapshot order) minus those the locals superseded, then the
    # applied local subjects (journal order) — deterministic.  Every
    # applied operation is either clean (its subject is not an
    # authority record) or a conflict winner (its subject IS one —
    # the local reference replaces the superseded authority record).
    converged_records: list = [
        record for record in fresh.authority_records if record.value not in local_winners
    ]
    for operation_id in applied:
        converged_records.append(admitted_records[operation_id].subject)

    return ResyncResult(
        resync_id="",
        episode_id=state.episode_id,
        contract_id=state.contract_id,
        base_snapshot_id=state.base_snapshot_id,
        fresh_snapshot_id=fresh.snapshot_id,
        resolution_rule=rule,
        divergences=tuple(divergences),
        applied_operations=tuple(applied),
        rejected_operations=tuple(rejected),
        converged_records=tuple(converged_records),
        recorded_at=recorded_at,
        provenance=provenance,
    )
