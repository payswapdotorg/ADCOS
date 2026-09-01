"""WORK-051 CommercialCore deterministic digest helpers.

The evidence chain of the commercial core: every digest is
content-derived over canonical JSON (WORK-003) from recorded
facts only -- identical logical histories produce byte-identical
digests, with no clock, randomness, or environment dependence.

- :func:`state_digest` -- the folded commercial state (sorted
  transaction ids; per-transaction projection digests);
- :func:`command_ledger_digest` -- the durable idempotency
  ledger (admitted command ids and digests, in journal order);
- :func:`reference_index_digest` -- the injected reference index
  snapshot;
- :func:`assemble_digest_stream` -- the canonical evidence
  document (journal digest, state digest, ledger digest, event
  list digest, reference index digest) used by the two-run and
  hash-seed determinism proofs.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, Tuple

from protocol.canonicalization import canonical_json_bytes

from .journal import AppendOnlyCommercialJournal
from .model import (
    CommercialEvent,
    CommercialTransaction,
    event_list_digest,
    transaction_digest,
)
from .references import ReferenceIndex


def state_digest(transactions: Iterable[CommercialTransaction]) -> str:
    """Deterministic digest over the folded commercial state.

    Iteration is over sorted transaction ids, so the digest is
    insertion-order independent and byte-identical for identical
    logical states.
    """
    items = [
        {"transaction_id": tx.transaction_id, "digest": transaction_digest(tx)}
        for tx in transactions
    ]
    items.sort(key=lambda item: item["transaction_id"])
    content = {"kind": "commercial-state", "transactions": items}
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def command_ledger_digest(
    ledger: Mapping[str, Mapping[str, str]]
) -> str:
    """Deterministic digest over the durable command ledger (the
    public :meth:`CommercialCore.command_ledger` mapping)."""
    entries = [
        {
            "command_id": command_id,
            "command_digest": entry["command_digest"],
            "event_id": entry["event_id"],
        }
        for command_id, entry in sorted(ledger.items())
    ]
    content = {"kind": "commercial-command-ledger", "commands": entries}
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def reference_index_digest(index: ReferenceIndex) -> str:
    """Deterministic digest over the injected reference index
    snapshot (sorted reference ids)."""
    content = {"kind": "commercial-reference-index", **index.to_dict()}
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def assemble_digest_stream(
    *,
    journal: AppendOnlyCommercialJournal,
    transactions: Iterable[CommercialTransaction],
    index: ReferenceIndex,
) -> str:
    """The canonical deterministic evidence document.

    One canonical JSON document binding: the journal digest, the
    folded state digest, the command-ledger digest, the event
    list digest, and the reference index digest.  Two runs of the
    identical command history over the identical injected clock
    produce byte-identical documents (the battery proves this
    in-process and under PYTHONHASHSEED 0/1/7919/unset).
    """
    events: Tuple[CommercialEvent, ...] = journal.events()
    content: Dict[str, Any] = {
        "kind": "commercial-digest-stream",
        "record_count": len(journal),
        "journal_digest": journal.journal_digest(),
        "state_digest": state_digest(transactions),
        "command_ledger_digest": command_ledger_digest(journal.command_ledger()),
        "event_list_digest": event_list_digest(events),
        "reference_index_digest": reference_index_digest(index),
    }
    return canonical_json_bytes(content).decode("utf-8")


def digest_of(text: str) -> str:
    """A plain sha256 hex digest of a UTF-8 document (battery
    helper for byte-equality proofs)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
