# ADCOS Upgrade / rollback / compatibility family (WORK-029)

Upgrade, rollback, and compatibility management so ADCOS can evolve
without a flag day (spec/architecture.md P12 — protocol evolution
without flag days; section 25 rule 13 — no flag-day upgrade; section
7 rules 4–5 — breaking changes require a new major protocol version,
additive changes use minor versions and feature negotiation).

## Authority boundaries (the layering contract)

The family is a **compatibility-orchestration layer**, never a new
authority:

- **Protocol version semantics stay WORK-003.** The known-major truth
  is `spec/schemas/protocol.json`, loaded read-only through
  `protocol.versioning.protocol_metadata()`. Profile negotiation
  classifies majors with WORK-003's own `classify_major` — an unknown
  major is rejected exactly as WORK-003 says, and mismatched majors
  fail closed with NO fallback to a lower common major. The
  rejection is structural: a `ProfileNegotiation` carrying a
  "selected" profile across mismatched majors is not a constructible
  value of the model.
- **Capability negotiation stays WORK-005.** Mixed-version capability
  interop is DELEGATED to `capabilities.negotiation.negotiate` — the
  real machinery, never re-implemented; the coexistence report
  carries its verdict as DATA.
- **Adapter health and observations stay WORK-016/W026.** Upgrade
  health gates are (subject kind, subject ref, metric, threshold)
  quads validated against the frozen WORK-026 metric registry, and
  their evidence is REAL telemetry observations consumed read-only —
  PROVENANCE-VERIFIED against the node's own WORK-026
  `TelemetryStore` (PR #31 review): every supplied observation must
  be a genuine `TelemetryObservation` the telemetry authority has
  actually RECORDED (`TelemetryStore.is_recorded`, the additive
  WORK-026 provenance-resolution surface). Duck-typed fakes (however
  completely populated), valid-but-unrecorded observations,
  cross-store injections, and tampered variants of recorded ids are
  rejected outright: a complete-content observation id is
  integrity, not authority provenance. No observation or stale
  observation is INSUFFICIENT_EVIDENCE: the gate fails closed —
  health is never assumed.
- **Upgrade state is node-local lifecycle state**
  (spec/architecture.md 5.6). The manager owns exactly one node's
  staged plan, stage, gate verdicts, rollback window, and
  minimum-version floor. It never touches topology, session,
  routing, policy, or identity state and is never a second authority
  for any of them. The coordinator is orchestration DATA over
  per-node managers — every verdict is the per-node manager's.
- **The four governance version kinds are never conflated**
  (spec/governance.md section 3). Architecture Version — not a
  dimension of this family at all (ACR-governed specification
  concern); Protocol Version — a MAJOR.MINOR line owned by WORK-003;
  Schema Version — per-artifact MAJOR.MINOR lines migrated
  reversibly here; Implementation Version — the MAJOR.MINOR.PATCH
  software line staged and rolled out here. The model enforces the
  separation structurally: neither version grammar parses where the
  other is required.

## The staged-upgrade ladder

`PLANNED -> PREPARED -> CANARY -> ROLLING -> COMMITTED` with the
honest terminal exits `ROLLED_BACK` and `ABORTED`:

1. **A stage advance is earned only by an explicit gate PASS.** A
   FAIL or INSUFFICIENT_EVIDENCE raises and leaves the stage
   unchanged.
2. **Staged implies reversible.** `begin()` rehearses the complete
   forward migration chain on a copy and verifies the chain is fully
   reversible BEFORE any live change. A plan crossing a
   non-reversible migration step cannot be staged at all: a staged
   upgrade that cannot be rolled back is not a staged upgrade — it
   is a flag day.
3. **COMMITTED is irreversible.** Post-commit rollback raises
   ROLLBACK_WINDOW_CLOSED; a further change is a new plan, never a
   silent re-open.
4. **Downgrade protection is a ratchet.** The minimum-version floor
   only moves up (at commit, to the plan's declared floor); a plan
   may never start below the floor (FLOOR_VIOLATION); a population
   rollback target below any node's floor is DOWNGRADE_BLOCKED,
   fail closed, and audited.
5. **Plans are upgrades by construction.** `UpgradePlan` rejects
   `to <= from`: an in-band downgrade does not exist — downgrades
   are rollbacks of staged plans (bounded by the floor), never new
   plans.
6. **Live migration application is transactional** (PR #31 review).
   The PREPARED→CANARY transition runs the COMPLETE forward chain
   for EVERY artifact on isolated deep copies and swaps the live
   schema state and version metadata only after the entire chain
   succeeds — a mutating, raising, or invalid-returning migration
   callable (the registry accepts arbitrary callables, and the
   `begin()` rehearsal proves nothing about the later live call)
   leaves live state byte-identical to the pre-transition state.
   `rollback()` applies the same isolation to its reversibility
   proof-walk (live version back to the pre-plan origin, on copies);
   the authoritative restore is the byte-identical pre-plan
   snapshot.

## Rolling upgrades (the population coordinator)

`RolloutCoordinator` stages one deterministic canary (the
lexicographically first node), making the population deliberately
MIXED-VERSION; only a canary rollout-gate PASS over real telemetry
promotes the remaining nodes; any failure halts the rollout and
rolls back every begun node (later batches never advance on an
unhealthy canary). Mixed-version coexistence mid-rollout is the
designed state, proven by coexistence reports against the real
WORK-003/WORK-005 machinery.

## Reversible schema migrations

`MigrationRegistry` walks deterministic fewest-edge paths over
forward edges only (a downgrade edge is not constructible: additive
steps bump exactly one minor, breaking steps exactly one major with
the minor reset to 0 — the governance section-3 discipline, enforced
at descriptor construction). Reversing a declared non-reversible
step fails closed; unknown paths fail closed; forward-then-backward
round-trips are byte-identical for reversible chains.

## Determinism discipline

Injected RFC 3339 instants (never a wall clock), sorted iteration,
integer versions, canonical JSON deep copies, complete-content
record identities (every content-derived id covers the COMPLETE
record DATA — `to_dict()` minus the id — so no field can mutate
invisibly). Standard library only; fully offline; no randomness.
