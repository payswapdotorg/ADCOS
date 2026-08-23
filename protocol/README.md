# ADCOS Protocol Package — WORK-003

## Status

**ACTIVE — Versioned Protocol Envelope and Serialization (Protocol Version 1.0)**

This package implements the stable wire-message envelope and the
implementation-independent serialization/versioning primitives of
`spec/architecture.md` §7, driven by the machine-readable protocol
artifact `spec/schemas/protocol.json`. It establishes the wire contract's
evolution foundation: protocol evolution without a flag day.

**WORK-003 does not implement runtime networking.** There is no transport,
no routing, no trust policy, no cryptographic identity, and no daemon
here — only the envelope model, deterministic serialization, compatibility
classification, and validation mechanics that later Work Items consume.

## Module map

```text
protocol/
  envelope.py          Envelope model — frozen §7 fields + unknown-field preservation
  versioning.py        Protocol version line, known majors, message-type registry (loaded from spec/schemas/protocol.json)
  validation.py        Deterministic validation pipeline + acceptance path (ValidatedEnvelope gating)
  temporal.py          RFC 3339 UTC instants; expiry / not-yet-valid / skew; replay hook
  canonicalization.py  Deterministic canonical JSON (RFC 8785-style subset)
  codec.py             WireCodec abstraction + codec registry
  codec_json.py        JSON debug codec (canonical JSON bytes; duplicate-key rejection)
  codec_cbor.py        PROVISIONAL deterministic-CBOR-profile compact codec (RFC 8949 §4.2 subset)
  signature.py         Canonical signature-input material (signature member excluded)
  vectors.py           Golden-vector loader
  vectors/             Golden vectors (see vectors/README.md)
```

## Key semantics

- **Envelope fields** follow frozen architecture §7 exactly. `correlation_id` is
  the only optional known member. Any other top-level member is an *unknown
  optional field*, preserved verbatim in `Envelope.extra` and round-tripped
  byte-identically. Extensions live in `extensions` and are likewise preserved;
  an extension entry whose value is an object carrying `"required": true` is a
  required-to-understand extension — processors that do not understand it fail
  safely (`rejected_unknown_required`).
- **No shadowing**: extension or unknown content can never overwrite or coerce
  a known envelope field; duplicate keys are rejected at parse.
- **Protocol versioning**: the wire carries the protocol major (frozen §7
  baseline `version: 1`); the MAJOR.MINOR protocol version line is declared in
  `spec/schemas/protocol.json` and is distinct from the Architecture, Schema,
  and Implementation versions. Unknown majors are rejected safely
  (`rejected_incompatible_major`); additive evolution within a known major is
  preserved (`known_additive`).
- **Message types**: the grammar and the registered types come from
  `spec/schemas/protocol.json` (currently `capability.advertise`, the type named
  by architecture §7; payload semantics are owned by WORK-005). Well-formed
  unregistered types are handled per the **explicit policy** supplied by the
  caller — `REJECT` or `FORWARD_OPAQUE` — never a universal accept-all rule.
- **Temporal validation**: RFC 3339 UTC (`Z` only, no local-time ambiguity);
  `expires_at >= issued_at`; expired and not-yet-valid rejection with
  configurable clock skew; a caller-supplied replay-validation hook (no
  distributed replay state in WORK-003). `ValidatedEnvelope` is obtainable only
  through the validation path, so expired/malformed envelopes cannot be
  accidentally processed.
- **Signature boundary**: signature material is metadata only — opaque string
  or `{algorithm, value}` object (LOCK-015 agility; no algorithm hard-coded).
  `signature_input_bytes(envelope)` yields deterministic canonical bytes
  (canonical JSON with the `signature` member omitted) for later signing.
  Keys, verification, and trust policy belong to WORK-004+.
- **Canonicalization** (provisional, documented in
  `protocol/canonicalization.py`): UTF-16 code-unit key ordering, minimal
  escaping, no whitespace, shortest-decimal integers, floats outside the
  subset (fail safely), absent ≠ null.
- **Compact codec status**: `codec_cbor.py` implements RFC 8949 §4.2 core
  deterministic encoding for the supported subset and is **PROVISIONAL — not
  the frozen production canonicalization profile**. Architecture §7 leaves
  the production profile to later conformance work. `tools/schema_check.py`
  (SCHEMA-07) mechanically rejects any attempt to mark the compact codec
  normative in `spec/schemas/protocol.json` prematurely.

## Usage sketch

```python
import protocol
from protocol import ParsePolicy, UnknownTypePolicy, validation_clock

outcome = protocol.accept(
    encoded_bytes,
    now=validation_clock("2030-01-01T00:00:00Z"),
    policy=ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE),
)
if outcome.accepted:
    process(outcome.validated)  # ValidatedEnvelope — the only accepted form
```

## Verification

```bash
python3 tools/envelope_selftest.py   # 16-case compatibility matrix + golden vectors + property/fuzz
```

CI runs this suite together with the WORK-001/002 suites on every push and
pull request. All tests are deterministic (seeded PRNGs, byte-identical
repeat runs) and fully offline.
