# WORK-032 — Conformance Suite — Architect Work Order

## Process state

**EXECUTION-READY — SOLE ACTIVE WORK ITEM**

Architect designation: 2026-08-28
Baseline: `main` after W031 merge and ACR-003 reconciliation.

Z.ai must implement only WORK-032 until this PR is reviewed, accepted, and merged. Do not begin WORK-033 or any later Work Item.

## Frozen source

- `spec/work-items.md` — WORK-032
- `spec/dependency-graph.md` — synchronized by ACR-003
- `spec/architecture.md` — Architecture Version 1.0
- `spec/architecture-lock.md`
- `spec/workflow.md`
- `spec/change-control.md`
- `spec/acr/ACR-003-w032-adapter-conformance-dependency.md`

## Objective

Build the ADCOS protocol/adapter conformance suite so an independent implementation can prove conformance against frozen contracts without the suite becoming a second protocol authority.

The suite is a verifier and evidence classifier. It must not silently define protocol semantics that do not already exist in the frozen architecture.

## Hard dependencies

All must remain Architect-accepted and merged before W032 implementation claims dependency completeness:

```text
W003  Protocol envelope / serialization
W004  Cryptographic identity
W005  Capability statements / negotiation
W007  Evidence-aware topology
W011  Routing
W012  Logical sessions
W015  Federation
W016  Adapter SDK/runtime
W017  Secure transport
```

The W016 dependency is now a synchronized hard DAG edge `W016 → W032` under accepted ACR-003. Do not reopen or modify this relationship inside W032.

## Authority boundary

### W032 may

- load frozen schemas, registries, vectors, and canonicalization rules;
- invoke accepted implementations through public contracts;
- define known-good and known-bad test vectors;
- compare observed behavior with frozen expected behavior;
- classify conformance results;
- produce deterministic, diagnosable evidence;
- exercise adapters through the stable W016 contract;
- test failure isolation and forbidden dependency directions.

### W032 must not

- create a second protocol vocabulary;
- redefine authority ownership;
- mint authoritative protocol objects as part of the system under test;
- accept caller-supplied structurally valid objects as proof of provenance;
- replace identity, policy, routing, session, topology, federation, transport, or adapter semantics;
- use simulator/reference implementations as independent interoperability evidence;
- modify frozen `spec/` semantics;
- import W033+ runtime semantics early;
- use private naming or implementation tricks as security boundaries.

## Required coverage

Build a complete conformance matrix across the frozen contracts, including at minimum:

- protocol envelope, versions, canonicalization, extension handling, expiration and replay metadata;
- NodeID and credential binding/rotation/revocation;
- signed capability statements, provenance, validity, negotiation, withdrawal and unknown extensions;
- topology dimensions, claim provenance, poisoning resistance and stale/removal convergence;
- routing determinism, intent/resource constraints, evidence confidence and alternate-path behavior;
- access-independent session identity, lifecycle, expiry, failover and replay safety;
- multipath/session binding where covered by the frozen contracts;
- federation scope, revocation, peer-domain isolation and resource/capability export policy;
- W016 adapter lifecycle, health, capability exposure, isolation and stable-contract behavior;
- W017 secure transport mappings, key/session binding, replay and downgrade protection;
- forbidden dependency/import directions and vendor/access leakage.

Every vector must have an explicit expected result and identify the authority/contract whose semantics determine that result.

## Negative/security requirements

Negative vectors are first-class. Cover applicable cases for:

- malformed required fields;
- invalid versions/schema combinations;
- canonicalization mismatch;
- expired/future data;
- replay and replay-state poisoning;
- forged identity/provenance;
- capability inflation;
- topology claim poisoning;
- route/session binding violations;
- federation scope escalation;
- transport downgrade;
- unknown required versus unknown optional extensions;
- adapter exceptions and failure isolation;
- hidden/private-authority access;
- forbidden imports/dependencies.

Preserve the distinction:

```text
integrity / structural validity != provenance / authorization
```

A well-formed object with a forged identity-bearing digest or event identifier is a negative case whenever provenance is authoritative.

## Evidence model

Every conformance result must distinguish:

```text
Architecture conformance
Automated verification
External evidence
```

Conformance vectors can establish automated verification and architectural contract behavior. They do not establish external interoperability unless the frozen Work Item explicitly requires an independent implementation/environment and that evidence is actually supplied.

Diagnostics must remain non-secret and identify:

```text
contract
invariant
stable reason/result class
non-secret canonical identifiers
```

Do not leak protected material through exception messages or fixtures.

## Determinism

The suite must be deterministic and reproducible:

- no wall-clock dependence without injected test values;
- no unbounded language/runtime randomness;
- vector ordering independent of insertion order;
- canonical serialization where byte identity matters;
- reproducible across subprocesses and supported hash seeds;
- stable failure classification.

## Failure/recovery

Where applicable, conformance tests must exercise:

- restart/recovery;
- stale and future data;
- conflicting versions;
- provider/adapter exceptions;
- cleanup failure;
- replay state handling;
- cross-authority injection attempts.

The harness must never mutate the system under test except through the contract being tested.

## Discriminating proof requirement

Important security and architecture tests must demonstrate that the vulnerable/incorrect behavior fails and the corrected behavior passes. Do not accept a regression that merely passes against one implementation.

At minimum, require discriminating treatment for provenance, replay, downgrade, capability inflation, authority-boundary violations, adapter isolation, and forbidden dependency directions.

## Expected repository areas

Implementation should be confined to a dedicated conformance family and its deterministic verification fixtures, plus narrowly justified CI/test wiring required by the Work Item.

Do not modify unrelated authority packages merely to simplify the conformance suite.

## Out of scope

- production protocol implementation;
- new protocol semantics;
- new authority ownership;
- vendor-specific runtime implementation;
- Linux Agent / W033 runtime;
- hardware/pilot certification;
- external interoperability claims not backed by the required environment;
- silent changes to the frozen dependency DAG;
- reopening ACR-003 or OAQ-001.

## Acceptance gate

Architect acceptance requires:

1. complete coverage matrix against the frozen W032 scope;
2. known-good and known-bad vectors;
3. discriminating security regressions;
4. explicit authority attribution for expected outcomes;
5. no second vocabulary or shadow authority;
6. no hidden/future dependency imports;
7. deterministic execution and reproducible results;
8. diagnosable failures without secret leakage;
9. CI verification of the conformance suite;
10. explicit separation of automated verification from any external evidence.

CI green is necessary but not sufficient. The final verdict is an Architect decision.

## No architecture drift

Do not reinterpret or simplify frozen semantics to make vectors pass. If implementation requires a frozen semantic change, stop and raise an ACR or Architect clarification instead of editing the frozen rule.
