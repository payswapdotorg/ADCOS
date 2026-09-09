# ADCOS Current State

**READY FOR CONTROLLED ARCHITECTURE TRANSITION — R6 complete; 1.1 is the mandatory forward implementation target; no active implementation authorization.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Reconciled software mainline: `88a73720d8ff28e95728a03e13db631ffdf9688f`
- R6 implementation delivery: `58eced2f7864bd8d6e9cac658574d8c7b0b48965`, accepted under `DEC-0097`, merged as PR #23 at `a08ce85f133dbb76cd15a21d7c16f8a49fa7cc19`
- Post-merge roadmap reconciliation: `88a73720d8ff28e95728a03e13db631ffdf9688f`
- Legacy architecture baseline: Architecture `1.0` frozen and retained for migration/history
- Forward implementation target: Architecture `1.1` proposal package
- Protocol baseline: `1.0` frozen unless/until a successor is separately accepted
- Roadmap: `1.5` frozen / authoritative

## Program authority

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. R0, R1, R2, R3, R5 and R6 are complete. R4 remains an independent physical-validation track under W040. The next forward software activity is the Architecture 1.1 transition gate M001; R7 remains the business-program gate that follows that transition.

## Execution authority

- `active_work_item: null`
- `active_authorization: null`
- Exactly one implementation authorization may be active; currently zero are active.
- Before any feature implementation, the sole Architect must authorize M001 — Architecture 1.1 Freeze through the repository ACR/change-control process.
- After M001 acceptance, subsequent feature Work Items MUST be derived from the 1.1 work-item/dependency package and MUST NOT revert to 1.0 semantics.

## Historical accepted state

W044–W047 and W049 were restored under R0 with acceptance provenance preserved. W048 remains accepted-not-restored and MUST NOT be recreated, mocked, or substituted implicitly. W050–W057 are accepted and present according to the authoritative roadmap/ledger. W040 remains independently in-review and unaccepted; its physical evidence remains separate from software evidence.

## R6

R6 Provider Onboarding & Federation is complete. WORK-057 was corrected and accepted under DEC-0097. The implementation established bounded provider onboarding/federation while preserving existing identity, trust, capability, resource, policy, federation, routing, session, transport, telemetry and commercial authorities.

## Architecture 1.1 transition

The Architecture 1.1 package is the forward design target:

- `spec/architecture-1.1-proposed.md`
- `spec/architecture-lock-1.1-proposed.md`
- `spec/application-model.md`
- `spec/work-items-1.1.md`
- `spec/dependency-graph-1.1.md`
- `spec/migration/classification-matrix.md`
- `spec/integration/vertical-proof.md`

The target architecture makes `ConnectivityContract` the canonical durable object,
uses provider sovereignty and adapter isolation, separates evidence types,
enforces closed-loop assurance, and permits authorized applications to purchase
or sponsor connectivity for bounded beneficiaries.

**Critical routing rule:** Architecture 1.0 remains a preserved historical/frozen
baseline, not the design source for new capabilities. During the transition,
agents use 1.0 only to understand and safely migrate existing implementation.
All new semantics and forward Work Items must trace to 1.1. M001 is the formal
promotion gate. After M001 is accepted, the 1.1 successor architecture/locks
become normative and 1.0 is historical evidence only.

## Next gate

M001 — Architecture 1.1 Freeze — is the immediate transition gate. It must produce
the accepted Architecture 1.1/lock snapshots, updated dependency/work-item
contracts, migration classifications, and durable acceptance evidence.

R7 — Universal Connectivity Commerce — follows the transition and must be
implemented from the accepted 1.1 architecture. Its goal is to normalize
heterogeneous connectivity resources into programmable offers selected by intent,
policy, evidence, availability, geography, quality and price.

## Evidence obligations

The following external evidence obligations remain open and must remain visible in every current-state projection until an Architect decision closes them:

- `EVID-002` — real SDR hardware topology for WORK-020.
- `EVID-003` — Raspberry Pi-class physical hardware for WORK-034.
- `EVID-004` — physical Android handset-backed second-path rebind/handover for WORK-035.
- `EVID-005` — physical Network-in-a-Box deployment at a real isolated site for WORK-036.
- `EVID-006` — real 5G interoperability lab for WORK-037.
- `EVID-007` — real users and physical devices for the WORK-040 pilot.
- `EVID-008` — a real 5G access path for the WORK-040 pilot.

`EVID-001` is closed and remains the only currently closed physical obligation.

## Source of truth

This file is a current-state projection only. Lifecycle history is governed by `spec/architect/execution-ledger.yaml`; architecture-transition authority by accepted ACRs and the 1.1 target package during promotion; program order by `spec/architect/roadmap.yaml`; permission by `spec/architect/authorizations/`. No conversation context is required or authoritative.
