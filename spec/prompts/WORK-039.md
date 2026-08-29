# WORK-039 — Federation at Scale

Status: EXECUTION-DESIGNATED. Implement ONLY WORK-039.

## Frozen contract
Objective: Scale federation, discovery, and route/capability exchange across many domains.
Dependencies: WORK-015, WORK-031, WORK-033, WORK-036.
Acceptance:
- federation scales horizontally;
- failure domains remain isolated;
- revocation propagates predictably.
Required verification: large-scale simulation and integration.
Definition of done: federation remains safe and predictable at multi-domain scale.

## Authority boundary
Compose over accepted WORK-015 federation authority and the accepted WORK-031 simulator, WORK-033 Linux Agent, and WORK-036 appliance surfaces. Do not create a second federation authority, duplicate identity/session/routing/policy semantics, or alter frozen protocol semantics. Simulation must not become a second source of protocol truth.

## Required verification
- deterministic large-scale domain simulation;
- horizontal-scale behavior and bounded resource use;
- isolated failure domains under partition/fault injection;
- revocation propagation with explicit convergence bounds/observations from the authoritative federation state;
- replay/determinism and discriminating negative tests;
- integration through accepted Agent/Network-in-a-Box composition surfaces;
- no W040+ semantics.

## Evidence
In-repo architecture conformance and automated large-scale simulation/integration are required. Real deployment evidence is not part of the frozen W039 acceptance criterion unless a new ACR says otherwise.

## Out of scope
Protocol redesign, new federation trust semantics, new authority owners, W040+ work, and treating simulation artifacts as authoritative federation state.
