# services — Service Registry and Edge Compute (WORK-025)

Technology-neutral service advertisement, discovery, policy-consumed
authorization, provider-neutral edge execution, and federation-scoped
visibility for ADCOS — implemented per `docs/WORK-025-handoff.md`
(the frozen Architect handoff).

## Authority boundaries (frozen)

| Concern | Owner | How this layer consumes it |
| --- | --- | --- |
| Policy | WORK-010 | `ServiceRegistry.apply_policy_decision` verifies a REAL tamper-evident `policy.model.PolicyDecision` (content-derived id, `allow` effect, freshness); deny/stale/tampered fail closed. The authorized invocation scope (service, session, caller, tenant) travels INSIDE the decision's digest-covered `extensions` binding — a binding that is BORN at the WORK-010 evaluator itself (`policy.invocation` derives it from the invocation descriptor the composition root declared in the evaluation context, with mirror checks against the first-class fields the rules evaluated). Apply accepts NO scope parameters and the `services` package possesses NO binding-construction capability, so a valid ALLOW can never be re-wrapped around a different authorization scope (PR #26 review, blocker 2, remediation 2) |
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
- `authorization.py` — the WORK-010 consumption seam, verification/extraction ONLY: the `InvocationBinding` (extracted from the decision's tamper-evident `extensions`) and `extract_invocation_binding` (fail-closed scope extraction). There is deliberately NO binding constructor here — the binding is born at the policy authority (`policy/invocation.py` + the evaluator's decision-building path), never minted by the service layer
- `federation.py` — federation-scoped DATA translation (exposure export / scope constants; `peer_claim_fingerprint` is a canonical-content sha256 digest, semantics pinned by the selftest)
- `serialization.py` — canonical DATA reduction over `protocol.canonicalization`

## Discipline highlights

- **Tenant isolation is fail-closed on every query path (PR #26 review, blocker 1)**: `lookup_service` and `discover_services` REQUIRE an explicit `tenant_domain` (omission is a structural TypeError; an empty scope fails closed with `tenant-isolation`); there is no unscoped or cross-tenant enumeration path, and an invocation decision bound to another tenant's scope is rejected before it can authorize anything.
- **Decision-bound invocation scope (PR #26 review, blocker 2, remediation 2)**: the service layer consumes a policy result whose authorized subject/scope is bound to the decision itself. The trust chain is `WORK-010 policy authority / composition root -> decision already bound to exact invocation context -> services verification/extraction ONLY -> execution`: the composition root declares the exact (service, session, caller, tenant) scope as an `adcos.service-invocation` descriptor inside the real `service.invoke` `PolicyContext`, the WORK-010 evaluator derives the digest-covered binding from that context (mirror-checked against the requester/domain the rules evaluated) and never emits an unbound `service.invoke` decision, and the registry extracts the scope from the born-bound decision while never accepting scope parameters — so rebinding is structurally impossible and no exported `services` operation can convert an unbound ALLOW into authorization for an arbitrary scope (pinned by the selftest's no-minting regression).
- **Execution scope is decision-only (PR #26 fourth review, finding B2)**: `admit_execution` accepts `(now, decision_ref, requirements, label)` and NOTHING else — the effective invocation scope is derived exclusively from the stored `InvocationDecision` (its born-bound, digest-covered binding). There is no service/session/caller input at the execution boundary to mismatch or restate: the caller cites a decision, and the admission (registry- and provider-side) carries exactly that decision's scope. The duplicated authority inputs of the previous API shape are gone, not merely checked.
- **Terminal close cannot strand provider state (PR #26 fourth review, finding B1)**: the registry lifecycle is the frozen `open -> close-pending -> closed` protocol. A close attempt tries every unproven provider close; terminal `closed` is claimed ONLY when every provider close is proven (per-registration proven-closure flags, so a proven provider is never re-attempted). An unproven close parks the registry in the explicit, RECOVERABLE `close-pending` state — audited canonically — in which ONLY `release_execution` / `retry_admission_cleanup` and the close retry are legal; every other operation fails closed naming the degraded state. The stranded `registry=closed / provider=active / no recovery path` combination is structurally unreachable.
- **Revocation is independent of the advertisement lifecycle (PR #26 fifth review, finding B3)**: the two policy effects carry different service-record dependencies, because they are different authority acts. An ALLOW *grants* standing authorization, so it still requires a currently live, tenant-consistent record (`_require_service_record`: unknown/withdrawn/stale fail closed). A NON-ALLOW effect *revokes*: recording that WORK-010 has ended an authorization has NO freshness or registration requirement, so `ALLOW@T1 -> service expires or is withdrawn -> DENY@T2 -> DecisionRevocation` always lands (identity consistency only — a still-known record, even a stale one, cannot be contradicted cross-tenant). At the consumption seam a revoked authorization fails `REAUTHORIZATION_REQUIRED` — the policy-lineage verdict — rather than being masked behind `SERVICE_STALE`/`SERVICE_WITHDRAWN`, and the revocation stays effective across advertisement refresh and re-registration (pinned by the selftest's lifecycle-independent revocation regression).
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
