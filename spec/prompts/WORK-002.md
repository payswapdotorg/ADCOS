# ADCOS — Z.ai Implementation Handoff

## WORK-002 — Core protocol vocabulary and registry model

**Status:** READY FOR IMPLEMENTATION

**Architectural authority:** The four frozen documents in `spec/` remain authoritative. This prompt is an implementation handoff, not a new architectural specification.

**Base state:** WORK-001 has been explicitly accepted by the Architect. Start from the current `main` branch and implement exactly this Work Item.

---

## 1. Mission

Implement **WORK-002 — Core protocol vocabulary and registry model** exactly as defined in the frozen ADCOS architecture and backlog.

WORK-002 establishes the machine-readable vocabulary and registry layer for the frozen ADCOS domain objects and access profiles. It must make the architecture nouns mechanically representable without introducing runtime networking behavior.

The desired result is a small, explicit, versioned registry/schema foundation that WORK-003 can consume for the protocol envelope and serialization layer.

Frozen Work Item objective:

> Define stable IDs for Node, Adapter, Capability, Link, Path, Session, Resource, Intent, Evidence, Federation, and access profiles.

Frozen acceptance criteria:

- IDs are technology-neutral.
- registries support additive future entries.
- 5G and future IMT entries are adapter/profile IDs, not core domain types.
- unknown extension identifiers are handled safely.

Frozen definition of done:

> All frozen architecture nouns have versioned machine-readable definitions.

Required verification:

> schema tests, compatibility tests.

Out of scope:

> network behavior.

---

## 2. Read these authorities first

Before changing anything, read the current contents of:

1. `spec/architecture.md`
2. `spec/architecture-lock.md`
3. `spec/work-items.md`
4. `spec/dependency-graph.md`
5. `spec/governance.md`
6. `spec/workflow.md`
7. `spec/prompts/WORK-001.md`

The specific frozen architecture areas governing this Work Item include:

- §2 Design Principles, especially P1 Access agnosticism, P2 Generation neutrality, P3 Replaceability, P4 Capability negotiation, P5 Evidence over assertion, P7 No blockchain dependency, P10 Open implementation boundary, and P12 Protocol evolution without flag days.
- §4 System Model.
- §5 Protocol Planes.
- §6 Core Protocol Objects.
- §7 Stable Protocol Envelope, especially its versioning/extension rules.
- §8 Capability and Technology Registry.
- §9 Node Agent, only insofar as it consumes registry objects; do not implement Agent runtime behavior.
- §10 Adapter Architecture, especially the language-neutral Adapter boundary and future-IMT/generic adapter principles.

Relevant frozen text states that ADCOS core objects must not require a particular access technology, that generation must remain neutral, that unknown future capabilities must be safely ignored unless required by policy, and that access technologies are represented through stable technology/profile identifiers rather than hard-coded core state-machine branches.

The architecture explicitly lists core objects including Node, Identity, Adapter, Capability, Link, Path, Session, Resource, Intent, Federation, and Evidence. It also explicitly defines technology registry examples such as 5G NR, LTE, IEEE 802.11/802.3, satellite, microwave, Bluetooth, sidelink, and IAB, with future examples such as IMT-2030 and a generic future technology placeholder.

Do not rely on this prompt when it conflicts with a frozen document. Stop and report the conflict to the Architect.

---

## 3. Architectural intent for WORK-002

WORK-002 is the **machine-readable registry/schema foundation**, not the protocol wire format.

Establish:

```text
spec/schemas/
├── registries/
│   ├── domain-object-registry.json
│   ├── access-profile-registry.json
│   └── capability-registry.json
└── *.schema.json
```

The exact file decomposition may differ only where that improves conformance, maintainability, or deterministic validation without changing semantics. Do not create runtime modules to compensate for schema design.

The implementation must provide a canonical, deterministic mapping for the frozen nouns and identifiers while preserving the architecture's distinction between:

```text
CORE DOMAIN OBJECTS
    Node
    Identity
    Adapter
    Capability
    Link
    Path
    Session
    Resource
    Intent
    Federation
    Evidence

ACCESS / TECHNOLOGY PROFILES
    5G NR / IMT-2020
    LTE
    Wi-Fi / IEEE 802.11
    Ethernet / IEEE 802.3
    Satellite
    Microwave
    Bluetooth
    NR sidelink
    NR IAB
    future IMT / generic future technologies
```

Technology/profile identifiers MUST NOT become core domain-type identifiers.

---

## 4. Required model

### 4.1 Domain object registry

Create machine-readable definitions for every frozen noun listed below:

- Node
- Identity
- Adapter
- Capability
- Link
- Path
- Session
- Resource
- Intent
- Federation
- Evidence

Each definition must have a stable identifier and a schema/version reference.

The identifier namespace must be technology-neutral and stable across access generations. Do not embed `5g`, `6g`, vendor names, hardware brands, modem models, or implementation-language assumptions in core object IDs.

Do not silently add extra normative core nouns that are not frozen. Supporting metadata objects may exist where strictly necessary to express the schema, but they must not become a new protocol-authority category.

### 4.2 Access profile registry

Implement a separate access-profile/technology registry. Use stable identifiers equivalent in meaning to the frozen examples, including at minimum:

```text
access.3gpp.nr.imt2020
access.3gpp.lte.imtadvanced
access.ieee.80211
access.ieee.8023
access.satellite
access.microwave
access.bluetooth
access.3gpp.sidelink
access.3gpp.iab
```

Include future-proof entries/extension behavior consistent with the architecture, including an IMT-2030/future-generation profile path and a generic unknown-future technology path.

Do not interpret those examples as permission to hard-code a future 6G specification that is not frozen by ADCOS.

### 4.3 Capability registry

Create a registry mechanism for capability identifiers that supports:

- stable ID;
- schema/version reference;
- whether a capability is core or profile-scoped;
- additive future registration;
- safe handling of unknown identifiers.

Do not implement capability advertisement, signing, negotiation, provenance, or runtime handling here; those belong to later Work Items.

### 4.4 Version model

Every machine-readable schema/registry artifact must carry the version metadata required by WORK-001 governance and the frozen architecture.

Preserve the distinction between:

- Architecture Version;
- Protocol Version;
- Schema Version;
- Implementation Version.

Do not duplicate an Architecture Version declaration outside `spec/architecture.md` Status. References to the Architecture Version in prose are allowed; actual declaration fields belong only where governance permits.

WORK-002 owns schema/registry versions, not the full wire Protocol Version implementation. Do not implement the protocol envelope from WORK-003.

---

## 5. Extension and unknown-ID behavior

Unknown future registry identifiers are expected.

The schema/registry model MUST permit a conformant implementation to:

- parse the containing object without crashing merely because a referenced identifier is unknown;
- preserve or pass through unknown identifiers where the schema permits opaque extension/reference semantics;
- reject only where a consuming contract explicitly marks the identifier as required/understood;
- distinguish "unknown" from "invalidly formed";
- avoid silently mapping an unknown identifier to a known identifier.

Do not invent protocol runtime fallback semantics. This Work Item defines the machine-readable registry model and compatibility rules needed by later runtime Work Items.

---

## 6. Technology-neutrality and 5G/6G boundary

This rule is non-negotiable.

The core registry MUST remain valid if the network has:

```text
only Wi-Fi
only Ethernet
only 5G
5G + Wi-Fi
5G + satellite
future 6G/IMT-2030
6G + technologies not yet invented
```

A 5G profile is data in the access registry. A future 6G profile is data in the same registry. Neither is a new core domain type.

Do not create enums such as:

```text
Technology::FiveG
Technology::SixG
```

inside normative core domain models if doing so would make generation a closed set. Prefer stable registry identifiers and versioned profile metadata.

Do not import 3GPP/O-RAN/vendor SDKs, modem APIs, SDR APIs, or technology-specific libraries for WORK-002.

---

## 7. Scope boundary

### IN SCOPE

- machine-readable registry definitions;
- JSON Schema definitions or equivalent machine-readable schema artifacts consistent with the frozen repository conventions;
- stable ID namespaces;
- schema/registry version fields;
- cross-reference rules between domain objects, capabilities, and access profiles;
- additive extension model;
- unknown-ID compatibility semantics;
- deterministic validation tooling/tests for the above;
- documentation needed to explain the implemented registry model.

### OUT OF SCOPE

Do NOT implement:

- protocol envelope runtime or serialization engine from WORK-003;
- cryptographic identity from WORK-004;
- runtime capability statements/negotiation from WORK-005;
- discovery;
- topology;
- routing;
- sessions;
- mobility;
- resource allocation;
- policy engine;
- adapter runtime;
- 5G integration;
- Wi-Fi integration;
- SDR/modem integration;
- Android/Linux Agent runtime;
- networking daemons;
- database persistence layer unless strictly required for schema validation tooling;
- application/UI;
- blockchain/token logic.

If implementation of a later concern seems necessary, STOP and explain why rather than pulling it into WORK-002.

---

## 8. Compatibility requirements

WORK-002 must support additive evolution.

At minimum, test these cases:

1. A known registry entry validates successfully.
2. A new additive registry entry can be added without invalidating unrelated existing entries.
3. An unknown future identifier can be represented/encountered without corrupting known fields.
4. An unknown identifier is not silently coerced into another identifier.
5. A malformed identifier is rejected distinctly from a well-formed but unknown identifier.
6. A technology/profile addition does not require a change to the core domain object list.
7. A future IMT/6G-style access profile can be added without changing the core object schemas.
8. Version metadata is validated consistently across schema and registry artifacts.

Do not claim full wire compatibility in WORK-002; the actual envelope and canonical wire encoding are WORK-003.

---

## 9. Determinism and canonical repository behavior

Registry artifacts must be deterministic.

Requirements:

- stable ordering where ordering is semantically irrelevant;
- stable formatting;
- no generated timestamps;
- no machine-local absolute paths;
- no nondeterministic generated IDs;
- validation output is reproducible;
- schema references resolve deterministically.

Any generated artifact must be reproducible from repository inputs.

---

## 10. Validation tooling

Extend the existing WORK-001 specification tooling only where necessary to validate WORK-002.

Do not weaken or remove existing checks.

Existing governance checks and the negative self-test suite must continue to pass.

Add focused schema/registry validation tests, preferably with zero third-party runtime dependencies unless the repository's current state already establishes an appropriate dependency. Do not add a heavy framework merely for convenience.

The new tests should exercise both valid and invalid fixtures and must include future/unknown-ID compatibility behavior.

---

## 11. Frozen dependency anomalies — DO NOT resolve here

The current frozen documents contain three already-known dependency declaration deltas surfaced by WORK-001 tooling:

- WORK-008 → WORK-007
- WORK-014 → WORK-017
- WORK-021 → WORK-019

These remain an Architect-owned specification issue.

**Do not modify `spec/work-items.md` or `spec/dependency-graph.md` to resolve them.**

If your implementation process encounters one of these inconsistencies, mention it in the PR as an existing known specification advisory and continue only within WORK-002's actual dependency boundary.

---

## 12. Frozen-document protection

Do not modify:

```text
spec/architecture.md
spec/architecture-lock.md
spec/work-items.md
spec/dependency-graph.md
```

Do not modify `spec/prompts/WORK-001.md`.

If a frozen document appears to require modification, STOP and report the exact conflict to the Architect. Do not reinterpret the architecture to make the implementation fit.

---

## 13. Required deliverables

The PR must include, as appropriate:

1. machine-readable domain-object schemas/registry;
2. machine-readable access-profile registry;
3. machine-readable capability registry/model;
4. schema/registry validation tests;
5. compatibility tests covering additive and unknown-ID behavior;
6. documentation for registry structure and extension rules;
7. any minimal validation tooling required to make these contracts deterministic and CI-verifiable.

Every added artifact must have a clear reason tied directly to WORK-002.

---

## 14. Required PR structure

Use the repository PR template exactly.

The PR body must include:

- `WORK-002` and title;
- objective;
- exact frozen architecture sections implemented;
- dependencies and confirmation that WORK-001 is Architect-accepted;
- acceptance criterion → evidence mapping;
- exact commands and results for all tests/checks;
- static analysis/type checking for introduced code;
- files changed;
- explicit out-of-scope statement;
- architecture-lock compliance;
- no-architecture-drift statement;
- known limitations.

State explicitly that WORK-002 does not implement runtime networking.

Do not merge the PR yourself.

---

## 15. Required verification before requesting Architect review

Run and report at minimum:

```bash
python3 tools/spec_check.py
python3 tools/spec_check_selftest.py
```

Then run the complete WORK-002 validation suite.

If schema validation tooling is language-native and already available, use it. Otherwise, implement a small deterministic validator/test harness rather than introducing an unnecessary external stack.

Also run static analysis/type checking for every new programmatic artifact.

Verify deterministic output where applicable by repeating deterministic checks and confirming byte-identical results.

Verify the four frozen documents and `spec/prompts/WORK-001.md` are byte-identical to `main`.

Verify no new 5G/6G/vendor-specific runtime dependency has been added.

---

## 16. Definition of done — Architect review standard

WORK-002 is not complete because tests pass.

The Architect will accept it only when all of the following are true:

- every frozen architecture noun has a stable machine-readable definition;
- core IDs are technology/generation neutral;
- access technologies are modeled through registries/profiles, not core domain types;
- 5G and future IMT/6G remain replaceable adapters/profiles;
- additive registry evolution works;
- unknown identifiers are handled safely and deterministically;
- schema/registry versions are explicit and compatible with WORK-001 governance;
- no later Work Item's runtime behavior has leaked into WORK-002;
- no frozen document changed;
- no dependency anomaly was silently "fixed";
- validation is deterministic and CI-verifiable;
- the PR contains complete evidence and an accurate scope statement.

The Architect will inspect the full diff, not merely CI results.

---

## 17. Stop conditions

STOP and report to the Architect immediately if any of these occur:

- a frozen rule appears ambiguous or contradictory;
- implementation seems to require a new core noun not covered by the frozen architecture;
- a technology-specific concept appears necessary in the core model;
- a 5G/6G-specific field would make a core object non-generation-neutral;
- a later Work Item must be implemented to make WORK-002 function;
- the dependency graph appears to require modification;
- a schema change would alter frozen protocol semantics rather than merely encode them;
- a compatibility requirement cannot be satisfied without an architectural change;
- a third-party dependency is needed solely for convenience but changes the repository boundary materially.

Do not solve architectural uncertainty by making an implementation assumption.

---

## 18. Final instruction

Implement **only WORK-002**.

Treat the frozen architecture as the contract, not as suggestions.

Prefer the smallest implementation that completely establishes the machine-readable vocabulary/registry foundation required by the architecture.

Make future generations possible by keeping the core stable and the access/profile registry extensible.

Submit one PR for WORK-002 and leave it open for Architect review.