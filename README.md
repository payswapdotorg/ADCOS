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

## Specification governance

WORK-001 established the governance layer around the frozen specification:

- `spec/governance.md` — document registry, naming conventions, versioning policy (architecture / protocol / schema / implementation versions are distinct lines), terminology ownership, machine-readable schema locations
- `spec/change-control.md` — Architecture Change Request (ACR) process; ACR records live in `spec/acr/`
- `spec/workflow.md` — Work Item / PR review rules and the Architect acceptance gate
- `spec/schemas/` — canonical location for future machine-readable schemas and registries (content begins with WORK-002)

The frozen documents change only through the ACR process. A normal implementation PR is never allowed to silently become an architecture change.

Run the deterministic specification consistency checks (offline, zero dependencies):

```bash
python3 tools/spec_check.py
```

CI runs the same checks on every push and pull request.
