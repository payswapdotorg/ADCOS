# ADCOS Architecture Lock

## Status

**FROZEN**

This document is the compact, enforceable set of architectural invariants for ADCOS. If a proposed implementation conflicts with this document or `spec/architecture.md`, the implementation is wrong until the architecture is formally changed through the architecture-change process.

---

## 1. Authority

- `spec/architecture.md` is the full architectural specification.
- `spec/architecture-lock.md` contains the non-negotiable invariants.
- `spec/work-items.md` is the only approved implementation backlog.
- `spec/dependency-graph.md` defines implementation sequencing.
- Z.ai is the implementation agent, not the architecture authority.
- The LLM Architect is the architecture/review authority.
- A PR is not complete merely because tests pass; it is complete only when it conforms to the frozen architecture and its Work Item definition of done.

---

## 2. Core Architectural Locks

### LOCK-001 — ADCOS is access-technology neutral
The ADCOS core must not encode 5G, LTE, Wi-Fi, 6G, satellite, or any single access technology as a required core abstraction.

### LOCK-002 — 5G is an adapter
5G NR is implemented through an access adapter. 3GPP RAN/core functions remain outside the ADCOS core domain.

### LOCK-003 — 6G is also an adapter
Future IMT-2030/6G and later technologies MUST enter through the same access abstraction. The core will not be rewritten for a new radio generation.

### LOCK-004 — No arbitrary-phone-gNB fiction
The architecture never assumes a normal iOS/Android application can control the phone cellular baseband or act as a gNB. Phones are endpoints unless suitable hardware/API capabilities exist.

### LOCK-005 — Node identity is access independent
Node identity must survive a change from 5G to Wi-Fi to satellite to future radio.

### LOCK-006 — Session identity is access independent
A logical session must not be identified by a cell ID, bearer ID, radio technology, or vendor-specific modem identifier.

### LOCK-007 — Capability negotiation is normative
Peers advertise and negotiate capabilities. Core code must not assume capabilities that have not been negotiated or evidenced.

### LOCK-008 — Claims have provenance
A remote node's statement about another node is a claim by the reporting node. It is never automatically equivalent to a direct statement or observation by the target node.

### LOCK-009 — Independent topology dimensions
Identity, advertisement freshness, reachability, link state, and evidence provenance are distinct state dimensions.

### LOCK-010 — No blockchain requirement
The networking protocol must function without blockchain, tokens, or a consensus network.

### LOCK-011 — Distributed by design
The architecture must permit control, user plane, edge services, and gateways to exist centrally, regionally, locally, or in multiple cooperating nodes.

### LOCK-012 — Local-first resilience
Loss of upstream Internet must not inherently destroy local network operation.

### LOCK-013 — Graceful degradation
Failure of one access, gateway, backhaul, energy source, or node must be handled by alternate paths where available.

### LOCK-014 — Future protocol evolution
Wire messages are versioned, extension-capable, and cryptographically protected. No protocol component may rely on a fixed field list that prevents additive evolution.

### LOCK-015 — Cryptographic agility
Cryptographic algorithms are negotiated/profiled. Algorithm identifiers must not be hard-coded into core semantics.

### LOCK-016 — Provider isolation
External RAN, core, modem, SDR, cloud, routing, and management implementations remain behind adapter/provider interfaces.

### LOCK-017 — No vendor authority
No vendor's API or implementation state is authoritative for ADCOS state merely because it is a vendor component.

### LOCK-018 — Standard leverage over reinvention
Where a standards-based primitive exists and satisfies the requirement, ADCOS uses it rather than defining a competing primitive.

### LOCK-019 — Intent over implementation detail
The high-level API describes desired connectivity properties; routing and adapter implementations determine how to satisfy them.

### LOCK-020 — Multipath is a capability
The protocol supports multi-path sessions, but applications are not coupled to one multipath implementation.

### LOCK-021 — Mobility is session-level
Mobility changes access paths while preserving logical session state where policy and capabilities allow.

### LOCK-022 — Security is zero-trust
A node is not trusted merely because it is inside a network, federation, subnet, or geographic area.

### LOCK-023 — No secret leakage
Credentials, private keys, modem secrets, operator secrets, and subscriber secrets must never be treated as ordinary topology/resource metadata.

### LOCK-024 — Conformance is architectural
A component cannot be declared conformant solely because it interoperates with 5G; it must also satisfy ADCOS core semantics and boundaries.

### LOCK-025 — Linux-first does not mean Linux-dependent
Linux/Rust are reference implementation choices, not wire-protocol assumptions.

---

## 3. Module Ownership

- `/protocol` owns protocol envelope, serialization contracts, message schemas, versioning, and registries.
- `/identity` owns node identity and credential references.
- `/trust` owns trust policy, authorization evidence, revocation, and attestation integration.
- `/capabilities` owns capability statements and negotiation.
- `/discovery` owns peer discovery.
- `/topology` owns topology state and evidence provenance.
- `/resources` owns resource models and admission.
- `/intent` owns intent schemas and normalization.
- `/policy` owns policy evaluation.
- `/routing` owns path computation and selection.
- `/session` owns logical connectivity sessions.
- `/mobility` owns session migration and handover.
- `/federation` owns inter-domain relationships.
- `/adapters` owns access/provider-specific implementations.
- `/transport` owns secure transport mappings.
- `/services` and `/edge` own service discovery/local service execution boundaries.
- `/telemetry` owns observations and operational measurements.
- `/management` owns lifecycle/control APIs.
- `/conformance` owns conformance testing.
- `/simulator` owns deterministic network simulation.

---

## 4. Import/Dependency Locks

- Core modules must not import provider SDKs.
- Core modules must not import 3GPP-specific RAN/CN implementation types.
- Core modules must not import Android/iOS SDKs.
- Adapter modules may depend on core contracts, never the reverse.
- UI/CLI code may call management APIs but must not implement protocol authority independently.
- Test doubles must implement the same interfaces used by real adapters.
- No duplicate identity authority, session authority, or topology authority is permitted.

---

## 5. Authority Rules

### Identity authority
The cryptographic identity subsystem is authoritative for NodeID and credential state.

### Topology authority
The topology subsystem is authoritative for ADCOS topology state and its evidence model.

### Session authority
The session subsystem is authoritative for logical sessions.

### Routing authority
The route engine is authoritative for selected ADCOS paths, subject to policy.

### Adapter authority
An adapter is authoritative only for the state of the technology it controls, not for ADCOS-wide state.

### External technology authority
3GPP/Open RAN/IP protocols remain authoritative for their own wire-level domains; ADCOS maps their state into ADCOS contracts.

---

## 6. Change Control

A frozen architecture change requires:

1. an Architecture Change Request;
2. explicit statement of affected invariants;
3. compatibility analysis;
4. impact on work items and dependencies;
5. migration/rollback plan;
6. architect approval;
7. new architecture version;
8. updated architecture lock and dependency graph.

No Work Item may silently modify a frozen rule.

---

## 7. Implementation Gate

Every PR must answer:

- Which Work Item does this implement?
- Which frozen architecture sections does it implement?
- Which architecture locks does it touch?
- What new protocol or domain authority is introduced?
- Does any access-specific dependency leak into core?
- Are tests proving the lock rather than merely exercising code?
- Are failure and recovery semantics tested?
- Are compatibility and future-extension semantics preserved?

A PR that cannot answer these questions is not ready for approval.
