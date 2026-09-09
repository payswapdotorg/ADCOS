# ADCOS Current State

**M001 ACTIVE — Architecture 1.1 Freeze is the sole active Work Item under authorization M001-CORE-001 (DEC-0098).**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Reconciled software mainline: `40737a0c716eff3ad05753431c24c2717afb2a68` (PR #24 Architect-accepted merge of the Architecture 1.1 transition package)
- R6 implementation delivery: `58eced2f7864bd8d6e9cac658574d8c7b0b48965`, accepted under `DEC-0097`, merged as PR #23 at `a08ce85f133dbb76cd15a21d7c16f8a49fa7cc19`
- Legacy architecture baseline: Architecture `1.0` frozen and retained for migration/history
- Forward implementation target: Architecture `1.1` proposal package (promotion in progress under M001/ACR-014)
- Protocol baseline: `1.0` frozen unless/until a successor is separately accepted
- Roadmap: `1.6` frozen / authoritative (advanced by DEC-0098)

## Program authority

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. R0, R1, R2, R3, R5 and R6 are complete. R4 remains an independent physical-validation track under W040. M001 — Architecture 1.1 Freeze — is now ACTIVE (DEC-0098). R7 remains the business-program gate that follows the M001 acceptance.

## Execution authority

- `active_work_item: M001`
- `active_authorization: M001-CORE-001` (issued by `DEC-0098`, baseline `40737a0c716eff3ad05753431c24c2717afb2a68`)
- Exactly one implementation authorization is active: `M001-CORE-001`. All W-item authorizations remain closed.
- M001 is a pure architecture/governance transition Work Item: its delivery PR must classify as governance-only (no implementation-domain files), promote the 1.1 successor snapshots, archive the 1.0 snapshot under `spec/history/`, and be accepted by the sole Architect (DEC-0099) before ACR-014 becomes ACCEPTED.
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
All new semantics and forward Work Items must trace to 1.1. M001 (ACTIVE,
ACR-014) is the formal promotion gate; until its delivery is accepted, only
explicitly authorized transition/migration work may proceed. After M001 is
accepted, the 1.1 successor architecture/locks become normative and 1.0 is
historical evidence only.

## Next gate

M001 — Architecture 1.1 Freeze — is the ACTIVE transition gate under
authorization M001-CORE-001. Its governance-classified delivery must produce
the accepted Architecture 1.1/lock snapshots (promoted into
`spec/architecture.md` / `spec/architecture-lock.md`), the successor work-item
registry and dependency graph, the archived 1.0 snapshot under `spec/history/`,
migration classifications, vertical-proof boundaries, and durable acceptance
evidence (DEC-0099).

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
