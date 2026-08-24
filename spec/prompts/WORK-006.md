# ADCOS Architect Handoff — WORK-006

## Status

**ACTIVE — Architect implementation handoff**

This prompt authorizes Z.ai to implement exactly WORK-006 from the frozen ADCOS architecture. The authoritative sources are, in order: `spec/architecture.md`, `spec/architecture-lock.md`, `spec/work-items.md`, `spec/dependency-graph.md`, and the Architect-accepted implementations already merged to `main` for WORK-001 through WORK-005.

Do not modify any frozen architecture document, architecture lock, work-item document, dependency graph, or prior Work Item prompt.

## Work Item

**WORK-006 — Peer discovery**

Dependencies: WORK-004, WORK-005. Both are Architect-accepted and merged to `main` before implementation begins.

Objective: implement authenticated, access-independent local and bootstrap-assisted peer discovery with deterministic duplicate/stale convergence and operation after upstream Internet loss.

## Architectural intent

Discovery answers one question:

> Which ADCOS participants are currently discoverable through a reachable local/bootstrap mechanism?

Discovery does **not** establish trust, topology authority, routing, reachability truth, resource availability, authorization, or federation membership. Those decisions belong to later layers.

The distinction is mandatory:

```text
Discovery observation
        ≠ identity
        ≠ trust
        ≠ topology authority
        ≠ route
        ≠ resource availability
```

A discovered peer is therefore an authenticated observation/record that a Node was observed through a discovery mechanism at a particular time/context. It must carry enough provenance and freshness metadata for WORK-007 to consume it without silently promoting it to authoritative topology.

## Scope

Implement only discovery and its local state boundary.

### In scope

1. Discovery record/message schema(s).
2. Local authenticated peer discovery over at least one IP-based local path.
3. Optional bootstrap-assisted discovery where a configured bootstrap source provides candidate peers, explicitly marked as bootstrap-derived observations.
4. Discovery identity binding through accepted WORK-004 NodeID/credential abstractions.
5. Capability advertisement reference/summary sufficient to identify what was observed, without duplicating WORK-005 capability vocabulary or semantics.
6. Freshness / expiration / stale detection using accepted WORK-003 temporal primitives.
7. Duplicate observation convergence with deterministic merge/update rules.
8. Local discovery state suitable for later WORK-007 topology ingestion.
9. Operation when upstream Internet connectivity is unavailable.
10. Recovery after partitions / duplicate observations / stale announcements.
11. Replay and freshness defenses appropriate to discovery records.
12. Deterministic serialization and protocol-envelope integration using WORK-003.
13. Adversarial, duplicate, partition/recovery, replay, expiration, and deterministic self-tests.
14. Tooling/CI integration required to make the above mechanically verifiable.
15. Boundary documentation.

### Explicitly out of scope — forbidden

Do NOT implement:

- WORK-007 topology graph or topology authority;
- path computation/routing (WORK-011);
- resource measurement/accounting (WORK-008);
- intent/QoS (WORK-009);
- policy/authorization engine (WORK-010);
- federation protocol/policy (WORK-015);
- generic Adapter runtime/SDK (WORK-016);
- secure transport implementation beyond what is minimally required to establish the discovery channel; the reusable transport belongs to WORK-017;
- IPv6/IP data-plane integration beyond the minimal local discovery substrate; WORK-018 owns broader IP integration;
- 5G/Wi-Fi/6G adapters or vendor/RAN integration;
- mesh/IAB/relay functionality (WORK-023);
- distributed revocation propagation;
- databases/persistent production storage;
- reputation/attestation policy;
- blockchain/token economics;
- UI/application logic.

Do not invent a second identity, capability, evidence, or envelope model. Reuse WORK-003/004/005 boundaries.

## Non-negotiable architecture rules

### 1. Access independence
Discovery logic must not branch on 5G, Wi-Fi, LTE, 6G, satellite, or vendor names. The discovery substrate is IP-based for WORK-006; access-specific discovery integration belongs behind later adapters.

### 2. Authentication without trust
A discovery record must be cryptographically attributable to the node that generated it, but successful authentication does not imply trust or authorization.

The implementation must preserve:

```text
authenticated peer observation
        ↓
known identity reference
        ↓
later topology/trust evaluation
```

not:

```text
authenticated discovery
        ↓
trusted topology fact
```

### 3. Discovery is not topology
The discovery package must not expose APIs whose semantics imply authoritative reachability, link state, gateway status, route validity, or resource availability.

A discovery result should be consumable by WORK-007 as an observation/claim with provenance and freshness.

### 4. Identity binding
Use the canonical WORK-004 NodeID parser and credential/provenance machinery. Do not duplicate NodeID syntax. Reject malformed NodeIDs and reject messages where the authenticated signing credential does not belong to the declared sender NodeID.

### 5. Capability references only
Discovery may carry references or a bounded snapshot of the peer's advertised capabilities from WORK-005. Do not duplicate the capability registry or reinterpret a capability statement as truth.

### 6. Deterministic convergence
For identical observations presented in different orders, the local discovery state must converge to byte-identical deterministic state.

No behavior may depend on hash-map iteration order, random values, local locale, or nondeterministic provider ordering.

### 7. Freshness / stale semantics
Discovery records require explicit issued/fresh-until or equivalent timing semantics. A stale discovery is not silently equivalent to current discovery.

Expiration and stale classification must be deterministic at an injected evaluation instant. Do not use wall-clock time directly inside core discovery semantics.

### 8. Duplicate observations
Repeated equivalent observations must be idempotent.

Conflicting observations for the same NodeID must not silently overwrite one another using arrival order. Define a deterministic merge rule based only on signed/provenance-bearing fields and timestamps/sequence information within the discovery contract.

### 9. Replay resistance
A previously valid discovery announcement must not be able to refresh freshness merely by replaying an old message. Use explicit issuance/freshness/sequence semantics appropriate to the frozen envelope model.

Do not implement a global anti-replay database; local bounded state is sufficient for WORK-006.

### 10. Upstream-independent operation
Discovery must operate when the node has no upstream Internet access, provided a local IP-based path exists.

Bootstrap-assisted discovery is additive: failure of the bootstrap source must not disable local discovery.

### 11. Local-first behavior
At minimum support:

```text
local peer discovery
        ↓
optional bootstrap assistance
        ↓
no Internet required for local convergence
```

Do not require a central registry or cloud service for basic operation.

### 12. Future-proofing
The discovery protocol must not assume today's access-generation vocabulary. Future 6G/IMT-2030/future access nodes use exactly the same discovery contract; their access details are capability/profile data.

## Required conceptual model

A discovery observation should be representable approximately as:

```text
DiscoveryObservation
  observation_id
  sender_node_id
  observed_node_id
  observed_at / issued_at
  freshness_until
  sequence / generation marker
  source_type = local | bootstrap
  source_context
  advertised_capability_references (optional)
  observed_endpoints (bounded, technology-neutral)
  signature
```

The exact field names may follow repository conventions, but do not add trust scores, route scores, topology states, resource measurements, or authorization results.

## Local protocol requirement

The implementation must provide one concrete IP-based local discovery mechanism for Linux/reference testing.

A minimal acceptable reference design is a UDP-based local discovery exchange bound to a configurable local interface/address scope, using the ADCOS envelope and authenticated signed observation content.

The implementation may use multicast, broadcast, a configured neighbor seed, or another IP-local mechanism, provided that:

- it is standards-compliant and documented;
- it does not require Internet access;
- it can be exercised deterministically in tests;
- transport specifics remain beneath the discovery contract.

Do not implement a complete service mesh or general-purpose routing layer.

## Bootstrap-assisted discovery

Bootstrap discovery is optional in the sense that it supplements local discovery, but its semantics must be represented explicitly if implemented.

Bootstrap-sourced records must carry a source/provenance marker showing:

```text
source_type = bootstrap
```

and must not be treated as equivalent to directly observed local peers merely because they came from a configured bootstrap node.

A bootstrap node is not automatically a trusted authority over the discovered node set.

## Duplicate/convergence semantics

Define and test deterministic behavior for at least:

1. exact duplicate observation;
2. same observation received in different order;
3. newer observation replacing older observation;
4. stale observation arriving after newer observation;
5. conflicting observation with same NodeID but different observation sequence/generation;
6. bootstrap observation versus direct local observation;
7. local partition followed by reconnection and duplicate exchange.

The merge result must be deterministic and preserve provenance/source context.

## Replay/freshness semantics

At minimum test:

```text
fresh valid observation             -> accepted
expired observation                -> stale/not-current
future-dated beyond allowed skew   -> rejected
replayed old observation           -> does not refresh freshness
same sequence different content    -> rejected unless the contract explicitly permits deterministic replacement
newer valid sequence               -> accepted
```

Reusing WORK-003 temporal/skew primitives is required where applicable.

## Security boundary

WORK-006 may verify that a discovery message is attributable to the sender NodeID and structurally valid.

It must NOT decide:

- whether the sender is trustworthy;
- whether the observed peer is authorized;
- whether a gateway claim is true;
- whether a discovered peer should be preferred for routing;
- whether a capability is actually available;
- whether two domains should federate.

Those are later layers.

## Required tests

Z.ai must implement deterministic tests covering at least:

1. local peer discovery succeeds over a loopback/local IP transport;
2. discovery succeeds without any upstream Internet requirement;
3. authenticated valid observation accepted;
4. forged sender identity rejected;
5. credential/NodeID mismatch rejected;
6. exact duplicate is idempotent;
7. observation arrival order does not change final state;
8. newer sequence/generation replaces older state deterministically;
9. stale/expired observation is not current;
10. replay of an old observation cannot refresh freshness;
11. conflicting same-sequence content fails closed;
12. malformed discovery envelope fails safely;
13. bootstrap-sourced discovery is marked distinctly from local discovery;
14. bootstrap failure does not disable local discovery;
15. partition/recovery convergence is deterministic;
16. capability references remain opaque and are never copied into a second registry;
17. discovery does not expose trust/authorization/topology authority fields;
18. future access profile identifiers can appear as data without discovery-core changes;
19. seeded fuzz/mutation inputs never crash the discovery parser/state machine;
20. repeated self-test runs are byte-identical.

Where a test touches an actual socket, use loopback/private local addresses and deterministic time injection; no external Internet access is permitted or required for the suite.

## Verification requirements

Before opening the PR, Z.ai must run:

```bash
python3 tools/spec_check.py
python3 tools/spec_check_selftest.py
python3 tools/schema_check.py
python3 tools/schema_selftest.py
python3 tools/envelope_selftest.py
python3 tools/identity_selftest.py
python3 tools/capability_selftest.py
python3 tools/discovery_selftest.py
python3 -m py_compile ...
python3 -m mypy ...
```

Also prove:

- deterministic output across repeat runs;
- frozen architecture/lock/backlog/dependency documents are byte-identical to `main`;
- prior Work Item prompts remain untouched;
- no 5G/6G/vendor SDK imports;
- no second identity/capability/evidence vocabulary;
- no secret/private-key material in fixtures or serialized discovery objects;
- no external network dependency in tests.

CI must run the complete accumulated suite plus the new discovery suite.

## Acceptance standard

WORK-006 is complete only when:

- ADCOS nodes can safely find one another over an IP-based local mechanism;
- authentication binds observations to the correct NodeID;
- duplicate/stale/replayed observations converge deterministically;
- local discovery continues without upstream Internet;
- bootstrap assistance is explicitly non-authoritative;
- discovery remains only an observation mechanism and does not become topology/trust/routing policy;
- all required tests and CI pass;
- no frozen architecture drift exists;
- the Architect explicitly accepts the PR.

## PR requirements

The PR must include exactly these sections, in order:

1. WORK-006
2. Objective
3. Architecture sections implemented
4. Dependencies
5. Acceptance criteria mapping
6. Verification
7. Files changed
8. Out of scope
9. Architecture lock compliance
10. No architecture drift
11. Known limitations

The PR must remain open and unmerged until Architect acceptance.

**Do not modify frozen specification documents.**
**Do not implement WORK-007 or any downstream Work Item.**
