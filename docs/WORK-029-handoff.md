# WORK-029 — Upgrade, Rollback, and Compatibility Manager

## Status

**IMPLEMENTATION HANDOFF — RECONSTRUCTED (implementer-side)**

No separate WORK-029 handoff existed on the accepted `main` baseline.
This brief reconstructs the implementation boundary from the frozen
`spec/work-items.md`, `spec/architecture.md`,
`spec/architecture-lock.md`, and accepted dependency/review governance
only. It does not modify the frozen architecture or backlog. It lives
under `docs/` (the WORK-023/024/025/028 handoff pattern) so that the
branch keeps `spec/` byte-identical to `origin/main`, as the
frozen-surface batteries require.

## Authoritative contract

Frozen `spec/work-items.md` defines WORK-029 as:

- **Objective:** implement protocol/software capability negotiation,
  rolling upgrades, downgrade protection, schema compatibility, and
  rollback.
- **Dependencies:** WORK-003, WORK-005, WORK-016, WORK-026
  (all Architect-accepted and merged).
- **Acceptance:** mixed-version nodes can coexist; incompatible
  versions fail closed; upgrades can be staged and rolled back;
  schema migrations are reversible.
- **Verification:** mixed-version integration tests.
- **Definition of done:** ADCOS can evolve without a flag day.

## Architectural rules

1. The frozen dependency list is exactly WORK-003, WORK-005,
   WORK-016, WORK-026. No additional dependencies are inferred from
   implementation convenience (`spec/workflow.md` §2.1).
2. The family is a compatibility-orchestration layer, never a new
   authority: the Protocol Version line stays WORK-003
   (`spec/schemas/protocol.json` is the single source of truth,
   consumed read-only); capability negotiation stays WORK-005
   (delegated to its `negotiate()`, never re-implemented); gate
   evidence stays WORK-026 (real telemetry observations, consumed
   read-only as DATA — self-sourced only, LOCK-008); upgrade state is
   node-local lifecycle state (`spec/architecture.md` §5.6), never
   topology/session/routing/policy state.
3. The four governance version kinds (`spec/governance.md` §3) are
   never conflated or collapsed: Architecture (not a dimension of
   this family at all — ACR-governed), Protocol, Schema,
   Implementation. The model enforces the separation structurally.
4. Fail closed, always: incompatible protocol majors have NO
   fallback; unknown majors follow the WORK-003 verdict; gates never
   assume health (no evidence or stale evidence is
   INSUFFICIENT_EVIDENCE); unknown migration paths and non-reversible
   reversals are refused; post-commit rollback windows stay closed;
   downgrade protection (the minimum-version floor) is a ratchet that
   blocks below-floor starts and population rollbacks, audibly.
5. Staged implies reversible: the manager only accepts plans whose
   COMPLETE schema-migration chain is reversible — a staged upgrade
   that cannot be rolled back is not a staged upgrade, it is a flag
   day (P12, §25 rule 13).
6. Vendor specifics stay behind the adapter/provider seam (LOCK-016):
   the family is standard-library only and access-technology neutral
   (LOCK-001/002/003).

## Required proof style

Every acceptance-critical control needs a structural proof or a
discriminating regression that fails against the vulnerable
implementation under review. Happy-path tests alone are insufficient.
