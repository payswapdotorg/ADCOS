# WORK-042 Implementation Handoff (repository-local)

**Status: ACTIVE — the durable handoff for the WORK-042 implementation
referenced by the active authorization `WORK-042-CORE-001`.**

This is the governance-level handoff on `main`. The implementation-level
handoff (module structure, interfaces, evidence model) will live on the
W042 delivery branch and in its PR body, per the WORK-041 precedent.
Nothing in chat is authoritative.

## Authority

- Authorization: `spec/architect/authorizations/WORK-042.yaml` —
  `WORK-042-CORE-001`, `status: active`, baseline
  `96db8aa4423dff845a223e0c93c67f3dc14e314d` (current main at activation;
  moves only through a formally recorded reconciliation).
- Decision: DEC-0055 (atomic W041 acceptance → W042 activation) —
  `spec/architect/decisions/DEC-0055-work-042-activation.yaml`.
- Architecture basis: ACR-006 (accepted by DEC-0048) — Event-Driven
  Platform Integration and Journal-First Recovery; ACR-005 (accepted by
  DEC-0047) consumed through the accepted WORK-041 NetworkPath interfaces.
- Ready-candidate contract: `spec/architect/work-items/WORK-042.md`
  (tracking issue #69).
- WORK-041 is accepted-merged (DEC-0054; PR #107 head `4ce5a42`, merge
  `96db8aa`, CI run 33426900730 SUCCESS) — the W041→W042 hard dependency
  is satisfied where W041 interfaces are consumed.
- W040 remains an independent physical validation track (in-review, NOT
  accepted; EVID-007/EVID-008 OPEN and W040-owned). W040 physical
  validation findings are advisory input (DEC-0051), not a prerequisite.

## Objective (from the W042 contract)

Implement the accepted ACR-006 event-driven platform integration and
journal-first recovery model while preserving all existing session and
authority semantics.

## Required outcomes (from the W042 contract)

- Add a platform-event ingestion boundary carrying authoritative
  observations.
- Reconcile events with snapshots deterministically; events are change
  notifications, snapshots remain state representation.
- Make mobile/platform execution resilient to process suspension and
  restart.
- Persist authoritative state through an append-only journal with periodic
  compact snapshots where appropriate.
- Recover by reconstructing durable state plus journal tail and
  reconciling with the current platform observation.
- Preserve stable logical session identity and existing
  recovery/session-loss semantics.

## Acceptance criteria (quoted from the W042 contract)

1. Platform changes can be delivered event-first without polling-only
   semantics.
2. Event/snapshot reconciliation is deterministic and idempotent.
3. Process death/suspension does not lose durable authorization/journal
   state.
4. Recovery reconstructs state correctly and records session loss honestly
   where transport state cannot survive process death.
5. Existing accepted batteries remain green and authority ownership is
   unchanged.

## Evidence classes (from the W042 contract)

- Software/architecture conformance: required (SOFTWARE class).
- Deterministic automated verification: required (SOFTWARE class).
- Physical-device evidence: NOT required for W042 implementation; physical
  claims remain governed separately (W040's open EVID-007/EVID-008
  obligations are separate and W040-owned).

## Hard dependencies (must be Architect-accepted and merged)

- WORK-012 Logical Sessions — accepted-merged (DEC-0012).
- WORK-013 Multipath Session Manager — accepted-merged (DEC-0013).
- WORK-014 Mobility/Handover — accepted-merged (DEC-0014).
- WORK-033 AgentRuntime — accepted-merged (DEC-0033).
- WORK-035 Mobile Agent — accepted-merged (DEC-0035).
- WORK-041 NetworkPath/platform boundary — accepted-merged (DEC-0054).

Architecture basis: ACR-006 (accepted by DEC-0048), consumed with ACR-005
(accepted by DEC-0047) through the WORK-041 interfaces where needed.

## Forbidden (from the W042 contract and the authorization record)

- New identity/session/routing/transport/federation/policy authority.
- Treating platform observations as protocol truth without existing
  authority establishment.
- Continuous-daemon assumptions on Android or similar lifecycle-managed
  platforms.
- Private-method fallbacks (and private authority access) for recovery or
  evidence.
- W040 continuation or WORK-043+ implementation.
- Commercial/payment implementation; wire-schema changes unless separately
  authorized; synthetic physical evidence presented as physical PASS;
  modifying frozen spec semantics.

## Authorized repository areas

The PR delta may touch exactly: `platform/` (the W042 package —
platform-event ingestion boundary, event/snapshot reconciliation,
append-only journal, snapshot/recovery), `tools/platform_selftest.py`
(the W042 battery), `docs/WORK-042-handoff.md`, and
`docs/WORK-042-evidence.md`. Implementation-level module layout inside
`platform/` is decided by the delivery branch and recorded in its
implementation-level handoff (the WORK-041 precedent).

## Downstream impact

- W048 (provider sharing) composes W041 + W042; it remains unauthorized
  and its interface dependency on W041/W042 is unchanged.
- The commercial chain (W051/W052/W053 per LEDGER-RECON-005) consumes the
  W042 journal-first discipline where noted; all commercial items remain
  unauthorized ready-candidates.

## Verification required before W042 PR review

```bash
python3 tools/spec_check.py
python3 tools/spec_check.py --provenance
python3 tools/spec_check_selftest.py
python3 tools/platform_selftest.py   # the W042 selftest (to be created by the implementation PR)
python3 tools/networkpath_selftest.py
python3 tools/agent_selftest.py
python3 tools/mobile_selftest.py
python3 tools/session_selftest.py
python3 tools/adapter_selftest.py
python3 tools/transport_selftest.py
python3 tools/ipintegration_selftest.py
```

All relevant existing batteries must remain green; no frozen authority
ownership changes; the implementation PR must inherit this authorization
byte-identically from main (ARCH-08) and must not modify
`spec/architect/` at all (review-protocol §3).

---

# WORK-042 Implementation Handoff (delivery branch)

**Status: DELIVERED — the implementation-level handoff on
`work-042-platform-journal-core` (cut from main `1909479`, which
carries the `WORK-042-CORE-001` authorization record
byte-identically from the recorded baseline `96db8aa`).**

Everything above the divider is the governance-level handoff from
main (unchanged). This section is the implementation-level handoff
per the WORK-041 precedent: module structure, interfaces, evidence
model.

## Module structure

```text
platform/                    (new package, 11 modules, 3827 lines)
    __init__.py              public API (55 frozen names)
    errors.py                PlatformError + frozen reason vocabulary (12)
    model.py                 PlatformEvent / EventKind / SessionBindingRef /
                             IngestionOutcome + content-derived ids
    boundary.py              the platform-event ingestion boundary
                             (push primary + change-detected polling
                             fallback over the accepted W033/W035 seams)
    state.py                 ReconciledState / ObservationRecord +
                             the deterministic fold (apply_record /
                             fold_state / fold_state_from)
    journal.py               JournalRecord (2 discriminated kinds) /
                             AppendOnlyJournal (hash chain, duplicate +
                             collision gates, persist-then-ack) /
                             PlatformStore seam (Memory + File durable)
    checkpoint.py            PlatformCheckpoint (journal-tail-bound
                             compact snapshot, content-derived id)
    recovery.py              load_verified_checkpoint / divergences /
                             perform_recovery + RecoveryReport
    lifecycle.py             PlatformIntegrator (the public production
                             surface) + ReconciledInterfaceSource /
                             ReconciledPlatformSource (the frozen-seam
                             composition views)
    evidence.py              RecoveryEvidenceRecord + digests + the
                             honest two-track disclosure
    integration.py           session_bindings_from_manager (public
                             NetworkPath reads -> checkpoint DATA)
tools/platform_selftest.py   the W042 battery (32 cases, 2259 lines)
docs/WORK-042-handoff.md     this document (governance part unchanged)
docs/WORK-042-evidence.md    the evidence document
```

## The implemented flow (ACR-006)

```text
platform authority (OS, through the accepted W033 InterfaceSource /
W035 MobilePlatformSource seams -- read-only)
    |
    | push: one observation per change callback (EVENT-FIRST primary)
    |      or: change-detected polling fallback
    v
PlatformEventBoundary  (typed validation, provenance, content id)
    v
PlatformEvent (kind, source, platform_ref, payload, observed_at, id)
    v
AppendOnlyJournal (hash-chained records, duplicate/contradiction
gates, persist-then-ack durable append)      [events = observations]
    v
ReconciledState (deterministic fold; latest observation per
reference; stale observations inert; session-loss outcomes distinct)
    v
PlatformCheckpoint (compact, journal-tail-bound, session-binding
references as DATA; persist-before-suspend)
    v
PlatformIntegrator.recover (load + verify journal; verify checkpoint
binding + state==fold(prefix); replay tail; ONE fresh platform
observation; reconcile through the ordinary boundary; record session
loss honestly; NO authority parameters at all)
    v
existing session/path/authority semantics (successor composes the
reconciled views through the frozen seams; re-establishment through
the ordinary WORK-012/033 paths)
```

## Key design decisions (all inside the ACR-006 contract)

1. **Events are observations; outcomes are decisions.** The journal
   discriminates `platform-event` records from `session-loss`
   records at the record-kind level, so an honest recovery outcome
   can never be mistaken for a platform observation (the contract's
   "distinguish observations from protocol decisions").
2. **Event id = fingerprint(kind, source, ref, payload, instant)** —
   the WORK-004/007/012/041 claim_id convention (empty = derive;
   non-empty must match). Journal record id additionally binds
   (sequence, content, prev link) — a hash chain, so load-time
   verification catches byte tamper, reorder, truncation, and
   sequence gaps.
3. **Contradiction rule**: two events for the same
   (platform_ref, observed_at) with different content are rejected
   whole at ingest AND re-checked by the fold on replay; an exact
   replay of the same event is an idempotent no-op (duplicate).
4. **Stale rule**: an observation older than the reconciled record
   for its reference is journaled for forensics but deterministically
   inert — ACR-006 §2 (no transition inferred from stale re-reads).
5. **Construction discipline**: a fresh `PlatformIntegrator` requires
   an EMPTY store; continuing from durable state is only possible
   through `recover()` (fresh observation + honest session loss).
   No silent adoption of stale state.
6. **Recovery takes no authority parameters** (store, clock, two
   read-only platform sources only): it cannot touch session,
   routing, identity, or transport state by construction. The
   successor re-establishes sessions through the ordinary paths
   (new session id, exactly one created event).
7. **Session-loss honesty is total**: every checkpoint binding is
   recorded lost at recovery (idempotently keyed on
   (session_id, checkpoint_id)), whatever the fresh platform
   observation says — a still-present interface never resurrects
   transport state (no faked liveness).
8. **The reconciled views implement the frozen seams**
   (`InterfaceSource`, `MobilePlatformSource`) over event-reconstructed
   state: the accepted authorities consume recovered state
   unchanged (composition, not replacement).
9. **Durability seam is injectable**: `MemoryPlatformStore`
   (deterministic verification) and `FilePlatformStore` (the real
   append-only durable store — journal file opened `ab` only, so it
   can only grow; the only filesystem-write site in the family).
   Every append is persisted BEFORE the in-memory ack.

## Verification

See `docs/WORK-042-evidence.md` for the complete table (battery,
spec checks, all existing batteries, determinism proofs, negative
coverage, authority-ownership audit). Headline: W042 battery
32/32 PASS; `spec_check.py` 17/17; `spec_check.py --provenance`
2/2; every mandated existing battery green; PYTHONHASHSEED
0/1/7919/unset subprocesses byte-identical.
