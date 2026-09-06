# WORK-057 Implementation Prompt — Provider Onboarding & Federation

## Authority
You are implementing **WORK-057 only** under repository-local authorization `WORK-057-CORE-001`, authorized by `DEC-0095`.

The authoritative baseline is the ADCOS `main` tree immediately preceding the R6 governance transition, identified by `baseline_sha: 16c066ff4766d362f0edfcb790524b2c0ef44cae`. The current `main` contains the governance transition and authoritative R6 state. Reconstruct from repository contents; do not rely on chat history.

Architecture Version: **1.0**
Protocol Version: **1.0**

## Mission alignment
Advance ADCOS toward the **Stripe of connectivity**: an external application can consume connectivity through stable platform interfaces while independently operated network owners retain control of their own infrastructure and underlying access technology remains behind adapter/provider boundaries.

## Exact objective
Enable an independently operated provider/domain to participate in ADCOS through a deterministic, auditable onboarding and federation lifecycle without creating a second connectivity, identity, routing, session, transport, payment, usage, allocation, or policy authority.

## Existing authoritative foundation
Inspect and reuse the existing federation, identity, trust, capability, resource, policy, commercial, telemetry, adapter, management, and developer API authorities through their public interfaces. The existing `federation/` implementation is normative WORK-015 infrastructure and already defines scoped/revocable relationships, least-authority grants, append-only events, deterministic exchanges, peer binding, provenance-preserving imported claims, and opaque imported references. Do not duplicate these authorities. fileciteturn278file0

## Required lifecycle
`registration → operator/domain identity binding → scoped credential issuance → adapter declaration/certification → capability/resource declaration → service/commercial profile binding → eligibility/policy evaluation → federation proposal → explicit acceptance → active federated membership → suspension/revocation/offboarding`

## Required capabilities
Implement the smallest coherent set needed to make the lifecycle executable and externally auditable:

1. Provider/operator/domain registration with explicit identity binding.
2. Explicit trust-domain association using existing federation authority.
3. Scoped credential/reference handling; never serialize secret material as ordinary domain/topology data.
4. Adapter declaration and certification evidence with provider-specific implementations isolated behind adapter boundaries.
5. Capability/resource declarations with provenance, validity, expiry, and source references.
6. Service and commercial profile bindings to existing commercial authorities; settlement references remain references.
7. Deterministic eligibility/policy evaluation using existing policy/eligibility authorities.
8. Federation proposal, explicit acceptance, membership activation, suspension, revocation, and deterministic offboarding.
9. Durable recovery after interrupted onboarding and idempotent duplicate/replay handling.
10. Mixed-version compatibility through existing upgrade/version authorities.
11. Observable/auditable evidence for every lifecycle transition.

## Non-negotiable authority rules
- Do not create a second identity authority.
- Do not create a second federation authority.
- Do not create a new routing, session, transport, NetworkPath, usage, settlement, payment, allocation, or generic policy authority.
- Federation membership never implies node-level trust.
- Federation scopes remain least-authority and non-transitive.
- Imported peer claims remain claims with provenance and do not become authoritative topology.
- Imported routes/capabilities/resources remain references consumed by their owning authorities.
- Provider/vendor success can never create connectivity or payment state.
- Credential issuance never grants broad provider authority beyond the declared scope.
- Revocation must fail closed and preserve historical evidence.
- No access-technology name or vendor SDK may leak into core semantics.
- Do not restore WORK-048.
- Do not modify or close WORK-040 physical-evidence obligations.

## Security requirements
Test and enforce malformed, expired, incompatible, unauthorized, conflicting, revoked, replayed, duplicated, out-of-order, concurrent, and stale onboarding inputs. Trust must be explicit; no transitive trust assumptions. Secrets remain separated from ordinary state. Provider-specific credentials remain under their provider/adapter boundary.

## Determinism requirements
Identical inputs must produce identical IDs, ordering, decisions, lifecycle transitions, evidence, and serialized outputs. Do not use wall-clock time, randomness, thread scheduling, unordered iteration, network access, or UUID generation where deterministic repository patterns require injected values or canonical ordering.

## Acceptance requirements
The implementation is acceptable only when evidence demonstrates all of the following:

- deterministic registration and identity binding;
- adapter certification and forbidden-import discipline;
- capability/resource provenance, validity, and expiry;
- eligibility/policy fail-closed behavior;
- federation proposal/acceptance/activation;
- suspension/revocation/offboarding and historical preservation;
- non-transitivity and authority separation;
- duplicate/replay/out-of-order/concurrent safety;
- interrupted onboarding recovery;
- mixed-version behavior;
- credential and secret separation;
- auditability and evidence provenance;
- proof that onboarding/federation cannot create connectivity/session/path/route/transport/usage/payment/settlement state;
- deterministic repeat-run evidence;
- regression compatibility with accepted W054/W055/W056 surfaces;
- proof that no W048 material was restored and W040 state was untouched.

## Implementation scope
Permitted implementation areas are those named by `WORK-057-CORE-001`, especially:
`federation/`, `adapters/`, `capabilities/`, `resources/`, `policy/`, `telemetry/`, `management/`, `developerapi/`, `tools/`, plus W057 evidence/handoff documents.

The implementation PR MUST NOT modify `spec/architect/` and MUST NOT alter frozen architecture/protocol semantics. An architecture conflict requires stopping and reporting the exact conflict; it must not be worked around.

## Required delivery
Deliver one PR for WORK-057 only, with:
- implementation;
- deterministic/adversarial tests;
- evidence manifest/report;
- explicit architecture-lock compliance statement;
- no-drift statement;
- exact verification commands and outputs;
- baseline/ancestry proof;
- list of all changed files;
- explicit statement that W048 was not restored and W040 was not altered.

Do not begin any successor Work Item. Do not request a new authorization. The sole Architect will perform the final adversarial review and acceptance.
