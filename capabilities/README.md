# ADCOS Capabilities Package — WORK-005

## Status

**ACTIVE — Capability Statements and Negotiation**

Implements signed, versioned capability advertisements and deterministic
negotiation per `spec/architecture.md` §6.4 and the WORK-005 handoff.

**The central boundary (enforced throughout):**

```text
Capability statement  ≠  truth  ≠  trust  ≠  authorization
                      ≠  topology authority
```

A capability statement is a CLAIM about what a node/adapter may provide.
A signature establishes an ATTRIBUTABLE statement (provenance) — never
truth, availability, authorization, or trust. Evidence references stay
opaque references; remote summaries remain claims by their reporter
(LOCK-008). Negotiation answers only *what mutually understood capability
both parties support* — never *whether the peer is trusted or authorized*
(WORK-010+).

## Module map

```text
capabilities/
  model.py           CapabilityStatement (frozen §6.4 fields) + withdrawal
  classification.py  KNOWN / UNKNOWN_BUT_WELL_FORMED / INVALID (registry-backed)
  registry.py        Read-only view over the WORK-002 capability registry
  validity.py        ACTIVE / NOT_YET_VALID / EXPIRED / WITHDRAWN (WORK-003 temporal)
  negotiation.py     Deterministic negotiation + explicit rejection reasons
  signing.py         Signature input via WORK-003 canonicalization; WORK-004 provider seam
  serialization.py   Canonical JSON via WORK-003 machinery; duplicate-key rejection
```

## Key semantics

- **Identifier authority**: the WORK-002 capability registry is the single
  vocabulary authority — loaded, never duplicated in code (proven by
  `no-duplicated-vocabulary-in-code`). Unknown well-formed identifiers are
  UNKNOWN_BUT_WELL_FORMED: preserved verbatim, safely ignorable when
  optional, an explicit `unknown-required-capability` failure when
  required. Malformed identifiers fail closed.
- **Statements** follow frozen §6.4: capability_id, schema_version
  (MAJOR.MINOR), provider_identity (a canonical WORK-004 NodeID — validated
  through `identity.node_id.parse_node_id`, never a duplicated grammar;
  arbitrary strings and near-miss forms fail closed), validity interval
  (valid_from/expires_at; WORK-003 RFC 3339 UTC), parameters and
  constraints (open-world typed data — never technology-specific core
  semantics), evidence references (opaque), signature (opaque), and an
  explicit withdrawal state. Serialization matches the WORK-002
  `capability.schema.json` field shape (validity nested).
- **Signing** covers the canonical security-critical content — provider
  identity, capability id, schema version, validity, parameters,
  constraints, evidence references, withdrawal state — through the WORK-003
  canonical signature-input machinery and the WORK-004 provider seam.
  Tampering with ANY covered member invalidates the signature. No key
  material ever enters this layer.
- **Lifecycle**: withdrawal (explicit act) and expiry (time-based) are
  DISTINCT terminal-for-usability states; neither negotiates as currently
  usable; historical statements remain queryable for audit. Neither is a
  node-identity revocation or a trust judgment.
- **Negotiation** is deterministic: injected evaluation instant, sorted
  iteration, tie-breaking by the data model (schema version descending,
  then provider identity, valid_from, signature) — stable under input
  reordering and repeat runs. Requirements are required-vs-optional;
  parameter/constraint expectations compare only defined semantics
  (numeric ≥ capacity-style, exact equality otherwise, recursive objects);
  unsupported required values fail explicitly, never silently satisfied.
  Rejection reasons are stable, explicit, and DISTINCT: unknown-required-
  capability, malformed-capability-id, version-incompatible,
  parameter-mismatch (required parameters unsatisfied), constraint-mismatch
  (parameters satisfied but required constraints unsatisfied), and
  no-active-statement. When both dimensions fail, parameters are reported
  first (deterministic order); optional requirements surface the distinct
  reason non-fatally in the outcome detail.

## Verification

```bash
python3 tools/capability_selftest.py   # 11 deterministic cases (20 required tests)
```

CI runs this suite with all prior suites. All key material is TEST-ONLY;
all clocks are injected; seeded PRNGs make runs byte-identical.
