# Open Architectural Questions

## Status

**CURRENT — no unresolved architecture questions**

### OAQ-001 — W032 / W016 dependency mismatch

Resolved by **ACR-003** on 2026-08-28.

Decision: WORK-016 (Adapter SDK/runtime) is a hard dependency of WORK-032 (Conformance Suite), exactly as already declared in `spec/work-items.md`. The frozen DAG is synchronized by adding `W016 → W032`.

Rationale: W032 explicitly validates protocol/adapter conformance and requires adapters to self-test against stable contracts. W016 owns the canonical Adapter SDK/runtime contract. The previous DAG omission was a frozen-document inconsistency, not evidence that the dependency was optional.

Normative record: `spec/acr/ACR-003-w032-adapter-conformance-dependency.md`

Result: no remaining open architectural question associated with OAQ-001. No other dependency edge is changed by this decision.
