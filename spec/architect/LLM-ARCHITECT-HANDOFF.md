# ADCOS — Durable LLM Architect Handoff

## Purpose

This file is the repository-local continuation anchor for a future LLM acting as the sole Principal Architect, Product Architect, Protocol Architect, Governance Authority, and Adversarial Reviewer.

A future architect must reconstruct truth from the repository and Git history first. Conversation memory, prompts, PR prose, and external notes have zero authority.

## Current authoritative state

- Repository: `github.com/payswapdotorg/ADCOS`
- Default branch: `main`
- Architecture Version: `1.0` — FROZEN
- Protocol Version: `1.0` — FROZEN
- Roadmap Version: `1.3` — FROZEN / AUTHORITATIVE
- Current governance track: `R5_DEVELOPER_CONNECTIVITY_PLATFORM_ACTIVE`
- Current active Work Item: `WORK-056`
- Current active authorization: `WORK-056-CORE-001`
- Implementation ancestry authority: `7ae438d46041b228164cc8880be37dc21f972b6f`
- `R0/R1/R2/R3`: COMPLETE
- `R4`: `PARALLEL_AFTER_R3`, independently represented by W040
- `R6`: `AFTER_R5`
- W040: in-review, unaccepted; EVID-007 and EVID-008 remain OPEN, PHYSICAL, W040-owned
- W048: accepted-not-restored; never restore/recreate/mock/substitute it under W056
- Mainline governance tip: `e3682732ccb2c2416def38d53f40ff0bffdec59a` (the tip the DEC-0092 reconciliation was cut from; the DEC-0092 guarded merge advances it). The authorization anchor compared by `tools/spec_check.py` ARCH-03/ARCH-05/ARCH-08 remains the WORK-056 baseline `7ae438d46041b228164cc8880be37dc21f972b6f`, recorded in `execution-state.yaml repository.main_sha` with anchor-vs-tip semantics.
- DEC-0090 remains historical accepted authority for the original narrow W046 oracle amendment.
- DEC-0091 is the current successor amendment for the active W056 delivery. Its sole canonical record is `spec/architect/decisions/DEC-0091-w056-residual-oracle-amendment.yaml`; DEC-0092 voided the duplicate-identity record `DEC-0091-w056-w054-oracle-scope-amendment.yaml` (byte-recoverable from Git history at commit `46fb7f1`).
- DEC-0092 is the current governance-state reconciliation: DEC-0091 identity disambiguation, state-pin reconciliation, and the dispatch-only exact-head W056/W054 acceptance-battery CI vehicle.

## Current W056 disposition

WORK-056 remains active under `WORK-056-CORE-001`.

PR #17 is open, unmerged, and **ACCEPTANCE WITHHELD — DO NOT MERGE** (Architect review `5558422610`, 2026-09-06). The round-4 delivery head is:
`35ec48a1a207b755da7deb2e7b45c00eba0578ac`

Round 4 incorporated the DEC-0091 governance mainline as a plain merge (no rebase, no force), applied the DEC-0091 case_01/case_24 oracle corrections with case_03 retained byte-identical under DEC-0090, and reported the genuine batteries green (developerapi `56/56`, composition `55/55`, deterministic across repeat runs and `PYTHONHASHSEED`). The review verified the Git-level scope as substantially correct (the seven authorized files, the three intended W046 oracle areas, no `spec/architect/` implementation changes) and withheld acceptance on exactly two gates: the DEC-0091 decision identity was ambiguous (two non-identical records with the same `decision_id`), and the required independent battery execution was not yet established. The delivery is neither accepted nor rejected; DEC-0091 remains live. No red accepted battery may be merged, and no delivery head may move before the acceptance decision.

## Current governance amendment

DEC-0091 is the durable successor to DEC-0090 for the active W056 delivery. Its canonical record (designated by DEC-0092) is `spec/architect/decisions/DEC-0091-w056-residual-oracle-amendment.yaml`. It authorizes exactly one test-file exception:

- path: `tools/composition_selftest.py`
- permitted change: reconcile the SAME single W046 availability fact at the three existing textual pins in case 01, case 03, and case 24, changing obsolete `DEFECT`/import-broken wording to `AVAILABLE`/repaired-state wording (case_03 already applied and retained byte-identical under DEC-0090; case_01/case_24 applied under DEC-0091)
- no authority implementation, production behavior, W048/W040 change, new semantic coverage, or unrelated test change
- one W056 delivery only; it expires at the next Architect acceptance or rejection

The active authorization `spec/architect/authorizations/WORK-056.yaml` is bound to DEC-0091 and names the canonical record file in `scope_amendment_record`.

## Acceptance target for the round-4 exact delivery head

The delivery `35ec48a1a207b755da7deb2e7b45c00eba0578ac` must independently prove, before acceptance:

1. W056 developer API battery: `56/56`.
2. W054 composition battery: `55/55`.
3. Repeat-run and `PYTHONHASHSEED` byte determinism.
4. Exact ancestry from `7ae438d...` with no history rewrite (already delivered and verified by review 5558422610).
5. Exact DEC-0091 scope: only the three existing W046 availability pins change in `tools/composition_selftest.py` (already verified).
6. No new `spec_check` or conformance failure beyond the known clean-root inherited signatures.
7. Architecture 1.0 / Protocol 1.0 and frozen wire semantics remain unchanged.
8. W048 remains accepted-not-restored and W040 physical evidence remains untouched.

Items 1-3 are executed independently at the exact head through the dispatch-only CI job established by DEC-0092 (`.github/workflows/spec-check.yml`, job `w056-w054-acceptance-batteries`, default input `35ec48a1a207b755da7deb2e7b45c00eba0578ac`); the durable GitHub Actions run record is the execution proof, and the Architect may re-dispatch, rerun, or additionally execute both batteries from a local checkout.

Treat worker evidence as claims requiring independent verification. No CI success may be claimed where CI is red. The specification-consistency job carries the known inherited historical failure signature (disclosed and unmasked exactly as on the pre-landing mainline); it is not masked or retried by the battery job.

## Non-negotiable governance rules

- Repository truth outranks conversation truth.
- Exactly one active implementation authorization.
- The Architect is the sole reviewer and merge authority; do not invent a separate reviewer role.
- Do not merge PR #17 in its current or any unverified state.
- Do not silently reinterpret an existing 1.x API contract.
- Do not broaden DEC-0091 beyond its exact path and exact W046 availability-oracle pins.
- No second source of truth.
- API/SDK/webhook surfaces are projections/adapters, not canonical authorities.
- Authentication, observation, topology, route, circuit, capability, policy, capacity, contribution, settlement, and payment remain distinct authority concepts.
- Software evidence never promotes or closes physical evidence.
- Historical ledger/reconciliation records are append-only.
- Never force-reset or rewrite accepted mainline history.

## Frozen program route

`R0 → R1 → R2 → R3 → R4/R5 → R6 → R7 → R8 → R9`

Do not reorder it. Do not reopen a completed release gate without durable change control. R4 remains parallel to R5/R6 as already governed.

The product exit criterion remains the frozen “Stripe of connectivity” objective: an external application can request, manage, observe, and reconcile connectivity through stable APIs without adopting an ADCOS UI or knowing provider/access technology/path/payment implementation details.

## Immediate next architect action

Do not start a new Work Item.

Do not merge PR #17.

The round-4 delivery `35ec48a1a207b755da7deb2e7b45c00eba0578ac` is already on the governance mainline (plain merge, no rebase, no force) with the three authorized W046 availability-oracle pin corrections applied and its Git-level scope verified by review `5558422610`. The delivery head must NOT move before the acceptance decision.

The next governance actions, in order:

1. Guarded-merge the DEC-0092 reconciliation (the DEC-0091 identity disambiguation + state-pin reconciliation + the exact-head battery vehicle) onto the mainline.
2. Establish the independent battery execution: dispatch the `w056-w054-acceptance-batteries` job at the exact head `35ec48a` (its default input) and read the durable GitHub Actions run record; re-dispatch, rerun, or execute locally at will.
3. Perform the adversarial acceptance review of `35ec48a` (batteries `56/56` and `55/55`, determinism, scope, ancestry, frozen-surface integrity) and accept or reject the delivery. Only a clean, fully evidenced delivery may be guarded-merged.

After accepted W056 merge, reconcile the durable execution ledger/state/roadmap projections and then close R5 and activate R6 through a new explicit governance transition. W040 continues independently.

## Where to read first

1. `spec/mission.md`
2. `spec/architecture.md`
3. `spec/architecture-lock.md`
4. `spec/work-items.md`
5. `spec/dependency-graph.md`
6. `spec/architect/roadmap.yaml`
7. `spec/architect/execution-state.yaml`
8. `spec/architect/execution-ledger.yaml`
9. `spec/architect/authorizations/WORK-056.yaml`
10. `spec/architect/decisions/DEC-0090-w056-scope-amendment.yaml`
11. `spec/architect/decisions/DEC-0091-w056-residual-oracle-amendment.yaml` (the sole canonical DEC-0091 record)
12. `spec/architect/decisions/DEC-0092-dec-0091-identity-disambiguation.yaml`
13. `spec/architect/work-items/WORK-056.md`
14. `docs/WORK-056-handoff.md`
15. PR #17 and its current exact head `35ec48a1a207b755da7deb2e7b45c00eba0578ac`

Then inspect `developerapi/` and the accepted W052/W053 public interfaces before judging the next delivery.

## Key provenance

- W054 reviewed `93ad4130f8308832e432ce3e83988f5a6a9b32e3`, merge `57963858e5a2b9d11faed94b50f94e058cede0a8`, DEC-0088.
- W055 reviewed `0fc86aac57332ca8b8043bf5ee20bb3240d70fe8`, merge `7801549c0ed50082a4fa7c20c71e50dc7bde87f9`, DEC-0089.
- W056 baseline `7ae438d46041b228164cc8880be37dc21f972b6f`.
- DEC-0090 was accepted on mainline merge `e0b8e0f39a7adc885e0a8da9180ad06db9bd14a8`.
- DEC-0091 was issued after rejection of `0581f7cba05972dd47961de9c7ae821c7153e595` and is the current active scope amendment (canonical record designated by DEC-0092).
- DEC-0092 was issued after review `5558422610` withheld acceptance of the round-4 delivery `35ec48a1a207b755da7deb2e7b45c00eba0578ac`: DEC-0091 identity disambiguated, state pins reconciled, and the exact-head battery-execution vehicle established.

## Handoff integrity rule

If any repository projection disagrees with another, stop and reconcile against Git history, the frozen roadmap, execution ledger, accepted decisions, and active authorization. Never choose whichever projection is most convenient. The clean-clone repository must remain sufficient for a new Architect to reconstruct the same state without this conversation.
