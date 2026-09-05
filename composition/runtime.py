"""W054 deterministic, resumable composition orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Protocol, Tuple

from protocol.canonicalization import canonical_json_bytes

from .model import (
    COMPOSITION_STAGES,
    CompositionError,
    CompositionReasonCode,
    CompositionRequest,
    CompositionResult,
    StageReceipt,
)


class StageExecutor(Protocol):
    """Public seam implemented by the already-accepted domain authorities.

    The executor must delegate to the authority that owns the stage.  It may
    not persist canonical state in the composition layer.  ``idempotency_key``
    is stable for the request/stage pair so authority-owned retry semantics can
    suppress duplicate side effects.
    """

    def __call__(
        self,
        stage: str,
        request: CompositionRequest,
        previous: Tuple[StageReceipt, ...],
        idempotency_key: str,
    ) -> StageReceipt:
        ...


@dataclass(frozen=True)
class CompositionJournalRecord:
    request_id: str
    request_digest: str
    stage: str
    idempotency_key: str
    receipt: StageReceipt


class CompositionStore(Protocol):
    """Persistence seam for orchestration receipts only."""

    def records(self, request_id: str) -> Tuple[CompositionJournalRecord, ...]:
        ...

    def append(self, record: CompositionJournalRecord) -> None:
        ...


class InMemoryCompositionStore:
    """Reference store used by conformance tests.

    Production deployments provide an equivalent durable store.  The stored
    records are orchestration receipts, not domain-state projections.
    """

    def __init__(self) -> None:
        self._records: Dict[str, Tuple[CompositionJournalRecord, ...]] = {}

    def records(self, request_id: str) -> Tuple[CompositionJournalRecord, ...]:
        return self._records.get(request_id, ())

    def append(self, record: CompositionJournalRecord) -> None:
        current = self._records.get(record.request_id, ())
        if current:
            previous = current[-1]
            if previous.stage == record.stage:
                if previous.idempotency_key != record.idempotency_key or previous.receipt.to_dict() != record.receipt.to_dict():
                    raise CompositionError(
                        CompositionReasonCode.STORE_CORRUPT,
                        "conflicting receipt for already-recorded composition stage",
                    )
                return
        expected_index = len(current)
        if record.stage != COMPOSITION_STAGES[expected_index]:
            raise CompositionError(
                CompositionReasonCode.STAGE_ORDER,
                "cannot append %s at journal position %d" % (record.stage, expected_index),
            )
        self._records[record.request_id] = current + (record,)


class CompositionRuntime:
    """Sequence the fixed product flow while delegating authority ownership.

    W054 owns only the ordering, request/stage idempotency key derivation and
    orchestration receipt history.  It never creates canonical commercial,
    connectivity, payment, session, usage, allocation, or client state.
    """

    def __init__(self, *, store: CompositionStore, executors: Dict[str, StageExecutor]) -> None:
        if not isinstance(store, CompositionStore) and not hasattr(store, "append"):
            raise CompositionError(CompositionReasonCode.INVALID_INPUT, "store must implement the composition store seam")
        if set(executors) != set(COMPOSITION_STAGES):
            missing = sorted(set(COMPOSITION_STAGES) - set(executors))
            extra = sorted(set(executors) - set(COMPOSITION_STAGES))
            raise CompositionError(
                CompositionReasonCode.INVALID_INPUT,
                "executor map must cover exactly the frozen stages; missing=%s extra=%s" % (missing, extra),
            )
        self._store = store
        self._executors = dict(executors)

    @staticmethod
    def idempotency_key(request: CompositionRequest, stage: str) -> str:
        if stage not in COMPOSITION_STAGES:
            raise CompositionError(CompositionReasonCode.INVALID_INPUT, "unknown stage %r" % stage)
        payload = {"request_digest": request.digest(), "stage": stage}
        return "sha256:" + sha256(canonical_json_bytes(payload)).hexdigest()

    @staticmethod
    def _validate_records(
        request: CompositionRequest, records: Tuple[CompositionJournalRecord, ...]
    ) -> Tuple[StageReceipt, ...]:
        receipts = []
        for index, record in enumerate(records):
            expected_stage = COMPOSITION_STAGES[index]
            if record.request_id != request.request_id:
                raise CompositionError(CompositionReasonCode.STORE_CORRUPT, "record request identity mismatch")
            if record.request_digest != request.digest():
                raise CompositionError(CompositionReasonCode.REQUEST_CONFLICT, "stored composition belongs to different request content")
            if record.stage != expected_stage or record.receipt.stage != expected_stage:
                raise CompositionError(CompositionReasonCode.STAGE_ORDER, "stored composition stages are not in frozen order")
            expected_key = CompositionRuntime.idempotency_key(request, expected_stage)
            if record.idempotency_key != expected_key:
                raise CompositionError(CompositionReasonCode.STORE_CORRUPT, "stored stage idempotency key is not content-derived")
            receipts.append(record.receipt)
        return tuple(receipts)

    def compose(self, request: CompositionRequest) -> CompositionResult:
        records = self._store.records(request.request_id)
        receipts = self._validate_records(request, records)
        if len(receipts) == len(COMPOSITION_STAGES):
            payload = {"request": request.to_dict(), "receipts": [r.to_dict() for r in receipts], "final_status": receipts[-1].status}
            digest = "sha256:" + sha256(canonical_json_bytes(payload)).hexdigest()
            return CompositionResult(request, receipts, receipts[-1].status, digest)

        for index in range(len(receipts), len(COMPOSITION_STAGES)):
            stage = COMPOSITION_STAGES[index]
            key = self.idempotency_key(request, stage)
            receipt = self._executors[stage](stage, request, receipts, key)
            if not isinstance(receipt, StageReceipt) or receipt.stage != stage:
                raise CompositionError(CompositionReasonCode.RECEIPT_INVALID, "executor returned an invalid receipt for %s" % stage)
            new_record = CompositionJournalRecord(
                request_id=request.request_id,
                request_digest=request.digest(),
                stage=stage,
                idempotency_key=key,
                receipt=receipt,
            )
            self._store.append(new_record)
            receipts = receipts + (receipt,)

        payload = {"request": request.to_dict(), "receipts": [r.to_dict() for r in receipts], "final_status": receipts[-1].status}
        digest = "sha256:" + sha256(canonical_json_bytes(payload)).hexdigest()
        return CompositionResult(request, receipts, receipts[-1].status, digest)
