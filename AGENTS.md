# ADCOS Agent Entry Point

ADCOS is self-describing. A new Architect or implementation agent MUST derive authority from the repository and live GitHub state, never from chat history.

## Resume order

1. Read `README.md`.
2. Read `spec/architect/resume-protocol.md`.
3. Read `spec/architect/current-state.md`.
4. Read `spec/architect/authority-order.md`.
5. Read `spec/architect/execution-state.yaml`.
6. Read `spec/architect/execution-ledger.yaml`.
7. Identify the active Work Item and read its authorization and handoff.

## Authority

Repository/GitHub state is the persistent Architect. Chat transcripts are not authority. A chat decision governs only after the Architect persists it in `spec/architect/`.

## Live-main rule

Always compare `execution-state.yaml.repository.main_sha` with the actual `origin/main` SHA before acting. If they differ, inspect the commits between them and re-read the persistent Architect package on the newer main. The newer repository state supersedes an older snapshot.

The same rule applies after every merge: reconcile stale recorded SHAs before starting new implementation work.

## Authorization

While `execution.mode` is `implementing`, exactly one Work Item authorization may be active. No active repository-local authorization means implementation MUST stop. A successful CI run does not itself authorize or accept an implementation.

## Lean governance

Do not create governance artifacts merely for ceremony.

Routine sequential Work Item progression is:

`implementation -> CI -> Architect acceptance -> ledger acceptance -> atomic authorization handoff -> next implementation`

Create a new ACR only when frozen architecture/registry semantics actually change. Create a new decision record only when the persistent decision/acceptance machinery requires one.

## Frozen architecture

Never modify frozen architecture documents from an implementation PR. An apparent architecture contradiction must be handled through the ACR process, not by weakening a validator.

## Evidence

Never convert software/emulated evidence into physical PASS by inference. W040 physical obligations are independent and remain governed by their own evidence records.

## Working practice

Prefer a local Git clone and ordinary Git history for multi-file changes. Avoid piecemeal Contents-API mutation of authoritative files. Do not write directly to `main` for implementation or governance transitions that require review.

## Verification

Before acting from a fresh session, run:

```bash
python3 tools/spec_check.py
```

If the persistent governance package fails its checks, repair the governance state through the proper review mechanism; never weaken the invariant to make a task pass.
