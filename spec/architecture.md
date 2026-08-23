# ADCOS Protocol Architecture

## Status

**FROZEN — Architecture Version 1.0**

This document is the authoritative architecture for the ADCOS project. The implementation must conform to this architecture exactly. Implementation convenience, framework preference, vendor preference, or performance optimization are not grounds for changing a frozen architectural rule.

**Project:** ADCOS — Adaptive Distributed Connectivity Operating System

**Primary thesis:** ADCOS is a future-proof, access-technology-neutral connectivity fabric that composes 5G, future 6G/IMT-2030 and later generations, Wi-Fi, Ethernet/fiber, microwave, satellite, mesh, device-to-device links, and future access technologies into a single authenticated, policy-controlled, federated network.

ADCOS is **not** a replacement PHY and is **not** a software trick that turns arbitrary commodity devices into 5G radios. Physical radio capability remains hardware-bound. ADCOS instead standardizes the software/fabric layer above heterogeneous access hardware and exposes a stable abstraction so a new radio generation can be introduced as an adapter without rewriting the network protocol.

---

## 1. Architectural North Star

ADCOS shall make the following statement true:

> A user, device, application, community, ISP, carrier, or infrastructure owner can contribute or consume connectivity resources without needing the entire network to be controlled by a single vendor or built around a single radio generation.

The network is therefore modeled as:

```text
                    GLOBAL FEDERATED FABRIC
                              │
                 ┌────────────┴────────────┐
                 │   FABRIC CONTROL PLANE │
                 │ identity / discovery   │
                 │ topology / routing     │
                 │ policy / federation    │
                 └────────────┬────────────┘
                              │
                 ┌────────────┴────────────┐
                 │    DISTRIBUTED SERVICE  │
                 │    + SESSION CONTROL    │
                 │ mobility / QoS / paths │
                 └────────────┬────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        │                     │                      │
   5G / IMT-2020         Wi-Fi / LAN          Future IMT-2030+
   access adapter       non-3GPP adapters      access adapters
        │                     │                      │
        └─────────────────────┼──────────────────────┘
                              │
                        PHYSICAL LINKS
```

The central design decision is that **ADCOS semantics live above access technology**. 5G is a first-class adapter, not the protocol itself. 6G is not allowed to become a second core protocol; it must be another access profile behind the same adapter boundary.

---

## 2. Design Principles

### P1 — Access agnosticism
No core ADCOS protocol object may require 5G, LTE, Wi-Fi, or any other specific access technology to exist.

### P2 — Generation neutrality
The core protocol MUST NOT encode a fixed assumption that "generation = 5G" or "generation = 6G". Access profiles are identified by stable technology-independent identifiers plus versioned capability sets.

### P3 — Replaceability
Any access technology may be replaced, upgraded, combined, or retired without changing identity, session, routing, policy, or federation semantics.

### P4 — Capability negotiation
Nodes advertise what they can actually do. Unknown future capabilities are ignored safely unless a policy explicitly requires them.

### P5 — Evidence over assertion
A topology/capability claim is never treated as authoritative merely because another node reported it. ADCOS records provenance: self-advertised, directly observed, externally reported, cryptographically attested, or experimentally measured.

### P6 — Least authority
Every node, adapter, service, operator, and user receives only the capabilities required for its role.

### P7 — No blockchain dependency
Decentralization is achieved through federation, cryptographic identity, explicit trust domains, distributed routing/resource policies, and ordinary settlement mechanisms. A blockchain or token is optional and outside the networking core.

### P8 — Local-first resilience
When global connectivity is unavailable, local services, local routing, local DNS/service discovery, local breakout, and store-and-forward operation must remain possible.

### P9 — Graceful degradation
Loss of spectrum, backhaul, compute, energy, or a neighboring node must degrade service where possible rather than collapse the network.

### P10 — Open implementation boundary
All external vendors and open-source stacks are adapters. Core domain code must not import vendor SDKs, vendor-specific RAN types, or hardware-specific APIs.

### P11 — Observable and auditable
Every materially important routing, authorization, capability, session, and federation decision must have machine-verifiable evidence sufficient for diagnosis and security review.

### P12 — Protocol evolution without flag days
Wire formats, registries, capability identifiers, and state machines are versioned. Backward compatibility and feature negotiation are mandatory design concerns.

---

## 3. Relationship to Existing Standards

ADCOS is an orchestration/fabric protocol, not a replacement for 3GPP or IETF protocols.

### Current anchors

- 3GPP defines 5G system architecture and access/network functions.
- O-RAN defines open RAN interfaces and cloudification/orchestration directions, including decoupling software from hardware.
- 3GPP non-3GPP access mechanisms allow 5G Core connectivity through Wi-Fi and related access networks.
- 3GPP IAB and sidelink provide standards-based foundations for wireless backhaul and direct/relay connectivity.
- IETF IPv6, QUIC, TLS, IPsec/WireGuard-class secure transports and standard routing are used where appropriate instead of reinventing transport/security primitives.

### Future anchor: IMT-2030 and beyond

ITU-R Recommendation M.2160 defines the IMT-2030 framework and identifies sustainability, security/resilience, connecting the unconnected, and ubiquitous intelligence among the future-network objectives. ITU agreed draft IMT-2030 technical performance requirements in 2026, and 3GPP Release 20 is the study phase for 6G while Release 21 is the normative 6G work. ADCOS therefore deliberately freezes only the cross-generation abstractions, not any future radio PHY, spectrum plan, or 6G-specific network function.

References:

- ITU-R M.2160, *Framework and overall objectives of the future development of IMT for 2030 and beyond*: https://www.itu.int/rec/R-REC-M.2160/en
- ITU, *IMT-2030: Technical requirements for the 6G future* (2026): https://www.itu.int/hub/2026/03/imt-2030-technical-requirements-for-the-6g-future/
- 3GPP, *Release 20*: https://www.3gpp.org/specifications-technologies/releases/release-20
- O-RAN ALLIANCE, *Technical Groups*: https://www.o-ran.org/technical-groups
- O-RAN ALLIANCE, *Architecture principles for a cloud-friendly future 6G RAN architecture*: https://www.o-ran.org/research-reports/architecture-principles-for-a-cloud-friendly-future-6g-ran-architecture

---

## 4. System Model

An ADCOS network is a graph of **Nodes** connected by **Links** and exposing **Capabilities** and **Resources**.

```text
Node
 ├── Identity
 ├── Roles
 ├── Access Adapters
 ├── Backhaul Adapters
 ├── Compute Resources
 ├── Storage Resources
 ├── Energy State
 ├── Service Endpoints
 └── Trust / Attestation State
      │
      └── Links → Neighbors → Paths → Sessions
```

A node can simultaneously act as endpoint, relay, gateway, edge compute host, access provider, backhaul provider, service host, or federation peer.

Roles are additive and dynamic. A role is never itself an identity.

---

## 5. Protocol Planes

ADCOS has six logical planes.

### 5.1 Identity & Trust Plane
Owns node identity, credentials, authorization, attestation evidence, trust-domain membership, key rotation, revocation, and provenance.

### 5.2 Discovery & Topology Plane
Owns neighbor discovery, capability advertisement, topology observations, evidence provenance, reachability state, link state, and topology convergence.

### 5.3 Resource & Intent Plane
Owns resource advertisements, service intents, policy constraints, QoS objectives, energy constraints, cost constraints, and admission decisions.

### 5.4 Session & Mobility Plane
Owns end-user/network session identity, path bindings, multi-path sessions, mobility, handover, failover, and continuity semantics.

### 5.5 Data/Fabric Plane
Carries user/service traffic through selected paths. It uses standard IP forwarding/tunneling primitives wherever possible and only introduces ADCOS-specific encapsulation where an explicit cross-access function is required.

### 5.6 Management & Observability Plane
Owns lifecycle management, telemetry, health, conformance, configuration, upgrade state, evidence retention, and operator APIs.

---

## 6. Core Protocol Objects

The following objects are frozen and their semantics must remain stable.

### 6.1 Node
A cryptographically identified participant.

Required fields:

- NodeID
- protocol version set
- software build identifier
- hardware class (optional disclosure)
- roles
- adapters
- capabilities
- resource state
- trust state
- administrative domain references

### 6.2 Identity
An asymmetric-key-backed identity independent of access technology.

Requirements:

- stable NodeID derived from a public-key identity or a registered equivalent;
- separate credentials for node identity, operator authority, and user identity where needed;
- rotation support;
- revocation support;
- no requirement that a node have a SIM;
- no prohibition against a node also possessing 3GPP credentials.

### 6.3 Adapter
A typed implementation boundary around a physical/logical access technology.

An Adapter MUST expose:

- adapter ID;
- access technology ID;
- supported profile versions;
- capabilities;
- link metrics;
- lifecycle controls;
- security state;
- resource mapping;
- session/bearer mapping;
- health.

### 6.4 Capability
A signed, versioned statement describing something the node/adapter may provide.

Capabilities contain:

- capability ID;
- schema version;
- provider identity;
- validity interval;
- parameters;
- constraints;
- evidence references;
- signature.

### 6.5 Link
A directional or bidirectional connectivity relationship between two adapters.

Link state is independent of node identity and advertisement freshness.

### 6.6 Path
An ordered set of links that can satisfy a session or resource intent.

A path carries:

- path ID;
- constituent links;
- measured metrics;
- policy score;
- confidence/provenance;
- expiry;
- failover options.

### 6.7 Session
A logical connectivity relationship independent of a particular radio bearer.

The session survives access changes when policy and technology permit.

### 6.8 Resource
A consumable or reservable quantity such as throughput, compute, storage, spectrum availability, energy budget, or service capacity.

### 6.9 Intent
A machine-readable request describing what connectivity is desired rather than how to obtain it.

Examples:

```text
bandwidth >= 20 Mbps
latency <= 30 ms
availability >= 99.9%
energy_cost <= threshold
local_breakout = preferred
privacy = end_to_end
```

### 6.10 Federation
A typed relationship between administrative domains allowing selected capabilities and services to be shared.

### 6.11 Evidence
A cryptographically attributable observation supporting a claim.

Evidence types:

- self-advertised;
- peer-observed;
- UE-observed;
- controller-measured;
- remotely attested;
- external authority attested;
- historical statistical evidence.

This distinction is mandatory. A reported gateway claim, for example, cannot be silently converted into an authoritative gateway fact.

---

## 7. Stable Protocol Envelope

All ADCOS protocol messages use a versioned envelope.

Conceptually:

```json
{
  "protocol": "adcos",
  "version": 1,
  "message_type": "capability.advertise",
  "message_id": "...",
  "sender": "...",
  "issued_at": "...",
  "expires_at": "...",
  "correlation_id": "...",
  "extensions": {},
  "payload": {},
  "evidence": [],
  "signature": "..."
}
```

Rules:

1. Unknown message types must be rejected safely or tunneled as opaque extensions according to the negotiated policy.
2. Unknown extension fields must not corrupt known fields.
3. Forward-compatible parsers must preserve unknown fields when proxying data that they do not own.
4. Breaking schema changes require a new major protocol version.
5. Additive changes use minor/schema versions and feature negotiation.
6. Security-critical fields are covered by signatures/MACs according to the message security profile.

Canonical serialization and hashing are implementation-independent. CBOR is the initial compact wire encoding candidate; JSON is the required human/debug encoding. The exact canonicalization profile is frozen by a later conformance work item before production wire compatibility is declared.

---

## 8. Capability and Technology Registry

ADCOS uses registries rather than hard-coded enums for access technologies.

Every access technology has:

- globally unique technology ID;
- profile versions;
- required base capabilities;
- optional capabilities;
- security profile;
- adapter lifecycle contract;
- interoperability notes.

Initial examples:

```text
access.3gpp.nr.imt2020
access.3gpp.lte.imtadvanced
access.ieee.80211
access.ieee.8023
access.satellite
access.microwave
access.bluetooth
access.3gpp.sidelink
access.3gpp.iab
```

Future entries may include:

```text
access.3gpp.nr.imt2030
access.3gpp.future.unknown
```

No core state machine may branch on a technology name. It branches on capabilities and negotiated profiles.

---

## 9. Node Agent

Every ADCOS-capable compute node runs an **ADCOS Agent**.

The Agent is the local operating layer between the ADCOS fabric and the host operating system/hardware.

Core services:

```text
Agent
 ├── Identity Service
 ├── Trust Service
 ├── Discovery Service
 ├── Topology Service
 ├── Capability Service
 ├── Resource Service
 ├── Intent Engine
 ├── Path Engine
 ├── Session Manager
 ├── Mobility Manager
 ├── Policy Engine
 ├── Adapter Runtime
 ├── Service Registry
 ├── Telemetry
 └── Local Persistence
```

The Agent may be minimal on an endpoint and full-featured on an infrastructure node.

---

## 10. Adapter Architecture

### 10.1 Adapter contract

```text
Adapter.open()
Adapter.capabilities()
Adapter.observe()
Adapter.allocate()
Adapter.release()
Adapter.bind_session()
Adapter.unbind_session()
Adapter.health()
Adapter.close()
```

The exact programming language is not architectural. Rust is the reference implementation language for the first Linux node implementation, but the protocol is language neutral.

### 10.2 5G adapter
The 5G adapter integrates with standards-compliant 5G RAN/core components. It may wrap OCUDU, OpenAirInterface, Open5GS, commercial modem APIs, SDRs, or future implementations.

The adapter must not leak 3GPP-specific state machines into the ADCOS core.

### 10.3 Non-3GPP access adapter
Integrates Wi-Fi and other access paths to a 5G Core or directly to the ADCOS fabric as policy permits. 3GPP N3IWF/TNGF mechanisms may be used where 5G Core interoperability is required.

### 10.4 Future-IMT adapter
The future 6G/IMT-2030 adapter consumes whatever RAN/core control model eventually becomes standardized and maps it to the same ADCOS contracts.

No ADCOS core release will wait for 6G standardization to finish.

### 10.5 Generic adapter
A generic adapter exists for experimental/future technologies. It allows a technology to be tested before a dedicated profile is standardized.

---

## 11. Discovery and Topology

Discovery is local and federated.

Each node may discover peers through:

- link-local broadcast/multicast;
- configured bootstrap peers;
- mDNS/LLDP equivalents where appropriate;
- 5G/network signaling adapters;
- explicit federation peers;
- store-and-forward discovery messages in intermittently connected networks.

Topology uses independent state dimensions:

```text
Identity:
  UNKNOWN | KNOWN | REMOVED

Advertisement:
  CURRENT | STALE

Reachability:
  UNREACHABLE | REACHABLE

Link:
  DOWN | DEGRADED | UP

Evidence:
  SELF | OBSERVED | ATTESTED | REPORTED | MEASURED
```

These dimensions must never be collapsed into one enum.

Remote summaries are treated as **claims by the summarizing node**, not as direct advertisements by the summarized node. A gateway or other high-value capability becomes authoritative only when supported by acceptable evidence under local policy.

---

## 12. Routing and Path Selection

ADCOS routing is policy-aware and resource-aware.

The route engine computes candidate paths based on:

- reachability;
- latency;
- throughput;
- loss;
- jitter;
- cost;
- energy;
- trust;
- capacity;
- administrative policy;
- locality;
- service availability;
- confidence/provenance.

The routing model is path-aware but does not mandate a particular Internet routing protocol.

A domain may use:

- ordinary IP routing;
- SD-WAN-like policy routing;
- path-aware protocols;
- mesh routing;
- controller-driven routes.

ADCOS defines the intent and session contracts above them.

---

## 13. Multipath

Multipath is a first-class capability, not a required transport implementation.

A session may bind:

```text
5G path
+
Wi-Fi path
+
microwave backhaul
```

The implementation may use MPTCP, a multipath-capable QUIC implementation, parallel tunnels, or another standards-compatible mechanism behind the Session Manager.

Applications do not depend on one implementation.

---

## 14. Mobility and Handover

Mobility operates on logical sessions, not on a specific cell identity.

The preferred sequence is:

```text
predict/observe new access
        ↓
reserve candidate path
        ↓
pre-authenticate when allowed
        ↓
attach/bind new adapter path
        ↓
switch traffic
        ↓
release old path
```

Make-before-break is preferred where resources allow it.

Hard handover is supported where required.

The logical Session ID remains stable across a successful handover.

---

## 15. Distributed Core and Edge

ADCOS does not mandate one centralized core.

Core functions may be distributed across nodes.

A deployment may contain:

- authentication service;
- session control service;
- policy service;
- user-plane gateways;
- local breakout gateways;
- DNS/service discovery;
- caches;
- edge compute;
- local application services.

3GPP 5G Core functions remain accessible through an adapter in deployments that require standards-compatible cellular operation.

---

## 16. Local-first Operation

A network must be able to continue useful operation without global Internet reachability.

Required mechanisms:

- local service registry;
- local DNS/service discovery;
- local breakout;
- community edge services;
- delayed synchronization;
- optional store-carry-forward bundles;
- configurable offline authorization grace periods;
- local policy cache.

Emergency/local services may be configured to survive loss of upstream connectivity.

---

## 17. Resource Model

A resource provider can expose:

```text
bandwidth
spectrum-availability
compute
storage
energy
backhaul
coverage
edge-service-capacity
```

Resources may be:

- continuously available;
- reservation based;
- best effort;
- scheduled;
- quota constrained;
- metered.

The protocol separates technical resource admission from economic settlement. Billing/token systems must not be imported into routing semantics.

---

## 18. Energy-aware Networking

Energy is a first-class routing constraint.

Nodes may expose:

- power source;
- battery state;
- estimated runtime;
- generation rate;
- thermal constraints;
- energy cost per unit traffic;
- minimum survival service profile.

Policies can reserve capacity for essential connectivity when energy is scarce.

---

## 19. Security Architecture

ADCOS uses a zero-trust posture.

Every trust decision is explicit.

Required:

- authenticated control-plane peers;
- authenticated resource claims where feasible;
- encrypted management channels;
- encrypted user traffic end-to-end where possible;
- role/capability based authorization;
- key rotation;
- revocation;
- replay protection;
- message expiration;
- signed software/firmware where the platform supports it;
- optional remote attestation;
- audit evidence for privileged operations.

A compromised node must not automatically compromise the network.

---

## 20. Privacy

ADCOS must minimize unnecessary exposure of:

- user identity;
- exact user location;
- traffic metadata;
- topology details;
- business relationships;
- device fingerprints.

Operators may use pseudonymous node identifiers and privacy-preserving measurements where technically feasible.

Location disclosure is capability/policy controlled and never globally required merely because a node participates in the network.

---

## 21. Federation

Federation enables independently operated domains to interoperate.

A federation relationship specifies:

- peer identities;
- trust policy;
- shared capabilities;
- route/import/export policy;
- service exposure;
- resource exposure;
- settlement policy;
- audit requirements;
- revocation semantics.

Federation is not equivalent to trust of every node in a peer domain. Trust is scoped to the federated capabilities and policies explicitly granted.

---

## 22. Management and Intent APIs

The management surface must express intent, not internal implementation details.

Examples:

```text
provide_access(area, requirements)
connect(device, intent)
provide_backhaul(node, capacity)
expose_service(service, policy)
reserve_capacity(resource, constraints)
join_federation(domain, policy)
```

Operators can also inspect low-level state, but higher-level APIs are normative for automation.

---

## 23. Hardware Model

ADCOS defines a minimal hardware-neutral reference profile.

### Endpoint
May have no ADCOS-capable radio and act only as an application client over an existing modem/Wi-Fi connection.

### Edge Node
Commodity CPU + Ethernet/Wi-Fi and optional radio adapters.

### Radio Node
Compute + SDR/RF front end or dedicated cellular radio.

### Gateway Node
Backhaul + user-plane routing + local services.

### Network-in-a-Box
Compute + radio + backhaul + core/edge functions + management in one deployable unit.

Raspberry Pi-class hardware is a reference target for experimental/low-capacity nodes, not a universal performance guarantee.

---

## 24. Device Classes

### Phones
Phones are first-class ADCOS endpoints and may participate through their existing modem, Wi-Fi, tethering, Bluetooth/UWB, USB, or future open radio APIs. An ordinary phone application is **not** assumed to have arbitrary control over the cellular baseband.

### Laptops/desktops
May run an ADCOS Agent and participate through Ethernet, Wi-Fi, USB modems, SDRs, or future programmable radios.

### Raspberry Pi / ARM SBC
Can run edge, relay, gateway, control, and experimental RAN functions subject to hardware capability.

### Dedicated radio hardware
Provides carrier-grade or higher-capacity RF access under the same adapter contract.

---

## 25. Future-proofing Rules for 6G and Beyond

These rules are non-negotiable.

1. **No `five_g_*` core object names.** Use `access_profile`, `radio_capability`, `bearer`, or similarly generic terms.
2. **No 5G-only assumptions in the core routing/session model.**
3. **No fixed physical topology assumption.** A cell, beam, radio unit, distributed radio cluster, satellite, relay, or future access object is represented through adapters/capabilities.
4. **No fixed spectrum model.** Licensed, shared, unlicensed, dynamic, satellite, and future spectrum models are policies/capabilities.
5. **No fixed identity mechanism.** ADCOS identity is access-independent and can be mapped to 3GPP identities where needed.
6. **No fixed control-plane location.** Services can run centrally, regionally, on edge nodes, or in a distributed cluster.
7. **No fixed routing algorithm.** The intent/session contracts survive route-engine replacement.
8. **No fixed cryptographic algorithm.** Cryptographic agility is required.
9. **No fixed transport.** QUIC/UDP/IPsec/etc. are adapters beneath stable session semantics.
10. **No fixed serialization.** Wire encoding is negotiated within the stable protocol envelope.
11. **No requirement that future radios expose today's 5G functions.**
12. **No assumption that 6G will be merely faster 5G.** New capabilities such as integrated sensing, ubiquitous connectivity, AI-native networking, distributed intelligence, new mobility/coverage modes, and other future capabilities enter through typed capability extensions.
13. **No flag-day upgrade.** New technology must coexist with existing nodes.
14. **Unknown future features must fail closed for security and fail soft for optional functionality.**

---

## 26. Reference Deployment Profiles

### Profile A — Community Wi-Fi + 5G gateway

```text
Phones/Laptops
   ↓
Wi-Fi / 5G UE
   ↓
Community Edge
   ↓
5G Core / UPF
   ↓
Fiber / Satellite
```

### Profile B — Solar community RAN

```text
Solar + battery
      ↓
ARM SBC + SDR/RF
      ↓
5G/NR access
      ↓
wireless mesh
      ↓
regional gateway
```

### Profile C — Multi-access community fabric

```text
        5G ───┐
              │
Wi-Fi ─────── ADCOS node ─── fiber
              │
        microwave
              │
          satellite
```

### Profile D — Future 6G migration

```text
5G adapter ──────────┐
                     │
6G/IMT-2030 adapter ─┼─ ADCOS Core ── same user/session identity
                     │
Wi-Fi/future adapter ┘
```

---

## 27. Initial Implementation Stack

The reference implementation shall be Linux-first and provider-neutral.

Initial preferred stack:

- Rust for the ADCOS Agent and protocol core;
- IPv6-first networking;
- QUIC/TLS where appropriate for secure application/control transport;
- SQLite or embedded storage only for node-local cache/state where suitable; authoritative multi-node state must not depend on a single local database;
- Open5GS for a first 5G Core integration target;
- OCUDU and/or OpenAirInterface for RAN integration targets;
- SDR support for laboratory/reference deployments;
- Android companion/application for endpoint participation subject to platform APIs;
- Linux/ARM reference agent for Raspberry Pi-class nodes.

The choice of these implementations is not a protocol dependency. A compliant implementation may substitute equivalent components behind the adapter boundary.

---

## 28. Conformance Model

Conformance is layered.

### Level 0 — Core protocol
Envelope, identity, capability, discovery, topology, policy, session, and federation semantics.

### Level 1 — Transport
Secure transport and path/session behavior.

### Level 2 — Access adapter
One or more access technologies.

### Level 3 — Infrastructure role
Relay, gateway, edge, RAN, backhaul, service host.

### Level 4 — Interoperability
Interoperation with external 3GPP/O-RAN/IETF implementations.

### Level 5 — Production
Security, resilience, performance, upgrade, observability, and operational conformance.

No implementation may claim full ADCOS conformance by passing only an access-specific interoperability test.

---

## 29. Architectural Boundaries

The following module boundaries are frozen:

```text
/core
/identity
/trust
/protocol
/capabilities
/discovery
/topology
/resources
/intent
/policy
/routing
/session
/mobility
/federation
/adapters
/transport
/services
/edge
/telemetry
/management
/conformance
/simulator
```

External technologies belong only beneath:

```text
/adapters
/transport
/management/providers
```

No core module may import an external vendor SDK or access-specific implementation type.

---

## 30. Architectural Non-Goals

ADCOS v1.0 does not attempt to:

- replace the 3GPP NR PHY;
- make arbitrary smartphones into gNBs through an app;
- standardize spectrum regulation;
- prescribe one commercial business model;
- require a cryptocurrency/token;
- replace O-RAN interfaces;
- replace IP;
- replace 5G Core;
- predict the final 6G PHY or air-interface design;
- guarantee carrier-grade performance on Raspberry Pi-class hardware;
- require one global operator.

---

## 31. Decision Summary

ADCOS is frozen as an **access-technology-neutral, cryptographically authenticated, federated connectivity fabric** with:

- stable identity;
- capability-driven adapters;
- evidence-aware topology;
- policy-aware routing;
- intent-driven resource selection;
- access-independent sessions;
- mobility and multipath;
- distributed edge/core;
- local-first resilience;
- federation between independent operators;
- standardized conformance;
- explicit future-generation adapter slots.

The architectural objective is not to win by building a slightly cheaper 5G stack. It is to make **connectivity infrastructure composable** and to allow 5G today and 6G tomorrow to become replaceable implementations beneath one persistent connectivity fabric.
