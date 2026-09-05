# WORK-054 — System Composition Conformance

## Identity
- Work Item ID: WORK-054
- Title: System Composition Conformance
- Phase: R2 — System Composition Conformance
- Critical path: yes

## Objective
Prove the complete commercial/connectivity composition without introducing a second authority.

## Baseline
- Implementation baseline: `13bfbda54eece391306ddb774e0700c9d862339a`
- Architecture version reference: `1.0`
- Protocol version reference: `1.0`

## Hard dependencies
- WORK-041 NetworkPath/platform boundary — accepted-merged, DEC-0054, merge `96db8aa4423dff845a223e0c93c67f3dc14e314d`
- WORK-042 Platform events/journal recovery — accepted-merged, DEC-0057, merge `207d70e20b8a05cb2f5149ff4e492e17c9a9189e`
- WORK-044 Payment Provider Adapters & Settlement Gateway — accepted-merged historical provenance, current artifacts restored/present where applicable
- WORK-045 Connectivity Eligibility, Provider Trust & Jurisdiction Policy — accepted-merged historical provenance, current artifacts restored/present where applicable
- WORK-046 Developer Connectivity API, SDK & Webhook Platform — accepted-merged historical provenance, current artifacts restored/present where applicable
- WORK-047 Connectivity Marketplace Discovery, Proximity & Path Selection — accepted-merged historical provenance, current artifacts restored/present where applicable
- WORK-048 Provider Connectivity Sharing Runtime — historically accepted, but explicitly `accepted-not-restored` on current main; this Work Item MUST fail closed rather than recreate or silently substitute W048 authority
- WORK-049 Provider & Buyer Connectivity Client Runtime — accepted-merged historical provenance, current artifacts restored/present where applicable
- WORK-050 Platform Connectivity Sharing Capability & Isolation Matrix — accepted-merged/current
- WORK-051 CommercialCore — accepted-merged, DEC-0059, merge `41b338080fbeb79627bff45cd79ddf09bf5cbb29`
- WORK-052 UsageLedger — accepted-merged, DEC-0061, merge `bcaf0d0677437d1ffca8f5e493cab516c87e7194`
- WORK-053 EconomicAllocation — accepted-merged, DEC-0063, merge `bb29c11c8bba6c9db5b87f85b1d62faad0bf7825`

## Soft dependencies
- W040 remains an independent physical track and is not a dependency for software conformance.
- Historical W044-W049 acceptance records are provenance inputs only; no old implementation branch is to be replayed.

## Authority consumed
WORK-051 CommercialCore, WORK-052 UsageLedger, WORK-053 EconomicAllocation, WORK-044 payment boundary, WORK-045 eligibility, WORK-046 developer API boundary, WORK-047 marketplace selection, WORK-048 sharing/isolation authority where present, WORK-049 client runtime, WORK-050 capability/isolation declarations, WORK-041 NetworkPath, WORK-042 platform recovery/journal, existing session/path/transport/routing authorities.

## Authority created
None. WORK-054 creates only a conformance/evidence layer. The canonical authorities remain owned by the existing Work Items.

## Authority forbidden
No shadow commercial state, no second connectivity state, no payment-as-connectivity authority, no marketplace-as-path authority, no API/webhook source of truth, no client canonical state, no synthetic replacement for absent W048 authority, and no new session/path/routing/transport/policy authority.

## Interfaces
Use existing public module/API boundaries. New conformance helpers must depend on public contracts and injected test doubles only where the existing interfaces already define such seams. Do not modify frozen wire schemas.

## State model
The conformance model must trace the ordered chain:

`intent -> offer -> eligibility -> reservation/lease -> candidate selection -> NetworkPath validation -> containment -> session -> delivered traffic -> usage -> BILLABLE_FINAL -> allocation -> external payment reference -> reconciliation`

Each edge must identify its owning authority and evidence class. Missing or unavailable authority must produce an explicit fail-closed result rather than inferred success.

## Failure model
Conformance must include negative paths for denied eligibility, failed reservation, unreachable candidate, failed NetworkPath validation, unavailable containment authority, session establishment failure, absent delivery evidence, non-billable usage, allocation rejection, payment-provider divergence, duplicate/out-of-order observation, and recovery/reconciliation. No failure may be converted into success by a downstream stage.

## Security model
Preserve existing trust boundaries and least-authority rules. Payment provider callbacks are untrusted observations until verified/reconciled. Webhooks are observations, never canonical state. No secret material belongs in conformance fixtures.

## Persistence/recovery
Conformance evidence must be deterministic and replayable. Where the tested chain crosses journal/recovery boundaries, the evidence must prove idempotent reconciliation and preservation of canonical state ownership.

## Adapter boundary
The composition layer must remain access-technology agnostic. No 5G, Wi-Fi, Ethernet, satellite, or provider implementation may become a core branching dependency in the composition authority.

## Verification
Required verification includes:
- deterministic composition conformance battery;
- positive end-to-end composition scenarios using existing authorities;
- mandatory negative proofs listed in the R2 roadmap gate;
- explicit W048 absence/fail-closed proof on current main;
- authority-ownership/import audits;
- duplicate/out-of-order/replay determinism;
- PYTHONHASHSEED invariance;
- repeat-run byte/digest stability;
- CI/provenance/scope audit proving only authorized surfaces changed.

## Acceptance gate
All available composition links are exercised end to end, every authority boundary is explicit, and the conformance battery proves the seven mandated negative invariants. Where the current mainline lacks an accepted component (notably W048), the battery must prove that the system refuses to fabricate or bypass that component; absence cannot be counted as a passing production composition.

## Evidence classes
- SOFTWARE: all deterministic composition tests, authority-boundary proofs, negative proofs, replay/idempotency, scope audit.
- PHYSICAL: none created or promoted by WORK-054.
- OPERATIONAL: none unless separately authorized.

## Out-of-scope
W048 implementation restoration; new commercial functionality; new payment integrations; KYC/KYB; live regulated funds movement; new developer-platform features; new marketplace functionality; new connectivity/session/routing/path/transport/federation/policy authority; frozen architecture changes; wire-schema changes; physical validation; modifying `spec/architect/` from the implementation PR; treating historical chat/prompts/issues as authority.

## Architectural precedents
DEC-0047 ACR-005, DEC-0048 ACR-006, DEC-0050 ACR-009, DEC-0054 W041 acceptance, DEC-0057 W042 acceptance, DEC-0059 W051 acceptance, DEC-0061 W052 acceptance, DEC-0063 W053 acceptance, DEC-0084 R1 reconciliation.

## Known open questions
1. Which existing public boundary should be the composition harness entry point without creating a second authority?
2. Can the current mainline demonstrate the complete containment segment without the absent W048 implementation, or must the result remain explicitly incomplete/fail-closed?
3. Which evidence digest/correlation format best proves one canonical chain without adding a new canonical state store?
