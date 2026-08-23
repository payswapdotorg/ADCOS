# ADCOS Envelope Golden Vectors — WORK-003

## Status

**PROVISIONAL — regression locks, not a frozen wire profile**

These vectors are deterministic regression locks for the WORK-003 envelope
representation(s): each stores the logical envelope, the expected canonical
JSON bytes, the expected compact (deterministic-CBOR-profile) bytes, the
expected canonical signature-input bytes, and the expected validation
outcome at a fixed validation time.

Placing these vectors in the repository does **not** freeze a production
wire profile: `spec/architecture.md` §7 deliberately leaves the exact
production canonicalization profile to later conformance work before
production wire compatibility is declared. The compact-codec bytes here
exercise the provisional deterministic-CBOR-profile codec; if the
production profile later diverges, these vectors are updated by that
conformance Work Item (with synchronized schema/registry versions).

## Catalog

| Vector | Verifies |
|---|---|
| `minimal-valid` | minimal valid envelope; canonical JSON/CBOR/signature-input bytes |
| `representative-message` | payload + evidence + correlation + structured signature metadata |
| `unknown-extension-preserved` | non-critical unknown extension preserved verbatim (known_additive) |
| `unknown-critical-extension` | `"required": true` unknown extension fails safely |
| `expiry-boundary-valid` | `expires_at == now` is not yet expired |
| `expiry-boundary-expired` | `expires_at == now - 1s` is expired |
| `expired-message` | typical expired message rejected |
| `incompatible-major-version` | protocol major 2 rejected safely |
| `signature-input-material` | canonical signature-input basis (signature member omitted) |
| `unknown-type-forward-opaque` | unregistered message type forwarded opaquely under explicit policy |
| `future-access-profile-ids` | WORK-002 access-profile IDs (incl. reserved IMT-2030 and unknown future) as opaque data |
| `inverted-temporal-window` | `expires_at < issued_at` rejected |
| `malformed-message-type` | grammar-violating message type rejected as malformed |

Vector files use the repository canonical JSON form (sorted keys, 2-space
indent); the `expected` blocks reference the **wire** canonical JSON form
(compact) — the loader asserts both mechanically. All vectors carry
`"status": "provisional"`.

Verification: `python3 tools/envelope_selftest.py` (golden-vectors-verified,
golden-vectors-compact-roundtrip).
