# ADCOS Agent Entry Point

This repository is self-describing. A new Architect or implementation agent MUST derive authority from the repository, never from chat history.

## First read

1. `README.md`
2. `spec/architect/resume-protocol.md`
3. `spec/architect/current-state.md`
4. `spec/architect/authority-order.md`
5. `spec/architect/execution-state.yaml`
6. `spec/architect/execution-ledger.yaml`

Then read the active Work Item authorization and handoff named by `execution-state.yaml`.

## Authority rule

The repository/GitHub state is authoritative. Chat transcripts are not authority. A chat decision governs only after it is persisted by the Architect into `spec/architect/`.

## Resume rule

Always compare the recorded `execution-state.yaml.repository.main_sha` with the actual `origin/main` SHA before acting. If main has advanced, inspect the intervening commits and re-read the persistent Architect package on the advanced main. The newer repository state supersedes stale local snapshots.

## Active execution rule

`execution-state.yaml` determines the active Work Item and authorization. Exactly one active authorization is allowed while `execution.mode` is `implementing`. No repository-local authorization means implementation MUST stop.

## Lean transition model

Do not create governance artifacts merely for ceremony.

For routine sequential Work Item execution, preserve only the repository-required lifecycle:

`implementation PR -> CI -> Architect acceptance -> ledger acceptance -> atomic authorization handoff -> next implementation`

Create an ACR only when frozen architectural semantics/registry structures actually need to change. Create a separate decision record only when the repository's decision/acceptance machinery requires one.

## Work Item completion

An implementation is not automatically accepted because CI is green. The Architect must persist the acceptance decision and ledger transition, including the exact reviewed SHA and merge SHA where required by the decision schema.

## Handoff safety

Never leave `execution.mode: implementing` with zero active authorizations. Never create two simultaneous active authorizations. Preserve W040 physical evidence obligations and never convert software evidence into physical PASS by inference.

## Coding scope

An implementation agent may modify only paths authorized by its active `WORK-XXX.yaml`. Frozen `spec/` architecture documents and persistent Architect records are not changed from an implementation PR unless the governing process explicitly authorizes that change.

## Verification

Before acting, run `python3 tools/spec_check.py`. A failure in the persistent Architect package is a governance inconsistency: repair the state through the proper governance mechanism rather than weakening the invariant.
