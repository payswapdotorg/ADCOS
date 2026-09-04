"""WORK-052 UsageLedger deterministic digest helpers.

The evidence chain of the usage ledger: every digest is
content-derived over canonical JSON (WORK-003) from recorded
facts only -- identical logical histories produce byte-identical
digests, with no clock, randomness, or environment dependence.

- :func:`state_digest` -- the folded usage state (sorted
  transaction ids; per-transaction projection digests; the
  per-transaction projection is itself sorted by observation id,
  so the state digest is arrival-order independent for the same
  admitted set);
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

from .evidence import UsageEvidenceIndex
from .journal import AppendOnlyUsageJournal
from .model import (
    UsageEvent,
    UsageTransaction,
    event_list_digest,
    usage_transaction_digest,
)


def state_digest(transactions: Iterable[UsageTransaction]) -> str:
    """Deterministic digest over the folded usage state.

    Iteration is over sorted transaction ids, so the digest is
    insertion-order independent and byte-identical for identical
    logical states.
    """
    items = [
        {
            "transaction_id": tx.transaction_id,
            "digest": usage_transaction_digest(tx),
        }
        for tx in transactions
    ]
    items.sort(key=lambda item: item["transaction_id"])
    content = {"kind": "usage-state", "transactions": items}
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def command_ledger_digest(
    ledger: Mapping[str, Mapping[str, str]]
) -> str:
    """Deterministic digest over the durable command ledger (the
    public :meth:`UsageLedger.command_ledger` mapping)."""
    entries = [
        {
            "command_id": command_id,
            "command_digest": entry["command_digest"],
            "event_id": entry["event_id"],
        }
        for command_id, entry in sorted(ledger.items())
    ]
    content = {"kind": "usage-command-ledger", "commands": entries}
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def evidence_index_digest(index: UsageEvidenceIndex) -> str:
    """Deterministic digest over the injected evidence index
    snapshot (sorted evidence/transaction ids)."""
    content = {"kind": "usage-evidence-index", **index.to_dict()}
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def assemble_digest_stream(
    *,
    journal: AppendOnlyUsageJournal,
    transactions: Iterable[UsageTransaction],
    index: UsageEvidenceIndex,
) -> str:
    """The canonical deterministic evidence document.

    One canonical JSON document binding: the journal digest, the
    folded state digest, the command-ledger digest, the event
    list digest, and the evidence index digest.  Two runs of the
    identical command history over the identical injected clock
    produce byte-identical documents (the battery proves this
    in-process and under PYTHONHASHSEED 0/1/7919/unset).
    """
    events: Tuple[UsageEvent, ...] = journal.events()
    content: Dict[str, Any] = {
        "kind": "usage-digest-stream",
        "record_count": len(journal),
        "journal_digest": journal.journal_digest(),
        "state_digest": state_digest(transactions),
        "command_ledger_digest": command_ledger_digest(journal.command_ledger()),
        "event_list_digest": event_list_digest(events),
        "evidence_index_digest": evidence_index_digest(index),
    }
    return canonical_json_bytes(content).decode("utf-8")


def digest_of(text: str) -> str:
    """A plain sha256 hex digest of a UTF-8 document (battery
    helper for byte-equality proofs)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
