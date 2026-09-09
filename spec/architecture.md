# ADCOS Architecture

## Status

FROZEN — Architecture Version 1.1.

- Accepted: ACR-014 (DEC-0098 approval; synchronized updates merged with the M001 delivery)
- Supersedes: Architecture 1.0, preserved verbatim at `spec/history/architecture-1.0.md`
- Scope: normative architecture — the sole forward design authority

## 1. Mission

ADCOS provides a programmable exchange and orchestration layer through which users, applications, organizations, governments, service providers and network operators can acquire, compose and continuously assure connectivity supplied by heterogeneous underlying networks.

> **One connectivity contract. Many networks. Continuous fulfillment.**

ADCOS is not a replacement for 3GPP, IETF, O-RAN, QUIC, MPTCP/MP-QUIC, DTN, provider routing systems, Wi-Fi systems, eSIM provisioning systems or other specialized network mechanisms.

## 2. Architectural boundary

ADCOS owns connectivity intent and normalization; provider capability and offer exchange; eligibility and policy evaluation; connectivity contracts and leases; provider-domain federation; execution-plan composition; connectivity assurance and evidence; usage accounting and connectivity settlement references; and developer-facing connectivity APIs.

Underlying providers own their actual network mechanisms, local topology, radio/core systems, routing, subscriber systems and provider-native credentials. Application systems own their own application semantics.

## 3. Canonical durable object

`ConnectivityContract` is the canonical durable object for acquired connectivity.

A contract contains contract identity; principal and beneficiary scope; normalized requirements; accepted offer references; hard constraints; committed service properties; validity interval; usage and pricing terms; assurance obligations; permitted execution scope; termination and compensation rules; provenance; and signature references.

A `Path`, `Session`, `Tunnel`, `Bearer`, `AdapterBinding`, `eSIM` or provider-native resource MUST NOT become the authority for the contract. Execution artifacts may change while the contract remains stable.

## 4. Application/customer model

A `ConnectivityPrincipal` may be a USER, DEVICE, APPLICATION, ORGANIZATION, GOVERNMENT, NGO, NETWORK_OPERATOR or SERVICE.

An authorized principal may request connectivity for itself or authorized beneficiaries. Therefore an application MAY purchase or sponsor connectivity for its users or devices.

Authorization is scoped: the ability to purchase connectivity does not confer authority over application data, identities, messages, content, or provider internal topology.

## 5. Provider sovereignty

ADCOS does not require a global topology database. Providers retain domain-local topology and routing authority. They export only what is required for interoperability: capabilities, service boundaries, offers, commitments, relevant execution endpoints/segments and measurements/evidence.

Provider secrets, subscriber records, proprietary topology and provider-native SDK types MUST NOT enter the ADCOS core. Federation membership does not imply universal trust.

## 6. Execution boundary

The normative execution adapter boundary is capability-oriented. Adapters MAY expose operations equivalent to `inspect_capabilities()`, `inspect_offers()`, `reserve()`, `activate()`, `measure()`, `reconfigure()`, `release()`, and `health()`.

Exact provider-native APIs remain inside adapters. The core MUST NOT import provider-native SDK types.

## 7. Standard-mechanism principle

ADCOS SHOULD leverage established mechanisms rather than reinventing them, including QUIC/TLS, MPTCP/MP-QUIC, 3GPP ATSSS, provider IGP/SDN/SR, SCION/path segments, DTN/BPv7, O-RAN/RIC interfaces, and GSMA/TM Forum/CAMARA-style APIs.

ADCOS coordinates these mechanisms; it does not claim ownership of their native protocol semantics.

## 8. Optimizer boundary

Path and execution optimization is replaceable. For a fixed evidence/policy snapshot, optimizer behavior MUST be deterministic with respect to the same input snapshot and declared tie-breaking rules.

Optimizers MUST NOT override hard contract constraints, identity/trust authorization, security requirements, provider trust restrictions, evidence obligations or policy prohibitions.

ML is reference/experimental unless explicitly adopted into the normative decision contract.

## 9. Closed-loop assurance

The lifecycle is:

```text
Intent -> Offer Discovery -> Eligibility + Policy
       -> Connectivity Contract -> Execution Plan
       -> Execution -> Delivery / Usage -> Evidence
       -> Assurance -> Replan / Failover / Compensation
```

Assurance distinguishes compliant, degraded, violated, unknown/stale evidence, failed and deliberately terminated states.

Replanning MUST NOT silently weaken hard contract constraints. A realization that cannot satisfy a hard contract must enter an explicit degraded/failed state or trigger explicit contract renegotiation.

## 10. Simple and complex deployments

A single-provider request may be:

```text
Intent -> Offer -> Contract -> one ExecutionSegment -> Assurance
```

A complex request may use multiple providers, segments, access mechanisms and failover alternatives under one contract.

Federation, multipath and advanced optimization are capabilities, not requirements for every deployment.

## 11. Commercial boundary

Connectivity acquisition is contract-centric and auditable. A reference lifecycle is:

```text
INTENT -> OFFER_SELECTED -> CONTRACT_ACTIVE -> EXECUTION_ACTIVE
        -> DELIVERY -> ASSURED -> USAGE_FINAL
        -> SETTLEMENT_PENDING -> SETTLED
```

External payment systems may perform money movement. ADCOS records connectivity commercial authority and settlement references necessary to reconcile consumption and provider commitments.

## 12. Developer-facing API semantics

Applications should be able to create connectivity intents, discover offers, check eligibility, accept offers, create/get connectivity contracts, inspect execution status and assurance, retrieve usage, receive signed events, and terminate or modify contracts.

Applications SHOULD NOT need to know about Node, Link, gNB, UPF, radio bearer, provider routing protocol or equivalent implementation detail.

## 13. Normative/reference/experimental separation

**Normative:** identity and authority, contracts, evidence, policy and eligibility, federation boundaries, protocol envelopes, security invariants, state transitions and compatibility.

**Reference:** deterministic baseline optimizer, Linux/runtime agents, simulators, default adapters and deployment patterns.

**Experimental:** ML/RL optimization, predictive assurance, novel traffic scheduling/routing, decentralized optimization and new access technologies.

## 14. Application integrations

### ShareNet

ShareNet remains responsible for content distribution, P2P propagation, publisher trust, contribution accounting and application economics. ADCOS supplies connectivity for gateways, relays and optionally user cohorts.

### RoamLink

RoamLink remains responsible for mobile observation, device context, mobile execution, eSIM product behavior and mobile UX. ADCOS supplies provider exchange, connectivity contracts, federation and assurance.

### COMOS

COMOS remains responsible for identity, communication bundles, conversations, channel semantics and delivery semantics. ADCOS supplies underlying connectivity for communication gateways, relays and endpoints.

## 15. Migration rule

Architecture 1.0 is historical evidence and MUST be retained as superseded architecture. Existing implementation is not presumed authoritative merely because it is already merged.

Every existing module/work item is classified as RETAIN, REFACTOR, DEMOTE, REPLACE or ARCHIVE. Historical acceptance evidence MUST NOT be rewritten.
