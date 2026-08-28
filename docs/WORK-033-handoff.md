# WORK-033 — Linux Agent: implementation handoff

Status: **IMPLEMENTED** — PR submitted, awaiting Architect review.
Branch: `work-033-linux-agent`, anchored at `main@44838d0d4c0b47ccb85b4061ec706ed3e59642d8`
(the WORK-032 merge).

## What was built

A new `agent/` family — the Linux reference agent — plus the
`tools/agent_selftest.py` verification battery (45 cases), one additive
CI step, and three dependency-graph-sanctioned allowlist amendments in
accepted batteries. No frozen architecture, spec, or prior family code
was modified.

| Module | Content |
|---|---|
| `agent/errors.py` | `AgentError` + the frozen 19-code `AgentReasonCode` vocabulary (caller-side composition faults only; adapter/transport/IP faults surface through their own typed failure values). |
| `agent/model.py` | Pure-DATA value model: `InterfaceSnapshot` (the Linux interface projection), `AgentEvent`/`AgentEventType` (the append-only log, content-derived ids), `AgentCommand`/`CommandKind`/`CommandOutcome`/`AgentRunResult` (the headless batch model with an integrity ledger), `AgentConfig` (+ identity/link-metric/migration specs; the credential secret is never configuration), the cross-agent establishment artifacts, and `MonitoringReport`. |
| `agent/clock.py` | The time seam: `SystemClock` (the ONLY wall-clock site in the family), `StepClock`/`FixedClock` (deterministic), instant arithmetic. Every authority call receives explicit injected instants. |
| `agent/interfaces.py` | Interface discovery: `LinuxInterfaceSource` (real read-only `/sys/class/net` + `/proc/net/if_inet6` via `pathlib`; kernel hwtype classification) and `StaticInterfaceSource` (the deterministic seam). The only filesystem-access site in the family. |
| `agent/bridge.py` | `InterfaceTechnologyAdapter(AdapterContract)` + `interface_descriptor`: bridges discovered interfaces into the WORK-016 SDK. Technology map ethernet→`access.ieee.8023`, wireless→`access.ieee.80211`, loopback/other→`access.generic.experimental` (registry DATA; no core branching). Deterministic step charges; opaque `agent-if:` refs. |
| `agent/monitoring.py` | Monitoring by composition: samples adapters through the sanctioned observe path, records genuine W026 observations (ADAPTER_HEALTH health-state/consecutive-failures + the six LINK metrics, SELF_ADVERTISED, bounded freshness), and assembles the report from the authorities' own state. |
| `agent/serialization.py` | Fail-closed round-trip helpers over WORK-003 canonicalization. |
| `agent/runtime.py` | `AgentRuntime` — the composition root: isolated real instances of identity (W004), topology (W007), resources (W008), policy (W010), routing (W011), sessions (W012), federation (W015), adapters (W016), transport (W017), IP integration (W018), telemetry (W026), upgrade (W029), management (W030) — plus boot/expose/register-peer, the four-leg cross-agent session establishment (request → accept → complete → finalize), bind/send/receive/suspend/terminate, monitor, negotiate-peer, self-test (the W032 matrix), shutdown, `execute()` (headless command batch with before/after authority digests and a trace digest), `run_headless`, and `verify_agent_replay`. |
| `agent/__init__.py` | Frozen 45-symbol public API. |

## Coverage against the frozen contract

Frozen acceptance criteria (`spec/work-items.md` WORK-033) → battery
cases (all PASS, `python3 tools/agent_selftest.py`):

- **"node can run headless"** — cases 01–04: data-driven boot with an
  injected secret (never command data), lifecycle guards, a
  5-command headless batch (`BOOT/EXPOSE/MONITOR/SELF_TEST/SHUTDOWN`)
  with a stable trace digest, and `BOOT` without an injected secret
  rejected. The family AST-audit (case 37) proves no interactive input
  anywhere.
- **"multiple network interfaces can be exposed as adapters"** —
  cases 05–10: static-seam determinism; the REAL Linux
  `/sys/class/net` source (loopback included); three interfaces
  exposed as three WORK-016 adapters under registered technologies
  (802.3 / 802.11 / generic-experimental) with validated descriptors
  and resource mappings; the six-metric observe vocabulary; typed
  capacity exhaustion; bind/unbind over a real session; and failure
  isolation (a flaky interface adapter faults as a typed value,
  siblings unaffected, health ladder DEGRADED/FAILED).
- **"sessions can be established and monitored"** — cases 11–20: the
  genuine chain on the initiator (engine-minted W010 decision → real
  W011 route → W012 session → W017 offer); mirrored sessions on the
  responder with the 4-step mutual-authentication handshake between
  two INDEPENDENT runtimes; bidirectional protected datagrams with
  tamper and replay rejection; responder DENY policy, initiator
  deny-by-default, route unavailability, and forged-decision
  artifacts all failing CLOSED; monitoring reflecting authority state
  (suspend reconciles adapter bindings); and full teardown
  (terminating closes transports, bindings, and both agents).
- **"logs/metrics are available"** — cases 21–25: 8 genuine W026
  observations per adapter per monitor cycle (2 adapter-health + 6
  link metrics) recorded in the real store; freshness windows
  (stale data audit-only); the append-only agent event log with
  unique content-derived ids and stable canonical bytes; management
  reads + a privileged `create_session` through the real W030 API
  with a verified tamper-evident audit chain; and the two-key RBAC
  model (an observer role reads but cannot create; denials are
  audited).
- **"end-to-end Linux tests"** (required verification) — cases 06 and
  31: real `/sys/class/net` discovery on this host, and application
  bytes carried over a REAL `AF_INET6` loopback socket through the
  agent's IP integration (threaded echo peer; the WORK-018 loopback
  conformance engine swapped in through the sanctioned
  `register_implementation` seam before binding).
- **Definition of done ("a general-purpose computer can participate
  in ADCOS")** — cases 12, 31, 33: two independent general-purpose
  nodes establish, bind, exchange datagrams, monitor, and tear down;
  the data path carries ordinary application bytes over real Linux
  sockets; and the whole flow is byte-reproducible.

Additional composed-dependency coverage:

- **W029**: cases 26–28, 32 — mixed-version coexistence (common
  profile 1.0), major-mismatch/unknown failing closed with no
  fallback, staged upgrades whose gates demand RECORDED telemetry
  evidence (`INSUFFICIENT_EVIDENCE` starved, pass after `monitor()`
  records real observations; commit migrates the agent-owned schema;
  rollback restores byte-identically), and the `NEGOTIATE_PEER`
  headless command.
- **W032**: cases 29–30 — the agent embeds the accepted conformance
  matrix as a verifier (136/136 CONFORMANT, stable digest across
  runs), and the agent's OWN interface adapter passes 14/15
  adapter-area vectors as a substituted candidate surface
  (`W032-CNF-ADP-001` pins the reference double's declared capability
  and is reference-pinned by design; its exposure==declared contract
  is re-proven against the candidate's own descriptor).

## Composition, not re-implementation

The agent is a composition root and never a second authority
(case 36 AST-proves no `PolicyDecision`/`RouteDecision` construction
and no authority subclassing):

- policy decisions come only from the real W010 `PolicyEngine`;
- route decisions only from the real W011 `RoutingEngine`;
- sessions only from the real W012 `SessionStore` (mirrored sessions
  reference the initiator's accepted artifacts — the W012
  reference-not-recompute contract);
- secure transport only from the real W017 `TransportManager`
  (integrity non-waivable, replay windows, downgrade rejection);
- interfaces only through the real W016 SDK (sandboxed, step-budgeted,
  failure-isolated);
- IP flows only through the real W018 manager (route/session identity
  separation, app-transparency `AppSocket`);
- metrics only through the real W026 store;
- version truth only from the real W029 manager;
- privileged operations only through the real W030 API (two-key RBAC
  + policy + tamper-evident audit);
- contract verification only through the real W032 suite.

Peer trust installation is explicit and honest: the responder-side
gate is the real policy engine; the dev identity profile's symmetric
verification requires locally installed verification material
(PSK-shaped, the documented WORK-004 dev limitation; production
asymmetric providers install public material only).

## Determinism

- Injected time only: the clock seam is the sole wall-clock site
  (case 37); the battery runs on `StepClock`/`FixedClock`.
- Case 33: two complete two-agent scenarios are byte-identical
  (node content digests, event-log digests, authority digests).
- Case 34: identical trace digests across fresh subprocesses and
  `PYTHONHASHSEED` ∈ {0, 1, 7919, unset}.
- Case 35: `verify_agent_replay` accepts a matching expected digest
  and rejects a wrong one.
- All identifiers are content-derived over WORK-003 canonical JSON.

## Frozen-surface discipline

- `spec/` byte-identical to origin/main (context-aware case 40: PR
  delta on branches, committed-wiring verification on main, clean-spec
  degraded mode when the origin/main ref is absent).
- `docs/` delta = this handoff only; `tools/` delta = the battery +
  the three sanctioned amendments below; `.github/` delta = one
  additive CI step (`Run Linux reference agent tests`,
  `python3 tools/agent_selftest.py`, unconditional — the
  post-PR-#36 context-aware pattern, no PR-gating).
- Public API frozen at 45 symbols (case 39); `py_compile` clean
  (case 42); no vendor/access tokens (case 38); no secret bytes in
  events, snapshots, frames, or audit records (cases 03, 45).
- mypy `--strict --follow-imports=silent` clean over all 9 agent
  files (the accepted W030/W031 invocation).

## Import discipline

Imports are limited to: the seven declared dependency families
(`adapters` incl. `adapters.ip`, `transport`, `telemetry`, `upgrade`,
`management`, `conformance`) + the sanctioned TRANSITIVE input
surfaces required by their public constructors/artifacts (W003
protocol, W004 identity, W007 topology, W008 resources, W010 policy,
W011 routing, W012 sessions, W015 federation — the same
transitive-input judgment W031/W032 used for W011/W012 inputs).
Forbidden roots (asserted by case 37): `simulator`, `multipath`,
`mobility`, `energy`, `discovery`, `intent`, `services`.

Flagged amendments to accepted batteries (each citing the frozen
W026/W029/W030 → W033 dependency edges; the W027/W029/W030/W031
precedent):

- `tools/telemetry_selftest.py` case_19: `agent` added to the
  sanctioned-consumer set, pinned to `telemetry.model` +
  `telemetry.store`.
- `tools/upgrade_selftest.py` case_33: `agent` added to the
  reverse-import exemptions.
- `tools/management_selftest.py` case_29: `agent` added to the
  reverse-import exclusions.

## Local verification evidence

- `python3 tools/agent_selftest.py` — **PASS 45/45**, including the
  embedded W032 matrix (136/136 CONFORMANT, digest
  `sha256:d8514c04…`, matching the accepted suite) and the real
  IPv6-loopback data path.
- Full local battery: all 35 tools pass in their sanctioned contexts
  (management/simulator PR-delta cases evaluate on this branch
  context as designed).
- mypy `--strict --follow-imports=silent` clean over the agent files.

## Out of scope (unchanged)

- No W034+ work; no modification of frozen architecture, the DAG,
  ACR-003, or OAQ-001; no new access technologies beyond the
  registered registry entries; no real radio/network hardware beyond
  the Linux loopback; no external-network interop claims (external
  evidence remains a separately-reported class).
