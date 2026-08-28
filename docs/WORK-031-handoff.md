# WORK-031 — Network and Behavior Simulator: Implementation Handoff

## Status

Implementation complete on branch `work-031-network-behavior-simulator`
(anchored on `main@bd775c5`, the verified W030 merge). Verification:
simulator battery 40/40 PASS, mypy `--strict` clean over
`simulator/` + `tools/simulator_selftest.py` (9 files), full repository
battery rerun (see the PR). Frozen `spec/` untouched; `.github/` delta
is one additive CI step; `docs/` delta is this handoff only.

## Authoritative contract

`spec/work-items.md` WORK-031 — Network and behavior simulator.
Objective: build a deterministic simulator for nodes, links, failures,
resources, mobility, and policies. Dependencies: WORK-007 (topology),
WORK-011 (routing), WORK-012 (sessions), WORK-013 (multipath),
WORK-027 (energy/resilience). Acceptance criteria: scenarios
reproducible; failures injectable; topology and policy behavior
observable; simulation does not alter core semantics. Required
verification: deterministic scenario tests.

## Architectural rules

- `/simulator` owns deterministic scenario orchestration and the
  simulated environment state — nothing else. It composes the real
  W007 `TopologyGraph`, W008 `ResourceStore`, W010
  `PolicyEngine`/`PolicyStore`, W011 `RoutingEngine`, W012
  `SessionStore`, W013 `MultipathStore`, W014 `MobilityStore`, W026
  `TelemetryStore`, and W027 `PowerSimulator`/`EnergyGovernor`/
  `NodeRejoinLedger` through their public, least-authority contracts.
- No shadow authorities: no second policy engine, no route selection,
  no session mutation outside `SessionStore`, no topology truth, no
  telemetry bypass. Every authority mutation is recorded in the trace
  mutation ledger with the owner's own verdict
  (committed/rejected/pending/degraded).
- Determinism: injected `ScenarioClock` (ticks → RFC 3339 UTC; no wall
  clock anywhere in the family — structurally enforced);
  `DeterministicStream` = documented counter-based sha256 PRNG bound
  to the explicit scenario seed; content-derived event/observation
  ids; execution ordered by explicit `(at_tick, sequence)` keys
  (insertion-order independent); `trace_digest` over canonical bytes.
- State model: scenario configuration / simulated environment state /
  scheduled events / observed authoritative outputs / evidence-trace
  state are separated. Rejected events advance nothing; unexpected
  exceptions are contained by a universal event failure boundary as
  exactly one `failed` record with pre/post authority digests.
- Fault taxonomy (first-class scenario events): link down/up/degraded,
  partition start/end, node down/up (restart/rejoin through the real
  W027 ledger), resource exhaustion (real W008 `EnergyState`
  measurement), session failure (real W012 transition table), path
  failure (real W013 status change; the session survives), policy
  amend/withdraw (real W010 store), telemetry emission (real W026
  observation), mobility handover (real W014 make-before-break),
  cleanup — and cleanup failure becomes an explicit PENDING state,
  never a silent pass.
- The explicit, restored test seam: default = fully isolated authority
  instances (no production state reachable). `AuthorityTestSeam`
  grants scoped access to ONE caller-provided component with a
  mandatory purpose; mutations are trace-recorded; close computes
  `restored` (digest equal) / `validated` (trace-recorded owner
  mutations) / `degraded` (pending cleanup or failed validation).
- Degradation is a METRIC dimension, not a topology state (LOCK-009):
  a degraded link stays `up` in its W007 claim and carries the
  deterministic metric penalty in the W011 facts (routing only builds
  candidates over UP links).
- Session policy binding never changes silently: path-add and
  mobility candidates are computed under the session's RETAINED
  accepted policy decision (the W012/013/014 binding contract).

## Deliberate, flagged amendments to accepted dependency surfaces

Both follow the established amendment pattern (the W027/W029/W030
amendments in the telemetry leaf invariant):

1. `tools/telemetry_selftest.py` case_19 (the accepted W026 leaf
   invariant): the `simulator` family is exempted from the
   reverse-import scan as a dependency-graph-sanctioned DOWNSTREAM
   consumer of telemetry TRANSITIVELY — its frozen hard dependency
   WORK-027 declares WORK-026 (`W026 --> W027 --> W031` in the frozen
   DAG) — and the WORK-031 boundary requires scenario telemetry to be
   evidence/data under the W026 vocabulary and provenance discipline.
   The usage is pinned to the DATA surface only
   (`telemetry.model/store/errors`), exactly like the management
   amendment. If the Architect rules the transitive justification
   insufficient, the correction is mechanical: remove the
   `telemetry-emit` event kind and the seam's TelemetryStore support
   (no frozen surface depends on them).
2. `tools/energy_selftest.py` case_30 (the accepted W027 import
   discipline): the `simulator` family is exempted from the
   "nothing imports energy" reverse-import scan on the DIRECT frozen
   DAG edge `W027 --> W031` (WORK-031 declares WORK-027 among its
   hard dependencies). The simulator composes the real
   PowerSimulator/EnergyGovernor/NodeRejoinLedger through their public
   surfaces only.

Known pre-existing local artifacts (unchanged from the W030 cycle,
both green in CI's degraded mode where no `origin/main` ref exists):
`tools/upgrade_selftest.py` case_36 and `tools/management_selftest.py`
case_32 hardcode their era's docs allowlists, so the committed
`docs/WORK-031-handoff.md` delta trips them LOCALLY only — the exact
artifact class the W030 cycle documented for the upgrade battery.

## Deliberate, flagged decisions

1. **Session lifecycle completion:** `SessionStore.create` leaves a
   session in `REQUESTED`; the runner drives the genuine W012
   transitions `REQUESTED → AUTHORIZED → ESTABLISHED` after creation
   so the session is operational for plan/handover/terminate
   operations. All transitions are owner-contract calls, recorded as
   mutations.
2. **Survival-profile completion constants:** `SimulatedNodeSpec`
   carries the thresholds scenarios vary; the remaining W027
   `SurvivalProfile` fields are documented constants (empty service
   classes, upstream 2/4/3 counters, loss threshold 2000 bp, max
   generation 500 mW) so derived profile ids stay pure functions of
   the spec.
3. **Avoid-variant exploration input:** path-add/handover hand the
   routing engine metric facts with an extreme latency penalty
   (1e9 ms) on named links — scenario exploration input in the same
   shape an operator supplies; the routing authority still selects.
4. **Degraded-link metric penalty:** latency ×(2..4), loss +1000..2000
   bp, drawn only from the explicit scenario seed (the only stochastic
   variation in the family).
5. **Energy resource registration:** each node registers one WORK-008
   ENERGY resource (`simulator:node-energy` scope) with an offer at
   bootstrap; exhaustion measurements carry real `EnergyState` values
   (the W008 requirement for ENERGY-kind measurements).

## Required proof style

- Deterministic scenario tests are discriminating: six
  degraded-implementation proofs (failure boundary removed; tuple-order
  execution; degradation leaking into the topology claim; private
  authority mutation; wall clock; shared authority instance) each make
  the corresponding regression FAIL — the battery is not
  vacuously green.
- Cross-process determinism: identical trace digests under
  PYTHONHASHSEED 0/1/7919 in subprocesses and in-process.
- Provenance discipline: every scenario-injected record carries
  simulator provenance; remote claims never enter the W007
  authoritative set (LOCK-008/009); telemetry observations are
  self-advertised W026 records.
- Integrity ≠ provenance: a forged `PolicyDecision` (well-formed,
  wrong decision id) cannot underwrite a session; the simulator mints
  no policy decisions at all (structural).

## Out of scope

No protocol semantic rewrite; no second authority; no production
networking stack; no real radio/vendor integration (no vendor tokens —
structurally enforced); no conformance certification by simulation
(the simulator is never external interoperability evidence); no W032
conformance suite; no Linux Agent; no frozen-spec changes; OAQ-001
(the W032/W016 dependency discrepancy) untouched.

## No architecture drift

Frozen `spec/` is byte-identical to `origin/main`. The `.github/` delta
is one additive CI step (`Run network/behavior simulator tests`). The
`docs/` delta is this handoff only. Known pre-existing artifact
(unchanged from the W030 cycle): `tools/upgrade_selftest.py` case_36
hardcodes `docs/WORK-029-handoff.md` in its local-only docs allowlist,
so it fails locally on any branch adding a handoff document while CI
passes in degraded mode (no `origin/main` ref) — verified byte-identical
behavior on `main@bd775c5`.
