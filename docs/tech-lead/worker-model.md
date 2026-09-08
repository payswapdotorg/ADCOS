# ADCOS 3x3 Worker Model

## Hierarchy

```text
Tech Lead
├── Worker A
│   ├── A1
│   ├── A2
│   └── A3
├── Worker B
│   ├── B1
│   ├── B2
│   └── B3
└── Worker C
    ├── C1
    ├── C2
    └── C3
```

The Tech Lead has at most 3 direct workers. Each worker has at most 3 subagents.

## Responsibilities

### Worker A — Core exchange

Contracts, offers, policy, eligibility, evidence and assurance.

### Worker B — Execution

Execution plans, segments, adapters, standards integration and legacy migration classification.

### Worker C — Product/economics/verification

Developer API, usage/commercial reconciliation, vertical proofs, conformance and adversarial architecture audits.

## Boundaries

Subagents must not change normative architecture, authority or contracts without Tech Lead approval under the repository change-control process.

Workers return exact files changed, tests run and exact results, unresolved findings, authority-impact statement, and evidence references.

The Tech Lead verifies all claims against the repository.
