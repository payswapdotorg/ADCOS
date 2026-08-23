# ADCOS — Z.ai Implementation Handoff

## WORK-003 — Versioned protocol envelope and serialization

**Status:** READY FOR IMPLEMENTATION

**Architectural authority:** The four frozen documents in `spec/` remain authoritative. This prompt is an implementation handoff, not a new architectural specification.

**Base state:** WORK-001 and WORK-002 have been Architect-accepted. Start from the accepted WORK-002 state and implement exactly this Work Item.

---

## 1. Mission

Implement **WORK-003 — Versioned protocol envelope and serialization** exactly as defined by the frozen ADCOS architecture, architecture lock, and Work Item backlog.

WORK-003 establishes the stable wire-message envelope and the implementation-independent serialization/versioning primitives that later Work Items will consume. It must make protocol evolution possible without a flag day while preserving unknown fields/extensions where the architecture requires it.

Frozen Work Item objective:

> Implement the stable envelope, schema versioning, canonicalization, extension handling, expiration, correlation, and signature metadata.

Frozen acceptance criteria:

- known messages parse deterministically;
- unknown optional fields survive proxying where possible;
- incompatible versions fail safely;
- replay/expiration metadata is validated.

Required verification:

> golden vectors, fuzz/property tests, compatibility tests.

Out of scope:

> trust policy and routing.

Frozen definition of done:

> The wire contract can evolve without a flag day.

---

## 2. Authorities you MUST read before coding

Read the current accepted repository state, not a remembered or copied version:

1. `spec/architecture.md`
2. `spec/architecture-lock.md`
3. `spec/work-items.md`
4. `spec/dependency-graph.md`
5. `spec/governance.md`
6. `spec/change-control.md`
7. `spec/workflow.md`
8. `spec/schemas/README.md`
9. `spec/prompts/WORK-002.md`

The most important frozen material for WORK-003 is:

- architecture §2 P1–P12, especially P2, P3, P4, P11, P12;
- architecture §7 Stable Protocol Envelope;
- architecture §8 Capability and Technology Registry;
- architecture §15–§16 where versioned messages may later carry resource/service semantics;
- architecture §25 Future-proofing requirements;
- LOCK-001 through LOCK-003 (access/generation neutrality);
- LOCK-014 and LOCK-015 (open-world evolution, algorithm/codec agility);
- LOCK-021/022/024/025 where envelope evidence, security, resilience and compatibility interact;
- the machine-readable registries and schemas created by WORK-002.

**Do not alter any frozen architecture document.** If implementation appears to require an architectural change, stop and report the exact conflict; do not reinterpret the architecture.

---

## 3. Frozen envelope contract

The architecture §7 conceptual envelope is:

```json
{
  "protocol": "adcos",
  "version": 1,
  "message_type": "capability.advertise",
  "message_id": "...",
  "sender": "...",
  "issued_at": "...",
  "expires_at": "...",
  "correlation_id": "...",
  "extensions": {},
  "payload": {},
  "evidence": [],
  "signature": "..."
}
```

Implement this as an explicit stable envelope abstraction, not as an ad-hoc dictionary passed around the codebase.

The implementation must preserve these semantic boundaries:

- `message_id` identifies one protocol message instance.
- `correlation_id` associates messages belonging to a larger interaction and may be absent where not applicable.
- `issued_at` and `expires_at` are temporal metadata and must be validated before an envelope is accepted for processing.
- `sender` is an identity reference; do not invent crypto identity semantics owned by WORK-004.
- `signature` is metadata/opaque material only in WORK-003. Do not implement trust policy, key management, credential issuance, rotation, revocation, or signature verification policy here; those belong to later Work Items.
- `payload` is typed application/protocol content whose detailed message schemas will expand in later Work Items.
- `extensions` is explicitly forward-compatibility surface area.
- `evidence` is an opaque/reference-bearing field at this stage; provenance semantics remain grounded in WORK-002 and later evidence/trust work.

Do not turn the envelope into a 5G envelope, a 6G envelope, a vendor envelope, or a transport-specific frame.

---

## 4. Protocol versioning model

Preserve the separation established by WORK-001/002:

```text
Architecture Version
        ≠
Protocol Version
        ≠
Schema Version
        ≠
Implementation Version
```

WORK-003 owns the **protocol version line and envelope compatibility semantics**. It does not change the Architecture Version.

The implementation must support at minimum:

- protocol major/minor representation;
- message/schema version metadata where required by the frozen contract;
- deterministic compatibility classification;
- explicit distinction between compatible additive evolution and incompatible breaking evolution.

The initial protocol version may remain the frozen conceptual `1`/v1 baseline where the repository has not yet frozen a more granular wire numbering format. Do not invent a multi-dimensional version matrix beyond what is required for compatibility and future evolution.

Future-version behavior must be explicit:

```text
known + compatible      -> parse/process
known + additive        -> parse/preserve according to negotiated capability
unknown optional        -> preserve/forward where possible
unknown required        -> fail safely
incompatible major      -> reject safely
malformed               -> reject safely
expired/replayed        -> reject according to validation policy
```

Do not silently downgrade, reinterpret, coerce, or strip unknown protocol content merely to make a parser succeed.

---

## 5. Serialization requirements

Implement deterministic serialization primitives with a clean separation between the logical envelope model and concrete encodings.

Frozen architectural direction:

- **CBOR** is the initial compact wire-encoding candidate.
- **JSON** is the required human/debug encoding.
- The exact production canonicalization profile is intentionally not yet declared as a final wire-compatibility standard; later conformance work will freeze production vectors.

Therefore:

1. Do not introduce a vendor-specific serialization format.
2. Do not hard-code application semantics into the serializer.
3. Provide an abstraction that can support the initial JSON/debug representation and a compact encoding without changing envelope semantics.
4. If a third-party CBOR implementation would add a runtime dependency, do not silently make the whole project depend on it. Follow the repository's existing dependency policy and keep the core abstraction implementation-neutral unless the frozen scope explicitly permits the dependency.
5. Canonicalization must be deterministic and documented well enough that two conformant implementations can independently reproduce the same canonical representation for the supported subset.

A canonical representation must have stable:

- key ordering where the selected encoding has meaningful map ordering;
- integer/string/boolean/null representation rules;
- UTF-8 behavior;
- handling of omitted-vs-present optional members;
- extension-field preservation;
- byte/string normalization assumptions.

Do not claim production-grade cross-language canonical-wire compatibility unless the implementation proves it with golden vectors.

---

## 6. Unknown-field and extension behavior

This is a core compatibility requirement.

### Unknown optional fields

A parser that does not own an extension MUST:

- recognize that it is unknown;
- preserve it where proxying/forwarding semantics permit;
- avoid corrupting or rewriting known fields;
- avoid coercing it into an existing field or type.

### Unknown required features

Where the envelope/message requires a feature the implementation cannot understand, it must fail safely rather than silently processing an incomplete semantic message.

### Extensions namespace

Keep extension metadata isolated from frozen core fields. Do not allow an extension to overwrite or shadow a standard envelope field through parser behavior.

Support an explicit extension representation that can carry future identifiers without requiring a new core struct field for every addition.

### Unknown message types

Per architecture §7, unknown message types may be:

- rejected safely; or
- transported as opaque extensions according to negotiated policy.

Do not invent a universal “accept all unknown messages” rule. The behavior must be an explicit policy/compatibility decision in the implementation API.

---

## 7. Temporal / replay metadata

WORK-003 owns the basic validation mechanics for the envelope's temporal fields, not a full anti-replay trust system.

Implement deterministic validation for:

- `issued_at` presence/format where required;
- `expires_at` presence/format where required;
- `expires_at >= issued_at`;
- expired-message rejection;
- configurable clock-skew tolerance where appropriate;
- a clearly defined replay-validation hook or deterministic message freshness input.

Do **not** implement persistent distributed replay state, trust scoring, credential revocation, or identity/key lifecycle. Those belong elsewhere.

The API must make it impossible to accidentally process an obviously expired/malformed envelope through the normal validation path.

Avoid local-time ambiguity. Use UTC / unambiguous machine representation.

---

## 8. Correlation and message identity

Implement deterministic validation of:

- `message_id` syntax/shape according to the repository's selected identifier contract;
- uniqueness semantics as a message-instance identifier, without pretending to provide a distributed uniqueness oracle;
- optional `correlation_id` semantics;
- absence/presence rules consistent across JSON/debug and compact representations.

Do not couple `message_id` to:

- NodeID;
- access technology;
- radio bearer;
- transport connection;
- implementation process ID.

Do not invent globally authoritative identity semantics that belong to WORK-004.

---

## 9. Signature metadata boundary

WORK-003 may represent signature metadata and provide canonical bytes/input material suitable for later signing, but it must NOT implement the complete cryptographic identity/security system.

Allowed:

- structured signature metadata representation;
- algorithm/profile identifier as opaque or registry-backed metadata;
- deterministic extraction of signable/canonical bytes;
- validation of signature-field shape;
- a clean interface that WORK-004/security work can use later.

Forbidden:

- private-key storage;
- credential issuance;
- NodeID derivation;
- key rotation/revocation;
- trust-domain policy;
- authorization policy;
- vendor-specific cryptographic SDK dependencies.

Do not hard-code one cryptographic algorithm as the only future option. Preserve algorithm/profile agility.

---

## 10. Schema integration with WORK-002

Consume, do not rewrite, the registries and schemas established by WORK-002.

The implementation must reference the canonical artifacts under:

```text
spec/schemas/
```

Do not duplicate registry vocabularies in code unless a generated/validated representation is explicitly justified and mechanically derived.

Do not create a second independent source of truth for:

- core object IDs;
- access profile IDs;
- capability IDs;
- schema versions.

If generated constants are useful, make the generator deterministic and prove that the generated result corresponds exactly to the registry source.

---

## 11. Compatibility and evolution matrix

The implementation must have executable tests covering at least these cases:

1. Current known envelope parses successfully.
2. Current envelope with additional unknown optional field parses successfully.
3. Unknown optional field survives parse → serialize → parse when proxying is permitted.
4. Unknown extension identifier remains byte/value-equivalent and is never coerced to a known identifier.
5. Unknown required feature/message capability fails safely.
6. Incompatible major protocol version fails safely.
7. Additive compatible minor/schema evolution remains parseable according to the selected compatibility rules.
8. `expires_at < issued_at` fails.
9. Already-expired message fails.
10. Malformed temporal value fails.
11. Invalid/missing required envelope member fails deterministically.
12. `message_id`/`correlation_id` round-trip deterministically.
13. Canonical serialization of the same logical envelope is byte-identical across repeat runs.
14. Canonical signature-input bytes are byte-identical across repeat runs.
15. Known payload survives JSON/debug representation without semantic mutation.
16. Future profile/access identifiers from WORK-002 can appear inside supported extension/profile fields without adding 5G/6G-specific core branches.

Also add property/fuzz-style tests for parser robustness within the project's dependency constraints. Mutated/truncated/duplicated-key/malformed inputs must fail safely rather than crash the process or produce a silently altered envelope.

---

## 12. Golden vectors

Create a small, human-inspectable set of golden vectors for the supported envelope representation(s).

At minimum include:

- minimal valid envelope;
- representative message with payload + evidence + correlation;
- unknown-extension envelope;
- expiration boundary cases;
- incompatible-version envelope;
- canonical signature-input material.

Golden vectors must live in a stable repository location and be deterministic.

Do not freeze a production wire profile merely by placing a vector in the repository; document clearly what is provisional vs. normative until later conformance work freezes the exact canonical wire profile.

---

## 13. API / module boundaries

Keep the implementation split into explicit responsibilities, for example:

```text
Envelope model
Protocol versioning
Validation
Compatibility classification
Extension preservation
Canonicalization
JSON/debug codec
Compact codec abstraction / CBOR adapter boundary
Signature-input material
Temporal validation
Golden-vector loader
```

The exact language/module names are implementation choices, but the architecture boundary is not.

Do not couple envelope parsing to routing, topology, discovery, session management, adapters, 5G, Wi-Fi, SDRs, or vendor SDKs.

No runtime network daemon is part of WORK-003.

---

## 14. Dependency and scope locks

This Work Item has exactly one dependency:

```text
WORK-002
```

Do not modify `spec/work-items.md` or `spec/dependency-graph.md` to add or remove dependencies.

The three known architecture-owned dependency advisories from WORK-001 remain unresolved:

- WORK-008 → WORK-007
- WORK-014 → WORK-017
- WORK-021 → WORK-019

Do not resolve them in this Work Item.

Explicitly out of scope:

- WORK-004 cryptographic node identity implementation;
- WORK-005 capability advertisement/negotiation runtime;
- discovery/topology/routing/session/mobility runtime;
- resource allocation/policy engine;
- access adapters;
- 5G/6G/IMT-specific integration;
- Agent networking daemon;
- persistence/database infrastructure;
- UI/application work;
- blockchain/token economics.

---

## 15. Required verification

Before opening the PR, run and report exact commands/results for:

1. `python3 tools/spec_check.py`
2. `python3 tools/spec_check_selftest.py`
3. all WORK-003 schema/envelope tests
4. golden-vector verification
5. fuzz/property/robustness tests
6. `python3 -m py_compile ...` for all introduced Python tooling, if Python tooling is used
7. `mypy ...` for introduced typed Python tooling, if applicable
8. repository-relevant static analysis/type checking for whatever implementation language is chosen
9. deterministic repeat-run comparison for canonical outputs
10. frozen-document drift check:

```bash
git diff origin/main -- \
  spec/architecture.md \
  spec/architecture-lock.md \
  spec/work-items.md \
  spec/dependency-graph.md \
  spec/prompts/WORK-001.md \
  spec/prompts/WORK-002.md
```

That diff must be empty relative to the accepted baseline.

CI must execute the appropriate WORK-003 verification suite on every PR.

---

## 16. Stop conditions

Stop implementation and report to the Architect instead of making an architectural assumption if any of these occur:

- a stable envelope field needs to be added beyond the frozen §7 contract and the reason is semantic rather than implementation detail;
- a protocol/version rule requires changing the frozen architecture;
- a serializer requires a technology-specific core field;
- unknown-field compatibility cannot be achieved without altering the frozen architecture;
- a required crypto decision conflicts with the WORK-004 boundary;
- production CBOR canonicalization semantics cannot be implemented without claiming an unfrozen standard;
- a dependency on WORK-004 or later is needed for WORK-003 correctness;
- implementation requires changing a frozen Work Item or dependency graph;
- any test requires internet access or an external service when an offline deterministic test should be possible.

Do not solve these by inventing architecture.

---

## 17. PR requirements

Open exactly one PR for WORK-003.

Required PR title:

```text
feat(WORK-003): versioned protocol envelope and serialization
```

The PR body must contain exactly these sections, in order:

1. `## WORK-003`
2. `## Objective`
3. `## Architecture sections implemented`
4. `## Dependencies`
5. `## Acceptance criteria mapping`
6. `## Verification`
7. `## Files changed`
8. `## Out of scope`
9. `## Architecture lock compliance`
10. `## No architecture drift`
11. `## Known limitations`

For every acceptance criterion, map it to concrete files/tests/evidence.

Leave the PR open and unmerged. The Architect performs the acceptance review.

---

## 18. Final implementation principle

The implementation goal is not to create a serializer that merely works today.

The goal is to create the smallest stable wire-envelope foundation that lets ADCOS evolve from the current protocol baseline through future access generations — including 6G/IMT-2030 and technologies not yet imagined — without changing the core envelope semantics every time a new radio, codec, field, capability, or deployment environment appears.

**Architecture first. Code second. Compatibility is a first-class invariant.**