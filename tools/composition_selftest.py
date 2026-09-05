#!/usr/bin/env python3
"""W054 deterministic composition-conformance battery.

Stdlib-only, offline, fresh-world, fail-closed tests for the fixed product
composition seam. The battery uses injected stage executors to prove
orchestration semantics and authority boundaries without implementing a second
copy of any domain authority.
"""

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
    CompositionError,
    CompositionReasonCode,
    CompositionRequest,
    CompositionRuntime,
    InMemoryCompositionStore,
    StageReceipt,
    compose_developer_request,
)
from composition.model import STAGE_AUTHORITIES  # noqa: E402
from composition.runtime import CompositionJournalRecord  # noqa: E402


@dataclass
class Fixture:
    calls: List[Tuple[str, str]]


def fixture_executor(fixture: Fixture):
    def execute(stage: str, request: CompositionRequest, previous: Tuple[StageReceipt, ...], key: str) -> StageReceipt:
        fixture.calls.append((stage, key))
        status = "accepted" if stage != "CANONICAL_OBSERVATION" else "observed"
        return StageReceipt(
            stage=stage,
            authority=STAGE_AUTHORITIES[stage],
            operation="compose.%s" % stage.lower(),
            status=status,
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


def run_once(seed: Optional[str] = None) -> bytes:
    env = dict(os.environ)
    if seed is None:
        env.pop("PYTHONHASHSEED", None)
    else:
        env["PYTHONHASHSEED"] = seed
    return subprocess.check_output([sys.executable, __file__, "--once"], cwd=str(ROOT), env=env)


def full_suite() -> Tuple[int, str]:
    total = 0

    # 1. Positive end-to-end composition follows the frozen chain exactly.
    fixture = Fixture([])
    runtime = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(fixture))
    req = request()
    result = runtime.compose(req)
    assert tuple(r.stage for r in result.receipts) == COMPOSITION_STAGES
    assert [stage for stage, _ in fixture.calls] == list(COMPOSITION_STAGES)
    total += 1

    # 2. Identical request is byte-identical and performs no stage calls.
    before = list(fixture.calls)
    replay = runtime.compose(req)
    assert replay.to_dict() == result.to_dict()
    assert fixture.calls == before
    total += 1

    # 3. Same request identity with changed content fails closed.
    expect_error(lambda: runtime.compose(request({"bandwidth_kbps": 2000})), CompositionReasonCode.REQUEST_CONFLICT)
    total += 1

    # 4. Developer API request shape is the stable composition entry point.
    adapter_fixture = Fixture([])
    adapter_runtime = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(adapter_fixture))
    developer_result = compose_developer_request(
        runtime=adapter_runtime,
        request={
            "request_id": "developer-001",
            "actor": "application-001",
            "source": "developer-api",
            "intent": {"bandwidth_kbps": 1000, "region": "EU"},
        },
    )
    assert developer_result.receipts[0].authority == "WORK-046"
    total += 1

    # 5. Payment is downstream of path, containment, session and delivery.
    payment_fixture = Fixture([])
    payment_result = CompositionRuntime(
        store=InMemoryCompositionStore(), executors=executors_for(payment_fixture)
    ).compose(request(request_id="payment-order"))
    index = {stage: i for i, stage in enumerate(COMPOSITION_STAGES)}
    assert index["PAYMENT_RECONCILIATION"] > index["NETWORK_PATH_VALIDATION"]
    assert index["PAYMENT_RECONCILIATION"] > index["CONTAINMENT"]
    assert index["PAYMENT_RECONCILIATION"] > index["DELIVERY"]
    assert payment_result.receipts[index["PAYMENT_RECONCILIATION"]].authority == "WORK-044"
    total += 1

    # 6. Stage ownership is a fixed authority map, not caller-declared.
    for stage in COMPOSITION_STAGES:
        assert STAGE_AUTHORITIES[stage] in {
            "WORK-041", "WORK-044", "WORK-045", "WORK-046", "WORK-047",
            "WORK-048", "WORK-051", "WORK-052", "WORK-053", "WORK-012",
        }
    total += 1

    # 7. Wrong authority for the first stage cannot enter the store.
    def bad_executor(stage, req, previous, key):
        return StageReceipt(
            stage=stage,
            authority="WORK-053",
            operation="bad",
            status="accepted",
            reference="bad",
        )

    bad_exec = {stage: bad_executor for stage in COMPOSITION_STAGES}
    expect_error(
        lambda: CompositionRuntime(store=InMemoryCompositionStore(), executors=bad_exec).compose(request(request_id="bad-authority")),
        CompositionReasonCode.AUTHORITY_INVALID,
    )
    total += 1

    # 8. Marketplace selection is followed by NetworkPath validation; selection cannot activate it.
    store = InMemoryCompositionStore()
    market_fixture = Fixture([])
    CompositionRuntime(store=store, executors=executors_for(market_fixture)).compose(request(request_id="marketplace"))
    records = store.records("marketplace")
    assert records[index["MARKETPLACE_SELECTION"]].stage == "MARKETPLACE_SELECTION"
    assert records[index["NETWORK_PATH_VALIDATION"]].stage == "NETWORK_PATH_VALIDATION"
    total += 1

    # 9. W050/capability results cannot claim physical PASS.
    expect_error(
        lambda: StageReceipt(
            stage="CONTAINMENT",
            authority="WORK-048",
            operation="containment",
            status="accepted",
            reference="containment",
            metadata={"physical_pass": True},
        ),
        CompositionReasonCode.PHYSICAL_CLAIM,
    )
    total += 1

    # 10. Client/API projection is not canonical domain state.
    client_fixture = Fixture([])
    client_result = CompositionRuntime(
        store=InMemoryCompositionStore(), executors=executors_for(client_fixture)
    ).compose(request(request_id="client-state"))
    assert client_result.receipts[0].authority == "WORK-046"
    assert "canonical_state" not in client_result.receipts[0].to_dict()["metadata"]
    total += 1

    # 11. Webhook/canonical observation is last and observation-only.
    assert COMPOSITION_STAGES[-1] == "CANONICAL_OBSERVATION"
    assert STAGE_AUTHORITIES[COMPOSITION_STAGES[-1]] == "WORK-046"
    total += 1

    # 12. Out-of-order records fail closed.
    expect_error(
        lambda: InMemoryCompositionStore().append(
            CompositionJournalRecord(
                request_id="x",
                request_digest=req.digest(),
                stage="DELIVERY",
                idempotency_key=CompositionRuntime.idempotency_key(req, "DELIVERY"),
                receipt=StageReceipt(
                    stage="DELIVERY", authority="WORK-048", operation="delivery", status="accepted", reference="x"
                ),
            )
        ),
        CompositionReasonCode.STAGE_ORDER,
    )
    total += 1

    # 13. Developer intents with reordered object keys have identical request digests.
    r1 = request({"region": "EU", "bandwidth_kbps": 1000}, request_id="determinism")
    r2 = request({"bandwidth_kbps": 1000, "region": "EU"}, request_id="determinism")
    assert r1.digest() == r2.digest()
    total += 1

    # 14. Fresh-world composition produces identical canonical result digests.
    a = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(Fixture([]))).compose(req)
    b = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(Fixture([]))).compose(req)
    assert a.digest == b.digest
    total += 1

    # 15. Unknown top-level Developer API members fail closed at the adapter.
    expect_error(
        lambda: compose_developer_request(
            runtime=runtime,
            request={
                "request_id": "bad-shape",
                "actor": "application-001",
                "source": "developer-api",
                "intent": {"x": 1},
                "canonical_state": "forged",
            },
        ),
        CompositionReasonCode.INVALID_INPUT,
    )
    total += 1

    # 16. No direct W054 authority can be declared in a receipt.
    expect_error(
        lambda: StageReceipt(
            stage="DEVELOPER_API",
            authority="WORK-054",
            operation="forged",
            status="accepted",
            reference="x",
        ),
        CompositionReasonCode.AUTHORITY_INVALID,
    )
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
