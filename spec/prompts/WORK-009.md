# ADCOS WORK-009 — Intent and QoS Model

## Status

ACTIVE — Implementation Handoff

## Objective

Implement the technology-neutral ADCOS Intent and QoS model. An Intent describes what connectivity or service properties are desired; it MUST NOT decide how those properties are achieved.

## Frozen boundary

```text
INTENT
  = desired outcome / requirements

INTENT != policy decision
INTENT != authorization
INTENT != topology fact
INTENT != resource offer
INTENT != resource measurement
INTENT != route/path
INTENT != adapter/access technology
INTENT != trust score
INTENT != price/settlement
```

The implementation must preserve this separation mechanically.

## Frozen work item

WORK-009 — Intent and QoS model

Objective: Implement intent schemas for bandwidth, latency, reliability, locality, energy, cost, privacy, and service constraints.

Dependencies: WORK-008

Acceptance criteria:
- intents describe requirements, not implementation technology;
- constraints support hard and soft preferences;
- unsupported constraints fail explicitly;
- normalized intents are deterministic.

Required verification: schema and policy tests.

Out of scope: route computation.

Definition of done: Applications/operators can ask for connectivity without specifying 5G/Wi-Fi/etc.

## Required domain concepts

Implement these technology-neutral objects:

1. **ConnectivityIntent** — immutable request with intent ID/digest, requester NodeID where applicable, validity, requirements, preferences, privacy requirements, and service constraints.
2. **Constraint** — normalized requirement/preference containing stable identifier, dimension, operator, value, unit/domain where applicable, hardness (`hard` or `soft`), deterministic weight/priority for soft preferences, optional scope/target, and provenance/reference metadata where appropriate.
3. **NormalizedIntent** — canonical deterministic representation after validation/defaulting. It must not perform policy evaluation or route/resource selection.
4. **NormalizationResult** — explicit success/failure with stable error codes and deterministic diagnostics.

Reuse existing authorities: WORK-004 NodeID parsing; WORK-003 temporal/canonicalization; WORK-002 registries; WORK-008 resource/unit primitives. Do not duplicate any of those authorities.

## Frozen constraint dimensions

The core dimensions are:

- bandwidth
- latency
- reliability
- locality
- energy
- cost
- privacy
- service

These are intent dimensions, not implementations.

Examples:

```text
bandwidth >= 10 Mbps      hard
latency <= 50 ms          hard
reliability >= 99.9%      hard
locality = "GH"           soft
energy_budget <= 5 kJ     soft
cost <= 5                 soft
privacy = "end-to-end"    hard
service = "voice"         hard
```

Core intent MUST reject implementation-specific dimensions such as 5G, NR, Wi-Fi, vendor names, cell IDs, route IDs, or next hops. They must never be promoted to normalized core semantics.

## Hard and soft semantics

`hard` means mandatory. `soft` means a preference for later policy/routing layers. Normalization records this distinction but does not choose a winner, resource, adapter, or path.

Hard/soft classification must be structurally explicit; do not encode it in arbitrary strings.

Normalization MUST NEVER downgrade a hard constraint to soft or upgrade a soft preference to hard.

## Unsupported constraints

Unknown or unsupported required constraints MUST fail explicitly. Never silently drop or coerce them.

Unknown optional extension fields may survive only through the existing WORK-003 extension semantics. Unknown required constraint data must yield a deterministic failure code.

Unsupported operators, incompatible units, ambiguous duplicates, and unsafe coercions must fail closed.

## Unit semantics

Reuse WORK-008's existing unit authority. Never create a second unit registry.

Equivalent units should normalize to an exact canonical base representation where the WORK-008 registry supports the conversion. Normative values MUST use exact integer/rational arithmetic; binary floating point, NaN, and Infinity are prohibited.

Examples:

```text
1000 kbps == 1 Mbps
1000 ms == 1 s
```

If safe normalization is impossible, fail explicitly rather than guessing.

## Locality

Locality is technology-neutral and MUST NOT become routing or topology state. It may represent a country, region, local domain/federation, or local-only preference.

Do not import GIS engines, routing engines, radio coverage logic, or vendor APIs into the intent core.

## Reliability

Reliability is a requested requirement/preference, not a prediction. Do not infer it from topology or measurements in WORK-009.

## Energy

Energy constraints describe budgets/preferences. They do not mutate WORK-008 EnergyState and do not perform admission decisions.

## Cost

Cost is a requested bound/preference only. WORK-009 MUST NOT implement pricing, settlement, billing, marketplace selection, tokens, or payment systems.

## Privacy

Privacy constraints record requirements, not enforcement. WORK-010 and later security/transport authorities determine whether/how they can be satisfied.

## Service constraints

Service constraints describe desired services without selecting an adapter. Reuse an existing registry identifier space when one exists; do not create a competing capability registry.

## Deterministic normalization

Normalization MUST be side-effect-free and canonical:

- same semantic input → byte-identical normalized output;
- map/constraint insertion order cannot change output;
- equivalent units normalize identically;
- canonical constraint ordering is stable;
- defaulting, if any, is explicit and deterministic;
- duplicate identifiers that create semantic ambiguity fail closed;
- canonical JSON uses WORK-003 machinery;
- any normalized digest/ID is content-derived and must not create a second identity authority.

No wall-clock reads inside normalization logic.

## Temporal semantics

Intents support validity/expiry using WORK-003 temporal primitives. Evaluation-dependent logic uses an injected instant. Normalization must not silently turn expiration into a routing/policy decision.

## Validation requirements

Reject at minimum:

- malformed NodeIDs;
- malformed/naive timestamps where timezone-aware values are required;
- negative/invalid quantities;
- incompatible units;
- unsupported operators;
- unsupported required dimensions;
- invalid hardness values;
- NaN/Infinity/floating-point normative values;
- duplicate constraints that create ambiguity;
- access-technology/vendor/routing/topology-specific core dimensions;
- secret/private-key material in serialized objects (LOCK-023).

## No policy/resource/routing leakage

Normalization outputs MUST NOT contain authoritative fields such as:

```text
authorized
trusted
admitted
selected_resource
selected_route
next_hop
adapter
access_technology
price
settlement
```

The normalization result answers only whether the intent is valid and what its canonical requirements are.

## Future-proofing

Future constraints and future access/profile identifiers must be addable through existing extension mechanisms. Do not special-case 5G or 6G. Unknown required future constraints fail explicitly; optional extension fields may survive per WORK-003.

## Suggested package structure

```text
intent/
  __init__.py
  model.py
  constraints.py
  normalization.py
  serialization.py
  validation.py
  README.md

tools/intent_selftest.py
```

Stdlib-only unless an already-frozen contract requires otherwise.

## Required adversarial verification

At least 25 deterministic cases covering:

1. minimal valid intent;
2. all eight dimensions;
3. hard vs soft constraints;
4. insertion-order-independent normalization;
5. equivalent unit normalization;
6. incompatible-unit rejection;
7. unsupported operator rejection;
8. unsupported required constraint rejection;
9. optional extension preservation;
10. duplicate constraint ambiguity rejection;
11. malformed requester NodeID rejection;
12. malformed/naive timestamp rejection;
13. validity/expiry behavior;
14. negative numeric rejection;
15. NaN/Infinity/float rejection;
16. deterministic digest/identity if implemented;
17. 5G/Wi-Fi/vendor implementation leakage rejection;
18. route/resource/trust/policy leakage audit;
19. secret-material serialization rejection;
20. future profile/constraint handling;
21. canonical byte identity across repeated runs;
22. fuzz/property inputs never crash;
23. hard constraints never silently downgraded;
24. soft constraints never silently upgraded;
25. normalization has no side effects on resource/topology state.

Add further cases where needed to prove the architecture locks.

## Integration requirements

Wire the new intent package and selftest into the existing deterministic governance/spec tooling and CI, following the established WORK-005..008 conventions.

Do not modify frozen authoritative documents. Do not modify existing schema registries unless the Architect explicitly authorizes such a change; reuse existing WORK-002/WORK-008 authorities.

Frozen documents and prior prompts through WORK-008 must remain byte-identical.

## Explicit out of scope

Do NOT implement policy evaluation (WORK-010), authorization/admission, trust scoring, resource selection, routing/path computation (WORK-011), sessions, mobility, federation decisions, adapter selection, 5G/Wi-Fi/LTE/6G/vendor integrations, pricing/settlement/billing, telemetry transport, or application-specific communication protocols.

## Definition of done

An application/operator can express a request such as:

```text
at least 10 Mbps
latency <= 50 ms
reliability >= 99.9%
end-to-end privacy
prefer local
energy budget <= 5 kJ
```

and receive either a deterministic canonical normalized intent or an explicit deterministic normalization failure, without specifying or selecting 5G, Wi-Fi, satellite, mesh, fiber, ShareNet bridging, or any other implementation mechanism.

## Architect review gate

The implementation PR must state exactly how intent remains separate from policy/resource/routing, how hard/soft constraints work, how WORK-008 units are reused, how unsupported required constraints fail, how canonicalization is deterministic, and prove no access technology leaked into core semantics.
