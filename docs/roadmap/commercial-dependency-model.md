# ADCOS Commercial Roadmap — Canonical Roadmap Projection

This file is retained as the historical/commercially-focused projection of the ADCOS implementation program. It is **not an independent authority**.

The sole authoritative implementation roadmap is:

- `spec/architect/roadmap.yaml` — machine-readable canonical roadmap and dependency DAG
- `spec/architect/roadmap.md` — human-readable projection

Frozen architecture remains authoritative in `spec/architecture.md`, `spec/architecture-lock.md`, `spec/work-items.md`, and `spec/dependency-graph.md`.

## Current verified commercial state

| Work Item | State | Dependency position |
|---|---|---|
| W051 CommercialCore | accepted-merged | chain head |
| W052 UsageLedger | **active-authorized** | hard dependency on W051; current implementation target |
| W053 EconomicAllocation | accepted-merged | hard dependency on W051 and W052; no implementation authorization |
| W044 Payment Provider Adapters | accepted-merged | hard dependencies W051/W053 |
| W045 Eligibility / Trust / Jurisdiction | accepted-merged | hard dependencies W051/W053/W044 |
| W046 Developer API / SDK / Webhooks | accepted-merged | hard dependencies W051/W052/W053/W044/W045 |
| W047 Marketplace Discovery / Proximity / Path Selection | accepted-merged | hard dependencies W051/W044/W045/W046 |
| W048 Provider Sharing Runtime | accepted-merged | hard dependencies W041/W042/W051; W050 advisory input only |
| W049 Provider + Buyer Client Runtime | accepted-merged | hard dependencies W046/W047/W048 |
| W050 Capability / Isolation Matrix | accepted-merged | independent hard dependency set; advisory input to W048/W049 |

W040 remains an independent physical-evidence track and is not a hard dependency of the commercial program. W043 remains retired/unassigned.

## Authority and authorization rule

Commercial roadmap membership does not authorize implementation. The only implementation permission comes from an active repository-local authorization under `spec/architect/authorizations/`, with its governing decision and exact baseline.

At the current checkpoint the sole active implementation authorization is `WORK-052-CORE-001`, issued by DEC-0059 and baseline-reconciled by DEC-0060 / LEDGER-RECON-009. The W052 implementation PR must branch from the exact live authorization-bearing mainline and must not modify `spec/architect/`.

## Historical record

The previous version of this document preserved the 2026-08-31 W041/W042 commercial-era numbering and is retained in Git history. DEC-0052 and the subsequent governance transitions superseded that interpretation. The canonical commercial numbering is now W051/W052/W053, with W041 reserved for NetworkPath and W042 for event-driven platform integration.

The former document's detailed reconciliation history is preserved in Git history and the governing decision/reconciliation records. No historical facts are silently erased; this replacement only removes the possibility of the stale document being mistaken for current authority.
