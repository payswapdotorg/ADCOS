# ADCOS Simulator — WORK-031: Network and Behavior Simulator

A deterministic simulator for ADCOS nodes, links, failures, resources,
mobility, and policies. The simulator is a controlled, reproducible
environment AROUND the accepted authorities — never a replacement
protocol implementation and never a second protocol authority.

## Module authority

`/simulator` owns deterministic scenario orchestration and the
simulated environment state. It does NOT own:

- topology truth (WORK-007 `TopologyGraph` — composed read/write via `merge`),
- resource truth (WORK-008 `ResourceStore`),
- policy decisions (WORK-010 `PolicyEngine`/`PolicyStore` — no shadow
  policy engine exists here),
- path selection (WORK-011 `RoutingEngine` — the simulator never picks
  a path),
- session lifecycle (WORK-012 `SessionStore`),
- multipath plans (WORK-013 `MultipathStore`),
- mobility transactions (WORK-014 `MobilityStore`),
- telemetry records (WORK-026 `TelemetryStore`),
- energy/resilience mechanics (WORK-027 `PowerSimulator`,
  `EnergyGovernor`, `NodeRejoinLedger`).

Every authority interaction goes through the owner's public,
least-authority contract and is recorded in the trace's mutation
ledger. The simulator never imports adapter SDKs or vendor names
(LOCK-016/017), never imports future W032+ runtime semantics, and is
never used as external interoperability evidence.

## Deterministic execution contract

- **Time is always injected.** `ScenarioClock` maps integer ticks to
  RFC 3339 UTC instants from the explicit `start_instant` +
  `tick_seconds`. No wall clock is read anywhere in the family (the
  self-test enforces this structurally over the source).
- **Randomness is explicit.** Where stochastic variation is genuinely
  required (degraded-link metric penalties, telemetry confidence
  jitter, exhaustion magnitude), it is drawn from
  `DeterministicStream`: a counter-based sha256 PRNG
  (`sha256("<seed>|<label>|<counter>")`, rejection sampling over the
  first 8 bytes little-endian) bound to the explicit scenario seed.
  No language-level PRNG, no hash-seed dependence.
- **Identity is content-derived.** Event ids and observation ids are
  sha256 fingerprints over canonical JSON (WORK-003 machinery). No
  mutable counters participate in identity.
- **Execution order is explicit.** Events are applied ordered by
  `(at_tick, sequence)`; two specs differing only in tuple order are
  the same scenario (insertion/order independence).
- **Reproducibility.** `trace_digest` is the sha256 over the canonical
  bytes of the ordered observation records. Identical seed + spec
  produces an identical digest — in-process, across processes, and
  across hash seeds. `verify_replay(spec, result)` re-runs and
  verifies; replay evidence is committed only after the digest
  verification passes.

## Simulation state model

Five separated state classes (frozen handoff §8):

1. **Scenario configuration** — the immutable `ScenarioSpec`
   (nodes/links/probes/policy material/events, explicit seed and time
   base);
2. **Simulated environment state** — `SimulatedEnvironment`: node
   power simulators, link status, partition cuts, online flags
   (simulator-owned; holds NO authority references);
3. **Scheduled events** — `ScheduledEvent` records with explicit
   ordering keys and content-derived ids;
4. **Observed authoritative outputs** — `ObservationRecord`s with
   pre/post authority digests, the mutation ledger, and flow
   observations (references only — never authority objects);
5. **Evidence/trace state** — the ordered trace and its digest.

A rejected event (semantic fail-closed target resolution) advances no
simulator state. An unexpected exception during event application is
contained by the universal event failure boundary as exactly one
`failed` record whose pre/post digests make any partial state
explicit.

## Authority composition (the genuine chains)

- **Bootstrap (tick 0):** per-node WORK-008 energy resources + offers;
  WORK-027 survival profiles in the rejoin ledger; WORK-007 REACHABLE
  self-claims per node + LINK_STATE claims per link; the initial
  WORK-010 policy set published through the real `PolicyStore` (issuer
  = the scenario's first node — an anonymous policy is not
  publishable).
- **SESSION_REQUEST:** real policy evaluation (conservative cross-set
  aggregation identical to the accepted WORK-030 management plane: an
  explicit blocking code in ANY live set denies; a silent set does not
  veto another set's explicit ALLOW) → real routing evaluation over
  the current topology/resources/link-metric facts → real session
  create → real lifecycle transitions to ESTABLISHED. The runner
  retains the session's route decision AND its accepted policy
  decision (the policy binding never changes silently).
- **PATH_ADD / MOBILITY_HANDOVER:** the alternate/candidate route is
  computed by the REAL routing engine under the session's RETAINED
  accepted policy decision (the WORK-012/013/014 binding contract),
  then admitted by the real `MultipathStore.add_path` /
  `MobilityStore.prepare_handover` + `commit_handover`
  (make-before-break, session identity preserved).
- **PATH_FAIL:** `MultipathStore.change_path_status` → `FAILED`
  (constituent failure never redefines the session's authoritative
  route; loss of one path does not terminate the session).
- **LINK_*/PARTITION_*:** environment state change → a real WORK-007
  link-state claim merged through `TopologyGraph.merge` → probes
  re-observed (policy + routing over the changed authority state).
- **NODE_UP (restart/rejoin):** `NodeRejoinLedger.rejoin` with claimed
  energy state from the node's real power simulator.
- **RESOURCE_EXHAUST:** a real WORK-008 `ResourceMeasurement` carrying
  a real `EnergyState` value, recorded through `ResourceStore`.
- **TELEMETRY_EMIT:** a real WORK-026 `TelemetryObservation`
  (self-advertised, W026 vocabulary and provenance discipline)
  recorded through `TelemetryStore.record_observation`.
- **OBSERVE:** probe sweep + per-node energy postures via
  `EnergyGovernor` over real `EnergyState`s.
- **CLEANUP:** real `SessionStore.terminate`; an owner-contract
  cleanup failure becomes an explicit PENDING mutation (never a
  silent pass).

The `avoid` exploration input (path-add/handover) hands the routing
engine metric facts with an extreme latency penalty on named links —
scenario exploration input in exactly the shape an operator supplies;
the routing authority still selects.

## The explicit, restored test seam

By default the simulator builds a fully isolated authority set — no
production authority object is reachable, so production authority
state cannot be mutated at all. The one sanctioned exception is
`AuthorityTestSeam(component, purpose)`:

- the purpose is mandatory and recorded in the scenario result;
- every mutation of the seam component goes through the owner's public
  contract and appears in the trace's mutation ledger;
- on close, the component is digested through its own canonical state
  API (`NodeRejoinLedger.ledger_digest`, `SessionStore.to_canonical_bytes`,
  `TelemetryStore`/`MobilityStore`/`PolicyStore` `snapshot()`), and
  the verdict is `restored` (digest unchanged), `validated` (digest
  changed through trace-recorded owner contracts), or `degraded`
  (cleanup failed / validation failed — explicit, never silent).

Integrity is not provenance: a digest match does not prove WHO caused
a mutation — the recorded mutation ledger does.

## Security / anti-drift rules

- Simulation objects that look valid are never substituted for real
  authority objects where the contract requires owner verification
  (the session-create chain only accepts engine-minted decisions; the
  self-test proves a forged decision fails closed).
- Private fields are not a security boundary; adapter/vendor names are
  opaque data at this layer.
- Simulator state is never protocol truth; telemetry produced here is
  evidence/data under the W026 recordedness/authorization model, never
  independent external evidence.
- The frozen `spec/` surfaces are untouched by this family; any
  required semantic change is an ACR first.

## Files

- `model.py` — frozen vocabularies, scenario spec, observation records;
- `time.py` — the injected `ScenarioClock`;
- `random.py` — the documented `DeterministicStream`;
- `environment.py` — `SimulatedEnvironment` (world state + projections
  into real authority input records);
- `seam.py` — `AuthorityTestSeam` + authority digesting;
- `runner.py` — `Simulator` (the orchestration core),
  `verify_replay`, `trace_digest`;
- `serialization.py` — canonical spec/result mappings (cross-process
  determinism);
- `../tools/simulator_selftest.py` — the deterministic scenario test
  battery (CI-wired).
