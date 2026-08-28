# WORK-025 — Service Registry and Edge Compute

## Authority

This handoff is issued by the Architect against the frozen ADCOS Architecture Version 1.0, the frozen `spec/work-items.md` WORK-025 entry, and accepted WORK-009, WORK-010, WORK-015, and WORK-024 boundaries.

This document is an implementation handoff only. It does not modify or reinterpret `spec/`.

## Hard dependencies

- WORK-009 — Intent/QoS model — accepted
- WORK-010 — Policy engine — accepted
- WORK-015 — Federation protocol — accepted
- WORK-024 — Distributed core / local breakout / UPF integration — accepted

WORK-020's outstanding SDR laboratory evidence is independent and does not block WORK-025.

## Objective

Implement a technology-neutral service registry and edge-compute integration layer so ADCOS nodes can advertise, discover, authorize, select, expose, and execute local services while preserving service identity, node identity, policy authority, federation authority, and connectivity/session authority as separate concerns.

The implementation must make the following architecture statement operational:

> ADCOS connectivity and edge services form one coherent fabric, while service semantics remain independent of access technology and service identity remains distinct from node identity.

## Architectural placement

WORK-025 belongs to the **Service Registry / Edge Compute** role inside the Agent and distributed-service architecture. It is not a new routing engine, policy engine, session manager, identity system, federation engine, or application platform.

The intended composition is:

```text
WORK-004 Identity authority
        |
WORK-010 Policy authority -------------------+
        |                                     |
WORK-011 Routing / WORK-012 Sessions         |
        |                                     v
        +--------------------------> ServiceRegistry / EdgeRuntime
                                           |
                         +-----------------+-----------------+
                         |                                   |
                  Service advertisement                 Service execution
                         |                                   |
                  capability + evidence                 local edge hook
                         |                                   |
                         v                                   v
                  discovery / lookup                Edge service provider
                         |
                 local-first selection
                         |
                 WORK-024 connectivity fabric
```

The service layer consumes existing authorities through their public seams. It must not become an alternative authority for identity, policy, routing, federation, or sessions.

## Non-negotiable invariants

1. **Service identity is distinct from NodeID.** A service may move between edge nodes without becoming a different service identity when the service authority permits continuity. A node may host multiple services. A service reference must never be derived from or collapsed onto a node identity.

2. **A service is not a capability claim merely because it is registered.** Service advertisement is attributable DATA. Evidence/provenance remains explicit. Remote reports remain claims until accepted under the appropriate authority/policy.

3. **Policy authority remains WORK-010.** WORK-025 consumes REAL policy decisions / authorization outcomes where required. It must not evaluate policy, invent trust, or silently override deny decisions.

4. **Federation authority remains WORK-015.** Federated service exposure/visibility is consumed as federation-scoped DATA and policy. Membership in a federation never implies unrestricted service trust or access.

5. **Routing authority remains WORK-011.** Service discovery may identify candidate service locations; it must not compute or replace network paths. Connectivity to a selected service composes ordinary WORK-011 paths / WORK-024 breakout semantics.

6. **Session authority remains WORK-012.** Service invocation/attachment must not mint or reinterpret logical connectivity sessions. A service handoff may change the underlying path/provider while preserving the governing session identity when supported.

7. **Local-first resilience is normative.** When upstream connectivity is unavailable, locally available and authorized services must remain discoverable and executable where their policy/capacity permits. Upstream dependency failure must not erase valid local service state.

8. **Availability is evidence-backed.** `available` must not be inferred solely from advertisement existence. Health, capacity, validity, placement, and execution readiness remain distinct facts where the owning authority exposes them.

9. **Service execution is a seam, not an application platform.** The Work Item may define an execution-hook abstraction and deterministic reference executor, but it must not implement a general-purpose application runtime, arbitrary plugin loading, container orchestration platform, or full PaaS.

10. **Least authority applies to service execution.** A service provider/edge executor receives only the context needed for the operation. Service execution must not receive unrestricted identity stores, policy internals, routing internals, credentials, federation state, or database access through the service contract.

11. **Credentials and secrets never become service-registry DATA.** Registration, lookup, evidence, and execution records must carry only opaque credential references / secret-free metadata. Secret retrieval, where explicitly required, remains behind the existing identity/credential boundary.

12. **Tenant/domain boundaries are explicit where persistence exists.** Service records, visibility, authorization, execution state, and discovery queries must not cross their owning administrative/tenant boundary without an explicit federation/policy path.

13. **Validation is side-effect free.** Identity derivation and authoritative registry mutations follow the validate/commit discipline established by WORK-023/024. Failed operations must not consume derivation state or partially mutate canonical state.

14. **Canonical state contains authoritative service facts only.** Do not serialize sockets, process ids, implementation labels, local filesystem paths, secrets, stack traces, timestamps generated implicitly by the process, or other diagnostics into canonical service state.

15. **No technology-specific service logic in core.** Wi-Fi, 5G, Ethernet, satellite, mesh, UPF, RAN, container, VM, Kubernetes, or vendor-specific APIs may be implementation/provider details only. Service discovery and execution semantics remain access-neutral.

16. **No hidden second registry.** Reuse existing WORK-002 capability/resource vocabularies and existing core identifiers. Do not introduce a parallel source of truth for NodeID, Capability ID, ResourceKind, Intent, Path, Session, or Federation identifiers.

17. **Determinism is required.** Given the same service records, policy DATA, discovery inputs, and injected instants, selection, lifecycle transitions, canonical bytes, and reference implementation outputs must be byte-identical across repeated runs and hash seeds.

## Required domain concepts

The implementation should establish technology-neutral service concepts sufficient to support the frozen acceptance criteria:

- `ServiceRef` / service identity
- service descriptor / metadata
- service endpoint or service location reference
- advertisement / registration state
- evidence/provenance for service claims
- visibility / publication scope
- service requirements and dependency declarations
- service capacity / resource accounting using WORK-008 DATA
- service health/readiness as observed DATA
- local-first discovery and selection
- execution request / execution result hooks
- placement / relocation metadata where needed
- lifecycle state with explicit fail-closed transitions
- deterministic expiration / stale advertisement handling
- federation-aware exposure without importing federation authority

Exact names are implementation choices unless frozen elsewhere; semantics above are mandatory.

## Service identity requirements

The central service identity rule is:

```text
ServiceID != NodeID
        != SessionID
        != PathID
        != CapabilityID
        != ResourceID
        != FederationID
        != implementation/provider identity
```

Service identity must be opaque to callers and stable under access-path changes. A service hosted by node A may later be hosted by node B without requiring the service abstraction to masquerade as either node.

Where content-derived identifiers are used, derive them from service-owned identity material only; never include incidental hosting implementation labels or access technology names.

## Discovery semantics

Service discovery is a lookup/claim mechanism, not a new topology authority.

At minimum, support:

```text
local service advertisement
        ↓
validation + freshness
        ↓
policy / visibility filtering
        ↓
capability / intent compatibility
        ↓
candidate service locations
        ↓
caller/composition-root selection
        ↓
ordinary WORK-011 / WORK-024 connectivity
```

Do not enumerate or score network routes inside the service registry.

Discovery must distinguish at least:

- unknown service;
- known but stale advertisement;
- known but unauthorized/hidden;
- known and currently eligible;
- known but unavailable at execution time;
- expired/tombstoned record where replay protection is required.

## Local-first behavior

A node with upstream loss must still be able to:

- retain valid local service registrations;
- discover locally hosted authorized services;
- evaluate eligibility from already-authorized local policy DATA;
- execute a local service through the edge execution seam;
- report the upstream outage without falsely declaring remote service loss as local state corruption.

A locally hosted service must not require a global service registry round trip merely to remain usable when the architecture/policy explicitly permits offline operation.

## Service placement and relocation

WORK-025 may model service placement and relocation, but the semantics are explicit:

```text
ServiceID stays stable
HostNode may change
Connectivity/session may change
Placement transition is recorded
Authorization is re-evaluated under current policy
```

Do not silently mutate a service's host and pretend no transition occurred. A relocation/failover operation that succeeds must record enough DATA for audit and deterministic reconstruction.

## Edge execution boundary

Define a minimal execution hook such as:

```text
prepare / admit
execute
result / status
cancel or release
health / readiness
```

The execution contract must be provider-neutral. Reference execution may be deterministic and in-process.

The execution surface must:

- reject unauthorized invocations before provider-side effects;
- carry service identity explicitly;
- carry caller/session references only as opaque authorized DATA;
- avoid exposing policy internals or secrets;
- isolate provider exceptions as typed failures/results;
- have deterministic resource/budget accounting;
- make partial execution failures explicit.

No arbitrary code generated from service advertisements is permitted.

## Resource and capacity integration

Reuse WORK-008 resources rather than inventing a service-capacity registry.

Service capacity may consume/declare existing `compute`, `storage`, `bandwidth`, `energy`, or `edge-service-capacity` DATA. Measurement and offer semantics remain distinct.

A service advertisement must not imply capacity reservation unless an explicit resource-admission path exists.

As learned in WORK-022:

> Existence of a service record is not evidence that its resource reservation exists.

Capacity exhaustion must fail closed and must leave authoritative state unchanged on failed admission.

## Intent integration

Service lookup may consume a REAL WORK-009 intent describing requirements such as locality, latency, privacy, service capability, availability, or resource bounds.

The service layer may perform deterministic compatibility filtering against declared service DATA, but policy semantics remain in WORK-010 and route computation remains in WORK-011.

Do not introduce a second intent grammar.

## Policy integration

When a service is privileged, private, federated, costly, or otherwise policy-controlled, the service layer must consume an explicit authorization/policy result.

Required negative cases should include:

- denied invocation;
- stale decision;
- future-dated decision;
- decision for another service/caller/session;
- tampered decision DATA where the existing policy model supports tamper evidence;
- policy change between discovery and execution where the contract requires re-authorization.

A discovered service is never implicitly authorized to execute merely because it was advertised.

## Federation integration

Federated service discovery must remain scoped:

```text
local service
   ↕ explicit federation policy
peer-domain service claim
   ↕ scoped visibility/trust
eligible candidate
```

Do not import or recreate WORK-015 federation trust state. The service layer may carry federation references, scope, and exposure policy as DATA.

Removing federation exposure must not delete local service state.

## Persistence expectations

If a durable service registry is required by the existing platform implementation, use the existing database/persistence conventions rather than introducing a new datastore abstraction.

Durable records should support:

- immutable identity/provenance where required;
- explicit lifecycle state;
- tenant/domain isolation;
- idempotent registration updates where the service semantics permit updates;
- deterministic conflict behavior;
- query-by-service identity and capability;
- expiration/withdrawal semantics.

Do not add persistence to the kernel merely for convenience.

## Expected implementation surface

Prefer a new `adapters` family only when an external execution provider truly requires an adapter. The core service registry and execution contracts should live in the existing service/Agent architecture location rather than inventing a technology adapter for the concept itself.

A reasonable first implementation may include:

```text
services/
  contract.py          service discovery + execution contracts
  model.py             service identity, descriptors, records, results
  validation.py        identity/ref/metadata validation
  errors.py            typed service failures
  registry.py           lifecycle + lookup + local-first visibility
  execution.py         provider-neutral execution seam/reference executor
  sandbox.py            least-authority execution mediation
  federation.py        federation-scoped DATA translation only, if needed
  serialization.py      canonical DATA reduction

 tools/service_selftest.py
 docs/WORK-025-...md / README documentation
 .github/workflows/spec-check.yml
```

This is guidance, not a mandate to create exactly these filenames. Do not create a new top-level module if an existing repository module already owns the same authority.

## Required verification battery

The focused selftest must prove at least:

1. Service identity is distinct from NodeID and SessionID.
2. Service registration is deterministic and repeat-safe.
3. Service advertisements carry explicit validity and provenance.
4. Stale/expired/withdrawn services fail closed.
5. Service discovery is capability/intent aware but does not compute routes.
6. Local-first discovery works with upstream connectivity absent.
7. Local service execution succeeds through the provider-neutral execution seam.
8. Unauthorized service execution fails before provider-side mutation.
9. Service execution/provider failures are isolated and typed.
10. Capacity admission uses WORK-008 DATA and never confuses advertisement with reservation.
11. Capacity exhaustion / execution failure leaves authoritative state unchanged where required.
12. Service placement can change host while preserving ServiceID.
13. Placement transition is explicitly recorded and auditable.
14. Session identity remains stable across supported service relocation/connectivity changes.
15. Federation-scoped service visibility does not leak local state or imply universal trust.
16. Removal of federation exposure preserves the local service record.
17. Tenant/domain isolation is enforced for durable/queryable service state where applicable.
18. Secret/credential markers never appear in service records, canonical bytes, results, or errors.
19. Least-authority execution context is structurally enforced.
20. No second policy/routing/identity/resource/federation authority is introduced.
21. No technology/vendor-specific symbols leak into the generic service layer.
22. Validation/commit sequence discipline holds; failed operations consume no identity-derivation state.
23. Canonical state is free of implementation/process diagnostics.
24. Repeated runs and multiple `PYTHONHASHSEED` values produce byte-identical output.
25. Existing full repository battery remains green.
26. Frozen `spec/` remains byte-identical to `main`.
27. `py_compile` and `mypy` remain clean for introduced Python code.
28. CI executes the new focused suite and passes.

## Acceptance gate

The implementation PR must be returned **open and unmerged** for Architect review.

The PR body must contain:

- WORK-025 objective;
- architecture sections implemented;
- dependency verification;
- service identity / node identity separation;
- policy/routing/federation authority boundaries;
- local-first and edge-execution behavior;
- resource/capacity semantics;
- federation visibility semantics;
- complete acceptance-criteria-to-test mapping;
- full verification results;
- explicit out-of-scope statement;
- architecture-lock compliance;
- no-architecture-drift statement;
- known limitations and honest environment disclosures.

Z.ai must **not merge** WORK-025. The Architect performs final acceptance and merge.

## Out of scope

- full PaaS/application platform;
- arbitrary user-code execution platform;
- container orchestration/Kubernetes control plane;
- vendor-specific edge runtimes as core semantics;
- new routing engine;
- new policy engine;
- new federation authority;
- new identity authority;
- new resource registry;
- blockchain/token economics;
- billing/settlement;
- proprietary radio/PHY implementation;
- changes to frozen `spec/` documents;
- UI redesign unrelated to the service/edge acceptance surface.

## Definition of done

ADCOS can discover and use authorized edge services locally and across eligible connectivity/federation scopes, preserve service identity independently of its hosting node, survive upstream failure where policy permits, and expose a provider-neutral execution seam without creating a competing core authority.
