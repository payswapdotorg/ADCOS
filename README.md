# ADCOS

**Adaptive Distributed Connectivity Operating System**

ADCOS is a future-proof connectivity fabric designed to compose heterogeneous connectivity infrastructure—5G, Wi-Fi, fixed networks, satellite, microwave, mesh, device-to-device links, and future 6G/IMT-2030 and beyond—into one authenticated, policy-driven, federated network.

It is not a new radio PHY and does not assume ordinary smartphones can become 5G base stations through software alone. Instead, ADCOS standardizes the fabric and adapter layer above physical access technologies so that today's 5G can be replaced or augmented by tomorrow's 6G without rewriting the network.

## Authoritative specification

- `spec/architecture.md` — frozen protocol architecture
- `spec/architecture-lock.md` — non-negotiable invariants
- `spec/work-items.md` — implementation backlog
- `spec/dependency-graph.md` — dependency-ordered implementation graph

The architecture is deliberately modeled after a strict architect → implementer → PR → review → correction → acceptance workflow.

## Implementation rule

**Architecture first. Code second.**

Z.ai is the implementation agent. The Architect is the authority over architecture and acceptance. A successful CI run does not make an architecture-violating implementation acceptable.
