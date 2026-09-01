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
Dependencies: WORK-012, WORK-013
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
- mixed-version nodes can coexist.
- incompatible versions fail closed.
- upgrades can be staged and rolled back.
- schema migrations are reversible.
Required verification: mixed-version integration tests.
Definition of done: ADCOS can evolve without a flag day.

### WORK-030 — Management API
Objective: Implement management, configuration, audit, and operational control APIs.
Dependencies: WORK-010, WORK-011, WORK-012, WORK-015, WORK-026
Acceptance criteria:
- privileged actions require explicit policy.
- audit logs are immutable or tamper-evident.
- APIs cannot bypass core authority boundaries.
Required verification: API security, audit, RBAC tests.
Definition of done: ADCOS can be operated as a real network platform.

# Phase 6 — Executable reference platform

### WORK-031 — Network and behavior simulator
Objective: Build a deterministic simulator for nodes, links, failures, resources, mobility, and policies.
Dependencies: WORK-007, WORK-011, WORK-012, WORK-013, WORK-027
Acceptance criteria:
- scenarios are reproducible.
- failures can be injected.
- topology and policy behavior can be observed.
- simulation does not alter core semantics.
Required verification: deterministic scenario tests.
Definition of done: ADCOS can be tested at scale without physical infrastructure.

### WORK-032 — Conformance suite
Objective: Build protocol/adapter conformance tests for all frozen contracts.
Dependencies: WORK-003, WORK-004, WORK-005, WORK-007, WORK-011, WORK-012, WORK-015, WORK-017, WORK-016
Acceptance criteria:
- known-good and known-bad vectors exist.
- adapters can self-test against stable contracts.
- interoperability failures are diagnosable.
Required verification: complete conformance matrix.
Definition of done: independent implementations can prove conformance.

### WORK-033 — Linux Agent
Objective: Build a Linux reference Agent implementing the core node runtime and initial adapters.
Dependencies: WORK-016, WORK-017, WORK-018, WORK-026, WORK-029, WORK-030, WORK-032
Acceptance criteria:
- node can run headless.
- multiple network interfaces can be exposed as adapters.
- sessions can be established and monitored.
- logs/metrics are available.
Required verification: end-to-end Linux tests.
Definition of done: a general-purpose computer can participate in ADCOS.

# Phase 7 — Hardware/device profiles

### WORK-034 — Raspberry Pi / low-power gateway
Objective: Optimize the Linux Agent for Raspberry Pi and similar edge hardware.
Dependencies: WORK-020, WORK-021, WORK-022, WORK-023, WORK-024, WORK-033
Acceptance criteria:
- low-resource operation.
- Ethernet/Wi-Fi/cellular adapters can coexist.
- device can operate as relay/gateway.
Required verification: hardware integration.
Definition of done: inexpensive edge hardware can act as ADCOS infrastructure.

### WORK-035 — Android/mobile Agent
Objective: Implement mobile participation with user policy, identity, session continuity, background limitations, and local discovery.
Dependencies: WORK-012, WORK-013, WORK-018, WORK-033
Acceptance criteria:
- mobile device participates without changing core semantics.
- user-controlled resource sharing.
- handover and offline behavior are supported within OS limits.
Required verification: mobile lifecycle tests.
Definition of done: phones can participate as clients, relays, or gateways where permitted.

### WORK-036 — Network-in-a-Box
Objective: Package ADCOS as an autonomous local network appliance for community or emergency deployment.
Dependencies: WORK-024, WORK-025, WORK-030, WORK-033, WORK-034
Acceptance criteria:
- local services operate without upstream Internet.
- multiple access adapters can coexist.
- operators can provision a complete local fabric.
Required verification: isolated-site integration.
Definition of done: ADCOS can operate as a community-scale local network.

### WORK-037 — Open RAN/Core interoperability profile
Objective: Validate ADCOS integration with open 5G Core/RAN and standardized non-3GPP access.
Dependencies: WORK-019, WORK-020, WORK-021, WORK-032, WORK-033
Acceptance criteria:
- at least one real 5G lab works end-to-end.
- adapter boundaries remain clean.
- mixed access is demonstrated.
Required verification: interoperability lab.
Definition of done: ADCOS proves credible 5G interoperability.

# Phase 8 — Future generation and scale

### WORK-038 — Future IMT / 6G adapter profile
Objective: Prove a hypothetical future access technology can be integrated using the same adapter/registry/core contracts without modifying core protocol semantics.
Dependencies: WORK-016, WORK-029, WORK-032, WORK-033
Acceptance criteria:
- new profile identifier can be added without core schema change.
- capabilities are additive.
- routing/session/resource/policy layers remain unchanged.
Required verification: synthetic future-profile conformance test.
Definition of done: future access generations can be introduced without architectural rewrite.

### WORK-039 — Federation at scale
Objective: Scale federation, discovery, and route/capability exchange across many domains.
Dependencies: WORK-015, WORK-031, WORK-033, WORK-036
Acceptance criteria:
- federation scales horizontally.
- failure domains remain isolated.
- revocation propagates predictably.
Required verification: large-scale simulation and integration.
Definition of done: ADCOS can operate across independently administered regions.

### WORK-040 — Pilot deployment
Objective: Execute an end-to-end pilot proving the full architecture in a real deployment.
Dependencies: WORK-027, WORK-028, WORK-036, WORK-037, WORK-039
Acceptance criteria:
- real users/devices participate.
- at least one 5G access path, one non-cellular path, and one relay/backhaul path work.
- resilience/failover demonstrated.
- operational evidence is captured.
Required verification: pilot report and final conformance review.
Definition of done: ADCOS is demonstrated as a credible decentralized connectivity platform.

# Phase 9 — Governed architecture evolution

Work Items registered beyond the original 40-item snapshot register here as their own governance transitions issue. WORK-041 is the first such item (registered by the DEC-0054/DEC-0055 governance transition after its delivery merged by PR #107); its registry definition is taken from the canonical W041 contract (spec/architect/work-items/WORK-041.md, tracking issue #68) and the authorization record WORK-041-CORE-001 (DEC-0052). WORK-042's governance registration is carried by ACR-011 (PROPOSED, PR #111): its delivery is merged by PR #110 (head 708a432, merge 207d70e, CI run 33444952103 SUCCESS) and its registry definition is taken from the canonical W042 contract (spec/architect/work-items/WORK-042.md, tracking issue #69) and the active authorization record WORK-042-CORE-001 (DEC-0055); until ACR-011 merges, WORK-042 remains unregistered on main.

### WORK-041 — First-Class Network Path and Platform Integration
Objective: Implement the accepted ACR-005 network-path/platform boundary — a technology-neutral NetworkPath representation over existing authority-owned state, separating platform observation from ADCOS protocol state, and separating path detection, validation, binding, activation, and retirement — without creating a new identity, session, routing, transport, federation, or policy authority.
Dependencies: WORK-016, WORK-018, WORK-033, WORK-034
Acceptance criteria:
- The same logical session can move between distinct validated physical paths without changing session_id.
- Candidate paths are detected without automatically becoming active.
- Failed validation/bind/probe leaves the existing active path intact where possible.
- The path/platform evidence chain is explicit, deterministic, replay-safe, and independently verifiable.
- Existing accepted batteries remain green; no frozen authority ownership changes.
Required verification: static checks, networkpath_selftest, deterministic evidence-chain verification.
Out of scope: new identity/session/routing/transport/federation/policy authority; wire-schema changes unless separately authorized; private authority access; synthetic physical evidence presented as physical PASS; W042 implementation (the W041→W042 interface dependency where W042 consumes W041 interfaces remains hard and is governed by the W042 ready-candidate contract); W043/W048 implementation; commercial core/payment/settlement implementation; physical validation claims (physical evidence is not required for this Work Item; any physical claims remain governed by WORK-040's open PHYSICAL obligations EVID-007/EVID-008).
Definition of done: Path and platform facts are representable as an explicit, deterministic, replay-safe evidence chain, with stable logical sessions across physical path changes and no new authority.

### WORK-042 — Event-Driven Platform Integration and Journal-First Recovery
Objective: Implement the accepted ACR-006 event-driven platform integration and journal-first recovery model — a platform-event ingestion boundary carrying authoritative observations, deterministic and idempotent event/snapshot reconciliation, an append-only journal with periodic compact snapshots, and durable restart/suspension recovery reconciling reconstructed state with the current platform observation — while preserving all existing session and authority semantics.
Dependencies: WORK-012, WORK-013, WORK-014, WORK-033, WORK-035, WORK-041
Acceptance criteria:
- Platform changes can be delivered event-first without polling-only semantics.
- Event/snapshot reconciliation is deterministic and idempotent.
- Process death/suspension does not lose durable authorization/journal state.
- Recovery reconstructs state correctly and records session loss honestly where transport state cannot survive process death.
- Existing accepted batteries remain green and authority ownership is unchanged.
Required verification: static checks, platform_selftest, deterministic recovery/journal/evidence-chain verification.
Out of scope: new identity/session/routing/transport/federation/policy authority; treating platform observations as protocol truth without existing authority establishment; continuous-daemon assumptions on Android or similar lifecycle-managed platforms; private-method fallbacks for recovery or evidence; wire-schema changes unless separately authorized; W040 or WORK-043+ implementation (W043 retired/unassigned; W044–W053 and the commercial chain remain unauthorized); synthetic physical evidence presented as physical PASS (physical evidence is not required for this Work Item; any physical claims remain governed by WORK-040's open PHYSICAL obligations EVID-007/EVID-008).
Definition of done: Platform observations cross a deterministic, idempotent, append-only, journaled boundary; process death is recoverable with honest session-loss records; stable logical session identity and existing recovery semantics are preserved with no new authority.

# Phase 10 — Canonical commercial phase

Work Items of the canonical commercial dependency model (ACR-009, accepted by DEC-0050; reconciled planning record docs/roadmap/commercial-dependency-model.md, LEDGER-RECON-005) register here. Registration is representation only: every item carries authorization "none" until its own repository-local authorization issues (ARCH-03/ARCH-08; review-protocol §3.1), and registration is not acceptance. WORK-043 is retired from commercial use and left unassigned (LEDGER-RECON-005 §4) — its slot is intentionally vacant, never reused or renumbered, and is machine-represented by the recorded retired set in tools/spec_check.py. The commercial chain order is W051 → W052 → W053; the periphery order is W044 → W045 → W046 → W047; W050 (capability/isolation matrix) is capability-model input consumed by W048/W049 — advisory, not a hard execution gate; W048 (provider sharing runtime) and W049 (client runtime) close the phase. Registry definitions are taken from the tracking issues (#83/#84/#85 for the chain, #88/#89/#90/#91 for the periphery, #96 for the matrix, #92 for the sharing runtime, #98 canonical for the client runtime) and the canonical model.

### WORK-051 — CommercialCore: connectivity intent, offers, reservation, lease, and transaction lifecycle
Objective: Implement the minimum commercial control-plane core described by ACR-009 — the canonical commercial state lifecycle from ConnectivityIntent through OfferSelected, ReservationHeld, SessionAuthorized, PathActive, DeliveryStarted, UsageAccruing, DeliveryCompleted, BillableFinal, SettlementPending, and Settled, with compensating states/events for cancellation, expiry, path failure, and non-delivery — without changing existing identity, session, routing, path, transport, or packet semantics.
Dependencies: none
Acceptance criteria:
- The full canonical commercial lifecycle is representable, append-only, deterministic, and idempotent, with every state transition attributable.
- Compensating states/events exist for cancellation, expiry, path failure, and non-delivery; historical records remain immutable.
- The core references existing logical session IDs, NetworkPath IDs, and delivery evidence without becoming authoritative for them.
- Payment success never implies delivery; reservation never implies delivery; delivery facts cannot be rewritten by later commercial events.
- Commerce cannot mutate connectivity/session/path/routing/transport authorities; no payment-provider-specific assumptions leak into the core.
Required verification: static checks, deterministic unit/integration coverage for the full lifecycle, cancellation/expiry, non-delivery, duplicate/out-of-order events, immutable-history guarantees, and authority-boundary checks.
Out of scope: payment rails, custody, payout execution, KYC/KYB, jurisdiction rules, marketplace discovery, and developer SDKs (later authorized Work Items); frozen architecture modification; implementation before a repository-local authorization exists.
Definition of done: The commercial transaction lifecycle is a deterministic, append-only, compensating-event state machine that composes with — never replaces — the accepted connectivity authorities.

### WORK-052 — UsageLedger: delivered-usage metering, billable finality, and append-only reconciliation
Objective: Implement the usage/economic ledger layer required by ACR-009 so commercial charges are derived from authoritative delivered-traffic evidence rather than payment or reservation state — canonical records for usage observation, delivery correlation, billable finality, reconciliation, and compensating economic events.
Dependencies: WORK-051
Acceptance criteria:
- Usage requires authorized delivery evidence; payment capture and reservation/lease state never create usage.
- Duplicate observations do not double-charge; out-of-order observations do not produce nondeterministic ledger state; delayed observations reconcile deterministically.
- Billable finality is explicit, immutable, and cannot rewrite prior facts; corrections are append-only compensating records.
- Usage records correlate delivered quantity to an authorized delivery/path evidence record and remain auditable end to end.
- Commerce cannot mutate connectivity/session/path/routing/transport authorities.
Required verification: static checks, deterministic tests for usage ingestion, duplicate/out-of-order delivery events, authorization correlation, billable finality, reconciliation, refund/reversal/dispute compensation, and authority-boundary failures, including tamper and replay checks.
Out of scope: payment-provider rails, payout execution, KYC/KYB, jurisdiction policy, marketplace discovery, and developer SDKs (later authorized Work Items); frozen architecture modification; implementation before a repository-local authorization exists.
Definition of done: Billable usage is an append-only, deterministic, auditable derivation from authoritative delivery evidence, separable from payment state.

### WORK-053 — EconomicAllocation: developer/provider/ADCOS revenue-share policy and external payment boundary
Objective: Implement the economic-allocation layer of the commercial connectivity control plane — converting billable-final usage facts from the UsageLedger into immutable allocation plans according to versioned developer-selected revenue-share policy, with the default three-way split of the gross billable amount into provider share, developer share, and ADCOS share, while keeping actual payment movement outside ADCOS behind an explicit payment-provider boundary.
Dependencies: WORK-052
Acceptance criteria:
- Each allocation references exactly one immutable policy version and one billable-final usage record.
- Allocation arithmetic is deterministic and idempotent, including explicit rounding behavior; allocations sum exactly to the billable amount after declared fees/taxes/adjustments.
- Settled historical allocations are never rewritten; corrections are compensating events.
- Payment-provider references identify external movement but are never themselves the source of commercial truth; failed, duplicate, delayed, or out-of-order provider callbacks cannot corrupt canonical allocation state.
- ADCOS does not custody, mint, or directly move regulated funds through this Work Item; economic state cannot mutate identity, session, routing, NetworkPath, transport, or packet authorities.
Required verification: static checks, deterministic coverage for policy versions, developer-selected splits, boundary validation, exact arithmetic/rounding, allocation idempotency, external payment-reference correlation, settlement acknowledgement, and compensating events, including tamper, replay, duplicate, and out-of-order tests.
Out of scope: concrete Stripe/Mobile Money/bank integration, payout execution, KYC/KYB, jurisdiction policy, marketplace discovery, and developer SDKs (later authorized Work Items and provider adapters); frozen architecture modification; implementation before a repository-local authorization exists.
Definition of done: Revenue allocation is a deterministic, immutable, versioned computation over billable-final facts with all external payment movement behind an explicit provider boundary.

### WORK-044 — Payment Provider Adapters & Settlement Gateway
Objective: Provide a provider-neutral adapter boundary between the canonical ADCOS commercial ledger and external regulated payment providers — ADCOS owns commercial state, usage correlation, allocation policy, reconciliation, refund/dispute state, and payout state; the external provider owns actual payment-rail execution and regulated funds movement.
Dependencies: WORK-051, WORK-053
Acceptance criteria:
- Idempotent payment intent creation/retrieval, authorization/capture/refund/reversal status mapping, and payout/transfer instruction emission from finalized allocations work through an abstract provider adapter without importing provider-specific semantics into the canonical ledger.
- Provider callbacks/webhooks ingest with signature/anti-replay checks and are reconciled against ADCOS records; provider/ADCOS divergence is identified without rewriting history.
- Provider success can never create usage or bypass billable-final requirements; provider adapters never mutate settled history.
- A deterministic fake/sandbox provider proves the flows; provider-specific capabilities are explicit and versioned.
- Strict import/boundary tests prove payment adapters do not import connectivity/session/path authorities in forbidden directions.
Required verification: static checks, deterministic sandbox-provider battery for idempotent payment intent/capture/refund/reversal/payout flows, negative tests for provider success not creating usage, callback replay/duplicate/out-of-order idempotency, reconciliation, and import-discipline checks.
Out of scope: live payment account onboarding; jurisdiction-wide legal/KYC implementation; custody of regulated funds; merchant-of-record obligations (jurisdiction/provider responsibilities represented as eligibility/capability state, not protocol authority); marketplace UI or developer SDK; changes to frozen networking semantics.
Definition of done: External payment movement crosses an explicit, provider-agnostic adapter boundary that the canonical ledger can always reconcile without depending on any single provider's semantics.

### WORK-045 — Connectivity Eligibility, Provider Trust & Jurisdiction Policy
Objective: Provide a deterministic eligibility layer answering whether a provider may legally/contractually offer a connectivity resource in a given jurisdiction and whether the provider, offer, device, network, and payment configuration satisfy platform policy — policy/eligibility oriented, without implementing legal compliance on behalf of jurisdictions.
Dependencies: WORK-051, WORK-053, WORK-044
Acceptance criteria:
- Provider eligibility records, jurisdiction capability/requirement registries, offer-level eligibility checks, and device/platform eligibility signals evaluate deterministically under a versioned policy engine.
- Expired/revoked eligibility fails closed; suspension prevents new offers/leases while preserving historical settlement records; reinstatement is explicit.
- Payment-provider approval never implies network-sharing eligibility, and network eligibility never implies payment eligibility (independent authorizations).
- Jurisdiction-specific requirements are data-driven and auditable; sensitive identity/KYC data remains with the appropriate regulated provider (ADCOS stores references and decision metadata only).
- Eligibility never silently mutates connectivity/session/path state.
Required verification: static checks, deterministic policy-engine evaluation over provider/offer/jurisdiction combinations, expired/revoked fail-closed tests, policy versioning without historical rewrites, and negative tests proving payment and connectivity authorization independence.
Out of scope: jurisdiction-specific legal advice engine; custody of government IDs or raw KYC documents; regulator authority claims (jurisdiction policy represented as configuration/evidence, not hardcoded universal law); marketplace UI; changes to networking/session/path semantics.
Definition of done: Eligibility is a deterministic, versioned, fail-closed policy layer whose decisions are attributable and auditable without making ADCOS a legal authority.

### WORK-046 — Developer Connectivity API, SDK & Webhook Platform
Objective: Expose stable APIs and SDK primitives for developers to create connectivity products — publish offers, create connectivity intents, reserve/lease capacity, observe lifecycle, retrieve usage/billing records, configure economic policy, and receive signed webhooks — a developer-platform experience without exposing connectivity/session/routing authority directly.
Dependencies: WORK-051, WORK-052, WORK-053, WORK-044, WORK-045
Acceptance criteria:
- A versioned API schema with backward-compatibility tests generates or maintains the SDKs; sandbox and production namespaces remain isolated.
- Mutating requests honor idempotency keys under retries and duplicates; scoped application credentials cannot mutate resources outside their declared capabilities.
- Signed webhook delivery carries replay/duplicate/out-of-order protection; webhooks are observations of ADCOS state, not a second source of truth.
- API success never implies physical connectivity success; developer-facing errors preserve canonical ADCOS reason codes.
- SDK contract tests reproduce the same canonical server semantics with no hidden business authority diverging from the server-side commercial model.
Required verification: static checks, deterministic schema/backward-compatibility tests, idempotency behavior under retries, signed webhook verification with replay/duplicate/out-of-order tests, scope tests, and sandbox/production isolation tests.
Out of scope: full marketplace UI implementation; payment custody implementation; direct mutation of identity, sessions, NetworkPath, routing, transport, or packet state through the API; networking protocol changes; sandbox/test behavior represented as physical or production evidence.
Definition of done: Developers can build connectivity products against a stable, versioned, idempotent, scoped API surface whose semantics are exactly the canonical server-side commercial model.

### WORK-047 — Connectivity Marketplace Discovery, Proximity & Path Selection
Objective: Enable buyers and applications to discover eligible nearby connectivity offers and select a suitable path using explicit price, quality, reachability, policy, and privacy constraints — without turning marketplace discovery into networking authority.
Dependencies: WORK-051, WORK-044, WORK-045, WORK-046
Acceptance criteria:
- Discovery/ranking is deterministic over identical candidate sets; expired/ineligible/suspended offers are excluded fail-closed.
- Privacy tests demonstrate bounded location precision; location is never exposed more precisely than required for the product decision.
- Stale quality telemetry carries age/confidence metadata and cannot silently become current state; a provider's advertised quality is not authoritative current reachability without validation.
- Candidate selection hands off to the production NetworkPath path-validation machinery (accepted WORK-041) rather than bypassing it.
- No forbidden imports or mutations of session/routing/transport authorities; no fabricated physical proximity, connectivity quality, or availability in ranking.
Required verification: static checks, deterministic discovery/ranking tests over identical candidate sets, eligibility exclusion tests, privacy/precision tests, stale-telemetry age/confidence tests, and path-validation handoff composition tests.
Out of scope: direct routing implementation; packet transport implementation; exact consumer location storage by default; monetization logic beyond invoking canonical commercial resources.
Definition of done: Marketplace discovery proposes deterministic, privacy-preserving, eligibility-filtered candidates whose activation always flows through the canonical path-validation machinery.

### WORK-050 — Platform Connectivity Sharing Capability & Isolation Matrix
Objective: Provide an explicit, versioned capability model describing which operating systems, device classes, network configurations, and deployment modes can safely provide or consume leased connectivity, which isolation primitives are available, and which sharing modes are unsupported or require additional infrastructure — descriptive/capability authority only.
Dependencies: none
Acceptance criteria:
- A platform capability registry covers provider and buyer roles, sharing-mode capability classes, isolation-primitive declarations with minimum security properties, metering capability and byte-counting authority declaration, and lease-enforcement capability (time, byte, concurrency, emergency stop).
- Capability discovery and deterministic compatibility evaluation produce explicit supported, restricted, unsupported, and unknown outcomes.
- The provider/consumer mode compatibility matrix is versioned; capability findings carry evidence references.
- Capability declaration is never confused with proof that a particular physical deployment currently works.
- The registry is not a routing, NetworkPath, session, identity, or transport authority.
Required verification: static checks, deterministic capability-evaluation and compatibility-matrix tests over versioned registries, and boundary tests proving the registry stays descriptive.
Out of scope: sharing-runtime enforcement code (WORK-048/W049 own runtime and enforcement under their own authorizations); any implementation vehicle for WORK-048; routing/transport authority.
Definition of done: Platform sharing capability and isolation constraints are an explicit, versioned, deterministic matrix consumed by — never enforcing for — the sharing and client runtimes.

### WORK-048 — Provider Connectivity Sharing Runtime, Isolation & Quota Enforcement
Objective: Provide a safe provider-side runtime that can expose a bounded connectivity resource for an authorized buyer lease — provider sharing session lifecycle, explicit provider consent, quota/capacity enforcement, isolation and lease expiry, and authoritative usage evidence for the UsageLedger — without becoming a second routing/session authority and without allowing buyer traffic to escape its declared policy.
Dependencies: WORK-041, WORK-042, WORK-051
Acceptance criteria:
- The provider sharing session lifecycle (prepare → authorized → active → paused → expired/revoked → closed) enforces explicit provider consent before exposure and binds each sharing session to a canonical commercial lease and the production NetworkPath/path-validation machinery.
- Byte/time/quota enforcement is deterministic with accounting hooks into the UsageLedger; concurrent buyer limits and capacity reservations cannot oversubscribe the declared provider envelope.
- Lease expiry and emergency stop controls halt new buyer traffic promptly without rewriting historical usage.
- Isolation between provider control traffic and buyer traffic uses an OS/network mechanism appropriate to the platform; isolation failures fail closed.
- Usage events correlate to the canonical lease/session and remain compatible with UsageLedger idempotency/reconciliation; network path loss/change composes with the NetworkPath validation/activation flow rather than bypassing it; no forbidden imports or writes into identity/session/routing/transport authorities.
Required verification: static checks, deterministic provider-sharing lifecycle battery with positive and fail-closed cases, consent/expiry/revocation/quota-exhaustion/emergency-stop tests, isolation tests, concurrent-capacity tests, usage correlation tests, and path-loss composition tests.
Out of scope: payment processing or payout logic (WORK-044); marketplace ranking/discovery implementation (WORK-047); developer API implementation (WORK-046); new core networking protocol semantics; arbitrary packet interception or plaintext inspection unless separately authorized; custody of payment credentials; assumption that every OS can safely share connectivity (platform capability must be explicit — WORK-050's matrix is advisory capability input, not a hard gate).
Definition of done: A provider can safely share a bounded, isolated, consent-gated, quota-enforced slice of connectivity under an active lease, with authoritative usage evidence and no second networking authority.

### WORK-049 — Provider & Buyer Connectivity Client Runtime
Objective: Provide a platform-neutral client/runtime boundary that lets an end user participate as a connectivity provider or buyer through an application — consent UX, capability discovery, policy presentation, secure handoffs, status/events, and offline/reconnect behavior — while keeping consent, lease state, path selection, isolation, metering, and lifecycle enforcement delegated to their canonical authorities.
Dependencies: WORK-046, WORK-047, WORK-048
Acceptance criteria:
- Provider-mode and buyer-mode client lifecycles present local policy (quota, time, price, sharing scope, privacy, emergency stop) with explicit, revocable provider consent.
- Device capability discovery yields explicit support/unsupported states; the client hands off securely to the provider sharing runtime (WORK-048), discovery/path selection (WORK-047), and developer API (WORK-046) where application-mediated.
- Client-side status/events for lease, connectivity, metering, and failures are projections of canonical state, never a new source of truth; offline/reconnect behavior never invents commercial truth.
- Privacy-preserving display of nearby offer/provider information; a platform adapter boundary covers Android/desktop/router-class environments.
- The client runtime is not identity, session, NetworkPath, routing, transport, commercial, usage, or payment authority.
Required verification: static checks, deterministic client-lifecycle and consent tests, handoff boundary tests, status/event projection tests, offline/reconnect tests, and platform-adapter boundary tests.
Out of scope: server-side commercial, usage, or payment authority; path validation or activation (NetworkPath machinery owns it); metering enforcement (WORK-048/W052 own it); WORK-050's capability matrix is advisory capability input consumed for device support states, not a hard gate.
Definition of done: End users can participate as providers or buyers through a client that projects canonical state, enforces explicit consent, and delegates every authority to its canonical owner.
