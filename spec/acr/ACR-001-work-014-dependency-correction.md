# ACR-001: Correct WORK-014 dependency declaration

## Status
ACCEPTED

## Proposed change
`spec/work-items.md` currently declares WORK-014 (Mobility and handover manager) as depending on WORK-012, WORK-013, and WORK-017. The frozen dependency graph does not contain `W017 → W014`; Phase 2 is explicitly ordered `W011 → W012 → W013 → W014 → W015`, while WORK-017 belongs to the parallel Phase 3 adapter/transport foundation and depends independently on WORK-003, WORK-004, and WORK-012.

Change WORK-014's dependency declaration to:

- WORK-012 — Logical sessions
- WORK-013 — Multipath session manager

Remove WORK-017 from the WORK-014 dependency list.

Motivation: mobility/handover is a connectivity-semantic concern. It must operate through abstract session, multipath, route, policy, resource, and adapter contracts and must not depend on a concrete secure-transport implementation. Requiring WORK-017 would introduce a backward phase dependency and contradict the frozen dependency graph's explicit sequencing authority.

Alternatives considered:

1. Add `W017 → W014` to `spec/dependency-graph.md` — rejected because this would incorrectly couple Phase 2 mobility semantics to Phase 3 transport implementation.
2. Keep WORK-014 blocked until WORK-017 — rejected because the graph does not authorize that dependency and mobility can be specified against transport-independent contracts.
3. Leave the documents inconsistent — rejected because the change-control process requires synchronized frozen documents.

## Affected architecture sections and locks
- `spec/architecture.md` sections: 6.7 Session, 6.6 Path, 8 Capability/Technology Registry, and the connectivity/session/mobility semantics governing the implementation phases.
- `LOCK-XXX identifiers: none` — no protocol semantic, identity, wire-format, authority, or access-technology rule is changed; this ACR corrects Work Item dependency metadata only.

## Compatibility analysis
Wire compatibility: none.

Persisted state: none.

Live sessions: none.

Federation relationships: none.

Existing deployments: none; this changes implementation sequencing only.

Mixed-version operation: unchanged.

The change does not add or remove any protocol field, message type, registry identifier, lifecycle state, or runtime authority. It only synchronizes the WORK-014 dependency declaration with the already-frozen dependency graph.

## Work-item and dependency impact
- Affected Work Items: WORK-014, WORK-017.
- Dependency graph recalculation: **no edge change is required**. The frozen graph already has the intended edges. The recalculated readiness is:
  - WORK-014 is ready after Architect acceptance of WORK-012 and WORK-013.
  - WORK-017 is independently ready after Architect acceptance of WORK-003, WORK-004, and WORK-012.
- WORK-014 may proceed before WORK-017.
- WORK-017 remains a parallel Phase 3 item.

## Migration / rollback plan
No runtime migration is required.

Rollback: revert the synchronized `spec/work-items.md` dependency correction and this ACR, restoring the previous metadata only if a later Architect-approved ACR establishes a different dependency model.

## Architect decision
**APPROVED — 2026-08-25.**

Rationale: the frozen dependency graph is the sequencing authority and already places WORK-014 in the Phase 2 chain `W011 → W012 → W013 → W014 → W015`. WORK-017 is a separate Phase 3 transport foundation. Mobility must remain transport-agnostic and must not be artificially blocked by a lower-layer implementation. The Work Item text was stale relative to the graph and is corrected to restore consistency.

## Resulting architecture version
unchanged
