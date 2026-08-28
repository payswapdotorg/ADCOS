# WORK-038 — Future IMT / 6G adapter profile

**Status:** EXECUTION-DESIGNATED — implement only WORK-038.

## Objective
Prove a hypothetical future access technology can be integrated using the same adapter/registry/core contracts without modifying core protocol semantics.

## Hard dependencies
WORK-016, WORK-029, WORK-032, WORK-033 — all accepted and merged at the implementation baseline.

## Frozen acceptance criteria
- a new profile identifier can be added without a core schema change;
- capabilities are additive;
- routing, session, resource, and policy layers remain unchanged.

## Required verification
Synthetic future-profile conformance test.

## Architectural boundary
- Treat the future IMT/6G technology as an additive adapter/profile, never as a new core domain type.
- Reuse the existing Adapter SDK/runtime, capability registry, compatibility/upgrade contracts, conformance suite, and Linux Agent composition surfaces.
- Do not modify frozen protocol semantics, core schemas, routing/session/resource/policy authorities, or existing access-profile meaning merely to accommodate the hypothetical technology.
- The future profile may introduce only profile-specific identifiers, capability data, adapter mappings, and test fixtures required by the frozen contracts.
- Unknown/future identifiers must remain safely representable and must not silently gain authority.
- Do not import vendor SDKs, radio/PHY implementation types, or platform-specific APIs into ADCOS core.
- Do not implement WORK-039+.

## Evidence classes
A. Architecture conformance — required now.
B. Automated verification — required now.
C. Physical/future-network interoperability — not applicable to this synthetic Work Item; do not invent real-world evidence.

## Required discrimination
The conformance battery must demonstrate that the new profile can be added while existing routing/session/resource/policy behavior remains byte-identical for unchanged inputs, and that profile-specific capability data is additive rather than authoritative core semantics.

## Acceptance gate
Architect acceptance requires the synthetic future-profile conformance test, proof of no core schema change, proof of additive capability registration, and structural evidence that routing/session/resource/policy code remains semantically untouched.
