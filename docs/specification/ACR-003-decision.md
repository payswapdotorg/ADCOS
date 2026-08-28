# ACR-003 — Architect Decision

**Status:** ACCEPTED — 2026-08-28

The Architect accepts the synchronization of the frozen W032 dependency declaration with the frozen dependency DAG by adding `W016 → W032`.

The dependency is already declared by `spec/work-items.md`; W016 is the canonical Adapter SDK/runtime contract and is directly relevant to W032's adapter conformance scope. This is a consistency reconciliation, not a new runtime dependency.

No other DAG edges change. OAQ-001 is closed. Architecture version remains 1.0. Future changes require a new ACR.
