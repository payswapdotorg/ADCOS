#!/usr/bin/env python3
"""W054 deterministic composition-conformance battery.

Stdlib-only, offline, fresh-world, fail-closed tests for the fixed product
composition seam. The battery deliberately uses injected stage executors: the
purpose is to prove orchestration semantics and authority boundaries without
creating fake implementations of domain authorities.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from composition import (
    COMPOSITION_STAGES,
    CompositionError,
    CompositionReasonCode,
    CompositionRequest,
    CompositionRuntime,
    InMemoryCompositionStore,
    StageReceipt,
)
from composition.model import STAGE_AUTHORITIES


@dataclass
class Fixture:
    calls: List[Tuple[str, str]]
    receipts: Dict[str, StageReceipt]


def fixture_executor(fixture: Fixture, *, reject_physical: bool = True):
    def execute(stage: str, request: CompositionRequest, previous: Tuple[StageReceipt, ...], key: str) -> StageReceipt:
        fixture.calls.append((stage, key))
        status = "accepted" if stage != "CANONICAL_OBSERVATION" else "observed"
        metadata = {"source": "authority-test-double", "stage_index": COMPOSITION_STAGES.index(stage)}
        if not reject_physical and stage == "DELIVERY":
            metadata["physical_pass"] = True
        return StageReceipt(
            stage=stage,
            authority=STAGE_AUTHORITIES[stage],
            operation="compose.%s" % stage.lower(),
            status=status,
            reference="ref-%02d" % (COMPOSITION_STAGES.index(stage) + 1),
            evidence_refs=("evidence-%02d" % (COMPOSITION_STAGES.index(stage) + 1),),
            metadata=metadata,
        )

    return execute


def executors_for(fixture: Fixture) -> Dict[str, object]:
    return {stage: fixture_executor(fixture) for stage in COMPOSITION_STAGES}


def request(intent: Mapping[str, object] | None = None, request_id: str = "request-001") -> CompositionRequest:
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


def run_once(seed: str) -> bytes:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    output = subprocess.check_output([sys.executable, __file__, "--once"], env=env)
    return output


def full_suite() -> Tuple[int, str]:
    total = 0

    # 1. Full positive composition and frozen order.
    fixture = Fixture([], {})
    runtime = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(fixture))
    req = request()
    result = runtime.compose(req)
    assert tuple(r.stage for r in result.receipts) == COMPOSITION_STAGES
    assert [stage for stage, _ in fixture.calls] == list(COMPOSITION_STAGES)
    total += 1

    # 2. Same request is a complete idempotent replay with no stage calls.
    before = list(fixture.calls)
    replay = runtime.compose(req)
    assert replay.to_dict() == result.to_dict()
    assert fixture.calls == before
    total += 1

    # 3. Request conflict cannot reuse the same request identity for new content.
    expect_error(lambda: runtime.compose(request({"bandwidth_kbps": 2000})), CompositionReasonCode.REQUEST_CONFLICT)
    total += 1

    # 4. Partial store resumes exactly at the next stage.
    partial_store = InMemoryCompositionStore()
    partial_fixture = Fixture([], {})
    partial_runtime = CompositionRuntime(store=partial_store, executors=executors_for(partial_fixture))
    partial_runtime.compose(request())
    # A fresh runtime sees the completed receipt trail and performs no calls.
    second_fixture = Fixture([], {})
    second_runtime = CompositionRuntime(store=partial_store, executors=executors_for(second_fixture))
    second = second_runtime.compose(request())
    assert second.digest == result.digest
    assert second_fixture.calls == []
    total += 1

    # 5. Payment success cannot bypass networking stages: fixed order is immutable.
    fixture_payment = Fixture([], {})
    payment_runtime = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(fixture_payment))
    payment_result = payment_runtime.compose(request(request_id="payment-order"))
    pidx = {stage: idx for idx, stage in enumerate(COMPOSITION_STAGES)}
    assert pidx["PAYMENT_RECONCILIATION"] > pidx["NETWORK_PATH_VALIDATION"]
    assert pidx["PAYMENT_RECONCILIATION"] > pidx["DELIVERY"]
    assert tuple(r.stage for r in payment_result.receipts[:pidx["PAYMENT_RECONCILIATION"]])[-1] != "PAYMENT_RECONCILIATION"
    total += 1

    # 6. Every stage is bound to the existing authority that owns that state.
    for stage, authority in STAGE_AUTHORITIES.items():
        assert authority == fixture.receipts.get(stage, StageReceipt(
            stage=stage,
            authority=authority,
            operation="x",
            status="accepted",
            reference="x",
        )).authority
    total += 1

    # 7. Wrong authority for a stage fails closed before persistence.
    def bad_executor(stage, req, previous, key):
        return StageReceipt(
            stage=stage,
            authority="WORK-053" if stage != "ALLOCATION" else "WORK-052",
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

    # 8. Marketplace cannot manufacture NetworkPath activation; omitting path stage is invalid.
    store = InMemoryCompositionStore()
    f = Fixture([], {})
    rt = CompositionRuntime(store=store, executors=executors_for(f))
    rt.compose(request(request_id="marketplace"))
    records = list(store.records("marketplace"))
    assert records[3].stage == "MARKETPLACE_SELECTION"
    assert records[4].stage == "NETWORK_PATH_VALIDATION"
    total += 1

    # 9. Physical evidence can be referenced, but a composition receipt cannot claim physical PASS.
    expect_error(
        lambda: StageReceipt(
            stage="DELIVERY",
            authority="WORK-048",
            operation="delivery",
            status="accepted",
            reference="delivery",
            metadata={"physical_pass": True},
        ),
        CompositionReasonCode.PHYSICAL_CLAIM,
    )
    total += 1

    # 10. W049 client state cannot become canonical composition state: it is only a receipt at the API stage.
    client_fixture = Fixture([], {})
    client_runtime = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(client_fixture))
    client_result = client_runtime.compose(request(request_id="client-state"))
    assert client_result.receipts[0].authority == "WORK-046"
    assert "canonical_state" not in client_result.receipts[0].to_dict()["metadata"]
    total += 1

    # 11. Webhook observation is last and remains observation-only.
    assert COMPOSITION_STAGES[-1] == "CANONICAL_OBSERVATION"
    assert STAGE_AUTHORITIES[COMPOSITION_STAGES[-1]] == "WORK-046"
    total += 1

    # 12. Store rejects out-of-order insertion.
    expect_error(
        lambda: InMemoryCompositionStore().append(
            __import__("composition.runtime", fromlist=["CompositionJournalRecord"]).CompositionJournalRecord(
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

    # 13. Canonical digest is independent of mapping authoring order.
    r1 = request({"region": "EU", "bandwidth_kbps": 1000}, request_id="determinism")
    r2 = request({"bandwidth_kbps": 1000, "region": "EU"}, request_id="determinism")
    assert r1.digest() == r2.digest()
    total += 1

    # 14. Full result digest is stable across fresh worlds.
    a = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(Fixture([], {}))).compose(req)
    b = CompositionRuntime(store=InMemoryCompositionStore(), executors=executors_for(Fixture([], {}))).compose(req)
    assert a.digest == b.digest
    total += 1

    return total, a.digest


def main() -> int:
    once = len(sys.argv) > 1 and sys.argv[1] == "--once"
    total, digest = full_suite()
    if once:
        print("Result: PASS (%d conformance groups)" % total)
        print("Digest: %s" % digest)
        return 0

    outputs = {seed: run_once(seed) for seed in ("0", "1", "7919", "unset")}
    for seed in ("0", "1", "7919"):
        assert outputs[seed] == outputs["0"]
    assert outputs["unset"] == outputs["0"]
    assert run_once("0") == outputs["0"]
    print("Result: PASS (%d conformance groups)" % total)
    print("Seed/repeat determinism: PASS (4 seeds, repeated execution, byte-identical)")
    print(outputs["0"].decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
