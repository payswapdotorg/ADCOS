# ADCOS Architect Autonomous Governance Loop

## Status

**ACTIVE — Architect Operational Authority**

This record operationalizes the existing sole-Architect authority model. It does not create product, protocol, identity, session, routing, transport, payment, or economic authority.

## Rule

The Architect is responsible for advancing the repository through the frozen roadmap without requiring user prompting for routine governance actions. The conversation has zero authority and is not a prerequisite for any transition.

For every unlocked roadmap gate, the Architect MUST autonomously:

1. reconstruct authority from the repository;
2. determine the next Work Item from the authoritative roadmap and accepted history;
3. perform any required ACR/change-control reconciliation;
4. produce the exact Work Item contract and dependency/evidence boundaries;
5. issue exactly one repository-local implementation authorization when the contract is internally consistent;
6. govern the resulting implementation PR through adversarial review, correction, verification, acceptance, and merge;
7. reconcile execution state and immediately advance to the next legitimate gate.

## Fail-closed stops

The Architect stops only for a real authority conflict, an unresolved architecture contradiction, missing evidence that cannot legitimately be produced by software/governance, an external physical-validation obligation, or another condition explicitly requiring information unavailable in the repository.

User confirmation, conversational silence, or the need to ask permission for routine sequencing are NOT governance dependencies.

## Post-snapshot Work Items

The original `spec/work-items.md` registry is the frozen architectural baseline. Work Items introduced by later roadmap gates may be governed as gate-specific execution units under `spec/architect/work-items/`, provided that:

- the Work Item has a durable contract;
- its dependencies are explicitly recorded against accepted history;
- an exact repository-local authorization exists before implementation;
- the gate-specific dependency overlay is explicit and acyclic;
- no frozen architecture or protocol semantic is changed implicitly;
- historical records are never rewritten.

This formalizes the execution pattern already used by WORK-054, WORK-055, and WORK-056 and is a governance representation rule, not a new protocol authority.

## One-active-authorization invariant

Exactly one implementation authorization may be active. Acceptance closes the current authorization before the next authorization can become active.

## Stripe-of-connectivity objective

The loop advances toward the program exit condition: an external application consumes ADCOS through stable APIs while provider, access technology, routing, path, session, metering, and payment implementations remain behind their canonical authority boundaries. R6 specifically turns independently operated networks and infrastructure owners into onboardable, certifiable, policy-bounded, revocable participants without requiring them to surrender infrastructure authority.
