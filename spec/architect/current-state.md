# ADCOS Current State

**R7 ACTIVE (DEC-0101) — Architecture 1.1 is the sole normative forward architecture, FROZEN with ACR-014 ACCEPTED; M001 ACCEPTED (DEC-0100); the bounded R7 program authorization R7-CORE-001 covers the charter child scopes M002-M014; M002 — Connectivity Contract Core is the current child work item (implementing).**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- M001 delivery: PR #25 head `36bfd8e636feafb531ef551a2e15793b57cc2f00` (branch `m001-architecture-1.1-freeze`, branch point `725397ffd60e7d8f44c24c85c86037f43ff6c303`), Architect-accepted under `DEC-0100` and merged as `80292c24502200f84d11491ed12e9cec5e5baf11`
- R7 activation: `DEC-0101` (governance compression) from the reconciled baseline `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (DEC-0100 acceptance head `4168f73` plus the fresh-session reconciliation repair; both push CI green)
- Architecture: Version `1.1` FROZEN (`spec/architecture.md`, LOCK-101..LOCK-120); Version 1.0 preserved verbatim at `spec/history/architecture-1.0.md`
- Protocol baseline: `1.0` frozen unless/until a successor is separately accepted
- Roadmap: `1.8` frozen / authoritative (advanced from 1.7 by DEC-0101)

## Program authority

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. R0, R1, R2, R3, R5, R6 and M001 — Architecture 1.1 Freeze — are complete (R6 Provider Onboarding & Federation completed under DEC-0097/WORK-057). R4 remains an independent physical-validation track under W040. **R7 — Universal Connectivity Commerce is ACTIVE** under DEC-0101: one bounded R7 program authorization (`R7-CORE-001`, `spec/architect/authorizations/R7.yaml`) with the R7 charter (`spec/architect/work-items/R7-charter.md`) as the gate-specific Work Item contract and `spec/architect/dependency-overlays/R7.yaml` as the gate overlay. The charter declares the child work-item scopes M002-M014; the Tech Lead may decompose, dispatch (3x3/9/depth-2), integrate and deliver within them without further pre-implementation authorization ceremonies. **Per-child acceptance remains mandatory** (DEC-0102 onward, one durable decision per child, exact reviewed head + merge SHA).

## Execution authority

- `active_work_item: M002` — Connectivity Contract Core is the current child in implementation
- `active_authorization: R7-CORE-001` — the sole active implementation authorization (program-level, DEC-0101); `M001-CORE-001` is closed by the DEC-0100 acceptance (status accepted, authorized false); all W-item authorizations remain closed
- M002 scope (charter): `contracts/` (new canonical domain), `tools/contract_selftest.py`, `docs/M002-evidence.md`, plus the authorization-aware battery-scope consultation repairs across the battery surface (the duty pre-recorded in `docs/M001-evidence.md` §4 for the post-M001 implementation era)
- Implementation PRs under R7-CORE-001 must classify as implementation-only (drift guard) and be fully covered by the declared scope (ARCH-08 provenance, byte-identical authorization inheritance from main)
- Subsequent feature work derives from the accepted 1.1 work-item/dependency package (M001-M014) and MUST NOT revert to 1.0 semantics

## Historical accepted state

W044–W047 and W049 were restored under R0 with acceptance provenance preserved. W048 remains accepted-not-restored and MUST NOT be recreated, mocked, or substituted implicitly. W050–W057 are accepted and present according to the authoritative roadmap/ledger. W040 remains independently in-review and unaccepted; its physical evidence remains separate from software evidence. The legacy implementation (adapters, commercial core, developer API, capabilities, policy, federation, mobility, sessions, usage, telemetry, composition, …) is a **migration reservoir** classified by the frozen migration matrix (`spec/migration/classification-matrix.md`); it is harvest material for the M003-M014 child scopes, never forward design authority.

## R7 — Universal Connectivity Commerce (current gate)

R7 is ACTIVE under DEC-0101 as a governance-compression activation: one bounded program authorization with child work-item scopes instead of thirteen per-item pre-implementation ceremonies. The R7 charter carries the architectural invariants (LOCK-101..LOCK-120), the child scopes and acceptance criteria (M002-M014), the dependency model (M002 → M003 → M004 → M005 → M006 → M007 → M008; M009 from M002; M013 independent; M010/M011/M012 from M013; M014 converging), the evidence policy (SOFTWARE-class deterministic batteries per child; physical obligations untouched), the migration policy (harvest per the classification matrix; no history rewriting), the 3-worker concurrency policy, and the per-child acceptance rules. **M002 — Connectivity Contract Core is NOW**: the canonical `ConnectivityContract` domain (identity; principal/beneficiary scope; normalized requirements; accepted offer references; hard constraints; committed service properties; validity interval; usage/pricing terms; assurance obligations; permitted execution scope; termination/compensation rules; provenance; signature references), lease/expiry, the contract-level lifecycle state machine, hard-constraint immutability (LOCK-108), and structural authority uniqueness (LOCK-117).

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
