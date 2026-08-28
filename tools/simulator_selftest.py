#!/usr/bin/env python3
"""ADCOS network and behavior simulator self-test (WORK-031).

The deterministic scenario / fault-injection / security battery for the
``simulator`` family, mapping the frozen WORK-031 contract to
discriminating cases:

- spec validation fail-closed; injected clock; documented PRNG
                                                       -> cases 01-03
- bootstrap composes the REAL authorities               -> case 04
- deterministic replay (in-process; verify_replay API) -> cases 05, 10
- insertion/order independence; seed and time
  reproducibility; cross-process determinism           -> cases 06-09
- fault injection: link down/degraded, partition +
  recovery, restart/rejoin, session failure, cleanup
  failure (explicit pending)                           -> cases 11-15
- observation: resources, telemetry, session full chain,
  multipath + mobility                                 -> cases 16-19
- policy behavior: deny-by-default, amend/withdraw,
  malformed material                                    -> cases 20-22
- simulator-vs-authority state separation; no private
  authority mutation; provenance discipline; forged
  authority objects rejected; no second authority; no
  wall clock                                           -> cases 23-28
- universal event failure boundary (hostile authority);
  rejected events advance nothing                      -> cases 29-30
- the explicit, restored test seam (purpose required;
  restored/validated/degraded verdicts)                -> cases 31-33
- serialization round trips; frozen import surface;
  compilation; CI wiring; frozen spec/docs; frozen API;
  hash-seed determinism                                -> cases 34-40
- PR #34 round-1 review corrections: W013 multipath
  digest boundary; transactional partitions; failed-event
  mutation-ledger preservation; content-derived bootstrap
  identity                                              -> cases 41-44
"""

from __future__ import annotations

import ast
import os
import py_compile
import subprocess
import sys
from typing import Any, Callable, Dict, List, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from simulator import (  # noqa: E402
    AuthorityTestSeam,
    DeterministicStream,
    EventKind,
    EventVerdict,
    MutationOutcome,
    ScenarioClock,
    ScenarioPolicyRule,
    ScenarioResult,
    ScenarioSpec,
    ScheduledEvent,
    SimulatedLinkSpec,
    SimulatedNodeSpec,
    Simulator,
    SimulatorError,
    SimulatorReasonCode,
    authority_digest,
    result_from_mapping,
    spec_from_mapping,
    spec_to_mapping,
    verify_replay,
)
from simulator.environment import SimulatedEnvironment  # noqa: E402

Result = Tuple[str, bool, str]

_NODE_A = "adcos:node:sim.profile.v1:" + "a" * 64
_NODE_B = "adcos:node:sim.profile.v1:" + "b" * 64
_NODE_C = "adcos:node:sim.profile.v1:" + "c" * 64

_START = "2026-06-01T00:00:00Z"
_NOW = "2026-06-01T00:01:00Z"

_SIMULATOR_FILES = tuple(
    os.path.join(REPO, "simulator", name)
    for name in (
        "__init__.py",
        "model.py",
        "time.py",
        "random.py",
        "environment.py",
        "seam.py",
        "runner.py",
        "serialization.py",
    )
)


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


def _nodes() -> Tuple[SimulatedNodeSpec, ...]:
    return (
        SimulatedNodeSpec(node_id=_NODE_A),
        SimulatedNodeSpec(node_id=_NODE_B),
        SimulatedNodeSpec(node_id=_NODE_C, initial_level_millijoules=1_200_000),
    )


def _links() -> Tuple[SimulatedLinkSpec, ...]:
    return (
        SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B, latency_ms=10),
        SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_C, latency_ms=20),
        SimulatedLinkSpec(node_a=_NODE_C, node_b=_NODE_B, latency_ms=20),
    )


def _rules() -> Tuple[ScenarioPolicyRule, ...]:
    return (ScenarioPolicyRule(rule_id="allow-sessions"),)


def _full_events() -> Tuple[ScheduledEvent, ...]:
    """The canonical rich scenario exercising every event kind."""
    return (
        ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.SESSION_REQUEST,
                       payload={"label": "s1", "source": _NODE_A, "destination": _NODE_B}),
        ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.LINK_DEGRADE,
                       payload={"node_a": _NODE_A, "node_b": _NODE_B}),
        ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.PATH_ADD,
                       payload={"label": "s1", "avoid": [[_NODE_A, _NODE_B]]}),
        ScheduledEvent(at_tick=4, sequence=1, kind=EventKind.TELEMETRY_EMIT,
                       payload={"node": _NODE_A, "subject_kind": "energy",
                                "subject_ref": _NODE_A,
                                "metric": "energy-level-millijoules",
                                "value": 3_400_000}),
        ScheduledEvent(at_tick=5, sequence=1, kind=EventKind.RESOURCE_EXHAUST,
                       payload={"node": _NODE_B, "fraction_bp": 500}),
        ScheduledEvent(at_tick=6, sequence=1, kind=EventKind.MOBILITY_HANDOVER,
                       payload={"label": "s1", "avoid": [[_NODE_A, _NODE_C]]}),
        ScheduledEvent(at_tick=7, sequence=1, kind=EventKind.PARTITION_START,
                       payload={"cuts": [[_NODE_A, _NODE_C], [_NODE_C, _NODE_B]]}),
        ScheduledEvent(at_tick=8, sequence=1, kind=EventKind.PARTITION_END,
                       payload={"cuts": [[_NODE_A, _NODE_C], [_NODE_C, _NODE_B]]}),
        ScheduledEvent(at_tick=9, sequence=1, kind=EventKind.NODE_DOWN,
                       payload={"node": _NODE_C}),
        ScheduledEvent(at_tick=10, sequence=1, kind=EventKind.NODE_UP,
                       payload={"node": _NODE_C}),
        ScheduledEvent(at_tick=11, sequence=1, kind=EventKind.OBSERVE, payload={}),
        ScheduledEvent(at_tick=11, sequence=2, kind=EventKind.TELEMETRY_EMIT,
                       payload={"node": _NODE_B, "subject_kind": "energy",
                                "subject_ref": _NODE_B,
                                "metric": "power-draw-milliwatts", "value": 100}),
        ScheduledEvent(at_tick=12, sequence=1, kind=EventKind.SESSION_FAIL,
                       payload={"label": "s1"}),
        ScheduledEvent(at_tick=13, sequence=1, kind=EventKind.CLEANUP,
                       payload={"label": "s1"}),
        ScheduledEvent(at_tick=14, sequence=1, kind=EventKind.POLICY_AMEND,
                       payload={"set_id": "amended", "version": 2,
                                "rules": [{"rule_id": "deny-sessions", "effect": "deny"}]}),
        ScheduledEvent(at_tick=15, sequence=1, kind=EventKind.SESSION_REQUEST,
                       payload={"label": "s2", "source": _NODE_A, "destination": _NODE_B}),
        ScheduledEvent(at_tick=16, sequence=1, kind=EventKind.POLICY_WITHDRAW,
                       payload={"set_id": "amended", "version": 2}),
    )


def _full_spec(seed: int = 42, scenario_id: str = "full-scenario") -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=scenario_id,
        seed=seed,
        start_instant=_START,
        tick_seconds=60,
        horizon_ticks=16,
        nodes=_nodes(),
        links=_links(),
        probes=((_NODE_A, _NODE_B),),
        policy_rules=_rules(),
        events=_full_events(),
    )


def _minimal_spec(seed: int = 1, scenario_id: str = "minimal") -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=scenario_id,
        seed=seed,
        start_instant=_START,
        tick_seconds=60,
        horizon_ticks=2,
        nodes=(SimulatedNodeSpec(node_id=_NODE_A), SimulatedNodeSpec(node_id=_NODE_B)),
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s1", "source": _NODE_A,
                                    "destination": _NODE_B}),
        ),
    )


def _scenario_fingerprint() -> str:
    """A stable digest of the canonical rich scenario (subprocess-safe)."""
    result = Simulator(_full_spec()).run()
    return result.trace_digest


def _record(result: ScenarioResult, kind: str) -> Any:
    for item in result.trace:
        if item.kind == kind:
            return item
    return None


# --------------------------------------------------------------------------
# 1-3: foundations
# --------------------------------------------------------------------------


def case_01_spec_validation_fail_closed() -> Result:
    name = "case_01_spec_validation_fail_closed"
    problems: List[str] = []

    def _rejects(label: str, build: Callable[[], object]) -> None:
        try:
            build()
        except SimulatorError:
            return
        except Exception as error:  # noqa: BLE001
            problems.append("%s raised %r instead of SimulatorError" % (label, error))
            return
        problems.append("%s was accepted" % label)

    def _spec(**overrides: Any) -> ScenarioSpec:
        values: Dict[str, Any] = dict(
            scenario_id="check", seed=1, start_instant=_START, tick_seconds=60,
            horizon_ticks=1, nodes=(SimulatedNodeSpec(node_id=_NODE_A),),
        )
        values.update(overrides)
        return ScenarioSpec(
            scenario_id=values["scenario_id"], seed=values["seed"],
            start_instant=values["start_instant"],
            tick_seconds=values["tick_seconds"],
            horizon_ticks=values["horizon_ticks"], nodes=values["nodes"],
            links=values.get("links", ()), probes=values.get("probes", ()),
            policy_rules=values.get("policy_rules", ()),
            events=values.get("events", ()),
        )

    _rejects("bad scenario id", lambda: _spec(scenario_id="Bad_Id"))
    _rejects("negative seed", lambda: _spec(seed=-1))
    _rejects("bad instant", lambda: _spec(start_instant="not-a-time"))
    _rejects("zero tick", lambda: _spec(tick_seconds=0))
    _rejects("no nodes", lambda: _spec(nodes=()))
    _rejects("unknown endpoint", lambda: _spec(
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),)))
    _rejects("unknown event kind", lambda: _spec(
        events=(ScheduledEvent(at_tick=0, sequence=1, kind="nuke", payload={}),)))
    _rejects("duplicate event key", lambda: _spec(events=(
        ScheduledEvent(at_tick=0, sequence=1, kind=EventKind.OBSERVE, payload={}),
        ScheduledEvent(at_tick=0, sequence=1, kind=EventKind.NODE_DOWN,
                       payload={"node": _NODE_A}),
    )))
    _rejects("event beyond horizon", lambda: _spec(
        events=(ScheduledEvent(at_tick=5, sequence=1,
                               kind=EventKind.OBSERVE, payload={}),)))
    _rejects("non-node node id", lambda: SimulatedNodeSpec(node_id="not-a-node"))
    _rejects("bad power source", lambda: SimulatedNodeSpec(
        node_id=_NODE_A, power_source="dilithium"))
    _rejects("out-of-range threshold", lambda: SimulatedNodeSpec(
        node_id=_NODE_A, survival_threshold_bp=20_000))
    _rejects("bad link metrics", lambda: SimulatedLinkSpec(
        node_a=_NODE_A, node_b=_NODE_B, loss_basis_points=99_999))
    _rejects("bad policy effect", lambda: ScenarioPolicyRule(
        rule_id="r1", effect="maybe"))
    if problems:
        return fail(name, "; ".join(problems))
    if len(EventKind.values()) != 18:
        return fail(name, "event taxonomy size drifted: %d" % len(EventKind.values()))
    if len(SimulatorReasonCode.values()) != 11:
        return fail(name, "reason code vocabulary drifted: %d"
                    % len(SimulatorReasonCode.values()))
    return ok(name, "vocabularies frozen; 13 malformed-spec classes rejected")


def case_02_injected_scenario_clock() -> Result:
    name = "case_02_injected_scenario_clock"
    problems: List[str] = []
    clock = ScenarioClock(_START, 60)
    if clock.instant_at(0) != _START:
        problems.append("tick 0 != start")
    if clock.instant_at(3) != "2026-06-01T00:03:00Z":
        problems.append("tick 3 -> %r" % clock.instant_at(3))
    twin = ScenarioClock(_START, 60)
    if [clock.instant_at(t) for t in range(10)] != [twin.instant_at(t) for t in range(10)]:
        problems.append("clocks diverge")
    for bad_instant in ("not-a-time", "2026-06-01T00:00:00+01:00", ""):
        try:
            ScenarioClock(bad_instant, 60)
            problems.append("instant %r accepted" % bad_instant)
        except SimulatorError:
            pass
    try:
        ScenarioClock(_START, 0)
        problems.append("tick_seconds=0 accepted")
    except SimulatorError:
        pass
    try:
        clock.instant_at(-1)
        problems.append("negative tick accepted")
    except SimulatorError:
        pass
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "tick->instant pure and injected; malformed bases fail closed")


def case_03_documented_prng_stream() -> Result:
    name = "case_03_documented_prng_stream"
    problems: List[str] = []
    stream_a = DeterministicStream(7, label="scenario")
    stream_b = DeterministicStream(7, label="scenario")
    seq_a = [stream_a.uint(1000) for _ in range(64)]
    seq_b = [stream_b.uint(1000) for _ in range(64)]
    if seq_a != seq_b:
        problems.append("same seed diverges")
    if len(set(seq_a)) < 40:
        problems.append("uint(1000) over 64 draws has poor spread (%d distinct)"
                        % len(set(seq_a)))
    other = DeterministicStream(8, label="scenario")
    if [other.uint(1000) for _ in range(64)] == seq_a:
        problems.append("different seed produced the same sequence")
    labeled = DeterministicStream(7, label="other")
    if [labeled.uint(1000) for _ in range(64)] == seq_a:
        problems.append("different label produced the same sequence")
    if stream_a.digest() != stream_b.digest():
        problems.append("digests differ at equal positions")
    before = stream_a.digest()
    stream_a.uint(2)
    if stream_a.digest() == before:
        problems.append("digest insensitive to stream position")
    for bad_bound in (0, -1):
        try:
            DeterministicStream(1).uint(bad_bound)
            problems.append("uint(%d) accepted" % bad_bound)
        except SimulatorError:
            pass
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "sha256 counter stream: seed/label/position sensitive, reproducible")


# --------------------------------------------------------------------------
# 4: bootstrap composes the REAL authorities
# --------------------------------------------------------------------------


def case_04_bootstrap_real_authorities() -> Result:
    name = "case_04_bootstrap_real_authorities"
    sim = Simulator(_minimal_spec())
    result = sim.run()
    bootstrap = result.trace[0] if result.trace else None
    if bootstrap is None or bootstrap.kind != "bootstrap":
        return fail(name, "no bootstrap record")
    mutations = bootstrap.mutations
    registered = [m for m in mutations if m.operation == "register-resource"]
    offered = [m for m in mutations if m.operation == "create-offer"]
    profiles = [m for m in mutations if m.operation == "register-profile"]
    claims = [m for m in mutations if m.operation == "merge-claim"]
    published = [m for m in mutations if m.operation == "publish"]
    if len(registered) != 2 or any(m.outcome != MutationOutcome.COMMITTED for m in registered):
        return fail(name, "resource registration mutations wrong: %r" % (registered,))
    if len(offered) != 2 or any(m.outcome != MutationOutcome.COMMITTED for m in offered):
        return fail(name, "offer mutations wrong")
    if len(profiles) != 1 or profiles[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "survival profile registration missing")
    if len(claims) != 3:  # 2 node claims + 1 link claim
        return fail(name, "expected 3 bootstrap claims, got %d" % len(claims))
    if len(published) != 1 or published[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "initial policy set not published")
    # Genuine composition: the real authorities hold the registered state.
    from protocol.temporal import parse_instant

    resource_ids = list(sim._energy_resource_ids.values())
    offer = sim._resources.get_current_offer(resource_ids[0], now=parse_instant(_NOW))
    if offer is None or offer.quantity.value != 10_000_000:
        return fail(name, "real ResourceStore holds no current offer")
    authoritative = sim._topology.get_authoritative_claims(
        _NODE_A, now=parse_instant(_NOW))
    if not any(claim.claim_type == "reachable" for claim in authoritative):
        return fail(name, "real TopologyGraph lacks authoritative reachability")
    if not sim._policy_store.list_applicable(_NOW):
        return fail(name, "real PolicyStore holds no applicable set")
    if sim._ledger.epoch(_NODE_A) != 0:
        return fail(name, "ledger epoch should start at 0 (no rejoin yet)")
    return ok(name, "resources/offers/profiles/claims/policy committed through real owners")


# --------------------------------------------------------------------------
# 5-10: determinism
# --------------------------------------------------------------------------


def case_05_complete_scenario_replay() -> Result:
    name = "case_05_complete_scenario_replay"
    spec = _full_spec()
    first = Simulator(spec).run()
    second = Simulator(spec).run()
    if first.trace_digest != second.trace_digest:
        return fail(name, "trace digests diverge on identical specs")
    if first.to_dict() != second.to_dict():
        return fail(name, "result content diverges despite equal digests")
    verified, detail = verify_replay(spec, first)
    if not verified:
        return fail(name, "verify_replay rejected a genuine result: %s" % detail)
    return ok(name, "16-tick rich scenario replays byte-identically (%s...)"
              % first.trace_digest[:18])


def case_06_insertion_order_independence() -> Result:
    name = "case_06_insertion_order_independence"
    base = _full_spec()
    events = list(base.events)[::-1]  # reversed tuple order
    shuffled = ScenarioSpec(
        scenario_id=base.scenario_id, seed=base.seed,
        start_instant=base.start_instant, tick_seconds=base.tick_seconds,
        horizon_ticks=base.horizon_ticks, nodes=base.nodes, links=base.links,
        probes=base.probes, policy_rules=base.policy_rules,
        events=tuple(events),
    )
    first = Simulator(base).run()
    second = Simulator(shuffled).run()
    if first.trace_digest != second.trace_digest:
        return fail(name, "reversed event tuple changed the trace digest")
    # Same for a rotation of the events.
    rotated = tuple(list(base.events)[3:] + list(base.events)[:3])
    third = Simulator(ScenarioSpec(
        scenario_id=base.scenario_id, seed=base.seed, start_instant=base.start_instant,
        tick_seconds=base.tick_seconds, horizon_ticks=base.horizon_ticks,
        nodes=base.nodes, links=base.links, probes=base.probes,
        policy_rules=base.policy_rules, events=rotated,
    )).run()
    if first.trace_digest != third.trace_digest:
        return fail(name, "rotated event tuple changed the trace digest")
    return ok(name, "event tuple order carries no identity (explicit keys only)")


def case_07_seed_reproducibility_and_sensitivity() -> Result:
    name = "case_07_seed_reproducibility_and_sensitivity"
    same_a = Simulator(_full_spec(seed=42)).run()
    same_b = Simulator(_full_spec(seed=42)).run()
    if same_a.trace_digest != same_b.trace_digest:
        return fail(name, "same seed diverges")
    other = Simulator(_full_spec(seed=43)).run()
    if same_a.trace_digest == other.trace_digest:
        return fail(name, "different seed produced the same digest")
    return ok(name, "same seed reproduces; different seed changes the digest")


def case_08_time_base_reproducibility() -> Result:
    name = "case_08_time_base_reproducibility"
    base = _full_spec()
    later = ScenarioSpec(
        scenario_id=base.scenario_id, seed=base.seed,
        start_instant="2027-01-01T00:00:00Z", tick_seconds=base.tick_seconds,
        horizon_ticks=base.horizon_ticks, nodes=base.nodes, links=base.links,
        probes=base.probes, policy_rules=base.policy_rules, events=base.events,
    )
    first = Simulator(base).run()
    second = Simulator(later).run()
    if first.trace_digest == second.trace_digest:
        return fail(name, "different time base produced the same digest")
    twin = Simulator(_full_spec()).run()
    if first.trace_digest != twin.trace_digest:
        return fail(name, "same time base diverged")
    return ok(name, "time base participates in reproducibility")


def case_09_cross_process_determinism() -> Result:
    name = "case_09_cross_process_determinism"
    script = (
        "import sys, json; sys.path.insert(0, %r); "
        "from simulator import Simulator, spec_from_mapping; "
        "spec = spec_from_mapping(json.loads(sys.stdin.read())); "
        "print(Simulator(spec).run().trace_digest)" % (REPO,)
    )
    mapping = spec_to_mapping(_full_spec())
    import json

    digests = []
    for seed in ("0", "7919"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps(mapping), capture_output=True, text=True, cwd=REPO,
            env=dict(os.environ, PYTHONHASHSEED=seed),
        )
        if proc.returncode != 0:
            return fail(name, "seed %s failed: %s" % (seed, proc.stderr.strip()[-300:]))
        digests.append(proc.stdout.strip())
    if len(set(digests)) != 1:
        return fail(name, "digests diverge across processes: %r" % (digests,))
    local = Simulator(_full_spec()).run().trace_digest
    if digests[0] != local:
        return fail(name, "subprocess digest differs from in-process digest")
    return ok(name, "identical digest in-process and across processes (seeds 0/7919)")


def case_10_replay_verification_api() -> Result:
    name = "case_10_replay_verification_api"
    spec = _full_spec()
    result = Simulator(spec).run()
    verified, _ = verify_replay(spec, result)
    if not verified:
        return fail(name, "genuine result failed verification")
    forged = ScenarioResult(
        ok=result.ok, scenario_id=result.scenario_id, seed=result.seed,
        trace=result.trace, trace_digest="sha256:" + "0" * 64,
        final_digests=result.final_digests,
        applied_events=result.applied_events,
        rejected_events=result.rejected_events, failed_events=result.failed_events,
        pending_cleanups=result.pending_cleanups,
        seam_purpose=result.seam_purpose, seam_verdict=result.seam_verdict,
        seam_detail=result.seam_detail,
    )
    verified, detail = verify_replay(spec, forged)
    if verified or "mismatch" not in detail:
        return fail(name, "forged digest accepted (%r)" % (detail,))
    return ok(name, "replay commits only after digest verification passes")


# --------------------------------------------------------------------------
# 11-15: fault injection
# --------------------------------------------------------------------------


def case_11_link_down_fault_injection() -> Result:
    name = "case_11_link_down_fault_injection"
    spec = ScenarioSpec(
        scenario_id="link-down", seed=5, start_instant=_START, tick_seconds=60,
        horizon_ticks=3, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        probes=((_NODE_A, _NODE_B),), policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.LINK_DOWN,
                           payload={"node_a": _NODE_A, "node_b": _NODE_B}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.LINK_UP,
                           payload={"node_a": _NODE_A, "node_b": _NODE_B}),
        ),
    )
    result = Simulator(spec).run()
    down = _record(result, EventKind.LINK_DOWN)
    up = _record(result, EventKind.LINK_UP)
    if down is None or up is None:
        return fail(name, "missing fault records")
    if down.verdict != EventVerdict.APPLIED or down.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "link-down not committed through the topology owner")
    if dict(down.before_digests)["topology"] == dict(down.after_digests)["topology"]:
        return fail(name, "topology digest unchanged by the fault")
    routing_down = [f for f in down.flows if f.flow == "routing"]
    if not routing_down or routing_down[0].ok:
        return fail(name, "routing did not observe the cut")
    routing_up = [f for f in up.flows if f.flow == "routing"]
    if not routing_up or not routing_up[0].ok:
        return fail(name, "routing did not recover after the heal")
    return ok(name, "cut observed (disconnected) and healed (selected) through real authorities")


def case_12_link_degradation_observable() -> Result:
    name = "case_12_link_degradation_observable"
    spec = ScenarioSpec(
        scenario_id="link-degrade", seed=9, start_instant=_START, tick_seconds=60,
        horizon_ticks=2, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B, latency_ms=10),),
        probes=((_NODE_A, _NODE_B),), policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.LINK_DEGRADE,
                           payload={"node_a": _NODE_A, "node_b": _NODE_B}),
        ),
    )
    result = Simulator(spec).run()
    degraded = _record(result, EventKind.LINK_DEGRADE)
    if degraded is None or degraded.verdict != EventVerdict.APPLIED:
        return fail(name, "degrade event not applied")
    routing = [f for f in degraded.flows if f.flow == "routing"]
    if not routing or not routing[0].ok:
        return fail(name, "degraded link left the probe without a path")
    # The degraded metrics must carry the deterministic penalty (>= 2x latency).
    sim = Simulator(spec)
    sim_result = sim.run()
    del sim_result
    metrics = sim._environment.link_metrics(_NOW, "2026-12-31T23:59:59Z")
    subject = sim._environment.link_subject(_NODE_A, _NODE_B)
    metric = metrics[subject]
    if metric.latency_ms < 20:
        return fail(name, "degraded latency %d below the 2x penalty floor" % metric.latency_ms)
    if metric.loss_basis_points < 1000:
        return fail(name, "degraded loss %d below the penalty floor" % metric.loss_basis_points)
    replay = Simulator(spec).run()
    if result.trace_digest != replay.trace_digest:
        return fail(name, "degradation scenario not reproducible")
    return ok(name, "deterministic degrade penalty observable; scenario reproducible")


def case_13_partition_and_recovery() -> Result:
    name = "case_13_partition_and_recovery"
    spec = ScenarioSpec(
        scenario_id="partition", seed=11, start_instant=_START, tick_seconds=60,
        horizon_ticks=3, nodes=_nodes(),
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),
               SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_C),
               SimulatedLinkSpec(node_a=_NODE_C, node_b=_NODE_B)),
        probes=((_NODE_A, _NODE_B),), policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.PARTITION_START,
                           payload={"cuts": [[_NODE_A, _NODE_B], [_NODE_A, _NODE_C],
                                             [_NODE_C, _NODE_B]]}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.PARTITION_END,
                           payload={"cuts": [[_NODE_A, _NODE_B], [_NODE_A, _NODE_C],
                                             [_NODE_C, _NODE_B]]}),
        ),
    )
    result = Simulator(spec).run()
    start = _record(result, EventKind.PARTITION_START)
    end = _record(result, EventKind.PARTITION_END)
    if start is None or end is None:
        return fail(name, "missing partition records")
    if len(start.mutations) != 3:
        return fail(name, "expected 3 cut claims, got %d" % len(start.mutations))
    if any(f.flow == "routing" and f.ok for f in start.flows):
        return fail(name, "probe routed during a full partition")
    if not any(f.flow == "routing" and f.ok for f in end.flows):
        return fail(name, "probe did not recover after partition end")
    return ok(name, "full partition disconnects; recovery restores routability")


def case_14_restart_rejoin_deterministic() -> Result:
    name = "case_14_restart_rejoin_deterministic"
    spec = ScenarioSpec(
        scenario_id="restart", seed=13, start_instant=_START, tick_seconds=60,
        horizon_ticks=5, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.NODE_DOWN,
                           payload={"node": _NODE_B}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.NODE_UP,
                           payload={"node": _NODE_B}),
            ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.NODE_DOWN,
                           payload={"node": _NODE_B}),
            ScheduledEvent(at_tick=4, sequence=1, kind=EventKind.NODE_UP,
                           payload={"node": _NODE_B}),
        ),
    )
    result = Simulator(spec).run()
    rejoins = [r for r in result.trace if r.kind == EventKind.NODE_UP]
    if len(rejoins) != 2:
        return fail(name, "expected 2 rejoin records")
    first = [f for f in rejoins[0].flows if f.flow == "energy"][0]
    second = [f for f in rejoins[1].flows if f.flow == "energy"][0]
    if "epoch 1" not in first.detail or "epoch 2" not in second.detail:
        return fail(name, "rejoin epochs wrong: %r / %r" % (first.detail, second.detail))
    if any(m.outcome != MutationOutcome.COMMITTED
           for r in rejoins for m in r.mutations):
        return fail(name, "rejoin mutations not committed")
    replay = Simulator(spec).run()
    if result.trace_digest != replay.trace_digest:
        return fail(name, "restart/rejoin scenario not reproducible")
    return ok(name, "two restarts chain epochs 1->2 through the real W027 ledger")


def case_15_session_fail_and_cleanup_pending() -> Result:
    name = "case_15_session_fail_and_cleanup_pending"
    spec = ScenarioSpec(
        scenario_id="cleanup-fail", seed=17, start_instant=_START, tick_seconds=60,
        horizon_ticks=3, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s1", "source": _NODE_A,
                                    "destination": _NODE_B}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.SESSION_FAIL,
                           payload={"label": "s1"}),
            ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.CLEANUP,
                           payload={"label": "s1"}),
        ),
    )
    result = Simulator(spec).run()
    if result.ok:
        return fail(name, "pending cleanup must make ok=False")
    if result.pending_cleanups != 1:
        return fail(name, "pending_cleanups=%d" % result.pending_cleanups)
    cleanup = _record(result, EventKind.CLEANUP)
    if cleanup is None or cleanup.mutations[0].outcome != MutationOutcome.PENDING:
        return fail(name, "cleanup failure not recorded as PENDING")
    if "terminal-state" not in cleanup.mutations[0].detail:
        return fail(name, "owner rejection detail missing: %r"
                    % cleanup.mutations[0].detail)
    return ok(name, "cleanup failure is an explicit pending state (never silent)")


# --------------------------------------------------------------------------
# 16-19: observation
# --------------------------------------------------------------------------


def case_16_resource_exhaustion_observation() -> Result:
    name = "case_16_resource_exhaustion_observation"
    spec = ScenarioSpec(
        scenario_id="exhaust", seed=19, start_instant=_START, tick_seconds=60,
        horizon_ticks=1, nodes=_nodes()[:2], policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.RESOURCE_EXHAUST,
                           payload={"node": _NODE_B, "fraction_bp": 500}),
        ),
    )
    sim = Simulator(spec)
    result = sim.run()
    record = _record(result, EventKind.RESOURCE_EXHAUST)
    if record is None or record.verdict != EventVerdict.APPLIED:
        return fail(name, "exhaustion event not applied")
    if record.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "measurement not committed: %r" % (record.mutations[0],))
    from protocol.temporal import parse_instant

    resource_id = sim._energy_resource_ids[_NODE_B]
    measurement = sim._resources.get_current_measurement(
        resource_id, now=parse_instant(_NOW))
    if measurement is None:
        return fail(name, "real ResourceStore holds no current measurement")
    value = measurement.value
    if not hasattr(value, "energy_level") or value.energy_level.value != 500_000:
        return fail(name, "measurement value is not the exhausted EnergyState")
    if measurement.source_class != "self-observation":
        return fail(name, "measurement provenance wrong: %r" % measurement.source_class)
    return ok(name, "EnergyState exhaustion measurement recorded through real W008")


def case_17_telemetry_observation_recorded() -> Result:
    name = "case_17_telemetry_observation_recorded"
    spec = ScenarioSpec(
        scenario_id="telemetry", seed=23, start_instant=_START, tick_seconds=60,
        horizon_ticks=1, nodes=_nodes()[:2], policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.TELEMETRY_EMIT,
                           payload={"node": _NODE_A, "subject_kind": "energy",
                                    "subject_ref": _NODE_A,
                                    "metric": "energy-level-millijoules",
                                    "value": 3_400_000}),
        ),
    )
    sim = Simulator(spec)
    result = sim.run()
    record = _record(result, EventKind.TELEMETRY_EMIT)
    if record is None or record.verdict != EventVerdict.APPLIED:
        return fail(name, "telemetry event not applied")
    if record.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "observation not committed")
    observation_id = record.mutations[0].detail
    stored = [
        item for item in sim._telemetry.snapshot().get("observations", [])
        if isinstance(item, dict) and item.get("observation_id") == observation_id
    ]
    if not stored:
        return fail(name, "real TelemetryStore holds no such observation")
    if stored[0].get("source_class") != "self-advertised":
        return fail(name, "provenance not preserved: %r" % stored[0].get("source_class"))
    if stored[0].get("source_node_id") != _NODE_A:
        return fail(name, "source node not preserved")
    replay = Simulator(spec).run()
    if result.trace_digest != replay.trace_digest:
        return fail(name, "telemetry scenario not reproducible")
    return ok(name, "W026 observation recorded with preserved provenance")


def case_18_session_full_chain_observation() -> Result:
    name = "case_18_session_full_chain_observation"
    spec = _minimal_spec()
    sim = Simulator(spec)
    result = sim.run()
    record = _record(result, EventKind.SESSION_REQUEST)
    if record is None or record.verdict != EventVerdict.APPLIED:
        return fail(name, "session request not applied")
    flows = [f.flow for f in record.flows]
    if flows != ["policy", "routing", "session", "session", "session"]:
        return fail(name, "chain flows wrong: %r" % flows)
    if not all(f.ok for f in record.flows):
        return fail(name, "chain step failed: %r" % (record.flows,))
    operations = [m.operation for m in record.mutations]
    if operations != ["create", "transition-authorized", "transition-established"]:
        return fail(name, "mutations wrong: %r" % operations)
    session_flow = [f for f in record.flows if f.flow == "session"][0]
    session = sim._sessions.get(session_flow.ref)
    if session is None or session.state != "ESTABLISHED":
        return fail(name, "session not established in the real W012 store")
    replay = Simulator(spec).run()
    if result.trace_digest != replay.trace_digest:
        return fail(name, "session scenario not reproducible")
    replay_flow = [
        f for r in replay.trace if r.kind == EventKind.SESSION_REQUEST
        for f in r.flows if f.flow == "session"
    ][0]
    if replay_flow.ref != session_flow.ref:
        return fail(name, "session identity not stable across replay")
    return ok(name, "policy -> routing -> create -> ESTABLISHED; identity replay-stable")


def case_19_multipath_and_mobility_observation() -> Result:
    name = "case_19_multipath_and_mobility_observation"
    spec = ScenarioSpec(
        scenario_id="mp-mobility", seed=29, start_instant=_START, tick_seconds=60,
        horizon_ticks=6, nodes=_nodes(), links=_links(), policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s1", "source": _NODE_A,
                                    "destination": _NODE_B}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.PATH_ADD,
                           payload={"label": "s1", "avoid": [[_NODE_A, _NODE_B]]}),
            ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.PATH_ADD,
                           payload={"label": "s1", "avoid": [[_NODE_A, _NODE_C]]}),
            ScheduledEvent(at_tick=4, sequence=1, kind=EventKind.PATH_FAIL,
                           payload={"label": "s1", "index": 1}),
            ScheduledEvent(at_tick=5, sequence=1, kind=EventKind.MOBILITY_HANDOVER,
                           payload={"label": "s1", "avoid": [[_NODE_A, _NODE_B]]}),
        ),
    )
    sim = Simulator(spec)
    result = sim.run()
    session_flow = [
        f for r in result.trace if r.kind == EventKind.SESSION_REQUEST
        for f in r.flows if f.flow == "session"
    ][0]
    session_id = session_flow.ref
    session = sim._sessions.get(session_id)
    if session is None or session.state != "ESTABLISHED":
        return fail(name, "session not established")
    adds = [r for r in result.trace if r.kind == EventKind.PATH_ADD]
    if len(adds) != 2 or not all(
        m.outcome == MutationOutcome.COMMITTED for r in adds for m in r.mutations
    ):
        return fail(name, "path admissions wrong: %r"
                    % [(r.verdict, [m.outcome for m in r.mutations]) for r in adds])
    fail_record = _record(result, EventKind.PATH_FAIL)
    if fail_record is None or fail_record.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "constituent failure not committed")
    fail_flow = [f for f in fail_record.flows if f.flow == "multipath"][0]
    if not fail_flow.ok or "session state ESTABLISHED" not in fail_flow.detail:
        return fail(name, "constituent failure did not preserve the session: %r"
                    % fail_flow.detail)
    session_after_fail = sim._sessions.get(session_id)
    if session_after_fail.state != "ESTABLISHED":
        return fail(name, "constituent failure changed the session state")
    handover = _record(result, EventKind.MOBILITY_HANDOVER)
    if handover is None:
        return fail(name, "missing handover record")
    commits = [m for m in handover.mutations if m.operation == "commit-handover"]
    if not commits or commits[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "handover not committed: %r" % (handover.mutations,))
    handover_flow = [f for f in handover.flows if f.flow == "mobility"][0]
    if "identity preserved" not in handover_flow.detail:
        return fail(name, "handover flow detail wrong: %r" % handover_flow.detail)
    # Session identity preserved through the handover, and the
    # make-before-break retire removed the failed old constituent from
    # the plan (the alternate remains active for the session).
    binding = sim._sessions.get(session_id)
    if binding.session_id != session_id:
        return fail(name, "session identity changed across handover")
    final_plan = sim._multipath.get_plan(session_id)
    final_statuses = [e.status for e in final_plan.entries]
    if final_statuses != ["ACTIVE"]:
        return fail(name, "post-handover plan wrong: %r" % final_statuses)
    replay = Simulator(spec).run()
    if result.trace_digest != replay.trace_digest:
        return fail(name, "multipath/mobility scenario not reproducible")
    return ok(name, "2-path plan, constituent failure survives session, MBB handover")


# --------------------------------------------------------------------------
# 20-22: policy behavior
# --------------------------------------------------------------------------


def case_20_policy_denial_default() -> Result:
    name = "case_20_policy_denial_default"
    spec = ScenarioSpec(
        scenario_id="deny-default", seed=31, start_instant=_START, tick_seconds=60,
        horizon_ticks=1, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s1", "source": _NODE_A,
                                    "destination": _NODE_B}),
        ),
    )
    result = Simulator(spec).run()
    record = _record(result, EventKind.SESSION_REQUEST)
    if record is None or record.verdict != EventVerdict.APPLIED:
        return fail(name, "session request not applied")
    policy_flow = [f for f in record.flows if f.flow == "policy"]
    if not policy_flow or policy_flow[0].ok or policy_flow[0].code != "default-deny":
        return fail(name, "deny-by-default not observed: %r" % (policy_flow,))
    if record.mutations:
        return fail(name, "denial mutated authority state: %r" % (record.mutations,))
    if dict(record.before_digests).get("sessions") != dict(record.after_digests).get("sessions"):
        return fail(name, "session store digest changed on a policy denial")
    return ok(name, "no applicable policy set -> deny-by-default; authority untouched")


def case_21_policy_amend_explicit_deny() -> Result:
    name = "case_21_policy_amend_explicit_deny"
    spec = ScenarioSpec(
        scenario_id="amend", seed=37, start_instant=_START, tick_seconds=60,
        horizon_ticks=4, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.POLICY_AMEND,
                           payload={"set_id": "scenario-policy", "version": 2,
                                    "rules": [{"rule_id": "deny-sessions",
                                               "effect": "deny"}]}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s1", "source": _NODE_A,
                                    "destination": _NODE_B}),
            ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.POLICY_WITHDRAW,
                           payload={"set_id": "scenario-policy", "version": 2}),
            ScheduledEvent(at_tick=4, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s2", "source": _NODE_A,
                                    "destination": _NODE_B}),
        ),
    )
    result = Simulator(spec).run()
    amend = _record(result, EventKind.POLICY_AMEND)
    if amend is None or amend.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "policy amend not committed")
    denied = [r for r in result.trace if r.kind == EventKind.SESSION_REQUEST][0]
    policy_flow = [f for f in denied.flows if f.flow == "policy"][0]
    if policy_flow.ok or "blocks" not in policy_flow.detail:
        return fail(name, "explicit deny not observed: %r" % policy_flow.detail)
    withdraw = _record(result, EventKind.POLICY_WITHDRAW)
    if withdraw is None or withdraw.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "withdraw not committed")
    allowed = [r for r in result.trace if r.kind == EventKind.SESSION_REQUEST][1]
    if not any(f.flow == "session" and f.ok for f in allowed.flows):
        return fail(name, "session not created after withdrawal restored v1")
    return ok(name, "v2 explicit deny blocks; withdrawal restores the v1 allow")


def case_22_policy_amend_validation() -> Result:
    name = "case_22_policy_amend_validation"
    problems: List[str] = []
    for rules in (
        [{"effect": "deny"}],  # no rule_id
        [{"rule_id": "x", "effect": "perhaps"}],  # bad effect
        [],
    ):
        spec = ScenarioSpec(
            scenario_id="amend-bad", seed=41, start_instant=_START,
            tick_seconds=60, horizon_ticks=1, nodes=_nodes()[:2],
            policy_rules=_rules(),
            events=(
                ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.POLICY_AMEND,
                               payload={"set_id": "x", "version": 2, "rules": rules}),
            ),
        )
        result = Simulator(spec).run()
        record = _record(result, EventKind.POLICY_AMEND)
        if record is None or record.verdict != EventVerdict.REJECTED:
            problems.append("malformed rules %r not rejected" % (rules,))
    # An unknown operation inside a well-formed amend fails closed at the
    # authority boundary (observed as a rejected mutation).
    spec = ScenarioSpec(
        scenario_id="amend-op", seed=43, start_instant=_START, tick_seconds=60,
        horizon_ticks=1, nodes=_nodes()[:2], policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.POLICY_AMEND,
                           payload={"set_id": "x", "version": 2,
                                    "rules": [{"rule_id": "r", "effect": "allow",
                                               "operation": "not.an-operation"}]}),
        ),
    )
    result = Simulator(spec).run()
    record = _record(result, EventKind.POLICY_AMEND)
    if record is None or record.verdict != EventVerdict.APPLIED:
        problems.append("unknown-operation amend not applied for observation")
    elif record.mutations[0].outcome != MutationOutcome.REJECTED:
        problems.append("unknown operation accepted by the policy owner")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(name, "malformed material rejected; unknown operations fail at the owner")


# --------------------------------------------------------------------------
# 23-28: separation / immutability / security
# --------------------------------------------------------------------------


def case_23_simulator_authority_state_separation() -> Result:
    name = "case_23_simulator_authority_state_separation"
    from sessions.store import SessionStore

    spec = _minimal_spec()
    sim = Simulator(spec)
    result = sim.run()
    digests_after_run = dict(result.final_digests)
    # 1. Mutating simulator environment state without applying an event
    #    never changes authority state.
    sim._environment.set_link_status(
        sim._environment.link_subject(_NODE_A, _NODE_B), "down")
    digests_after_mutation = dict(sim._digest_state(_NOW))
    if digests_after_run.get("topology") != digests_after_mutation.get("topology"):
        return fail(name, "environment mutation leaked into topology authority")
    if digests_after_run.get("sessions") != digests_after_mutation.get("sessions"):
        return fail(name, "environment mutation leaked into session authority")
    # 2. A caller's production store is never reachable without a seam.
    production = SessionStore()
    production_digest = authority_digest(production)
    Simulator(_minimal_spec(scenario_id="isolated")).run()
    if authority_digest(production) != production_digest:
        return fail(name, "production store mutated without any seam")
    # 3. Authority instances are per-simulator (fresh, not shared globals).
    other = Simulator(_minimal_spec(scenario_id="another"))
    other.run()
    if sim._sessions is other._sessions or sim._topology is other._topology:
        return fail(name, "authority instances shared across simulators")
    return ok(name, "environment/authority state separated; production unreachable")


def case_24_no_private_authority_mutation() -> Result:
    name = "case_24_no_private_authority_mutation"
    problems: List[str] = []
    for path in _SIMULATOR_FILES:
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and node.attr.startswith("_")
                    and not node.attr.startswith("__")):
                target = node.value
                if isinstance(target, ast.Name) and target.id in ("self", "cls"):
                    continue
                if isinstance(target, (ast.Attribute, ast.Call)):
                    continue
                problems.append("%s:%d private attribute access %r"
                                % (os.path.basename(path), node.lineno, node.attr))
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if (isinstance(target, ast.Attribute)
                            and not (isinstance(target.value, ast.Name)
                                     and target.value.id == "self")):
                        problems.append("%s:%d attribute assignment outside self"
                                        % (os.path.basename(path), node.lineno))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(name, "no private authority access; no attribute mutation outside self")


def case_25_provenance_injection() -> Result:
    name = "case_25_provenance_injection"
    spec = ScenarioSpec(
        scenario_id="provenance", seed=47, start_instant=_START, tick_seconds=60,
        horizon_ticks=1, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.TELEMETRY_EMIT,
                           payload={"node": _NODE_B, "subject_kind": "energy",
                                    "subject_ref": _NODE_B,
                                    "metric": "reserve-bp", "value": 3_500}),
        ),
    )
    sim = Simulator(spec)
    result = sim.run()
    # 1. Every environment-emitted claim carries simulator provenance and
    #    the provenance-correct source class.
    clock = ScenarioClock(_START, 60)
    stream = DeterministicStream(47, label="scenario")
    env = SimulatedEnvironment(spec, clock, stream)
    claims = env.node_claims(_START, "2026-12-31T23:59:59Z")
    if not claims or claims[0].reporter != claims[0].subject:
        return fail(name, "node claims are not self-attributed")
    if claims[0].provenance != "simulator:environment":
        return fail(name, "claim provenance missing")
    link_claims = env.all_link_claims(_START, "2026-12-31T23:59:59Z")
    if link_claims and link_claims[0].source_class != "self-advertisement":
        return fail(name, "link claim source class wrong")
    # 2. The topology authority's authoritative set contains ONLY
    #    self-attributed claims (a remote claim about a node never
    #    becomes authoritative -- LOCK-008/009).
    from topology import ClaimType, SourceClass, TopologyClaim

    hostile = TopologyClaim(
        subject=_NODE_B, reporter=_NODE_A, claim_type=ClaimType.REACHABLE,
        value="true", source_class=SourceClass.REMOTE_CLAIM,
        issued_at=_START, freshness_until="2026-12-31T23:59:59Z", sequence=1,
    )
    sim._topology.merge(hostile)
    from protocol.temporal import parse_instant

    authoritative = sim._topology.get_authoritative_claims(
        _NODE_B, now=parse_instant(_NOW))
    if any(claim.reporter != _NODE_B for claim in authoritative):
        return fail(name, "remote claim entered the authoritative set")
    # 3. Telemetry provenance is preserved by the store (self-advertised).
    record = _record(result, EventKind.TELEMETRY_EMIT)
    if record is None or record.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "telemetry not recorded")
    return ok(name, "provenance-correct injections; remote claims stay non-authoritative")


def case_26_forged_authority_objects_rejected() -> Result:
    name = "case_26_forged_authority_objects_rejected"
    # Integrity is not provenance: a well-formed-looking PolicyDecision with
    # a forged decision_id cannot underwrite a session. The genuine chain
    # (engine-minted decision) succeeds; the forged one fails closed.
    from policy.model import PolicyDecision
    from routing import RoutingEngine, RoutingContext, LinkMetrics
    from sessions.store import SessionStore
    from topology import TopologyGraph, TopologyClaim, ClaimType, SourceClass, make_link_subject

    graph = TopologyGraph()
    for claim in (
        TopologyClaim(subject=_NODE_A, reporter=_NODE_A,
                      claim_type=ClaimType.REACHABLE, value="true",
                      source_class=SourceClass.SELF_ADVERTISEMENT,
                      issued_at=_START, freshness_until="2026-12-31T23:59:59Z"),
        TopologyClaim(subject=_NODE_B, reporter=_NODE_B,
                      claim_type=ClaimType.REACHABLE, value="true",
                      source_class=SourceClass.SELF_ADVERTISEMENT,
                      issued_at=_START, freshness_until="2026-12-31T23:59:59Z"),
        TopologyClaim(subject=make_link_subject(_NODE_A, _NODE_B), reporter=_NODE_A,
                      claim_type=ClaimType.LINK_STATE, value="up",
                      source_class=SourceClass.SELF_ADVERTISEMENT,
                      issued_at=_START, freshness_until="2026-12-31T23:59:59Z"),
    ):
        graph.merge(claim)
    metrics = {
        make_link_subject(_NODE_A, _NODE_B): LinkMetrics(
            latency_ms=10, loss_basis_points=0, capacity_bps=1_000_000,
            energy_cost_millijoules=100, confidence_basis_points=10_000,
            observed_at=_START, freshness_until="2026-12-31T23:59:59Z"),
    }

    def _decision(decision_id: str) -> PolicyDecision:
        return PolicyDecision(
            decision_id=decision_id, effect="allow", code="allow", detail="forged",
            matched_rule_ids=("r1",), policy_set_id="ps-1", policy_set_version=1,
            evaluation_instant=_NOW,
        )

    from resources import ResourceStore

    forged = _decision("sha256:" + "f" * 64)
    context = RoutingContext(
        source_node_id=_NODE_A, destination_node_id=_NODE_B, topology=graph,
        resources=ResourceStore(),
        evaluation_instant=_NOW, policy_decision=forged, link_metrics=metrics,
    )
    result = RoutingEngine().evaluate(context)
    store = SessionStore()
    created = False
    if result.ok and result.decision is not None and result.decision.selected is not None:
        outcome = store.create(
            result.decision, forged, source_node_id=_NODE_A,
            destination_node_id=_NODE_B, creation_instant=_NOW,
        )
        created = outcome.ok
    if created:
        return fail(name, "forged policy decision underwrote a session")
    # And the simulator itself never mints policy decisions: the source
    # contains no PolicyDecision construction.
    for path in _SIMULATOR_FILES:
        with open(path, "r", encoding="utf-8") as handle:
            if "PolicyDecision(" in handle.read():
                return fail(name, "%s constructs a PolicyDecision"
                            % os.path.basename(path))
    return ok(name, "forged decision rejected; simulator mints no policy decisions")


def case_27_no_second_authority_structural() -> Result:
    name = "case_27_no_second_authority_structural"
    allowed_roots = {
        "protocol", "identity", "topology", "resources", "policy", "routing",
        "sessions", "multipath", "mobility", "telemetry", "energy",
    }
    problems: List[str] = []
    for path in _SIMULATOR_FILES:
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed_roots and root not in sys.stdlib_module_names:
                        problems.append("%s imports %s" % (os.path.basename(path), alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                root = node.module.split(".")[0]
                if root not in allowed_roots and root not in sys.stdlib_module_names:
                    problems.append("%s imports from %s" % (os.path.basename(path), node.module))
    import re

    lowered = " ".join(
        open(path, "r", encoding="utf-8").read().lower() for path in _SIMULATOR_FILES
    )
    for vendor in ("open5gs", "android", "3gpp", "lte", "5g", "6g", "wifi",
                   "vendor", "handset", "modem"):
        if re.search(r"\b%s\b" % vendor, lowered):
            problems.append("vendor token %r present" % vendor)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(name, "imports limited to accepted authorities; no vendor tokens")


def case_28_no_wall_clock_structural() -> Result:
    name = "case_28_no_wall_clock_structural"
    problems: List[str] = []
    for path in _SIMULATOR_FILES:
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "random":
                        problems.append("%s imports random" % os.path.basename(path))
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module == "random":
                    problems.append("%s imports random" % os.path.basename(path))
                if node.module in ("time", "datetime"):
                    for alias in node.names:
                        if alias.name in ("time", "now", "monotonic", "utcnow"):
                            problems.append("%s imports datetime.%s"
                                            % (os.path.basename(path), alias.name))
            if isinstance(node, ast.Call):
                function = node.func
                if (isinstance(function, ast.Attribute)
                        and function.attr in ("now", "utcnow", "time", "monotonic",
                                              "perf_counter", "urandom")):
                    problems.append("%s:%d wall-clock/uncontrolled-entropy call %r"
                                    % (os.path.basename(path), node.lineno, function.attr))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(name, "no wall clock, no language PRNG, no uncontrolled entropy")


# --------------------------------------------------------------------------
# 29-30: failure boundary / rejected events
# --------------------------------------------------------------------------


def case_29_universal_event_failure_boundary() -> Result:
    name = "case_29_universal_event_failure_boundary"
    from sessions.store import SessionStore

    class HostileSessionStore(SessionStore):
        def create(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("hostile session authority")

    seam = AuthorityTestSeam(
        HostileSessionStore(), purpose="hostile authority failure-boundary proof"
    )
    spec = _minimal_spec()
    result = Simulator(spec, seam=seam).run()
    failed = [r for r in result.trace if r.verdict == EventVerdict.FAILED]
    if len(failed) != 1:
        return fail(name, "expected exactly 1 failed record, got %d" % len(failed))
    record = failed[0]
    if record.kind != EventKind.SESSION_REQUEST:
        return fail(name, "failed record kind %r" % record.kind)
    if "RuntimeError" not in record.detail:
        return fail(name, "exception class missing: %r" % record.detail)
    if not record.before_digests or not record.after_digests:
        return fail(name, "pre/post digests missing on the failed record")
    if result.failed_events != 1 or result.ok:
        return fail(name, "stats wrong: failed=%d ok=%r"
                    % (result.failed_events, result.ok))
    if len(result.trace) != 2:  # bootstrap + the failed session request
        return fail(name, "trace length %d (partial advance?)" % len(result.trace))
    # The hostile component never bypassed the seam contract: purpose recorded.
    if result.seam_purpose != "hostile authority failure-boundary proof":
        return fail(name, "seam purpose not recorded")
    return ok(name, "hostile authority -> exactly one failed record; run completes")


def case_30_rejected_events_advance_nothing() -> Result:
    name = "case_30_rejected_events_advance_nothing"
    spec = ScenarioSpec(
        scenario_id="rejected", seed=53, start_instant=_START, tick_seconds=60,
        horizon_ticks=3, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.LINK_DOWN,
                           payload={"node_a": _NODE_A, "node_b": "adcos:node:no.pe.v1:"
                                    + "9" * 64}),
            ScheduledEvent(at_tick=1, sequence=2, kind=EventKind.NODE_DOWN,
                           payload={"node": "adcos:node:no.pe.v1:" + "9" * 64}),
            ScheduledEvent(at_tick=1, sequence=3, kind=EventKind.PATH_ADD,
                           payload={"label": "missing", "avoid": []}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.OBSERVE, payload={}),
        ),
    )
    result = Simulator(spec).run()
    if result.rejected_events != 3:
        return fail(name, "expected 3 rejected, got %d" % result.rejected_events)
    for record in result.trace:
        if record.verdict == EventVerdict.REJECTED:
            if dict(record.before_digests) != dict(record.after_digests):
                return fail(name, "rejected event %r changed authority digests"
                            % record.kind)
            if record.mutations:
                return fail(name, "rejected event %r mutated state" % record.kind)
    # A rejected event never advances the applied sequence: the following
    # OBSERVE still applies.
    observe = _record(result, EventKind.OBSERVE)
    if observe is None or observe.verdict != EventVerdict.APPLIED:
        return fail(name, "subsequent event did not apply after rejections")
    return ok(name, "semantic rejections advance nothing; execution continues")


# --------------------------------------------------------------------------
# 31-33: the explicit, restored test seam
# --------------------------------------------------------------------------


def case_31_seam_requires_purpose() -> Result:
    name = "case_31_seam_requires_purpose"
    from sessions.store import SessionStore

    try:
        AuthorityTestSeam(SessionStore(), purpose="  ")
        return fail(name, "blank purpose accepted")
    except SimulatorError as error:
        if error.code != SimulatorReasonCode.SEAM_PURPOSE_REQUIRED:
            return fail(name, "wrong code %r" % error.code)
    try:
        AuthorityTestSeam(object(), purpose="x")
        return fail(name, "unsupported component accepted")
    except SimulatorError as error:
        if error.code != SimulatorReasonCode.UNSUPPORTED_SEAM_COMPONENT:
            return fail(name, "wrong code %r" % error.code)
    # Supported component types digest through their own canonical APIs.
    from energy.resilience import NodeRejoinLedger

    ledger = NodeRejoinLedger()
    digest = authority_digest(ledger)
    if not digest.startswith("sha256:"):
        return fail(name, "ledger digest malformed")
    seam = AuthorityTestSeam(SessionStore(), purpose="p")
    if seam.open() != seam.close():
        pass  # restored case checked separately
    return ok(name, "purpose mandatory; unsupported components fail closed")


def case_32_seam_restored_verdict() -> Result:
    name = "case_32_seam_restored_verdict"
    from sessions.store import SessionStore

    store = SessionStore()
    seam = AuthorityTestSeam(store, purpose="read-only observation seam")
    spec = ScenarioSpec(
        scenario_id="seam-restored", seed=59, start_instant=_START,
        tick_seconds=60, horizon_ticks=1, nodes=_nodes()[:2], policy_rules=_rules(),
    )
    result = Simulator(spec, seam=seam).run()
    if result.seam_verdict != "restored":
        return fail(name, "verdict %r (expected restored)" % result.seam_verdict)
    if result.seam_purpose != "read-only observation seam":
        return fail(name, "purpose not surfaced")
    if authority_digest(store) != seam.open_digest:
        return fail(name, "component digest drifted after close")
    return ok(name, "untouched seam component closes as restored (digest equal)")


def case_33_seam_validated_and_degraded_verdicts() -> Result:
    name = "case_33_seam_validated_and_degraded_verdicts"
    from energy.resilience import NodeRejoinLedger

    # validated: mutations through owner contracts, all trace-recorded
    ledger = NodeRejoinLedger()
    seam = AuthorityTestSeam(ledger, purpose="restart/rejoin observation")
    spec = ScenarioSpec(
        scenario_id="seam-validated", seed=61, start_instant=_START,
        tick_seconds=60, horizon_ticks=2, nodes=_nodes()[:2], policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.NODE_DOWN,
                           payload={"node": _NODE_B}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.NODE_UP,
                           payload={"node": _NODE_B}),
        ),
    )
    result = Simulator(spec, seam=seam).run()
    if result.seam_verdict != "validated":
        return fail(name, "verdict %r (expected validated)" % result.seam_verdict)
    if ledger.epoch(_NODE_B) != 1:
        return fail(name, "rejoin epoch %r" % ledger.epoch(_NODE_B))
    rejoin_mutations = [
        m for record in result.trace for m in record.mutations
        if m.authority == "energy-resilience"
    ]
    if not any(m.operation == "rejoin" and m.outcome == MutationOutcome.COMMITTED
               for m in rejoin_mutations):
        return fail(name, "seam mutations not trace-recorded")

    # degraded: a pending cleanup on the seam component
    from sessions.store import SessionStore

    store = SessionStore()
    seam2 = AuthorityTestSeam(store, purpose="cleanup-failure observation")
    spec2 = ScenarioSpec(
        scenario_id="seam-degraded", seed=67, start_instant=_START,
        tick_seconds=60, horizon_ticks=3, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
        policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s1", "source": _NODE_A,
                                    "destination": _NODE_B}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.SESSION_FAIL,
                           payload={"label": "s1"}),
            ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.CLEANUP,
                           payload={"label": "s1"}),
        ),
    )
    result2 = Simulator(spec2, seam=seam2).run()
    if result2.seam_verdict != "degraded":
        return fail(name, "verdict %r (expected degraded)" % result2.seam_verdict)
    if "pending" not in result2.seam_detail:
        return fail(name, "degraded detail lacks the pending cause: %r"
                    % result2.seam_detail)
    return ok(name, "validated on trace-recorded mutations; degraded on pending cleanup")


# --------------------------------------------------------------------------
# 34-40: serialization, surfaces, wiring
# --------------------------------------------------------------------------


def case_34_serialization_round_trips() -> Result:
    name = "case_34_serialization_round_trips"
    spec = _full_spec()
    mapping = spec_to_mapping(spec)
    rebuilt = spec_from_mapping(mapping)
    if spec_to_mapping(rebuilt) != mapping:
        return fail(name, "spec round trip is not stable")
    result = Simulator(spec).run()
    restored = result_from_mapping(result.to_dict())
    if restored.trace_digest != result.trace_digest:
        return fail(name, "result digest not reproduced from the wire form")
    if restored.to_dict() != result.to_dict():
        return fail(name, "result round trip loses content")
    return ok(name, "spec and result round-trip byte-identically")


def case_35_no_future_work_item_semantics() -> Result:
    name = "case_35_no_future_work_item_semantics"
    # The simulator composes W007/W008/W010/W011/W012/W013/W014/W026/W027
    # only. In particular it must not depend on the management plane
    # (W030), the upgrade manager (W029), adapters, or any W032+ surface.
    forbidden = ("management", "upgrade", "adapters", "federation", "intent",
                 "services", "discovery", "capabilities", "transport")
    problems: List[str] = []
    for path in _SIMULATOR_FILES:
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden:
                        problems.append("%s imports %s"
                                        % (os.path.basename(path), alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module.split(".")[0] in forbidden:
                    problems.append("%s imports from %s"
                                    % (os.path.basename(path), node.module))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(name, "composition limited to the frozen dependency authorities")


def case_36_py_compile_clean() -> Result:
    name = "case_36_py_compile_clean"
    for path in _SIMULATOR_FILES:
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as error:
            return fail(name, "%s does not compile: %s" % (os.path.basename(path), error))
    return ok(name, "simulator family compiles clean")


def case_37_ci_wiring() -> Result:
    name = "case_37_ci_wiring"
    workflow_path = os.path.join(REPO, ".github", "workflows", "spec-check.yml")
    with open(workflow_path, "r", encoding="utf-8") as handle:
        workflow = handle.read()
    if "python3 tools/simulator_selftest.py" not in workflow:
        return fail(name, "simulator battery not wired into CI")
    expected = [
        "spec_check.py", "spec_check_selftest.py", "schema_check.py",
        "schema_selftest.py", "envelope_selftest.py", "identity_selftest.py",
        "capability_selftest.py", "discovery_selftest.py",
        "topology_selftest.py", "resource_selftest.py", "intent_selftest.py",
        "policy_selftest.py", "routing_selftest.py", "session_selftest.py",
        "multipath_selftest.py", "mobility_selftest.py",
        "federation_selftest.py", "adapter_selftest.py",
        "transport_selftest.py", "ipintegration_selftest.py",
        "fivegc_selftest.py", "wifi_selftest.py", "backhaul_selftest.py",
        "mesh_selftest.py", "distcore_selftest.py", "service_selftest.py",
        "telemetry_selftest.py", "energy_selftest.py", "security_selftest.py",
        "upgrade_selftest.py", "management_selftest.py", "simulator_selftest.py",
    ]
    for battery in expected:
        if "tools/%s" % battery not in workflow:
            return fail(name, "battery %r missing from CI" % battery)
    return ok(name, "CI wired: simulator battery + all %d prior tools" % len(expected))


def case_38_frozen_spec_intact() -> Result:
    name = "case_38_frozen_spec_intact"
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/"],
        capture_output=True, text=True, cwd=REPO,
    )
    if status.stdout.strip():
        return fail(name, "uncommitted spec/ changes: %s" % status.stdout.strip())
    ref_check = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, text=True, cwd=REPO,
    )
    if ref_check.returncode == 0:
        spec_diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "spec/"],
            capture_output=True, text=True, cwd=REPO,
        )
        if spec_diff.stdout.strip():
            return fail(name, "spec/ differs from origin/main: %s"
                        % spec_diff.stdout.strip())
        docs_diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "docs/"],
            capture_output=True, text=True, cwd=REPO,
        )
        changed = {line for line in docs_diff.stdout.splitlines() if line.strip()}
        allowed = {"docs/WORK-031-handoff.md"}  # the W023..030 handoff precedent
        if not changed <= allowed:
            return fail(name, "docs/ changes beyond the handoff: %r" % sorted(changed))
        workflow = subprocess.run(
            ["git", "diff", "origin/main", "--", ".github/"],
            capture_output=True, text=True, cwd=REPO,
        )
        if "simulator_selftest.py" not in workflow.stdout:
            return fail(name, ".github delta does not include the simulator CI step")
        tools_diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "tools/"],
            capture_output=True, text=True, cwd=REPO,
        )
        tool_changes = {line for line in tools_diff.stdout.splitlines() if line.strip()}
        allowed_tools = {
            "tools/telemetry_selftest.py",  # flagged W031 amendment (DAG W026->W027->W031)
            "tools/energy_selftest.py",     # flagged W031 amendment (DAG W027->W031)
            "tools/simulator_selftest.py",  # this battery
        }
        if not tool_changes <= allowed_tools:
            return fail(name, "tools/ changes beyond the flagged amendments: %r"
                        % sorted(tool_changes - allowed_tools))
        return ok(name, "spec/ byte-identical; docs/ = the W031 handoff; CI step "
                       "additive; tools/ = the two flagged amendments + this battery")
    tree = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/", "docs/"],
        capture_output=True, text=True, cwd=REPO,
    )
    if tree.stdout.strip():
        return fail(name, "working tree dirty over frozen surfaces: %s"
                    % tree.stdout.strip())
    return ok(name, "spec/ clean (origin/main ref unavailable; working tree clean)")


def case_39_api_surface_frozen() -> Result:
    name = "case_39_api_surface_frozen"
    import simulator

    expected = {
        "AuthorityMutation", "AuthorityTestSeam", "DeterministicStream",
        "EventKind", "EventVerdict", "FlowObservation", "MutationOutcome",
        "ObservationRecord", "ScenarioClock", "ScenarioPolicyRule",
        "ScenarioResult", "ScenarioSpec", "ScheduledEvent",
        "SimulatedEnvironment", "SimulatedLinkSpec", "SimulatedNodeSpec",
        "Simulator", "SimulatorError", "SimulatorReasonCode",
        "authority_digest", "result_from_mapping", "seam_verdict",
        "spec_from_mapping", "spec_to_mapping", "trace_digest",
        "verify_replay",
    }
    actual = set(simulator.__all__)
    if actual != expected:
        missing = expected - actual
        extra = actual - expected
        return fail(name, "surface drifted (missing %r, extra %r)"
                    % (sorted(missing), sorted(extra)))
    return ok(name, "public API surface frozen at %d symbols" % len(expected))


def case_40_determinism_across_hash_seeds() -> Result:
    name = "case_40_determinism_across_hash_seeds"
    script = (
        "import sys; sys.path.insert(0, %r); "
        "import tools.simulator_selftest as t; "
        "print(t._scenario_fingerprint())" % (REPO,)
    )
    digests = []
    for seed in ("0", "1", "7919"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=REPO,
            env=dict(os.environ, PYTHONHASHSEED=seed),
        )
        if proc.returncode != 0:
            return fail(name, "seed %s failed: %s" % (seed, proc.stderr.strip()[-300:]))
        digests.append(proc.stdout.strip())
    if len(set(digests)) != 1:
        return fail(name, "fingerprints diverge across seeds: %r" % (digests,))
    return ok(name, "composed scenario fingerprint identical across seeds 0/1/7919")


# --------------------------------------------------------------------------
# 41-44: PR #34 round-1 review corrections
# --------------------------------------------------------------------------


def case_41_multipath_digest_in_trace() -> Result:
    """BLOCKER 1 regression: the W013 multipath authority is inside the
    pre/post digest boundary -- a plan mutation is visible in the
    evidence record, and replay captures it."""
    name = "case_41_multipath_digest_in_trace"
    spec = ScenarioSpec(
        scenario_id="mp-digest", seed=61, start_instant=_START, tick_seconds=60,
        horizon_ticks=5, nodes=_nodes(), links=_links(), policy_rules=_rules(),
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.SESSION_REQUEST,
                           payload={"label": "s1", "source": _NODE_A,
                                    "destination": _NODE_B}),
            ScheduledEvent(at_tick=2, sequence=1, kind=EventKind.PATH_ADD,
                           payload={"label": "s1", "avoid": [[_NODE_A, _NODE_B]]}),
            ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.PATH_ADD,
                           payload={"label": "s1", "avoid": [[_NODE_A, _NODE_C]]}),
            ScheduledEvent(at_tick=4, sequence=1, kind=EventKind.PATH_FAIL,
                           payload={"label": "s1", "index": 1}),
            ScheduledEvent(at_tick=5, sequence=1, kind=EventKind.OBSERVE, payload={}),
        ),
    )
    result = Simulator(spec).run()
    # Every observation record carries the multipath digest entry.
    for record in result.trace:
        if "multipath" not in dict(record.after_digests):
            return fail(name, "record %r lacks a multipath digest" % record.kind)
        if record.kind != "bootstrap" and "multipath" not in dict(record.before_digests):
            return fail(name, "record %r lacks a pre-event multipath digest"
                        % record.kind)
    # The session's empty plan appears at creation, the path admission
    # changes the plan, and the constituent failure changes it again:
    # each mutation is visible in the multipath digest.
    session = _record(result, EventKind.SESSION_REQUEST)
    add = _record(result, EventKind.PATH_ADD)
    fault = _record(result, EventKind.PATH_FAIL)
    observe = _record(result, EventKind.OBSERVE)
    # Guard the fixture: both admissions and the constituent failure
    # must genuinely COMMIT (a silently rejected event would trivially
    # leave the digest unchanged).
    if any(m.outcome != MutationOutcome.COMMITTED for m in add.mutations) or \
            fault is None or not fault.mutations or \
            fault.mutations[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "fixture regression: multipath mutations did not commit: %r"
                    % ([(r.kind, [m.outcome for m in r.mutations])
                        for r in result.trace if r.mutations],))
    for record, label in (
        (session, "session creation (empty plan)"),
        (add, "path admission"),
        (fault, "constituent failure"),
    ):
        if dict(record.before_digests)["multipath"] == dict(record.after_digests)["multipath"]:
            return fail(name, "%s left the multipath digest unchanged" % label)
    # Control: a pure observation sweep does not touch multipath state.
    if dict(observe.before_digests)["multipath"] != dict(observe.after_digests)["multipath"]:
        return fail(name, "OBSERVE changed the multipath digest")
    # The final result exposes the multipath authority state, and a
    # full replay verifies the trace (digests included) byte-identically.
    if "multipath" not in dict(result.final_digests):
        return fail(name, "final digests lack the multipath entry")
    verified, detail = verify_replay(spec, result)
    if not verified:
        return fail(name, "replay rejected the multipath-carrying trace: %s" % detail)
    return ok(name, "W013 plan mutations visible in pre/post multipath digests; replay verified")


def case_42_partition_transactional_rejection() -> Result:
    """BLOCKER 2 regression: multi-target simulator state changes are
    transactional -- a partially valid partition payload mutates
    NOTHING, at the environment layer by construction and end-to-end
    through the runner (byte/state equality and zero progression)."""
    name = "case_42_partition_transactional_rejection"
    # -- Layer 1: the environment mutators themselves. -------------------
    spec = ScenarioSpec(
        scenario_id="txn-partition", seed=62, start_instant=_START, tick_seconds=60,
        horizon_ticks=1, nodes=_nodes()[:2],
        links=(SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),),
    )
    clock = ScenarioClock(_START, 60)
    stream = DeterministicStream(62, label="scenario")
    env = SimulatedEnvironment(spec, clock, stream)
    valid = env.link_subject(_NODE_A, _NODE_B)
    unknown = "adcos:link:no.pe.v1:" + "7" * 64

    def fingerprint() -> List[Tuple[str, str, bool]]:
        return [
            (subject, env.link_status(subject), env.is_degraded(subject))
            for subject in env.link_subjects
        ]

    pristine = fingerprint()
    try:
        env.cut_links((valid, unknown))
        return fail(name, "mixed cut did not fail closed")
    except SimulatorError as error:
        if error.code != SimulatorReasonCode.UNKNOWN_LINK:
            return fail(name, "mixed cut failed with the wrong code: %s" % error.code)
    if fingerprint() != pristine:
        return fail(name, "mixed cut mutated state before failing (non-transactional)")
    # Restore path: after a genuine cut, a mixed restore must restore
    # NOTHING -- the cut remains, so the rejection advanced no state.
    env.cut_links((valid,))
    cut_state = fingerprint()
    if cut_state == pristine:
        return fail(name, "valid cut did not change the fingerprint (bad fixture)")
    try:
        env.restore_links((valid, unknown))
        return fail(name, "mixed restore did not fail closed")
    except SimulatorError as error:
        if error.code != SimulatorReasonCode.UNKNOWN_LINK:
            return fail(name, "mixed restore failed with the wrong code: %s" % error.code)
    if fingerprint() != cut_state:
        return fail(name, "mixed restore mutated state before failing")
    # -- Layer 2: the runner boundary, end to end. -----------------------
    # One valid link followed by an unknown link (known nodes, no
    # simulated link between them): REJECTED with byte-identical
    # digests, and zero simulator progression -- the scenario without
    # the bad events produces byte-identical applied records and final
    # authority state.
    runner_nodes = _nodes()
    runner_links = (SimulatedLinkSpec(node_a=_NODE_A, node_b=_NODE_B),)
    runner_probes = ((_NODE_A, _NODE_B),)
    runner_rules = _rules()
    session_event = ScheduledEvent(
        at_tick=2, sequence=1, kind=EventKind.SESSION_REQUEST,
        payload={"label": "s1", "source": _NODE_A, "destination": _NODE_B})
    observe_event = ScheduledEvent(at_tick=3, sequence=1, kind=EventKind.OBSERVE,
                                   payload={})
    with_bad = ScenarioSpec(
        scenario_id="txn-runner", seed=63, start_instant=_START, tick_seconds=60,
        horizon_ticks=3, nodes=runner_nodes, links=runner_links,
        probes=runner_probes, policy_rules=runner_rules,
        events=(
            ScheduledEvent(at_tick=1, sequence=1, kind=EventKind.PARTITION_START,
                           payload={"cuts": [[_NODE_A, _NODE_B], [_NODE_A, _NODE_C]]}),
            ScheduledEvent(at_tick=1, sequence=2, kind=EventKind.PARTITION_END,
                           payload={"cuts": [[_NODE_A, _NODE_B], [_NODE_A, _NODE_C]]}),
            session_event,
            observe_event,
        ),
    )
    without_bad = ScenarioSpec(
        scenario_id="txn-runner", seed=63, start_instant=_START, tick_seconds=60,
        horizon_ticks=3, nodes=runner_nodes, links=runner_links,
        probes=runner_probes, policy_rules=runner_rules,
        events=(session_event, observe_event),
    )
    a = Simulator(with_bad).run()
    b = Simulator(without_bad).run()
    if a.rejected_events != 2:
        return fail(name, "expected 2 rejected records, got %d" % a.rejected_events)
    for record in a.trace:
        if record.verdict == EventVerdict.REJECTED:
            if dict(record.before_digests) != dict(record.after_digests):
                return fail(name, "rejected %r changed authority digests"
                            % record.kind)
            if record.mutations:
                return fail(name, "rejected %r mutated state" % record.kind)
    applied_a = [r.content_dict() for r in a.trace if r.verdict == EventVerdict.APPLIED]
    applied_b = [r.content_dict() for r in b.trace if r.verdict == EventVerdict.APPLIED]
    if applied_a != applied_b:
        return fail(name, "rejected partitions advanced the applied sequence")
    if dict(a.final_digests) != dict(b.final_digests):
        return fail(name, "rejected partitions changed the final authority state")
    if a.applied_events != b.applied_events:
        return fail(name, "applied counts diverged: %d vs %d"
                    % (a.applied_events, b.applied_events))
    return ok(name, "mixed partitions mutate nothing at either layer; zero progression")


def case_43_failed_event_preserves_committed_mutations() -> Result:
    """BLOCKER 3 regression: an unexpected fault AFTER a committed owner
    mutation cannot discard the trace's mutation ledger -- the failed
    record carries the committed mutation(s), the pre/post digests make
    the partial authority state explicit, and the event stays FAILED."""
    name = "case_43_failed_event_preserves_committed_mutations"
    from sessions.store import SessionStore

    class HostileTransitionSessionStore(SessionStore):
        # create() is INHERITED -- the real owner contract commits --
        # and the fault strikes a LATER owner call inside the same
        # multi-step event (the concrete exposure the review named).
        def transition(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("hostile transition after committed create")

    seam = AuthorityTestSeam(
        HostileTransitionSessionStore(),
        purpose="failed-event ledger preservation proof",
    )
    spec = _minimal_spec()
    result = Simulator(spec, seam=seam).run()
    failed = [r for r in result.trace if r.verdict == EventVerdict.FAILED]
    if len(failed) != 1:
        return fail(name, "expected exactly 1 failed record, got %d" % len(failed))
    record = failed[0]
    if record.kind != EventKind.SESSION_REQUEST:
        return fail(name, "failed record kind %r" % record.kind)
    # The create COMPLETED before the fault: its owner-contract record
    # must survive in the failed observation with its accurate verdict.
    creates = [m for m in record.mutations if m.operation == "create"]
    if len(creates) != 1 or creates[0].outcome != MutationOutcome.COMMITTED:
        return fail(name, "committed create mutation lost from the failed record: %r"
                    % (record.mutations,))
    if creates[0].authority != "sessions":
        return fail(name, "create record authority wrong: %r" % creates[0].authority)
    # Partial authority state is explicit BOTH ways: the preserved
    # ledger above AND the pre/post session digests diverging (the
    # session exists even though the event failed).
    if dict(record.before_digests)["sessions"] == dict(record.after_digests)["sessions"]:
        return fail(name, "session digests did not expose the partial state")
    # Flow records completed before the fault survive too.
    if not any(f.flow == "session" for f in record.flows):
        return fail(name, "completed session flow lost from the failed record")
    if "RuntimeError" not in record.detail:
        return fail(name, "exception class missing: %r" % record.detail)
    if result.failed_events != 1 or result.ok:
        return fail(name, "stats wrong: failed=%d ok=%r"
                    % (result.failed_events, result.ok))
    if len(result.trace) != 2:  # bootstrap + the failed session request
        return fail(name, "trace length %d (partial advance?)" % len(result.trace))
    return ok(name, "failed record carries the committed create mutation + diverging digests")


def case_44_bootstrap_identity_content_derived() -> Result:
    """Review-note regression: the bootstrap observation's event id is
    content-derived under the same canonical rule as every scheduled
    event -- no special sentinel identity, no order dependence."""
    name = "case_44_bootstrap_identity_content_derived"
    spec = _minimal_spec()
    result = Simulator(spec).run()
    bootstrap = result.trace[0] if result.trace else None
    if bootstrap is None or bootstrap.kind != "bootstrap":
        return fail(name, "no bootstrap record")
    event_id = bootstrap.event_id
    if not event_id.startswith("sha256:"):
        return fail(name, "bootstrap event id is not a content-derived "
                    "fingerprint: %r" % event_id)
    if event_id != spec.bootstrap_event_id():
        return fail(name, "bootstrap event id diverged from the spec-derived identity")
    # Insertion-order independence holds for the bootstrap identity:
    # permuting every configuration tuple (nodes/links/probes/rules and
    # the event schedule) changes nothing.
    base = _full_spec()
    permuted = ScenarioSpec(
        scenario_id=base.scenario_id, seed=base.seed,
        start_instant=base.start_instant, tick_seconds=base.tick_seconds,
        horizon_ticks=base.horizon_ticks,
        nodes=tuple(reversed(base.nodes)), links=tuple(reversed(base.links)),
        probes=tuple(reversed(base.probes)),
        policy_rules=tuple(reversed(base.policy_rules)),
        events=tuple(reversed(base.events)),
    )
    if permuted.bootstrap_event_id() != base.bootstrap_event_id():
        return fail(name, "configuration tuple order changed the bootstrap identity")
    # Different world content changes the identity (seed participates).
    different = ScenarioSpec(
        scenario_id=base.scenario_id, seed=base.seed + 7,
        start_instant=base.start_instant, tick_seconds=base.tick_seconds,
        horizon_ticks=base.horizon_ticks, nodes=base.nodes, links=base.links,
        probes=base.probes, policy_rules=base.policy_rules, events=base.events,
    )
    if different.bootstrap_event_id() == base.bootstrap_event_id():
        return fail(name, "world content change left the bootstrap identity unchanged")
    # Deterministic across runs.
    second = Simulator(spec).run()
    if second.trace[0].event_id != event_id:
        return fail(name, "bootstrap identity is not reproducible")
    return ok(name, "bootstrap identity content-derived, order-independent, seed-sensitive")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

CASES = (
    case_01_spec_validation_fail_closed,
    case_02_injected_scenario_clock,
    case_03_documented_prng_stream,
    case_04_bootstrap_real_authorities,
    case_05_complete_scenario_replay,
    case_06_insertion_order_independence,
    case_07_seed_reproducibility_and_sensitivity,
    case_08_time_base_reproducibility,
    case_09_cross_process_determinism,
    case_10_replay_verification_api,
    case_11_link_down_fault_injection,
    case_12_link_degradation_observable,
    case_13_partition_and_recovery,
    case_14_restart_rejoin_deterministic,
    case_15_session_fail_and_cleanup_pending,
    case_16_resource_exhaustion_observation,
    case_17_telemetry_observation_recorded,
    case_18_session_full_chain_observation,
    case_19_multipath_and_mobility_observation,
    case_20_policy_denial_default,
    case_21_policy_amend_explicit_deny,
    case_22_policy_amend_validation,
    case_23_simulator_authority_state_separation,
    case_24_no_private_authority_mutation,
    case_25_provenance_injection,
    case_26_forged_authority_objects_rejected,
    case_27_no_second_authority_structural,
    case_28_no_wall_clock_structural,
    case_29_universal_event_failure_boundary,
    case_30_rejected_events_advance_nothing,
    case_31_seam_requires_purpose,
    case_32_seam_restored_verdict,
    case_33_seam_validated_and_degraded_verdicts,
    case_34_serialization_round_trips,
    case_35_no_future_work_item_semantics,
    case_36_py_compile_clean,
    case_37_ci_wiring,
    case_38_frozen_spec_intact,
    case_39_api_surface_frozen,
    case_40_determinism_across_hash_seeds,
    case_41_multipath_digest_in_trace,
    case_42_partition_transactional_rejection,
    case_43_failed_event_preserves_committed_mutations,
    case_44_bootstrap_identity_content_derived,
)


def main() -> int:
    print("ADCOS network and behavior simulator self-test (WORK-031) -- %d cases"
          % len(CASES))
    print("-" * 72)
    failures: List[str] = []
    for case in CASES:
        try:
            name, passed, detail = case()
        except Exception as error:  # noqa: BLE001 -- battery robustness
            name, passed, detail = case.__name__, False, "EXCEPTION: %r" % error
        status = "[ok  ]" if passed else "[FAIL]"
        print("%s %-52s %s" % (status, name, detail))
        if not passed:
            failures.append(name)
    print("-" * 72)
    if failures:
        print("Result: FAIL (%d/%d cases failed)" % (len(failures), len(CASES)))
        for name in failures:
            print("  - %s" % name)
        return 1
    print("Result: PASS (%d/%d cases)" % (len(CASES), len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
