# ADCOS Implementation Backlog — Work Items

## Status

**FROZEN BACKLOG — Implementation is dependency-driven.**

Each Work Item is independently reviewable. Z.ai must implement only one Work Item at a time unless the Architect explicitly authorizes otherwise. A Work Item is complete only after its PR is reviewed, all requested corrections are resolved, required verification passes, and the Architect explicitly accepts it.

## Work Item Template

Every implementation PR must include:

- Work Item ID/title;
- objective;
- exact architecture sections implemented;
- dependencies satisfied;
- acceptance criteria mapped to tests/evidence;
- repository areas changed;
- explicit out-of-scope statement;
- verification results;
- architectural lock compliance statement;
- no-architecture-drift statement.

---

# Phase 0 — Specification and Governance

### WORK-001 — Protocol specification/governance foundation
Objective: Establish repository structure, specification conventions, versioning policy, change-control process, terminology, and machine-readable schema locations.
Dependencies: none
Acceptance criteria:
- `spec/` contains the four authoritative documents and stable naming conventions.
- Protocol versioning and architecture versioning are distinct.
- Architecture Change Request process is documented.
- Work Item/PR review rules are documented.
- CI can run specification consistency checks.
Required verification: static checks, documentation validation.
Out of scope: protocol runtime implementation.
Definition of done: The repository itself cannot ambiguously identify which specification is authoritative.

### WORK-002 — Core protocol vocabulary and registry model
Objective: Define stable IDs for Node, Adapter, Capability, Link, Path, Session, Resource, Intent, Evidence, Federation, and access profiles.
Dependencies: WORK-001
Acceptance criteria:
- IDs are technology-neutral.
- registries support additive future entries.
- 5G and future IMT entries are adapter/profile IDs, not core domain types.
- unknown extension identifiers are handled safely.
Required verification: schema tests, compatibility tests.
Out of scope: network behavior.
Definition of done: All frozen architecture nouns have versioned machine-readable definitions.

### WORK-003 — Versioned protocol envelope and serialization
Objective: Implement the stable envelope, schema versioning, canonicalization, extension handling, expiration, correlation, and signature metadata.
Dependencies: WORK-002
Acceptance criteria:
- known messages parse deterministically.
- unknown optional fields survive proxying where possible.
- incompatible versions fail safely.
- replay/expiration metadata is validated.
Required verification: golden vectors, fuzz/property tests, compatibility tests.
Out of scope: trust policy and routing.
Definition of done: The wire contract can evolve without a flag day.

### WORK-004 — Cryptographic node identity and credential abstraction
Objective: Implement access-independent NodeID, key lifecycle, credential references, rotation, revocation, and algorithm agility.
Dependencies: WORK-003
Acceptance criteria:
- NodeID survives adapter changes.
- key rotation works without changing NodeID semantics.
- algorithms are negotiated/profiled.
- credential material is never serialized as ordinary topology data.
Required verification: security tests, rotation tests, negative tests.
Out of scope: federation policy.
Definition of done: Nodes have durable cryptographic identity independent of 5G/Wi-Fi/etc.

# Phase 1 — Evidence, Discovery, Topology, Resources

### WORK-005 — Capability statements and negotiation
Objective: Implement signed, versioned capability advertisements, schemas, constraints, validity periods, and negotiation.
Dependencies: WORK-003, WORK-004
Acceptance criteria:
- every capability carries provenance/evidence references.
- capabilities may be withdrawn/expired.
- negotiation can select a common profile.
- unknown optional capabilities are safely ignored.
Required verification: schema, adversarial, compatibility tests.
Out of scope: actual adapter implementations.
Definition of done: Nodes can truthfully and safely describe what they can provide.

### WORK-006 — Peer discovery
Objective: Implement local and bootstrap-assisted discovery independent of access technology.
Dependencies: WORK-004, WORK-005
Acceptance criteria:
- nodes can discover peers over at least one IP-based local path.
- discovery is authenticated.
- duplicate and stale discoveries converge deterministically.
- discovery can operate after upstream Internet loss.
Required verification: integration, duplicate, partition/recovery tests.
Out of scope: global routing.
Definition of done: ADCOS nodes can safely find one another.

### WORK-007 — Evidence-aware topology graph
Objective: Implement independent identity/advertisement/reachability/link dimensions and claim provenance.
Dependencies: WORK-005, WORK-006
Acceptance criteria:
- remote summaries remain claims by the reporter.
- high-value capabilities cannot become authoritative solely through remote summaries.
- topology dimensions are independent in storage and state transitions.
- stale/removed/reachable states converge deterministically.
Required verification: adversarial topology tests, poisoning tests, partition tests.
Out of scope: path optimization.
Definition of done: ADCOS topology is evidence-aware and resistant to basic topology poisoning.

### WORK-008 — Resource model and measurements
Objective: Implement bandwidth, capacity, compute, storage, energy, backhaul, coverage, and service-capacity resource models.
Dependencies: WORK-005, WORK-007
Acceptance criteria:
- resource offers are separable from measured observations.
- resource validity/expiry is supported.
- resource accounting is technology-neutral.
- energy state can be represented.
Required verification: schema, accounting, stale-state tests.
Out of scope: settlement.
Definition of done: The fabric can reason about connectivity as a set of resources.

### WORK-009 — Intent and QoS model
Objective: Implement intent schemas for bandwidth, latency, reliability, locality, energy, cost, privacy, and service constraints.
Dependencies: WORK-008
Acceptance criteria:
- intents describe requirements, not implementation technology.
- constraints support hard and soft preferences.
- unsupported constraints fail explicitly.
- normalized intents are deterministic.
Required verification: schema and policy tests.
Out of scope: route computation.
Definition of done: Applications/operators can ask for connectivity without specifying 5G/Wi-Fi/etc.

### WORK-010 — Policy engine
Objective: Implement policy evaluation for trust, resource access, locality, federation, privacy, emergency/service priority, and energy reserve.
Dependencies: WORK-004, WORK-008, WORK-009
Acceptance criteria:
- policy decisions are explicit and auditable.
- deny-by-default applies to privileged operations.
- emergency/local policies can be configured independently.
- policies do not mutate topology authority.
Required verification: authorization and conflict-resolution tests.
Out of scope: identity cryptography.
Definition of done: Resource/session decisions can be policy-governed.

# Phase 2 — Routing, Sessions, Mobility, Federation

### WORK-011 — Path computation and routing engine
Objective: Implement candidate path construction and policy/resource-aware scoring.
Dependencies: WORK-007, WORK-008, WORK-009, WORK-010
Acceptance criteria:
- routing considers reachability, performance, trust, cost, locality, energy, and evidence confidence.
- route calculations are deterministic for the same inputs.
- alternate paths can be retained.
- no routing code branches on 5G/6G names.
Required verification: graph tests, fault-injection, performance tests.
Out of scope: transport implementation.
Definition of done: ADCOS can select paths based on intent, not access generation.

### WORK-012 — Logical sessions
Objective: Implement access-independent session identity, path bindings, lifecycle, renewal, and teardown.
Dependencies: WORK-003, WORK-004, WORK-011
Acceptance criteria:
- Session ID does not encode access technology.
- path changes do not require a new Session ID.
- session state is replay-safe and expiry-aware.
- session policy is enforced.
Required verification: lifecycle, restart, failover tests.
Out of scope: access-specific bearer control.
Definition of done: connectivity sessions survive the replacement of one underlying access path where supported.

### WORK-013 — Multipath session manager
Objective: Support multiple candidate/active paths for one logical session.
Dependencies: WORK-011, WORK-012
Acceptance criteria:
- multiple access paths can coexist.
- traffic policy can select active/standby/striped modes.
- loss of one path does not necessarily terminate the session.
- transport implementation remains replaceable.
Required verification: fault-injection, packet-loss, reorder, concurrency tests.
Out of scope: one mandatory multipath transport protocol.
Definition of done: multipath exists as a stable session capability.

### WORK-014 — Mobility and handover manager
Objective: Implement session-level mobility, candidate path reservation, make-before-break when possible, and rollback.
Dependencies: WORK-012, WORK-013, WORK-017
Acceptance criteria:
- session identity survives supported handover.
- old/new path transition is auditable.
- failed handovers roll back safely.
- access-specific mechanics remain in adapters.
Required verification: mobility simulation, fault-injection, timing tests.
Out of scope: radio PHY algorithms.
Definition of done: Mobility is an ADCOS session concern, not a cell-specific core concern.

### WORK-015 — Federation protocol
Objective: Implement inter-domain peering, trust scopes, route/capability exchange, revocation, and federation lifecycle.
Dependencies: WORK-004, WORK-005, WORK-007, WORK-010, WORK-011
Acceptance criteria:
- federation is scoped and revocable.
- peer-domain membership does not imply node-level trust.
- capability/resource export policies are explicit.
- federation can be removed without deleting local state.
Required verification: cross-domain security and isolation tests.
Out of scope: economic settlement implementation.
Definition of done: independently operated domains can cooperate safely.

# Phase 3 — Adapter and Transport Framework

### WORK-016 — Adapter SDK/runtime
Objective: Implement the generic Adapter contract, lifecycle, health, capability exposure, resource mapping, session binding, and sandboxing boundary.
Dependencies: WORK-003, WORK-005, WORK-012
Acceptance criteria:
- adapters depend on stable core interfaces.
- core does not depend on adapter implementations.
- adapter failures are isolated.
- adapter identity is distinct from NodeID.
Required verification: contract tests, failure-isolation tests.
Out of scope: individual access technologies.
Definition of done: New access technologies can be added without modifying core semantics.

### WORK-017 — Secure transport profiles
Objective: Implement transport mappings for secure control/user paths, starting with TLS 1.3/QUIC and standard IP tunnels where required.
Dependencies: WORK-003, WORK-004, WORK-012
Acceptance criteria:
- session security is independent of access technology.
- keys are bound to session/identity policy.
- transport can be replaced behind the transport interface.
- replay and downgrade attacks are tested.
Required verification: security, interoperability, downgrade tests.
Out of scope: application protocols.
Definition of done: ADCOS sessions have secure transport mappings.

### WORK-018 — IPv6 and IP integration boundary
Objective: Define how ADCOS sessions map to standard IP networks, including IPv6-first operation, local routing, and external gateway integration.
Dependencies: WORK-012, WORK-017
Acceptance criteria:
- standard IPv6 connectivity works end to end.
- ADCOS does not require applications to understand ADCOS internals.
- NAT/IPv4 compatibility is adapter/policy behavior, not core identity.
Required verification: packet-path and interoperability tests.
Out of scope: cellular RAN implementation.
Definition of done: ADCOS can carry ordinary Internet traffic.

# Phase 4 — 5G, Non-3GPP, Backhaul, Edge

### WORK-019 — 5G Core integration adapter
Objective: Integrate a standards-compliant 5G Core through an adapter boundary, initially targeting Open5GS.
Dependencies: WORK-016, WORK-017, WORK-018
Acceptance criteria:
- 5G Core state remains outside ADCOS core authority.
- sessions can map between ADCOS and 5G Core semantics.
- 5G authentication credentials remain access-specific.
- core remains usable with another 5G implementation.
Required verification: 5G interoperability tests.
Out of scope: 5G radio PHY.
Definition of done: ADCOS can interoperate with an open 5G Core.

### WORK-020 — 5G RAN/gNB adapter
Objective: Integrate open 5G RAN implementations, initially OCUDU and/or OpenAirInterface, including CU/DU/RU boundary mapping.
Dependencies: WORK-019
Acceptance criteria:
- ADCOS core imports no vendor/Open RAN implementation types.
- RAN capability/health/resource state is mapped through adapters.
- RAN failure is isolated from core state.
- at least one SDR-based lab topology works.
Required verification: end-to-end lab tests.
Out of scope: new PHY implementation.
Definition of done: ADCOS can provision/use a standards-compliant 5G access path.

### WORK-021 — Wi-Fi/non-3GPP access adapter
Objective: Integrate Wi-Fi and non-3GPP access, including a 5G Core-compatible path where required.
Dependencies: WORK-018, WORK-019
Acceptance criteria:
- same ADCOS session model can use Wi-Fi and 5G.
- N3IWF/TNGF or equivalent standards-based mechanisms remain behind the adapter boundary.
- access change is transparent to session authority where supported.
Required verification: mixed-access integration tests.
Out of scope: Wi-Fi chipset firmware.
Definition of done: 5G and Wi-Fi are interchangeable access candidates for the same fabric.

### WORK-022 — Ethernet/fiber/microwave/satellite adapter family
Objective: Add generic high-capacity, fixed, and long-haul access/backhaul adapters.
Dependencies: WORK-016, WORK-018
Acceptance criteria:
- link metrics and resource state enter the same model as cellular/wireless paths.
- adapter-specific APIs remain isolated.
- backhaul paths can be selected by routing.
Required verification: multi-link integration tests.
Out of scope: modem firmware.
Definition of done: wired and non-cellular backhaul become first-class fabric resources.

### WORK-023 — Mesh, IAB, relay, and store-and-forward backhaul
Objective: Implement multi-hop connectivity mechanisms, including integration points for 3GPP IAB/sidelink relay and generic mesh/store-and-forward paths.
Dependencies: WORK-011, WORK-013, WORK-022
Acceptance criteria:
- multi-hop paths are represented as ordinary Paths.
- node/reporter evidence is preserved across hops.
- disconnected operation can continue with configured store-and-forward semantics.
Required verification: partition/recovery, multi-hop, loop-prevention tests.
Out of scope: proprietary mesh PHY.
Definition of done: connectivity can extend through multiple relays and intermittent links.

### WORK-024 — Distributed core / local breakout / UPF integration
Objective: Implement distributed user-plane and local-service placement.
Dependencies: WORK-018, WORK-019, WORK-021, WORK-022
Acceptance criteria:
- local traffic can remain local.
- remote gateway failover works.
- 5G UPF and generic IP gateway functions can coexist behind adapters.
- policy determines local vs remote breakout.
Required verification: failover, latency, locality, partition tests.
Definition of done: the network can operate as a distributed access/core fabric.

### WORK-025 — Service registry and edge compute
Objective: Implement local service discovery, service advertisement, service policy, and edge execution hooks.
Dependencies: WORK-009, WORK-010, WORK-015, WORK-024
Acceptance criteria:
- services are discoverable by capability and policy.
- local services remain available during upstream failure where configured.
- service identity is separate from node identity.
Required verification: local-first integration tests.
Out of scope: full application platform.
Definition of done: connectivity and edge services form one coherent fabric.

# Phase 5 — Resilience, Security, Operations

### WORK-026 — Telemetry and observability
Objective: Implement standardized measurements for links, paths, sessions, resources, energy, and adapter health.
Dependencies: WORK-007, WORK-008, WORK-011, WORK-012, WORK-016
Acceptance criteria:
- measurements carry source, time, confidence, and validity.
- telemetry cannot silently become topology authority without policy.
- privacy controls exist.
Required verification: schema, privacy, stale-data tests.
Definition of done: operators can explain why the network made a decision.

### WORK-027 — Energy-aware control and resilience
Objective: Integrate power, battery, thermal, degraded-backhaul, and offline policies into scheduling/routing.
Dependencies: WORK-008, WORK-010, WORK-011, WORK-024, WORK-026
Acceptance criteria:
- energy state can influence path selection.
- survival profile can protect essential services.
- node restart/rejoin is deterministic.
- intermittent upstream connectivity is supported.
Required verification: power simulation, partition/recovery tests.
Definition of done: ADCOS is practical for solar/off-grid and unstable infrastructure environments.

### WORK-028 — Threat model and security hardening
Objective: Produce the threat model, abuse cases, security controls, negative tests, and secure defaults across the full stack.
Dependencies: WORK-004, WORK-005, WORK-007, WORK-010, WORK-015, WORK-017
Acceptance criteria:
- compromised node model is documented.
- replay, spoofing, poisoning, downgrade, privilege escalation, route hijack, capability inflation, and federation abuse are tested.
- privileged operations are auditable.
Required verification: security test suite and threat-model review.
Definition of done: security is an executable property, not documentation only.

### WORK-029 — Upgrade, rollback, and compatibility manager
Objective: Implement protocol/software capability negotiation, rolling upgrades, downgrade protection, schema compatibility, and rollback.
Dependencies: WORK-003, WORK-005, WORK-016, WORK-026
Acceptance criteria:
- mixed-version nodes can coexist where compatibility permits.
- unsupported versions fail safely.
- rollback does not corrupt identity/session state.
- future access profiles can be introduced without core replacement.
Required verification: mixed-version integration tests.
Definition of done: ADCOS can evolve without a network-wide flag day.

### WORK-030 — Management API and operator control plane
Objective: Implement read/write APIs for node, topology, resources, intents, federation, sessions, policies, and lifecycle.
Dependencies: WORK-010, WORK-011, WORK-012, WORK-015, WORK-026
Acceptance criteria:
- authorization is server-side.
- APIs are idempotent where required.
- state changes are auditable.
- management APIs cannot bypass core authorities.
Required verification: API, authorization, audit tests.
Definition of done: operators can run the network without editing internal state.

# Phase 6 — Reference Implementations and Interoperability

### WORK-031 — Deterministic simulator
Objective: Build a simulation environment for nodes, links, failures, mobility, energy, and routing.
Dependencies: WORK-007, WORK-011, WORK-012, WORK-013, WORK-027
Acceptance criteria:
- scenarios are deterministic/replayable.
- partitions and failures can be injected.
- routing decisions are inspectable.
Required verification: scenario suite.
Definition of done: Architect can evaluate protocol behavior before RF hardware deployment.

### WORK-032 — Core conformance suite and golden vectors
Objective: Create machine-checkable conformance tests for envelopes, identity, capabilities, topology, routing, session, federation, and security semantics.
Dependencies: WORK-003, WORK-004, WORK-005, WORK-007, WORK-011, WORK-012, WORK-015, WORK-017
Acceptance criteria:
- golden wire vectors exist.
- negative/security vectors exist.
- extension/future-version behavior is tested.
Definition of done: independent implementations can validate core protocol compatibility.

### WORK-033 — Linux reference Agent
Objective: Build the complete reference ADCOS Agent for Linux/x86_64 and ARM64.
Dependencies: WORK-016, WORK-017, WORK-018, WORK-026, WORK-029, WORK-030, WORK-032
Acceptance criteria:
- endpoint, relay, gateway, and edge roles operate.
- ARM64 works.
- agent survives restart and reconnect.
- no access-specific assumptions in core.
Required verification: full integration suite.
Definition of done: ADCOS is runnable on ordinary Linux hardware.

### WORK-034 — Raspberry Pi reference node
Objective: Package a low-cost experimental community node using Raspberry Pi-class ARM hardware.
Dependencies: WORK-033, WORK-020, WORK-021, WORK-022, WORK-023, WORK-024
Acceptance criteria:
- node can serve as relay/gateway/edge node.
- optional SDR/5G adapter works in laboratory conditions.
- metrics and energy state are visible.
Definition of done: a low-cost reference node demonstrates the architecture.

### WORK-035 — Android endpoint integration
Objective: Implement the Android-side ADCOS endpoint/companion capabilities that platform APIs permit.
Dependencies: WORK-012, WORK-013, WORK-018, WORK-033
Acceptance criteria:
- phone can participate through available Wi-Fi, cellular, tethering, VPN/tunnel, and supported local links.
- no unsupported modem-control assumptions are made.
- future open-radio APIs can be inserted through adapters.
Definition of done: ordinary phones can consume and participate in ADCOS connectivity without pretending to be arbitrary gNBs.

### WORK-036 — Network-in-a-Box reference deployment
Objective: Produce a single-box community deployment with compute, core, management, optional 5G access, Wi-Fi, local services, and backhaul.
Dependencies: WORK-024, WORK-025, WORK-030, WORK-033, WORK-034
Acceptance criteria:
- install/boot/discover/configure workflow is automated.
- offline/local-first mode works.
- failure recovery works.
Definition of done: a small community can deploy a coherent local network with minimal specialist intervention.

### WORK-037 — Open RAN/Core interoperability profile
Objective: Validate ADCOS against current open-source 5G stacks.
Dependencies: WORK-019, WORK-020, WORK-021, WORK-032, WORK-033
Acceptance criteria:
- at least one Open5GS path works.
- at least one OCUDU/OAI path works.
- adapter replacement does not alter core session semantics.
Definition of done: ADCOS proves real interoperability rather than a mocked architecture.

# Phase 7 — 6G/Future-Proofing and Scale

### WORK-038 — Future-IMT/6G adapter contract validation
Objective: Validate that a hypothetical IMT-2030/6G access implementation can be integrated without core protocol changes.
Dependencies: WORK-016, WORK-029, WORK-032, WORK-033
Acceptance criteria:
- mock future access profile implements Adapter contract.
- no core module changes when swapping the mock profile.
- new capability types can be added without breaking old nodes.
- new mobility/radio objects can be mapped through adapter extensions.
Definition of done: future-generation compatibility is demonstrated by executable tests, not prose.

### WORK-039 — Federated multi-community scale test
Objective: Validate thousands of logical nodes/domains in simulation and selected hardware deployments.
Dependencies: WORK-015, WORK-031, WORK-033, WORK-036
Acceptance criteria:
- topology convergence remains bounded.
- routing and resource decisions remain explainable.
- compromised/failed domains do not collapse the global fabric.
Definition of done: architecture scales beyond a single community.

### WORK-040 — Pilot-grade community deployment
Objective: Deliver an end-to-end rural/community deployment profile with solar/off-grid operation, local services, mixed access, open 5G, and external backhaul.
Dependencies: WORK-027, WORK-028, WORK-036, WORK-037, WORK-039
Acceptance criteria:
- deployment is reproducible.
- operational telemetry exists.
- failure recovery is documented and tested.
- compliance/spectrum constraints are externalized to deployment policy.
Definition of done: ADCOS is demonstrated as a credible deployable network architecture rather than a laboratory protocol.
