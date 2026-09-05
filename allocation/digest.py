"""WORK-053 EconomicAllocation deterministic digest helpers.

The evidence chain of the economic-allocation ledger: every
digest is content-derived over canonical JSON (WORK-003) from
recorded facts only -- identical logical histories produce
byte-identical digests, with no clock, randomness, or
environment dependence.

- :func:`state_digest` -- the folded allocation state (the
  policy-registry digest and the sorted per-allocation
  projection digests; the per-allocation projection carries
  sorted reference/compensation audit lists, so the state digest
  is arrival-order independent for the same admitted set);
- :func:`command_ledger_digest` -- the durable idempotency
  ledger (admitted command ids and digests, in journal order);
- :func:`evidence_index_digest` -- the injected evidence index
  snapshot;
- :func:`assemble_digest_stream` -- the canonical evidence
  document (journal digest, state digest, ledger digest, event
  list digest, evidence index digest) used by the two-run and
  hash-seed determinism proofs.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .evidence import AllocationEvidenceIndex
from .journal import AppendOnlyAllocationJournal
from .ledger import AllocationFoldState
from .model import (
    AllocationEvent,
    AllocationTransaction,
    allocation_transaction_digest,
    event_list_digest,
    policy_registry_digest,
)


def state_digest(fold: AllocationFoldState) -> str:
    """Deterministic digest over the folded allocation state.

    Iteration is over sorted policy/allocation ids, so the
    digest is insertion-order independent and byte-identical for
    identical logical states.
    """
    content: Dict[str, Any] = {
        "kind": "allocation-state",
        "policy_registry_digest": policy_registry_digest(
            fold.policies
        ),
        "policy_count": len(fold.policies),
        "allocations": [
            {
                "usage_transaction_id": (
                    transaction.usage_transaction_id
                ),
                "digest": allocation_transaction_digest(transaction),
            }
            for transaction in _sorted_allocations(fold)
        ],
        "allocation_count": len(fold.allocations),
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def _sorted_allocations(
    fold: AllocationFoldState,
) -> Tuple[AllocationTransaction, ...]:
    return tuple(
        fold.allocations[key] for key in sorted(fold.allocations)
    )


def command_ledger_digest(
    ledger: Mapping[str, Mapping[str, str]]
) -> str:
    """Deterministic digest over the durable command ledger (the
    public :meth:`AllocationLedger.command_ledger` mapping)."""
    entries = [
        {
            "command_id": command_id,
            "command_digest": entry["command_digest"],
            "event_id": entry["event_id"],
        }
        for command_id, entry in sorted(ledger.items())
    ]
    content = {"kind": "allocation-command-ledger", "commands": entries}
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def evidence_index_digest(index: AllocationEvidenceIndex) -> str:
    """Deterministic digest over the injected evidence index
    snapshot (sorted usage/reference ids)."""
    content = {
        "kind": "allocation-evidence-index",
        **index.to_dict(),
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


def assemble_digest_stream(
    *,
    journal: AppendOnlyAllocationJournal,
    fold: AllocationFoldState,
    index: AllocationEvidenceIndex,
) -> str:
    """The canonical deterministic evidence document.

    One canonical JSON document binding: the journal digest, the
    folded state digest, the command-ledger digest, the event
    list digest, and the evidence index digest.  Two runs of the
    identical command history over the identical injected clock
    produce byte-identical documents (the battery proves this
    in-process and under PYTHONHASHSEED 0/1/7919/unset).
    """
    events: Tuple[AllocationEvent, ...] = journal.events()
    content: Dict[str, Any] = {
        "kind": "allocation-digest-stream",
        "record_count": len(journal),
        "journal_digest": journal.journal_digest(),
        "state_digest": state_digest(fold),
        "command_ledger_digest": command_ledger_digest(
            journal.command_ledger()
        ),
        "event_list_digest": event_list_digest(events),
        "evidence_index_digest": evidence_index_digest(index),
    }
    return canonical_json_bytes(content).decode("utf-8")


def digest_of(text: str) -> str:
    """A plain sha256 hex digest of a UTF-8 document (battery
    helper for byte-equality proofs)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
