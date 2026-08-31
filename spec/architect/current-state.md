# ADCOS Current State

**Persistent Architect snapshot — reconciled after the DEC-0052 atomic handoff and the commercial roadmap reconciliation (LEDGER-RECON-005).**

## Repository

- Repository: `github.com/pectoraux/ADCOS`
- Current `main`: `bb964a1bd94176fdc55f6870ffcdaf75445cc657` (tree-clean; PR #101 merged DEC-0051 ratification, PR #103 merged DEC-0052 atomic handoff + DEC-0053 single-Architect authority, and the W041 implementation-directive docs commit; the persistent state and the active WORK-041-CORE-001 baseline are reconciled to this mainline by LEDGER-RECON-005)
- Architecture version: `1.0` (`spec/architecture.md`)
- Protocol version: `1.0` (`spec/schemas/protocol.json`)

## Permanent mission

`spec/mission.md` is the permanent Mission Authority. It is the stable objective for ADCOS and is not changed through ordinary architecture ACRs.

## Authority

GitHub/repository state is the persistent Architect. Chat is not an authority source. Durable mission, architecture snapshots, locks, accepted ACRs, dependency graph, Work Item contracts, persistent decisions, experience/learning records, accepted precedents, verification evidence, documentation, and history follow `spec/architect/authority-order.md`.

## Execution state

- Active Work Item: `WORK-041`
- Execution mode: `implementing`
- Active authorization: `WORK-041-CORE-001` (DEC-0052), baseline `bb964a1bd94176fdc55f6870ffcdaf75445cc657` (atomic handoff from WORK-040-CORRECTION-001; baseline reconciled to the current mainline by LEDGER-RECON-005)
- W041 status: `active` — implements the ACR-005 NetworkPath/platform boundary (DEC-0047)
- W040 status: `in-review` on PR `#48` (round 1 verdict: CHANGES_REQUIRED, DEC-0046). The W040 correction authorization `WORK-040-CORRECTION-001` was superseded by DEC-0052 (atomic handoff); W040 is **not accepted** (lifecycle stays `in-review`, `acceptance_decision: null`).
- W040 implementation head: `ee9b356020b6450d85837f60e60c41d08f0ec09a`
- W040 original baseline: `1669ae9a396838b72ba461c846b98e84478ab24f`
- Correction-cycle handoff: `docs/WORK-040-correction-handoff.md`
- W041 implementation handoff: `docs/WORK-041-handoff.md`
- The active authorization is scoped to WORK-041 only and does not authorize W042/W043/W048 or any commercial-core/payment implementation.

## W040 review disposition

W040 remains **CHANGES_REQUIRED**. The current repository-local authorization permits only the Architect-requested correction cycle:

1. obtain and prove a real-device participant for criterion 1;
2. obtain and prove a defensible physical 5G access path for criterion 2, if actually available;
3. preserve the already demonstrated non-cellular, relay/backhaul, failover, and operational evidence;
4. preserve all authority, adapter-boundary, provenance, anti-promotion, and architecture/mission governance invariants.

A software rehearsal cannot close a physical criterion by inference.

## Accepted Work Items

`WORK-001` through `WORK-039` are Architect-accepted and merged.

## Planned / gated Work Items

- `WORK-040`: correction authorization `WORK-040-CORRECTION-001` superseded by DEC-0052 (atomic handoff to W041). W040 remains an independent physical validation track — `in-review`, **not accepted**; EVID-007 (PARTIAL) and EVID-008 (NOT-TESTABLE) remain OPEN and W040-owned. The correction cycle may resume later under a `type: evidence-continuation` authorization once physical evidence is available.
- `WORK-041`: contract recorded under ACR-005 (tracking issue #68); **active authorized implementation track** under `WORK-041-CORE-001` (DEC-0052). Implements the ACR-005 NetworkPath/platform boundary. W040 was decoupled as a non-blocking prerequisite by DEC-0051; W041 is DAG-ready and active.
- `WORK-042`: READY-CANDIDATE contract recorded under ACR-006 (tracking issue #69, `spec/architect/work-items/WORK-042.md`); execution not authorized, and depends on W041 where its interfaces are consumed.
- `WORK-043`: retired from commercial use and left unassigned (LEDGER-RECON-005); the commercial-era "W043 EconomicAllocation" label is superseded by W053.
- Commercial chain (resequenced by LEDGER-RECON-005): `WORK-051` CommercialCore (issue #83) → `WORK-052` UsageLedger (issue #84) → `WORK-053` EconomicAllocation (issue #85) — ready-candidates, unauthorized. `WORK-044`–`WORK-050` (issues #88–#92, #98, #96) remain ready-candidates, unauthorized; the duplicate W049 definition is resolved (issue #98 canonical, issue #95 superseded, discoverable).
- `WORK-044+`: the canonical commercial dependency model is `docs/roadmap/commercial-dependency-model.md` (W041–W053 decomposition, explicit dependency graph, W040 as physical validation / evidence track — advisory, not a prerequisite, superseded-label history). Not authorized; each Work Item must still be established and authorized through the mission/learning/change-control process.
- Superseded governance threads pending disposition: PR #100 (W041=CommercialCore contract reconciliation — the opposite of the DEC-0052 binding) and PR #102 (W040→W041 handoff analysis — implemented by merged PR #103).

## Architecture Change Requests

- `ACR-004` — Connectivity Commerce Plane — `SUPERSEDED` by accepted `ACR-009`; PR #49 remains historical/proposed evidence only and is not an active architecture authority.
- `ACR-005` — First-Class Network Path and Platform Boundary — **ACCEPTED**, DEC-0047, proposal merged by PR #64.
- `ACR-006` — Event-Driven Platform Integration and Journal-First Recovery — **ACCEPTED**, DEC-0048, proposal merged by PR #64.
- `ACR-007` — Mission-Immutable, Architecture-Evolvable Governance — **ACCEPTED**, DEC-0049, merged by PR #67.
- `ACR-009` — Commercial Connectivity Control Plane — **ACCEPTED**, DEC-0050, proposal merged by PR #82; durable acceptance is recorded by PR #86.

ACR-005 and ACR-006 define reusable architectural direction without independently authorizing implementation. ACR-007 defines the mission/architecture distinction and durable learning loop. ACR-009 defines the accepted commercial control-plane architecture; none of these ACRs independently authorizes Work Item implementation.

## Experience and learning

The durable learning registry is `spec/experience/lessons.yaml` and its process is defined in `spec/experience/README.md`.

Seeded lessons include:

- integrity is not provenance;
- physical evidence must prove the physical boundary;
- successful output counts can hide missing mechanisms;
- ephemeral LLM context is not durable architecture memory;
- architecture should evolve when evidence shows the current hypothesis needs improvement.

Experience records are evidence for Architect reasoning. They cannot directly amend architecture; accepted ACRs remain the architectural change mechanism.

## Open external evidence obligations

Tracked in `spec/architect/evidence-obligations.yaml` (statuses PASS / PARTIAL / NOT-TESTABLE / OPEN; software PASS never silently becomes physical PASS).

| ID | Work Item | Criterion | Class | Status |
|---|---|---|---|---|
| EVID-002 | WORK-020 | physical SDR-based lab topology (criterion 4) | PHYSICAL | **OPEN** (SDR-LAB RESULT: BLOCKED) |
| EVID-003 | WORK-034 | real Raspberry Pi / edge hardware track | PHYSICAL | **OPEN** |
| EVID-004 | WORK-035 | physical Android device track; physical transport handover | PHYSICAL | **OPEN** |
| EVID-005 | WORK-036 | physical appliance deployment at a real site | PHYSICAL | **OPEN** |
| EVID-006 | WORK-037 | real 5G interoperability lab (class C) | PHYSICAL | **OPEN** |
| EVID-007 | WORK-040 | real users/devices participate (criterion 1) | PHYSICAL | **PARTIAL** (software-class participants; correction cycle WORK-040-CORRECTION-001 per DEC-0046) |
| EVID-008 | WORK-040 | real 5G access path (criterion 2) | PHYSICAL | **NOT-TESTABLE** on the pilot host (correction cycle WORK-040-CORRECTION-001 per DEC-0046) |

(EVID-001, the WORK-019 Open5GS interop gate, is closed PASS.)

## Persistent Architect package

The persistent Architect package was established by PR #60 and reconciled by PR #61. Its core rule is that implementation authorization must be repository-local and inherited from the base; an in-review ledger entry is descriptive only and never authorizes implementation.

## Architectural improvement records

ACR-005/006 and the ACR-007 mission/evolution record provide durable architectural direction and learning governance. ACR-009 is now an accepted commercial architecture layer under DEC-0050. Previous snapshots and decisions remain historical and are never rewritten.

## Resume rule

A fresh Architect reads `spec/mission.md`, this file, `spec/architect/authority-order.md`, `execution-state.yaml`, `execution-ledger.yaml`, relevant experience records, decisions, authorizations, and the active Work Item handoff before acting. No prior chat is required or authoritative.
