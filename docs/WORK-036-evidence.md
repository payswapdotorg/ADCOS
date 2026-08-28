# WORK-036 — Network-in-a-Box: Implementation Evidence

**Status:** implementation delivered for Architect review.
**Branch:** `work-036-network-in-a-box`, created from the W035 merge
commit `cffbe01639eca7c67988e2df16a7641e145203c1` (the Architect's
designated base).
**Battery:** `tools/appliance_selftest.py` — 42 cases, wired into CI
after the WORK-035 mobile step (work-item order).

## Two-track evidence classification (the W020/W034/W035 discipline)

| Track | Status |
| --- | --- |
| Software/simulated isolated-site integration | **supported-verified** (deterministic battery, 42/42) |
| Physical appliance deployment at a real site | **OPEN** — until genuinely demonstrated |

The disclosure is pinned as `appliance.isolation.APPLIANCE_EVIDENCE_STATUS`
and asserted by battery case_08 (an isolated-site simulation is
engineering verification, **never** a physical-deployment PASS). The
inherited WORK-034 hardware track (`HARDWARE_EVIDENCE_STATUS`) stays OPEN
and is asserted alongside. The later field run is a validation
obligation, not a reason to stop software development.

## What was implemented (`appliance/`, 7 files)

- **`errors.py`** — `ApplianceError` + frozen `ApplianceReasonCode`
  (11 reasons, `appliance.` prefix).
- **`model.py`** — frozen vocabularies (upstream mode, provision state,
  verdicts — the honest union of the inherited edge scheduler verdicts
  and the appliance-native ones, 9 command kinds, 3 provision step
  kinds, 10 event kinds) and value records (`GatewayEntry` /
  `ServiceEntry` / `FabricManifest` with canonical bytes and digests,
  `ProvisionStep`, `ApplianceCommand` with content-derived ids over a
  fail-closed canonical param projection, `ApplianceEvent` with
  content-derived ids, `ApplianceOutcome`, `ApplianceRunResult`) — DATA
  with validation, in the WORK-033 `agent.model` style.
- **`isolation.py`** — the upstream/isolated-site boundary: the
  two-track disclosure, the pure posture map, the local-fabric query
  policy (federated queries refused with typed reasons under BOTH
  postures — never silently downgraded), and the pure
  isolated-site readiness predicate.
- **`provisioning.py`** — the pure fail-closed manifest validation and
  step planning (types → evidence digests → vocabularies → duplicates →
  one-gateway-per-node → path coherence → emptiness); the frozen plan
  order is gateways → paths → services.
- **`fabric.py`** — the `FabricView` projection (adapters, posture,
  gateways, paths, services, completeness) over public reads only, with
  the pure `fabric_complete` predicate.
- **`appliance.py`** — `NetworkAppliance`: owns exactly one
  WORK-034 `EdgeGateway` (→ exactly one WORK-033 `AgentRuntime` with the
  WORK-030 management surface inside), exactly one WORK-025
  `ServiceRegistry` (reference edge executor) and one WORK-024
  `DistributedCoreManager` (reference LOCAL-mode IP gateway engine),
  each wired to THE runtime's session store through read-only
  projections; provisioning application through public contracts;
  service discovery/lookup/request (decisions as INPUT — the appliance
  never mints one, and the composition-root cross-check refuses
  decisions born-bound to another invocation scope); upstream posture
  control (strict toggle, journaled, forwarded to the W025 lever);
  `run_appliance` / `run_appliance_headless` / `verify_appliance_replay`.
- **`__init__.py`** — the frozen 35-export public API.

## Coverage vs the frozen contract

| Required discrimination | Evidence |
| --- | --- |
| local services without upstream Internet | case_17 (discover/lookup/EXECUTE fully isolated), case_23 (served while a live session runs), case_19 (ops continue across upstream transitions) |
| multiple access adapters coexist | case_11 (three adapters OPEN simultaneously; edge posture connected; access plan respected) |
| operators provision a complete local fabric | case_12 (2 gateways, 2 paths, 2 services from one manifest; `FabricView.complete`), case_39 (honest observation before/after), case_16 (completeness pure; live view) |
| invalid manifests rejected fail-closed | case_04 (pure validation: digests, vocabularies, duplicates, node ambiguity, path coherence, emptiness), case_13 (nothing applied; journaled), case_14 (mid-apply conflict: typed reason, honest partial detail, tracked fabric unchanged), case_15 (re-provision: services repeat-safe; duplicate gateways typed) |
| isolated-site INTEGRATION | case_23 (two complete appliances: peered runtimes, ordinary session, byte-identical datagram round-trip, live local service, both boxes isolated), case_25 (local breakout serves a REAL session through a provisioned gateway and path), case_26 (no remote breakout in the box — honest typed mismatch) |
| upstream posture | case_19 (journaled, forwarded, strict toggle), case_18 (federated refusal under both postures), case_24 (`session_id` sacred across upstream transitions) |
| operators through W030 | case_27 (RBAC-gated reads; unknown operator denied AND audited; chain verifies) |
| edge resource-awareness inherited | case_22 (critical pressure: essential commands defer with typed reasons, surfaced verbatim — 110 executed / 10 deferred) |
| decisions as INPUT (no minting) | case_21 (missing/mistyped → typed refusal; rebound scope → refused BEFORE the registry is touched; bad hex typed), case_17 (genuine born-bound decision executes) |
| lookup failures typed | case_20 (unknown/withdrawn surface the frozen W025 reasons; params discipline) |
| no shadow authority | case_33 (no authority constructor in `appliance/`; exactly one `EdgeGateway`/`ServiceRegistry`/`DistributedCoreManager`), case_09 (`runtime is gateway.runtime`; readers bound to THE session store; mistyped seams rejected) |
| import discipline | case_34 (sanctioned roots only: agent, edge, services, adapters.distcore, routing, protocol.canonicalization, sessions/policy as DATA vocabularies; adapters narrowed to distcore) |
| later-work freedom | case_35 (no W037+ naming tokens) |
| determinism | case_28 (fresh runs byte-identical), case_29 (`PYTHONHASHSEED` 0/1/7919/None subprocess invariance), case_30 (replay verify accepts/rejects) |
| injected clock only | case_32 (no wall clock / randomness / OS / network in `appliance/`) |
| secret hygiene | case_31 (boot secret and payload content never in any surface; details carry digests) |
| anti-faking disclosure | case_08 (two-track status pinned; inherited hardware track OPEN) |
| frozen surfaces | case_01/05/06/07 (vocabularies and records), case_37 (API exact), case_40 (spec/ byte-identical), case_41 (PR-delta shape), case_42 (CI wiring + ordering) |

## Dependency consumption (through accepted public contracts only)

- **W033 (Linux agent):** the unchanged `AgentRuntime` — owned by the
  owned `EdgeGateway`; passthrough commands (`boot`,
  `expose-interfaces`, `monitor`) are re-wrapped as genuine
  `AgentCommand` values and routed through the UNCHANGED
  `EdgeGateway.run_edge` path (which routes through the unchanged
  `AgentRuntime.execute`); sessions flow through the ordinary
  handshake; no agent semantic is re-implemented, patched, or shadowed.
- **W034 (edge gateway):** the unchanged `EdgeGateway` — composed, one
  per appliance; pressure/posture/coexistence surfaces are read through
  the gateway's public properties; the scheduler verdicts are surfaced
  verbatim (never remapped).
- **W030 (management):** consumed through the runtime's own
  `management_api` (RBAC roles + operator ids carried in the
  `AgentConfig` DATA, as in WORK-033); the appliance adds no
  management operation.
- **W025 (services):** one `ServiceRegistry` over the reference edge
  executor with a read-only `SessionReader` projection of THE runtime's
  store (the `_StoreSessionReader` composition-root pattern); the W025
  upstream lever is the appliance's isolated-site posture control;
  invocation decisions are genuine born-bound INPUT (the engine recipe
  from the accepted WORK-025 battery), with a composition-root
  scope-coherence cross-check before the authority is touched.
- **W024 (distributed core):** one `DistributedCoreManager` over the
  reference LOCAL-mode `ReferenceIPGatewayEngine` with its own
  read-only `SessionReader` projection; gateways/paths provision
  through `register_gateway`/`register_path`; the LOCAL-only provider
  set is a design decision (the box breaks out locally; a REMOTE-mode
  determination fails with the honest typed `path-gateway-mismatch`).

## Composition and determinism discipline

- One `EdgeGateway` per appliance (→ one runtime, one management
  surface); one service registry; one distributed-core manager; the
  readers are bound to THE runtime's genuine `SessionStore` (type
  validated, read-only).
- One epoch = one injected-clock read; every decision is journaled in
  the append-only `ApplianceEvent` journal with content-derived ids;
  whole scenarios are one replayable digest (`appliance_digest`), and
  the appliance `content_digest` covers the appliance snapshot plus the
  service/distcore/edge digests.
- No wall clock, no randomness, no OS or network access anywhere in
  `appliance/`.

## Flagged battery amendments (all narrowing, DAG-cited)

1. `tools/agent_selftest.py` case_40 allowlist +=
   `tools/appliance_selftest.py` + `docs/WORK-036-handoff.md` +
   `docs/WORK-036-evidence.md`; `_EXPECTED_TOOLS` += the appliance
   battery. (W033 → W036: the appliance battery extends the agent
   battery transitively through the W034 edge composition.)
2. `tools/edge_selftest.py` case_47 `allowed_exact` += the appliance
   battery + both docs and the `appliance/` prefix; `_EXPECTED_TOOLS`
   += the appliance battery; the case_47 `.github` delta check made
   removal-aware (W034 → W036, the W033 → W035 precedent: the
   successor's appended CI step no longer sits adjacent to the edge
   step, so the context-line heuristic no longer holds; the invariant
   is unchanged and stronger — the edge CI step stays present and no
   delta line removes it).
3. `tools/mobile_selftest.py` case_44 `allowed_exact` += the appliance
   battery + both docs and the `appliance/` prefix; case_45
   `_EXPECTED_TOOLS` += the appliance battery with the ordering
   agent < edge < mobile < appliance. (W035 → W036: the appliance
   battery follows the mobile battery in work-item order.)

No frozen `spec/` file was modified; `agent/`, `edge/`, `mobile/`,
`services/`, `adapters/` sources are untouched (only the sanctioned
battery amendments above).

## Local verification evidence

- `python3 tools/appliance_selftest.py` — **PASS 42/42**.
- `python3 tools/agent_selftest.py` — **PASS 45/45** (amendments active).
- `python3 tools/edge_selftest.py` — **PASS 48/48** (amendments active).
- `python3 tools/mobile_selftest.py` — **PASS 45/45** (amendments active).
- `python3 tools/spec_check.py` — **PASS 9/9** blocking checks.
- The four W020-precedent local-context artifacts (conformance
  case_45 / management case_32 / simulator case_38 / upgrade case_36)
  flag "docs/ changes beyond their own handoff" against a local
  `origin/main` ref and pass in CI's depth-1 degraded mode — the
  accepted PR #21/#39/#40 precedent.

## Field-deployment guidance

Track 1 (software/simulated) is fully covered by the deterministic
battery: the scripted world drives provisioning, isolation, upstream
transitions, sessions, breakouts, and operator surfaces with injected
time. A field run should implement the platform seams (hardware source,
interface source, execution/breakout providers) over a real appliance
at a real isolated site and re-run the same scenario scripts; that run
— and only that run — may close the physical-deployment track, which
remains **OPEN** here.
