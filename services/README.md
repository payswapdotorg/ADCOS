# services — Service Registry and Edge Compute (WORK-025)

Technology-neutral service advertisement, discovery, policy-consumed
authorization, provider-neutral edge execution, and federation-scoped
visibility for ADCOS — implemented per `docs/WORK-025-handoff.md`
(the frozen Architect handoff).

## Authority boundaries (frozen)

| Concern | Owner | How this layer consumes it |
| --- | --- | --- |
| Policy | WORK-010 | `ServiceRegistry.apply_policy_decision` verifies a REAL tamper-evident `policy.model.PolicyDecision` (content-derived id, `allow` effect, freshness); deny/stale/tampered fail closed. The authorized invocation scope (service, session, caller, tenant) travels INSIDE the decision's digest-covered `extensions` binding (`services/authorization.py`) — apply accepts NO scope parameters, so a valid ALLOW can never be re-wrapped around a different authorization scope (PR #26 review, blocker 2) |
| Federation | WORK-015 | `FederationReader` (read-only `check_scope` projection) consumed as DATA; scopes carried as the frozen `service.discover` / `service.invoke` strings (cross-checked by the selftest, never imported) |
| Routing | WORK-011 | Discovery returns candidate service LOCATIONS; routes are never computed, scored, or enumerated — connectivity composes ordinary Paths / WORK-024 breakout semantics at the composition root |
| Sessions | WORK-012 | `SessionReader` (read-only `lookup` projection); session ids are opaque authorized DATA; secureable = ESTABLISHED/DEGRADED |
| Resources | WORK-008 | Capacity declarations use frozen resource kinds and base units as DATA (`compute`, `storage`, `bandwidth`, `energy`, `edge-service-capacity` — cross-checked by the selftest); advertisement = offer, admission/allocation = reservation |
| Identity | WORK-004 | NodeIDs validated as DATA grammar; service identity derives from service-owned material only |

## Service identity

`ServiceRef = services:service:<sha256[:32]>` over
`{(name, service_kind, tenant_domain)}` — hosting node, endpoint,
capacity, labels, and visibility are deliberately excluded, so a
service may move between edge nodes without becoming a different
service identity.  The identity is structurally disjoint from every
NodeID / session / path / resource / federation / family grammar.

## Module layout

- `errors.py` — frozen reason-code vocabulary (`services` prefix), caller-side `ServiceError` (raised) vs implementation-side `ServiceFailure` (returned value)
- `validation.py` — fail-closed shape/grammar validators, DATA discipline, credential-like rejection, identity-separation asserts
- `model.py` — frozen vocabularies, canonical records (descriptor / advertisement / evidence / candidate / decision / admission / allocation / outcome / placement / tombstone / exposure / observation / event), and the deterministic `derive_*` family (SHA-256 over canonical JSON)
- `contract.py` — `ExecutionProviderContract` ABC (open/admit/execute/release/observe/health/close), the immutable least-authority `ServiceContext`, `SessionReader`, `FederationReader`
- `sandbox.py` — `SandboxedExecutionProvider`: step budgets, return-shape contract validation, exception isolation (typed failures; only exception CLASS names cross — LOCK-023), health ladder
- `execution.py` — `ReferenceEdgeExecutor`: deterministic in-process reference implementation with the validate/commit split and candidate-sequence discipline
- `registry.py` — `ServiceRegistry`: the composition root (lifecycle, discovery, policy application, execution, capacity, federation exposure, canonical state)
- `authorization.py` — the WORK-010 consumption seam: the `InvocationBinding` (carried inside the decision's tamper-evident `extensions`), `extract_invocation_binding` (fail-closed scope extraction), and `bind_invocation_decision` (the composition-root helper that binds a genuine engine ALLOW to the exact invocation scope)
- `federation.py` — federation-scoped DATA translation (exposure export / scope constants; `peer_claim_fingerprint` is a canonical-content sha256 digest, semantics pinned by the selftest)
- `serialization.py` — canonical DATA reduction over `protocol.canonicalization`

## Discipline highlights

- **Tenant isolation is fail-closed on every query path (PR #26 review, blocker 1)**: `lookup_service` and `discover_services` REQUIRE an explicit `tenant_domain` (omission is a structural TypeError; an empty scope fails closed with `tenant-isolation`); there is no unscoped or cross-tenant enumeration path, and an invocation decision bound to another tenant's scope is rejected before it can authorize anything.
- **Decision-bound invocation scope (PR #26 review, blocker 2)**: the service layer consumes a policy result whose authorized subject/scope is bound to the decision itself — the composition root evaluates a real `service.invoke` context, then binds the engine ALLOW via `bind_invocation_decision`; the registry extracts the scope from the digest-covered binding and never accepts scope parameters, so rebinding is structurally impossible (forging the binding breaks the digest).
- **Validate/commit with candidate sequence**: derivation nonces advance only in commit phases; failed operations consume no derivation state and never partially mutate canonical state.
- **Local-first (LOCK-012)**: the registry is local deterministic state; with upstream unavailable, local records stay registered, local discovery and execution keep working, and the outage is reported (observation) rather than mistaken for local corruption.
- **Advertisement ≠ reservation (the WORK-022 lesson)**: registration alone reserves nothing; execution admissions consume declared `edge-service-capacity`; exhaustion fails closed leaving authoritative state unchanged.
- **Execution is a seam, not a platform (LOCK-016/017)**: deterministic reference executor, no arbitrary code loading, no container/VM/vendor runtime concepts; provider faults isolated as typed values.
- **Secrets never become registry DATA (LOCK-023)**: credential-like text is rejected in every free-text field; canonical bytes carry no secrets.
- **Determinism**: identical inputs and injected instants produce byte-identical canonical bytes across runs and hash seeds (proven by `tools/service_selftest.py` including `PYTHONHASHSEED` subprocess runs).

## Verification

`python3 tools/service_selftest.py` — the focused WORK-025 battery
(mapping every handoff verification item), also wired into
`.github/workflows/spec-check.yml`.
