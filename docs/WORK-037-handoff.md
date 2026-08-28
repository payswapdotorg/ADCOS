# WORK-037 — Open RAN/Core interoperability profile: Implementation Handoff

**Status:** EXECUTION-DESIGNATED — implement only WORK-037.

## Objective
Validate ADCOS integration with open 5G Core/RAN and standardized
non-3GPP access.

## Hard dependencies
WORK-019 (5G Core adapter), WORK-020 (RAN adapter), WORK-021
(Wi-Fi/non-3GPP adapter), WORK-032 (conformance suite), WORK-033
(Linux reference agent) — all Architect-accepted and merged at the
implementation baseline (`cffbe01` → W035 merge → W036 merge
`481fc52` → the Architect's W037 branch anchor `518c071`).

## Acceptance
- at least one real 5G lab works end-to-end;
- adapter boundaries remain clean;
- mixed access is demonstrated.

## Architecture boundary
- Compose over the ACCEPTED adapters and authorities only: the
  profile layer validates, declares, and orchestrates — it never
  re-implements 5G Core, RAN, Wi-Fi/non-3GPP, identity, sessions,
  routing, multipath, policy, or transport authority, and it never
  mints a session (the session under test is INPUT validated through
  a read-only lookup).
- The profile is declarative DATA (`ProfileDeclaration`: 5 components
  — the W019/W020/W021 adapter families + the W032 conformance suite
  + the W033 reference agent — over exactly 7 reference points, each
  owned by exactly one component; fail-closed validation; canonical
  bytes + digests).
- The class-B scenario composes the three accepted conformance peers
  (real loopback sockets) and carries ONE sacred, access-independent
  `session_id` across four legs (5G Core PDU session → RAN access
  path → N3IWF tunnel → 5G Core re-bind); byte-identical round trips
  on every leg; cross-family ref opacity (only SHA-256 digests of
  adapter refs are journaled); journaled access changes; replayable
  digests; injected instants only.
- The class-C gate COMPOSES the three accepted real interop gates
  (W019 Open5GS, W020 SDR-lab, W021 N3IWF) — never re-implemented,
  never bypassed; each leg keeps its INDEPENDENT operator switch; the
  profile adds exactly one requirement: the SAME session id on every
  leg (config-level coherence validated fail-closed BEFORE any leg
  runs).
- Vendor/Open RAN implementation types never enter ADCOS core
  (asserted by the battery's core-purity audit over the frozen core
  roots).
- Do not implement WORK-038+.

## Verification
Frozen vocabularies and records; the full profile-validation negative
matrix; the mixed-access scenario (session discipline, ref opacity,
journal, determinism across fresh runs and hash seeds, replay with
tamper rejection); the lab-gate semantics (GATE_DISABLED / LEG_DISABLED /
FORBIDDEN / UNREACHABLE / SESSION_DIVERGENCE aggregation matrix, with
NO new PASS path — PASSED only as the conjunction of the three real
leg PASSED outcomes); the three-class evidence model (A/B closed
in-repo; C OPEN until the real gate passes; anti-promotion enforced
in code); structural audits (no shadow authority, import discipline,
core purity, injected clock, secret hygiene, naming-token freedom);
frozen surfaces (API, spec/, PR-delta shape, CI wiring + ordering).

## Evidence
Architecture conformance and automated verification are required and
delivered now (classes A/B).  The real interoperability lab is the
frozen acceptance criterion (class C): RF simulation, OAI RFsim,
software emulation, and synthetic interoperability are engineering
evidence that can NEVER be promoted to class C — the lab gate
discloses this and the evidence model enforces it structurally.

## Out of scope
Protocol redesign, PHY implementation, vendor SDK leakage into core,
W038+ semantics, and inventing substitutes for missing
physical/interoperability evidence.
