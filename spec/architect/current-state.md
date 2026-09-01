# ADCOS Current State

**Persistent Architect snapshot — reconciled after the atomic WORK-042 acceptance → W051 activation (DEC-0057 + DEC-0058, LEDGER-RECON-007); ACR-011 is accepted (DEC-0056) and the commercial chain head WORK-051 is the active implementation track.**

## Repository

- Repository: `github.com/pectoraux/ADCOS`
- Current `main`: `fe6e6e35a49cb2113315d0ec1569f7e93a3cf200` (tree-clean; PR #110 merged the WORK-042 implementation at head `708a432`, CI run 33444952103 SUCCESS; PR #111 merged the accepted ACR-011 registry extension; PR #115 persisted the DEC-0056 acceptance record). The persistent-state snapshot baseline and the active `WORK-051-CORE-001` authorization baseline are reconciled to this mainline by LEDGER-RECON-007 (the DEC-0057/DEC-0058 atomic transition).
- Architecture version: `1.0` (`spec/architecture.md`)
- Protocol version: `1.0` (`spec/schemas/protocol.json`)

## Permanent mission

`spec/mission.md` is the permanent Mission Authority. It is the stable objective for ADCOS and is not changed through ordinary architecture ACRs.

## Authority

GitHub/repository state is the persistent Architect. Chat is not an authority source. Durable mission, architecture snapshots, locks, accepted ACRs, dependency graph, Work Item contracts, persistent decisions, experience/learning records, accepted precedents, verification evidence, documentation, and history follow `spec/architect/authority-order.md`.

## Execution state

- Active Work Item: `WORK-051`
- Execution mode: `implementing`
- Active authorization: `WORK-051-CORE-001` (DEC-0058), baseline `fe6e6e35a49cb2113315d0ec1569f7e93a3cf200` (atomic activation after the W042 acceptance; the persistent state is reconciled to this mainline by LEDGER-RECON-007)
- W042 status: `accepted-merged` — the ACR-006 event-driven platform integration and journal-first recovery implementation was delivered on PR `#110` (head `708a432`, merge `207d70e`, authoritative CI run 33444952103 SUCCESS with the platform battery step passing 32/32, merged 2026-08-31T22:54:17Z) under `WORK-042-CORE-001` and is accepted by **DEC-0057** (review round 1 on the exact merged head, no corrections required) with SOFTWARE-class evidence only; the execution-ledger entry records lifecycle `accepted-merged` with `acceptance_decision: DEC-0057` and `reviewed_sha: 708a432`; the `WORK-042-CORE-001` authorization is superseded (DEC-0058, scope and provenance preserved in the record)
- W051 status: `active` — the commercial chain head (CommercialCore, ACR-009, tracking issue #83; frozen-registry dependencies none) is the single active implementation track under `WORK-051-CORE-001` (DEC-0058): the canonical commercial state lifecycle (ConnectivityIntent through Settled with compensating states/events), referencing — never owning — logical session, NetworkPath, and delivery evidence identities; its battery and delivery arrive on a future implementation PR that inherits the authorization byte-identically from main
- W040 status: `in-review` on PR `#48` (round 1 verdict: CHANGES_REQUIRED, DEC-0046). The W040 correction authorization `WORK-040-CORRECTION-001` was superseded by DEC-0052 (atomic handoff); W040 is **not accepted** (lifecycle stays `in-review`, `acceptance_decision: null`).
- W040 implementation head: `ee9b356020b6450d85837f60e60c41d08f0ec09a`
- W040 original baseline: `1669ae9a396838b72ba461c846b98e84478ab24f`
- Correction-cycle handoff: `docs/WORK-040-correction-handoff.md`
- W041 implementation handoff: `docs/WORK-041-handoff.md` (governance + implementation levels)
- W042 implementation handoff: `docs/WORK-042-handoff.md` (governance level; the implementation-level handoff appended on the delivery, merged with PR #110)
- W051 implementation handoff: `docs/WORK-051-handoff.md` (governance level; the implementation-level handoff will live on the W051 delivery branch, per the W041/W042 precedent)
- The active authorization is scoped to WORK-051 only and does not authorize WORK-043 (retired), WORK-044–WORK-050, the rest of the commercial chain (W052/W053), or any payment-rails/custody/KYC/jurisdiction/discovery/SDK implementation.

## W040 review disposition

W040 remains **CHANGES_REQUIRED**. The current repository-local authorization permits only the Architect-requested correction cycle:

1. obtain and prove a real-device participant for criterion 1;
2. obtain and prove a defensible physical 5G access path for criterion 2, if actually available;
3. preserve the already demonstrated non-cellular, relay/backhaul, failover, and operational evidence;
4. preserve all authority, adapter-boundary, provenance, anti-promotion, and architecture/mission governance invariants.

A software rehearsal cannot close a physical criterion by inference.

## Accepted Work Items

`WORK-001` through `WORK-039` are Architect-accepted and merged (chat-era migration). `WORK-041` is Architect-accepted and merged (DEC-0054; PR #107). `WORK-042` is Architect-accepted and merged (DEC-0057; PR #110). `WORK-040` is **not** accepted (in-review).

## Planned / gated Work Items

- `WORK-040`: correction authorization `WORK-040-CORRECTION-001` superseded by DEC-0052 (atomic handoff to W041). W040 remains an independent physical validation track — `in-review`, **not accepted**; EVID-007 (PARTIAL) and EVID-008 (NOT-TESTABLE) remain OPEN and W040-owned. The correction cycle may resume later under a `type: evidence-continuation` authorization once physical evidence is available.
- `WORK-041`: **accepted-merged** (DEC-0054; PR #107 head `4ce5a42`, merge `96db8aa`, CI run 33426900730 SUCCESS). Registered in the frozen registry as the first Phase 9 (Governed architecture evolution) item by the DEC-0054/DEC-0055 transition — `spec/work-items.md` and `spec/dependency-graph.md` carry its registration (dependencies WORK-016/WORK-018/WORK-033/WORK-034; expected Work Item count 41; WORK-001–WORK-040 byte-identical), and its execution-ledger entry is lifecycle `accepted-merged`. The `WORK-041-CORE-001` authorization is superseded (DEC-0055) and preserved as durable provenance. Its battery `tools/networkpath_selftest.py` is wired into CI.
- `WORK-042`: **accepted-merged** (DEC-0057; PR #110 head `708a432`, merge `207d70e`, CI run 33444952103 SUCCESS). Delivered under `WORK-042-CORE-001` (DEC-0055) inside the authorized scope (`platform/`, `tools/platform_selftest.py` 32/32 in CI, the two W042 docs, one additive CI step); registered in the frozen backlog (Phase 9) and the dependency graph by the accepted ACR-011. The `WORK-042-CORE-001` authorization is superseded (DEC-0058) and preserved as durable provenance. Its battery `tools/platform_selftest.py` is wired into CI. Its handoff is `docs/WORK-042-handoff.md` and its evidence is `docs/WORK-042-evidence.md` (SOFTWARE-class only; no PHYSICAL claim).
- `WORK-043`: retired from commercial use and left unassigned (LEDGER-RECON-005); the commercial-era "W043 EconomicAllocation" label is superseded by W053. ACR-011 represents the retirement as an explicit machine-checked retired slot (`RETIRED_WORK_ITEM_IDS` in `tools/spec_check.py`): the only sanctioned gap in the WORK-NNN sequence, never reused or renumbered.
- Commercial chain (resequenced by LEDGER-RECON-005): `WORK-051` CommercialCore (issue #83) is the **active authorized** chain head under `WORK-051-CORE-001` (DEC-0058, baseline `fe6e6e3`) — the single active implementation track; `WORK-052` UsageLedger (issue #84) and `WORK-053` EconomicAllocation (issue #85) remain ready-candidates, unauthorized (hard-gated on W051). `WORK-044`–`WORK-050` (issues #88–#92, #98, #96) remain ready-candidates, unauthorized (hard-gated on the W051 chain; the duplicate W049 definition is resolved: issue #98 canonical, issue #95 superseded, discoverable). ACR-011 (accepted) registered all of them in the frozen registry (Phase 10) as `registered`-only ledger entries with authorization "none" — registration is representation, never authorization (review-protocol §3.1; ARCH-03/ARCH-08); only WORK-051 is activated, by DEC-0058.
- `WORK-044+`: the canonical commercial dependency model is `docs/roadmap/commercial-dependency-model.md` (W041–W053 decomposition, explicit dependency graph, W040 as physical validation / evidence track — advisory, not a prerequisite, superseded-label history). Not authorized; each Work Item must still be established and authorized through the mission/learning/change-control process.
- Superseded governance threads pending disposition: PR #100 (W041=CommercialCore contract reconciliation — the opposite of the DEC-0052 binding), PR #102 (W040→W041 handoff analysis — implemented by merged PR #103), and PR #108 (ACR-010 frozen Work Item registry extension — its scope was applied directly by the DEC-0054/DEC-0055 transition, LEDGER-RECON-006).

## Architecture Change Requests

- `ACR-004` — Connectivity Commerce Plane — `SUPERSEDED` by accepted `ACR-009`; PR #49 remains historical/proposed evidence only and is not an active architecture authority.
- `ACR-005` — First-Class Network Path and Platform Boundary — **ACCEPTED**, DEC-0047, proposal merged by PR #64.
- `ACR-006` — Event-Driven Platform Integration and Journal-First Recovery — **ACCEPTED**, DEC-0048, proposal merged by PR #64.
- `ACR-007` — Mission-Immutable, Architecture-Evolvable Governance — **ACCEPTED**, DEC-0049, merged by PR #67.
- `ACR-009` — Commercial Connectivity Control Plane — **ACCEPTED**, DEC-0050, proposal merged by PR #82; durable acceptance is recorded by PR #86.
- `ACR-010` — Work Item Registry Extension Beyond WORK-040 — **SUPERSEDED** (never accepted through the ACR process): proposed on PR #108 to register WORK-041 and move the expected Work Item count 40 → 41; the DEC-0054/DEC-0055 transition applied that scope directly (LEDGER-RECON-006) as the mechanical prerequisite of recording the W041 acceptance, so PR #108 remains historical proposal evidence.
- `ACR-011` — Commercial Phase Registry Extension — **ACCEPTED**, DEC-0056 (proposal merged by PR #111 at `810374e`; the acceptance record persisted by PR #115): the frozen Work Item registry extends from 41 to 52 registered items (`WORK-042` in Phase 9 plus the canonical commercial phase `WORK-044..WORK-053` in Phase 10, with `WORK-043` represented as the machine-checked retired slot), the WORK-042 delivery ledger entry, ten registered-only commercial ledger entries, and the synchronized checker expectations. No acceptance, no authorization, and no architecture-version change was performed by the proposal itself; the machine-checked contradiction it resolved is documented in `docs/governance/ACR-011-commercial-phase-registry-reconciliation.md`.

ACR-005 and ACR-006 define reusable architectural direction without independently authorizing implementation. ACR-007 defines the mission/architecture distinction and durable learning loop. ACR-009 defines the accepted commercial control-plane architecture; none of these ACRs independently authorizes Work Item implementation. ACR-011 is accepted: it made the delivered WORK-042 and the canonical commercial phase machine-representable in the frozen registry without creating any authorization, accepting any Work Item, or altering any accepted architecture semantic; the WORK-042 acceptance (DEC-0057) and the WORK-051 activation (DEC-0058) are the separate repository-local decisions recorded in the DEC-0057/DEC-0058 transition.

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
