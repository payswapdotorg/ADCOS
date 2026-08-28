"""Management-plane audit authority (WORK-030): the tamper-evident
audit ledger.

Every management API call -- allowed OR denied -- produces exactly one
audit record (spec/architecture.md P11: "Every materially important
routing, authorization, capability, session, and federation decision
must have machine-verifiable evidence"; section 19: "audit evidence
for privileged operations").

Tamper evidence (the WORK-030 acceptance criterion "audit logs are
immutable or tamper-evident") is a sha256 hash CHAIN:

    record_id_n = sha256(record_id_{n-1} + "|" + canonical(content_n))

so every record's id covers its own content AND the entire prefix
chain (a sequential Merkle chain).  ``AuditLedger.verify_chain``
recomputes the chain from record 1 and reports the first break:

- mutating any field of any record breaks that record's id and every
  later linkage;
- deleting a record breaks its successor's ``prev_digest``;
- reordering breaks linkage immediately;
- appending a forged record changes ``chain_head()``, which exists
  precisely so deployments can pin/notarize the head externally
  (evidence retention, spec/architecture.md 5.6).

Immutability is structural: the history lives in an IMMUTABLE tuple in
closure cells of the constructor frame (the accepted WORK-027
closure-owned authority discipline) rebound only via ``nonlocal``
inside the genuine append path -- there is NO instance attribute
holding the ledger, no mutation API, no removal API, and no way to
rewrite history through the public surface.  In-place tampering
requires interpreted-frame closure surgery, and even a wholesale
tuple replacement cannot forge continuity with any externally pinned
head.

Honest boundary (documented, tested): tamper evidence detects IN-PLACE
tampering mechanically; a wholesale replacement of the entire ledger
by an attacker who also controls every externally pinned head is
outside what an in-repo ledger can prove -- that is what external
notarization of ``chain_head()`` is for.  The record payload itself
carries deterministic diagnostics only, never secrets (section 20
privacy discipline).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .errors import ManagementError, ManagementReasonCode
from .model import (
    AuditOutcome,
    AuditRecord,
    ManagementOperation,
    derive_audit_record_id,
    require_instant,
)


def _recompute_chain(
    history: Tuple[AuditRecord, ...],
) -> "AuditVerification":
    """Recompute the chain over a history tuple (a module-level PURE
    function so the public callables' closure cells hold DATA ONLY --
    the accepted closure-owned discipline).  Any in-place tampering
    (field mutation, deletion, reordering, forged insertion) breaks
    at a specific sequence."""
    prev = ""
    for index, record in enumerate(history):
        expected_sequence = index + 1
        if record.sequence != expected_sequence:
            return AuditVerification(
                ok=False,
                checked=index,
                head=prev,
                first_break_sequence=expected_sequence,
            )
        if record.prev_digest != prev:
            return AuditVerification(
                ok=False,
                checked=index,
                head=prev,
                first_break_sequence=record.sequence,
            )
        if derive_audit_record_id(prev, record) != record.record_id:
            return AuditVerification(
                ok=False,
                checked=index,
                head=prev,
                first_break_sequence=record.sequence,
            )
        prev = record.record_id
    return AuditVerification(
        ok=True,
        checked=len(history),
        head=prev,
        first_break_sequence=0,
    )


@dataclass(frozen=True)
class AuditVerification:
    """The result of :meth:`AuditLedger.verify_chain` (DATA)."""

    ok: bool
    checked: int
    head: str
    first_break_sequence: int  # 0 when ok (no break)

    def __post_init__(self) -> None:
        if not isinstance(self.checked, int) or self.checked < 0:
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit verification checked must be a non-negative int",
            )
        if self.ok and self.first_break_sequence != 0:
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit verification cannot be ok with a break sequence",
            )
        if not self.ok and self.first_break_sequence < 1:
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit verification break sequence must be >= 1",
            )


class AuditLedger:
    """The append-only, tamper-evident audit ledger.

    Construction is parameterless; the ledger starts empty (head
    ``""``).  Appending is performed by the management API layer (the
    composition root) -- the ledger itself performs no authorization;
    it records outcomes the API hands it, with strict structural
    validation.
    """

    def __init__(self) -> None:
        history: Tuple[AuditRecord, ...] = ()
        lock = threading.Lock()

        def append(
            *,
            recorded_instant: str,
            operation: str,
            operator_node_id: str,
            outcome: str,
            detail: str,
            evidence_refs: Tuple[str, ...] = (),
        ) -> AuditRecord:
            """Append one record (the ONLY mutation; content-derived
            chained id minted HERE, never caller-supplied)."""
            nonlocal history
            require_instant(recorded_instant, "audit recorded_instant")
            if operation not in ManagementOperation.values():
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "audit operation %r is not a frozen management "
                    "operation" % (operation,),
                )
            if outcome not in AuditOutcome.values():
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "audit outcome %r is not a frozen audit outcome"
                    % (outcome,),
                )
            if not isinstance(operator_node_id, str) or not operator_node_id:
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "audit operator_node_id must be a non-empty string",
                )
            if not isinstance(detail, str):
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "audit detail must be a string",
                )
            if not isinstance(evidence_refs, tuple):
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "audit evidence_refs must be a tuple of strings",
                )
            with lock:
                sequence = len(history) + 1
                prev = history[-1].record_id if history else ""
                probe = AuditRecord(
                    record_id="0" * 64,
                    sequence=sequence,
                    recorded_instant=recorded_instant,
                    operation=operation,
                    operator_node_id=operator_node_id,
                    outcome=outcome,
                    detail=detail,
                    evidence_refs=tuple(evidence_refs),
                    prev_digest=prev,
                )
                record = AuditRecord(
                    record_id=derive_audit_record_id(prev, probe),
                    sequence=probe.sequence,
                    recorded_instant=probe.recorded_instant,
                    operation=probe.operation,
                    operator_node_id=probe.operator_node_id,
                    outcome=probe.outcome,
                    detail=probe.detail,
                    evidence_refs=probe.evidence_refs,
                    prev_digest=probe.prev_digest,
                )
                history = history + (record,)
            return record

        def records() -> Tuple[AuditRecord, ...]:
            """The full append-only history (read-only tuple of
            immutable records)."""
            return history

        def chain_head() -> str:
            """The current head digest ("" when empty) -- the value to
            pin/notarize externally for evidence retention."""
            return history[-1].record_id if history else ""

        def verify_chain() -> AuditVerification:
            """Recompute the chain from record 1.  Any in-place
            tampering (field mutation, deletion, reordering, forged
            insertion) breaks at a specific sequence."""
            return _recompute_chain(history)

        def snapshot() -> Dict[str, Any]:
            """A JSON-shaped read-only snapshot (deterministic)."""
            verification = _recompute_chain(history)
            return {
                "record_count": len(history),
                "chain_head": history[-1].record_id if history else "",
                "chain_ok": verification.ok,
                "records": [record.content_dict() for record in history],
            }

        # The public surface: EXACTLY these instance-attribute
        # callables.  The history lives in closure cells only.
        self.append = append
        self.records = records
        self.chain_head = chain_head
        self.verify_chain = verify_chain
        self.snapshot = snapshot

    def public_surface(self) -> Tuple[str, ...]:
        """The sorted names of the public instance-attribute callables
        (the complete public surface of this object)."""
        return tuple(sorted(k for k in vars(self) if not k.startswith("_")))

    def __repr__(self) -> str:  # pragma: no cover -- trivial
        return "AuditLedger(records=%d)" % len(self.records())


__all__ = [
    "AuditLedger",
    "AuditVerification",
]
