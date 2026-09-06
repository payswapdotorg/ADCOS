# WORK-057 — Provider Onboarding & Federation

## Identity
- Work Item ID: WORK-057
- Title: Provider Onboarding & Federation
- Program gate: R6 — Provider Onboarding & Federation
- Status: PROPOSED — not registered in the frozen backlog and not authorized
- Critical path: yes

## Objective
Provide the operator-facing control boundary that allows independently operated networks, ISPs, carriers, enterprises, satellite systems, hotspots, mesh operators, and infrastructure owners to participate in ADCOS through explicit onboarding and federation without surrendering infrastructure authority or creating a second ADCOS-wide authority.

## Baseline
- Governance baseline: `b11cf44db922811d2518c05685aee14127243264` (R5/W056 accepted by DEC-0094)
- Architecture version reference: `1.0`
- Protocol version reference: `1.0`
- Registration proposal: `ACR-012`
- Implementation authorization: none until the ACR is accepted and the frozen backlog/DAG are synchronized

## Hard dependencies
- WORK-015 — Federation protocol
- WORK-016 — Adapter SDK/runtime
- WORK-026 — Telemetry and observability
- WORK-029 — Upgrade/rollback/compatibility manager
- WORK-039 — Federation at scale
- WORK-044 — Payment Provider Adapters & Settlement Gateway
- WORK-045 — Connectivity Eligibility, Provider Trust & Jurisdiction Policy
- WORK-046 — Developer Connectivity API, SDK & Webhook Platform
- WORK-047 — Connectivity Marketplace Discovery, Proximity & Path Selection
- WORK-050 — Platform Connectivity Sharing Capability & Isolation Matrix
- WORK-051 — CommercialCore
- WORK-052 — UsageLedger
- WORK-053 — EconomicAllocation
- WORK-055 — Protocol Production Conformance
- WORK-056 — Developer Connectivity Platform Production Hardening

## Explicit non-dependencies
- WORK-048 is not a hard dependency. Its accepted implementation remains absent from current mainline and must not be restored, recreated, mocked, or substituted by WORK-057.
- WORK-049 is not a hard dependency. Client participation UX/runtime is downstream of operator onboarding and federation, not an authority prerequisite for onboarding.
- WORK-040 is not a software dependency. Its physical evidence remains independent and W040-owned.

## Authority consumed
Existing federation membership/trust scope; node identity and credential references; capability statements and evidence provenance; policy/eligibility decisions; adapter certification boundaries; commercial lifecycle; usage/finality; allocation; external payment-provider references; developer API; marketplace offer discovery; telemetry; upgrade/compatibility controls.

## Authority created
None beyond a bounded onboarding/federation lifecycle record set that is subordinate to the existing identity, trust, capability, policy, federation, commercial, payment, and telemetry authorities. W057 does not become authoritative for NodeID, canonical session state, NetworkPath, routing, transport, usage, allocation, payment movement, or physical connectivity.

## Core lifecycle
```text
application/registration
    -> operator/domain identity binding
    -> credential/scoped-access issuance
    -> adapter declaration + certification evidence
    -> capability/resource declaration
    -> service/commercial profile binding
    -> eligibility/policy evaluation
    -> federation agreement proposal
    -> explicit federation acceptance
    -> active federated membership
    -> suspension/revocation/offboarding
```

Every transition is versioned, attributable, deterministic, replay-safe, and auditable. Federation membership is scoped and revocable; domain membership does not imply trust in individual nodes or all capabilities within the domain.

## Required capabilities
1. Operator/domain registration using existing identity and credential references; no raw private keys or regulated identity documents become ordinary onboarding metadata.
2. Explicit trust-domain membership and federation agreement lifecycle using existing federation authority.
3. Adapter certification records that bind an operator's declared access/provider adapters to evidence without making the adapter vendor authoritative for ADCOS state.
4. Capability/resource declarations with validity, provenance, and withdrawal semantics using existing capability/resource authorities.
5. Commercial/service profile binding to existing CommercialCore, Eligibility, Payment, Allocation, and Developer API surfaces without duplicating their canonical state.
6. Settlement configuration as references/configuration only; W057 does not move, custody, mint, or settle regulated funds.
7. Observability and evidence records sufficient to audit onboarding decisions, federation changes, suspension, revocation, and offboarding.
8. Fail-closed suspension/revocation for new admissions while preserving immutable historical records.
9. Deterministic offboarding that revokes future participation without deleting historical commercial/federation evidence.
10. Explicit mixed-version compatibility behavior using existing protocol negotiation/versioning; incompatible peers fail closed rather than being silently reinterpreted.

## Federation invariants
- Federation membership is scoped, explicit, revocable, and non-transitive.
- Provider/domain membership never implies node-level identity or trust.
- Capability declarations are claims until satisfied by the evidence/policy rules of the consuming authority.
- A provider's external system is authoritative only for its own technology domain; ADCOS records the mapped observation/claim according to evidence rules.
- Provider success, payment success, or onboarding completion never creates connectivity/session/path state.
- Onboarding cannot activate a path, create usage, create billable finality, or settle money.
- Revocation prevents new federation-dependent admission where policy requires it, while historical state remains immutable.
- No vendor-specific API/type leaks into protocol/core authority.

## Security model
Zero-trust federation; least-authority credentials; scoped administrative roles; anti-replay and duplicate protection; signed federation artifacts where required by existing protocol profiles; secret separation; explicit revocation; no implicit trust transitivity; deterministic conflict handling.

## Failure/recovery model
Malformed, expired, incompatible, unsigned/invalidly signed, revoked, unauthorized, duplicate-conflicting, or out-of-policy onboarding/federation inputs fail closed. Interrupted onboarding resumes from durable state without inventing membership. Federation revocation is idempotent. Historical commercial and federation evidence is append-only and never rewritten.

## Adapter boundary
Provider-specific network, access, routing, management, cloud, RAN, modem, satellite, enterprise, or hotspot APIs stay behind the existing adapter boundary. Certification validates the adapter contract and evidence; it does not import provider implementation details into the core.

## Verification
- deterministic onboarding lifecycle battery;
- federation membership/acceptance/revocation/offboarding tests;
- trust-scope isolation and non-transitivity negatives;
- capability declaration provenance/expiry/withdrawal tests;
- adapter certification and forbidden-import audits;
- eligibility/policy integration negatives;
- commercial/payment/reference-only boundary negatives;
- onboarding cannot create connectivity/session/path/usage/payment state;
- replay, duplicate, out-of-order, and concurrent onboarding tests;
- mixed-version compatibility and fail-closed incompatibility tests;
- credential scope and privilege-boundary negatives;
- secret-handling and metadata-classification audits;
- deterministic evidence/audit record verification;
- upgrade/rollback/offboarding recovery tests;
- PYTHONHASHSEED and repeat-run determinism;
- full sibling-battery regression verification.

## Acceptance gate
The sole Architect accepts W057 only when the exact delivery demonstrates that independently operated providers/domains can be registered, certified, bound to existing commercial/policy/service configuration, federated, suspended/revoked, and offboarded through a deterministic least-authority boundary; no new connectivity/commercial authority is created; no W048 restoration occurs; all affected accepted batteries remain green; and no frozen Architecture/Protocol semantic change occurs.

## Evidence classes
- SOFTWARE: deterministic onboarding/federation tests, scope/security audits, adapter certification evidence, lifecycle/audit evidence.
- OPERATIONAL: only when separately authorized and actually observed.
- PHYSICAL: none implied by this Work Item; real deployment evidence remains separately governed by W040 or a future explicit evidence authorization.

## Out-of-scope
- W048 restoration or any substitute sharing runtime.
- New identity, session, NetworkPath, routing, transport, packet, usage, allocation, or payment authority.
- Custody or movement of regulated funds.
- KYC/KYB document custody or legal-advice automation.
- Vendor-specific semantics inside the core.
- New protocol wire semantics unless separately authorized through ACR/change control.
- Marketplace ranking/routing implementation beyond invoking existing canonical surfaces.
- Physical deployment claims or closure of W040 evidence.
- Global autonomous trust without explicit federation policy.

## Definition of done
An independently operated provider/domain can pass through a deterministic, auditable onboarding and federation lifecycle and expose only the explicitly authorized capabilities/services through existing ADCOS authorities, with revocation/offboarding and evidence preservation, without creating a second source of truth or requiring surrender of underlying infrastructure control.
