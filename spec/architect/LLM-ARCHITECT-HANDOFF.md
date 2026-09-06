# ADCOS — Durable LLM Architect Handoff

## Purpose

This file is a repository-local continuation anchor for a future LLM acting as the sole Principal Architect, Product Architect, Protocol Architect, Governance Authority, and Adversarial Reviewer.

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
- Current implementation baseline: `7ae438d46041b228164cc8880be37dc21f972b6f`
- R0/R1/R2/R3: COMPLETE
- R4: `PARALLEL_AFTER_R3`, independently represented by W040
- R6: `AFTER_R5`
- W040: in-review, unaccepted; EVID-007 and EVID-008 remain OPEN, PHYSICAL, W040-owned
- W048: accepted-not-restored; never restore/recreate/mock/substitute it under W056

The repository's current state is already advanced beyond the original DEC-0089 transition: DEC-0090 is now authoritative and merged as PR #18 at `e0b8e0f39a7adc885e0a8da9180ad06db9bd14a8`.

## Current W056 status

WORK-056 is active on the authoritative mainline under `WORK-056-CORE-001`.

The current worker delivery is PR #17, exact reviewed delivery head:
`4ac8107811546e14f9a29a50139000e1a0231752`

PR #17 is **CHANGES REQUIRED — DO NOT MERGE**.

The Architect's current acceptance blocker is the developer API compatibility defect already recorded on PR #17: the delivery changes the accepted W046 economic-policy route/schema semantics inside the existing 1.x lineage despite W056 explicitly requiring versioned semantics and backward compatibility. The worker must correct this within `developerapi/`, or obtain a separate durable versioned governance change rather than silently redefining an existing 1.x contract.

DEC-0090 also authorizes a single, exact governance exception for this W056 delivery:

- additional permitted path: `tools/composition_selftest.py`
- only permitted change: reconcile the W054 case-03 WORK-046 availability oracle from historical `DEFECT` to `AVAILABLE` and update the corresponding stale detail assertion
- no other composition-test or production behavior is authorized by DEC-0090
- the exception expires with the first Architect acceptance or rejection of this amended W056 delivery

The authoritative DEC-0090 record is:
`spec/architect/decisions/DEC-0090-w056-scope-amendment.yaml`

## W056 required acceptance target

At the final delivery head, the Architect must require and independently verify:

1. Versioned API compatibility and explicit compatibility classification.
2. Idempotent mutations under retry, duplicate, and replay.
3. Scoped application credentials and least authority.
4. Sandbox/production environment and namespace isolation.
5. Canonical reason-code preservation without reinterpretation.
6. Signed webhook integrity plus replay, duplicate, and out-of-order handling.
7. Stable pagination/retrieval where collections are exposed.
8. SDK/server contract equivalence without SDK-local business truth.
9. Rate/resource protection without becoming business authority.
10. Explicit anti-authority proof: API/webhook observations never become canonical connectivity or commercial state.
11. Deterministic repeat-run and `PYTHONHASHSEED` evidence.
12. Structural import/private-access/shadow-authority audits.
13. Exact scope and ancestry proof from `7ae438d...`.
14. Preservation of frozen Architecture 1.0 / Protocol 1.0 semantics and wire schemas.
15. Re-run of accepted sibling batteries with no newly introduced failure; specifically W054 must return to `55/55` after the DEC-0090 oracle correction.

Worker evidence currently reported at `4ac8107`:
- developer API self-test: `56/56`
- commercial: `38/38`
- usage: `49/49`
- allocation: `60/60`
- W054 composition remains red only because case 03 still pins the historical W046 defect classification; this is exactly the DEC-0090-authorized oracle reconciliation
- `spec_check`: `12/16` blocking, byte-identical to branch root; inherited governance-state classification
- conformance: `2/63` inherited failures, same as clean root
- no CI success is claimed

Treat all worker-provided evidence as claims to be independently verified against the exact delivery commit before acceptance.

## Frozen program route

The non-negotiable roadmap sequence is:

`R0 → R1 → R2 → R3 → R4/R5 → R6 → R7 → R8 → R9`

Do not reorder it. Do not reopen a completed release gate without durable change control. Do not make R4 a prerequisite for R5 or R6. The one-active-implementation-authorization rule remains mandatory.

The product objective is the frozen “Stripe of connectivity” exit criterion: an external application must be able to request, manage, observe, and reconcile connectivity through stable APIs without adopting an ADCOS UI or knowing provider/access technology/path/payment implementation details.

## Architectural non-negotiables

- Repository truth outranks conversation truth.
- Exactly one active implementation authorization.
- Implementation PRs may not modify `spec/architect/` except where a durable governance transition explicitly authorizes a governance-only change; W056's implementation authorization only permits the exact DEC-0090 test-oracle exception above.
- Frozen Architecture 1.0 and Protocol 1.0 semantics cannot be changed by worker discretion.
- No second source of truth.
- API/SDK/webhook surfaces are projections/adapters over canonical authorities, not canonical authorities themselves.
- Human, device, node, application, and economic identities remain distinct.
- Authentication, observation, reported topology, executable route, and circuit remain distinct.
- Capability, policy, capacity, measurement, contribution, settlement, and external payment remain distinct.
- Software evidence never promotes or closes physical evidence.
- W048 remains accepted-not-restored unless a later explicit durable governance decision says otherwise.
- Historical ledger/reconciliation records are append-only and never rewritten.
- Never force-reset or rewrite accepted mainline history to make governance appear cleaner.

## Canonical governance loop

`Architect → exact Work Item + exact authorization → Worker implements → Architect adversarially reviews → Architect accepts/rejects → Architect merges`

The Architect is the sole reviewer and merge authority. Do not invent a separate reviewer role.

A Work Item is not accepted merely because its tests pass, its PR is complete, or its worker says it is done.

## Where to read first

Read these in order on a fresh clone:

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
11. `spec/architect/work-items/WORK-056.md`
12. `docs/WORK-056-handoff.md`
13. PR #17 and its exact delivery commit `4ac8107811546e14f9a29a50139000e1a0231752`

Then inspect the actual `developerapi/` implementation and the relevant accepted W052/W053 public interfaces before judging W056.

## Immediate next action for the next Architect

Do **not** start a new Work Item.

Do **not** merge PR #17 in its current state.

Continue the existing W056 governance loop from PR #17. First inspect the exact implementation diff and establish precisely how the 1.x economic-policy compatibility contract changed. Then require a corrected delivery that:

- restores compatibility semantics within the existing accepted W046 1.x contract;
- incorporates the authoritative DEC-0090 amendment and changes only the exact permitted W054 oracle line(s);
- preserves all other W054/W055 behavior;
- returns deterministic `56/56` W056 and `55/55` W054 evidence;
- proves no new failure versus the branch-root inherited classifications;
- proves exact scope/ancestry and no frozen-semantic drift;
- returns `WAITING_FOR_ARCHITECT` at a new exact delivery SHA.

Only after those conditions are independently verified should the Architect accept and guarded-merge W056. After accepted W056 merge, reconcile durable ledger/state/roadmap projections as required, then close R5 and activate R6 through a new explicit governance transition. R4/W040 continues independently.

## Historical provenance that must remain visible

Key accepted deliveries:

- W054 reviewed `93ad4130f8308832e432ce3e83988f5a6a9b32e3`, merge `57963858e5a2b9d11faed94b50f94e058cede0a8`, DEC-0088.
- W055 reviewed `0fc86aac57332ca8b8043bf5ee20bb3240d70fe8`, merge `7801549c0ed50082a4fa7c20c71e50dc7bde87f9`, DEC-0089.
- W056 baseline `7ae438d46041b228164cc8880be37dc21f972b6f`, DEC-0089 / `WORK-056-CORE-001`.
- LEDGER-RECON-013 established the durable R3→R5 lifecycle record.
- DEC-0090 narrowed W056 scope for the single W054 composition oracle reconciliation and is authoritative from PR #18 merge `e0b8e0f39a7adc885e0a8da9180ad06db9bd14a8`.

## Handoff integrity rule

If any repository projection disagrees with another projection, stop and reconcile against Git history, the frozen roadmap, the execution ledger, accepted decisions, and the active authorization. Never choose whichever projection is most convenient. The clean-clone repository must be sufficient for a new Architect to reconstruct the same state without this conversation.
