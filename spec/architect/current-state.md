# ADCOS Current State

**IMPLEMENTING — R2 System Composition Conformance (WORK-054); exactly one active authorization.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Current `main`: `13bfbda54eece391306ddb774e0700c9d862339a`
- Reconciled governance snapshot: `13bfbda54eece391306ddb774e0700c9d862339a` (DEC-0084 / PR #9)
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Program authority

The frozen roadmap is `spec/architect/roadmap.yaml`, Version 1.2. R0 and R1 are complete. R2 is active under DEC-0085 with WORK-054 and exactly one implementation authorization. The roadmap is the only program roadmap; chat, issue prose, old handoffs, and external planning documents do not govern execution.

## R0 — complete

R0 was accepted and merged as PR #8 on the exact frozen main `3bdfb6d`, merge `a3391e86851e06032de848e6eb0b4267fa33310a`; the resulting tree reproduces the accepted restoration state.

## R1 — complete

R1 was reconciled by DEC-0084 and merged as PR #9, merge `13bfbda54eece391306ddb774e0700c9d862339a`. The durable governance projections now agree on the live mainline.

## R2 — active

DEC-0085 activates WORK-054 — System Composition Conformance.

- Work Item: `WORK-054`
- Authorization: `WORK-054-CORE-001`
- Baseline: `13bfbda54eece391306ddb774e0700c9d862339a`
- Branch: `work-054-system-composition-conformance`
- Objective: prove the complete commercial/connectivity composition without introducing a second authority.
- Execution mode: `implementing`

Required chain:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

Mandatory negative proofs:

- payment success cannot create connectivity;
- reservation success cannot imply reachability;
- marketplace discovery cannot activate a path;
- W050 capability declaration cannot enforce containment;
- W049 client state cannot become canonical state;
- API/webhook observation cannot become a second source of truth;
- software evidence cannot close physical evidence.

W048 is historically accepted but explicitly `accepted-not-restored` on current main. WORK-054 must fail closed on that absence and must not recreate W048.

## Historical accepted delivery state

W044–W047 and W049 restored to current main under R0 with original acceptance provenance preserved. W048 acceptance provenance remains preserved but its implementation artifacts are not part of the accepted restoration tree. W050–W053 remain accepted and present.

## Independent physical track

W040 remains `in-review`, unaccepted, and independent. EVID-007 and EVID-008 remain open and W040-owned. No software evidence is promoted to physical evidence.

## Execution authority

Exactly one implementation authorization is active: `WORK-054-CORE-001`. No historical authorization has been revived. No second authorization may be created while WORK-054 is active.

The implementation worker must cut its branch from the exact authorization-bearing main baseline and may not modify `spec/architect/` from the implementation PR.

## Next transition

WORK-054 must be implemented, verified, adversarially reviewed by the Architect, and explicitly accepted before R2 can close and any subsequent authorization can issue.

## Source of truth

This file is a current-state projection only. The program is governed by `roadmap.yaml`; lifecycle history by `execution-ledger.yaml`; permission by repository-local authorizations; contracts by the frozen specification. No conversation context is required or authoritative.
