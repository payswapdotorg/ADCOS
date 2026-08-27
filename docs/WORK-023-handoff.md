# WORK-023 — Mesh, IAB, Relay, and Store-and-Forward Backhaul

## Status

**IMPLEMENTATION HANDOFF — Architect-anchored**

This brief translates the frozen WORK-023 backlog entry into the implementation boundary for this Work Item. It does not modify the frozen architecture or backlog.

## Authoritative contract

Frozen `spec/work-items.md` defines WORK-023 as:

- **Objective:** implement multi-hop connectivity mechanisms, including integration points for 3GPP IAB/sidelink relay and generic mesh/store-and-forward paths.
- **Dependencies:** WORK-011, WORK-013, WORK-022.
- **Acceptance:** multi-hop paths are represented as ordinary Paths; node/reporter evidence is preserved across hops; disconnected operation can continue with configured store-and-forward semantics.
- **Verification:** partition/recovery, multi-hop, and loop-prevention tests.
- **Out of scope:** proprietary mesh PHY.
- **Definition of done:** connectivity can extend through multiple relays and intermittent links.

## Architectural rules

1. `/routing` remains authoritative for ADCOS path selection. The mesh family must not create a second routing authority.
2. `/session` remains authoritative for logical session identity. A hop, relay, IAB link, next hop, queue, or store-and-forward bundle must never become the session identity.
3. `/topology` remains authoritative for topology and evidence provenance. Node/reporter observations must remain distinguishable from authoritative state.
4. External 3GPP IAB/sidelink and any proprietary radio/mesh technology remain behind adapters/providers. No vendor or PHY types enter core semantics.
5. Store-and-forward is a resilience/transport mechanism, not a replacement session model. Disconnected operation may defer delivery, but it must preserve the original logical destination/session identity and provenance.
6. Loop prevention must be explicit and deterministic. Forwarding a bundle/path through a node already present in its forwarding history must fail closed before introducing a cycle.
7. Multi-hop composition must use ordinary `Path` semantics and existing path references rather than creating a parallel mesh-only path identity model.
8. Implementation state that depends on a concrete relay technology must remain outside canonical core state unless already represented by an established technology-neutral primitive.
9. Capability and queue/resource claims require provenance and freshness; an unavailable upstream hop must degrade service rather than silently becoming an authoritative reachable path.
10. Keep all new protocol/data structures versioned and additive; do not alter frozen schemas or architecture documents in this Work Item.

## Required implementation shape

Use a new adapter-family package beneath the frozen `/adapters` boundary, with a stable technology-neutral mesh/relay contract and sandboxed manager/runtime. The family should support at least:

- an ordinary multi-hop reference implementation used for deterministic testing;
- an independent relay implementation/test double proving replaceability;
- a store-and-forward queue/bundle mechanism with explicit configured limits and deterministic expiry;
- a 3GPP IAB/sidelink integration seam that carries external identifiers as DATA, without importing vendor/PHY semantics into core;
- a bridge onto the accepted WORK-016 `AdapterContract` where a generic access/provider adapter surface is needed.

The conformance implementation may use an in-process or real-socket peer, but it must remain separate from any production technology adapter and must not be treated as evidence of proprietary-radio interoperability.

## Acceptance-critical invariants

### Multi-hop path identity
A composed route over N hops is one ordinary ADCOS `Path` with hop evidence/segments. Adding/removing/reordering relays must not rewrite the logical session identity.

### Evidence preservation
Every hop/reporter contribution must retain the reporter identity and provenance class. A relay-reported state must not silently become self-observed or authoritative.

### Store-and-forward
Bundles must carry enough stable metadata to resume delivery after partitions. Expiry, hop budget, replay/duplicate detection, and queue capacity must be deterministic and fail closed.

### Loop prevention
The forwarding guard must reject a cycle before enqueue/forward commit. The rejection must leave the bundle queue and path state unchanged.

### Replaceability
Changing relay implementation must not invalidate established logical sessions or rewrite canonical path/session state merely because implementation identity changed.

### Disconnected operation
The system must distinguish `queued/deferred`, `forwardable`, `expired`, `delivered`, and `rejected-loop` (or equivalent technology-neutral states) without claiming delivery that did not occur.

## Required verification matrix

The selftest suite must include, at minimum:

1. 2-hop and 3-hop path construction using ordinary `Path` primitives.
2. Same-session continuity across relay changes.
3. Reporter/evidence provenance preservation across every hop.
4. Partition while forwarding, followed by deterministic recovery and eventual delivery.
5. Queue capacity exhaustion and expiry with no ghost delivery.
6. Duplicate-bundle detection / replay rejection.
7. Loop rejection for direct cycles and longer cycles, including no-state-change assertions.
8. Independent implementation swap with existing live bindings preserved.
9. IAB/sidelink external identifiers remain opaque DATA at the core boundary.
10. Full determinism across repeated runs and `PYTHONHASHSEED` variation.
11. Frozen `spec/` byte-identity and full sibling battery remain green.

## Delivery gate

Z.ai must:

- work only on WORK-023;
- branch from current `main` containing accepted WORK-022;
- keep frozen `spec/` untouched unless an Architect-authorized architecture change is separately issued;
- add the family selftest and CI registration;
- return an open PR for Architect review;
- **not merge the PR**;
- leave WORK-024 and all later downstream work blocked until WORK-023 is Architect-accepted.

## Explicit non-goals

Do not implement proprietary mesh PHY, radio scheduling, SDR drivers, vendor-specific relay firmware, or a second routing/session authority.
