# WORK-057 — Provider Onboarding & Federation Handoff

## Status
ACTIVE — authorized by DEC-0095 / WORK-057-CORE-001.

## Mission
Make independently operated connectivity infrastructure consumable through ADCOS without requiring the infrastructure operator to surrender infrastructure authority and without coupling applications to any specific provider or access technology.

## Baseline
Implementation must begin from the authoritative mainline containing the DEC-0095 governance transition. Do not implement from an older W056/R5 tree or from a chat-derived state.

## Required lifecycle
registration → operator/domain identity binding → scoped credential issuance → adapter declaration/certification → capability/resource declaration → service/commercial profile binding → eligibility/policy evaluation → federation proposal → explicit acceptance → active federated membership → suspension/revocation/offboarding

## Architectural invariants
- Human, device, node, application, and economic identities remain distinct.
- Authentication evidence, observed link state, topology claims, route state, and circuit/session state remain distinct.
- Provider SDKs and technology-specific semantics stay behind adapter/provider boundaries.
- Federation membership is scoped, explicit, revocable, and non-transitive.
- Capability/resource declarations retain provenance and validity; they do not prove current connectivity.
- Commercial and settlement configuration binds to existing commercial authorities; it cannot become payment authority.
- Onboarding cannot create or mutate canonical identity, routing, session, transport, usage, payment, or allocation authority.
- W048 is accepted-not-restored.
- W040 remains an independent physical-evidence obligation.

## Review posture
The Architect will compare the complete delivery against WORK-057-CORE-001, the R6 dependency overlay, the frozen Architecture/Protocol surfaces, and all acceptance evidence. Tests do not override architecture. Any required correction returns to the same Work Item; no successor authorization may be inferred.
