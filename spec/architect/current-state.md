# ADCOS Current State

**M001 IN REVIEW — the Architecture 1.1 Freeze delivery is on branch `m001-architecture-1.1-freeze` awaiting sole-Architect acceptance (DEC-0100); Architecture 1.1 is promoted as the sole normative forward architecture by this delivery.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Delivery branch point: `725397ffd60e7d8f44c24c85c86037f43ff6c303` (main CI green; PR #24 merge + DEC-0098 activation + guard repair + DEC-0099 battery-mirror reconciliation)
- R6 implementation delivery: `58eced2f7864bd8d6e9cac658574d8c7b0b48965`, accepted under `DEC-0097`, merged as PR #23 at `a08ce85f133dbb76cd15a21d7c16f8a49fa7cc19`
- Architecture: Version `1.1` FROZEN in the M001 delivery (`spec/architecture.md`); Version 1.0 preserved verbatim at `spec/history/architecture-1.0.md`
- Protocol baseline: `1.0` frozen unless/until a successor is separately accepted
- Roadmap: `1.6` frozen / authoritative (advances to 1.7 at the DEC-0100 acceptance)

## Program authority

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. R0, R1, R2, R3, R5 and R6 are complete. R4 remains an independent physical-validation track under W040. M001 — Architecture 1.1 Freeze — is ACTIVE and IN REVIEW (delivery branch `m001-architecture-1.1-freeze`). R7 remains the business-program gate that follows the M001 acceptance.

## Execution authority

- `active_work_item: M001` (in review)
- `active_authorization: M001-CORE-001` (issued by `DEC-0098`; scope amended by `DEC-0099`)
- Exactly one implementation authorization is active: `M001-CORE-001`. All W-item authorizations remain closed.
- The M001 delivery is a pure architecture/governance transition: it promotes the 1.1 successor snapshots into the canonical files, preserves the 1.0 snapshot verbatim under `spec/history/`, flips ACR-014 to ACCEPTED, and evolves the current-governance checkers to the post-freeze invariants. Sole-Architect review of the exact delivery head and the DEC-0100 acceptance close M001.
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

**Critical routing rule:** With the M001 delivery, Architecture 1.1
(`spec/architecture.md`, LOCK-101..LOCK-120) is the sole normative forward
architecture. Architecture 1.0 is preserved historical evidence at
`spec/history/`, used only to understand and migrate existing
implementation. All new semantics and forward Work Items must trace to 1.1.
Until the DEC-0100 acceptance closes M001, only explicitly authorized
transition/migration work may proceed.

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
