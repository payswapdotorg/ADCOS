# ACR-014: Architecture 1.1 Freeze — application connectivity model

## Status
ACCEPTED (approved via DEC-0098; synchronized updates delivered with the
M001 delivery under authorization M001-CORE-001; acceptance of the exact
delivery head is recorded as DEC-0100)

## Motivating experience / research
- `spec/research/standards-and-use-cases.md` — the Architecture 1.1 direction is
  grounded in IETF RFC 9315 (intent), QUIC, MPTCP/MP-QUIC, 3GPP ATSSS, SCION,
  DTN/BPv7, O-RAN, GSMA/TM Forum/CAMARA and ETSI MEC boundaries.
- The accepted Architecture 1.0 execution history (WORK-001..WORK-057, ledger
  `spec/architect/execution-ledger.yaml`) demonstrated that a Node/Link/Path
  topology-centric core and implementation-first Work Items make the
  application-facing connectivity outcome (buy/sponsor/assure connectivity)
  a derived property instead of the canonical object.
- The Architecture 1.1 transition package (PR #24, merged as
  `40737a0c716eff3ad05753431c24c2717afb2a68`) defines a complete, reviewed
  target: architecture, normative locks (LOCK-101..LOCK-120), application
  model, work items M001–M014, dependency graph, migration classification
  matrix, and vertical proofs for ShareNet/RoamLink/COMOS.

## Proposed change
Adopt Architecture 1.1 as the sole normative forward architecture:

1. Promote the 1.1 architecture semantics and LOCK-101..LOCK-120 into the
   canonical authority files (`spec/architecture.md`,
   `spec/architecture-lock.md`).
2. Preserve the Architecture 1.0 snapshot verbatim as historical evidence
   under `spec/history/` (architecture, locks, work-item registry,
   dependency graph), with an explicit supersedence chain. No historical
   acceptance record is rewritten.
3. Promote the successor Work Item registry (M001–M014) and dependency graph
   to canonical status; preserve the 1.0 registries as history.
4. Accept the migration classification matrix (RETAIN / REFACTOR / DEMOTE /
   REPLACE / ARCHIVE) as the binding classification for existing
   implementation under 1.1.
5. Accept the vertical-proof boundaries (ShareNet, RoamLink, COMOS) as
   compatibility proofs, not ownership transfers.

Alternatives considered: (a) remain on Architecture 1.0 and keep accumulating
execution-layer Work Items — rejected because the application connectivity
outcome would remain a derived property and provider/topology semantics would
keep leaking upward; (b) incremental per-domain ACRs — rejected because the
contract-canonical object model, authority boundaries and registry are one
coherent change; (c) rewrite history — rejected by the frozen history rules.

## Mission consistency
The mission (`spec/mission.md`) — adaptive, interoperable, policy-controlled
connectivity across independently operated networks — is preserved and
sharpened: `ConnectivityContract` makes the acquired-connectivity outcome
first-class, provider sovereignty is locked (LOCK-104/105/110), and the
application model widens who can acquire connectivity without concentrating
authority (LOCK-117). Nothing in this ACR abandons or narrows the mission.

## Affected architecture sections and locks
- `spec/architecture.md` — all sections (superseded snapshot preserved at
  `spec/history/architecture-1.0.md`)
- `spec/architecture-lock.md` — superseded LOCK-001..LOCK-0xx preserved at
  `spec/history/architecture-lock-1.0.md`; successor locks LOCK-101..LOCK-120
  become normative
- `spec/work-items.md` — 1.0 registry preserved at
  `spec/history/work-items-1.0.md`; successor registry M001–M014 promoted
- `spec/dependency-graph.md` — 1.0 graph preserved at
  `spec/history/dependency-graph-1.0.md`; successor graph promoted
- Governance/process docs (`spec/governance.md`, `spec/change-control.md`,
  `spec/workflow.md`) — synchronized pointer updates only, no process
  semantic change

## Compatibility analysis
- Wire compatibility: no protocol envelope or schema change in this ACR;
  Protocol Version 1.0 and `spec/schemas/protocol.json` remain unchanged.
- Persisted state: no implementation state is migrated or deleted; existing
  implementation is classified by the migration matrix, not rewritten.
- Live sessions/federation: unaffected by this governance act.
- Deployments: mixed-version operation continues under Protocol 1.0
  compatibility authority (WORK-029 lineage).
- Existing acceptance evidence: preserved verbatim; historical verdicts
  remain true for the architecture version under which they were accepted.

## Work-item and dependency impact
- Affected Work Items: the frozen 1.0 registry (52 items, WORK-043 retired)
  becomes historical; the successor registry M001–M014 becomes the forward
  contract set. Lifecycle history for W-items remains in the execution
  ledger and is never rewritten.
- Dependency recalculation: the successor dependency graph
  (`spec/dependency-graph-1.1.md`) is acyclic and gates R7 on M001; the 1.0
  graph is preserved as history. R4/W040 physical evidence and W048
  accepted-not-restored status are untouched.

## Migration / rollback plan
- Migration: M001 executes this freeze; M002..M014 implement forward from the
  1.1 contracts. Existing modules are re-baselined per the classification
  matrix as each successor Work Item reaches them.
- Rollback: because the 1.0 snapshot is preserved verbatim under
  `spec/history/`, a future accepted ACR can restore 1.0 authority by
  reversing the promotion pointers; no information is destroyed.

## Architect decision
DEC-0098 (2026-09-09, sole Architect, single-agent mode): approved the
promotion path and activated Work Item M001 under repository-local
authorization `M001-CORE-001` from baseline `40737a0c716eff3ad05753431c24c2717afb2a68`.
The synchronized updates are delivered by the M001 freeze delivery (this
change); the exact delivery head is reviewed and accepted under DEC-0100.

## Resulting architecture version
Architecture Version 1.1 (recorded in `spec/architecture.md` upon the M001
delivery). Protocol Version unchanged (1.0). Roadmap version advances to 1.6
(activation) and 1.7 (completion) under the corresponding durable decisions.
