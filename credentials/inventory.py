"""ADCOS credential inventory verification (M018 — Credential and
Key Lifecycle Operations).

CREDENTIAL INVENTORY VERIFICATION: every admitted credential traces
to a valid lifecycle record — an inventory audit that FAILS CLOSED
(an admitted credential without a complete lifecycle record chain is
a TYPED FAILURE, never a warning).

The audit is a PURE READ over the accepted authorities (by
reference): the identity store's own public records
(``CredentialStore.list_records`` — never the secret path), the
journal's folded admitted set, and the accepted M014
credential-lifecycle bookkeeping.  For every credential in the
admitted set the audit verifies:

1. the reference RESOLVES to an identity record (else the typed
   ``unknown-reference`` break);
2. the record's status IS ACTIVE — the journal's admitted set and
   the identity authority agree (else ``status-mismatch``: the local
   admitted set is never silently trusted over the authority);
3. the record carries its activation instant (else
   ``missing-activation``);
4. the (node, role) key-version chain is a GAPLESS run 1..max with
   each generation present exactly once and only the maximum
   generation admitted (else ``generation-gap``);
5. the accepted M014 bookkeeping records the activation (else
   ``bookkeeping-missing`` — the consumed M014 evaluation would
   itself fail closed).

And over the node's FULL record set: every SUPERSEDED generation
carries its supersession instant (else ``missing-supersession``) and
every REVOKED record carries its revocation metadata (else
``missing-revocation-info``).

A clean audit returns the typed :class:`InventoryAuditRecord` (the
per-credential trace with the journaled operation references that
produced each admitted state — the full lifecycle chain).  Any break
raises the typed ``credential-inventory-incomplete`` failure citing
the break kind and the credential (the audit is journaled by the
caller through the ordinary journal discipline when desired).
"""

from __future__ import annotations

from typing import Dict

from identity.convergence import (
    CredentialLifecyclePolicy,
    CredentialLifecycleState,
    evaluate_credential_lifecycle,
)
from identity.lifecycle import LifecycleState
from identity.node_id import NodeID

from .errors import CredentialLifecycleError, CredentialLifecycleReason
from .journal import LifecycleJournal
from .model import (
    CREDENTIALS_ISSUER,
    INVENTORY_BREAK_KINDS,
    InventoryAuditRecord,
    InventoryTrace,
    LifecycleOperationRecord,
    _wrap_consumed_error,
)

__all__ = ["run_inventory_audit", "journal_inventory_audit"]


def _records_for_node(store, node_id: NodeID) -> list:
    records = [
        record
        for record in store.list_records()
        if record.node_id == node_id
    ]
    return records


def _inventory_failure(break_kind: str, credential_ref: str, detail: str) -> None:
    if break_kind not in INVENTORY_BREAK_KINDS:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.VOCABULARY,
            "unknown inventory break kind %r (frozen vocabulary only)"
            % (break_kind,),
        )
    raise CredentialLifecycleError(
        CredentialLifecycleReason.INVENTORY_INCOMPLETE,
        "inventory audit failed closed [%s]: %s (an admitted credential "
        "without a complete lifecycle chain is a typed failure — never a "
        "warning)" % (break_kind, detail),
    )


def run_inventory_audit(
    *,
    journal: LifecycleJournal,
    store,
    m014_state: CredentialLifecycleState,
    policy: CredentialLifecyclePolicy,
    node_id: NodeID,
    at_instant: str,
) -> InventoryAuditRecord:
    """The fail-closed inventory audit over the journal's folded
    admitted set, the identity authority's own records and the
    accepted M014 bookkeeping.  Returns the typed audit record (with
    the per-credential trace) ONLY when every admitted credential
    traces to a complete lifecycle record chain; any break raises the
    typed ``credential-inventory-incomplete`` failure citing the
    break kind."""
    if not isinstance(journal, LifecycleJournal):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_inventory_audit requires a LifecycleJournal",
        )
    if not isinstance(m014_state, CredentialLifecycleState):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_inventory_audit requires the accepted M014 "
            "CredentialLifecycleState (by reference)",
        )
    if not isinstance(policy, CredentialLifecyclePolicy):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_inventory_audit requires the accepted M014 "
            "CredentialLifecyclePolicy (by reference)",
        )
    if not isinstance(node_id, NodeID) or node_id.text != journal.node_id:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ID_MISMATCH,
            "the inventory audit requires the journal's own node (%r)"
            % (journal.node_id,),
        )
    if store is None or not hasattr(store, "list_records"):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_inventory_audit requires the accepted identity "
            "CredentialStore public read surface (by reference — never the "
            "secret path)",
        )
    fold = journal.fold()
    admitted = fold.current_admitted()
    records = _records_for_node(store, node_id)
    by_reference = {
        record.reference.reference_id: record for record in records
    }

    # -- every admitted credential traces to a valid lifecycle record --
    for ref in admitted:
        record = by_reference.get(ref)
        if record is None:
            _inventory_failure(
                "unknown-reference",
                ref,
                "the admitted credential has no record in the identity "
                "store",
            )
        if record.status is not LifecycleState.ACTIVE:
            _inventory_failure(
                "status-mismatch",
                ref,
                "the journal admits the credential but the identity "
                "authority's record status is %r (the local admitted set "
                "is never silently trusted over the authority)"
                % (record.status.value,),
            )
        if record.activated_at is None:
            _inventory_failure(
                "missing-activation",
                ref,
                "the ACTIVE credential carries no activation instant (an "
                "incomplete lifecycle chain)",
            )
        with _wrap_consumed_error("the M014 lifecycle evaluation"):
            try:
                verdict = evaluate_credential_lifecycle(
                    policy, m014_state, ref, at_instant
                )
            except CredentialLifecycleError:
                raise
            except Exception as error:  # noqa: BLE001 - consumed typed error
                # the consumed M014 evaluation failing closed on an
                # ADMITTED credential means the bookkeeping does not
                # carry its activation — the typed inventory break
                _inventory_failure(
                    "bookkeeping-missing",
                    ref,
                    "the consumed M014 evaluation failed closed (%s: %s) — "
                    "the bookkeeping does not carry the admitted "
                    "credential's activation"
                    % (
                        getattr(error, "code", "error"),
                        getattr(error, "detail", error),
                    ),
                )
        if verdict.verdict not in ("ok", "rotation-due"):
            _inventory_failure(
                "bookkeeping-missing",
                ref,
                "the consumed M014 verdict for the admitted credential is "
                "%r — the bookkeeping disagrees with the admitted state "
                "(fail closed)" % (verdict.verdict,),
            )

    # -- the node's full record set: complete chains, gapless versions --
    for record in records:
        if record.status is LifecycleState.SUPERSEDED:
            if record.superseded_at is None:
                _inventory_failure(
                    "missing-supersession",
                    record.reference.reference_id,
                    "the SUPERSEDED generation carries no supersession "
                    "instant (an incomplete lifecycle chain)",
                )
        if record.status is LifecycleState.REVOKED and record.revoked is None:
            _inventory_failure(
                "missing-revocation-info",
                record.reference.reference_id,
                "the REVOKED credential carries no revocation metadata "
                "(an incomplete lifecycle chain)",
            )
    roles = sorted({record.role for record in records})
    for role in roles:
        versions = sorted(
            record.key_version
            for record in records
            if record.role == role
        )
        if versions != list(range(1, len(versions) + 1)):
            _inventory_failure(
                "generation-gap",
                "cred:%s:%s:*" % (node_id.text, role),
                "the (node, role) key-version chain %s is not a gapless "
                "run from 1 (a generation is missing from the chain)"
                % (versions,),
            )
        for record in records:
            if (
                record.role == role
                and record.status is LifecycleState.ACTIVE
                and record.key_version != max(versions)
            ):
                _inventory_failure(
                    "generation-gap",
                    record.reference.reference_id,
                    "an ACTIVE credential is not the maximum generation of "
                    "its role chain (versions %s)" % (versions,),
                )

    # -- the clean typed audit record (the full per-credential trace) --
    operation_refs: Dict[str, str] = {}
    for record in fold.records:
        if record.subject_ref and record.subject_ref not in operation_refs:
            operation_refs[record.subject_ref] = record.operation_id
        if (
            record.replacement_ref
            and record.replacement_ref not in operation_refs
        ):
            operation_refs[record.replacement_ref] = record.operation_id
    traces = tuple(
        InventoryTrace(
            credential_ref=ref,
            status=by_reference[ref].status.value,
            key_version=by_reference[ref].key_version,
            activated_at=by_reference[ref].activated_at or "",
            operation_refs=(
                (operation_refs[ref],) if ref in operation_refs else ()
            ),
        )
        for ref in admitted
    )
    audit = InventoryAuditRecord(
        audit_id="",
        node_id=node_id.text,
        audited_at=at_instant,
        admitted_count=len(admitted),
        traces=traces,
    )
    return audit


def journal_inventory_audit(
    journal: LifecycleJournal,
    audit: InventoryAuditRecord,
    *,
    at_instant: str,
) -> LifecycleOperationRecord:
    """Journal one COMPLETED clean audit as lifecycle evidence (the
    ``inventory-audit`` operation kind: read-only — the authoritative
    admitted set is unchanged, mechanically enforced by the record
    kernel).  Only a clean audit can be journaled (a broken chain
    raised at :func:`run_inventory_audit` and never produced a
    record — the failure is the typed error, never a warning)."""
    if not isinstance(journal, LifecycleJournal):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "journal_inventory_audit requires a LifecycleJournal",
        )
    if not isinstance(audit, InventoryAuditRecord):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "journal_inventory_audit requires an InventoryAuditRecord",
        )
    if audit.node_id != journal.node_id:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ID_MISMATCH,
            "the audit for node %r cannot be journaled on the journal of "
            "node %r" % (audit.node_id, journal.node_id),
        )
    return journal.append(
        LifecycleOperationRecord(
            operation_id="",
            kind="inventory-audit",
            sequence=len(journal) + 1,
            node_id=journal.node_id,
            recorded_at=at_instant,
            subject_ref="",
            before_admitted=journal.fold().current_admitted(),
            after_admitted=journal.fold().current_admitted(),
            evidence_refs=(audit.audit_id,),
            provenance=CREDENTIALS_ISSUER,
        )
    )
