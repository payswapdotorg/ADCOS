# ADCOS Architect Handoff — WORK-005

## Status

**ACTIVE — Architect implementation handoff**

This prompt authorizes Z.ai to implement exactly WORK-005 from the frozen ADCOS architecture. The authoritative sources are, in order: `spec/architecture.md`, `spec/architecture-lock.md`, `spec/work-items.md`, `spec/dependency-graph.md`, and the accepted implementations already merged to `main` for WORK-001 through WORK-004.

Do not modify any frozen architecture document, architecture lock, work-item, dependency graph, or prior Work Item prompt.

## Work Item

**WORK-005 — Capability statements and negotiation**

Dependencies: WORK-003, WORK-004. Both are Architect-accepted and merged.

Objective: implement signed, versioned capability advertisements, machine-readable capability statement schemas, parameter/constraint handling, validity periods, evidence references, withdrawal/expiry, deterministic negotiation, and safe unknown-optional capability handling.

## Architectural intent

ADCOS Capability is a **claim about what a Node or Adapter may provide**, not proof that the capability currently exists and not a topology fact.

Frozen §6.4 requires every Capability to contain:

- capability ID;
- schema version;
- provider identity;
- validity interval;
- parameters;
- constraints;
- evidence references;
- signature.

Frozen P4/P5/P11/P12 and LOCK-007/008/014/015/022/024 apply throughout.

Capability statements must therefore remain:

```text
technology-neutral
versioned
signed
provenance-linked
validity-bounded
open-world
negotiable
non-authoritative until appropriate evidence/policy exists
```

A capability advertisement must never become authoritative merely because it is signed, relayed, repeated, or accepted by a peer. Signature establishes provenance/authenticity of the statement; it does not establish truth, availability, authorization, or trust.

## Scope

Implement only the capability domain and negotiation boundary.

### In scope

1. Machine-readable capability statement schema(s).
2. Capability identifier consumption from the accepted WORK-002 capability registry. Do not create a second vocabulary authority.
3. Capability statement model.
4. Schema-version handling.
5. Provider identity reference using the accepted WORK-004 NodeID/identity model.
6. Valid-from / expires-at validation using the accepted WORK-003 temporal primitives.
7. Parameters and constraints as open-world typed data.
8. Evidence references using the accepted WORK-002 evidence model; evidence remains references/claims, not topology authority.
9. Signature metadata / signing integration through the accepted WORK-004 provider abstraction and WORK-003 canonical signing-input machinery.
10. Withdrawal/revocation/expiry representation for capability statements.
11. Deterministic compatibility classification for capability/profile versions.
12. Deterministic negotiation of mutually supported capabilities/profiles.
13. Explicit required-vs-optional negotiation semantics.
14. Safe handling of unknown optional capability identifiers.
15. Safe rejection of unknown required capabilities when a request explicitly requires them.
16. Golden/compatibility/adversarial tests and deterministic self-tests.
17. Tooling/CI integration needed to make the above mechanically verifiable.
18. Documentation of the capability package boundaries.

### Out of scope — forbidden

Do NOT implement:

- peer discovery (WORK-006);
- topology graph or topology authority (WORK-007);
- resource measurement/accounting (WORK-008);
- intent normalization/QoS engine (WORK-009);
- policy engine / authorization policy (WORK-010);
- routing/path computation (WORK-011);
- session/mobility (WORK-012+);
- generic Adapter runtime (WORK-016);
- 5G/Wi-Fi/6G adapters;
- RAN/core integration;
- federation policy;
- persistent databases;
- distributed revocation propagation;
- reputation systems;
- blockchain/token logic;
- UI/application logic.

Do not invent a capability implementation API that requires the adapter framework. WORK-005 defines the **capability contract and negotiation semantics**; actual adapter lifecycle integration belongs later.

## Non-negotiable architecture rules

### 1. No technology-specific core branching
The capability system must never use closed enums or branches such as:

```text
if capability == 5G
if capability == wifi
if capability == 6G
```

Access technologies remain registry/profile data. Future IMT-2030 and later capabilities must flow through the same core capability machinery.

### 2. No second vocabulary authority
`spec/schemas/registries/capability-registry.json` from WORK-002 is the canonical capability identifier authority.

The implementation may validate against it, load it, and extend it only through ordinary future registry governance. Do not duplicate IDs in Python/Rust code or another JSON/YAML enum.

### 3. Identity and signature boundaries
Use WORK-004 identity abstractions.

Do not embed private keys or secrets in capability objects.

Do not reinterpret possession of a valid identity as trust.

Do not introduce a new cryptographic provider or algorithm registry.

### 4. Evidence is not truth
A capability statement can contain:

```text
provider = Node A
evidence = [claim/observation references]
```

but a capability reported by Node B about Node C must remain a claim by B. WORK-005 must not add code that upgrades remote summaries into authoritative facts.

### 5. Open-world evolution
Unknown capability IDs are classified, not silently coerced.

At minimum distinguish:

```text
KNOWN
UNKNOWN_BUT_WELL_FORMED
INVALID
```

Unknown optional capabilities may be ignored/preserved.
Unknown required capabilities cause explicit negotiation failure.
Malformed IDs fail closed.

### 6. Version compatibility
Capability schema/profile versions must be explicit.

Do not invent a second incompatible versioning system. Reuse the accepted WORK-003 protocol/schema version semantics where applicable.

Additive compatible profile evolution must be distinguishable from incompatible changes.

### 7. Validity
Capability statements must carry a validity interval and be rejected for processing when structurally malformed or outside the declared validity policy.

Do not conflate:

```text
capability expired
capability withdrawn
node identity revoked
provider untrusted
```

These are distinct concepts; later policy/trust work decides what a peer may do with them.

### 8. Negotiation is deterministic
Given identical local/remote inputs and policy-independent negotiation parameters, the result must be deterministic.

Do not rely on hash-map iteration order, wall-clock time, random choices, locale-sensitive ordering, or provider implementation order.

### 9. Negotiation is not policy
Negotiation answers:

> What mutually understood capability/profile can both parties support?

It does not answer:

> Is this peer authorized or trusted to use it?

That belongs to WORK-010 and later trust/federation mechanisms.

## Required implementation shape

Recommended boundary:

```text
capabilities/
├── model.py
├── registry.py
├── classification.py
├── validity.py
├── negotiation.py
├── signing.py
├── serialization.py
└── README.md
```

Names may differ only when there is a clear architectural reason.

Suggested machine-readable artifacts:

```text
spec/schemas/capability.schema.json
spec/schemas/negotiation.schema.json
```

Do not add redundant registry files unless required by the frozen architecture.

## Capability model

The public model should represent at least:

```text
CapabilityStatement
  capability_id
  schema_version
  provider_id
  valid_from
  expires_at
  parameters
  constraints
  evidence_refs
  signature
  withdrawal_state / withdrawn_at where required by the design
```

The exact field names may follow the frozen §6.4 semantics and existing repository conventions, but do not add unrelated concepts such as trust score, routing score, topology state, resource measurement, or policy decision.

## Capability identifiers

Consume the accepted WORK-002 registry.

The seed registry currently contains the frozen core capability examples, including capability concepts for multipath, local breakout, and store-and-forward. Treat those identifiers as data. Future identifiers must be loadable without changing core code.

Do not hard-code the seed set into tests as the only legal vocabulary. Tests should include a future well-formed capability identifier and prove it can be represented safely.

## Parameters and constraints

Parameters and constraints are open-world data.

They must not be tied to 5G terminology.

Good examples:

```json
{
  "bandwidth_mbps": 100,
  "latency_ms": 25
}
```

or a future profile-specific structure loaded by capability/schema version.

Negotiation must compare only semantics defined for the capability/profile. Unsupported or unknown constraints must fail explicitly when they are required rather than silently being treated as satisfied.

## Evidence references

Evidence references must be opaque identifiers/references at this layer.

WORK-005 does not implement evidence collection, topology observation, telemetry, or evidentiary trust weighting.

Do not infer:

```text
signed capability => true
```

Only:

```text
signed capability => attributable statement
```

## Signing

Use the accepted WORK-003 canonicalization/signature-input machinery and WORK-004 provider abstraction.

The capability signature MUST cover the canonical capability content that is security-critical, including the provider identity, capability ID, schema version, validity interval, parameters, constraints, evidence references, and withdrawal state where present.

Do not sign mutable/non-semantic formatting.

Do not invent a cryptographic algorithm identifier.

Do not serialize private key material.

## Withdrawal / expiry

Implement a capability lifecycle sufficient to distinguish at least:

```text
ACTIVE
WITHDRAWN
EXPIRED
```

Malformed or impossible transitions fail closed.

A withdrawn capability must not negotiate as currently usable.
An expired capability must not negotiate as currently usable.
Historical statements may remain queryable for audit/provenance purposes.

Do not implement distributed revocation propagation here.

## Negotiation

Implement a deterministic negotiation function over local and peer capability offers/preferences.

It should support:

```text
common capability ID
compatible schema/profile versions
required vs optional requirements
parameter compatibility
constraint compatibility
```

The result should explicitly identify:

```text
selected capability/profile
why candidates were rejected
whether failure was due to unknown required capability,
version incompatibility, constraint mismatch, or absence of a common profile
```

Do not introduce cost, trust, reputation, routing, or resource scoring. Those belong to later layers.

When multiple compatible candidates exist, use a deterministic ordering defined by the protocol data model rather than implementation order.

## Required tests

At minimum implement deterministic tests covering:

1. canonical capability construction;
2. capability schema validation;
3. signature generation/verification through the existing provider seam;
4. tampered parameter rejection;
5. tampered provider identity rejection;
6. tampered evidence reference rejection;
7. expiry rejection;
8. withdrawal rejection;
9. unknown optional capability preserved/ignored safely;
10. unknown required capability causes explicit failure;
11. malformed capability ID rejected;
12. future well-formed capability ID preserved without core modification;
13. compatible schema/profile negotiation succeeds;
14. incompatible version negotiation fails deterministically;
15. parameter mismatch fails deterministically;
16. constraint mismatch fails deterministically;
17. deterministic tie-breaking when multiple candidates are compatible;
18. negotiation does not grant trust/authorization;
19. remote evidence references remain references and are not upgraded to authority;
20. fuzzed/mutated capability inputs fail safely and never crash.

Also test round-trip preservation through the accepted WORK-003 JSON and provisional compact codec where applicable.

## Required verification

Run all prior suites plus the new capability suite.

Expected:

```text
spec_check.py
spec_check_selftest.py
schema_check.py
schema_selftest.py
envelope_selftest.py
identity_selftest.py
capability_selftest.py
```

All must be deterministic across repeated runs.

Run static compilation/type checking on all affected modules.

Prove:

- frozen documents unchanged;
- previous accepted prompts unchanged;
- no capability vocabulary duplicated in source code;
- no vendor/5G/6G/RAN SDK imports;
- no secrets/private keys in capability fixtures;
- no third-party dependency added unless explicitly justified and architect-authorized (default is stdlib-only for this stage);
- CI runs the new capability suite.

## PR requirements

The PR body MUST contain exactly the repository's established Work Item sections and map every acceptance criterion to evidence.

Include:

1. WORK-005 objective;
2. exact architecture sections implemented;
3. dependencies satisfied;
4. acceptance-criteria → evidence table;
5. verification commands/results;
6. files changed;
7. out-of-scope statement;
8. architecture-lock compliance;
9. no-architecture-drift statement;
10. known limitations / deliberate boundary decisions;
11. explicit statement that no frozen documents were modified.

Leave the PR open for Architect review. Do not merge it.

## Stop conditions

Stop and report rather than modifying frozen architecture if any of these become necessary:

- adding a new core domain primitive not present in §6;
- modifying the capability vocabulary beyond ordinary registry extension;
- changing envelope semantics;
- changing identity semantics;
- adding trust/policy authority;
- changing any dependency edge;
- introducing a technology-specific core branch;
- changing any LOCK-001…LOCK-025 rule;
- changing production canonicalization semantics;
- requiring a vendor SDK or access-specific runtime to implement the capability core.

## Architect acceptance standard

Green CI is necessary but insufficient.

Acceptance requires the Architect to confirm that the implementation:

- exactly implements WORK-005;
- respects all frozen locks;
- keeps claims/evidence/provenance distinct from authority;
- keeps identity, capability, trust, resource, routing, and adapter concerns separated;
- remains generation-neutral and future-proof;
- has no hidden second source of truth;
- is deterministic and fail-closed;
- introduces no architecture drift.
