# WORK-054 — System Composition Conformance

This document is the implementation handoff corresponding to the repository-local authorization `WORK-054-CORE-001` issued by DEC-0085.

## Exact baseline

Implementation branch MUST be cut from:

`13bfbda54eece391306ddb774e0700c9d862339a`

Architecture Version: `1.0`
Protocol Version: `1.0`

## Objective

Prove the complete commercial/connectivity composition without introducing a second authority.

## Canonical chain

`intent -> offer -> eligibility -> reservation/lease -> candidate selection -> NetworkPath validation -> containment -> session -> delivered traffic -> usage -> BILLABLE_FINAL -> allocation -> external payment reference -> reconciliation`

## Mandatory negative proofs

1. Payment success cannot create connectivity.
2. Reservation success cannot imply reachability.
3. Marketplace discovery cannot activate a path.
4. W050 capability declaration cannot enforce containment.
5. W049 client state cannot become canonical state.
6. API/webhook observation cannot become a second source of truth.
7. Software evidence cannot close physical evidence.

## Critical W048 condition

W048 is historically accepted but its implementation artifacts are intentionally absent from the accepted R0 restoration tree and current main. This is not permission to reconstruct W048 inside WORK-054.

The WORK-054 implementation MUST explicitly detect the unavailable W048 authority and fail closed. A conformance result that silently substitutes another implementation, mock, or new authority is invalid.

## Authority rule

WORK-054 creates no canonical state authority. It is a conformance/evidence layer over already accepted authorities. Existing Work Item ownership remains authoritative.

## Authorized implementation surface

The implementation PR may change only the explicitly authorized implementation/evidence surfaces:

- `composition/`
- `tools/composition_selftest.py`
- `docs/WORK-054-evidence.md`
- `docs/WORK-054-handoff.md`

The implementation PR MUST NOT modify `spec/architect/`.

## Required verification

The worker must provide:

- deterministic positive composition scenarios;
- all seven mandatory negative proofs;
- explicit W048 fail-closed/absence proof;
- authority ownership/import audit;
- duplicate/out-of-order/replay protection and idempotency proof;
- restart/recovery determinism where applicable;
- PYTHONHASHSEED invariance;
- byte/digest-stable repeated runs;
- CI and provenance evidence proving scope compliance.

## Out of scope

No W048 restoration. No new commercial or connectivity authority. No live payment integration. No KYC/KYB. No physical validation. No architecture/protocol/wire-schema change. No second source of truth. No modification of frozen governance surfaces.

## Architect acceptance

Implementation is not accepted merely because tests pass. The Architect will review the exact delivered SHA, scope, evidence, authority boundaries, failure behavior, determinism, and negative proofs before acceptance.

---

# WORK-054 Implementation Handoff (this PR)

**Implementation-level handoff appended by the authorized worker
(delivery under `WORK-054-CORE-001`; implementation baseline
`461d1482180222f4b63f780d6d9ea1d54c49d643` per DEC-0086). The
Architect directive above is preserved verbatim and remains
authoritative; this appendix records what was delivered and how
each directive requirement is satisfied.**

## 1. What was delivered

A conformance/orchestration/evidence layer — and nothing else:

- `composition/` (6 modules): the authority availability
  registry, the frozen 13-edge chain model, the SOFTWARE-only
  evidence discipline, the composed conformance world (existing
  authorities only, built through their own public constructors
  over injected seams), and the orchestrator (the strict chain
  driver, the segment-conformance driver, and the deterministic
  digest stream).
- `tools/composition_selftest.py`: the 55-case deterministic
  battery (the authority table, the strict chain, the segments,
  the seven mandatory negative proofs, the failure matrix, the
  replay/recovery proofs, the determinism proofs, and the
  import/scope/vendor audits).
- `docs/WORK-054-evidence.md`: the evidence record (every claim
  mechanically backed by a numbered battery case).

## 2. Authority rules honored (the no-second-authority model)

- The composition layer constructs ONLY existing authority
  objects (the W032 ConformanceWorld precedent) and builds every
  cross-authority input as an immutable caller-side snapshot
  derived from PUBLIC reads (the W051/W052/W053/W044 injection
  contracts: `ReferenceIndex`, `UsageEvidenceIndex`,
  `AllocationEvidenceIndex`, `CommercialSnapshot`).
- It creates no canonical business state store, no connectivity
  state store, no payment/eligibility/marketplace/developer-
  platform/client authority, no session/path/routing/transport/
  policy authority, and no substitute for an absent authority.
  The audits (battery cases 45/46) enforce this mechanically:
  no authority class is defined or subclassed; no
  store/journal/ledger/gateway/manager class exists; no
  filesystem is touched; the composition trace is derived data,
  never journaled, never authoritative.
- Existing Work Item ownership is preserved exactly: every chain
  edge cites its owning authority; the W047 coordination seams
  (coordinate/handoff/record) are consumed as the accepted
  composition surfaces they are; the W041 machinery's own
  lifecycle drives path validation/binding/activation.

## 3. The W048 rule (accepted-not-restored)

- The absence is DETECTED structurally (no `sharing/` package;
  `containment/` is the restored ACR-012 vocabulary only) and
  recorded in the authority registry as `absent-fail-closed`.
- The strict chain FAILS CLOSED at the containment edge with the
  typed `w048-runtime-absent-fail-closed` reason; every
  downstream edge is NOT_ENTERED; the verdict is
  `BLOCKED_MISSING_AUTHORITY` with `production_composition=False`
  and there is NO verdict form that could report a passing
  production composition while the authority is absent.
- The client-boundary sharing reads fail closed
  (`client-stale-state`; never fabricated) and the provider-mode
  client refuses construction without the runtime.
- W048 is never restored, recreated, mocked, or substituted, and
  the absence is never downgraded into a successful production
  composition: the segment-conformance run that exercises the
  available downstream links travels with an explicit disclaimer
  and never claims production composition.

## 4. The WORK-046 inherited-defect disclosure

The restored W046 developer-API artifacts fail to import on the
current mainline (a stale `usage.errors.UsageLedgerError`
cross-import against the evolved W052 surface). The defect is
outside the authorized scope: detected, recorded
(`defect-inherited` with the exact stale symbol), and disclosed
in the evidence record; never repaired, never silently
bypassed. The API/webhook observation negatives are proven
through the RECEIVING authorities' public boundaries (W052 kind
table, W044 callback fold, W053 reference kinds). The same
disclosure covers the four restored batteries that fail at
import on the base mainline (payment/eligibility/developerapi/
client) — they are byte-identically broken on the base and are
NOT modified here.

## 5. Determinism contract

- All clocks are WORK-033 `StepClock` seams with frozen epochs;
  no wall clock, no entropy, no UUIDs, no network, no filesystem
  writes (battery case_48).
- All digests follow the WORK-003 canonical-JSON SHA-256
  convention (case_44).
- The scenario stream is byte-identical across fresh runs and
  across PYTHONHASHSEED 0/1/7919/unset (cases 41–43); the full
  command sequence replays as idempotent no-ops with
  byte-identical journal digests (case 38); journal-first
  recovery reproduces every authority state exactly (case 39).

## 6. Scope discipline

The PR modifies ONLY the authorized surfaces (`composition/`,
`tools/composition_selftest.py`, `docs/WORK-054-evidence.md`,
`docs/WORK-054-handoff.md`; battery case_51). `spec/architect/`,
the frozen architecture, protocol semantics, wire schemas, W040,
EVID-007, EVID-008, and every W044–W053 implementation artifact
are untouched (case_50 pins the frozen surfaces byte-identical to
`origin/main`). No CI wiring was added (the authorized scope does
not include `.github/`; the battery is standalone evidence).
No unrelated cleanup, no inherited-defect repair, no
future-roadmap functionality, and no new APIs were introduced:
the harness uses only existing public boundaries and the
injected-seam/test-double surfaces those boundaries already
define (the W044 `SandboxProvider` adapter seam and the W033
clock/interface seams).

## 7. Known limitations (honest)

- The full production composition CANNOT complete on the current
  mainline: the strict chain is honestly blocked at containment
  (WORK-048 accepted-not-restored). Completing it requires an
  explicit Architect directive to restore/implement W048 — which
  is expressly out of scope for WORK-054.
- The WORK-046 boundary cannot be driven live (the inherited
  import defect); its consumers' classification behavior is
  proven at the receiving boundaries instead.
- The composition battery is not CI-wired (out of authorized
  scope); it is re-runnable standalone and its full output is
  recorded in the evidence document.

## 8. Acceptance pointers

- The deterministic battery: `python3 tools/composition_selftest.py`
  (55/55 PASS; `--determinism-stream` for the byte-stable
  fingerprint).
- The evidence record: `docs/WORK-054-evidence.md` (the strict
  chain verdict, the seven negative proofs, the W048/W046
  disclosures, the determinism digests, the failure matrix, the
  audits).
- The chain model and outcome vocabularies: `composition/chain.py`
  (frozen; battery case_07 pins the ownership table).
- The authority availability table: `composition/authority.py`
  (the W048 `absent-fail-closed` and W046 `defect-inherited`
  classifications are first-class, honest records).
