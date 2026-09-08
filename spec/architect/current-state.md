# ADCOS Current State

**READY — R6 Provider Onboarding & Federation complete; no active implementation authorization.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Actual `main` tip: `88a73720d8ff28e95728a03e13db631ffdf9688f`
- R6 implementation delivery: `58eced2f7864bd8d6e9cac658574d8c7b0b48965`, accepted under `DEC-0097`, merged as PR #23 at `a08ce85f133dbb76cd15a21d7c16f8a49fa7cc19`
- Post-merge human-roadmap reconciliation: `88a73720d8ff28e95728a03e13db631ffdf9688f`
- Architecture: `1.0` frozen
- Protocol: `1.0` frozen
- Roadmap: `1.5` frozen / authoritative

## Program authority

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. R0, R1, R2, R3, R5 and R6 are complete. R4 remains an independent physical-validation track under W040. R7 is the next unlocked software gate and is not activated.

## Execution authority

- `active_work_item: null`
- `active_authorization: null`
- Exactly one implementation authorization may be active; currently zero are active.
- The next software implementation requires a fresh gate-specific Work Item, explicit dependency overlay, repository-local authorization, and sole-Architect acceptance under the post-snapshot governance model established by ACR-013 / DEC-0095.

## Historical accepted state

W044–W047 and W049 were restored under R0 with acceptance provenance preserved. W048 remains accepted-not-restored and MUST NOT be recreated, mocked, or substituted implicitly. W050–W057 are accepted and present according to the authoritative roadmap/ledger. W040 remains independently in-review and unaccepted; its physical evidence remains separate from software evidence.

## R6

R6 Provider Onboarding & Federation is complete. WORK-057 was corrected and accepted under DEC-0097. The implementation established bounded provider onboarding/federation while preserving existing identity, trust, capability, resource, policy, federation, routing, session, transport, telemetry and commercial authorities.

## Next gate

R7 — Universal Connectivity Commerce — is unlocked but not activated. Its goal is to normalize heterogeneous connectivity resources into programmable offers selected by intent, policy, evidence, availability, geography, quality and price. R7 must be represented by a gate-specific Work Item and dependency overlay before implementation authorization is issued.

## Application-platform direction

The repository also contains the Architecture 1.1 proposal package in the current branch/PR history. That proposal is **not** the current frozen authority until formally accepted through the ACR process. It defines the intended evolution toward an application-facing connectivity exchange with `ConnectivityContract` as the canonical durable object and application-funded/sponsored connectivity as a supported use case.

Until such an ACR is accepted, implementation agents MUST follow Architecture 1.0. They MUST NOT silently treat `spec/architecture-1.1-proposed.md` as authoritative.

## Source of truth

This file is a current-state projection only. Lifecycle history is governed by `spec/architect/execution-ledger.yaml`; permission by `spec/architect/authorizations/`; architecture by `spec/architecture.md`; program order by `spec/architect/roadmap.yaml`. No conversation context is required or authoritative.
