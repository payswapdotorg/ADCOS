# WORK-037 — Open RAN/Core interoperability profile

Architect execution handoff. Implement ONLY WORK-037.

## Objective
Validate ADCOS integration with open 5G Core/RAN and standardized non-3GPP access.

## Hard dependencies
WORK-019, WORK-020, WORK-021, WORK-032, WORK-033 — all must remain accepted/merged at the implementation baseline.

## Acceptance
- at least one real 5G lab works end-to-end;
- adapter boundaries remain clean;
- mixed access is demonstrated.

## Required verification
Interoperability lab. RF simulation/emulation is engineering evidence only and must never be promoted to real-lab evidence.

## Authority boundary
Compose over accepted adapters and authorities. Do not reimplement 5G Core, RAN, Wi-Fi/non-3GPP, identity, sessions, routing, multipath, policy, or transport authorities. Vendor/Open RAN implementation types must not enter ADCOS core.

## Evidence classes
A. Architecture conformance — required now.
B. Automated verification — required now.
C. Real interoperability — required for the frozen acceptance claim. Synthetic/RF-simulation evidence may supplement A/B but cannot satisfy C.

## Out of scope
Protocol redesign, PHY implementation, vendor SDK leakage into core, W038+ semantics, and inventing substitutes for missing physical/interoperability evidence.
