# ADCOS

**Adaptive Distributed Connectivity Operating System**

ADCOS is evolving into a programmable connectivity exchange and orchestration
layer for heterogeneous connectivity: **one connectivity contract, many networks,
continuous fulfillment.** It composes provider-supplied 5G, Wi-Fi, fixed, satellite,
mesh and future access capabilities without requiring ADCOS to own provider-native
topology or radio/core authority.

## Authoritative specification and transition package

### Normative architecture — Architecture 1.1 (FROZEN via ACR-014)

- `spec/architecture-1.1-proposed.md` — target architecture
- `spec/architecture-lock-1.1-proposed.md` — target normative locks
- `spec/application-model.md` — application/customer connectivity model
- `spec/work-items-1.1.md` — forward implementation sequence
- `spec/dependency-graph-1.1.md` — forward dependency model
- `spec/migration/classification-matrix.md` — 1.0 → 1.1 migration classification
- `spec/integration/vertical-proof.md` — ShareNet/RoamLink/COMOS proof boundary

### Preserved legacy baseline — Architecture 1.0 (superseded, archived)

- `spec/history/architecture-1.0.md` — preserved verbatim 1.0 snapshot
- `spec/history/architecture-lock-1.0.md` — preserved verbatim 1.0 locks
- `spec/history/work-items-1.0.md` — preserved verbatim W001–W057 registry
- `spec/history/dependency-graph-1.0.md` — preserved verbatim 1.0 dependency graph

The canonical files `spec/architecture.md`, `spec/architecture-lock.md`,
`spec/work-items.md` and `spec/dependency-graph.md` now carry the
Architecture 1.1 successor content (FROZEN via ACR-014 with the M001
delivery)

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

This section projects the authoritative program state from
`spec/architect/current-state.md` (the sole authority for current-state wording).

R6 Provider Onboarding & Federation is complete. **M001 — Architecture 1.1
Freeze is ACCEPTED (DEC-0100; ACR-014 ACCEPTED; Architecture 1.1 FROZEN as the
sole normative forward architecture, 1.0 preserved under `spec/history/`).**
**R7 — Universal Connectivity Commerce is ACTIVE** under DEC-0101 as a bounded
program authorization (`R7-CORE-001`) with the R7 charter
(`spec/architect/work-items/R7-charter.md`) declaring the child work-item
scopes M002-M014. **M002 — Connectivity Contract Core is ACCEPTED (DEC-0102;
head 0112943, merge 0ffdf47; the canonical `contracts/` domain is live).**
**M003 — Offers and Provider Capability Exchange is ACCEPTED (DEC-0103; head
eace143, merge 4090e03; the provider-domain `offers/` model is live with its
49/49 battery). M013 — Developer Connectivity API is ACCEPTED (DEC-0113; head
69ef8de, merge 8f4d58a2; chain-independent).** **M009 — Usage and Commercial
Reconciliation is ACCEPTED (DEC-0109; head 5a807cd, merge c985b88; the
usage/commercial/allocation/payment domains re-bound to the canonical
contracts/ domain with the payment 44/44 and eligibility 46/46 DEC-0099
re-baselines landed).** **M010 — Vertical Proof — ShareNet is ACCEPTED
(DEC-0110; head d5be84e, merge d0d26d3; the 33/33 sharenet battery is
CI-wired).** **M011 — Vertical Proof — RoamLink is ACCEPTED (DEC-0111;
head fb4a921, merge c0f23c8; the 56/56 roamlink battery is CI-wired).**
**M012 — Vertical Proof — COMOS is ACCEPTED (DEC-0112; head 201ceb8e,
merge 6e3d09f; the 33/33 comos battery is CI-wired).**
**M004 — Eligibility and Policy is ACCEPTED (DEC-0104; head 92f293b, merge
a52e1ee; the policy battery evolved to 103/103).**
**M005 — Evidence and
Assurance is ACCEPTED (DEC-0105; head a0c4aff, merge ccae488; the 97/97
assurance battery is CI-wired).**
**M006 — Execution Plan is ACCEPTED (DEC-0106; head 764007b, merge
1f9f509; the 36/36 executionplan battery is CI-wired).**
**M007 — Provider/Standard Adapters is ACCEPTED (DEC-0107; head 1636b15,
merge cc93bb4; the adapter battery expanded to 70/70 — the CI step already
wired and green at the merged head; one disclosed payment-battery
frozen-family repair ratified).**
**M008 — Replan and Failover is the current child work item.** Per-child
acceptance (DEC-0104 onward) is
mandatory and is the serialization point; the Tech Lead may decompose,
dispatch, integrate and deliver within the authorized child scopes without
further pre-implementation authorization ceremonies.

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
