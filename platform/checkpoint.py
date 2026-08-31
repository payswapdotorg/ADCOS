"""WORK-042 durable checkpoints (compact snapshots bound to the
journal).

A checkpoint is the COMPACT durable state representation of ACR-006
section 3:

    reconciled state (the fold output at position P)
        + the journal position P (sequence)
        + the journal prefix digest at P (the binding)
        + the session-binding REFERENCES the process held at P
        = recoverable state, reconstructible deterministically

Binding discipline (battery-pinned):

- the checkpoint records the journal TAIL it was cut from: loading
  verifies ``prefix_digest(P) == journal_tail_digest`` and that the
  journal is at least P records long; a mismatch (a checkpoint
  ahead of the journal, a truncated journal, or a tampered binding)
  fails closed with ``CHECKPOINT_MISMATCH`` -- never a silent
  fallback to full replay;
- the recorded state must BE the true fold of the prefix: recovery
  recomputes ``fold(records[:P])`` and compares it to the recorded
  state; a fabricated or stale state fails closed;
- ``checkpoint_id`` is content-derived over the full checkpoint
  content (tamper evidence at construction and on load);
- no secret material: the checkpoint carries references, digests,
  observation payloads of the accepted technology-neutral models,
  and instants only.

Checkpoints are periodically REPLACED (that is the compact-snapshot
model); the journal itself is never rewritten.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import PlatformError, PlatformReasonCode
from .journal import JournalRecord, record_list_digest
from .model import SessionBindingRef
from .state import ReconciledState

#: The schema discriminator of the persisted checkpoint payload
#: (incompatible payloads fail closed at load).
CHECKPOINT_SCHEMA = "adcos.platform.checkpoint.v1"


def derive_checkpoint_id(content: Dict[str, Any]) -> str:
    """The content-derived checkpoint fingerprint (identity DATA)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


@dataclass(frozen=True)
class PlatformCheckpoint:
    """One compact durable snapshot bound to a journal position.

    Content binding: ``checkpoint_id`` MUST equal the fingerprint of
    the checkpoint content -- enforced at construction (empty id
    means "derive it"; a non-empty id must match), so a tampered or
    deserialized checkpoint can never carry an attacker-chosen id.
    """

    checkpoint_id: str
    schema: str
    reconciled_state: ReconciledState
    journal_tail_sequence: int
    journal_tail_digest: str
    session_bindings: Tuple[SessionBindingRef, ...]
    produced_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint_id, str):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "checkpoint_id must be a string",
            )
        if self.schema != CHECKPOINT_SCHEMA:
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint schema %r is not %r (incompatible durable "
                "state -- fail closed)" % (self.schema, CHECKPOINT_SCHEMA),
            )
        if not isinstance(self.reconciled_state, ReconciledState):
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint reconciled_state must be a ReconciledState",
            )
        if (
            isinstance(self.journal_tail_sequence, bool)
            or not isinstance(self.journal_tail_sequence, int)
            or self.journal_tail_sequence < 0
        ):
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint journal_tail_sequence must be a non-negative "
                "integer",
            )
        if (
            not isinstance(self.journal_tail_digest, str)
            or not self.journal_tail_digest.startswith("sha256:")
        ):
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint journal_tail_digest must be a sha256 digest",
            )
        bindings = list(self.session_bindings)
        keys = [binding.binding_key() for binding in bindings]
        if len(keys) != len(set(keys)):
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "duplicate session binding references in a checkpoint",
            )
        if not isinstance(self.produced_at, str) or not self.produced_at:
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint produced_at must be a non-empty instant string",
            )
        expected = derive_checkpoint_id(self.content())
        if self.checkpoint_id == "":
            object.__setattr__(self, "checkpoint_id", expected)
        elif self.checkpoint_id != expected:
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint_id %r does not match the derived fingerprint "
                "%r (content binding -- tampered or misbound checkpoint "
                "rejected)" % (self.checkpoint_id[:80], expected[:80]),
            )

    def content(self) -> Dict[str, Any]:
        """The canonical checkpoint content (identity input)."""
        return {
            "schema": self.schema,
            "reconciled_state": self.reconciled_state.to_dict(),
            "journal_tail_sequence": self.journal_tail_sequence,
            "journal_tail_digest": self.journal_tail_digest,
            "session_bindings": [
                binding.to_dict() for binding in self.session_bindings
            ],
            "produced_at": self.produced_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self.content()
        payload["checkpoint_id"] = self.checkpoint_id
        return payload

    @classmethod
    def from_dict(cls, data: object) -> "PlatformCheckpoint":
        if not isinstance(data, Mapping):
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint must be a mapping",
            )
        raw_bindings = data.get("session_bindings", [])
        if not isinstance(raw_bindings, (list, tuple)):
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint session_bindings must be a sequence",
            )
        return cls(
            checkpoint_id=str(data.get("checkpoint_id", "")),
            schema=str(data.get("schema", "")),
            reconciled_state=ReconciledState.from_dict(
                data.get("reconciled_state", {})
            ),
            journal_tail_sequence=int(data.get("journal_tail_sequence", -1)),
            journal_tail_digest=str(data.get("journal_tail_digest", "")),
            session_bindings=tuple(
                SessionBindingRef.from_dict(item) for item in raw_bindings
            ),
            produced_at=str(data.get("produced_at", "")),
        )

    def to_bytes(self) -> bytes:
        """The canonical durable payload (the on-medium form)."""
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_bytes(cls, payload: bytes) -> "PlatformCheckpoint":
        """Load and verify a durable checkpoint payload (fail
        closed on malformed bytes)."""
        import json as _json

        if not isinstance(payload, bytes) or payload == b"":
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint payload must be non-empty bytes",
            )
        try:
            data = _json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_INVALID,
                "checkpoint payload is not valid JSON (%s -- corrupt "
                "durable state, fail closed)" % type(error).__name__,
            ) from error
        return cls.from_dict(data)


def build_checkpoint(
    *,
    state: ReconciledState,
    records: List[JournalRecord],
    session_bindings: Tuple[SessionBindingRef, ...],
    produced_at: str,
) -> PlatformCheckpoint:
    """Cut one checkpoint from the CURRENT journal position.

    The binding values are computed from the live record list, so
    the returned checkpoint is bound to the journal prefix at the
    moment of the call (persist-before-suspend: the caller persists
    it immediately through the store).
    """
    if not isinstance(state, ReconciledState):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "state must be a ReconciledState",
        )
    for record in records:
        if not isinstance(record, JournalRecord):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "records must be JournalRecord values",
            )
    return PlatformCheckpoint(
        checkpoint_id="",
        schema=CHECKPOINT_SCHEMA,
        reconciled_state=state,
        journal_tail_sequence=len(records),
        journal_tail_digest=record_list_digest(records),
        session_bindings=tuple(
            sorted(session_bindings, key=lambda item: item.binding_key())
        ),
        produced_at=produced_at,
    )


__all__ = [
    "CHECKPOINT_SCHEMA",
    "PlatformCheckpoint",
    "build_checkpoint",
    "derive_checkpoint_id",
]
