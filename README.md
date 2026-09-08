# ADCOS

**Adaptive Distributed Connectivity Operating System**

ADCOS is a future-proof connectivity fabric designed to compose heterogeneous connectivity infrastructure—5G, Wi-Fi, fixed networks, satellite, microwave, mesh, device-to-device links, and future 6G/IMT-2030 and beyond—into one authenticated, policy-driven, federated network.

It is not a new radio PHY and does not assume ordinary smartphones can become 5G base stations through software alone. Instead, ADCOS standardizes the fabric and adapter layer above physical access technologies so that today's 5G can be replaced or augmented by tomorrow's 6G without rewriting the network.

## Authoritative specification

- `spec/architecture.md` — current frozen protocol architecture
- `spec/architecture-lock.md` — current non-negotiable invariants
- `spec/work-items.md` — current implementation backlog
- `spec/dependency-graph.md` — dependency-ordered implementation graph
- `spec/architect/roadmap.yaml` — sole canonical program roadmap
- `spec/architect/resume-protocol.md` — deterministic fresh-session recovery
- `spec/architect/LLM-ARCHITECT-HANDOFF.md` — persistent Architect/Tech Lead handoff
- `docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md` — Tech Lead entry point
- `docs/tech-lead/worker-model.md` — 3 direct workers × 3 subagents

The repository is designed to be sufficient to implement ADCOS without access
to conversation history.

## Implementation rule

**Architecture first. Code second.**

The persistent Architect is the authority over architecture, governance,
authorization, acceptance and merge. The Tech Lead orchestrates authorized
implementation work. A successful CI run does not make an architecture-violating
implementation acceptable.

For autonomous engagements, a single LLM may act as both Architect and Tech
Lead while retaining every repository-local authority, evidence and change-control
constraint.

## Specification governance

The frozen documents change only through the ACR process. A normal implementation
PR is never allowed to silently become an architecture change.

The persistent Architect package records current state, authority precedence,
execution state, lifecycle ledger, evidence obligations, decisions,
authorizations, review protocols and resume rules. **No repository-local active
authorization means implementation must stop.**

## Current program direction

R6 Provider Onboarding & Federation is complete. R7 Universal Connectivity
Commerce is the next unlocked software gate. R8 hardens resilience, mobility and
scale; R9 adds future access technologies strictly through the adapter boundary.

The proposed Architecture 1.1 package is present as a deliberate successor
proposal. It makes `ConnectivityContract` the canonical durable object and
permits authorized applications to purchase or sponsor connectivity for their
users/devices. It is not current architecture authority until formally promoted
by the repository's ACR/change-control process.

## Verification

Run the specification and fresh-session checks from the repository root:

```bash
python3 tools/spec_check.py
python3 tools/fresh_session_check.py
```

The fresh-session checker verifies that the Tech Lead handoff, single-agent mode,
3x3 worker limit and current governance checkpoint are present and that the
persisted execution snapshot matches `origin/main` when that ref is available.

CI runs the specification consistency checks on every push and pull request.
