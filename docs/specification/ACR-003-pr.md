# ACR-003 Review Record

This PR synchronizes the frozen W032 dependency declaration with the frozen DAG.

Decision: `W016 → W032` is a hard dependency.

Reason: W016 owns the canonical Adapter SDK/runtime contract and W032 explicitly requires adapter conformance testing against stable contracts.

This is a consistency reconciliation, following accepted ACR-002 precedent. No protocol/runtime semantics change. Architecture version remains 1.0. OAQ-001 is closed by ACR-003.
