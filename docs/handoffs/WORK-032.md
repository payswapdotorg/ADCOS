# WORK-032 — Conformance Suite: Implementation Handoff

## Status

**EXECUTION-READY — SOLE ACTIVE WORK ITEM**

Architect-designated active target: 2026-08-28.
Baseline: current `main` after W031 merge and ACR-003.

The frozen Work Item remains normative. This handoff summarizes the repository-local implementation contract; it does not redefine architecture.

## Objective

Build protocol/adapter conformance tests for all frozen contracts so an independent implementation can prove conformance without the suite becoming a second protocol authority.

## Hard dependencies

```text
W003, W004, W005, W007, W011, W012, W015, W016, W017
```

The dependency graph and frozen Work Item declaration are synchronized by accepted `ACR-003`: `W016 → W032` is a hard dependency. `OAQ-001` is CLOSED. Do not change the DAG as part of W032.

## Existing authorities consumed

- W003 protocol envelope/serialization
- W004 identity/credentials
- W005 capabilities
- W007 topology/evidence
- W011 routing
- W012 sessions
- W015 federation
- W016 Adapter SDK/runtime
- W017 secure transport

The suite verifies these contracts. It does not replace any of them.

## Authority boundary

### MAY

- load canonical schemas and frozen vectors;
- compose accepted implementations through public contracts;
- define positive and negative vectors;
- compare canonical observed results against frozen expected results;
- classify conformance outcomes;
- test adapter behavior via W016;
- test failure isolation and forbidden dependencies.

### MUST NOT

- mint new protocol vocabularies;
- redefine authority ownership;
- create shadow policy/identity/topology/routing/session/federation/transport authorities;
- treat structural validity as provenance;
- treat a simulator or reference peer as independent interoperability evidence;
- import future W033+ runtime semantics;
- modify frozen architecture semantics;
- use private implementation names as security boundaries.

## Conformance matrix

Create complete coverage for the frozen contract surface, including:

1. envelope versions/canonicalization/extensions/expiry/replay metadata;
2. identity, credential binding, rotation and revocation;
3. signed capabilities, provenance, validity, withdrawal and negotiation;
4. topology dimensions, claim provenance and poisoning/staleness behavior;
5. routing determinism, intent/resource/evidence constraints and alternates;
6. session identity/lifecycle/expiry/failover/replay safety;
7. multipath behavior where required by frozen contracts;
8. federation scope, revocation and isolation;
9. adapter lifecycle, health, isolation and stable SDK behavior;
10. secure transport mapping, key/session binding, replay and downgrade protection.

Every vector must identify its expected verdict and the authority/contract that determines it.

## Security and negative testing

Include applicable negative cases for:

```text
malformed required fields
invalid versions
canonicalization mismatch
expired/future data
replay/replay poisoning
forged identity/provenance
capability inflation
route/session binding violation
federation scope escalation
transport downgrade
unknown required vs optional extensions
adapter/provider exceptions
forbidden imports
```

Preserve:

```text
integrity != provenance
valid structure != authorized authority artifact
```

Important security regressions must be discriminating: prove the vulnerable behavior fails and the corrected behavior passes.

## Failure and recovery

Where contract semantics require it, exercise restart/recovery, stale data, version conflicts, adapter failures, cleanup failure, replay handling, and cross-authority injection attempts.

The harness may mutate only through the contract being tested and must not become a mutation authority itself.

## Determinism

Vector execution must be reproducible across processes and supported hash seeds. Avoid wall-clock and ambient randomness. Canonicalize vector/result ordering where byte identity matters.

## Evidence discipline

Report separately:

```text
Architecture conformance
Automated verification
External evidence
```

Do not claim external interoperability from in-repo conformance tests.

Failures must be diagnosable with stable non-secret contract/result identifiers and must not leak protected material.

## Expected implementation shape

Prefer a dedicated conformance family plus deterministic vectors/fixtures and narrowly scoped CI integration. Avoid changes to existing authority implementations unless an already-frozen contract is genuinely violated; in that case stop and request Architect clarification/ACR rather than changing the architecture.

## Out of scope

No production protocol implementation, new protocol semantics, new authority, vendor stack, hardware certification, Linux Agent, pilot work, or W033+ runtime.

## Acceptance

W032 is complete only when the Architect confirms:

- complete frozen-contract coverage;
- positive and negative vectors;
- discriminating security regressions;
- explicit authority attribution;
- no shadow vocabulary/authority;
- no hidden/future imports;
- deterministic execution;
- diagnostic, non-secret failures;
- required CI verification;
- automated verification kept distinct from external evidence.

A green suite is necessary, not sufficient, for Architect acceptance.
