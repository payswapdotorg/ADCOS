# WORK-034 — Raspberry Pi / low-power gateway: implementation handoff

**IMPLEMENTED** — PR submitted on branch `work-034-raspberry-pi-gateway`
(created from the merge commit of WORK-020). The implementer does not
merge its own PR (workflow §6); this handoff is the review basis.

## Evidence classification (two tracks, the WORK-020 governance pattern)

| Track | Status | Basis |
| --- | --- | --- |
| Architecture conformance | PASS (battery cases 40-48) | composition over the unchanged WORK-033 agent; frozen-surface and structural audits |
| software-constrained | PASS (battery cases 1-39) | deterministic emulated constrained operation: board-profile capacity envelopes, pressure ladders, admission matrices, real `/proc` hardware source reads |
| physical-hardware | **OPEN** | no physical board is available in this environment; `HARDWARE_EVIDENCE_STATUS["physical-hardware"] == "open"` is frozen DATA and the battery asserts it byte-for-byte (case_06) |

The frozen `spec/` contract's "hardware integration" required
verification is therefore **not claimed as satisfied**. QEMU/ARM64
and container resource controls are valid *engineering* verification
of the software track; they never become a physical-hardware PASS
(the WORK-020 physical-SDR anti-faking rule, applied to boards).

## What was built

`edge/` — the Pi-class edge layer over the accepted Linux agent:

| File | Content |
| --- | --- |
| `edge/errors.py` | typed error model (frozen reason vocabulary) |
| `edge/model.py` | frozen vocabularies (pressure domains/levels, posture, priorities, verdicts, event kinds) + value records (readings, events, outcomes, run results, forward records) with canonical bytes/digests |
| `edge/hardware.py` | frozen Pi-class board profiles (DATA), `HardwareInventory`, `StaticHardwareSource` (verification seam), `LinuxHardwareSource` (real `/proc/meminfo`, `/proc/cpuinfo`, `shutil.disk_usage`; board-declared, capacity-capped, fail-closed), `FailingHardwareSource`, `HARDWARE_EVIDENCE_STATUS` (anti-faking disclosure) |
| `edge/pressure.py` | frozen 70/90 watermark ladder, frozen CPU/memory/storage charge tables (complete over the agent's command kinds), `ResourceBudget`, `PressureLedger` (integer math, epoch replenish, reclaim/compact), `compute_pressure` |
| `edge/scheduler.py` | frozen priority classification, admission matrix (level × priority), CPU epoch-budget gate (protected bypasses, still charged), offline gate; `decide_command` pure |
| `edge/coexistence.py` | frozen access classes, technology→class registry DATA, deployment access plan (e.g. `wwan0` → cellular), `AccessView` join over live agent adapters, deterministic selection (preference → health → capacity → name), connectivity posture (connected/degraded/offline) |
| `edge/gateway.py` | `EdgeGateway` (owns one `AgentRuntime`), `GatewayClaim`/`GatewayTable` (evidence-scoped, TTL'd, fail-closed; WORK-023 evidence + relay vocabularies as DATA), forwarding through ordinary sessions, bounded TTL'd defer queue with typed shedding and drain, pressure telemetry (WORK-026 observations), `run_edge_headless`/`verify_edge_replay` |

`tools/edge_selftest.py` — the 48-case battery (below). CI step
"Run Raspberry Pi edge gateway tests" appended after the agent step
(work-item order).

## Coverage against the frozen contract

- **low-resource operation** — cases 7-11 (ladder/ledger/reading
  math), 12-15 (admission + budget gates), 27 (queue bounds),
  28-30 (pressure-driven deferral, recovery, events, telemetry);
  constrained envelopes come from the board profiles (case 01) and
  the real `/proc` source (case 04).
- **Ethernet/Wi-Fi/cellular adapters can coexist** — cases 16-20
  (classification/selection/posture), 22 (live three-class
  coexistence, all adapters OPEN+HEALTHY simultaneously), 23 (three
  sessions bound concurrently, one per access class — the
  discriminator), 24 (ethernet loss → degraded posture → wifi
  failover).
- **device can operate as relay/gateway** — cases 31-35: evidenced
  claims, forwarding with byte-identical session delivery, fail-closed
  lookup (unknown/expired/remote-claim — never upgraded), replacement,
  session-failure wrapping.
- **offline and degraded operation** — cases 14 (offline gate
  unit), 24 (degraded failover), 25 (offline defer + drain on
  access return), 26 (TTL expiry sheds with typed reason).
- **hardware integration (required verification)** — OPEN, per the
  two-track table above; case 06 pins the disclosure.
- **inexpensive edge hardware can act as ADCOS infrastructure
  (DoD)** — the software track is delivered; the DoD's physical
  half awaits hardware, exactly as the physical-SDR half of W020
  does.

## Composition, not re-implementation

- `agent/` is byte-identical to the W033 merge; the edge layer never
  patches, wraps, or subclasses `AgentRuntime` (case 40). Executed
  commands go through the unchanged `AgentRuntime.execute`; the
  scheduler only decides *whether/when*.
- No new session/routing/resource/policy semantics: no
  `PolicyDecision`/`RouteDecision` construction anywhere in `edge/`;
  gateway forwarding rides ordinary W012/W017 session datagrams.
- No second authority: the edge event journal records scheduling
  and coexistence DECISIONS; the agent event log remains the record
  of authority mutations.
- No access-technology duplication: the only adapters import is the
  WORK-023 mesh vocabulary (`EvidenceSourceClass`, `RelayTechnology`)
  used as DATA (case 41 bans every other adapters subfamily).
- W027 boundary: energy-driven survival policies stay in `energy/`
  (a forbidden import root for this family); the edge pressure model
  is resource-driven command scheduling, deliberately disjoint.

## Determinism

- Same scenario → identical `edge_digest` / agent event digest /
  content digest (case 36); fresh subprocesses under PYTHONHASHSEED
  0/1/7919/None produce identical digests (case 37);
  `verify_edge_replay` accepts a match and rejects divergence
  (case 38); all value round-trips are byte-identical (case 39).
- No wall-clock reads anywhere in `edge/` (case 41); all instants
  come from the injected agent clock.

## Frozen-surface discipline

- `spec/` is byte-identical to `origin/main` (case 46).
- The PR delta is exactly: `edge/`, `tools/edge_selftest.py`,
  `tools/agent_selftest.py` (allowlist amendment), this doc, and the
  CI step (case 47).
- The `edge.__all__` API surface is frozen (case 45); the charge
  tables and admission matrix are frozen DATA with completeness
  checks against `agent.CommandKind` (case 09).

## Import discipline

Allowed roots for the edge family: `protocol`, `agent`,
`adapters.mesh` (vocabulary DATA only), `telemetry`, stdlib
(`hashlib`, `dataclasses`, `datetime` (arithmetic only),
`pathlib`/`shutil` (hardware.py only), `typing`).
Forbidden: every other family root, plus `os/socket/time/random/
secrets/uuid/subprocess/urllib/http/ssl/asyncio` (case 41).

**Flagged amendment to an accepted battery:** `tools/agent_selftest.py`
case_40's PR-delta allowlist gains `tools/edge_selftest.py` and
`docs/WORK-034-handoff.md`, citing the W033 → W034 DAG edge (the
edge work item builds directly on the agent battery's subject) — the
same narrowing-amendment precedent W033 itself set for
W026/W029/W030.

## Local verification evidence

```
$ python3 tools/edge_selftest.py
Result: PASS (48/48 cases passed)

$ python3 tools/agent_selftest.py
Result: PASS (45/45 cases passed)

$ python3 tools/spec_check.py
spec-check: PASS (9/9 checks)
```

(Exact counts recorded at PR time; see the PR body for the CI run.)

## Constrained-environment guidance (software track)

The deterministic in-repo evidence uses `StaticHardwareSource`
capacity envelopes. To reproduce the same battery against a real
constrained environment: run the repository's battery under
`qemu-aarch64-static` (or an ARM64 container) with cgroup
`memory.max`/`cpu.max` limits — `LinuxHardwareSource` reads the
board-declared envelope from the real `/proc`, so a declared
`raspberry-pi-zero-2w` profile on a larger host reports the board's
512 MiB envelope (honest emulation, case 04). This remains
software-track evidence; the physical-hardware track stays OPEN.

## Out of scope (unchanged)

- frozen protocol semantics, `spec/` (byte-identical)
- access/backhaul/RAN/Wi-Fi/distributed-core adapter internals
  (W020-W024)
- energy survival policies (W027)
- W035+ behavior
- physical board bring-up (evidence track OPEN)
