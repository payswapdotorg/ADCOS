# ADCOS Current State

**Persistent Architect snapshot — updated after PR #60 merge.**

## Repository

- Repository: `github.com/pectoraux/ADCOS`
- Current `main`: `93efa54f1edc2ec3c0bb5646827719f92af06b86`
- Architecture version: `1.0` (`spec/architecture.md`)
- Protocol version: `1.0` (`spec/schemas/protocol.json`)

## Authority

GitHub/repository state is the persistent Architect. Chat is not an authority source. Durable architecture, locks, accepted ACRs, dependency graph, Work Item contracts, persistent decisions, accepted precedents, verification evidence, documentation, and history follow `spec/architect/authority-order.md`.

## Execution state

- Active Work Item: `WORK-040`
- Execution mode: `correction-authorized`
- W040 status: `in-review`
- W040 implementation PR: `#48`
- W040 implementation head: `ee9b356020b6450d85837f60e60c41d08f0ec09a`
- W040 original baseline: `1669ae9a396838b72ba461c846b98e84478ab24f`
- The current authorization is correction-only and does not authorize unrelated implementation or any W041+ work.

## W040 review disposition

W040 remains **CHANGES_REQUIRED**. The current repository-local authorization permits only the Architect-requested correction cycle:

1. obtain and prove a real-device participant for criterion 1;
2. obtain and prove a defensible physical 5G access path for criterion 2, if actually available;
3. preserve the already demonstrated non-cellular, relay/backhaul, failover, and operational evidence;
4. preserve all authority, adapter-boundary, provenance, anti-promotion, and frozen-spec invariants.

A software rehearsal cannot close a physical criterion by inference.

## Accepted Work Items

`WORK-001` through `WORK-039` are Architect-accepted and merged.

## Blocked / gated Work Items

- `WORK-040`: correction cycle active; acceptance remains blocked pending Architect re-review.
- `WORK-041+`: not yet part of the frozen backlog; blocked pending an accepted roadmap change.

## Open ACRs

- `ACR-004` — Connectivity Commerce Plane — `PROPOSED`, PR #49; not on main.

## Open external evidence obligations

Tracked in `spec/architect/evidence-obligations.yaml`. Physical evidence remains separate from software evidence and cannot be closed by inference.

## Persistent Architect package

PR #60 (`governance: establish persistent Architect package`) merged as `93efa54f1edc2ec3c0bb5646827719f92af06b86`. PA-001 is authoritative on main: an `in-review` ledger entry is descriptive only and is never an implementation authorization.

## Resume rule

A fresh Architect reads this file, `execution-state.yaml`, `execution-ledger.yaml`, the applicable decision and authorization records, and the active Work Item handoff before acting. No prior chat is required or authoritative.