# ADCOS Current State

**R7 ACTIVE (DEC-0101) — Architecture 1.1 is the sole normative forward architecture, FROZEN with ACR-014 ACCEPTED; M001 ACCEPTED (DEC-0100); M002 Connectivity Contract Core ACCEPTED (DEC-0102, merge `0ffdf47`); M003 Offers and Provider Capability Exchange ACCEPTED (DEC-0103, merge `4090e03`); M013 Developer Connectivity API ACCEPTED (DEC-0113, merge `8f4d58a2`, chain-independent); the bounded R7 program authorization R7-CORE-001 covers the charter child scopes M002-M014; M004 — Eligibility and Policy is the current child work item (implementing).**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- M001 delivery: PR #25 head `36bfd8e636feafb531ef551a2e15793b57cc2f00` (branch `m001-architecture-1.1-freeze`, branch point `725397ffd60e7d8f44c24c85c86037f43ff6c303`), Architect-accepted under `DEC-0100` and merged as `80292c24502200f84d11491ed12e9cec5e5baf11`
- R7 activation: `DEC-0101` (governance compression) from the reconciled baseline `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (DEC-0100 acceptance head `4168f73` plus the fresh-session reconciliation repair; both push CI green)
- M002 delivery: PR #26 head `0112943c99c7fd3215bf7c8d2b0ebb740a282132` (branch `m002-contract-core`, base `7d28d9d` containing the R7-CORE-001 baseline `1e5c55f`), Tech-Lead-accepted under `DEC-0102` and merged as `0ffdf4775112c0b71b71f47f3688a50347ab4371` (push CI green run 34386408652; PR-head CI green run 34384904922)
- M003 delivery: PR #27 head `eace14349cbfae06235712778c578fbda0d4cffb` (branch `m003-offer-exchange`, base `d022e06` the DEC-0102-accepted head with the provenance repair), Tech-Lead-accepted under `DEC-0103` and merged as `4090e032324fc4fa5fcc6ffe81a85c22eca331a3` (PR-head CI green run 34394500718; merge-push CI green run 34396825502; the offer battery is CI-wired at acceptance)
- M013 delivery: PR #28 head `69ef8dee1adcf8c8a6f5855c9056d0364a0fd7b9` (branch `m013-developer-api`, base `d022e06`; zero file overlap with the M003 delivery), Tech-Lead-accepted under `DEC-0113` and merged as `8f4d58a23966a3af5242f37bab293a114cf5085a` (PR-head CI green run 34395941523; merge-push CI run 34397464404)
- Architecture: Version `1.1` FROZEN (`spec/architecture.md`, LOCK-101..LOCK-120); Version 1.0 preserved verbatim at `spec/history/architecture-1.0.md`
- Protocol baseline: `1.0` frozen unless/until a successor is separately accepted
- Roadmap: `2.0` frozen / authoritative (advanced from 1.9 by DEC-0103/DEC-0113: M003 + M013 COMPLETE, M004 current child)

## Program authority

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. R0, R1, R2, R3, R5, R6 and M001 — Architecture 1.1 Freeze — are complete (R6 Provider Onboarding & Federation completed under DEC-0097/WORK-057). R4 remains an independent physical-validation track under W040. **R7 — Universal Connectivity Commerce is ACTIVE** under DEC-0101: one bounded R7 program authorization (`R7-CORE-001`, `spec/architect/authorizations/R7.yaml`) with the R7 charter (`spec/architect/work-items/R7-charter.md`) as the gate-specific Work Item contract and `spec/architect/dependency-overlays/R7.yaml` as the gate overlay. The charter declares the child work-item scopes M002-M014; the Tech Lead may decompose, dispatch (3x3/9/depth-2), integrate and deliver within them without further pre-implementation authorization ceremonies. **Per-child acceptance remains mandatory** (one durable decision per child, exact reviewed head + merge SHA; M002 is closed by DEC-0102, M003 by DEC-0103, M013 by DEC-0113; the next is DEC-0104 for M004).

## Execution authority

- `active_work_item: M004` — Eligibility and Policy is the current child in implementation
- `active_authorization: R7-CORE-001` — the sole active implementation authorization (program-level, DEC-0101; child advanced M002 → M003 by DEC-0102, M003 → M004 by DEC-0103); `M001-CORE-001` is closed by the DEC-0100 acceptance (status accepted, authorized false); all W-item authorizations remain closed
- M004 scope (charter): `policy/`, `eligibility/`, `tools/policy_selftest.py` (the eligibility battery re-baseline may land here or under M009 per its DEC-0099 disclosure), `docs/M004-evidence.md` — deterministic eligibility and policy evaluation around the canonical contract; zero provider-SDK leakage (LOCK-110 discipline at the policy boundary)
- Implementation PRs under R7-CORE-001 must classify as implementation-only (drift guard) and be fully covered by the declared scope (ARCH-08 provenance, byte-identical authorization inheritance from main)
- Subsequent feature work derives from the accepted 1.1 work-item/dependency package (M001-M014) and MUST NOT revert to 1.0 semantics

## Historical accepted state

W044–W047 and W049 were restored under R0 with acceptance provenance preserved. W048 remains accepted-not-restored and MUST NOT be recreated, mocked, or substituted implicitly. W050–W057 are accepted and present according to the authoritative roadmap/ledger. W040 remains independently in-review and unaccepted; its physical evidence remains separate from software evidence. The legacy implementation (adapters, commercial core, developer API, capabilities, policy, federation, mobility, sessions, usage, telemetry, composition, …) is a **migration reservoir** classified by the frozen migration matrix (`spec/migration/classification-matrix.md`); it is harvest material for the M003-M014 child scopes, never forward design authority.

## R7 — Universal Connectivity Commerce (current gate)

R7 is ACTIVE under DEC-0101 as a governance-compression activation: one bounded program authorization with child work-item scopes instead of thirteen per-item pre-implementation ceremonies. The R7 charter carries the architectural invariants (LOCK-101..LOCK-120), the child scopes and acceptance criteria (M002-M014), the dependency model (M002 → M003 → M004 → M005 → M006 → M007 → M008; M009 from M002; M013 independent; M010/M011/M012 from M013; M014 converging), the evidence policy (SOFTWARE-class deterministic batteries per child; physical obligations untouched), the migration policy (harvest per the classification matrix; no history rewriting), the 3-worker concurrency policy, and the per-child acceptance rules. **M002 — Connectivity Contract Core is DELIVERED AND ACCEPTED (DEC-0102)**: the canonical `ConnectivityContract` domain — live under `contracts/` with its 54/54 battery. **M003 — Offers and Provider Capability Exchange is DELIVERED AND ACCEPTED (DEC-0103)**: the provider-domain offer model (`offers/` with LOCK-118 provenance, explicit bounded commitments, the LOCK-105 no-topology catalog exchange, LOCK-113 integer pricing reference shapes) plus the capabilities/discovery/marketplace harvest per the frozen migration matrix, with the 49/49 offer battery CI-wired at acceptance. **M013 — Developer Connectivity API is DELIVERED AND ACCEPTED (DEC-0113)**: the `developerapi/` surface harvested onto the canonical 1.1 authority (LOCK-114 opaque typed references; the gateway re-bound to the accepted contracts domain; schema 2.0 with the honest 1.x/0.8 retirement) with its 56/56 battery — the first two-worker parallel delivery round of the charter's 3-worker pipeline. **M004 — Eligibility and Policy is NOW**.

## Architecture 1.1 transition

The transition is complete. Architecture 1.1 (`spec/architecture.md`, LOCK-101..LOCK-120) is the sole normative forward architecture, permanently; Architecture 1.0 is preserved historical evidence at `spec/history/`, used only to understand and migrate existing implementation. All new semantics and forward Work Items trace to 1.1. The authoritative transition record is ACR-014 (ACCEPTED) with the DEC-0100 acceptance chain.

## Evidence obligations

The following external evidence obligations remain open and must remain visible in every current-state projection until an Architect decision closes them:

- `EVID-002` — real SDR hardware topology for WORK-020.
- `EVID-003` — Raspberry Pi-class physical hardware for WORK-034.
- `EVID-004` — physical Android handset-backed second-path rebind/handover for WORK-035.
- `EVID-005` — physical Network-in-a-Box deployment at a real isolated site for WORK-036.
- `EVID-006` — real 5G interoperability lab for WORK-037.
- `EVID-007` — real users and physical devices for the WORK-040 pilot.
- `EVID-008` — a real 5G access path for the WORK-040 pilot.

`EVID-001` is closed and remains the only currently closed physical obligation. R7 software evidence never converts to PHYSICAL PASS.

## Source of truth

This file is a current-state projection only. Lifecycle history is governed by `spec/architect/execution-ledger.yaml`; architecture-transition authority by accepted ACRs; program order by `spec/architect/roadmap.yaml`; the R7 gate contract by `spec/architect/work-items/R7-charter.md`; permission by `spec/architect/authorizations/`. No conversation context is required or authoritative.
