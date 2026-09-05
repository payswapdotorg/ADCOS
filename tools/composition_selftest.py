#!/usr/bin/env python3
"""W054 deterministic composition-conformance battery."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from composition import (  # noqa: E402
    COMPOSITION_STAGES,
    STAGE_AUTHORITIES,
    CompositionError,
    CompositionReasonCode,
    CompositionRequest,
    CompositionRuntime,
    InMemoryCompositionStore,
    StageReceipt,
    compose_developer_request,
)
from composition.runtime import CompositionJournalRecord  # noqa: E402


@dataclass
class Fixture:
    calls: List[Tuple[str, str]]


def fixture_executor(fixture: Fixture):
    def execute(stage: str, request: CompositionRequest, previous: Tuple[StageReceipt, ...], key: str) -> StageReceipt:
        fixture.calls.append((stage, key))
        return StageReceipt(
            stage=stage,
            authority=STAGE_AUTHORITIES[stage],
            operation="compose.%s" % stage.lower(),
            status="observed" if stage == "CANONICAL_OBSERVATION" else "accepted",
            reference="ref-%02d" % (COMPOSITION_STAGES.index(stage) + 1),
            evidence_refs=("evidence-%02d" % (COMPOSITION_STAGES.index(stage) + 1),),
            metadata={"source": "authority-test-double", "stage_index": COMPOSITION_STAGES.index(stage)},
        )
    return execute


def executors_for(fixture: Fixture) -> Dict[str, object]:
    return {stage: fixture_executor(fixture) for stage in COMPOSITION_STAGES}


def request(intent: Optional[Mapping[str, object]] = None, request_id: str = "request-001") -> CompositionRequest:
    return CompositionRequest(
        request_id=request_id,
        actor="application-001",
        source="developer-api",
        intent=dict(intent or {"bandwidth_kbps": 1000, "region": "EU"}),
    )


def expect_error(fn, reason: str) -> None:
    try:
        fn()
    except CompositionError as exc:
        assert exc.reason == reason, (exc.reason, reason)
        return
    raise AssertionError("expected %s" % reason)


def expect_type_error(fn) -> None:
    try:
        fn()
    except TypeError:
        return
    raise AssertionError("expected TypeError")


def run_once(seed: Optional[str] = None) -> bytes:
    env = dict(os.environ)
    if seed is None:
        env.pop("PYTHONHASHSEED", None)
    else:
        env["PYTHONHASHSEED"] = seed
    return subprocess.check_output([sys.executable, __file__, "--once"], cwd=str(ROOT), env=env)


def full_suite() -> Tuple[int, str]:
    total = 0
    index = {stage: i for i, stage in enumerate(COMPOSITION_STAGES)}

    fixture = Fixture([])
    runtime = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(fixture))
    req = request()
    result = runtime.compose(req)
    assert tuple(r.stage for r in result.receipts) == COMPOSITION_STAGES
    assert [stage for stage, _ in fixture.calls] == list(COMPOSITION_STAGES)
    total += 1

    before = list(fixture.calls)
    replay = runtime.compose(req)
    assert replay.to_dict() == result.to_dict()
    assert fixture.calls == before
    total += 1

    expect_error(lambda: runtime.compose(request({"bandwidth_kbps": 2000})), CompositionReasonCode.REQUEST_CONFLICT)
    total += 1

    adapter_fixture = Fixture([])
    adapter_runtime = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(adapter_fixture))
    developer_result = compose_developer_request(
        runtime=adapter_runtime,
        request={"request_id": "developer-001", "actor": "application-001", "source": "developer-api", "intent": {"bandwidth_kbps": 1000, "region": "EU"}},
    )
    assert developer_result.receipts[0].authority == "WORK-046"
    total += 1

    payment_result = CompositionRuntime(
        store=InMemoryCompositionStore(), executors=executors_for(Fixture([]))
    ).compose(request(request_id="payment-order"))
    assert index["PAYMENT_RECONCILIATION"] > index["NETWORK_PATH_VALIDATION"]
    assert index["PAYMENT_RECONCILIATION"] > index["CONTAINMENT"]
    assert index["PAYMENT_RECONCILIATION"] > index["DELIVERY"]
    assert payment_result.receipts[index["PAYMENT_RECONCILIATION"]].authority == "WORK-044"
    total += 1

    assert set(STAGE_AUTHORITIES.values()) <= {
        "WORK-012", "WORK-041", "WORK-044", "WORK-045", "WORK-046", "WORK-047",
        "WORK-048", "WORK-051", "WORK-052", "WORK-053",
    }
    total += 1

    def bad_executor(stage, req, previous, key):
        return StageReceipt(stage=stage, authority="WORK-053", operation="bad", status="accepted", reference="bad")

    bad_exec = {stage: bad_executor for stage in COMPOSITION_STAGES}
    expect_error(
        lambda: CompositionRuntime(store=InMemoryCompositionStore(), executors=bad_exec).compose(request(request_id="bad-authority")),
        CompositionReasonCode.AUTHORITY_INVALID,
    )
    total += 1

    store = InMemoryCompositionStore()
    market_fixture = Fixture([])
    CompositionRuntime(store=store, executors=executors_for(market_fixture)).compose(request(request_id="marketplace"))
    records = store.records("marketplace")
    assert records[index["MARKETPLACE_SELECTION"]].stage == "MARKETPLACE_SELECTION"
    assert records[index["NETWORK_PATH_VALIDATION"]].stage == "NETWORK_PATH_VALIDATION"
    total += 1

    expect_error(
        lambda: StageReceipt(stage="CONTAINMENT", authority="WORK-048", operation="containment", status="accepted", reference="containment", metadata={"physical_pass": True}),
        CompositionReasonCode.PHYSICAL_CLAIM,
    )
    total += 1

    client_result = CompositionRuntime(
        store=InMemoryCompositionStore(), executors=executors_for(Fixture([]))
    ).compose(request(request_id="client-state"))
    assert client_result.receipts[0].authority == "WORK-046"
    assert "canonical_state" not in client_result.receipts[0].to_dict()["metadata"]
    total += 1

    assert COMPOSITION_STAGES[-1] == "CANONICAL_OBSERVATION"
    assert STAGE_AUTHORITIES[COMPOSITION_STAGES[-1]] == "WORK-046"
    total += 1

    expect_error(
        lambda: InMemoryCompositionStore().append(
            CompositionJournalRecord(
                request_id="x",
                request_digest=req.digest(),
                stage="DELIVERY",
                idempotency_key=CompositionRuntime.idempotency_key(req, "DELIVERY"),
                receipt=StageReceipt(stage="DELIVERY", authority="WORK-048", operation="delivery", status="accepted", reference="x"),
            )
        ),
        CompositionReasonCode.STAGE_ORDER,
    )
    total += 1

    r1 = request({"region": "EU", "bandwidth_kbps": 1000}, request_id="determinism")
    r2 = request({"bandwidth_kbps": 1000, "region": "EU"}, request_id="determinism")
    assert r1.digest() == r2.digest()
    total += 1

    a = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(Fixture([]))).compose(req)
    b = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(Fixture([]))).compose(req)
    assert a.digest == b.digest
    total += 1

    expect_error(
        lambda: compose_developer_request(
            runtime=runtime,
            request={"request_id": "bad-shape", "actor": "application-001", "source": "developer-api", "intent": {"x": 1}, "canonical_state": "forged"},
        ),
        CompositionReasonCode.INVALID_INPUT,
    )
    total += 1

    expect_error(
        lambda: StageReceipt(stage="DEVELOPER_API", authority="WORK-054", operation="forged", status="accepted", reference="x"),
        CompositionReasonCode.AUTHORITY_INVALID,
    )
    total += 1

    original = {"bandwidth_kbps": 1000, "region": "EU"}
    frozen_request = request(original, request_id="nested-request")
    digest_before = frozen_request.digest()
    original["bandwidth_kbps"] = 9000
    assert frozen_request.digest() == digest_before
    expect_type_error(lambda: frozen_request.intent.__setitem__("x", 1))
    total += 1

    metadata = {"note": "immutable"}
    receipt = StageReceipt(stage="DEVELOPER_API", authority="WORK-046", operation="compose", status="accepted", reference="x", metadata=metadata)
    metadata["note"] = "mutated-outside"
    assert receipt.metadata["note"] == "immutable"
    expect_type_error(lambda: receipt.metadata.__setitem__("note", "forged"))
    total += 1

    return total, a.digest


def main() -> int:
    once = len(sys.argv) > 1 and sys.argv[1] == "--once"
    total, digest = full_suite()
    if once:
        print("Result: PASS (%d conformance groups)" % total)
        print("Digest: %s" % digest)
        return 0
    outputs = {"0": run_once("0"), "1": run_once("1"), "7919": run_once("7919"), "unset": run_once(None)}
    assert outputs["0"] == outputs["1"] == outputs["7919"] == outputs["unset"]
    assert run_once("0") == outputs["0"]
    print("Result: PASS (%d conformance groups)" % total)
    print("Seed/repeat determinism: PASS (0/1/7919/unset, repeated execution, byte-identical)")
    print(outputs["0"].decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
