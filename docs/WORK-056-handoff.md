# WORK-056 — Architect Handoff

## Status

**DELIVERED — WAITING FOR ARCHITECT**

Work Item: `WORK-056` — Developer Connectivity Platform Production Hardening  
Authorization: `WORK-056-CORE-001`  
Decision: `DEC-0089`  
Authorized baseline: `7ae438d46041b228164cc8880be37dc21f972b6f`  
Implementation branch: `work-056-developer-platform-hardening` (rooted at the
post-governance mainline `4852a016fce61cecec8078084da1d9bbe81d2681`, the PR #16
guarded merge, itself descending from the authorized baseline)

## Delivery record (WORK-056-CORE-001)

The implementation is delivered as one plain commit on the authorized
lineage (the exact head SHA is recorded in the PR body, the PR head, and
the worker worklog; the battery's scope/ancestry case verifies the
lineage mechanically). The delivery:

1. **repairs the inherited W046 import defect** — the boundary was
   import-broken against the current accepted W052/W053 public surfaces
   (the W054 composition battery had classified this honestly as
   `WORK-046 DEFECT`); the adapted-authority layer, the
   canonical-reason table, and the economic-policy request schema are
   re-bound to the CURRENT accepted public APIs with the frozen
   route/capability/envelope contract preserved (the sole route-shape
   delta, disclosed in the evidence record §2: the single-segment
   policy read);
2. **adds the W056 discrimination layer** — eleven sabotaged
   candidates (battery fixtures only, implemented over public APIs)
   paired with cases 46–56 across every required category: version
   laundering, idempotent re-keying, privilege escalation, environment
   bridging, reason rewriting, webhook signature/replay/order
   blindness, pagination instability + cursor forgery, SDK request
   reshaping + response fabrication, rate-limit-as-business-authority,
   and observation-as-command — each candidate is proven to FAIL the
   paired vector the genuine boundary passes (the W054/W055 family
   discriminating-power mandate);
3. **the battery is green at the delivery head**:
   `python3 tools/developerapi_selftest.py` → `PASS (56/56)`.

The full evidence record, the sibling-battery classification (including
the disclosed composition-pin follow-up, which lies outside the W056
authorized scope and awaits Architect disposition), and the honest
boundaries are in `docs/WORK-056-evidence.md`.

## Governance transition

WORK-055/R3 was accepted after final Architect adversarial review and merged as PR #15 at `7801549c0ed50082a4fa7c20c71e50dc7bde87f9`; the R3-closing governance (PR #16, including the LEDGER-RECON-013 reconciliation and the byte-exact historical-SHA restoration) was subsequently accepted and merged as the guarded merge `4852a016fce61cecec8078084da1d9bbe81d2681` — the branch root of this delivery. DEC-0089 closes R3 and opens the R5 software track.

R4 remains explicitly parallel after R3. W040 remains in-review and unaccepted; EVID-007 and EVID-008 remain open PHYSICAL obligations. W048 remains accepted-not-restored and is not part of this authorization.

Because the repository requires exactly one active implementation authorization, `WORK-056-CORE-001` is the sole active implementation authorization. No second software Work Item may be activated concurrently unless a later durable governance decision supersedes this one.

## Worker instruction

Cut the implementation branch from the exact current mainline baseline `7ae438d46041b228164cc8880be37dc21f972b6f` and implement only WORK-056. Do not modify `spec/architect/` from the implementation PR.

The worker must not redesign frozen Architecture 1.0 or Protocol 1.0. Any requirement that appears to need frozen semantic/wire-schema change is a blocker and must be surfaced for ACR/change control rather than solved locally.

## Required outcome

Harden the accepted `developerapi/` surface so an external application can consume ADCOS through stable APIs/SDK primitives/webhooks without adopting an ADCOS UI and without receiving direct authority over canonical networking or commercial state.

Required categories:

1. versioned API contract and compatibility classification;
2. idempotent mutation under retry/duplicate/replay;
3. scoped application credentials and least authority;
4. sandbox/production environment isolation;
5. canonical reason-code preservation;
6. signed webhook integrity and replay/duplicate/out-of-order handling;
7. stable pagination/retrieval where exposed;
8. SDK/server contract equivalence;
9. rate/resource protection without creating business authority;
10. anti-authority proofs showing API/webhooks are projections/observations, never canonical state.

## Required evidence

The delivery must include a deterministic self-test battery, positive and negative vectors, sabotage/discrimination cases, structural import and private-access audits, exact scope/ancestry proof, repeat-run and `PYTHONHASHSEED` determinism evidence, and a concise evidence/handoff record.

All evidence is SOFTWARE unless a later authorization explicitly creates an OPERATIONAL evidence obligation. Nothing in WORK-056 can close or promote W040 PHYSICAL evidence.

## Forbidden shortcuts

No mock may replace a production authority in acceptance evidence. No SDK-local database may become commercial or connectivity truth. No webhook may directly mutate canonical state without passing the same canonical server authority used by ordinary API mutation. No credentials may be widened for convenience. No environment identifiers may be trusted solely because they are client-supplied. No provider, carrier, access technology, payment rail, or network implementation may leak into the protocol core through the developer surface.

## Acceptance

Worker returns `WAITING_FOR_ARCHITECT` with the exact delivery SHA, parent SHA, diff inventory, deterministic battery output, CI classification, and evidence record. The sole Architect then performs the adversarial review. Acceptance is not implied by tests or PR completion.
