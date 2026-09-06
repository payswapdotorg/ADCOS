# ACR-012: R6 Provider Onboarding & Federation registration

## Status
PROPOSED

## Motivating experience / research
R5/W056 is now accepted and merged by DEC-0094. The frozen roadmap defines R6 as the next gate: Provider Onboarding & Federation. No new architectural semantic requirement is being introduced; this ACR registers the implementation boundary needed to execute the already-frozen R6 objective through a new Work Item.

## Proposed change
Register WORK-057 — Provider Onboarding & Federation — as the sole implementation Work Item for R6. The Work Item will implement only the operator-facing onboarding/federation control boundary: operator/domain registration, trust-domain membership, adapter certification evidence, capability declaration, commercial/service profile binding, settlement configuration references, observability/evidence, suspension/revocation, and deterministic offboarding. It will consume the existing federation, capability, policy, commercial, payment, eligibility, developer API, marketplace, telemetry, and adapter authorities through their public interfaces. It will not restore W048, replace any canonical authority, or introduce new frozen protocol semantics.

Alternatives rejected:
- Reusing an accepted Work Item: rejected because accepted Work Items are historical delivery records and cannot be reused or renumbered.
- Extending W056 after acceptance: rejected because DEC-0094 closed WORK-056-CORE-001 and its amendments.
- Treating R6 itself as authorization: rejected by the roadmap rule that the roadmap does not authorize implementation.
- Creating a generic onboarding authority inside the protocol core: rejected because it would violate the existing separation between federation, policy, commercial, and adapter authorities.

## Mission consistency
The change directly advances the mission by allowing independently operated infrastructure to participate in the federated ADCOS fabric without surrendering infrastructure authority. It preserves access-technology neutrality, federation by explicit trust, evidence provenance, least authority, and external-provider independence.

## Affected architecture sections and locks
- `spec/architecture.md`: §5 Protocol Planes (Identity/Trust, Discovery/Topology, Resource/Intent, Management/Observability); §6.10 Federation; §6.11 Evidence; §9 Node Agent; §10 Adapter Architecture.
- `spec/architecture-lock.md`: LOCK-007 (capability negotiation), LOCK-008 (claim provenance), LOCK-016 (provider isolation), LOCK-017 (no vendor authority), LOCK-022 (zero trust), LOCK-023 (secret separation), LOCK-024 (conformance). No lock text is changed by this ACR.

## Compatibility analysis
- Wire protocol: unchanged; no new frozen wire message semantics are required by this registration.
- Persisted state: W057 introduces only Work-Item-defined onboarding/federation records and evidence projections; it must use explicit versioning and append-only lifecycle semantics where required by existing authorities.
- Live sessions: onboarding/revocation may affect admission of future work but must not rewrite canonical session history. Revocation must fail closed for new admission while preserving historical records.
- Federation relationships: membership is explicitly scoped, revocable, and non-transitive. Domain membership must never imply trust in individual nodes or capabilities beyond the granted scope.
- Mixed-version operation: federation/onboarding APIs must use existing version negotiation and reject unsupported incompatible versions rather than silently reinterpret them.

## Work-item and dependency impact
- New Work Item: WORK-057 — Provider Onboarding & Federation.
- Proposed hard dependencies: WORK-015, WORK-016, WORK-026, WORK-029, WORK-039, WORK-044, WORK-045, WORK-046, WORK-047, WORK-050, WORK-051, WORK-052, WORK-053, WORK-055, WORK-056.
- WORK-048 is intentionally NOT a hard dependency because its accepted implementation artifacts remain absent from current mainline; W057 must not restore, recreate, mock, or substitute W048.
- WORK-049 is not a hard dependency because client-runtime behavior is downstream participation UX/runtime, not provider onboarding authority.
- Dependency graph addition: each listed hard dependency points to WORK-057; no existing edge is removed or reordered.

## Migration / rollback plan
No protocol migration is required. Registration is additive governance. If W057 implementation is rejected, the Work Item returns to unaccepted/unimplemented status and the active implementation slot remains empty; no accepted Work Item or frozen semantic is rolled back. If an implemented onboarding/federation deployment must be rolled back, new admissions are disabled and federation credentials are revoked through the canonical trust/authorization mechanisms while historical commercial and federation records remain immutable.

## Architect decision
PROPOSED. The sole Architect finds the R6 boundary sufficiently defined to enter the durable governance process, but implementation authorization is intentionally withheld until the frozen backlog, dependency graph, roadmap version, ledger, and authorization record are synchronized in one accepted governance transition.

## Resulting architecture version
Unchanged: Architecture Version 1.0 and Protocol Version 1.0 remain frozen.
