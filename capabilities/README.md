# ADCOS Capabilities Package — WORK-005

## Status

**ACTIVE — Capability Statements and Negotiation**
**M003 refactor (Architecture 1.1, R7-CORE-001): provider-domain
advertisement seam added — see the end of this README.**

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
  advertisement.py   M003: provider-domain advertisement seam (see below)
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
- **Verification** (`verify_statement`) is time-aware and provenance-bound:
  the caller injects the evaluation instant (no wall clock — fully
  deterministic), and the verifier checks that (1) the credential's
  WORK-004 record belongs to the SAME NodeID as the statement's
  `provider_identity` (cross-node forgery rejected), (2) the credential's
  lifecycle is usable AT the injected instant — ACTIVE status, not revoked,
  and not expired (`expires_at <= now` is rejected, mirroring
  `IdentityService._require_active`; an ACTIVE-but-expired credential has a
  byte-correct signature but is rejected because the key was no longer
  usable at the claimed instant), and (3) the signature is byte-exact over
  the canonical content. This verifies PROVENANCE — never truth, trust, or
  authorization.
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
python3 tools/capability_selftest.py   # deterministic cases (all required tests + the M003 seam)
```

CI runs this suite with all prior suites. All key material is TEST-ONLY;
all clocks are injected; seeded PRNGs make runs byte-identical.

## M003 refactor — the provider-domain advertisement seam

Migration classification (frozen `spec/migration/classification-matrix.md`):
**"Capability registry: RETAIN + REFACTOR → Offer/capability exchange."**

- **RETAINED (untouched):** the statement model and its frozen §6.4 field
  shape; the registry-backed classification (the single vocabulary
  authority); validity evaluation; deterministic negotiation; signing and
  verification through the WORK-004 provider seam; canonical serialization.
  All WORK-005 acceptance semantics and public surface stay in force —
  every existing dependent (negotiation consumers, topology ingest,
  conformance vectors, adapters, federation onboarding) is unaffected.
- **REFACTORED (added): `advertisement.py`** — the provider-domain
  advertisement seam for the Architecture 1.1 offer exchange (M003,
  `offers/`): `advertisement_entry(statement)` projects ONE verified
  statement into a typed entry (capability id, schema version, provider
  identity, the content digest over the statement's canonical bytes, and
  the registry classification carried verbatim as DATA);
  `advertisement_entries(statements, now=...)` projects the batch of
  currently-ACTIVE statements at the injected instant, deterministically
  sorted by the data model, failing closed on ambiguous same-key content.
  The seam never classifies on its own authority (classification flows
  from the registry), never re-signs or re-verifies (callers verify
  statements first — the digest binds the entry to the exact statement
  bytes), and never judges trust, authorization, or availability (the
  statement boundary is unchanged).
- **Demoted (explicitly out of the 1.1 seam):** nothing — the peer
  negotiation surface stays as-is; provider advertisement grounding is
  ADDITIVE on top of it.

The offers domain (M003) consumes these entries as the grounding material
of `CapabilityAdvertisement` records; it never re-classifies capability
ids (no second vocabulary authority — this package stays the
classification authority).
