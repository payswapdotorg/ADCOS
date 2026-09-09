# ADCOS Work Item Registry

## Status

FROZEN — Architecture Version 1.1 successor registry (M001–M014).

- Accepted: ACR-014 (DEC-0098 approval; synchronized updates merged with the M001 delivery)
- Supersedes: the Architecture 1.0 W-item registry (W001–W057), preserved verbatim at `spec/history/work-items-1.0.md`
- Lifecycle and acceptance history for every W-item remains governed solely by `spec/architect/execution-ledger.yaml` and is never rewritten

Implementation is dependency-driven (see `spec/dependency-graph.md`).

## M001 — Architecture 1.1 Freeze
Formal ACR, architecture authority transition, lock update, historical archive and handoff update.
**Status: delivered — acceptance pending (M001-CORE-001, DEC-0098/DEC-0099).**

## M002 — Connectivity Contract Core
Implement canonical contract, lifecycle, hard constraints, lease/expiry and authority uniqueness.

## M003 — Offers and Provider Capability Exchange
Implement provider-domain capability advertisements, offers, validity, commitments and provenance.

## M004 — Eligibility and Policy
Implement deterministic eligibility and policy evaluation without provider SDK leakage.

## M005 — Evidence and Assurance
Implement typed evidence records and contract-level assurance evaluation.

## M006 — Execution Plan
Implement contract-to-execution-plan translation and execution segments.

## M007 — Provider/Standard Adapters
Build reference adapters around existing standard/provider mechanisms.

## M008 — Replan and Failover
Implement closed-loop replan while preserving hard contract constraints.

## M009 — Usage and Commercial Reconciliation
Implement usage records and settlement references without moving payment authority into networking.
(Re-baselines the era-superseded payment/eligibility/client batteries disclosed by DEC-0099.)

## M010 — ShareNet Vertical Proof
Prove application-funded connectivity and failure recovery.

## M011 — RoamLink Vertical Proof
Prove mobile/roaming connectivity acquisition through ADCOS.

## M012 — COMOS Vertical Proof
Prove communication gateway connectivity through ADCOS.

## M013 — Developer Connectivity API
Expose technology-neutral contract/offers/assurance/usage semantics.

## M014 — Production Federation
Production-harden provider domains, authorization, evidence, compatibility, rate limits and revocation.

## Post-snapshot gate contracts

Gate-specific R7+ Work Item contracts live under `spec/architect/work-items/`
with dependency overlays under `spec/architect/dependency-overlays/`
(governance basis ACR-013 / DEC-0095). Exactly one implementation
authorization may be active at a time
(`spec/architect/authorizations/`).
