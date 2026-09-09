# ADCOS Current State

**M001 ACCEPTED (DEC-0100) — Architecture 1.1 is the sole normative forward architecture, FROZEN with ACR-014 ACCEPTED; no implementation authorization is active; R7 — Universal Connectivity Commerce is the next unlocked (not activated) gate.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- M001 delivery: PR #25 head `36bfd8e636feafb531ef551a2e15793b57cc2f00` (branch `m001-architecture-1.1-freeze`, branch point `725397ffd60e7d8f44c24c85c86037f43ff6c303`), Architect-accepted under `DEC-0100` and merged as `80292c24502200f84d11491ed12e9cec5e5baf11`
- Pre-acceptance governance repair: `3e3ea3b` (current_spec_check fail-closed aggregation + marker alignment; WORK-057 ledger projection appended; conformance case_63 frozen-authority mirror re-baselined to the acceptance merge; main push CI green)
- R6 implementation delivery: `58eced2f7864bd8d6e9cac658574d8c7b0b48965`, accepted under `DEC-0097`, merged as PR #23 at `a08ce85f133dbb76cd15a21d7c16f8a49fa7cc19`
- Architecture: Version `1.1` FROZEN (`spec/architecture.md`, LOCK-101..LOCK-120); Version 1.0 preserved verbatim at `spec/history/architecture-1.0.md`
- Protocol baseline: `1.0` frozen unless/until a successor is separately accepted
- Roadmap: `1.7` frozen / authoritative (advanced from 1.6 by DEC-0100)

## Program authority

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. R0, R1, R2, R3, R5, R6 and M001 — Architecture 1.1 Freeze — are complete. R4 remains an independent physical-validation track under W040. R7 — Universal Connectivity Commerce — is the next gate: UNLOCKED and NOT ACTIVATED, awaiting its gate-specific Work Item contract, dependency overlay, evidence obligations, and repository-local implementation authorization.

## Execution authority

- `active_work_item: null` — implementation is halted pending the R7 activation decision
- `active_authorization: null` — no implementation authorization is active; `M001-CORE-001` is closed by the `DEC-0100` acceptance (status accepted, authorized false)
- M001 delivered a pure architecture/governance transition: the 1.1 successor snapshots are canonical, the 1.0 snapshot is preserved verbatim under `spec/history/`, ACR-014 is ACCEPTED, and the current-governance checkers enforce the post-acceptance invariants and fail closed on pre-acceptance markers.
- Subsequent feature Work Items MUST be derived from the accepted 1.1 work-item/dependency package (M001-M014) and MUST NOT revert to 1.0 semantics.

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

R7 — Universal Connectivity Commerce — is the next gate: UNLOCKED (its M001
prerequisite is satisfied by DEC-0100) and NOT ACTIVATED. Activation requires
the gate-specific R7 Work Item contract, dependency overlay, evidence
obligations, and repository-local implementation authorization before any
implementation. The first implementation candidate is M002 — Connectivity
Contract Core (canonical contract, lifecycle, hard constraints, lease/expiry
and authority uniqueness) per the accepted 1.1 dependency model. Its goal is to normalize
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
