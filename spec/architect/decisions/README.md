# ADCOS Decision Registry

## Status

**ACTIVE — Persistent Governance Authority**

Durable Architect decision records live in this directory as `DEC-NNNN-<short-slug>.yaml`, numbered sequentially and stably. Schema: `spec/architect/decision-record-template.md`. Verified by `tools/spec_check.py` (ARCH-04).

Migration convention: records DEC-0001 … DEC-0039 are the acceptances of WORK-001 … WORK-039, reconstructed from repository-durable evidence. Unknown chat-era detail is not invented. Records DEC-0040 … DEC-0060 are corrective/governance/architecture/acceptance decisions whose requirements shape future work.

## Registry

| ID | Type | Work Item | Verdict | Standing | Subject |
|---|---|---|---|---|---|
| DEC-0001 | acceptance | WORK-001 | ACCEPTED | ACCEPTED | Specification/governance foundation |
| DEC-0002 | acceptance | WORK-002 | ACCEPTED | ACCEPTED | Core protocol vocabulary and registry model |
| DEC-0003 | acceptance | WORK-003 | ACCEPTED | ACCEPTED | Versioned protocol envelope and serialization |
| DEC-0004 | acceptance | WORK-004 | ACCEPTED | ACCEPTED | Cryptographic node identity |
| DEC-0005 | acceptance | WORK-005 | ACCEPTED | ACCEPTED | Capability statements and negotiation |
| DEC-0006 | acceptance | WORK-006 | ACCEPTED | ACCEPTED | Peer discovery |
| DEC-0007 | acceptance | WORK-007 | ACCEPTED | ACCEPTED | Evidence-aware topology graph |
| DEC-0008 | acceptance | WORK-008 | ACCEPTED | ACCEPTED | Resource model and measurements |
| DEC-0009 | acceptance | WORK-009 | ACCEPTED | ACCEPTED | Intent and QoS model |
| DEC-0010 | acceptance | WORK-010 | ACCEPTED | ACCEPTED | Policy engine |
| DEC-0011 | acceptance | WORK-011 | ACCEPTED | ACCEPTED | Path computation and routing engine |
| DEC-0012 | acceptance | WORK-012 | ACCEPTED | ACCEPTED | Logical sessions |
| DEC-0013 | acceptance | WORK-013 | ACCEPTED | ACCEPTED | Multipath session manager |
| DEC-0014 | acceptance | WORK-014 | ACCEPTED | ACCEPTED | Mobility and handover manager |
| DEC-0015 | acceptance | WORK-015 | ACCEPTED | ACCEPTED | Federation protocol |
| DEC-0016 | acceptance | WORK-016 | ACCEPTED | ACCEPTED | Adapter SDK/runtime |
| DEC-0017 | acceptance | WORK-017 | ACCEPTED | ACCEPTED | Secure transport profiles |
| DEC-0018 | acceptance | WORK-018 | ACCEPTED | ACCEPTED | IPv6 and IP integration boundary |
| DEC-0019 | acceptance | WORK-019 | ACCEPTED | ACCEPTED | 5G Core integration adapter |
| DEC-0020 | acceptance | WORK-020 | ACCEPTED | ACCEPTED | 5G RAN/gNB adapter |
| DEC-0021 | acceptance | WORK-021 | ACCEPTED | ACCEPTED | Wi-Fi/non-3GPP access adapter |
| DEC-0022 | acceptance | WORK-022 | ACCEPTED | ACCEPTED | Backhaul adapter family |
| DEC-0023 | acceptance | WORK-023 | ACCEPTED | ACCEPTED | Mesh, IAB, relay, store-and-forward |
| DEC-0024 | acceptance | WORK-024 | ACCEPTED | ACCEPTED | Distributed core / local breakout / UPF |
| DEC-0025 | acceptance | WORK-025 | ACCEPTED | ACCEPTED | Service registry and edge compute |
| DEC-0026 | acceptance | WORK-026 | ACCEPTED | ACCEPTED | Telemetry and observability |
| DEC-0027 | acceptance | WORK-027 | ACCEPTED | ACCEPTED | Energy-aware control and resilience |
| DEC-0028 | acceptance | WORK-028 | ACCEPTED | ACCEPTED | Threat model and security hardening |
| DEC-0029 | acceptance | WORK-029 | ACCEPTED | ACCEPTED | Upgrade, rollback, compatibility manager |
| DEC-0030 | acceptance | WORK-030 | ACCEPTED | ACCEPTED | Management API |
| DEC-0031 | acceptance | WORK-031 | ACCEPTED | ACCEPTED | Network and behavior simulator |
| DEC-0032 | acceptance | WORK-032 | ACCEPTED | ACCEPTED | Conformance suite |
| DEC-0033 | acceptance | WORK-033 | ACCEPTED | ACCEPTED | Linux Agent |
| DEC-0034 | acceptance | WORK-034 | ACCEPTED | ACCEPTED | Raspberry Pi / low-power gateway |
| DEC-0035 | acceptance | WORK-035 | ACCEPTED | ACCEPTED | Android/mobile Agent |
| DEC-0036 | acceptance | WORK-036 | ACCEPTED | ACCEPTED | Network-in-a-Box |
| DEC-0037 | acceptance | WORK-037 | ACCEPTED | ACCEPTED | Open RAN/Core interop profile |
| DEC-0038 | acceptance | WORK-038 | ACCEPTED | ACCEPTED | Future IMT/6G adapter profile |
| DEC-0039 | acceptance | WORK-039 | ACCEPTED | ACCEPTED | Federation at scale |
| DEC-0040 | correction | WORK-035 | CHANGES_REQUIRED | SUPERSEDED | Physical evidence v1 |
| DEC-0041 | correction | WORK-035 | CHANGES_REQUIRED | SUPERSEDED | Physical evidence v2 |
| DEC-0042 | correction | WORK-035 | CHANGES_REQUIRED | CHANGES_REQUIRED | Physical evidence v6: handover gate remains OPEN |
| DEC-0043 | correction | WORK-039 | CHANGES_REQUIRED | SUPERSEDED | Multi-hop relay blocker |
| DEC-0044 | governance | null | CHANGES_REQUIRED | CHANGES_REQUIRED | Persistent-Architect mandate |
| DEC-0045 | governance | null | CHANGES_REQUIRED | CHANGES_REQUIRED | PA-001: in-review is never authorization |
| DEC-0046 | correction | WORK-040 | CHANGES_REQUIRED | CHANGES_REQUIRED | W040 round-1 correction authorization |
| DEC-0047 | architecture | null | ACCEPTED | ACCEPTED | ACR-005: first-class network path/platform boundary |
| DEC-0048 | architecture | null | ACCEPTED | ACCEPTED | ACR-006: event-driven platform/journal-first recovery |
| DEC-0049 | architecture | null | ACCEPTED | ACCEPTED | ACR-007: mission-immutable, architecture-evolvable governance |
| DEC-0050 | architecture | null | ACCEPTED | ACCEPTED | ACR-009: commercial connectivity control plane |
| DEC-0051 | governance | null | ACCEPTED | ACCEPTED | Work Item dependency decoupling (W040 decoupled as non-blocking prerequisite for downstream software work) |
| DEC-0052 | governance | WORK-040 | ACCEPTED | ACCEPTED | Atomic W040→W041 execution handoff (supersede WORK-040-CORRECTION-001; activate WORK-041-CORE-001; preserve W040 evidence ownership) |
| DEC-0053 | governance | null | ACCEPTED | ACCEPTED | Single-Architect review and merge authority |
| DEC-0054 | acceptance | WORK-041 | ACCEPTED | ACCEPTED | W041 acceptance: first-class network path/platform integration (PR #107, head 4ce5a42, merge 96db8aa, CI 33426900730) |
| DEC-0055 | governance | WORK-041 | ACCEPTED | ACCEPTED | Atomic W041 acceptance → W042 activation (supersede WORK-041-CORE-001; activate WORK-042-CORE-001; registry extension applied — ACR-010/PR #108 superseded; W040 evidence ownership preserved) |
| DEC-0056 | governance | null | ACCEPTED | ACCEPTED | ACR-011 acceptance: extend Work Item registry through canonical commercial phase |
| DEC-0057 | acceptance | WORK-042 | ACCEPTED | ACCEPTED | W042 acceptance: event-driven platform integration + journal-first recovery (PR #110, head 708a432, merge 207d70e, CI 33444952103) |
| DEC-0058 | governance | WORK-042 | ACCEPTED | ACCEPTED | Atomic W042 acceptance → W051 activation (supersede WORK-042-CORE-001; activate WORK-051-CORE-001 CommercialCore chain head; LEDGER-RECON-007 baseline fe6e6e3; no registry change — ACR-011 already accepted; W040 evidence ownership preserved) |
| DEC-0059 | acceptance | WORK-051 | ACCEPTED | ACCEPTED | W051 acceptance: CommercialCore conformance completion (PR #145, head e247b4e, merge 41b3380, CI 33838171573; battery 38/38; atomic W051 acceptance → W052 activation) |
| DEC-0060 | governance | WORK-052 | ACCEPTED | ACCEPTED | W052 baseline reconciliation via LEDGER-RECON-009; no implementation, no scope change |
| DEC-0061 | governance | WORK-052 | ACCEPTED | ACCEPTED | W052 acceptance and atomic activation of WORK-053-CORE-001 |
| DEC-0063 | governance | WORK-053 | ACCEPTED | ACCEPTED | W053 acceptance and atomic activation of WORK-044-CORE-001; no W044 implementation included |
| DEC-0080 | governance | null | ACCEPTED | ACCEPTED | Canonical roadmap freeze, repository-only source of truth, and mainline-integrity fail-closed gate |
| DEC-0084 | governance | null | ACCEPTED | ACCEPTED | R1 governance reconciliation after the accepted R0 restoration (PR #8, merge a3391e8): reconciled roadmap, current-state, execution-state, and execution-ledger to the restored mainline; historical provenance preserved |
| DEC-0095 | governance | WORK-057 | ACCEPTED | SUPERSEDED | ACR-013 acceptance: post-snapshot gate-specific Work Item governance and activation of WORK-057-CORE-001 for R6 |
| DEC-0096 | correction | WORK-057 | CHANGES_REQUIRED | SUPERSEDED | W057 Round 1 adversarial review: adapter certification authority bypass and federation proposal self-acceptance |
| DEC-0097 | acceptance | WORK-057 | ACCEPTED | ACCEPTED | W057 Round 2 acceptance: P0 corrections verified; PR #23 head 58eced2 merged as a08ce85; WORK-057 authorization closed; R6 complete; R7 next unlocked but unactivated |
| DEC-0098 | governance | M001 | ACCEPTED | ACCEPTED | M001 activation: Architecture 1.1 Freeze authorized under M001-CORE-001 from baseline 40737a0 (PR #24 transition-package merge); ACR-014 proposed with the DEC-0098 approval path; roadmap 1.5 -> 1.6 |
| DEC-0099 | governance | M001 | ACCEPTED | ACCEPTED | M001 scope amendment + battery-mirror reconciliation: agent conformance mirror synced to accepted W055 total (163); marketplace stale WORK-047.yaml reference removed; era-superseded payment/eligibility/client batteries skip-with-disclosure behind CI precondition guards (re-baseline under the 1.1 M009/M014 commercial track) |
| DEC-0100 | acceptance | M001 | ACCEPTED | ACCEPTED | M001 acceptance: Architecture 1.1 Freeze accepted at PR #25 head 36bfd8e, merged as 80292c2; ACR-014 ACCEPTED; M001-CORE-001 closed; pre-acceptance repairs recorded (3e3ea3b: current_spec_check fail-closed aggregation + marker alignment, WORK-057 ledger projection appended, conformance case_63 frozen-authority mirror re-baselined to the acceptance merge); roadmap 1.6 -> 1.7 with M001 COMPLETE and R7 next unlocked but unactivated |
| DEC-0101 | governance | R7 | ACCEPTED | ACCEPTED | R7 activation + governance compression: one bounded R7 program authorization (R7-CORE-001, baseline 1e5c55f) with child work-item scopes M002-M014 per the R7 charter; per-child acceptance stays mandatory (DEC-0102+); Tech Lead empowered to decompose/dispatch/integrate without per-item pre-implementation ceremonies; stale state projections repaired; roadmap 1.7 -> 1.8 |

## Rules

1. IDs are never reused or renumbered; superseded records stay.
2. A rendered verdict is never edited; later records supersede earlier ones via `resolved_by` where applicable.
3. New records are added by the Architect in the same governance transition that they justify.
4. `tools/spec_check.py` ARCH-04 verifies unique IDs, filename consistency, acceptance SHA/ledger consistency, and reference resolution.
| DEC-0102 | acceptance | M002 | ACCEPTED | ACCEPTED | M002 acceptance: Connectivity Contract Core accepted at PR #26 head 0112943 (contracts/ canonical domain + 54/54 battery + evidence matrix + the authorization-aware consultation repairs), merged as 0ffdf47 after three reviewed CI-repair riders (case_42 echo-server latch race; the four PR-only batteries' consultation completion; imt/scale Pattern-B completion + latent type-crash fix); R7-CORE-001 stays active, child advances M002 -> M003; roadmap 1.8 -> 1.9 with M002 COMPLETE |
| DEC-0103 | acceptance | M003 | ACCEPTED | ACCEPTED | M003 acceptance: Offers and Provider Capability Exchange accepted at PR #27 head eace143 (offers/ provider-domain offer model with LOCK-118 provenance and bounded commitments; capabilities/discovery/marketplace harvest per the matrix; three disclosed battery evolutions + the new 49/49 offer battery), merged as 4090e03; R7-CORE-001 stays active, child advances M003 -> M004; roadmap 1.9 -> 2.0 with M003 COMPLETE; the offer battery is CI-wired by this acceptance (existence-guard pattern) |
| DEC-0113 | acceptance | M013 | ACCEPTED | ACCEPTED | M013 acceptance: Developer Connectivity API accepted at PR #28 head 69ef8de (developerapi/ harvested onto the canonical 1.1 authority: gateway re-bound to the accepted contracts domain, LOCK-114 opaque typed references, schema 2.0 with honest 1.x/0.8 retirement, 56/56 evolved battery), merged as 8f4d58a2; chain-independent child (does not move the current-child pointer); roadmap v2.0 records M013 COMPLETE; M010/M011/M012 become available downstream |
| DEC-0109 | acceptance | M009 | ACCEPTED | ACCEPTED | M009 acceptance: Usage and Commercial Reconciliation accepted at PR #29 head 5a807cd (usage/commercial/allocation/payment re-bound to the canonical contracts/ domain per LOCK-113; the DEC-0099-disclosed payment 44/44 and eligibility 46/46 honest re-baselines; battery evolutions usage 53/commercial 41/allocation 62; 393-line evidence matrix), merged as c985b88; chain child that does not move the current-child pointer (M004 stays current per DEC-0103, the M013 precedent); roadmap 2.0 -> 2.1 with M009 COMPLETE; the payment/eligibility CI precondition guards converted to direct runs by this acceptance (the M002 CI-wiring precedent) |
| DEC-0110 | acceptance | M010 | ACCEPTED | ACCEPTED | M010 acceptance: Vertical Proof — ShareNet accepted at PR #30 head d5be84e (the 8-step frozen flow harness on the accepted M002/M003/M013 authorities; 33/33 battery; LOCK-108 failover constraint preservation; LOCK-120 external-application boundary; disclosed deterministic seams for the pending children), merged as d0d26d3; chain-independent vertical proof (does not move the current-child pointer); roadmap 2.1 -> 2.2 with M010 COMPLETE; the sharenet battery is CI-wired by this acceptance (existence-guard pattern); the PR's initial CI failure was the pre-RECON-018 governance state, not the delivery (LEDGER-RECON-018 root-caused and repaired it) |
