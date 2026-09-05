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
