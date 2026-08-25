# ADCOS WORK-015 — Federation Protocol

## Status

**AUTHORITATIVE ARCHITECT HANDOFF — follows the frozen Architecture Version 1.0**

This prompt is the implementation contract for WORK-015. Z.ai is the implementer; the LLM Architect is the review authority. Do not infer missing architecture from convenience or from future Work Items.

## Work Item

**ID:** WORK-015
**Title:** Federation protocol
**Phase:** Phase 2 — Connectivity semantics
**Base:** accepted `main` after WORK-014

## Objective

Implement `/federation` as the authoritative ADCOS layer for **inter-domain relationships** between independently operated ADCOS administrative domains.

Federation MUST allow explicitly scoped cooperation without turning domain membership into universal trust, without duplicating node identity authority, topology authority, policy authority, routing authority, or session authority, and without introducing settlement/economic authority into networking semantics.

## Frozen architectural anchors

Use these as the authoritative contract:

- Architecture §6.10 — Federation is a typed relationship between administrative domains allowing selected capabilities and services to be shared.
- Architecture §21 — Federation specifies peer identities, trust policy, shared capabilities, route/import/export policy, service exposure, resource exposure, settlement policy, audit requirements, and revocation semantics.
- Architecture P5 — evidence over assertion.
- Architecture P6 — least authority.
- Architecture P7 — no blockchain requirement.
- Architecture P11 — observable and auditable.
- LOCK-001/003/005/006/007/008/011/012/014/016/017/022/023/024.

## Dependencies

Hard dependencies already Architect-accepted:

- WORK-004 — identity
- WORK-005 — capabilities
- WORK-007 — evidence-aware topology