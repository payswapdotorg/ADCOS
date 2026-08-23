# ADCOS — Z.ai Implementation Handoff

## WORK-004 — Cryptographic node identity and credential abstraction

**Status:** READY FOR IMPLEMENTATION

**Architectural authority:** The four frozen documents in `spec/` remain authoritative. This prompt is an implementation handoff, not a new architectural specification.

**Base state:** WORK-001, WORK-002, and WORK-003 have been Architect-accepted. Start from the current `main` branch and implement exactly this Work Item.

---

## 1. Mission

Implement **WORK-004 — Cryptographic node identity and credential abstraction** exactly as defined by the frozen ADCOS architecture, architecture lock, backlog, and accepted prior Work Items.

WORK-004 establishes durable, access-independent cryptographic node identity and the abstraction around credential references, lifecycle, rotation, revocation, and algorithm agility. It must create the identity boundary that later trust, capability, discovery, federation, adapter, and session Work Items consume.

Frozen Work Item objective:

> Implement access-independent NodeID, key lifecycle, credential references, rotation, revocation, and algorithm agility.

Frozen acceptance criteria:

- NodeID survives adapter changes.
- key rotation works without changing NodeID semantics.
- algorithms are negotiated/profiled.
- credential material is never serialized as ordinary topology data.

Required verification:

> security tests, rotation tests, negative tests.

Out of scope:

> federation policy.

Definition of done:

> Nodes have durable cryptographic identity independent of 5G/Wi-Fi/etc.

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
8. `spec/prompts/WORK-002.md`
9. `spec/prompts/WORK-003.md`
10. `spec/schemas/identity.schema.json`
11. `spec/schemas/node.schema.json`
12. `spec/schemas/protocol.json`

Relevant frozen architecture areas include:

- §2 P1–P6 and P10–P12: access neutrality, generation neutrality, replaceability, capability negotiation, evidence, least authority, open implementation boundary, observability, and evolution.
- §5.1 Identity & Trust Plane.
- §6.1 Node.
- §6.2 Identity.
- §6.3 Adapter, especially the adapter boundary.
- §7 Stable Protocol Envelope and protocol versioning.
- §8 Capability and Technology Registry.
- §10 Adapter Architecture.
- §21 Federation, only insofar as identity must be usable across administrative domains without implementing federation policy.
- §22 Security Architecture.
- §23 Trust, Evidence, and Provenance.
- §25 Future-Proofing Rules.

Relevant architecture locks include **LOCK-001, 003, 005, 006, 007, 015, 016, 017, 018, 022, 023, 024, and 025**, plus the module ownership and import/dependency rules.

---

## 3. Frozen identity semantics you must preserve

The frozen architecture says:

- Identity is an **asymmetric-key-backed identity independent of access technology**.
- A stable **NodeID** is derived from a public-key identity or registered equivalent.
- Node identity, operator authority, and user identity are separate where needed.
- Rotation is supported.
- Revocation is supported.
- A node does not need a SIM.
- A node may also possess 3GPP credentials.
- Node identity survives a transition between 5G, Wi-Fi, satellite, Ethernet, mesh, future IMT, or any other access adapter.
- Credentials/private keys/secrets are not ordinary topology or resource metadata.
- Cryptographic algorithms are negotiated/profiled; algorithm identifiers are not hard-coded into core semantics.
- The network is zero-trust. Possessing an identity is not itself authorization or trust.
- External provider/vendor/modem credentials remain behind adapters/providers and are not promoted into ADCOS identity semantics.

Do not reinterpret these rules for convenience.

---

## 4. Required architecture boundary

The implementation MUST create a clear separation between these concepts:

```text
NodeID
  = durable identity reference

Key material
  = cryptographic signing/authentication material, never ordinary topology data

Credential reference
  = opaque reference to credential material or credential record

Credential metadata
  = algorithm/profile, validity, status, provenance, key version, etc.

Trust / authorization
  = policy and evidence consumed later; NOT decided by identity itself

Adapter credentials
  = access/vendor-specific credentials behind adapter/provider boundaries
```

In particular:

```text
NodeID != public key bytes
NodeID != certificate blob
NodeID != private key
NodeID != SIM/IMSI
NodeID != modem identifier
NodeID != MAC address
NodeID != vendor account ID
NodeID != trust decision
```

The chosen NodeID derivation scheme must be deterministic and stable under key rotation. If the architecture permits more than one derivation mechanism, encode the mechanism/profile as explicit metadata rather than making callers infer it.

A key rotation MUST NOT silently generate a new NodeID for the same logical node identity. Re-keying a node is not the same operation as creating a new node identity.

---

## 5. Scope of implementation

Implement the identity module according to the frozen module ownership rule:

```text
/identity
    owns node identity and credential references
```

The implementation should expose a small, stable API around:

- identity creation;
- NodeID derivation;
- public identity representation;
- key-version management;
- key rotation;
- credential reference creation/resolution abstraction;
- credential lifecycle state;
- revocation state;
- algorithm/profile negotiation metadata;
- serialization-safe public metadata;
- secure separation of secret material from ordinary topology objects.

The implementation language remains consistent with the repository's current reference choice unless there is an existing repository convention that requires otherwise.

Do not implement later trust/federation behavior merely because identity data can represent it.

---

## 6. NodeID requirements

Define and test a stable NodeID representation with all of these properties:

1. **Access independent.** It must contain no 5G cell/gNB/bearer, Wi-Fi BSSID, satellite terminal, Ethernet, SDR, SIM, modem, or vendor semantics.
2. **Deterministic.** Reconstructing the same identity under the same identity profile produces the same NodeID.
3. **Stable across key rotation.** Rotating the active credential/key does not change NodeID.
4. **Collision resistant under the selected derivation profile.** Document the cryptographic construction and domain separation.
5. **Algorithm/profile explicit.** Any cryptographic/profile choices are represented by stable identifiers and are not hidden in implementation conventions.
6. **Canonical serialization.** A NodeID has one canonical wire/text representation and round-trips without ambiguity.
7. **Non-secret.** A NodeID can safely appear in ordinary protocol/topology messages.
8. **Future-proof.** The representation must allow algorithm/profile migration without forcing a future rewrite of all identity-consuming protocol objects.

Do not make a NodeID from a mutable key directly if that would violate rotation stability. If a stable public identity key is retained separately from rotating operational keys, make that distinction explicit and document its security boundary.

---

## 7. Key lifecycle

Implement explicit lifecycle states and transitions for operational credential/key records. At minimum, distinguish:

```text
PROVISIONED
ACTIVE
ROTATING
SUPERSEDED
REVOKED
EXPIRED
```

Use only the states necessary to make the lifecycle explicit; do not invent unrelated trust states owned elsewhere.

Required properties:

- only an appropriate active key/profile can be selected for new signing/authentication operations;
- superseded keys remain identifiable for historical verification/reference where policy permits;
- revoked keys cannot be selected as active credentials;
- lifecycle transitions are deterministic and invalid transitions fail closed;
- expiry and revocation are distinct concepts;
- key rotation is atomic from the logical identity's perspective;
- a failed rotation leaves the previous valid identity operational rather than creating ambiguous half-state.

No key bytes should appear in normal topology objects, JSON schemas, logs, fixtures, or test output.

---

## 8. Credential references

The identity layer must use **opaque credential references** rather than embedding secret material.

A credential reference should be sufficient for later components to identify/select credential material without revealing that material.

At minimum model metadata needed for:

- reference ID;
- NodeID association;
- credential/key role;
- algorithm/profile ID;
- lifecycle status;
- creation/activation/expiry timestamps where applicable;
- revocation state/reference;
- provenance/source classification;
- version/key generation number.

Do not add certificate chains, private key blobs, seed phrases, SIM secrets, API tokens, or vendor secrets to ordinary ADCOS protocol objects.

A credential-store interface may be defined so implementations can use:

```text
OS keystore
TPM
HSM
secure enclave
file-backed development store
external secret manager
```

but the core identity API must not depend on one provider.

---

## 9. Algorithm agility and profiles

Algorithm selection must be profile-driven.

The identity layer should represent something equivalent to:

```text
IdentityProfile
 ├── profile_id
 ├── NodeID derivation rule
 ├── key roles
 ├── supported algorithms
 ├── signature/authentication profile
 └── version
```

Requirements:

- algorithms are referenced by stable identifiers;
- negotiation occurs from explicit supported/allowed profiles rather than hard-coded branching on a single algorithm;
- unknown algorithms fail safely unless an explicit extension mechanism says they may be ignored/preserved;
- the identity layer does not assert that an algorithm is trusted merely because it is syntactically valid;
- cryptographic provider implementations are replaceable.

Do not freeze the project to one vendor library or one national cryptography regime.

Use standard cryptographic primitives where the reference implementation needs actual cryptographic operations. Do not invent a new cryptographic algorithm.

---

## 10. Revocation

Implement a local credential revocation abstraction, not the entire federation trust system.

Required behavior:

- a credential can be marked revoked;
- revoked credentials cannot be newly activated/selected;
- revocation metadata is distinguishable from expiration;
- revocation state can be serialized as non-secret metadata/reference;
- identity itself remains stable when one credential is revoked, unless the explicit identity-destruction semantics are invoked;
- callers can query revocation state without receiving secret material.

Do not implement network-wide revocation distribution, federation trust policy, reputation, or authorization policy. Those belong to later Work Items.

---

## 11. Security invariants

The implementation MUST fail closed for:

- malformed NodeIDs;
- unsupported identity profiles;
- unsupported cryptographic algorithms;
- duplicate credential references;
- invalid lifecycle transitions;
- revoked credential activation;
- expired credential activation where expiry is enforced;
- mismatched NodeID/identity material;
- secret material passed through public serialization APIs;
- ambiguous identity/profile combinations;
- malformed serialized credential metadata.

Tests MUST demonstrate that secret bytes do not appear in:

- Node objects;
- protocol envelopes;
- topology/resource dictionaries;
- ordinary structured logs;
- exception messages;
- debugging representations.

Do not print or commit real secrets, private keys, seed material, or long-lived test credentials.

Use generated ephemeral test material where actual cryptographic operations are required.

---

## 12. Serialization and interaction with WORK-003

Consume the accepted WORK-003 envelope and serialization APIs where identity-related metadata is serialized.

Do not fork a second serialization system.

Identity-related protocol objects should use stable references and metadata that can travel through the existing envelope without embedding secret material.

The identity module must not require a specific access adapter to serialize/deserialize NodeID or public identity metadata.

Unknown future identity/profile identifiers must not be coerced into known algorithms or profiles.

---

## 13. Testing requirements

Add deterministic tests covering at minimum:

### Identity construction

- create an identity;
- derive NodeID;
- serialize public identity metadata;
- deserialize and reproduce the same NodeID;
- reject malformed identity input.

### Rotation

- create NodeID with key generation 1;
- rotate to key generation 2;
- verify NodeID is unchanged;
- verify generation 1 becomes superseded according to policy;
- verify generation 2 becomes active;
- verify failed rotation leaves generation 1 active.

### Revocation

- revoke an active credential;
- verify it cannot become active again;
- verify identity/NodeID remains stable;
- distinguish revoked from expired.

### Algorithm agility

- negotiate a mutually supported profile;
- select deterministically;
- reject unsupported profiles;
- preserve unknown profile identifiers without coercion;
- prove no core code assumes one fixed algorithm.

### Secret isolation

- public serialization contains NodeID and public metadata only;
- private/secret material is absent from topology-like objects;
- logs/error strings do not contain secrets;
- attempting to serialize a secret-bearing object through the public API fails or redacts by explicit design.

### Negative/security tests

Include malformed, revoked, expired, duplicate, mismatched, unsupported, and illegal-transition cases.

Tests should use property-based or fuzz-style mutation where useful, especially around serialized identity metadata and lifecycle transitions.

---

## 14. Compatibility and future-proofing requirements

The implementation must demonstrate:

1. replacing 5G with Wi-Fi does not alter NodeID;
2. replacing Wi-Fi with future IMT does not alter NodeID;
3. rotating operational keys does not alter NodeID;
4. adding a future identity profile does not require changing the NodeID consumer API;
5. removing/revoking an operational credential does not destroy the logical identity object;
6. unknown future profile IDs are not reinterpreted as known profiles.

A committed compatibility test should exercise at least one hypothetical future profile identifier such as:

```text
identity.future.example-v1
```

without adding it to the frozen architecture or treating it as normative.

---

## 15. Required artifacts

Expected repository changes are approximately:

```text
identity/
  __init__.py
  model.py
  node_id.py
  profiles.py
  credentials.py
  lifecycle.py
  revocation.py
  store.py          # interface / provider abstraction only
  serialization.py  # public metadata only, using existing protocol facilities

tools/
  identity_selftest.py

spec/schemas/
  identity-profile.schema.json       # only if needed to make the profile contract machine-readable
  credential-reference.schema.json   # only if needed; do not duplicate WORK-002 identity schema
```

These are illustrative boundaries, not permission to create unnecessary modules. Prefer the smallest coherent implementation.

Do not create a second `Node` or `Identity` schema that conflicts with WORK-002. Extend the machine-readable model only through additive artifacts or the existing schemas where the frozen architecture and governance allow it.

If a schema change appears to alter WORK-002's accepted contract or the frozen architecture, STOP and report the conflict rather than silently changing it.

---

## 16. Explicitly out of scope

Do NOT implement:

- trust policy;
- authorization policy;
- federation trust/peering;
- reputation;
- topology/discovery;
- capability advertisement/negotiation;
- session/mobility;
- access adapters;
- 5G/6G integration;
- modem APIs;
- SIM/USIM management;
- Android/iOS integration;
- routing;
- distributed revocation propagation;
- blockchain/token economics;
- application/UI;
- persistent database infrastructure;
- hardware-specific secure enclaves;
- custom cryptographic algorithms.

Provider integrations may be represented as interfaces/mocks but must not leak provider semantics into the identity contract.

---

## 17. Forbidden architectural shortcuts

Do not:

- derive NodeID directly from a rotating operational public key if that makes rotation change NodeID;
- use a MAC address, modem identifier, SIM/IMSI, IP address, certificate serial number, filesystem path, or vendor account as NodeID;
- put private keys or shared secrets into JSON/schema/topology objects;
- make authorization equivalent to possession of a valid NodeID;
- hard-code a single signature algorithm as the only supported profile;
- hard-code a single keystore/HSM/vendor API into core identity code;
- make identity dependent on 5G, Wi-Fi, LTE, satellite, Ethernet, or future IMT;
- let adapters directly mutate core identity state without going through the identity contract;
- silently reinterpret unknown algorithm/profile identifiers;
- add federation or trust policy under the guise of revocation.

---

## 18. Verification and PR requirements

Before submitting the PR:

1. Run the complete existing verification suite.
2. Run the new identity-specific test suite.
3. Run `py_compile` and the repository's static/type checks for introduced code.
4. Run deterministic repeat checks where tooling supports them.
5. Verify no private key/secret material appears in repository output, fixtures, logs, diffs, or generated artifacts.
6. Verify the four frozen documents and all prior accepted prompts are unchanged.
7. Verify the known dependency advisories remain untouched.
8. Report exact commands and results in the PR body.

The PR must contain all required sections from `.github/PULL_REQUEST_TEMPLATE.md`.

The PR is not complete because tests pass. Architect acceptance requires conformance to this handoff, `spec/work-items.md`, `spec/architecture.md`, and `spec/architecture-lock.md`.

---

## 19. Stop conditions

STOP and report the exact conflict instead of improvising if any of these occur:

- stable NodeID cannot be implemented without violating the frozen identity semantics;
- a requested crypto/profile choice would have to become a new architecture rule;
- existing WORK-002 or WORK-003 schemas are insufficient in a way that requires changing their accepted semantics;
- secret material would need to cross a public protocol boundary;
- an implementation requires vendor/modem/5G-specific state in core identity code;
- revocation requires federation policy not defined by WORK-004;
- the implementation would require changing any frozen document;
- a dependency inconsistency requires modifying `spec/work-items.md` or `spec/dependency-graph.md`.

In any stop condition, do not reinterpret, simplify, or extend the architecture. Leave frozen documents untouched and return the exact conflict plus the smallest evidence needed for Architect resolution.

---

## 20. Definition of done

WORK-004 is complete only when:

- a durable NodeID exists and is demonstrably independent of access technology;
- operational key rotation leaves NodeID unchanged;
- credential references and lifecycle are explicit;
- revocation is represented and fails closed locally;
- algorithms/profiles are explicit and replaceable;
- secret material cannot enter ordinary topology/protocol metadata;
- the implementation uses the accepted WORK-003 serialization boundary;
- security/rotation/negative tests are deterministic and green;
- no trust/federation/access-provider behavior leaked into identity;
- frozen documents are untouched;
- the Architect accepts the PR.

**Do not merge the PR yourself.**

**Do not proceed to WORK-005 until the Architect explicitly accepts WORK-004.**
