# WORK-014 — Mobility and Handover Manager

## Status
AUTHORITATIVE IMPLEMENTATION HANDOFF — ARCHITECT

## Work Item
**WORK-014 — Mobility and handover manager**

## Baseline
Implement only from the current accepted `main` after WORK-013 acceptance.

At handoff preparation, the accepted WORK-013 merge is:

```text
edb241ca03fbb2f91b0c89cf67cb17d85298575c
```

Do not branch from an older Work Item branch. Do not copy implementation from an unaccepted branch.

## Dependency correction
ACR-001 is accepted. WORK-014 depends only on:

- WORK-012 — Logical sessions
- WORK-013 — Multipath session manager

WORK-017 is **not** a WORK-014 dependency. The frozen dependency graph is the sequencing authority, and it places WORK-014 in Phase 2 before Phase 3 transport implementation.

## Objective
Implement `/mobility` as the authoritative ADCOS layer for session-level mobility and handover.

Mobility changes the underlying access path(s) while preserving logical session identity whenever the policy, session contract, route candidates, and adapter capabilities permit it.

The mobility layer MUST NOT become:

- a routing engine;
- a topology authority;
- a resource accounting authority;
- a policy engine;
- a transport implementation;
- an access-technology controller;
- a radio/PHY algorithm;
- an adapter registry;
- a federation authority.

## Frozen architectural boundary

The ownership chain is:

```text
Topology      -> what connectivity/evidence exists
Resources     -> what capacity/state exists
Intent        -> what is desired
Policy        -> what is permitted
Routing       -> which feasible path(s) are selected
Session       -> logical connectivity lifecycle
Multipath     -> multiple paths for one logical session
Mobility      -> transition of an existing session between accepted paths
Transport     -> how bytes are securely carried
Adapter       -> how a concrete access/provider realizes transport
```

Mobility consumes authoritative outputs from the lower layers. It MUST NOT recalculate their authority.

The key invariant is:

```text
Mobility changes PATH BINDING / PATH LIFECYCLE,
not SESSION IDENTITY.
```

## Frozen locks that govern this Work Item

WORK-014 must satisfy at least:

- LOCK-001 — access-technology neutrality
- LOCK-003 — future IMT technologies remain adapters
- LOCK-005 — Node identity is access independent
- LOCK-006 — Session identity is access independent
- LOCK-007 — capability negotiation is normative
- LOCK-008 — claims retain provenance
- LOCK-013 — graceful degradation
- LOCK-016 — provider isolation
- LOCK-017 — no vendor authority
- LOCK-019 — intent over implementation detail
- LOCK-020 — multipath is a capability
- LOCK-021 — mobility is session-level
- LOCK-022 — zero-trust
- LOCK-023 — no secret leakage
- LOCK-024 — conformance is architectural

Module ownership is frozen: `/mobility` owns session migration and handover. `/session` remains authoritative for logical session state. `/routing` remains authoritative for selected ADCOS paths. `/adapters` and `/transport` remain below mobility.

## Required design

### 1. Mobility plan
Introduce a mobility domain model representing an explicit handover transaction for an existing session.

The model must contain enough information to make the transaction:

- explicit;
- deterministic;
- auditable;
- replay-safe;
- rollback-safe;
- bound to the existing session;
- bound to the old path and the accepted candidate path(s);
- time/expiry aware.

A mobility transaction MUST NOT silently mutate a session.

At minimum distinguish:

```text
mobility plan
mobility attempt/transaction
mobility event/history
mobility result/failure
```

Do not conflate a plan with its execution history.

### 2. Preserve Session ID

A successful handover MUST preserve the existing `session_id`.

No access-generation identifier, cell identifier, bearer identifier, adapter identifier, modem identifier, or vendor identifier may become part of the logical session identity.

A handover is therefore a state transition on an existing session, not creation of a replacement session.

### 3. Old/new path binding

Every handover must explicitly identify:

- current/old accepted path binding;
- candidate/new accepted path binding;
- route decision identity;
- path identity;
- the policy/intent bindings used to authorize the candidate;
- evaluation instant and expiry information sufficient to prove that the candidate was valid when committed.

The new path MUST pass the same accepted binding semantics required by WORK-012/013. Do not duplicate route-validation, policy-validation, intent-validation, or path-ID derivation rules. Reuse established authorities/interfaces.

### 4. Candidate reservation

Implement a transport-independent reservation/prepare phase.

The mobility layer may reserve or mark a candidate path as prepared only through the already-defined resource/session contracts. It MUST NOT invent a second resource admission system.

Distinguish at least:

```text
candidate observed
candidate accepted
candidate reserved/prepared
handover committed
handover rolled back
candidate rejected/expired
```

Reservation is not consumption.

Preparation is not activation.

Selection is not execution.

### 5. Make-before-break

Where the existing multipath/session contracts permit it, support:

```text
old path remains active
        ↓
new path prepared/validated
        ↓
new path committed
        ↓
old path retired
```

Do not assume every underlying transport/access supports make-before-break.

The core must express the semantic operation while adapters/transport determine whether the requested preparation/activation is actually possible.

### 6. Break-before-make fallback

Where make-before-break is not possible, the mobility layer may perform an explicitly modelled break-before-make transition.

This must never silently convert into a new session.

The session must enter a clearly represented transitional/degraded state and either:

- commit to a valid new path; or
- enter a deterministic failure state while preserving the existing session identity/history.

### 7. Rollback

Failed handovers MUST roll back to the last authoritative session/path state whenever that state remains valid.

Rollback semantics must be explicit and auditable.

At minimum test:

- preparation failure;
- candidate expiration before commit;
- new-path validation failure;
- policy denial;
- path disappearance;
- resource reservation failure;
- commit failure;
- duplicate/replayed handover event;
- conflicting sequence reuse.

A failed handover must never leave a half-applied path binding.

### 8. Atomicity

The semantic mutation of a handover must be atomic at the session/history boundary.

A multi-step handover implementation may perform external preparation, but the authoritative session state change must follow the same atomic/replay-safe discipline established by WORK-012 and WORK-013.

No state may expose:

```text
new path active + old path still authoritative
```

or any equivalent half-committed state unless that state is explicitly represented as a valid transitional state in the frozen mobility model.

### 9. Multipath interaction

Mobility must work with WORK-013 rather than replace it.

The mobility layer may:

- prepare a candidate constituent path;
- activate/deactivate a constituent path through multipath semantics;
- move the preferred/active set where the accepted multipath contract permits;
- preserve alternate paths during handover.

It must NOT create a second path-selection/scheduling authority.

Do not introduce a `primary_route` authority that contradicts WORK-013's multipath state model.

### 10. Routing interaction

Mobility consumes a new accepted route/path from WORK-011.

Mobility MUST NOT call routing internals in a way that silently recomputes and mutates routing authority.

A mobility request may request/receive a candidate route, but the selected route remains a routing-layer output and its content-derived identity must remain intact.

### 11. Policy and intent interaction

Before commit, the candidate path must remain valid against the session's bound intent and policy context.

Do not embed a second policy engine.

Do not reinterpret soft intent preferences as authorization.

Do not silently accept a candidate because it is reachable if it fails a hard session constraint.

### 12. Time and expiry

All evaluation instants MUST be injected.

No wall-clock reads inside deterministic mobility-domain logic.

A candidate that is valid when discovered but expired at commit MUST fail closed.

Old and new path expiry must be considered explicitly in transition/rollback semantics.

### 13. Replay and sequencing

Use deterministic sequence/event semantics consistent with WORK-012/013.

Required properties:

- exact duplicate replay is idempotent;
- conflicting reuse of an event identity/sequence fails closed;
- gaps or stale sequences fail closed where the session history contract requires them;
- replay cannot create a new route binding without the original validated handover semantics;
- replay cannot bypass policy/intent/path binding validation.

### 14. Concurrency

The same session may receive concurrent mobility requests.

Define deterministic behavior for:

- two handovers targeting different candidates;
- two handovers targeting the same candidate;
- one request superseding another;
- one request racing with termination;
- one request racing with a multipath path failure;
- one request racing with candidate expiry.

At most one authoritative transition may win a given sequence point, and losers must fail or become explicit stale/superseded outcomes rather than partially mutating state.

### 15. Serialization

Any new mobility domain objects/events that cross the protocol boundary must use the established WORK-003 canonical serialization machinery.

Do not create a second canonicalization or hashing system.

Any content-derived IDs MUST be recomputable from content and verified during construction/deserialization.

### 16. Error model

Use explicit, deterministic reason codes for at least:

```text
invalid session
unknown session
invalid candidate
candidate expired
candidate unavailable
policy denied
intent violation
path binding mismatch
old-path mismatch
sequence conflict
replay conflict
reservation failure
commit failure
rollback failure
concurrent transition
unsupported operation
```

Do not expose internal exceptions as the semantic protocol result.

### 17. Access-technology neutrality

The mobility package MUST NOT branch on:

- 5G
- LTE
- Wi-Fi
- 6G
- NR
- gNB
- eNB
- N3IWF
- QUIC
- TLS
- modem vendor names
- chipset names
- SIM/IMSI
- cell IDs

Those belong to adapters/transport or future Work Items.

A mobility test double should model abstract capability results such as `prepare`, `activate`, `deactivate`, `rollback`, not concrete radio procedures.

### 18. No transport dependency

Do NOT import `/transport`, 5G SDKs, Open5GS, OpenAirInterface, Android/iOS APIs, or provider SDKs.

WORK-014 must be implementable and fully testable before WORK-017 exists.

### 19. State authority

The session subsystem remains authoritative for the logical session.

The mobility subsystem may own the mobility transaction state/history, but it must commit session/path changes only through the accepted session/multipath contract.

No duplicate session state authority is permitted.

### 20. Failure semantics

The most important invariant is:

```text
NO HALF-HANDOVER
```

Every handover attempt must end in one of:

```text
committed
rolled_back
failed_without_mutation
explicitly_degraded/transitional
```

with deterministic evidence explaining why.

## Suggested module boundary

Z.ai may choose exact filenames, but the package should normally separate responsibilities similar to:

```text
mobility/
  model.py
  validation.py
  planning.py
  execution.py
  rollback.py
  serialization.py
  __init__.py
  README.md
```

Do not create these files merely to match the list if the code structure does not require them.

## Required verification

Create a dedicated `tools/mobility_selftest.py` and integrate it into the existing deterministic CI suite.

At minimum the self-test MUST cover:

1. session ID remains unchanged across successful handover;
2. old/new path IDs are distinct and content-bound;
3. old-path binding mismatch fails closed;
4. new-path binding mismatch fails closed;
5. policy denial prevents commit;
6. hard intent violation prevents commit;
7. expired candidate cannot commit;
8. preparation failure rolls back with no half-state;
9. commit failure rolls back atomically;
10. break-before-make fallback preserves session identity;
11. make-before-break preserves the old path until new path commit;
12. old path retires only after successful new-path commit;
13. duplicate handover replay is idempotent;
14. conflicting replay fails closed;
15. sequence gaps/stale sequences fail closed;
16. concurrent handover requests are deterministic;
17. handover racing with termination is deterministic and atomic;
18. candidate resource reservation is not confused with consumption;
19. no second policy authority is created;
20. no second routing authority is created;
21. no second topology authority is created;
22. no wall-clock reads;
23. no randomness;
24. no access-technology/vendor imports or branches;
25. no secret leakage in mobility state/serialization;
26. content-derived IDs recompute and tampering fails;
27. serialization round-trip is byte-identical;
28. deterministic result across process runs;
29. stale/expired old-path handling is deterministic;
30. rollback remains possible only when the prior authoritative state is still valid.

The exact number of tests is up to Z.ai; all 30 categories above are mandatory.

## Required audits

The implementation PR must mechanically prove:

- `mobility/` does not import provider/access/transport implementations;
- `mobility/` does not create a duplicate `SessionStore`, `RoutingEngine`, `PolicyEngine`, or `ResourceStore` authority;
- no wall-clock access exists in deterministic mobility logic;
- no randomness exists in IDs or transition sequencing;
- path/session IDs are content-bound;
- frozen architecture documents are untouched;
- prior accepted Work Item prompts are untouched;
- deterministic self-test output is byte-identical across repeated processes;
- no secret material appears in mobility metadata, events, logs, or exception messages.

## Out of scope

Do not implement:

- TLS/QUIC;
- IP tunnels;
- 5G Core/RAN integration;
- Wi-Fi integration;
- radio handover algorithms;
- gNB/eNB procedures;
- PHY/MAC scheduling;
- modem control;
- SIM/USIM/IMSI handling;
- distributed federation;
- billing/settlement;
- telemetry platform;
- mobile OS integration;
- packet forwarding implementation.

## PR requirements

The PR body must contain the standard 11 sections established by the repository workflow.

It must explicitly state:

- Work Item: WORK-014;
- dependencies satisfied: WORK-012 and WORK-013;
- WORK-017 is NOT a dependency per ACR-001 and the frozen dependency graph;
- exact architecture/lock sections implemented;
- acceptance criteria mapped to concrete tests/evidence;
- all changed files;
- out-of-scope items;
- full verification results;
- architecture-lock compliance;
- no architecture drift.

Do not modify `spec/architecture.md`, `spec/architecture-lock.md`, or `spec/dependency-graph.md` in the implementation PR.

If implementation appears to require changing any frozen architectural rule, STOP and request an ACR rather than changing the rule locally.

## Architect review gate

The Architect will independently inspect the complete diff. Passing tests or CI does not imply acceptance.

Acceptance requires all of the following:

```text
Session ID survives handover
AND
old/new path transition is auditable
AND
failed handover leaves no half-state
AND
replay cannot bypass validation
AND
concurrency is deterministic
AND
mobility remains below routing/policy/topology authority
AND
transport/access-specific mechanics remain outside the core
AND
all required verification categories pass
```

## Definition of Done

WORK-014 is complete only when an Architect-approved implementation demonstrates that an existing ADCOS logical session can safely transition between independently selected paths while preserving session identity, maintaining auditability, supporting make-before-break where capability permits, failing safely otherwise, and rolling back without corrupting session state — all without introducing dependence on any concrete transport or access technology.
