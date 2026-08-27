# services — Service Registry and Edge Compute (WORK-025)

Technology-neutral service advertisement, discovery, policy-consumed
authorization, provider-neutral edge execution, and federation-scoped
visibility for ADCOS — implemented per `docs/WORK-025-handoff.md`
(the frozen Architect handoff).

## Authority boundaries (frozen)

| Concern | Owner | How this layer consumes it |
| --- | --- | --- |
| Policy | WORK-010 | `ServiceRegistry.apply_policy_decision` verifies a REAL tamper-evident `policy.model.PolicyDecision` (content-derived id, `allow` effect, freshness); deny/stale/tampered fail closed |
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
- `federation.py` — federation-scoped DATA translation (exposure export / scope constants)
- `serialization.py` — canonical DATA reduction over `protocol.canonicalization`

## Discipline highlights

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
