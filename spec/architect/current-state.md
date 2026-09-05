# ADCOS Current State

**BLOCKED — R0 restored the accepted mainline artifacts; R1 remains blocked pending durable execution-ledger normalization.**

## Repository

- Repository: `github.com/pectoraux/ADCOS`
- Current canonical `main`: `7fb47bb312708d06f3b3c1ba0496104362c7d135`
- Roadmap: `spec/architect/roadmap.yaml` — **FROZEN, Version 1.0, sole program-roadmap authority**
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Governance state

- Decision: `DEC-0081`
- R0: `COMPLETED`
- R1: `BLOCKED_LEDGER_RECONCILIATION`
- Active Work Item: none
- Active authorization: none
- Exactly zero implementation authorizations are active.
- The Architect is the sole review, acceptance, and merge authority.

## Mainline restoration

R0 PR #157 restored the previously accepted W044-W049 implementation surfaces onto the current mainline from the repository's historical accepted-artifact recovery tree. The clean restoration was one commit directly on the current mainline and changed no `spec/architect/` governance files.

Restored packages:

- `payment/`
- `eligibility/`
- `developerapi/`
- `marketplace/`
- `client/`

Restored verification/evidence surfaces include the W044-W049 deterministic selftests and the five corresponding CI invocations. The restoration is not a new implementation and does not re-accept those Work Items.

## Accepted history

W044, W045, W046, W047, W048, W049, W050, W051, W052, and W053 remain accepted according to durable repository/GitHub acceptance history. Their exact reviewed/merge provenance is recorded in `spec/architect/roadmap.yaml` and DEC-0080; R0 restores missing implementation artifacts without falsifying that history.

W040 remains independent, `in-review`, unaccepted, with its physical evidence obligations still open and W040-owned.

## R1 blocking condition

`spec/architect/execution-ledger.yaml` still represents W044-W050 using the earlier registered/activation-era lifecycle snapshot. That ledger is historical lifecycle authority and must be reconciled explicitly rather than silently replaced or rebuilt from memory.

R1 must:

1. use the live ledger as the source document;
2. preserve all historical Work Item fields and all prior reconciliation records except explicitly authorized state additions;
3. add a new reconciliation for the R0-restored mainline;
4. align the lifecycle representation with the durable accepted history already established by DEC-0080 and the historical accepted delivery records;
5. leave exactly zero active implementation authorizations after reconciliation.

No implementation may begin until R1 is accepted.

## Source of truth

A fresh clone of `main` is sufficient to reconstruct ADCOS. The repository itself is the only persistent source of truth. Chat history, model memory, prompts, issue prose, PR conversation, and external planning documents have zero authority.

The authority chain is:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → durable decisions + execution ledger/state → active authorization → implementation/evidence`

The roadmap controls program order. The ledger controls lifecycle history. Execution state controls the current execution slot. Repository-local authorizations control implementation permission.
