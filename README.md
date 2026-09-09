# ADCOS

**Adaptive Distributed Connectivity Operating System**

ADCOS is evolving into a programmable connectivity exchange and orchestration
layer for heterogeneous connectivity: **one connectivity contract, many networks,
continuous fulfillment.** It composes provider-supplied 5G, Wi-Fi, fixed, satellite,
mesh and future access capabilities without requiring ADCOS to own provider-native
topology or radio/core authority.

## Authoritative specification and transition package

### Forward implementation target — Architecture 1.1

- `spec/architecture-1.1-proposed.md` — target architecture
- `spec/architecture-lock-1.1-proposed.md` — target normative locks
- `spec/application-model.md` — application/customer connectivity model
- `spec/work-items-1.1.md` — forward implementation sequence
- `spec/dependency-graph-1.1.md` — forward dependency model
- `spec/migration/classification-matrix.md` — 1.0 → 1.1 migration classification
- `spec/integration/vertical-proof.md` — ShareNet/RoamLink/COMOS proof boundary

### Preserved legacy baseline — Architecture 1.0

- `spec/architecture.md` — historical/frozen 1.0 baseline
- `spec/architecture-lock.md` — historical/frozen 1.0 locks
- `spec/work-items.md` — historical 1.0 implementation backlog
- `spec/dependency-graph.md` — historical 1.0 dependency graph

Architecture 1.0 is retained for migration and historical integrity. **New ADCOS
behavior MUST be designed from the Architecture 1.1 target and its locks; agents
must not fall back to 1.0 semantics simply because the old implementation exists.**

`M001 — Architecture 1.1 Freeze` is the controlled promotion gate. Once M001 is
accepted through the ACR/change-control process, the accepted 1.1 successor
snapshots become the sole normative forward architecture.

## Agent governance

- `spec/architect/roadmap.yaml` — sole canonical program roadmap
- `spec/architect/resume-protocol.md` — deterministic fresh-session recovery
- `spec/architect/LLM-ARCHITECT-HANDOFF.md` — persistent Architect/Tech Lead handoff
- `docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md` — Tech Lead entry point and 1.1 routing
- `docs/tech-lead/worker-model.md` — 3 direct workers × 3 subagents

The repository is designed to be sufficient to implement the ADCOS 1.1 roadmap
without access to conversation history.

## Implementation rule

**Architecture first. Code second.**

The persistent Architect is the authority over architecture, governance,
authorization, acceptance and merge. The Tech Lead orchestrates authorized
implementation work. A successful CI run does not make an architecture-violating
implementation acceptable.

For autonomous engagements, a single LLM may act as both Architect and Tech Lead
while retaining every repository-local authority, evidence and change-control
constraint.

## Current transition state

R6 Provider Onboarding & Federation is complete. The repository is now at the
Architecture 1.1 transition boundary. There is currently no active implementation
authorization. The immediate next gate is **M001 — Architecture 1.1 Freeze**;
R7 Universal Connectivity Commerce follows M001 and is implemented from the
accepted 1.1 contract model.

R4/W040 remains an independent physical-validation track. W048 remains
accepted-not-restored and may not be silently recreated.

## Verification

Run the specification and fresh-session checks from the repository root:

```bash
python3 tools/spec_check.py
python3 tools/fresh_session_check.py
```

The fresh-session checker verifies that the Architecture 1.1 forward target, Tech
Lead handoff, single-agent mode, 3x3 worker limit and current governance checkpoint
are present and that the persisted execution snapshot matches `origin/main` when
that ref is available.

CI runs the specification consistency checks on every push and pull request.
